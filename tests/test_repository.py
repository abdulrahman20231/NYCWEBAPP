from nyc_rentals_platform.app.repository import build_filters, filter_listings, get_filter_options, load_snapshot


def test_borough_filter_returns_only_requested_borough() -> None:
    filters = build_filters(borough="Brooklyn")
    listings = filter_listings(filters)
    assert listings
    assert all(listing.borough == "Brooklyn" for listing in listings)


def test_price_and_pet_filter_can_be_combined() -> None:
    filters = build_filters(max_price=4000, pet_friendly=True)
    listings = filter_listings(filters)
    assert listings
    assert all(listing.price <= 4000 and listing.pet_friendly for listing in listings)


def test_filter_options_are_populated() -> None:
    options = get_filter_options()
    assert "Manhattan" in options["boroughs"]
    assert options["stats"]["count"] >= 10


def test_source_filter_returns_requested_source_only() -> None:
    filters = build_filters(source="zillow")
    listings = filter_listings(filters)
    assert listings
    assert all(listing.source_key == "zillow" for listing in listings)


def test_aggregated_snapshot_excludes_zero_price_rows() -> None:
    snapshot = load_snapshot()
    assert snapshot.items
    assert all(listing.price > 0 for listing in snapshot.items)


def test_zillow_listings_do_not_all_share_one_image() -> None:
    zillow_listings = [listing for listing in load_snapshot().items if listing.source_key == "zillow"]
    assert zillow_listings
    assert len({listing.image_url for listing in zillow_listings}) > 1


def test_all_listings_have_coordinates_for_map_rendering() -> None:
    snapshot = load_snapshot()
    assert snapshot.items
    assert all(listing.latitude and listing.longitude for listing in snapshot.items)
