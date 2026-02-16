import logging
import time
from bs4 import BeautifulSoup
from curl_cffi import requests
from src.models import Listing

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.commercialcafe.com/commercial-real-estate/us/ca/san-francisco/?ListingType=Lease"


class CommercialCafeScraper:
    def __init__(self):
        self.session = requests.Session(impersonate="chrome136", timeout=30)

    def _warmup(self):
        """Hit the homepage to establish cookies before searching."""
        try:
            self.session.get("https://www.commercialcafe.com")
        except Exception:
            pass

    def scrape(self) -> list[Listing]:
        logger.info(f"Scraping {SEARCH_URL}")
        self._warmup()
        try:
            resp = self.session.get(SEARCH_URL)
            resp.raise_for_status()
        except Exception as e:
            logger.warning(f"CommercialCafe blocked or failed: {e}")
            return []

        time.sleep(3)

        soup = BeautifulSoup(resp.text, "html.parser")

        listings = []
        for card in soup.select("li.property-details"):
            listing = self._parse_card(card)
            if listing:
                listings.append(listing)

        logger.info(f"Found {len(listings)} CommercialCafe listings")
        return listings

    def _parse_card(self, card) -> Listing | None:
        link_tag = card.select_one("h2.building-name a")
        if not link_tag:
            return None

        href = link_tag.get("href", "")
        if not href.startswith("http"):
            href = f"https://www.commercialcafe.com{href}"

        title = link_tag.get_text(strip=True)

        addr_tag = card.select_one(".building-address")
        address = addr_tag.get_text(strip=True) if addr_tag else ""

        price_tag = card.select_one(".price span")
        price = price_tag.get_text(strip=True) if price_tag else ""

        sqft = ""
        availability_items = card.select(".availability li")
        for item in availability_items:
            text = item.get_text(strip=True)
            if "sqft" in text.lower():
                sqft = text
                break

        return Listing(
            title=title,
            price=price,
            sqft=sqft,
            address=address,
            link=href,
            source="commercialcafe",
        )
