# -*- coding: utf-8 -*-
from odoo import models, fields, api


class HrContract(models.Model):
    _inherit = 'hr.contract'

    probation_period_months = fields.Integer(
        string='Probation Period (Months)',
        default=6,
        help='Duration of the probation period in months (from 1 to 6 months). Default is 6 months.'
    )

    @api.constrains('probation_period_months')
    def _check_probation_period_months(self):
        """Validate that probation period is between 1 and 6 months"""
        for contract in self:
            if contract.probation_period_months and (contract.probation_period_months < 1 or contract.probation_period_months > 6):
                from odoo.exceptions import ValidationError
                raise ValidationError(
                    'Probation period must be between 1 and 6 months.'
                )
