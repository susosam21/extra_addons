# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    code = fields.Char(
        string='Code',
        help='Unique code to identify the leave type (e.g., ANNUAL, SICK, HOLIDAY)'
    )


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    @api.constrains('date_from', 'employee_id')
    def _check_probation_period(self):
        """
        Prevent employees from taking leave during probation period.
        Probation period is the first year from joining date.
        """
        for leave in self:
            if not leave.employee_id or not leave.date_from:
                continue
            
            # Get employee's contract
            contract = self.env['hr.contract'].search([
                ('employee_id', '=', leave.employee_id.id),
                ('state', '=', 'open'),
            ], limit=1, order='date_start asc')
            
            if not contract:
                continue
            
            # Calculate one year from joining date
            joining_date = contract.date_start
            probation_end_date = joining_date + relativedelta(years=1)
            
            # Get leave request date
            leave_date = leave.date_from.date() if isinstance(leave.date_from, datetime) else leave.date_from
            
            # Check if leave is requested during probation period
            if leave_date < probation_end_date:
                raise ValidationError(_(
                    'Employee %s is still in probation period (until %s). '
                    'Leave requests are not allowed during probation period.'
                ) % (leave.employee_id.name, probation_end_date.strftime('%Y-%m-%d')))


class HrLeaveAllocation(models.Model):
    _inherit = 'hr.leave.allocation'

    is_auto_allocated = fields.Boolean(
        string='Auto Allocated',
        default=False,
        help='Indicates if this allocation was created automatically by the system'
    )

    @api.model
    def _get_or_create_annual_leave_type(self):
        """
        Get or create the Annual Leave type for automatic allocation.
        Uses code 'ANNUAL' for unique identification.
        """
        leave_type = self.env['hr.leave.type'].search([
            ('code', '=', 'ANNUAL'),
        ], limit=1)
        
        if not leave_type:
            leave_type = self.env['hr.leave.type'].create({
                'name': 'Annual Leave',
                'code': 'ANNUAL',
                'allocation_type': 'fixed_allocation',
                'validity_start': False,
                'requires_allocation': 'yes',
                'employee_requests': 'yes',
                'approval_required': True,
                'color': 5,  # Purple color
            })
            _logger.info(f"Created Annual Leave type: {leave_type.id}")
        
        return leave_type

    @api.model
    def _get_or_create_sick_leave_type(self):
        """
        Get or create the Sick Leave type for automatic allocation.
        Uses code 'SICK' for unique identification.
        """
        leave_type = self.env['hr.leave.type'].search([
            ('code', '=', 'SICK'),
        ], limit=1)
        
        if not leave_type:
            leave_type = self.env['hr.leave.type'].create({
                'name': 'Sick Leave',
                'code': 'SICK',
                'allocation_type': 'fixed_allocation',
                'validity_start': False,
                'requires_allocation': 'yes',
                'employee_requests': 'yes',
                'approval_required': True,
                'color': 1,  # Red color
            })
            _logger.info(f"Created Sick Leave type: {leave_type.id}")
        
        return leave_type

    @api.model
    def _get_or_create_unpaid_leave_type(self):
        """
        Get or create the Unpaid Leave type.
        Uses code 'UNPAID' for unique identification.
        """
        leave_type = self.env['hr.leave.type'].search([
            ('code', '=', 'UNPAID'),
        ], limit=1)
        
        if not leave_type:
            leave_type = self.env['hr.leave.type'].create({
                'name': 'Unpaid Leave',
                'code': 'UNPAID',
                'allocation_type': 'no',
                'validity_start': False,
                'requires_allocation': 'no',
                'employee_requests': 'yes',
                'approval_required': True,
                'unpaid': True,
                'color': 3,  # Gray color
            })
            _logger.info(f"Created Unpaid Leave type: {leave_type.id}")
        
        return leave_type

    @api.model
    def _get_or_create_public_holiday_type(self):
        """
        Get or create the Public Holiday type.
        Uses code 'HOLIDAY' for unique identification.
        """
        leave_type = self.env['hr.leave.type'].search([
            ('code', '=', 'HOLIDAY'),
        ], limit=1)
        
        if not leave_type:
            leave_type = self.env['hr.leave.type'].create({
                'name': 'Public Holiday',
                'code': 'HOLIDAY',
                'allocation_type': 'no',
                'validity_start': False,
                'requires_allocation': 'no',
                'employee_requests': 'no',
                'approval_required': False,
                'color': 4,  # Yellow color
            })
            _logger.info(f"Created Public Holiday type: {leave_type.id}")
        
        return leave_type

    @api.model
    def _allocate_leaves_for_employee(self, employee, contract):
        """
        Allocate leaves for a single employee based on their contract and tenure.
        
        Rules:
        - First 11 months (probation): 2 days per month (total 22 days over 11 months)
        - At 1 year completion: Additional 8 days (total becomes 30 days)
        - After 1 year: 2.5 days per month
        - Leaves valid for 1 year only
        """
        today = fields.Date.today()
        joining_date = contract.date_start
        
        # Calculate months since joining
        months_since_joining = relativedelta(today, joining_date).months + \
                             (relativedelta(today, joining_date).years * 12)
        
        # Get annual leave type
        leave_type = self._get_or_create_annual_leave_type()
        
        # Define allocation validity period (1 year)
        validity_start = today
        validity_end = today + relativedelta(years=1)
        
        # Check if employee completed 1 year
        one_year_date = joining_date + relativedelta(years=1)
        has_completed_one_year = today >= one_year_date
        
        if not has_completed_one_year:
            # Employee is in first year (probation period)
            # Allocate 2 days per month for months completed
            
            # Don't allocate for the first month (month 0)
            if months_since_joining < 1:
                _logger.debug(f"Employee {employee.name} is in first month, no allocation yet")
                return 0
            
            # Check last allocation date to avoid duplicate monthly allocations
            last_allocation = self.search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id', '=', leave_type.id),
                ('is_auto_allocated', '=', True),
                ('state', '=', 'validate'),
            ], order='date_from desc', limit=1)
            
            # Calculate days to allocate this month
            days_to_allocate = 2.0
            
            # Check if we already allocated this month
            if last_allocation:
                last_alloc_date = last_allocation.date_from
                current_month_start = today.replace(day=1)
                
                if last_alloc_date >= current_month_start:
                    _logger.debug(f"Employee {employee.name} already has allocation for this month")
                    return 0
            
            # Special case: At exactly 1 year, give 8 extra days
            if months_since_joining == 12:
                days_to_allocate = 8.0
                _logger.info(f"Employee {employee.name} completed 1 year, allocating 8 bonus days")
            
        else:
            # Employee has completed more than 1 year
            # Allocate 2.5 days per month
            
            # Check if already allocated this month
            current_month_start = today.replace(day=1)
            existing_allocation = self.search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id', '=', leave_type.id),
                ('is_auto_allocated', '=', True),
                ('date_from', '>=', current_month_start),
                ('state', '=', 'validate'),
            ], limit=1)
            
            if existing_allocation:
                _logger.debug(f"Employee {employee.name} already has allocation for this month")
                return 0
            
            days_to_allocate = 2.5
        
        # Create the allocation
        try:
            allocation = self.create({
                'name': f'Auto Allocation - {today.strftime("%B %Y")}',
                'holiday_status_id': leave_type.id,
                'employee_id': employee.id,
                'number_of_days': days_to_allocate,
                'state': 'confirm',
                'is_auto_allocated': True,
                'date_from': validity_start,
                'date_to': validity_end,
                'allocation_type': 'accrual',
            })
            
            # Automatically validate the allocation
            allocation.action_validate()
            
            _logger.info(
                f"Allocated {days_to_allocate} days to {employee.name} "
                f"(Months since joining: {months_since_joining})"
            )
            return days_to_allocate
            
        except Exception as e:
            _logger.error(f"Failed to allocate leaves for {employee.name}: {str(e)}")
            return 0

    @api.model
    def _allocate_sick_leave_for_employee(self, employee, contract):
        """
        Allocate sick leaves for a single employee.
        
        Rules:
        - 15 days per contract year
        - No carry over (expires after 1 year)
        - Only eligible after probation period (1 year from joining)
        - Allocated once per contract year
        """
        today = fields.Date.today()
        joining_date = contract.date_start
        
        # Calculate if employee has completed probation period (1 year)
        one_year_date = joining_date + relativedelta(years=1)
        has_completed_probation = today >= one_year_date
        
        if not has_completed_probation:
            _logger.debug(f"Employee {employee.name} still in probation, no sick leave allocation")
            return 0
        
        # Get sick leave type
        leave_type = self._get_or_create_sick_leave_type()
        
        # Calculate current contract year start date
        # Contract year starts from joining date anniversary
        years_since_joining = relativedelta(today, joining_date).years
        current_contract_year_start = joining_date + relativedelta(years=years_since_joining)
        
        # Check if sick leave already allocated for current contract year
        existing_allocation = self.search([
            ('employee_id', '=', employee.id),
            ('holiday_status_id', '=', leave_type.id),
            ('is_auto_allocated', '=', True),
            ('date_from', '>=', current_contract_year_start),
            ('state', '=', 'validate'),
        ], limit=1)
        
        if existing_allocation:
            _logger.debug(f"Employee {employee.name} already has sick leave allocation for current contract year")
            return 0
        
        # Define allocation validity period (1 year from today, no carry over)
        validity_start = today
        validity_end = today + relativedelta(years=1)
        
        # Allocate 15 days
        days_to_allocate = 15.0
        
        try:
            allocation = self.create({
                'name': f'Sick Leave Allocation - Contract Year {years_since_joining + 1}',
                'holiday_status_id': leave_type.id,
                'employee_id': employee.id,
                'number_of_days': days_to_allocate,
                'state': 'confirm',
                'is_auto_allocated': True,
                'date_from': validity_start,
                'date_to': validity_end,
                'allocation_type': 'accrual',
            })
            
            # Automatically validate the allocation
            allocation.action_validate()
            
            _logger.info(
                f"Allocated {days_to_allocate} sick leave days to {employee.name} "
                f"(Contract year: {years_since_joining + 1})"
            )
            return days_to_allocate
            
        except Exception as e:
            _logger.error(f"Failed to allocate sick leaves for {employee.name}: {str(e)}")
            return 0

    @api.model
    def _auto_allocate_leaves(self):
        """
        Cron job method to automatically allocate leaves to employees
        based on their contract and tenure.
        """
        _logger.info("=" * 80)
        _logger.info("Starting automatic leave allocation process...")
        _logger.info("=" * 80)
        
        # Ensure all leave types are created
        self._get_or_create_annual_leave_type()
        self._get_or_create_sick_leave_type()
        self._get_or_create_unpaid_leave_type()
        self._get_or_create_public_holiday_type()
        
        today = fields.Date.today()
        
        # Find all active employees with active contracts
        contracts = self.env['hr.contract'].search([
            ('state', '=', 'open'),
            ('date_start', '<=', today),
            '|',
            ('date_end', '=', False),
            ('date_end', '>=', today),
        ])
        
        total_allocated_annual = 0
        total_allocated_sick = 0
        employee_count = 0
        
        for contract in contracts:
            employee = contract.employee_id
            
            if not employee or not employee.active:
                continue
            
            # Allocate annual leave (monthly)
            days_allocated_annual = self._allocate_leaves_for_employee(employee, contract)
            
            # Allocate sick leave (yearly after probation)
            days_allocated_sick = self._allocate_sick_leave_for_employee(employee, contract)
            
            if days_allocated_annual > 0 or days_allocated_sick > 0:
                total_allocated_annual += days_allocated_annual
                total_allocated_sick += days_allocated_sick
                employee_count += 1
        
        _logger.info("=" * 80)
        _logger.info(
            f"Leave allocation completed. "
            f"Annual: {total_allocated_annual} days, Sick: {total_allocated_sick} days "
            f"to {employee_count} employees"
        )
        _logger.info("=" * 80)
        
        return True
