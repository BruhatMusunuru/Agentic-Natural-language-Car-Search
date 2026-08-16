"""zip/city -> (lat, lon) resolution, backed by the `zipcodes` package.

`zipcodes` ships a bundled offline dataset of every US zip code (~42k,
~1.9MB) -- no network call, ever, and no need to hand-maintain a lookup
table (the previous approach, viable only for the ~20-listing curated
fixture, doesn't scale to the full ~22k-listing dataset spanning ~4k
distinct zips across data/*.parquet). This satisfies FR-5/FR-15: distance
is computed from real coordinates, but there is still no live/network
geocoding of the free-text query -- resolution is a lookup against this
bundled static dataset.
"""

from __future__ import annotations

import re
from functools import lru_cache

import zipcodes as _zipcodes

DEFAULT_RADIUS_MI = 50

_ZIP_LIKE = re.compile(r"^[\d-]+$")


@lru_cache(maxsize=4096)
def zip_to_coords(zip_code: str) -> tuple[float, float] | None:
    """Look up a zip code's (lat, lon), or None if it's not a recognized US zip."""
    zip_code = zip_code.strip()
    if not _ZIP_LIKE.match(zip_code):
        return None
    matches = _zipcodes.matching(zip_code)  # type: ignore[no-untyped-call]
    if not matches:
        return None
    entry = matches[0]
    lat, lon = entry.get("lat"), entry.get("long")
    if lat is None or lon is None:
        return None
    return float(lat), float(lon)


@lru_cache(maxsize=1024)
def _city_to_coords(city: str, state: str | None) -> tuple[float, float] | None:
    filters: dict[str, str] = {"city": city.title()}
    if state:
        filters["state"] = state.upper()
    matches = _zipcodes.filter_by(**filters)  # type: ignore[no-untyped-call]
    by_state: dict[str, list[tuple[float, float]]] = {}
    for m in matches:
        if m.get("lat") is None or m.get("long") is None:
            continue
        by_state.setdefault(m["state"], []).append((float(m["lat"]), float(m["long"])))
    if not by_state:
        return None
    # Same city name can exist in multiple states (e.g. "Beverly Hills" in
    # both CA and FL). With no state given, disambiguate by picking the
    # state with the most zips under that city name (a rough size/
    # prominence proxy) rather than averaging across unrelated regions.
    coords = max(by_state.values(), key=len)
    lat = sum(c[0] for c in coords) / len(coords)
    lon = sum(c[1] for c in coords) / len(coords)
    return lat, lon


def resolve_location(location: str) -> tuple[float, float] | None:
    """Resolve free-text location to (lat, lon), or None if unresolvable.

    Tries an exact zip-code match first, then a city[, state] lookup
    (e.g. "Chicago", "Naperville, IL", "Aurora IL"). No network geocoding
    is ever performed -- everything comes from the bundled `zipcodes`
    dataset.
    """
    text = location.strip()
    if not text:
        return None

    zip_coords = zip_to_coords(text)
    if zip_coords is not None:
        return zip_coords

    parts = [p.strip() for p in text.replace(",", " ").split()]
    if not parts:
        return None

    # Last token might be a two-letter state code (e.g. "Aurora IL").
    state = None
    city_parts = parts
    if len(parts[-1]) == 2 and parts[-1].isalpha():
        state = parts[-1]
        city_parts = parts[:-1]
    if not city_parts:
        return None

    city = " ".join(city_parts)
    coords = _city_to_coords(city, state)
    if coords is not None:
        return coords
    if state is not None:
        # Retry without the (possibly misparsed) state token.
        return _city_to_coords(" ".join(parts), None)
    return None
