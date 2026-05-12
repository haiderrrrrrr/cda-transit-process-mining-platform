from __future__ import annotations

from build_event_log import build_all
from clean_data_root import clean_data_root
from extract_routes import extract_all
from generate_coordinates import generate_coordinates
from generate_report_assets import generate_assets
from validate_outputs import validate_outputs


def main() -> None:
    print("1/6 Extracting route PDFs...")
    print(extract_all())
    print("2/6 Building event log, XES, graph, and analytics...")
    print(build_all())
    print("3/6 Generating map coordinate support...")
    print(generate_coordinates())
    print("4/6 Generating report figures and PDF draft...")
    print(generate_assets())
    print("5/6 Validating outputs...")
    print(validate_outputs())
    print("6/6 Organizing folders and cleaning data root...")
    print(clean_data_root())


if __name__ == "__main__":
    main()
