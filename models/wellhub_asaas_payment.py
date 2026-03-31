# -*- coding: utf-8 -*-
"""Espelho de cobranças Asaas; status conforme retorno da API (ex.: RECEIVED, OVERDUE, PENDING).

Quando uma cobrança deixa de aparecer na listagem GET /v3/payments após sincronização, o status
local é definido como STATUS_EXCLUDED (ausência na API para aquele cliente/assinatura).
Os valores oficiais retornados pelo Asaas estão na documentação (Payment status); EXCLUDED é
valor usado neste módulo apenas para esse caso de espelho.
"""

from odoo import api, fields, models

# Literal usado no campo status quando a cobrança não existe mais na listagem sincronizada.
STATUS_EXCLUDED = "EXCLUDED"


class WellhubAsaasPayment(models.Model):
    _name = "wellhub.asaas.payment"
    _description = "Cobrança Asaas (Wellhub)"
    _order = "due_date desc, id desc"

    name = fields.Char(
        string="Referência",
        compute="_compute_name",
        store=True,
    )
    asaas_payment_id = fields.Char(
        string="ID Asaas",
        required=True,
        index=True,
    )
    collaborator_id = fields.Many2one(
        "wellhub.collaborator",
        string="Colaborador",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="collaborator_id.company_id",
        store=True,
        readonly=True,
    )
    asaas_customer_id = fields.Char(string="Cliente Asaas", index=True)
    asaas_subscription_id = fields.Char(string="Assinatura Asaas", index=True)
    status = fields.Char(
        string="Status",
        help="Valor retornado pela API Asaas para o campo status da cobrança. "
        "EXCLUDED: ausente na última sincronização (GET /v3/payments) para o colaborador.",
        index=True,
    )
    value = fields.Float(string="Valor")
    net_value = fields.Float(string="Valor líquido")
    due_date = fields.Date(string="Vencimento")
    payment_date = fields.Date(string="Data de pagamento")
    invoice_url = fields.Char(string="URL fatura")
    bank_slip_url = fields.Char(string="URL boleto")
    confirmation_date = fields.Date(string="Data de confirmação")

    _sql_constraints = [
        (
            "asaas_payment_id_unique",
            "unique(asaas_payment_id)",
            "Já existe um registro para esta cobrança Asaas.",
        ),
    ]

    @api.depends("asaas_payment_id")
    def _compute_name(self):
        for rec in self:
            rec.name = rec.asaas_payment_id or "—"

    @api.model
    def _parse_asaas_date(self, value):
        if not value:
            return False
        if isinstance(value, str) and len(value) >= 10:
            return fields.Date.from_string(value[:10])
        return False

    @api.model
    def upsert_from_asaas_payment_dict(self, payment, collaborator):
        """Atualiza ou cria registro a partir do objeto payment do JSON Asaas (webhook ou GET)."""
        if not payment or not isinstance(payment, dict):
            return self.browse()
        pay_id = payment.get("id")
        if not pay_id:
            return self.browse()
        vals = {
            "asaas_payment_id": pay_id,
            "collaborator_id": collaborator.id,
            "asaas_customer_id": payment.get("customer") or "",
            "asaas_subscription_id": payment.get("subscription") or "",
            "status": payment.get("status") or "",
            "value": float(payment.get("value") or 0),
            "net_value": float(payment.get("netValue") or 0),
            "due_date": self._parse_asaas_date(payment.get("dueDate")),
            "payment_date": self._parse_asaas_date(payment.get("paymentDate")),
            "invoice_url": payment.get("invoiceUrl") or "",
            "bank_slip_url": payment.get("bankSlipUrl") or "",
            "confirmation_date": self._parse_asaas_date(
                payment.get("confirmationDate")
            ),
        }
        existing = self.search(
            [("asaas_payment_id", "=", pay_id)], limit=1
        )
        if existing:
            existing.write(vals)
            return existing
        return self.create(vals)

    @api.model
    def mark_absent_from_sync_as_excluded(self, collaborator, seen_asaas_payment_ids):
        """Cobranças locais cujo id Asaas não veio na listagem passam a status EXCLUDED."""
        seen = {str(x) for x in (seen_asaas_payment_ids or []) if x is not None}
        local = self.search([("collaborator_id", "=", collaborator.id)])
        to_update = local.filtered(
            lambda p: str(p.asaas_payment_id or "") not in seen
            and (p.status or "") != STATUS_EXCLUDED
        )
        if to_update:
            to_update.write({"status": STATUS_EXCLUDED})
        return to_update
