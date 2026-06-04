{
    "name": "Kola Purchase Procurement",
    "version": "19.0.1.0.0",
    "category": "Supply Chain/Purchase",
    "summary": "Multi-vendor RFQs, supplier bids, and employee purchase requests",
    "author": "Benaiah Muganzi",
    "license": "LGPL-3",
    "depends": ["purchase", "hr"],
    "data": [
        "security/ir.model.access.csv",
        "data/purchase_request_sequence.xml",
        "views/purchase_order_views.xml",
        "views/purchase_request_views.xml",
    ],
    "installable": True,
    "application": False,
}
