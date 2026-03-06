"""
OLX.pl connector for real estate listings.
Uses Playwright for dynamic content loading.
"""
import asyncio
import json
import random
import re
from typing import Any, List, Optional
from urllib.parse import urlencode, urljoin

from playwright.async_api import BrowserContext, async_playwright

from app.connectors.base import BaseConnector, ConnectorRegistry, FilterConfig
from app.logging_config import get_logger
from app.schemas import OfferNormalized
from app.settings import settings

logger = get_logger("connectors.olx")


@ConnectorRegistry.register
class OlxConnector(BaseConnector):
    """Connector for OLX.pl real estate listings."""

    name = "olx"
    base_url = "https://www.olx.pl"
    fetch_mode = "playwright"

    CATEGORY_PATHS = {
        "sale": "nieruchomosci/mieszkania/sprzedaz",
        "rent": "nieruchomosci/mieszkania/wynajem",
    }

    REGION_PATHS = {
        "pomorskie": "pomorskie",
        "mazowieckie": "mazowieckie",
        "malopolskie": "malopolskie",
        "slaskie": "slaskie",
        "dolnoslaskie": "dolnoslaskie",
        "wielkopolskie": "wielkopolskie",
    }

    def build_search_url(self, filter_config: FilterConfig) -> str:
        """Build OLX search URL from filters."""
        category = self.CATEGORY_PATHS.get(
            filter_config.transaction_type, self.CATEGORY_PATHS["sale"]
        )
        path_parts = [category]

        if filter_config.region:
            region_path = self.REGION_PATHS.get(filter_config.region, filter_config.region)
            path_parts.append(region_path)

        base_path = "/".join(path_parts)

        params = {}
        if filter_config.min_price:
            params["search[filter_float_price:from]"] = filter_config.min_price
        if filter_config.max_price:
            params["search[filter_float_price:to]"] = filter_config.max_price
        if filter_config.min_area:
            params["search[filter_float_m:from]"] = filter_config.min_area
        if filter_config.max_area:
            params["search[filter_float_m:to]"] = filter_config.max_area
        if filter_config.rooms:
            params["search[filter_enum_rooms_num[0]]"] = filter_config.rooms

        query_string = urlencode(params)
        url = f"{self.base_url}/{base_path}?{query_string}" if query_string else f"{self.base_url}/{base_path}"

        logger.debug("Built OLX URL", extra={"url": url})
        return url

    def canonicalize_url(self, url: str) -> str:
        """Canonicalize OLX URL for deduplication."""
        url = re.sub(r'[?&](utm_|fbclid|gclid|ref|tracking|bs|highlighted|promoted|from)=[^&]*', '', url)
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

                # Block only fonts/video — keep image URLs available in DOM
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

            # Accept cookie consent if present
            try:
                cookie_btn = await page.wait_for_selector(
                    "button[data-testid='cookie-banner-accept-all']",
                    timeout=4000,
                )
                if cookie_btn:
                    await cookie_btn.click()
                    await asyncio.sleep(0.5)
            except Exception:
                pass

            # Scroll to trigger lazy loading
            await page.evaluate("""
                async () => {
                    await new Promise((resolve) => {
                        let totalHeight = 0;
                        const distance = 300;
                        const timer = setInterval(() => {
                            const scrollHeight = document.body.scrollHeight;
                            window.scrollBy(0, distance);
                            totalHeight += distance;
                            if (totalHeight >= scrollHeight) {
                                clearInterval(timer);
                                resolve();
                            }
                        }, 100);
                    });
                }
            """)

            await asyncio.sleep(random.uniform(0.5, 1.0))

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
        """Extract offers from OLX page content."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(page_content, "html.parser")
        offers: List[OfferNormalized] = []

        # 1. Best: Next.js SSR payload
        offers = self._extract_from_next_data(soup)

        # 2. Fallback: JSON-LD
        if not offers:
            offers = self._extract_from_json_ld(soup)

        # 3. Fallback: embedded window data
        if not offers:
            offers = self._extract_from_page_data(soup)

        # 4. Last resort: raw HTML
        if not offers:
            offers = self._extract_from_html(soup)

        logger.info("Extracted offers from OLX", extra={"count": len(offers)})
        return offers

    # ------------------------------------------------------------------
    # __NEXT_DATA__ — most reliable for Next.js apps
    # ------------------------------------------------------------------

    @staticmethod
    def _deep_get(data: Any, *keys) -> Any:
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
            logger.debug(f"Failed to parse OLX __NEXT_DATA__: {e}")
            return []

        pp = self._deep_get(data, "props", "pageProps")
        items = (
            self._deep_get(pp, "data", "ads")
            or self._deep_get(pp, "listing", "ads")
            or self._deep_get(pp, "initialProps", "data", "ads")
            or self._deep_get(pp, "ads")
            or self._find_ad_arrays(data)
            or []
        )

        offers: List[OfferNormalized] = []
        for item in items:
            try:
                offer = self._parse_next_data_item(item)
                if offer and offer.url and offer.title:
                    offers.append(offer)
            except Exception as e:
                logger.debug(f"Failed to parse OLX Next.js item: {e}")

        logger.info("OLX __NEXT_DATA__ extraction", extra={"count": len(offers)})
        return offers

    def _find_ad_arrays(self, data: Any, depth: int = 0) -> List[dict]:
        """Recursively find arrays that look like OLX ad collections."""
        if depth > 6:
            return []
        if isinstance(data, list):
            if len(data) >= 2 and isinstance(data[0], dict):
                first = data[0]
                if ("id" in first or "url" in first) and "title" in first:
                    return data
            for item in data[:3]:
                result = self._find_ad_arrays(item, depth + 1)
                if result:
                    return result
        elif isinstance(data, dict):
            for v in data.values():
                if isinstance(v, (dict, list)):
                    result = self._find_ad_arrays(v, depth + 1)
                    if result:
                        return result
        return []

    def _parse_next_data_item(self, item: dict) -> Optional[OfferNormalized]:
        """Parse a single OLX ad from __NEXT_DATA__ into OfferNormalized."""
        # Full URL preferred, else build from id/slug
        url = item.get("url", "")
        if not url:
            slug = item.get("slug") or str(item.get("id", ""))
            url = urljoin(self.base_url, slug) if slug else ""

        title = item.get("title", "")

        # Price
        price_obj = item.get("price") or {}
        price_text = ""
        if isinstance(price_obj, dict):
            val = price_obj.get("value") or price_obj.get("amount")
            cur = price_obj.get("currency", "PLN")
            if val is not None:
                price_text = f"{val} {cur}"
        elif isinstance(price_obj, (int, float)):
            price_text = f"{price_obj} PLN"

        # Area and rooms from params list
        area_text = ""
        rooms_text = ""
        for param in item.get("params", []):
            key = param.get("key", "")
            value = param.get("value", {})
            val = value.get("value", "") if isinstance(value, dict) else value
            if key in ("m", "surface"):
                area_text = f"{val} m²"
            elif key == "rooms":
                rooms_text = str(val)

        # Location
        loc = item.get("location") or {}
        city = ""
        region = ""
        if isinstance(loc, dict):
            city_obj = loc.get("city") or {}
            region_obj = loc.get("region") or {}
            city = city_obj.get("name", "") if isinstance(city_obj, dict) else str(city_obj or "")
            region = region_obj.get("name", "") if isinstance(region_obj, dict) else str(region_obj or "")
        location_text = ", ".join(filter(None, [city, region]))

        # Images — OLX uses photos[].link
        images_raw = item.get("photos") or item.get("images") or []
        images = []
        for p in images_raw:
            if isinstance(p, str):
                images.append(p)
            elif isinstance(p, dict):
                src = p.get("link") or p.get("url") or p.get("src")
                if src:
                    images.append(src)

        source_created_at = (
            item.get("created_time") or item.get("created_at")
            or item.get("date") or item.get("date_created")
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

                if data.get("@type") == "ItemList":
                    for elem in data.get("itemListElement", []):
                        item_data = elem.get("item", {})
                        if item_data.get("@type") == "Product":
                            offer = self._parse_json_ld_product(item_data)
                            if offer:
                                offers.append(offer)

                elif data.get("@type") == "Product":
                    offer = self._parse_json_ld_product(data)
                    if offer:
                        offers.append(offer)

            except Exception as e:
                logger.debug(f"Failed to parse JSON-LD: {e}")

        return offers

    def _parse_json_ld_product(self, data: dict) -> Optional[OfferNormalized]:
        """Parse a JSON-LD Product into OfferNormalized."""
        offer_data = {
            "url": data.get("url", ""),
            "title": data.get("name", ""),
            "price_text": "",
            "area_text": "",
            "rooms_text": "",
            "location_text": "",
            "source_created_at": (
                data.get("datePosted") or data.get("datePublished") or data.get("dateCreated")
            ),
        }

        offers = data.get("offers", {})
        if isinstance(offers, dict):
            price = offers.get("price")
            currency = offers.get("priceCurrency", "PLN")
            if price:
                offer_data["price_text"] = f"{price} {currency}"

        description = data.get("description", "")
        area_match = re.search(r'(\d+[\s,]?\d*)\s*m[²2]', description)
        if area_match:
            offer_data["area_text"] = area_match.group(0)

        rooms_match = re.search(r'(\d+)\s*pok', description.lower())
        if rooms_match:
            offer_data["rooms_text"] = rooms_match.group(1)

        address = data.get("address", {})
        if isinstance(address, dict):
            city = address.get("addressLocality", "")
            region = address.get("addressRegion", "")
            offer_data["location_text"] = f"{city}, {region}" if city else ""

        normalized = self.normalize_offer(offer_data)
        return normalized if normalized.url and normalized.title else None

    # ------------------------------------------------------------------
    # Embedded window data fallback
    # ------------------------------------------------------------------

    def _extract_from_page_data(self, soup) -> List[OfferNormalized]:
        """Extract offers from embedded page data/scripts."""
        offers = []

        for script in soup.find_all("script"):
            if not script.string:
                continue

            text = script.string
            patterns = [
                r'window\.__INITIAL_STATE__\s*=\s*({.+?});',
                r'window\.__APP_CONFIG__\s*=\s*({.+?});',
                r'"offers":\s*(\[.+?\])',
            ]

            for pattern in patterns:
                match = re.search(pattern, text, re.DOTALL)
                if match:
                    try:
                        data = json.loads(match.group(1))
                        if isinstance(data, list):
                            for item in data:
                                offer = self._parse_api_item(item)
                                if offer:
                                    offers.append(offer)
                    except json.JSONDecodeError:
                        continue

        return offers

    def _parse_api_item(self, item: dict) -> Optional[OfferNormalized]:
        """Parse an API item into OfferNormalized."""
        offer_data = {
            "url": item.get("url", item.get("slug", "")),
            "title": item.get("title", ""),
            "price_text": "",
            "area_text": "",
            "rooms_text": "",
            "location_text": "",
            "source_created_at": (
                item.get("created_time") or item.get("created_at")
                or item.get("date") or item.get("date_created")
            ),
        }

        price = item.get("price", {})
        if isinstance(price, dict):
            value = price.get("value", "")
            currency = price.get("currency", "PLN")
            if value:
                offer_data["price_text"] = f"{value} {currency}"
        elif isinstance(price, (int, float)):
            offer_data["price_text"] = f"{price} PLN"

        location = item.get("location", {})
        if isinstance(location, dict):
            city = location.get("city", {}).get("name", "")
            region = location.get("region", {}).get("name", "")
            offer_data["location_text"] = f"{city}, {region}" if city else ""

        photos = item.get("photos") or item.get("images") or []
        if isinstance(photos, list):
            urls = []
            for p in photos:
                if isinstance(p, str):
                    urls.append(p)
                elif isinstance(p, dict):
                    src = p.get("link") or p.get("url")
                    if src:
                        urls.append(src)
            if urls:
                offer_data["images"] = urls

        for param in item.get("params", []):
            key = param.get("key", "")
            value = param.get("value", {})
            if key == "m":
                val = value.get("value", "") if isinstance(value, dict) else value
                offer_data["area_text"] = f"{val} m²"
            elif key == "rooms":
                val = value.get("value", "") if isinstance(value, dict) else value
                offer_data["rooms_text"] = str(val)

        normalized = self.normalize_offer(offer_data)
        return normalized if normalized.url and normalized.title else None

    # ------------------------------------------------------------------
    # Raw HTML fallback
    # ------------------------------------------------------------------

    def _extract_from_html(self, soup) -> List[OfferNormalized]:
        """Extract offers from HTML structure."""
        offers = []

        listing_selectors = [
            "[data-cy='l-card']",
            "div[data-testid='l-card']",
            "[data-testid='listing-card']",
            ".listing-card",
            ".offer-wrapper",
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
        """Parse a single OLX listing element."""
        offer_data = {
            "url": "", "title": "", "price_text": "",
            "area_text": "", "rooms_text": "", "location_text": "",
        }

        link = listing.find("a", href=True)
        if link:
            href = link.get("href", "")
            offer_data["url"] = urljoin(self.base_url, href) if href.startswith("/") else href

        title_elem = (
            listing.select_one("[data-cy='ad-card-title']") or
            listing.select_one("[data-testid='ad-title']") or
            listing.find("h4") or listing.find("h6") or listing.find("h3") or
            listing.select_one(".title")
        )
        if title_elem:
            offer_data["title"] = title_elem.get_text(strip=True)

        price_elem = (
            listing.select_one("[data-testid='ad-price']") or
            listing.select_one(".price") or
            listing.find(string=re.compile(r'\d+\s*\d*\s*zł'))
        )
        if price_elem:
            offer_data["price_text"] = (
                price_elem.get_text(strip=True) if hasattr(price_elem, 'get_text') else str(price_elem)
            )

        details_text = listing.get_text(" ", strip=True)
        area_match = re.search(r'(\d+[\s,]?\d*)\s*m[²2]', details_text)
        if area_match:
            offer_data["area_text"] = area_match.group(0)

        rooms_match = re.search(r'(\d+)\s*pok', details_text.lower())
        if rooms_match:
            offer_data["rooms_text"] = rooms_match.group(1)

        location_elem = (
            listing.select_one("[data-testid='location-date']") or
            listing.select_one(".location") or
            listing.select_one(".bottom-cell")
        )
        if location_elem:
            location_parts = location_elem.get_text(strip=True).split("-")
            if location_parts:
                offer_data["location_text"] = location_parts[0].strip()

        image_elem = listing.find("img")
        if image_elem:
            src = image_elem.get("src") or image_elem.get("data-src")
            if not src:
                srcset = image_elem.get("srcset", "")
                if srcset:
                    src = srcset.split(",")[0].strip().split(" ")[0]
            if src:
                offer_data["images"] = [urljoin(self.base_url, src)]

        if "sprzedaj z olx" in offer_data.get("title", "").lower():
            return None

        return offer_data if offer_data["url"] else None
