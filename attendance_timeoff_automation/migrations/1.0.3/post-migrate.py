# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Migration script to compute month field for existing attendance records
    """
    _logger.info("Starting migration to compute month field for existing attendance records")
    
    # Update month field for all existing attendance records
    cr.execute("""
        UPDATE hr_attendance
        SET month = TO_CHAR(attendance_date, 'YYYY-MM')
        WHERE attendance_date IS NOT NULL
        AND month IS NULL
    """)
    
    affected_rows = cr.rowcount
    _logger.info(f"Migration completed: Updated {affected_rows} attendance records with month field")
