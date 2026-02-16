import logging
from bs4 import BeautifulSoup
import requests
from src.models import Listing

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.commercialcafe.com/commercial-real-estate/us/ca/san-francisco/?ListingType=Lease"

# NOTE: CommercialCafe uses Cloudflare bot protection and will return 403
# for automated requests. In practice, scrape() will catch the 403 and
# return []. Selectors below are based on a Wayback Machine snapshot and
# may need updating if CommercialCafe changes their markup.
# TODO: Verify selectors with browser DevTools or switch to an alternative
# data source (e.g., CommercialCafe email alerts, Yardi API).


class CommercialCafeScraper:
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
            logger.warning(f"CommercialCafe blocked or failed: {e}")
            return []

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
