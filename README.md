# Shop Seeker

An automated tool that scrapes commercial real estate listings in San Francisco, uses Claude AI to evaluate each one for suitability as a shared carpentry workshop, and writes the results to a Google Sheet.

Runs daily as an AWS Lambda function on a cron schedule.

## How It Works

1. **Scrape** listings from three sources:
   - **Craigslist** — office/commercial category, filtered by max price. Uses plain HTTP requests.
   - **LoopNet** — commercial real estate for lease. Uses [curl_cffi](https://github.com/lexiforest/curl_cffi) with Chrome impersonation to bypass Akamai bot protection.
   - **CommercialCafe** — commercial real estate for lease. Also uses curl_cffi for Cloudflare bypass.

2. **Deduplicate** against previously seen listings (tracked by URL in the Google Sheet).

3. **Geo-filter** listings that have coordinates, removing any outside a configurable radius from a center point.

4. **Review** each candidate with Claude Haiku, which evaluates:
   - Estimated true monthly cost
   - Usable square footage
   - Suitability for woodworking (ground floor access, power, ventilation, not a carpeted office)
   - Overall suitability score (1-10)
   - Approved/rejected decision

5. **Write results** to a Google Sheet with separate "Approved" and "Rejected" tabs, including Claude's analysis. The sheet has columns for human follow-up tracking.

## Architecture

```
EventBridge (daily cron)
        |
        v
  AWS Lambda (Python 3.12)
        |
        ├── Craigslist (requests)
        ├── LoopNet (curl_cffi)
        ├── CommercialCafe (curl_cffi)
        |
        v
  Claude Haiku (review each listing)
        |
        v
  Google Sheets (results)
```

All secrets are stored in AWS Secrets Manager. Search parameters are configured via Lambda environment variables set through the SAM template.

## Prerequisites

- Python 3.12
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (required for `sam build`)
- [AWS CLI](https://aws.amazon.com/cli/)
- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
- An [Anthropic API key](https://console.anthropic.com/) with credits
- A GCP service account with Google Sheets API access
- A Google Sheet with "Approved" and "Rejected" tabs

## Setup

### 1. AWS Secrets Manager

Create three secrets in your target region:

```bash
# GCP service account credentials (full JSON key file)
aws secretsmanager create-secret \
  --name "shop-seeker/google-creds" \
  --secret-string file://path/to/service-account.json

# Anthropic API key
aws secretsmanager create-secret \
  --name "shop-seeker/anthropic-key" \
  --secret-string '{"api_key":"sk-ant-..."}'

# Google Sheet ID
aws secretsmanager create-secret \
  --name "shop-seeker/google-sheet-id" \
  --secret-string '{"sheet_id":"your-sheet-id-here"}'
```

### 2. Google Sheet

Create a Google Sheet with two tabs named exactly **Approved** and **Rejected**. Share the sheet with your GCP service account email (with Editor access).

### 3. Search Configuration

The following parameters can be customized in `template.yaml` (or overridden at deploy time):

| Parameter | Default | Description |
|---|---|---|
| `CenterLat` | `37.7767` | Search center latitude |
| `CenterLng` | `-122.4173` | Search center longitude |
| `RadiusMiles` | `4` | Geo-filter radius in miles |
| `MaxPrice` | `2400` | Max monthly price (passed to Craigslist) |
| `MinSqft` | `400` | Minimum square footage |
| `CraigslistRegion` | `sfbay` | Craigslist regional subdomain |

## Build

Docker must be running. The `--use-container` flag is required because `curl_cffi` has native C dependencies that must be compiled for the Lambda Linux runtime.

```bash
sam build --use-container
```

## Deploy

```bash
sam deploy
```

Or for first-time setup:

```bash
sam deploy --guided
```

The stack deploys to the region specified in `samconfig.toml` (default: `us-west-1`).

## Test Locally

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest
```

32 tests cover all modules: scrapers, geo-filtering, Claude review parsing, Google Sheets integration, and the Lambda handler orchestration.

## Invoke Manually

```bash
# Trigger a run outside the daily schedule
aws lambda invoke \
  --function-name shop-seeker-ShopSeekerFunction-XXXX \
  --region us-west-1 \
  --cli-read-timeout 910 \
  output.json
```

The function name can be found in the CloudFormation stack outputs or via `aws lambda list-functions`.

## Monitor

### CloudWatch Logs

The function logs progress at each stage:

```
Shop Seeker run starting
Found 42 previously seen URLs
Starting Craigslist scraper
Found 85 search results
Craigslist done: 85 listings
Starting LoopNet scraper
LoopNet done: 12 listings
Starting CommercialCafe scraper
CommercialCafe done: 0 listings
Scraped 97 total listings
74 new listings after dedup
Skipping out-of-radius: ...
58 candidates for Claude review
Reviewing 1/58: ...
Reviewing 2/58: ...
Done. Approved: 8, Rejected: 50
```

View logs via the AWS Console or CLI:

```bash
aws logs tail /aws/lambda/shop-seeker-ShopSeekerFunction-XXXX \
  --region us-west-1 --follow
```

### Google Sheet

Check the "Approved" tab for new listings worth contacting. Each row includes Claude's estimated monthly cost, suitability score (1-10), and notes explaining the assessment.

### Daily Schedule

The Lambda runs daily at **6:00 AM Pacific** (14:00 UTC) via EventBridge. The schedule can be changed in `template.yaml` under the `DailySchedule` event.

## Project Structure

```
shop-seeker/
├── template.yaml              # SAM/CloudFormation template
├── samconfig.toml             # SAM deployment config
├── requirements.txt           # Runtime dependencies
├── requirements-dev.txt       # Dev/test dependencies
├── src/
│   ├── config.py              # Search parameters from env vars
│   ├── geo.py                 # Bounding box / radius filtering
│   ├── handler.py             # Lambda entry point
│   ├── models.py              # Listing dataclass
│   ├── reviewer.py            # Claude AI review logic
│   ├── sheets.py              # Google Sheets read/write
│   └── scrapers/
│       ├── craigslist.py      # Plain HTTP scraper
│       ├── loopnet.py         # curl_cffi Chrome impersonation
│       └── commercialcafe.py  # curl_cffi Chrome impersonation
└── tests/
    ├── fixtures/              # HTML fixtures for scraper tests
    ├── test_craigslist.py
    ├── test_loopnet.py
    ├── test_commercialcafe.py
    ├── test_sheets.py
    ├── test_reviewer.py
    ├── test_handler.py
    ├── test_geo.py
    └── test_models.py
```
