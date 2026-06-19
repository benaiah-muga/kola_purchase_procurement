# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged("standard", "at_install", "post_install")
class TestPurchaseProcurement(TransactionCase):
    """End-to-end tests for the procurement bidding workflow."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # --- Vendors ---
        Partner = cls.env["res.partner"]
        cls.vendor1 = Partner.create({
            "name": "Test Vendor Alpha",
            "email": "alpha@test.com",
            "supplier_rank": 1,
        })
        cls.vendor2 = Partner.create({
            "name": "Test Vendor Beta",
            "email": "beta@test.com",
            "supplier_rank": 1,
        })
        cls.vendor3 = Partner.create({
            "name": "Test Vendor Gamma",
            "email": "gamma@test.com",
            "supplier_rank": 1,
        })

        # --- Products ---
        Product = cls.env["product.product"]
        cls.productA = Product.create({
            "name": "Test Product A",
            "purchase_ok": True,
            "uom_id": cls.env.ref("uom.product_uom_unit").id,
        })
        cls.productB = Product.create({
            "name": "Test Product B",
            "purchase_ok": True,
            "uom_id": cls.env.ref("uom.product_uom_unit").id,
        })

        # --- Users ---
        # Make the current user a purchase user so all actions are accessible.
        cls.user = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Procurement Officer",
            "login": "proc_test",
            "group_ids": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("purchase.group_purchase_user").id,
            ])],
            "email": "proc@test.com",
        })

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _create_request(self, lines=None):
        """Create a draft purchase request with the given product lines.

        ``lines`` is a list of tuples (product, quantity, estimated_price).
        """
        vals = {
            "employee_id": self.user.employee_id.id or self.env["hr.employee"].create({
                "user_id": self.user.id,
                "name": "Procurement Test",
            }).id,
            "vendor_ids": [(6, 0, [self.vendor1.id, self.vendor2.id, self.vendor3.id])],
        }
        if lines:
            vals["line_ids"] = [
                (0, 0, {
                    "product_id": p.id,
                    "quantity": q,
                    "estimated_price": ep,
                })
                for p, q, ep in lines
            ]
        return self.env["purchase.request"].with_user(self.user).create(vals)

    def _create_bid(self, rfq, vendor, prices):
        """Create and submit a bid for *vendor* on *rfq*.

        ``prices`` is a dict {product_id: unit_price}.
        """
        bid = self.env["purchase.rfq.bid"].with_user(self.user).create({
            "order_id": rfq.id,
            "vendor_id": vendor.id,
        })
        bid.action_copy_rfq_lines()
        for bl in bid.line_ids:
            if bl.product_id.id in prices:
                bl.price_unit = prices[bl.product_id.id]
        bid.action_submit()
        return bid

    # ------------------------------------------------------------------
    # 1. Request lifecycle
    # ------------------------------------------------------------------
    def test_request_submit_approve(self):
        """A draft request can be submitted and approved."""
        req = self._create_request([(self.productA, 10, 100.0)])
        self.assertEqual(req.state, "draft")

        req.action_submit()
        self.assertEqual(req.state, "submitted")

        req.action_approve()
        self.assertEqual(req.state, "approved")

    # ------------------------------------------------------------------
    # 2. Whole-request rejection (mandatory reason)
    # ------------------------------------------------------------------
    def test_request_reject_without_reason_fails(self):
        """Rejecting without a reason must raise UserError."""
        req = self._create_request([(self.productA, 5, 50.0)])
        req.action_submit()
        req.action_approve()

        with self.assertRaises(Exception):  # UserError
            req.action_reject()

        self.assertEqual(req.state, "approved")

    def test_request_reject_with_reason(self):
        """Rejecting with a reason via the wizard works."""
        req = self._create_request([(self.productA, 5, 50.0)])
        req.action_submit()
        req.action_approve()

        wizard = self.env["purchase.request.reject.wizard"].with_user(self.user).create({
            "request_id": req.id,
            "reason": "Budget exceeded for this quarter.",
        })
        wizard.action_confirm_reject()

        self.assertEqual(req.state, "rejected")
        self.assertEqual(req.rejection_reason, "Budget exceeded for this quarter.")

    def test_request_reset_to_draft_clears_reason(self):
        """Resetting to draft clears the rejection reason."""
        req = self._create_request([(self.productA, 5, 50.0)])
        req.action_submit()
        req.action_approve()

        wizard = self.env["purchase.request.reject.wizard"].with_user(self.user).create({
            "request_id": req.id,
            "reason": "Budget exceeded.",
        })
        wizard.action_confirm_reject()
        self.assertEqual(req.state, "rejected")

        req.action_reset_to_draft()
        self.assertEqual(req.state, "draft")
        self.assertFalse(req.rejection_reason)

    # ------------------------------------------------------------------
    # 3. Line-level rejection
    # ------------------------------------------------------------------
    def test_line_reject_without_reason_fails(self):
        """A line cannot be set to rejected without a reason."""
        req = self._create_request([(self.productA, 5, 50.0)])
        line = req.line_ids[0]

        with self.assertRaises(Exception):  # ValidationError (constrains)
            line.write({"state": "rejected"})

    def test_line_reject_with_reason(self):
        """Rejecting a line via the wizard works."""
        req = self._create_request([(self.productA, 5, 50.0), (self.productB, 3, 30.0)])
        line = req.line_ids[0]

        wiz = self.env["purchase.request.line.reject.wizard"].with_user(self.user).create({
            "line_ids": [(6, 0, line.ids)],
            "reason": "Product no longer needed.",
        })
        wiz.action_confirm_reject()

        self.assertEqual(line.state, "rejected")
        self.assertEqual(line.rejection_reason, "Product no longer needed.")
        self.assertEqual(req.line_ids.filtered(lambda l: l.state == "open").product_id, self.productB)

    def test_rejected_lines_excluded_from_rfq(self):
        """Rejected lines are excluded when creating the RFQ."""
        req = self._create_request([(self.productA, 5, 50.0), (self.productB, 3, 30.0)])
        lineB = req.line_ids.filtered(lambda l: l.product_id == self.productB)
        wiz = self.env["purchase.request.line.reject.wizard"].with_user(self.user).create({
            "line_ids": [(6, 0, lineB.ids)],
            "reason": "Not needed.",
        })
        wiz.action_confirm_reject()

        req.action_submit()
        req.action_approve()
        req.action_create_rfq()

        self.assertEqual(req.rfq_id.state, "draft")
        # Only productA should appear in the RFQ.
        rfq_products = req.rfq_id.order_line.mapped("product_id")
        self.assertEqual(rfq_products, self.productA)

    # ------------------------------------------------------------------
    # 4. RFQ creation from approved request
    # ------------------------------------------------------------------
    def test_create_rfq_from_request(self):
        """Approved request creates a draft RFQ with correct vendors and lines."""
        req = self._create_request([(self.productA, 10, 100.0)])
        req.action_submit()
        req.action_approve()
        req.action_create_rfq()

        self.assertTrue(req.rfq_id)
        self.assertEqual(req.state, "rfq_created")
        self.assertEqual(req.rfq_id.state, "draft")
        self.assertEqual(len(req.rfq_id.order_line), 1)
        self.assertIn(self.vendor1, req.rfq_id.vendor_ids)
        self.assertIn(self.vendor2, req.rfq_id.vendor_ids)

    # ------------------------------------------------------------------
    # 5. Bid sequence (BD001, BD002, ...)
    # ------------------------------------------------------------------
    def test_bid_naming_sequence(self):
        """Bids get chronological auto-incrementing names BD001, BD002, ..."""
        rfq = self._create_request([(self.productA, 10, 100.0)])
        rfq.action_submit()
        rfq.action_approve()
        rfq.action_create_rfq()

        bid1 = self._create_bid(rfq.rfq_id, self.vendor1, {self.productA.id: 90.0})
        bid2 = self._create_bid(rfq.rfq_id, self.vendor2, {self.productA.id: 95.0})
        bid3 = self._create_bid(rfq.rfq_id, self.vendor3, {self.productA.id: 85.0})

        self.assertTrue(bid1.name.startswith("BD"))
        self.assertTrue(bid2.name.startswith("BD"))
        self.assertTrue(bid3.name.startswith("BD"))
        self.assertGreater(bid2.name, bid1.name)
        self.assertGreater(bid3.name, bid2.name)

    # ------------------------------------------------------------------
    # 6. Duplicate vendor bid is blocked
    # ------------------------------------------------------------------
    def test_unique_vendor_bid_per_rfq(self):
        """A vendor cannot submit two bids for the same RFQ."""
        rfq = self._create_request([(self.productA, 10, 100.0)])
        rfq.action_submit()
        rfq.action_approve()
        rfq.action_create_rfq()

        self._create_bid(rfq.rfq_id, self.vendor1, {self.productA.id: 90.0})
        with self.assertRaises(Exception):  # ValidationError
            self._create_bid(rfq.rfq_id, self.vendor1, {self.productA.id: 85.0})

    # ------------------------------------------------------------------
    # 7. Email context populated with all vendor emails
    # ------------------------------------------------------------------
    def test_rfq_send_context_includes_all_vendors(self):
        """action_rfq_send returns context with default_partner_ids for all vendors."""
        rfq = self._create_request([(self.productA, 10, 100.0)])
        rfq.action_submit()
        rfq.action_approve()
        rfq.action_create_rfq()

        action = rfq.rfq_id.action_rfq_send()
        ctx = action.get("context", {})
        default_partners = ctx.get("default_partner_ids", [])
        partner_ids = [cmd[2] for cmd in default_partners if isinstance(cmd, list) and cmd[0] == 6]
        self.assertTrue(partner_ids)
        # partner_ids should include all vendors (minus partner_id which core handles)
        for vendor in rfq.rfq_id.vendor_ids:
            if vendor.id != rfq.rfq_id.partner_id.id:
                self.assertIn(vendor.id, partner_ids[0])

    # ------------------------------------------------------------------
    # 8. Bidding state auto-transition on send
    # ------------------------------------------------------------------
    def test_rfq_auto_enters_bidding_on_send(self):
        """Sending an RFQ automatically enters the Bidding state."""
        rfq = self._create_request([(self.productA, 10, 100.0)])
        rfq.action_submit()
        rfq.action_approve()
        rfq.action_create_rfq()

        self.assertEqual(rfq.rfq_id.state, "draft")
        # Simulate what the mail composer does: post with mark_rfq_as_sent.
        rfq.rfq_id.with_context(mark_rfq_as_sent=True).message_post(body="RFQ sent")
        self.assertEqual(rfq.rfq_id.state, "bidding")

    # ------------------------------------------------------------------
    # 9. Single-vendor winner -> 1 PO (backward-compatible demo path)
    # ------------------------------------------------------------------
    def test_single_vendor_winner_creates_one_po(self):
        """Selecting one bid as winner and finalizing creates exactly one PO."""
        rfq = self._create_request([(self.productA, 10, 100.0)])
        rfq.action_submit()
        rfq.action_approve()
        rfq.action_create_rfq()
        rfq.rfq_id.with_context(mark_rfq_as_sent=True).message_post(body="Sent")

        bid = self._create_bid(rfq.rfq_id, self.vendor1, {self.productA.id: 90.0})
        bid.action_select_winner()  # award whole bid

        rfq.rfq_id.action_finalize_bidding()

        self.assertEqual(rfq.rfq_id.state, "done_bidding")
        self.assertEqual(rfq.rfq_id.generated_po_count, 1)

        po = rfq.rfq_id.generated_po_ids
        self.assertEqual(po.partner_id, self.vendor1)
        self.assertEqual(po.state, "purchase")
        self.assertEqual(len(po.order_line), 1)
        self.assertEqual(po.order_line[0].price_unit, 90.0)

    # ------------------------------------------------------------------
    # 10. Multi-vendor line awarding -> multiple POs
    # ------------------------------------------------------------------
    def test_multi_vendor_awarding_creates_separate_pos(self):
        """Awarding different lines to different vendors creates separate POs."""
        rfq = self._create_request([(self.productA, 10, 100.0), (self.productB, 5, 50.0)])
        rfq.action_submit()
        rfq.action_approve()
        rfq.action_create_rfq()
        rfq.rfq_id.with_context(mark_rfq_as_sent=True).message_post(body="Sent")

        # Vendor1 offers best price for productA, Vendor2 for productB.
        bid1 = self._create_bid(rfq.rfq_id, self.vendor1, {
            self.productA.id: 90.0,
            self.productB.id: 60.0,
        })
        bid2 = self._create_bid(rfq.rfq_id, self.vendor2, {
            self.productA.id: 95.0,
            self.productB.id: 40.0,
        })

        # Award productA to vendor1, productB to vendor2.
        line_a = bid1.line_ids.filtered(lambda l: l.product_id == self.productA)
        line_b = bid2.line_ids.filtered(lambda l: l.product_id == self.productB)
        line_a.is_awarded = True
        line_b.is_awarded = True

        rfq.rfq_id.action_finalize_bidding()

        self.assertEqual(rfq.rfq_id.state, "done_bidding")
        self.assertEqual(rfq.rfq_id.generated_po_count, 2)

        # Vendor1's PO should have productA.
        po1 = rfq.rfq_id.generated_po_ids.filtered(lambda o: o.partner_id == self.vendor1)
        self.assertTrue(po1)
        self.assertEqual(po1.order_line.mapped("product_id"), self.productA)
        self.assertEqual(po1.order_line[0].price_unit, 90.0)
        self.assertEqual(po1.state, "purchase")

        # Vendor2's PO should have productB.
        po2 = rfq.rfq_id.generated_po_ids.filtered(lambda o: o.partner_id == self.vendor2)
        self.assertTrue(po2)
        self.assertEqual(po2.order_line.mapped("product_id"), self.productB)
        self.assertEqual(po2.order_line[0].price_unit, 40.0)
        self.assertEqual(po2.state, "purchase")

    # ------------------------------------------------------------------
    # 11. Finalize without awarded lines is blocked
    # ------------------------------------------------------------------
    def test_finalize_without_awards_fails(self):
        """Finalizing with no awarded lines raises UserError."""
        rfq = self._create_request([(self.productA, 10, 100.0)])
        rfq.action_submit()
        rfq.action_approve()
        rfq.action_create_rfq()
        rfq.rfq_id.with_context(mark_rfq_as_sent=True).message_post(body="Sent")

        with self.assertRaises(Exception):  # UserError
            rfq.rfq_id.action_finalize_bidding()

    # ------------------------------------------------------------------
    # 12. Product can only be awarded to one vendor
    # ------------------------------------------------------------------
    def test_single_award_per_product(self):
        """A product awarded to two vendors raises ValidationError."""
        rfq = self._create_request([(self.productA, 10, 100.0)])
        rfq.action_submit()
        rfq.action_approve()
        rfq.action_create_rfq()
        rfq.rfq_id.with_context(mark_rfq_as_sent=True).message_post(body="Sent")

        bid1 = self._create_bid(rfq.rfq_id, self.vendor1, {self.productA.id: 90.0})
        bid2 = self._create_bid(rfq.rfq_id, self.vendor2, {self.productA.id: 95.0})

        bid1.line_ids[0].is_awarded = True
        with self.assertRaises(Exception):  # ValidationError
            bid2.line_ids[0].is_awarded = True

    # ------------------------------------------------------------------
    # 13. Backwards compatibility: action_create_po_from_winner still works
    # ------------------------------------------------------------------
    def test_create_po_from_winner_shim(self):
        """The old action_create_po_from_winner shim still works."""
        rfq = self._create_request([(self.productA, 10, 100.0)])
        rfq.action_submit()
        rfq.action_approve()
        rfq.action_create_rfq()
        rfq.rfq_id.with_context(mark_rfq_as_sent=True).message_post(body="Sent")

        bid = self._create_bid(rfq.rfq_id, self.vendor1, {self.productA.id: 90.0})
        bid.action_select_winner()

        rfq.rfq_id.action_create_po_from_winner()
        self.assertEqual(rfq.rfq_id.state, "done_bidding")
        self.assertEqual(rfq.rfq_id.generated_po_count, 1)
