# About the data

Search runs against the **entire** real dataset in `data/*.parquet` — every
daily MarketCheck-style export snapshot (30 files, ~22k listings after
data-quality filtering), not a hand-picked subset. `search/dataset.py` queries
the parquet files directly through [DuckDB](https://duckdb.org/), an embedded
OLAP engine: every filter (make/model/body/price/mileage/year/fuel, and
location+radius via a SQL haversine expression) is pushed down into a
vectorized SQL scan, so the service never loads the ~22k-row dataset into
Python objects/memory — only the handful of rows that actually match a
search get materialized. A search across the whole dataset takes well
under 200ms once DuckDB's connection is warm.

Two data-shape decisions worth knowing about:

- **Price**: `salePrice` and `kbbFairPurchasePrice` are gated (`"[PREMIUM]"`)
  in every row of the source export, so there's no usable per-listing sale
  price anywhere in the data. `kbbFairPriceHigh` (a real KBB fair-price
  band) is used as each listing's effective `price` throughout. Rows with
  `kbbFairPriceHigh <= 0` (a "missing price" sentinel — ~5.8% of otherwise-
  qualifying rows, with a clean gap before the next-lowest real price of
  ~$1,680) are excluded as data-quality noise, the same way `[PREMIUM]`/
  empty values are.
- **Location**: the source data has no `lat`/`lon` columns, only
  `sellerCity`/`sellerState`/`sellerZip` (~4k distinct zips across the full
  dataset — too many to hand-maintain). `geo/locations.py` resolves zips and
  city names via the [`zipcodes`](https://pypi.org/project/zipcodes/)
  package, which bundles a complete offline US zip-code dataset (~43k
  zips, ~1.9MB) — no network geocoding call, ever. Ambiguous city names
  (e.g. "Beverly Hills" exists in both CA and FL) resolve to whichever
  state has more zips under that name, rather than averaging across
  unrelated regions.

The small curated fixture (`src/car_search/data/seed_listings.json`, 26
hand-picked real rows, built by `scripts/curate_seed_listings.py`) is no
longer the production data source — it's kept checked in purely so the
unit test suite has a small, fast, dependency-light dataset to test
`search/search.py`'s reference filtering logic against without needing
DuckDB/parquet I/O for every test.
