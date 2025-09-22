import logging
import os
import pickle
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class FitSpec:
    coordinates: np.ndarray
    data: np.ndarray
    fit_class: Any
    fit_kwargs: Dict[str, Any] = None


def fit_in_subprocess(fit_spec: FitSpec) -> Tuple[Any, np.ndarray, float] | None:
    """
    Run fitting in a subprocess to avoid lmfit hanging issues.
    Returns the same objects as _fit_and_snr: (fit_result, residuals, snr)

    Args:
        fit_spec: FitSpec containing the coordinates, data and fit class to use

    Returns:
        Tuple of (fit_result, residuals, snr) or None if fitting fails
    """
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pkl') as tmp_input:
        pickle.dump(fit_spec, tmp_input)
        input_path = tmp_input.name

    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pkl') as tmp_output:
        output_path = tmp_output.name

    fit_script = f'''
import pickle
import numpy as np
from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class FitSpec:
    coordinates: Any
    data: Any
    fit_class: Any
    fit_kwargs: Dict[str, Any] = None

try:
    # Load input data
    with open('{input_path}', 'rb') as f:
        spec = pickle.load(f)

    # Initialize fit kwargs if not provided
    fit_kwargs = spec.fit_kwargs or {{}}

    # Perform the fit
    fit = spec.fit_class(spec.coordinates, spec.data, **fit_kwargs)
    fit_result = fit.run(fit)
    fit_curve = fit_result.eval()
    residuals = spec.data - fit_curve

    # Calculate SNR
    amp = fit_result.params["A"].value
    noise = np.std(residuals)
    snr = amp/(4*noise)

    # Save results
    result = {{
        'fit_result': fit_result,
        'residuals': residuals,
        'snr': snr,
        'success': True
    }}

    with open('{output_path}', 'wb') as f:
        pickle.dump(result, f)

    print("FIT_SUCCESS")

except Exception as e:
    # Save error information
    error_result = {{
        'error': str(e),
        'success': False
    }}

    with open('{output_path}', 'wb') as f:
        pickle.dump(error_result, f)

    print(f"FIT_ERROR: {{e}}, {{type(e)}}")
'''

    try:
        result = subprocess.run(
            [sys.executable, '-c', fit_script],
            capture_output=True, text=True, timeout=60
        )

        if result.returncode == 0 and "FIT_SUCCESS" in result.stdout:
            # Load successful results
            with open(output_path, 'rb') as f:
                fit_data = pickle.load(f)

            if fit_data['success']:
                return fit_data['fit_result'], fit_data['residuals'], fit_data['snr']
            else:
                logger.error(f"Fitting failed: {fit_data.get('error', 'Unknown error')}")
                return None
        else:
            logger.error(f"Fitting subprocess failed: {result.stderr}")
            logger.error(f"Stdout: {result.stdout}")
            return None

    except subprocess.TimeoutExpired:
        logger.error("Fitting subprocess timed out")
        return None
    except Exception as e:
        logger.error(f"Error running fitting subprocess: {e}")
        return None
    finally:
        # Clean up temporary files
        try:
            os.unlink(input_path)
        except OSError:
            pass
        try:
            os.unlink(output_path)
        except OSError:
            pass


def serialize_params(params):
    return {n: dict(value=v.value, error=v.stderr) for n, v in params.items()}