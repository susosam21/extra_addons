# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    working_type = fields.Selection([
        ('office', 'Office'),
        ('remote', 'Remote'),
        ('holiday', 'Holiday'),
        ('sick', 'Sick Leave'),
        ('annual_leave', 'Annual Leave'),
        ('weekend', 'OFF'),
    ], string='Working Type', default='office', required=True)

    @api.model
    def _get_working_type_from_leave(self, leave):
        """
        Map leave type to working_type based on leave type code.
        Returns the appropriate working_type for a given leave record.
        """
        leave_type_code = leave.holiday_status_id.code or ''
        
        # Map leave types to working_type using unique codes
        if leave_type_code == 'SICK':
            return 'sick'
        elif leave_type_code == 'ANNUAL':
            return 'annual_leave'
        elif leave_type_code == 'HOLIDAY':
            return 'holiday'
        elif leave_type_code == 'UNPAID':
            return 'annual_leave'  # Treat unpaid as annual leave in attendance
        else:
            # Fallback: check name if code is not set
            leave_type_name = leave.holiday_status_id.name.lower()
            if 'sick' in leave_type_name:
                return 'sick'
            elif 'annual' in leave_type_name or 'paid' in leave_type_name:
                return 'annual_leave'
            elif 'holiday' in leave_type_name or 'public' in leave_type_name:
                return 'holiday'
            else:
                return 'holiday'  # Default

    @api.model
    def _create_timeoff_attendances(self):
        """
        Cron job method to automatically create attendance records for approved time off.
        Creates attendance records with appropriate working_type based on leave type.
        """
        _logger.info("Starting time off attendance creation process...")
        
        # Get current month's first and last day
        today = fields.Date.today()
        first_day = today.replace(day=1)
        last_day = (first_day + relativedelta(months=1)) - timedelta(days=1)
        
        # Search for approved leaves in the current month
        leaves = self.env['hr.leave'].search([
            ('state', '=', 'validate'),
            ('date_from', '<=', datetime.combine(last_day, datetime.max.time())),
            ('date_to', '>=', datetime.combine(first_day, datetime.min.time())),
        ])
        
        created_count = 0
        
        for leave in leaves:
            employee = leave.employee_id
            if not employee or not employee.active:
                continue
            
            # Determine the working_type based on leave type
            working_type = self._get_working_type_from_leave(leave)
            
            # Get leave date range
            leave_start = leave.date_from.date() if isinstance(leave.date_from, datetime) else leave.date_from
            leave_end = leave.date_to.date() if isinstance(leave.date_to, datetime) else leave.date_to
            
            # Ensure dates are within current month
            leave_start = max(leave_start, first_day)
            leave_end = min(leave_end, last_day)
            
            # Create attendance record for each day of the leave
            current_date = leave_start
            while current_date <= leave_end:
                # Check if attendance record already exists for this day
                existing = self.search([
                    ('employee_id', '=', employee.id),
                    ('check_in', '>=', datetime.combine(current_date, datetime.min.time())),
                    ('check_in', '<', datetime.combine(current_date + timedelta(days=1), datetime.min.time())),
                ], limit=1)
                
                if not existing:
                    # Create attendance record for the leave day
                    check_in = datetime.combine(current_date, datetime.min.time().replace(hour=0, minute=0))
                    check_out = datetime.combine(current_date, datetime.min.time().replace(hour=23, minute=59))
                    
                    try:
                        self.create({
                            'employee_id': employee.id,
                            'check_in': check_in,
                            'check_out': check_out,
                            'working_type': working_type,
                        })
                        created_count += 1
                        _logger.debug(f"Created {working_type} attendance for {employee.name} on {current_date}")
                    except Exception as e:
                        _logger.error(f"Failed to create time off attendance for {employee.name} on {current_date}: {str(e)}")
                
                current_date += timedelta(days=1)
        
        _logger.info(f"Time off attendance creation completed. Created: {created_count} records")
        return True

    @api.model
    def _create_weekend_attendances(self):
        """
        Cron job method to automatically create weekend attendance records
        for the current month based on employee work schedules.
        Only processes active employees with valid contracts.
        """
        _logger.info("Starting weekend attendance creation process...")
        
        # Get current month's first and last day
        today = fields.Date.today()
        first_day = today.replace(day=1)
        last_day = (first_day + relativedelta(months=1)) - timedelta(days=1)
        
        # Find active employees with valid contracts
        employees = self.env['hr.employee'].search([
            ('active', '=', True),
        ])
        
        created_count = 0
        skipped_count = 0
        
        for employee in employees:
            # Check if employee has an active contract
            contract = self.env['hr.contract'].search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'open'),
                ('date_start', '<=', last_day),
                '|',
                ('date_end', '=', False),
                ('date_end', '>=', first_day),
            ], limit=1)
            
            if not contract:
                _logger.debug(f"Skipping employee {employee.name} - no active contract")
                skipped_count += 1
                continue
            
            # Get the resource calendar (work schedule) from the contract
            calendar = contract.resource_calendar_id
            if not calendar:
                _logger.warning(f"Employee {employee.name} has no work schedule defined in contract")
                skipped_count += 1
                continue
            
            # Get all days that are NOT working days (weekends)
            # Calendar attendance lines define working hours
            # We need to find days not covered by the calendar
            working_days = set()
            for attendance_line in calendar.attendance_ids:
                # dayofweek: 0=Monday, 1=Tuesday, ..., 6=Sunday
                working_days.add(int(attendance_line.dayofweek))
            
            # Generate weekend days for the current month
            current_date = first_day
            while current_date <= last_day:
                # Python weekday: 0=Monday, 6=Sunday
                weekday = current_date.weekday()
                
                # If this day is NOT in the working days, it's a weekend/off day
                if weekday not in working_days:
                    # Check if attendance record already exists for this day
                    existing = self.search([
                        ('employee_id', '=', employee.id),
                        ('check_in', '>=', datetime.combine(current_date, datetime.min.time())),
                        ('check_in', '<', datetime.combine(current_date + timedelta(days=1), datetime.min.time())),
                    ], limit=1)
                    
                    if not existing:
                        # Create weekend attendance record
                        # Set check_in to start of day and check_out to end of day
                        check_in = datetime.combine(current_date, datetime.min.time().replace(hour=0, minute=0))
                        check_out = datetime.combine(current_date, datetime.min.time().replace(hour=23, minute=59))
                        
                        try:
                            self.create({
                                'employee_id': employee.id,
                                'check_in': check_in,
                                'check_out': check_out,
                                'working_type': 'weekend',
                            })
                            created_count += 1
                            _logger.debug(f"Created weekend attendance for {employee.name} on {current_date}")
                        except Exception as e:
                            _logger.error(f"Failed to create weekend attendance for {employee.name} on {current_date}: {str(e)}")
                
                current_date += timedelta(days=1)
        
        _logger.info(f"Weekend attendance creation completed. Created: {created_count}, Skipped employees: {skipped_count}")
        return True

    @api.model
    def _create_automated_attendances(self):
        """
        Master cron job method that orchestrates both weekend and time off attendance creation.
        This method is called by the scheduled action.
        """
        _logger.info("=" * 80)
        _logger.info("Starting automated attendance creation process...")
        _logger.info("=" * 80)
        
        # First, create time off attendances
        self._create_timeoff_attendances()
        
        # Then, create weekend attendances
        self._create_weekend_attendances()
        
        _logger.info("=" * 80)
        _logger.info("Automated attendance creation process completed")
        _logger.info("=" * 80)
        return True
