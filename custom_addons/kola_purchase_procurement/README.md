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

The RFQ already exists as `purchase.order`, so the clean Odoo approach I found is model inheritance with `_inherit = "purchase.order"`. A `Many2many` field is appropriate because one RFQ can have many vendors and one vendor can be invited to many RFQs.

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

Bids are separate business records, not just email messages or notes. A custom bid model is therefore appropriate. It keeps all supplier responses connected to the RFQ while preserving Odoo's standard Purchase app behavior.

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

Odoo already converts RFQs to Purchase Orders through `button_confirm`. The module reuses that standard method through `action_create_po_from_winner` instead of creating a parallel PO process. This is easier and safer because standard Odoo validations still run.

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

---

# Demo Walkthrough

## Setup: Sample Data

### Vendors (Suppliers)

| Vendor Name | Email | Location |
|-------------|-------|----------|
| Tech Supplies Ltd | sales@techsupplies.ug | Kampala |
| Global Electronics Inc | orders@globalelec.ug | Jinja |
| Office Essentials Co | sales@officeessentials.ug | Entebbe |
| Premium Hardware Suppliers | info@premiumhw.ug | Nairobi |

### Products (Purchase Items)

| Product | List Price (UGX) | Cost Price (UGX) |
|---------|------------------|------------------|
| Laptop Computer - 15" Business Pro | 4,500,000 | 3,600,000 |
| Ergonomic Office Chair | 850,000 | 600,000 |
| Wireless Mouse - Ergonomic | 85,000 | 55,000 |
| USB-C Docking Station | 680,000 | 450,000 |
| External Monitor - 27" 4K | 2,200,000 | 1,600,000 |
| Mechanical Keyboard - RGB | 380,000 | 250,000 |

---

## Feature 4: Employee Purchase Request (First Step)

**Scenario:** John Ssentamu from IT Department needs office equipment.

### Step 4.1: Create Purchase Request

1. Go to **Purchase > Orders > Purchase Requests**
2. Click **Create**
3. Fill in:
   - **Employee:** John Ssentamu
   - **Needed Date:** 2026-06-20
   - **Suggested Vendors:** Tech Supplies Ltd, Global Electronics Inc, Office Essentials Co
4. Add **Request Lines** (Products tab):

| Product | Description | Qty | Est. Unit Price (UGX) |
|---------|-------------|-----|----------------------|
| Laptop Computer - 15" Business Pro | Laptop | 3 | 4,500,000 |
| Office Chair | Ergonomic Chair | 3 | 850,000 |
| Wireless Mouse | Ergonomic Mouse | 3 | 85,000 |

5. Click **Submit** → Status changes to "Submitted"

<img width="1250" height="1010" alt="purchase request" src="https://github.com/user-attachments/assets/91f0c7d3-0129-441f-97e4-1696adbec382" />


### Step 4.2: Approve Request

1. Open the submitted request PR/00002
2. Click **Approve** → Status changes to "Approved"
3. **Create RFQ** button becomes visible

<img width="1250" height="1010" alt="After PR Approval" src="https://github.com/user-attachments/assets/7321e185-b1e6-4310-8ffd-b986fc9be506" />


### Step 4.3: Generate RFQ from Request

1. With approved request open, click **Create RFQ**
2. System automatically:
   - Creates RFQ with vendor_ids pre-populated from suggested vendors
   - Links RFQ back to the purchase request (purchase_request_id field)
   - Creates RFQ lines from request product lines
3. Click **Edit** to verify vendor assignments

---

## Feature 1: Assign One RFQ To Several Vendors

**Scenario:** Procurement prepared RFQ for IT equipment, inviting 3 vendors to quote.

### Step 1.1: View RFQ with Multiple Vendors

1. Go to **Purchase > Orders > Purchase Orders**
2. Open the **RFQ**
3. In the form, verify:
   - **Assigned Vendors** field shows: Tech Supplies Ltd, Global Electronics Inc, Office Essentials Co
   - **Primary Vendor** (partner_id): Tech Supplies Ltd (first suggested vendor)
   - **Origin** field shows: PR/00002 (linked request)

<img width="1412" height="1010" alt="createdrfq_from Request_assignedtomultiplevendors" src="https://github.com/user-attachments/assets/f1512fa3-9e43-435f-bc75-d1bec829b1cd" />


### Step 1.2: RFQ Sent to Multiple Vendors via Email

Odoo automatically sends the RFQ to all assigned vendors via email.

<img width="1412" height="1010" alt="createdrfq_from Request_assignedtomultiplevendors" src="https://github.com/user-attachments/assets/3bbc13cd-d22c-4c1f-b57c-f8b043c948db" />


---

## Feature 2: Receive Bids From Suppliers

**Scenario:** Each vendor submits a bid with their quoted prices.

### Step 2.1: Create Bid for Tech Supplies Ltd

1. Open the **RFQ**
2. Go to **Supplier Bids** tab
3. Click **Create Supplier Bid**
4. Form opens:
   - **RFQ:(pre-filled)
   - **Vendor:** Tech Supplies Ltd
   - **Bid Date:** 2026-06-05
   - **Valid Until:** 2026-06-12
   - **Promised Delivery:** 2026-06-18
