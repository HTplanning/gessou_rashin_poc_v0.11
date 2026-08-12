"""Flask Web application for 月相羅針 計算PoC v0.11｜全端末共通 生年月日・出生時間入力UI版."""

from __future__ import annotations

import os
from datetime import datetime

from flask import Flask, jsonify, render_template, request

from astronomy import (
    AstronomyError,
    calculate_birth_astronomy,
    calculate_birth_date_astronomy,
)
from location_master import resolve_location
from phase_classifier import classify_phase, classify_possible_phases


app = Flask(__name__)


UNKNOWN_TIME_SAMPLE_INTERVAL_MINUTES = 30
LOGIC_VERSION = "PoC標準月相8分類（45°区分）"
POC_VERSION = "v0.11"


def _validate_form(birth_date: str, birth_time: str, birth_place: str) -> list[str]:
    errors: list[str] = []

    if not birth_date:
        errors.append("生年月日を入力してください。")
    else:
        try:
            datetime.strptime(birth_date, "%Y-%m-%d")
        except ValueError:
            errors.append("生年月日の形式が正しくありません。")

    # Since PoC v0.2, birth time is optional. Validate only when supplied.
    if birth_time:
        try:
            datetime.strptime(birth_time, "%H:%M")
        except ValueError:
            errors.append("出生時間の形式が正しくありません。")

    if not birth_place.strip():
        errors.append("出生地を入力してください。")

    return errors


def _build_known_time_result(form: dict[str, str], location: dict[str, object]) -> dict:
    astronomy = calculate_birth_astronomy(
        birth_date=form["birth_date"],
        birth_time=form["birth_time"],
        timezone_name=str(location["timezone"]),
    )
    phase = classify_phase(float(astronomy["angle_difference"]))

    local_dt = astronomy["local_datetime"]
    utc_dt = astronomy["utc_datetime"]
    return {
        "birth_time_known": True,
        "classification_status": "exact",
        "birth_data": (
            f'{local_dt.strftime("%Y-%m-%d %H:%M:%S")} '
            f'{form["birth_place"]}'
        ),
        "birth_place": form["birth_place"],
        "timezone": location["timezone"],
        "utc_datetime": utc_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "julian_day": float(astronomy["julian_day"]),
        "sun_longitude": float(astronomy["sun_longitude"]),
        "moon_longitude": float(astronomy["moon_longitude"]),
        "angle_difference": float(astronomy["angle_difference"]),
        "phase_id": phase["id"],
        "phase_name": phase["name"],
        "phase_range": phase["rangeText"],
        "phase_english_name": phase["englishName"],
        "phase_description": phase["description"],
        "phase_note": phase["note"],
        "ephemeris_mode": astronomy["sun_ephemeris_mode"],
        "location_scope": location.get("scope"),
        "latitude": location.get("latitude"),
        "longitude": location.get("longitude"),
        "logic_version": LOGIC_VERSION,
        "poc_version": POC_VERSION,
    }


def _build_unknown_time_result(form: dict[str, str], location: dict[str, object]) -> dict:
    day_astronomy = calculate_birth_date_astronomy(
        birth_date=form["birth_date"],
        timezone_name=str(location["timezone"]),
        interval_minutes=UNKNOWN_TIME_SAMPLE_INTERVAL_MINUTES,
    )
    classification = classify_possible_phases(day_astronomy["angle_differences"])
    samples = day_astronomy["samples"]

    return {
        "birth_time_known": False,
        "classification_status": classification["classification_status"],
        "birth_date": form["birth_date"],
        "birth_place": form["birth_place"],
        "timezone": location["timezone"],
        "check_period": (
            f'{day_astronomy["start_local_datetime"].strftime("%Y-%m-%d %H:%M:%S")} ～ '
            f'{day_astronomy["end_local_datetime"].strftime("%H:%M:%S")}'
        ),
        "sample_interval_minutes": day_astronomy["interval_minutes"],
        "sample_count": classification["sample_count"],
        "start_angle_difference": classification["angle_path_start"],
        "end_angle_difference": classification["angle_path_end"],
        "possible_phases": classification["possible_phases"],
        "unknown_time_note": classification["unknown_time_note"],
        "ephemeris_mode": samples[0]["sun_ephemeris_mode"] if samples else "",
        "location_scope": location.get("scope"),
        "latitude": location.get("latitude"),
        "longitude": location.get("longitude"),
        "logic_version": LOGIC_VERSION,
        "poc_version": POC_VERSION,
    }


def _api_form_from_json(payload: object) -> dict[str, str]:
    """Normalize JSON input into the same three strings used by v0.6."""
    if not isinstance(payload, dict):
        payload = {}

    def clean(key: str) -> str:
        value = payload.get(key, "")
        return value.strip() if isinstance(value, str) else ""

    return {
        "birth_date": clean("birth_date"),
        "birth_time": clean("birth_time"),
        "birth_place": clean("birth_place"),
    }


def _calculate_result(form: dict[str, str]) -> dict:
    """Call the existing v0.6 calculation pipeline without changing its logic."""
    location = resolve_location(form["birth_place"])
    if form["birth_time"]:
        return _build_known_time_result(form, location)
    return _build_unknown_time_result(form, location)


@app.get("/")
def index():
    """Serve the lightweight Vue 3 screen. Calculation is handled by the API."""
    return render_template("index.html")


@app.post("/api/calculate")
def api_calculate():
    """Calculate 月相PoC values from JSON and return structured JSON."""
    form = _api_form_from_json(request.get_json(silent=True))
    errors = _validate_form(**form)
    if errors:
        return jsonify({"success": False, "errors": errors}), 400

    try:
        result = _calculate_result(form)
    except ValueError as exc:
        return jsonify({"success": False, "errors": [str(exc)]}), 400
    except AstronomyError:
        app.logger.exception("Astronomy calculation failed")
        return (
            jsonify(
                {
                    "success": False,
                    "errors": [
                        "天体計算に失敗しました。入力内容を確認して、もう一度お試しください。"
                    ],
                }
            ),
            500,
        )
    except Exception:
        # Do not expose Python internals to the browser.
        app.logger.exception("Unexpected calculation error")
        return (
            jsonify(
                {
                    "success": False,
                    "errors": ["計算中にエラーが発生しました。もう一度お試しください。"],
                }
            ),
            500,
        )

    return jsonify({"success": True, "result": result})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
