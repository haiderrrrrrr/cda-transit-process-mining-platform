from __future__ import annotations

from organize_data import organize_data
from pipeline_utils import DATA_DIR, ORGANIZED_PATHS

KEEP_ROOT_NAMES = {
    "cda_transit_route_pdf's",
    "01_extracted",
    "02_event_logs",
    "03_analytics",
    "04_map_data",
    "05_validation",
    "README.md",
}


def clean_data_root() -> dict:
    organize_data()
    removed = []
    for file_name, organized_file in ORGANIZED_PATHS.items():
        root_file = DATA_DIR / file_name
        if root_file.exists() and organized_file.exists():
            root_file.unlink()
            removed.append(file_name)

    old_text_dir = DATA_DIR / "pdf_text_extracts"
    organized_text_dir = DATA_DIR / "01_extracted" / "pdf_text_extracts"
    if old_text_dir.exists() and organized_text_dir.exists():
        for child in old_text_dir.iterdir():
            child.unlink()
        old_text_dir.rmdir()
        removed.append("pdf_text_extracts")

    leftover = sorted(item.name for item in DATA_DIR.iterdir() if item.name not in KEEP_ROOT_NAMES)
    return {"removed_root_items": removed, "leftover_review_items": leftover}


if __name__ == "__main__":
    print(clean_data_root())
