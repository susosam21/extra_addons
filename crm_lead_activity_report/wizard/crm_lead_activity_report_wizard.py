from collections import Counter, defaultdict
from datetime import datetime, time
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import html2plaintext


class CrmLeadActivityReportWizard(models.TransientModel):
    _name = 'crm.lead.activity.report.wizard'
    _description = 'CRM Lead Activity Report Wizard'

    date_from = fields.Date(required=True, default=lambda self: fields.Date.context_today(self).replace(day=1))
    date_to = fields.Date(required=True, default=lambda self: fields.Date.context_today(self))
    team_id = fields.Many2one(comodel_name='crm.team', string='Sales Team')
    user_id = fields.Many2one(comodel_name='res.users', string='Salesperson')
    include_archived = fields.Boolean(default=False)
    line_ids = fields.One2many(
        comodel_name='crm.lead.activity.report.line',
        inverse_name='wizard_id',
        readonly=True,
    )

    def _datetime_bounds(self):
        self.ensure_one()
        start_dt = datetime.combine(self.date_from, time.min)
        end_dt = datetime.combine(self.date_to, time.max)
        return start_dt, end_dt

    @api.model
    def _note_keywords(self):
        return {
            'positive': [
                'interested', 'qualified', 'approved', 'agreed', 'confirmed',
                'accepted', 'scheduled', 'meeting', 'demo', 'proposal sent',
                'follow up positive', 'budget approved',
            ],
            'negative': [
                'not interested', 'unreachable', 'no answer', 'no response',
                'rejected', 'lost', 'wrong number', 'invalid', 'spam',
                'budget issue', 'price too high', 'closed business',
            ],
            'neutral': [
                'follow up', 'callback', 'called', 'emailed', 'contacted',
                'left voicemail', 'waiting', 'pending',
            ],
        }

    def _sentiment_from_counts(self, positive_count, negative_count, neutral_count):
        if positive_count > 0 and negative_count > 0:
            return 'mixed'
        if positive_count > 0:
            return 'positive'
        if negative_count > 0:
            return 'negative'
        return 'neutral'

    def _analyze_messages(self, messages):
        keywords = self._note_keywords()
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        keyword_counter = Counter()

        for message in messages:
            text = html2plaintext(message.body or '').strip().lower()
            if not text:
                continue

            matched_positive = 0
            matched_negative = 0
            matched_neutral = 0

            for token in keywords['positive']:
                hits = len(re.findall(r'\b%s\b' % re.escape(token), text))
                if hits:
                    matched_positive += hits
                    keyword_counter[token] += hits

            for token in keywords['negative']:
                hits = len(re.findall(r'\b%s\b' % re.escape(token), text))
                if hits:
                    matched_negative += hits
                    keyword_counter[token] += hits

            for token in keywords['neutral']:
                hits = len(re.findall(r'\b%s\b' % re.escape(token), text))
                if hits:
                    matched_neutral += hits
                    keyword_counter[token] += hits

            if matched_positive > matched_negative and matched_positive >= matched_neutral:
                positive_count += 1
            elif matched_negative > matched_positive and matched_negative >= matched_neutral:
                negative_count += 1
            else:
                neutral_count += 1

        top_keywords = [kw for kw, _count in keyword_counter.most_common(5)]
        sentiment = self._sentiment_from_counts(positive_count, negative_count, neutral_count)

        summary_parts = [
            _('Positive: %s') % positive_count,
            _('Negative: %s') % negative_count,
            _('Neutral: %s') % neutral_count,
        ]
        if top_keywords:
            summary_parts.append(_('Top keywords: %s') % ', '.join(top_keywords))

        return {
            'positive_count': positive_count,
            'negative_count': negative_count,
            'neutral_count': neutral_count,
            'sentiment': sentiment,
            'summary': ' | '.join(summary_parts),
        }

    def _is_internal_note(self, message):
        mt_note = self.env.ref('mail.mt_note', raise_if_not_found=False)
        subtype = message.subtype_id
        return bool(
            subtype and (
                subtype.internal
                or (mt_note and subtype.id == mt_note.id)
            )
        )

    def _extract_issue_summary(self, internal_messages):
        snippets = []
        for msg in reversed(internal_messages[-3:]):
            plain = html2plaintext(msg.body or '').strip()
            if plain:
                compact = ' '.join(plain.split())
                snippets.append(compact[:220])
        return ' | '.join(snippets)

    def action_generate_report(self):
        self.ensure_one()

        if self.date_to < self.date_from:
            raise UserError(_('End date must be greater than or equal to start date.'))

        start_dt, end_dt = self._datetime_bounds()

        lead_domain = [
            ('create_date', '>=', fields.Datetime.to_string(start_dt)),
            ('create_date', '<=', fields.Datetime.to_string(end_dt)),
            ('type', '=', 'lead'),
        ]
        if self.team_id:
            lead_domain.append(('team_id', '=', self.team_id.id))
        if self.user_id:
            lead_domain.append(('user_id', '=', self.user_id.id))

        leads = self.env['crm.lead'].with_context(active_test=not self.include_archived).search(lead_domain)
        if not leads:
            raise UserError(_('No leads found for the selected filters.'))

        message_domain = [
            ('model', '=', 'crm.lead'),
            ('res_id', 'in', leads.ids),
            ('message_type', 'in', ['comment', 'email']),
        ]
        messages = self.env['mail.message'].sudo().search(message_domain, order='date asc, id asc')

        messages_by_lead = defaultdict(list)
        for msg in messages:
            messages_by_lead[msg.res_id].append(msg)

        lines_model = self.env['crm.lead.activity.report.line']
        existing_lines = lines_model.search([('wizard_id', '=', self.id)])
        if existing_lines:
            existing_lines.unlink()

        now_utc = fields.Datetime.now()
        line_vals = []

        for lead in leads:
            lead_messages = messages_by_lead.get(lead.id, [])
            note_count = len(lead_messages)
            internal_messages = [msg for msg in lead_messages if self._is_internal_note(msg)]
            internal_note_count = len(internal_messages)

            first_interaction = lead_messages[0].date if lead_messages else False
            last_interaction = lead_messages[-1].date if lead_messages else False
            last_note_at = last_interaction

            analysis = self._analyze_messages(lead_messages)

            days_to_first_interaction = 0.0
            if first_interaction and lead.create_date:
                delta = fields.Datetime.from_string(first_interaction) - fields.Datetime.from_string(lead.create_date)
                days_to_first_interaction = round(delta.total_seconds() / 86400.0, 2)

            days_since_last_note = 0.0
            if last_note_at:
                delta_since = now_utc - fields.Datetime.from_string(last_note_at)
                days_since_last_note = round(delta_since.total_seconds() / 86400.0, 2)

            tag_names = ', '.join(lead.tag_ids.mapped('name')) if lead.tag_ids else ''
            contacted_tag = any('contacted' in (tag.name or '').lower() for tag in lead.tag_ids)

            latest_internal_note = ''
            if internal_messages:
                latest_internal_note = html2plaintext(internal_messages[-1].body or '').strip()

            issue_summary = self._extract_issue_summary(internal_messages)
            lost_reason_name = lead.lost_reason_id.name if lead.lost_reason_id else ''

            line_vals.append({
                'wizard_id': self.id,
                'lead_id': lead.id,
                'lead_name': lead.name,
                'company_name': lead.partner_name,
                'email_from': lead.email_from,
                'phone': lead.phone,
                'team_id': lead.team_id.id,
                'user_id': lead.user_id.id,
                'stage_id': lead.stage_id.id,
                'lead_created_at': lead.create_date,
                'first_interaction_at': first_interaction,
                'last_interaction_at': last_interaction,
                'last_note_at': last_note_at,
                'note_count': note_count,
                'internal_note_count': internal_note_count,
                'positive_note_count': analysis['positive_count'],
                'negative_note_count': analysis['negative_count'],
                'neutral_note_count': analysis['neutral_count'],
                'note_sentiment': analysis['sentiment'],
                'contacted_tag': contacted_tag,
                'tag_names': tag_names,
                'lost_reason': lost_reason_name,
                'latest_internal_note': latest_internal_note,
                'issue_summary': issue_summary,
                'note_analysis': analysis['summary'],
                'days_to_first_interaction': days_to_first_interaction,
                'days_since_last_note': days_since_last_note,
            })

        lines_model.create(line_vals)
        return self.env.ref('crm_lead_activity_report.crm_lead_activity_report_html').report_action(self)
