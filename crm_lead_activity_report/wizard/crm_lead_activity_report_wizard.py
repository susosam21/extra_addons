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

    def _build_report_lines(self, leads):
        message_domain = [
            ('model', '=', 'crm.lead'),
            ('res_id', 'in', leads.ids),
            ('message_type', 'in', ['comment', 'email']),
        ]
        messages = self.env['mail.message'].sudo().search(message_domain, order='date asc, id asc')

        messages_by_lead = defaultdict(list)
        for msg in messages:
            messages_by_lead[msg.res_id].append(msg)

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

        return line_vals

    @api.model
    def get_dashboard_data(self, date_from=False, date_to=False, team_id=False, user_id=False, include_archived=False):
        date_from = fields.Date.to_date(date_from) if date_from else fields.Date.context_today(self).replace(day=1)
        date_to = fields.Date.to_date(date_to) if date_to else fields.Date.context_today(self)

        if date_to < date_from:
            raise UserError(_('End date must be greater than or equal to start date.'))

        start_dt = datetime.combine(date_from, time.min)
        end_dt = datetime.combine(date_to, time.max)

        lead_domain = [
            ('create_date', '>=', fields.Datetime.to_string(start_dt)),
            ('create_date', '<=', fields.Datetime.to_string(end_dt)),
            ('type', '=', 'lead'),
        ]
        if team_id:
            lead_domain.append(('team_id', '=', int(team_id)))
        if user_id:
            lead_domain.append(('user_id', '=', int(user_id)))

        leads = self.env['crm.lead'].with_context(active_test=not include_archived).search(lead_domain)
        lines = self._build_report_lines(leads)
        total = len(lines)

        team_ids = [line['team_id'] for line in lines if line['team_id']]
        user_ids = [line['user_id'] for line in lines if line['user_id']]
        stage_ids = [line['stage_id'] for line in lines if line['stage_id']]

        team_map = {x['id']: x['name'] for x in self.env['crm.team'].sudo().search_read([('id', 'in', team_ids)], ['name'])}
        user_map = {x['id']: x['name'] for x in self.env['res.users'].sudo().search_read([('id', 'in', user_ids)], ['name'])}
        stage_map = {x['id']: x['name'] for x in self.env['crm.stage'].sudo().search_read([('id', 'in', stage_ids)], ['name'])}

        lines_view = []
        for line in lines:
            tags_lower = (line.get('tag_names') or '').lower()
            is_call_back = 'call back' in tags_lower or 'callback' in tags_lower
            is_proposal = 'proposal' in tags_lower or 'quotation' in tags_lower
            has_interaction = bool(line.get('first_interaction_at') or line.get('last_interaction_at') or line.get('internal_note_count'))
            contacted = bool(line.get('contacted_tag') or has_interaction)
            lost = bool(line.get('lost_reason'))
            actions = []
            if is_proposal:
                actions.append('Send Proposal')
            if is_call_back:
                actions.append('Call Back')
            lines_view.append(dict(
                line,
                team_name=team_map.get(line['team_id'], ''),
                user_name=user_map.get(line['user_id'], ''),
                stage_name=stage_map.get(line['stage_id'], ''),
                is_call_back=is_call_back,
                is_proposal=is_proposal,
                contacted=contacted,
                lost=lost,
                action_labels=actions,
            ))

        stage_counts = Counter()
        lost_reason_counts = Counter()
        by_salesperson = defaultdict(lambda: {
            'salesperson': '',
            'assigned': 0,
            'pct_total': 0,
            'moved_to_briefed': 0,
            'pending_activities': 0,
            'contacted': 0,
            'lost': 0,
            'internal_notes': 0,
        })
        briefed_by_salesperson = defaultdict(list)
        lost_by_salesperson = defaultdict(list)

        for line in lines_view:
            stage_name = line['stage_name'] or 'Undefined Stage'
            stage_counts[stage_name] += 1
            if line['lost_reason']:
                lost_reason_counts[line['lost_reason']] += 1

            salesperson = line['user_name'] or 'Unassigned'
            by_salesperson[salesperson]['salesperson'] = salesperson
            by_salesperson[salesperson]['assigned'] += 1
            by_salesperson[salesperson]['moved_to_briefed'] += 1 if 'brief' in stage_name.lower() else 0
            by_salesperson[salesperson]['pending_activities'] += 1 if (line['is_call_back'] or line['is_proposal']) else 0
            by_salesperson[salesperson]['contacted'] += 1 if line['contacted'] else 0
            by_salesperson[salesperson]['lost'] += 1 if line['lost'] else 0
            by_salesperson[salesperson]['internal_notes'] += line['internal_note_count']

            if 'brief' in stage_name.lower():
                briefed_by_salesperson[salesperson].append({
                    'company': line['company_name'] or line['lead_name'],
                    'email': line['email_from'] or '-',
                    'phone': line['phone'] or '-',
                    'actions': line['action_labels'] or ['-'],
                    'updated': line['last_note_at'] or line['last_interaction_at'] or line['lead_created_at'],
                })

            if line['lost_reason']:
                lost_by_salesperson[salesperson].append({
                    'company': line['company_name'] or line['lead_name'],
                    'email': line['email_from'] or '-',
                    'phone': line['phone'] or '-',
                    'lost_reason': line['lost_reason'],
                    'date': line['last_note_at'] or line['last_interaction_at'] or line['lead_created_at'],
                })

        for key in by_salesperson:
            by_salesperson[key]['pct_total'] = round((by_salesperson[key]['assigned'] / total) * 100, 1) if total else 0
            by_salesperson[key]['contact_rate'] = round((by_salesperson[key]['contacted'] / by_salesperson[key]['assigned']) * 100, 1) if by_salesperson[key]['assigned'] else 0
            by_salesperson[key]['loss_rate'] = round((by_salesperson[key]['lost'] / by_salesperson[key]['assigned']) * 100, 1) if by_salesperson[key]['assigned'] else 0

        stage_rows = []
        for name, count in stage_counts.most_common():
            stage_rows.append({
                'name': name,
                'count': count,
                'pct': round((count / total) * 100, 1) if total else 0,
            })

        lost_rows = []
        total_lost = sum(1 for line in lines_view if line['lost'])
        total_contacted = sum(1 for line in lines_view if line['contacted'])
        total_uncontacted = total - total_contacted
        avg_days_to_contact = round(
            sum(line['days_to_first_interaction'] for line in lines_view if line['contacted'] and line['days_to_first_interaction'] >= 0)
            / max(1, total_contacted),
            2,
        ) if total_contacted else 0
        total_notes = sum(line['internal_note_count'] for line in lines_view)
        avg_internal_notes_per_contacted = round(total_notes / max(1, total_contacted), 2) if total_contacted else 0

        for name, count in lost_reason_counts.most_common():
            lost_rows.append({
                'name': name,
                'count': count,
                'pct': round((count / total_lost) * 100, 1) if total_lost else 0,
            })

        reason_rows = []
        for idx, (name, count) in enumerate(lost_reason_counts.most_common(), start=1):
            reason_rows.append({
                'rank': idx,
                'name': name,
                'count': count,
                'pct_total_lost': round((count / total_lost) * 100, 1) if total_lost else 0,
            })

        positive_notes = sum(line['positive_note_count'] for line in lines_view)
        negative_notes = sum(line['negative_note_count'] for line in lines_view)
        neutral_notes = sum(line['neutral_note_count'] for line in lines_view)

        observations = [
            'The team worked on %s leads in the selected period.' % total,
            'Contacted leads: %s (%s%%).' % (total_contacted, round((total_contacted / total) * 100, 1) if total else 0),
            'Lost leads: %s. Unresolved issues should be reviewed from internal notes.' % total_lost,
            'Top lost reason: %s.' % (reason_rows[0]['name'] if reason_rows else 'No lost reason captured'),
            'Internal log notes captured: %s.' % total_notes,
        ]

        return {
            'filters': {
                'date_from': fields.Date.to_string(date_from),
                'date_to': fields.Date.to_string(date_to),
                'team_id': int(team_id) if team_id else False,
                'user_id': int(user_id) if user_id else False,
                'include_archived': bool(include_archived),
            },
            'kpis': {
                'total': total,
                'worked': sum(1 for l in lines_view if (l['contacted'] or l['lost'] or l['internal_note_count'] > 0)),
                'untouched': sum(1 for l in lines_view if not (l['contacted'] or l['lost'] or l['internal_note_count'] > 0)),
                'contacted': total_contacted,
                'moved_to_briefed': sum(1 for l in lines_view if 'brief' in (l['stage_name'] or '').lower()),
                'call_back': sum(1 for l in lines_view if l['is_call_back']),
                'proposal_to_send': sum(1 for l in lines_view if l['is_proposal']),
                'lost': total_lost,
                'internal_notes': total_notes,
                'uncontacted': total_uncontacted,
            },
            'analytics': {
                'contact_rate': round((total_contacted / total) * 100, 1) if total else 0,
                'loss_rate': round((total_lost / total) * 100, 1) if total else 0,
                'avg_days_to_contact': avg_days_to_contact,
                'avg_internal_notes_per_contacted': avg_internal_notes_per_contacted,
                'top_lost_reason': reason_rows[0]['name'] if reason_rows else 'N/A',
                'positive_notes': positive_notes,
                'negative_notes': negative_notes,
                'neutral_notes': neutral_notes,
            },
            'stages': stage_rows,
            'lost_reasons': lost_rows,
            'reason_rows': reason_rows,
            'by_salesperson': sorted(by_salesperson.values(), key=lambda x: x['assigned'], reverse=True),
            'briefed_by_salesperson': [
                {'salesperson': k, 'count': len(v), 'leads': v}
                for k, v in sorted(briefed_by_salesperson.items(), key=lambda item: len(item[1]), reverse=True)
            ],
            'lost_by_salesperson': [
                {'salesperson': k, 'count': len(v), 'leads': v}
                for k, v in sorted(lost_by_salesperson.items(), key=lambda item: len(item[1]), reverse=True)
            ],
            'observations': observations,
            'lines': lines_view,
            'teams': self.env['crm.team'].search_read([], ['name']),
            'users': self.env['res.users'].search_read([('share', '=', False)], ['name']),
        }

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

        lines_model = self.env['crm.lead.activity.report.line']
        existing_lines = lines_model.search([('wizard_id', '=', self.id)])
        if existing_lines:
            existing_lines.unlink()

        line_vals = self._build_report_lines(leads)
        lines_model.create([dict(vals, wizard_id=self.id) for vals in line_vals])
        return self.env.ref('crm_lead_activity_report.crm_lead_activity_report_html').report_action(self)
