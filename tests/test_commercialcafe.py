import pathlib
import responses
from src.scrapers.commercialcafe import CommercialCafeScraper

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@responses.activate
def test_scrape_returns_listings():
    results_html = (FIXTURES / "commercialcafe_results.html").read_text()
    responses.get(
        "https://www.commercialcafe.com/commercial-real-estate/us/ca/san-francisco/?ListingType=Lease",
        body=results_html,
        status=200,
    )

    scraper = CommercialCafeScraper()
    listings = scraper.scrape()

    assert len(listings) >= 1
    for listing in listings:
        assert listing.source == "commercialcafe"
        assert listing.link.startswith("https://")


@responses.activate
def test_scrape_handles_empty_results():
    responses.get(
        "https://www.commercialcafe.com/commercial-real-estate/us/ca/san-francisco/?ListingType=Lease",
        body="<html><body></body></html>",
        status=200,
    )

    scraper = CommercialCafeScraper()
    listings = scraper.scrape()
    assert listings == []


@responses.activate
def test_scrape_handles_cloudflare_block():
    responses.get(
        "https://www.commercialcafe.com/commercial-real-estate/us/ca/san-francisco/?ListingType=Lease",
        body='<html><head><title>Just a moment...</title></head><body></body></html>',
        status=403,
    )

    scraper = CommercialCafeScraper()
    listings = scraper.scrape()
    assert listings == []
