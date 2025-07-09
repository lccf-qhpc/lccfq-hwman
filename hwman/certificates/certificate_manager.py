"""
Certificate Management for Mutual TLS (mTLS) in gRPC

This module handles:
1. Creating a Certificate Authority (CA)
2. Generating server certificates signed by the CA
3. Generating client certificates for each user, signed by the CA
4. Managing certificate files and directories

The mTLS flow:
1. Server has a certificate signed by our CA
2. Each client (user) has a certificate signed by our CA
3. During TLS handshake, both sides verify each other's certificates
4. Server can identify the user from their certificate's Common Name (CN)
"""

import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple
import ipaddress

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

logger = logging.getLogger(__name__)


class CertificateManager:
    """
    Manages all certificates for mTLS:
    - CA certificate (signs all other certificates)
    - Server certificate (for the gRPC server)
    - Client certificates (one per user)
    """

    @staticmethod
    def _save_certificate_and_key(
        cert: x509.Certificate,
        private_key: rsa.RSAPrivateKey,
        cert_path: Path,
        key_path: Path,
    ):
        """Save a certificate and its private key to files in PEM format."""

        # Serialize certificate to PEM format
        cert_pem = cert.public_bytes(serialization.Encoding.PEM)

        # Serialize private key to PEM format (unencrypted for simplicity)
        key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        # Write to files
        with open(cert_path, "wb") as f:
            f.write(cert_pem)
        with open(key_path, "wb") as f:
            f.write(key_pem)

        logger.info(f"Saved certificate: {cert_path}")
        logger.info(f"Saved private key: {key_path}")

    @staticmethod
    def _generate_private_key() -> rsa.RSAPrivateKey:
        """Generate a new RSA private key for certificates."""
        return rsa.generate_private_key(
            public_exponent=65537,  # Standard RSA exponent
            key_size=2048,  # 2048-bit key (good security/performance balance)
        )

    def __init__(self, cert_dir: Path):
        """
        Initialize certificate manager with a directory to store certificates.

        Directory structure will be:
        cert_dir/
        ├── ca.crt          # CA certificate (public)
        ├── ca.key          # CA private key (keep secure!)
        ├── server.crt      # Server certificate
        ├── server.key      # Server private key
        └── clients/        # Client certificates
            ├── user1.crt
            ├── user1.key
            └── ...
        """
        self.cert_dir = Path(cert_dir)
        self.cert_dir.mkdir(parents=True, exist_ok=True)

        # Certificate file paths
        self.ca_cert_file = self.cert_dir / "ca.crt"
        self.ca_key_file = self.cert_dir / "ca.key"
        self.server_cert_file = self.cert_dir / "server.crt"
        self.server_key_file = self.cert_dir / "server.key"

        # Client certificates directory
        self.clients_dir = self.cert_dir / "clients"
        self.clients_dir.mkdir(exist_ok=True)

    def _create_ca_certificate(self) -> Tuple[x509.Certificate, rsa.RSAPrivateKey]:
        """
        Create a Certificate Authority (CA) certificate.

        The CA certificate is used to sign all other certificates (server + clients).
        This establishes a "trust chain" - if you trust the CA, you trust certificates it signs.
        """
        logger.info("Creating CA certificate...")

        # Generate private key for CA
        ca_private_key = self._generate_private_key()

        # Create the CA certificate
        # Note: For CA certificates, subject == issuer (self-signed)
        subject = issuer = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "IL"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "Urbana"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "LCCF Lab"),
                x509.NameAttribute(NameOID.COMMON_NAME, "LCCF CA"),  # CA name
            ]
        )

        ca_cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(
                issuer  # Self-signed, so issuer = subject
            )
            .public_key(ca_private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc))
            .not_valid_after(
                datetime.now(timezone.utc)
                + timedelta(days=3650)  # CA valid for 10 years
            )
            .add_extension(
                # Mark this as a CA certificate (can sign other certificates)
                x509.BasicConstraints(ca=True, path_length=None),
                critical=True,
            )
            .add_extension(
                # Define what this certificate can be used for
                x509.KeyUsage(
                    key_cert_sign=True,  # Can sign certificates
                    crl_sign=True,  # Can sign certificate revocation lists
                    key_encipherment=False,
                    content_commitment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    digital_signature=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .sign(ca_private_key, hashes.SHA256())
        )

        return ca_cert, ca_private_key

    def _create_server_certificate(
        self,
        ca_cert: x509.Certificate,
        ca_private_key: rsa.RSAPrivateKey,
        hostname: str = "localhost",
    ) -> Tuple[x509.Certificate, rsa.RSAPrivateKey]:
        """
        Create a server certificate signed by the CA.

        This certificate identifies the gRPC server and enables TLS encryption.
        """
        logger.info(f"Creating server certificate for {hostname}...")

        # Generate private key for server
        server_private_key = self._generate_private_key()

        # Create server certificate
        subject = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "IL"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "Urbana"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "LCCF Lab"),
                x509.NameAttribute(NameOID.COMMON_NAME, hostname),  # Server hostname
            ]
        )

        server_cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(
                ca_cert.subject  # Signed by CA
            )
            .public_key(server_private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc))
            .not_valid_after(
                datetime.now(timezone.utc)
                + timedelta(days=365)  # Server cert valid for 1 year
            )
            .add_extension(
                # Alternative names for the server (localhost, 127.0.0.1, etc.)
                x509.SubjectAlternativeName(
                    [
                        x509.DNSName(hostname),
                        x509.DNSName("localhost"),
                        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                    ]
                ),
                critical=False,
            )
            .add_extension(
                # This is NOT a CA certificate
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .add_extension(
                # Define server certificate usage
                x509.KeyUsage(
                    key_cert_sign=False,
                    crl_sign=False,
                    key_encipherment=True,  # Can encrypt keys
                    content_commitment=False,
                    data_encipherment=True,  # Can encrypt data
                    key_agreement=False,
                    digital_signature=True,  # Can create digital signatures
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .sign(ca_private_key, hashes.SHA256())
        )  # Signed by CA's private key

        return server_cert, server_private_key

    def _create_client_certificate(
        self, ca_cert: x509.Certificate, ca_private_key: rsa.RSAPrivateKey, user_id: str
    ) -> Tuple[x509.Certificate, rsa.RSAPrivateKey]:
        """
        Create a client certificate for a specific user, signed by the CA.

        The user_id will be embedded in the certificate's Common Name (CN).
        The server can extract this during the TLS handshake to identify the user.
        """
        logger.info(f"Creating client certificate for user: {user_id}")

        # Generate private key for client
        client_private_key = self._generate_private_key()

        # Create client certificate with user_id in Common Name
        subject = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "IL"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "Urbana"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "LCCF Lab"),
                x509.NameAttribute(NameOID.COMMON_NAME, user_id),  # USER ID HERE!
            ]
        )

        client_cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(
                ca_cert.subject  # Signed by CA
            )
            .public_key(client_private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc))
            .not_valid_after(
                datetime.now(timezone.utc)
                + timedelta(days=365)  # Client cert valid for 1 year
            )
            .add_extension(
                # This is NOT a CA certificate
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .add_extension(
                # Define client certificate usage
                x509.KeyUsage(
                    key_cert_sign=False,
                    crl_sign=False,
                    key_encipherment=True,  # Can encrypt keys
                    content_commitment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    digital_signature=True,  # Can create digital signatures
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                # Extended key usage for client authentication
                x509.ExtendedKeyUsage(
                    [
                        x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH,  # This cert is for client auth
                    ]
                ),
                critical=True,
            )
            .sign(ca_private_key, hashes.SHA256())
        )  # Signed by CA's private key

        return client_cert, client_private_key

    def setup_ca_and_server(
        self, hostname: str = "localhost"
    ) -> Tuple[Path, Path, Path]:
        """
        Set up the complete certificate infrastructure:
        1. Create CA certificate (if not exists)
        2. Create server certificate (if not exists)

        Returns paths to: (ca_cert_file, server_cert_file, server_key_file)
        """

        # Check if CA already exists
        if not (self.ca_cert_file.exists() and self.ca_key_file.exists()):
            # Create CA certificate
            ca_cert, ca_private_key = self._create_ca_certificate()
            self._save_certificate_and_key(
                ca_cert, ca_private_key, self.ca_cert_file, self.ca_key_file
            )
        else:
            logger.info("CA certificate already exists")
            # Load existing CA
            with open(self.ca_cert_file, "rb") as f:
                ca_cert = x509.load_pem_x509_certificate(f.read())
            with open(self.ca_key_file, "rb") as f:
                loaded_key = serialization.load_pem_private_key(f.read(), password=None)
                # We know this is an RSA key since we always generate RSA keys
                assert isinstance(loaded_key, rsa.RSAPrivateKey)
                ca_private_key = loaded_key

        # Check if server certificate already exists
        if not (self.server_cert_file.exists() and self.server_key_file.exists()):
            # Create server certificate
            server_cert, server_private_key = self._create_server_certificate(
                ca_cert, ca_private_key, hostname
            )
            self._save_certificate_and_key(
                server_cert,
                server_private_key,
                self.server_cert_file,
                self.server_key_file,
            )
        else:
            logger.info("Server certificate already exists")

        return self.ca_cert_file, self.server_cert_file, self.server_key_file

    def create_client_certificate(self, user_id: str) -> Tuple[Path, Path]:
        """
        Create a client certificate for a specific user.

        Returns paths to: (client_cert_file, client_key_file)
        """

        # Load CA certificate and key
        with open(self.ca_cert_file, "rb") as f:
            ca_cert = x509.load_pem_x509_certificate(f.read())
        with open(self.ca_key_file, "rb") as f:
            loaded_key = serialization.load_pem_private_key(f.read(), password=None)
            # We know this is an RSA key since we always generate RSA keys
            assert isinstance(loaded_key, rsa.RSAPrivateKey)
            ca_private_key = loaded_key

        # Create client certificate
        client_cert, client_private_key = self._create_client_certificate(
            ca_cert, ca_private_key, user_id
        )

        # Save client certificate
        client_cert_file = self.clients_dir / f"{user_id}.crt"
        client_key_file = self.clients_dir / f"{user_id}.key"

        self._save_certificate_and_key(
            client_cert, client_private_key, client_cert_file, client_key_file
        )

        return client_cert_file, client_key_file

    def list_client_certificates(self) -> Dict[str, Tuple[Path, Path]]:
        """
        List all existing client certificates.

        Returns dict of {user_id: (cert_path, key_path)}
        """
        clients = {}
        for cert_file in self.clients_dir.glob("*.crt"):
            user_id = cert_file.stem  # filename without extension
            key_file = self.clients_dir / f"{user_id}.key"
            if key_file.exists():
                clients[user_id] = (cert_file, key_file)

        return clients
