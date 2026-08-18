"""Production entrypoint with safe reporting/data visibility enhancements.

Keeps the existing application intact while adding a stable history view and
an all-data report endpoint. No database reset or destructive migration is
performed here.
"""
from datetime import datetime, timedelta
from flask import jsonify, render_template

from app import app, db, DailyEntry, build_report, valid_date


def _date_n_months_ago(year: int, month: int, months: int):
    index = year * 12 + (month - 1) - months
    return index // 12, index % 12 + 1


@app.get("/api/report/all")
def report_all():
    entries = DailyEntry.query.order_by(DailyEntry.date.asc(), DailyEntry.id.asc()).all()
    if not entries:
        return jsonify(build_report([], None, None))
    return jsonify(build_report(entries, entries[0].date, entries[-1].date))


@app.get("/api/data-health")
def data_health():
    entries = DailyEntry.query.order_by(DailyEntry.date.asc()).all()
    products = db.session.execute(db.select(__import__("app").Product)).scalars().all()
    return jsonify({
        "entries_count": len(entries),
        "products_count": len(products),
        "first_entry_date": entries[0].date if entries else None,
        "last_entry_date": entries[-1].date if entries else None,
        "database": app.config.get("SQLALCHEMY_DATABASE_URI", "").split("@")[-1],
    })


# Replace the old period page with a history-first page. Existing APIs and
# existing stored records remain untouched.
app.view_functions["periodic_report"] = lambda: render_template("history.html")


if __name__ == "__main__":
    app.run()
