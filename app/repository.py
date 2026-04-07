from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from .models import Listing, ListingFilters, ListingsSnapshot


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
IMPORTS_DIR = DATA_DIR / "imports"
SEED_DATA_FILE = DATA_DIR / "listings.csv"
SCRAPED_DATA_FILE = DATA_DIR / "scraped_listings.csv"
ZILLOW_FEED_FILE = IMPORTS_DIR / "zillow_listings.csv"
REALTOR_IMPORT_FILE = IMPORTS_DIR / "realtor_listings.csv"
AIRBNB_IMPORT_FILE = IMPORTS_DIR / "airbnb_listings.csv"
DEFAULT_IMAGE_URL = (
    "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85"
    "?auto=format&fit=crop&w=1200&q=80"
)
FALLBACK_IMAGE_POOL = [
    "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1494526585095-c41746248156?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1484154218962-a197022b5858?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1448630360428-65456885c650?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1502005229762-cf1b2da7c5d6?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1460317442991-0ec209397118?auto=format&fit=crop&w=1200&q=80",
]
NEIGHBORHOOD_COORDINATES = {
    "Astoria": (40.7644, -73.9235),
    "Brooklyn": (40.6782, -73.9442),
    "East Village": (40.7265, -73.9815),
    "Fort Greene": (40.6904, -73.9740),
    "Harlem": (40.8116, -73.9465),
    "Kew Gardens": (40.7098, -73.8304),
    "Long Island City": (40.7447, -73.9485),
    "Manhattan": (40.7831, -73.9712),
    "Midtown": (40.7549, -73.9840),
    "Park Slope": (40.6720, -73.9770),
    "Queens": (40.7282, -73.7949),
    "Riverdale": (40.9006, -73.9067),
    "South Bronx": (40.8183, -73.9180),
    "Staten Island": (40.5795, -74.1502),
    "Upper West Side": (40.7870, -73.9754),
    "Williamsburg": (40.7081, -73.9571),
}
Borough_COORDINATES = {
    "Bronx": (40.8448, -73.8648),
    "Brooklyn": (40.6782, -73.9442),
    "Manhattan": (40.7831, -73.9712),
    "Queens": (40.7282, -73.7949),
    "Staten Island": (40.5795, -74.1502),
}

_SNAPSHOT_CACHE: ListingsSnapshot | None = None
_SNAPSHOT_SIGNATURE: tuple[tuple[str, float], ...] | None = None


def _parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _split_csv_values(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _normalize_float(raw: str | None, default: float = 0.0) -> float:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _normalize_int(raw: str | None, default: int = 0) -> int:
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return default


def _hash_id(*parts: str) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:12]


def _has_real_rows(csv_path: Path) -> bool:
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return False

    with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        return next(reader, None) is not None


def _existing_data_sources() -> list[Path]:
    existing = [
        path
        for path in [
            SCRAPED_DATA_FILE,
            ZILLOW_FEED_FILE,
            REALTOR_IMPORT_FILE,
            AIRBNB_IMPORT_FILE,
        ]
        if _has_real_rows(path)
    ]
    if existing:
        return existing
    return [SEED_DATA_FILE]


def _snapshot_signature() -> tuple[tuple[str, float], ...]:
    return tuple((str(path), path.stat().st_mtime) for path in _existing_data_sources())


def _clean_text(value: str | None, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _infer_beds(title: str, description: str, raw_beds: float) -> float:
    if raw_beds > 0:
        return raw_beds
    text = f"{title} {description}".lower()
    if "studio" in text:
        return 0.0
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:bed|beds|bedroom|bedrooms|bd|br)\b", text)
    if match:
        return float(match.group(1))
    return 0.0


def _infer_sqft(title: str, description: str, raw_sqft: int) -> int:
    if raw_sqft > 0:
        return raw_sqft
    text = f"{title} {description}".lower()
    match = re.search(r"(\d{3,5})\s*(?:sq\.?\s*ft|sqft|square feet|ft2)\b", text)
    if match:
        return int(match.group(1))
    return 0


def _infer_amenity(value: bool, *texts: str, keywords: tuple[str, ...]) -> bool:
    if value:
        return True
    haystack = " ".join(texts).lower()
    return any(keyword in haystack for keyword in keywords)


