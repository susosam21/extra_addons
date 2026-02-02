# Fix: Duplicate Leave Allocation Bug & Missing Current Month Allocation

## Problem 1: Duplicate Leave Allocations

For contracts starting on or after January 1, 2024 (with probation period), the leave allocation system was creating duplicate allocations. 

### Example Scenario
- Contract start date: May 1, 2025
- Probation period: 6 months (ends November 1, 2025)
- Expected: Allocations for May, June, July 2025 (2 days each = 6 days)
- Bug behavior: System was re-creating these allocations multiple times

### Root Cause

When allocations were created during the probation period:
1. The `date_from` field was set to `probation_end_date` (e.g., November 1, 2025)
2. The `allocation_date` (actual month being allocated) was May, June, or July 2025
3. Duplicate detection logic used `date_from` to track allocated months
4. When cron ran again, it checked `allocated_months` based on `date_from` (November 2025)
5. It didn't find May, June, July in the set, so it allocated them again
6. This resulted in duplicates with the note "allocation for May, June, July 2025"

## Solution

Added a new field `allocation_date` to track the actual month being allocated, separate from the validity period:

### Changes Made

1. **New Field** ([hr_leave.py](attendance_timeoff_automation/models/hr_leave.py#L70-L73)):
   ```python
   allocation_date = fields.Date(
       string='Allocation Date',
       help='The actual date/month this allocation represents (used for duplicate detection)'
   )
   ```

2. **Updated Duplicate Detection** ([hr_leave.py](attendance_timeoff_automation/models/hr_leave.py#L223-L232)):
   - Now checks `allocation_date` instead of `date_from`
   - Falls back to `date_from` for backward compatibility with old records

3. **Store Allocation Month** ([hr_leave.py](attendance_timeoff_automation/models/hr_leave.py#L340)):
   - Saves `month_allocation_date` to `allocation_date` field
   - Keeps `date_from`/`date_to` for validity period

4. **Migration Script** ([migrations/1.0.1/post-migrate.py](attendance_timeoff_automation/migrations/1.0.1/post-migrate.py)):
   - Populates `allocation_date` for existing records
   - Sets `allocation_date = date_from` for existing allocations

### How It Works Now

```
Allocation for May 2025 (during probation):
- allocation_date: 2025-05-01 (used for duplicate detection)
- date_from: 2025-11-01 (validity starts after probation)
- date_to: 2026-11-01 (validity ends 1 year later)
```

When the cron runs again:
1. Reads existing allocations
2. Builds `allocated_months` set using `allocation_date` (2025-05-01)
3. Checks if 2025-05-01 is in the set → YES, skip this month
4. No duplicate allocations are created

## Problem 2: Missing Current Month Allocation

### Issue Description

Allocations for the current month were not being created if today's day of month was earlier than the employee's joining day.

### Example Scenario
- Employee joined: January 15, 2025 (joining day = 15th)
- Current date: February 2, 2026
- Expected: February 2026 allocation should exist (scheduled for Feb 15)
- Bug behavior: February 2026 allocation not created yet (waiting for Feb 15)

### Root Cause

The allocation loop processed months from contract start up to "today":
```python
while current_date <= today:  # today = Feb 2, 2026
    month_allocation_date = current_date.replace(day=allocation_day)  # Feb 15
    # Feb 15 > Feb 2, so loop stops before creating Feb allocation
```

This meant:
- Allocations were created only when `month_allocation_date <= today`
- If joining day (e.g., 15th) was after today's day (e.g., 2nd), the current month allocation wasn't created
- Users had to wait until their joining day in the month for the allocation to appear

### Solution

Changed the loop to process through the entire current month, not just up to today's day:

```python
# Process all months from start to current month (inclusive)
current_month_start = today.replace(day=1)
while current_date <= current_month_start:
```

Now the allocation is created for the full current month regardless of what day of the month it is today.

## Testing

To test the fixes:
1. Upgrade the module to version 1.0.2
2. Run the cron job manually: "Auto Allocate Annual Leaves"
3. Verify no duplicate allocations are created
4. Verify February 2026 (current month) allocations are created for all employees
5. Check employee's leave allocations show correct counts

## Upgrade Instructions

```bash
# In Odoo, upgrade the module
# Settings → Technical → Modules → Apps
# Search for "Attendance And Time off Automation"
# Click "Upgrade"

# Or via command line:
odoo-bin -u attendance_timeoff_automation -d your_database
```

**Note:** 
- Version 1.0.1 fixed the duplicate allocation bug
- Version 1.0.2 fixes the missing current month allocation bug
- The migration script from 1.0.1 automatically populates the `allocation_date` field for existing records
