"""
JSON structured logging configuration.
All logs output to stdout in JSON format for production environments.
"""
import logging
import sys
from typing import Any, Dict

from pythonjsonlogger import jsonlogger

from app.settings import settings


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields."""
    
    def add_fields(
        self,
        log_record: Dict[str, Any],
        record: logging.LogRecord,
        message_dict: Dict[str, Any]
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        
        # Add standard fields
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["source"] = {
            "file": record.pathname,
            "line": record.lineno,
            "function": record.funcName,
        }
        
        # Add timestamp in ISO format
        log_record["timestamp"] = self.formatTime(record)
        
        # Add app context
        log_record["app"] = {
            "name": settings.app_name,
            "env": settings.app_env,
        }
        
        # Move 'message' to 'msg' for consistency
        if "message" in log_record:
            log_record["msg"] = log_record.pop("message")


def setup_logging() -> logging.Logger:
    """Configure and return the root logger."""
    
    # Create logger
    logger = logging.getLogger("real_estate_monitor")
    logger.setLevel(getattr(logging, settings.log_level.upper()))
    
    # Clear existing handlers
    logger.handlers = []
    
    # Create stdout handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, settings.log_level.upper()))
    
    # JSON formatter for production
    if settings.is_production:
        formatter = CustomJsonFormatter(
            "%(timestamp)s %(level)s %(name)s %(message)s"
        )
    else:
        # Simple formatter for development
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("playwright").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.INFO)
    
    return logger


# Global logger instance
logger = setup_logging()


def get_logger(name: str) -> logging.Logger:
    """Get a child logger with the given name."""
    return logging.getLogger(f"real_estate_monitor.{name}")
