import pathlib
import responses
from src.scrapers.craigslist import CraigslistScraper

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@responses.activate
def test_scrape_returns_listings():
    results_html = (FIXTURES / "craigslist_results.html").read_text()
    detail_html = (FIXTURES / "craigslist_detail.html").read_text()

    responses.get(
        "https://sfbay.craigslist.org/search/san-francisco-ca/off",
        body=results_html,
        status=200,
    )
    responses.get(
        "https://sfbay.craigslist.org/sfc/off/d/warehouse-space/1111.html",
        body=detail_html,
        status=200,
    )
    responses.get(
        "https://sfbay.craigslist.org/sfc/off/d/workshop-loft/2222.html",
        body=detail_html,
        status=200,
    )
    responses.get(
        "https://sfbay.craigslist.org/sfc/off/d/office-suite/3333.html",
        body=detail_html,
        status=200,
    )

    scraper = CraigslistScraper(region="sfbay")
    listings = scraper.scrape()

    assert len(listings) >= 1
    for listing in listings:
        assert listing.source == "craigslist"
        assert listing.link.startswith("https://")
        assert listing.title != ""


@responses.activate
def test_scrape_populates_full_text():
    results_html = (FIXTURES / "craigslist_results.html").read_text()
    detail_html = (FIXTURES / "craigslist_detail.html").read_text()

    responses.get(
        "https://sfbay.craigslist.org/search/san-francisco-ca/off",
        body=results_html,
        status=200,
    )
    responses.get(
        "https://sfbay.craigslist.org/sfc/off/d/warehouse-space/1111.html",
        body=detail_html,
        status=200,
    )
    responses.get(
        "https://sfbay.craigslist.org/sfc/off/d/workshop-loft/2222.html",
        body=detail_html,
        status=200,
    )
    responses.get(
        "https://sfbay.craigslist.org/sfc/off/d/office-suite/3333.html",
        body=detail_html,
        status=200,
    )

    scraper = CraigslistScraper(region="sfbay")
    listings = scraper.scrape()

    assert any(listing.full_text != "" for listing in listings)


@responses.activate
def test_scrape_handles_empty_results():
    responses.get(
        "https://sfbay.craigslist.org/search/san-francisco-ca/off",
        body="<html><body><ol class='cl-static-search-results'></ol></body></html>",
        status=200,
    )

    scraper = CraigslistScraper(region="sfbay")
    listings = scraper.scrape()
    assert listings == []
