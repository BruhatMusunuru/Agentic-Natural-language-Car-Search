"""Curate a small, real, deterministic inventory fixture from data/2026-07-01.csv.

Run: python scripts/curate_seed_listings.py

This is a one-time/occasional curation tool, not something the service runs
at request time (see US-001). It looks up a hand-picked, hardcoded list of
real `listingId`s from the raw daily export CSV -- chosen to cover multiple
body types and fuel types, a wide price spread (~$1,700-$100k), a cluster of
listings within ~50 miles of Chicago, IL (for the US-004 flagship query),
and several listings clearly farther away in other states -- and writes them
to the checked-in fixture at src/car_search/data/seed_listings.json.

Every row is a real, unmodified record from the source export; nothing here
is fabricated.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_CSV = REPO_ROOT / "data" / "2026-07-01.csv"
OUT_PATH = REPO_ROOT / "src" / "car_search" / "data" / "seed_listings.json"

# Hand-picked listingIds from data/2026-07-01.csv. See module docstring for
# selection rationale. Comment on each line notes why it was picked.
CURATED_LISTING_IDS: list[str] = [
    # -- Chicago-metro (~50mi), low-mileage SUV under $30k: makes the
    # -- US-004 flagship query ("reliable family SUV under $30k, low
    # -- mileage, near Chicago") return real, sensible matches.
    "784374095",  # Evanston, IL 60201 -- 2025 Subaru Outback
    "784295593",  # Oak Lawn, IL 60453 -- 2024 Honda HR-V
    "784318216",  # Schaumburg, IL 60173 -- 2018 Audi Q5
    "784238606",  # Elmhurst, IL 60126 -- 2025 Nissan Kicks
    "783945978",  # Chicago, IL 60610 -- 2025 Honda HR-V
    "783664367",  # Naperville, IL 60540 -- 2023 GMC Terrain
    "779605194",  # Naperville, IL 60540 -- 2023 Volkswagen Taos
    "784230419",  # Aurora, IL 60504 -- 2023 Hyundai Tucson (flagship shape)
    # -- Chicago-metro variety: other body/fuel types, still in-radius.
    "782873210",  # Downers Grove, IL 60515 -- 2010 Honda Accord, SEDAN, high mileage
    "784331796",  # Zion, IL 60099 -- 2005 Toyota Prius, HATCH, Hybrid Gas/Electric
    "784158187",  # Barrington, IL 60010 -- 2025 Toyota 4Runner, SUV, Hybrid, high price
    "784158185",  # Barrington, IL 60010 -- 2017 Mercedes-Benz E 400, WAGON
    "784271680",  # Zion, IL 60099 -- 2005 Toyota Sienna, VANS
    "784282431",  # Rockford, IL 61107 -- 2010 Kia Soul, HATCH (~75mi, just outside 50mi radius)
    # -- Farther away (other states): price spread, body/fuel coverage,
    # -- radius-exclusion tests.
    "783509700",  # Cincinnati, OH 45251 -- 2024 Jeep Wagoneer, SUV
    "764559144",  # Louisville, KY 40218 -- 2025 Chrysler Pacifica, VANS
    "772792322",  # Willoughby, OH 44094 -- 2019 RAM 3500, TRUCKS, Diesel
    "776510941",  # Austin, TX 78617 -- 2010 Kia Soul, HATCH, low price
    "777642076",  # Ontario, CA 91762 -- 2005 Toyota Camry, SEDAN, low price
    "784261007",  # Delray Beach, FL 33483 -- 2022 Tesla Model X, SUV, Electric
    "784004192",  # Beverly Hills, CA 90211 -- 2024 Audi Q8 e-tron, SUV, Electric
    "784436750",  # Linden, NJ 07036 -- 2022 Porsche Taycan, SEDAN, Electric, highest price
    "780848294",  # Chanute, KS 66720 -- 2005 Ford Taurus, SEDAN, lowest price
    "783536623",  # Lewisville, TX 75067 -- 2006 Porsche 911, CONVERT
    "784455349",  # Lewisville, TX 75067 -- 2013 Nissan GT-R, COUPE
    "784442852",  # Rochester, MN 55906 -- 2003 Chevrolet Tahoe, SUV, Flexible Fuel
]


def load_rows_by_id() -> dict[str, dict[str, Any]]:
    with RAW_CSV.open(newline="", encoding="utf-8") as f:
        return {row["listingId"]: row for row in csv.DictReader(f)}


def to_listing(row: dict[str, Any]) -> dict[str, Any]:
    for field in ("bodyStyle", "fuelType", "kbbFairPriceLow", "kbbFairPriceHigh", "sellerZip"):
        value = row[field]
        if not value or value == "[PREMIUM]":
            raise ValueError(f"listingId {row['listingId']} has unusable {field!r}: {value!r}")
    return {
        "id": row["listingId"],
        "make": row["makeName"],
        "model": row["modelName"],
        "body_type": row["bodyStyle"],
        "price": round(float(row["kbbFairPriceHigh"])),
        "mileage": int(row["mileage"]),
        "year": int(row["year"]),
        "fuel_type": row["fuelType"],
        "city": row["sellerCity"],
        "state": row["sellerState"],
        "zip": row["sellerZip"],
    }


def main() -> None:
    rows_by_id = load_rows_by_id()
    curated: list[dict[str, Any]] = []
    for listing_id in CURATED_LISTING_IDS:
        row = rows_by_id.get(listing_id)
        if row is None:
            raise KeyError(f"listingId {listing_id} not found in {RAW_CSV}")
        curated.append(to_listing(row))

    curated.sort(key=lambda r: r["id"])
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(curated, indent=2) + "\n")
    print(f"Wrote {len(curated)} listings to {OUT_PATH}")


if __name__ == "__main__":
    main()
