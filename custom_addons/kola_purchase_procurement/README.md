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

<!-- SCREENSHOT PLACEHOLDER: -->
<!-- Screenshot 1: RFQ form showing the "Assigned Vendors" many2many_tags field with multiple vendors selected -->
<!-- Path: docs/screenshots/feature1_rfq_multiple_vendors.png -->
<!-- Description: Capture the purchase order form in edit mode showing the "Assigned Vendors" field with multiple vendor tags displayed. -->

Odoo models involved:

- `purchase.order`: Odoo's standard RFQ and Purchase Order model.
- `res.partner`: Odoo's standard contact/vendor model.

Model relationships:

- `purchase.order.vendor_ids` is a `Many2many` relationship to `res.partner`.
- The existing `purchase.order.partner_id` remains in place because Odoo requires a primary vendor for standard RFQ and PO behavior.

Design choice:

The RFQ already exists as `purchase.order`, so the clean Odoo approach is model inheritance with `_inherit = "purchase.order"`. A `Many2many` field is appropriate because one RFQ can have many vendors and one vendor can be invited to many RFQs.

<!-- SCREENSHOT PLACEHOLDER: -->
<!-- Screenshot 2: Search filter showing vendor_ids field available as a filter option -->
<!-- Path: docs/screenshots/feature1_vendor_filter.png -->
<!-- Description: Capture the purchase order search view showing the "Assigned Vendors" filter field. -->

Implementation files:

- `models/purchase_order.py`
- `views/purchase_order_views.xml`

## Feature 2: Receive Bids From Suppliers Against The RFQ

Business requirement: Each invited vendor can submit a bid for the RFQ, including prices, quantities, and promised delivery.

<!-- SCREENSHOT PLACEHOLDER: -->
<!-- Screenshot 3: Supplier Bid form showing bid lines with product, quantity, unit price, and subtotal -->
<!-- Path: docs/screenshots/feature2_bid_form.png -->
<!-- Description: Capture the Supplier Bid form view displaying the bid header (vendor, dates, currency) and the Bid Lines tab with products, quantities, prices, and calculated subtotals. -->

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

<!-- SCREENSHOT PLACEHOLDER: -->
<!-- Screenshot 4: Supplier Bids list view showing multiple bids with different states (Draft, Submitted, Won, Lost) -->
<!-- Path: docs/screenshots/feature2_bid_list.png -->
<!-- Description: Capture the Supplier Bids list view showing several bids with state badges indicating Draft, Submitted, Won, and Lost statuses. -->

Implementation files:

- `models/purchase_rfq_bid.py`
- `views/purchase_order_views.xml`
- `security/ir.model.access.csv`

## Feature 3: Select Winning Bidder And Assign A Purchase Order

Business requirement: Procurement should compare supplier bids, select a winner, and convert the RFQ into a Purchase Order for that vendor.

<!-- SCREENSHOT PLACEHOLDER: -->
<!-- Screenshot 5: RFQ form with "Supplier Bids" tab expanded showing bids with "Select Winner" button visible -->
<!-- Path: docs/screenshots/feature3_rfq_with_bids.png -->
<!-- Description: Capture the purchase order form showing the "Supplier Bids" page with multiple bids listed and the "Select Winner" button visible for draft/submitted bids. -->

Odoo models involved:

- `purchase.rfq.bid`: stores bid state: Draft, Submitted, Won, Lost.
- `purchase.order`: stores the winning bid and becomes the Purchase Order.

Model relationships:

- `purchase.order.winning_bid_id` is a `Many2one` relationship to `purchase.rfq.bid`.
- The winning bid updates the RFQ's primary `partner_id`.

Design choice:

Odoo already converts RFQs to Purchase Orders through `button_confirm`. The module reuses that standard method through `action_create_po_from_winner` instead of creating a parallel PO process. This is easier to explain and safer because standard Odoo validations still run.

