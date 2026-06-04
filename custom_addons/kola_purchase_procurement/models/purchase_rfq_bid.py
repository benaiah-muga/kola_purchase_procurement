from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PurchaseRfqBid(models.Model):
    _name = "purchase.rfq.bid"
    _description = "Supplier Bid"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "order_id, amount_total, id"

    name = fields.Char(default=lambda self: _("New Bid"), required=True, copy=False)
    order_id = fields.Many2one(
        "purchase.order",
        string="RFQ",
        required=True,
        ondelete="cascade",
        domain="[('state', 'in', ('draft', 'sent'))]",
    )
    vendor_id = fields.Many2one(
        "res.partner",
        string="Vendor",
        required=True,
        domain="[('supplier_rank', '>', 0)]",
        tracking=True,
    )
    bid_date = fields.Date(default=fields.Date.context_today, required=True)
    validity_date = fields.Date(string="Valid Until")
    delivery_date = fields.Datetime(string="Promised Delivery")
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    line_ids = fields.One2many("purchase.rfq.bid.line", "bid_id", string="Bid Lines", copy=True)
    amount_total = fields.Monetary(compute="_compute_amount_total", store=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("won", "Won"),
            ("lost", "Lost"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    notes = fields.Text()

    @api.depends("line_ids.price_subtotal")
    def _compute_amount_total(self):
        for bid in self:
            bid.amount_total = sum(bid.line_ids.mapped("price_subtotal"))

    @api.constrains("order_id", "vendor_id")
    def _check_vendor_assigned_to_rfq(self):
        for bid in self:
            if bid.order_id.vendor_ids and bid.vendor_id not in bid.order_id.vendor_ids:
                raise ValidationError(_("The bid vendor must be one of the vendors assigned to the RFQ."))

    @api.onchange("order_id")
    def _onchange_order_id(self):
        if self.order_id:
            self.currency_id = self.order_id.currency_id
            self.company_id = self.order_id.company_id

    def action_copy_rfq_lines(self):
        for bid in self:
            bid.line_ids.unlink()
            bid.line_ids = [
                (
                    0,
                    0,
                    {
                        "product_id": line.product_id.id,
                        "name": line.name,
                        "quantity": line.product_qty,
                        "product_uom_id": line.product_uom_id.id,
                        "price_unit": line.price_unit,
                    },
                )
                for line in bid.order_id.order_line
                if not line.display_type and line.product_id
            ]
        return True

    def action_submit(self):
        self.write({"state": "submitted"})
        return True

    def action_select_winner(self):
        for bid in self:
            if not bid.line_ids:
                raise UserError(_("Add bid lines before selecting a winner."))
            bid.order_id._apply_winning_bid(bid)
        return True


class PurchaseRfqBidLine(models.Model):
    _name = "purchase.rfq.bid.line"
    _description = "Supplier Bid Line"
    _order = "bid_id, id"

    bid_id = fields.Many2one("purchase.rfq.bid", string="Bid", required=True, ondelete="cascade")
    product_id = fields.Many2one("product.product", string="Product", required=True, domain="[('purchase_ok', '=', True)]")
    name = fields.Char(string="Description", required=True)
    quantity = fields.Float(default=1.0, required=True)
    product_uom_id = fields.Many2one("uom.uom", string="Unit of Measure", required=True)
    price_unit = fields.Monetary(string="Unit Price", required=True)
    currency_id = fields.Many2one(related="bid_id.currency_id", store=True, readonly=True)
    price_subtotal = fields.Monetary(compute="_compute_price_subtotal", store=True)

    @api.depends("quantity", "price_unit")
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.display_name
            self.product_uom_id = self.product_id.uom_id
