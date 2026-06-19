from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PurchaseRfqBid(models.Model):
    _name = "purchase.rfq.bid"
    _description = "Supplier Bid"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "order_id, amount_total, id"

    name = fields.Char(default=lambda self: _("New Bid"), required=True, copy=False, readonly=True)
    order_id = fields.Many2one(
        "purchase.order",
        string="RFQ",
        required=True,
        ondelete="cascade",
        domain="[('state', 'in', ('draft', 'sent', 'bidding'))]",
    )
    vendor_id = fields.Many2one(
        "res.partner",
        string="Vendor",
        required=True,
        domain="[('supplier_rank', '>', 0)]",
        tracking=True,
    )
    order_state = fields.Selection(related="order_id.state", string="RFQ State", store=True)
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
    awarded_amount = fields.Monetary(
        string="Awarded Total",
        compute="_compute_awarded_amount",
        store=True,
        help="Subtotal of the bid lines that have been awarded to this vendor.",
    )
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

    # ------------------------------------------------------------------
    # Sequencing: BD001, BD002, ...
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == _("New Bid"):
                vals["name"] = self.env["ir.sequence"].next_by_code("purchase.rfq.bid") or _("New Bid")
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends("line_ids.price_subtotal")
    def _compute_amount_total(self):
        for bid in self:
            bid.amount_total = sum(bid.line_ids.mapped("price_subtotal"))

    @api.depends("line_ids.price_subtotal", "line_ids.is_awarded")
    def _compute_awarded_amount(self):
        for bid in self:
            awarded = bid.line_ids.filtered("is_awarded")
            bid.awarded_amount = sum(awarded.mapped("price_subtotal"))

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains("order_id", "vendor_id")
    def _check_vendor_assigned_to_rfq(self):
        for bid in self:
            if bid.order_id.vendor_ids and bid.vendor_id not in bid.order_id.vendor_ids:
                raise ValidationError(_("The bid vendor must be one of the vendors assigned to the RFQ."))

    @api.constrains("order_id", "vendor_id")
    def _check_unique_vendor_bid(self):
        """A vendor may submit only one bid per RFQ."""
        for bid in self:
            duplicates = self.search([
                ("order_id", "=", bid.order_id.id),
                ("vendor_id", "=", bid.vendor_id.id),
                ("id", "!=", bid.id),
            ], limit=1)
            if duplicates:
                raise ValidationError(_(
                    "Vendor %(vendor)s already has a bid (%(existing)s) for this RFQ.",
                    vendor=bid.vendor_id.display_name,
                    existing=duplicates.name,
                ))

    @api.onchange("order_id")
    def _onchange_order_id(self):
        if self.order_id:
            self.currency_id = self.order_id.currency_id
            self.company_id = self.order_id.company_id

    # ------------------------------------------------------------------
    # Bid lifecycle
    # ------------------------------------------------------------------
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
        for bid in self:
            if not bid.line_ids:
                raise UserError(_("Add bid lines before submitting the bid."))
        self.write({"state": "submitted"})
        return True

    def action_set_to_draft(self):
        self.write({"state": "draft"})
        return True

    # ------------------------------------------------------------------
    # Awarding
    # ------------------------------------------------------------------
    def action_select_winner(self):
        """Whole-bid winner: award every line of this bid on its RFQ.

        This is the simple single-vendor path. Procurement can instead award
        individual lines across several bids by ticking ``is_awarded`` directly
        in the bid list and finalizing bidding on the RFQ.
        """
        for bid in self:
            if bid.order_id.state != "bidding":
                raise UserError(_("Bids can only be awarded while the RFQ is in the Bidding stage."))
            if not bid.line_ids:
                raise UserError(_("Add bid lines before selecting a winner."))
            bid.order_id._apply_winning_bid(bid)
        return True

    def action_toggle_award(self):
        """Toggle the ``is_awarded`` flag on every line of the bid.

        Exposed as a list-row button so procurement can award a vendor's whole
        bid with one click, or award individual lines by editing the bid form.
        """
        for bid in self:
            if bid.order_id.state != "bidding":
                raise UserError(_("Bid lines can only be awarded while the RFQ is in the Bidding stage."))
            awarded = all(line.is_awarded for line in bid.line_ids)
            bid.line_ids.write({"is_awarded": not awarded})
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
    is_awarded = fields.Boolean(
        string="Awarded",
        copy=False,
        help="Tick when procurement awards this line to the vendor. The RFQ is "
             "finalized into one purchase order per winning vendor.",
    )
    vendor_id = fields.Many2one(related="bid_id.vendor_id", string="Vendor", store=True)

    @api.depends("quantity", "price_unit")
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.display_name
            self.product_uom_id = self.product_id.uom_id

    @api.constrains("is_awarded")
    def _check_single_award_per_product(self):
        """A product may be awarded to only one vendor on the same RFQ."""
        for line in self.filtered("is_awarded"):
            if line.bid_id.order_id.state != "bidding":
                raise ValidationError(_("Bid lines can only be awarded while the RFQ is in the Bidding stage."))
            if not line.bid_id.order_id:
                continue
            same_product_awards = self.search([
                ("product_id", "=", line.product_id.id),
                ("is_awarded", "=", True),
                ("bid_id.order_id", "=", line.bid_id.order_id.id),
                ("id", "!=", line.id),
            ], limit=1)
            if same_product_awards:
                raise ValidationError(_(
                    "Product %(product)s is already awarded to %(vendor)s on this RFQ. "
                    "A product can only be awarded to one vendor.",
                    product=line.product_id.display_name,
                    vendor=same_product_awards.bid_id.vendor_id.display_name,
                ))
