# -*- coding: utf-8 -*-
"""Webhook Asaas: cobranças com objeto `payment` no JSON.

Somente eventos e `billingType` alinhados à integração em cartão de crédito.
Referência: https://docs.asaas.com/docs/webhook-para-cobrancas
"""

import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# Eventos de cobrança processados quando `payment.billingType` é CREDIT_CARD (documentação Asaas).
_ASAAS_WEBHOOK_PAYMENT_EVENTS_CREDIT_CARD = frozenset(
    {
        "PAYMENT_CREATED",
        "PAYMENT_AUTHORIZED",
        "PAYMENT_CONFIRMED",
        "PAYMENT_RECEIVED",
        "PAYMENT_CREDIT_CARD_CAPTURE_REFUSED",
        "PAYMENT_OVERDUE",
        "PAYMENT_REFUNDED",
    }
)


class AfrWellhubAsaasWebhook(http.Controller):
    @http.route(
        "/afr_wellhub/asaas/webhook",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def asaas_webhook(self, **kwargs):
        """Valida `asaas-access-token`; processa só eventos da whitelist e cobrança CREDIT_CARD."""
        expected = (
            request.env["ir.config_parameter"]
            .sudo()
            .get_param("afr_wellhub.webhook_token", "")
        )
        received = (request.httprequest.headers.get("asaas-access-token") or "").strip()
        if not expected or received != expected:
            _logger.warning("Asaas webhook: token inválido ou não configurado.")
            return request.make_response("Unauthorized", status=401)

        try:
            raw = request.httprequest.data.decode("utf-8")
            body = json.loads(raw) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            return request.make_response("Bad Request", status=400)

        payment = body.get("payment")
        event = (body.get("event") or "").strip().upper()

        if not isinstance(payment, dict) or not payment.get("id"):
            _logger.debug(
                "Asaas webhook: ignorado (sem objeto payment ou id). event=%s", event or "—"
            )
            return request.make_response("OK", status=200)

        if event not in _ASAAS_WEBHOOK_PAYMENT_EVENTS_CREDIT_CARD:
            _logger.debug(
                "Asaas webhook: evento fora da whitelist (cartão), não processado. event=%s",
                event or "—",
            )
            return request.make_response("OK", status=200)

        billing = (payment.get("billingType") or "").strip().upper()
        if billing != "CREDIT_CARD":
            _logger.debug(
                "Asaas webhook: billingType não é cartão de crédito, não processado. "
                "event=%s billingType=%s payment_id=%s",
                event,
                billing or "—",
                payment.get("id"),
            )
            return request.make_response("OK", status=200)

        try:
            request.env["wellhub.collaborator"].sudo()._webhook_process_payment(
                payment
            )
        except Exception:
            _logger.exception("Asaas webhook: falha ao processar pagamento.")
        return request.make_response("OK", status=200)
