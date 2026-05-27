# -*- coding: utf-8 -*-
"""Formulário público de inscrição de colaboradores Wellhub e ativação por e-mail."""

import logging
import re

from odoo import _, fields, http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from odoo.tools import format_amount, format_date
from odoo.tools.mail import email_normalize

_logger = logging.getLogger(__name__)


def _cpf_digits_valid(cpf):
    """Valida CPF (11 dígitos) com dígitos verificadores (receita federal)."""
    if len(cpf) != 11 or not cpf.isdigit():
        return False
    if cpf == cpf[0] * 11:
        return False
    s = sum(int(cpf[i]) * (10 - i) for i in range(9))
    r = s % 11
    d1 = 0 if r < 2 else 11 - r
    if d1 != int(cpf[9]):
        return False
    s = sum(int(cpf[i]) * (11 - i) for i in range(10))
    r = s % 11
    d2 = 0 if r < 2 else 11 - r
    return d2 == int(cpf[10])


def _br_phone_digits_valid(digits):
    """Telefone BR: 10 dígitos (fixo) ou 11 (celular), DDD 11–99."""
    if len(digits) not in (10, 11):
        return False
    ddd = int(digits[:2])
    if ddd < 11 or ddd > 99:
        return False
    return True


def _format_br_phone_display(digits):
    """Formata (DD) NNNN-NNNN ou (DD) NNNNN-NNNN para exibição/armazenamento."""
    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:11]}"
    if len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:10]}"
    return digits