def _source_key_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if "craigslist" in host:
        return "craigslist"
    if "zillow" in host:
        return "zillow"
    if "realtor" in host:
        return "realtor"
    if "hotpads" in host:
        return "hotpads"
    if "airbnb" in host:
        return "airbnb"
    if not host:
        return "curated"
    return host.replace(".", "-")


def _source_label_from_key(source_key: str) -> str:
    mapping = {
        "craigslist": "Craigslist",
        "zillow": "Zillow",
        "realtor": "Realtor.com",
        "hotpads": "HotPads",
        "airbnb": "Airbnb",
        "curated": "RentScout Curated",
        "seed": "RentScout Seed",
    }
    return mapping.get(source_key, source_key.replace("-", " ").title())


def _fallback_image_for(seed: str) -> str:
    if not seed:
        return DEFAULT_IMAGE_URL
    index = int(hashlib.sha1(seed.encode("utf-8")).hexdigest(), 16) % len(FALLBACK_IMAGE_POOL)
    return FALLBACK_IMAGE_POOL[index]


def _jitter(seed: str, scale: float) -> float:
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()
    value = int(digest[:8], 16) / 0xFFFFFFFF
    return (value - 0.5) * scale


def _estimate_coordinates(seed: str, neighborhood: str, borough: str) -> tuple[float, float]:
    base_lat, base_lng = NEIGHBORHOOD_COORDINATES.get(
        neighborhood,
        Borough_COORDINATES.get(borough, Borough_COORDINATES["Manhattan"]),
    )
    return (
        round(base_lat + _jitter(f"{seed}-lat", 0.03), 6),
        round(base_lng + _jitter(f"{seed}-lng", 0.03), 6),
    )


def _apply_coordinate_fallback(listing: Listing) -> Listing:
    if listing.latitude and listing.longitude:
        return listing
    listing.latitude, listing.longitude = _estimate_coordinates(
        listing.id or listing.address or listing.title,
        listing.neighborhood,
        listing.borough,
    )
    return listing


def _infer_borough(*values: str) -> str:
    text = " ".join(values).lower()
    if any(token in text for token in ["brooklyn", "williamsburg", "park slope", "fort greene", "dumbo", "bushwick"]):
        return "Brooklyn"
    if any(token in text for token in ["queens", "astoria", "lic", "long island city", "arverne", "flushing"]):
        return "Queens"
    if any(token in text for token in ["bronx", "riverdale", "fordham", "kingsbridge"]):
        return "Bronx"
    if any(token in text for token in ["staten island", "st. george"]):
        return "Staten Island"
    return "Manhattan"


def _infer_neighborhood(address: str, borough: str) -> str:
    text = address.lower()
    mapping = {
        "Williamsburg": ["williamsburg"],
        "Park Slope": ["park slope"],
        "Fort Greene": ["fort greene"],
        "Long Island City": ["long island city", "lic"],
        "Astoria": ["astoria"],
        "Harlem": ["harlem"],
        "Midtown": ["midtown", "w 43rd"],
        "Upper West Side": ["upper west side", "columbus ave", "w 61st"],
        "East Village": ["east village", "les", "lower east side", "tompkins"],
        "Riverdale": ["riverdale", "w 238th"],
        "Kew Gardens": ["kew gardens", "union turnpike"],
        "South Bronx": ["south bronx", "mott haven"],
    }
    for name, hints in mapping.items():
        if any(hint in text for hint in hints):
            return name
    return borough


def _dedupe_key(listing: Listing) -> str:
    if listing.listing_url:
        return listing.listing_url
    return f"{listing.source_key}|{listing.title}|{listing.address}|{listing.price}"


def _is_usable_listing(listing: Listing) -> bool:
    if listing.price <= 0:
        return False
    if not listing.title.strip():
        return False
    if not listing.listing_url.strip():
        return False
    return True


