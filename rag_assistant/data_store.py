"""Loads the AutoTrader listings parquet files into an in-memory DuckDB table
and exposes filtered search / lookup / aggregate helpers that the agent's
tools call into.

This is the "retrieval" half of the RAG pipeline: every answer the assistant
gives is grounded in rows returned from here, never invented.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import duckdb

from . import config

# Columns that are masked with the literal string "[PREMIUM]" in this sample
# export (100% of rows). They carry no real information here, so we null
# them out on load rather than let the model see/quote a fake placeholder.
_PREMIUM_COLUMNS = [
    "vin",
    "salePrice",
    "kbbFairPurchasePrice",
    "sellerName",
    "sellerPhone",
    "sellerRating",
    "sellerWebsite",
    "images",
    "listingUrl",
]

# Fields concatenated (lower-cased) into a single blob for keyword search.
_SEARCH_TEXT_COLUMNS = [
    "listingTitle",
    "trim",
    "bodyStyle",
    "engine",
    "drivetrain",
    "transmission",
    "fuelType",
    "exteriorColor",
    "interiorColor",
    "description",
    "options",
    "sellerCity",
    "sellerState",
]

_DEAL_RANK_SQL = """
    CASE dealIndicator
        WHEN 'Great' THEN 0
        WHEN 'Good' THEN 1
        WHEN 'Fair' THEN 2
        WHEN 'High' THEN 3
        WHEN 'Overpriced' THEN 4
        ELSE 5
    END
