from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .models import listing_to_dict
from .repository import (
    build_filters,
    filter_listings,
    get_filter_options,
    get_listing_by_id,
    load_snapshot,
    source_name_for_listing,
)


BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(
    title="NYC Rentals Platform",
    description="A modern NYC apartment rental discovery app with filters and map view.",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    snapshot = load_snapshot()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "app_name": "RentScout NYC",
            "data_source_kind": snapshot.source_kind,
            "source_counts": snapshot.source_counts,
        },
    )


@app.get("/listings/{listing_id}", response_class=HTMLResponse)
async def listing_page(request: Request, listing_id: str) -> HTMLResponse:
    listing = get_listing_by_id(listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")

    return templates.TemplateResponse(
        "listing.html",
        {
            "request": request,
            "listing": listing_to_dict(listing),
            "source_name": source_name_for_listing(listing),
        },
    )


@app.get("/api/listings")
async def list_listings(
    search: str = "",
    source: str | None = None,
    borough: str | None = None,
    neighborhood: str | None = None,
    min_price: int | None = Query(default=None, ge=0),
    max_price: int | None = Query(default=None, ge=0),
    min_beds: float | None = Query(default=None, ge=0),
    max_beds: float | None = Query(default=None, ge=0),
    min_baths: float | None = Query(default=None, ge=0),
    pet_friendly: bool | None = None,
    furnished: bool | None = None,
    has_doorman: bool | None = None,
    has_laundry: bool | None = None,
    near_subway: bool | None = None,
    allows_guarantors: bool | None = None,
    featured_only: bool | None = None,
    sort_by: str = "featured",
) -> dict[str, object]:
    filters = build_filters(
        search=search,
        source=source,
        borough=borough,
        neighborhood=neighborhood,
        min_price=min_price,
        max_price=max_price,
        min_beds=min_beds,
        max_beds=max_beds,
        min_baths=min_baths,
        pet_friendly=pet_friendly,
        furnished=furnished,
        has_doorman=has_doorman,
        has_laundry=has_laundry,
        near_subway=near_subway,
        allows_guarantors=allows_guarantors,
        featured_only=featured_only,
        sort_by=sort_by,
    )
    listings = filter_listings(filters)
    snapshot = load_snapshot()
    return {
        "count": len(listings),
        "items": [listing_to_dict(listing) for listing in listings],
        "source": {
            "kind": snapshot.source_kind,
            "file": snapshot.source_file,
            "breakdown": snapshot.source_counts,
        },
    }


@app.get("/api/listings/{listing_id}")
async def listing_detail(listing_id: str) -> dict[str, object]:
    listing = get_listing_by_id(listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    return listing_to_dict(listing)


@app.get("/api/filter-options")
async def filter_options() -> dict[str, object]:
    return get_filter_options()


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
