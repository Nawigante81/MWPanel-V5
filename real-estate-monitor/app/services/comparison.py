"""
Offer comparison tool.
Compare multiple offers side by side.
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from decimal import Decimal

from app.logging_config import get_logger
from app.models import Offer

logger = get_logger("comparison")


@dataclass
class ComparisonResult:
    """Result of comparing offers."""
    best_price: Optional[str]  # offer_id
    best_area: Optional[str]
    best_price_per_m2: Optional[str]
    best_location: Optional[str]
    overall_best: Optional[str]
    details: Dict[str, Any]


class OfferComparator:
    """
    Compare multiple offers and find the best one.
    """
    
    def compare_offers(self, offers: List[Offer]) -> ComparisonResult:
        """
        Compare offers and return analysis.
        
        Args:
            offers: List of offers to compare
        
        Returns:
            ComparisonResult with analysis
        """
        if not offers:
            return ComparisonResult(None, None, None, None, None, {})
        
        if len(offers) == 1:
            return ComparisonResult(
                str(offers[0].id),
                str(offers[0].id),
                str(offers[0].id),
                str(offers[0].id),
                str(offers[0].id),
                {"single_offer": True}
            )
        
        # Find best in each category
        best_price = self._find_best_price(offers)
        best_area = self._find_best_area(offers)
        best_price_per_m2 = self._find_best_price_per_m2(offers)
        best_location = self._find_best_location(offers)
        
        # Calculate overall score
        overall_best = self._calculate_overall_best(
            offers, best_price, best_area, best_price_per_m2
        )
        
        # Build details
        details = {
            "offers_count": len(offers),
            "price_range": self._get_price_range(offers),
            "area_range": self._get_area_range(offers),
            "avg_price_per_m2": self._get_avg_price_per_m2(offers),
            "comparison_table": self._build_comparison_table(offers),
        }
        
        return ComparisonResult(
            best_price=str(best_price.id) if best_price else None,
            best_area=str(best_area.id) if best_area else None,
            best_price_per_m2=str(best_price_per_m2.id) if best_price_per_m2 else None,
            best_location=str(best_location.id) if best_location else None,
            overall_best=str(overall_best.id) if overall_best else None,
            details=details
        )
    
    def _find_best_price(self, offers: List[Offer]) -> Optional[Offer]:
        """Find offer with lowest price."""
        valid_offers = [o for o in offers if o.price]
        if not valid_offers:
            return None
        return min(valid_offers, key=lambda o: o.price)
    
    def _find_best_area(self, offers: List[Offer]) -> Optional[Offer]:
        """Find offer with largest area."""
        valid_offers = [o for o in offers if o.area_m2]
        if not valid_offers:
            return None
        return max(valid_offers, key=lambda o: o.area_m2)
    
    def _find_best_price_per_m2(self, offers: List[Offer]) -> Optional[Offer]:
        """Find offer with best price per m²."""
        valid_offers = [o for o in offers if o.price and o.area_m2 and o.area_m2 > 0]
        if not valid_offers:
            return None
        return min(valid_offers, key=lambda o: o.price / Decimal(o.area_m2))
    
    def _find_best_location(self, offers: List[Offer]) -> Optional[Offer]:
        """Find offer in best location (heuristic)."""
        # Prefer city center or popular districts
        # This is a simplified version
        city_scores = {
            "gdansk": 10,
            "sopot": 9,
            "gdynia": 8,
        }
        
        best_offer = None
        best_score = -1
        
        for offer in offers:
            if offer.city:
                city = offer.city.lower()
                score = city_scores.get(city, 5)
                if score > best_score:
                    best_score = score
                    best_offer = offer
        
        return best_offer
    
    def _calculate_overall_best(
        self,
        offers: List[Offer],
        best_price: Optional[Offer],
        best_area: Optional[Offer],
        best_price_per_m2: Optional[Offer]
    ) -> Optional[Offer]:
        """Calculate overall best offer using scoring."""
        if not offers:
            return None
        
        scores = {str(o.id): 0 for o in offers}
        
        # Award points for each category
        if best_price:
            scores[str(best_price.id)] += 3
        if best_area:
            scores[str(best_area.id)] += 2
        if best_price_per_m2:
            scores[str(best_price_per_m2.id)] += 4
        
        # Additional scoring
        for offer in offers:
            # Bonus for more rooms
            if offer.rooms and offer.rooms >= 3:
                scores[str(offer.id)] += 1
            
            # Penalty for very high price
            if offer.price and offer.price > 1000000:
                scores[str(offer.id)] -= 1
        
        # Find highest score
        best_id = max(scores, key=scores.get)
        return next(o for o in offers if str(o.id) == best_id)
    
    def _get_price_range(self, offers: List[Offer]) -> Dict[str, Any]:
        """Get price range statistics."""
        prices = [float(o.price) for o in offers if o.price]
        
        if not prices:
            return {"min": None, "max": None, "avg": None}
        
        return {
            "min": min(prices),
            "max": max(prices),
            "avg": sum(prices) / len(prices),
        }
    
    def _get_area_range(self, offers: List[Offer]) -> Dict[str, Any]:
        """Get area range statistics."""
        areas = [o.area_m2 for o in offers if o.area_m2]
        
        if not areas:
            return {"min": None, "max": None, "avg": None}
        
        return {
            "min": min(areas),
            "max": max(areas),
            "avg": sum(areas) / len(areas),
        }
    
    def _get_avg_price_per_m2(self, offers: List[Offer]) -> Optional[float]:
        """Get average price per m²."""
        values = []
        for o in offers:
            if o.price and o.area_m2 and o.area_m2 > 0:
                values.append(float(o.price) / o.area_m2)
        
        if values:
            return sum(values) / len(values)
        return None
    
    def _build_comparison_table(self, offers: List[Offer]) -> List[Dict]:
        """Build comparison table data."""
        table = []
        
        for offer in offers:
            price_per_m2 = None
            if offer.price and offer.area_m2 and offer.area_m2 > 0:
                price_per_m2 = round(float(offer.price) / offer.area_m2, 2)
            
            table.append({
                "id": str(offer.id),
                "title": offer.title[:50] if offer.title else "",
                "price": float(offer.price) if offer.price else None,
                "area_m2": offer.area_m2,
                "rooms": offer.rooms,
                "city": offer.city,
                "price_per_m2": price_per_m2,
                "url": offer.url,
            })
        
        return table
    
    def generate_comparison_report(self, offers: List[Offer]) -> str:
        """Generate text comparison report."""
        result = self.compare_offers(offers)
        
        report = []
        report.append("=" * 60)
        report.append("OFFER COMPARISON REPORT")
        report.append("=" * 60)
        report.append("")
        
        # Summary
        report.append("SUMMARY")
        report.append("-" * 40)
        report.append(f"Total offers compared: {result.details['offers_count']}")
        
        price_range = result.details['price_range']
        if price_range['min']:
            report.append(f"Price range: {price_range['min']:,.0f} - {price_range['max']:,.0f} PLN")
            report.append(f"Average price: {price_range['avg']:,.0f} PLN")
        
        area_range = result.details['area_range']
        if area_range['min']:
            report.append(f"Area range: {area_range['min']:.0f} - {area_range['max']:.0f} m²")
        
        avg_price_m2 = result.details['avg_price_per_m2']
        if avg_price_m2:
            report.append(f"Average price/m²: {avg_price_m2:,.0f} PLN")
        
        report.append("")
        
        # Winners
        report.append("BEST OFFERS BY CATEGORY")
        report.append("-" * 40)
        
        if result.best_price:
            offer = next(o for o in offers if str(o.id) == result.best_price)
            report.append(f"Best price: {offer.title[:40]} ({offer.price:,.0f} PLN)")
        
        if result.best_area:
            offer = next(o for o in offers if str(o.id) == result.best_area)
            report.append(f"Best area: {offer.title[:40]} ({offer.area_m2:.0f} m²)")
        
        if result.best_price_per_m2:
            offer = next(o for o in offers if str(o.id) == result.best_price_per_m2)
            price_m2 = float(offer.price) / offer.area_m2
            report.append(f"Best price/m²: {offer.title[:40]} ({price_m2:,.0f} PLN/m²)")
        
        report.append("")
        report.append("=" * 60)
        
        return "\n".join(report)


# Global instance
_comparator: Optional[OfferComparator] = None


def get_offer_comparator() -> OfferComparator:
    """Get or create offer comparator."""
    global _comparator
    
    if _comparator is None:
        _comparator = OfferComparator()
    
    return _comparator
