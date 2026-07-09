#!/usr/bin/env python3
"""
Local dashboard server for the Taiwan News Ticker.

Serves the generated index.html and keeps it fresh automatically:
  - a background thread re-runs the fetch/translate/render pipeline every
    15 minutes (fetch_news.REFRESH_INTERVAL_SECONDS), starting immediately
    on launch,
  - the page itself polls /api/status every minute and reloads only when
    new content has actually landed (not on a blind timer),
  - the "Refresh Now" button in the page calls /api/refresh to trigger an
    immediate run on demand.

Usage:
    python server.py
    PORT=9000 python server.py   # use a different port

Then open the printed URL (default http://localhost:8850).
"""
from __future__ import annotations

import logging
import os
import threading
import time

from flask import Flask, jsonify, send_from_directory

import fetch_news

log = logging.getLogger("server")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

PORT = int(os.environ.get("PORT", 8850))

app = Flask(__name__, static_folder=None)
_refresh_lock = threading.Lock()


@app.route("/")
def index():
    if not fetch_news.DEFAULT_OUTPUT.exists():
        return (
            "index.html not generated yet - the first background refresh is "
            "still running, reload in a moment.",
            503,
        )
    # The page is regenerated in place every refresh; without this, browsers
    # happily serve a stale cached copy (via a 304) after a reload, which
    # defeats both the "Refresh Now" button and the auto-refresh polling.
    response = send_from_directory(fetch_news.BASE_DIR, "index.html")
    response.headers["Cache-Control"] = "no-store, must-revalidate"
    return response


@app.route("/api/status")
def api_status():
    response = jsonify(fetch_news.get_status())
    response.headers["Cache-Control"] = "no-store, must-revalidate"
    return response


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    if not _refresh_lock.acquire(blocking=False):
        return jsonify({"status": "busy", "message": "A refresh is already running"}), 409
    try:
        result = fetch_news.run_pipeline()
    except Exception as exc:  # noqa: BLE001 - surface any pipeline failure to the button
        log.exception("On-demand refresh failed")
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        _refresh_lock.release()
    return jsonify({"status": "ok", **result})


def _scheduler_loop():
    """Runs a refresh immediately, then every REFRESH_INTERVAL_SECONDS."""
    while True:
        if _refresh_lock.acquire(blocking=False):
            try:
                log.info("Scheduled refresh starting...")
                result = fetch_news.run_pipeline()
                log.info("Scheduled refresh complete: %d articles", result["count"])
            except Exception:  # noqa: BLE001 - keep the loop alive across failures
                log.exception("Scheduled refresh failed")
            finally:
                _refresh_lock.release()
        else:
            log.info("Skipping scheduled refresh - a refresh is already in progress")
        time.sleep(fetch_news.REFRESH_INTERVAL_SECONDS)


if __name__ == "__main__":
    threading.Thread(target=_scheduler_loop, daemon=True).start()
    log.info("Starting Taiwan News Ticker on http://localhost:%d", PORT)
    log.info(
        "Background refresh runs every %d minutes automatically.",
        fetch_news.REFRESH_INTERVAL_SECONDS // 60,
    )
    app.run(host="0.0.0.0", port=PORT, threaded=True)
