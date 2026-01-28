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

    date_from = fields.Date(string='From Date', required=True, default=lambda self: fields.Date.today().replace(day=1))
    date_to = fields.Date(string='To Date', required=True, default=lambda self: fields.Date.today())
    employee_ids = fields.Many2many('hr.employee', string='Employees', help='Leave empty to include all employees')
    line_ids = fields.One2many('hr.attendance.summary.line', 'summary_id', string='Summary Lines')

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
        # Calculate total working days (excluding weekends)
        total_working_days = self._calculate_working_days(self.date_from, self.date_to)
        
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
                leave_days += 1
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
        
        # Calculate attendance percentage
        attendance_percentage = (worked_days / total_working_days * 100) if total_working_days > 0 else 0
        
        return {
            'summary_id': self.id,
            'employee_id': employee.id,
            'total_working_days': total_working_days,
            'worked_days': worked_days,
            'office_days': office_days,
            'remote_days': remote_days,
            'leave_days': leave_days,
            'holiday_days': holiday_days,
            'sick_days': sick_days,
            'weekend_days': weekend_days,
            'attendance_percentage': attendance_percentage,
        }

    def _calculate_working_days(self, date_from, date_to):
        """
        Calculate the number of working days (excluding weekends) in the date range.
        """
        current_date = date_from
        working_days = 0
        
        while current_date <= date_to:
            # Check if it's a weekday (Monday=0 to Sunday=6)
            if current_date.weekday() < 5:  # Monday to Friday
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
