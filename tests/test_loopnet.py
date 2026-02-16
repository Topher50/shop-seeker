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

    assert len(listings) == 2
    for listing in listings:
        assert listing.source == "loopnet"
        assert listing.link.startswith("https://")
        assert listing.title != ""

    assert listings[0].title == "Industrial Warehouse"
    assert listings[0].address == "100 Mission St, San Francisco, CA 94105"
    assert listings[0].price == "$2,000/mo"
    assert listings[0].sqft == "800 SF"

    assert listings[1].title == "Flex Space with Loading Dock"
    assert listings[1].price == "$1,500/mo"
    assert listings[1].sqft == "500 SF"


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
