"""
Connectors package for real estate sources.
"""
from app.connectors.base import (
    BaseConnector,
    ConnectorRegistry,
    FilterConfig,
    register_connector,
)

# Import all connectors to register them
from app.connectors.otodom import OtodomConnector
from app.connectors.olx import OlxConnector
from app.connectors.facebook import FacebookConnector
from app.connectors.popular_portals import (
    GratkaConnector,
    MorizonConnector,
    DomiportaConnector,
    NieruchomosciOnlineConnector,
    TabelaOfertConnector,
)

__all__ = [
    "BaseConnector",
    "ConnectorRegistry",
    "FilterConfig",
    "register_connector",
    "OtodomConnector",
    "OlxConnector",
    "FacebookConnector",
    "GratkaConnector",
    "MorizonConnector",
    "DomiportaConnector",
    "NieruchomosciOnlineConnector",
    "TabelaOfertConnector",
]
