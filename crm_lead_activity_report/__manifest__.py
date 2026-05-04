{
    'name': 'CRM Lead Activity Report',
    'version': '17.0.1.0.0',
    'category': 'Sales/CRM',
    'summary': 'Detailed lead report with connection timestamps and note analysis',
    'description': """
CRM Lead Activity Report
========================
Adds a detailed lead activity report for Odoo 17 Community with:
- First and last interaction timestamps
- Last note date and note volume
- Note sentiment hints (positive/negative/neutral)
- Keyword-based note analysis summary
- Team and salesperson filtering
""",
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'depends': [
        'crm',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/crm_lead_activity_report_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
