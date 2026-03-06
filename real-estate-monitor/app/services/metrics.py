"""
Prometheus metrics export service.
Provides detailed metrics for monitoring and alerting.
"""
from prometheus_client import Counter, Gauge, Histogram, Info, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client.registry import CollectorRegistry

from app.logging_config import get_logger

logger = get_logger("metrics")

# Create custom registry
registry = CollectorRegistry()

# Application info
app_info = Info(
    "real_estate_monitor",
    "Application information",
    registry=registry
)
app_info.info({"version": "1.0.0", "app": "real-estate-monitor"})

# Counters
offers_scraped_total = Counter(
    "offers_scraped_total",
    "Total number of offers scraped",
    ["source", "status"],
    registry=registry
)

offers_inserted_total = Counter(
    "offers_inserted_total",
    "Total number of new offers inserted",
    ["source"],
    registry=registry
)

notifications_sent_total = Counter(
    "notifications_sent_total",
    "Total number of notifications sent",
    ["channel", "status"],
    registry=registry
)

scrape_runs_total = Counter(
    "scrape_runs_total",
    "Total number of scrape runs",
    ["source", "status"],
    registry=registry
)

# Gauges
offers_in_database = Gauge(
    "offers_in_database",
    "Current number of offers in database",
    ["source"],
    registry=registry
)

pending_notifications = Gauge(
    "pending_notifications",
    "Number of pending notifications",
    registry=registry
)

scrape_queue_size = Gauge(
    "scrape_queue_size",
    "Current scrape queue size",
    registry=registry
)

source_health = Gauge(
    "source_health",
    "Source health status (1=healthy, 0=unhealthy)",
    ["source"],
    registry=registry
)

circuit_breaker_state = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half_open)",
    ["source"],
    registry=registry
)

active_proxies = Gauge(
    "active_proxies",
    "Number of active proxies",
    registry=registry
)

# Histograms
scrape_duration_seconds = Histogram(
    "scrape_duration_seconds",
    "Time spent scraping",
    ["source"],
    buckets=[1, 5, 10, 30, 60, 120, 300],
    registry=registry
)

notification_latency_seconds = Histogram(
    "notification_latency_seconds",
    "Time from offer insertion to notification",
    ["channel"],
    buckets=[1, 5, 10, 30, 60, 120, 300],
    registry=registry
)

offer_price_pln = Histogram(
    "offer_price_pln",
    "Distribution of offer prices in PLN",
    buckets=[100000, 200000, 300000, 400000, 500000, 750000, 1000000, 1500000, 2000000],
    registry=registry
)

offer_area_m2 = Histogram(
    "offer_area_m2",
    "Distribution of offer areas",
    buckets=[20, 30, 40, 50, 60, 80, 100, 150, 200],
    registry=registry
)


class MetricsCollector:
    """Helper class for collecting and exposing metrics."""
    
    @staticmethod
    def record_scrape(source: str, status: str, offers_found: int, offers_new: int):
        """Record scrape metrics."""
        offers_scraped_total.labels(source=source, status=status).inc(offers_found)
        scrape_runs_total.labels(source=source, status=status).inc()
        
        if offers_new > 0:
            offers_inserted_total.labels(source=source).inc(offers_new)
    
    @staticmethod
    def record_notification(channel: str, status: str):
        """Record notification metrics."""
        notifications_sent_total.labels(channel=channel, status=status).inc()
    
    @staticmethod
    def record_scrape_duration(source: str, duration: float):
        """Record scrape duration."""
        scrape_duration_seconds.labels(source=source).observe(duration)
    
    @staticmethod
    def record_offer_price(price: float):
        """Record offer price for distribution."""
        if price:
            offer_price_pln.observe(price)
    
    @staticmethod
    def record_offer_area(area: float):
        """Record offer area for distribution."""
        if area:
            offer_area_m2.observe(area)
    
    @staticmethod
    def set_offers_count(source: str, count: int):
        """Set current offers count."""
        offers_in_database.labels(source=source).set(count)
    
    @staticmethod
    def set_pending_notifications(count: int):
        """Set pending notifications count."""
        pending_notifications.set(count)
    
    @staticmethod
    def set_source_health(source: str, healthy: bool):
        """Set source health status."""
        source_health.labels(source=source).set(1 if healthy else 0)
    
    @staticmethod
    def set_circuit_breaker(source: str, state: str):
        """Set circuit breaker state."""
        state_map = {"closed": 0, "open": 1, "half_open": 2}
        circuit_breaker_state.labels(source=source).set(state_map.get(state, 0))
    
    @staticmethod
    def set_active_proxies(count: int):
        """Set active proxies count."""
        active_proxies.set(count)


def get_metrics():
    """Generate Prometheus metrics output."""
    return generate_latest(registry)


def get_metrics_content_type():
    """Get content type for metrics endpoint."""
    return CONTENT_TYPE_LATEST
