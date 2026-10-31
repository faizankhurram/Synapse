"""Flask frontend for SYNAPSE.

This file adds a browser UI around the existing CLI. It does not replace the
CLI: frontend submissions are sent to main.py through a subprocess.
"""

from __future__ import annotations

from dataclasses import asdict

from flask import Flask, jsonify, render_template, request

from frontend_bridge import run_from_frontend
from knowledge.catalog_db import CPUS, GAMES, GPUS, MOTHERBOARDS


app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/catalog")
def catalog():
    games = [
        {
            "id": game_id,
            "title": data["title_name"],
            "icon": "".join(part[0] for part in data["title_name"].replace("/", " ").split()[:3]).upper(),
        }
        for game_id, data in GAMES.items()
    ]
    return jsonify(
        {
            "cpus": list(CPUS.keys()),
            "gpus": list(GPUS.keys()),
            "motherboards": list(MOTHERBOARDS.keys()),
            "games": games,
        }
    )


@app.post("/api/run")
def run():
    result = run_from_frontend(request.get_json(silent=True) or {})
    status = 200 if result.ok or result.stage0 else 400
    return jsonify(asdict(result)), status


if __name__ == "__main__":
    app.run(debug=True)
