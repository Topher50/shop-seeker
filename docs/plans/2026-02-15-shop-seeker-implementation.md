# Shop Seeker Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a daily AWS Lambda scraper that finds workshop/commercial spaces on Craigslist, LoopNet, and CommercialCafe, filters them with Claude Haiku, and writes results to a shared Google Sheet.

**Architecture:** Python Lambda triggered by EventBridge cron. Scrapes 3 sites → basic filtering & dedup against Google Sheet → Claude Haiku review → writes approved/rejected listings to separate Sheet tabs. Secrets in AWS Secrets Manager. Deployed via SAM.

**Tech Stack:** Python 3.12, BeautifulSoup4, requests, gspread, anthropic SDK, AWS SAM, Lambda, EventBridge, Secrets Manager

---

### Task 1: Project scaffolding and dependencies

**Files:**
- Create: `src/__init__.py`
- Create: `src/config.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `.gitignore`

**Step 1: Create `.gitignore`**

```gitignore
__pycache__/
*.pyc
.pytest_cache/
.venv/
venv/
.env
*.egg-info/
.aws-sam/
build/
dist/
```

**Step 2: Create `requirements.txt`**

```
beautifulsoup4>=4.12,<5
requests>=2.31,<3
gspread>=6.0,<7
anthropic>=0.40,<1
google-auth>=2.0,<3
```

**Step 3: Create `requirements-dev.txt`**

```
-r requirements.txt
pytest>=8.0,<9
pytest-mock>=3.12,<4
responses>=0.25,<1
```

**Step 4: Create source and test directories**

```bash
mkdir -p src tests
touch src/__init__.py tests/__init__.py
```

**Step 5: Create `src/config.py`**

```python
import os

SEARCH_CONFIG = {
    "center_lat": float(os.environ.get("CENTER_LAT", "37.7767")),
    "center_lng": float(os.environ.get("CENTER_LNG", "-122.4173")),
    "radius_miles": float(os.environ.get("RADIUS_MILES", "4")),
    "max_price": float(os.environ.get("MAX_PRICE", "2400")),
    "min_sqft": float(os.environ.get("MIN_SQFT", "400")),
    "craigslist_region": os.environ.get("CRAIGSLIST_REGION", "sfbay"),
    "sheet_id": os.environ.get("GOOGLE_SHEET_ID", ""),
}
```

**Step 6: Create `tests/conftest.py`**

```python
import os
import pytest

os.environ.setdefault("CENTER_LAT", "37.7767")
os.environ.setdefault("CENTER_LNG", "-122.4173")
os.environ.setdefault("RADIUS_MILES", "4")
os.environ.setdefault("MAX_PRICE", "2400")
os.environ.setdefault("MIN_SQFT", "400")
os.environ.setdefault("CRAIGSLIST_REGION", "sfbay")
os.environ.setdefault("GOOGLE_SHEET_ID", "test-sheet-id")
```

**Step 7: Set up virtual environment and install dependencies**

```bash
python -m venv .venv
source .venv/Scripts/activate  # Windows Git Bash
pip install -r requirements-dev.txt
```

**Step 8: Run pytest to verify setup**

Run: `pytest --co -q`
Expected: "no tests ran" (but no import errors)

**Step 9: Commit**

```bash
git add .gitignore requirements.txt requirements-dev.txt src/ tests/
git commit -m "feat: project scaffolding with dependencies and config"
```

---

### Task 2: Distance filtering module

**Files:**
- Create: `src/geo.py`
- Create: `tests/test_geo.py`

**Step 1: Write the failing tests**

```python
# tests/test_geo.py
from src.geo import is_within_radius, bounding_box


def test_bounding_box_returns_four_floats():
    box = bounding_box(37.7767, -122.4173, 4)
    assert len(box) == 4
    south, north, west, east = box
    assert south < 37.7767 < north
    assert west < -122.4173 < east


def test_bounding_box_radius_approximate():
    """4 miles ~ 0.058 degrees latitude."""
    box = bounding_box(37.7767, -122.4173, 4)
    south, north, west, east = box
    assert abs((north - south) / 2 - 0.058) < 0.005


