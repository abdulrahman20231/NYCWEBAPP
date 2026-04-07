from __future__ import annotations

import csv
from pathlib import Path


FIELD_ORDER = [
    "id",
    "title",
    "description",
    "borough",
    "neighborhood",
    "address",
    "price",
    "beds",
    "baths",
    "sqft",
    "property_type",
    "available_from",
    "lease_term",
    "image_url",
    "listing_url",
    "latitude",
    "longitude",
    "pet_friendly",
    "furnished",
    "has_doorman",
    "has_laundry",
    "near_subway",
    "allows_guarantors",
    "featured",
]


class CsvExportPipeline:
    def open_spider(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        output_path = project_root / "data" / "scraped_listings.csv"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_handle = output_path.open("w", newline="", encoding="utf-8")
        self.writer = csv.DictWriter(self.file_handle, fieldnames=FIELD_ORDER)
        self.writer.writeheader()

    def close_spider(self) -> None:
        self.file_handle.close()

    def process_item(self, item):
        row = {field: item.get(field, "") for field in FIELD_ORDER}
        self.writer.writerow(row)
        return item
