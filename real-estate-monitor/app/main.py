"""
FastAPI application for real estate monitor.
Provides health checks, API endpoints, and minimal web panel.
"""
import time
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

import redis
from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session, get_db, get_sync_session
from app.logging_config import get_logger
from app.models import Notification, Offer, ScrapeRun, Source
from app.schemas import (
    FailureResponse,
    HealthCheckComponent,
    HealthCheckResponse,
    OfferListResponse,
    OfferResponse,
    ScrapeRunResponse,
    SourceResponse,
)
from app.services.circuit_breaker import get_circuit_breaker
from app.services.rate_limit import get_redis_client
from app.services.metrics import get_metrics, get_metrics_content_type
from app.services.config_manager import get_config_manager, ConfigValidator
from app.services.export import get_data_exporter
from app.services.webhook import get_webhook_service
from app.services.proxy_manager import get_proxy_manager
from app.services.retry_queue import get_retry_queue
from app.services.search import get_search_service
from app.services.comparison import get_offer_comparator
from app.services.alert_rules import get_alert_rules_engine, AlertRuleBuilder
from app.services.price_prediction import get_price_prediction_service
from app.settings import settings
from app.tasks.scheduler import seed_sources, run_scheduled_scrape
from app.api.compat_router import router as compat_router

logger = get_logger("api")

# Create FastAPI app
app = FastAPI(
    title="Real Estate Monitor",
    description="24/7 Real Estate Listing Monitoring System",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://192.168.100.188:5173",
        "https://domradar.online",
        "https://www.domradar.online",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Frontend compatibility routes (must be registered before legacy endpoints)
app.include_router(compat_router)

# =============================================================================
# Startup Event
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    logger.info("Starting up Real Estate Monitor API")
    
    # Seed initial sources
    try:
        seed_sources.delay()
        logger.info("Seeded initial sources")
    except Exception as e:
        logger.error(f"Failed to seed sources: {e}")


# =============================================================================
# Health Check Endpoints
# =============================================================================

@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """
    Health check endpoint.
    
    Checks:
    - PostgreSQL connectivity
    - Redis connectivity
    - Queue lag estimate
    """
    components = {}
    overall_status = "healthy"
    
    # Check PostgreSQL
    try:
        from app.db import async_engine
        start = time.time()
        async with async_engine.connect() as conn:
            await conn.execute(select(func.now()))
        pg_latency = (time.time() - start) * 1000
        components["postgres"] = HealthCheckComponent(
            status="healthy",
            latency_ms=round(pg_latency, 2),
        )
    except Exception as e:
        components["postgres"] = HealthCheckComponent(
            status="unhealthy",
            error=str(e),
        )
        overall_status = "unhealthy"
    
    # Check Redis
    try:
        start = time.time()
        redis_client = get_redis_client()
        redis_client.ping()
        redis_latency = (time.time() - start) * 1000
        components["redis"] = HealthCheckComponent(
            status="healthy",
            latency_ms=round(redis_latency, 2),
        )
    except Exception as e:
        components["redis"] = HealthCheckComponent(
            status="unhealthy",
            error=str(e),
        )
        overall_status = "unhealthy"
    
    # Estimate queue lag
    queue_lag = None
    try:
        from app.db import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            # Get pending notifications
            pending_count = await session.scalar(
                select(func.count(Notification.id))
                .where(Notification.status == "pending")
            )
            
            # Get last scrape run
            last_scrape = await session.scalar(
                select(ScrapeRun)
                .order_by(desc(ScrapeRun.started_at))
                .limit(1)
            )
            
            if last_scrape:
                lag = datetime.utcnow() - last_scrape.started_at
                queue_lag = lag.total_seconds()
    except Exception as e:
        logger.debug(f"Could not estimate queue lag: {e}")
    
    return HealthCheckResponse(
        status=overall_status,
        timestamp=datetime.utcnow(),
        components=components,
        queue_lag_seconds=queue_lag,
    )


@app.get("/metrics")
async def metrics():
    """
    Basic metrics endpoint (JSON format).
    """
    metrics_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "counters": {},
        "gauges": {},
    }
    
    try:
        from app.db import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            # Offer counts
            total_offers = await session.scalar(select(func.count(Offer.id)))
            new_offers_24h = await session.scalar(
                select(func.count(Offer.id))
                .where(Offer.first_seen >= datetime.utcnow() - timedelta(hours=24))
            )
            
            metrics_data["counters"]["total_offers"] = total_offers
            metrics_data["counters"]["new_offers_24h"] = new_offers_24h
            
            # Notification counts
            pending_notifications = await session.scalar(
                select(func.count(Notification.id))
                .where(Notification.status == "pending")
            )
            failed_notifications = await session.scalar(
                select(func.count(Notification.id))
                .where(Notification.status == "failed")
            )
            
            metrics_data["gauges"]["pending_notifications"] = pending_notifications
            metrics_data["gauges"]["failed_notifications"] = failed_notifications
            
            # Source health
            sources = await session.execute(select(Source))
            for source in sources.scalars():
                metrics_data["gauges"][f"source_{source.name}_enabled"] = (
                    1 if source.enabled else 0
                )
    except Exception as e:
        logger.error(f"Failed to collect metrics: {e}")
    
    return metrics_data


# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/sources", response_model=List[SourceResponse])
async def list_sources(
    session: AsyncSession = Depends(get_db),
):
    """List all configured sources."""
    result = await session.execute(
        select(Source).order_by(Source.name)
    )
    sources = result.scalars().all()
    return sources