def test_is_within_radius_inside():
    # SoMa: ~1 mile from 1390 Market
    assert is_within_radius(37.7785, -122.3950, 37.7767, -122.4173, 4) is True


def test_is_within_radius_outside():
    # Outer Sunset: ~5+ miles from 1390 Market
    assert is_within_radius(37.7535, -122.5050, 37.7767, -122.4173, 4) is False


def test_is_within_radius_edge():
    # Bayview: ~3.5 miles, should be inside
    assert is_within_radius(37.7340, -122.3910, 37.7767, -122.4173, 4) is True
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_geo.py -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# src/geo.py
import math


def bounding_box(
    center_lat: float, center_lng: float, radius_miles: float
) -> tuple[float, float, float, float]:
    """Return (south, north, west, east) bounding box."""
    lat_delta = radius_miles / 69.0
    lng_delta = radius_miles / (69.0 * math.cos(math.radians(center_lat)))
    return (
        center_lat - lat_delta,
        center_lat + lat_delta,
        center_lng - lng_delta,
        center_lng + lng_delta,
    )


def is_within_radius(
    lat: float,
    lng: float,
    center_lat: float,
    center_lng: float,
    radius_miles: float,
) -> bool:
    """Check if a point is within radius_miles of center using bounding box."""
    south, north, west, east = bounding_box(center_lat, center_lng, radius_miles)
    return south <= lat <= north and west <= lng <= east
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_geo.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add src/geo.py tests/test_geo.py
git commit -m "feat: add distance filtering with bounding box"
```

---

### Task 3: Listing data model

**Files:**
- Create: `src/models.py`
- Create: `tests/test_models.py`

**Step 1: Write the failing tests**

```python
# tests/test_models.py
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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_models.py -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# src/models.py
from dataclasses import dataclass, field


@dataclass
class Listing:
    title: str
    price: str
    sqft: str
    address: str
    link: str
    source: str
    lat: float | None = None
    lng: float | None = None
    full_text: str = ""

    @property
    def unique_key(self) -> str:
        return self.link
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_models.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add src/models.py tests/test_models.py
git commit -m "feat: add Listing data model"
```

---

### Task 4: Craigslist scraper

**Files:**
- Create: `src/scrapers/__init__.py`
- Create: `src/scrapers/craigslist.py`
- Create: `tests/test_craigslist.py`
- Create: `tests/fixtures/craigslist_results.html`
- Create: `tests/fixtures/craigslist_detail.html`

**Step 1: Create a realistic HTML fixture for Craigslist search results**

Research the live Craigslist search results page structure first, then create `tests/fixtures/craigslist_results.html` with 3 sample listing entries mimicking the real HTML structure. Include a mix: one with price/sqft in range, one out of range, one with ambiguous pricing.

Also create `tests/fixtures/craigslist_detail.html` with a single listing detail page including a full description body.

**Step 2: Write the failing tests**

```python
# tests/test_craigslist.py
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
    # Mock detail pages for each listing found in results
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
        body="<html><body><div class='cl-results-page'></div></body></html>",
        status=200,
    )

    scraper = CraigslistScraper(region="sfbay")
    listings = scraper.scrape()
    assert listings == []
```

**Step 3: Run tests to verify they fail**

Run: `pytest tests/test_craigslist.py -v`
Expected: FAIL with ImportError

**Step 4: Write the scraper implementation**

```python
# src/scrapers/__init__.py
# Scraper package

# src/scrapers/craigslist.py
import time
import random
import logging
from bs4 import BeautifulSoup
import requests
from src.models import Listing

logger = logging.getLogger(__name__)

# Craigslist search categories relevant to workshop/commercial space
SEARCH_PATHS = [
    "/search/san-francisco-ca/off",  # office & commercial
]


