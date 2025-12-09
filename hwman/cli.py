#!/usr/bin/env python3
"""
Main CLI for the Hardware Management (hwman) tool.
"""

import copy
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import typer
from cryptography import x509
from dotenv import load_dotenv

from hwman.certificate_manager import CertificateManager
from hwman.config import HwmanSettings
from hwman.main import Server

app = typer.Typer(
    name="hwman",
    help="Hardware Management CLI Tool",
)

# Create a subcommand group for certificate management
cert_app = typer.Typer(
    name="cert",
    help="Certificate management commands",
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


# Certificate management commands

@cert_app.command("setup-server")
def cert_setup_server(
    cert_dir: Annotated[
        str, typer.Option("--cert-dir", help="Certificate directory")
    ] = "./certs",
    hostname: Annotated[
        str, typer.Option("--hostname", help="Server hostname")
    ] = "localhost",
) -> None:
    """Set up CA and server certificates.

    This creates:
    - CA certificate (if not exists)
    - Server certificate (if not exists)
    """
    typer.echo(f"Setting up server certificates in: {cert_dir}")

    cert_manager = CertificateManager(Path(cert_dir))
    ca_cert_file, server_cert_file, server_key_file = cert_manager.setup_ca_and_server(
        hostname
    )

    typer.echo("Server certificate setup complete!")
    typer.echo(f"Certificate directory: {cert_dir}")
    typer.echo(f"CA certificate: {ca_cert_file}")
    typer.echo(f"Server certificate: {server_cert_file}")
    typer.echo(f"Server private key: {server_key_file}")

    typer.echo("\nNext steps:")
    typer.echo("1. Start the server: uv run hwman start")
    typer.echo("2. Create client certificates: uv run hwman cert create-client <user_id>")


@cert_app.command("create-client")
def cert_create_client(
    user_id: Annotated[str, typer.Argument(help="User ID for the certificate")],
    cert_dir: Annotated[
        str, typer.Option("--cert-dir", help="Certificate directory")
    ] = "./certs",
) -> None:
    """Create a client certificate for a specific user.

    The user_id will be embedded in the certificate's Common Name,
    which the server uses to identify the user.
    """
    typer.echo(f"Creating client certificate for user: {user_id}")

    cert_manager = CertificateManager(Path(cert_dir))

    # Check if server certificates exist
    if not (
        cert_manager.ca_cert_file.exists() and cert_manager.server_cert_file.exists()
    ):
        typer.echo("Error: Server certificates not found!", err=True)
        typer.echo(
            "Run setup-server first: uv run hwman cert setup-server", err=True
        )
        raise typer.Exit(1)

    try:
        # Create client certificate
        client_cert_file, client_key_file = cert_manager.create_client_certificate(
            user_id
        )

        typer.echo("Client certificate created successfully!")
        typer.echo(f"User ID: {user_id}")
        typer.echo(f"Certificate: {client_cert_file}")
        typer.echo(f"Private key: {client_key_file}")

        # Display certificate info
        typer.echo("\nCertificate Details:")
        _display_certificate_info(client_cert_file)

        typer.echo("\nUsage:")
        typer.echo(f"  Use these credentials to connect to the hwman server")

    except Exception as e:
        typer.echo(f"Failed to create client certificate: {e}", err=True)
        raise typer.Exit(1)


@cert_app.command("list-clients")
def cert_list_clients(
    cert_dir: Annotated[
        str, typer.Option("--cert-dir", help="Certificate directory")
    ] = "./certs",
) -> None:
    """List all existing client certificates."""
    cert_manager = CertificateManager(Path(cert_dir))
    clients = cert_manager.list_client_certificates()

    if not clients:
        typer.echo("No client certificates found.")
        typer.echo(
            "Create one with: uv run hwman cert create-client <user_id>"
        )
        return

    typer.echo(f"Found {len(clients)} client certificate(s):")
    typer.echo("")

    for user_id, (cert_path, key_path) in clients.items():
        typer.echo(f"User: {user_id}")
        typer.echo(f"  Certificate: {cert_path}")
        typer.echo(f"  Private key: {key_path}")

        # Display expiration info
        try:
            with open(cert_path, "rb") as f:
                cert = x509.load_pem_x509_certificate(f.read())

            now = datetime.now(timezone.utc)
            expires = cert.not_valid_after_utc

            if expires > now:
                days_left = (expires - now).days
                typer.echo(f"  Status: Valid (expires in {days_left} days)")
            else:
                typer.echo("  Status: Expired")

        except Exception as e:
            typer.echo(f"  Status: Could not read certificate: {e}")

        typer.echo("")


@cert_app.command("status")
def cert_status(
    cert_dir: Annotated[
        str, typer.Option("--cert-dir", help="Certificate directory")
    ] = "./certs",
) -> None:
    """Display the status of server certificates."""
    cert_manager = CertificateManager(Path(cert_dir))

    typer.echo(f"Server Certificate Status ({cert_dir}):")
    typer.echo("")

    # Check CA certificate
    if cert_manager.ca_cert_file.exists():
        typer.echo(f"CA Certificate: {cert_manager.ca_cert_file}")
        _display_certificate_info(cert_manager.ca_cert_file)
    else:
        typer.echo(f"CA Certificate missing: {cert_manager.ca_cert_file}")

    typer.echo("")

    # Check server certificate
    if cert_manager.server_cert_file.exists():
        typer.echo(f"Server Certificate: {cert_manager.server_cert_file}")
        _display_certificate_info(cert_manager.server_cert_file)
    else:
        typer.echo(f"Server Certificate missing: {cert_manager.server_cert_file}")

    typer.echo("")

    # Overall status
    if cert_manager.ca_cert_file.exists() and cert_manager.server_cert_file.exists():
        typer.echo("Server certificates are ready!")
        typer.echo("You can start the server with: uv run hwman start")
    else:
        typer.echo("Server certificates are incomplete!")
        typer.echo("Run setup-server: uv run hwman cert setup-server")


def _display_certificate_info(cert_file: Path) -> None:
    """Display detailed information about a certificate."""
    try:
        with open(cert_file, "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read())

        # Extract certificate details
        subject = cert.subject

        # Get Common Name (user ID)
        user_id = None
        for attribute in subject:
            if attribute.oid == x509.oid.NameOID.COMMON_NAME:
                user_id = attribute.value
                break

        typer.echo(f"  User ID (CN): {user_id}")
        typer.echo(f"  Valid from: {cert.not_valid_before_utc}")
        typer.echo(f"  Valid until: {cert.not_valid_after_utc}")
        typer.echo(f"  Serial number: {cert.serial_number}")

        # Check if expired
        now = datetime.now(timezone.utc)
        if cert.not_valid_after_utc > now:
            days_left = (cert.not_valid_after_utc - now).days
            typer.echo(f"  Status: Valid ({days_left} days remaining)")
        else:
            typer.echo("  Status: Expired")

    except Exception as e:
        typer.echo(f"Could not read certificate: {e}")


# Register the certificate subcommand
app.add_typer(cert_app, name="cert")


def main() -> None:
    """Entry point for the hwman CLI."""
    app()


if __name__ == "__main__":
    main()
