import json
from unittest.mock import MagicMock, patch
from src.reviewer import ReviewResult, review_listing
from src.models import Listing


def _make_listing(**kwargs) -> Listing:
    defaults = {
        "title": "Warehouse Space",
        "price": "$1800/mo",
        "sqft": "600",
        "address": "123 Folsom St, SF",
        "link": "https://example.com/1",
        "source": "craigslist",
        "full_text": "600 sqft warehouse ground floor, roll-up door, 200amp power.",
    }
    defaults.update(kwargs)
    return Listing(**defaults)


def test_review_result_approved():
    r = ReviewResult(
        approved=True,
        est_monthly_cost="$1800",
        suitability_score=8,
        reasoning="Ground floor warehouse with power and roll-up door.",
    )
    assert r.approved is True
    assert r.suitability_score == 8


def test_review_result_rejected():
    r = ReviewResult(
        approved=False,
        est_monthly_cost="$2000",
        suitability_score=2,
        reasoning="3rd floor carpeted office, no freight access.",
    )
    assert r.approved is False


@patch("src.reviewer.anthropic.Anthropic")
def test_review_listing_parses_approved(mock_anthropic_cls):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(
            text=json.dumps(
                {
                    "approved": True,
                    "est_monthly_cost": "$1800",
                    "suitability_score": 8,
                    "reasoning": "Great workshop space.",
                }
            )
        )
    ]
    mock_client.messages.create.return_value = mock_response

    listing = _make_listing()
    result = review_listing(listing, api_key="test-key")

    assert result.approved is True
    assert result.est_monthly_cost == "$1800"
    assert result.suitability_score == 8


@patch("src.reviewer.anthropic.Anthropic")
def test_review_listing_parses_rejected(mock_anthropic_cls):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(
            text=json.dumps(
                {
                    "approved": False,
                    "est_monthly_cost": "$3500",
                    "suitability_score": 1,
                    "reasoning": "Way over budget.",
                }
            )
        )
    ]
    mock_client.messages.create.return_value = mock_response

    listing = _make_listing()
    result = review_listing(listing, api_key="test-key")

    assert result.approved is False
    assert result.reasoning == "Way over budget."


@patch("src.reviewer.anthropic.Anthropic")
def test_review_listing_handles_malformed_json(mock_anthropic_cls):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="not valid json")]
    mock_client.messages.create.return_value = mock_response

    listing = _make_listing()
    result = review_listing(listing, api_key="test-key")

    # Should default to rejected on parse failure
    assert result.approved is False
    assert "parse" in result.reasoning.lower() or "error" in result.reasoning.lower()
