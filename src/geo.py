import math


def bounding_box(
    center_lat: float, center_lng: float, radius_miles: float
) -> tuple[float, float, float, float]:
    """Return (south, north, west, east) bounding box."""
    lat_delta = radius_miles / 69.0
    lng_delta = radius_miles / (69.0 * math.cos(math.radians(center_lat)))
    return (
        center_lat - lat_delta,
        center_lat + lat_delta,
        center_lng - lng_delta,
        center_lng + lng_delta,
    )


def is_within_radius(
    lat: float,
    lng: float,
    center_lat: float,
    center_lng: float,
    radius_miles: float,
) -> bool:
    """Check if a point is within radius_miles of center using bounding box."""
    south, north, west, east = bounding_box(center_lat, center_lng, radius_miles)
    return south <= lat <= north and west <= lng <= east
