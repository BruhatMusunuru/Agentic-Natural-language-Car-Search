"""Out-of-core listings query engine over the FULL car-listing export.

Queries every daily snapshot in `data/*.parquet` (~22k qualifying rows
across 30 files) directly via DuckDB's vectorized SQL engine. The service
never loads the raw dataset into Python objects/memory -- DuckDB scans the
parquet files' columnar data and pushes every filter (including the
location/radius haversine check, joined against a zip-coordinate table) down
into the query itself. Only the handful of rows that actually match a
search are ever materialized into `Listing` objects.

This is the production listings backend (see search.py::search_listings,
orchestrator.py). The small curated fixture in inventory.py/
data/seed_listings.json remains checked in for fast, dependency-light
offline unit tests, but is no longer the source of truth for real search
traffic.
"""

from __future__ import annotations

import csv
import tempfile
from functools import lru_cache
from pathlib import Path

import duckdb
import zipcodes as _zipcodes

from car_search.locations import DEFAULT_RADIUS_MI, resolve_location
from car_search.models import FilterResult, Listing, SearchFilters

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_GLOB = str(REPO_ROOT / "data" / "*.parquet")

# Rows must have every field the service actually uses (see US-001's
# curation criteria, applied here across the whole dataset instead of one
# day): a real body type, fuel type, a genuine positive price band, and a
# seller zip. ~1,300 rows (5.8%) across the full dataset have
# kbbFairPriceHigh <= 0 with a clean gap before the next-lowest real price
# (~$1,680) -- 0 is a "missing price" sentinel in this export, not a real
# price, so those rows are excluded the same way "[PREMIUM]"/empty values
# are.
_QUALIFYING_WHERE = """
    bodyStyle IS NOT NULL AND bodyStyle != ''
    AND fuelType IS NOT NULL AND fuelType != ''
    AND kbbFairPriceLow IS NOT NULL
    AND kbbFairPriceHigh IS NOT NULL AND kbbFairPriceHigh > 0
    AND sellerZip IS NOT NULL AND sellerZip != ''
"""

_LISTING_COLUMNS = """
    listingId AS id, makeName AS make, modelName AS model, bodyStyle AS body_type,
    kbbFairPriceHigh AS price, mileage, year, fuelType AS fuel_type,
    sellerCity AS city, sellerState AS state, sellerZip AS zip
"""

_HAVERSINE_MI_SQL = """
    2 * 3958.8 * asin(sqrt(
        pow(sin(radians(zc.lat - {lat}) / 2), 2)
        + cos(radians({lat})) * cos(radians(zc.lat)) * pow(sin(radians(zc.lon - {lon}) / 2), 2)
    ))
"""


def _zip_coords_csv_path() -> Path:
    """A cached CSV dump of the `zipcodes` package's full bundled US zip
    dataset, so DuckDB can read_csv it directly (milliseconds) instead of
    row-by-row INSERTs (which take seconds for ~43k rows). Regenerated
    once per unique zipcodes package version, then reused."""
    cache_path = Path(tempfile.gettempdir()) / f"car_search_zip_coords_{_zipcodes.__version__}.csv"
    if cache_path.exists():
        return cache_path
    rows = (
        (z["zip_code"], z["lat"], z["long"])
        for z in _zipcodes.list_all()  # type: ignore[no-untyped-call]
        if z.get("lat") is not None and z.get("long") is not None
    )
    with cache_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["zip", "lat", "lon"])
        writer.writerows(rows)
    return cache_path


@lru_cache(maxsize=1)
def _connection() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(database=":memory:")
    # CREATE VIEW can't take prepared-statement parameters; the path comes
    # from our own cache function, not user input, so inlining it is safe.
    csv_path = str(_zip_coords_csv_path()).replace("'", "''")
    con.execute(f"CREATE VIEW zip_coords AS SELECT * FROM read_csv_auto('{csv_path}')")
    return con


