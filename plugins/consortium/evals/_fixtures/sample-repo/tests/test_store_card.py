from shop.distance import distance_km


def test_card_distance():
    assert distance_km(500) == 0.5
