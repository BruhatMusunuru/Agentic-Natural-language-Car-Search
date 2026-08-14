"""Tests for the Strands @tool wrappers: correct delegation to data_store and
valid tool schemas (what actually gets sent to Claude as the tool spec).
"""

from __future__ import annotations

from rag_assistant import tools


def test_tool_specs_have_required_shape():
    for t in tools.ALL_TOOLS:
        spec = t.tool_spec
        assert spec["name"]
        assert spec["description"]
        assert spec["inputSchema"]["json"]["type"] == "object"


def test_get_listing_details_tool_spec_requires_listing_id():
    spec = tools.get_listing_details.tool_spec
    assert spec["inputSchema"]["json"]["required"] == ["listing_id"]


def test_search_listings_tool_delegates_and_returns_results():
    result = tools.search_listings(make="Honda", limit=3)
    assert result["returned"] <= 3
    assert all(listing["makeName"] == "Honda" for listing in result["listings"])


def test_get_listing_details_tool_reports_error_for_unknown_id():
    result = tools.get_listing_details(listing_id="does-not-exist")
    assert "error" in result


def test_get_listing_details_tool_returns_record_for_known_id():
    found = tools.search_listings(limit=1)["listings"][0]
    result = tools.get_listing_details(listing_id=found["listingId"])
    assert "error" not in result
    assert str(result["listingId"]) == str(found["listingId"])


def test_market_stats_tool_delegates():
    result = tools.market_stats(make="Toyota")
    assert result["count"] > 0
    assert "estimated_price_range" in result
