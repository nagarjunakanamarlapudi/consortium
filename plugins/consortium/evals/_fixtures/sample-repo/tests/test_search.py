from shop.distance import distance_km


def test_search_radius():
    assert distance_km(2000) == 2
