"""Subprocess bridge for driving the existing SYNAPSE CLI from the frontend."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from knowledge.catalog_db import CPUS, GAMES, GPUS, MOTHERBOARDS


PROJECT_DIR = Path(__file__).resolve().parent
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


@dataclass
class FrontendRunResult:
    ok: bool
    mode: str
    precheck_passed: bool
    stage0: list[dict[str, str]]
    final_text: str
    raw_output: str
    error: str = ""


def _strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text).replace("\r\n", "\n")


def _require_catalog_value(value: str, catalog: dict[str, Any], label: str) -> str:
    if value not in catalog:
        raise ValueError(f"Invalid {label} selection.")
    return value


def _int_in_range(value: Any, label: str, lo: int, hi: int) -> int:
    try:
        parsed = int(str(value).strip())
    except ValueError as exc:
        raise ValueError(f"{label} must be an integer.") from exc
    if not lo <= parsed <= hi:
        raise ValueError(f"{label} must be between {lo} and {hi}.")
    return parsed


def _float_in_range(value: Any, label: str, lo: float, hi: float) -> float:
    try:
        parsed = float(str(value).strip())
    except ValueError as exc:
        raise ValueError(f"{label} must be numeric.") from exc
    if not lo <= parsed <= hi:
        raise ValueError(f"{label} must be between {lo:g} and {hi:g}.")
    return parsed


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    mode = payload.get("mode")
    if mode not in {"forward", "backward"}:
        raise ValueError("Choose either forward or backward chaining.")

    ram_gen = payload.get("ram_gen") or ""
    if ram_gen and ram_gen not in {"DDR3", "DDR4", "DDR5"}:
        raise ValueError("RAM generation must be DDR3, DDR4, or DDR5.")

    drive_type = payload.get("drive_type") or "SSD"
    if drive_type not in {"HDD", "SSD"}:
        raise ValueError("Drive type must be HDD or SSD.")

    game_title = ""
    if mode == "backward":
        game_id = payload.get("game_id")
        if game_id not in GAMES:
            raise ValueError("Select a valid game from the suggestions.")
        game_title = GAMES[game_id]["title_name"]

    return {
        "mode": mode,
        "cpu": _require_catalog_value(str(payload.get("cpu", "")), CPUS, "CPU"),
        "gpu": _require_catalog_value(str(payload.get("gpu", "")), GPUS, "GPU"),
        "motherboard": _require_catalog_value(str(payload.get("motherboard", "")), MOTHERBOARDS, "motherboard"),
        "ram_capacity": _int_in_range(payload.get("ram_capacity"), "RAM capacity", 4, 128),
        "ram_gen": ram_gen,
        "drive_type": drive_type,
        "storage_free": _float_in_range(payload.get("storage_free"), "Storage free space", 0.0, 10000.0),
        "psu_wattage": _int_in_range(payload.get("psu_wattage"), "PSU wattage", 200, 1600),
        "game_title": game_title,
    }


def build_cli_inputs(values: dict[str, Any]) -> list[str]:
    return [
        values["cpu"],
        values["gpu"],
        values["motherboard"],
        str(values["ram_capacity"]),
        values["ram_gen"],
        values["drive_type"],
        str(values["storage_free"]),
        str(values["psu_wattage"]),
        values["game_title"],
    ]


def run_cli_subprocess(values: dict[str, Any], timeout: int = 90) -> tuple[str, str, int]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    process = subprocess.Popen(
        [sys.executable, "-u", "main.py"],
        cwd=PROJECT_DIR,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )

    assert process.stdin is not None
    for value in build_cli_inputs(values):
        process.stdin.write(f"{value}\n")
        process.stdin.flush()
        time.sleep(0.03)
    process.stdin.close()
    process.stdin = None

    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        raise RuntimeError("The CLI process timed out before finishing.")
    return stdout, stderr, process.returncode


def _section(text: str, start_marker: str, end_markers: list[str]) -> str:
    start = text.find(start_marker)
    if start == -1:
        return ""
    end = len(text)
    for marker in end_markers:
        idx = text.find(marker, start + len(start_marker))
        if idx != -1:
            end = min(end, idx)
    return text[start:end].strip()


def parse_stage0(text: str) -> list[dict[str, str]]:
    stage = _section(text, "2. STAGE 0 PRE-CHECKS", ["3. FORWARD", "3. BACKWARD", "4. FINAL", "5. FINAL"])
    rows: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw_line in stage.splitlines():
        line = raw_line.strip()
        if line.startswith("Rule 0."):
            if current:
                rows.append(current)
            current = {"rule": line, "check": "", "status": "UNKNOWN", "explanation": ""}
        elif current and line.startswith("check"):
            current["check"] = line.split(":", 1)[1].strip()
        elif current and line.startswith("status"):
            current["status"] = "PASS" if "[PASS]" in line else "FAIL"
    if current:
        rows.append(current)

    explanations = {
        "Rule 0.1": "CPU socket and motherboard socket must match.",
        "Rule 0.2": "RAM generation must match what the motherboard supports.",
        "Rule 0.3": "Power supply must cover CPU, GPU, extra components, and a safety margin.",
        "Rule 0.4": "Storage must have usable free space.",
    }
    for row in rows:
        row["explanation"] = next((v for k, v in explanations.items() if row["rule"].startswith(k)), "")
    return rows


def _trim_final_for_frontend(final_section: str) -> str:
    for marker in ("System diagnostics",):
        idx = final_section.find(marker)
        if idx != -1:
            return final_section[idx:].strip()
    return final_section.strip()


def parse_frontend_output(mode: str, raw_output: str) -> tuple[bool, list[dict[str, str]], str]:
    clean = _strip_ansi(raw_output)
    stage0 = parse_stage0(clean)
    precheck_passed = bool(stage0) and all(row["status"] == "PASS" for row in stage0)
    if not precheck_passed:
        return (
            False,
            stage0,
            "Compatibility and bottleneck inference were not run because Stage 0 found physical hardware faults.",
        )

    if mode == "backward":
        final = _section(clean, "4. FINAL CONCLUSIONS", [])
    else:
        final = _section(clean, "5. FINAL CONCLUSIONS", [])
    return True, stage0, _trim_final_for_frontend(final)


def run_from_frontend(payload: dict[str, Any]) -> FrontendRunResult:
    try:
        values = validate_payload(payload)
        stdout, stderr, returncode = run_cli_subprocess(values)
        combined = stdout + (f"\n{stderr}" if stderr else "")
        precheck_passed, stage0, final_text = parse_frontend_output(values["mode"], combined)
        return FrontendRunResult(
            ok=returncode == 0,
            mode=values["mode"],
            precheck_passed=precheck_passed,
            stage0=stage0,
            final_text=final_text,
            raw_output=combined,
            error="" if returncode == 0 else stderr or "The CLI process exited with an error.",
        )
    except Exception as exc:
        return FrontendRunResult(
            ok=False,
            mode=str(payload.get("mode", "")),
            precheck_passed=False,
            stage0=[],
            final_text="",
            raw_output="",
            error=str(exc),
        )
