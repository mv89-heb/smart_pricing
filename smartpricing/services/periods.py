"""Period-lock read/write helpers.

Shared by /api/periods/<ym>/lock|unlock (the original endpoints, kept for
backward compatibility / existing tests) and /api/period-locks/<ym> (GET/POST/
DELETE - the endpoint the dashboard screen actually calls; see routes/periods.py
for the bug this fixes).
"""
from datetime import datetime

from ..extensions import db
from ..models import PeriodLock


def is_locked(date_or_month):
    return PeriodLock.query.filter_by(year_month=date_or_month[:7], locked=True).first() is not None


def get_lock_status(year_month):
    row = PeriodLock.query.filter_by(year_month=year_month).first()
    return bool(row and row.locked)


def set_lock(year_month, locked, username):
    row = PeriodLock.query.filter_by(year_month=year_month).first()
    if row is None:
        row = PeriodLock(year_month=year_month, locked=locked)
        db.session.add(row)
    if locked:
        row.locked = True
        row.locked_at = datetime.utcnow()
        row.locked_by = username
    else:
        row.locked = False
    db.session.commit()
    return row
