#!/usr/bin/env python3
"""
Debug wrapper for hwman server.
This script can be run directly with PyCharm debugger.
"""

import logging
import sys
from pathlib import Path
from dotenv import load_dotenv

from hwman.config import HwmanSettings
from hwman.main import Server
from hwman.cli import setup_logging


def main():
    """Start the server in debug mode."""

    # Load environment variables from .env file if it exists
    env_file = Path.cwd() / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        print(f"Loaded environment variables from {env_file}")

    # Load configuration from TOML file
    config_file = Path("config.toml")

    try:
        config = HwmanSettings(_toml_file=config_file)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        print(f"Please create a config file at {config_file}", file=sys.stderr)
        print("You can copy from configs/example_config.toml as a template", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        sys.exit(1)

    # Setup logging
    setup_logging(config.log_level)

    # Create logger
    logger = logging.getLogger(__name__)

    logger.info("Starting server with configuration from:")
    logger.info(f"  Config file: {config_file.absolute()}")
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
        sys.exit(0)
    except Exception as e:
        logger.error(f"Server failed to start: {e}")
        logger.exception("Full traceback:")
        sys.exit(1)


if __name__ == "__main__":
    main()