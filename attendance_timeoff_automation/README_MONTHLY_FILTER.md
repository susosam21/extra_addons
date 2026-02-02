# Monthly Attendance Filtering Feature

## Overview
This feature adds comprehensive monthly filtering capabilities to the attendance module, allowing both employees and administrators to easily filter and view attendance records by month.

## Features Added

### 1. Month Field
- **New Field**: `month` - A computed field that stores the year-month in format "YYYY-MM" (e.g., "2026-02")
- **Type**: Stored computed field (automatically updated when attendance_date changes)
- **Visibility**: Displayed in the tree/list view for easy identification

### 2. Search and Filter Capabilities

#### Search Bar
- Users can search directly by typing month values (e.g., "2026-02", "2025-12")
- Combined search with employee name, working type, etc.

#### Quick Filters
- **This Month**: Automatically filters to show all attendance records for the current month
- **Last Month**: Shows all attendance records from the previous month
- Both filters are accessible from the filter dropdown in the attendance list view

#### Group By Options
- **Group by Month**: Organize attendance records grouped by month for better overview
- **Group by Working Type**: Group records by office/remote/holiday/sick leave/etc.
- Can be combined with employee grouping for detailed analysis

### 3. For Regular Employees
Employees can view their own attendance records and use:
- Month field in the list view to see which month each record belongs to
- "This Month" or "Last Month" filters to quickly view current/previous month's attendance
- Month search to find specific months
- Group by Month to see their attendance organized by month

### 4. For Administrators
Administrators with full access can:
- View all employees' attendance records
- Filter by month across all employees
- Combine employee filter with month filter (e.g., "Show John's attendance for January 2026")
- Use Group by Month + Employee to see a comprehensive overview
- Export filtered data for reporting

## Usage Examples

### Example 1: View Your Current Month Attendance
1. Go to Attendance menu
2. Click on "Filters"
3. Select "This Month"

### Example 2: View Specific Month for All Employees (Admin)
1. Go to Attendance menu
2. In search bar, type the month: "2026-01"
3. Click "Group By" → "Employee" to see breakdown by employee

### Example 3: View Specific Employee's Specific Month (Admin)
1. Go to Attendance menu
2. In search bar, type employee name
3. Then type month: "2026-02"
4. Results show only that employee's February 2026 attendance

### Example 4: Monthly Report by Working Type
1. Go to Attendance menu
2. Click "Filters" → "This Month" (or "Last Month")
3. Click "Group By" → "Working Type"
4. See breakdown of office/remote/leave days

## Technical Details

### Model Changes
- File: `models/hr_attendance.py`
- New field: `month` (Char, computed from `attendance_date`, stored)
- New compute method: `_compute_month()`

### View Changes
- File: `views/hr_attendance_views.xml`
- Added month field to tree view
- Created comprehensive search view with:
  - Month search field
  - "This Month" and "Last Month" filters
  - "Group by Month" and "Group by Working Type" options

### Migration
- File: `migrations/1.0.3/post-migrate.py`
- Automatically computes month field for all existing attendance records
- Runs automatically during module update

## Module Version
Updated from `17.0.1.0.2` to `17.0.1.0.3`

## Benefits
1. **Quick Access**: Instantly filter to current or previous month
2. **Better Organization**: Group and view attendance by month
3. **Flexible Reporting**: Combine filters for detailed analysis
4. **User-Friendly**: Intuitive filters accessible to all users
5. **Admin Control**: Powerful filtering across all employees
6. **Performance**: Stored computed field ensures fast filtering