def _load_normalized_csv(csv_path: Path) -> list[Listing]:
    listings: list[Listing] = []
    with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            listing_url = _clean_text(row.get("listing_url"))
            source_key = _source_key_from_url(listing_url)
            source_label = _source_label_from_key(source_key)
            borough = _clean_text(row.get("borough"), _infer_borough(row.get("address", ""), row.get("neighborhood", "")))
            neighborhood = _clean_text(row.get("neighborhood"), _infer_neighborhood(_clean_text(row.get("address")), borough))
            listing_id = _clean_text(row.get("id"), f"{source_key}-{_hash_id(listing_url, row.get('title', ''))}")
            title = _clean_text(row.get("title"), "NYC Rental Listing")
            description = _clean_text(row.get("description"), "No description provided.")
            address = _clean_text(row.get("address"), "New York, NY")
            raw_beds = _normalize_float(row.get("beds"))
            raw_sqft = _normalize_int(row.get("sqft"))
            listings.append(
                _apply_coordinate_fallback(Listing(
                    id=listing_id,
                    source_key=source_key,
                    source_label=source_label,
                    title=title,
                    description=description,
                    borough=borough,
                    neighborhood=neighborhood,
                    address=address,
                    price=_normalize_int(row.get("price")),
                    beds=_infer_beds(title, description, raw_beds),
                    baths=_normalize_float(row.get("baths"), default=1.0),
                    sqft=_infer_sqft(title, description, raw_sqft),
                    property_type=_clean_text(row.get("property_type"), "Apartment"),
                    available_from=_clean_text(row.get("available_from")),
                    lease_term=_clean_text(row.get("lease_term"), "12 months"),
                    image_url=_clean_text(row.get("image_url")) or _fallback_image_for(listing_id),
                    listing_url=listing_url,
                    latitude=_normalize_float(row.get("latitude")),
                    longitude=_normalize_float(row.get("longitude")),
                    pet_friendly=_infer_amenity(
                        _parse_bool(row.get("pet_friendly", "")),
                        title,
                        description,
                        address,
                        keywords=("pet", "pets", "cats", "dogs", "dog friendly", "cat friendly"),
                    ),
                    furnished=_parse_bool(row.get("furnished", "")),
                    has_doorman=_infer_amenity(
                        _parse_bool(row.get("has_doorman", "")),
                        title,
                        description,
                        keywords=("doorman", "concierge", "attended lobby"),
                    ),
                    has_laundry=_infer_amenity(
                        _parse_bool(row.get("has_laundry", "")),
                        title,
                        description,
                        keywords=("laundry", "washer", "dryer", "w/d", "washer/dryer"),
                    ),
                    near_subway=_infer_amenity(
                        _parse_bool(row.get("near_subway", "")),
                        title,
                        description,
                        address,
                        keywords=("subway", "train", "station", "metro"),
                    ),
                    allows_guarantors=_infer_amenity(
                        _parse_bool(row.get("allows_guarantors", "")),
                        title,
                        description,
                        keywords=("guarantor", "rhino"),
                    ),
                    featured=_parse_bool(row.get("featured", "")),
                ))
            )
    return listings


def _load_zillow_feed(csv_path: Path) -> list[Listing]:
    listings: list[Listing] = []
    with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for index, row in enumerate(reader, start=1):
            listing_url = _clean_text(row.get("link"))
            if not listing_url:
                continue

            area = _clean_text(row.get("area"), "New York, NY")
            if "|" in area:
                building_name, address = [part.strip() for part in area.split("|", 1)]
            else:
                building_name, address = "", area

            borough = _infer_borough(area, listing_url)
            neighborhood = _infer_neighborhood(address, borough)
            title = _clean_text(row.get("title"), building_name or f"{neighborhood} rental")
            source_key = _source_key_from_url(listing_url)
            listing_id = f"{source_key}-{_hash_id(listing_url, str(index))}"
            description = _clean_text(
                row.get("description"),
                "Imported from another NYC rental feed. Open the source listing for the latest building details.",
            )
            raw_beds = _normalize_float(row.get("bedrooms"))
            listings.append(
                _apply_coordinate_fallback(Listing(
                    id=listing_id,
                    source_key=source_key,
                    source_label=_source_label_from_key(source_key),
                    title=title,
                    description=description,
                    borough=borough,
                    neighborhood=neighborhood,
                    address=_clean_text(address, "New York, NY"),
                    price=_normalize_int(row.get("price")),
                    beds=_infer_beds(title, description, raw_beds),
                    baths=1.0,
                    sqft=_infer_sqft(title, description, 0),
                    property_type="Apartment",
                    available_from="",
                    lease_term="Check source",
                    image_url=_clean_text(row.get("image")) or _fallback_image_for(listing_id),
                    listing_url=listing_url,
                    latitude=0.0,
                    longitude=0.0,
                    pet_friendly=_infer_amenity(
                        False,
                        title,
                        description,
                        area,
                        keywords=("pet", "pets", "cats", "dogs"),
                    ),
                    furnished=_infer_amenity(False, title, description, keywords=("furnished", "fully furnished")),
                    has_doorman=_infer_amenity(False, title, description, keywords=("doorman", "concierge")),
                    has_laundry=_infer_amenity(False, title, description, keywords=("laundry", "washer", "dryer", "w/d")),
                    near_subway=_infer_amenity(True, title, description, address, keywords=("subway", "train", "station", "metro")),
                    allows_guarantors=_infer_amenity(False, title, description, keywords=("guarantor",)),
                    featured=False,
                ))
            )
    return listings


