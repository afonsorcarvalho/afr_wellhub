# -*- coding: utf-8 -*-
"""Cliente HTTP para a API v3 do Asaas (documentação: https://docs.asaas.com/reference/comece-por-aqui)."""

import json
import logging
import re

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

ASAAS_PRODUCTION = "https://api.asaas.com"
ASAAS_SANDBOX = "https://api-sandbox.asaas.com"

# Nome do grupo de clientes no Asaas para quem se inscreve pelo portal (campo groupName).
# Documentação: CustomerSaveRequestDTO / CustomerUpdateRequestDTO — não há endpoint para
# criar grupo vazio; o agrupamento existe ao atribuir groupName ao cliente.
ASAAS_WELLHUB_PORTAL_GROUP_NAME = "Wellhub"


class AfrWellhubAsaasApi(models.AbstractModel):
    _name = "afr.wellhub.asaas.api"
    _description = "Cliente API Asaas (Wellhub)"

    @api.model
    def _get_config_param(self, key, default=""):
        return (
            self.env["ir.config_parameter"].sudo().get_param(key, default) or default
        )

    @api.model
    def _base_url(self):
        env_type = self._get_config_param("afr_wellhub.asaas_environment", "sandbox")
        if env_type == "production":
            return ASAAS_PRODUCTION
        return ASAAS_SANDBOX

    @api.model
    def _api_key(self):
        key = self._get_config_param("afr_wellhub.asaas_api_key", "")
        if not key:
            raise UserError(_("Configure a chave de API Asaas nas configurações."))
        return key

    @api.model
    def _request_timeout(self):
        try:
            return int(self._get_config_param("afr_wellhub.asaas_timeout", "30"))
        except ValueError:
            return 30

    @api.model
    def _headers(self):
        return {
            "access_token": self._api_key(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @api.model
    def _parse_errors(self, response):
        try:
            body = response.json()
        except ValueError:
            return response.text or str(response.status_code)
        errors = body.get("errors")
        if isinstance(errors, list) and errors:
            parts = []
            for err in errors:
                if isinstance(err, dict):
                    code = err.get("code") or ""
                    desc = err.get("description") or ""
                    parts.append(f"{code}: {desc}".strip(": "))
                else:
                    parts.append(str(err))
            return "; ".join(parts) if parts else json.dumps(body)
        return json.dumps(body)

    @api.model
    def _request(self, method, path, params=None, json_body=None):
        """Executa chamada à API. path começa com /v3/..."""
        url = f"{self._base_url().rstrip('/')}{path}"
        try:
            response = requests.request(
                method,
                url,
                headers=self._headers(),
                params=params,
                json=json_body,
                timeout=self._request_timeout(),
            )
        except requests.RequestException as e:
            _logger.warning("Asaas request failed: %s %s", method, path)
            raise UserError(
                _("Falha de comunicação com o Asaas: %s") % str(e)
            ) from e
        if response.status_code >= 400:
            msg = self._parse_errors(response)
            _logger.warning(
                "Asaas HTTP %s %s: %s",
                response.status_code,
                path,
                msg[:500],
            )
            raise UserError(
                _("Erro Asaas (%(status)s): %(msg)s")
                % {"status": response.status_code, "msg": msg}
            )
        if response.status_code == 204 or not response.content:
            return {}
        try:
            return response.json()
        except ValueError as e:
            raise UserError(_("Resposta inválida do Asaas.")) from e

    @api.model
    def customer_find_by_external_reference(self, external_ref):
        data = self._request(
            "GET",
            "/v3/customers",
            params={"externalReference": external_ref, "limit": 10},
        )
        items = data.get("data") or []
        if items:
            return items[0].get("id")
        return None

    @api.model
    def customer_find_by_cpf_cnpj(self, cpf_cnpj_digits):
        """Localiza cliente existente por CPF/CNPJ (GET /v3/customers?cpfCnpj=…).

        Documentação: https://docs.asaas.com/reference/list-customers — filtro cpfCnpj.
        Ignora registros marcados como excluídos na resposta.
        """
        if not cpf_cnpj_digits:
            return None
        data = self._request(
            "GET",
            "/v3/customers",
            params={"cpfCnpj": cpf_cnpj_digits, "limit": 20},
        )
        for item in data.get("data") or []:
            if item.get("deleted"):
                continue
            cid = (item.get("id") or "").strip()
            if cid:
                return cid
        return None

    @api.model
    def customer_create(self, payload):
        return self._request("POST", "/v3/customers", json_body=payload)

    @api.model
    def customer_update(self, customer_id, payload):
        """Atualiza cliente (PUT /v3/customers/{id}). Permissão CUSTOMER:WRITE."""
        if not customer_id:
            return {}
        return self._request(
            "PUT",
            f"/v3/customers/{customer_id}",
            json_body=payload,
        )

    @api.model
    def customer_wellhub_group_has_any_customer_in_asaas(self):
        """Indica se já existe pelo menos um cliente no Asaas com groupName «Wellhub».

        GET /v3/customers?groupName=… — documentação «List Customers».
        A API não expõe criação de grupo sem cliente; este método só informa se o nome
        de grupo já está em uso (útil para log / diagnóstico).
        """
        data = self._request(
            "GET",
            "/v3/customers",
            params={"groupName": ASAAS_WELLHUB_PORTAL_GROUP_NAME, "limit": 1},
        )
        return bool(data.get("data"))

    @api.model
    def _wellhub_portal_group_payload(self, collaborator):
        """Retorna {'groupName': 'Wellhub'} se inscrição pelo portal; senão {}."""
        self.env["wellhub.collaborator"].browse(collaborator.id).ensure_one()
        if not collaborator.portal_inscription:
            return {}
        return {"groupName": ASAAS_WELLHUB_PORTAL_GROUP_NAME}

    @api.model
    def _log_if_first_wellhub_group_customer(self):
        """Registra em log quando ainda não há clientes com groupName «Wellhub» na conta."""
        if self.customer_wellhub_group_has_any_customer_in_asaas():
            return
        _logger.info(
            "Asaas: primeiro cliente atribuído ao grupo «%s» (groupName na API).",
            ASAAS_WELLHUB_PORTAL_GROUP_NAME,
        )

    @api.model
    def _customer_ensure_apply_wellhub_group(self, collaborator, customer_id):
        """Garante groupName no Asaas para colaboradores vindos do formulário público."""
        extra = self._wellhub_portal_group_payload(collaborator)
        if not extra:
            return
        self._log_if_first_wellhub_group_customer()
        self.customer_update(customer_id, extra)

    @api.model
    def customer_ensure(self, collaborator):
        """Garante cliente Asaas: externalReference, depois CPF/CNPJ, senão POST.

        Se já existir cliente com o mesmo CPF/CNPJ na conta Asaas, não cria duplicata:
        atualiza nome, e-mail, telefone e externalReference (vínculo Wellhub).

        Inscrições pelo portal recebem ``groupName`` «Wellhub» (grupo no painel Asaas
        conforme documentação do campo groupName; não há POST separado para «criar grupo»).
        """
        self.env["wellhub.collaborator"].browse(collaborator.id).ensure_one()
        ext_ref = collaborator._asaas_external_reference()
        group_extra = self._wellhub_portal_group_payload(collaborator)
        if collaborator.asaas_customer_id:
            self._customer_ensure_apply_wellhub_group(
                collaborator, collaborator.asaas_customer_id
            )
            return collaborator.asaas_customer_id
        existing = self.customer_find_by_external_reference(ext_ref)
        if existing:
            self._customer_ensure_apply_wellhub_group(collaborator, existing)
            return existing
        cpf_cnpj = re.sub(r"\D", "", collaborator.cpf_cnpj or "")
        if not cpf_cnpj:
            raise UserError(
                _("CPF/CNPJ é obrigatório para criar o cliente no Asaas.")
            )
        phone_digits = re.sub(r"\D", "", collaborator.phone or "")
        payload = {
            "name": collaborator.name,
            "cpfCnpj": cpf_cnpj,
            "email": collaborator.email,
            "externalReference": ext_ref,
        }
        if phone_digits:
            payload["mobilePhone"] = phone_digits
        payload.update(group_extra)

        existing_by_doc = self.customer_find_by_cpf_cnpj(cpf_cnpj)
        if existing_by_doc:
            _logger.info(
                "Asaas: cliente existente por CPF/CNPJ (%s…), atualizando id=%s",
                cpf_cnpj[:3],
                existing_by_doc,
            )
            if group_extra:
                self._log_if_first_wellhub_group_customer()
            self.customer_update(existing_by_doc, payload)
            return existing_by_doc

        if group_extra:
            self._log_if_first_wellhub_group_customer()
        created = self.customer_create(payload)
        return created.get("id")

    @api.model
    def _credit_card_fee_fixed(self):
        """Taxa fixa (R$) por cobrança recebida no cartão — padrão divulgado na página Asaas."""
        try:
            return float(self._get_config_param("afr_wellhub.cc_fee_fixed", "0.49") or 0)
        except ValueError:
            return 0.49

    @api.model
    def _credit_card_fee_percent(self):
        """Percentual sobre o valor total (cartão à vista na tabela pública Asaas)."""
        try:
            return float(self._get_config_param("afr_wellhub.cc_fee_percent", "2.99") or 0)
        except ValueError:
            return 2.99

    @api.model
    def _notification_package_fee(self):
        """Pacote e-mail+SMS cobrado pelo Asaas por cobrança paga (valor público de referência)."""
        try:
            return float(
                self._get_config_param("afr_wellhub.notification_package_fee", "0.99") or 0
            )
        except ValueError:
            return 0.99

    @api.model
    def _subscription_base_value(self, collaborator):
        """Valor base da assinatura (campo ou padrão nas configurações)."""
        raw = collaborator.subscription_value
        if raw is None or raw <= 0:
            raw = float(
                self._get_config_param("afr_wellhub.default_subscription_value", "0") or 0
            )
        return float(raw or 0)

    @api.model
    def subscription_net_before_card_fee_for_asaas(self, collaborator):
        """Base + pacote de notificações e-mail/SMS (somados antes do gross-up do cartão).

        Ordem: (valor assinatura) + (taxa pacote notif., se repasse ativo); em seguida aplica-se
        taxa fixa + percentual do cartão sobre esse total, para o % incidir também sobre as notificações.
        Taxas de notificação: https://docs.asaas.com/docs/notificacoes — valores em
        https://www.asaas.com/precos-e-taxas (página pública cita R$ 0,99 pelo pacote por transação).
        """
        base = self._subscription_base_value(collaborator)
        if base <= 0:
            return 0.0
        if collaborator.pass_asaas_notification_email_sms_fee:
            base += self._notification_package_fee()
        return base

    @api.model
    def compute_gross_subscription_value_from_net(self, net_amount):
        """Valor bruto a cobrar no Asaas para que, após taxa fixa + % do cartão, reste net_amount.

        Modelo alinhado à cobrança por transação: taxa = fixo + (percentual/100) * bruto;
        líquido = bruto - taxa  =>  bruto = (líquido + fixo) / (1 - percentual/100).
        O parâmetro net_amount deve já incluir repasses somados antes (ex.: pacote e-mail/SMS).
        Referência de taxas de cartão: https://www.asaas.com/precos-e-taxas
        """
        net = float(net_amount or 0)
        fixed = self._credit_card_fee_fixed()
        pct = self._credit_card_fee_percent()
        if pct >= 100:
            raise UserError(
                _("O percentual de taxa de cartão nas configurações deve ser menor que 100.")
            )
        divisor = 1.0 - (pct / 100.0)
        if divisor <= 0:
            raise UserError(_("Configuração inválida de taxa de cartão (percentual)."))
        gross = (net + fixed) / divisor
        return round(gross, 2)

    @api.model
    def subscription_value_for_asaas(self, collaborator):
        """Valor (float) a enviar no campo value da assinatura no Asaas."""
        adjusted = self.subscription_net_before_card_fee_for_asaas(collaborator)
        if adjusted <= 0:
            return 0.0
        billing = collaborator._get_effective_billing_type()
        if (
            billing == "CREDIT_CARD"
            and collaborator.pass_credit_card_fee_to_customer
        ):
            return self.compute_gross_subscription_value_from_net(adjusted)
        return round(float(adjusted), 2)

    @api.model
    def subscription_get(self, subscription_id):
        """GET /v3/subscriptions/{id} — confirma assinatura recorrente no Asaas."""
        if not subscription_id:
            return {}
        return self._request("GET", f"/v3/subscriptions/{subscription_id}")

    @api.model
    def subscription_create(self, collaborator, customer_id):
        """Cria assinatura recorrente: POST /v3/subscriptions (não POST /v3/payments).

        Documentação: https://docs.asaas.com/reference/criar-nova-assinatura
        Guia: https://docs.asaas.com/docs/assinaturas
        """
        value = self.subscription_value_for_asaas(collaborator)
        if value <= 0:
            raise UserError(_("Defina o valor da assinatura no colaborador ou nas configurações."))
        billing = collaborator._get_effective_billing_type()
        if billing == "UNDEFINED":
            raise UserError(
                _(
                    "Para assinatura recorrente no Asaas, a forma de pagamento não pode ser "
                    "'Indefinido'. Defina Pix, Boleto ou Cartão no colaborador ou nas configurações."
                )
            )
        cycle = collaborator.subscription_cycle or self._get_config_param(
            "afr_wellhub.default_cycle", "MONTHLY"
        )
        next_due = collaborator.next_due_date
        if not next_due:
            next_due = fields.Date.context_today(collaborator)
        payload = {
            "customer": customer_id,
            "billingType": billing,
            "value": value,
            "nextDueDate": next_due.strftime("%Y-%m-%d"),
            "cycle": cycle,
            "description": _("[Assinatura recorrente Wellhub] %s") % collaborator.name,
            "externalReference": collaborator._asaas_subscription_external_reference(),
        }
        # discount, interest, fine — opcionais na API Criar nova assinatura.
        payload.update(collaborator._asaas_subscription_discount_interest_fine_payload())
        result = self._request("POST", "/v3/subscriptions", json_body=payload)
        sub_id = (result.get("id") or "").strip()
        if not sub_id.startswith("sub_"):
            raise UserError(
                _(
                    "O Asaas não retornou um id de assinatura (sub_…). "
                    "Verifique permissão SUBSCRIPTION:WRITE na chave de API, o ambiente "
                    "(sandbox/produção) e se a resposta não é de outro endpoint. "
                    "Cobranças avulsas usam id pay_… (POST /v3/payments)."
                )
            )
        obj = (result.get("object") or "").strip().lower()
        if obj and obj != "subscription":
            raise UserError(
                _("Resposta inesperada do Asaas (object=%(obj)s). Esperado assinatura.")
                % {"obj": result.get("object")}
            )
        return result

    @api.model
    def subscription_delete(self, subscription_id):
        if not subscription_id:
            return {}
        return self._request("DELETE", f"/v3/subscriptions/{subscription_id}")

    @api.model
    def payments_list(self, customer_id=None, subscription_id=None, offset=0, limit=100):
        params = {"offset": offset, "limit": min(limit, 100)}
        if customer_id:
            params["customer"] = customer_id
        if subscription_id:
            params["subscription"] = subscription_id
        return self._request("GET", "/v3/payments", params=params)

    @api.model
    def payment_get(self, payment_id):
        return self._request("GET", f"/v3/payments/{payment_id}")