5. Click **Copy RFQ Lines** → System populates bid lines
6. Edit prices (Tech Supplies offers competitive rates):

| Product | Qty | Unit Price (UGX) | Subtotal |
|---------|-----|------------------|----------|
| Laptop | 3 | 4,200,000 | 12,600,000 |
| Office Chair | 3 | 580,000 | 1,740,000 |
| Wireless Mouse | 3 | 52,000 | 156,000 |
| **Total** | | | **14,496,000** |

7. Click **Submit Bid** → Status: "Submitted"

<img width="1075" height="1010" alt="bidcreation" src="https://github.com/user-attachments/assets/49f509ff-9bb6-43a7-925e-5d8250eb41b3" />


### Step 2.2: Create Bid for Global Electronics Inc

Repeat steps above with vendor: Global Electronics Inc

| Product | Qty | Unit Price (UGX) | Subtotal |
|---------|-----|------------------|----------|
| Laptop | 3 | 4,400,000 | 13,200,000 |
| Office Chair | 3 | 720,000 | 2,160,000 |
| Wireless Mouse | 3 | 65,000 | 195,000 |
| **Total** | | | **15,555,000** |

Keep in **Draft** for now.

### Step 2.3: Create Bid for Office Essentials Co

Vendor: Office Essentials Co

| Product | Qty | Unit Price (UGX) | Subtotal |
|---------|-----|------------------|----------|
| Laptop | 3 | 4,500,000 | 13,500,000 |
| Office Chair | 3 | 800,000 | 2,400,000 |
| Wireless Mouse | 3 | 80,000 | 240,000 |
| **Total** | | | **16,140,000** |

Click **Submit Bid** → Status: "Submitted"

### Step 2.4: View All Bids

From the **RFQ**, go to **Supplier Bids** tab. View all 3 bids with states:

- Tech Supplies Ltd: **Submitted** - UGX 14,496,000
- Global Electronics Inc: **Draft** - UGX 15,555,000
- Office Essentials Co: **Submitted** - UGX 16,140,000

<img width="1075" height="1010" alt="bidlistwithability toselect a winner" src="https://github.com/user-attachments/assets/e408863a-8c21-4454-8422-e2a91ef6ccac" />


---

## Feature 3: Select Winning Bidder

**Scenario:** Procurement reviews bids and selects Tech Supplies Ltd (lowest price).

### Step 3.1: Compare Bids

Open the **RFQ** → **Supplier Bids** tab. Review bid totals:

- Tech Supplies: UGX 14,496,000 (lowest)
- Global Electronics: UGX 15,555,000
- Office Essentials: UGX 16,140,000 (highest)

### Step 3.2: Select Winner

1. Click **Select Winner** on Tech Supplies Ltd bid row
2. System:
   - Updates RFQ **partner_id** to Tech Supplies Ltd
   - Sets **winning_bid_id** to this bid
   - Updates RFQ line prices from winning bid
   - Marks other bids as "Lost"
3. Tech Supplies bid status changes to: **Won**
4. Other bids status change to: **Lost**

<img width="1306" height="1010" alt="After selecting the winning bid" src="https://github.com/user-attachments/assets/7f88ecca-18e3-4e32-a54b-e71a06bb46fa" />


### Step 3.3: Create Purchase Order

1. In RFQ header, click **Create PO from Winner**
2. System calls `button_confirm()` to confirm the PO
3. RFQ becomes a confirmed **Purchase Order**

View confirmed PO with:
- Vendor: Tech Supplies Ltd
- Lines with updated prices from winning bid
- **Origin:** RFQ/00002
- **Purchase Request:** PR/00002

### Step 3.4: Verify Complete Workflow

Open the newly created Purchase Order. Verify:
- Vendor is Tech Supplies Ltd
- Line prices reflect winning bid (UGX 4,200,000 for laptops, etc.)
- Total matches selected bid: **UGX 14,496,000**
- Origin links back to RFQ and Purchase Request

<img width="859" height="495" alt="purchase_order" src="https://github.com/user-attachments/assets/1fcdf692-8bb3-4a9a-bd02-eeabb5f1bb7b" />


---

## Complete Workflow Summary

```
Employee creates Purchase Request (PR/00001)
          ↓
Procurement approves request
          ↓
RFQ created with 3 vendors assigned (RFQ/00001)
          ↓
Vendors submit bids:
  - Tech Supplies: UGX 14,496,000 ← WINNER
  - Global Electronics: UGX 15,555,000
  - Office Essentials: UGX 16,140,000
          ↓
Procurement selects Tech Supplies as winner
          ↓
Purchase Order created: UGX 14,496,000
```

---

## Install And Demo

1. Start Odoo.
2. Activate Developer Mode.
3. Go to Apps.
4. Click Update Apps List.
5. Search for `Kola Purchase Procurement`.
6. Install it.
7. Go to **Purchase > Orders > Purchase Requests**.
8. Create and approve a purchase request.
9. Add suggested vendors and create the RFQ.
10. Open the RFQ, confirm multiple assigned vendors, record bids, select a winner, and create the Purchase Order.
