"""
Additional popular portals connectors (best-effort HTML parsing).
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from app.connectors.base import BaseConnector, FilterConfig, register_connector
from app.logging_config import get_logger
from app.schemas import OfferNormalized

logger = get_logger("connectors.popular")


class GenericPortalConnector(BaseConnector):
    name = "generic"
    base_url = ""
    fetch_mode = "http"
    search_path_template = "/"

    def build_search_url(self, filter_config: FilterConfig) -> str:
        region = (filter_config.region or "").strip().lower()
        path = self.search_path_template.format(region=region)
        return f"{self.base_url}{path}"

    def canonicalize_url(self, url: str) -> str:
        parsed = urlparse(url)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "", ""))

    async def extract_offers(self, page_content: str) -> List[OfferNormalized]:
        soup = BeautifulSoup(page_content, "html.parser")
        offers: List[OfferNormalized] = []

        # 1) JSON-LD / embedded data first (bardziej stabilne)
        for parsed in self._extract_from_json_ld(soup):
            try:
                normalized = self.normalize_offer(parsed)
                if normalized.url and normalized.title:
                    offers.append(normalized)
            except Exception:
                continue

        # 2) HTML fallback
        listing_selectors = [
            "article",
            "[data-testid='listing-item']",
            "[data-cy='listing-item']",
            "li[class*='offer']",
            "div[class*='offer']",
            "div[class*='listing']",
            "div[class*='result']",
            "li[class*='result']",
        ]

        listings = []
        for selector in listing_selectors:
            listings = soup.select(selector)
            if len(listings) >= 8:
                break

        for listing in listings:
            parsed = self._parse_listing_element(listing)
            if not parsed:
                continue
            try:
                normalized = self.normalize_offer(parsed)
                if normalized.url and normalized.title:
                    offers.append(normalized)
            except Exception:
                continue

        # Deduplicate by URL
        seen = set()
        unique: List[OfferNormalized] = []
        for o in offers:
            c = self.canonicalize_url(o.url)
            if c in seen:
                continue
            seen.add(c)
            unique.append(o)

        logger.info("Extracted offers", extra={"source": self.name, "count": len(unique)})
        return unique

    def _is_listing_url(self, url: str) -> bool:
        u = url.lower()
        if not u.startswith("http"):
            return False
        # common nav/non-offer paths
        banned = ["/szukaj.html", "/biura-nieruchomosci", "/deweloperzy", "/firmy/", "/porady/"]
        if any(b in u for b in banned):
            return False

        if self.name == "morizon":
            return "/oferta/" in u
        if self.name == "gratka":
            return "/nieruchomosci/" in u and ("/ob/" in u or "/oi/" in u)
        if self.name == "nieruchomosci-online":
            return "nieruchomosci-online.pl" in u and u.endswith(".html") and "/szukaj.html" not in u
        if self.name == "domiporta":
            return "/nieruchomosci/" in u or "/mieszkanie/" in u

        return True

    def _extract_from_json_ld(self, soup) -> List[Dict[str, Any]]:
        parsed: List[Dict[str, Any]] = []

        def walk(node: Any):
            if isinstance(node, dict):
                node_type = str(node.get("@type", "")).lower()

                # Offer object
                if node_type == "offer" and node.get("url"):
                    url = str(node.get("url"))
                    if self._is_listing_url(url):
                        item = node.get("itemOffered") if isinstance(node.get("itemOffered"), dict) else {}
                        title = item.get("name") or node.get("name") or ""
                        location = ""
                        addr = item.get("address") if isinstance(item.get("address"), dict) else {}
                        if addr:
                            location = ", ".join([x for x in [addr.get("addressLocality"), addr.get("addressRegion")] if x])
                        image = node.get("image") or item.get("image")
                        images = [image] if isinstance(image, str) else ([x for x in image if isinstance(x, str)] if isinstance(image, list) else [])
                        parsed.append({
                            "url": url,
                            "title": title,
                            "price_text": f"{node.get('price', '')} {node.get('priceCurrency', 'PLN')}" if node.get("price") else "",
                            "area_text": "",
                            "rooms_text": "",
                            "location_text": location,
                            "images": images,
                            "source_created_at": node.get("availabilityStarts") or node.get("priceValidUntil") or node.get("datePosted"),
                        })

                # Product/CollectionPage with nested data
                for v in node.values():
                    if isinstance(v, (dict, list)):
                        walk(v)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        for script in soup.select("script[type='application/ld+json']"):
            txt = (script.string or script.get_text() or "").strip()
            if not txt:
                continue
            try:
                data = json.loads(txt)
            except Exception:
                continue
            walk(data)

        return parsed

    def _parse_listing_element(self, listing) -> Optional[dict]:
        link = listing.find("a", href=True)
        if not link:
            return None

        href = link.get("href", "")
        if not href:
            return None
        url = urljoin(self.base_url, href)
        if not self._is_listing_url(url):
            return None

        title_elem = (
            listing.find("h2") or
            listing.find("h3") or
            listing.find("h4") or
            listing.select_one("[class*='title']") or
            link
        )
        title = title_elem.get_text(" ", strip=True) if title_elem else ""
        if not title or len(title) < 8:
            return None

        text = listing.get_text(" ", strip=True)

        price_match = re.search(r"([\d\s\u00A0,.]{3,})\s*(zł|pln|eur|€)", text.lower())
        price_text = price_match.group(0) if price_match else ""

        area_match = re.search(r"(\d+[\s,]?\d*)\s*m[²2]", text.lower())
        rooms_match = re.search(r"(\d+)\s*pok", text.lower())

        image_elem = listing.find("img")
        images = []
        if image_elem:
            src = image_elem.get("src") or image_elem.get("data-src")
            if not src:
                srcset = image_elem.get("srcset")
                if srcset:
                    src = srcset.split(",")[0].strip().split(" ")[0]
            if src:
                images = [urljoin(self.base_url, src)]

        location_elem = listing.select_one("[class*='location'], [class*='address']")
        location_text = location_elem.get_text(" ", strip=True) if location_elem else ""

        time_elem = listing.find("time")
        source_created_at = time_elem.get("datetime") if time_elem else None

        return {
            "url": url,
            "title": title,
            "price_text": price_text,
            "area_text": area_match.group(0) if area_match else "",
            "rooms_text": rooms_match.group(1) if rooms_match else "",
            "location_text": location_text,
            "images": images,
            "source_created_at": source_created_at,
        }


@register_connector
class GratkaConnector(GenericPortalConnector):
    name = "gratka"
    base_url = "https://gratka.pl"
    # Region pages often return empty placeholder payloads; base listing is richer
    search_path_template = "/nieruchomosci/mieszkania"


@register_connector
class MorizonConnector(GenericPortalConnector):
    name = "morizon"
    base_url = "https://www.morizon.pl"
    search_path_template = "/mieszkania/{region}/"


@register_connector
class DomiportaConnector(GenericPortalConnector):
    name = "domiporta"
    base_url = "https://www.domiporta.pl"
    search_path_template = "/mieszkanie/sprzedam/{region}"


@register_connector
class NieruchomosciOnlineConnector(GenericPortalConnector):
    name = "nieruchomosci-online"
    base_url = "https://www.nieruchomosci-online.pl"
    search_path_template = "/szukaj.html?3,mieszkanie,sprzedaz,,{region}"


@register_connector
class TabelaOfertConnector(GenericPortalConnector):
    name = "tabelaofert"
    base_url = "https://tabelaofert.pl"
    search_path_template = "/mieszkania-na-sprzedaz/{region}"
