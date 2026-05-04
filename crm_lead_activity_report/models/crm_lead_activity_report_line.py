from odoo import fields, models


class CrmLeadActivityReportLine(models.TransientModel):
    _name = 'crm.lead.activity.report.line'
    _description = 'CRM Lead Activity Report Line'
    _order = 'last_interaction_at desc, id desc'

    wizard_id = fields.Many2one(
        comodel_name='crm.lead.activity.report.wizard',
        required=True,
        ondelete='cascade',
    )
    lead_id = fields.Many2one(comodel_name='crm.lead', required=True, readonly=True)

    lead_name = fields.Char(readonly=True)
    company_name = fields.Char(readonly=True)
    email_from = fields.Char(readonly=True)
    phone = fields.Char(readonly=True)

    team_id = fields.Many2one(comodel_name='crm.team', readonly=True)
    user_id = fields.Many2one(comodel_name='res.users', string='Salesperson', readonly=True)
    stage_id = fields.Many2one(comodel_name='crm.stage', readonly=True)

    lead_created_at = fields.Datetime(readonly=True)
    first_interaction_at = fields.Datetime(readonly=True)
    last_interaction_at = fields.Datetime(readonly=True)
    last_note_at = fields.Datetime(readonly=True)

    note_count = fields.Integer(readonly=True)
    internal_note_count = fields.Integer(readonly=True)
    positive_note_count = fields.Integer(readonly=True)
    negative_note_count = fields.Integer(readonly=True)
    neutral_note_count = fields.Integer(readonly=True)

    note_sentiment = fields.Selection(
        selection=[
            ('positive', 'Positive'),
            ('negative', 'Negative'),
            ('neutral', 'Neutral'),
            ('mixed', 'Mixed'),
        ],
        readonly=True,
    )
    contacted_tag = fields.Boolean(readonly=True)
    tag_names = fields.Char(readonly=True)
    lost_reason = fields.Char(readonly=True)

    latest_internal_note = fields.Text(readonly=True)
    issue_summary = fields.Text(readonly=True)
    note_analysis = fields.Text(readonly=True)

    days_to_first_interaction = fields.Float(
        string='Days To First Interaction',
        digits=(16, 2),
        readonly=True,
    )
    days_since_last_note = fields.Float(
        string='Days Since Last Note',
        digits=(16, 2),
        readonly=True,
    )
