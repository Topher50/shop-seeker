from src.models import Listing


def test_listing_creation():
    listing = Listing(
        title="Warehouse Space 600sqft",
        price="$1800/mo",
        sqft="600",
        address="123 Folsom St, SF",
        link="https://sfbay.craigslist.org/sfc/off/123.html",
        source="craigslist",
    )
    assert listing.title == "Warehouse Space 600sqft"
    assert listing.link == "https://sfbay.craigslist.org/sfc/off/123.html"
    assert listing.source == "craigslist"


def test_listing_defaults():
    listing = Listing(
        title="Test",
        price="",
        sqft="",
        address="",
        link="https://example.com/1",
        source="craigslist",
    )
    assert listing.lat is None
    assert listing.lng is None
    assert listing.full_text == ""


def test_listing_unique_key_is_link():
    listing = Listing(
        title="Test",
        price="",
        sqft="",
        address="",
        link="https://example.com/1",
        source="craigslist",
    )
    assert listing.unique_key == "https://example.com/1"
