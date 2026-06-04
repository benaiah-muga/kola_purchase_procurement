from odoo import fields, models, _
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    vendor_ids = fields.Many2many(
        "res.partner",
        "purchase_order_vendor_rel",
        "order_id",
        "partner_id",
        string="Assigned Vendors",
        domain="[('supplier_rank', '>', 0), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="Vendors invited to submit bids for this RFQ.",
    )
    bid_ids = fields.One2many(
        "purchase.rfq.bid",
        "order_id",
        string="Supplier Bids",
        copy=False,
    )
    bid_count = fields.Integer(string="Bid Count", compute="_compute_bid_count")
    winning_bid_id = fields.Many2one(
        "purchase.rfq.bid",
        string="Winning Bid",
        copy=False,
        readonly=True,
    )
    purchase_request_id = fields.Many2one(
        "purchase.request",
        string="Purchase Request",
        copy=False,
        readonly=True,
    )

    def _compute_bid_count(self):
        for order in self:
            order.bid_count = len(order.bid_ids)

    def action_create_bid(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Supplier Bid"),
            "res_model": "purchase.rfq.bid",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_order_id": self.id,
                "default_currency_id": self.currency_id.id,
                "default_company_id": self.company_id.id,
            },
        }

    def action_create_po_from_winner(self):
        for order in self:
            if not order.winning_bid_id:
                raise UserError(_("Select a winning bid before creating the purchase order."))
            if order.state not in ("draft", "sent"):
                continue
            order.button_confirm()
        return True

    def _apply_winning_bid(self, bid):
        self.ensure_one()
        if bid.order_id != self:
            raise UserError(_("The selected bid does not belong to this RFQ."))
        if bid.vendor_id not in self.vendor_ids:
            self.vendor_ids = [(4, bid.vendor_id.id)]

        self.partner_id = bid.vendor_id
        self.winning_bid_id = bid

        for bid_line in bid.line_ids:
            matching_line = self.order_line.filtered(
                lambda line: not line.display_type and line.product_id == bid_line.product_id
            )[:1]
            if matching_line:
                matching_line.write({
                    "price_unit": bid_line.price_unit,
                    "product_qty": bid_line.quantity,
                    "product_uom_id": bid_line.product_uom_id.id,
                    "date_planned": bid.delivery_date or matching_line.date_planned,
                })

        (self.bid_ids - bid).write({"state": "lost"})
        bid.state = "won"
