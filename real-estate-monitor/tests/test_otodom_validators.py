from app.integrations.otodom.validators import validate_property_for_publish


def test_validator_requires_fields_and_images():
    prop = {
        "title": "",
        "description": "",
        "offer_type": "sale",
        "property_type": "apartment",
        "price": None,
        "city": "",
    }
    out = validate_property_for_publish(prop, [])
    assert out.ok is False
    assert "title" in out.missing_fields
    assert "images" in out.missing_fields


def test_validator_success():
    prop = {
        "title": "OK",
        "description": "Opis",
        "offer_type": "sale",
        "property_type": "apartment",
        "price": 100,
        "city": "Gdańsk",
    }
    images = [{"file_url": "https://example.com/i.jpg"}]
    out = validate_property_for_publish(prop, images)
    assert out.ok is True
