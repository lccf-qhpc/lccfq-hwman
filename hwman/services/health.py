import logging

import grpc
from hwman.grpc.protobufs_compiled.health_pb2_grpc import HealthDispatchServicer  # type: ignore
from hwman.grpc.protobufs_compiled.health_pb2 import PingResponse, Ping  # type: ignore


logger = logging.getLogger(__name__)


class HealthService(HealthDispatchServicer):
    def TestPing(self, request: Ping, context: grpc.ServicerContext) -> PingResponse:
        """
        Handle the TestPing request.
        This method is called when a client sends a Ping request to the server.
        """
        logger.info(f"Received TestPing request from client {context.peer()}.")
        response = PingResponse(message="Pong")
        return response
