"""car_search: natural-language car search service."""


def main() -> None:
    """Entry point for the `car-search` console script: runs the local API server."""
    import os

    import uvicorn

    uvicorn.run(
        "car_search.server:app",
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8000")),
    )
