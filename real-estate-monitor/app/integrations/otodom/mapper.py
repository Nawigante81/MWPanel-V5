from __future__ import annotations

from typing import Any, Dict

OFFER_TYPE_MAP = {
    "sale": "sell",
    "rent": "rent",
}

PROPERTY_TYPE_MAP = {
    "apartment": "flat",
    "house": "house",
    "plot": "plot",
    "commercial": "commercial",
    "warehouse": "warehouse",
}

MARKET_TYPE_MAP = {
    "primary": "primary",
    "secondary": "secondary",
}

HEATING_MAP = {
    "gas": "gas",
    "city": "municipal",
    "electric": "electric",
}


def map_property_to_otodom_payload(prop: Dict[str, Any], env_cfg: Dict[str, Any]) -> Dict[str, Any]:
    offer_type = OFFER_TYPE_MAP.get((prop.get("offer_type") or "").lower(), "sell")
    property_type = PROPERTY_TYPE_MAP.get((prop.get("property_type") or "").lower(), "flat")
    market_type = MARKET_TYPE_MAP.get((prop.get("market_type") or "").lower(), "secondary")

    payload = {
        "title": prop.get("title"),
        "description": prop.get("description"),
        "offerType": offer_type,
        "propertyType": property_type,
        "marketType": market_type,
        "price": float(prop.get("price") or 0),
        "area": float(prop.get("area") or 0),
        "rooms": prop.get("rooms"),
        "plotArea": prop.get("plot_area"),
        "floor": prop.get("floor"),
        "totalFloors": prop.get("total_floors"),
        "yearBuilt": prop.get("year_built"),
        "condition": prop.get("condition"),
        "heating": HEATING_MAP.get((prop.get("heating") or "").lower(), prop.get("heating")),
        "ownership": prop.get("ownership"),
        "location": {
            "country": prop.get("country") or "PL",
            "city": prop.get("city"),
            "district": prop.get("district"),
            "street": prop.get("street"),
            "postalCode": prop.get("postal_code"),
            "coordinates": {
                "lat": float(prop["latitude"]) if prop.get("latitude") is not None else None,
                "lon": float(prop["longitude"]) if prop.get("longitude") is not None else None,
            },
        },
        "contact": {
            "name": env_cfg.get("OTODOM_DEFAULT_CONTACT_NAME"),
            "email": env_cfg.get("OTODOM_DEFAULT_CONTACT_EMAIL"),
            "phone": env_cfg.get("OTODOM_DEFAULT_CONTACT_PHONE"),
        },
        "externalReference": str(prop.get("id")),
    }

    # remove None recursively (light)
    def _clean(x):
        if isinstance(x, dict):
            return {k: _clean(v) for k, v in x.items() if v is not None}
        if isinstance(x, list):
            return [_clean(v) for v in x if v is not None]
        return x

    return _clean(payload)
