from flask import Blueprint, jsonify, request

from ..services.reports import build_full_history_report, build_period_report, compare_periods, valid_range

bp = Blueprint("reports", __name__)


@bp.get("/api/report/period")
def get_period_report():
    start = str(request.args.get("from") or "").strip()
    end = str(request.args.get("to") or "").strip()
    if not valid_range(start, end):
        return jsonify({"error": "טווח תאריכים לא תקין"}), 400
    return jsonify(build_period_report(start, end))


@bp.get("/api/report/compare")
def compare_report():
    a_from = str(request.args.get("a_from") or "").strip()
    a_to = str(request.args.get("a_to") or "").strip()
    b_from = str(request.args.get("b_from") or "").strip()
    b_to = str(request.args.get("b_to") or "").strip()
    if not (valid_range(a_from, a_to) and valid_range(b_from, b_to)):
        return jsonify({"error": "טווח השוואה לא תקין"}), 400
    return jsonify(compare_periods(a_from, a_to, b_from, b_to))


@bp.get("/api/report/all")
def report_all():
    """Previously unreachable: the only implementation lived in wsgi_patched.py,
    which imported a function (build_report) that did not exist anywhere in the
    codebase, so that module could never be imported - and nothing loaded it
    anyway. The main screen's injected period panel and the (unused) history
    page both call this."""
    return jsonify(build_full_history_report())


@bp.get("/api/report/month/<string:year_month>")
def report_month(year_month):
    """Previously missing - templates/index.html's dashboard modal calls this
    to get the raw entry list for a month, and had no backend route to hit."""
    from ..models import DailyEntry
    from ..utils import entry_json, valid_month

    if not valid_month(year_month):
        return jsonify({"error": "חודש לא תקין"}), 400
    rows = (
        DailyEntry.query.filter(DailyEntry.date.like(f"{year_month}-%"))
        .order_by(DailyEntry.date.asc(), DailyEntry.id.asc())
        .all()
    )
    return jsonify([entry_json(row) for row in rows])