"""

# Fields returned to the model for each listing in search results. Kept
# compact so several results fit comfortably in the tool-result context.
SUMMARY_FIELDS = [
    "listingId",
    "year",
    "makeName",
    "modelName",
    "trim",
    "bodyStyle",
    "listingType",
    "mileage",
    "estPriceLow",
    "estPriceHigh",
    "dealIndicator",
    "drivetrain",
    "transmission",
    "fuelType",
    "mpgCity",
    "mpgHighway",
    "exteriorColor",
    "hasLeatherSeats",
    "daysOnMarket",
    "isHot",
    "isNewlyListed",
    "isReducedPrice",
    "sellerCity",
    "sellerState",
    "isPrivateSeller",
    "kbbConsumerRatings",
    "safetyRecallCount",
]

_lock = threading.Lock()
_connection: duckdb.DuckDBPyConnection | None = None
_row_count: int = 0


def get_connection() -> duckdb.DuckDBPyConnection:
    """Return a DuckDB connection (a fresh cursor onto the process-wide,
    lazily-built database).

    A single ``DuckDBPyConnection`` is not safe to share across concurrent
    ``execute()``/``fetch*()`` calls from multiple threads - and FastAPI runs
    sync endpoints in a thread pool, so concurrent requests are the normal
    case here, not an edge case. Handing each caller its own ``cursor()``
    (cheap - it shares the same in-memory database) avoids that without
    serializing all queries behind a lock.
    """
    global _connection, _row_count
    with _lock:
        if _connection is None:
            _connection, _row_count = _build_connection(config.DATA_DIR)
        return _connection.cursor()


def row_count() -> int:
    """Number of distinct listings loaded (forces the DB to build if needed)."""
    get_connection()
    return _row_count


def dataset_summary() -> dict[str, Any]:
    """High-level facts about the loaded dataset (size, date coverage) for
    grounding the system prompt - so the assistant can truthfully answer
    "how much/how current is your data" without guessing or calling a tool.
    """
    con = get_connection()
    first_seen, last_seen = con.execute(
        "SELECT MIN(_firstSeenAt), MAX(_lastSeenAt) FROM listings"
    ).fetchone()
    return {
        "listing_count": row_count(),
        "first_seen": first_seen.date().isoformat() if first_seen else None,
        "last_seen": last_seen.date().isoformat() if last_seen else None,
    }


def _build_connection(data_dir: Path) -> tuple[duckdb.DuckDBPyConnection, int]:
    glob_path = str(Path(data_dir) / "*.parquet")
    matches = list(Path(data_dir).glob("*.parquet"))
    if not matches:
        raise FileNotFoundError(
            f"No listing parquet files found under {data_dir}. "
            "Set LISTINGS_DATA_DIR to point at the AutoTrader data/data directory."
        )

    con = duckdb.connect(database=":memory:")

    # Dedupe: a listing can appear in multiple daily exports; keep the most
    # recently seen snapshot of each one.
    con.execute(
        f"""
        CREATE OR REPLACE TABLE listings AS
        SELECT * EXCLUDE (rn) FROM (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY listingId ORDER BY _lastSeenAt DESC
            ) AS rn
            FROM read_parquet('{glob_path}', union_by_name=true)
        )
        WHERE rn = 1
        """
    )

    for col in _PREMIUM_COLUMNS:
        con.execute(f'UPDATE listings SET "{col}" = NULL WHERE "{col}" = \'[PREMIUM]\'')

    # Estimated price band: prefer the KBB fair-purchase-price range; fall
    # back to MSRP (new vehicles only) when KBB data is missing. There is no
    # real asking price in this sample export (salePrice is premium-masked).
    con.execute(
        """
        ALTER TABLE listings ADD COLUMN estPriceLow DOUBLE;
        ALTER TABLE listings ADD COLUMN estPriceHigh DOUBLE;
        ALTER TABLE listings ADD COLUMN estPriceMid DOUBLE;
        ALTER TABLE listings ADD COLUMN searchBlob VARCHAR;
        """
    )
    con.execute(
        """
        UPDATE listings SET
            estPriceLow = COALESCE(kbbFairPriceLow, msrp),
            estPriceHigh = COALESCE(kbbFairPriceHigh, msrp)
        """
    )
    con.execute(
        """
        UPDATE listings SET
            estPriceMid = CASE
                WHEN estPriceLow IS NOT NULL AND estPriceHigh IS NOT NULL
                    THEN (estPriceLow + estPriceHigh) / 2.0
                ELSE COALESCE(estPriceLow, estPriceHigh)
            END
        """
    )
    text_concat = " || ' ' || ".join(f"COALESCE(\"{c}\", '')" for c in _SEARCH_TEXT_COLUMNS)
    con.execute(f"UPDATE listings SET searchBlob = LOWER({text_concat})")

    total = con.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    return con, int(total)


def _row_to_dict(columns: list[str], row: tuple[Any, ...]) -> dict[str, Any]:
    return dict(zip(columns, row))


def search_listings(
    *,
    make: str | None = None,
    model: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    max_mileage: int | None = None,
    body_style: str | None = None,
    fuel_type: str | None = None,
    drivetrain: str | None = None,
    transmission: str | None = None,
    listing_type: str | None = None,
    deal_indicator: str | None = None,
    city: str | None = None,
    state: str | None = None,
    min_mpg_highway: int | None = None,
    only_hot: bool | None = None,
    keywords: str | None = None,
    limit: int = config.DEFAULT_SEARCH_LIMIT,
) -> list[dict[str, Any]]:
    """Filter + rank listings and return compact summaries.

    All filters are optional and combined with AND. ``keywords`` does a
    case-insensitive substring match against title/description/options/etc.
    (every whitespace-separated token must appear somewhere in the blob).
    """
    con = get_connection()
    clauses: list[str] = []
    params: list[Any] = []

    def add(clause: str, *values: Any) -> None:
        clauses.append(clause)
        params.extend(values)

    if make:
        add("(makeName ILIKE ? OR makeCode ILIKE ?)", f"%{make}%", f"%{make}%")
    if model:
        add("(modelName ILIKE ? OR modelCode ILIKE ?)", f"%{model}%", f"%{model}%")
    if year_min is not None:
        add("year >= ?", year_min)
    if year_max is not None:
        add("year <= ?", year_max)
    if price_min is not None:
        add("(estPriceHigh IS NULL OR estPriceHigh >= ?)", price_min)
    if price_max is not None:
        add("(estPriceLow IS NULL OR estPriceLow <= ?)", price_max)
    if max_mileage is not None:
        add("mileage <= ?", max_mileage)
    if body_style:
        add("bodyStyle ILIKE ?", f"%{body_style}%")
    if fuel_type:
        add("(fuelType ILIKE ? OR fuelTypeGroup ILIKE ?)", f"%{fuel_type}%", f"%{fuel_type}%")
    if drivetrain:
        add("drivetrain ILIKE ?", f"%{drivetrain}%")
    if transmission:
        add("(transmission ILIKE ? OR transmissionGroup ILIKE ?)", f"%{transmission}%", f"%{transmission}%")
    if listing_type:
        add("listingType ILIKE ?", f"%{listing_type}%")
    if deal_indicator:
        add("dealIndicator ILIKE ?", f"%{deal_indicator}%")
    if city:
        add("sellerCity ILIKE ?", f"%{city}%")
    if state:
        add("(sellerState ILIKE ? OR sellerState = ?)", f"%{state}%", state.upper())
    if min_mpg_highway is not None:
        add("mpgHighway >= ?", min_mpg_highway)
    if only_hot:
        add("isHot = TRUE")
    if keywords:
        for token in keywords.lower().split():
            add("searchBlob LIKE ?", f"%{token}%")

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    limit = max(1, min(int(limit), config.MAX_SEARCH_LIMIT))
    columns_sql = ", ".join(f'"{c}"' for c in SUMMARY_FIELDS)

    sql = f"""
        SELECT {columns_sql}
        FROM listings
        {where_sql}
        ORDER BY isHot DESC, {_DEAL_RANK_SQL} ASC, daysOnMarket ASC NULLS LAST
        LIMIT ?
    """
    params.append(limit)

    result = con.execute(sql, params)
    columns = [d[0] for d in result.description]
    rows = result.fetchall()

    total_matches = con.execute(f"SELECT COUNT(*) FROM listings {where_sql}", params[:-1]).fetchone()[0]

    return {
        "total_matches": int(total_matches),
        "returned": len(rows),
        "listings": [_row_to_dict(columns, row) for row in rows],
    }


def get_listing(listing_id: str) -> dict[str, Any] | None:
    """Full detail for one listing by its listingId."""
    con = get_connection()
    result = con.execute(
        "SELECT * FROM listings WHERE CAST(listingId AS VARCHAR) = ?",
        [str(listing_id)],
    )
    columns = [d[0] for d in result.description]
    row = result.fetchone()
    if row is None:
        return None
    record = _row_to_dict(columns, row)
    record.pop("searchBlob", None)
    return record


def market_stats(
    *,
    make: str | None = None,
    model: str | None = None,
    body_style: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
) -> dict[str, Any]:
    """Aggregate stats (counts, price/mileage ranges, deal mix) over a slice
    of the listings, e.g. "how many 2022+ Honda CR-Vs are there and what do
    they typically cost".
    """
    con = get_connection()
    clauses: list[str] = []
    params: list[Any] = []

    def add(clause: str, *values: Any) -> None:
        clauses.append(clause)
        params.extend(values)

    if make:
        add("(makeName ILIKE ? OR makeCode ILIKE ?)", f"%{make}%", f"%{make}%")
    if model:
        add("(modelName ILIKE ? OR modelCode ILIKE ?)", f"%{model}%", f"%{model}%")
    if body_style:
        add("bodyStyle ILIKE ?", f"%{body_style}%")
    if year_min is not None:
        add("year >= ?", year_min)
    if year_max is not None:
        add("year <= ?", year_max)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    summary = con.execute(
        f"""
        SELECT
            COUNT(*) AS count,
            MIN(year) AS min_year,
            MAX(year) AS max_year,
            AVG(mileage) AS avg_mileage,
            AVG(estPriceMid) AS avg_est_price,
            MIN(estPriceLow) AS min_est_price,
            MAX(estPriceHigh) AS max_est_price,
            AVG(daysOnMarket) AS avg_days_on_market
        FROM listings
        {where_sql}
        """,
        params,
    ).fetchone()

    deal_mix = con.execute(
        f"""
        SELECT COALESCE(dealIndicator, 'Unrated') AS deal, COUNT(*) AS n
        FROM listings
        {where_sql}
        GROUP BY 1 ORDER BY n DESC
        """,
        params,
    ).fetchall()

    top_models = con.execute(
        f"""
        SELECT makeName, modelName, COUNT(*) AS n
        FROM listings
        {where_sql}
        GROUP BY 1, 2 ORDER BY n DESC LIMIT 10
        """,
        params,
    ).fetchall()

    return {
        "count": int(summary[0]),
        "year_range": [summary[1], summary[2]],
        "avg_mileage": summary[3],
        "avg_estimated_price": summary[4],
        "estimated_price_range": [summary[5], summary[6]],
        "avg_days_on_market": summary[7],
        "deal_indicator_mix": {row[0]: row[1] for row in deal_mix},
        "top_make_model_breakdown": [
            {"make": r[0], "model": r[1], "count": r[2]} for r in top_models
        ],
    }
