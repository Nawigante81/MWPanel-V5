"""
Otodom.pl connector for real estate listings.
Uses Playwright for dynamic content loading.
"""
import asyncio
import json
import random
import re
from typing import List, Optional
from urllib.parse import urlencode, urljoin

from playwright.async_api import BrowserContext, Page, async_playwright

from app.connectors.base import BaseConnector, ConnectorRegistry, FilterConfig
from app.logging_config import get_logger
from app.schemas import OfferNormalized
from app.settings import settings

logger = get_logger("connectors.otodom")


@ConnectorRegistry.register
class OtodomConnector(BaseConnector):
    """Connector for Otodom.pl real estate listings."""

    name = "otodom"
    base_url = "https://www.otodom.pl"
    fetch_mode = "playwright"

    # Region mapping for OtodOM
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

        # Transaction type
        if filter_config.transaction_type == "sale":
            path_parts.append("sprzedaz")
        else:
            path_parts.append("wynajem")

        # Property type
        if filter_config.property_type:
            path_parts.append(filter_config.property_type)
        else:
            path_parts.append("mieszkanie")  # Default to apartments

        # Region
        region = filter_config.region or "pomorskie"
        path_parts.append(region)

        base_path = "/".join(path_parts)

        # Query parameters
        params = {}

        if filter_config.city:
            params["search[region_id]"] = "1"  # Placeholder, would need city ID lookup

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
        url = f"{self.base_url}/{base_path}?{query_string}"

        logger.debug("Built Otodom URL", extra={"url": url})
        return url

    def canonicalize_url(self, url: str) -> str:
        """Canonicalize Otodom URL for deduplication."""
        # Remove tracking parameters
        import re
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
        """Extract offers from Otodom page content."""
        from bs4 import BeautifulSoup

        offers = []
        soup = BeautifulSoup(page_content, "html.parser")

        # Try to extract from JSON-LD first (more reliable)
        json_ld_offers = self._extract_from_json_ld(soup)
        if json_ld_offers:
            offers.extend(json_ld_offers)

        # Fallback to HTML parsing
        if not offers:
            html_offers = self._extract_from_html(soup)
            offers.extend(html_offers)

        logger.info(
            "Extracted offers from Otodom",
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

                # Handle both single item and array
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

                    # Extract price
                    offers_data = item.get("offers", {})
                    if isinstance(offers_data, dict):
                        price = offers_data.get("price")
                        currency = offers_data.get("priceCurrency", "PLN")
                        if price:
                            offer_data["price_text"] = f"{price} {currency}"

                    # Extract from description
                    description = item.get("description", "")

                    # Try to extract area from description
                    area_match = re.search(r'(\d+[\s,]?\d*)\s*m[²2]', description)
                    if area_match:
                        offer_data["area_text"] = area_match.group(0)

                    # Try to extract rooms
                    rooms_match = re.search(r'(\d+)\s*pok', description.lower())
                    if rooms_match:
                        offer_data["rooms_text"] = rooms_match.group(1)

                    # Location
                    address = item.get("address", {})
                    if isinstance(address, dict):
                        city = address.get("addressLocality", "")
                        region = address.get("addressRegion", "")
                        offer_data["location_text"] = f"{city}, {region}"

                    # Coordinates
                    geo = item.get("geo", {})
                    if isinstance(geo, dict):
                        offer_data["lat"] = geo.get("latitude")
                        offer_data["lng"] = geo.get("longitude")

                    # Images
                    image = item.get("image")
                    if isinstance(image, str) and image:
                        offer_data["images"] = [image]
                    elif isinstance(image, list):
                        offer_data["images"] = [img for img in image if isinstance(img, str)]

                    normalized = self.normalize_offer(offer_data)
                    if normalized.url and normalized.title:
                        offers.append(normalized)

            except (json.JSONDecodeError, Exception) as e:
                logger.debug(f"Failed to parse JSON-LD: {e}")
                continue

        return offers

    def _extract_from_html(self, soup) -> List[OfferNormalized]:
        """Extract offers from HTML structure."""
        offers = []

        # Otodom listing selectors (may need updates as site changes)
        listing_selectors = [
            "[data-cy='listing-item']",
            ".listing-item",
            "[data-testid='listing-item']",
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
                continue

        return offers

    def _parse_listing_element(self, listing) -> Optional[dict]:
        """Parse a single listing element."""
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
            offer_data["url"] = urljoin(self.base_url, href)

        # Title
        title_elem = (
            listing.select_one("[data-cy='listing-item-title']") or
            listing.select_one("[data-testid='listing-title']") or
            listing.find("h3") or
            listing.find("h2") or
            listing.select_one(".listing-title")
        )
        if title_elem:
            offer_data["title"] = title_elem.get_text(strip=True)

        # Price
        price_elem = (
            listing.select_one("[data-testid='listing-price']") or
            listing.select_one("[data-cy='price']") or
            listing.select_one(".listing-price") or
            listing.find(string=re.compile(r'\d+\s*\d*\s*zł'))
        )
        if price_elem:
            if hasattr(price_elem, 'get_text'):
                offer_data["price_text"] = price_elem.get_text(strip=True)
            else:
                offer_data["price_text"] = str(price_elem)

        # Area and rooms
        params_elem = (
            listing.select_one("[data-testid='listing-params']") or
            listing.select_one(".listing-params") or
            listing.select_one(".params-list")
        )
        params_text = params_elem.get_text(strip=True) if params_elem else listing.get_text(" ", strip=True)

        # Extract area
        area_match = re.search(r'(\d+[\s,]?\d*)\s*m[²2]', params_text)
        if area_match:
            offer_data["area_text"] = area_match.group(0)

        # Extract rooms
        rooms_match = re.search(r'(\d+)\s*pok', params_text.lower())
        if rooms_match:
            offer_data["rooms_text"] = rooms_match.group(1)

        # Location
        location_elem = (
            listing.select_one("[data-testid='listing-location']") or
            listing.select_one(".listing-location") or
            listing.select_one(".location")
        )
        if location_elem:
            offer_data["location_text"] = location_elem.get_text(strip=True)

        # Publication date (if present in card)
        time_elem = listing.find("time")
        if time_elem:
            offer_data["source_created_at"] = time_elem.get("datetime") or time_elem.get_text(strip=True)

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

        return offer_data if offer_data["url"] else None
