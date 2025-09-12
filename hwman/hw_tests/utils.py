import uuid
from typing import Any

import labcore.instruments.qick.qick_sweep_v2 as qick_sweep_v2
from instrumentserver.client import Client
from labcore.instruments.qick.config import QBoardConfig
from qick.asm_v2 import QickSweep1D


def generate_id():
    return str(uuid.uuid4())[:8]


def set_bandpass_filters(conf_: QBoardConfig):
    conf_.config()
    # Setting bandpass filters for DAC
    conf_.soc.rfb_set_gen_filter(
        conf_.config()[1]["q_gen_ch"],
        fc=conf_.config()[1]["q_ge"] / 1000,
        ftype="bandpass",
        bw=1.0,
    )  # Frequency units ere are in GHz
    conf_.soc.rfb_set_gen_filter(
        conf_.config()[1]["ro_gen_ch"],
        fc=conf_.config()[1]["ro_freq"] / 1000,
        ftype="bandpass",
        bw=1.0,
    )  # Frequency units ere are in GHz
    conf_.soc.rfb_set_ro_filter(
        conf_.config()[1]["ro_ch"],
        fc=conf_.config()[1]["ro_freq"] / 1000,
        ftype="bandpass",
        bw=1.0,
    )  # Frequency units ere are in GHz

    # Set attenuator on DAC.
    conf_.soc.rfb_set_gen_rf(
        conf_.config()[1]["q_gen_ch"], 5, 5
    )  # Frequency units ere are in GHz
    conf_.soc.rfb_set_gen_rf(
        conf_.config()[1]["ro_gen_ch"], 5, 15
    )  # Frequency units ere are in GHz
    # Set attenuator on ADC.
    conf_.soc.rfb_set_ro_rf(
        conf_.config()[1]["ro_ch"], 0
    )  # Frequency units ere are in GHz


instruments = Client()
params = instruments.get_instrument("parameter_manager")


class QickConfig(QBoardConfig):
    def config_(self) -> dict[str, Any]:
        global params

        cfg = {
            # General measurement-related parameters
            "reps": params.msmt.reps(),  # Repeition number
            "soft_avgs": params.msmt.soft_avgs(),  # Soft averaging number
            "steps": params.msmt.steps(),  # Number of steps for first sweep dimension
            "steps2": params.msmt.steps2(),  # Number of steps for second sweep dimension
            "trig_time": params.msmt.trig_time(),  # ADC trigger offset time caused by electrical delay
            "final_delay": params.msmt.final_delay(),  # Delay after the measurement is done (10*T1 is recommended)
            # Readout resonator
            "ro_gen_ch": params.readout.dac_ch(),  # Generator for RO resonator
            "ro_ch": params.readout.adc_ch(),  # Receiver for RO resonator
            "ro_nqz": params.readout.nqz(),  # Nyquist zone for RO resonator; depends on your firmware & hardware
            "ro_freq": params.readout.f_res(),  # Resonance frequency of RO resonator (MHz)
            "ro_freqs": QickSweep1D(
                "ro_freq_loop", params.readout.start_f(), params.readout.end_f()
            ),  # 1D loop for RO resonator frequency sweep (MHz)
            "ro_len": params.readout.length(),  # Length of RO resonator pulse (us)
            "ro_phase": params.readout.phase(),  # Phase of RO resonator pulse (degree)
            ### TODO: Is gain in voltage or power?
            "ro_gain": params.readout.gain(),  # Gain of RO resonator pulse (arb unit, [-1, 1])
            "ro_gains": QickSweep1D(
                "ro_gain_loop", params.readout.start_g(), params.readout.end_g()
            ),  # 1D loop for RO resonator gain sweep
            # Qubit
            "q_gen_ch": params.qubit.dac_ch(),  # Generator for qubit
            "q_nqz": params.qubit.nqz(),  # Nyquist zone for qubit; depends on your firmware & hardware
            "q_ge": params.qubit.f_ge(),  # g->e transition frequency of qubit (MHz)
            "q_ges": QickSweep1D(
                "q_ge_freq_loop", params.qubit.start_ge_f(), params.qubit.end_ge_f()
            ),  # 1D loop for qubit g->e transition frequency sweep (MHz)
            "q_ge_sig": params.qubit.sigma(),  # One sigma length of Gaussian pulse for g->e (us)
            "q_flat_len": params.qubit.c_len(),  # Length of constant pulse (us)
            "q_ge_phase": params.qubit.phase(),  # Phase of qubit pulse for g->e (degree)
            "q_ge_gain": params.qubit.gain(),  # Gain of qubit pulse for g->e (arb unit, [-1, 1])
            "q_ge_gains": QickSweep1D(
                "q_ge_gain_loop", params.qubit.start_ge_g(), params.qubit.end_ge_g()
            ),  # 1D loop for qubit g->e transition power sweep (arb unit)
            ## Qubit coherence measurements
            "wait_time_T1": QickSweep1D("T1_wait_time_loop", 0, 4 * params.qubit.T1()),
            "wait_time_T2R": QickSweep1D(
                "T2R_wait_time_loop", 0, 4 * params.qubit.T2R()
            ),
            "wait_time_T2E": QickSweep1D(
                "T2E_wait_time_loop", 0, 4 * params.qubit.T2E()
            ),
            "q_ge_detuning": params.qubit.detuning(),
            "n_echoes": params.qubit.n_echo(),
        }

        return cfg


conf = QickConfig(
    params=params,
    nameserver_host="192.168.1.10",
    nameserver_name="rfsoc",
)
qick_sweep_v2.config = conf  # type: ignore[assignment]