def _make_predicate(field: str, filters: SearchFilters) -> tuple[str, list[object]] | None:
    """SQL fragment + params for one filter field, or None if unset."""
    if field == "make" and filters.make is not None:
        return "lower(makeName) = lower(?)", [filters.make]
    if field == "model" and filters.model is not None:
        return "lower(modelName) = lower(?)", [filters.model]
    if field == "body_type" and filters.body_type is not None:
        return "bodyStyle = ?", [filters.body_type.value]
    if field == "price_max" and filters.price_max is not None:
        return "kbbFairPriceHigh <= ?", [filters.price_max]
    if field == "mileage_max" and filters.mileage_max is not None:
        return "mileage <= ?", [filters.mileage_max]
    if field == "year_min" and filters.year_min is not None:
        return "year >= ?", [filters.year_min]
    if field == "fuel_type" and filters.fuel_type is not None:
        return "fuelType = ?", [filters.fuel_type.value]
    return None


def _radius_predicate(filters: SearchFilters) -> tuple[str, list[object]] | None:
    if filters.location is None:
        return None
    origin = resolve_location(filters.location)
    if origin is None:
        return None
    lat, lon = origin
    radius = filters.radius_mi if filters.radius_mi is not None else DEFAULT_RADIUS_MI
    distance_sql = _HAVERSINE_MI_SQL.format(lat="?", lon="?")
    # zc.lat IS NULL (listing's zip not resolvable) -> don't exclude it;
    # mirrors search.py::_passes_radius's fallback behavior.
    return f"(zc.lat IS NULL OR {distance_sql} <= ?)", [lat, lat, lon, radius]


def _rows_to_listings(rows: list[tuple[object, ...]], columns: list[str]) -> list[Listing]:
    return [Listing.model_validate(dict(zip(columns, row, strict=True))) for row in rows]


def search_full_dataset(filters: SearchFilters) -> FilterResult:
    """Query the full dataset (data/*.parquet) for listings matching filters.

    Mirrors search.py::filter_listings' semantics and FilterResult shape
    exactly, but every filter (including radius) is pushed down into SQL
    against DuckDB's vectorized parquet scan -- no in-memory Python list of
    the ~22k qualifying rows is ever built.
    """
    con = _connection()
    field_predicates = {
        field: _make_predicate(field, filters)
        for field in ("make", "model", "body_type", "price_max", "mileage_max", "year_min", "fuel_type")
    }
    radius_predicate = _radius_predicate(filters)

    base_from = f"read_parquet('{DATA_GLOB}') LEFT JOIN zip_coords zc ON zc.zip = sellerZip"

    excluded_by: dict[str, int] = {}
    for field, predicate in field_predicates.items():
        if predicate is None:
            excluded_by[field] = 0
            continue
        sql, params = predicate
        count = con.execute(
            f"SELECT count(*) FROM {base_from} WHERE {_QUALIFYING_WHERE} AND NOT ({sql})",
            params,
        ).fetchone()
        excluded_by[field] = count[0] if count else 0

    if radius_predicate is None:
        excluded_by["radius_mi"] = 0
    else:
        sql, params = radius_predicate
        count = con.execute(
            f"SELECT count(*) FROM {base_from} WHERE {_QUALIFYING_WHERE} AND NOT ({sql})",
            params,
        ).fetchone()
        excluded_by["radius_mi"] = count[0] if count else 0

    where_clauses = [_QUALIFYING_WHERE]
    all_params: list[object] = []
    for predicate in field_predicates.values():
        if predicate is not None:
            sql, params = predicate
            where_clauses.append(sql)
            all_params.extend(params)
    if radius_predicate is not None:
        sql, params = radius_predicate
        where_clauses.append(sql)
        all_params.extend(params)

    query = f"SELECT {_LISTING_COLUMNS} FROM {base_from} WHERE {' AND '.join(where_clauses)}"
    result = con.execute(query, all_params)
    columns = [desc[0] for desc in result.description]
    rows = result.fetchall()
    matches = _rows_to_listings(rows, columns)

    return FilterResult(matches=matches, excluded_by=excluded_by)


def dataset_row_count() -> int:
    """Total qualifying rows across the full dataset (for docs/diagnostics)."""
    con = _connection()
    row = con.execute(
        f"SELECT count(*) FROM read_parquet('{DATA_GLOB}') WHERE {_QUALIFYING_WHERE}"
    ).fetchone()
    return int(row[0]) if row else 0
