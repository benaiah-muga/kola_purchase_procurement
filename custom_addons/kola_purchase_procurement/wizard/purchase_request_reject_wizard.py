from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PurchaseRequestRejectWizard(models.TransientModel):
    """Collect a mandatory reason before rejecting a whole purchase request."""
    _name = "purchase.request.reject.wizard"
    _description = "Reject Purchase Request"

    request_id = fields.Many2one(
        "purchase.request",
        string="Purchase Request",
        required=True,
        ondelete="cascade",
    )
    request_name = fields.Char(related="request_id.name", string="Reference", readonly=True)
    reason = fields.Text(string="Rejection Reason", required=True)

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        active_id = self.env.context.get("active_id")
        if active_id and "request_id" in fields_list:
            defaults.setdefault("request_id", active_id)
        return defaults

    def action_confirm_reject(self):
        self.ensure_one()
        if not self.reason or not self.reason.strip():
            raise UserError(_("A rejection reason is required."))
        self.request_id.write({"rejection_reason": self.reason})
        self.request_id.action_reject()
        return {"type": "ir.actions.act_window_close"}


class PurchaseRequestLineRejectWizard(models.TransientModel):
    """Collect a mandatory reason before rejecting an individual request line."""
    _name = "purchase.request.line.reject.wizard"
    _description = "Reject Purchase Request Line"

    line_ids = fields.Many2many(
        "purchase.request.line",
        "purchase_request_line_reject_wizard_rel",
        "wizard_id",
        "line_id",
        string="Lines to Reject",
        required=True,
    )
    reason = fields.Text(string="Rejection Reason", required=True)

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        active_ids = self.env.context.get("active_ids") or self.env.context.get("default_line_ids") or []
        if active_ids and isinstance(active_ids[0], (list, tuple)) and active_ids[0][0] == 6:
            active_ids = active_ids[0][2]
        if active_ids and "line_ids" in fields_list:
            defaults.setdefault("line_ids", [(6, 0, active_ids)])
        return defaults

    def action_confirm_reject(self):
        self.ensure_one()
        if not self.reason or not self.reason.strip():
            raise UserError(_("A rejection reason is required."))
        self.line_ids.write({"rejection_reason": self.reason})
        self.line_ids.action_reject_line()
        return {"type": "ir.actions.act_window_close"}
