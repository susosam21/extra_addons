#!/usr/bin/env python3
"""
Test script to understand allocation logic for February 2026
Current date: February 2, 2026
"""

from datetime import date
from dateutil.relativedelta import relativedelta

# Simulate today's date
today = date(2026, 2, 2)
print(f"Today: {today}")
print(f"Today day of month: {today.day}")
print()

# Test scenarios
test_cases = [
    {"name": "Employee joined Jan 1, 2025", "joining_date": date(2025, 1, 1)},
    {"name": "Employee joined Jan 15, 2025", "joining_date": date(2025, 1, 15)},
    {"name": "Employee joined Feb 1, 2025", "joining_date": date(2025, 2, 1)},
    {"name": "Employee joined Feb 15, 2025", "joining_date": date(2025, 2, 15)},
    {"name": "Employee joined Dec 1, 2024", "joining_date": date(2024, 12, 1)},
]

for test in test_cases:
    joining_date = test["joining_date"]
    allocation_day = joining_date.day
    
    print(f"\n{'='*60}")
    print(f"{test['name']}")
    print(f"Joining date: {joining_date} (day {allocation_day})")
    print(f"{'='*60}")
    
    current_date = joining_date
    allocations = []
    
    while current_date <= today:
        # Adjust to the same day as joining date
        try:
            month_allocation_date = current_date.replace(day=allocation_day)
        except ValueError:
            # Handle case where day doesn't exist in month
            month_allocation_date = current_date + relativedelta(day=31)
        
        allocations.append(month_allocation_date)
        current_date = current_date + relativedelta(months=1)
    
    # Show last few allocations
    print(f"\nTotal allocations would be: {len(allocations)}")
    print(f"Last 3 allocation dates:")
    for alloc_date in allocations[-3:]:
        print(f"  - {alloc_date.strftime('%B %d, %Y')}")
    
    # Check specifically for February 2026
    feb_2026_allocations = [d for d in allocations if d.year == 2026 and d.month == 2]
    if feb_2026_allocations:
        print(f"\n✓ February 2026 allocation WILL BE CREATED on: {feb_2026_allocations[0]}")
    else:
        print(f"\n✗ February 2026 allocation WILL NOT BE CREATED")
        # Find next allocation
        future = [d for d in allocations if d > today]
        if not future:
            next_month = current_date
            try:
                next_allocation = next_month.replace(day=allocation_day)
            except ValueError:
                next_allocation = next_month + relativedelta(day=31)
            print(f"  Next allocation would be: {next_allocation.strftime('%B %d, %Y')}")
            print(f"  (Current loop stopped at {current_date})")

print("\n" + "="*60)
print("ANALYSIS:")
print("="*60)
print("""
The loop condition is: while current_date <= today
Where today = February 2, 2026

This means:
- If employee joined on day 1 or 2: February allocation WILL be created
- If employee joined on day 3-31: February allocation WILL NOT be created yet
  (because the allocation date would be Feb 3+ which is > Feb 2)

The issue is that the allocation for a month is only created when:
  month_allocation_date <= today

So if an employee joined on the 15th of any month, their February 2026 
allocation would only be created on or after February 15, 2026.
""")
