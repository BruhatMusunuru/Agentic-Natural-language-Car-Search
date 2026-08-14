"""Strands tools the agent calls to ground its answers in real listings.

Each tool is a thin, typed wrapper around ``rag_assistant.data_store``. The
model never sees raw listing data except through these calls, and every
response includes the total number of matches so the model can tell the
user when a search was narrow or came up empty instead of guessing.
"""

from __future__ import annotations

from typing import Any

from strands import tool

from . import data_store


@tool
def search_listings(
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
    limit: int = 8,
) -> dict[str, Any]:
    """Search the vehicle listings dataset. This is the primary tool for
    finding vehicles that match what the user is asking about - always call
    this before answering any question about specific vehicles, prices, or
    availability instead of guessing.

    Args:
        make: Vehicle make/brand, e.g. "Toyota", "BMW".
        model: Vehicle model, e.g. "Camry", "X3".
        year_min: Minimum model year (inclusive).
        year_max: Maximum model year (inclusive).
        price_min: Minimum estimated price in USD (KBB fair-price based; see
            note in results about pricing).
        price_max: Maximum estimated price in USD.
        max_mileage: Maximum odometer reading in miles.
        body_style: e.g. "SUV", "Sedan", "Truck", "Coupe".
        fuel_type: e.g. "Gasoline", "Electric", "Hybrid", "Diesel".
        drivetrain: e.g. "All wheel drive", "Front-wheel drive".
        transmission: "Automatic" or "Manual".
        listing_type: "New", "Used", or "Certified".
        deal_indicator: KBB deal rating: "Great", "Good", "Fair", "High", or
            "Overpriced".
        city: Seller/dealer city.
        state: Seller/dealer state (2-letter code or name).
        min_mpg_highway: Minimum highway MPG.
        only_hot: If true, only return listings flagged as high-interest ("hot").
        keywords: Free-text keywords to match against the title, trim,
            description, and options (e.g. "sunroof leather navigation").
            All words must appear somewhere in the listing.
        limit: Max number of listings to return (default 8, max 25).

    Returns:
        A dict with `total_matches` (how many listings matched before the
        limit was applied), `returned` (how many are included below), and
        `listings` (the matching listings). IMPORTANT pricing caveat: this
        sample dataset masks the dealer's actual asking price
        (`salePrice`), so `estPriceLow`/`estPriceHigh` are KBB Fair
        Purchase Price estimates, not the listed price - always describe
        them to the user as an estimated price range, not "the price".
    """
    return data_store.search_listings(
        make=make,
        model=model,
        year_min=year_min,
        year_max=year_max,
        price_min=price_min,
        price_max=price_max,
        max_mileage=max_mileage,
        body_style=body_style,
        fuel_type=fuel_type,
        drivetrain=drivetrain,
        transmission=transmission,
        listing_type=listing_type,
        deal_indicator=deal_indicator,
        city=city,
        state=state,
        min_mpg_highway=min_mpg_highway,
        only_hot=only_hot,
        keywords=keywords,
        limit=limit,
    )


@tool
def get_listing_details(listing_id: str) -> dict[str, Any]:
    """Look up the full detail record for one specific listing by its
    listingId (as returned by `search_listings`). Use this when the user
    asks to know more about a particular vehicle already found in search
    results - it includes the full marketing description, option list, and
    seller location that the compact search results omit.

    Args:
        listing_id: The `listingId` value from a `search_listings` result.

    Returns:
        The full listing record, or an `error` message if no listing with
        that id exists in the dataset.
    """
    record = data_store.get_listing(listing_id)
    if record is None:
        return {"error": f"No listing found with listingId={listing_id!r}."}
    return record


@tool
def market_stats(
    make: str | None = None,
    model: str | None = None,
    body_style: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
) -> dict[str, Any]:
    """Get aggregate market statistics (count, price range, mileage,
    deal-rating mix) over a slice of the listings. Use this for questions
    about typical/average pricing, how many vehicles of a type are
    available, or comparing segments - rather than trying to average
    numbers yourself from a handful of search results.

    Args:
        make: Vehicle make/brand to filter to, e.g. "Honda".
        model: Vehicle model to filter to, e.g. "CR-V".
        body_style: Body style to filter to, e.g. "SUV".
        year_min: Minimum model year (inclusive).
        year_max: Maximum model year (inclusive).

    Returns:
        Aggregate stats for listings matching the given filters, including
        `count`, `estimated_price_range`, `avg_estimated_price`,
        `avg_mileage`, `deal_indicator_mix`, and the top make/model
        breakdown within the slice.
    """
    return data_store.market_stats(
        make=make,
        model=model,
        body_style=body_style,
        year_min=year_min,
        year_max=year_max,
    )


ALL_TOOLS = [search_listings, get_listing_details, market_stats]
