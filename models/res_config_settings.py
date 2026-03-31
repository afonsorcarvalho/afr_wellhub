# -*- coding: utf-8 -*-
"""Parâmetros globais Asaas / Wellhub (ir.config_parameter)."""

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    wellhub_asaas_api_key = fields.Char(
        string="Chave de API Asaas",
        config_parameter="afr_wellhub.asaas_api_key",
        help="Token access_token enviado no header das requisições (documentação Asaas).",
    )
    wellhub_asaas_environment = fields.Selection(
        selection=[("sandbox", "Sandbox"), ("production", "Produção")],
        string="Ambiente Asaas",
        config_parameter="afr_wellhub.asaas_environment",
        default="sandbox",
    )
    wellhub_asaas_webhook_token = fields.Char(
        string="Token do webhook Asaas",
        config_parameter="afr_wellhub.webhook_token",
        help="Deve coincidir com o authToken configurado no webhook Asaas; validação via header asaas-access-token (documentação Asaas).",
    )
    wellhub_default_subscription_value = fields.Float(
        string="Valor padrão da assinatura",
        default=0.0,
    )
    wellhub_default_billing_type = fields.Selection(
        selection=[
            ("UNDEFINED", "Indefinido"),
            ("BOLETO", "Boleto"),
            ("CREDIT_CARD", "Cartão de crédito"),
            ("PIX", "Pix"),
        ],
        string="Forma de pagamento padrão",
        config_parameter="afr_wellhub.default_billing_type",
        default="PIX",
    )
    wellhub_default_cycle = fields.Selection(
        selection=[
            ("WEEKLY", "Semanal"),
            ("BIWEEKLY", "Quinzenal"),
            ("MONTHLY", "Mensal"),
            ("BIMONTHLY", "Bimestral"),
            ("QUARTERLY", "Trimestral"),
            ("SEMIANNUALLY", "Semestral"),
            ("YEARLY", "Anual"),
        ],
        string="Periodicidade padrão",
        config_parameter="afr_wellhub.default_cycle",
        default="MONTHLY",
    )
    wellhub_asaas_timeout = fields.Integer(
        string="Timeout HTTP (s)",
        default=30,
    )
    wellhub_cc_fee_fixed = fields.Float(
        string="Taxa fixa cartão (R$)",
        default=0.49,
        help="Padrão público Asaas (cartão à vista): R$ 0,49 por cobrança recebida. "
        "Confira valores atualizados em https://www.asaas.com/precos-e-taxas e no menu Taxas da sua conta.",
    )
    wellhub_cc_fee_percent = fields.Float(
        string="Taxa percentual cartão (%)",
        default=2.99,
        help="Padrão público Asaas (cartão à vista): 2,99% sobre o valor total. "
        "Promoção para novos clientes pode ser 1,99% (3 meses). "
        "Parcelamentos têm percentuais maiores na mesma página.",
    )
    wellhub_notification_package_fee = fields.Float(
        string="Pacote notif. e-mail + SMS (R$)",
        default=0.99,
        help="Referência pública Asaas: pacote de notificações por e-mail e SMS cobrado por "
        "cobrança paga (tabela em https://www.asaas.com/precos-e-taxas ). "
        "Taxas aplicáveis também em https://docs.asaas.com/docs/notificacoes — confira em Minha conta > Taxas.",
    )
    _portal_billing_selection = [
        ("", "Igual ao padrão geral (Assinaturas)"),
        ("UNDEFINED", "Indefinido"),
        ("BOLETO", "Boleto"),
        ("CREDIT_CARD", "Cartão de crédito"),
        ("PIX", "Pix"),
    ]
    _portal_cycle_selection = [
        ("", "Igual ao padrão geral (Assinaturas)"),
        ("WEEKLY", "Semanal"),
        ("BIWEEKLY", "Quinzenal"),
        ("MONTHLY", "Mensal"),
        ("BIMONTHLY", "Bimestral"),
        ("QUARTERLY", "Trimestral"),
        ("SEMIANNUALLY", "Semestral"),
        ("YEARLY", "Anual"),
    ]
    wellhub_portal_default_subscription_value = fields.Float(
        string="Valor assinatura (portal)",
        default=0.0,
        help="Se maior que zero, usado na inscrição pelo site e na ativação por e-mail. "
        "Se zero, usa o 'Valor padrão da assinatura' do bloco Assinaturas (padrão).",
    )
    wellhub_portal_default_billing_type = fields.Selection(
        selection=_portal_billing_selection,
        string="Forma de pagamento (portal)",
        default="",
        help="Vazio = mesmo padrão do bloco 'Assinaturas (padrão)'. Defina aqui para forçar "
        "Pix, Boleto ou Cartão nos colaboradores vindos do formulário público.",
    )
    wellhub_portal_default_cycle = fields.Selection(
        selection=_portal_cycle_selection,
        string="Periodicidade (portal)",
        default="",
        help="Vazio = mesmo padrão do bloco 'Assinaturas (padrão)'.",
    )
    wellhub_portal_pass_notification_email_sms_fee = fields.Boolean(
        string="Portal: repassar pacote e-mail/SMS",
        default=True,
        help="Aplicado ao criar/atualizar inscrição pelo site e ao confirmar o link do e-mail.",
    )
    wellhub_portal_pass_credit_card_fee_to_customer = fields.Boolean(
        string="Portal: repassar taxa do cartão",
        default=True,
        help="Aplicado ao criar/atualizar inscrição pelo site e ao confirmar o link do e-mail.",
    )
    # --- Juros, multa e desconto (Assinaturas padrão) — aplicados a novos colaboradores no backend. ---
    wellhub_default_asaas_discount_type = fields.Selection(
        selection=[
            ("none", "Sem desconto"),
            ("PERCENTAGE", "Percentual sobre a cobrança"),
            ("FIXED", "Valor fixo (R$)"),
        ],
        string="Tipo de desconto (padrão)",
        default="none",
    )
    wellhub_default_asaas_discount_value = fields.Float(
        string="Valor do desconto (padrão)",
        default=0.0,
    )
    wellhub_default_asaas_discount_due_date_limit_days = fields.Integer(
        string="Desconto: dias antes do vencimento (padrão)",
        default=0,
    )
    wellhub_default_asaas_interest_monthly_percent = fields.Float(
        string="Juros ao mês % (padrão)",
        default=0.0,
    )
    wellhub_default_asaas_fine_type = fields.Selection(
        selection=[
            ("none", "Sem multa"),
            ("PERCENTAGE", "Percentual sobre a cobrança"),
            ("FIXED", "Valor fixo (R$)"),
        ],
        string="Tipo de multa (padrão)",
        default="none",
    )
    wellhub_default_asaas_fine_value = fields.Float(
        string="Valor da multa (padrão)",
        default=0.0,
    )
    # --- Portal: sobrescreve o bloco acima quando não for "Igual ao padrão". ---
    _inherit_discount_selection = [
        ("inherit", "Igual ao padrão (Assinaturas)"),
        ("none", "Sem desconto"),
        ("PERCENTAGE", "Percentual sobre a cobrança"),
        ("FIXED", "Valor fixo (R$)"),
    ]
    _inherit_fine_selection = [
        ("inherit", "Igual ao padrão (Assinaturas)"),
        ("none", "Sem multa"),
        ("PERCENTAGE", "Percentual sobre a cobrança"),
        ("FIXED", "Valor fixo (R$)"),
    ]
    wellhub_portal_asaas_discount_type = fields.Selection(
        selection=_inherit_discount_selection,
        string="Tipo de desconto (portal)",
        default="inherit",
    )
    wellhub_portal_asaas_discount_value = fields.Float(
        string="Valor do desconto (portal)",
        default=0.0,
        help="Usado quando o tipo no portal não for 'Igual ao padrão'. Se zero e tipo explícito, pode falhar validação — informe conforme o tipo.",
    )
    wellhub_portal_asaas_discount_due_date_limit_days = fields.Integer(
        string="Desconto: dias antes do venc. (portal)",
        default=0,
    )
    wellhub_portal_asaas_interest_mode = fields.Selection(
        selection=[
            ("inherit", "Igual ao padrão (Assinaturas)"),
            ("custom", "Definir juros ao mês abaixo"),
        ],
        string="Juros ao mês (portal)",
        default="inherit",
    )
    wellhub_portal_asaas_interest_monthly_percent = fields.Float(
        string="Juros ao mês % (portal)",
        default=0.0,
        help="Somente quando 'Definir juros ao mês abaixo' está selecionado.",
    )
    wellhub_portal_asaas_fine_type = fields.Selection(
        selection=_inherit_fine_selection,
        string="Tipo de multa (portal)",
        default="inherit",
    )
    wellhub_portal_asaas_fine_value = fields.Float(
        string="Valor da multa (portal)",
        default=0.0,
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        icp = self.env["ir.config_parameter"].sudo()
        res["wellhub_default_subscription_value"] = float(
            icp.get_param("afr_wellhub.default_subscription_value", "0") or 0
        )
        res["wellhub_asaas_timeout"] = int(
            icp.get_param("afr_wellhub.asaas_timeout", "30") or 30
        )
        res["wellhub_cc_fee_fixed"] = float(
            icp.get_param("afr_wellhub.cc_fee_fixed", "0.49") or 0
        )
        res["wellhub_cc_fee_percent"] = float(
            icp.get_param("afr_wellhub.cc_fee_percent", "2.99") or 0
        )
        res["wellhub_notification_package_fee"] = float(
            icp.get_param("afr_wellhub.notification_package_fee", "0.99") or 0
        )
        res["wellhub_portal_default_subscription_value"] = float(
            icp.get_param("afr_wellhub.portal_default_subscription_value", "0") or 0
        )
        res["wellhub_portal_default_billing_type"] = (
            icp.get_param("afr_wellhub.portal_default_billing_type", "") or ""
        )
        res["wellhub_portal_default_cycle"] = (
            icp.get_param("afr_wellhub.portal_default_cycle", "") or ""
        )
        res["wellhub_portal_pass_notification_email_sms_fee"] = (
            icp.get_param(
                "afr_wellhub.portal_pass_notification_email_sms_fee", "true"
            )
            or "true"
        ).lower() in ("1", "true", "yes", "on")
        res["wellhub_portal_pass_credit_card_fee_to_customer"] = (
            icp.get_param(
                "afr_wellhub.portal_pass_credit_card_fee_to_customer", "true"
            )
            or "true"
        ).lower() in ("1", "true", "yes", "on")
        res["wellhub_default_asaas_discount_type"] = (
            icp.get_param("afr_wellhub.default_asaas_discount_type", "none") or "none"
        )
        res["wellhub_default_asaas_discount_value"] = float(
            icp.get_param("afr_wellhub.default_asaas_discount_value", "0") or 0
        )
        res["wellhub_default_asaas_discount_due_date_limit_days"] = int(
            float(icp.get_param("afr_wellhub.default_asaas_discount_due_date_limit_days", "0") or 0)
        )
        res["wellhub_default_asaas_interest_monthly_percent"] = float(
            icp.get_param("afr_wellhub.default_asaas_interest_monthly_percent", "0") or 0
        )
        res["wellhub_default_asaas_fine_type"] = (
            icp.get_param("afr_wellhub.default_asaas_fine_type", "none") or "none"
        )
        res["wellhub_default_asaas_fine_value"] = float(
            icp.get_param("afr_wellhub.default_asaas_fine_value", "0") or 0
        )
        res["wellhub_portal_asaas_discount_type"] = (
            icp.get_param("afr_wellhub.portal_asaas_discount_type", "inherit") or "inherit"
        )
        res["wellhub_portal_asaas_discount_value"] = float(
            icp.get_param("afr_wellhub.portal_asaas_discount_value", "0") or 0
        )
        res["wellhub_portal_asaas_discount_due_date_limit_days"] = int(
            float(icp.get_param("afr_wellhub.portal_asaas_discount_due_date_limit_days", "0") or 0)
        )
        res["wellhub_portal_asaas_interest_mode"] = (
            icp.get_param("afr_wellhub.portal_asaas_interest_mode", "inherit") or "inherit"
        )
        res["wellhub_portal_asaas_interest_monthly_percent"] = float(
            icp.get_param("afr_wellhub.portal_asaas_interest_monthly_percent", "0") or 0
        )
        res["wellhub_portal_asaas_fine_type"] = (
            icp.get_param("afr_wellhub.portal_asaas_fine_type", "inherit") or "inherit"
        )
        res["wellhub_portal_asaas_fine_value"] = float(
            icp.get_param("afr_wellhub.portal_asaas_fine_value", "0") or 0
        )
        return res

    def set_values(self):
        super().set_values()
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param(
            "afr_wellhub.default_subscription_value",
            str(float(self.wellhub_default_subscription_value or 0)),
        )
        icp.set_param(
            "afr_wellhub.asaas_timeout",
            str(int(self.wellhub_asaas_timeout or 30)),
        )
        icp.set_param(
            "afr_wellhub.cc_fee_fixed",
            str(float(self.wellhub_cc_fee_fixed or 0)),
        )
        icp.set_param(
            "afr_wellhub.cc_fee_percent",
            str(float(self.wellhub_cc_fee_percent or 0)),
        )
        icp.set_param(
            "afr_wellhub.notification_package_fee",
            str(float(self.wellhub_notification_package_fee or 0)),
        )
        icp.set_param(
            "afr_wellhub.portal_default_subscription_value",
            str(float(self.wellhub_portal_default_subscription_value or 0)),
        )
        icp.set_param(
            "afr_wellhub.portal_default_billing_type",
            (self.wellhub_portal_default_billing_type or "").strip(),
        )
        icp.set_param(
            "afr_wellhub.portal_default_cycle",
            (self.wellhub_portal_default_cycle or "").strip(),
        )
        icp.set_param(
            "afr_wellhub.portal_pass_notification_email_sms_fee",
            "true" if self.wellhub_portal_pass_notification_email_sms_fee else "false",
        )
        icp.set_param(
            "afr_wellhub.portal_pass_credit_card_fee_to_customer",
            "true" if self.wellhub_portal_pass_credit_card_fee_to_customer else "false",
        )
        icp.set_param(
            "afr_wellhub.default_asaas_discount_type",
            self.wellhub_default_asaas_discount_type or "none",
        )
        icp.set_param(
            "afr_wellhub.default_asaas_discount_value",
            str(float(self.wellhub_default_asaas_discount_value or 0)),
        )
        icp.set_param(
            "afr_wellhub.default_asaas_discount_due_date_limit_days",
            str(int(self.wellhub_default_asaas_discount_due_date_limit_days or 0)),
        )
        icp.set_param(
            "afr_wellhub.default_asaas_interest_monthly_percent",
            str(float(self.wellhub_default_asaas_interest_monthly_percent or 0)),
        )
        icp.set_param(
            "afr_wellhub.default_asaas_fine_type",
            self.wellhub_default_asaas_fine_type or "none",
        )
        icp.set_param(
            "afr_wellhub.default_asaas_fine_value",
            str(float(self.wellhub_default_asaas_fine_value or 0)),
        )
        icp.set_param(
            "afr_wellhub.portal_asaas_discount_type",
            self.wellhub_portal_asaas_discount_type or "inherit",
        )
        icp.set_param(
            "afr_wellhub.portal_asaas_discount_value",
            str(float(self.wellhub_portal_asaas_discount_value or 0)),
        )
        icp.set_param(
            "afr_wellhub.portal_asaas_discount_due_date_limit_days",
            str(int(self.wellhub_portal_asaas_discount_due_date_limit_days or 0)),
        )
        icp.set_param(
            "afr_wellhub.portal_asaas_interest_mode",
            self.wellhub_portal_asaas_interest_mode or "inherit",
        )
        icp.set_param(
            "afr_wellhub.portal_asaas_interest_monthly_percent",
            str(float(self.wellhub_portal_asaas_interest_monthly_percent or 0)),
        )
        icp.set_param(
            "afr_wellhub.portal_asaas_fine_type",
            self.wellhub_portal_asaas_fine_type or "inherit",
        )
        icp.set_param(
            "afr_wellhub.portal_asaas_fine_value",
            str(float(self.wellhub_portal_asaas_fine_value or 0)),
        )
