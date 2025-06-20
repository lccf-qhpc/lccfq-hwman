import uuid
import logging
from pathlib import Path

import grpc
from concurrent import futures

from hwman.grpc.protobufs_compiled import jobs_pb2_grpc  # type: ignore
from hwman.grpc.protobufs_compiled.jobs_pb2 import (  # type: ignore
    JobType,
    JobStatus,
    Result,
    DataAxis,
    Job,
)
from hwman.grpc.protobufs_compiled.jobs_pb2_grpc import JobDispatchServicer  # type: ignore
from hwman.setup_measurements import execute_measurement
from hwman.measurements.dummy import generate_dummy_sweep
from hwman.grpc.certificate_manager import CertificateManager


def dummy_measurement():
    sweep = generate_dummy_sweep()
    data_location, data = execute_measurement(sweep, "dummy_measurement")

    axes = []
    for ax in data.axes():
        axis = DataAxis(name=ax, values=list(int(x) for x in data[ax]["values"]))
        axes.append(axis)
    for dep in data.dependents():
        axis = DataAxis(
            name=dep,
            values=list(int(x) for x in data[dep]["values"]),
            depends_on=data[dep]["axes"],
        )
        axes.append(axis)
    result = Result(id=str(uuid.uuid4()), path=str(data_location), data=axes)
    return result


def extract_user_from_context(context) -> str:
    """
    Extract the user ID from the client's certificate.
    
    In mTLS, the client's certificate is available in the gRPC context.
    We extract the Common Name (CN) from the certificate subject.
    """
    try:
        # Get the peer's certificate from the TLS context
        auth_context = context.auth_context()
        
        # Look for the certificate subject's common name
        for key, value in auth_context.items():
            if key == 'x509_common_name':
                return value[0].decode('utf-8')  # Convert bytes to string
        
        # Fallback: couldn't extract user from certificate
        return "unknown_user"
    
    except Exception as e:
        logger.warning(f"Failed to extract user from certificate: {e}")
        return "unknown_user"


class JobService(JobDispatchServicer):
    def SubmitJob(self, request, context):
        """
        Process job requests with user identification from mTLS certificates.
        
        The key difference from before: we can now identify which user
        is making the request by looking at their certificate!
        """
        
        # Extract user ID from the client's certificate
        user_id = extract_user_from_context(context)
        
        # Log the authenticated user
        logger.info(f"Authenticated user '{user_id}' submitted job: {request.id}, type: {request.type}")
        
        if request.type == JobType.JOB_TYPE_DUMMY:
            # Execute the dummy measurement
            result = dummy_measurement()
            ret = Job(
                id=request.id,
                # Set the user field to the authenticated user
                user=request.user or user_id,  # Use cert user if not provided in request
                type=request.type,
                status=JobStatus.JOB_STATUS_SUCCESS,
                payload=request.payload,
                result=result,
            )
            
            logger.info(f"Job completed for user '{user_id}': {ret.id}")
            return ret

        else:
            logger.error(f"Unsupported job type for user '{user_id}': {request.type}")
            raise NotImplementedError(f"Job type {request.type} not implemented")


def create_mtls_server(
    port: str = "50051",
    cert_dir: Path = Path("./certs"),
    hostname: str = "localhost"
):
    """
    Create a gRPC server with mutual TLS (mTLS) authentication.
    
    mTLS Flow:
    1. Server loads its certificate and CA certificate
    2. Server configures gRPC to REQUIRE client certificates
    3. When client connects, both sides verify each other's certificates
    4. Server can identify the user from their certificate's Common Name
    """
    
    logger.info("Setting up mTLS server...")
    
    # Initialize certificate manager
    cert_manager = CertificateManager(cert_dir)
    
    # Set up CA and server certificates (creates them if they don't exist)
    ca_cert_file, server_cert_file, server_key_file = cert_manager.setup_ca_and_server(hostname)
    
    # Load the certificates for gRPC
    with open(server_cert_file, 'rb') as f:
        server_cert = f.read()
    with open(server_key_file, 'rb') as f:
        server_key = f.read()
    with open(ca_cert_file, 'rb') as f:
        ca_cert = f.read()
    
    # Create SSL server credentials for mTLS
    # This is the key part - we specify:
    # 1. Server's certificate and key (so clients can verify the server)
    # 2. CA certificate (so server can verify client certificates)
    # 3. require_client_auth=True (forces clients to present certificates)
    server_credentials = grpc.ssl_server_credentials(
        private_key_certificate_chain_pairs=[(server_key, server_cert)],
        root_certificates=ca_cert,           # CA cert to verify client certs
        require_client_auth=True             # REQUIRE client certificates
    )
    
    # Create gRPC server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    jobs_pb2_grpc.add_JobDispatchServicer_to_server(JobService(), server)
    
    # Add secure port with mTLS
    server.add_secure_port(f"[::]:{port}", server_credentials)
    
    logger.info(f"mTLS server configured on port {port}")
    logger.info(f"Certificates directory: {cert_dir}")
    logger.info(f"CA certificate: {ca_cert_file}")
    logger.info(f"Server certificate: {server_cert_file}")
    
    # Display information about existing client certificates
    clients = cert_manager.list_client_certificates()
    if clients:
        logger.info(f"Existing client certificates:")
        for user_id, (cert_path, key_path) in clients.items():
            logger.info(f"   - {user_id}: {cert_path}")
    else:
        logger.info("No client certificates found. Create some with:")
        logger.info("   python -m hwman.grpc.certificate_cli create-client <user_id>")
    
    return server, cert_manager


def serve(
    port: str = "50051",
    cert_dir: str = "./certs",
    hostname: str = "localhost"
):
    """Start the mTLS gRPC server."""
    
    server, cert_manager = create_mtls_server(
        port=port,
        cert_dir=Path(cert_dir),
        hostname=hostname
    )
    
    logger.info("Starting mTLS gRPC server...")
    server.start()
    
    logger.info("Server is running and waiting for mTLS connections...")
    logger.info("Clients must present valid certificates signed by our CA")
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("\nServer shutting down...")
        server.stop(0)


if __name__ == "__main__":
    # Configure logging to see what's happening
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # Start the server with mTLS
    serve(
        port="50051",
        cert_dir="./certs",
        hostname="localhost"
    )
