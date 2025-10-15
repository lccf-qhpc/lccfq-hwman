"""
Standalone script to run the QubitTuneup protocol.
This is meant to be executed as a subprocess to avoid gRPC fork issues.
"""
import logging

from hwman.hw_tests.utils import setup_measurement_env, get_params

from qcui_measurement.protocols import base as ProtocolBase
from qcui_measurement.protocols.base import PlatformTypes
from qcui_measurement.protocols.implementations.qubit_tunep import QubitTuneup


logger = logging.getLogger(__name__)


def main():
    """Execute the tuneup protocol."""
    ProtocolBase.PLATFORMTYPE = PlatformTypes.QICK

    setup_measurement_env()
    params = get_params()

    logger.info("Got params, executing")
    protocol = QubitTuneup(params)
    protocol.execute()
    logger.info("QubitTuneup protocol execution completed")


if __name__ == "__main__":
    main()