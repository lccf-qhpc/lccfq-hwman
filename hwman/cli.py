#!/usr/bin/env python3
"""
Main CLI for the Hardware Management (hwman) tool.
"""

import logging
from pathlib import Path
from typing import Annotated

import typer

from hwman.main import Server

app = typer.Typer(
    name="hwman",
    help="Hardware Management CLI Tool",
)


def setup_logging(log_level: str = "INFO"):
    """Configure logging for the application."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


@app.command()
def start(
    address: Annotated[str, typer.Option(help="Server address to bind to")] = "localhost",
    port: Annotated[int, typer.Option(help="Server port to bind to")] = 50001,
    cert_dir: Annotated[str, typer.Option("--cert-dir", help="Directory for certificates")] = "./certs",
    log_level: Annotated[str, typer.Option(
        "--log-level", 
        help="Set logging level",
        case_sensitive=False
    )] = "INFO"
):
    """Start the hardware management server."""
    
    # Validate log level
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if log_level.upper() not in valid_levels:
        typer.echo(f"Error: Invalid log level '{log_level}'. Must be one of: {', '.join(valid_levels)}", err=True)
        raise typer.Exit(1)
    
    # Setup logging
    setup_logging(log_level.upper())
    
    # Create logger
    logger = logging.getLogger(__name__)
    
    logger.info(f"Starting server with:")
    logger.info(f"  Address: {address}")
    logger.info(f"  Port: {port}")
    logger.info(f"  Certificate directory: {cert_dir}")
    logger.info(f"  Log level: {log_level.upper()}")
    
    try:
        # Initialize server
        server = Server(
            address=address,
            port=port,
            cert_dir=cert_dir
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
        raise typer.Exit(1)


def main():
    """Entry point for the hwman CLI."""
    app()


if __name__ == "__main__":
    main() 