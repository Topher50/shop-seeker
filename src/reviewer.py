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