class AfrWellhubPortal(http.Controller):
    def _wellhub_company(self):
        """Empresa do website atual (cadastro multi-empresa alinhado ao site)."""
        website = getattr(request, "website", None)
        if website and website.company_id:
            return website.company_id
        return request.env.company.sudo()

    def _activation_asaas_email_preview_vals(self, collab):
        """Dados para reproduzir na página o layout típico do e-mail de cobrança Asaas."""
        collab = collab.sudo()
        company = collab.company_id.sudo()
        partner = company.partner_id.sudo()
        env = request.env
        lang = env.context.get("lang") or "pt_BR"
        currency = company.currency_id
        amount = 0.0
        try:
            amount = float(env["afr.wellhub.asaas.api"].subscription_value_for_asaas(collab))
        except Exception:
            amount = float(collab.asaas_charge_value_preview or 0.0)
        if currency and amount:
            amount_str = format_amount(env, amount, currency, lang_code=lang)
        else:
            amount_str = "—"
        due = collab.next_due_date or fields.Date.context_today(collab)
        due_str = format_date(env, due, lang_code=lang) if due else "—"
        cnpj = (partner.vat or "").strip() or "—"
        description = _("[Assinatura recorrente Wellhub] %s") % (collab.name or "")
        icp = env["ir.config_parameter"].sudo()
        env_type = (icp.get_param("afr_wellhub.asaas_environment", "sandbox") or "sandbox").strip()
        asaas_host = (
            "sandbox.asaas.com" if env_type == "sandbox" else "www.asaas.com"
        )
        preview_link_example = f"https://{asaas_host}/i/…"
        # Linhas do rodapé (como no e-mail Asaas): contatos da empresa.
        footer_lines = []
        if partner.name:
            footer_lines.append(partner.name.strip())
        if partner.vat:
            footer_lines.append(partner.vat.strip())
        if partner.email:
            footer_lines.append(partner.email.strip())
        phone = (partner.phone or partner.mobile or "").strip()
        if phone:
            footer_lines.append(phone)
        street_line = ", ".join(
            p for p in (partner.street or "", partner.street2 or "") if p.strip()
        ).strip()
        if street_line:
            footer_lines.append(street_line)
        loc_parts = []
        if partner.zip:
            loc_parts.append(partner.zip.strip())
        if partner.city:
            loc_parts.append(partner.city.strip())
        if partner.state_id:
            loc_parts.append(partner.state_id.name.strip())
        if loc_parts:
            footer_lines.append(" — ".join(loc_parts))
        return {
            "show_asaas_email_preview": True,
            "preview_company_name": company.name or "—",
            "preview_company_cnpj": cnpj,
            "preview_customer_name": collab.name or "—",
            "preview_amount_str": amount_str,
            "preview_due_str": due_str,
            "preview_description": description,
            "preview_footer_lines": footer_lines,
            "preview_link_example": preview_link_example,
        }

    _VALID_BR_UFS = frozenset({
        "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA",
        "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN",
        "RS", "RO", "RR", "SC", "SP", "SE", "TO",
    })

    def _validate_signup_payload(self, post):
        """Valida nome, e-mail (normalizado), telefone BR, CPF e endereço (exigido pelo Asaas Checkout)."""
        name = (post.get("name") or "").strip()
        email = (post.get("email") or "").strip()
        phone = (post.get("phone") or "").strip()
        cpf_cnpj = (post.get("cpf_cnpj") or "").strip()
        street = (post.get("street") or "").strip()
        street_number = (post.get("street_number") or "").strip()
        postal_code = (post.get("postal_code") or "").strip()
        city = (post.get("city") or "").strip()
        state_uf = (post.get("state_uf") or "").strip().upper()
        if len(name) < 2:
            raise ValidationError(_("Informe o nome completo."))
        email_norm = email_normalize(email, strict=False)
        if not email_norm:
            raise ValidationError(_("Informe um e-mail válido."))

        phone_digits = re.sub(r"\D", "", phone)
        if not _br_phone_digits_valid(phone_digits):
            raise ValidationError(
                _(
                    "Informe um telefone válido com DDD: 10 dígitos (fixo) ou 11 (celular), "
                    "ex.: (98) 98159-9692."
                )
            )

        cpf_digits = re.sub(r"\D", "", cpf_cnpj)
        if len(cpf_digits) != 11:
            raise ValidationError(_("O CPF deve ter 11 dígitos."))
        if not _cpf_digits_valid(cpf_digits):
            raise ValidationError(_("CPF inválido (dígitos verificadores)."))

        if not street:
            raise ValidationError(_("Informe o logradouro (rua/avenida)."))
        if not street_number:
            raise ValidationError(_("Informe o número do endereço."))
        cep_digits = re.sub(r"\D", "", postal_code)
        if len(cep_digits) != 8:
            raise ValidationError(_("O CEP deve ter 8 dígitos."))
        if not city:
            raise ValidationError(_("Informe a cidade."))
        if state_uf not in self._VALID_BR_UFS:
            raise ValidationError(_("Selecione uma UF válida."))

        return {
            "name": name,
            "email": email_norm,
            "phone": _format_br_phone_display(phone_digits),
            "cpf_cnpj": cpf_digits,
            "street": street,
            "street_number": street_number,
            "postal_code": cep_digits,
            "city": city,
            "state_uf": state_uf,
        }

    @http.route(
        "/afr_wellhub/inscricao",
        type="http",
        auth="public",
        website=True,
        methods=["GET"],
    )
    def wellhub_inscricao_get(self, **kwargs):
        return request.render(
            "afr_wellhub.portal_wellhub_inscricao_form",
            {"error": None, "values": {}},
        )

    @http.route(
        "/afr_wellhub/inscricao",
        type="http",
        auth="public",
        website=True,
        methods=["POST"],
        csrf=True,
    )
    def wellhub_inscricao_post(self, **post):
        error = None
        values = {
            "name": post.get("name") or "",
            "email": post.get("email") or "",
            "phone": post.get("phone") or "",
            "cpf_cnpj": post.get("cpf_cnpj") or "",
            "street": post.get("street") or "",
            "street_number": post.get("street_number") or "",
            "postal_code": post.get("postal_code") or "",
            "city": post.get("city") or "",
            "state_uf": (post.get("state_uf") or "").upper(),
        }
        try:
            payload = self._validate_signup_payload(post)
        except ValidationError as e:
            error = e.args[0]
            return request.render(
                "afr_wellhub.portal_wellhub_inscricao_form",
                {"error": error, "values": values},
            )

        Collab = request.env["wellhub.collaborator"].sudo()
        company = self._wellhub_company()
        domain = [
            ("email", "=ilike", payload["email"]),
            ("company_id", "=", company.id),
        ]
        existing = Collab.search(domain, limit=1)

        try:
            if existing:
                if existing.signup_pending:
                    portal_vals = Collab._prepare_portal_signup_collaborator_vals()
                    existing.with_context(afr_wellhub_skip_asaas_sync=True).write(
                        {
                            "signup_token": Collab._portal_new_signup_token(),
                            "signup_token_expiry": Collab._portal_signup_token_expiry_string(),
                            "name": payload["name"],
                            "phone": payload["phone"],
                            "cpf_cnpj": payload["cpf_cnpj"],
                            "street": payload["street"],
                            "street_number": payload["street_number"],
                            "postal_code": payload["postal_code"],
                            "city": payload["city"],
                            "state_uf": payload["state_uf"],
                            "portal_inscription": True,
                            **portal_vals,
                        }
                    )
                    collab = existing
                else:
                    error = _(
                        "Já existe um cadastro ativo para este e-mail. "
                        "Em caso de dúvida, entre em contato com o suporte."
                    )
                    return request.render(
                        "afr_wellhub.portal_wellhub_inscricao_form",
                        {"error": error, "values": values},
                    )
            else:
                collab = Collab.with_context(afr_wellhub_skip_asaas_sync=True).create(
                    {
                        "name": payload["name"],
                        "email": payload["email"],
                        "phone": payload["phone"],
                        "cpf_cnpj": payload["cpf_cnpj"],
                        "street": payload["street"],
                        "street_number": payload["street_number"],
                        "postal_code": payload["postal_code"],
                        "city": payload["city"],
                        "state_uf": payload["state_uf"],
                        "company_id": company.id,
                        "wellhub_subscription_enrolled": False,
                        "signup_pending": True,
                        "portal_inscription": True,
                        "signup_token": Collab._portal_new_signup_token(),
                        "signup_token_expiry": Collab._portal_signup_token_expiry_string(),
                        **Collab._prepare_portal_signup_collaborator_vals(),
                    }
                )
            template = request.env.ref(
                "afr_wellhub.mail_template_wellhub_signup_activation",
                raise_if_not_found=False,
            )
            if template:
                template.sudo().send_mail(collab.id, force_send=True)
            else:
                _logger.error(
                    "Template afr_wellhub.mail_template_wellhub_signup_activation não encontrado."
                )
                error = _("Configuração de e-mail incompleta. Contate o administrador.")
                return request.render(
                    "afr_wellhub.portal_wellhub_inscricao_form",
                    {"error": error, "values": values},
                )
        except ValidationError as e:
            error = e.args[0]
            return request.render(
                "afr_wellhub.portal_wellhub_inscricao_form",
                {"error": error, "values": values},
            )
        except Exception:
            _logger.exception("Wellhub inscrição: falha ao gravar ou enviar e-mail.")
            error = _("Não foi possível concluir a inscrição. Tente novamente mais tarde.")
            return request.render(
                "afr_wellhub.portal_wellhub_inscricao_form",
                {"error": error, "values": values},
            )

        return request.render(
            "afr_wellhub.portal_wellhub_inscricao_done",
            {"email": payload["email"]},
        )

    @http.route(
        "/afr_wellhub/inscricao/ativar",
        type="http",
        auth="public",
        website=True,
        methods=["GET"],
    )
    def wellhub_inscricao_ativar(self, token=None, **kwargs):
        if not token or not isinstance(token, str):
            return request.render(
                "afr_wellhub.portal_wellhub_ativar_result",
                {
                    "ok": False,
                    "message": _("Link inválido."),
                    "show_asaas_email_preview": False,
                },
            )
        token = token.strip()
        Collab = request.env["wellhub.collaborator"].sudo()
        collab = Collab.search(
            [("signup_token", "=", token)],
            limit=1,
        )
        if not collab:
            return request.render(
                "afr_wellhub.portal_wellhub_ativar_result",
                {
                    "ok": False,
                    "message": _(
                        "Link inválido ou inscrição já confirmada. "
                        "Se precisar de ajuda, contate o suporte."
                    ),
                    "show_asaas_email_preview": False,
                },
            )
        try:
            status, payload = collab.action_portal_activate_subscription()
        except UserError as e:
            return request.render(
                "afr_wellhub.portal_wellhub_ativar_result",
                {
                    "ok": False,
                    "message": str(e),
                    "show_asaas_email_preview": False,
                },
            )
        except Exception:
            _logger.exception("Wellhub ativação: falha para colaborador id=%s", collab.id)
            return request.render(
                "afr_wellhub.portal_wellhub_ativar_result",
                {
                    "ok": False,
                    "message": _("Não foi possível ativar a assinatura. Tente mais tarde."),
                    "show_asaas_email_preview": False,
                },
            )
        if status == "ready":
            return request.redirect(payload, code=303)
        if status == "failed":
            return request.render(
                "afr_wellhub.portal_wellhub_ativar_result",
                {
                    "ok": False,
                    "message": payload,
                    "show_asaas_email_preview": False,
                },
            )
        # status == "pending": spinner + auto-refresh enquanto thread async cria o checkout.
        return request.render(
            "afr_wellhub.portal_wellhub_preparando_checkout",
            {"elapsed_seconds": payload, "token": token},
        )

    @http.route(
        "/afr_wellhub/checkout/sucesso",
        type="http",
        auth="public",
        website=True,
        methods=["GET"],
    )
    def wellhub_checkout_sucesso(self, **kwargs):
        return request.render("afr_wellhub.portal_wellhub_checkout_sucesso", {})

    @http.route(
        "/afr_wellhub/checkout/cancelado",
        type="http",
        auth="public",
        website=True,
        methods=["GET"],
    )
    def wellhub_checkout_cancelado(self, **kwargs):
        return request.render("afr_wellhub.portal_wellhub_checkout_cancelado", {})

    @http.route(
        "/afr_wellhub/checkout/expirado",
        type="http",
        auth="public",
        website=True,
        methods=["GET"],
    )
    def wellhub_checkout_expirado(self, **kwargs):
        return request.render("afr_wellhub.portal_wellhub_checkout_expirado", {})

    @http.route(
        "/afr_wellhub/inscricao/reenviar",
        type="http",
        auth="public",
        website=True,
        methods=["GET"],
    )
    def wellhub_inscricao_reenviar_get(self, **kwargs):
        return request.render(
            "afr_wellhub.portal_wellhub_reenviar_form",
            {"error": None},
        )

    @http.route(
        "/afr_wellhub/inscricao/reenviar",
        type="http",
        auth="public",
        website=True,
        methods=["POST"],
        csrf=True,
    )
    def wellhub_inscricao_reenviar_post(self, **post):
        email_raw = (post.get("email") or "").strip()
        email_norm = email_normalize(email_raw, strict=False)
        if not email_norm:
            return request.render(
                "afr_wellhub.portal_wellhub_reenviar_form",
                {"error": _("Informe um e-mail válido."), "email_value": email_raw},
            )
        Collab = request.env["wellhub.collaborator"].sudo()
        company = self._wellhub_company()
        # Reenvio aceito também para colaboradores que clicaram em ativar (enrolled=True) mas
        # ainda não pagaram o checkout — necessário para recuperar fluxo se o e-mail original foi
        # perdido após abandono do checkout Asaas.
        collab = Collab.search(
            [
                ("email", "=ilike", email_norm),
                ("company_id", "=", company.id),
                ("asaas_subscription_id", "=", False),
                "|",
                ("signup_pending", "=", True),
                ("wellhub_subscription_enrolled", "=", True),
            ],
            limit=1,
        )
        if collab:
            try:
                collab.with_context(afr_wellhub_skip_asaas_sync=True).write(
                    {
                        "signup_token": Collab._portal_new_signup_token(),
                        "signup_token_expiry": Collab._portal_signup_token_expiry_string(),
                    }
                )
                template = request.env.ref(
                    "afr_wellhub.mail_template_wellhub_signup_activation",
                    raise_if_not_found=False,
                )
                if template:
                    template.sudo().send_mail(collab.id, force_send=True)
                else:
                    _logger.error(
                        "Wellhub reenvio: template mail_template_wellhub_signup_activation não encontrado."
                    )
            except Exception:
                _logger.exception("Wellhub reenvio: falha ao renovar token ou enviar e-mail.")
        # Sempre retorna mensagem genérica (não revela se e-mail existe)
        return request.render(
            "afr_wellhub.portal_wellhub_reenviar_done",
            {},
        )
