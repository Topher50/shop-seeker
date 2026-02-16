import pathlib
from unittest.mock import patch, MagicMock
from src.scrapers.loopnet import LoopNetScraper

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _make_response(body, status_code=200):
    resp = MagicMock()
    resp.text = body
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return resp


@patch("time.sleep")
@patch("src.scrapers.loopnet.requests.Session")
def test_scrape_returns_listings(MockSession, _mock_sleep):
    results_html = (FIXTURES / "loopnet_results.html").read_text()
    warmup_resp = _make_response("<html></html>")
    search_resp = _make_response(results_html)

    mock_session = MagicMock()
    mock_session.get.side_effect = [warmup_resp, search_resp]
    MockSession.return_value = mock_session

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


@patch("time.sleep")
@patch("src.scrapers.loopnet.requests.Session")
def test_scrape_handles_empty_results(MockSession, _mock_sleep):
    warmup_resp = _make_response("<html></html>")
    search_resp = _make_response("<html><body></body></html>")

    mock_session = MagicMock()
    mock_session.get.side_effect = [warmup_resp, search_resp]
    MockSession.return_value = mock_session

    scraper = LoopNetScraper()
    listings = scraper.scrape()
    assert listings == []


@patch("time.sleep")
@patch("src.scrapers.loopnet.requests.Session")
def test_scrape_handles_bot_block(MockSession, _mock_sleep):
    warmup_resp = _make_response("<html></html>")
    search_resp = _make_response(
        "<html><body><div id='sec-if-cpt-container'>captcha</div></body></html>"
    )

    mock_session = MagicMock()
    mock_session.get.side_effect = [warmup_resp, search_resp]
    MockSession.return_value = mock_session

    scraper = LoopNetScraper()
    listings = scraper.scrape()
    assert listings == []


@patch("time.sleep")
@patch("src.scrapers.loopnet.requests.Session")
def test_scrape_handles_network_error(MockSession, _mock_sleep):
    warmup_resp = _make_response("<html></html>")

    mock_session = MagicMock()
    mock_session.get.side_effect = [warmup_resp, Exception("Connection refused")]
    MockSession.return_value = mock_session

    scraper = LoopNetScraper()
    listings = scraper.scrape()
    assert listings == []
