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

from fastapi import FastAPI

logger = logging.getLogger(__name__)

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}





