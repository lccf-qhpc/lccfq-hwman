import logging

from hwman.grpc.protobufs_compiled.health_pb2_grpc import HealthDispatchServicer
from hwman.grpc.protobufs_compiled.health_pb2 import PingResponse


logger = logging.getLogger(__name__)

class HealthService(HealthDispatchServicer):

    def TestPing(self, request, context):
        """
        Handle the TestPing request.
        This method is called when a client sends a Ping request to the server.
        """
        logger.info(f"Received TestPing request from client {context.peer()}.")
        response = PingResponse(message="Pong")
        return response






