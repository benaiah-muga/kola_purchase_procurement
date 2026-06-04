from odoo import api, fields, models, _
from odoo.exceptions import UserError


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
    notes = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("purchase.request") or _("New")
        return super().create(vals_list)

    def action_submit(self):
        for request in self:
            if not request.line_ids:
                raise UserError(_("Add at least one product line before submitting the request."))
            request.state = "submitted"
        return True

    def action_approve(self):
        self.write({"state": "approved"})
        return True

    def action_reject(self):
        self.write({"state": "rejected"})
        return True

    def action_reset_to_draft(self):
        self.write({"state": "draft"})
        return True

    def action_create_rfq(self):
        PurchaseOrder = self.env["purchase.order"]
        for request in self:
            if request.state != "approved":
                raise UserError(_("Only approved purchase requests can be converted into RFQs."))
            if not request.vendor_ids:
                raise UserError(_("Add at least one suggested vendor before creating the RFQ."))

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
                    for line in request.line_ids
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

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.description = self.product_id.display_name
            self.product_uom_id = self.product_id.uom_id
            self.estimated_price = self.product_id.standard_price
