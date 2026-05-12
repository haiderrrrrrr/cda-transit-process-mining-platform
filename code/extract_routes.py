from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import fitz
import pandas as pd

from pipeline_utils import (
    PDF_DIR,
    TEXT_DIR,
    TIME_RE,
    TRIP_ID_RE,
    ensure_dirs,
    normalize_key,
    normalize_stop,
    route_id_from_pdf_name,
)


def grouped_lines(page: fitz.Page, y_tolerance: float = 3.0) -> list[dict]:
    words = sorted(page.get_text("words"), key=lambda w: (w[1], w[0]))
    groups: list[list[tuple]] = []
    for word in words:
        y = word[1]
        if not groups or abs(groups[-1][0][1] - y) > y_tolerance:
            groups.append([word])
        else:
            groups[-1].append(word)

    lines = []
    for group in groups:
        ordered = sorted(group, key=lambda w: w[0])
        text = " ".join(w[4] for w in ordered)
        lines.append(
            {
                "text": text,
                "words": ordered,
                "min_x": min(w[0] for w in ordered),
                "max_x": max(w[2] for w in ordered),
                "y": sum(w[1] for w in ordered) / len(ordered),
            }
        )
    return lines


def fix_compacted_stop_time(text: str) -> str:
    return re.sub(r"([A-Za-z)])(\d{2}:\d{2}:\d{2})", r"\1 \2", text)


def parse_metadata(lines: list[dict], fallback_route_id: str) -> dict:
    metadata = {
        "route_id": fallback_route_id,
        "route_numeric_id": "",
        "short_name": fallback_route_id,
        "long_name": "",
        "direction": "Forward",
        "total_trips_declared": None,
        "average_headway_min": None,
    }
    for line in lines[:30]:
        text = line["text"].strip()
        if match := re.match(r"Route ID\s+(.+)$", text):
            metadata["route_numeric_id"] = match.group(1).strip()
        elif match := re.match(r"Short Name\s+(.+)$", text):
            metadata["short_name"] = match.group(1).strip()
            metadata["route_id"] = match.group(1).strip()
        elif match := re.match(r"Long Name\s+(.+)$", text):
            metadata["long_name"] = match.group(1).strip()
        elif match := re.match(r"Direction\s+(.+)$", text):
            metadata["direction"] = match.group(1).strip()
        elif match := re.match(r"Total Trips\s+(\d+)$", text):
            metadata["total_trips_declared"] = int(match.group(1))
        elif match := re.match(r"Average Headway \(min\)\s+(\d+)$", text):
            metadata["average_headway_min"] = int(match.group(1))
    return metadata


