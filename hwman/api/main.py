"""
Filename: main.py
Author: Marcos Frenkel
Date: 2025-05-20
Version: 1.0
Description:
    This file holds the API code for the LCCF Hardware manager.

License: Apache 2.0
Contact: marcosf2@illinois.edu
"""

import logging
from pathlib import Path

from fastapi import FastAPI

from hwman.setup_measurements import execute_measurement
from hwman.measurements.dummy import generate_dummy_sweep

logger = logging.getLogger(__name__)

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/measurements/dummy")
async def dummy_measurement() -> dict[str, Path | dict[str, list[int]]]:
    """
    Dummy measurement endpoint. Writes dummy data to a file and returns data.
    """

    sweep = generate_dummy_sweep()
    data_location, data = execute_measurement(sweep, "dummy_measurement")

    ret = {}
    for ax in data.axes():
        ret[ax] = list(int(x) for x in data[ax]["values"])
    for dep in data.dependents():
        ret[dep] = list(int(x) for x in data[dep]["values"])

    return {"data_location": data_location, "data": ret}



