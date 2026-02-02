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
    attendance_date = fields.Date(
        string='Day',
        compute='_compute_attendance_date',
        store=True
    )
    day_name = fields.Char(
        string='Day',
        compute='_compute_day_name',
        store=True
    )
    month = fields.Char(
        string='Month',
        compute='_compute_month',
        store=True
    )
    note = fields.Text(string='Note')

    @api.depends('check_in', 'check_out')
    def _compute_attendance_date(self):
        for record in self:
            dt_value = record.check_in or record.check_out
            if isinstance(dt_value, datetime):
                record.attendance_date = dt_value.date()
            else:
                record.attendance_date = dt_value

    @api.depends('attendance_date')
    def _compute_day_name(self):
        for record in self:
            if record.attendance_date:
                record.day_name = record.attendance_date.strftime('%A')
            else:
                record.day_name = False

    @api.depends('attendance_date')
    def _compute_month(self):
        for record in self:
            if record.attendance_date:
                record.month = record.attendance_date.strftime('%Y-%m')
            else:
                record.month = False

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to check for approved leaves and update working_type accordingly."""
        records = super(HrAttendance, self).create(vals_list)
        for record in records:
            record._check_and_update_for_approved_leave()
        return records

    def write(self, vals):
        """Override write to check for approved leaves and update working_type accordingly."""
        result = super(HrAttendance, self).write(vals)
        # Only check for leave update if date/employee changed to avoid unnecessary processing
        if 'check_in' in vals or 'check_out' in vals or 'employee_id' in vals:
            for record in self:
                record._check_and_update_for_approved_leave()
        return result

    def _check_and_update_for_approved_leave(self):
        """Check if there's an approved leave for this attendance and update working_type."""
        if not self.employee_id or not self.check_in:
            return
        
        attendance_date = self.check_in.date() if isinstance(self.check_in, datetime) else self.check_in
        
        # Search for approved leave that covers this date
        leave = self.env['hr.leave'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'validate'),
            ('date_from', '<=', datetime.combine(attendance_date, datetime.max.time())),
            ('date_to', '>=', datetime.combine(attendance_date, datetime.min.time())),
        ], limit=1)
        
        if leave:
            # Get the appropriate working_type for this leave
            leave_working_type = self._get_working_type_from_leave(leave)
            leave_note = self._get_leave_note(leave)
            
            # FIX: Check if update is actually needed before calling write
            vals = {}
            if self.working_type != leave_working_type:
                vals['working_type'] = leave_working_type
            if leave_note and self.note != leave_note:
                vals['note'] = leave_note
                
            # Only update if there are actual changes
            if vals:
                # Use SQL update to avoid triggering write method again
                self.env.cr.execute(
                    "UPDATE hr_attendance SET working_type = %s, note = %s WHERE id = %s",
                    (vals.get('working_type', self.working_type), 
                     vals.get('note', self.note), 
                     self.id)
                )
                self.invalidate_recordset(['working_type', 'note'])
                _logger.info(f"Updated attendance for {self.employee_id.name} on {attendance_date} to {leave_working_type} due to approved leave")

    @api.model
    def _get_leave_note(self, leave):
        """Return a note string from leave description if available."""
        if not leave:
            return False
        leave_name = (leave.name or '').strip()
        return leave_name if leave_name else False

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
                
                if existing:
                    # If it's a weekend attendance, update it to the leave type
                    if existing.working_type == 'weekend':
                        try:
                            # Keep the 0 hours duration (check_in = check_out) but update the type
                            leave_note = self._get_leave_note(leave)
                            update_vals = {
                                'working_type': working_type,
                            }
                            if leave_note:
                                update_vals['note'] = leave_note
                            existing.write({
                                **update_vals,
                            })
                            created_count += 1
                            _logger.debug(f"Updated weekend to {working_type} attendance for {employee.name} on {current_date}")
                        except Exception as e:
                            _logger.error(f"Failed to update weekend attendance for {employee.name} on {current_date}: {str(e)}")
                else:
                    # Create attendance record for the leave day with 0 hours
                    # Set check_in and check_out to the same time (0 hours duration)
                    check_in = datetime.combine(current_date, datetime.min.time().replace(hour=0, minute=0))
                    check_out = check_in  # Same time = 0 hours
                    
                    try:
                        leave_note = self._get_leave_note(leave)
                        create_vals = {
                            'employee_id': employee.id,
                            'check_in': check_in,
                            'check_out': check_out,
                            'working_type': working_type,
                        }
                        if leave_note:
                            create_vals['note'] = leave_note
                        self.create({
                            **create_vals,
                        })
                        created_count += 1
                        _logger.debug(f"Created {working_type} attendance (0 hours) for {employee.name} on {current_date}")
                    except Exception as e:
                        _logger.error(f"Failed to create time off attendance for {employee.name} on {current_date}: {str(e)}")
                
                current_date += timedelta(days=1)
        
        _logger.info(f"Time off attendance creation completed. Created: {created_count} records")
        self._create_public_holiday_attendances(first_day, last_day)
        return True

    @api.model
    def _create_public_holiday_attendances(self, first_day, last_day):
        """Create attendances for public holidays from resource calendar leaves."""
        _logger.info("Starting public holiday attendance creation process...")

        employees = self.env['hr.employee'].search([
            ('active', '=', True),
        ])

        created_count = 0
        ResourceLeave = self.env['resource.calendar.leaves']

        for employee in employees:
            contract = self.env['hr.contract'].search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'open'),
                ('date_start', '<=', last_day),
                '|',
                ('date_end', '=', False),
                ('date_end', '>=', first_day),
            ], limit=1)

            if not contract or not contract.resource_calendar_id:
                continue

            calendar = contract.resource_calendar_id
            calendar_leaves = ResourceLeave.search([
                ('calendar_id', '=', calendar.id),
                ('resource_id', '=', False),
                ('date_from', '<=', datetime.combine(last_day, datetime.max.time())),
                ('date_to', '>=', datetime.combine(first_day, datetime.min.time())),
            ])

            for calendar_leave in calendar_leaves:
                leave_start = calendar_leave.date_from.date() if isinstance(calendar_leave.date_from, datetime) else calendar_leave.date_from
                leave_end = calendar_leave.date_to.date() if isinstance(calendar_leave.date_to, datetime) else calendar_leave.date_to

                leave_start = max(leave_start, first_day)
                leave_end = min(leave_end, last_day)

                current_date = leave_start
                while current_date <= leave_end:
                    existing = self.search([
                        ('employee_id', '=', employee.id),
                        ('check_in', '>=', datetime.combine(current_date, datetime.min.time())),
                        ('check_in', '<', datetime.combine(current_date + timedelta(days=1), datetime.min.time())),
                    ], limit=1)

                    holiday_note = (calendar_leave.name or '').strip() or False

                    if existing:
                        if existing.working_type == 'weekend':
                            try:
                                update_vals = {
                                    'working_type': 'holiday',
                                }
                                if holiday_note:
                                    update_vals['note'] = holiday_note
                                existing.write(update_vals)
                                created_count += 1
                                _logger.debug(f"Updated weekend to holiday attendance for {employee.name} on {current_date}")
                            except Exception as e:
                                _logger.error(f"Failed to update public holiday attendance for {employee.name} on {current_date}: {str(e)}")
                    else:
                        check_in = datetime.combine(current_date, datetime.min.time().replace(hour=0, minute=0))
                        check_out = check_in
                        try:
                            create_vals = {
                                'employee_id': employee.id,
                                'check_in': check_in,
                                'check_out': check_out,
                                'working_type': 'holiday',
                            }
                            if holiday_note:
                                create_vals['note'] = holiday_note
                            self.create(create_vals)
                            created_count += 1
                            _logger.debug(f"Created holiday attendance (0 hours) for {employee.name} on {current_date}")
                        except Exception as e:
                            _logger.error(f"Failed to create public holiday attendance for {employee.name} on {current_date}: {str(e)}")

                    current_date += timedelta(days=1)

        _logger.info(f"Public holiday attendance creation completed. Created/Updated: {created_count} records")
        return True

    @api.model
    def _create_weekend_attendances(self):
        """
        Cron job method to automatically create weekend attendance records
        for the current month based on employee work schedules.
        Only processes active employees with valid contracts.
        Creates attendance with 0 hours for days with 0 working hours in schedule.
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
            
            # Identify days with 0 working hours (weekends/off days)
            # Check the duration_days field instead of calculating from hour_from/hour_to
            zero_hour_days = set()
            _logger.info(f"Checking calendar '{calendar.name}' for employee {employee.name}")
            _logger.info(f"  Calendar has {len(calendar.attendance_ids)} attendance lines")
            
            for attendance_line in calendar.attendance_ids:
                day_num = int(attendance_line.dayofweek)
                duration = attendance_line.duration_days if hasattr(attendance_line, 'duration_days') else 0
                
                _logger.info(f"  Day {day_num} ({['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][day_num]}): "
                           f"duration_days = {duration}")
                
                # If duration is 0, it's a weekend/off day
                if duration == 0 or abs(duration) < 0.01:
                    zero_hour_days.add(day_num)
                    _logger.info(f"    ✓ Identified as 0-duration day (weekend)")
            
            _logger.info(f"Employee {employee.name}: Zero-hour days = {sorted(zero_hour_days)}")
            
            # Generate weekend days for the current month
            current_date = first_day
            while current_date <= last_day:
                # Python weekday: 0=Monday, 6=Sunday
                weekday = current_date.weekday()
                
                # If this day has 0 working hours, create weekend attendance
                if weekday in zero_hour_days:
                    # Check if attendance record already exists for this day
                    existing = self.search([
                        ('employee_id', '=', employee.id),
                        ('check_in', '>=', datetime.combine(current_date, datetime.min.time())),
                        ('check_in', '<', datetime.combine(current_date + timedelta(days=1), datetime.min.time())),
                    ], limit=1)
                    
                    if not existing:
                        # Create weekend attendance record with 0 hours
                        # Set both check_in and check_out to the same time (0 hours)
                        check_in = datetime.combine(current_date, datetime.min.time().replace(hour=0, minute=0))
                        check_out = check_in  # Same time = 0 hours
                        
                        try:
                            self.create({
                                'employee_id': employee.id,
                                'check_in': check_in,
                                'check_out': check_out,
                                'working_type': 'weekend',
                            })
                            created_count += 1
                            _logger.debug(f"Created weekend attendance (0 hours) for {employee.name} on {current_date}")
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
