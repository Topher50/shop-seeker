import logging
import re
import time
from bs4 import BeautifulSoup
from curl_cffi import requests
from src.models import Listing

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.loopnet.com/search/commercial-real-estate/san-francisco-ca/for-lease/"


class LoopNetScraper:
    def __init__(self):
        self.session = requests.Session(impersonate="chrome136", timeout=30)

    def _warmup(self):
        """Hit the homepage to establish cookies before searching."""
        try:
            self.session.get("https://www.loopnet.com")
        except Exception:
            pass

    def scrape(self) -> list[Listing]:
        logger.info(f"Scraping {SEARCH_URL}")
        self._warmup()
        try:
            resp = self.session.get(SEARCH_URL)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch {SEARCH_URL}: {e}")
            return []

        time.sleep(3)

        soup = BeautifulSoup(resp.text, "html.parser")

        # LoopNet uses Akamai bot protection; detect and bail out gracefully
        if soup.select_one("#sec-if-cpt-container"):
            logger.warning("LoopNet returned bot challenge page, skipping")
            return []

        listings = []
        for card in soup.select("article.placard"):
            listing = self._parse_card(card)
            if listing:
                listings.append(listing)

        logger.info(f"Found {len(listings)} LoopNet listings")
        return listings

    def _parse_card(self, card) -> Listing | None:
        title_tag = card.select_one("header h4 a")
        if not title_tag:
            return None

        title = title_tag.get_text(strip=True)
        href = title_tag.get("href", "")
        if not href.startswith("http"):
            href = f"https://www.loopnet.com{href}"

        # Address from subtitle-beta link
        addr_tag = card.select_one("header a.subtitle-beta")
        address = addr_tag.get_text(strip=True) if addr_tag else ""

        # Data points: price from li[name="Price"], sqft from text pattern
        price = ""
        sqft = ""
        for li in card.select("ul.data-points-2c li"):
            name_attr = li.get("name")
            text = li.get_text(strip=True)
            if name_attr == "Price":
                if text.lower() not in ("upon request", "negotiable", "call for pricing"):
                    price = text
            elif re.search(r"\d+[\d,]*\s*SF", text, re.IGNORECASE):
                sqft = text

        return Listing(
            title=title,
            price=price,
            sqft=sqft,
            address=address,
            link=href,
            source="loopnet",
        )
