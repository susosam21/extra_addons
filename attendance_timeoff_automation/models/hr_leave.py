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
        Probation period is based on the contract's probation_period_months field.
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
            
            # Get probation period in months from contract (default to 6 if not set)
            probation_months = contract.probation_period_months if contract.probation_period_months else 6
            
            # Calculate probation end date from joining date
            joining_date = contract.date_start
            probation_end_date = joining_date + relativedelta(months=probation_months)
            
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
                'requires_allocation': 'yes',
                'employee_requests': 'yes',
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
                'requires_allocation': 'yes',
                'employee_requests': 'yes',
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
                'requires_allocation': 'no',
                'employee_requests': 'yes',
                'unpaid': True,
                'color': 3,  # Gray color
            })
            _logger.info(f"Created Unpaid Leave type: {leave_type.id}")
        
        return leave_type

    # @api.model
    # def _get_or_create_public_holiday_type(self):
    #     """
    #     Get or create the Public Holiday type.
    #     Uses code 'HOLIDAY' for unique identification.
    #     """
    #     leave_type = self.env['hr.leave.type'].search([
    #         ('code', '=', 'HOLIDAY'),
    #     ], limit=1)
        
    #     if not leave_type:
    #         leave_type = self.env['hr.leave.type'].create({
    #             'name': 'Public Holiday',
    #             'code': 'HOLIDAY',
    #             'requires_allocation': 'no',
    #             'employee_requests': 'no',
    #             'color': 4,  # Yellow color
    #         })
    #         _logger.info(f"Created Public Holiday type: {leave_type.id}")
        
    #     return leave_type

    @api.model
    def _allocate_leaves_for_employee(self, employee, contract):
        """
        Allocate monthly annual leaves for a single employee based on their contract.
        Allocates for all missing months from contract year start to current month.
        
        Probation Period (New Contracts from 2024 onwards):
        - Allocations start from joining date
        - For allocations during probation: validity starts from probation end date
        - For allocations after probation: validity starts from allocation date
        
        First Contract Year:
        - First 11 allocations: 2 days each (22 days total)
        - 12th allocation: 8 days (balance to reach 30 days)
        - Total: 30 days
        
        Subsequent Years (Year 2 onwards):
        - 2.5 days per month
        - Maximum 30 days per year (2.5 × 12 = 30)
        
        Validity: 1 year from validity start date
        """
        today = fields.Date.today()
        
        # Get the FIRST contract (original joining date) for the employee
        first_contract = self.env['hr.contract'].search([
            ('employee_id', '=', employee.id),
        ], order='date_start asc', limit=1)
        
        if not first_contract:
            _logger.debug(f"No contract found for employee {employee.name}")
            return 0
        
        # Use the original joining date from the first contract
        joining_date = first_contract.date_start
        
        # Determine contract type based on ORIGINAL joining date (new contracts from 2024-01-01 onwards)
        cutoff_date = fields.Date.from_string('2024-01-01')
        is_new_contract = joining_date >= cutoff_date
        
        # Get probation period for validity date calculation
        probation_months = first_contract.probation_period_months if first_contract.probation_period_months else 6
        probation_end_date = joining_date + relativedelta(months=probation_months)
        
        # Allocation starts from joining date for all contracts
        allocation_start_date = joining_date
        
        # Get annual leave type
        leave_type = self._get_or_create_annual_leave_type()
        
        # Get ALL existing auto-allocated annual leave for this employee
        existing_allocations = self.search([
            ('employee_id', '=', employee.id),
            ('holiday_status_id', '=', leave_type.id),
            ('is_auto_allocated', '=', True),
            ('state', '=', 'validate'),
        ])
        
        # Get list of months already allocated using date_from (not create_date)
        allocated_months = set()
        for alloc in existing_allocations:
            if alloc.date_from:
                month_key = alloc.date_from.strftime('%Y-%m-%d')  # Full date for precise matching
                allocated_months.add(month_key)
        
        total_days_allocated = 0
        contract_type = "New" if is_new_contract else "Old"
        
        # Get the day of month from ORIGINAL joining date (to maintain consistent day each month)
        allocation_day = joining_date.day
        
        # Calculate all months from allocation start date to today
        current_date = allocation_start_date
        
        # Track allocations per year (to handle cumulative totals within the current run)
        year_totals = {}  # {year_index: cumulative_days_allocated_in_this_run}
        
        # Loop through ALL months from allocation start date to today
        while current_date <= today:
            # Adjust to the same day as joining date, handling month-end cases
            try:
                month_allocation_date = current_date.replace(day=allocation_day)
            except ValueError:
                # Handle case where day doesn't exist in month (e.g., Feb 31)
                # Use last day of the month instead
                month_allocation_date = current_date + relativedelta(day=31)
            
            # Create unique key for this specific allocation date
            allocation_date_key = month_allocation_date.strftime('%Y-%m-%d')
            
            # Skip if already allocated for this exact date
            if allocation_date_key in allocated_months:
                current_date = current_date + relativedelta(months=1)
                continue
            
            # Calculate which contract year and month we're in (based on JOINING DATE, not allocation start)
            years_from_joining = relativedelta(month_allocation_date, joining_date).years
            year_start = joining_date + relativedelta(years=years_from_joining)
            year_end = joining_date + relativedelta(years=years_from_joining + 1)
            
            # Calculate month in year based on joining date anniversary
            month_in_year = relativedelta(month_allocation_date, year_start).months + 1
            
            # Check total allocated in this contract year (existing + current run)
            year_allocations = [a for a in existing_allocations 
                               if a.date_from >= year_start and a.date_from < year_end]
            total_this_year_existing = sum(a.number_of_days for a in year_allocations)
            total_this_year_current_run = year_totals.get(years_from_joining, 0)
            total_this_year = total_this_year_existing + total_this_year_current_run
            
            # Count how many allocations have been made in this contract year
            allocations_count_this_year = len(year_allocations)
            if years_from_joining in year_totals:
                # Count allocations in current run for this year
                allocations_count_this_year += sum(1 for _ in range(len(year_allocations), len(year_allocations) + int(total_this_year_current_run / 2)))
            
            # Skip if already reached 30 days in this year
            if total_this_year >= 30.0:
                current_date = current_date + relativedelta(months=1)
                continue
            
            # Determine if this is the first year of contract (based on joining date)
            is_first_year = (years_from_joining == 0)
            
            if is_first_year:
                # First year logic: 2 days for first 11 allocations, then balance to 30
                if allocations_count_this_year < 11:
                    days_to_allocate = 2.0
                else:  # 12th allocation and beyond
                    # Add remaining to reach 30 days total in first year
                    days_to_allocate = 30.0 - total_this_year
                    _logger.info(
                        f"Employee {employee.name} reached allocation #{allocations_count_this_year + 1} in first year, "
                        f"allocating {days_to_allocate} days to reach 30 total"
                    )
                
                # Ensure we don't exceed 30 days per year
                if total_this_year + days_to_allocate > 30.0:
                    days_to_allocate = 30.0 - total_this_year
            else:
                # Subsequent years (Year 2+): Standard 2.5 days per month
                days_to_allocate = 2.5
                
                # Ensure we don't exceed 30 days per year
                if total_this_year + days_to_allocate > 30.0:
                    days_to_allocate = 30.0 - total_this_year
            
            # Skip if no days to allocate
            if days_to_allocate <= 0:
                current_date = current_date + relativedelta(months=1)
                continue
            
            # Define allocation validity period
            # If allocation is during probation, validity starts from probation end date
            # Otherwise, validity starts from allocation date
            if is_new_contract and month_allocation_date < probation_end_date:
                validity_start = probation_end_date
            else:
                validity_start = month_allocation_date
            
            validity_end = validity_start + relativedelta(years=1)
            
            # Create the monthly allocation
            try:
                allocation = self.create({
                    'name': f'Annual Leave - {month_allocation_date.strftime("%B %Y")} ({contract_type} Contract)',
                    'holiday_status_id': leave_type.id,
                    'employee_id': employee.id,
                    'number_of_days': days_to_allocate,
                    'state': 'confirm',
                    'is_auto_allocated': True,
                    'date_from': validity_start,
                    'date_to': validity_end,
                    'allocation_type': 'regular',
                })
                
                # Automatically validate the allocation
                allocation.action_validate()
                
                total_days_allocated += days_to_allocate
                
                # Track cumulative total for this year in current run
                if years_from_joining not in year_totals:
                    year_totals[years_from_joining] = 0
                year_totals[years_from_joining] += days_to_allocate
                
                year_info = f"Year {years_from_joining + 1}"
                if is_first_year:
                    year_info += f", Allocation #{allocations_count_this_year + 1}"
                
                _logger.info(
                    f"Allocated {days_to_allocate} annual leave days to {employee.name} "
                    f"for {month_allocation_date.strftime('%B %Y')} ({contract_type} contract, "
                    f"{year_info}, Contract Month {month_in_year}, "
                    f"Valid: {validity_start} to {validity_end}, "
                    f"Total this year: {total_this_year_existing + year_totals[years_from_joining]}/30)"
                )
                
                # Add to allocated_months set to avoid duplicates in this run
                allocated_months.add(allocation_date_key)
                
            except Exception as e:
                _logger.error(f"Failed to allocate leaves for {employee.name} for {month_allocation_date}: {str(e)}")
            
            # Move to next month
            current_date = current_date + relativedelta(months=1)
        
        return total_days_allocated

    @api.model
    def _allocate_sick_leave_for_employee(self, employee, contract):
        """
        Allocate sick leaves for a single employee.
        
        Rules:
        - 15 days per contract year (based on joining date anniversary)
        - Validity period: From contract year start to contract year end
        - No carry over (expires at end of contract year)
        - Only eligible after probation period (based on contract, max 6 months)
        - Allocated once per contract year
        - Continues until contract ends or employee is no longer active
        """
        today = fields.Date.today()
        joining_date = contract.date_start
        
        # Get probation period from contract (default to 6 months if not set)
        probation_months = contract.probation_period_months if contract.probation_period_months else 6
        
        # Calculate if employee has completed probation period
        probation_end_date = joining_date + relativedelta(months=probation_months)
        has_completed_probation = today >= probation_end_date
        
        if not has_completed_probation:
            _logger.debug(f"Employee {employee.name} still in probation ({probation_months} months), no sick leave allocation")
            return 0
        
        # Get sick leave type
        leave_type = self._get_or_create_sick_leave_type()
        
        # Calculate current contract year based on joining date anniversary
        years_since_joining = relativedelta(today, joining_date).years
        current_contract_year_start = joining_date + relativedelta(years=years_since_joining)
        current_contract_year_end = joining_date + relativedelta(years=years_since_joining + 1)
        
        # Check if allocation already exists for current contract year
        existing_allocation = self.search([
            ('employee_id', '=', employee.id),
            ('holiday_status_id', '=', leave_type.id),
            ('is_auto_allocated', '=', True),
            ('state', '=', 'validate'),
            ('date_from', '>=', current_contract_year_start),
            ('date_from', '<', current_contract_year_end),
        ], limit=1)
        
        if existing_allocation:
            _logger.debug(
                f"Employee {employee.name} already has sick leave allocation for "
                f"contract year {years_since_joining + 1} ({current_contract_year_start} to {current_contract_year_end})"
            )
            return 0
        
        # Define allocation validity period (contract year based)
        validity_start = current_contract_year_start
        validity_end = current_contract_year_end
        
        # If contract has an end date and it's before the contract year end, use contract end date
        if contract.date_end and contract.date_end < validity_end:
            validity_end = contract.date_end
            _logger.info(
                f"Contract for {employee.name} ends on {contract.date_end}, "
                f"adjusting sick leave validity to contract end date"
            )
        
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
                'allocation_type': 'regular',
            })
            
            # Automatically validate the allocation
            allocation.action_validate()
            
            _logger.info(
                f"Allocated {days_to_allocate} sick leave days to {employee.name} "
                f"for contract year {years_since_joining + 1} "
                f"(Valid: {validity_start} to {validity_end})"
            )
            return days_to_allocate
            
        except Exception as e:
            _logger.error(f"Failed to allocate sick leaves for {employee.name}: {str(e)}")
            return 0

    @api.model
    def _auto_allocate_leaves(self):
        """
        Cron job method to automatically allocate monthly annual leaves to employees.
        
        First Year: 2 days for first 11 allocations, then balance to 30 on 12th allocation
        Subsequent Years: 2.5 days per month
        Maximum: 30 days per contract year
        """
        _logger.info("=" * 80)
        _logger.info("Starting automatic monthly annual leave allocation process...")
        _logger.info("=" * 80)
        
        # Ensure annual leave type is created
        self._get_or_create_annual_leave_type()
        
        today = fields.Date.today()
        
        # Find all active employees with active contracts
        contracts = self.env['hr.contract'].search([
            ('state', '=', 'open'),
            ('date_start', '<=', today),
            '|',
            ('date_end', '=', False),
            ('date_end', '>=', today),
        ])
        
        total_allocated = 0
        employee_count = 0
        
        for contract in contracts:
            employee = contract.employee_id
            
            if not employee or not employee.active:
                continue
            
            # Allocate monthly annual leave
            days_allocated = self._allocate_leaves_for_employee(employee, contract)
            
            if days_allocated > 0:
                total_allocated += days_allocated
                employee_count += 1
        
        _logger.info("=" * 80)
        _logger.info(
            f"Annual leave allocation completed. "
            f"Total: {total_allocated} days allocated to {employee_count} employees"
        )
        _logger.info("=" * 80)
        
        return True

    @api.model
    def _auto_allocate_sick_leaves(self):
        """
        Cron job method to automatically allocate sick leaves to employees
        based on their contract and tenure.
        Separate from annual leave allocation to allow independent scheduling.
        """
        _logger.info("=" * 80)
        _logger.info("Starting automatic sick leave allocation process...")
        _logger.info("=" * 80)
        
        # Ensure sick leave type is created
        self._get_or_create_sick_leave_type()
        
        today = fields.Date.today()
        
        # Find all active employees with active contracts
        contracts = self.env['hr.contract'].search([
            ('state', '=', 'open'),
            ('date_start', '<=', today),
            '|',
            ('date_end', '=', False),
            ('date_end', '>=', today),
        ])
        
        total_allocated = 0
        employee_count = 0
        
        for contract in contracts:
            employee = contract.employee_id
            
            if not employee or not employee.active:
                continue
            
            # Allocate sick leave (yearly after probation)
            days_allocated = self._allocate_sick_leave_for_employee(employee, contract)
            
            if days_allocated > 0:
                total_allocated += days_allocated
                employee_count += 1
        
        _logger.info("=" * 80)
        _logger.info(
            f"Sick leave allocation completed. "
            f"Total: {total_allocated} days allocated to {employee_count} employees"
        )
        _logger.info("=" * 80)
        
        return True
