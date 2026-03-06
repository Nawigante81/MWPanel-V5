"""
Management commands for the real estate monitor.
Usage: python -m app.manage <command>
"""
import argparse
import asyncio
import sys

from app.connectors.base import ConnectorRegistry, FilterConfig
from app.db import get_sync_session
from app.logging_config import get_logger
from app.models import Source
from app.settings import settings
from app.tasks.scheduler import seed_sources
from app.tasks.scrape import scrape_source

logger = get_logger("manage")


def seed_sources_cmd():
    """Seed initial sources into the database."""
    logger.info("Seeding sources...")
    result = seed_sources.delay()
    print(f"Task dispatched: {result.id}")
    
    # Wait for result
    try:
        output = result.get(timeout=10)
        print(f"Result: {output}")
    except Exception as e:
        print(f"Task result timeout or error: {e}")


def run_once(source_name: str):
    """Run a single scrape for debugging."""
    logger.info(f"Running single scrape for: {source_name}")
    
    # Check if source exists
    connector = ConnectorRegistry.get(source_name)
    if not connector:
        print(f"Error: Unknown source '{source_name}'")
        print(f"Available sources: {', '.join(ConnectorRegistry.list_connectors())}")
        sys.exit(1)
    
    # Create filter
    filter_config = FilterConfig(
        region="pomorskie",
        transaction_type="sale",
    )
    
    # Dispatch task
    result = scrape_source.delay(source_name, filter_config.to_dict())
    print(f"Task dispatched: {result.id}")
    
    # Wait for result
    try:
        output = result.get(timeout=120)
        print(f"Result: {output}")
    except Exception as e:
        print(f"Task result timeout or error: {e}")


def list_sources():
    """List all configured sources."""
    print("Registered connectors:")
    for name in ConnectorRegistry.list_connectors():
        connector = ConnectorRegistry.get(name)
        print(f"  - {name} ({connector.fetch_mode})")
    
    print("\nDatabase sources:")
    with get_sync_session() as session:
        from sqlalchemy import select
        sources = session.execute(select(Source)).scalars().all()
        
        for source in sources:
            status = "enabled" if source.enabled else "disabled"
            print(f"  - {source.name} ({status}, interval={source.interval_seconds}s)")


def test_whatsapp():
    """Test WhatsApp configuration."""
    print("WhatsApp Configuration:")
    print(f"  Enabled: {settings.whatsapp_enabled}")
    print(f"  Phone Number ID: {settings.wa_phone_number_id}")
    print(f"  Recipient: {settings.wa_to}")
    print(f"  Token configured: {'Yes' if settings.wa_token else 'No'}")


def main():
    """Main entry point for management commands."""
    parser = argparse.ArgumentParser(
        description="Real Estate Monitor Management Commands"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # seed_sources command
    subparsers.add_parser("seed_sources", help="Seed initial sources")
    
    # run_once command
    run_once_parser = subparsers.add_parser("run_once", help="Run single scrape")
    run_once_parser.add_argument("--source", required=True, help="Source name")
    
    # list_sources command
    subparsers.add_parser("list_sources", help="List all sources")
    
    # test_whatsapp command
    subparsers.add_parser("test_whatsapp", help="Test WhatsApp configuration")
    
    args = parser.parse_args()
    
    if args.command == "seed_sources":
        seed_sources_cmd()
    elif args.command == "run_once":
        run_once(args.source)
    elif args.command == "list_sources":
        list_sources()
    elif args.command == "test_whatsapp":
        test_whatsapp()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
