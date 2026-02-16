import time
import random
import logging
from bs4 import BeautifulSoup
import requests
from src.models import Listing

logger = logging.getLogger(__name__)

SEARCH_PATHS = [
    "/search/san-francisco-ca/off",
]

MAX_DETAIL_FETCHES = 50


class CraigslistScraper:
    BASE_URL = "https://sfbay.craigslist.org"

    def __init__(self, region: str = "sfbay", max_price: int | None = None):
        self.region = region
        self.max_price = max_price
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "ShopSeeker/1.0 (workshop space finder)"}
        )

    def scrape(self) -> list[Listing]:
        listings = []
        detail_count = 0
        for path in SEARCH_PATHS:
            url = f"{self.BASE_URL}{path}"
            params = {}
            if self.max_price:
                params["max_price"] = self.max_price
            logger.info(f"Scraping {url} params={params}")
            try:
                resp = self.session.get(url, params=params, timeout=30)
                resp.raise_for_status()
            except requests.RequestException as e:
                logger.error(f"Failed to fetch {url}: {e}")
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            result_items = soup.select("li.cl-static-search-result")
            logger.info(f"Found {len(result_items)} search results")

            for item in result_items:
                listing = self._parse_result(item)
                if listing:
                    if detail_count < MAX_DETAIL_FETCHES:
                        self._fetch_detail(listing)
                        detail_count += 1
                        time.sleep(random.uniform(1, 2))
                    listings.append(listing)

        return listings

    def _parse_result(self, item) -> Listing | None:
        link_tag = item.select_one("a")
        if not link_tag:
            return None

        href = link_tag.get("href", "")
        if not href.startswith("http"):
            href = f"{self.BASE_URL}{href}"

        title_tag = item.select_one(".title")
        title = title_tag.get_text(strip=True) if title_tag else link_tag.get_text(strip=True)

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

        map_tag = soup.select_one("#map")
        if map_tag:
            lat = map_tag.get("data-latitude")
            lng = map_tag.get("data-longitude")
            if lat and lng:
                listing.lat = float(lat)
                listing.lng = float(lng)

        addr_tag = soup.select_one(".mapaddress")
        if addr_tag:
            listing.address = addr_tag.get_text(strip=True)
