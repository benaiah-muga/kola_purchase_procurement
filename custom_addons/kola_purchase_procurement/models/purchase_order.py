from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    vendor_ids = fields.Many2many(
        "res.partner",
        "purchase_order_vendor_rel",
        "order_id",
        "partner_id",
        string="Vendors",
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
    # Summary helpers used by the form to guide non-technical users through bidding.
    awarded_line_count = fields.Integer(
        string="Awarded Lines",
        compute="_compute_awarded_summary",
    )
    winning_vendor_count = fields.Integer(
        string="Winning Vendors",
        compute="_compute_awarded_summary",
    )
    generated_po_ids = fields.One2many(
        "purchase.order",
        "bidding_source_id",
        string="Generated Purchase Orders",
        copy=False,
    )
    generated_po_count = fields.Integer(
        string="Created POs",
        compute="_compute_generated_po_count",
    )
    bidding_source_id = fields.Many2one(
        "purchase.order",
        string="Bidding Source RFQ",
        copy=False,
        readonly=True,
    )

    # The standard purchase order state is extended with two stages that structure
    # the procurement workflow: ``bidding`` opens bid collection right after the
    # RFQ has been sent, and ``done_bidding`` marks the RFQ as finalized once the
    # winning bids have been turned into purchase orders.
    state = fields.Selection(
        selection_add=[
            ("bidding", "Bidding"),
            ("done_bidding", "Bidding Done"),
        ],
        ondelete={"bidding": "set default", "done_bidding": "set default"},
    )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("partner_id") and vals.get("vendor_ids"):
                first_vendor_id = self._get_first_vendor_id_from_commands(vals["vendor_ids"])
                if first_vendor_id:
                    vals["partner_id"] = first_vendor_id

        orders = super().create(vals_list)
        orders._sync_vendor_ids_with_partner()
        return orders

    def write(self, vals):
        result = super().write(vals)
        if not self.env.context.get("skip_vendor_partner_sync"):
            if "vendor_ids" in vals:
                for order in self:
                    if order.vendor_ids and order.partner_id not in order.vendor_ids:
                        order.with_context(skip_vendor_partner_sync=True).partner_id = order.vendor_ids[:1]
            if "partner_id" in vals:
                self._sync_vendor_ids_with_partner()
        return result

    @api.onchange("vendor_ids")
    def _onchange_vendor_ids(self):
        for order in self:
            if order.vendor_ids and order.partner_id not in order.vendor_ids:
                order.partner_id = order.vendor_ids[:1]

    @api.onchange("partner_id")
    def _onchange_partner_id_sync_vendor_ids(self):
        for order in self:
            if order.partner_id and order.partner_id not in order.vendor_ids:
                order.vendor_ids = [(4, order.partner_id.id)]

    # ------------------------------------------------------------------
    # Vendor <-> partner synchronization helpers
    # ------------------------------------------------------------------
    @api.model
    def _get_first_vendor_id_from_commands(self, commands):
        for command in commands:
            if isinstance(command, (list, tuple)):
                if command[0] == 6 and command[2]:
                    return command[2][0]
                if command[0] == 4:
                    return command[1]
        return False

    def _sync_vendor_ids_with_partner(self):
        for order in self:
            if order.partner_id and order.partner_id not in order.vendor_ids:
                order.with_context(skip_vendor_partner_sync=True).vendor_ids = [(4, order.partner_id.id)]

    # ------------------------------------------------------------------
    # Computed helpers
    # ------------------------------------------------------------------
    def _compute_bid_count(self):
        for order in self:
            order.bid_count = len(order.bid_ids)

    @api.depends("bid_ids.line_ids.is_awarded")
    def _compute_awarded_summary(self):
        for order in self:
            awarded_lines = order.bid_ids.mapped("line_ids").filtered("is_awarded")
            order.awarded_line_count = len(awarded_lines)
            order.winning_vendor_count = len(awarded_lines.mapped("bid_id.vendor_id"))

    @api.depends("generated_po_ids")
    def _compute_generated_po_count(self):
        for order in self:
            order.generated_po_count = len(order.generated_po_ids)

    # ------------------------------------------------------------------
    # Bidding workflow
    # ------------------------------------------------------------------
    def message_post(self, **kwargs):
        """Advance the RFQ straight into the Bidding stage once it has been emailed.

        Core Odoo flips ``draft`` orders to ``sent`` here, under the
        ``mark_rfq_as_sent`` flag set by the email composer. We let that happen
        first, then promote the order to ``bidding`` so bid collection can begin
        immediately after the RFQ is sent.
        """
        res = super().message_post(**kwargs)
        if self.env.context.get("mark_rfq_as_sent"):
            to_open_bidding = self.filtered(lambda o: o.state == "sent")
            if to_open_bidding:
                to_open_bidding.write({"state": "bidding"})
        return res

    def action_rfq_send(self):
        """Open the email composer with every invited vendor pre-filled as a recipient.

        Standard Odoo only addresses the single ``partner_id``. Because this
        module supports multi-vendor RFQs, we inject all selected vendors into
        the composer's ``partner_ids`` through the context so the user sees them
        in the "To" field automatically.
        """
        # Only rich context population when there are extra vendors beyond the
        # primary partner. Falls back to the parent behaviour otherwise.
        vendor_ids = []
        for order in self:
            vendor_ids += order.vendor_ids.ids or order.partner_id.ids
        vendor_ids = list(dict.fromkeys(vendor_ids))  # de-dup, keep order

        action = super().action_rfq_send()
        if isinstance(action, dict) and vendor_ids:
            ctx = action.get("context", {}) or {}
            ctx["default_partner_ids"] = [(6, 0, vendor_ids)]
            action["context"] = ctx
        return action

    # ------------------------------------------------------------------
    # Bid creation entry point
    # ------------------------------------------------------------------
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

    def action_view_generated_pos(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Generated Purchase Orders"),
            "res_model": "purchase.order",
            "domain": [("bidding_source_id", "=", self.id)],
            "view_mode": "list,form",
        }

    # ------------------------------------------------------------------
    # Awarding helpers (whole-bid winner)
    # ------------------------------------------------------------------
    def _apply_winning_bid(self, bid):
        """Mark every line of ``bid`` as awarded and clear awards on other bids.

        This is the simple, single-vendor path. Multi-vendor awarding is handled
        by ticking ``is_awarded`` on individual bid lines directly from the bid
        list, then calling :meth:`action_finalize_bidding`.
        """
        self.ensure_one()
        if bid.order_id != self:
            raise UserError(_("The selected bid does not belong to this RFQ."))
        if bid.vendor_id not in self.vendor_ids:
            self.vendor_ids = [(4, bid.vendor_id.id)]

        self.bid_ids.mapped("line_ids").write({"is_awarded": False})
        bid.line_ids.write({"is_awarded": True})
        self.partner_id = bid.vendor_id
        self.winning_bid_id = bid

    # ------------------------------------------------------------------
    # Finalize bidding -> create one purchase order per winning vendor
    # ------------------------------------------------------------------
    def action_finalize_bidding(self):
        """Turn awarded bid lines into confirmed purchase orders.

        Lines are grouped by their bid's vendor; for each vendor a separate
        purchase order is created, priced from the awarded bid lines, and
        confirmed. This keeps Odoo's one-vendor-per-PO contract intact so
        receipts and vendor bills keep working even when products are sourced
        from different suppliers within the same RFQ.
        """
        self.ensure_one()
        if self.state != "bidding":
            raise UserError(_("Purchase orders can only be created after the RFQ is in the Bidding stage."))

        awards_by_vendor = self._collect_awarded_lines_by_vendor()
        if not awards_by_vendor:
            raise UserError(_(
                "No awarded bid lines found. Mark at least one bid line as "
                "awarded before creating the purchase order(s)."
            ))

        PurchaseOrder = self.env["purchase.order"]
        created_orders = PurchaseOrder
        for vendor, bid_lines in awards_by_vendor.items():
            order_vals = self._prepare_po_vals_from_awards(vendor, bid_lines)
            new_order = PurchaseOrder.create(order_vals)
            created_orders += new_order
            new_order.button_confirm()

        # Mark every awarded bid and its vendor's bid state.
        self._mark_bid_states_after_finalize(awards_by_vendor)
        self.write({"state": "done_bidding"})
        return self.action_view_generated_pos()

    def _collect_awarded_lines_by_vendor(self):
        """Return an ordered mapping {vendor: bid_lines} for awarded lines."""
        self.ensure_one()
        awarded = self.bid_ids.mapped("line_ids").filtered("is_awarded")
        grouped = defaultdict(lambda: self.env["purchase.rfq.bid.line"])
        for line in awarded:
            grouped[line.bid_id.vendor_id] |= line
        return grouped

    def _prepare_po_vals_from_awards(self, vendor, bid_lines):
        """Build the create values for one purchase order from awarded bid lines."""
        self.ensure_one()
        bid = bid_lines[:1].bid_id
        order_lines = [
            (
                0,
                0,
                {
                    "product_id": bl.product_id.id,
                    "name": bl.name or bl.product_id.display_name,
                    "product_qty": bl.quantity,
                    "product_uom_id": bl.product_uom_id.id,
                    "price_unit": bl.price_unit,
                    "date_planned": bl.bid_id.delivery_date or fields.Datetime.now(),
                },
            )
            for bl in bid_lines
        ]
        return {
            "partner_id": vendor.id,
            "vendor_ids": [(6, 0, [vendor.id])],
            "origin": self.origin or self.name,
            "purchase_request_id": self.purchase_request_id.id,
            "company_id": self.company_id.id,
            "currency_id": self.currency_id.id,
            "bidding_source_id": self.id,
            "order_line": order_lines,
        }

    def _mark_bid_states_after_finalize(self, awards_by_vendor):
        """Mark bids with at least one awarded line as won, all others as lost."""
        self.ensure_one()
        winning_bids = self.env["purchase.rfq.bid"]
        for vendor_lines in awards_by_vendor.values():
            winning_bids |= vendor_lines.mapped("bid_id")
        (self.bid_ids - winning_bids).filtered(
            lambda b: b.state not in ("won",)
        ).write({"state": "lost"})
        winning_bids.write({"state": "won"})

    # ------------------------------------------------------------------
    # Backwards compatibility shim
    # ------------------------------------------------------------------
    def action_create_po_from_winner(self):
        """Deprecated entry point kept so older buttons still route correctly.

        It now defers to the unified finalize flow so single-vendor winners and
        multi-vendor awarding share the same code path.
        """
        if self.winning_bid_id and not self.bid_ids.mapped("line_ids").filtered("is_awarded"):
            # Nothing explicitly awarded yet but a winning bid was selected the
            # classic way: treat the whole winning bid as awarded.
            self._apply_winning_bid(self.winning_bid_id)
        return self.action_finalize_bidding()
