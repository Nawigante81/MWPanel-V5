"""
Services package for shared functionality.
"""
from app.services.rate_limit import (
    TokenBucket,
    DistributedLock,
    get_redis_client,
    get_token_bucket,
    get_distributed_lock,
)
from app.services.circuit_breaker import CircuitBreaker, get_circuit_breaker
from app.services.normalize import (
    PriceNormalizer,
    AreaNormalizer,
    RoomsNormalizer,
    LocationNormalizer,
    CoordinateNormalizer,
)
from app.services.proxy_manager import ProxyManager, get_proxy_manager
from app.services.notifications import (
    NotificationManager,
    get_notification_manager,
    BaseNotifier,
    WhatsAppNotifier,
    EmailNotifier,
    SlackNotifier,
    TelegramNotifier,
    DiscordNotifier,
)
from app.services.smart_filter import (
    OfferScorer,
    PreferenceLearner,
    SmartFilter,
    calculate_price_trend,
)
from app.services.image_analysis import (
    ImageAnalyzer,
    DuplicateImageDetector,
    get_image_analyzer,
    get_duplicate_detector,
)
from app.services.metrics import (
    MetricsCollector,
    get_metrics,
    get_metrics_content_type,
)
from app.services.webhook import (
    WebhookService,
    WebhookVerifier,
    get_webhook_service,
)
from app.services.geofencing import (
    GeoPoint,
    Geofence,
    LocationFilter,
    GeocodingService,
    DistanceMatrixService,
    haversine_distance,
    get_geocoding_service,
    get_distance_service,
)
from app.services.duplicate_detector import (
    CrossSourceDuplicateDetector,
    DuplicateStore,
    get_duplicate_detector,
    get_duplicate_store,
)
from app.services.retry_queue import (
    RetryQueue,
    get_retry_queue,
)
from app.services.config_manager import (
    ConfigManager,
    ConfigValidator,
    get_config_manager,
)
from app.services.export import (
    DataExporter,
    get_data_exporter,
)
from app.services.search import (
    FullTextSearch,
    get_search_service,
)
from app.services.comparison import (
    OfferComparator,
    get_offer_comparator,
)
from app.services.alert_rules import (
    AlertRulesEngine,
    AlertRuleBuilder,
    get_alert_rules_engine,
)
from app.services.reports import (
    ReportGenerator,
    get_report_generator,
)
from app.services.api_rate_limit import (
    APIRateLimiter,
    RateLimitMiddleware,
    get_api_rate_limiter,
)
from app.services.google_sheets import (
    GoogleSheetsSync,
    get_google_sheets_sync,
)
from app.services.backup import (
    BackupService,
    get_backup_service,
)
from app.services.price_prediction import (
    PricePredictionService,
    PricePredictionModel,
    MarketAnalyzer,
    PricePrediction,
    MarketTrend,
    get_price_prediction_service,
)

__all__ = [
    # Rate limiting
    "TokenBucket",
    "DistributedLock",
    "get_redis_client",
    "get_token_bucket",
    "get_distributed_lock",
    # Circuit breaker
    "CircuitBreaker",
    "get_circuit_breaker",
    # Normalization
    "PriceNormalizer",
    "AreaNormalizer",
    "RoomsNormalizer",
    "LocationNormalizer",
    "CoordinateNormalizer",
    # Proxy
    "ProxyManager",
    "get_proxy_manager",
    # Notifications
    "NotificationManager",
    "get_notification_manager",
    "BaseNotifier",
    "WhatsAppNotifier",
    "EmailNotifier",
    "SlackNotifier",
    "TelegramNotifier",
    "DiscordNotifier",
    # Smart filtering
    "OfferScorer",
    "PreferenceLearner",
    "SmartFilter",
    "calculate_price_trend",
    # Image analysis
    "ImageAnalyzer",
    "DuplicateImageDetector",
    "get_image_analyzer",
    "get_duplicate_detector",
    # Metrics
    "MetricsCollector",
    "get_metrics",
    "get_metrics_content_type",
    # Webhooks
    "WebhookService",
    "WebhookVerifier",
    "get_webhook_service",
    # Geofencing
    "GeoPoint",
    "Geofence",
    "LocationFilter",
    "GeocodingService",
    "DistanceMatrixService",
    "haversine_distance",
    "get_geocoding_service",
    "get_distance_service",
    # Duplicate detection
    "CrossSourceDuplicateDetector",
    "DuplicateStore",
    "get_duplicate_detector",
    "get_duplicate_store",
    # Retry queue
    "RetryQueue",
    "get_retry_queue",
    # Config
    "ConfigManager",
    "ConfigValidator",
    "get_config_manager",
    # Export
    "DataExporter",
    "get_data_exporter",
    # Search
    "FullTextSearch",
    "get_search_service",
    # Comparison
    "OfferComparator",
    "get_offer_comparator",
    # Alert rules
    "AlertRulesEngine",
    "AlertRuleBuilder",
    "get_alert_rules_engine",
    # Reports
    "ReportGenerator",
    "get_report_generator",
    # API rate limit
    "APIRateLimiter",
    "RateLimitMiddleware",
    "get_api_rate_limiter",
    # Google Sheets
    "GoogleSheetsSync",
    "get_google_sheets_sync",
    # Backup
    "BackupService",
    "get_backup_service",
    # Price prediction
    "PricePredictionService",
    "PricePredictionModel",
    "MarketAnalyzer",
    "PricePrediction",
    "MarketTrend",
    "get_price_prediction_service",
]
