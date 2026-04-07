from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class Listing:
    id: str
    source_key: str
    source_label: str
    title: str
    description: str
    borough: str
    neighborhood: str
    address: str
    price: int
    beds: float
    baths: float
    sqft: int
    property_type: str
    available_from: str
    lease_term: str
    image_url: str
    listing_url: str
    latitude: float
    longitude: float
    pet_friendly: bool
    furnished: bool
    has_doorman: bool
    has_laundry: bool
    near_subway: bool
    allows_guarantors: bool
    featured: bool


@dataclass(slots=True)
class ListingFilters:
    search: str = ""
    sources: list[str] = field(default_factory=list)
    boroughs: list[str] = field(default_factory=list)
    neighborhoods: list[str] = field(default_factory=list)
    min_price: int | None = None
    max_price: int | None = None
    min_beds: float | None = None
    max_beds: float | None = None
    min_baths: float | None = None
    pet_friendly: bool | None = None
    furnished: bool | None = None
    has_doorman: bool | None = None
    has_laundry: bool | None = None
    near_subway: bool | None = None
    allows_guarantors: bool | None = None
    featured_only: bool | None = None
    sort_by: str = "featured"


@dataclass(slots=True)
class ListingsSnapshot:
    items: list[Listing]
    source_file: str
    source_kind: str
    source_counts: dict[str, int]


def listing_to_dict(listing: Listing) -> dict[str, object]:
    return asdict(listing)