def _load_seed_data(csv_path: Path) -> list[Listing]:
    listings: list[Listing] = []
    with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            title = _clean_text(row.get("title"), "NYC Rental Listing")
            description = _clean_text(row.get("description"), "No description provided.")
            raw_beds = _normalize_float(row.get("beds"))
            listings.append(
                _apply_coordinate_fallback(Listing(
                    id=_clean_text(row.get("id")),
                    source_key="seed",
                    source_label="RentScout Seed",
                    title=title,
                    description=description,
                    borough=_clean_text(row.get("borough"), "Manhattan"),
                    neighborhood=_clean_text(row.get("neighborhood"), "Manhattan"),
                    address=_clean_text(row.get("address"), "New York, NY"),
                    price=_normalize_int(row.get("price")),
                    beds=_infer_beds(title, description, raw_beds),
                    baths=_normalize_float(row.get("baths"), default=1.0),
                    sqft=_infer_sqft(title, description, _normalize_int(row.get("sqft"))),
                    property_type=_clean_text(row.get("property_type"), "Apartment"),
                    available_from=_clean_text(row.get("available_from")),
                    lease_term=_clean_text(row.get("lease_term"), "12 months"),
                    image_url=_clean_text(row.get("image_url")) or _fallback_image_for(_clean_text(row.get("id"))),
                    listing_url=_clean_text(row.get("listing_url")),
                    latitude=_normalize_float(row.get("latitude")),
                    longitude=_normalize_float(row.get("longitude")),
                    pet_friendly=_parse_bool(row.get("pet_friendly", "")),
                    furnished=_parse_bool(row.get("furnished", "")),
                    has_doorman=_parse_bool(row.get("has_doorman", "")),
                    has_laundry=_parse_bool(row.get("has_laundry", "")),
                    near_subway=_parse_bool(row.get("near_subway", "")),
                    allows_guarantors=_parse_bool(row.get("allows_guarantors", "")),
                    featured=_parse_bool(row.get("featured", "")),
                ))
            )
    return listings


