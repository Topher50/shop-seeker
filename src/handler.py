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
