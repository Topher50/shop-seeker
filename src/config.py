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