def _load_partner_import(csv_path: Path, default_source_key: str) -> list[Listing]:
    listings: list[Listing] = []
    with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for index, row in enumerate(reader, start=1):
            listing_url = _clean_text(row.get("listing_url"))
            source_key = _clean_text(row.get("source_key"), default_source_key)
            source_label = _clean_text(row.get("source_label"), _source_label_from_key(source_key))
            listing_id = _clean_text(row.get("id"), f"{source_key}-{_hash_id(listing_url, str(index))}")
            borough = _clean_text(row.get("borough"), _infer_borough(row.get("address", ""), row.get("neighborhood", "")))
            neighborhood = _clean_text(row.get("neighborhood"), _infer_neighborhood(_clean_text(row.get("address")), borough))
            title = _clean_text(row.get("title"), "NYC Rental Listing")
            description = _clean_text(
                row.get("description"),
                "Imported from a partner source feed. Open the source listing for the latest details.",
            )
            address = _clean_text(row.get("address"), "New York, NY")
            raw_beds = _normalize_float(row.get("beds"))
            listings.append(
                _apply_coordinate_fallback(Listing(
                    id=listing_id,
                    source_key=source_key,
                    source_label=source_label,
                    title=title,
                    description=description,
                    borough=borough,
                    neighborhood=neighborhood,
                    address=address,
                    price=_normalize_int(row.get("price")),
                    beds=_infer_beds(title, description, raw_beds),
                    baths=_normalize_float(row.get("baths"), default=1.0),
                    sqft=_infer_sqft(title, description, _normalize_int(row.get("sqft"))),
                    property_type=_clean_text(row.get("property_type"), "Apartment"),
                    available_from=_clean_text(row.get("available_from")),
                    lease_term=_clean_text(row.get("lease_term"), "Check source"),
                    image_url=_clean_text(row.get("image_url")) or _fallback_image_for(listing_id),
                    listing_url=listing_url,
                    latitude=_normalize_float(row.get("latitude")),
                    longitude=_normalize_float(row.get("longitude")),
                    pet_friendly=_infer_amenity(_parse_bool(row.get("pet_friendly", "")), title, description, address, keywords=("pet", "pets", "cats", "dogs")),
                    furnished=_infer_amenity(_parse_bool(row.get("furnished", "")), title, description, keywords=("furnished", "fully furnished")),
                    has_doorman=_infer_amenity(_parse_bool(row.get("has_doorman", "")), title, description, keywords=("doorman", "concierge")),
                    has_laundry=_infer_amenity(_parse_bool(row.get("has_laundry", "")), title, description, keywords=("laundry", "washer", "dryer", "w/d")),
                    near_subway=_infer_amenity(_parse_bool(row.get("near_subway", "")), title, description, address, keywords=("subway", "train", "station", "metro")),
                    allows_guarantors=_infer_amenity(_parse_bool(row.get("allows_guarantors", "")), title, description, keywords=("guarantor",)),
                    featured=_parse_bool(row.get("featured", "")),
                ))
            )
    return listings


def load_snapshot() -> ListingsSnapshot:
    global _SNAPSHOT_CACHE, _SNAPSHOT_SIGNATURE

    signature = _snapshot_signature()
    if _SNAPSHOT_CACHE is not None and _SNAPSHOT_SIGNATURE == signature:
        return _SNAPSHOT_CACHE

    files = _existing_data_sources()
    listings: list[Listing] = []
    file_labels: list[str] = []

    for path in files:
        file_labels.append(path.name)
        if path == SCRAPED_DATA_FILE:
            listings.extend(_load_normalized_csv(path))
        elif path == ZILLOW_FEED_FILE:
            listings.extend(_load_zillow_feed(path))
        elif path == REALTOR_IMPORT_FILE:
            listings.extend(_load_partner_import(path, "realtor"))
        elif path == AIRBNB_IMPORT_FILE:
            listings.extend(_load_partner_import(path, "airbnb"))
        else:
            listings.extend(_load_seed_data(path))

    deduped: list[Listing] = []
    seen: set[str] = set()
    for listing in listings:
        if not _is_usable_listing(listing):
            continue
        key = _dedupe_key(listing)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(listing)

    source_counts = dict(sorted(Counter(listing.source_label for listing in deduped).items()))
    source_kind = "aggregated" if len(source_counts) > 1 else "single-source"
    snapshot = ListingsSnapshot(
        items=deduped,
        source_file=", ".join(file_labels),
        source_kind=source_kind,
        source_counts=source_counts,
    )
    _SNAPSHOT_CACHE = snapshot
    _SNAPSHOT_SIGNATURE = signature
    return snapshot


def load_listings() -> list[Listing]:
    return load_snapshot().items


