import pathlib
import responses
from src.scrapers.loopnet import LoopNetScraper

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@responses.activate
def test_scrape_returns_listings():
    results_html = (FIXTURES / "loopnet_results.html").read_text()
    responses.get(
        "https://www.loopnet.com/search/commercial-real-estate/san-francisco-ca/for-lease/",
        body=results_html,
        status=200,
    )

    scraper = LoopNetScraper()
    listings = scraper.scrape()

    assert len(listings) >= 1
    for listing in listings:
        assert listing.source == "loopnet"
        assert listing.link.startswith("https://")


@responses.activate
def test_scrape_handles_empty_results():
    responses.get(
        "https://www.loopnet.com/search/commercial-real-estate/san-francisco-ca/for-lease/",
        body="<html><body></body></html>",
        status=200,
    )

    scraper = LoopNetScraper()
    listings = scraper.scrape()
    assert listings == []


@responses.activate
def test_scrape_handles_bot_block():
    responses.get(
        "https://www.loopnet.com/search/commercial-real-estate/san-francisco-ca/for-lease/",
        body="<html><body><div id='sec-if-cpt-container'>captcha</div></body></html>",
        status=200,
    )

    scraper = LoopNetScraper()
    listings = scraper.scrape()
    assert listings == []
