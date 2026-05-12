from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

from pipeline_utils import ORGANIZED_PATHS, PDF_DIR, data_file, safe_json_dump


def validate_outputs() -> dict:
    required = [
        "routes.csv",
        "event_log.csv",
        "cda_transit_event_log.xes",
        "transition_metrics.csv",
        "trip_metrics.csv",
        "process_graph.json",
        "pdf_coverage_report.csv",
        "xes_validation.json",
    ]
    missing = [name for name in required if not data_file(name).exists()]
    routes = pd.read_csv(data_file("routes.csv"))
    coverage = pd.read_csv(data_file("pdf_coverage_report.csv"))
    trips = pd.read_csv(data_file("trip_metrics.csv"))
    transitions = pd.read_csv(data_file("transition_metrics.csv"))
    xes_path = data_file("cda_transit_event_log.xes")
    root = ET.parse(xes_path).getroot()
    xes_version = root.attrib.get("xes.version")
    source_pdf_count = len(list(PDF_DIR.glob("*.pdf")))
    pdf_count = source_pdf_count or len(coverage)
    checks = {
        "missing_files": missing,
        "pdf_count": pdf_count,
        "source_pdf_files_present": source_pdf_count > 0,
        "coverage_rows": len(coverage),
        "all_pdfs_covered": len(coverage) == pdf_count,
        "coverage_all_pass": bool((coverage["status"] == "PASS").all()),
        "route_count": int(routes["route_id"].nunique()),
        "event_rows": int(len(routes)),
        "trip_count": int(trips["case_id"].nunique()),
        "transition_edge_count": int(len(transitions)),
        "no_negative_trip_durations": bool((trips["duration_seconds"] >= 0).all()),
        "no_negative_transition_durations": bool((transitions["avg_duration_seconds"] >= 0).all()),
        "xes_version": xes_version,
        "xes_version_is_1_0": xes_version == "1.0",
    }
    checks["passed"] = (
        not checks["missing_files"]
        and checks["all_pdfs_covered"]
        and checks["coverage_all_pass"]
        and checks["no_negative_trip_durations"]
        and checks["no_negative_transition_durations"]
        and checks["xes_version_is_1_0"]
    )
    safe_json_dump(ORGANIZED_PATHS["validation_summary.json"], checks)
    return checks


if __name__ == "__main__":
    print(json.dumps(validate_outputs(), indent=2))
