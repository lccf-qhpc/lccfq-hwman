import uuid
import logging
from pathlib import Path
from enum import Enum, auto
from dataclasses import dataclass

from instrumentserver.client import Client
from instrumentserver.client.proxy import ProxyInstrumentModule

from labcore.analysis import FitResult
from cqedtoolbox.instruments.qick import qick_sweep_v2
from cqedtoolbox.instruments.qick.config import QBoardConfig
from cqedtoolbox.protocols.configs.qick_config import QickConfig

logger = logging.getLogger(__name__)

_params = None


class DataType(Enum):
    REAL = auto()
    IMAG = auto()
    MAG = auto()


@dataclass
class TestReturn:
    data_type: DataType
    data_path: Path
    fit_result: FitResult
    snr: float
    images: list[Path]


def generate_id():
    return str(uuid.uuid4())[:8]


def set_bandpass_filters(conf_: QBoardConfig):
    # Setting badnpass filters for DAC
    conf_.soc.rfb_set_gen_filter(conf_.config()[1]['q_dac_ch'], fc=conf_.config()[1]["q_freq"] / 1000,
                                ftype='bandpass',
                                bw=1.0)  # Frequency unitsh ere are in GHz
    conf_.soc.rfb_set_gen_filter(conf_.config()[1]['ro_dac_ch'], fc=conf_.config()[1]["ro_freq"] / 1000,
                                ftype='bandpass',
                                bw=1.0)  # Frequency unitsh ere are in GHz
    conf_.soc.rfb_set_ro_filter(conf_.config()[1]['ro_adc_ch'], fc=conf_.config()[1]["ro_freq"] / 1000,
                               ftype='bandpass',
                               bw=1.0)  # Frequency unitsh ere are in GHz

    # Set attenuator on DAC.
    conf_.soc.rfb_set_gen_rf(conf_.config()[1]['q_dac_ch'], 5, 5)  # Frequency unitsh ere are in GHz
    conf_.soc.rfb_set_gen_rf(conf_.config()[1]['ro_dac_ch'], 5, 15)  # Frequency unitsh ere are in GHz
    # Set attenuator on ADC.
    conf_.soc.rfb_set_ro_rf(conf_.config()[1]['ro_adc_ch'], 0)  # Frequency unitsh ere are in GHz


def setup_measurement_env() -> QickConfig:
    global _params
    logger.debug("Getting instrumentserver client")
    instruments = Client()
    logger.debug("Getting parameter manager proxy")
    params = instruments.get_instrument("parameter_manager")
    _params = params

    conf = QickConfig(
        params=params,
        nameserver_host="192.168.1.10",
        nameserver_name="rfsoc",
    )
    qick_sweep_v2.config = conf  # type: ignore[assignment]
    return conf


def get_params() -> ProxyInstrumentModule:
    global _params
    if _params is not None:
        return _params
    raise Exception("params is not set yet")