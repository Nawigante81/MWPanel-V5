from app.integrations.otodom.mapper import map_property_to_otodom_payload


def test_map_property_to_otodom_payload_basic():
    prop = {
        "id": "p1",
        "title": "Mieszkanie 2 pokoje",
        "description": "Opis",
        "offer_type": "sale",
        "property_type": "apartment",
        "market_type": "secondary",
        "price": 600000,
        "area": 49.5,
        "rooms": 2,
        "city": "Gdańsk",
        "country": "PL",
    }
    cfg = {
        "OTODOM_DEFAULT_CONTACT_NAME": "Jan",
        "OTODOM_DEFAULT_CONTACT_EMAIL": "jan@example.com",
        "OTODOM_DEFAULT_CONTACT_PHONE": "+48123123123",
    }
    payload = map_property_to_otodom_payload(prop, cfg)
    assert payload["offerType"] == "sell"
    assert payload["propertyType"] == "flat"
    assert payload["price"] == 600000.0
    assert payload["contact"]["email"] == "jan@example.com"
