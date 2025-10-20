"""
Reusable logging configuration for all microservices.
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional


class LoggingManager:
    """Class to manage logging configuration for microservices."""
    @staticmethod
    def setup_logging(
            service_name: str,
            log_file_path: Optional[str] = None,
            log_level: int = logging.INFO,
            enable_console: bool = True,
            enable_file: bool = True,
            max_bytes: int = 10 * 1024 * 1024,  # 10MB
            backup_count: int = 5
    ) -> logging.Logger:
        """
        Setup consistent logging configuration for any service.

        Args:
            service_name: Name of the service for logger identification
            log_file_path: Path to log file (None for no file logging)
            log_level: Logging level
            enable_console: Whether to log to console
            enable_file: Whether to log to file
            max_bytes: Max log file size before rotation
            backup_count: Number of backup files to keep

        Returns:
            Configured logger instance
        """
        # Clear existing handlers
        logging.getLogger().handlers.clear()

        # Create formatters
        detailed_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        simple_formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%H:%M:%S"
        )

        # Setup root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)

        # Console handler
        if enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(simple_formatter)
            console_handler.setLevel(log_level)
            root_logger.addHandler(console_handler)

        # File handler with rotation
        if enable_file and log_file_path:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

            file_handler = RotatingFileHandler(
                filename=log_file_path,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setFormatter(detailed_formatter)
            file_handler.setLevel(logging.DEBUG)  # File gets all details
            root_logger.addHandler(file_handler)

        # Reduce noise from third-party libraries
        logging.getLogger("uvicorn").setLevel(logging.WARNING)
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("redis").setLevel(logging.WARNING)

        return logging.getLogger(service_name)
