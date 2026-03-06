"""
Reviews & Ratings Service - System Ocen i Recenzji

Zarządzanie opiniami o agentach i ofertach.
System ocen, recenzje klientów, moderacja.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import uuid
import statistics

from sqlalchemy import func, and_, desc
from sqlalchemy.orm import Session

from app.core.logging import get_logger

logger = get_logger(__name__)


class ReviewType(str, Enum):
    """Typ recenzji"""
    AGENT = "agent"              # Ocena agenta
    LISTING = "listing"          # Ocena oferty
    OFFICE = "office"            # Ocena biura
    VIEWING = "viewing"          # Ocena prezentacji


class ReviewStatus(str, Enum):
    """Status recenzji"""
    PENDING = "pending"          # Oczekuje na moderację
    APPROVED = "approved"        # Zatwierdzona
    REJECTED = "rejected"        # Odrzucona
    FLAGGED = "flagged"          # Zgłoszona do weryfikacji


@dataclass
class Review:
    """Recenzja/ocena"""
    id: str
    review_type: ReviewType
    
    # Oceniany obiekt
    target_id: str               # ID agenta/oferty/biura
    target_name: str             # Nazwa wyświetlana
    
    # Autor
    author_id: str               # ID autora (klienta)
    author_name: str             # Imię/nick autora
    author_email: Optional[str]
    is_verified: bool            # Zweryfikowany klient (kupił/sprzedał)
    
    # Treść
    rating: int                  # 1-5 gwiazdek
    title: Optional[str]
    content: str
    
    # Dodatkowe oceny
    sub_ratings: Dict[str, int]  # np. {"komunikacja": 5, "wiedza": 4}
    
    # Status
    status: ReviewStatus
    
    # Daty
    created_at: datetime
    updated_at: datetime
    moderated_at: Optional[datetime]
    moderated_by: Optional[str]
    
    # Reakcje
    helpful_count: int
    unhelpful_count: int
    
    # Odpowiedź
    response: Optional[str]
    responded_at: Optional[datetime]
    responded_by: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'review_type': self.review_type.value,
            'target': {
                'id': self.target_id,
                'name': self.target_name,
            },
            'author': {
                'name': self.author_name,
                'verified': self.is_verified,
            },
            'rating': self.rating,
            'title': self.title,
            'content': self.content,
            'sub_ratings': self.sub_ratings,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'helpful_count': self.helpful_count,
            'response': self.response,
            'responded_at': self.responded_at.isoformat() if self.responded_at else None,
        }


@dataclass
class RatingSummary:
    """Podsumowanie ocen"""
    target_id: str
    target_type: ReviewType
    
    # Statystyki
    average_rating: float
    total_reviews: int
    rating_distribution: Dict[int, int]  # {5: 10, 4: 5, ...}
    
    # Szczegółowe oceny
    sub_rating_averages: Dict[str, float]
    
    # Trend
    recent_trend: str  # "improving", "stable", "declining"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'target_id': self.target_id,
            'target_type': self.target_type.value,
            'average_rating': round(self.average_rating, 2),
            'total_reviews': self.total_reviews,
            'rating_distribution': self.rating_distribution,
            'sub_rating_averages': {k: round(v, 2) for k, v in self.sub_rating_averages.items()},
            'recent_trend': self.recent_trend,
        }


class ReviewsRatingsService:
    """
    Serwis ocen i recenzji.
    
    Zarządza opiniami klientów o agentach, ofertach i biurze.
    """
    
    # Szablony sub-ocen dla różnych typów
    SUB_RATINGS = {
        ReviewType.AGENT: {
            'communication': 'Komunikacja',
            'knowledge': 'Wiedza o rynku',
            'professionalism': 'Profesjonalizm',
            'availability': 'Dostępność',
            'effectiveness': 'Skuteczność',
        },
        ReviewType.LISTING: {
            'description_accuracy': 'Zgodność z opisem',
            'photos_accuracy': 'Zgodność ze zdjęciami',
            'location': 'Lokalizacja',
            'value_for_money': 'Stosunek jakości do ceny',
        },
        ReviewType.OFFICE: {
            'service_quality': 'Jakość obsługi',
            'offer_selection': 'Wybór ofert',
            'transparency': 'Transparentność',
            'after_sales': 'Obsługa posprzedażowa',
        },
        ReviewType.VIEWING: {
            'punctuality': 'Punktualność',
            'preparation': 'Przygotowanie',
            'information': 'Udzielone informacje',
        },
    }
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    async def create_review(
        self,
        review_type: ReviewType,
        target_id: str,
        target_name: str,
        author_id: str,
        author_name: str,
        rating: int,
        content: str,
        title: Optional[str] = None,
        sub_ratings: Optional[Dict[str, int]] = None,
        author_email: Optional[str] = None,
        is_verified: bool = False,
    ) -> Review:
        """
        Utwórz nową recenzję.
        
        Args:
            review_type: Typ recenzji (agent/listing/office/viewing)
            target_id: ID ocenianego obiektu
            target_name: Nazwa wyświetlana
            author_id: ID autora
            author_name: Imię autora
            rating: Ocena 1-5
            content: Treść recenzji
            title: Tytuł recenzji
            sub_ratings: Szczegółowe oceny
            author_email: Email autora
            is_verified: Czy klient był zweryfikowany
        """
        if not 1 <= rating <= 5:
            raise ValueError("Rating must be between 1 and 5")
        
        review = Review(
            id=str(uuid.uuid4()),
            review_type=review_type,
            target_id=target_id,
            target_name=target_name,
            author_id=author_id,
            author_name=author_name,
            author_email=author_email,
            is_verified=is_verified,
            rating=rating,
            title=title,
            content=content,
            sub_ratings=sub_ratings or {},
            status=ReviewStatus.PENDING,  # Wymaga moderacji
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            moderated_at=None,
            moderated_by=None,
            helpful_count=0,
            unhelpful_count=0,
            response=None,
            responded_at=None,
            responded_by=None,
        )
        
        # Zapisz do bazy
        self._save_review(review)
        
        logger.info(f"Review created: {review.id} for {review_type.value}:{target_id}")
        
        return review
    
    async def moderate_review(
        self,
        review_id: str,
        status: ReviewStatus,
        moderator_id: str,
        reason: Optional[str] = None,
    ) -> Optional[Review]:
        """Zmoderuj recenzję (zatwierdź/odrzuć)"""
        review = self._get_review(review_id)
        if not review:
            return None
        
        review.status = status
        review.moderated_at = datetime.utcnow()
        review.moderated_by = moderator_id
        
        if reason and status == ReviewStatus.REJECTED:
            review.content = f"[ODRZUCONE: {reason}]"
        
        self._update_review(review)
        
        logger.info(f"Review {review_id} moderated: {status.value}")
        
        return review
    
    async def respond_to_review(
        self,
        review_id: str,
        response: str,
        responder_id: str,
    ) -> Optional[Review]:
        """Odpowiedz na recenzję"""
        review = self._get_review(review_id)
        if not review:
            return None
        
        review.response = response
        review.responded_at = datetime.utcnow()
        review.responded_by = responder_id
        
        self._update_review(review)
        
        logger.info(f"Response added to review {review_id}")
        
        return review
    
    async def mark_helpful(
        self,
        review_id: str,
        helpful: bool = True,
    ) -> bool:
        """Oznacz recenzję jako pomocna/niepomocna"""
        review = self._get_review(review_id)
        if not review:
            return False
        
        if helpful:
            review.helpful_count += 1
        else:
            review.unhelpful_count += 1
        
        self._update_review(review)
        
        return True
    
    async def get_reviews(
        self,
        review_type: Optional[ReviewType] = None,
        target_id: Optional[str] = None,
        status: ReviewStatus = ReviewStatus.APPROVED,
        min_rating: Optional[int] = None,
        max_rating: Optional[int] = None,
        verified_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Review]:
        """Pobierz recenzje z filtrami"""
        reviews = self._query_reviews(
            review_type=review_type,
            target_id=target_id,
            status=status,
            min_rating=min_rating,
            max_rating=max_rating,
            verified_only=verified_only,
            limit=limit,
            offset=offset,
        )
        
        # Sortuj: najnowsze pierwsze
        reviews.sort(key=lambda r: r.created_at, reverse=True)
        
        return reviews
    
    async def get_rating_summary(
        self,
        target_id: str,
        review_type: ReviewType,
    ) -> Optional[RatingSummary]:
        """Pobierz podsumowanie ocen dla obiektu"""
        reviews = self._query_reviews(
            target_id=target_id,
            review_type=review_type,
            status=ReviewStatus.APPROVED,
        )
        
        if not reviews:
            return None
        
        ratings = [r.rating for r in reviews]
        
        # Dystrybucja ocen
        distribution = {i: 0 for i in range(1, 6)}
        for r in ratings:
            distribution[r] += 1
        
        # Średnie sub-ocen
        sub_rating_sums = {}
        sub_rating_counts = {}
        
        for review in reviews:
            for key, value in review.sub_ratings.items():
                if key not in sub_rating_sums:
                    sub_rating_sums[key] = 0
                    sub_rating_counts[key] = 0
                sub_rating_sums[key] += value
                sub_rating_counts[key] += 1
        
        sub_rating_averages = {
            key: sub_rating_sums[key] / sub_rating_counts[key]
            for key in sub_rating_sums
        }
        
        # Trend (ostatnie 3 miesiące vs wcześniej)
        three_months_ago = datetime.utcnow() - timedelta(days=90)
        recent = [r.rating for r in reviews if r.created_at >= three_months_ago]
        older = [r.rating for r in reviews if r.created_at < three_months_ago]
        
        if recent and older:
            recent_avg = statistics.mean(recent)
            older_avg = statistics.mean(older)
            
            if recent_avg > older_avg + 0.2:
                trend = "improving"
            elif recent_avg < older_avg - 0.2:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"
        
        return RatingSummary(
            target_id=target_id,
            target_type=review_type,
            average_rating=statistics.mean(ratings),
            total_reviews=len(reviews),
            rating_distribution=distribution,
            sub_rating_averages=sub_rating_averages,
            recent_trend=trend,
        )
    
    async def get_agent_leaderboard(
        self,
        office_id: Optional[str] = None,
        period_days: int = 30,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Ranking agentów według ocen"""
        # Pobierz wszystkich agentów
        agents = self._get_agents(office_id)
        
        leaderboard = []
        
        for agent in agents:
            summary = await self.get_rating_summary(agent['id'], ReviewType.AGENT)
            
            if summary and summary.total_reviews >= 3:  # Min 3 recenzje
                leaderboard.append({
                    'agent_id': agent['id'],
                    'agent_name': agent['name'],
                    'average_rating': summary.average_rating,
                    'total_reviews': summary.total_reviews,
                    'recent_trend': summary.recent_trend,
                })
        
        # Sortuj po ocenie
        leaderboard.sort(key=lambda x: x['average_rating'], reverse=True)
        
        return leaderboard[:limit]
    
    async def flag_review(
        self,
        review_id: str,
        reason: str,
        flagged_by: str,
    ) -> Optional[Review]:
        """Zgłoś recenzję do weryfikacji"""
        review = self._get_review(review_id)
        if not review:
            return None
        
        review.status = ReviewStatus.FLAGGED
        review.updated_at = datetime.utcnow()
        
        self._update_review(review)
        
        logger.info(f"Review {review_id} flagged by {flagged_by}: {reason}")
        
        return review
    
    async def get_pending_reviews(
        self,
        limit: int = 50,
    ) -> List[Review]:
        """Pobierz recenzje oczekujące na moderację"""
        return self._query_reviews(
            status=ReviewStatus.PENDING,
            limit=limit,
        )
    
    async def get_review_stats(self) -> Dict[str, Any]:
        """Statystyki recenzji"""
        all_reviews = self._query_reviews()
        
        pending = len([r for r in all_reviews if r.status == ReviewStatus.PENDING])
        approved = len([r for r in all_reviews if r.status == ReviewStatus.APPROVED])
        rejected = len([r for r in all_reviews if r.status == ReviewStatus.REJECTED])
        flagged = len([r for r in all_reviews if r.status == ReviewStatus.FLAGGED])
        
        avg_rating = statistics.mean([r.rating for r in all_reviews if r.status == ReviewStatus.APPROVED]) if approved > 0 else 0
        
        return {
            'total': len(all_reviews),
            'pending': pending,
            'approved': approved,
            'rejected': rejected,
            'flagged': flagged,
            'average_rating': round(avg_rating, 2),
        }
    
    def get_sub_rating_definitions(self, review_type: ReviewType) -> Dict[str, str]:
        """Pobierz definicje sub-ocen dla danego typu"""
        return self.SUB_RATINGS.get(review_type, {})
    
    # ==========================================================================
    # Metody pomocnicze (symulacja bazy)
    # ==========================================================================
    
    def _save_review(self, review: Review):
        """Zapisz recenzję do bazy"""
        pass
    
    def _get_review(self, review_id: str) -> Optional[Review]:
        """Pobierz recenzję z bazy"""
        return None
    
    def _update_review(self, review: Review):
        """Zaktualizuj recenzję"""
        pass
    
    def _query_reviews(
        self,
        review_type: Optional[ReviewType] = None,
        target_id: Optional[str] = None,
        status: Optional[ReviewStatus] = None,
        min_rating: Optional[int] = None,
        max_rating: Optional[int] = None,
        verified_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Review]:
        """Zapytanie do bazy recenzji"""
        return []
    
    def _get_agents(self, office_id: Optional[str] = None) -> List[Dict[str, str]]:
        """Pobierz listę agentów"""
        return []


# Singleton
def get_reviews_service(db_session: Session) -> ReviewsRatingsService:
    return ReviewsRatingsService(db_session)
