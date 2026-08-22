from flask import Blueprint, jsonify, session

from ..security import write_access
from ..services.periods import get_lock_status, set_lock
from ..utils import valid_month

bp = Blueprint("periods", __name__)


@bp.post("/api/periods/<string:year_month>/lock")
def lock_period(year_month):
    denied = write_access()
    if denied:
        return denied
    if not valid_month(year_month):
        return jsonify({"success": False, "error": "חודש לא תקין"}), 400
    set_lock(year_month, True, session.get("username", "מערכת"))
    return jsonify({"success": True, "year_month": year_month, "locked": True})


@bp.post("/api/periods/<string:year_month>/unlock")
def unlock_period(year_month):
    denied = write_access()
    if denied:
        return denied
    if not valid_month(year_month):
        return jsonify({"success": False, "error": "חודש לא תקין"}), 400
    set_lock(year_month, False, session.get("username", "מערכת"))
    return jsonify({"success": True, "year_month": year_month, "locked": False})


# --- Below: what the dashboard screen actually calls -----------------------
# BUG FIX: static/dashboard.html's refreshLock()/lockPeriod()/unlockPeriod()
# call GET/POST/DELETE on /api/period-locks/<year_month>. That route never
# existed on the backend (only /api/periods/<ym>/lock and .../unlock, both
# POST-only, did) so the dashboard's lock indicator and lock/unlock buttons
# always failed with a 404. Both route families now share the same service
# functions, so they can never disagree about a month's lock state.

@bp.get("/api/period-locks/<string:year_month>")
def get_period_lock(year_month):
    if not valid_month(year_month):
        return jsonify({"error": "חודש לא תקין"}), 400
    return jsonify({"year_month": year_month, "locked": get_lock_status(year_month)})


@bp.post("/api/period-locks/<string:year_month>")
def create_period_lock(year_month):
    denied = write_access()
    if denied:
        return denied
    if not valid_month(year_month):
        return jsonify({"success": False, "error": "חודש לא תקין"}), 400
    set_lock(year_month, True, session.get("username", "מערכת"))
    return jsonify({"success": True, "year_month": year_month, "locked": True})


@bp.route("/api/period-locks/<string:year_month>", methods=["DELETE"])
def delete_period_lock(year_month):
    denied = write_access()
    if denied:
        return denied
    if not valid_month(year_month):
        return jsonify({"success": False, "error": "חודש לא תקין"}), 400
    set_lock(year_month, False, session.get("username", "מערכת"))
    return jsonify({"success": True, "year_month": year_month, "locked": False})
