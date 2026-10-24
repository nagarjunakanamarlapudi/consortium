from shop.distance import distance_km


def test_notification_distance():
    assert distance_km(1500) == 1.5
