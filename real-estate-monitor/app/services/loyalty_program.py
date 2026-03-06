"""
Loyalty Program Service - System Lojalnościowy

Nagradzanie klientów powracających za aktywność i polecenia.
Punkty, nagrody, poziomy lojalnościowe.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import uuid

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.core.logging import get_logger

logger = get_logger(__name__)


class LoyaltyTier(str, Enum):
    """Poziom lojalnościowy"""
    BRONZE = "bronze"              # 0-999 pkt
    SILVER = "silver"              # 1000-4999 pkt
    GOLD = "gold"                  # 5000-9999 pkt
    PLATINUM = "platinum"          # 10000+ pkt


class PointsAction(str, Enum):
    """Akcje punktowe"""
    REGISTRATION = "registration"           # Rejestracja
    PROFILE_COMPLETE = "profile_complete"   # Uzupełnienie profilu
    LISTING_VIEW = "listing_view"           # Oglądanie oferty
    FAVORITE_ADD = "favorite_add"           # Dodanie do ulubionych
    VIEWING_ATTEND = "viewing_attend"       # Udział w prezentacji
    REFERRAL = "referral"                   # Polecenie znajomego
    REFERRAL_SUCCESS = "referral_success"   # Skuteczne polecenie
    REVIEW_SUBMIT = "review_submit"         # Dodanie opinii
    SOCIAL_SHARE = "social_share"           # Udostępnienie w social
    NEWSLETTER_SUB = "newsletter_sub"       # Subskrypcja newslettera
    APP_DOWNLOAD = "app_download"           # Pobranie aplikacji
    TRANSACTION = "transaction"             # Transakcja


class RewardType(str, Enum):
    """Typ nagrody"""
    DISCOUNT_PERCENT = "discount_percent"   # Zniżka procentowa
    DISCOUNT_AMOUNT = "discount_amount"     # Zniżka kwotowa
    FREE_SERVICE = "free_service"           # Darmowa usługa
    CASHBACK = "cashback"                   # Zwrot gotówki
    GIFT = "gift"                           # Prezent
    PRIORITY = "priority"                   # Priorytetowa obsługa


@dataclass
class LoyaltyMember:
    """Członek programu lojalnościowego"""
    id: str
    user_id: str
    
    # Punkty
    total_points: int = 0
    available_points: int = 0
    lifetime_points: int = 0
    
    # Poziom
    tier: LoyaltyTier = LoyaltyTier.BRONZE
    tier_since: datetime = field(default_factory=datetime.utcnow)
    
    # Historia
    transactions: List['PointsTransaction'] = field(default_factory=list)
    rewards: List['RewardRedemption'] = field(default_factory=list)
    
    # Polecenia
    referral_code: str = ""
    referrals_count: int = 0
    successful_referrals: int = 0
    
    # Daty
    joined_at: datetime = field(default_factory=datetime.utcnow)
    last_activity_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'user_id': self.user_id,
            'points': {
                'total': self.total_points,
                'available': self.available_points,
                'lifetime': self.lifetime_points,
            },
            'tier': {
                'current': self.tier.value,
                'since': self.tier_since.isoformat(),
                'next_tier_progress': self._get_next_tier_progress(),
            },
            'referrals': {
                'code': self.referral_code,
                'total': self.referrals_count,
                'successful': self.successful_referrals,
            },
            'joined_at': self.joined_at.isoformat(),
        }
    
    def _get_next_tier_progress(self) -> Dict[str, Any]:
        """Postęp do następnego poziomu"""
        tier_thresholds = {
            LoyaltyTier.BRONZE: 0,
            LoyaltyTier.SILVER: 1000,
            LoyaltyTier.GOLD: 5000,
            LoyaltyTier.PLATINUM: 10000,
        }
        
        current_threshold = tier_thresholds[self.tier]
        
        if self.tier == LoyaltyTier.PLATINUM:
            return {
                'next_tier': None,
                'points_needed': 0,
                'progress_percent': 100,
            }
        
        next_tier = {
            LoyaltyTier.BRONZE: LoyaltyTier.SILVER,
            LoyaltyTier.SILVER: LoyaltyTier.GOLD,
            LoyaltyTier.GOLD: LoyaltyTier.PLATINUM,
        }[self.tier]
        
        next_threshold = tier_thresholds[next_tier]
        points_needed = next_threshold - self.lifetime_points
        progress = (self.lifetime_points - current_threshold) / (next_threshold - current_threshold) * 100
        
        return {
            'next_tier': next_tier.value,
            'points_needed': max(0, points_needed),
            'progress_percent': min(100, max(0, progress)),
        }


@dataclass
class PointsTransaction:
    """Transakcja punktowa"""
    id: str
    member_id: str
    action: PointsAction
    points: int  # Dodatnie lub ujemne
    description: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'action': self.action.value,
            'points': self.points,
            'description': self.description,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
        }


@dataclass
class Reward:
    """Dostępna nagroda"""
    id: str
    name: str
    description: str
    type: RewardType
    value: float
    points_cost: int
    
    # Ograniczenia
    stock: Optional[int] = None
    valid_from: datetime = field(default_factory=datetime.utcnow)
    valid_until: Optional[datetime] = None
    
    # Wymagania
    min_tier: LoyaltyTier = LoyaltyTier.BRONZE
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'type': self.type.value,
            'value': self.value,
            'points_cost': self.points_cost,
            'min_tier': self.min_tier.value,
            'available': self.stock is None or self.stock > 0,
        }


@dataclass
class RewardRedemption:
    """Wykorzystanie nagrody"""
    id: str
    member_id: str
    reward_id: str
    reward_name: str
    points_spent: int
    status: str  # pending, fulfilled, cancelled
    code: str    # Kod do wykorzystania
    redeemed_at: datetime = field(default_factory=datetime.utcnow)
    fulfilled_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'reward': {
                'id': self.reward_id,
                'name': self.reward_name,
            },
            'points_spent': self.points_spent,
            'status': self.status,
            'code': self.code,
            'redeemed_at': self.redeemed_at.isoformat(),
            'fulfilled_at': self.fulfilled_at.isoformat() if self.fulfilled_at else None,
        }


# Konfiguracja punktów
POINTS_CONFIG = {
    PointsAction.REGISTRATION: {'points': 100, 'description': 'Rejestracja w programie'},
    PointsAction.PROFILE_COMPLETE: {'points': 50, 'description': 'Uzupełnienie profilu'},
    PointsAction.LISTING_VIEW: {'points': 5, 'description': 'Oglądanie oferty', 'limit_per_day': 20},
    PointsAction.FAVORITE_ADD: {'points': 10, 'description': 'Dodanie do ulubionych'},
    PointsAction.VIEWING_ATTEND: {'points': 200, 'description': 'Udział w prezentacji'},
    PointsAction.REFERRAL: {'points': 100, 'description': 'Polecenie znajomego'},
    PointsAction.REFERRAL_SUCCESS: {'points': 1000, 'description': 'Skuteczne polecenie (transakcja)'},
    PointsAction.REVIEW_SUBMIT: {'points': 50, 'description': 'Dodanie opinii'},
    PointsAction.SOCIAL_SHARE: {'points': 25, 'description': 'Udostępnienie w social media'},
    PointsAction.NEWSLETTER_SUB: {'points': 30, 'description': 'Subskrypcja newslettera'},
    PointsAction.APP_DOWNLOAD: {'points': 150, 'description': 'Pobranie aplikacji mobilnej'},
    PointsAction.TRANSACTION: {'points': 0, 'description': 'Transakcja - punkty zależne od wartości'},
}

# Dostępne nagrody
DEFAULT_REWARDS = [
    Reward(
        id='discount_5_percent',
        name='Zniżka 5% na prowizję',
        description='5% zniżki na prowizję biura przy kolejnej transakcji',
        type=RewardType.DISCOUNT_PERCENT,
        value=5.0,
        points_cost=500,
        min_tier=LoyaltyTier.BRONZE,
    ),
    Reward(
        id='discount_10_percent',
        name='Zniżka 10% na prowizję',
        description='10% zniżki na prowizję biura',
        type=RewardType.DISCOUNT_PERCENT,
        value=10.0,
        points_cost=1000,
        min_tier=LoyaltyTier.SILVER,
    ),
    Reward(
        id='free_valuation',
        name='Darmowa wycena nieruchomości',
        description='Profesjonalna wycena Twojej nieruchomości',
        type=RewardType.FREE_SERVICE,
        value=300.0,
        points_cost=800,
        min_tier=LoyaltyTier.BRONZE,
    ),
    Reward(
        id='priority_viewing',
        name='Priorytetowa prezentacja',
        description='Pierwszeństwo w umawianiu prezentacji',
        type=RewardType.PRIORITY,
        value=0.0,
        points_cost=300,
        min_tier=LoyaltyTier.BRONZE,
    ),
    Reward(
        id='cashback_100',
        name='100 zł zwrotu',
        description='100 zł zwrotu po zakończonej transakcji',
        type=RewardType.CASHBACK,
        value=100.0,
        points_cost=1000,
        min_tier=LoyaltyTier.SILVER,
    ),
    Reward(
        id='cashback_500',
        name='500 zł zwrotu',
        description='500 zł zwrotu po zakończonej transakcji',
        type=RewardType.CASHBACK,
        value=500.0,
        points_cost=4000,
        min_tier=LoyaltyTier.GOLD,
    ),
    Reward(
        id='vip_service',
        name='VIP Service',
        description='Dedykowany agent i priorytetowa obsługa przez 6 miesięcy',
        type=RewardType.PRIORITY,
        value=0.0,
        points_cost=5000,
        min_tier=LoyaltyTier.PLATINUM,
    ),
]


class LoyaltyProgramService:
    """
    Serwis programu lojalnościowego.
    
    Zarządza punktami, nagrodami i poziomami lojalnościowymi klientów.
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.members: Dict[str, LoyaltyMember] = {}
        self.rewards: Dict[str, Reward] = {r.id: r for r in DEFAULT_REWARDS}
    
    async def enroll_member(self, user_id: str) -> LoyaltyMember:
        """Zapisz użytkownika do programu lojalnościowego"""
        # Generuj kod polecający
        referral_code = self._generate_referral_code(user_id)
        
        member = LoyaltyMember(
            id=str(uuid.uuid4()),
            user_id=user_id,
            referral_code=referral_code,
        )
        
        self.members[member.id] = member
        
        # Przyznaj punkty za rejestrację
        await self.award_points(member.id, PointsAction.REGISTRATION)
        
        logger.info(f"Member enrolled: {user_id}")
        
        return member
    
    async def get_member(self, user_id: str) -> Optional[LoyaltyMember]:
        """Pobierz dane członka"""
        for member in self.members.values():
            if member.user_id == user_id:
                return member
        return None
    
    async def award_points(
        self,
        member_id: str,
        action: PointsAction,
        custom_points: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[PointsTransaction]:
        """
        Przyznaj punkty za akcję.
        
        Args:
            member_id: ID członka
            action: Typ akcji
            custom_points: Niestandardowa liczba punktów
            metadata: Dodatkowe dane
        """
        member = self.members.get(member_id)
        if not member:
            return None
        
        config = POINTS_CONFIG.get(action)
        if not config and custom_points is None:
            return None
        
        points = custom_points if custom_points is not None else config['points']
        description = config['description'] if config else 'Custom'
        
        # Specjalna obsługa transakcji
        if action == PointsAction.TRANSACTION and metadata:
            transaction_value = metadata.get('value', 0)
            points = int(transaction_value * 0.001)  # 1 pkt za 1000 zł
        
        transaction = PointsTransaction(
            id=str(uuid.uuid4()),
            member_id=member_id,
            action=action,
            points=points,
            description=description,
            metadata=metadata or {},
        )
        
        member.transactions.append(transaction)
        member.total_points += points
        member.available_points += points
        member.lifetime_points += points
        member.last_activity_at = datetime.utcnow()
        
        # Sprawdź awans poziomu
        await self._check_tier_upgrade(member)
        
        logger.info(f"Awarded {points} points to member {member_id} for {action.value}")
        
        return transaction
    
    async def deduct_points(
        self,
        member_id: str,
        points: int,
        reason: str,
    ) -> bool:
        """Odejmij punkty (np. przy wymianie na nagrodę)"""
        member = self.members.get(member_id)
        if not member:
            return False
        
        if member.available_points < points:
            return False
        
        transaction = PointsTransaction(
            id=str(uuid.uuid4()),
            member_id=member_id,
            action=PointsAction.REGISTRATION,  # Placeholder
            points=-points,
            description=reason,
        )
        
        member.transactions.append(transaction)
        member.available_points -= points
        
        return True
    
    async def redeem_reward(
        self,
        member_id: str,
        reward_id: str,
    ) -> Optional[RewardRedemption]:
        """Wymień punkty na nagrodę"""
        member = self.members.get(member_id)
        if not member:
            return None
        
        reward = self.rewards.get(reward_id)
        if not reward:
            return None
        
        # Sprawdź wymagania
        if member.available_points < reward.points_cost:
            return None
        
        if member.tier.value < reward.min_tier.value:
            return None
        
        if reward.stock is not None and reward.stock <= 0:
            return None
        
        # Odejmij punkty
        success = await self.deduct_points(
            member_id,
            reward.points_cost,
            f'Wymiana na nagrodę: {reward.name}',
        )
        
        if not success:
            return None
        
        # Generuj kod
        code = self._generate_reward_code()
        
        redemption = RewardRedemption(
            id=str(uuid.uuid4()),
            member_id=member_id,
            reward_id=reward_id,
            reward_name=reward.name,
            points_spent=reward.points_cost,
            status='pending',
            code=code,
        )
        
        member.rewards.append(redemption)
        
        # Zmniejsz stock
        if reward.stock is not None:
            reward.stock -= 1
        
        logger.info(f"Reward redeemed: {reward.name} by member {member_id}")
        
        return redemption
    
    async def get_available_rewards(
        self,
        member_id: str,
    ) -> List[Reward]:
        """Pobierz dostępne nagrody dla członka"""
        member = self.members.get(member_id)
        if not member:
            return []
        
        available = []
        for reward in self.rewards.values():
            # Sprawdź poziom
            if member.tier.value < reward.min_tier.value:
                continue
            
            # Sprawdź punkty
            if member.available_points < reward.points_cost:
                continue
            
            # Sprawdź dostępność
            if reward.stock is not None and reward.stock <= 0:
                continue
            
            # Sprawdź daty
            if reward.valid_until and reward.valid_until < datetime.utcnow():
                continue
            
            available.append(reward)
        
        return sorted(available, key=lambda r: r.points_cost)
    
    async def process_referral(
        self,
        referral_code: str,
        new_user_id: str,
    ) -> bool:
        """Przetwórz polecenie (nowy użytkownik użył kodu)"""
        # Znajdź polecającego
        referrer = None
        for member in self.members.values():
            if member.referral_code == referral_code:
                referrer = member
                break
        
        if not referrer:
            return False
        
        # Przyznaj punkty polecającemu
        await self.award_points(
            referrer.id,
            PointsAction.REFERRAL,
            metadata={'referred_user_id': new_user_id},
        )
        
        referrer.referrals_count += 1
        
        logger.info(f"Referral processed: {referrer.user_id} referred {new_user_id}")
        
        return True
    
    async def process_successful_referral(
        self,
        referral_code: str,
        transaction_value: float,
    ) -> bool:
        """Przetwórz udane polecenie (transakcja)"""
        referrer = None
        for member in self.members.values():
            if member.referral_code == referral_code:
                referrer = member
                break
        
        if not referrer:
            return False
        
        # Przyznaj punkty za udane polecenie
        await self.award_points(
            referrer.id,
            PointsAction.REFERRAL_SUCCESS,
            metadata={'transaction_value': transaction_value},
        )
        
        referrer.successful_referrals += 1
        
        logger.info(f"Successful referral: {referrer.user_id}, transaction: {transaction_value}")
        
        return True
    
    async def get_transaction_history(
        self,
        member_id: str,
        limit: int = 50,
    ) -> List[PointsTransaction]:
        """Historia transakcji punktowych"""
        member = self.members.get(member_id)
        if not member:
            return []
        
        transactions = sorted(
            member.transactions,
            key=lambda t: t.created_at,
            reverse=True,
        )
        
        return transactions[:limit]
    
    async def get_leaderboard(
        self,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Ranking członków"""
        sorted_members = sorted(
            self.members.values(),
            key=lambda m: m.lifetime_points,
            reverse=True,
        )
        
        return [
            {
                'rank': idx + 1,
                'user_id': m.user_id,
                'tier': m.tier.value,
                'lifetime_points': m.lifetime_points,
                'successful_referrals': m.successful_referrals,
            }
            for idx, m in enumerate(sorted_members[:limit])
        ]
    
    async def get_stats(self) -> Dict[str, Any]:
        """Statystyki programu"""
        total_members = len(self.members)
        
        by_tier = {}
        for tier in LoyaltyTier:
            count = len([m for m in self.members.values() if m.tier == tier])
            by_tier[tier.value] = count
        
        total_points_issued = sum(m.lifetime_points for m in self.members.values())
        total_referrals = sum(m.referrals_count for m in self.members.values())
        
        return {
            'total_members': total_members,
            'by_tier': by_tier,
            'total_points_issued': total_points_issued,
            'total_referrals': total_referrals,
        }
    
    # ==========================================================================
    # Metody prywatne
    # ==========================================================================
    
    async def _check_tier_upgrade(self, member: LoyaltyMember):
        """Sprawdź czy członek powinien awansować poziom"""
        new_tier = None
        
        if member.lifetime_points >= 10000:
            new_tier = LoyaltyTier.PLATINUM
        elif member.lifetime_points >= 5000:
            new_tier = LoyaltyTier.GOLD
        elif member.lifetime_points >= 1000:
            new_tier = LoyaltyTier.SILVER
        
        if new_tier and new_tier.value > member.tier.value:
            old_tier = member.tier
            member.tier = new_tier
            member.tier_since = datetime.utcnow()
            
            logger.info(f"Member {member.user_id} upgraded from {old_tier.value} to {new_tier.value}")
    
    def _generate_referral_code(self, user_id: str) -> str:
        """Generuj kod polecający"""
        import hashlib
        hash_obj = hashlib.md5(f"{user_id}{datetime.utcnow()}".encode())
        return hash_obj.hexdigest()[:8].upper()
    
    def _generate_reward_code(self) -> str:
        """Generuj kod nagrody"""
        import secrets
        return secrets.token_urlsafe(16).upper()


# Singleton
def get_loyalty_service(db_session: Session) -> LoyaltyProgramService:
    return LoyaltyProgramService(db_session)
