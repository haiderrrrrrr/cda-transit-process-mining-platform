from __future__ import annotations

import json
import math
import re
import unicodedata
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
PDF_DIR = DATA_DIR / "cda_transit_route_pdf's"
REPORT_DIR = PROJECT_ROOT / "report"
FIGURES_DIR = REPORT_DIR / "figures"
TEXT_DIR = DATA_DIR / "pdf_text_extracts"
ORGANIZED_PATHS = {
    "routes.csv": DATA_DIR / "01_extracted" / "routes.csv",
    "extraction_audit.csv": DATA_DIR / "01_extracted" / "extraction_audit.csv",
    "pdf_coverage_report.csv": DATA_DIR / "01_extracted" / "pdf_coverage_report.csv",
    "event_log.csv": DATA_DIR / "02_event_logs" / "event_log.csv",
    "cda_transit_event_log.xes": DATA_DIR / "02_event_logs" / "cda_transit_event_log.xes",
    "transition_events.csv": DATA_DIR / "03_analytics" / "transition_events.csv",
    "transition_metrics.csv": DATA_DIR / "03_analytics" / "transition_metrics.csv",
    "global_transition_metrics.csv": DATA_DIR / "03_analytics" / "global_transition_metrics.csv",
    "trip_metrics.csv": DATA_DIR / "03_analytics" / "trip_metrics.csv",
    "bottlenecks.csv": DATA_DIR / "03_analytics" / "bottlenecks.csv",
    "process_graph.json": DATA_DIR / "03_analytics" / "process_graph.json",
    "stop_coordinates.csv": DATA_DIR / "04_map_data" / "stop_coordinates.csv",
    "stop_coordinate_audit.csv": DATA_DIR / "04_map_data" / "stop_coordinate_audit.csv",
    "member_home_coordinates.csv": DATA_DIR / "04_map_data" / "member_home_coordinates.csv",
    "xes_validation.json": DATA_DIR / "05_validation" / "xes_validation.json",
    "validation_summary.json": DATA_DIR / "05_validation" / "validation_summary.json",
}

PKT = timezone(timedelta(hours=5), name="PKT")
BASE_DATE = datetime(2026, 4, 23, tzinfo=PKT)
TIME_RE = re.compile(r"\b\d{2}:\d{2}:\d{2}\b")
TRIP_ID_RE = re.compile(r"^\d{3,}[-\w]*$")


def ensure_dirs() -> None:
    for directory in (DATA_DIR, REPORT_DIR, FIGURES_DIR, TEXT_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def normalize_stop(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value))
    value = re.sub(r"\s+", " ", value).strip()
    aliases = {
        "Nust Metro Station": "NUST Metro Station",
        "FAST": "FAST University",
    }
    return aliases.get(value, value)


def normalize_key(value: str) -> str:
    value = normalize_stop(value).lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def parse_time(value: str) -> time:
    return datetime.strptime(value, "%H:%M:%S").time()


def combine_date_time(value: str, day_offset: int = 0) -> datetime:
    parsed = parse_time(value)
    return datetime.combine(BASE_DATE.date(), parsed, tzinfo=PKT) + timedelta(days=day_offset)


def seconds_between(start: str, end: str) -> int:
    start_dt = combine_date_time(start)
    end_dt = combine_date_time(end)
    if end_dt < start_dt:
        end_dt += timedelta(days=1)
    return int((end_dt - start_dt).total_seconds())


def fmt_duration(seconds: float | int | None) -> str:
    if seconds is None or (isinstance(seconds, float) and math.isnan(seconds)):
        return "n/a"
    seconds = int(round(float(seconds)))
    mins, secs = divmod(seconds, 60)
    hours, mins = divmod(mins, 60)
    if hours:
        return f"{hours} hr {mins} min {secs} sec"
    return f"{mins} min {secs} sec"


def safe_json_dump(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def data_file(name: str) -> Path:
    root_path = DATA_DIR / name
    if root_path.exists():
        return root_path
    organized_path = ORGANIZED_PATHS.get(name)
    if organized_path and organized_path.exists():
        return organized_path
    return root_path


def route_id_from_pdf_name(path: Path) -> str:
    return path.stem.replace("_Forward", "")