def parse_pdf(path: Path) -> tuple[list[dict], dict, list[dict], str]:
    doc = fitz.open(path)
    fallback_route_id = route_id_from_pdf_name(path)
    rows: list[dict] = []
    audit: list[dict] = []
    all_text_pages: list[str] = []
    current_trip_id = ""
    current_start_time = ""
    stop_sequence = 0
    metadata: dict | None = None
    declared_trip_ids: set[str] = set()

    for page_index, page in enumerate(doc, start=1):
        page_text = page.get_text()
        all_text_pages.append(f"--- PAGE {page_index} ---\n{page_text}")
        lines = grouped_lines(page)
        if metadata is None:
            metadata = parse_metadata(lines, fallback_route_id)

        for line_number, line in enumerate(lines, start=1):
            text = fix_compacted_stop_time(line["text"]).strip()
            if not text:
                continue
            lower = text.lower()
            if lower in {
                "field value",
                "trip id start time",
                "stop_name arrival_time departure_time",
            }:
                continue
            if lower.startswith(("field ", "route id", "short name", "long name", "direction", "total trips", "average headway")):
                continue

            times = TIME_RE.findall(text)
            tokens = text.split()
            if len(times) == 1 and tokens and TRIP_ID_RE.match(tokens[0]) and tokens[0] != times[0]:
                current_trip_id = tokens[0]
                current_start_time = times[0]
                stop_sequence = 0
                declared_trip_ids.add(current_trip_id)
                continue

            if len(times) >= 2 and current_trip_id:
                arrival_time, departure_time = times[0], times[1]
                stop_part = text.split(arrival_time, 1)[0].strip()
                stop_part = re.sub(r"\s+", " ", stop_part)
                stop_name = normalize_stop(stop_part)
                if not stop_name or stop_name.lower() in {"stop_name", "arrival_time"}:
                    audit.append(
                        {
                            "source_pdf": path.name,
                            "page": page_index,
                            "line": line_number,
                            "issue": "empty_or_header_stop",
                            "raw_text": text,
                        }
                    )
                    continue
                stop_sequence += 1
                rows.append(
                    {
                        "route_id": metadata["route_id"],
                        "route_numeric_id": metadata["route_numeric_id"],
                        "short_name": metadata["short_name"],
                        "long_name": metadata["long_name"],
                        "direction": metadata["direction"],
                        "trip_id": current_trip_id,
                        "trip_start_time": current_start_time,
                        "stop_sequence": stop_sequence,
                        "stop_name": stop_name,
                        "stop_name_normalized": normalize_key(stop_name),
                        "arrival_time": arrival_time,
                        "departure_time": departure_time,
                        "source_pdf": path.name,
                        "source_page": page_index,
                        "source_line": line_number,
                        "source_text": text,
                        "extraction_confidence": "high",
                    }
                )

    metadata = metadata or parse_metadata([], fallback_route_id)
    metadata["pdf_pages"] = doc.page_count
    metadata["trips_extracted"] = len(declared_trip_ids)
    return rows, metadata, audit, "\n".join(all_text_pages)


def extract_all() -> dict:
    ensure_dirs()
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    all_rows: list[dict] = []
    audit_rows: list[dict] = []
    coverage_rows: list[dict] = []

    for pdf in pdfs:
        rows, metadata, audit, text = parse_pdf(pdf)
        (TEXT_DIR / f"{pdf.stem}.txt").write_text(text, encoding="utf-8")
        all_rows.extend(rows)
        audit_rows.extend(audit)
        unique_stops = len({row["stop_name_normalized"] for row in rows})
        extracted_trips = len({row["trip_id"] for row in rows})
        coverage_rows.append(
            {
                "source_pdf": pdf.name,
                "route_id": metadata["route_id"],
                "declared_total_trips": metadata["total_trips_declared"],
                "extracted_trips": extracted_trips,
                "rows_extracted": len(rows),
                "unique_stops": unique_stops,
                "pdf_pages": metadata["pdf_pages"],
                "status": "PASS" if rows and (metadata["total_trips_declared"] in (None, extracted_trips)) else "REVIEW",
            }
        )
        if not audit:
            audit_rows.append(
                {
                    "source_pdf": pdf.name,
                    "page": "",
                    "line": "",
                    "issue": "none",
                    "raw_text": "",
                    "status": "PASS",
                    "details": f"No extraction issues detected. Extracted {extracted_trips} trips and {len(rows)} stop events.",
                }
            )
        if not rows:
            audit_rows.append({"source_pdf": pdf.name, "page": "", "line": "", "issue": "no_rows_extracted", "raw_text": ""})

    routes = pd.DataFrame(all_rows)
    if not routes.empty:
        routes = routes.sort_values(["route_id", "trip_start_time", "trip_id", "stop_sequence"]).reset_index(drop=True)
    audit_df = pd.DataFrame(audit_rows)
    coverage_df = pd.DataFrame(coverage_rows)
    routes.to_csv(PDF_DIR.parent / "routes.csv", index=False)
    audit_df.to_csv(PDF_DIR.parent / "extraction_audit.csv", index=False)
    coverage_df.to_csv(PDF_DIR.parent / "pdf_coverage_report.csv", index=False)
    return {
        "pdfs_processed": len(pdfs),
        "rows": len(routes),
        "routes": int(routes["route_id"].nunique()) if not routes.empty else 0,
        "trips": int(routes["trip_id"].nunique()) if not routes.empty else 0,
        "audit_issues": len(audit_df),
    }


if __name__ == "__main__":
    print(extract_all())
