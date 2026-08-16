"""Static zip -> (lat, lon) lookup and free-text location resolution.

No live/network geocoding (see FR-15). Coordinates are city-level
approximations sourced from public city coordinates, hardcoded for exactly
the zip codes present in the curated seed fixture (see
scripts/curate_seed_listings.py).
"""

from __future__ import annotations

# zip -> (lat, lon), city-level approximation.
ZIP_COORDS: dict[str, tuple[float, float]] = {
    # Chicago metro
    "60201": (42.0451, -87.6877),  # Evanston, IL
    "60453": (41.7198, -87.7581),  # Oak Lawn, IL
    "60173": (42.0334, -88.0834),  # Schaumburg, IL
    "60126": (41.8994, -87.9403),  # Elmhurst, IL
    "60610": (41.9038, -87.6355),  # Chicago, IL
    "60540": (41.7508, -88.1535),  # Naperville, IL
    "60504": (41.7466, -88.2262),  # Aurora, IL
    "60515": (41.8089, -87.9987),  # Downers Grove, IL
    "60099": (42.4467, -87.8323),  # Zion, IL
    "60010": (42.1536, -88.1367),  # Barrington, IL
    "61107": (42.2917, -89.0217),  # Rockford, IL (~75mi from Chicago)
    # Farther away (other states)
    "45251": (39.2431, -84.5836),  # Cincinnati, OH
    "40218": (38.2009, -85.6602),  # Louisville, KY
    "44094": (41.6431, -81.4062),  # Willoughby, OH
    "78617": (30.1789, -97.7444),  # Austin, TX
    "91762": (34.0633, -117.6509),  # Ontario, CA
    "33483": (26.4615, -80.0728),  # Delray Beach, FL
    "90211": (34.0669, -118.4008),  # Beverly Hills, CA
    "07036": (40.6220, -74.2446),  # Linden, NJ
    "66720": (37.6795, -95.4522),  # Chanute, KS
    "75067": (33.0462, -96.9942),  # Lewisville, TX
    "55906": (44.0121, -92.4802),  # Rochester, MN
}

# Named locations a free-text query might mention. Chicago is the flagship
# hub city (see US-004); the others give resolve_location somewhere sensible
# to land for out-of-radius/other-state queries.
NAMED_LOCATIONS: dict[str, tuple[float, float]] = {
    "chicago": (41.8781, -87.6298),
    "chicago, il": (41.8781, -87.6298),
    "chicago il": (41.8781, -87.6298),
    "evanston": ZIP_COORDS["60201"],
    "oak lawn": ZIP_COORDS["60453"],
    "schaumburg": ZIP_COORDS["60173"],
    "elmhurst": ZIP_COORDS["60126"],
    "naperville": ZIP_COORDS["60540"],
    "aurora": ZIP_COORDS["60504"],
    "downers grove": ZIP_COORDS["60515"],
    "zion": ZIP_COORDS["60099"],
    "barrington": ZIP_COORDS["60010"],
    "rockford": ZIP_COORDS["61107"],
    "cincinnati": ZIP_COORDS["45251"],
    "louisville": ZIP_COORDS["40218"],
    "willoughby": ZIP_COORDS["44094"],
    "austin": ZIP_COORDS["78617"],
    "ontario": ZIP_COORDS["91762"],
    "ontario, ca": ZIP_COORDS["91762"],
    "delray beach": ZIP_COORDS["33483"],
    "beverly hills": ZIP_COORDS["90211"],
    "linden": ZIP_COORDS["07036"],
    "chanute": ZIP_COORDS["66720"],
    "lewisville": ZIP_COORDS["75067"],
    "rochester": ZIP_COORDS["55906"],
    "rochester, mn": ZIP_COORDS["55906"],
}

DEFAULT_RADIUS_MI = 50


def resolve_location(location: str) -> tuple[float, float] | None:
    """Resolve free-text location to (lat, lon), or None if unresolvable.

    Tries an exact zip-code match first, then a case-insensitive lookup
    against NAMED_LOCATIONS (matching on the whole string or its
    comma-separated city part). No network geocoding is ever performed.
    """
    text = location.strip()
    if not text:
        return None

    if text in ZIP_COORDS:
        return ZIP_COORDS[text]

    normalized = text.lower()
    if normalized in NAMED_LOCATIONS:
        return NAMED_LOCATIONS[normalized]

    city_part = normalized.split(",")[0].strip()
    if city_part in NAMED_LOCATIONS:
        return NAMED_LOCATIONS[city_part]

    return None
