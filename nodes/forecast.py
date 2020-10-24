#!/usr/bin/env python3
"""
Polyglot v2 node server for WeatherFlow Weather Station data.
Copyright (c) 2018,2019,2020 Robert Paauwe
"""
import polyinterface
import sys
import time
import datetime
import json
import math
import threading

LOGGER = polyinterface.LOGGER

class ForecastNode(polyinterface.Node):
    id = 'forecast'
    units = 'metric'
    hint = [1,11,7,0]
    drivers = [
            {'driver': 'ST', 'value': 0, 'uom': 75},   # day
            {'driver': 'GV0', 'value': 0, 'uom': 4},   # high temp
            {'driver': 'GV1', 'value': 0, 'uom': 4},   # low temp
            {'driver': 'GV13', 'value': 0, 'uom': 25}, # weather
            {'driver': 'GV18', 'value': 0, 'uom': 51}, # pop
            ]

    def SetUnits(self, u):
        self.units = u
        if (u == 'c'):  # C
            self.drivers[1]['uom'] = 4
            self.drivers[2]['uom'] = 4
        elif (u == 'uk'):  # C
            self.drivers[1]['uom'] = 4
            self.drivers[2]['uom'] = 4
        elif (u == 'f'):   # F
            self.drivers[1]['uom'] = 17
            self.drivers[2]['uom'] = 17

    def setDriver(self, driver, value):
        if ((driver == 'GV0' or driver == 'GV1') and self.units == "f"):
            value = round((value * 1.8) + 32, 1)  # convert to F

        super(ForecastNode, self).setDriver(driver, value, report=True, force=True)

    def update(self, forecast):
        if 'day_num' in forecast:
            # 0 = monday (UOM should be 1)
            # 1 = tuesday (UOM should be 2)
            # 2 = wednesday (UOM should be 3)
            # 3 = thursday (UOM should be 4)
            # 4 = friday (UOM should be 5)
            # 5 = saturday (UOM should be 6)
            # 6 = sunday (UOM should be 0)
            dt = datetime.date.fromtimestamp(forecast['day_start_local'])
            self.setDriver('ST', dt.weekday() + 1)
        if 'air_temp_high' in forecast:
            self.setDriver('GV0', forecast['air_temp_high'])
        if 'air_temp_low' in forecast:
            self.setDriver('GV1', forecast['air_temp_low'])
        if 'precip_probability' in forecast:
            self.setDriver('GV18', forecast['precip_probability'])
        if 'conditions' in forecast:
            # convert conditions string to value
            condition_code = 0
            self.setDriver('GV13', condition_code)