<!-- SCREENSHOT PLACEHOLDER: -->
<!-- Screenshot 6: RFQ after winning bid selected showing "Create PO from Winner" button and updated pricing -->
<!-- Path: docs/screenshots/feature3_winning_bid_selected.png -->
<!-- Description: Capture the purchase order form after selecting a winning bid, showing the updated prices in order lines and the "Create PO from Winner" action button visible in the header. -->

<!-- SCREENSHOT PLACEHOLDER: -->
<!-- Screenshot 7: Confirmed Purchase Order with origin linked to winning bid -->
<!-- Path: docs/screenshots/feature3_purchase_order_created.png -->
<!-- Description: Capture the resulting Purchase Order after creating from winner, showing confirmed state with vendor and line items from the winning bid. -->

Implementation files:

- `models/purchase_order.py`
- `models/purchase_rfq_bid.py`
- `views/purchase_order_views.xml`

## Feature 4: Employee Purchase Requests

Business requirement: Employees need a simple way to request items from Procurement. Procurement uses the approved request to prepare the RFQ.

<!-- SCREENSHOT PLACEHOLDER: -->
<!-- Screenshot 8: Purchase Request list view showing requests in various states -->
<!-- Path: docs/screenshots/feature4_purchase_request_list.png -->
<!-- Description: Capture the Purchase Requests list view showing requests with different states (Draft, Submitted, Approved, Rejected, RFQ Created) and department grouping. -->

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

<!-- SCREENSHOT PLACEHOLDER: -->
<!-- Screenshot 9: Purchase Request form showing line items with product, description, quantity, and estimated price -->
<!-- Path: docs/screenshots/feature4_purchase_request_form.png -->
<!-- Description: Capture the Purchase Request form showing the Products tab with request lines containing products, descriptions, quantities, unit of measure, and estimated prices. -->

<!-- SCREENSHOT PLACEHOLDER: -->
<!-- Screenshot 10: Approved Purchase Request with "Create RFQ" button visible -->
<!-- Path: docs/screenshots/feature4_approved_request_create_rfq.png -->
<!-- Description: Capture an approved Purchase Request form showing the "Create RFQ" button in the header and suggested vendors selected in the vendor_ids field. -->

<!-- SCREENSHOT PLACEHOLDER: -->
<!-- Screenshot 11: RFQ created from Purchase Request showing purchase_request_id link -->
<!-- Path: docs/screenshots/feature4_rfq_from_request.png -->
<!-- Description: Capture the resulting RFQ showing the "Purchase Request" field populated with the originating request name and vendor_ids pre-populated from the request. -->

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

## Screenshots Reference

| Screenshot | Description | File Path |
|------------|-------------|-----------|
| 1 | RFQ form with Assigned Vendors many2many field | `docs/screenshots/feature1_rfq_multiple_vendors.png` |
| 2 | Purchase order search with vendor filter | `docs/screenshots/feature1_vendor_filter.png` |
| 3 | Supplier Bid form with bid lines | `docs/screenshots/feature2_bid_form.png` |
| 4 | Supplier Bids list with state badges | `docs/screenshots/feature2_bid_list.png` |
| 5 | RFQ with Supplier Bids tab and Select Winner button | `docs/screenshots/feature3_rfq_with_bids.png` |
| 6 | RFQ after winning bid selected | `docs/screenshots/feature3_winning_bid_selected.png` |
| 7 | Confirmed Purchase Order from winning bid | `docs/screenshots/feature3_purchase_order_created.png` |
| 8 | Purchase Requests list view | `docs/screenshots/feature4_purchase_request_list.png` |
| 9 | Purchase Request form with product lines | `docs/screenshots/feature4_purchase_request_form.png` |
| 10 | Approved request with Create RFQ button | `docs/screenshots/feature4_approved_request_create_rfq.png` |
| 11 | RFQ linked to Purchase Request | `docs/screenshots/feature4_rfq_from_request.png` |

To add screenshots: save them to the paths indicated above and they will display in GitHub/GitLab rendered markdown.
