"""FastAPI app exposing POST /search (US-010).

Run locally with: car-search (or `uvicorn car_search.api.server:app`).
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from car_search.orchestrator import SearchResponse, run_search

app = FastAPI(title="car-search", description="Natural-language car search API")


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)


@app.post("/search", response_model=SearchResponse)
def search(request: SearchRequest) -> SearchResponse:
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="query must not be empty")
    return run_search(query)
