"""
Full-text search service using PostgreSQL tsvector.
"""
from typing import List, Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger
from app.models import Offer

logger = get_logger("search")


class FullTextSearch:
    """
    Full-text search for offers using PostgreSQL.
    
    Features:
    - Search in titles and descriptions
    - Ranking by relevance
    - Filtering by search query
    """
    
    def __init__(self):
        self.language = "polish"  # Can be changed to 'simple' or 'english'
    
    async def search(
        self,
        session: AsyncSession,
        query: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Offer]:
        """
        Search offers by query string.
        
        Args:
            session: Database session
            query: Search query
            limit: Max results
            offset: Pagination offset
        
        Returns:
            List of matching offers
        """
        if not query or len(query.strip()) < 2:
            return []
        
        # Build tsquery
        tsquery = self._build_tsquery(query)
        
        sql = text("""
            SELECT o.*
            FROM offers o
            WHERE 
                (o.search_vector @@ to_tsquery(:language, :tsquery)
                OR o.title ILIKE :like_query
                OR o.city ILIKE :like_query)
                AND o.status = 'active'
            ORDER BY 
                ts_rank(o.search_vector, to_tsquery(:language, :tsquery)) DESC,
                o.last_seen DESC
            LIMIT :limit OFFSET :offset
        """)
        
        result = await session.execute(
            sql,
            {
                "language": self.language,
                "tsquery": tsquery,
                "like_query": f"%{query}%",
                "limit": limit,
                "offset": offset,
            }
        )
        
        return result.scalars().all()
    
    async def search_with_filters(
        self,
        session: AsyncSession,
        query: str,
        city: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        min_area: Optional[float] = None,
        max_area: Optional[float] = None,
        limit: int = 50
    ) -> List[Offer]:
        """Search with additional filters."""
        if not query or len(query.strip()) < 2:
            return []
        
        tsquery = self._build_tsquery(query)
        
        # Build dynamic SQL
        conditions = ["o.status = 'active'"]
        params = {
            "language": self.language,
            "tsquery": tsquery,
            "like_query": f"%{query}%",
            "limit": limit,
        }
        
        if city:
            conditions.append("o.city ILIKE :city")
            params["city"] = f"%{city}%"
        
        if min_price is not None:
            conditions.append("o.price >= :min_price")
            params["min_price"] = min_price
        
        if max_price is not None:
            conditions.append("o.price <= :max_price")
            params["max_price"] = max_price
        
        if min_area is not None:
            conditions.append("o.area_m2 >= :min_area")
            params["min_area"] = min_area
        
        if max_area is not None:
            conditions.append("o.area_m2 <= :max_area")
            params["max_area"] = max_area
        
        where_clause = " AND ".join(conditions)
        
        sql = text(f"""
            SELECT o.*
            FROM offers o
            WHERE 
                (o.search_vector @@ to_tsquery(:language, :tsquery)
                OR o.title ILIKE :like_query)
                AND {where_clause}
            ORDER BY 
                ts_rank(o.search_vector, to_tsquery(:language, :tsquery)) DESC,
                o.last_seen DESC
            LIMIT :limit
        """)
        
        result = await session.execute(sql, params)
        return result.scalars().all()
    
    def _build_tsquery(self, query: str) -> str:
        """
        Build PostgreSQL tsquery from user query.
        
        Converts "mieszkanie gdansk" to "mieszkanie & gdansk"
        """
        # Remove special characters
        cleaned = "".join(c for c in query if c.isalnum() or c.isspace())
        
        # Split and join with AND operator
        words = [w for w in cleaned.split() if len(w) >= 2]
        
        if not words:
            return ""
        
        return " & ".join(words)
    
    async def update_search_vector(self, session: AsyncSession, offer_id: str):
        """Update search vector for a single offer."""
        sql = text("""
            UPDATE offers
            SET search_vector = 
                setweight(to_tsvector(:language, COALESCE(title, '')), 'A') ||
                setweight(to_tsvector(:language, COALESCE(city, '')), 'B') ||
                setweight(to_tsvector(:language, COALESCE(region, '')), 'C')
            WHERE id = :offer_id
        """)
        
        await session.execute(
            sql,
            {"language": self.language, "offer_id": offer_id}
        )
    
    async def reindex_all(self, session: AsyncSession):
        """Reindex all offers (run after bulk import)."""
        sql = text("""
            UPDATE offers
            SET search_vector = 
                setweight(to_tsvector(:language, COALESCE(title, '')), 'A') ||
                setweight(to_tsvector(:language, COALESCE(city, '')), 'B') ||
                setweight(to_tsvector(:language, COALESCE(region, '')), 'C')
            WHERE search_vector IS NULL
        """)
        
        result = await session.execute(sql, {"language": self.language})
        logger.info(f"Reindexed {result.rowcount} offers")


class OfferIndexer:
    """Index offers for search."""
    
    @staticmethod
    def generate_search_vector(offer: Offer) -> str:
        """Generate search vector text for an offer."""
        parts = []
        
        if offer.title:
            parts.append(offer.title)
        if offer.city:
            parts.append(offer.city)
        if offer.region:
            parts.append(offer.region)
        
        return " ".join(parts)


# Global instance
_search_service: Optional[FullTextSearch] = None


def get_search_service() -> FullTextSearch:
    """Get or create search service."""
    global _search_service
    
    if _search_service is None:
        _search_service = FullTextSearch()
    
    return _search_service
