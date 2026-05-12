from __future__ import annotations

import shutil
from pathlib import Path

from pipeline_utils import DATA_DIR

STRUCTURE = {
    "01_extracted": [
        "routes.csv",
        "extraction_audit.csv",
        "pdf_coverage_report.csv",
    ],
    "02_event_logs": [
        "event_log.csv",
        "cda_transit_event_log.xes",
    ],
    "03_analytics": [
        "transition_events.csv",
        "transition_metrics.csv",
        "global_transition_metrics.csv",
        "trip_metrics.csv",
        "bottlenecks.csv",
        "process_graph.json",
    ],
    "04_map_data": [
        "stop_coordinates.csv",
        "stop_coordinate_audit.csv",
    ],
    "05_validation": [
        "xes_validation.json",
        "validation_summary.json",
    ],
}


def copy_if_exists(source: Path, destination: Path) -> None:
    if source.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def organize_data() -> dict:
    copied = []
    for folder, files in STRUCTURE.items():
        target_dir = DATA_DIR / folder
        target_dir.mkdir(exist_ok=True)
        for file_name in files:
            source = DATA_DIR / file_name
            destination = target_dir / file_name
            copy_if_exists(source, destination)
            if destination.exists():
                copied.append(str(destination.relative_to(DATA_DIR)))

    text_source = DATA_DIR / "pdf_text_extracts"
    text_target = DATA_DIR / "01_extracted" / "pdf_text_extracts"
    if text_source.exists():
        if text_target.exists():
            shutil.rmtree(text_target)
        shutil.copytree(text_source, text_target)
        copied.append(str(text_target.relative_to(DATA_DIR)))

    readme = DATA_DIR / "README.md"
    readme.write_text(
        """# Data Folder Layout

This folder keeps assignment-required compatibility files at the `data/` root while also providing an organized enterprise-style layout.

## Root Compatibility Files

The root copies are kept because the assignment explicitly asks for `data/routes.csv` and intermediate event log files, and the GUI/pipeline use these stable paths.

## Organized Copies

- `01_extracted/`: extracted `routes.csv`, PDF coverage, extraction audit, and extracted PDF text.
- `02_event_logs/`: merged process-mining event log CSV and XES file.
- `03_analytics/`: transition metrics, trip metrics, bottlenecks, and process graph JSON.
- `04_map_data/`: stop coordinate files for the real map and bonus route maps.
- `05_validation/`: validation summaries for XES and generated outputs.

## Submission Guidance

Must-have data files for grading:

- `routes.csv`
- `event_log.csv`
- `cda_transit_event_log.xes`
- `transition_metrics.csv`
- `trip_metrics.csv`
- `bottlenecks.csv`
- `pdf_coverage_report.csv`
- `xes_validation.json`
- `validation_summary.json`

Helpful but optional audit/intermediate files:

- `transition_events.csv`
- `global_transition_metrics.csv`
- `process_graph.json`
- `extraction_audit.csv`
- `pdf_text_extracts/`
- `stop_coordinates.csv`
- `stop_coordinate_audit.csv`
""",
        encoding="utf-8",
    )
    copied.append("README.md")
    return {"organized_items": len(copied), "folders": list(STRUCTURE)}


if __name__ == "__main__":
    print(organize_data())
