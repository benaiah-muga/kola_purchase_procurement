{
    "name": "Kola Purchase Procurement",
    "version": "19.0.2.0.0",
    "category": "Supply Chain/Purchase",
    "summary": "Multi-vendor RFQs, supplier bids, bidding workflow, and employee purchase requests",
    "author": "Benaiah Muganzi",
    "license": "LGPL-3",
    "depends": ["purchase", "hr"],
    "data": [
        "security/ir.model.access.csv",
        "data/purchase_request_sequence.xml",
        "data/bid_sequence.xml",
        "wizard/purchase_request_reject_wizard_views.xml",
        "views/purchase_order_views.xml",
        "views/purchase_request_views.xml",
    ],
    "installable": True,
    "application": False,
}
