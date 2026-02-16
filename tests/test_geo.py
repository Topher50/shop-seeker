from src.geo import is_within_radius, bounding_box


def test_bounding_box_returns_four_floats():
    box = bounding_box(37.7767, -122.4173, 4)
    assert len(box) == 4
    south, north, west, east = box
    assert south < 37.7767 < north
    assert west < -122.4173 < east


def test_bounding_box_radius_approximate():
    """4 miles ~ 0.058 degrees latitude."""
    box = bounding_box(37.7767, -122.4173, 4)
    south, north, west, east = box
    assert abs((north - south) / 2 - 0.058) < 0.005


def test_is_within_radius_inside():
    # SoMa: ~1 mile from 1390 Market
    assert is_within_radius(37.7785, -122.3950, 37.7767, -122.4173, 4) is True


def test_is_within_radius_outside():
    # Outer Sunset: ~5+ miles from 1390 Market
    assert is_within_radius(37.7535, -122.5050, 37.7767, -122.4173, 4) is False


def test_is_within_radius_edge():
    # Bayview: ~3.5 miles, should be inside
    assert is_within_radius(37.7340, -122.3910, 37.7767, -122.4173, 4) is True
