{
    'name': 'Attendance And Time off Automation',
    'version': '17.0.1.0.2',
    'category': 'Human Resources/Attendances',
    'summary': 'Automate attendance tracking with working types and weekend generation',
    'description': """
        Attendance And Time off Automation
        ===================================
        * Add working_type field to attendance records (Office, Remote, Holiday, Sick Leave, Annual Leave, Weekend)
        * Automatically create weekend attendance records based on employee work schedules
        * Automatically create attendance records for approved time off requests
        * Map leave types to appropriate working_type (Sick Leave, Annual Leave, Holiday)
        * Automatic leave allocation based on employee tenure:
          - First 11 months: 2 days/month (probation period)
          - At 1 year: Additional 8 days bonus (total 30 days)
          - After 1 year: 2.5 days/month
        * Prevent leave requests during probation period (first year)
        * Leave allocations valid for 1 year
        * Only processes active employees with valid contracts
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': [
        'hr_attendance',
        'hr_contract',
        'hr_holidays',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/delete_old_dashboard.xml',
        'views/hr_attendance_views.xml',
        'views/hr_contract_views.xml',
        'views/hr_attendance_summary_views.xml',
        'data/ir_cron_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'attendance_timeoff_automation/static/src/components/attendance_summary_widget.js',
            'attendance_timeoff_automation/static/src/components/attendance_summary_widget.xml',
            'attendance_timeoff_automation/static/src/components/attendance_summary_widget.css',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
