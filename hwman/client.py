import logging
from pathlib import Path

import grpc
from hwman.grpc.protobufs_compiled.jobs_pb2_grpc import JobDispatchStub  # type: ignore
from hwman.grpc.protobufs_compiled.jobs_pb2 import Job, JobType  # type: ignore


def create_mtls_channel(
    user_id: str,
    host: str = "localhost",
    port: str = "50051",
    cert_dir: Path = Path("./certs"),
):
    """
    Create a gRPC channel with mutual TLS (mTLS) authentication.

    mTLS Client Flow:
    1. Load CA certificate (to verify server)
    2. Load client certificate and key (to authenticate to server)
    3. Create secure channel with both certificates
    4. gRPC handles the mutual authentication automatically
    """

    target = f"{host}:{port}"

    # Define certificate paths
    ca_cert_file = cert_dir / "ca.crt"
    client_cert_file = cert_dir / "clients" / f"{user_id}.crt"
    client_key_file = cert_dir / "clients" / f"{user_id}.key"

    # Check if all required certificates exist
    missing_files = []
    if not ca_cert_file.exists():
        missing_files.append(str(ca_cert_file))
    if not client_cert_file.exists():
        missing_files.append(str(client_cert_file))
    if not client_key_file.exists():
        missing_files.append(str(client_key_file))

    if missing_files:
        raise FileNotFoundError(
            f"Missing certificate files for user '{user_id}': {missing_files}\n"
            f"Create client certificate with: python -m hwman.grpc.certificate_cli create-client {user_id}"
        )

    # Load CA certificate (to verify the server's certificate)
    with open(ca_cert_file, "rb") as f:
        ca_cert = f.read()

    # Load client certificate and private key (to authenticate to the server)
    with open(client_cert_file, "rb") as f:
        client_cert = f.read()
    with open(client_key_file, "rb") as f:
        client_key = f.read()

    # Create SSL channel credentials for mTLS
    # This configures the client to:
    # 1. Verify server certificate using CA certificate
    # 2. Present client certificate for authentication
    credentials = grpc.ssl_channel_credentials(
        root_certificates=ca_cert,  # CA cert to verify server
        private_key=client_key,  # Client's private key
        certificate_chain=client_cert,  # Client's certificate
    )

    # Create secure channel
    channel = grpc.secure_channel(target, credentials)

    logger.info(f"Created mTLS channel to {target} for user '{user_id}'")
    return channel


def run_with_mtls(
    user_id: str,
    host: str = "localhost",
    port: str = "50051",
    cert_dir: str = "./certs",
):
    """
    Run the gRPC client using mTLS authentication.

    The user_id must match a client certificate that exists in the cert_dir.
    """

    logger.info(f"Starting mTLS gRPC client for user: {user_id}")

    try:
        # Create mTLS channel
        with create_mtls_channel(user_id, host, port, Path(cert_dir)) as channel:
            # Create gRPC stub
            stub = JobDispatchStub(channel)

            # Create job request
            job = Job(
                type=JobType.JOB_TYPE_DUMMY,
                # user=user_id  # Optional: set user in request too
            )

            logger.info(f"Sending job request for user '{user_id}'...")

            # Make the request
            # Note: No need to manually add authentication metadata!
            # The mTLS handshake handles authentication automatically
            response = stub.SubmitJob(job)

            logger.info(f"Response received for user '{user_id}':")
            logger.info(f"   Job ID: {response.id}")
            logger.info(f"   Job Type: {response.type}")
            logger.info(f"   User: {response.user}")
            logger.info(f"   Status: {response.status}")

            if response.result:
                logger.info(f"Result: {response.result.id} at {response.result.path}")
                logger.info(f"Data axes: {len(response.result.data)} axes")

            return True

    except grpc.RpcError as e:
        logger.error(f"RPC failed for user '{user_id}': {e.code()}: {e.details()}")
        return False

    except FileNotFoundError as e:
        logger.error(f"Certificate error: {e}")
        return False

    except Exception as e:
        logger.error(f"Unexpected error for user '{user_id}': {e}")
        return False


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    # Example usage with mTLS

    print("=" * 60)
    print("Testing mTLS connection with different users:")

    # You can test with different user IDs
    # (Make sure these certificates exist!)
    test_users = ["alice"]  # , "bob", "admin"]

    for user_id in test_users:
        print(f"\n--- Testing with user: {user_id} ---")
        success = run_with_mtls(user_id=user_id, cert_dir="./certs")

        if success:
            print(f"{user_id}: Connection successful")
        else:
            print(f"{user_id}: Connection failed")
