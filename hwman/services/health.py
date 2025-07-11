import logging
import os
from typing import Any
import subprocess
from pathlib import Path

import grpc

# Import the instrumentserver module to ensure it is available
from hwman.grpc.protobufs_compiled.health_pb2_grpc import HealthDispatchServicer  # type: ignore
from hwman.grpc.protobufs_compiled.health_pb2 import (  # type: ignore
    PingResponse,
    Ping,
    HealthRequest,
    InstrumentServerResponse,
)
from hwman.services import Service

logger = logging.getLogger(__name__)


class HealthService(Service, HealthDispatchServicer):
    def __init__(
        self,
        config_file: str | Path = "./serverConfig.yml",
        proxy_ns_name: str = "rfsoc",
        ns_host: str = "localhost",
        ns_port: int = 8888,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        HealthService: Takes care of the health of the hardware manager. Makes sure everything in the environment is
        ok to run. Provides tools to handle external resources like instrumentserver and QICK.

        :param config_file: Path to the configuration file for the instrumentserver.
        :param proxy_ns_name: Name of the Pyro nameserver proxy. Needs to match the QICK configuration.
        :param ns_host: Host of the Pyro nameserver. Should be the computer running the nameserver's IP address or hostname.
        :param ns_port: Port of the Pyro nameserver. Should match the port used by the QICK configuration.
        :param args: Passed to the parent class HealthDispatchServicer.
        :param kwargs: Passed to the parent class HealthDispatchServicer.
        """

        self.config_file = Path(config_file)
        self.instrumentserver_process: subprocess.Popen | None = None

        self.proxy_ns_name = proxy_ns_name
        self.ns_host = ns_host
        self.ns_port = ns_port
        self.pyro_nameserver_process: subprocess.Popen | None = None

        super().__init__(*args, **kwargs)

    def cleanup(self) -> None:
        """Clean up the instrumentserver and Pyro nameserver processes if they are running."""
        if (
            self.instrumentserver_process
            and self.instrumentserver_process.poll() is None
        ):
            logger.info("Cleaning up instrumentserver...")
            self._stop_instrumentserver()

        if self.pyro_nameserver_process and self.pyro_nameserver_process.poll() is None:
            logger.info("Cleaning up Pyro nameserver...")
            self._stop_pyro_nameserver()
        logger.info("HealthService cleanup completed.")

    def health_check(self) -> bool:
        """Check the health of the instrumentserver and Pyro nameserver."""
        instrumentserver_status, instrumentserver_message = (
            self._get_instrumentserver_status()
        )
        pyro_nameserver_status, pyro_nameserver_message = (
            self._get_pyro_nameserver_status()
        )
        all_ok = instrumentserver_status and pyro_nameserver_status
        return all_ok

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
        if (
            self.instrumentserver_process
            and self.instrumentserver_process.poll() is None
        ):
            return False, "Instrumentserver is already running"

        try:
            cmd = [
                "uv",
                "run",
                "instrumentserver",
                "--gui",
                "False",
                "-c",
                str(self.config_file),
            ]

            self.instrumentserver_process = subprocess.Popen(
                cmd,
                start_new_session=True,  # Create subprocess in new session to avoid threading issues
                text=True,
            )
            logger.info(
                f"Started instrumentserver with PID: {self.instrumentserver_process.pid}"
            )
            return (
                True,
                f"Instrumentserver started with PID: {self.instrumentserver_process.pid}",
            )
        except Exception as e:
            logger.error(f"Failed to start instrumentserver: {e}")
            return False, f"Failed to start instrumentserver: {e}"

    def _stop_instrumentserver(self) -> tuple[bool, str]:
        """Stop the instrumentserver subprocess."""
        if (
            not self.instrumentserver_process
            or self.instrumentserver_process.poll() is not None
        ):
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
            return (
                True,
                f"Instrumentserver is running with PID: {self.instrumentserver_process.pid}",
            )
        else:
            return (
                False,
                f"Instrumentserver is not running (exit code: {self.instrumentserver_process.returncode})",
            )

    def StartInstrumentServer(
        self, request: HealthRequest, context: grpc.ServicerContext
    ) -> InstrumentServerResponse:
        """
        Handle the StartInstrumentServer request.
        This method starts the instrumentserver subprocess.
        """
        logger.info(
            f"Received StartInstrumentServer request from client {context.peer()}."
        )
        success, message = self._start_instrumentserver()
        is_running = success

        response = InstrumentServerResponse(
            message=message, success=success, is_running=is_running
        )
        return response

    def StopInstrumentServer(
        self, request: HealthRequest, context: grpc.ServicerContext
    ) -> InstrumentServerResponse:
        """
        Handle the StopInstrumentServer request.
        This method stops the instrumentserver subprocess.
        """
        logger.info(
            f"Received StopInstrumentServer request from client {context.peer()}."
        )
        success, message = self._stop_instrumentserver()
        is_running = not success if success else False

        response = InstrumentServerResponse(
            message=message, success=success, is_running=is_running
        )
        return response

    def GetInstrumentServerStatus(
        self, request: HealthRequest, context: grpc.ServicerContext
    ) -> InstrumentServerResponse:
        """
        Handle the GetInstrumentServerStatus request.
        This method returns the current status of the instrumentserver subprocess.
        """
        logger.info(
            f"Received GetInstrumentServerStatus request from client {context.peer()}."
        )
        is_running, message = self._get_instrumentserver_status()

        response = InstrumentServerResponse(
            message=message,
            success=True,  # The status check itself is always successful
            is_running=is_running,
        )
        return response

    def _start_pyro_nameserver(self) -> tuple[bool, str]:
        logger.info("Starting Pyro nameserver...")
        if self.pyro_nameserver_process and self.pyro_nameserver_process.poll() is None:
            return False, "Instrumentserver is already running"

        cmd = [
            "pyro4-ns",
            "-n",
            self.ns_host,
            "-p",
            str(self.ns_port),
        ]
        try:
            self.pyro_nameserver_process = subprocess.Popen(
                cmd,
                env={
                    **os.environ,
                    "PYRO_SERIALIZERS_ACCEPTED": "pickle",
                    "PYRO_PICKLE_PROTOCOL_VERSION": "4",
                },
                start_new_session=True,  # Create subprocess in new session to avoid threading issues
                text=True,
            )

            logger.info("Pyro nameserver started successfully.")
            return True, "Pyro nameserver started successfully."
        except Exception as e:
            logger.error(f"Failed to start Pyro nameserver: {e}")
            return False, f"Failed to start Pyro nameserver: {e}"

    def _stop_pyro_nameserver(self) -> tuple[bool, str]:
        logger.info("Stopping Pyro nameserver...")

        if (
            not self.pyro_nameserver_process
            or self.pyro_nameserver_process.poll() is not None
        ):
            return False, "Pyro nameserver is not running."

        try:
            self.pyro_nameserver_process.terminate()
            self.pyro_nameserver_process.wait(timeout=5)
            logger.info("Pyro nameserver stopped successfully.")
            return True, "Pyro nameserver stopped successfully."
        except subprocess.TimeoutExpired:
            logger.warning("Pyro nameserver did not terminate gracefully, killing it.")
            self.pyro_nameserver_process.kill()
            return True, "Pyro nameserver killed (did not terminate gracefully)."
        except Exception as e:
            logger.error(f"Failed to stop Pyro nameserver: {e}")
            return False, f"Failed to stop Pyro nameserver: {e}"

    def _get_pyro_nameserver_status(self) -> tuple[bool, str]:
        """Get the status of the Pyro nameserver subprocess."""
        if not self.pyro_nameserver_process:
            return False, "Pyro nameserver has never been started."

        if self.pyro_nameserver_process.poll() is None:
            return (
                True,
                f"Pyro nameserver is running with PID: {self.pyro_nameserver_process.pid}",
            )
        else:
            return (
                False,
                f"Pyro nameserver is not running (exit code: {self.pyro_nameserver_process.returncode})",
            )

    def StartPyroNameserver(
        self, request: HealthRequest, context: grpc.ServicerContext
    ) -> InstrumentServerResponse:
        """
        Handle the StartPyroNameServer request.
        This method starts the Pyro nameserver subprocess.
        """
        logger.info(
            f"Received StartPyroNameserver request from client {context.peer()}."
        )
        success, message = self._start_pyro_nameserver()

        response = InstrumentServerResponse(
            message=message, success=success, is_running=success
        )
        return response

    def StopPyroNameserver(
        self, request: HealthRequest, context: grpc.ServicerContext
    ) -> InstrumentServerResponse:
        """
        Handle the StopPyroNameServer request.
        This method stops the Pyro nameserver subprocess.
        """
        logger.info(
            f"Received StopPyroNameserver request from client {context.peer()}."
        )
        success, message = self._stop_pyro_nameserver()

        response = InstrumentServerResponse(
            message=message, success=success, is_running=not success
        )
        return response

    def GetPyroNameserverStatus(
        self, request: HealthRequest, context: grpc.ServicerContext
    ) -> InstrumentServerResponse:
        """
        Handle the GetPyroNameServerStatus request.
        This method returns the current status of the Pyro nameserver subprocess.
        """
        logger.info(
            f"Received GetPyroNameserverStatus request from client {context.peer()}."
        )
        is_running, message = self._get_pyro_nameserver_status()

        response = InstrumentServerResponse(
            message=message,
            success=True,  # The status check itself is always successful
            is_running=is_running,
        )
        return response
