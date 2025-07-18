import os
import logging
from typing import Any
import subprocess
from pathlib import Path
import time

import grpc

from instrumentserver.client.proxy import Client as ins_c

# Import the instrumentserver module to ensure it is available
from hwman.grpc.protobufs_compiled.health_pb2_grpc import HealthServicer  # type: ignore
from hwman.grpc.protobufs_compiled.health_pb2 import (  # type: ignore
    PingResponse,
    Ping,
    HealthRequest,
    InstrumentServerResponse,
)
from hwman.services import Service

logger = logging.getLogger(__name__)


class HealthService(Service, HealthServicer):
    def __init__(
        self,
        config_file: str | Path = "./serverConfig.yml",
        instrumentserver_params_file: str
        | Path = "./configs/parameter_manager-parameter_manager.json",
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
        :param args: Passed to the parent class HealthServicer.
        :param kwargs: Passed to the parent class HealthServicer.
        """

        self.config_file = Path(config_file)
        self.instrumentserver_params_file = Path(instrumentserver_params_file)
        self.instrumentserver_process: subprocess.Popen | None = None

        self.proxy_ns_name = proxy_ns_name
        self.ns_host = ns_host
        self.ns_port = ns_port
        self.pyro_nameserver_process: subprocess.Popen | None = None

        self.qick_server_process: subprocess.Popen | None = None

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

        if self.qick_server_process and self.qick_server_process.poll() is None:
            logger.info("Cleaning up qick server...")
            self._stop_qick_server()

        logger.info("HealthService cleanup completed.")

    def health_check(self) -> bool:
        """Check the health of the instrumentserver and Pyro nameserver."""
        instrumentserver_status, instrumentserver_message = (
            self._get_instrumentserver_status()
        )
        pyro_nameserver_status, pyro_nameserver_message = (
            self._get_pyro_nameserver_status()
        )
        qick_server_status, qick_server_message = self._get_qick_server_status()
        all_ok = (
            instrumentserver_status and pyro_nameserver_status and qick_server_status
        )
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

            # Loading parameters
            instrument_client = ins_c()
            params = instrument_client.get_instrument("parameter_manager")
            logger.info(f"Loading parameters from {self.instrumentserver_params_file}")
            params.fromFile(self.instrumentserver_params_file)
            logger.info("Testing parameters loaded successfully")
            if params.qubit.f_ge() is not None:
                logger.info(f"Qubit frequency: {params.qubit.f_ge()}")
            else:
                logger.error("Qubit frequency is None")
                return False, "Qubit frequency is None"

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

    def _start_qick_server(self) -> tuple[bool, str]:
        """Start the qick server via SSH to qick_board."""
        logger.info("Starting qick server...")
        if self.qick_server_process and self.qick_server_process.poll() is None:
            return False, "Qick server is already running"

        try:
            # Set the missing environment variables that are needed for QICK to work
            # Use export to ensure they are available to sudo -E
            cmd = [
                "ssh",
                "qick_board",
                "cd /home/xilinx/jupyter_notebooks/qick/pyro4 && "
                "export BOARD=ZCU216 && "
                "export VIRTUAL_ENV=/usr/local/share/pynq-venv && "
                "export XILINX_XRT=/usr && "
                "export PATH=/usr/local/share/pynq-venv/bin:$PATH && "
                "sudo -S -E /usr/local/share/pynq-venv/bin/python pyro_service.py",
            ]

            self.qick_server_process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=None,  # Inherit parent's stdout - output goes directly to console/logs
                stderr=None,  # Inherit parent's stderr
                start_new_session=True,
                text=True,
            )

            if self.qick_server_process.stdin:
                self.qick_server_process.stdin.write(f"{os.environ['QICK_PASSWORD']}\n")
                self.qick_server_process.stdin.flush()
            time.sleep(20)
            logger.info("Qick server started successfully")
            return True, f"Qick server started with PID: {self.qick_server_process.pid}"

        except Exception as e:
            logger.error(f"Failed to start qick server: {e}")
            return False, f"Failed to start qick server: {e}"

    def _stop_qick_server(self) -> tuple[bool, str]:
        """Stop the qick server subprocess."""
        logger.info("Stopping qick server...")
        if not self.qick_server_process or self.qick_server_process.poll() is not None:
            return False, "Qick server is not running"

        try:
            # First, kill the remote pyro_service.py processes via SSH
            logger.info("Attempting to kill remote pyro_service.py processes...")

            kill_cmd = [
                "ssh",
                "qick_board",
                f"echo '{os.environ['QICK_PASSWORD']}' | sudo -S pkill -f 'pyro_service.py'",
            ]

            kill_process = subprocess.Popen(
                kill_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )

            stdout, stderr = kill_process.communicate(timeout=10)
            logger.info(
                f"Remote kill command completed with return code: {kill_process.returncode}"
            )

            # Then terminate the local SSH connection
            self.qick_server_process.terminate()
            self.qick_server_process.wait(timeout=5)

            logger.info("Qick server stopped successfully")
            return True, "Qick server stopped successfully"

        except subprocess.TimeoutExpired:
            logger.warning("Qick server did not terminate gracefully, killing it")

            # Force kill the remote processes
            try:
                logger.info(
                    "Attempting force kill of remote pyro_service.py processes..."
                )
                force_kill_cmd = [
                    "ssh",
                    "qick_board",
                    f"echo '{os.environ['QICK_PASSWORD']}' | sudo -S pkill -9 -f 'pyro_service.py'",
                ]

                force_kill_process = subprocess.Popen(
                    force_kill_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )

                force_kill_process.communicate(timeout=5)
                logger.info("Force kill of remote processes completed")

            except Exception as force_kill_error:
                logger.error(
                    f"Failed to force kill remote processes: {force_kill_error}"
                )

            # Kill the local SSH connection
            self.qick_server_process.kill()
            return True, "Qick server killed (did not terminate gracefully)"
        except Exception as e:
            logger.error(f"Failed to stop qick server: {e}")
            return False, f"Failed to stop qick server: {e}"

    def _get_qick_server_status(self) -> tuple[bool, str]:
        """Get the status of the qick server subprocess."""
        if not self.qick_server_process:
            return False, "Qick server has never been started"

        # Check if local SSH process is still running
        local_ssh_running = self.qick_server_process.poll() is None

        if not local_ssh_running:
            return (
                False,
                f"Qick server SSH connection is not running (exit code: {self.qick_server_process.returncode})",
            )

        # Check if the remote pyro_service.py processes are actually running
        try:
            check_cmd = ["ssh", "qick_board", "pgrep -f 'pyro_service.py'"]

            check_process = subprocess.Popen(
                check_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )

            stdout, stderr = check_process.communicate(timeout=5)

            if check_process.returncode == 0:
                # Process found, extract PIDs
                remote_pids = stdout.strip().replace("\n", ", ")
                return (
                    True,
                    f"Qick server is running - SSH PID: {self.qick_server_process.pid}, Remote PIDs: {remote_pids}",
                )
            else:
                return (
                    False,
                    f"Qick server SSH connection is running (PID: {self.qick_server_process.pid}) but remote pyro_service.py processes are not found",
                )

        except subprocess.TimeoutExpired:
            return (
                False,
                f"Qick server SSH connection is running (PID: {self.qick_server_process.pid}) but unable to check remote process status (timeout)",
            )
        except Exception as e:
            return (
                False,
                f"Qick server SSH connection is running (PID: {self.qick_server_process.pid}) but unable to check remote process status: {e}",
            )

    def StartQickServer(
        self, request: HealthRequest, context: grpc.ServicerContext
    ) -> InstrumentServerResponse:
        """
        Handle the StartQickServer request.
        This method starts the qick server via SSH.
        """
        logger.info(f"Received StartQickServer request from client {context.peer()}.")
        success, message = self._start_qick_server()

        response = InstrumentServerResponse(
            message=message, success=success, is_running=success
        )
        return response

    def StopQickServer(
        self, request: HealthRequest, context: grpc.ServicerContext
    ) -> InstrumentServerResponse:
        """
        Handle the StopQickServer request.
        This method stops the qick server subprocess.
        """
        logger.info(f"Received StopQickServer request from client {context.peer()}.")
        success, message = self._stop_qick_server()

        response = InstrumentServerResponse(
            message=message, success=success, is_running=not success
        )
        return response

    def GetQickServerStatus(
        self, request: HealthRequest, context: grpc.ServicerContext
    ) -> InstrumentServerResponse:
        """
        Handle the GetQickServerStatus request.
        This method returns the current status of the qick server subprocess.
        """
        logger.info(
            f"Received GetQickServerStatus request from client {context.peer()}."
        )
        is_running, message = self._get_qick_server_status()

        response = InstrumentServerResponse(
            message=message,
            success=True,  # The status check itself is always successful
            is_running=is_running,
        )
        return response
