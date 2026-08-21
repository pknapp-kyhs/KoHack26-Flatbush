from flask import Flask, render_template, request, jsonify
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server use
import matplotlib.pyplot as plt
import base64
import stats
import siddur_store
from collections import deque

app = Flask(__name__)

# speed_history stores 1 for active, 0 for idle (2-second intervals)
speed_history = deque(maxlen=10)
checkin_history = deque(maxlen=50)

# Anxiety-specific state
check_in_intervals = []


# ---------------------------------------------------------------------------
# Sefaria helpers
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

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
    path = request.json.get('path', [])
    book = path[0].replace('_', ' ')
    segments = ", ".join(path[1:])
    full_ref = f"{book}, {segments}"

    # Reset scroll history for a fresh start on a new prayer
    speed_history.clear()

    txt = siddur_store.get_text(full_ref)

    # Bootstrap fallback for references not yet present in the local import.
    if not txt:
        txt = siddur_store.fetch_text(full_ref)
        if txt:
            siddur_store.save_text(full_ref, txt)

    return jsonify({"text": txt or "Liturgy not found.", "error": not txt})


@app.route("/stream_sample", methods=["POST"])
def stream_sample():
    """
    Receives a scroll-activity sample and evaluates both flatline (scroll) and
    anxiety-based warnings using the current scroll speed average.
    """
    is_active = request.json.get('active', 0)
    speed_history.append(is_active)

    # --- Scroll flatline alert (unchanged) ---
    flatline = False
    if len(speed_history) >= 3:
        if all(v == 0 for v in list(speed_history)[-3:]):
            flatline = True

    # --- Derive average scroll speed for anxiety helpers ---
    average_scroll_speed = float(np.mean(list(speed_history))) if speed_history else 0.0

    # --- Anxiety warnings (only meaningful once we have check-in data) ---
    slow_scroll = stats.warn_slow_scroll_speed(average_scroll_speed)
    high_anxiety = stats.warn_high_anxiety(stats.anxiety_list)
    high_change = stats.warn_high_change(stats.anxiety_list)

    # How long until the next check-in is suggested (minutes)
    next_check_in = stats.calculate_next_anxiety_check(stats.anxiety_list, average_scroll_speed)

    return jsonify({
        "flatline_alert": flatline,
        "slow_scroll_alert": slow_scroll,
        "high_anxiety_alert": high_anxiety,
        "high_change_alert": high_change,
        "next_checkin_minutes": next_check_in,
        "average_scroll_speed": average_scroll_speed,
    })


@app.route("/submit_checkin", methods=["POST"])
def submit_checkin():
    """
    Accepts a check-in payload, validates the anxiety score (1–10),
    appends it to the session history, and returns warning flags plus
    an updated chart image.
    """
    data = request.json or {}

    # Validate anxiety score
    try:
        score = int(data.get("anxiety_score", 0))
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "anxiety_score must be an integer."}), 400

    if not (1 <= score <= 10):
        return jsonify({
            "status": "error",
            "message": "anxiety_score must be between 1 and 10."
        }), 400

    # Record how many minutes elapsed since the last check-in
    interval = float(data.get("interval_minutes", 5))
    stats.anxiety_list.append(score)
    check_in_intervals.append(interval)
    checkin_history.append(data)

    print(f"Check-in received: {data}")

    # Derive current scroll speed from history
    average_scroll_speed = float(np.mean(list(speed_history))) if speed_history else 0.0

    # Build response with warning flags
    response = {
        "status": "ok",
        "high_anxiety_alert": stats.warn_high_anxiety(stats.anxiety_list),
        "high_change_alert": stats.warn_high_change(stats.anxiety_list),
        "slow_scroll_alert": stats.warn_slow_scroll_speed(average_scroll_speed),
        "next_checkin_minutes": stats.calculate_next_anxiety_check(stats.anxiety_list, average_scroll_speed),
    }

    # Attach a chart once we have enough data points
    if len(stats.anxiety_list) >= 2:
        response["chart_png_base64"] = stats.build_anxiety_plot(stats.anxiety_list, check_in_intervals)

    return jsonify(response)


@app.route("/anxiety_chart", methods=["GET"])
def anxiety_chart():
    """Standalone endpoint that returns the latest anxiety chart as a PNG image."""
    if len(stats.anxiety_list) < 2:
        return jsonify({"error": "Not enough data to plot yet."}), 400

    png_b64 = stats.build_anxiety_plot(stats.anxiety_list, check_in_intervals)
    img_bytes = base64.b64decode(png_b64)
    from flask import Response
    return Response(img_bytes, mimetype='image/png')


if __name__ == "__main__":
    app.run(debug=True, port=5001)
