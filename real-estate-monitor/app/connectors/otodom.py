"""
Otodom.pl connector for real estate listings.
Uses Playwright for dynamic content loading.
"""
import asyncio
import json
import random
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urljoin

from playwright.async_api import BrowserContext, Page, async_playwright

from app.connectors.base import BaseConnector, ConnectorRegistry, FilterConfig
from app.logging_config import get_logger
from app.schemas import OfferNormalized
from app.settings import settings

logger = get_logger("connectors.otodom")

# Otodom roomsNumber enum → int
_ROOMS_MAP = {
    "ONE": "1", "TWO": "2", "THREE": "3", "FOUR": "4",
    "FIVE": "5", "SIX_OR_MORE": "6",
}


@ConnectorRegistry.register
class OtodomConnector(BaseConnector):
    """Connector for Otodom.pl real estate listings."""

    name = "otodom"
    base_url = "https://www.otodom.pl"
    fetch_mode = "playwright"

    REGION_IDS = {
        "pomorskie": "pomorskie",
        "mazowieckie": "mazowieckie",
        "malopolskie": "malopolskie",
        "slaskie": "slaskie",
        "dolnoslaskie": "dolnoslaskie",
        "wielkopolskie": "wielkopolskie",
    }

    def build_search_url(self, filter_config: FilterConfig) -> str:
        """Build Otodom search URL from filters."""
        path_parts = ["pl", "wyniki"]

        if filter_config.transaction_type == "sale":
            path_parts.append("sprzedaz")
        else:
            path_parts.append("wynajem")

        path_parts.append(filter_config.property_type or "mieszkanie")
        path_parts.append(filter_config.region or "pomorskie")

        base_path = "/".join(path_parts)

        params = {}
        if filter_config.min_price:
            params["priceMin"] = filter_config.min_price
        if filter_config.max_price:
            params["priceMax"] = filter_config.max_price
        if filter_config.min_area:
            params["areaMin"] = filter_config.min_area
        if filter_config.max_area:
            params["areaMax"] = filter_config.max_area
        if filter_config.rooms:
            params["roomsNumber"] = filter_config.rooms

        query_string = urlencode(params)
        url = f"{self.base_url}/{base_path}?{query_string}" if query_string else f"{self.base_url}/{base_path}"

        logger.debug("Built Otodom URL", extra={"url": url})
        return url

    def canonicalize_url(self, url: str) -> str:
        """Canonicalize Otodom URL for deduplication."""
        url = re.sub(r'[?&](utm_|fbclid|gclid|ref|tracking)=[^&]*', '', url)
        return url.split('?')[0] if '?' in url else url

    async def fetch_with_playwright(
        self,
        url: str,
        context: Optional[BrowserContext] = None,
    ) -> str:
        """Fetch page using Playwright with stealth settings."""

        playwright = None
        browser = None
        own_context = context is None

        try:
            playwright = await async_playwright().start()

            if own_context:
                browser = await playwright.chromium.launch(
                    headless=settings.playwright_headless,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-web-security",
                        "--disable-features=IsolateOrigins,site-per-process",
                    ],
                )

                context = await browser.new_context(
                    user_agent=self.user_agent,
                    viewport={"width": 1920, "height": 1080},
                    locale="pl-PL",
                    timezone_id="Europe/Warsaw",
                )

                # Block only fonts/video — keep images for URL extraction from HTML
                await context.route(
                    "**/*.{woff,woff2,mp4,webm}",
                    lambda route: route.abort(),
                )

            page = await context.new_page()

            await page.set_extra_http_headers({
                "Accept-Language": "pl-PL,pl;q=0.9",
                "DNT": "1",
            })

            response = await page.goto(
                url,
                wait_until="networkidle",
                timeout=settings.playwright_navigation_timeout,
            )

            if response and response.status >= 400:
                raise Exception(f"HTTP {response.status}")

            await asyncio.sleep(random.uniform(1.0, 2.0))

            content = await page.content()
            await page.close()
            return content

        finally:
            if own_context:
                if context:
                    await context.close()
                if browser:
                    await browser.close()
                if playwright:
                    await playwright.stop()

    async def extract_offers(self, page_content: str) -> List[OfferNormalized]:
        """Extract offers from Otodom page content."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(page_content, "html.parser")
        offers: List[OfferNormalized] = []

        # 1. Best: Next.js SSR payload
        offers = self._extract_from_next_data(soup)

        # 2. Fallback: JSON-LD
        if not offers:
            offers = self._extract_from_json_ld(soup)

        # 3. Last resort: raw HTML
        if not offers:
            offers = self._extract_from_html(soup)

        logger.info("Extracted offers from Otodom", extra={"count": len(offers)})
        return offers

    # ------------------------------------------------------------------
    # __NEXT_DATA__ — most reliable for Next.js apps
    # ------------------------------------------------------------------

    @staticmethod
    def _deep_get(data: Any, *keys) -> Any:
        """Safely traverse nested dicts."""
        for key in keys:
            if isinstance(data, dict):
                data = data.get(key)
            else:
                return None
        return data

    def _extract_from_next_data(self, soup) -> List[OfferNormalized]:
        """Extract offers from Next.js __NEXT_DATA__ JSON block."""
        script = soup.find("script", id="__NEXT_DATA__")
        if not script or not script.string:
            return []

        try:
            data = json.loads(script.string)
        except Exception as e:
            logger.debug(f"Failed to parse __NEXT_DATA__: {e}")
            return []

        pp = self._deep_get(data, "props", "pageProps")
        items = (
            self._deep_get(pp, "listings", "items")
            or self._deep_get(pp, "data", "searchAds", "items")
            or self._deep_get(pp, "initialProps", "data", "searchAds", "items")
            or self._deep_get(pp, "ads")
            or self._find_listing_arrays(data)
            or []
        )

        offers: List[OfferNormalized] = []
        for item in items:
            try:
                offer = self._parse_next_data_item(item)
                if offer and offer.url and offer.title:
                    offers.append(offer)
            except Exception as e:
                logger.debug(f"Failed to parse Otodom Next.js item: {e}")

        logger.info("Otodom __NEXT_DATA__ extraction", extra={"count": len(offers)})
        return offers

    def _find_listing_arrays(self, data: Any, depth: int = 0) -> List[dict]:
        """Recursively find arrays that look like listing collections."""
        if depth > 6:
            return []
        if isinstance(data, list):
            if len(data) >= 2 and isinstance(data[0], dict):
                first = data[0]
                if ("slug" in first or "id" in first) and "title" in first:
                    return data
            for item in data[:3]:
                result = self._find_listing_arrays(item, depth + 1)
                if result:
                    return result
        elif isinstance(data, dict):
            for v in data.values():
                if isinstance(v, (dict, list)):
                    result = self._find_listing_arrays(v, depth + 1)
                    if result:
                        return result
        return []

    def _parse_next_data_item(self, item: dict) -> Optional[OfferNormalized]:
        """Parse a single item from __NEXT_DATA__ into OfferNormalized."""
        url = item.get("url", "")
        if not url:
            slug = item.get("slug") or str(item.get("id", ""))
            url = f"{self.base_url}/pl/oferta/{slug}" if slug else ""

        title = item.get("title", "")

        # Price
        price_obj = item.get("totalPrice") or item.get("price") or {}
        price_text = ""
        if isinstance(price_obj, dict):
            val = price_obj.get("value") or price_obj.get("amount")
            cur = price_obj.get("currency", "PLN")
            if val is not None:
                price_text = f"{val} {cur}"
        elif isinstance(price_obj, (int, float)):
            price_text = f"{price_obj} PLN"

        # Area
        area = item.get("areaInSquareMeters") or item.get("area_m2") or item.get("area")
        area_text = f"{area} m²" if area else ""

        # Rooms
        rooms_raw = item.get("roomsNumber") or item.get("rooms")
        rooms_text = _ROOMS_MAP.get(str(rooms_raw), str(rooms_raw)) if rooms_raw else ""

        # Location
        loc = item.get("location") or {}
        addr = loc.get("address", {}) if isinstance(loc, dict) else {}
        city, region = "", ""
        if isinstance(addr, dict):
            city_obj = addr.get("city") or addr.get("district") or {}
            region_obj = addr.get("province") or addr.get("region") or {}
            city = city_obj.get("name", "") if isinstance(city_obj, dict) else str(city_obj or "")
            region = region_obj.get("name", "") if isinstance(region_obj, dict) else str(region_obj or "")
        location_text = ", ".join(filter(None, [city, region]))

        # Coordinates
        geo = loc.get("coordinates") or loc.get("geo") or {} if isinstance(loc, dict) else {}
        lat = geo.get("latitude") or geo.get("lat") if isinstance(geo, dict) else None
        lng = geo.get("longitude") or geo.get("lng") or geo.get("lon") if isinstance(geo, dict) else None

        # Images
        images_raw = item.get("images") or item.get("photos") or []
        images = []
        for img in images_raw:
            if isinstance(img, str):
                images.append(img)
            elif isinstance(img, dict):
                src = (
                    img.get("large") or img.get("medium")
                    or img.get("thumbnail") or img.get("url") or img.get("link")
                )
                if src:
                    images.append(src)

        source_created_at = (
            item.get("dateCreated") or item.get("created_time")
            or item.get("date") or item.get("dateModified")
        )

        offer_data = {
            "url": url,
            "title": title,
            "price_text": price_text,
            "area_text": area_text,
            "rooms_text": rooms_text,
            "location_text": location_text,
            "images": images,
            "source_created_at": source_created_at,
            "lat": lat,
            "lng": lng,
        }

        normalized = self.normalize_offer(offer_data)
        return normalized if normalized.url and normalized.title else None

    # ------------------------------------------------------------------
    # JSON-LD fallback
    # ------------------------------------------------------------------

    def _extract_from_json_ld(self, soup) -> List[OfferNormalized]:
        """Extract offers from JSON-LD structured data."""
        offers = []

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                items = data if isinstance(data, list) else [data]

                for item in items:
                    if item.get("@type") != "Product":
                        continue

                    offer_data = {
                        "url": item.get("url", ""),
                        "title": item.get("name", ""),
                        "price_text": "",
                        "area_text": "",
                        "rooms_text": "",
                        "location_text": "",
                        "source_created_at": (
                            item.get("datePosted")
                            or item.get("datePublished")
                            or item.get("dateCreated")
                        ),
                    }

                    offers_data = item.get("offers", {})
                    if isinstance(offers_data, dict):
                        price = offers_data.get("price")
                        currency = offers_data.get("priceCurrency", "PLN")
                        if price:
                            offer_data["price_text"] = f"{price} {currency}"

                    description = item.get("description", "")
                    area_match = re.search(r'(\d+[\s,]?\d*)\s*m[²2]', description)
                    if area_match:
                        offer_data["area_text"] = area_match.group(0)

                    rooms_match = re.search(r'(\d+)\s*pok', description.lower())
                    if rooms_match:
                        offer_data["rooms_text"] = rooms_match.group(1)

                    address = item.get("address", {})
                    if isinstance(address, dict):
                        city = address.get("addressLocality", "")
                        region = address.get("addressRegion", "")
                        offer_data["location_text"] = f"{city}, {region}"

                    geo = item.get("geo", {})
                    if isinstance(geo, dict):
                        offer_data["lat"] = geo.get("latitude")
                        offer_data["lng"] = geo.get("longitude")

                    image = item.get("image")
                    if isinstance(image, str) and image:
                        offer_data["images"] = [image]
                    elif isinstance(image, list):
                        offer_data["images"] = [img for img in image if isinstance(img, str)]

                    normalized = self.normalize_offer(offer_data)
                    if normalized.url and normalized.title:
                        offers.append(normalized)

            except Exception as e:
                logger.debug(f"Failed to parse JSON-LD: {e}")
                continue

        return offers

    # ------------------------------------------------------------------
    # Raw HTML fallback
    # ------------------------------------------------------------------

    def _extract_from_html(self, soup) -> List[OfferNormalized]:
        """Extract offers from HTML structure."""
        offers = []

        listing_selectors = [
            "[data-cy='listing-item']",
            "[data-testid='listing-item']",
            "li[data-id]",
            ".listing-item",
            ".offer-item",
            "article",
        ]

        listings = []
        for selector in listing_selectors:
            listings = soup.select(selector)
            if listings:
                break

        for listing in listings:
            try:
                offer_data = self._parse_listing_element(listing)
                if offer_data:
                    normalized = self.normalize_offer(offer_data)
                    if normalized.url and normalized.title:
                        offers.append(normalized)
            except Exception as e:
                logger.debug(f"Failed to parse listing: {e}")

        return offers

    def _parse_listing_element(self, listing) -> Optional[dict]:
        """Parse a single listing element."""
        offer_data = {
            "url": "", "title": "", "price_text": "",
            "area_text": "", "rooms_text": "", "location_text": "",
        }

        link = listing.find("a", href=True)
        if link:
            offer_data["url"] = urljoin(self.base_url, link.get("href", ""))

        title_elem = (
            listing.select_one("[data-cy='listing-item-title']") or
            listing.select_one("[data-testid='listing-title']") or
            listing.find("h3") or listing.find("h2") or
            listing.select_one(".listing-title")
        )
        if title_elem:
            offer_data["title"] = title_elem.get_text(strip=True)

        price_elem = (
            listing.select_one("[data-testid='listing-price']") or
            listing.select_one("[data-cy='price']") or
            listing.select_one(".listing-price") or
            listing.find(string=re.compile(r'\d+\s*\d*\s*zł'))
        )
        if price_elem:
            offer_data["price_text"] = (
                price_elem.get_text(strip=True) if hasattr(price_elem, 'get_text') else str(price_elem)
            )

        params_text = listing.get_text(" ", strip=True)
        area_match = re.search(r'(\d+[\s,]?\d*)\s*m[²2]', params_text)
        if area_match:
            offer_data["area_text"] = area_match.group(0)

        rooms_match = re.search(r'(\d+)\s*pok', params_text.lower())
        if rooms_match:
            offer_data["rooms_text"] = rooms_match.group(1)

        location_elem = (
            listing.select_one("[data-testid='listing-location']") or
            listing.select_one(".listing-location") or
            listing.select_one(".location")
        )
        if location_elem:
            offer_data["location_text"] = location_elem.get_text(strip=True)

        time_elem = listing.find("time")
        if time_elem:
            offer_data["source_created_at"] = time_elem.get("datetime") or time_elem.get_text(strip=True)

        image_elem = listing.find("img")
        if image_elem:
            src = image_elem.get("src") or image_elem.get("data-src")
            if not src:
                srcset = image_elem.get("srcset", "")
                if srcset:
                    src = srcset.split(",")[0].strip().split(" ")[0]
            if src:
                offer_data["images"] = [urljoin(self.base_url, src)]

        return offer_data if offer_data["url"] else None
