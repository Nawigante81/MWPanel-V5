"""
Advanced Alert Rules Engine.
Allows users to create custom alert rules with conditions.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from app.logging_config import get_logger
from app.models import AlertRule, AlertOperator, NotificationChannel
from app.schemas import OfferNormalized
from app.services.notifications import get_notification_manager

logger = get_logger("alert_rules")


class AlertRulesEngine:
    """
    Engine for evaluating alert rules against offers.
    
    Supports complex conditions like:
    - price < 500000 AND city = "Gdańsk"
    - area > 50 AND rooms >= 3
    """
    
    def __init__(self):
        self.operators = {
            AlertOperator.LESS_THAN: lambda x, y: x < y,
            AlertOperator.LESS_EQUAL: lambda x, y: x <= y,
            AlertOperator.GREATER_THAN: lambda x, y: x > y,
            AlertOperator.GREATER_EQUAL: lambda x, y: x >= y,
            AlertOperator.EQUAL: lambda x, y: x == y,
            AlertOperator.NOT_EQUAL: lambda x, y: x != y,
            AlertOperator.CONTAINS: lambda x, y: y.lower() in str(x).lower(),
            AlertOperator.IN: lambda x, y: x in y if isinstance(y, list) else x == y,
        }
    
    def evaluate_rule(self, rule: AlertRule, offer: OfferNormalized) -> bool:
        """
        Evaluate if an offer matches the alert rule conditions.
        
        Args:
            rule: AlertRule with conditions
            offer: Offer to check
        
        Returns:
            True if offer matches all conditions
        """
        if not rule.is_active:
            return False
        
        # Check cooldown
        if rule.last_triggered:
            cooldown_end = rule.last_triggered + timedelta(minutes=rule.cooldown_minutes)
            if datetime.utcnow() < cooldown_end:
                return False
        
        # Evaluate all conditions (AND logic)
        for condition in rule.conditions:
            if not self._evaluate_condition(condition, offer):
                return False
        
        return True
    
    def _evaluate_condition(self, condition: dict, offer: OfferNormalized) -> bool:
        """Evaluate a single condition."""
        field = condition.get("field")
        operator = AlertOperator(condition.get("operator"))
        value = condition.get("value")
        
        # Get field value from offer
        offer_value = self._get_field_value(offer, field)
        
        if offer_value is None:
            return False
        
        # Apply operator
        op_func = self.operators.get(operator)
        if not op_func:
            logger.warning(f"Unknown operator: {operator}")
            return False
        
        try:
            return op_func(offer_value, value)
        except Exception as e:
            logger.error(f"Error evaluating condition: {e}")
            return False
    
    def _get_field_value(self, offer: OfferNormalized, field: str) -> Any:
        """Get field value from offer."""
        field_map = {
            "price": offer.price,
            "area_m2": offer.area_m2,
            "rooms": offer.rooms,
            "city": offer.city,
            "region": offer.region,
            "source": offer.source,
            "title": offer.title,
        }
        return field_map.get(field)
    
    async def trigger_rule(self, rule: AlertRule, offer: OfferNormalized):
        """Trigger alert for a rule."""
        logger.info(
            f"Triggering alert rule: {rule.name}",
            extra={"rule_id": str(rule.id), "offer_url": offer.url}
        )
        
        # Send notifications
        notifier = get_notification_manager()
        
        for channel_str in rule.channels:
            channel = NotificationChannel(channel_str)
            try:
                await notifier.send_to_channel(channel, offer, rule.user_id)
            except Exception as e:
                logger.error(f"Failed to send alert to {channel}: {e}")
        
        # Update rule stats
        rule.last_triggered = datetime.utcnow()
        rule.trigger_count += 1
    
    def check_all_rules(self, rules: List[AlertRule], offer: OfferNormalized) -> List[AlertRule]:
        """
        Check all rules against an offer.
        
        Returns:
            List of triggered rules
        """
        triggered = []
        
        for rule in rules:
            if self.evaluate_rule(rule, offer):
                triggered.append(rule)
        
        return triggered


class AlertRuleBuilder:
    """Helper class for building alert rules."""
    
    @staticmethod
    def price_drop_rule(
        user_id: str,
        threshold_percent: float = 5.0
    ) -> dict:
        """Build a rule for price drops."""
        return {
            "user_id": user_id,
            "name": f"Price Drop Alert ({threshold_percent}%)",
            "conditions": [
                {"field": "status", "operator": "eq", "value": "price_changed"}
            ],
            "channels": ["whatsapp", "email"],
            "cooldown_minutes": 60,
        }
    
    @staticmethod
    def location_price_rule(
        user_id: str,
        city: str,
        max_price: float
    ) -> dict:
        """Build a rule for specific city and max price."""
        return {
            "user_id": user_id,
            "name": f"Offers in {city} under {max_price:,.0f} PLN",
            "conditions": [
                {"field": "city", "operator": "contains", "value": city},
                {"field": "price", "operator": "le", "value": max_price},
            ],
            "channels": ["whatsapp"],
            "cooldown_minutes": 30,
        }
    
    @staticmethod
    def size_rule(
        user_id: str,
        min_area: float,
        min_rooms: int
    ) -> dict:
        """Build a rule for minimum size requirements."""
        return {
            "user_id": user_id,
            "name": f"Min {min_area}m² and {min_rooms} rooms",
            "conditions": [
                {"field": "area_m2", "operator": "ge", "value": min_area},
                {"field": "rooms", "operator": "ge", "value": min_rooms},
            ],
            "channels": ["email"],
            "cooldown_minutes": 120,
        }


# Global instance
_rules_engine: Optional[AlertRulesEngine] = None


def get_alert_rules_engine() -> AlertRulesEngine:
    """Get or create alert rules engine."""
    global _rules_engine
    
    if _rules_engine is None:
        _rules_engine = AlertRulesEngine()
    
    return _rules_engine
