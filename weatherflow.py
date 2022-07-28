#!/usr/bin/env python3
"""
Polyglot v3 node server for WeatherFlow Weather Station data.
Copyright (c) 2018,2019,2021 Robert Paauwe
"""
import udi_interface
import sys
import time
import datetime
import threading
from nodes import weatherflow

LOGGER = udi_interface.LOGGER

if __name__ == "__main__":
    try:
        polyglot = udi_interface.Interface([weatherflow.Controller])
        polyglot.start('3.0.22')
        control = weatherflow.Controller(polyglot, 'controller', 'controller', 'WeatherFlow')
        polyglot.runForever()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
