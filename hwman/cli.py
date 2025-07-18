#!/usr/bin/env python3
"""
Main CLI for the Hardware Management (hwman) tool.
"""

import logging
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv

from hwman.main import Server

app = typer.Typer(
    name="hwman",
    help="Hardware Management CLI Tool",
)


def setup_logging(log_level: str = "INFO") -> None:
    """Configure logging for the application."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


@app.command()
def start(
    address: Annotated[
        str, typer.Option("--address", help="Server address to bind to")
    ] = "localhost",
    port: Annotated[int, typer.Option("--port", help="Server port to bind to")] = 50001,
    cert_dir: Annotated[
        str, typer.Option("--cert-dir", help="Directory for certificates")
    ] = "./certs",
    log_level: Annotated[
        str, typer.Option("--log-level", help="Set logging level", case_sensitive=False)
    ] = "INFO",
    instrumentserver_config_file: Annotated[
        str, typer.Option("-c", help="Path to instrumentserver config file")
    ] = "./configs/serverConfig.yml",
    proxy_ns_name: Annotated[
        str, typer.Option("-pn", help="Name of the Pyro nameserver proxy")
    ] = "rfsoc",
    ns_host: Annotated[
        str, typer.Option("-nh", help="Host of the Pyro nameserver")
    ] = "localhost",
    ns_port: Annotated[
        int, typer.Option("-np", help="Port of the Pyro nameserver")
    ] = 8888,
    start_external_services: Annotated[
        bool, typer.Option("-se", help="Start external services")
    ] = True,
) -> None:
    """Start the hardware management server."""

    # Load environment variables from .env file if it exists
    env_file = Path.cwd() / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        print(f"Loaded environment variables from {env_file}")

    # Validate log level
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if log_level.upper() not in valid_levels:
        typer.echo(
            f"Error: Invalid log level '{log_level}'. Must be one of: {', '.join(valid_levels)}",
            err=True,
        )
        raise typer.Exit(1)

    # Setup logging
    setup_logging(log_level.upper())

    # Create logger
    logger = logging.getLogger(__name__)

    logger.info("Starting server with:")
    logger.info(f"  Address: {address}")
    logger.info(f"  Port: {port}")
    logger.info(f"  Certificate directory: {cert_dir}")
    logger.info(f"  Log level: {log_level.upper()}")

    try:
        # Initialize server
        server = Server(
            address=address,
            port=port,
            cert_dir=cert_dir,
            instrumentserver_config_file=instrumentserver_config_file,
            proxy_ns_name=proxy_ns_name,
            ns_host=ns_host,
            ns_port=ns_port,
            start_external_services=start_external_services,
        )

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
