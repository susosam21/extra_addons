# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


class HrAttendanceSummary(models.TransientModel):
    """
    Transient model for generating attendance summary reports.
    This model computes worked days vs total working days for employees.
    """
    _name = 'hr.attendance.summary'
    _description = 'HR Attendance Summary'
    _rec_name = 'name'

    name = fields.Char(string='Name', compute='_compute_name', store=True)
    month_selection = fields.Selection([
        ('01', 'January'),
        ('02', 'February'),
        ('03', 'March'),
        ('04', 'April'),
        ('05', 'May'),
        ('06', 'June'),
        ('07', 'July'),
        ('08', 'August'),
        ('09', 'September'),
        ('10', 'October'),
        ('11', 'November'),
        ('12', 'December'),
    ], string='Month', default=lambda self: str(fields.Date.today().month).zfill(2))
    year_selection = fields.Integer(string='Year', default=lambda self: fields.Date.today().year)
    date_from = fields.Date(string='From Date', compute='_compute_dates', store=True)
    date_to = fields.Date(string='To Date', compute='_compute_dates', store=True)
    employee_ids = fields.Many2many('hr.employee', string='Employees', help='Leave empty to include all employees')
    line_ids = fields.One2many('hr.attendance.summary.line', 'summary_id', string='Summary Lines')
    
    # Time off summary fields
    total_paid_time_off = fields.Float(string='Total Paid Time Off', compute='_compute_timeoff_summary')
    total_sick_time_off = fields.Float(string='Total Sick Time Off', compute='_compute_timeoff_summary')
    total_compensatory_hours = fields.Float(string='Total Compensatory Hours', compute='_compute_timeoff_summary')
    
    # Summary fields for tree view
    total_employees = fields.Integer(string='Total Employees', compute='_compute_summary_stats')
    total_worked_days_sum = fields.Float(string='Total Worked Days', compute='_compute_summary_stats')
    total_working_days_sum = fields.Float(string='Total Working Days', compute='_compute_summary_stats')
    overall_attendance_percentage = fields.Float(string='Overall Attendance %', compute='_compute_summary_stats')
    
    # Working type totals
    total_office_days = fields.Integer(string='Total Office Days', compute='_compute_summary_stats')
    total_remote_days = fields.Integer(string='Total Remote Days', compute='_compute_summary_stats')
    total_annual_leave_days = fields.Integer(string='Total Annual Leave Days', compute='_compute_summary_stats')
    total_sick_days = fields.Integer(string='Total Sick Days', compute='_compute_summary_stats')
    total_holiday_days = fields.Integer(string='Total Holiday Days', compute='_compute_summary_stats')
    total_weekend_days = fields.Integer(string='Total Weekend Days', compute='_compute_summary_stats')
    actual_worked_count = fields.Integer(string='Employees Who Worked', compute='_compute_summary_stats')
    actual_working_days_in_month = fields.Float(string='Actual Working Days in Month', compute='_compute_summary_stats')

    @api.depends('month_selection', 'year_selection')
    def _compute_name(self):
        """Generate a display name based on month and year."""
        month_names = {
            '01': 'January', '02': 'February', '03': 'March', '04': 'April',
            '05': 'May', '06': 'June', '07': 'July', '08': 'August',
            '09': 'September', '10': 'October', '11': 'November', '12': 'December'
        }
        for record in self:
            if record.month_selection and record.year_selection:
                month_name = month_names.get(record.month_selection, 'Unknown')
                record.name = f"{month_name} {record.year_selection} - Attendance Summary"
            else:
                record.name = "Attendance Summary"

    @api.depends('month_selection', 'year_selection')
    def _compute_dates(self):
        """Compute date_from and date_to based on month and year selection."""
        for record in self:
            if record.month_selection and record.year_selection:
                month = int(record.month_selection)
                year = record.year_selection
                # First day of the month
                record.date_from = datetime(year, month, 1).date()
                # Last day of the month
                if month == 12:
                    record.date_to = datetime(year, 12, 31).date()
                else:
                    record.date_to = (datetime(year, month + 1, 1) - timedelta(days=1)).date()
            else:
                record.date_from = fields.Date.today().replace(day=1)
                record.date_to = fields.Date.today()

    @api.depends('employee_ids')
    def _compute_timeoff_summary(self):
        """Compute total available time off across selected employees."""
        for record in self:
            if not record.employee_ids:
                employees = self.env['hr.employee'].search([('active', '=', True)])
            else:
                employees = record.employee_ids

            employees = record._filter_employees_with_contract(
                employees,
                record.date_from or fields.Date.today().replace(day=1),
                record.date_to or fields.Date.today(),
            )
            
            total_paid = 0
            total_sick = 0
            total_comp = 0
            
            for employee in employees:
                # Get allocation for each leave type
                allocations = self.env['hr.leave.allocation'].search([
                    ('employee_id', '=', employee.id),
                    ('state', '=', 'validate'),
                    ('date_to', '>=', fields.Date.today()),
                ])
                
                for allocation in allocations:
                    leave_type_code = allocation.holiday_status_id.code or ''
                    leave_type_name = allocation.holiday_status_id.name.lower()
                    
                    # Calculate remaining days/hours
                    remaining = allocation.number_of_days - allocation.leaves_taken
                    
                    if leave_type_code == 'ANNUAL' or 'paid' in leave_type_name or 'annual' in leave_type_name:
                        total_paid += remaining
                    elif leave_type_code == 'SICK' or 'sick' in leave_type_name:
                        total_sick += remaining
                    elif 'comp' in leave_type_name or 'overtime' in leave_type_name:
                        # Convert days to hours for compensatory time
                        total_comp += remaining * 8
            
            record.total_paid_time_off = total_paid
            record.total_sick_time_off = total_sick
            record.total_compensatory_hours = total_comp

    @api.depends('line_ids', 'line_ids.worked_days', 'line_ids.total_working_days')
    def _compute_summary_stats(self):
        """Compute summary statistics for tree view display."""
        for record in self:
            total_employees = len(record.line_ids)
            total_worked = sum(record.line_ids.mapped('worked_days'))
            total_working = sum(record.line_ids.mapped('total_working_days'))
            
            # Calculate totals for each working type
            total_office = sum(record.line_ids.mapped('office_days'))
            total_remote = sum(record.line_ids.mapped('remote_days'))
            total_annual_leave = sum(record.line_ids.mapped('leave_days'))
            total_sick = sum(record.line_ids.mapped('sick_days'))
            total_holiday = sum(record.line_ids.mapped('holiday_days'))
            total_weekend = sum(record.line_ids.mapped('weekend_days'))
            
            # Count employees who actually worked (office + remote > 0)
            actual_worked = len([line for line in record.line_ids if (line.office_days + line.remote_days) > 0])
            
            # Calculate actual working days in month based on employee schedules
            actual_working_days = sum(record.line_ids.mapped('total_working_days'))

            # Deduct public holidays from total working days
            adjusted_total_working = max(total_working - total_holiday, 0)
            
            record.total_employees = total_employees
            record.total_worked_days_sum = total_worked
            record.total_working_days_sum = adjusted_total_working
            record.overall_attendance_percentage = (total_worked / total_working * 100) if total_working > 0 else 0
            record.total_office_days = int(total_office)
            record.total_remote_days = int(total_remote)
            record.total_annual_leave_days = int(total_annual_leave)
            record.total_sick_days = int(total_sick)
            record.total_holiday_days = int(total_holiday)
            record.total_weekend_days = int(total_weekend)
            record.actual_worked_count = actual_worked
            record.actual_working_days_in_month = max(actual_working_days - total_holiday, 0)

    def action_compute_summary(self):
        """Compute the attendance summary for the selected date range and employees."""
        self.ensure_one()
        
        # Clear existing lines
        self.line_ids.unlink()
        
        # Get employees
        if self.employee_ids:
            employees = self.employee_ids
        else:
            employees = self.env['hr.employee'].search([('active', '=', True)])

        employees = self._filter_employees_with_contract(employees, self.date_from, self.date_to)
        
        # Compute summary for each employee
        lines_data = []
        for employee in employees:
            summary_data = self._compute_employee_summary(employee)
            lines_data.append(summary_data)
        
        # Create summary lines
        self.env['hr.attendance.summary.line'].create(lines_data)
        
        # Return action to display the summary
        return {
            'type': 'ir.actions.act_window',
            'name': 'Attendance Summary',
            'res_model': 'hr.attendance.summary',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }

    def _compute_employee_summary(self, employee):
        """
        Compute attendance summary for a single employee.
        Returns a dict with summary data.
        """
        # Calculate total working days based on employee schedule
        total_working_days = self._calculate_working_days(self.date_from, self.date_to, employee)
        
        # Get attendance records for the period
        attendances = self.env['hr.attendance'].search([
            ('employee_id', '=', employee.id),
            ('check_in', '>=', datetime.combine(self.date_from, datetime.min.time())),
            ('check_in', '<=', datetime.combine(self.date_to, datetime.max.time())),
        ])
        
        # Calculate worked days based on working_type
        worked_days = 0
        office_days = 0
        remote_days = 0
        leave_days = 0
        holiday_days = 0
        sick_days = 0
        weekend_days = 0
        
        # Group attendances by date to avoid double counting
        attendance_by_date = {}
        for attendance in attendances:
            attendance_date = attendance.check_in.date() if isinstance(attendance.check_in, datetime) else attendance.check_in
            if attendance_date not in attendance_by_date:
                attendance_by_date[attendance_date] = []
            attendance_by_date[attendance_date].append(attendance)
        
        # Process each date
        for date, date_attendances in attendance_by_date.items():
            # Get the most relevant working_type for the day
            # Priority: leave types > office/remote
            working_types = [att.working_type for att in date_attendances]
            
            if 'sick' in working_types:
                sick_days += 1
                # Sick days don't count as worked days
            elif 'annual_leave' in working_types:
                leave_days += 1
                # Annual leave days don't count as worked days
            elif 'holiday' in working_types:
                holiday_days += 1
                # Holiday days don't count as worked days
            elif 'weekend' in working_types:
                weekend_days += 1
                # Weekend days don't count as worked days
            elif 'office' in working_types:
                office_days += 1
                worked_days += 1
            elif 'remote' in working_types:
                remote_days += 1
                worked_days += 1
        
        # Deduct public holidays from working days
        adjusted_working_days = max(total_working_days - holiday_days, 0)

        # Calculate attendance percentage
        attendance_percentage = (worked_days / adjusted_working_days * 100) if adjusted_working_days > 0 else 0
        
        return {
            'summary_id': self.id,
            'employee_id': employee.id,
            'total_working_days': adjusted_working_days,
            'worked_days': worked_days,
            'office_days': office_days,
            'remote_days': remote_days,
            'leave_days': leave_days,
            'holiday_days': holiday_days,
            'sick_days': sick_days,
            'weekend_days': weekend_days,
            'attendance_percentage': attendance_percentage,
        }

    def _calculate_working_days(self, date_from, date_to, employee):
        """
        Calculate the number of working days in the date range based on the
        employee's working schedule (resource calendar).
        """
        calendar = False
        contract = self.env['hr.contract'].search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'open'),
            ('date_start', '<=', date_to),
            '|',
            ('date_end', '=', False),
            ('date_end', '>=', date_from),
        ], limit=1)

        if contract and contract.resource_calendar_id:
            calendar = contract.resource_calendar_id
        elif hasattr(employee, 'resource_calendar_id') and employee.resource_calendar_id:
            calendar = employee.resource_calendar_id

        current_date = date_from
        working_days = 0

        while current_date <= date_to:
            weekday = current_date.weekday()
            if calendar:
                is_working_day = any(
                    int(att.dayofweek) == weekday and att.duration_days > 0
                    for att in calendar.attendance_ids
                )
                if is_working_day:
                    working_days += 1
            else:
                if weekday < 5:
                    working_days += 1
            current_date += timedelta(days=1)

        return working_days

    @api.model
    def get_summary_data(self, date_from=None, date_to=None, employee_ids=None):
        """
        API method to get summary data for dashboard widget.
        Returns a list of dictionaries with summary information.
        """
        # Set default dates (current month)
        if not date_from:
            date_from = fields.Date.today().replace(day=1)
        else:
            date_from = fields.Date.to_date(date_from)
        
        if not date_to:
            date_to = fields.Date.today()
        else:
            date_to = fields.Date.to_date(date_to)
        
        # Get employees
        if employee_ids:
            employees = self.env['hr.employee'].browse(employee_ids)
        else:
            employees = self.env['hr.employee'].search([('active', '=', True)])

        employees = self._filter_employees_with_contract(employees, date_from, date_to)
        
        # Create temporary summary record
        summary = self.create({
            'date_from': date_from,
            'date_to': date_to,
        })
        
        # Compute summary data
        summary_data = []
        for employee in employees:
            employee_summary = summary._compute_employee_summary(employee)
            summary_data.append({
                'employee_id': employee.id,
                'employee_name': employee.name,
                'total_working_days': employee_summary['total_working_days'],
                'worked_days': employee_summary['worked_days'],
                'office_days': employee_summary['office_days'],
                'remote_days': employee_summary['remote_days'],
                'leave_days': employee_summary['leave_days'],
                'holiday_days': employee_summary['holiday_days'],
                'sick_days': employee_summary['sick_days'],
                'weekend_days': employee_summary['weekend_days'],
                'attendance_percentage': round(employee_summary['attendance_percentage'], 2),
            })
        
        return summary_data

    def _filter_employees_with_contract(self, employees, date_from, date_to):
        """Return only employees who have an active contract in the given period."""
        if not employees:
            return employees

        contracts = self.env['hr.contract'].search([
            ('employee_id', 'in', employees.ids),
            ('state', '=', 'open'),
            ('date_start', '<=', date_to),
            '|',
            ('date_end', '=', False),
            ('date_end', '>=', date_from),
        ])

        contract_employee_ids = set(contracts.mapped('employee_id').ids)
        return employees.filtered(lambda e: e.id in contract_employee_ids)


class HrAttendanceSummaryLine(models.TransientModel):
    """Lines for attendance summary report."""
    _name = 'hr.attendance.summary.line'
    _description = 'HR Attendance Summary Line'
    _order = 'attendance_percentage desc, employee_id'

    summary_id = fields.Many2one('hr.attendance.summary', string='Summary', required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    total_working_days = fields.Float(string='Total Working Days', digits=(10, 2))
    worked_days = fields.Float(string='Worked Days', digits=(10, 2))
    office_days = fields.Float(string='Office Days', digits=(10, 2))
    remote_days = fields.Float(string='Remote Days', digits=(10, 2))
    leave_days = fields.Float(string='Leave Days', digits=(10, 2))
    holiday_days = fields.Float(string='Holiday Days', digits=(10, 2))
    sick_days = fields.Float(string='Sick Days', digits=(10, 2))
    weekend_days = fields.Float(string='Weekend Days', digits=(10, 2))
    attendance_percentage = fields.Float(string='Attendance %', digits=(10, 2))
