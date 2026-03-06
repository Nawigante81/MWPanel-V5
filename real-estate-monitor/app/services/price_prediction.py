"""
Price Prediction ML Service.
Uses machine learning to predict property prices and detect good deals.
"""
import pickle
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from decimal import Decimal

import numpy as np
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger
from app.models import Offer, PriceHistory
from app.schemas import OfferNormalized
from app.settings import settings

logger = get_logger("price_prediction")

# Try to import sklearn, but make it optional
try:
    from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
    from sklearn.preprocessing import StandardScaler, LabelEncoder
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_absolute_error, r2_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn not installed, price prediction disabled")


@dataclass
class PricePrediction:
    """Price prediction result."""
    predicted_price: float
    confidence_score: float  # 0-1
    price_range_low: float
    price_range_high: float
    deal_rating: str  # "excellent", "good", "fair", "overpriced"
    deal_score: float  # -100 to +100, positive = good deal
    factors: Dict[str, float]  # Feature importance


@dataclass
class MarketTrend:
    """Market trend analysis."""
    trend_direction: str  # "rising", "falling", "stable"
    trend_strength: float  # 0-1
    avg_price_change_percent: float
    forecast_next_month: float
    confidence: float


class PricePredictionModel:
    """
    Machine Learning model for property price prediction.
    
    Features:
    - Area (m²)
    - Number of rooms
    - City/Region (encoded)
    - Source (encoded)
    - Days since listing
    """
    
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler() if SKLEARN_AVAILABLE else None
        self.city_encoder = LabelEncoder() if SKLEARN_AVAILABLE else None
        self.region_encoder = LabelEncoder() if SKLEARN_AVAILABLE else None
        self.source_encoder = LabelEncoder() if SKLEARN_AVAILABLE else None
        self.is_trained = False
        self.training_date = None
        self.metrics = {}
    
    async def train(self, session: AsyncSession, min_samples: int = 100) -> bool:
        """
        Train the price prediction model.
        
        Args:
            session: Database session
            min_samples: Minimum samples required for training
        
        Returns:
            True if training successful
        """
        if not SKLEARN_AVAILABLE:
            logger.warning("scikit-learn not available, cannot train model")
            return False
        
        # Fetch training data
        offers = await session.execute(
            select(Offer)
            .where(Offer.price.isnot(None))
            .where(Offer.area_m2.isnot(None))
            .where(Offer.city.isnot(None))
            .where(Offer.status == "active")
            .limit(5000)
        )
        offers = offers.scalars().all()
        
        if len(offers) < min_samples:
            logger.warning(f"Not enough samples for training: {len(offers)} < {min_samples}")
            return False
        
        logger.info(f"Training price prediction model with {len(offers)} samples")
        
        # Prepare features
        X, y = self._prepare_training_data(offers)
        
        if len(X) < min_samples:
            logger.warning(f"Not enough valid samples after preprocessing")
            return False
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train model
        self.model = GradientBoostingRegressor(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42
        )
        
        self.model.fit(X_train_scaled, y_train)
        
        # Evaluate
        y_pred = self.model.predict(X_test_scaled)
        
        self.metrics = {
            "mae": mean_absolute_error(y_test, y_pred),
            "r2": r2_score(y_test, y_pred),
            "samples": len(offers),
            "training_date": datetime.utcnow().isoformat(),
        }
        
        self.is_trained = True
        self.training_date = datetime.utcnow()
        
        logger.info(f"Model trained successfully. MAE: {self.metrics['mae']:.2f}, R²: {self.metrics['r2']:.3f}")
        
        return True
    
    def _prepare_training_data(self, offers: List[Offer]) -> Tuple[np.ndarray, np.ndarray]:
        """Prepare feature matrix and target vector."""
        features = []
        targets = []
        
        # Collect all cities, regions, sources for encoding
        cities = list(set(o.city for o in offers if o.city))
        regions = list(set(o.region for o in offers if o.region))
        sources = list(set(o.source.name for o in offers if o.source))
        
        if cities:
            self.city_encoder.fit(cities)
        if regions:
            self.region_encoder.fit(regions)
        if sources:
            self.source_encoder.fit(sources)
        
        for offer in offers:
            if not offer.price or not offer.area_m2:
                continue
            
            feature_vector = self._extract_features(offer)
            if feature_vector is not None:
                features.append(feature_vector)
                targets.append(float(offer.price))
        
        return np.array(features), np.array(targets)
    
    def _extract_features(self, offer: Offer) -> Optional[List[float]]:
        """Extract feature vector from offer."""
        try:
            features = [
                offer.area_m2 or 0,
                offer.rooms or 0,
                (datetime.utcnow() - offer.first_seen).days if offer.first_seen else 0,
            ]
            
            # Encode categorical features
            if offer.city and self.city_encoder:
                try:
                    city_encoded = self.city_encoder.transform([offer.city])[0]
                except ValueError:
                    city_encoded = -1
                features.append(city_encoded)
            else:
                features.append(-1)
            
            if offer.region and self.region_encoder:
                try:
                    region_encoded = self.region_encoder.transform([offer.region])[0]
                except ValueError:
                    region_encoded = -1
                features.append(region_encoded)
            else:
                features.append(-1)
            
            if offer.source and offer.source.name and self.source_encoder:
                try:
                    source_encoded = self.source_encoder.transform([offer.source.name])[0]
                except ValueError:
                    source_encoded = -1
                features.append(source_encoded)
            else:
                features.append(-1)
            
            return features
            
        except Exception as e:
            logger.debug(f"Failed to extract features: {e}")
            return None
    
    def predict(self, offer: OfferNormalized) -> Optional[PricePrediction]:
        """
        Predict price for an offer.
        
        Returns:
            PricePrediction or None if model not trained
        """
        if not self.is_trained or not SKLEARN_AVAILABLE:
            return None
        
        try:
            # Extract features
            features = self._extract_features_from_normalized(offer)
            if features is None:
                return None
            
            # Scale and predict
            X = self.scaler.transform([features])
            predicted = self.model.predict(X)[0]
            
            # Get feature importance
            importance = dict(zip(
                ["area", "rooms", "days_listed", "city", "region", "source"],
                self.model.feature_importances_
            ))
            
            # Calculate confidence based on R²
            confidence = self.metrics.get("r2", 0.5)
            
            # Calculate price range (±10% based on MAE)
            mae = self.metrics.get("mae", predicted * 0.1)
            price_range_low = max(0, predicted - mae * 2)
            price_range_high = predicted + mae * 2
            
            # Calculate deal rating
            actual_price = float(offer.price) if offer.price else predicted
            price_diff_percent = ((actual_price - predicted) / predicted) * 100
            
            if price_diff_percent < -15:
                deal_rating = "excellent"
                deal_score = min(100, abs(price_diff_percent) * 3)
            elif price_diff_percent < -5:
                deal_rating = "good"
                deal_score = min(50, abs(price_diff_percent) * 2)
            elif price_diff_percent < 5:
                deal_rating = "fair"
                deal_score = 0
            elif price_diff_percent < 15:
                deal_rating = "overpriced"
                deal_score = -min(50, price_diff_percent * 2)
            else:
                deal_rating = "very_overpriced"
                deal_score = -min(100, price_diff_percent * 3)
            
            return PricePrediction(
                predicted_price=round(predicted, 2),
                confidence_score=round(confidence, 2),
                price_range_low=round(price_range_low, 2),
                price_range_high=round(price_range_high, 2),
                deal_rating=deal_rating,
                deal_score=round(deal_score, 2),
                factors=importance
            )
            
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return None
    
    def _extract_features_from_normalized(self, offer: OfferNormalized) -> Optional[List[float]]:
        """Extract features from normalized offer."""
        try:
            features = [
                offer.area_m2 or 0,
                offer.rooms or 0,
                0,  # days_listed - unknown for new offers
            ]
            
            # Encode categorical features
            if offer.city and self.city_encoder:
                try:
                    city_encoded = self.city_encoder.transform([offer.city])[0]
                except ValueError:
                    city_encoded = -1
                features.append(city_encoded)
            else:
                features.append(-1)
            
            if offer.region and self.region_encoder:
                try:
                    region_encoded = self.region_encoder.transform([offer.region])[0]
                except ValueError:
                    region_encoded = -1
                features.append(region_encoded)
            else:
                features.append(-1)
            
            if offer.source and self.source_encoder:
                try:
                    source_encoded = self.source_encoder.transform([offer.source])[0]
                except ValueError:
                    source_encoded = -1
                features.append(source_encoded)
            else:
                features.append(-1)
            
            return features
            
        except Exception as e:
            logger.debug(f"Failed to extract features: {e}")
            return None
    
    def save_model(self, filepath: str):
        """Save trained model to file."""
        if not self.is_trained:
            logger.warning("Cannot save untrained model")
            return
        
        try:
            model_data = {
                "model": self.model,
                "scaler": self.scaler,
                "city_encoder": self.city_encoder,
                "region_encoder": self.region_encoder,
                "source_encoder": self.source_encoder,
                "metrics": self.metrics,
                "training_date": self.training_date,
            }
            
            with open(filepath, 'wb') as f:
                pickle.dump(model_data, f)
            
            logger.info(f"Model saved to {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to save model: {e}")
    
    def load_model(self, filepath: str) -> bool:
        """Load trained model from file."""
        try:
            with open(filepath, 'rb') as f:
                model_data = pickle.load(f)
            
            self.model = model_data["model"]
            self.scaler = model_data["scaler"]
            self.city_encoder = model_data["city_encoder"]
            self.region_encoder = model_data["region_encoder"]
            self.source_encoder = model_data["source_encoder"]
            self.metrics = model_data["metrics"]
            self.training_date = model_data["training_date"]
            self.is_trained = True
            
            logger.info(f"Model loaded from {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False


class MarketAnalyzer:
    """Analyze market trends and forecast prices."""
    
    async def analyze_trends(
        self,
        session: AsyncSession,
        city: Optional[str] = None,
        days: int = 90
    ) -> MarketTrend:
        """
        Analyze market trends for a city or overall.
        
        Args:
            session: Database session
            city: City to analyze (None for all)
            days: Number of days to analyze
        
        Returns:
            MarketTrend with analysis results
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        # Build query
        query = select(Offer).where(Offer.first_seen >= cutoff)
        
        if city:
            query = query.where(Offer.city.ilike(f"%{city}%"))
        
        result = await session.execute(query)
        offers = result.scalars().all()
        
        if len(offers) < 10:
            return MarketTrend(
                trend_direction="unknown",
                trend_strength=0,
                avg_price_change_percent=0,
                forecast_next_month=0,
                confidence=0
            )
        
        # Group by week
        weekly_prices = {}
        for offer in offers:
            if not offer.price:
                continue
            
            week = offer.first_seen.isocalendar()[1]
            year = offer.first_seen.year
            key = f"{year}-{week}"
            
            if key not in weekly_prices:
                weekly_prices[key] = []
            weekly_prices[key].append(float(offer.price))
        
        if len(weekly_prices) < 2:
            return MarketTrend(
                trend_direction="stable",
                trend_strength=0,
                avg_price_change_percent=0,
                forecast_next_month=0,
                confidence=0.5
            )
        
        # Calculate weekly averages
        weekly_avg = {
            k: sum(v) / len(v)
            for k, v in sorted(weekly_prices.items())
        }
        
        prices = list(weekly_avg.values())
        
        # Calculate trend
        first_price = prices[0]
        last_price = prices[-1]
        
        change_percent = ((last_price - first_price) / first_price) * 100
        
        # Determine trend direction
        if change_percent > 5:
            trend_direction = "rising"
            trend_strength = min(1, abs(change_percent) / 20)
        elif change_percent < -5:
            trend_direction = "falling"
            trend_strength = min(1, abs(change_percent) / 20)
        else:
            trend_direction = "stable"
            trend_strength = 0
        
        # Simple linear forecast
        if len(prices) >= 4:
            # Use last 4 weeks for trend
            recent_change = prices[-1] - prices[-4]
            forecast = prices[-1] + (recent_change / 4)  # Project next week
        else:
            forecast = last_price
        
        # Confidence based on sample size
        confidence = min(1, len(offers) / 100)
        
        return MarketTrend(
            trend_direction=trend_direction,
            trend_strength=round(trend_strength, 2),
            avg_price_change_percent=round(change_percent, 2),
            forecast_next_month=round(forecast, 2),
            confidence=round(confidence, 2)
        )
    
    async def find_good_deals(
        self,
        session: AsyncSession,
        predictor: PricePredictionModel,
        min_deal_score: float = 30,
        limit: int = 20
    ) -> List[Dict]:
        """
        Find underpriced offers (good deals).
        
        Args:
            session: Database session
            predictor: Trained prediction model
            min_deal_score: Minimum deal score to include
            limit: Maximum results
        
        Returns:
            List of good deals
        """
        if not predictor.is_trained:
            return []
        
        # Get recent offers
        cutoff = datetime.utcnow() - timedelta(days=7)
        
        result = await session.execute(
            select(Offer)
            .where(Offer.first_seen >= cutoff)
            .where(Offer.status == "active")
            .where(Offer.price.isnot(None))
            .order_by(Offer.first_seen.desc())
            .limit(200)
        )
        
        offers = result.scalars().all()
        
        good_deals = []
        
        for offer in offers:
            # Convert to normalized for prediction
            from app.schemas import OfferNormalized
            
            normalized = OfferNormalized(
                source=offer.source.name if offer.source else "unknown",
                url=offer.url,
                title=offer.title,
                price=offer.price,
                currency=offer.currency,
                city=offer.city,
                region=offer.region,
                area_m2=offer.area_m2,
                rooms=offer.rooms,
                lat=offer.lat,
                lng=offer.lng,
            )
            
            prediction = predictor.predict(normalized)
            
            if prediction and prediction.deal_score >= min_deal_score:
                good_deals.append({
                    "offer_id": str(offer.id),
                    "title": offer.title,
                    "actual_price": float(offer.price) if offer.price else None,
                    "predicted_price": prediction.predicted_price,
                    "deal_score": prediction.deal_score,
                    "deal_rating": prediction.deal_rating,
                    "savings": round(prediction.predicted_price - float(offer.price), 2) if offer.price else None,
                    "url": offer.url,
                })
        
        # Sort by deal score
        good_deals.sort(key=lambda x: x["deal_score"], reverse=True)
        
        return good_deals[:limit]


class PricePredictionService:
    """Main service for price prediction features."""
    
    def __init__(self):
        self.model = PricePredictionModel()
        self.analyzer = MarketAnalyzer()
        self.model_path = "/app/data/price_model.pkl"
    
    async def initialize(self, session: AsyncSession):
        """Initialize the service - load or train model."""
        # Try to load existing model
        import os
        if os.path.exists(self.model_path):
            if self.model.load_model(self.model_path):
                return
        
        # Train new model
        await self.model.train(session)
        
        # Save if trained
        if self.model.is_trained:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            self.model.save_model(self.model_path)
    
    async def predict_offer(
        self,
        offer: OfferNormalized
    ) -> Optional[PricePrediction]:
        """Predict price for an offer."""
        return self.model.predict(offer)
    
    async def analyze_market(
        self,
        session: AsyncSession,
        city: Optional[str] = None
    ) -> MarketTrend:
        """Analyze market trends."""
        return await self.analyzer.analyze_trends(session, city)
    
    async def find_deals(
        self,
        session: AsyncSession,
        min_score: float = 30
    ) -> List[Dict]:
        """Find good deals."""
        return await self.analyzer.find_good_deals(
            session, self.model, min_score
        )
    
    def get_model_info(self) -> Dict:
        """Get model information."""
        return {
            "is_trained": self.model.is_trained,
            "training_date": self.model.training_date.isoformat() if self.model.training_date else None,
            "metrics": self.model.metrics,
            "sklearn_available": SKLEARN_AVAILABLE,
        }


# Celery task for model retraining
from app.tasks.celery_app import celery_app


@celery_app.task
def retrain_price_model():
    """Scheduled task to retrain price prediction model."""
    import asyncio
    asyncio.run(_do_retrain())


async def _do_retrain():
    """Async retrain function."""
    from app.db import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        service = PricePredictionService()
        
        success = await service.model.train(session)
        
        if success:
            import os
            os.makedirs(os.path.dirname(service.model_path), exist_ok=True)
            service.model.save_model(service.model_path)
            logger.info("Price model retrained and saved")
        else:
            logger.warning("Price model retraining failed")


# Global instance
_price_service: Optional[PricePredictionService] = None


def get_price_prediction_service() -> PricePredictionService:
    """Get or create price prediction service."""
    global _price_service
    
    if _price_service is None:
        _price_service = PricePredictionService()
    
    return _price_service
