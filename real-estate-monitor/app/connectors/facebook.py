"""
Facebook Marketplace connector for real estate listings.
Uses Playwright with cookie injection for authenticated access.
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

logger = get_logger("connectors.facebook")


@ConnectorRegistry.register
class FacebookConnector(BaseConnector):
    """Connector for Facebook Marketplace real estate listings."""
    
    name = "facebook"
    base_url = "https://www.facebook.com"
    fetch_mode = "playwright"
    
    def build_search_url(self, filter_config: FilterConfig) -> str:
        """Build Facebook Marketplace search URL from filters."""
        # Facebook Marketplace uses query-based search
        params = {
            "sortBy": "creation_time_descend",  # Newest first
        }
        
        # Build search query
        query_parts = ["nieruchomości", "mieszkanie"]
        
        if filter_config.city:
            query_parts.append(filter_config.city)
        elif filter_config.region:
            query_parts.append(filter_config.region)
        
        params["query"] = " ".join(query_parts)
        
        # Price filters
        if filter_config.min_price:
            params["minPrice"] = filter_config.min_price
        
        if filter_config.max_price:
            params["maxPrice"] = filter_config.max_price
        
        # Facebook uses specific category for property rentals/sales
        if filter_config.transaction_type == "rent":
            params["category_id"] = "1157218201037950"  # Property Rentals
        else:
            params["category_id"] = "1154501386233295"  # Property for Sale
        
        query_string = urlencode(params)
        url = f"{self.base_url}/marketplace/search?{query_string}"
        
        logger.debug("Built Facebook URL", extra={"url": url})
        return url
    
    def canonicalize_url(self, url: str) -> str:
        """Canonicalize Facebook URL for deduplication."""
        # Facebook URLs are generally stable for marketplace items
        # Remove tracking parameters
        url = re.sub(r'[?&](__tn__|__cft__|hc_ref|ref)=[^&]*', '', url)
        return url.split('?')[0] if '?' in url else url
    
    async def _inject_cookies(self, context: BrowserContext) -> None:
        """Inject Facebook cookies from environment."""
        if not settings.fb_cookies_json:
            logger.warning("No Facebook cookies configured")
            return
        
        try:
            cookies = settings.fb_cookies_json
            
            # Convert to Playwright format if needed
            playwright_cookies = []
            for cookie in cookies:
                pw_cookie = {
                    "name": cookie.get("name"),
                    "value": cookie.get("value"),
                    "domain": cookie.get("domain", ".facebook.com"),
                    "path": cookie.get("path", "/"),
                }
                
                if cookie.get("expires"):
                    pw_cookie["expires"] = cookie.get("expires")
                
                if cookie.get("secure"):
                    pw_cookie["secure"] = cookie.get("secure")
                
                if cookie.get("httpOnly"):
                    pw_cookie["httpOnly"] = cookie.get("httpOnly")
                
                playwright_cookies.append(pw_cookie)
            
            await context.add_cookies(playwright_cookies)
            logger.info("Injected Facebook cookies")
            
        except Exception as e:
            logger.error(f"Failed to inject cookies: {e}")
    
    async def fetch_with_playwright(
        self,
        url: str,
        context: Optional[BrowserContext] = None,
    ) -> str:
        """Fetch page using Playwright with cookie injection."""
        
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
                        "--disable-extensions",
                    ],
                )
                
                context = await browser.new_context(
                    user_agent=self.user_agent,
                    viewport={"width": 1920, "height": 1080},
                    locale="pl-PL",
                    timezone_id="Europe/Warsaw",
                )
                
                # Inject cookies for authentication
                await self._inject_cookies(context)
                
                # Block unnecessary resources
                await context.route(
                    "**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2,mp4,webm}",
                    lambda route: route.abort(),
                )
            
            page = await context.new_page()
            
            # Set extra headers
            await page.set_extra_http_headers({
                "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8",
                "DNT": "1",
                "Upgrade-Insecure-Requests": "1",
            })
            
            # Navigate with timeout
            response = await page.goto(
                url,
                wait_until="networkidle",
                timeout=settings.playwright_navigation_timeout,
            )
            
            if response and response.status >= 400:
                raise Exception(f"HTTP {response.status}")
            
            # Wait for content to load (Facebook is slow)
            await asyncio.sleep(random.uniform(2.0, 4.0))
            
            # Check for login wall
            login_indicators = [
                "log in",
                "zaloguj",
                "create account",
                "utwórz konto",
            ]
            
            content_check = await page.content()
            content_lower = content_check.lower()
            
            for indicator in login_indicators:
                if indicator in content_lower:
                    logger.warning("Facebook login wall detected - cookies may be expired")
                    break
            
            # Scroll to trigger lazy loading
            await page.evaluate("""
                async () => {
                    await new Promise((resolve) => {
                        let totalHeight = 0;
                        const distance = 400;
                        const timer = setInterval(() => {
                            const scrollHeight = document.body.scrollHeight;
                            window.scrollBy(0, distance);
                            totalHeight += distance;
                            
                            if (totalHeight >= scrollHeight || totalHeight > 5000) {
                                clearInterval(timer);
                                resolve();
                            }
                        }, 150);
                    });
                }
            """)
            
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
        """Extract offers from Facebook page content."""
        from bs4 import BeautifulSoup
        
        offers = []
        soup = BeautifulSoup(page_content, "html.parser")
        
        # Try to extract from embedded JSON data first
        json_offers = self._extract_from_json_data(soup)
        if json_offers:
            offers.extend(json_offers)
        
        # Fallback to HTML parsing
        if not offers:
            html_offers = self._extract_from_html(soup)
            offers.extend(html_offers)
        
        logger.info(
            "Extracted offers from Facebook",
            extra={"count": len(offers)},
        )
        
        return offers
    
    def _extract_from_json_data(self, soup) -> List[OfferNormalized]:
        """Extract offers from embedded JSON data."""
        offers = []
        
        # Look for marketplace data in scripts
        scripts = soup.find_all("script")
        
        for script in scripts:
            if not script.string:
                continue
            
            text = script.string
            
            # Look for marketplace feed data
            patterns = [
                r'"marketplace_search":\s*({.+?"feed_units":.+?})',
                r'"feed_units":\s*(\{.+?\})',
                r'"marketplace_item_details":\s*(\{.+?\})',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, text, re.DOTALL)
                
                for match in matches:
                    try:
                        # Try to parse as JSON
                        data = json.loads(match)
                        
                        # Extract feed units
                        feed_units = data.get("feed_units", {}).get("edges", [])
                        
                        for unit in feed_units:
                            node = unit.get("node", {})
                            listing = node.get("listing", {})
                            
                            if listing:
                                offer = self._parse_marketplace_listing(listing)
                                if offer:
                                    offers.append(offer)
                                    
                    except (json.JSONDecodeError, Exception) as e:
                        logger.debug(f"Failed to parse JSON data: {e}")
                        continue
        
        return offers
    
    def _parse_marketplace_listing(self, listing: dict) -> Optional[OfferNormalized]:
        """Parse a Facebook marketplace listing."""
        offer_data = {
            "url": "",
            "title": "",
            "price_text": "",
            "area_text": "",
            "rooms_text": "",
            "location_text": "",
        }
        
        # ID and URL
        listing_id = listing.get("id", "")
        if listing_id:
            offer_data["url"] = f"{self.base_url}/marketplace/item/{listing_id}"
        
        # Title
        marketplace_title = listing.get("marketplace_listing_title", "")
        story = listing.get("story", {})
        story_title = story.get("story_title", {}).get("text", "") if isinstance(story.get("story_title"), dict) else ""
        
        offer_data["title"] = marketplace_title or story_title
        
        # Price
        price_info = listing.get("listing_price", {})
        if isinstance(price_info, dict):
            amount = price_info.get("amount", "")
            currency = price_info.get("currency", "PLN")
            if amount:
                offer_data["price_text"] = f"{amount} {currency}"
        
        # Location
        location = listing.get("location", {})
        if isinstance(location, dict):
            city = location.get("reverse_geocode", {}).get("city", "")
            state = location.get("reverse_geocode", {}).get("state", "")
            offer_data["location_text"] = f"{city}, {state}" if city else ""
        
        # Description for area/rooms extraction
        description = listing.get("commerce_item_details", {}).get("description", {}).get("text", "")
        
        # Try to extract area from description
        area_match = re.search(r'(\d+[\s,]?\d*)\s*m[²2]', description)
        if area_match:
            offer_data["area_text"] = area_match.group(0)
        
        # Try to extract rooms
        rooms_match = re.search(r'(\d+)\s*pok', description.lower())
        if rooms_match:
            offer_data["rooms_text"] = rooms_match.group(1)
        
        normalized = self.normalize_offer(offer_data)
        return normalized if normalized.url and normalized.title else None
    
    def _extract_from_html(self, soup) -> List[OfferNormalized]:
        """Extract offers from HTML structure."""
        offers = []
        
        # Facebook Marketplace listing selectors
        # Note: These are brittle and may need frequent updates
        listing_selectors = [
            "[role='article']",
            "[data-testid='marketplace_search_feed_item']",
            ".x1gslohp",  # Common FB class pattern
        ]
        
        listings = []
        for selector in listing_selectors:
            listings = soup.select(selector)
            if listings:
                break
        
        for listing in listings:
            try:
                offer_data = self._parse_html_listing(listing)
                if offer_data:
                    normalized = self.normalize_offer(offer_data)
                    if normalized.url and normalized.title:
                        offers.append(normalized)
            except Exception as e:
                logger.debug(f"Failed to parse listing: {e}")
                continue
        
        return offers
    
    def _parse_html_listing(self, listing) -> Optional[dict]:
        """Parse a single HTML listing element."""
        offer_data = {
            "url": "",
            "title": "",
            "price_text": "",
            "area_text": "",
            "rooms_text": "",
            "location_text": "",
        }
        
        # Find link
        link = listing.find("a", href=re.compile(r'/marketplace/item/'))
        if link:
            href = link.get("href", "")
            offer_data["url"] = urljoin(self.base_url, href.split("?")[0])
        
        # Find title - usually in an anchor or span
        title_elem = listing.find(text=re.compile(r'(?i)mieszkanie|dom|kawalerka|apartament'))
        if title_elem:
            parent = title_elem.parent
            if parent:
                offer_data["title"] = parent.get_text(strip=True)
        
        # Find price
        price_elem = listing.find(text=re.compile(r'\d+[\s\d]*\s*zł'))
        if price_elem:
            offer_data["price_text"] = str(price_elem).strip()
        
        # Find location
        location_patterns = [
            re.compile(r'(?i)(gdansk|gdańsk|sopot|gdynia|warszawa|kraków|krakow|wrocław|wroclaw|poznań|poznan)'),
        ]
        
        for pattern in location_patterns:
            location_elem = listing.find(text=pattern)
            if location_elem:
                offer_data["location_text"] = str(location_elem).strip()
                break
        
        return offer_data if offer_data["url"] else None
