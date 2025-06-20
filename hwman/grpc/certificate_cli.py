#!/usr/bin/env python3
"""
Command-line interface for managing mTLS certificates.

This CLI tool helps you:
1. Create client certificates for users
2. List existing certificates
3. View certificate information
4. Set up the certificate infrastructure

Usage examples:
  python -m hwman.grpc.certificate_cli create-client alice
  python -m hwman.grpc.certificate_cli create-client bob --cert-dir ./my_certs
  python -m hwman.grpc.certificate_cli list-clients
  python -m hwman.grpc.certificate_cli setup-server
"""

import argparse
import logging
from pathlib import Path
from datetime import datetime, timezone

from hwman.grpc.certificate_manager import CertificateManager
from cryptography import x509

logger = logging.getLogger(__name__)


def setup_server_certificates(cert_dir: str, hostname: str):
    """
    Set up the server certificate infrastructure.

    This creates:
    - CA certificate (if not exists)
    - Server certificate (if not exists)
    """

    print(f"Setting up server certificates in: {cert_dir}")

    cert_manager = CertificateManager(Path(cert_dir))
    ca_cert_file, server_cert_file, server_key_file = cert_manager.setup_ca_and_server(
        hostname
    )

    print("Server certificate setup complete!")
    print(f"Certificate directory: {cert_dir}")
    print(f"CA certificate: {ca_cert_file}")
    print(f"Server certificate: {server_cert_file}")
    print(f"Server private key: {server_key_file}")

    print("\n Next steps:")
    print("1. Start the server: python -m hwman.grpc.server")
    print(
        "2. Create client certificates: python -m hwman.grpc.certificate_cli create-client <user_id>"
    )


def create_client_certificate(user_id: str, cert_dir: str):
    """
    Create a client certificate for a specific user.

    The user_id will be embedded in the certificate's Common Name,
    which the server uses to identify the user.
    """

    print(f"Creating client certificate for user: {user_id}")

    cert_manager = CertificateManager(Path(cert_dir))

    # Check if server certificates exist
    if not (
        cert_manager.ca_cert_file.exists() and cert_manager.server_cert_file.exists()
    ):
        print("Server certificates not found!")
        print(
            "Run setup-server first: python -m hwman.grpc.certificate_cli setup-server"
        )
        return False

    try:
        # Create client certificate
        client_cert_file, client_key_file = cert_manager.create_client_certificate(
            user_id
        )

        print("Client certificate created successfully!")
        print(f"User ID: {user_id}")
        print(f"Certificate: {client_cert_file}")
        print(f"Private key: {client_key_file}")

        # Display certificate info
        print("\n Certificate Details:")
        display_certificate_info(client_cert_file)

        print("\n Usage:")
        print(f"   python -m hwman.grpc.client run_with_mtls {user_id}")

        return True

    except Exception as e:
        print(f"Failed to create client certificate: {e}")
        return False


def list_client_certificates(cert_dir: str):
    """List all existing client certificates."""

    cert_manager = CertificateManager(Path(cert_dir))
    clients = cert_manager.list_client_certificates()

    if not clients:
        print("No client certificates found.")
        print(
            "Create one with: python -m hwman.grpc.certificate_cli create-client <user_id>"
        )
        return

    print(f"Found {len(clients)} client certificate(s):")
    print("")

    for user_id, (cert_path, key_path) in clients.items():
        print(f"User: {user_id}")
        print(f"Certificate: {cert_path}")
        print(f"Private key: {key_path}")

        # Display expiration info
        try:
            with open(cert_path, "rb") as f:
                cert = x509.load_pem_x509_certificate(f.read())

            now = datetime.now(timezone.utc)
            expires = cert.not_valid_after

            if expires > now:
                days_left = (expires - now).days
                print(f"   Status: Valid (expires in {days_left} days)")
            else:
                print("   Status: Expired")

        except Exception as e:
            print(f"   Status: Could not read certificate: {e}")

        print("")


def display_certificate_info(cert_file: Path):
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

        print(f"   User ID (CN): {user_id}")
        print(f"   Valid from: {cert.not_valid_before_utc}")
        print(f"   Valid until: {cert.not_valid_after_utc}")
        print(f"   Serial number: {cert.serial_number}")

        # Check if expired
        now = datetime.now(timezone.utc)
        if cert.not_valid_after_utc > now:
            days_left = (cert.not_valid_after_utc - now).days
            print(f"   Status: Valid ({days_left} days remaining)")
        else:
            print("   Status: Expired")

    except Exception as e:
        print(f"Could not read certificate: {e}")


def display_server_status(cert_dir: str):
    """Display the status of server certificates."""

    cert_manager = CertificateManager(Path(cert_dir))

    print(f"️Server Certificate Status ({cert_dir}):")
    print("")

    # Check CA certificate
    if cert_manager.ca_cert_file.exists():
        print(f"CA Certificate: {cert_manager.ca_cert_file}")
        display_certificate_info(cert_manager.ca_cert_file)
    else:
        print(f"CA Certificate missing: {cert_manager.ca_cert_file}")

    print("")

    # Check server certificate
    if cert_manager.server_cert_file.exists():
        print(f"Server Certificate: {cert_manager.server_cert_file}")
        display_certificate_info(cert_manager.server_cert_file)
    else:
        print(f"Server Certificate missing: {cert_manager.server_cert_file}")

    print("")

    # Overall status
    if cert_manager.ca_cert_file.exists() and cert_manager.server_cert_file.exists():
        print("Server certificates are ready!")
        print("You can start the server with: python -m hwman.grpc.server")
    else:
        print("Server certificates are incomplete!")
        print("Run setup-server: python -m hwman.grpc.certificate_cli setup-server")


def main():
    """Main CLI entry point."""

    parser = argparse.ArgumentParser(
        description="Manage mTLS certificates for gRPC service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s setup-server                     # Set up CA and server certificates
  %(prog)s create-client alice              # Create certificate for user 'alice'
  %(prog)s create-client bob --cert-dir /tmp/certs  # Use custom certificate directory
  %(prog)s list-clients                     # List all client certificates
  %(prog)s status                           # Show server certificate status
        """,
    )

    # Global options
    parser.add_argument(
        "--cert-dir", default="./certs", help="Certificate directory (default: ./certs)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Setup server command
    setup_parser = subparsers.add_parser(
        "setup-server", help="Set up CA and server certificates"
    )
    setup_parser.add_argument(
        "--hostname", default="localhost", help="Server hostname (default: localhost)"
    )

    # Create client command
    create_parser = subparsers.add_parser(
        "create-client", help="Create a client certificate for a user"
    )
    create_parser.add_argument("user_id", help="User ID for the certificate")

    # List clients command
    subparsers.add_parser("list-clients", help="List all existing client certificates")

    # Status command
    subparsers.add_parser("status", help="Show server certificate status")

    # Parse arguments
    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Execute command
    if args.command == "setup-server":
        setup_server_certificates(args.cert_dir, args.hostname)

    elif args.command == "create-client":
        create_client_certificate(args.user_id, args.cert_dir)

    elif args.command == "list-clients":
        list_client_certificates(args.cert_dir)

    elif args.command == "status":
        display_server_status(args.cert_dir)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
