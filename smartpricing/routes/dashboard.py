from flask import Blueprint, jsonify, request

from ..services.reports import build_period_report, compare_periods, valid_range

bp = Blueprint("dashboard", __name__)


@bp.get("/api/dashboard/summary")
def dashboard_summary():
    start = str(request.args.get("from") or "").strip()
    end = str(request.args.get("to") or "").strip()
    if not valid_range(start, end):
        return jsonify({"error": "טווח תאריכים לא תקין"}), 400
    return jsonify(build_period_report(start, end))


@bp.get("/api/dashboard/compare")
def dashboard_compare():
    a_from = str(request.args.get("a_from") or "").strip()
    a_to = str(request.args.get("a_to") or "").strip()
    b_from = str(request.args.get("b_from") or "").strip()
    b_to = str(request.args.get("b_to") or "").strip()
    if not (valid_range(a_from, a_to) and valid_range(b_from, b_to)):
        return jsonify({"error": "טווח השוואה לא תקין"}), 400
    return jsonify(compare_periods(a_from, a_to, b_from, b_to))
