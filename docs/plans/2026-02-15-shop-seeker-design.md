# Shop Seeker — Design Document

## Problem

Three friends in San Francisco need a workshop space for hobby carpentry. Finding suitable commercial/warehouse space is tedious — listings are scattered across multiple sites, pricing is often ambiguous (per sqft, variable options), and many spaces that technically meet size/price criteria are clearly unsuitable for woodworking (carpeted offices, upper floors without freight access, etc.).

## Solution

An automated daily scraper that finds candidate listings, uses Claude to evaluate suitability and parse true pricing, and writes results to a shared Google Sheet for the group to track and follow up on.

## Architecture

```
EventBridge (daily cron, 6am PT)
    │
    ▼
AWS Lambda (Python 3.12)
    │
    ├── Scrape Craigslist SF
    ├── Scrape LoopNet
    ├── Scrape CommercialCafe
    │
    ▼
Basic Filter & Deduplicate
    │  - Remove listings already in Approved Sheet (by URL)
    │  - Remove listings already in Rejected Sheet (by URL)
    │  - Rough keyword/category filtering
    │  - Drop out-of-area posts via geocoding + 4mi radius
    │
    ▼
Claude API Review (Haiku)
    │  - Parse actual monthly cost from ambiguous pricing
    │  - Assess suitability for hobby carpentry workshop
    │  - Return structured JSON: approved/rejected + fields
    │
    ├── APPROVED → "Approved" tab in Google Sheet
    └── REJECTED → "Rejected" tab in Google Sheet
```

## Scraping Strategy

### Craigslist SF
- Target `sfbay.craigslist.org` — commercial real estate, office/commercial, warehouse/storage sections
- Static HTML, scraped with BeautifulSoup + requests
- Filter by SF geographic area via URL params

### LoopNet & CommercialCafe
- Parse search result pages with requests; look for underlying API endpoints if available
- Fallback: if JS rendering is required, defer these sites to a later version or use email alert scraping

### Distance Filtering
- Bounding box: ~4 mile radius around 1390 Market St (37.7767, -122.4173)
- Geocode addresses using a free service (Census Geocoder or Nominatim)
- Listings with no parseable address are still sent to Claude (better to surface a maybe than miss a good listing); Claude flags "location unclear" in notes

### Rate Limiting & Politeness
- Random delays between requests (2-5 seconds)
- Respect robots.txt
- Identifying user-agent string

## Claude API Review

Each candidate listing's full text is sent to Claude Haiku with a system prompt that includes:

- The space is for a hobby carpentry workshop with 3 people
- Must be suitable for woodworking: ground floor or freight elevator access, not carpeted office space, ideally with ventilation and adequate power
- Parse the true monthly cost from whatever pricing format the listing uses ($/sqft with sqft options, ranges, negotiable, etc.)
- Score suitability 1-10 with brief reasoning
- Return structured JSON: approved/rejected, estimated monthly cost, sqft, suitability score, notes/rejection reason

## Google Sheets Integration

### Authentication
- GCP project with Google Sheets API enabled
- Service account with JSON key, shared to the Sheet via service account email
- Key stored in AWS Secrets Manager

### Library
- `gspread` — Python wrapper for the Sheets API

### Sheet Structure

Single Google Sheets document with two tabs:

**Tab: "Approved"**

| Column | Populated By |
|---|---|
| Title | Scraper |
| Price | Scraper |
| Sqft | Scraper |
| Address/Neighborhood | Scraper |
| Link | Scraper |
| Date Found | Scraper |
| Est. Monthly Cost | Claude |
| Suitability Score | Claude |
| AI Notes | Claude |
| Followed Up? | Human (checkbox) |
| Who | Human |
| Notes | Human |

**Tab: "Rejected"**

| Column | Populated By |
|---|---|
| Title | Scraper |
| Price | Scraper |
| Sqft | Scraper |
| Address/Neighborhood | Scraper |
| Link | Scraper |
| Date Found | Scraper |
| Est. Monthly Cost | Claude |
| Suitability Score | Claude |
| Rejection Reason | Claude |
| Reviewed By | Human |
| Notes | Human |

### Deduplication
- On each run, pull all URLs from both tabs into a set
- Skip any scraped listing whose URL is already in either set

## AWS Infrastructure

### Lambda
- Python 3.12 runtime
- Dependencies: `beautifulsoup4`, `requests`, `gspread`, `anthropic`
- Memory: 256MB
- Timeout: 5 minutes
- Environment variables for search config (radius, price cap, min sqft, sheet ID)

### EventBridge
- Cron rule: `cron(0 14 * * ? *)` — daily at 6am PT (14:00 UTC)

### Secrets Manager
- Google Sheets service account JSON key
- Anthropic API key

### IAM
- Lambda execution role with Secrets Manager read access and CloudWatch Logs write access

### Deployment
- AWS SAM (`template.yaml`)
- Deploy via `sam build && sam deploy`

### Monitoring
- CloudWatch Logs for each run
- Optional SNS email alert on Lambda errors

## Configuration

```python
SEARCH_CONFIG = {
    "center_lat": 37.7767,         # 1390 Market St
    "center_lng": -122.4173,
    "radius_miles": 4,
    "max_price": 2400,             # $/month
    "min_sqft": 400,               # sqft
    "craigslist_region": "sfbay",
}
```

Config values are stored as Lambda environment variables for easy adjustment without code changes.
