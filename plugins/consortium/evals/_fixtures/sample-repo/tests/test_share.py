from shop.distance import distance_km


def test_shared_distance():
    assert distance_km(0) == 0
