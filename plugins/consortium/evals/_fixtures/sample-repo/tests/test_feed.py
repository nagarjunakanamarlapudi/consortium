from shop.distance import distance_km


def test_feed_distance():
    assert distance_km(250) == 0.25
