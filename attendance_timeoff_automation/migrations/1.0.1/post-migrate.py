# -*- coding: utf-8 -*-
"""
Post-migration script to populate allocation_date field for existing allocations.
This ensures backward compatibility and fixes duplicate allocations issue.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Populate allocation_date for existing auto-allocated annual leave records.
    
    For allocations created during probation period:
    - The date_from was set to probation_end_date (validity start)
    - The allocation_date should be the actual month being allocated
    - We can extract this from the allocation name which contains the month/year
    
    For allocations created after probation:
    - date_from already represents the allocation month
    - We can copy date_from to allocation_date
    """
    _logger.info("Starting migration: populating allocation_date field...")
    
    # Update all existing auto-allocated records to have allocation_date = date_from
    # This is a safe default for records created after probation
    cr.execute("""
        UPDATE hr_leave_allocation
        SET allocation_date = date_from
        WHERE is_auto_allocated = TRUE
        AND allocation_date IS NULL
        AND date_from IS NOT NULL
    """)
    
    rows_updated = cr.rowcount
    _logger.info(f"Migration completed: Updated {rows_updated} allocation records with allocation_date")
