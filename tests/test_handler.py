from unittest.mock import MagicMock, patch
from src.models import Listing


def _make_listing(**kwargs) -> Listing:
    defaults = {
        "title": "Test Space",
        "price": "$1800",
        "sqft": "600",
        "address": "123 Folsom St",
        "link": "https://example.com/1",
        "source": "craigslist",
        "full_text": "A workshop space.",
        "lat": 37.785,
        "lng": -122.395,
    }
    defaults.update(kwargs)
    return Listing(**defaults)


@patch("src.handler.get_secrets")
@patch("src.handler.SheetsClient")
@patch("src.handler.CommercialCafeScraper")
@patch("src.handler.LoopNetScraper")
@patch("src.handler.CraigslistScraper")
@patch("src.handler.review_listing")
def test_handler_skips_seen_urls(mock_review, mock_cl, mock_ln, mock_cc, mock_sheets_cls, mock_secrets):
    from src.handler import lambda_handler

    mock_secrets.return_value = {"google_creds": {}, "anthropic_key": "k"}

    mock_sheets = MagicMock()
    mock_sheets.get_seen_urls.return_value = {"https://example.com/1"}
    mock_sheets_cls.return_value = mock_sheets

    mock_cl.return_value.scrape.return_value = [_make_listing()]
    mock_ln.return_value.scrape.return_value = []
    mock_cc.return_value.scrape.return_value = []

    lambda_handler({}, None)

    mock_review.assert_not_called()
    mock_sheets.append_approved.assert_not_called()
    mock_sheets.append_rejected.assert_not_called()


@patch("src.handler.get_secrets")
@patch("src.handler.SheetsClient")
@patch("src.handler.CommercialCafeScraper")
@patch("src.handler.LoopNetScraper")
@patch("src.handler.CraigslistScraper")
@patch("src.handler.review_listing")
def test_handler_sends_approved_to_sheet(
    mock_review, mock_cl, mock_ln, mock_cc, mock_sheets_cls, mock_secrets
):
    from src.handler import lambda_handler
    from src.reviewer import ReviewResult

    mock_secrets.return_value = {"google_creds": {}, "anthropic_key": "k"}

    mock_sheets = MagicMock()
    mock_sheets.get_seen_urls.return_value = set()
    mock_sheets_cls.return_value = mock_sheets

    mock_cl.return_value.scrape.return_value = [_make_listing()]
    mock_ln.return_value.scrape.return_value = []
    mock_cc.return_value.scrape.return_value = []

    mock_review.return_value = ReviewResult(
        approved=True,
        est_monthly_cost="$1800",
        suitability_score=8,
        reasoning="Great space.",
    )

    lambda_handler({}, None)

    mock_sheets.append_approved.assert_called_once()
    mock_sheets.append_rejected.assert_not_called()


@patch("src.handler.get_secrets")
@patch("src.handler.SheetsClient")
@patch("src.handler.CommercialCafeScraper")
@patch("src.handler.LoopNetScraper")
@patch("src.handler.CraigslistScraper")
@patch("src.handler.review_listing")
def test_handler_sends_rejected_to_sheet(
    mock_review, mock_cl, mock_ln, mock_cc, mock_sheets_cls, mock_secrets
):
    from src.handler import lambda_handler
    from src.reviewer import ReviewResult

    mock_secrets.return_value = {"google_creds": {}, "anthropic_key": "k"}

    mock_sheets = MagicMock()
    mock_sheets.get_seen_urls.return_value = set()
    mock_sheets_cls.return_value = mock_sheets

    mock_cl.return_value.scrape.return_value = [_make_listing()]
    mock_ln.return_value.scrape.return_value = []
    mock_cc.return_value.scrape.return_value = []

    mock_review.return_value = ReviewResult(
        approved=False,
        est_monthly_cost="$3500",
        suitability_score=1,
        reasoning="Over budget.",
    )

    lambda_handler({}, None)

    mock_sheets.append_rejected.assert_called_once()
    mock_sheets.append_approved.assert_not_called()


@patch("src.handler.get_secrets")
@patch("src.handler.SheetsClient")
@patch("src.handler.CommercialCafeScraper")
@patch("src.handler.LoopNetScraper")
@patch("src.handler.CraigslistScraper")
@patch("src.handler.review_listing")
def test_handler_filters_out_of_radius(
    mock_review, mock_cl, mock_ln, mock_cc, mock_sheets_cls, mock_secrets
):
    from src.handler import lambda_handler

    mock_secrets.return_value = {"google_creds": {}, "anthropic_key": "k"}

    mock_sheets = MagicMock()
    mock_sheets.get_seen_urls.return_value = set()
    mock_sheets_cls.return_value = mock_sheets

    # Outer Sunset — outside 4mi radius
    listing = _make_listing(lat=37.7535, lng=-122.5050)
    mock_cl.return_value.scrape.return_value = [listing]
    mock_ln.return_value.scrape.return_value = []
    mock_cc.return_value.scrape.return_value = []

    lambda_handler({}, None)

    # Out of radius but has coordinates, should be skipped
    mock_review.assert_not_called()


@patch("src.handler.get_secrets")
@patch("src.handler.SheetsClient")
@patch("src.handler.CommercialCafeScraper")
@patch("src.handler.LoopNetScraper")
@patch("src.handler.CraigslistScraper")
@patch("src.handler.review_listing")
def test_handler_passes_no_coords_to_claude(
    mock_review, mock_cl, mock_ln, mock_cc, mock_sheets_cls, mock_secrets
):
    from src.handler import lambda_handler
    from src.reviewer import ReviewResult

    mock_secrets.return_value = {"google_creds": {}, "anthropic_key": "k"}

    mock_sheets = MagicMock()
    mock_sheets.get_seen_urls.return_value = set()
    mock_sheets_cls.return_value = mock_sheets

    # No lat/lng — should still go to Claude
    listing = _make_listing(lat=None, lng=None)
    mock_cl.return_value.scrape.return_value = [listing]
    mock_ln.return_value.scrape.return_value = []
    mock_cc.return_value.scrape.return_value = []

    mock_review.return_value = ReviewResult(
        approved=True,
        est_monthly_cost="$1800",
        suitability_score=7,
        reasoning="Location unclear but looks promising.",
    )

    lambda_handler({}, None)

    mock_review.assert_called_once()
