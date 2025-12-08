#!/usr/bin/env python3
"""
Main CLI for the Hardware Management (hwman) tool.
"""

import copy
import logging
import sys
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv

from hwman.config import HwmanSettings
from hwman.main import Server

app = typer.Typer(
    name="hwman",
    help="Hardware Management CLI Tool",
)


class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors based on logger name and level."""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green  
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    
    # Service-specific colors (for logger names)
    SERVICE_COLORS = {
        'hwman.main': '\033[94m',                          # Blue
        'hwman.services.health': '\033[92m',               # Light Green
        'hwman.services.health.instrumentserver': '\033[95m',  # Light Magenta
        'hwman.services.health.pyro_nameserver': '\033[91m',   # Light Red  
        'hwman.services.health.qick_server': '\033[97m',       # White
        'hwman.services.tests': '\033[96m',                # Light Cyan
        'hwman.certificates': '\033[93m',                  # Light Yellow
    }
    
    RESET = '\033[0m'  # Reset color

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Check if output is a terminal
        self.use_colors = hasattr(sys.stderr, 'isatty') and sys.stderr.isatty()

    def format(self, record):
        if not self.use_colors:
            return super().format(record)
        
        # Create a copy of the record to avoid mutating the original
        record_copy = copy.copy(record)
        
        # Get color for service (logger name)
        service_color = self.SERVICE_COLORS.get(record_copy.name, '')
        
        # Get color for log level
        level_color = self.COLORS.get(record_copy.levelname, '')
        
        # Apply colors to specific parts
        if service_color:
            record_copy.name = f"{service_color}{record_copy.name}{self.RESET}"
        if level_color:
            record_copy.levelname = f"{level_color}{record_copy.levelname}{self.RESET}"
            
        return super().format(record_copy)


def setup_logging(log_level: str = "INFO") -> None:
    """Configure logging for the application."""
    
    # Create formatter
    formatter = ColoredFormatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    # Setup handler
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        handlers=[handler],
        force=True  # Override any existing configuration
    )


@app.command()
def start(
    config_file: Annotated[
        str, typer.Option("-c", "--config", help="Path to TOML configuration file")
    ] = "config.toml",
) -> None:
    """Start the hardware management server.

    Configuration is loaded from a TOML file. See configs/example_config.toml for an example.
    """

    # Load environment variables from .env file if it exists
    env_file = Path.cwd() / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        print(f"Loaded environment variables from {env_file}")

    # Load configuration from TOML file
    config_path = Path(config_file)
    try:
        config = HwmanSettings(_toml_file=config_path)
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        typer.echo(f"Please create a config file at {config_path}", err=True)
        typer.echo(f"You can copy from configs/example_config.toml as a template", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error loading configuration: {e}", err=True)
        raise typer.Exit(1)

    # Setup logging
    setup_logging(config.log_level)

    # Create logger
    logger = logging.getLogger(__name__)

    logger.info("Starting server with configuration from:")
    logger.info(f"  Config file: {config_path.absolute()}")
    logger.info(f"  Address: {config.server_address}:{config.server_port}")
    logger.info(f"  Certificate directory: {config.cert_dir}")
    logger.info(f"  Log level: {config.log_level}")
    logger.info(f"  Start external services: {config.start_external_services}")

    try:
        # Initialize server with config
        server = Server(config)

        # Initialize certificates
        server._initialize_certificates()

        # Start serving
        server.serve()

    except KeyboardInterrupt:
        logger.info("Server shutdown requested by user")
        raise typer.Exit(0)
    except Exception as e:
        logger.error(f"Server failed to start: {e}")
        logger.exception("Full traceback:")
        raise typer.Exit(1)


def main() -> None:
    """Entry point for the hwman CLI."""
    app()


if __name__ == "__main__":
    main()
