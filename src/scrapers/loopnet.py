import logging
from bs4 import BeautifulSoup
import requests
from src.models import Listing

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.loopnet.com/search/commercial-real-estate/san-francisco-ca/for-lease/"


# NOTE: LoopNet uses Akamai bot protection and will almost always return
# a challenge page instead of real results. The selectors below are based
# on LoopNet's known "placard" terminology but are unverified against the
# live site. In practice, scrape() will detect the bot challenge and return [].
# TODO: Verify selectors with browser DevTools or switch to an alternative
# data source (e.g., LoopNet email alerts, API access).


class LoopNetScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )

    def scrape(self) -> list[Listing]:
        logger.info(f"Scraping {SEARCH_URL}")
        try:
            resp = self.session.get(SEARCH_URL, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch {SEARCH_URL}: {e}")
            return []

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
        link_tag = card.select_one("a")
        if not link_tag:
            return None

        href = link_tag.get("href", "")
        if not href.startswith("http"):
            href = f"https://www.loopnet.com{href}"

        title_tag = card.select_one("h4")
        title = title_tag.get_text(strip=True) if title_tag else ""

        data_points = card.select(".data-points-2c-value")
        price = data_points[0].get_text(strip=True) if len(data_points) > 0 else ""
        sqft = data_points[1].get_text(strip=True) if len(data_points) > 1 else ""

        addr_tag = card.select_one(".placard-carousel-address")
        address = addr_tag.get_text(strip=True) if addr_tag else ""

        return Listing(
            title=title,
            price=price,
            sqft=sqft,
            address=address,
            link=href,
            source="loopnet",
        )
