{
    'name': 'National ID Application',
    'version': '1.0',
    'category': 'Administration',
    'summary': 'Process online National ID applications',
    'description': """
        Custom module for processing online National ID applications.
        Includes a public-facing web form with file uploads,
        backend management with two-stage approval workflow,
        and portal tracking functionality.
    """,
    'author': 'Benaiah',
    'depends': ['base', 'website', 'portal', 'mail'],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/id_application_views.xml',
        'views/website_form_templates.xml',
        'views/portal_templates.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
