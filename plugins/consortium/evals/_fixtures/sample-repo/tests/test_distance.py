from shop.distance import distance_km


def test_distance_conversion():
    assert distance_km(1000) == 1
