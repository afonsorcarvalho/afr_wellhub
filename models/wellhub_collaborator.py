# -*- coding: utf-8 -*-
"""Colaborador Wellhub: cadastro local; assinatura ativa dispara assinatura recorrente no Asaas."""

import json
import logging
import secrets
import threading
import time
from datetime import timedelta

import odoo
from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Status de cobrança Asaas considerados pagos (documentação; eventos PAYMENT_CONFIRMED / RECEIVED).
_ASAAS_PAYMENT_STATUSES_PAID = frozenset({"RECEIVED", "CONFIRMED"})


class WellhubCollaborator(models.Model):
    _name = "wellhub.collaborator"
    _description = "Colaborador Wellhub"

    name = fields.Char(string="Nome", required=True)
    email = fields.Char(string="E-mail", required=True)
    phone = fields.Char(string="Telefone", required=True)
    cpf_cnpj = fields.Char(
        string="CPF/CNPJ",
        required=True,
        help="Obrigatório para cadastro do cliente no Asaas (API exige cpfCnpj).",
    )
    # Endereço — exigido pelo Asaas Checkout (POST /v3/checkouts) em customerData.address,
    # addressNumber, postalCode e province. Mantido opcional no modelo para compatibilidade
    # com colaboradores antigos cadastrados via backend; validado como obrigatório só no
    # fluxo do portal (controllers/portal_wellhub.py).
    street = fields.Char(string="Logradouro")
    street_number = fields.Char(string="Número")
    postal_code = fields.Char(string="CEP")
    city = fields.Char(string="Cidade")
    state_uf = fields.Selection(
        selection=[
            ("AC", "Acre"), ("AL", "Alagoas"), ("AP", "Amapá"), ("AM", "Amazonas"),
            ("BA", "Bahia"), ("CE", "Ceará"), ("DF", "Distrito Federal"),
            ("ES", "Espírito Santo"), ("GO", "Goiás"), ("MA", "Maranhão"),
            ("MT", "Mato Grosso"), ("MS", "Mato Grosso do Sul"), ("MG", "Minas Gerais"),
            ("PA", "Pará"), ("PB", "Paraíba"), ("PR", "Paraná"), ("PE", "Pernambuco"),
            ("PI", "Piauí"), ("RJ", "Rio de Janeiro"), ("RN", "Rio Grande do Norte"),
            ("RS", "Rio Grande do Sul"), ("RO", "Rondônia"), ("RR", "Roraima"),
            ("SC", "Santa Catarina"), ("SP", "São Paulo"), ("SE", "Sergipe"),
            ("TO", "Tocantins"),
        ],
        string="UF",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Empresa",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    active = fields.Boolean(default=True)

    # Inscrição via website: aguarda clique no link do e-mail antes de criar assinatura Asaas.
    signup_pending = fields.Boolean(
        string="Inscrição aguardando confirmação por e-mail",
        default=False,
        help="Quando verdadeiro, o colaborador preencheu o formulário público mas ainda não ativou o link enviado ao e-mail.",
    )
    signup_token = fields.Char(
        string="Token de ativação",
        copy=False,
        index=True,
        groups="afr_wellhub.group_afr_wellhub_manager",
        help="Exibido apenas enquanto a confirmação por e-mail está pendente; apagado após o uso.",
    )
    signup_token_expiry = fields.Datetime(
        string="Validade do token de inscrição",
        copy=False,
        groups="afr_wellhub.group_afr_wellhub_manager",
        help="Preenchido enquanto a inscrição aguarda confirmação; limpo após o uso do link.",
    )
    signup_email_confirmed_at = fields.Datetime(
        string="Inscrição confirmada por e-mail em",
        readonly=True,
        copy=False,
        groups="afr_wellhub.group_afr_wellhub_manager",
        help="Data/hora em que o colaborador abriu o link de ativação enviado ao e-mail. "
        "O token é removido após a confirmação por segurança.",
    )
    signup_mail_activation_url = fields.Char(
        string="URL de ativação (e-mail)",
        compute="_compute_signup_mail_activation_url",
        help="Montada para o template de e-mail (web.base.url + token).",
    )
    portal_inscription = fields.Boolean(
        string="Inscrição pelo portal",
        default=False,
        copy=False,
        help="Marcado quando o cadastro veio do formulário público de inscrição. "
        "Usado para enviar groupName «Wellhub» ao criar/atualizar o cliente no Asaas "
        "(campo groupName na API; documentação: CustomerSaveRequestDTO).",
    )

    wellhub_subscription_enrolled = fields.Boolean(
        string="Contrato assinatura Asaas (recorrência)",
        default=False,
        help="Quando ativo, o Odoo cria cliente e Assinatura no Asaas (POST /v3/subscriptions) "
        "e passam a ser geradas cobranças. O campo «Assinatura Wellhub ativa» abaixo só fica "
        "verdadeiro quando houver cobrança da assinatura paga (status RECEIVED ou CONFIRMED na API) "
        "e não houver inadimplência pela regra definida no código.",
    )
    wellhub_subscription_active = fields.Boolean(
        string="Assinatura Wellhub ativa",
        compute="_compute_wellhub_subscription_status",
        store=True,
        readonly=True,
        help="Verdadeiro quando o contrato Asaas está ativo, há pelo menos uma cobrança da "
        "assinatura paga no Asaas (RECEIVED ou CONFIRMED) e não há cobrança em atraso "
        "(OVERDUE ou PENDING vencida). Atualizado ao sincronizar cobranças (cron ou manual).",
    )
    wellhub_external_id = fields.Char(
        string="ID externo Wellhub",
        help="Reservado para integração futura com a API Wellhub.",
    )
    wellhub_last_sync = fields.Datetime(
        string="Última sync Wellhub",
        readonly=True,
    )

    asaas_customer_id = fields.Char(string="Cliente Asaas", readonly=True)
    asaas_subscription_id = fields.Char(string="Assinatura Asaas", readonly=True)

    asaas_checkout_id = fields.Char(string="Checkout Asaas (id)", readonly=True)
    asaas_checkout_url = fields.Char(string="URL do checkout Asaas", readonly=True)
    asaas_checkout_status = fields.Selection(
        selection=[
            ("CREATED", "Criado"),
            ("PAID", "Pago"),
            ("EXPIRED", "Expirado"),
            ("CANCELED", "Cancelado"),
        ],
        string="Status do checkout Asaas",
        readonly=True,
    )
    asaas_checkout_expires_at = fields.Datetime(
        string="Checkout Asaas expira em",
        readonly=True,
    )

    subscription_value = fields.Float(
        string="Valor da assinatura (base)",
        help="Valor base do plano. Com repasse do pacote e-mail/SMS, esse valor é somado à taxa "
        "do pacote antes de calcular o gross-up do cartão (o % do cartão incide sobre o total). "
        "Com repasse da taxa do cartão e forma cartão: o alvo líquido após taxa fixa + % do Asaas "
        "é (base + pacote notif. se ativo). Se vazio, usa o padrão nas configurações.",
    )
    pass_asaas_notification_email_sms_fee = fields.Boolean(
        string="Repassar pacote e-mail/SMS (Asaas)",
        default=False,
        help="O Asaas cobra taxas por notificações de cobrança; na página pública de preços consta "
        "R$ 0,99 pelo pacote de e-mail e SMS utilizado a cada transação paga (valores podem variar — "
        "veja Minha conta > Taxas). Se ativo, esse valor (configurável em Ajustes) é somado à base "
        "da assinatura antes do cálculo da taxa percentual do cartão, para compensação ao cliente. "
        "Referência: https://docs.asaas.com/docs/notificacoes e https://www.asaas.com/precos-e-taxas",
    )
    pass_credit_card_fee_to_customer = fields.Boolean(
        string="Repassar taxa do cartão ao cliente",
        default=True,
        help="Se ativo e a forma de pagamento for cartão de crédito, o valor enviado ao Asaas "
        "compensa taxa fixa + percentual (Ajustes), conforme https://www.asaas.com/precos-e-taxas . "
        "O cálculo usa (base + pacote e-mail/SMS, se repasse de notif. ativo) como alvo antes do % . "
        "Ajuste percentuais se sua conta usar taxa promocional (ex.: 1,99%).",
    )
    asaas_net_before_card_preview = fields.Float(
        string="Base + pacote e-mail/SMS",
        compute="_compute_asaas_charge_value_preview",
        digits=(16, 2),
        help="Soma do valor base com o pacote de notificações, antes da taxa fixa e % do cartão.",
    )
    asaas_charge_value_preview = fields.Float(
        string="Valor final da cobrança no Asaas (prévia)",
        compute="_compute_asaas_charge_value_preview",
        digits=(16, 2),
        help="Valor que seria enviado ao criar a assinatura (inclui repasses de notif. e cartão, se ativos).",
    )
    billing_type = fields.Selection(
        selection=[
            ("UNDEFINED", "Indefinido"),
            ("BOLETO", "Boleto"),
            ("CREDIT_CARD", "Cartão de crédito"),
            ("PIX", "Pix"),
        ],
        string="Forma de pagamento (Asaas)",
        help="Para assinatura recorrente, use Pix, Boleto ou Cartão. "
        "Indefinido não pode ser usado com contrato de assinatura Asaas ativo. "
        "Se vazio, usa o padrão nas configurações.",
    )
    subscription_cycle = fields.Selection(
        selection=[
            ("WEEKLY", "Semanal"),
            ("BIWEEKLY", "Quinzenal"),
            ("MONTHLY", "Mensal"),
            ("BIMONTHLY", "Bimestral"),
            ("QUARTERLY", "Trimestral"),
            ("SEMIANNUALLY", "Semestral"),
            ("YEARLY", "Anual"),
        ],
        string="Periodicidade",
        help="Se vazio, usa o padrão nas configurações.",
    )
    next_due_date = fields.Date(
        string="Primeiro vencimento",
        help="Usado na criação da assinatura no Asaas (nextDueDate). Se vazio, usa a data de hoje.",
    )

    # Desconto, juros e multa na assinatura (POST /v3/subscriptions — documentação Asaas).
    asaas_discount_type = fields.Selection(
        selection=[
            ("none", "Sem desconto"),
            ("PERCENTAGE", "Percentual sobre a cobrança"),
            ("FIXED", "Valor fixo (R$)"),
        ],
        string="Tipo de desconto (Asaas)",
        default="none",
    )
    asaas_discount_value = fields.Float(
        string="Valor do desconto",
        help="Percentual ou valor em R$, conforme o tipo. Só enviado ao Asaas se o tipo estiver definido.",
    )
    asaas_discount_due_date_limit_days = fields.Integer(
        string="Desconto: dias antes do vencimento",
        default=0,
        help="0 = até o vencimento; 1 = até um dia antes (campo dueDateLimitDays da API).",
    )
    asaas_interest_monthly_percent = fields.Float(
        string="Juros ao mês (%)",
        help="Percentual de juros ao mês sobre o valor da cobrança após o vencimento (API: interest.value).",
    )
    asaas_fine_type = fields.Selection(
        selection=[
            ("none", "Sem multa"),
            ("PERCENTAGE", "Percentual sobre a cobrança"),
            ("FIXED", "Valor fixo (R$)"),
        ],
        string="Tipo de multa (Asaas)",
        default="none",
    )
    asaas_fine_value = fields.Float(
        string="Valor da multa",
        help="Percentual ou valor fixo conforme o tipo de multa.",
    )

    payment_ids = fields.One2many(
        "wellhub.asaas.payment",
        "collaborator_id",
        string="Cobranças Asaas",
    )
    payment_count = fields.Integer(compute="_compute_payment_count")

    # Inadimplência: contrato Asaas ativo e (OVERDUE OU PENDING com vencimento anterior a hoje).
    is_delinquent = fields.Boolean(
        string="Inadimplente",
        compute="_compute_wellhub_subscription_status",
        store=True,
        help="Contrato assinatura Asaas ativo e cobrança em atraso conforme regra no código.",
    )
    is_adimplente_active = fields.Boolean(
        string="Adimplente (assinatura ativa)",
        compute="_compute_wellhub_subscription_status",
        store=True,
        help="Igual a «Assinatura Wellhub ativa»: cobrança paga e sem atraso na regra atual.",
    )

    @api.depends(
        "wellhub_subscription_enrolled",
        "asaas_subscription_id",
        "payment_ids.status",
        "payment_ids.due_date",
        "payment_ids.asaas_subscription_id",
    )
    def _compute_wellhub_subscription_status(self):
        today = fields.Date.context_today(self)
        for rec in self:
            delinquent = False
            has_paid = False
            sub_id = (rec.asaas_subscription_id or "").strip()
            if rec.wellhub_subscription_enrolled and sub_id:
                for pay in rec.payment_ids:
                    st = (pay.status or "").upper()
                    if st == "OVERDUE":
                        delinquent = True
                        break
                    if st == "PENDING" and pay.due_date and pay.due_date < today:
                        delinquent = True
                        break
                if not delinquent:
                    for pay in rec.payment_ids:
                        if (pay.asaas_subscription_id or "").strip() != sub_id:
                            continue
                        if (pay.status or "").upper() in _ASAAS_PAYMENT_STATUSES_PAID:
                            has_paid = True
                            break
            active = (
                rec.wellhub_subscription_enrolled
                and bool(sub_id)
                and has_paid
                and not delinquent
            )
            rec.is_delinquent = delinquent
            rec.wellhub_subscription_active = active
            rec.is_adimplente_active = active

    @api.depends("payment_ids")
    def _compute_payment_count(self):
        for rec in self:
            rec.payment_count = len(rec.payment_ids)

    @api.depends("signup_token")
    def _compute_signup_mail_activation_url(self):
        base = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("web.base.url", "")
            or ""
        ).rstrip("/")
        for rec in self:
            if rec.signup_token and base:
                rec.signup_mail_activation_url = (
                    f"{base}/afr_wellhub/inscricao/ativar?token={rec.signup_token}"
                )
            else:
                rec.signup_mail_activation_url = ""

    @api.constrains("signup_pending", "wellhub_subscription_enrolled")
    def _check_signup_pending_vs_subscription(self):
        for rec in self:
            if rec.signup_pending and rec.wellhub_subscription_enrolled:
                raise ValidationError(
                    _(
                        "Não é possível ter inscrição pendente e contrato de assinatura Asaas ao mesmo tempo."
                    )
                )

    @api.depends(
        "subscription_value",
        "billing_type",
        "pass_credit_card_fee_to_customer",
        "pass_asaas_notification_email_sms_fee",
    )
    def _compute_asaas_charge_value_preview(self):
        api = self.env["afr.wellhub.asaas.api"]
        for rec in self:
            try:
                rec.asaas_net_before_card_preview = round(
                    float(api.subscription_net_before_card_fee_for_asaas(rec)),
                    2,
                )
                rec.asaas_charge_value_preview = api.subscription_value_for_asaas(rec)
            except Exception:
                rec.asaas_net_before_card_preview = 0.0
                rec.asaas_charge_value_preview = 0.0

    @api.constrains("email")
    def _check_email(self):
        for rec in self:
            if rec.email and "@" not in rec.email:
                raise ValidationError(_("Informe um e-mail válido."))

    def _asaas_external_reference(self):
        self.ensure_one()
        return f"afr_wh_{self.id}"

    def _asaas_subscription_external_reference(self):
        """Referência externa só da assinatura (distinta do cliente) para o Asaas."""
        self.ensure_one()
        return f"afr_wh_sub_{self.id}"

    def _get_effective_billing_type(self):
        """Forma de pagamento efetiva (campo do colaborador ou padrão nas configurações)."""
        self.ensure_one()
        if self.billing_type:
            return self.billing_type
        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("afr_wellhub.default_billing_type", "PIX")
            or "PIX"
        )

    def _asaas_subscription_discount_interest_fine_payload(self):
        """Monta discount, interest e fine para o JSON da assinatura Asaas (somente se preenchidos)."""
        self.ensure_one()
        extra = {}
        dtype = self.asaas_discount_type or "none"
        if dtype in ("PERCENTAGE", "FIXED") and (self.asaas_discount_value or 0) > 0:
            extra["discount"] = {
                "type": dtype,
                "value": float(self.asaas_discount_value),
                "dueDateLimitDays": int(self.asaas_discount_due_date_limit_days or 0),
            }
        if (self.asaas_interest_monthly_percent or 0) > 0:
            extra["interest"] = {
                "value": float(self.asaas_interest_monthly_percent),
            }
        ftype = self.asaas_fine_type or "none"
        if ftype in ("PERCENTAGE", "FIXED") and (self.asaas_fine_value or 0) > 0:
            extra["fine"] = {
                "type": ftype,
                "value": float(self.asaas_fine_value),
            }
        return extra

    @api.constrains(
        "asaas_discount_type",
        "asaas_discount_value",
        "asaas_fine_type",
        "asaas_fine_value",
        "asaas_interest_monthly_percent",
    )
    def _check_asaas_discount_interest_fine(self):
        for rec in self:
            dtype = rec.asaas_discount_type or "none"
            if dtype in ("PERCENTAGE", "FIXED"):
                if not rec.asaas_discount_value or rec.asaas_discount_value <= 0:
                    raise ValidationError(
                        _("Com tipo de desconto definido, informe um valor de desconto positivo.")
                    )
            elif dtype == "none" and (rec.asaas_discount_value or 0) > 0:
                raise ValidationError(
                    _("Para usar desconto, selecione o tipo (percentual ou valor fixo).")
                )
            ftype = rec.asaas_fine_type or "none"
            if ftype in ("PERCENTAGE", "FIXED"):
                if not rec.asaas_fine_value or rec.asaas_fine_value <= 0:
                    raise ValidationError(
                        _("Com tipo de multa definido, informe um valor de multa positivo.")
                    )
            elif ftype == "none" and (rec.asaas_fine_value or 0) > 0:
                raise ValidationError(
                    _("Para usar multa, selecione o tipo (percentual ou valor fixo).")
                )
            if (rec.asaas_interest_monthly_percent or 0) < 0:
                raise ValidationError(_("Juros ao mês não pode ser negativo."))

    @api.constrains("asaas_subscription_id")
    def _check_asaas_subscription_id_format(self):
        """Garante que o id armazenado seja de assinatura (sub_), não de cobrança avulsa (pay_)."""
        for rec in self:
            sid = (rec.asaas_subscription_id or "").strip()
            if sid and not sid.startswith("sub_"):
                raise ValidationError(
                    _(
                        "O campo 'Assinatura Asaas' deve conter o id de uma assinatura "
                        "(prefixo sub_). Valores como pay_ indicam cobrança avulsa e não "
                        "devem ser gravados aqui."
                    )
                )

    @api.constrains("wellhub_subscription_enrolled", "billing_type")
    def _check_billing_for_recurring_subscription(self):
        for rec in self:
            if not rec.wellhub_subscription_enrolled:
                continue
            billing = rec._get_effective_billing_type()
            if billing == "UNDEFINED":
                raise ValidationError(
                    _(
                        "Para criar assinatura recorrente no Asaas, defina a forma de pagamento "
                        "como Pix, Boleto ou Cartão (no colaborador ou nas configurações padrão). "
                        "O valor 'Indefinido' não é permitido com contrato de assinatura Asaas ativo."
                    )
                )

    @api.model
    def default_get(self, fields_list):
        """Preenche desconto, juros e multa a partir do bloco Assinaturas (padrão) em Ajustes."""
        res = super().default_get(fields_list)
        defs = self._get_assinaturas_default_discount_interest_fine()
        for fname, val in defs.items():
            if fname in fields_list:
                res[fname] = val
        return res

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get("afr_wellhub_skip_asaas_sync"):
            return res
        if any(
            k in vals
            for k in (
                "wellhub_subscription_enrolled",
                "name",
                "email",
                "phone",
                "cpf_cnpj",
                "subscription_value",
                "billing_type",
                "subscription_cycle",
                "next_due_date",
                "pass_credit_card_fee_to_customer",
                "pass_asaas_notification_email_sms_fee",
                "asaas_discount_type",
                "asaas_discount_value",
                "asaas_discount_due_date_limit_days",
                "asaas_interest_monthly_percent",
                "asaas_fine_type",
                "asaas_fine_value",
            )
        ):
            self._sync_asaas_subscription_state()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get("afr_wellhub_skip_asaas_sync"):
            records._sync_asaas_subscription_state()
        return records

    def _sync_asaas_subscription_state(self):
        """Ativação: cria cliente + (checkout se portal, senão assinatura direto). Desativação: remove assinatura no Asaas."""
        api = self.env["afr.wellhub.asaas.api"]
        for rec in self:
            if not rec.id:
                continue
            if rec.wellhub_subscription_enrolled:
                if rec.asaas_subscription_id:
                    continue
                if rec.portal_inscription:
                    # Fluxo portal: subscription nasce no webhook CHECKOUT_PAID; aqui só
                    # garantimos customer e checkout válido.
                    try:
                        customer_id = api.customer_ensure(rec)
                        rec.with_context(afr_wellhub_skip_asaas_sync=True).write(
                            {"asaas_customer_id": customer_id}
                        )
                        rec._ensure_active_checkout()
                    except UserError:
                        raise
                    except Exception as e:
                        raise UserError(
                            _("Não foi possível criar o checkout no Asaas: %s") % str(e)
                        ) from e
                    continue
                try:
                    customer_id = api.customer_ensure(rec)
                    sub = api.subscription_create(rec, customer_id)
                    sub_id = sub.get("id") or ""
                    rec.with_context(afr_wellhub_skip_asaas_sync=True).write(
                        {
                            "asaas_customer_id": customer_id,
                            "asaas_subscription_id": sub_id,
                        }
                    )
                except UserError:
                    raise
                except Exception as e:
                    raise UserError(
                        _("Não foi possível criar a assinatura no Asaas: %s") % str(e)
                    ) from e
            else:
                if rec.asaas_subscription_id:
                    try:
                        api.subscription_delete(rec.asaas_subscription_id)
                    except UserError as e:
                        raise UserError(
                            _(
                                "Não foi possível cancelar a assinatura no Asaas. "
                                "Verifique a configuração ou o painel Asaas. Detalhes: %s"
                            )
                            % e
                        ) from e
                    rec.with_context(afr_wellhub_skip_asaas_sync=True).write(
                        {"asaas_subscription_id": False}
                    )

    def _ensure_active_checkout(self):
        """Retorna URL do checkout vigente; reusa se ainda válido (CREATED + não expirado), senão cria novo.

        Garante `asaas_customer_id` populado localmente antes da criação do checkout — sem isso,
        as ações de backend ("Sincronizar cobranças Asaas") e o handler do webhook não conseguem
        relacionar pagamentos do Asaas ao colaborador (faltam tanto customer quanto subscription
        no model local).

        Documentação: https://docs.asaas.com/docs/checkout-com-assinatura-recorrente
        """
        self.ensure_one()
        now = fields.Datetime.from_string(fields.Datetime.now())
        cached_url = (self.asaas_checkout_url or "").strip()
        cached_ok = cached_url.startswith(("http://", "https://"))
        if (
            self.asaas_checkout_id
            and cached_ok
            and self.asaas_checkout_status == "CREATED"
            and self.asaas_checkout_expires_at
            and self.asaas_checkout_expires_at > now
        ):
            return cached_url

        api = self.env["afr.wellhub.asaas.api"]
        # Garante customer Asaas dedupado (POST /v3/customers ou GET por externalReference/CPF)
        # antes do checkout, e o passa via campo `customer` no payload — sem isso o Checkout
        # cria customer novo a cada chamada via customerData (Asaas painel acumula dezenas de
        # registros idênticos do mesmo CPF/email).
        if not self.asaas_customer_id:
            customer_id = api.customer_ensure(self)
            if customer_id:
                self.with_context(afr_wellhub_skip_asaas_sync=True).write(
                    {"asaas_customer_id": customer_id}
                )
        response = api.checkout_create(self, customer_id=self.asaas_customer_id or None)
        checkout_id = (response.get("id") or "").strip()
        checkout_url = api.checkout_extract_url(response)
        if not checkout_id or not checkout_url:
            _logger.warning(
                "Asaas checkout: resposta sem id ou url. response=%s",
                json.dumps(response)[:500] if isinstance(response, dict) else str(response)[:500],
            )
            raise UserError(
                _("Resposta inesperada do Asaas ao criar checkout (id ou URL ausente).")
            )
        minutes = api._checkout_minutes_to_expire()
        expires_at = now + timedelta(minutes=minutes)
        self.with_context(afr_wellhub_skip_asaas_sync=True).write(
            {
                "asaas_checkout_id": checkout_id,
                "asaas_checkout_url": checkout_url,
                "asaas_checkout_status": "CREATED",
                "asaas_checkout_expires_at": fields.Datetime.to_string(expires_at),
            }
        )
        return checkout_url

    def _sync_payments_from_asaas_impl(self):
        """Atualiza espelhos e status das cobranças via GET /v3/payments (sem UI)."""
        api = self.env["afr.wellhub.asaas.api"]
        Payment = self.env["wellhub.asaas.payment"]
        for rec in self:
            if not rec.asaas_customer_id and not rec.asaas_subscription_id:
                raise UserError(
                    _("Não há cliente ou assinatura Asaas vinculada a este colaborador.")
                )
            seen_ids = set()
            offset = 0
            while True:
                data = api.payments_list(
                    customer_id=rec.asaas_customer_id or None,
                    subscription_id=rec.asaas_subscription_id or None,
                    offset=offset,
                    limit=100,
                )
                chunk = data.get("data") or []
                for item in chunk:
                    pid = item.get("id")
                    if pid is not None:
                        seen_ids.add(str(pid))
                    Payment.upsert_from_asaas_payment_dict(item, rec)
                if not data.get("hasMore"):
                    break
                offset += len(chunk)
                if not chunk:
                    break
            Payment.mark_absent_from_sync_as_excluded(rec, seen_ids)
            # Atualiza campos armazenados «Assinatura Wellhub ativa» / adimplência após o espelho.
            rec._compute_wellhub_subscription_status()

    def action_sync_payments_from_asaas(self):
        """Sincroniza cobranças via GET /v3/payments (cliente ou assinatura)."""
        self._sync_payments_from_asaas_impl()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Asaas"),
                "message": _("Cobranças sincronizadas."),
                "type": "success",
                "sticky": False,
            },
        }

    @api.model
    def _webhook_process_payment(self, payment):
        """Localiza colaborador pelo customer/subscription/checkout Asaas e atualiza wellhub.asaas.payment.

        A ordem de fallback (subscription → customer → checkoutSession) protege contra
        divergência: no fluxo via Checkout o customer criado pelo Asaas pode não bater com
        qualquer customer pré-existente que tivéssemos localmente (Checkout não dedupa).
        """
        if not isinstance(payment, dict):
            return
        subscription_id = (payment.get("subscription") or "").strip()
        customer_id = (payment.get("customer") or "").strip()
        checkout_session_id = (payment.get("checkoutSession") or "").strip()
        Collab = self.sudo()
        collab = Collab.browse()
        if subscription_id:
            collab = Collab.search(
                [("asaas_subscription_id", "=", subscription_id)], limit=1
            )
        if not collab and customer_id:
            collab = Collab.search(
                [("asaas_customer_id", "=", customer_id)], limit=1
            )
        if not collab and checkout_session_id:
            collab = Collab.search(
                [("asaas_checkout_id", "=", checkout_session_id)], limit=1
            )
        if not collab:
            _logger.warning(
                "Asaas webhook payment: colaborador não encontrado "
                "(payment_id=%s, sub=%s, customer=%s, checkout=%s).",
                payment.get("id"), subscription_id or "—",
                customer_id or "—", checkout_session_id or "—",
            )
            return
        # Garante asaas_customer_id e asaas_subscription_id locais alinhados ao payload.
        updates = {}
        if customer_id and customer_id != (collab.asaas_customer_id or ""):
            updates["asaas_customer_id"] = customer_id
        # Quando a subscription_id é descoberta agora (não havia antes), aplica metadata
        # local (description, juros, multa, notifyCustomer) na subscription Asaas via PUT —
        # o Checkout não propaga esses campos na criação automática da subscription, e nem
        # sempre o evento CHECKOUT_PAID dispara antes do PAYMENT_*.
        subscription_just_discovered = bool(
            subscription_id and subscription_id != (collab.asaas_subscription_id or "")
        )
        if subscription_just_discovered:
            updates["asaas_subscription_id"] = subscription_id
        if updates:
            collab.with_context(afr_wellhub_skip_asaas_sync=True).write(updates)
        if subscription_just_discovered:
            try:
                self.env["afr.wellhub.asaas.api"].subscription_apply_local_metadata(
                    collab, subscription_id
                )
            except Exception:
                _logger.exception(
                    "Wellhub webhook payment: falha ao aplicar metadados em %s "
                    "(collaborator id=%s).", subscription_id, collab.id,
                )
        self.env["wellhub.asaas.payment"].sudo().upsert_from_asaas_payment_dict(
            payment, collab
        )
        collab._compute_wellhub_subscription_status()

    @api.model
    def _webhook_process_checkout(self, checkout, event):
        """Atualiza status do checkout local e, em CHECKOUT_PAID, vincula asaas_subscription_id.

        Localiza o colaborador por `externalReference` (formato `afr_wh_co_{id}`); fallback por
        `asaas_checkout_id` igual a `checkout.id`. Quando o evento for `CHECKOUT_PAID`, tenta extrair
        `subscription.id` do payload e, se ausente, faz GET /v3/subscriptions filtrando pela
        externalReference da assinatura (`afr_wh_sub_{id}`).
        """
        if not isinstance(checkout, dict):
            return
        checkout_id = (checkout.get("id") or "").strip()
        if not checkout_id:
            return
        ext_ref = (checkout.get("externalReference") or "").strip()
        collab = self.browse()
        if ext_ref.startswith("afr_wh_co_"):
            try:
                collab_id = int(ext_ref.split("_")[-1])
            except (TypeError, ValueError):
                collab_id = 0
            if collab_id:
                collab = self.sudo().browse(collab_id).exists()
        if not collab:
            collab = self.sudo().search(
                [("asaas_checkout_id", "=", checkout_id)], limit=1
            )
        if not collab:
            _logger.warning(
                "Asaas webhook checkout: colaborador não encontrado. event=%s checkout_id=%s ext_ref=%s",
                event,
                checkout_id,
                ext_ref or "—",
            )
            return

        status_map = {
            "CHECKOUT_CREATED": "CREATED",
            "CHECKOUT_PAID": "PAID",
            "CHECKOUT_EXPIRED": "EXPIRED",
            "CHECKOUT_CANCELED": "CANCELED",
        }
        new_status = status_map.get(event)
        if not new_status:
            return

        vals = {
            "asaas_checkout_status": new_status,
            "asaas_checkout_id": collab.asaas_checkout_id or checkout_id,
        }
        # Asaas inclui o id do customer no payload de checkout (campo `customer`); ele é
        # autoritativo — o customer que de fato foi vinculado à subscription gerada pelo
        # Checkout. Pode divergir de qualquer asaas_customer_id local antigo (cenário em
        # que customer_ensure prévio criou um customer diferente do que o Checkout usou).
        checkout_customer_id = (checkout.get("customer") or "").strip()
        if checkout_customer_id and checkout_customer_id != (collab.asaas_customer_id or ""):
            vals["asaas_customer_id"] = checkout_customer_id
        sub_id_to_update = ""
        if event == "CHECKOUT_PAID":
            sub_id_to_update = collab.asaas_subscription_id or ""
            if not sub_id_to_update:
                sub_obj = checkout.get("subscription")
                sub_id = ""
                if isinstance(sub_obj, dict):
                    sub_id = (sub_obj.get("id") or "").strip()
                if not sub_id:
                    api = self.env["afr.wellhub.asaas.api"]
                    # Buscar usando o customer do payload do checkout (autoritativo), não o
                    # asaas_customer_id local (que pode ser de um customer obsoleto criado
                    # antes pelo fluxo legado).
                    customer_for_lookup = checkout_customer_id or collab.asaas_customer_id
                    sub_id = (
                        api.subscription_find_by_external_reference(
                            collab._asaas_subscription_external_reference()
                        )
                        or api.subscription_find_latest_for_customer(customer_for_lookup)
                        or ""
                    )
                if sub_id:
                    vals["asaas_subscription_id"] = sub_id
                    sub_id_to_update = sub_id
            vals.update(
                {
                    "signup_token": False,
                    "signup_token_expiry": False,
                }
            )
        collab.with_context(afr_wellhub_skip_asaas_sync=True).write(vals)
        # PUT /v3/subscriptions/{id} para aplicar description + discount/interest/fine que
        # o Checkout não propaga ao criar a subscription automática. Idempotente; falhas são
        # logadas mas não bloqueiam o webhook (assinatura já existe no Asaas).
        if event == "CHECKOUT_PAID" and sub_id_to_update:
            try:
                self.env["afr.wellhub.asaas.api"].subscription_apply_local_metadata(
                    collab, sub_id_to_update
                )
            except Exception:
                _logger.exception(
                    "Wellhub webhook: falha ao atualizar metadados da subscription %s "
                    "(collaborator id=%s).",
                    sub_id_to_update,
                    collab.id,
                )

    def action_sync_wellhub_api(self):
        """Placeholder para integração futura com API Wellhub (sem documentação no escopo atual)."""
        self.ensure_one()
        raise UserError(
            _(
                "Integração com a API Wellhub ainda não está implementada. "
                "Use o campo 'Contrato assinatura Asaas (recorrência)' até haver especificação da API."
            )
        )

    def unlink(self):
        api = self.env["afr.wellhub.asaas.api"]
        for rec in self:
            if rec.asaas_subscription_id:
                try:
                    api.subscription_delete(rec.asaas_subscription_id)
                except UserError:
                    # Permite excluir no Odoo mesmo se a API falhar; operador trata no Asaas.
                    pass
        return super().unlink()

    @api.model
    def cron_update_asaas_payment_statuses(self):
        """Ação programada: atualiza status e dados das cobranças Asaas (GET /v3/payments)."""
        candidates = self.search(
            [
                "|",
                ("asaas_customer_id", "!=", False),
                ("asaas_subscription_id", "!=", False),
            ]
        )
        for rec in candidates:
            try:
                rec._sync_payments_from_asaas_impl()
            except UserError:
                _logger.warning(
                    "Cron Asaas: atualização de cobranças ignorada para colaborador id=%s",
                    rec.id,
                )

    @api.model
    def _portal_valid_billing_types(self):
        return frozenset({"UNDEFINED", "BOLETO", "CREDIT_CARD", "PIX"})

    @api.model
    def _portal_valid_cycles(self):
        return frozenset(
            {
                "WEEKLY",
                "BIWEEKLY",
                "MONTHLY",
                "BIMONTHLY",
                "QUARTERLY",
                "SEMIANNUALLY",
                "YEARLY",
            }
        )

    @api.model
    def _portal_bool_param(self, key, default=True):
        """Lê parâmetro sim/não usado nos padrões de inscrição pelo portal."""
        raw = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(key, "true" if default else "false")
            or ""
        ).lower()
        return raw in ("1", "true", "yes", "on")

    @api.model
    def _get_assinaturas_default_discount_interest_fine(self):
        """Padrões do bloco Assinaturas (Ajustes) para desconto, juros e multa na API Asaas."""
        icp = self.env["ir.config_parameter"].sudo()
        return {
            "asaas_discount_type": icp.get_param(
                "afr_wellhub.default_asaas_discount_type", "none"
            )
            or "none",
            "asaas_discount_value": float(
                icp.get_param("afr_wellhub.default_asaas_discount_value", "0") or 0
            ),
            "asaas_discount_due_date_limit_days": int(
                float(
                    icp.get_param(
                        "afr_wellhub.default_asaas_discount_due_date_limit_days", "0"
                    )
                    or 0
                )
            ),
            "asaas_interest_monthly_percent": float(
                icp.get_param("afr_wellhub.default_asaas_interest_monthly_percent", "0")
                or 0
            ),
            "asaas_fine_type": icp.get_param("afr_wellhub.default_asaas_fine_type", "none")
            or "none",
            "asaas_fine_value": float(
                icp.get_param("afr_wellhub.default_asaas_fine_value", "0") or 0
            ),
        }

    @api.model
    def _merge_portal_discount_interest_fine_icp(self):
        """Portal: herda Assinaturas (padrão) quando tipo/juros/multa estão em 'Igual ao padrão'."""
        base = self._get_assinaturas_default_discount_interest_fine()
        icp = self.env["ir.config_parameter"].sudo()
        out = dict(base)

        pdt = (icp.get_param("afr_wellhub.portal_asaas_discount_type", "inherit") or "inherit").strip()
        if pdt == "inherit":
            pass
        elif pdt == "none":
            out["asaas_discount_type"] = "none"
            out["asaas_discount_value"] = 0.0
            out["asaas_discount_due_date_limit_days"] = 0
        else:
            out["asaas_discount_type"] = pdt
            out["asaas_discount_value"] = float(
                icp.get_param("afr_wellhub.portal_asaas_discount_value", "0") or 0
            )
            out["asaas_discount_due_date_limit_days"] = int(
                float(
                    icp.get_param(
                        "afr_wellhub.portal_asaas_discount_due_date_limit_days", "0"
                    )
                    or 0
                )
            )

        interest_mode = (
            icp.get_param("afr_wellhub.portal_asaas_interest_mode", "inherit") or "inherit"
        ).strip()
        if interest_mode == "inherit":
            out["asaas_interest_monthly_percent"] = base["asaas_interest_monthly_percent"]
        else:
            out["asaas_interest_monthly_percent"] = float(
                icp.get_param("afr_wellhub.portal_asaas_interest_monthly_percent", "0") or 0
            )

        pft = (icp.get_param("afr_wellhub.portal_asaas_fine_type", "inherit") or "inherit").strip()
        if pft == "inherit":
            pass
        elif pft == "none":
            out["asaas_fine_type"] = "none"
            out["asaas_fine_value"] = 0.0
        else:
            out["asaas_fine_type"] = pft
            out["asaas_fine_value"] = float(
                icp.get_param("afr_wellhub.portal_asaas_fine_value", "0") or 0
            )

        return out

    @api.model
    def _get_portal_subscription_config(self):
        """Padrões de assinatura para inscrição via portal (Ajustes > Wellhub / Asaas).

        Valor: usa ``portal_default_subscription_value`` se > 0; senão o padrão geral
        ``default_subscription_value``. Forma de pagamento e periodicidade vazias no portal
        significam usar o mesmo comportamento do colaborador (campo vazio → padrão geral).
        Desconto, juros e multa: bloco Portal sobrescreve o bloco Assinaturas (padrão) quando
        não estiver em \"Igual ao padrão\".
        """
        icp = self.env["ir.config_parameter"].sudo()
        portal_sv = float(icp.get_param("afr_wellhub.portal_default_subscription_value", "0") or 0)
        global_sv = float(icp.get_param("afr_wellhub.default_subscription_value", "0") or 0)
        subscription_value = portal_sv if portal_sv > 0 else global_sv

        p_bill = (icp.get_param("afr_wellhub.portal_default_billing_type", "") or "").strip()
        billing_type = p_bill if p_bill in self._portal_valid_billing_types() else False

        p_cycle = (icp.get_param("afr_wellhub.portal_default_cycle", "") or "").strip()
        subscription_cycle = p_cycle if p_cycle in self._portal_valid_cycles() else False

        fin = self._merge_portal_discount_interest_fine_icp()
        return {
            "subscription_value": subscription_value,
            "billing_type": billing_type,
            "subscription_cycle": subscription_cycle,
            "pass_asaas_notification_email_sms_fee": self._portal_bool_param(
                "afr_wellhub.portal_pass_notification_email_sms_fee",
                default=True,
            ),
            "pass_credit_card_fee_to_customer": self._portal_bool_param(
                "afr_wellhub.portal_pass_credit_card_fee_to_customer",
                default=True,
            ),
            **fin,
        }

    @api.model
    def _prepare_portal_signup_collaborator_vals(self):
        """Campos de assinatura aplicados ao criar/atualizar cadastro pelo formulário público."""
        cfg = self._get_portal_subscription_config()
        out = {
            "pass_asaas_notification_email_sms_fee": cfg[
                "pass_asaas_notification_email_sms_fee"
            ],
            "pass_credit_card_fee_to_customer": cfg["pass_credit_card_fee_to_customer"],
        }
        if cfg["subscription_value"] > 0:
            out["subscription_value"] = cfg["subscription_value"]
        if cfg["billing_type"]:
            out["billing_type"] = cfg["billing_type"]
        if cfg["subscription_cycle"]:
            out["subscription_cycle"] = cfg["subscription_cycle"]
        out.update(
            {
                "asaas_discount_type": cfg["asaas_discount_type"],
                "asaas_discount_value": cfg["asaas_discount_value"],
                "asaas_discount_due_date_limit_days": cfg[
                    "asaas_discount_due_date_limit_days"
                ],
                "asaas_interest_monthly_percent": cfg["asaas_interest_monthly_percent"],
                "asaas_fine_type": cfg["asaas_fine_type"],
                "asaas_fine_value": cfg["asaas_fine_value"],
            }
        )
        return out

    def action_resend_signup_confirmation_email(self):
        """Reenvia o e-mail com o link de ativação (inscrição pelo portal).

        Renova token e validade (48 h), como no reenvio automático do formulário público.
        """
        self.ensure_one()
        if self.wellhub_subscription_enrolled:
            raise UserError(
                _(
                    "Não é possível reenviar o e-mail: o contrato de assinatura Asaas já foi ativado."
                )
            )
        if not self.signup_pending:
            raise UserError(
                _(
                    "Não há inscrição aguardando confirmação por e-mail. "
                    "Este reenvio aplica-se apenas a colaboradores com inscrição pendente."
                )
            )
        vals = {
            "signup_token": self._portal_new_signup_token(),
            "signup_token_expiry": self._portal_signup_token_expiry_string(),
        }
        self.with_context(afr_wellhub_skip_asaas_sync=True).write(vals)
        template = self.env.ref(
            "afr_wellhub.mail_template_wellhub_signup_activation",
            raise_if_not_found=False,
        )
        if not template:
            raise UserError(
                _("Template de e-mail de ativação não encontrado. Atualize o módulo afr_wellhub.")
            )
        template.send_mail(self.id, force_send=True)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Wellhub"),
                "message": _("E-mail de confirmação reenviado para %s.") % (self.email or ""),
                "type": "success",
                "sticky": False,
            },
        }

    def _spawn_async_checkout(self):
        """Cria checkout Asaas em thread background; usado para liberar o handler HTTP de imediato.

        A criação do checkout chama 1-2 endpoints Asaas (customer_ensure + POST /v3/checkouts)
        que podem levar 30-60s no sandbox e estourar o `proxy_read_timeout` do nginx (504).
        Rodar em thread permite renderizar uma página de spinner ao usuário e fazer polling
        via auto-refresh até `asaas_checkout_url` ficar pronto. A thread usa cursor próprio
        (Registry(db).cursor()) para isolar transações; commit/rollback explícitos.

        A thread espera ~1.5s antes de ler para reduzir colisão "could not serialize access due
        to concurrent update" com o COMMIT do handler HTTP, e ainda assim tenta novamente
        em caso de erro de serialização (Postgres SQLSTATE 40001).
        """
        self.ensure_one()
        db = self.env.cr.dbname
        cid = self.id

        def runner():
            time.sleep(1.5)
            registry = odoo.modules.registry.Registry(db)
            max_attempts = 3
            backoff = 1.0
            for attempt in range(1, max_attempts + 1):
                with registry.cursor() as cr:
                    env = api.Environment(cr, SUPERUSER_ID, {})
                    try:
                        env["wellhub.collaborator"].browse(cid)._ensure_active_checkout()
                        cr.commit()
                        return
                    except Exception as e:
                        cr.rollback()
                        msg = str(e)
                        is_serialize_conflict = (
                            "could not serialize access" in msg
                            or "concurrent update" in msg
                            or getattr(e, "pgcode", "") == "40001"
                        )
                        if is_serialize_conflict and attempt < max_attempts:
                            _logger.info(
                                "Wellhub: conflito de serialização ao criar checkout "
                                "(collaborator id=%s, tentativa %s/%s). Aguardando %.1fs.",
                                cid, attempt, max_attempts, backoff,
                            )
                            time.sleep(backoff)
                            backoff *= 2
                            continue
                        _logger.exception(
                            "Wellhub: criação async de checkout falhou (collaborator id=%s).",
                            cid,
                        )
                        return

        threading.Thread(target=runner, daemon=True).start()

    # Timeout (segundos) tolerado entre o clique no /ativar e a página de checkout ficar pronta.
    # Acima disso, o usuário recebe orientação para tentar de novo em vez de spinner eterno.
    _CHECKOUT_ASYNC_TIMEOUT_SECONDS = 90

    def action_portal_activate_subscription(self):
        """Ativa assinatura Wellhub após confirmação do e-mail.

        Retorna tupla `(status, payload)`:
          - `("ready", url)` — checkout pronto, controller faz redirect 303 para `url`.
          - `("pending", elapsed_seconds)` — checkout em criação, controller renderiza spinner.
          - `("failed", message)` — criação async falhou ou estourou timeout, controller exibe
            mensagem com orientação para reenviar.

        Idempotência: re-cliques antes do pagamento reusam URL cached ou aguardam thread em
        andamento. Token e `signup_pending` permanecem até o webhook `CHECKOUT_PAID`.
        """
        self.ensure_one()
        if self.asaas_subscription_id:
            raise UserError(_("Esta inscrição já foi confirmada ou não é válida."))
        if not self.signup_token:
            raise UserError(_("Esta inscrição já foi confirmada ou não é válida."))

        if self.wellhub_subscription_enrolled:
            return self._portal_check_or_retry_checkout()

        now = fields.Datetime.from_string(fields.Datetime.now())
        if self.signup_token_expiry:
            exp = fields.Datetime.from_string(self.signup_token_expiry)
            if now > exp:
                raise UserError(
                    _("O link de ativação expirou. Solicite uma nova inscrição ou contate o suporte.")
                )

        cfg = self._get_portal_subscription_config()
        if cfg["subscription_value"] <= 0:
            raise UserError(
                _(
                    "Configure o valor da assinatura para o portal ou o valor padrão geral "
                    "em Ajustes (Wellhub / Asaas) antes de permitir ativações pelo portal."
                )
            )
        # billing_type forçado a CREDIT_CARD no fluxo do portal porque o checkout Asaas
        # é criado com billingTypes=["CREDIT_CARD"]. Necessário para que o gross-up de taxa
        # do cartão em `subscription_value_for_asaas` seja aplicado (alinha valor cobrado e
        # absorção da taxa). Se um dia o checkout passar a aceitar mais meios, ajustar aqui.
        vals = {
            "signup_pending": False,
            "signup_email_confirmed_at": fields.Datetime.now(),
            "portal_inscription": True,
            "wellhub_subscription_enrolled": True,
            "subscription_value": cfg["subscription_value"],
            "billing_type": "CREDIT_CARD",
            "subscription_cycle": cfg["subscription_cycle"] or False,
            "next_due_date": fields.Date.context_today(self),
            "pass_asaas_notification_email_sms_fee": cfg["pass_asaas_notification_email_sms_fee"],
            "pass_credit_card_fee_to_customer": cfg["pass_credit_card_fee_to_customer"],
            "asaas_discount_type": cfg["asaas_discount_type"],
            "asaas_discount_value": cfg["asaas_discount_value"],
            "asaas_discount_due_date_limit_days": cfg["asaas_discount_due_date_limit_days"],
            "asaas_interest_monthly_percent": cfg["asaas_interest_monthly_percent"],
            "asaas_fine_type": cfg["asaas_fine_type"],
            "asaas_fine_value": cfg["asaas_fine_value"],
        }
        # afr_wellhub_skip_asaas_sync evita que o write-hook bloqueie chamando Asaas síncrono —
        # a criação do checkout acontece via _spawn_async_checkout em thread background.
        self.with_context(afr_wellhub_skip_asaas_sync=True).write(vals)
        # Commit antes do spawn: a thread async usa cursor próprio (outra conexão Postgres) e
        # leria snapshot anterior ao write deste handler, causando "could not serialize access
        # due to concurrent update" quando tentasse atualizar asaas_checkout_*. Commit aqui
        # garante visibilidade entre cursors antes do trabalho assíncrono começar.
        self.env.cr.commit()
        self._spawn_async_checkout()
        return ("pending", 0)

    def _portal_check_or_retry_checkout(self):
        """Re-click após enrollment. Retorna ('ready', url) | ('pending', elapsed) | ('failed', msg)."""
        self.ensure_one()
        cached_url = (self.asaas_checkout_url or "").strip()
        if (
            cached_url.startswith(("http://", "https://"))
            and self.asaas_checkout_status == "CREATED"
        ):
            now = fields.Datetime.from_string(fields.Datetime.now())
            if (
                self.asaas_checkout_expires_at
                and self.asaas_checkout_expires_at > now
            ):
                return ("ready", cached_url)
        started = self.signup_email_confirmed_at
        if started:
            elapsed = (
                fields.Datetime.from_string(fields.Datetime.now())
                - fields.Datetime.from_string(fields.Datetime.to_string(started))
            ).total_seconds()
        else:
            elapsed = 0
        if elapsed >= self._CHECKOUT_ASYNC_TIMEOUT_SECONDS:
            # Timeout: relança thread async (caso o spawn anterior tenha morrido) e dá ao
            # usuário a opção de tentar via reenviar.
            self._spawn_async_checkout()
            return (
                "failed",
                _(
                    "A criação do link de pagamento demorou mais que o esperado. "
                    "Aguarde alguns instantes e atualize a página ou solicite um novo link."
                ),
            )
        return ("pending", int(elapsed))

    @api.model
    def _portal_signup_token_expiry_string(self):
        """Retorna data/hora de expiração do token (48 h após agora, horário servidor)."""
        now = fields.Datetime.from_string(fields.Datetime.now())
        return fields.Datetime.to_string(now + timedelta(hours=48))

    @api.model
    def _portal_new_signup_token(self):
        """Gera token seguro para o link de ativação enviado por e-mail."""
        return secrets.token_urlsafe(32)
