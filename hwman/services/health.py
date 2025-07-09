import logging
import subprocess
from pathlib import Path

import grpc

# Import the instrumentserver module to ensure it is available
import instrumentserver
from hwman.grpc.protobufs_compiled.health_pb2_grpc import HealthDispatchServicer  # type: ignore
from hwman.grpc.protobufs_compiled.health_pb2 import (  # type: ignore
    PingResponse, 
    Ping, 
    InstrumentServerRequest, 
    InstrumentServerResponse
)
from hwman.services import Service

logger = logging.getLogger(__name__)


class HealthService(Service ,HealthDispatchServicer):
    def __init__(self, config_file: str | Path = "./serverConfig.yml"):
        self.config_file = Path(config_file)
        self.instrumentserver_process: subprocess.Popen | None = None

    def TestPing(self, request: Ping, context: grpc.ServicerContext) -> PingResponse:
        """
        Handle the TestPing request.
        This method is called when a client sends a Ping request to the server.
        """
        logger.info(f"Received TestPing request from client {context.peer()}.")
        response = PingResponse(message="Pong")
        return response

    def _start_instrumentserver(self) -> tuple[bool, str]:
        """Start the instrumentserver subprocess."""
        if self.instrumentserver_process and self.instrumentserver_process.poll() is None:
            return False, "Instrumentserver is already running"
        
        try:
            cmd = ["uv", "run", "instrumentserver", "--gui", "False", "-c", str(self.config_file)]

            self.instrumentserver_process = subprocess.Popen(
                cmd,
                start_new_session=True,  # Create subprocess in new session to avoid threading issues
                text=True
            )
            logger.info(f"Started instrumentserver with PID: {self.instrumentserver_process.pid}")
            return True, f"Instrumentserver started with PID: {self.instrumentserver_process.pid}"
        except Exception as e:
            logger.error(f"Failed to start instrumentserver: {e}")
            return False, f"Failed to start instrumentserver: {e}"

    def _stop_instrumentserver(self) -> tuple[bool, str]:
        """Stop the instrumentserver subprocess."""
        if not self.instrumentserver_process or self.instrumentserver_process.poll() is not None:
            return False, "Instrumentserver is not running"
        
        try:
            self.instrumentserver_process.terminate()
            self.instrumentserver_process.wait(timeout=5)
            logger.info("Instrumentserver stopped successfully")
            return True, "Instrumentserver stopped successfully"
        except subprocess.TimeoutExpired:
            logger.warning("Instrumentserver did not terminate gracefully, killing it")
            self.instrumentserver_process.kill()
            return True, "Instrumentserver killed (did not terminate gracefully)"
        except Exception as e:
            logger.error(f"Failed to stop instrumentserver: {e}")
            return False, f"Failed to stop instrumentserver: {e}"

    def _get_instrumentserver_status(self) -> tuple[bool, str]:
        """Get the status of the instrumentserver subprocess."""
        if not self.instrumentserver_process:
            return False, "Instrumentserver has never been started"
        
        if self.instrumentserver_process.poll() is None:
            return True, f"Instrumentserver is running with PID: {self.instrumentserver_process.pid}"
        else:
            return False, f"Instrumentserver is not running (exit code: {self.instrumentserver_process.returncode})"

    def cleanup(self) -> None:
        """Clean up the instrumentserver process if it's running."""
        if self.instrumentserver_process and self.instrumentserver_process.poll() is None:
            logger.info("Cleaning up instrumentserver...")
            self._stop_instrumentserver()

    def StartInstrumentServer(self, request: InstrumentServerRequest, context: grpc.ServicerContext) -> InstrumentServerResponse:
        """
        Handle the StartInstrumentServer request.
        This method starts the instrumentserver subprocess.
        """
        logger.info(f"Received StartInstrumentServer request from client {context.peer()}.")
        logger.warning("Hello I am reaching here")
        success, message = self._start_instrumentserver()
        is_running = success
        
        response = InstrumentServerResponse(
            message=message,
            success=success,
            is_running=is_running
        )
        return response

    def StopInstrumentServer(self, request: InstrumentServerRequest, context: grpc.ServicerContext) -> InstrumentServerResponse:
        """
        Handle the StopInstrumentServer request.
        This method stops the instrumentserver subprocess.
        """
        logger.info(f"Received StopInstrumentServer request from client {context.peer()}.")
        success, message = self._stop_instrumentserver()
        is_running = not success if success else False
        
        response = InstrumentServerResponse(
            message=message,
            success=success,
            is_running=is_running
        )
        return response

    def GetInstrumentServerStatus(self, request: InstrumentServerRequest, context: grpc.ServicerContext) -> InstrumentServerResponse:
        """
        Handle the GetInstrumentServerStatus request.
        This method returns the current status of the instrumentserver subprocess.
        """
        logger.info(f"Received GetInstrumentServerStatus request from client {context.peer()}.")
        is_running, message = self._get_instrumentserver_status()
        
        response = InstrumentServerResponse(
            message=message,
            success=True,  # The status check itself is always successful
            is_running=is_running
        )
        return response
