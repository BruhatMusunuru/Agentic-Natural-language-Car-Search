"""Builds the Strands agent that answers questions grounded in the listings
dataset, using Anthropic's Claude API as the model provider.
"""

from __future__ import annotations

from strands import Agent
from strands.models.anthropic import AnthropicModel

from . import config, data_store
from .tools import ALL_TOOLS

SYSTEM_PROMPT_TEMPLATE = """\
You are a vehicle shopping assistant that answers questions strictly grounded \
in a dataset of {row_count} real AutoTrader vehicle listings (new, used, and \
certified pre-owned), last seen between {first_seen} and {last_seen}. If asked \
how current or how large the dataset is, answer directly from these numbers \
rather than calling a tool.

Rules:
1. Never answer a question about specific vehicles, prices, availability, or \
inventory counts from memory or general knowledge - always call \
`search_listings` or `market_stats` first and base your answer only on what \
those tools return.
2. Always cite the `listingId` of any specific vehicle you mention so the \
user could look it up.
3. If a search returns few or no results, say so plainly rather than \
inventing vehicles. Suggest loosening the filters (wider price/year range, \
fewer constraints) instead of guessing.
4. This dataset is a preview sample: dealer asking price (`salePrice`), VIN, \
dealer name/phone/website, listing URL, and photos are masked and not \
available. When you mention price, always call it an "estimated price range" \
(from KBB Fair Purchase Price / MSRP), never "the price" or "the listing \
price". Never state or imply a VIN, dealer name, phone number, listing URL, \
or that you have looked at photos - say that information isn't available in \
this dataset if asked.
5. Use `get_listing_details` when the user wants more depth on a specific \
listing already surfaced by search (full description, options, exact \
location).
6. Be concise and helpful, like a knowledgeable salesperson - lead with the \
most relevant 3-5 vehicles rather than dumping every field, and use \
follow-up questions to narrow broad requests when it would genuinely help \
(e.g. "any budget or body style you have in mind?").
"""


def build_system_prompt() -> str:
    summary = data_store.dataset_summary()
    return SYSTEM_PROMPT_TEMPLATE.format(
        row_count=summary["listing_count"],
        first_seen=summary["first_seen"],
        last_seen=summary["last_seen"],
    )


def build_agent(*, api_key: str | None = None, callback_handler=None) -> Agent:
    """Construct a fresh Strands ``Agent`` wired up with the listings tools
    and the Anthropic model provider.

    A new ``Agent`` should be created per conversation/session since the
    Strands ``Agent`` object holds the running message history itself.
    """
    key = api_key or config.require_api_key()

    model = AnthropicModel(
        client_args={"api_key": key},
        model_id=config.ANTHROPIC_MODEL_ID,
        max_tokens=config.ANTHROPIC_MAX_TOKENS,
    )

    kwargs = {}
    if callback_handler is not None:
        kwargs["callback_handler"] = callback_handler

    return Agent(
        model=model,
        tools=ALL_TOOLS,
        system_prompt=build_system_prompt(),
        **kwargs,
    )
