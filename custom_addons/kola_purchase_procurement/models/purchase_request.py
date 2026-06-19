from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PurchaseRequest(models.Model):
    _name = "purchase.request"
    _description = "Purchase Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(default=lambda self: _("New"), required=True, copy=False, readonly=True)
    requester_id = fields.Many2one(
        "res.users",
        string="Requested By",
        default=lambda self: self.env.user,
        required=True,
        readonly=True,
    )
    employee_id = fields.Many2one(
        "hr.employee",
        string="Employee",
        default=lambda self: self.env.user.employee_id,
    )
    department_id = fields.Many2one(related="employee_id.department_id", string="Department", store=True, readonly=True)
    request_date = fields.Date(default=fields.Date.context_today, required=True)
    needed_date = fields.Date(string="Needed By")
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one("res.currency", related="company_id.currency_id", readonly=True)
    vendor_ids = fields.Many2many(
        "res.partner",
        "purchase_request_vendor_rel",
        "request_id",
        "partner_id",
        string="Suggested Vendors",
        domain="[('supplier_rank', '>', 0)]",
    )
    line_ids = fields.One2many("purchase.request.line", "request_id", string="Request Lines", copy=True)
    rfq_id = fields.Many2one("purchase.order", string="RFQ", readonly=True, copy=False)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("rfq_created", "RFQ Created"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    # Reason for rejecting the whole request. Required whenever the request is
    # rejected as a whole (see constrains + the rejection wizard).
    rejection_reason = fields.Text(
        string="Rejection Reason",
        copy=False,
        tracking=True,
    )
    rejected_line_count = fields.Integer(
        string="Rejected Lines",
        compute="_compute_rejected_line_count",
    )
    notes = fields.Text()

    @api.depends("line_ids.state")
    def _compute_rejected_line_count(self):
        for request in self:
            request.rejected_line_count = len(request.line_ids.filtered(lambda l: l.state == "rejected"))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("purchase.request") or _("New")
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_submit(self):
        for request in self:
            if not request.line_ids:
                raise UserError(_("Add at least one product line before submitting the request."))
            open_lines = request.line_ids.filtered(lambda l: l.state != "rejected")
            if not open_lines:
                raise UserError(_("All lines are rejected. There is nothing to submit."))
            request.state = "submitted"
        return True

    def action_approve(self):
        self.write({"state": "approved"})
        return True

    def action_reject(self):
        """Reject the whole request. A reason must have been recorded first.

        The UI drives this through the rejection wizard so the reason is
        mandatory. Calling this method directly without a reason raises so the
        rule is enforced server-side too.
        """
        for request in self:
            if not request.rejection_reason or not request.rejection_reason.strip():
                raise UserError(_("A rejection reason is required before rejecting the request."))
        self.write({"state": "rejected"})
        return True

    def action_reset_to_draft(self):
        # Keep the rejection reason on the chatter history but clear it on the
        # record so a fresh decision can be recorded if it is rejected again.
        self.write({"state": "draft", "rejection_reason": False})
        return True

    # ------------------------------------------------------------------
    # RFQ creation
    # ------------------------------------------------------------------
    def action_create_rfq(self):
        PurchaseOrder = self.env["purchase.order"]
        for request in self:
            if request.state != "approved":
                raise UserError(_("Only approved purchase requests can be converted into RFQs."))
            if not request.vendor_ids:
                raise UserError(_("Add at least one suggested vendor before creating the RFQ."))

            rfq_lines = request.line_ids.filtered(lambda l: l.state != "rejected")
            if not rfq_lines:
                raise UserError(_(
                    "All lines are rejected. There is nothing to send to vendors."
                ))

            order_vals = {
                "partner_id": request.vendor_ids[0].id,
                "vendor_ids": [(6, 0, request.vendor_ids.ids)],
                "purchase_request_id": request.id,
                "origin": request.name,
                "company_id": request.company_id.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": line.product_id.id,
                            "name": line.description or line.product_id.display_name,
                            "product_qty": line.quantity,
                            "product_uom_id": line.product_uom_id.id,
                            "price_unit": line.estimated_price,
                            "date_planned": fields.Datetime.now(),
                        },
                    )
                    for line in rfq_lines
                ],
            }
            request.rfq_id = PurchaseOrder.create(order_vals)
            request.state = "rfq_created"
        return self.action_view_rfq()

    def action_view_rfq(self):
        self.ensure_one()
        if not self.rfq_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("RFQ"),
            "res_model": "purchase.order",
            "res_id": self.rfq_id.id,
            "view_mode": "form",
        }

    @api.constrains("state", "rejection_reason")
    def _check_rejection_has_reason(self):
        for request in self:
            if request.state == "rejected" and (
                not request.rejection_reason or not request.rejection_reason.strip()
            ):
                raise ValidationError(_(
                    "Request %(name)s cannot be rejected without a reason.",
                    name=request.name,
                ))


class PurchaseRequestLine(models.Model):
    _name = "purchase.request.line"
    _description = "Purchase Request Line"
    _order = "request_id, id"

    request_id = fields.Many2one("purchase.request", required=True, ondelete="cascade")
    product_id = fields.Many2one("product.product", string="Product", required=True, domain="[('purchase_ok', '=', True)]")
    description = fields.Char(required=True)
    quantity = fields.Float(default=1.0, required=True)
    product_uom_id = fields.Many2one("uom.uom", string="Unit of Measure", required=True)
    estimated_price = fields.Monetary(string="Estimated Unit Price")
    currency_id = fields.Many2one(related="request_id.currency_id", readonly=True)
    state = fields.Selection(
        [
            ("open", "Open"),
            ("rejected", "Rejected"),
        ],
        default="open",
        required=True,
        string="Line Status",
    )
    rejection_reason = fields.Text(string="Rejection Reason", copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            product = self.env["product.product"].browse(vals.get("product_id"))
            if product:
                vals.setdefault("description", product.display_name)
                vals.setdefault("product_uom_id", product.uom_id.id)
                vals.setdefault("estimated_price", product.standard_price)
        return super().create(vals_list)

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.description = self.product_id.display_name
            self.product_uom_id = self.product_id.uom_id
            self.estimated_price = self.product_id.standard_price

    def action_reject_line(self):
        """Reject the selected line(s). A reason must be supplied afterwards.

        The line-reject wizard collects the reason; this method only flips the
        line to ``rejected`` so the wizard has a record to act on. The mandatory
        reason is enforced by the constrains below.
        """
        for line in self:
            line.state = "rejected"
        return True

    def action_open_reject_wizard(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Reject Request Line"),
            "res_model": "purchase.request.line.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_line_ids": [(6, 0, self.ids)]},
        }

    def action_restore_line(self):
        for line in self:
            line.write({"state": "open", "rejection_reason": False})
        return True

    @api.constrains("state", "rejection_reason")
    def _check_line_rejection_has_reason(self):
        for line in self:
            if line.state == "rejected" and (
                not line.rejection_reason or not line.rejection_reason.strip()
            ):
                raise ValidationError(_(
                    "Line for %(product)s cannot be rejected without a reason.",
                    product=line.product_id.display_name,
                ))
