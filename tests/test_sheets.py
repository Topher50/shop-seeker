from unittest.mock import MagicMock, patch
from src.sheets import SheetsClient

APPROVED_HEADERS = [
    "Title", "Price", "Sqft", "Address/Neighborhood", "Link",
    "Date Found", "Est. Monthly Cost", "Suitability Score",
    "AI Notes", "Followed Up?", "Who", "Notes",
]

REJECTED_HEADERS = [
    "Title", "Price", "Sqft", "Address/Neighborhood", "Link",
    "Date Found", "Est. Monthly Cost", "Suitability Score",
    "Rejection Reason", "Reviewed By", "Notes",
]


@patch("src.sheets.gspread.service_account_from_dict")
def test_get_seen_urls_returns_set(mock_auth):
    mock_sheet = MagicMock()
    mock_approved = MagicMock()
    mock_rejected = MagicMock()

    mock_approved.col_values.return_value = [
        "Link", "https://example.com/1", "https://example.com/2"
    ]
    mock_rejected.col_values.return_value = [
        "Link", "https://example.com/3"
    ]

    mock_sheet.worksheet.side_effect = lambda name: {
        "Approved": mock_approved,
        "Rejected": mock_rejected,
    }[name]

    mock_auth.return_value.open_by_key.return_value = mock_sheet

    client = SheetsClient(credentials_dict={}, sheet_id="test")
    seen = client.get_seen_urls()

    assert seen == {
        "https://example.com/1",
        "https://example.com/2",
        "https://example.com/3",
    }


@patch("src.sheets.gspread.service_account_from_dict")
def test_append_approved(mock_auth):
    mock_sheet = MagicMock()
    mock_approved = MagicMock()
    mock_sheet.worksheet.return_value = mock_approved
    mock_auth.return_value.open_by_key.return_value = mock_sheet

    client = SheetsClient(credentials_dict={}, sheet_id="test")
    client.append_approved(
        title="Warehouse",
        price="$1800",
        sqft="600",
        address="123 Folsom St",
        link="https://example.com/1",
        date_found="2026-02-15",
        est_monthly_cost="$1800",
        suitability_score="8",
        ai_notes="Good space for woodworking",
    )

    mock_approved.append_row.assert_called_once()
    row = mock_approved.append_row.call_args[0][0]
    assert row[0] == "Warehouse"
    assert row[4] == "https://example.com/1"
    assert len(row) == len(APPROVED_HEADERS)


@patch("src.sheets.gspread.service_account_from_dict")
def test_append_rejected(mock_auth):
    mock_sheet = MagicMock()
    mock_rejected = MagicMock()
    mock_sheet.worksheet.return_value = mock_rejected
    mock_auth.return_value.open_by_key.return_value = mock_sheet

    client = SheetsClient(credentials_dict={}, sheet_id="test")
    client.append_rejected(
        title="Office Suite",
        price="$2000",
        sqft="500",
        address="456 Market St",
        link="https://example.com/2",
        date_found="2026-02-15",
        est_monthly_cost="$2000",
        suitability_score="2",
        rejection_reason="Carpeted office, no ventilation",
    )

    mock_rejected.append_row.assert_called_once()
    row = mock_rejected.append_row.call_args[0][0]
    assert row[0] == "Office Suite"
    assert row[8] == "Carpeted office, no ventilation"
    assert len(row) == len(REJECTED_HEADERS)
