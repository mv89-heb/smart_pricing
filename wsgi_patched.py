"""Production entrypoint with safe reporting/data visibility enhancements.

Keeps the existing application intact while adding a stable history view and
an all-data report endpoint. No database reset or destructive migration is
performed here.
"""
from flask import jsonify, render_template, make_response

from app import app, db, DailyEntry, Product, build_report


@app.get("/api/report/all")
def report_all():
    """Return the complete stored billing history without modifying anything."""
    entries = DailyEntry.query.order_by(DailyEntry.date.asc(), DailyEntry.id.asc()).all()
    if not entries:
        return jsonify(build_report([], None, None))
    return jsonify(build_report(entries, entries[0].date, entries[-1].date))


@app.get("/api/data-health")
def data_health():
    """Show whether the currently connected database still contains the data."""
    entries_count = db.session.query(DailyEntry.id).count()
    products_count = db.session.query(Product.id).count()
    first_entry = DailyEntry.query.order_by(DailyEntry.date.asc(), DailyEntry.id.asc()).first()
    last_entry = DailyEntry.query.order_by(DailyEntry.date.desc(), DailyEntry.id.desc()).first()
    return jsonify({
        "entries_count": entries_count,
        "products_count": products_count,
        "first_entry_date": first_entry.date if first_entry else None,
        "last_entry_date": last_entry.date if last_entry else None,
        "data_present": entries_count > 0 or products_count > 0,
    })


# Replace the old period page with a history-first page. Existing APIs and
# existing stored records remain untouched.
app.view_functions["periodic_report"] = lambda: render_template("history.html")

# Keep the existing daily screen, but make the full-history workspace obvious.
_original_index = app.view_functions.get("index")
if _original_index:
    def _index_with_history_link():
        response = _original_index()
        response = make_response(response)
        html = response.get_data(as_text=True)
        banner = '''<a href="/periodic-report" style="position:fixed;bottom:18px;left:18px;z-index:9999;background:#4f46e5;color:#fff;padding:11px 16px;border-radius:12px;font-weight:800;text-decoration:none;box-shadow:0 8px 24px rgba(15,23,42,.2)">📊 היסטוריה — 3 חודשים אחרונים</a>'''
        if "היסטוריה — 3 חודשים אחרונים" not in html and "</body>" in html:
            html = html.replace("</body>", banner + "</body>")
            response.set_data(html)
        return response
    app.view_functions["index"] = _index_with_history_link


if __name__ == "__main__":
    app.run()
