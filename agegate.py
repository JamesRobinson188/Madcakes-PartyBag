# agegate.py
from flask import Blueprint, request, session, jsonify
import datetime as dt

agebp = Blueprint("agegate", __name__, url_prefix="/age")

def _age_from_ddmmyyyy(s: str):
    try:
        d, m, y = s.strip().split("/")
        dob = dt.date(int(y), int(m), int(d))
    except Exception:
        return None
    today = dt.date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

@agebp.post("/verify")
def verify():
    data = request.get_json(silent=True) or request.form
    dob = (data.get("dob") or "").strip()
    age = _age_from_ddmmyyyy(dob)
    if age is None:
        return jsonify({"ok": False, "error": "invalid_format"}), 400
    if age < 18:
        return jsonify({"ok": False, "error": "underage"}), 403
    session["adult_verified"] = True
    return jsonify({"ok": True})
