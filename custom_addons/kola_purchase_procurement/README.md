# Kola Purchase Procurement

This module implements the assignment requirements for Odoo Community Edition 19.0.

## Where The Module Lives

Place the module at:

```text
custom_addons/kola_purchase_procurement/
```

The local Odoo configuration already includes:

```text
/home/benaiah/odoo19/custom_addons
```

in `addons_path`, so Odoo can discover the module after updating the app list.

## Feature 1: Assign One RFQ To Several Vendors

Business requirement: Procurement should prepare one RFQ and invite several suppliers to quote for the same requested items.

Odoo models involved:

- `purchase.order`: Odoo's standard RFQ and Purchase Order model.
- `res.partner`: Odoo's standard contact/vendor model.

Model relationships:

- `purchase.order.vendor_ids` is a `Many2many` relationship to `res.partner`.
- The existing `purchase.order.partner_id` remains in place because Odoo requires a primary vendor for standard RFQ and PO behavior.

Design choice:

The RFQ already exists as `purchase.order`, so the clean Odoo approach is model inheritance with `_inherit = "purchase.order"`. A `Many2many` field is appropriate because one RFQ can have many vendors and one vendor can be invited to many RFQs.

Implementation files:

- `models/purchase_order.py`
- `views/purchase_order_views.xml`

## Feature 2: Receive Bids From Suppliers Against The RFQ

Business requirement: Each invited vendor can submit a bid for the RFQ, including prices, quantities, and promised delivery.

Odoo models involved:

- `purchase.rfq.bid`: custom model for supplier bids.
- `purchase.rfq.bid.line`: custom model for bid line prices.
- `purchase.order`: parent RFQ.
- `product.product`: products being quoted.

Model relationships:

- `purchase.order.bid_ids` is a `One2many` relationship to `purchase.rfq.bid`.
- `purchase.rfq.bid.order_id` is a `Many2one` relationship back to the RFQ.
- `purchase.rfq.bid.line.bid_id` is a `Many2one` relationship to the bid.
- `purchase.rfq.bid.line.product_id` links each quoted line to a product.

Design choice:

Bids are separate business records, not just email messages or notes. A custom bid model is therefore appropriate and easy to demo. It keeps all supplier responses connected to the RFQ while preserving Odoo's standard Purchase app behavior.

Implementation files:

- `models/purchase_rfq_bid.py`
- `views/purchase_order_views.xml`
- `security/ir.model.access.csv`

## Feature 3: Select Winning Bidder And Assign A Purchase Order

Business requirement: Procurement should compare supplier bids, select a winner, and convert the RFQ into a Purchase Order for that vendor.

Odoo models involved:

- `purchase.rfq.bid`: stores bid state: Draft, Submitted, Won, Lost.
- `purchase.order`: stores the winning bid and becomes the Purchase Order.

Model relationships:

- `purchase.order.winning_bid_id` is a `Many2one` relationship to `purchase.rfq.bid`.
- The winning bid updates the RFQ's primary `partner_id`.

Design choice:

Odoo already converts RFQs to Purchase Orders through `button_confirm`. The module reuses that standard method through `action_create_po_from_winner` instead of creating a parallel PO process. This is easier to explain and safer because standard Odoo validations still run.

Implementation files:

- `models/purchase_order.py`
- `models/purchase_rfq_bid.py`
- `views/purchase_order_views.xml`

## Feature 4: Employee Purchase Requests

Business requirement: Employees need a simple way to request items from Procurement. Procurement uses the approved request to prepare the RFQ.

Odoo models involved:

- `purchase.request`: custom request header.
- `purchase.request.line`: requested products and quantities.
- `hr.employee`: employee information.
- `res.users`: requester account.
- `purchase.order`: RFQ created from the approved request.

Model relationships:

- `purchase.request.line_ids` is a `One2many` relationship to `purchase.request.line`.
- `purchase.request.line.request_id` is the inverse `Many2one`.
- `purchase.request.rfq_id` links the request to the generated RFQ.
- `purchase.order.purchase_request_id` links the RFQ back to the request.

Design choice:

The request is a separate business document because it happens before an RFQ exists. A custom model keeps employee requests simple and avoids overloading `purchase.order` with pre-procurement states that do not belong to the standard Purchase app.

Implementation files:

- `models/purchase_request.py`
- `views/purchase_request_views.xml`
- `data/purchase_request_sequence.xml`
- `security/ir.model.access.csv`

## Install And Demo

1. Start Odoo.
2. Activate Developer Mode.
3. Go to Apps.
4. Click Update Apps List.
5. Search for `Kola Purchase Procurement`.
6. Install it.
7. Go to Purchase > Orders > Purchase Requests.
8. Create and approve a purchase request.
9. Add suggested vendors and create the RFQ.
10. Open the RFQ, confirm multiple assigned vendors, record bids, select a winner, and create the Purchase Order.