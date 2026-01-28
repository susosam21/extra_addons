# Attendance Summary Widget Module

## Overview
This Odoo 17 module adds a comprehensive management summary widget for employee attendance tracking. The widget displays a detailed report showing worked days vs. total working days for each employee with dynamic date range filtering.

## Features

### 1. Enhanced Working Type Field
The attendance model now includes an extended `working_type` selection field with the following options:
- **full_day**: Full working day
- **half_day**: Half working day (counts as 0.5 worked days)
- **leave**: General leave
- **office**: Office work
- **remote**: Remote work
- **holiday**: Public holiday
- **sick**: Sick leave
- **annual_leave**: Annual leave
- **weekend**: Weekend/OFF day

### 2. Attendance Summary Model (`hr.attendance.summary`)
A transient model that computes comprehensive attendance statistics:
- Total working days (excluding weekends)
- Worked days (calculated based on working_type)
- Full days count
- Half days count
- Leave days count
- Office days count
- Remote days count
- Attendance percentage

### 3. Dynamic Date Range
- Filter by custom date ranges
- Default to current month
- Flexible month or date range selection

### 4. Dashboard Widget
A beautiful, interactive dashboard widget featuring:
- Real-time data filtering by date range
- Color-coded progress bars:
  - Green (≥90%): Excellent attendance
  - Yellow (70-89%): Good attendance
  - Red (<70%): Needs improvement
- Detailed statistics table with all metrics
- Summary statistics (total employees, average attendance)
- Responsive design with Bootstrap styling

### 5. Manager Access
- Dedicated menu items for attendance summary
- Full access for attendance managers
- User-level access for viewing own data

## Installation

1. Copy the module to your Odoo addons directory
2. Update the apps list in Odoo
3. Install the "Attendance And Time off Automation" module

## Usage

### Accessing the Attendance Summary

#### Option 1: Dashboard Widget
1. Navigate to **Attendances → Attendance Dashboard**
2. The widget displays automatically with current month data
3. Use the date filters to change the reporting period
4. Click "Refresh" to reload data

#### Option 2: Summary Report
1. Navigate to **Attendances → Reporting → Attendance Summary**
2. Select date range (From Date and To Date)
3. Optionally select specific employees
4. Click "Compute Summary" button
5. View detailed breakdown in the summary table

### Understanding the Data

- **Working Days**: Total business days (Monday-Friday) in the selected period
- **Worked Days**: Actual days worked (full_day = 1, half_day = 0.5)
- **Full Days**: Number of full working days
- **Half Days**: Number of half working days
- **Leave Days**: Days on leave (sick, annual, holiday)
- **Office Days**: Days worked from office
- **Remote Days**: Days worked remotely
- **Attendance %**: (Worked Days / Working Days) × 100

### Color Coding

The widget uses visual indicators:
- **Green**: ≥90% attendance (Excellent)
- **Yellow**: 70-89% attendance (Good)
- **Red**: <70% attendance (Needs Improvement)

## Technical Details

### Models
- `hr.attendance.summary`: Main transient model for summary computation
- `hr.attendance.summary.line`: Lines model for detailed employee data

### Views
- Form view with date filters and summary table
- Dashboard view with embedded widget
- Tree view with decorations and progress bars

### JavaScript Widget
- OWL Component: `AttendanceSummaryWidget`
- Located in: `static/src/components/`
- Features:
  - Reactive state management
  - Async data loading
  - Date change handlers
  - Dynamic styling

### API Methods
- `get_summary_data(date_from, date_to, employee_ids)`: Returns summary data for widget
- `action_compute_summary()`: Computes and displays summary report
- `_compute_employee_summary(employee)`: Calculates metrics for one employee
- `_calculate_working_days(date_from, date_to)`: Counts business days

## Best Practices

1. **Working Type Selection**: Always set the correct working_type when creating attendance records
2. **Half Days**: Use half_day working_type for partial attendance (counts as 0.5 days)
3. **Leave Integration**: The module automatically updates working_type based on approved leaves
4. **Regular Monitoring**: Review attendance summaries monthly for better workforce management
5. **Date Ranges**: Use specific date ranges for accurate reporting

## Configuration

### Security Groups
- `base.group_user`: Basic read/write access
- `hr_attendance.group_hr_attendance_manager`: Full administrative access

### Menu Items
- **Attendance Dashboard**: Main entry point with widget
- **Attendance Summary**: Detailed report generation

## Calculation Logic

### Worked Days Calculation
```python
# Full day or office/remote work = 1 day
if working_type in ('full_day', 'office', 'remote'):
    worked_days += 1

# Half day = 0.5 days
elif working_type == 'half_day':
    worked_days += 0.5

# Leave days = 0 days (not counted as worked)
elif working_type in ('leave', 'annual_leave', 'sick', 'holiday'):
    worked_days += 0
```

### Working Days Calculation
Only Monday to Friday are counted as working days. Weekends are automatically excluded.

## Dependencies
- `hr_attendance`: Odoo HR Attendance module
- `hr_contract`: Odoo HR Contract module
- `hr_holidays`: Odoo HR Leave module

## Compatibility
- Odoo Version: 17.0
- Python Version: 3.8+
- Browser: Modern browsers with ES6 support

## Support
For issues or feature requests, please contact your system administrator or module maintainer.

## License
LGPL-3

## Author
Your Company

---

**Note**: This module follows Odoo 17 best practices for models, views, and JavaScript widgets using the OWL framework.
