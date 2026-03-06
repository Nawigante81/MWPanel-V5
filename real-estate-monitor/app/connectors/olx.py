"""
OLX.pl connector for real estate listings.
Uses Playwright for dynamic content loading.
"""
import asyncio
import json
import random
import re
from typing import List, Optional
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

    # Category IDs for OLX
    CATEGORY_PATHS = {
        "sale": "nieruchomosci/mieszkania/sprzedaz",
        "rent": "nieruchomosci/mieszkania/wynajem",
    }

    # Region mapping
    REGION_PATHS = {
        "pomorskie": "pomorskie",
        "mazowieckie": "mazowieckie",
        "malopolskie": "malopolskie",
        "slaskie": "slaskie",
    }

    def build_search_url(self, filter_config: FilterConfig) -> str:
        """Build OLX search URL from filters."""
        # Base category path
        category = self.CATEGORY_PATHS.get(
            filter_config.transaction_type,
            self.CATEGORY_PATHS["sale"]
        )

        path_parts = [category]

        # Add region if specified
        if filter_config.region:
            region_path = self.REGION_PATHS.get(
                filter_config.region,
                filter_config.region
            )
            path_parts.append(region_path)

        base_path = "/".join(path_parts)

        # Query parameters
        params = {}

        if filter_config.city:
            params["search[city_id]"] = "0"  # Would need city ID lookup

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
        separator = "?" if query_string else ""

        url = f"{self.base_url}/{base_path}{separator}{query_string}"

        logger.debug("Built OLX URL", extra={"url": url})
        return url

    def canonicalize_url(self, url: str) -> str:
        """Canonicalize OLX URL for deduplication."""
        # Remove tracking parameters
        url = re.sub(r'[?&](utm_|fbclid|gclid|ref|tracking|bs)=[^&]*', '', url)
        # Remove OLX-specific params
        url = re.sub(r'[?&](highlighted|promoted|from)=[^&]*', '', url)
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

                # Block unnecessary resources
                await context.route(
                    "**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2}",
                    lambda route: route.abort(),
                )

            page = await context.new_page()

            # Set extra headers
            await page.set_extra_http_headers({
                "Accept-Language": "pl-PL,pl;q=0.9",
                "DNT": "1",
            })

            # Navigate with timeout
            response = await page.goto(
                url,
                wait_until="networkidle",
                timeout=settings.playwright_navigation_timeout,
            )

            if response and response.status >= 400:
                raise Exception(f"HTTP {response.status}")

            # Wait for content to load
            await asyncio.sleep(random.uniform(1.0, 2.0))

            # Handle cookie consent if present
            try:
                cookie_button = await page.wait_for_selector(
                    "button[data-testid='cookie-banner-accept-all']",
                    timeout=5000,
                )
                if cookie_button:
                    await cookie_button.click()
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

        offers = []
        soup = BeautifulSoup(page_content, "html.parser")

        # Try multiple extraction strategies and merge
        json_ld_offers = self._extract_from_json_ld(soup)
        html_offers = self._extract_from_html(soup)

        offers.extend(json_ld_offers)
        offers.extend(html_offers)

        # If still empty, try embedded page data
        if not offers:
            api_offers = self._extract_from_page_data(soup)
            offers.extend(api_offers)

        logger.info(
            "Extracted offers from OLX",
            extra={"count": len(offers)},
        )

        return offers

    def _extract_from_json_ld(self, soup) -> List[OfferNormalized]:
        """Extract offers from JSON-LD structured data."""
        offers = []

        scripts = soup.find_all("script", type="application/ld+json")

        for script in scripts:
            try:
                data = json.loads(script.string)

                # Handle ItemList
                if data.get("@type") == "ItemList":
                    items = data.get("itemListElement", [])
                    for item in items:
                        item_data = item.get("item", {})
                        if item_data.get("@type") == "Product":
                            offer = self._parse_json_ld_product(item_data)
                            if offer:
                                offers.append(offer)

                # Handle single Product
                elif data.get("@type") == "Product":
                    offer = self._parse_json_ld_product(data)
                    if offer:
                        offers.append(offer)

            except (json.JSONDecodeError, Exception) as e:
                logger.debug(f"Failed to parse JSON-LD: {e}")
                continue

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
                data.get("datePosted")
                or data.get("datePublished")
                or data.get("dateCreated")
            ),
        }

        # Extract price
        offers = data.get("offers", {})
        if isinstance(offers, dict):
            price = offers.get("price")
            currency = offers.get("priceCurrency", "PLN")
            if price:
                offer_data["price_text"] = f"{price} {currency}"

        # Extract from description
        description = data.get("description", "")

        # Try to extract area
        area_match = re.search(r'(\d+[\s,]?\d*)\s*m[²2]', description)
        if area_match:
            offer_data["area_text"] = area_match.group(0)

        # Try to extract rooms
        rooms_match = re.search(r'(\d+)\s*pok', description.lower())
        if rooms_match:
            offer_data["rooms_text"] = rooms_match.group(1)

        # Location
        address = data.get("address", {})
        if isinstance(address, dict):
            city = address.get("addressLocality", "")
            region = address.get("addressRegion", "")
            offer_data["location_text"] = f"{city}, {region}" if city else ""

        normalized = self.normalize_offer(offer_data)
        return normalized if normalized.url and normalized.title else None

    def _extract_from_html(self, soup) -> List[OfferNormalized]:
        """Extract offers from HTML structure."""
        offers = []

        # OLX listing selectors
        listing_selectors = [
            "[data-cy='l-card']",
            ".listing-card",
            "[data-testid='listing-card']",
            ".offer-wrapper",
            "div[data-testid='l-card']",
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
                continue

        return offers

    def _parse_listing_element(self, listing) -> Optional[dict]:
        """Parse a single OLX listing element."""
        offer_data = {
            "url": "",
            "title": "",
            "price_text": "",
            "area_text": "",
            "rooms_text": "",
            "location_text": "",
        }

        # URL
        link = listing.find("a", href=True)
        if link:
            href = link.get("href", "")
            # OLX sometimes uses relative URLs
            if href.startswith("/"):
                href = urljoin(self.base_url, href)
            offer_data["url"] = href

        # Title
        title_elem = (
            listing.select_one("[data-cy='ad-card-title']") or
            listing.select_one("[data-testid='ad-title']") or
            listing.find("h4") or
            listing.find("h6") or
            listing.find("h3") or
            listing.select_one(".title")
        )
        if title_elem:
            offer_data["title"] = title_elem.get_text(strip=True)

        # Price
        price_elem = (
            listing.select_one("[data-testid='ad-price']") or
            listing.select_one(".price") or
            listing.find(string=re.compile(r'\d+\s*\d*\s*zł'))
        )
        if price_elem:
            if hasattr(price_elem, 'get_text'):
                offer_data["price_text"] = price_elem.get_text(strip=True)
            else:
                offer_data["price_text"] = str(price_elem)

        # Area and rooms from details
        details_elem = (
            listing.select_one("[data-testid='ad-params']") or
            listing.select_one(".details") or
            listing.select_one(".params")
        )
        details_text = details_elem.get_text(strip=True) if details_elem else listing.get_text(" ", strip=True)

        # Extract area
        area_match = re.search(r'(\d+[\s,]?\d*)\s*m[²2]', details_text)
        if area_match:
            offer_data["area_text"] = area_match.group(0)

        # Extract rooms
        rooms_match = re.search(r'(\d+)\s*pok', details_text.lower())
        if rooms_match:
            offer_data["rooms_text"] = rooms_match.group(1)

        # Location
        location_elem = (
            listing.select_one("[data-testid='location-date']") or
            listing.select_one(".location") or
            listing.select_one(".bottom-cell")
        )
        if location_elem:
            location_text = location_elem.get_text(strip=True)
            # Extract just the location part (before date)
            location_parts = location_text.split("-")
            if location_parts:
                offer_data["location_text"] = location_parts[0].strip()
            if len(location_parts) > 1:
                offer_data["source_created_at"] = location_parts[-1].strip()

        # Image
        image_elem = listing.find("img")
        if image_elem:
            src = image_elem.get("src") or image_elem.get("data-src")
            if not src:
                srcset = image_elem.get("srcset")
                if srcset:
                    src = srcset.split(",")[0].strip().split(" ")[0]
            if src:
                offer_data["images"] = [urljoin(self.base_url, src)]

        # Skip OLX promo card without real listing url/title
        if "sprzedaj z olx" in offer_data.get("title", "").lower():
            return None

        return offer_data if offer_data["url"] else None

    def _extract_from_page_data(self, soup) -> List[OfferNormalized]:
        """Extract offers from embedded page data/scripts."""
        offers = []

        # Look for window.__APP_CONFIG or similar
        scripts = soup.find_all("script")

        for script in scripts:
            if not script.string:
                continue

            text = script.string

            # Look for various data patterns
            patterns = [
                r'window\.__APP_CONFIG__\s*=\s*({.+?});',
                r'window\.__INITIAL_STATE__\s*=\s*({.+?});',
                r'"offers":\s*(\[.+?\])',
            ]

            for pattern in patterns:
                match = re.search(pattern, text, re.DOTALL)
                if match:
                    try:
                        data = json.loads(match.group(1))
                        # Parse based on structure
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
                item.get("created_time")
                or item.get("created_at")
                or item.get("date")
                or item.get("date_created")
            ),
        }

        # Price
        price = item.get("price", {})
        if isinstance(price, dict):
            value = price.get("value", "")
            currency = price.get("currency", "PLN")
            if value:
                offer_data["price_text"] = f"{value} {currency}"
        elif isinstance(price, (int, float)):
            offer_data["price_text"] = f"{price} PLN"

        # Location
        location = item.get("location", {})
        if isinstance(location, dict):
            city = location.get("city", {}).get("name", "")
            region = location.get("region", {}).get("name", "")
            offer_data["location_text"] = f"{city}, {region}" if city else ""

        # Image
        photos = item.get("photos") or item.get("images") or []
        if isinstance(photos, list):
            urls = []
            for p in photos:
                if isinstance(p, str):
                    urls.append(p)
                elif isinstance(p, dict):
                    if p.get("link"):
                        urls.append(p["link"])
                    elif p.get("url"):
                        urls.append(p["url"])
            if urls:
                offer_data["images"] = urls

        # Params
        params = item.get("params", [])
        for param in params:
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