@app.get("/sources/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Get a single source by ID."""
    source = await session.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@app.get("/offers", response_model=OfferListResponse)
async def list_offers(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=500),
    offset: Optional[int] = Query(default=None, ge=0),
    source: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    sort: Optional[str] = Query(default=None),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_db),
):
    """
    List offers with pagination, filtering and sorting.

    Date filtering/sorting is based on source publication date (source_created_at),
    with fallback to first_seen for legacy rows.
    """
    if offset is None:
        offset = (page - 1) * limit
    else:
        page = (offset // limit) + 1

    query = select(Offer)
    count_query = select(func.count(Offer.id))

    source_obj = None
    if source:
        source_obj = await session.scalar(select(Source).where(Source.name == source))
        if source_obj:
            query = query.where(Offer.source_id == source_obj.id)
            count_query = count_query.where(Offer.source_id == source_obj.id)
        else:
            return OfferListResponse(
                items=[],
                data=[],
                total=0,
                page=page,
                pages=0,
                limit=limit,
                offset=offset,
                source=source,
                status=status,
            )

    if status:
        query = query.where(Offer.status == status)
        count_query = count_query.where(Offer.status == status)
    else:
        # hide parser garbage by default
        query = query.where(Offer.status != "invalid_parse")
        count_query = count_query.where(Offer.status != "invalid_parse")

    parsed_from = None
    parsed_to = None
    try:
        if date_from:
            parsed_from = datetime.fromisoformat(date_from).replace(hour=0, minute=0, second=0, microsecond=0)
        if date_to:
            parsed_to = datetime.fromisoformat(date_to).replace(hour=23, minute=59, second=59, microsecond=999999)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid date format. Use YYYY-MM-DD.")

    pub_dt = func.coalesce(Offer.source_created_at, Offer.first_seen)

    if parsed_from:
        query = query.where(pub_dt >= parsed_from)
        count_query = count_query.where(pub_dt >= parsed_from)
    if parsed_to:
        query = query.where(pub_dt <= parsed_to)
        count_query = count_query.where(pub_dt <= parsed_to)

    total = int(await session.scalar(count_query) or 0)
    pages = (total + limit - 1) // limit if total else 0

    # Sorting
    if sort == "date":
        sort_col = pub_dt
    else:
        sort_col = Offer.last_seen

    sort_expr = sort_col.asc() if order == "asc" else sort_col.desc()

    result = await session.execute(query.order_by(sort_expr).offset(offset).limit(limit))
    offers = result.scalars().all()

    return OfferListResponse(
        items=offers,
        data=offers,
        total=total,
        page=page,
        pages=pages,
        limit=limit,
        offset=offset,
        source=source,
        status=status,
    )


@app.get("/offers/{offer_id}", response_model=OfferResponse)
async def get_offer(
    offer_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Get a single offer by ID."""
    offer = await session.get(Offer, offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    return offer


@app.get("/scrape-runs", response_model=List[ScrapeRunResponse])
async def list_scrape_runs(
    limit: int = Query(default=20, ge=1, le=100),
    source: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_db),
):
    """List recent scrape runs."""
    query = select(ScrapeRun).order_by(desc(ScrapeRun.started_at))
    
    if source:
        source_obj = await session.scalar(
            select(Source).where(Source.name == source)
        )
        if source_obj:
            query = query.where(ScrapeRun.source_id == source_obj.id)
    
    result = await session.execute(query.limit(limit))
    return result.scalars().all()


@app.get("/failures", response_model=List[FailureResponse])
async def list_failures(
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
):
    """
    List recent failures (scrape errors and notification errors).
    """
    failures = []
    
    # Get failed scrape runs
    scrape_result = await session.execute(
        select(ScrapeRun)
        .where(ScrapeRun.status == "failed")
        .where(ScrapeRun.error.isnot(None))
        .order_by(desc(ScrapeRun.started_at))
        .limit(limit // 2)
    )
    
    for run in scrape_result.scalars():
        source = await session.get(Source, run.source_id)
        failures.append(FailureResponse(
            type="scrape",
            id=run.id,
            source_id=run.source_id,
            source_name=source.name if source else None,
            error=run.error,
            created_at=run.started_at,
        ))
    
    # Get failed notifications
    notify_result = await session.execute(
        select(Notification)
        .where(Notification.status == "failed")
        .where(Notification.last_error.isnot(None))
        .order_by(desc(Notification.created_at))
        .limit(limit // 2)
    )
    
    for notification in notify_result.scalars():
        offer = await session.get(Offer, notification.offer_id)
        source = await session.get(Source, offer.source_id) if offer else None
        failures.append(FailureResponse(
            type="notify",
            id=notification.id,
            source_id=source.id if source else None,
            source_name=source.name if source else None,
            error=notification.last_error,
            created_at=notification.created_at,
            tries=notification.tries,
            status=notification.status,
        ))
    
    # Sort by created_at descending
    failures.sort(key=lambda x: x.created_at, reverse=True)
    
    return failures[:limit]


# =============================================================================
# Circuit Breaker Endpoints
# =============================================================================

@app.get("/circuit-breakers")
async def list_circuit_breakers():
    """List circuit breaker status for all sources."""
    breaker = get_circuit_breaker()
    
    with get_async_session() as session:
        result = await session.execute(select(Source))
        sources = result.scalars().all()
    
    statuses = []
    for source in sources:
        status = breaker.get_status(source.name)
        statuses.append(status)
    
    return statuses


@app.post("/circuit-breakers/{source_name}/reset")
async def reset_circuit_breaker(source_name: str):
    """Manually reset a circuit breaker."""
    breaker = get_circuit_breaker()
    breaker.manual_reset(source_name)
    return {"status": "reset", "source": source_name}


# =============================================================================
# Minimal Web Panel (HTML)
# =============================================================================

@app.get("/panel", response_class=HTMLResponse)
async def web_panel():
    """Simple HTML panel for viewing offers."""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Real Estate Monitor</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
            h1 { color: #333; }
            .container { max-width: 1200px; margin: 0 auto; }
            .stats { display: flex; gap: 20px; margin-bottom: 20px; }
            .stat-card { background: white; padding: 15px; border-radius: 8px; flex: 1; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .stat-value { font-size: 24px; font-weight: bold; color: #2196F3; }
            .stat-label { color: #666; font-size: 14px; }
            .offer-card { background: white; padding: 15px; margin-bottom: 10px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .offer-title { font-weight: bold; color: #333; margin-bottom: 5px; }
            .offer-details { color: #666; font-size: 14px; }
            .offer-price { color: #4CAF50; font-weight: bold; }
            .offer-link { color: #2196F3; text-decoration: none; }
            .offer-link:hover { text-decoration: underline; }
            .source-badge { display: inline-block; padding: 2px 8px; background: #e3f2fd; color: #1976d2; border-radius: 4px; font-size: 12px; margin-left: 10px; }
            .nav { margin-bottom: 20px; }
            .nav a { margin-right: 15px; color: #2196F3; text-decoration: none; }
            .status-healthy { color: #4CAF50; }
            .status-unhealthy { color: #f44336; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Real Estate Monitor</h1>
            <div class="nav">
                <a href="/panel">Dashboard</a>
                <a href="/health">Health</a>
                <a href="/metrics">Metrics</a>
                <a href="/docs">API Docs</a>
            </div>
            <div id="content">
                <p>Loading...</p>
            </div>
        </div>
        <script>
            async function loadDashboard() {
                try {
                    const [health, offers, sources] = await Promise.all([
                        fetch('/health').then(r => r.json()),
                        fetch('/offers?limit=10').then(r => r.json()),
                        fetch('/sources').then(r => r.json())
                    ]);
                    
                    let html = '<div class="stats">';
                    html += '<div class="stat-card">';
                    html += '<div class="stat-value status-' + health.status + '">' + health.status + '</div>';
                    html += '<div class="stat-label">System Status</div>';
                    html += '</div>';
                    html += '<div class="stat-card">';
                    html += '<div class="stat-value">' + offers.total + '</div>';
                    html += '<div class="stat-label">Total Offers</div>';
                    html += '</div>';
                    html += '<div class="stat-card">';
                    html += '<div class="stat-value">' + sources.length + '</div>';
                    html += '<div class="stat-label">Active Sources</div>';
                    html += '</div>';
                    html += '</div>';
                    
                    html += '<h2>Recent Offers</h2>';
                    offers.items.forEach(offer => {
                        html += '<div class="offer-card">';
                        html += '<div class="offer-title">' + escapeHtml(offer.title) + '</div>';
                        html += '<div class="offer-details">';
                        if (offer.price) {
                            html += '<span class="offer-price">' + offer.price + ' ' + (offer.currency || 'PLN') + '</span>';
                        }
                        if (offer.area_m2) {
                            html += ' | ' + offer.area_m2 + ' m²';
                        }
                        if (offer.rooms) {
                            html += ' | ' + offer.rooms + ' pok';
                        }
                        if (offer.city) {
                            html += ' | ' + escapeHtml(offer.city);
                        }
                        html += '</div>';
                        html += '<div><a class="offer-link" href="' + offer.url + '" target="_blank">View Offer</a></div>';
                        html += '</div>';
                    });
                    
                    document.getElementById('content').innerHTML = html;
                } catch (e) {
                    document.getElementById('content').innerHTML = '<p>Error loading dashboard: ' + e.message + '</p>';
                }
            }
            
            function escapeHtml(text) {
                const div = document.createElement('div');
                div.textContent = text;
                return div.innerHTML;
            }
            
            loadDashboard();
            setInterval(loadDashboard, 30000);  // Refresh every 30 seconds
        </script>
    </body>
    </html>
    """
    return html


# =============================================================================
# Prometheus Metrics Endpoint
# =============================================================================

@app.get("/metrics/prometheus")
async def prometheus_metrics():
    """Prometheus metrics endpoint."""
    from fastapi.responses import Response
    return Response(
        content=get_metrics(),
        media_type=get_metrics_content_type()
    )


# =============================================================================
# Export Endpoints
# =============================================================================

@app.get("/export/csv")
async def export_csv(
    source: Optional[str] = None,
    limit: int = Query(default=10000, ge=1, le=50000),
    session: AsyncSession = Depends(get_db),
):
    """Export offers to CSV."""
    from fastapi.responses import PlainTextResponse
    
    exporter = get_data_exporter()
    csv_data = await exporter.export_to_csv(session, source, limit)
    
    filename = exporter.get_filename("csv", source)
    
    return PlainTextResponse(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.get("/export/json")
async def export_json(
    source: Optional[str] = None,
    limit: int = Query(default=10000, ge=1, le=50000),
    include_raw: bool = Query(default=False),
    session: AsyncSession = Depends(get_db),
):
    """Export offers to JSON."""
    from fastapi.responses import JSONResponse
    
    exporter = get_data_exporter()
    json_data = await exporter.export_to_json(session, source, limit, include_raw)
    
    filename = exporter.get_filename("json", source)
    
    return JSONResponse(
        content=json.loads(json_data),
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.get("/export/excel")
async def export_excel(
    source: Optional[str] = None,
    limit: int = Query(default=10000, ge=1, le=50000),
    session: AsyncSession = Depends(get_db),
):
    """Export offers to Excel."""
    from fastapi.responses import Response
    
    exporter = get_data_exporter()
    excel_data = await exporter.export_to_excel(session, source, limit)
    
    filename = exporter.get_filename("excel", source)
    
    return Response(
        content=excel_data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# =============================================================================
# Config API Endpoints
# =============================================================================

@app.patch("/sources/{source_name}/config")
async def update_source_config(
    source_name: str,
    config: dict,
):
    """Update source configuration dynamically."""
    manager = get_config_manager()
    validator = ConfigValidator()
    
    # Validate inputs
    if 'interval_seconds' in config:
        valid, msg = validator.validate_interval(config['interval_seconds'])
        if not valid:
            raise HTTPException(status_code=400, detail=msg)
    
    if 'rate_limit_rps' in config:
        valid, msg = validator.validate_rate_limit(config['rate_limit_rps'])
        if not valid:
            raise HTTPException(status_code=400, detail=msg)
    
    success = manager.update_source(source_name, **config)
    
    if not success:
        raise HTTPException(status_code=404, detail="Source not found")
    
    return {"status": "updated", "source": source_name, "config": config}


@app.post("/sources/{source_name}/enable")
async def enable_source(source_name: str):
    """Enable a source."""
    manager = get_config_manager()
    success = manager.enable_source(source_name)
    
    if not success:
        raise HTTPException(status_code=404, detail="Source not found")
    
    return {"status": "enabled", "source": source_name}


@app.post("/sources/{source_name}/disable")
async def disable_source(source_name: str):
    """Disable a source."""
    manager = get_config_manager()
    success = manager.disable_source(source_name)
    
    if not success:
        raise HTTPException(status_code=404, detail="Source not found")
    
    return {"status": "disabled", "source": source_name}


@app.get("/config")
async def get_all_configs():
    """Get all source configurations."""
    manager = get_config_manager()
    return manager.get_all_configs()


@app.post("/scrape/trigger")
async def trigger_scrape(source: Optional[str] = Query(default=None)):
    """Manual trigger of scraping jobs (all enabled sources or one source)."""
    queued = []

    if source:
        task = run_scheduled_scrape.delay(source)
        queued.append({"source": source, "task_id": task.id})
    else:
        with get_sync_session() as session:
            source_names = [
                src.name
                for src in session.execute(select(Source).where(Source.enabled == True)).scalars().all()
            ]
        for source_name in source_names:
            task = run_scheduled_scrape.delay(source_name)
            queued.append({"source": source_name, "task_id": task.id})

    return {"status": "queued", "count": len(queued), "items": queued}


# =============================================================================
# Webhook Endpoints
# =============================================================================

@app.get("/webhooks")
async def list_webhooks(session: AsyncSession = Depends(get_db)):
    """List all webhooks."""
    from app.models import Webhook
    
    result = await session.execute(select(Webhook).order_by(Webhook.created_at))
    webhooks = result.scalars().all()
    
    return [
        {
            "id": str(w.id),
            "name": w.name,
            "url": w.url,
            "is_active": w.is_active,
            "filters": w.filters,
            "fail_count": w.fail_count,
            "last_triggered": w.last_triggered.isoformat() if w.last_triggered else None,
        }
        for w in webhooks
    ]


@app.post("/webhooks")
async def create_webhook(
    webhook_data: dict,
    session: AsyncSession = Depends(get_db),
):
    """Create a new webhook."""
    from app.models import Webhook
    
    webhook = Webhook(
        url=webhook_data["url"],
        name=webhook_data.get("name"),
        secret=webhook_data.get("secret"),
        filters=webhook_data.get("filters"),
    )
    
    session.add(webhook)
    await session.commit()
    
    return {"id": str(webhook.id), "status": "created"}


@app.delete("/webhooks/{webhook_id}")
async def delete_webhook(
    webhook_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Delete a webhook."""
    from app.models import Webhook
    
    webhook = await session.get(Webhook, webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    await session.delete(webhook)
    await session.commit()
    
    return {"status": "deleted"}


# =============================================================================
# Proxy Management Endpoints
# =============================================================================

@app.get("/proxies")
async def get_proxy_stats():
    """Get proxy statistics."""
    manager = get_proxy_manager()
    return manager.get_stats()


@app.post("/proxies/health-check")
async def run_proxy_health_check():
    """Run health check on all proxies."""
    manager = get_proxy_manager()
    results = await manager.health_check()
    return results


# =============================================================================
# Retry Queue Endpoints
# =============================================================================

@app.get("/retry-queue")
async def get_retry_queue_stats():
    """Get retry queue statistics."""
    queue = get_retry_queue()
    return queue.get_stats()


# =============================================================================
# Search Endpoints
# =============================================================================

@app.get("/search")
async def search_offers(
    q: str = Query(..., min_length=2, description="Search query"),
    city: Optional[str] = Query(default=None),
    min_price: Optional[float] = Query(default=None),
    max_price: Optional[float] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
):
    """
    Full-text search for offers.
    
    Searches in titles, cities, and regions.
    """
    search_service = get_search_service()
    
    if city or min_price or max_price:
        offers = await search_service.search_with_filters(
            session, q, city, min_price, max_price, limit=limit
        )
    else:
        offers = await search_service.search(session, q, limit=limit)
    
    return {
        "query": q,
        "count": len(offers),
        "offers": offers,
    }


# =============================================================================
# Comparison Endpoints
# =============================================================================

@app.post("/compare")
async def compare_offers(
    offer_ids: List[UUID],
    session: AsyncSession = Depends(get_db),
):
    """
    Compare multiple offers side by side.
    
    Returns analysis of which offer is best in each category.
    """
    if len(offer_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 offers required")
    
    if len(offer_ids) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 offers can be compared")
    
    # Get offers
    offers = []
    for offer_id in offer_ids:
        offer = await session.get(Offer, offer_id)
        if offer:
            offers.append(offer)
    
    if len(offers) < 2:
        raise HTTPException(status_code=404, detail="Not enough valid offers found")
    
    comparator = get_offer_comparator()
    result = comparator.compare_offers(offers)
    
    return {
        "comparison": result,
        "report": comparator.generate_comparison_report(offers),
    }


# =============================================================================
# Alert Rules Endpoints
# =============================================================================

@app.get("/alert-rules")
async def list_alert_rules(
    user_id: str = Query(default="default"),
    session: AsyncSession = Depends(get_db),
):
    """List alert rules for a user."""
    from app.models import AlertRule
    
    result = await session.execute(
        select(AlertRule)
        .where(AlertRule.user_id == user_id)
        .order_by(AlertRule.created_at.desc())
    )
    
    rules = result.scalars().all()
    
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "is_active": r.is_active,
            "conditions": r.conditions,
            "channels": r.channels,
            "trigger_count": r.trigger_count,
            "last_triggered": r.last_triggered.isoformat() if r.last_triggered else None,
        }
        for r in rules
    ]


@app.post("/alert-rules")
async def create_alert_rule(
    rule_data: dict,
    user_id: str = Query(default="default"),
    session: AsyncSession = Depends(get_db),
):
    """Create a new alert rule."""
    from app.models import AlertRule
    
    rule = AlertRule(
        user_id=user_id,
        name=rule_data["name"],
        conditions=rule_data["conditions"],
        channels=rule_data.get("channels", ["whatsapp"]),
        cooldown_minutes=rule_data.get("cooldown_minutes", 60),
    )
    
    session.add(rule)
    await session.commit()
    
    return {"id": str(rule.id), "status": "created"}


@app.delete("/alert-rules/{rule_id}")
async def delete_alert_rule(
    rule_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Delete an alert rule."""
    from app.models import AlertRule
    
    rule = await session.get(AlertRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    await session.delete(rule)
    await session.commit()
    
    return {"status": "deleted"}


# =============================================================================
# Offer Notes & Tags Endpoints
# =============================================================================

@app.get("/offers/{offer_id}/notes")
async def get_offer_notes(
    offer_id: UUID,
    user_id: str = Query(default="default"),
    session: AsyncSession = Depends(get_db),
):
    """Get notes for an offer."""
    from app.models import OfferNote
    
    result = await session.execute(
        select(OfferNote)
        .where(OfferNote.offer_id == offer_id)
        .where(OfferNote.user_id == user_id)
        .order_by(OfferNote.created_at.desc())
    )
    
    notes = result.scalars().all()
    
    return [
        {
            "id": str(n.id),
            "note": n.note,
            "created_at": n.created_at.isoformat(),
            "updated_at": n.updated_at.isoformat(),
        }
        for n in notes
    ]


@app.post("/offers/{offer_id}/notes")
async def add_offer_note(
    offer_id: UUID,
    note_data: dict,
    user_id: str = Query(default="default"),
    session: AsyncSession = Depends(get_db),
):
    """Add a note to an offer."""
    from app.models import OfferNote
    
    note = OfferNote(
        offer_id=offer_id,
        user_id=user_id,
        note=note_data["note"],
    )
    
    session.add(note)
    await session.commit()
    
    return {"id": str(note.id), "status": "created"}


@app.get("/offers/{offer_id}/tags")
async def get_offer_tags(
    offer_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Get tags for an offer."""
    from app.models import OfferTag
    
    result = await session.execute(
        select(OfferTag)
        .where(OfferTag.offer_id == offer_id)
    )
    
    tags = result.scalars().all()
    
    return [t.tag for t in tags]


@app.post("/offers/{offer_id}/tags")
async def add_offer_tag(
    offer_id: UUID,
    tag_data: dict,
    user_id: str = Query(default="default"),
    session: AsyncSession = Depends(get_db),
):
    """Add a tag to an offer."""
    from app.models import OfferTag
    
    # Check if tag already exists
    existing = await session.scalar(
        select(OfferTag)
        .where(OfferTag.offer_id == offer_id)
        .where(OfferTag.tag == tag_data["tag"])
    )
    
    if existing:
        raise HTTPException(status_code=400, detail="Tag already exists")
    
    tag = OfferTag(
        offer_id=offer_id,
        tag=tag_data["tag"],
        created_by=user_id,
    )
    
    session.add(tag)
    await session.commit()
    
    return {"status": "created"}


@app.delete("/offers/{offer_id}/tags/{tag}")
async def remove_offer_tag(
    offer_id: UUID,
    tag: str,
    session: AsyncSession = Depends(get_db),
):
    """Remove a tag from an offer."""
    from app.models import OfferTag
    
    tag_obj = await session.scalar(
        select(OfferTag)
        .where(OfferTag.offer_id == offer_id)
        .where(OfferTag.tag == tag)
    )
    
    if not tag_obj:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    await session.delete(tag_obj)
    await session.commit()
    
    return {"status": "deleted"}


# =============================================================================
# Favorites Endpoints
# =============================================================================

@app.get("/favorites")
async def get_favorites(
    user_id: str = Query(default="default"),
    session: AsyncSession = Depends(get_db),
):
    """Get user's favorite offers."""
    from app.models import UserFavorite, Offer
    
    result = await session.execute(
        select(Offer)
        .join(UserFavorite, UserFavorite.offer_id == Offer.id)
        .where(UserFavorite.user_id == user_id)
        .order_by(UserFavorite.created_at.desc())
    )
    
    offers = result.scalars().all()
    
    return offers


@app.post("/favorites/{offer_id}")
async def add_favorite(
    offer_id: UUID,
    user_id: str = Query(default="default"),
    session: AsyncSession = Depends(get_db),
):
    """Add offer to favorites."""
    from app.models import UserFavorite
    
    # Check if already favorited
    existing = await session.scalar(
        select(UserFavorite)
        .where(UserFavorite.offer_id == offer_id)
        .where(UserFavorite.user_id == user_id)
    )
    
    if existing:
        raise HTTPException(status_code=400, detail="Already in favorites")
    
    favorite = UserFavorite(
        offer_id=offer_id,
        user_id=user_id,
    )
    
    session.add(favorite)
    await session.commit()
    
    return {"status": "added"}


@app.delete("/favorites/{offer_id}")
async def remove_favorite(
    offer_id: UUID,
    user_id: str = Query(default="default"),
    session: AsyncSession = Depends(get_db),
):
    """Remove offer from favorites."""
    from app.models import UserFavorite
    
    favorite = await session.scalar(
        select(UserFavorite)
        .where(UserFavorite.offer_id == offer_id)
        .where(UserFavorite.user_id == user_id)
    )
    
    if not favorite:
        raise HTTPException(status_code=404, detail="Not in favorites")
    
    await session.delete(favorite)
    await session.commit()
    
    return {"status": "removed"}


# =============================================================================
# Price Prediction Endpoints
# =============================================================================

@app.get("/predictions/model-info")
async def get_prediction_model_info():
    """Get price prediction model information."""
    service = get_price_prediction_service()
    return service.get_model_info()


@app.post("/predictions/train")
async def train_prediction_model(session: AsyncSession = Depends(get_db)):
    """Manually trigger model training."""
    service = get_price_prediction_service()
    
    success = await service.model.train(session)
    
    if success:
        # Save model
        import os
        os.makedirs(os.path.dirname(service.model_path), exist_ok=True)
        service.model.save_model(service.model_path)
        
        return {
            "status": "trained",
            "metrics": service.model.metrics
        }
    else:
        raise HTTPException(status_code=400, detail="Training failed or not enough data")


@app.get("/offers/{offer_id}/prediction")
async def predict_offer_price(
    offer_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Get price prediction for a specific offer."""
    offer = await session.get(Offer, offer_id)
    
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    
    # Initialize service
    service = get_price_prediction_service()
    await service.initialize(session)
    
    # Convert to normalized
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
    
    prediction = await service.predict_offer(normalized)
    
    if not prediction:
        raise HTTPException(status_code=503, detail="Prediction service not available")
    
    return {
        "offer_id": str(offer_id),
        "actual_price": float(offer.price) if offer.price else None,
        "prediction": {
            "predicted_price": prediction.predicted_price,
            "confidence": prediction.confidence_score,
            "price_range": {
                "low": prediction.price_range_low,
                "high": prediction.price_range_high,
            },
            "deal_rating": prediction.deal_rating,
            "deal_score": prediction.deal_score,
            "factors": prediction.factors,
        }
    }


@app.get("/market-trends")
async def get_market_trends(
    city: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_db),
):
    """Get market trend analysis."""
    service = get_price_prediction_service()
    
    trends = await service.analyze_market(session, city)
    
    return {
        "city": city,
        "trend_direction": trends.trend_direction,
        "trend_strength": trends.trend_strength,
        "avg_price_change_percent": trends.avg_price_change_percent,
        "forecast_next_month": trends.forecast_next_month,
        "confidence": trends.confidence,
    }


@app.get("/good-deals")
async def find_good_deals(
    min_score: float = Query(default=30, ge=0, le=100),
    limit: int = Query(default=20, ge=1, le=50),
    session: AsyncSession = Depends(get_db),
):
    """
    Find underpriced offers (good deals).
    
    Uses ML model to predict expected price and compare with actual price.
    """
    service = get_price_prediction_service()
    await service.initialize(session)
    
    deals = await service.find_deals(session, min_score)
    
    return {
        "count": len(deals),
        "min_score": min_score,
        "deals": deals,
    }


# =============================================================================
# Competitor Monitoring Endpoints
# =============================================================================

@app.get("/competitors/analysis")
async def get_competitor_market_analysis(
    city: str = Query(..., description="City to analyze"),
    district: Optional[str] = Query(default=None, description="District (optional)"),
    property_type: str = Query(default="apartment", description="Property type"),
    organization_id: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_db),
):
    """
    Get market analysis comparing our listings with competitors.
    
    Returns statistics, price comparisons, and trends.
    """
    from app.services.competitor_monitoring import CompetitorMonitoringService
    
    service = CompetitorMonitoringService(session)
    analysis = await service.get_market_analysis(
        city=city,
        district=district,
        property_type=property_type,
        organization_id=organization_id
    )
    
    return analysis.to_dict()


@app.get("/competitors/alerts")
async def get_competitor_price_alerts(
    organization_id: str = Query(...),
    days: int = Query(default=7, ge=1, le=30),
    min_change_percent: float = Query(default=5.0, ge=1.0, le=50.0),
    session: AsyncSession = Depends(get_db),
):
    """
    Get alerts about competitor price changes.
    
    Shows listings where competitors changed prices significantly.
    """
    from app.services.competitor_monitoring import CompetitorMonitoringService
    
    service = CompetitorMonitoringService(session)
    alerts = await service.get_price_alerts(
        organization_id=organization_id,
        days=days,
        min_change_percent=min_change_percent
    )
    
    return {
        "alerts": alerts,
        "total": len(alerts),
        "period_days": days,
        "min_change_percent": min_change_percent,
    }


@app.get("/competitors/compare/{listing_id}")
async def compare_with_competitors(
    listing_id: UUID,
    radius_km: float = Query(default=1.0, ge=0.1, le=10.0),
    session: AsyncSession = Depends(get_db),
):
    """
    Compare our listing with similar competitor listings.
    
    Returns price comparison and recommendations.
    """
    from app.services.competitor_monitoring import CompetitorMonitoringService
    
    service = CompetitorMonitoringService(session)
    comparison = await service.compare_with_our_listing(
        our_listing_id=listing_id,
        radius_km=radius_km
    )
    
    return comparison


@app.get("/competitors/activity-report")
async def get_competitor_activity_report(
    city: str = Query(...),
    days: int = Query(default=30, ge=7, le=90),
    session: AsyncSession = Depends(get_db),
):
    """
    Get competitor activity report for a city.
    
    Shows new listings, price changes, and sold properties.
    """
    from app.services.competitor_monitoring import CompetitorMonitoringService
    
    service = CompetitorMonitoringService(session)
    report = await service.get_competitor_activity_report(
        city=city,
        days=days
    )
    
    return report


# =============================================================================
# Task Management Endpoints
# =============================================================================

@app.get("/tasks")
async def list_tasks(
    user_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None, regex="^(pending|in_progress|completed|cancelled)$"),
    priority: Optional[str] = Query(default=None, regex="^(low|medium|high|urgent)$"),
    related_to: Optional[str] = Query(default=None, description="Filter by related entity (e.g., 'listing:123', 'client:456')"),
    session: AsyncSession = Depends(get_db),
):
    """
    List tasks for agents.
    
    Filter by user, status, priority, or related entity.
    """
    from app.services.task_management import TaskManagementService
    
    service = TaskManagementService(session)
    tasks = await service.list_tasks(
        user_id=user_id,
        status=status,
        priority=priority,
        related_to=related_to
    )
    
    return {
        "tasks": [task.to_dict() for task in tasks],
        "total": len(tasks),
    }


@app.post("/tasks")
async def create_task(
    task_data: dict,
    session: AsyncSession = Depends(get_db),
):
    """
    Create a new task.
    
    Required fields: title, assigned_to
    Optional: description, due_date, priority, related_type, related_id
    """
    from app.services.task_management import TaskManagementService
    
    service = TaskManagementService(session)
    
    try:
        task = await service.create_task(
            title=task_data["title"],
            assigned_to=task_data["assigned_to"],
            description=task_data.get("description"),
            created_by=task_data.get("created_by", "system"),
            due_date=task_data.get("due_date"),
            priority=task_data.get("priority", "medium"),
            related_type=task_data.get("related_type"),
            related_id=task_data.get("related_id"),
        )
        
        return {"id": task.id, "status": "created", "task": task.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/tasks/{task_id}")
async def get_task(
    task_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Get a single task by ID."""
    from app.services.task_management import TaskManagementService
    
    service = TaskManagementService(session)
    task = await service.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return task.to_dict()


@app.patch("/tasks/{task_id}")
async def update_task(
    task_id: UUID,
    update_data: dict,
    session: AsyncSession = Depends(get_db),
):
    """Update task status, priority, or other fields."""
    from app.services.task_management import TaskManagementService
    
    service = TaskManagementService(session)
    
    task = await service.update_task(
        task_id=task_id,
        **update_data
    )
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {"status": "updated", "task": task.to_dict()}


@app.post("/tasks/{task_id}/complete")
async def complete_task(
    task_id: UUID,
    completion_data: dict = {},
    session: AsyncSession = Depends(get_db),
):
    """Mark a task as completed."""
    from app.services.task_management import TaskManagementService
    
    service = TaskManagementService(session)
    
    task = await service.complete_task(
        task_id=task_id,
        notes=completion_data.get("notes"),
        completed_by=completion_data.get("completed_by")
    )
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {"status": "completed", "task": task.to_dict()}


@app.delete("/tasks/{task_id}")
async def delete_task(
    task_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Delete a task."""
    from app.services.task_management import TaskManagementService
    
    service = TaskManagementService(session)
    success = await service.delete_task(task_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {"status": "deleted"}


@app.get("/tasks/dashboard/{user_id}")
async def get_task_dashboard(
    user_id: str,
    session: AsyncSession = Depends(get_db),
):
    """
    Get task dashboard for a user.
    
    Shows statistics: pending, overdue, due today, completed today.
    """
    from app.services.task_management import TaskManagementService
    
    service = TaskManagementService(session)
    dashboard = await service.get_user_dashboard(user_id)
    
    return dashboard


@app.get("/tasks/upcoming/{user_id}")
async def get_upcoming_tasks(
    user_id: str,
    days: int = Query(default=7, ge=1, le=30),
    session: AsyncSession = Depends(get_db),
):
    """Get upcoming tasks due in the next N days."""
    from app.services.task_management import TaskManagementService
    
    service = TaskManagementService(session)
    tasks = await service.get_upcoming_tasks(user_id, days)
    
    return {
        "tasks": [task.to_dict() for task in tasks],
        "period_days": days,
    }


# =============================================================================
# Google Maps Integration Endpoints
# =============================================================================

@app.get("/maps/geocode")
async def geocode_address(
    address: str = Query(..., description="Address to geocode"),
    city: Optional[str] = Query(default=None),
):
    """
    Geocode an address to coordinates.
    
    Converts a street address to latitude and longitude.
    """
    from app.services.google_maps import get_google_maps_service
    
    service = get_google_maps_service()
    result = await service.geocode_address(address, city)
    
    if not result:
        raise HTTPException(status_code=404, detail="Address not found")
    
    return result.to_dict()


@app.get("/maps/reverse-geocode")
async def reverse_geocode(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
):
    """
    Reverse geocode coordinates to address.
    
    Converts latitude and longitude to a street address.
    """
    from app.services.google_maps import get_google_maps_service, GeoLocation
    
    service = get_google_maps_service()
    result = await service.reverse_geocode(lat, lng)
    
    if not result:
        raise HTTPException(status_code=404, detail="Location not found")
    
    return result.to_dict()


@app.get("/maps/distance")
async def calculate_distance(
    origin_lat: float = Query(..., description="Origin latitude"),
    origin_lng: float = Query(..., description="Origin longitude"),
    dest_lat: float = Query(..., description="Destination latitude"),
    dest_lng: float = Query(..., description="Destination longitude"),
    mode: str = Query(default="driving", regex="^(driving|walking|bicycling|transit)$"),
):
    """
    Calculate distance and travel time between two points.
    
    Returns distance in meters/km and duration in seconds/minutes.
    """
    from app.services.google_maps import get_google_maps_service, GeoLocation
    
    service = get_google_maps_service()
    
    origin = GeoLocation(lat=origin_lat, lng=origin_lng)
    destination = GeoLocation(lat=dest_lat, lng=dest_lng)
    
    result = await service.calculate_distance(origin, destination, mode)
    
    if not result:
        raise HTTPException(status_code=500, detail="Could not calculate distance")
    
    return result.to_dict()


@app.post("/maps/optimize-route")
async def optimize_route(route_data: dict):
    """
    Optimize a route through multiple waypoints.
    
    Solves the traveling salesman problem for the given waypoints.
    """
    from app.services.google_maps import (
        get_google_maps_service, 
        GeoLocation, 
        RouteWaypoint
    )
    
    service = get_google_maps_service()
    
    # Parse waypoints
    waypoints_data = route_data.get("waypoints", [])
    if len(waypoints_data) < 2:
        raise HTTPException(status_code=400, detail="At least 2 waypoints required")
    
    waypoints = []
    for wp in waypoints_data:
        waypoints.append(RouteWaypoint(
            id=wp.get("id", str(uuid.uuid4())),
            address=wp.get("address", ""),
            location=GeoLocation(
                lat=wp["location"]["lat"],
                lng=wp["location"]["lng"]
            ),
            duration_minutes=wp.get("duration_minutes", 30),
        ))
    
    # Parse optional start/end
    start_location = None
    end_location = None
    
    if "start_location" in route_data:
        start = route_data["start_location"]
        start_location = GeoLocation(lat=start["lat"], lng=start["lng"])
    
    if "end_location" in route_data:
        end = route_data["end_location"]
        end_location = GeoLocation(lat=end["lat"], lng=end["lng"])
    
    mode = route_data.get("mode", "driving")
    
    result = await service.optimize_route(
        waypoints=waypoints,
        start_location=start_location,
        end_location=end_location,
        mode=mode,
    )
    
    return result.to_dict()


@app.get("/maps/autocomplete")
async def autocomplete_address(
    input_text: str = Query(..., min_length=2, description="Input text for autocomplete"),
    city: Optional[str] = Query(default=None),
):
    """
    Autocomplete address suggestions.
    
    Returns address suggestions as the user types.
    """
    from app.services.google_maps import get_google_maps_service
    
    service = get_google_maps_service()
    suggestions = await service.autocomplete_address(input_text, city)
    
    return {
        "input": input_text,
        "suggestions": [s.to_dict() for s in suggestions],
        "count": len(suggestions),
    }


@app.get("/maps/nearby-listings")
async def find_nearby_listings(
    lat: float = Query(..., description="Center latitude"),
    lng: float = Query(..., description="Center longitude"),
    radius_km: float = Query(default=5.0, ge=0.1, le=50.0),
    session: AsyncSession = Depends(get_db),
):
    """
    Find listings within a radius of a location.
    
    Returns listings sorted by distance from the center point.
    """
    from app.services.google_maps import get_google_maps_service, GeoLocation
    
    service = get_google_maps_service()
    center = GeoLocation(lat=lat, lng=lng)
    
    # Get listings with coordinates from database
    result = await session.execute(
        select(Offer).where(
            Offer.lat.isnot(None),
            Offer.lng.isnot(None),
        )
    )
    offers = result.scalars().all()
    
    # Convert to dict format
    listings = []
    for offer in offers:
        listings.append({
            'id': str(offer.id),
            'title': offer.title,
            'price': float(offer.price) if offer.price else None,
            'city': offer.city,
            'lat': offer.lat,
            'lng': offer.lng,
            'url': offer.url,
        })
    
    nearby = await service.find_nearby_listings(center, listings, radius_km)
    
    return {
        "center": {"lat": lat, "lng": lng},
        "radius_km": radius_km,
        "listings": nearby,
        "total": len(nearby),
    }


@app.get("/maps/static")
async def get_static_map(
    lat: float = Query(..., description="Center latitude"),
    lng: float = Query(..., description="Center longitude"),
    zoom: int = Query(default=15, ge=1, le=20),
    size: str = Query(default="600x400", regex="^\d+x\d+$"),
):
    """
    Get URL for a static map image.
    
    Returns a URL that can be used to display a map image.
    """
    from app.services.google_maps import get_google_maps_service, GeoLocation
    
    service = get_google_maps_service()
    location = GeoLocation(lat=lat, lng=lng)
    
    url = await service.get_static_map_url(location, zoom, size)
    
    return {
        "map_url": url,
        "center": {"lat": lat, "lng": lng},
        "zoom": zoom,
        "size": size,
    }


# =============================================================================
# WebSocket Endpoint
# =============================================================================

@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: Optional[str] = Query(default=None),
    organization_id: Optional[str] = Query(default=None),
):
    """
    WebSocket endpoint for real-time notifications.
    
    Connect to receive instant notifications about:
    - New offers
    - Price changes
    - Task assignments
    - Viewing reminders
    - Competitor alerts
    
    Message format:
    {
        "event": "subscribe",
        "payload": {"channel": "offers"}
    }
    """
    from app.services.websocket_notifications import (
        get_websocket_manager,
        websocket_endpoint as ws_handler,
    )
    
    await ws_handler(websocket, user_id, organization_id)


@app.get("/ws/stats")
async def get_websocket_stats():
    """Get WebSocket connection statistics."""
    from app.services.websocket_notifications import get_websocket_manager
    
    manager = get_websocket_manager()
    return manager.get_stats()


# =============================================================================
# Excel Import/Export Endpoints
# =============================================================================

@app.get("/excel/template")
async def download_excel_template():
    """
    Download Excel template for importing offers.
    
    Returns a template file with example data and instructions.
    """
    from fastapi.responses import Response
    from app.services.excel_operations import ExcelOperationsService
    
    service = ExcelOperationsService(None)
    template_bytes = await service.export_template()
    
    return Response(
        content=template_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=import_template.xlsx"}
    )


@app.post("/excel/validate")
async def validate_excel_import(
    file: bytes,
):
    """
    Validate Excel file before importing.
    
    Checks for required columns, data types, and format errors.
    Returns validation results without importing.
    """
    from app.services.excel_operations import ExcelOperationsService
    
    service = ExcelOperationsService(None)
    result = await service.validate_import(file)
    
    return result.to_dict()


@app.post("/excel/import")
async def import_excel_offers(
    file: bytes,
    organization_id: Optional[str] = Query(default=None),
    created_by: Optional[str] = Query(default=None),
    skip_validation: bool = Query(default=False),
):
    """
    Import offers from Excel file.
    
    Required columns: title, property_type, transaction_type, price, area_sqm, city
    """
    from app.services.excel_operations import ExcelOperationsService
    
    service = ExcelOperationsService(None)
    result = await service.import_offers(
        file_content=file,
        organization_id=organization_id,
        created_by=created_by,
        skip_validation=skip_validation,
    )
    
    return result.to_dict()


@app.post("/excel/export")
async def export_offers_to_excel(
    export_config: dict,
    session: AsyncSession = Depends(get_db),
):
    """
    Export offers to Excel.
    
    Configure columns, filters, and formatting in the request body.
    """
    from fastapi.responses import Response
    from app.services.excel_operations import (
        ExcelOperationsService, 
        ExportConfig,
    )
    
    service = ExcelOperationsService(session)
    
    config = ExportConfig(
        columns=export_config.get('columns', ['title', 'price', 'city', 'area_sqm']),
        include_headers=export_config.get('include_headers', True),
        filters=export_config.get('filters', {}),
    )
    
    # Query offers from database
    result = await session.execute(select(Offer))
    offers = result.scalars().all()
    
    # Convert to dict format
    offers_data = []
    for offer in offers:
        offers_data.append({
            'id': str(offer.id),
            'title': offer.title,
            'price': float(offer.price) if offer.price else None,
            'city': offer.city,
            'area_sqm': offer.area_m2,
            'rooms': offer.rooms,
            'url': offer.url,
        })
    
    excel_bytes = await service.export_offers(offers_data, config)
    
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=offers_export_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"}
    )


# =============================================================================
# Reviews & Ratings Endpoints
# =============================================================================

@app.post("/reviews")
async def create_review(
    review_data: dict,
    session: AsyncSession = Depends(get_db),
):
    """
    Create a new review/rating.
    
    Types: agent, listing, office, viewing
    """
    from app.services.reviews_ratings import (
        ReviewsRatingsService,
        ReviewType,
    )
    
    service = ReviewsRatingsService(session)
    
    review = await service.create_review(
        review_type=ReviewType(review_data['review_type']),
        target_id=review_data['target_id'],
        target_name=review_data['target_name'],
        author_id=review_data['author_id'],
        author_name=review_data['author_name'],
        rating=review_data['rating'],
        content=review_data['content'],
        title=review_data.get('title'),
        sub_ratings=review_data.get('sub_ratings'),
        author_email=review_data.get('author_email'),
        is_verified=review_data.get('is_verified', False),
    )
    
    return {"id": review.id, "status": "created", "review": review.to_dict()}


@app.get("/reviews")
async def get_reviews(
    review_type: Optional[str] = Query(default=None),
    target_id: Optional[str] = Query(default=None),
    status: str = Query(default="approved"),
    verified_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
):
    """Get reviews with filters."""
    from app.services.reviews_ratings import (
        ReviewsRatingsService,
        ReviewType,
        ReviewStatus,
    )
    
    service = ReviewsRatingsService(session)
    
    reviews = await service.get_reviews(
        review_type=ReviewType(review_type) if review_type else None,
        target_id=target_id,
        status=ReviewStatus(status),
        verified_only=verified_only,
        limit=limit,
    )
    
    return {
        "reviews": [r.to_dict() for r in reviews],
        "total": len(reviews),
    }


@app.get("/reviews/summary/{target_id}")
async def get_rating_summary(
    target_id: str,
    review_type: str,
    session: AsyncSession = Depends(get_db),
):
    """Get rating summary for a target (agent/listing/office)."""
    from app.services.reviews_ratings import ReviewsRatingsService, ReviewType
    
    service = ReviewsRatingsService(session)
    summary = await service.get_rating_summary(target_id, ReviewType(review_type))
    
    if not summary:
        raise HTTPException(status_code=404, detail="No reviews found")
    
    return summary.to_dict()


@app.get("/reviews/leaderboard")
async def get_agent_leaderboard(
    office_id: Optional[str] = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_db),
):
    """Get top-rated agents leaderboard."""
    from app.services.reviews_ratings import ReviewsRatingsService
    
    service = ReviewsRatingsService(session)
    leaderboard = await service.get_agent_leaderboard(office_id, limit=limit)
    
    return {"leaderboard": leaderboard}


@app.post("/reviews/{review_id}/respond")
async def respond_to_review(
    review_id: str,
    response_data: dict,
    session: AsyncSession = Depends(get_db),
):
    """Respond to a review."""
    from app.services.reviews_ratings import ReviewsRatingsService
    
    service = ReviewsRatingsService(session)
    review = await service.respond_to_review(
        review_id=review_id,
        response=response_data['response'],
        responder_id=response_data['responder_id'],
    )
    
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    return {"status": "responded", "review": review.to_dict()}


# =============================================================================
# Social Ads Endpoints
# =============================================================================

@app.post("/ads/campaigns")
async def create_ad_campaign(
    campaign_data: dict,
    session: AsyncSession = Depends(get_db),
):
    """
    Create a new social media ad campaign.
    
    Templates: standard_sale, premium_listing, quick_sale, rental
    """
    from app.services.social_ads import SocialAdsService
    
    service = SocialAdsService(session)
    
    campaign = await service.create_campaign(
        listing_id=campaign_data['listing_id'],
        listing_data=campaign_data['listing_data'],
        template_id=campaign_data['template_id'],
        created_by=campaign_data['created_by'],
        custom_budget=campaign_data.get('custom_budget'),
        custom_targeting=campaign_data.get('custom_targeting'),
    )
    
    return {"id": campaign.id, "status": "created", "campaign": campaign.to_dict()}


@app.get("/ads/campaigns")
async def get_ad_campaigns(
    listing_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
):
    """Get ad campaigns with filters."""
    from app.services.social_ads import SocialAdsService, CampaignStatus
    
    service = SocialAdsService(session)
    
    campaigns = await service.get_campaigns(
        listing_id=listing_id,
        status=CampaignStatus(status) if status else None,
        limit=limit,
    )
    
    return {
        "campaigns": [c.to_dict() for c in campaigns],
        "total": len(campaigns),
    }


@app.post("/ads/campaigns/{campaign_id}/publish")
async def publish_ad_campaign(
    campaign_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Publish campaign to Facebook/Instagram."""
    from app.services.social_ads import SocialAdsService
    
    service = SocialAdsService(session)
    campaign = await service.publish_campaign(campaign_id)
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    return {"status": "published", "campaign": campaign.to_dict()}


@app.get("/ads/templates")
async def get_ad_templates():
    """Get available ad templates."""
    from app.services.social_ads import SocialAdsService
    
    service = SocialAdsService(None)
    templates = await service.get_templates()
    
    return {"templates": templates}


@app.post("/ads/recommendations")
async def get_ad_recommendations(
    listing: dict,
):
    """Get ad campaign recommendations for a listing."""
    from app.services.social_ads import SocialAdsService
    
    service = SocialAdsService(None)
    recommendations = await service.get_recommendations(listing)
    
    return recommendations


# =============================================================================
# AI Chatbot Endpoints
# =============================================================================

@app.post("/chatbot/conversations")
async def start_chatbot_conversation(
    user_data: dict = {},
):
    """Start a new chatbot conversation."""
    from app.services.chatbot_ai import get_chatbot_service
    
    service = get_chatbot_service(None)
    conversation = await service.start_conversation(
        user_id=user_data.get('user_id'),
        user_name=user_data.get('user_name'),
        user_phone=user_data.get('user_phone'),
        user_email=user_data.get('user_email'),
        channel=user_data.get('channel', 'website'),
    )
    
    return conversation.to_dict()


@app.post("/chatbot/conversations/{conversation_id}/message")
async def send_chatbot_message(
    conversation_id: str,
    message_data: dict,
):
    """Send a message to the chatbot."""
    from app.services.chatbot_ai import get_chatbot_service
    
    service = get_chatbot_service(None)
    
    response = await service.process_message(
        conversation_id=conversation_id,
        message_text=message_data['message'],
    )
    
    return {"response": response.to_dict()}


@app.get("/chatbot/conversations/{conversation_id}")
async def get_chatbot_conversation(
    conversation_id: str,
):
    """Get conversation details."""
    from app.services.chatbot_ai import get_chatbot_service
    
    service = get_chatbot_service(None)
    conversation = await service.get_conversation(conversation_id)
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return conversation.to_dict()


@app.get("/chatbot/stats")
async def get_chatbot_stats():
    """Get chatbot statistics."""
    from app.services.chatbot_ai import get_chatbot_service
    
    service = get_chatbot_service(None)
    stats = await service.get_stats()
    
    return stats


@app.get("/chatbot/leads")
async def get_qualified_leads():
    """Get qualified leads from chatbot conversations."""
    from app.services.chatbot_ai import get_chatbot_service
    
    service = get_chatbot_service(None)
    leads = await service.get_qualified_leads()
    
    return {
        "leads": [l.to_dict() for l in leads],
        "total": len(leads),
    }


# =============================================================================
# Recommendations Endpoints
# =============================================================================

@app.get("/recommendations/similar/{listing_id}")
async def get_similar_listings(
    listing_id: str,
    limit: int = Query(default=5, ge=1, le=20),
    session: AsyncSession = Depends(get_db),
):
    """Get similar listings to the given one."""
    from app.services.recommendations import get_recommendations_service
    
    service = get_recommendations_service(session)
    recommendations = await service.get_similar_listings(listing_id, limit)
    
    return {
        "recommendations": [r.to_dict() for r in recommendations],
        "listing_id": listing_id,
    }


@app.get("/recommendations/for-user/{user_id}")
async def get_recommendations_for_user(
    user_id: str,
    limit: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_db),
):
    """Get personalized recommendations for a user."""
    from app.services.recommendations import get_recommendations_service
    
    service = get_recommendations_service(session)
    recommendations = await service.get_recommendations_for_user(user_id, limit)
    
    return {
        "recommendations": [r.to_dict() for r in recommendations],
        "user_id": user_id,
    }


@app.get("/recommendations/trending")
async def get_trending_listings(
    city: Optional[str] = Query(default=None),
    days: int = Query(default=7, ge=1, le=30),
    limit: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_db),
):
    """Get trending/popular listings."""
    from app.services.recommendations import get_recommendations_service
    
    service = get_recommendations_service(session)
    trending = await service.get_trending_listings(city, days, limit)
    
    return {
        "trending": [t.to_dict() for t in trending],
        "city": city,
        "period_days": days,
    }


@app.get("/recommendations/also-viewed/{listing_id}")
async def get_customers_also_viewed(
    listing_id: str,
    limit: int = Query(default=5, ge=1, le=20),
    session: AsyncSession = Depends(get_db),
):
    """Get listings that other customers also viewed."""
    from app.services.recommendations import get_recommendations_service
    
    service = get_recommendations_service(session)
    also_viewed = await service.get_customers_also_viewed(listing_id, limit)
    
    return {
        "also_viewed": [a.to_dict() for a in also_viewed],
        "listing_id": listing_id,
    }


@app.post("/recommendations/track-view")
async def track_listing_view(
    track_data: dict,
    session: AsyncSession = Depends(get_db),
):
    """Track a listing view for recommendations."""
    from app.services.recommendations import get_recommendations_service
    
    service = get_recommendations_service(session)
    await service.track_listing_view(
        user_id=track_data['user_id'],
        listing_id=track_data['listing_id'],
        duration_seconds=track_data.get('duration_seconds', 0),
    )
    
    return {"status": "tracked"}


# =============================================================================
# Partners API Endpoints
# =============================================================================

@app.post("/partners")
async def register_partner(
    partner_data: dict,
    session: AsyncSession = Depends(get_db),
):
    """Register a new partner (external agency/developer)."""
    from app.services.partners_api import PartnersAPIService, PartnerType
    
    service = PartnersAPIService(session)
    
    partner = await service.register_partner(
        name=partner_data['name'],
        partner_type=PartnerType(partner_data['partner_type']),
        contact_name=partner_data['contact_name'],
        contact_email=partner_data['contact_email'],
        contact_phone=partner_data['contact_phone'],
        webhook_url=partner_data.get('webhook_url'),
        access_level=partner_data.get('access_level', 'read_only'),
        commission_share=partner_data.get('commission_share', 50.0),
    )
    
    return {
        "id": partner.id,
        "api_key": partner.api_key,
        "api_secret": partner.api_secret,
        "status": "pending_activation",
        "partner": partner.to_dict(),
    }


@app.get("/partners")
async def list_partners(
    status: Optional[str] = Query(default=None),
    partner_type: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_db),
):
    """List partners with filters."""
    from app.services.partners_api import (
        PartnersAPIService,
        PartnerStatus,
        PartnerType,
    )
    
    service = PartnersAPIService(session)
    
    partners = await service.list_partners(
        status=PartnerStatus(status) if status else None,
        partner_type=PartnerType(partner_type) if partner_type else None,
    )
    
    return {
        "partners": [p.to_dict() for p in partners],
        "total": len(partners),
    }


@app.post("/partners/{partner_id}/activate")
async def activate_partner(
    partner_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Activate a partner."""
    from app.services.partners_api import PartnersAPIService
    
    service = PartnersAPIService(session)
    partner = await service.activate_partner(partner_id)
    
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    
    return {"status": "activated", "partner": partner.to_dict()}


@app.get("/partners/{partner_id}/stats")
async def get_partner_stats(
    partner_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Get partner statistics."""
    from app.services.partners_api import PartnersAPIService
    
    service = PartnersAPIService(session)
    stats = await service.get_partner_stats(partner_id)
    
    if not stats:
        raise HTTPException(status_code=404, detail="Partner not found")
    
    return stats


@app.post("/partners/{partner_id}/share-listing")
async def share_listing_with_partner(
    partner_id: str,
    share_data: dict,
    session: AsyncSession = Depends(get_db),
):
    """Share a listing with a partner."""
    from app.services.partners_api import PartnersAPIService
    
    service = PartnersAPIService(session)
    shared = await service.share_listing(partner_id, share_data['listing_id'])
    
    if not shared:
        raise HTTPException(status_code=404, detail="Partner not found or inactive")
    
    return {"status": "shared", "shared": shared.to_dict()}


# =============================================================================
# Loyalty Program Endpoints
# =============================================================================

@app.post("/loyalty/enroll")
async def enroll_loyalty_member(
    user_data: dict,
    session: AsyncSession = Depends(get_db),
):
    """Enroll a user in the loyalty program."""
    from app.services.loyalty_program import get_loyalty_service
    
    service = get_loyalty_service(session)
    member = await service.enroll_member(user_data['user_id'])
    
    return {"status": "enrolled", "member": member.to_dict()}


@app.get("/loyalty/member/{user_id}")
async def get_loyalty_member(
    user_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Get loyalty member details."""
    from app.services.loyalty_program import get_loyalty_service
    
    service = get_loyalty_service(session)
    member = await service.get_member(user_id)
    
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    
    return member.to_dict()


@app.post("/loyalty/award-points")
async def award_loyalty_points(
    award_data: dict,
    session: AsyncSession = Depends(get_db),
):
    """Award points to a member."""
    from app.services.loyalty_program import get_loyalty_service, PointsAction
    
    service = get_loyalty_service(session)
    
    member = await service.get_member(award_data['user_id'])
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    
    transaction = await service.award_points(
        member_id=member.id,
        action=PointsAction(award_data['action']),
        custom_points=award_data.get('custom_points'),
        metadata=award_data.get('metadata'),
    )
    
    return {"status": "awarded", "transaction": transaction.to_dict()}


@app.get("/loyalty/rewards")
async def get_available_rewards(
    user_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Get available rewards for a member."""
    from app.services.loyalty_program import get_loyalty_service
    
    service = get_loyalty_service(session)
    
    member = await service.get_member(user_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    
    rewards = await service.get_available_rewards(member.id)
    
    return {
        "rewards": [r.to_dict() for r in rewards],
        "member_points": member.available_points,
    }


@app.post("/loyalty/redeem")
async def redeem_loyalty_reward(
    redeem_data: dict,
    session: AsyncSession = Depends(get_db),
):
    """Redeem points for a reward."""
    from app.services.loyalty_program import get_loyalty_service
    
    service = get_loyalty_service(session)
    
    member = await service.get_member(redeem_data['user_id'])
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    
    redemption = await service.redeem_reward(
        member_id=member.id,
        reward_id=redeem_data['reward_id'],
    )
    
    if not redemption:
        raise HTTPException(status_code=400, detail="Cannot redeem reward")
    
    return {"status": "redeemed", "redemption": redemption.to_dict()}


@app.post("/loyalty/referral")
async def process_referral(
    referral_data: dict,
    session: AsyncSession = Depends(get_db),
):
    """Process a referral code."""
    from app.services.loyalty_program import get_loyalty_service
    
    service = get_loyalty_service(session)
    success = await service.process_referral(
        referral_code=referral_data['referral_code'],
        new_user_id=referral_data['new_user_id'],
    )
    
    return {"status": "processed" if success else "failed"}


@app.get("/loyalty/leaderboard")
async def get_loyalty_leaderboard(
    limit: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_db),
):
    """Get loyalty program leaderboard."""
    from app.services.loyalty_program import get_loyalty_service
    
    service = get_loyalty_service(session)
    leaderboard = await service.get_leaderboard(limit)
    
    return {"leaderboard": leaderboard}


@app.get("/loyalty/stats")
async def get_loyalty_stats(
    session: AsyncSession = Depends(get_db),
):
    """Get loyalty program statistics."""
    from app.services.loyalty_program import get_loyalty_service
    
    service = get_loyalty_service(session)
    stats = await service.get_stats()
    
    return stats


# =============================================================================
# Root Endpoint
# =============================================================================

@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Real Estate Monitor",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "panel": "/panel",
        "features": [
            "multi-channel-notifications",
            "price-history-tracking",
            "smart-filtering",
            "image-analysis",
            "prometheus-metrics",
            "webhook-integration",
            "geofencing",
            "cross-source-duplicate-detection",
            "auto-retry",
            "dynamic-config",
            "data-export",
            "competitor-monitoring",
            "task-management",
            "google-maps-integration",
            "websocket-notifications",
            "excel-import-export",
            "reviews-ratings",
            "social-ads",
            "ai-chatbot",
            "recommendations",
            "partners-api",
            "loyalty-program",
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