class CraigslistScraper:
    BASE_URL = "https://sfbay.craigslist.org"

    def __init__(self, region: str = "sfbay"):
        self.region = region
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "ShopSeeker/1.0 (workshop space finder)"}
        )

    def scrape(self) -> list[Listing]:
        listings = []
        for path in SEARCH_PATHS:
            url = f"{self.BASE_URL}{path}"
            logger.info(f"Scraping {url}")
            try:
                resp = self.session.get(url, timeout=30)
                resp.raise_for_status()
            except requests.RequestException as e:
                logger.error(f"Failed to fetch {url}: {e}")
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            result_items = soup.select("li.cl-static-search-result")

            for item in result_items:
                listing = self._parse_result(item)
                if listing:
                    self._fetch_detail(listing)
                    listings.append(listing)
                    time.sleep(random.uniform(2, 5))

        return listings

    def _parse_result(self, item) -> Listing | None:
        link_tag = item.select_one("a")
        if not link_tag:
            return None

        href = link_tag.get("href", "")
        if not href.startswith("http"):
            href = f"{self.BASE_URL}{href}"

        title = link_tag.get_text(strip=True)
        price_tag = item.select_one(".price")
        price = price_tag.get_text(strip=True) if price_tag else ""

        return Listing(
            title=title,
            price=price,
            sqft="",
            address="",
            link=href,
            source="craigslist",
        )

    def _fetch_detail(self, listing: Listing) -> None:
        try:
            resp = self.session.get(listing.link, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch detail {listing.link}: {e}")
            return

        soup = BeautifulSoup(resp.text, "html.parser")
        body = soup.select_one("#postingbody")
        if body:
            listing.full_text = body.get_text(strip=True)

        # Try to extract address from map or location attributes
        map_tag = soup.select_one("#map")
        if map_tag:
            lat = map_tag.get("data-latitude")
            lng = map_tag.get("data-longitude")
            if lat and lng:
                listing.lat = float(lat)
                listing.lng = float(lng)
```

Note: The HTML selectors above are based on Craigslist's known structure. **During implementation, verify the actual selectors by fetching a live page first and inspecting it.** Craigslist changes its HTML periodically. Adjust selectors as needed.

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_craigslist.py -v`
Expected: All 3 tests PASS (may need to adjust fixture HTML and selectors to match)

**Step 6: Commit**

```bash
git add src/scrapers/ tests/test_craigslist.py tests/fixtures/
git commit -m "feat: add Craigslist scraper"
```

---

### Task 5: LoopNet scraper

**Files:**
- Create: `src/scrapers/loopnet.py`
- Create: `tests/test_loopnet.py`
- Create: `tests/fixtures/loopnet_results.html`

**Step 1: Research LoopNet's page structure**

Fetch a live LoopNet search page for SF commercial for lease. Examine the HTML to determine if results are in static HTML or loaded via JS/API. Check for any API endpoints in network requests. Document the selectors or API format found.

**Step 2: Create a realistic HTML/JSON fixture**

Based on research, create `tests/fixtures/loopnet_results.html` (or `.json` if an API endpoint is found).

**Step 3: Write the failing tests**

Follow the same pattern as Task 4: test that the scraper returns `Listing` objects with correct `source="loopnet"`, titles, and links. Test empty results. Test that addresses/sqft are extracted when available.

```python
# tests/test_loopnet.py
import pathlib
import responses
from src.scrapers.loopnet import LoopNetScraper

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@responses.activate
def test_scrape_returns_listings():
    # Mock based on discovered URL structure
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
```

**Step 4: Run tests to verify they fail**

Run: `pytest tests/test_loopnet.py -v`
Expected: FAIL

**Step 5: Write the scraper implementation**

Follow the same pattern as CraigslistScraper. Class `LoopNetScraper` with a `scrape()` method returning `list[Listing]`. Adjust selectors based on research in Step 1.

If LoopNet blocks scraping (common), implement a stub that logs a warning and returns `[]`, with a TODO for future approach (email alerts, API access, etc.).

**Step 6: Run tests to verify they pass**

Run: `pytest tests/test_loopnet.py -v`
Expected: All tests PASS

**Step 7: Commit**

```bash
git add src/scrapers/loopnet.py tests/test_loopnet.py tests/fixtures/loopnet_results.html
git commit -m "feat: add LoopNet scraper"
```

---

### Task 6: CommercialCafe scraper

**Files:**
- Create: `src/scrapers/commercialcafe.py`
- Create: `tests/test_commercialcafe.py`
- Create: `tests/fixtures/commercialcafe_results.html`

Follow the exact same approach as Task 5. Research the site, create fixtures, write failing tests, implement, verify, commit.

```bash
git commit -m "feat: add CommercialCafe scraper"
```

---

### Task 7: Google Sheets integration

**Files:**
- Create: `src/sheets.py`
- Create: `tests/test_sheets.py`

**Step 1: Write the failing tests**

```python
# tests/test_sheets.py
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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_sheets.py -v`
Expected: FAIL

**Step 3: Write the implementation**

```python
# src/sheets.py
import gspread

LINK_COL = 5  # Column E = Link


class SheetsClient:
    def __init__(self, credentials_dict: dict, sheet_id: str):
        gc = gspread.service_account_from_dict(credentials_dict)
        self.spreadsheet = gc.open_by_key(sheet_id)

    def get_seen_urls(self) -> set[str]:
        urls = set()
        for tab_name in ("Approved", "Rejected"):
            ws = self.spreadsheet.worksheet(tab_name)
            col = ws.col_values(LINK_COL)
            urls.update(url for url in col[1:] if url)  # skip header
        return urls

    def append_approved(
        self,
        title: str,
        price: str,
        sqft: str,
        address: str,
        link: str,
        date_found: str,
        est_monthly_cost: str,
        suitability_score: str,
        ai_notes: str,
    ) -> None:
        ws = self.spreadsheet.worksheet("Approved")
        row = [
            title, price, sqft, address, link, date_found,
            est_monthly_cost, suitability_score, ai_notes,
            "", "", "",  # Followed Up?, Who, Notes (human columns)
        ]
        ws.append_row(row)

    def append_rejected(
        self,
        title: str,
        price: str,
        sqft: str,
        address: str,
        link: str,
        date_found: str,
        est_monthly_cost: str,
        suitability_score: str,
        rejection_reason: str,
    ) -> None:
        ws = self.spreadsheet.worksheet("Rejected")
        row = [
            title, price, sqft, address, link, date_found,
            est_monthly_cost, suitability_score, rejection_reason,
            "", "",  # Reviewed By, Notes (human columns)
        ]
        ws.append_row(row)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_sheets.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add src/sheets.py tests/test_sheets.py
git commit -m "feat: add Google Sheets integration"
```

---

### Task 8: Claude API review module

**Files:**
- Create: `src/reviewer.py`
- Create: `tests/test_reviewer.py`

**Step 1: Write the failing tests**

```python
# tests/test_reviewer.py
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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_reviewer.py -v`
Expected: FAIL

**Step 3: Write the implementation**

```python
# src/reviewer.py
import json
import logging
from dataclasses import dataclass
import anthropic
from src.models import Listing

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You evaluate commercial/warehouse space listings for suitability as a hobby carpentry workshop for 3 people.

Criteria:
- Budget: up to $2,400/month
- Minimum usable space: 400 sqft
- Must be suitable for woodworking: ground floor or freight elevator access preferred, not a carpeted office, adequate power, ventilation is a plus
- Located in or near San Francisco

Your job:
1. Parse the TRUE monthly cost from the listing (handle $/sqft pricing, ranges, negotiable terms, etc.)
2. Estimate usable square footage
3. Assess suitability for a carpentry workshop (score 1-10)
4. Decide: approved (worth contacting) or rejected (clearly unsuitable)

Respond with ONLY valid JSON:
{
    "approved": true/false,
    "est_monthly_cost": "$X,XXX",
    "suitability_score": 1-10,
    "reasoning": "Brief explanation"
}"""


@dataclass
class ReviewResult:
    approved: bool
    est_monthly_cost: str
    suitability_score: int
    reasoning: str


def review_listing(listing: Listing, api_key: str) -> ReviewResult:
    client = anthropic.Anthropic(api_key=api_key)

    user_content = f"""Title: {listing.title}
Listed Price: {listing.price}
Listed Sqft: {listing.sqft}
Address: {listing.address}
Source: {listing.source}

Full listing text:
{listing.full_text}"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )

        raw = response.content[0].text
        data = json.loads(raw)

        return ReviewResult(
            approved=bool(data["approved"]),
            est_monthly_cost=str(data.get("est_monthly_cost", "Unknown")),
            suitability_score=int(data.get("suitability_score", 0)),
            reasoning=str(data.get("reasoning", "")),
        )
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.error(f"Failed to parse Claude response: {e}")
        return ReviewResult(
            approved=False,
            est_monthly_cost="Unknown",
            suitability_score=0,
            reasoning=f"Error parsing Claude response: {e}",
        )
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_reviewer.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add src/reviewer.py tests/test_reviewer.py
git commit -m "feat: add Claude API review module"
```

---

### Task 9: Lambda handler (orchestrator)

**Files:**
- Create: `src/handler.py`
- Create: `tests/test_handler.py`

**Step 1: Write the failing tests**

```python
# tests/test_handler.py
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
@patch("src.handler.CraigslistScraper")
@patch("src.handler.review_listing")
def test_handler_skips_seen_urls(mock_review, mock_cl, mock_sheets_cls, mock_secrets):
    from src.handler import lambda_handler
    from src.reviewer import ReviewResult

    mock_secrets.return_value = {"google_creds": {}, "anthropic_key": "k"}

    mock_sheets = MagicMock()
    mock_sheets.get_seen_urls.return_value = {"https://example.com/1"}
    mock_sheets_cls.return_value = mock_sheets

    mock_cl.return_value.scrape.return_value = [_make_listing()]

    lambda_handler({}, None)

    mock_review.assert_not_called()
    mock_sheets.append_approved.assert_not_called()
    mock_sheets.append_rejected.assert_not_called()


@patch("src.handler.get_secrets")
@patch("src.handler.SheetsClient")
@patch("src.handler.CraigslistScraper")
@patch("src.handler.review_listing")
def test_handler_sends_approved_to_sheet(
    mock_review, mock_cl, mock_sheets_cls, mock_secrets
):
    from src.handler import lambda_handler
    from src.reviewer import ReviewResult

    mock_secrets.return_value = {"google_creds": {}, "anthropic_key": "k"}

    mock_sheets = MagicMock()
    mock_sheets.get_seen_urls.return_value = set()
    mock_sheets_cls.return_value = mock_sheets

    mock_cl.return_value.scrape.return_value = [_make_listing()]

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
@patch("src.handler.CraigslistScraper")
@patch("src.handler.review_listing")
def test_handler_sends_rejected_to_sheet(
    mock_review, mock_cl, mock_sheets_cls, mock_secrets
):
    from src.handler import lambda_handler
    from src.reviewer import ReviewResult

    mock_secrets.return_value = {"google_creds": {}, "anthropic_key": "k"}

    mock_sheets = MagicMock()
    mock_sheets.get_seen_urls.return_value = set()
    mock_sheets_cls.return_value = mock_sheets

    mock_cl.return_value.scrape.return_value = [_make_listing()]

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
@patch("src.handler.CraigslistScraper")
@patch("src.handler.review_listing")
def test_handler_filters_out_of_radius(
    mock_review, mock_cl, mock_sheets_cls, mock_secrets
):
    from src.handler import lambda_handler

    mock_secrets.return_value = {"google_creds": {}, "anthropic_key": "k"}

    mock_sheets = MagicMock()
    mock_sheets.get_seen_urls.return_value = set()
    mock_sheets_cls.return_value = mock_sheets

    # Outer Sunset — outside 4mi radius
    listing = _make_listing(lat=37.7535, lng=-122.5050)
    mock_cl.return_value.scrape.return_value = [listing]

    lambda_handler({}, None)

    # Out of radius but has coordinates, should be skipped
    mock_review.assert_not_called()


@patch("src.handler.get_secrets")
@patch("src.handler.SheetsClient")
@patch("src.handler.CraigslistScraper")
@patch("src.handler.review_listing")
def test_handler_passes_no_coords_to_claude(
    mock_review, mock_cl, mock_sheets_cls, mock_secrets
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

    mock_review.return_value = ReviewResult(
        approved=True,
        est_monthly_cost="$1800",
        suitability_score=7,
        reasoning="Location unclear but looks promising.",
    )

    lambda_handler({}, None)

    mock_review.assert_called_once()
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_handler.py -v`
Expected: FAIL

**Step 3: Write the implementation**

```python
# src/handler.py
import json
import logging
from datetime import date
import boto3
from src.config import SEARCH_CONFIG
from src.geo import is_within_radius
from src.models import Listing
from src.scrapers.craigslist import CraigslistScraper
from src.scrapers.loopnet import LoopNetScraper
from src.scrapers.commercialcafe import CommercialCafeScraper
from src.sheets import SheetsClient
from src.reviewer import review_listing

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_secrets() -> dict:
    client = boto3.client("secretsmanager")

    google_resp = client.get_secret_value(SecretId="shop-seeker/google-creds")
    google_creds = json.loads(google_resp["SecretString"])

    anthropic_resp = client.get_secret_value(SecretId="shop-seeker/anthropic-key")
    anthropic_key = json.loads(anthropic_resp["SecretString"])["api_key"]

    return {"google_creds": google_creds, "anthropic_key": anthropic_key}


def lambda_handler(event, context):
    logger.info("Shop Seeker run starting")

    secrets = get_secrets()
    sheets = SheetsClient(
        credentials_dict=secrets["google_creds"],
        sheet_id=SEARCH_CONFIG["sheet_id"],
    )

    # Step 1: Get already-seen URLs
    seen_urls = sheets.get_seen_urls()
    logger.info(f"Found {len(seen_urls)} previously seen URLs")

    # Step 2: Scrape all sources
    all_listings: list[Listing] = []

    cl = CraigslistScraper(region=SEARCH_CONFIG["craigslist_region"])
    all_listings.extend(cl.scrape())

    ln = LoopNetScraper()
    all_listings.extend(ln.scrape())

    cc = CommercialCafeScraper()
    all_listings.extend(cc.scrape())

    logger.info(f"Scraped {len(all_listings)} total listings")

    # Step 3: Filter
    new_listings = [l for l in all_listings if l.unique_key not in seen_urls]
    logger.info(f"{len(new_listings)} new listings after dedup")

    candidates = []
    for listing in new_listings:
        if listing.lat is not None and listing.lng is not None:
            if not is_within_radius(
                listing.lat,
                listing.lng,
                SEARCH_CONFIG["center_lat"],
                SEARCH_CONFIG["center_lng"],
                SEARCH_CONFIG["radius_miles"],
            ):
                logger.info(f"Skipping out-of-radius: {listing.title}")
                continue
        candidates.append(listing)

    logger.info(f"{len(candidates)} candidates for Claude review")

    # Step 4: Claude review and write to sheets
    today = date.today().isoformat()
    approved_count = 0
    rejected_count = 0

    for listing in candidates:
        result = review_listing(listing, api_key=secrets["anthropic_key"])

        if result.approved:
            sheets.append_approved(
                title=listing.title,
                price=listing.price,
                sqft=listing.sqft,
                address=listing.address,
                link=listing.link,
                date_found=today,
                est_monthly_cost=result.est_monthly_cost,
                suitability_score=str(result.suitability_score),
                ai_notes=result.reasoning,
            )
            approved_count += 1
        else:
            sheets.append_rejected(
                title=listing.title,
                price=listing.price,
                sqft=listing.sqft,
                address=listing.address,
                link=listing.link,
                date_found=today,
                est_monthly_cost=result.est_monthly_cost,
                suitability_score=str(result.suitability_score),
                rejection_reason=result.reasoning,
            )
            rejected_count += 1

    logger.info(
        f"Done. Approved: {approved_count}, Rejected: {rejected_count}"
    )

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "scraped": len(all_listings),
                "new": len(new_listings),
                "candidates": len(candidates),
                "approved": approved_count,
                "rejected": rejected_count,
            }
        ),
    }
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_handler.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add src/handler.py tests/test_handler.py
git commit -m "feat: add Lambda handler orchestrator"
```

---

### Task 10: SAM template and deployment config

**Files:**
- Create: `template.yaml`
- Create: `samconfig.toml`

**Step 1: Create `template.yaml`**

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: Shop Seeker - Workshop space finder

Globals:
  Function:
    Timeout: 300
    Runtime: python3.12
    MemorySize: 256

Parameters:
  GoogleSheetId:
    Type: String
    Description: Google Sheet ID for results
  CenterLat:
    Type: String
    Default: "37.7767"
  CenterLng:
    Type: String
    Default: "-122.4173"
  RadiusMiles:
    Type: String
    Default: "4"
  MaxPrice:
    Type: String
    Default: "2400"
  MinSqft:
    Type: String
    Default: "400"
  CraigslistRegion:
    Type: String
    Default: "sfbay"

Resources:
  ShopSeekerFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: .
      Handler: src.handler.lambda_handler
      Environment:
        Variables:
          GOOGLE_SHEET_ID: !Ref GoogleSheetId
          CENTER_LAT: !Ref CenterLat
          CENTER_LNG: !Ref CenterLng
          RADIUS_MILES: !Ref RadiusMiles
          MAX_PRICE: !Ref MaxPrice
          MIN_SQFT: !Ref MinSqft
          CRAIGSLIST_REGION: !Ref CraigslistRegion
      Policies:
        - Version: '2012-10-17'
          Statement:
            - Effect: Allow
              Action:
                - secretsmanager:GetSecretValue
              Resource:
                - !Sub "arn:aws:secretsmanager:${AWS::Region}:${AWS::AccountId}:secret:shop-seeker/*"
      Events:
        DailySchedule:
          Type: Schedule
          Properties:
            Schedule: cron(0 14 * * ? *)
            Description: Run Shop Seeker daily at 6am PT
            Enabled: true

Outputs:
  ShopSeekerFunction:
    Description: Lambda function ARN
    Value: !GetAtt ShopSeekerFunction.Arn
```

**Step 2: Create `samconfig.toml`**

```toml
version = 0.1

[default.deploy.parameters]
stack_name = "shop-seeker"
resolve_s3 = true
s3_prefix = "shop-seeker"
region = "us-west-2"
confirm_changeset = true
capabilities = "CAPABILITY_IAM"
parameter_overrides = "GoogleSheetId=\"YOUR_SHEET_ID_HERE\""
```

**Step 3: Validate the template**

Run: `sam validate`
Expected: Template is valid

**Step 4: Commit**

```bash
git add template.yaml samconfig.toml
git commit -m "feat: add SAM template and deployment config"
```

---

### Task 11: Run full test suite and final cleanup

**Step 1: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests PASS

**Step 2: Verify project structure**

```
shop-seeker/
├── docs/plans/
│   ├── 2026-02-15-shop-seeker-design.md
│   └── 2026-02-15-shop-seeker-implementation.md
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── geo.py
│   ├── handler.py
│   ├── models.py
│   ├── reviewer.py
│   ├── sheets.py
│   └── scrapers/
│       ├── __init__.py
│       ├── craigslist.py
│       ├── loopnet.py
│       └── commercialcafe.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── fixtures/
│   │   ├── craigslist_results.html
│   │   ├── craigslist_detail.html
│   │   ├── loopnet_results.html
│   │   └── commercialcafe_results.html
│   ├── test_geo.py
│   ├── test_models.py
│   ├── test_craigslist.py
│   ├── test_loopnet.py
│   ├── test_commercialcafe.py
│   ├── test_sheets.py
│   ├── test_reviewer.py
│   └── test_handler.py
├── template.yaml
├── samconfig.toml
├── requirements.txt
├── requirements-dev.txt
├── .gitignore
└── CLAUDE.md
```

**Step 3: Final commit**

```bash
git add -A
git commit -m "chore: final cleanup and verify project structure"
```

---

### Task 12: Manual setup steps (post-deployment)

These are manual steps the user must complete — not automatable:

1. **GCP Service Account:**
   - Create GCP project, enable Google Sheets API
   - Create service account, download JSON key
   - Store JSON key in AWS Secrets Manager as `shop-seeker/google-creds`

2. **Anthropic API Key:**
   - Get API key from console.anthropic.com
   - Store in AWS Secrets Manager as `shop-seeker/anthropic-key` with format `{"api_key": "sk-ant-..."}`

3. **Google Sheet:**
   - Create a new Google Sheet
   - Share it with the service account email (Editor access)
   - Create two tabs: "Approved" and "Rejected"
   - Add header rows matching the column definitions in the design doc
   - Copy the Sheet ID from the URL and update `samconfig.toml`

4. **Deploy:**
   ```bash
   sam build
   sam deploy
   ```

5. **Test manually:**
   ```bash
   sam remote invoke ShopSeekerFunction --stack-name shop-seeker
   ```
