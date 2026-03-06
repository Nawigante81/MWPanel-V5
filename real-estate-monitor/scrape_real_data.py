#!/usr/bin/env python3
"""
Scraper for fetching real estate data from free sources.
Saves data to JSON for frontend consumption.
"""
import asyncio
import json
import re
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlencode

import httpx
from bs4 import BeautifulSoup


class OtodomScraper:
    """Simple scraper for Otodom.pl listings."""
    
    BASE_URL = "https://www.otodom.pl"
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "pl-PL,pl;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
    }
    
    def __init__(self):
        self.client = httpx.AsyncClient(headers=self.HEADERS, timeout=30.0, follow_redirects=True)
    
    async def close(self):
        await self.client.aclose()
    
    def build_url(self, city: str = "warszawa", transaction: str = "sprzedaz", 
                  property_type: str = "mieszkanie", page: int = 1) -> str:
        """Build search URL."""
        path = f"/pl/wyniki/{transaction}/{property_type}/{city}"
        params = {"page": page}
        return f"{self.BASE_URL}{path}?{urlencode(params)}"
    
    async def fetch_page(self, url: str) -> str:
        """Fetch page content."""
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return ""
    
    def parse_listings(self, html: str) -> List[Dict]:
        """Parse listings from HTML."""
        listings = []
        soup = BeautifulSoup(html, "html.parser")
        
        # Try to find listing items
        listing_selectors = [
            "[data-cy='listing-item']",
            "[data-testid='listing-item']",
            ".listing-item",
            "article[data-testid]",
            ".offer-item",
        ]
        
        items = []
        for selector in listing_selectors:
            items = soup.select(selector)
            if items:
                print(f"Found {len(items)} items with selector: {selector}")
                break
        
        # Also try JSON-LD
        json_ld_data = self._extract_json_ld(soup)
        if json_ld_data:
            print(f"Found {len(json_ld_data)} items in JSON-LD")
            return json_ld_data
        
        for item in items:
            try:
                listing = self._parse_item(item)
                if listing:
                    listings.append(listing)
            except Exception as e:
                print(f"Error parsing item: {e}")
                continue
        
        return listings
    
    def _extract_json_ld(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract data from JSON-LD scripts."""
        listings = []
        scripts = soup.find_all("script", type="application/ld+json")
        
        for script in scripts:
            try:
                data = json.loads(script.string)
                items = data if isinstance(data, list) else [data]
                
                for item in items:
                    if item.get("@type") == "Product":
                        listing = self._parse_json_ld_item(item)
                        if listing:
                            listings.append(listing)
            except Exception as e:
                continue
        
        return listings
    
    def _parse_json_ld_item(self, item: Dict) -> Optional[Dict]:
        """Parse a JSON-LD item."""
        try:
            offers = item.get("offers", {})
            price = None
            currency = "PLN"
            
            if isinstance(offers, dict):
                price = offers.get("price")
                currency = offers.get("priceCurrency", "PLN")
            
            address = item.get("address", {})
            city = ""
            region = ""
            
            if isinstance(address, dict):
                city = address.get("addressLocality", "")
                region = address.get("addressRegion", "")
            
            # Extract area and rooms from description
            description = item.get("description", "")
            area = self._extract_area(description)
            rooms = self._extract_rooms(description)
            
            return {
                "id": f"otodom_{hash(item.get('url', ''))}",
                "title": item.get("name", ""),
                "price": price,
                "currency": currency,
                "city": city,
                "district": "",
                "area_sqm": area,
                "rooms": rooms,
                "property_type": "apartment",
                "transaction_type": "sale",
                "status": "active",
                "url": item.get("url", ""),
                "description": description,
                "source": "Otodom",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
        except Exception as e:
            return None
    
    def _parse_item(self, item) -> Optional[Dict]:
        """Parse a single listing item."""
        try:
            # URL
            link = item.find("a", href=True)
            if not link:
                return None
            url = urljoin(self.BASE_URL, link.get("href", ""))
            
            # Title
            title_elem = item.find("h3") or item.find("h2") or item.find("[data-testid='listing-title']")
            title = title_elem.get_text(strip=True) if title_elem else ""
            
            # Price
            price_text = ""
            price_elem = item.find(attrs={"data-testid": "listing-price"}) or item.find(class_="listing-price")
            if price_elem:
                price_text = price_elem.get_text(strip=True)
            
            price, currency = self._parse_price(price_text)
            
            # Location
            location_text = ""
            location_elem = item.find(attrs={"data-testid": "listing-location"}) or item.find(class_="listing-location")
            if location_elem:
                location_text = location_elem.get_text(strip=True)
            
            city, district = self._parse_location(location_text)
            
            # Area and rooms
            params_text = ""
            params_elem = item.find(attrs={"data-testid": "listing-params"}) or item.find(class_="listing-params")
            if params_elem:
                params_text = params_elem.get_text(strip=True)
            
            area = self._extract_area(params_text)
            rooms = self._extract_rooms(params_text)
            
            return {
                "id": f"otodom_{hash(url)}",
                "title": title,
                "price": price,
                "currency": currency,
                "city": city,
                "district": district,
                "area_sqm": area,
                "rooms": rooms,
                "property_type": "apartment",
                "transaction_type": "sale",
                "status": "active",
                "url": url,
                "description": "",
                "source": "Otodom",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
        except Exception as e:
            print(f"Error parsing item: {e}")
            return None
    
    def _parse_price(self, price_text: str) -> tuple:
        """Parse price from text."""
        if not price_text:
            return None, "PLN"
        
        # Remove spaces and extract number
        match = re.search(r'([\d\s]+)\s*(zł|PLN|EUR|USD)?', price_text.replace(' ', '').replace(',', '.'))
        if match:
            price_str = match.group(1).replace(' ', '').replace(',', '')
            try:
                price = int(price_str)
                currency = match.group(2) if match.group(2) else "PLN"
                return price, currency
            except:
                pass
        
        return None, "PLN"
    
    def _parse_location(self, location_text: str) -> tuple:
        """Parse city and district from location."""
        if not location_text:
            return "", ""
        
        parts = [p.strip() for p in location_text.split(",")]
        if len(parts) >= 2:
            return parts[0], parts[1]
        elif len(parts) == 1:
            return parts[0], ""
        
        return "", ""
    
    def _extract_area(self, text: str) -> Optional[int]:
        """Extract area from text."""
        if not text:
            return None
        
        match = re.search(r'(\d+[\s,]?\d*)\s*m[²2]', text)
        if match:
            try:
                area_str = match.group(1).replace(' ', '').replace(',', '.')
                return int(float(area_str))
            except:
                pass
        
        return None
    
    def _extract_rooms(self, text: str) -> Optional[int]:
        """Extract number of rooms from text."""
        if not text:
            return None
        
        match = re.search(r'(\d+)\s*pok', text.lower())
        if match:
            try:
                return int(match.group(1))
            except:
                pass
        
        return None


class MockDataGenerator:
    """Generate realistic mock data based on real market prices."""
    
    CITIES = [
        ("Warszawa", "Mokotów", 12000, 18000),
        ("Warszawa", "Śródmieście", 15000, 22000),
        ("Warszawa", "Wola", 10000, 15000),
        ("Kraków", "Stare Miasto", 13000, 19000),
        ("Kraków", "Podgórze", 10000, 14000),
        ("Kraków", "Krowodrza", 11000, 16000),
        ("Wrocław", "Krzyki", 9000, 13000),
        ("Wrocław", "Śródmieście", 10000, 15000),
        ("Gdańsk", "Śródmieście", 11000, 16000),
        ("Gdańsk", "Wrzeszcz", 10000, 14000),
        ("Poznań", "Stare Miasto", 9000, 13000),
        ("Łódź", "Śródmieście", 7000, 10000),
    ]
    
    STREETS = [
        "ul. Marszałkowska", "ul. Puławska", "ul. Wilcza", "ul. Nowy Świat",
        "ul. Grodzka", "ul. Floriańska", "ul. Starowiślna", "ul. Dietla",
        "ul. Oławska", "ul. Ruska", "ul. Świdnicka", "ul. Legnicka",
        "ul. Długa", "ul. Długi Targ", "ul. Grunwaldzka", "ul. Zwycięstwa",
        "ul. Piotrkowska", "ul. Gdańska", "ul. Wschodnia", "ul. Zachodnia",
    ]
    
    TITLES = [
        "Przestronne mieszkanie w centrum",
        "Nowoczesne mieszkanie z balkonem",
        "Mieszkanie po remoncie",
        "Klimatyczne mieszkanie w kamienicy",
        "Mieszkanie w nowym budownictwie",
        "Mieszkanie z widokiem na park",
        "Mieszkanie w spokojnej okolicy",
        "Mieszkanie blisko metra",
        "Mieszkanie dla rodziny",
        "Mieszkanie inwestycyjne",
        "Luksusowe mieszkanie",
        "Mieszkanie z garażem",
    ]
    
    DESCRIPTIONS = [
        "Mieszkanie o wysokim standardzie wykończenia. W pobliżu sklepy, szkoły i przystanki komunikacji miejskiej.",
        "Przestronne i jasne mieszkanie z dużym balkonem. Idealne dla pary lub małej rodziny.",
        "Mieszkanie po kapitalnym remoncie. Nowa instalacja elektryczna i hydrauliczna.",
        "Klimatyczne mieszkanie w zabytkowej kamienicy. Wysokie sufity i oryginalne drzwi.",
        "Nowoczesne mieszkanie w apartamentowcu z ochroną i monitoringiem.",
    ]
    
    def generate_listings(self, count: int = 50) -> List[Dict]:
        """Generate realistic mock listings."""
        import random
        
        listings = []
        for i in range(count):
            city, district, price_min, price_max = random.choice(self.CITIES)
            area = random.randint(28, 120)
            rooms = random.randint(1, 5)
            
            # Calculate realistic price
            price_per_m2 = random.randint(price_min, price_max)
            price = area * price_per_m2
            
            street = random.choice(self.STREETS)
            street_number = random.randint(1, 150)
            
            listing = {
                "id": f"mock_{i+1}",
                "title": f"{random.choice(self.TITLES)} - {rooms} pokoje, {area}m²",
                "price": price,
                "currency": "PLN",
                "city": city,
                "district": district,
                "street": f"{street} {street_number}",
                "area_sqm": area,
                "rooms": rooms,
                "floor": random.randint(0, 10),
                "total_floors": random.randint(4, 12),
                "year_built": random.randint(1960, 2023),
                "property_type": random.choice(["apartment", "house", "commercial"]),
                "transaction_type": "sale",
                "status": random.choice(["active", "active", "active", "reserved", "sold"]),
                "url": f"https://example.com/listing/{i+1}",
                "description": random.choice(self.DESCRIPTIONS),
                "source": "Mock Data",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
            listings.append(listing)
        
        return listings


async def scrape_otodom():
    """Scrape data from Otodom."""
    scraper = OtodomScraper()
    all_listings = []
    
    cities = ["warszawa", "krakow", "wroclaw", "gdansk", "poznan", "lodz"]
    
    for city in cities:
        print(f"Scraping {city}...")
        url = scraper.build_url(city=city, page=1)
        html = await scraper.fetch_page(url)
        
        if html:
            listings = scraper.parse_listings(html)
            print(f"  Found {len(listings)} listings")
            all_listings.extend(listings)
        
        # Be nice to the server
        await asyncio.sleep(1)
    
    await scraper.close()
    return all_listings


def generate_mock_data():
    """Generate realistic mock data."""
    generator = MockDataGenerator()
    return generator.generate_listings(100)


def save_to_json(listings: List[Dict], filename: str):
    """Save listings to JSON file."""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(listings, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(listings)} listings to {filename}")


def save_to_frontend_json(listings: List[Dict], filename: str):
    """Save listings in frontend-compatible format."""
    # Transform to match frontend schema
    transformed = []
    for listing in listings:
        transformed.append({
            "id": listing.get("id", ""),
            "title": listing.get("title", ""),
            "price": listing.get("price", 0),
            "currency": listing.get("currency", "PLN"),
            "city": listing.get("city", ""),
            "district": listing.get("district", ""),
            "street": listing.get("street", ""),
            "area_sqm": listing.get("area_sqm"),
            "rooms": listing.get("rooms"),
            "floor": listing.get("floor"),
            "total_floors": listing.get("total_floors"),
            "year_built": listing.get("year_built"),
            "property_type": listing.get("property_type", "apartment"),
            "transaction_type": listing.get("transaction_type", "sale"),
            "status": listing.get("status", "active"),
            "source": listing.get("source", ""),
            "description": listing.get("description", ""),
            "url": listing.get("url", ""),
            "created_at": listing.get("created_at", datetime.now().isoformat()),
            "updated_at": listing.get("updated_at", datetime.now().isoformat()),
        })
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(transformed, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(transformed)} listings to {filename}")


async def main():
    """Main function."""
    print("=" * 60)
    print("Real Estate Data Scraper")
    print("=" * 60)
    
    # Try to scrape Otodom first
    print("\n1. Attempting to scrape Otodom.pl...")
    try:
        otodom_listings = await scrape_otodom()
        if otodom_listings:
            save_to_frontend_json(otodom_listings, "/mnt/okcomputer/output/app/public/data/listings.json")
            print(f"Successfully scraped {len(otodom_listings)} listings from Otodom")
        else:
            print("No listings found from Otodom, falling back to mock data")
            raise Exception("No data")
    except Exception as e:
        print(f"Scraping failed: {e}")
        print("\n2. Generating realistic mock data...")
        mock_listings = generate_mock_data()
        save_to_frontend_json(mock_listings, "/mnt/okcomputer/output/app/public/data/listings.json")
    
    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
