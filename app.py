"""Calm Cavanah Flask application.

This is the canonical entry point.  ``fullapp.py`` remains as a compatibility
wrapper for older launch commands.
"""

import base64
from collections import deque

import numpy as np
from flask import Flask, Response, jsonify, render_template, request

import siddur_store
import stats


app = Flask(__name__)

# Activity samples represent one two-second interval: 1 is active, 0 is idle.
speed_history = deque(maxlen=10)
checkin_history = deque(maxlen=50)
check_in_intervals = deque(maxlen=50)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/siddur_index/<nusach>")
def siddur_index(nusach):
    schema = siddur_store.get_schema(nusach)
    if schema:
        return jsonify({"schema": schema, "local": True})

    data = siddur_store.fetch_schema(nusach)
    if not data:
        return jsonify({"error": "Siddur catalog is not available."}), 503
    if data.get("schema"):
        siddur_store.save_schema(nusach, data["schema"])
    return jsonify({**data, "local": False})


@app.route("/get_prayer", methods=["POST"])
def get_prayer():
    data = request.get_json(silent=True) or {}
    path = data.get("path")
    if not isinstance(path, list) or not path or not all(isinstance(item, str) for item in path):
        return jsonify({"error": "path must be a non-empty list of strings.", "text": []}), 400

    book = path[0].replace("_", " ")
    full_ref = ", ".join([book, *path[1:]])
    speed_history.clear()

    text = siddur_store.get_text(full_ref)
    if not text:
        text = siddur_store.fetch_text(full_ref)
        if text:
            siddur_store.save_text(full_ref, text)

    return jsonify({"text": text or [], "error": not bool(text)})


@app.route("/stream_sample", methods=["POST"])
def stream_sample():
    data = request.get_json(silent=True) or {}
    active = data.get("active", 0)
    try:
        active = 1 if float(active) > 0 else 0
    except (TypeError, ValueError):
        return jsonify({"error": "active must be numeric."}), 400

    speed_history.append(active)
    recent = list(speed_history)[-3:]
    flatline = len(recent) == 3 and all(value == 0 for value in recent)
    average_scroll_speed = float(np.mean(list(speed_history))) if speed_history else 0.0
    anxiety = stats.anxiety_list

    return jsonify({
        "flatline_alert": flatline,
        "slow_scroll_alert": stats.warn_slow_scroll_speed(average_scroll_speed),
        "high_anxiety_alert": stats.warn_high_anxiety(anxiety),
        "high_change_alert": stats.warn_high_change(anxiety),
        "next_checkin_minutes": stats.calculate_next_anxiety_check(anxiety, average_scroll_speed),
        "average_scroll_speed": average_scroll_speed,
    })


@app.route("/submit_checkin", methods=["POST"])
def submit_checkin():
    data = request.get_json(silent=True) or {}
    try:
        score = int(data.get("anxiety_score", data.get("anxiety")))
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "anxiety_score must be an integer."}), 400
    if not 1 <= score <= 10:
        return jsonify({"status": "error", "message": "anxiety_score must be between 1 and 10."}), 400

    try:
        interval = float(data.get("interval_minutes", 5))
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "interval_minutes must be numeric."}), 400
    if interval < 0:
        return jsonify({"status": "error", "message": "interval_minutes cannot be negative."}), 400

    stats.anxiety_list.append(score)
    check_in_intervals.append(interval)
    checkin_history.append(data)
    average_scroll_speed = float(np.mean(list(speed_history))) if speed_history else 0.0
    response = {
        "status": "ok",
        "high_anxiety_alert": stats.warn_high_anxiety(stats.anxiety_list),
        "high_change_alert": stats.warn_high_change(stats.anxiety_list),
        "slow_scroll_alert": stats.warn_slow_scroll_speed(average_scroll_speed),
        "next_checkin_minutes": stats.calculate_next_anxiety_check(stats.anxiety_list, average_scroll_speed),
    }
    if len(stats.anxiety_list) >= 2:
        response["chart_png_base64"] = stats.build_anxiety_plot(stats.anxiety_list, check_in_intervals)
    return jsonify(response)


@app.route("/anxiety_chart")
def anxiety_chart():
    if len(stats.anxiety_list) < 2:
        return jsonify({"error": "Not enough data to plot yet."}), 400
    return Response(base64.b64decode(stats.build_anxiety_plot(stats.anxiety_list, check_in_intervals)), mimetype="image/png")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