def filter_listings(filters: ListingFilters) -> list[Listing]:
    listings = load_listings()
    query = filters.search.strip().lower()

    def matches(listing: Listing) -> bool:
        if query:
            haystack = " ".join(
                [
                    listing.title,
                    listing.description,
                    listing.borough,
                    listing.neighborhood,
                    listing.address,
                    listing.property_type,
                    listing.source_label,
                ]
            ).lower()
            if query not in haystack:
                return False

        if filters.sources and listing.source_key not in filters.sources:
            return False
        if filters.boroughs and listing.borough not in filters.boroughs:
            return False
        if filters.neighborhoods and listing.neighborhood not in filters.neighborhoods:
            return False
        if filters.min_price is not None and listing.price < filters.min_price:
            return False
        if filters.max_price is not None and listing.price > filters.max_price:
            return False
        if filters.min_beds is not None and listing.beds < filters.min_beds:
            return False
        if filters.max_beds is not None and listing.beds > filters.max_beds:
            return False
        if filters.min_baths is not None and listing.baths < filters.min_baths:
            return False
        if filters.pet_friendly is True and not listing.pet_friendly:
            return False
        if filters.furnished is True and not listing.furnished:
            return False
        if filters.has_doorman is True and not listing.has_doorman:
            return False
        if filters.has_laundry is True and not listing.has_laundry:
            return False
        if filters.near_subway is True and not listing.near_subway:
            return False
        if filters.allows_guarantors is True and not listing.allows_guarantors:
            return False
        if filters.featured_only is True and not listing.featured:
            return False
        return True

    filtered = [listing for listing in listings if matches(listing)]
    return sort_listings(filtered, filters.sort_by)


def sort_listings(listings: list[Listing], sort_by: str) -> list[Listing]:
    sort_key = sort_by or "featured"

    if sort_key == "price_asc":
        return sorted(listings, key=lambda listing: (listing.price, listing.source_label))
    if sort_key == "price_desc":
        return sorted(listings, key=lambda listing: (-listing.price, listing.source_label))
    if sort_key == "beds_desc":
        return sorted(listings, key=lambda listing: (-listing.beds, listing.price))
    if sort_key == "newest":
        return sorted(listings, key=lambda listing: listing.available_from, reverse=True)

    return sorted(
        listings,
        key=lambda listing: (
            not listing.featured,
            listing.price,
            listing.source_label,
        ),
    )


def get_listing_by_id(listing_id: str) -> Listing | None:
    for listing in load_listings():
        if listing.id == listing_id:
            return listing
    return None


def get_filter_options() -> dict[str, object]:
    snapshot = load_snapshot()
    listings = snapshot.items
    boroughs = sorted({listing.borough for listing in listings})
    neighborhoods = sorted({listing.neighborhood for listing in listings})
    source_keys = sorted({listing.source_key for listing in listings})
    source_labels = {listing.source_key: listing.source_label for listing in listings}
    prices = [listing.price for listing in listings if listing.price is not None]
    beds = [listing.beds for listing in listings]
    baths = [listing.baths for listing in listings]

    return {
        "sources": [{"key": key, "label": source_labels[key]} for key in source_keys],
        "boroughs": boroughs,
        "neighborhoods": neighborhoods,
        "stats": {
            "min_price": min(prices) if prices else 0,
            "max_price": max(prices) if prices else 0,
            "max_beds": int(max(beds)) if beds else 0,
            "max_baths": int(max(baths)) if baths else 0,
            "count": len(listings),
        },
        "source": {
            "kind": snapshot.source_kind,
            "file": snapshot.source_file,
            "breakdown": snapshot.source_counts,
        },
    }


def build_filters(
    *,
    search: str = "",
    source: str | None = None,
    borough: str | None = None,
    neighborhood: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    min_beds: float | None = None,
    max_beds: float | None = None,
    min_baths: float | None = None,
    pet_friendly: bool | None = None,
    furnished: bool | None = None,
    has_doorman: bool | None = None,
    has_laundry: bool | None = None,
    near_subway: bool | None = None,
    allows_guarantors: bool | None = None,
    featured_only: bool | None = None,
    sort_by: str = "featured",
) -> ListingFilters:
    return ListingFilters(
        search=search or "",
        sources=_split_csv_values(source),
        boroughs=_split_csv_values(borough),
        neighborhoods=_split_csv_values(neighborhood),
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


def source_name_for_listing(listing: Listing) -> str:
    host = urlparse(listing.listing_url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if host:
        return f"{listing.source_label} ({host})"
    return listing.source_label
