#!/usr/bin/env python3
"""
Polyglot v3 node server for WeatherFlow Weather Station data.
Copyright (c) 2018,2019,2020,2021 Robert Paauwe
"""
import udi_interface
import sys
import time
import datetime
import json
import math
import threading

LOGGER = udi_interface.LOGGER

class ForecastNode(udi_interface.Node):
    id = 'forecast'
    units = 'metric'
    drivers = [
            {'driver': 'ST',   'value': 0, 'uom': 75, 'name': 'Day of Week'},   # day
            {'driver': 'GV0',  'value': 0, 'uom': 4,  'name': 'High Temperature'},   # high temp
            {'driver': 'GV1',  'value': 0, 'uom': 4,  'name': 'Low Temperature'},   # low temp
            {'driver': 'GV13', 'value': 0, 'uom': 25, 'name': 'Weather Conditions'}, # weather
            {'driver': 'POP',  'value': 0, 'uom': 51, 'name': 'Chance of Precipitation'}, # pop
            ]

    def __init__(self, polyglot, primary, address, name):
        super(ForecastNode, self).__init__(polyglot, primary, address, name)
        self.units = None


    def SetUnits(self, u):
        LOGGER.info('Setting forecast units to {}'.format(u))
        self.units = u

    def update(self, forecast, force=False):
        """
        {'day_start_local': 1613980800, 'day_num': 22, 'month_num': 2, 'conditions': 'Clear', 'icon': 'clear-day', 'sunrise': 1613918795, 'sunset': 1613958540, 'air_temp_high': 18.0, 'air_temp_low': 6.0, 'precip_probability': 10, 'precip_icon': 'chance-rain', 'precip_type': 'rain'}
        """
        if 'day_num' in forecast:
            # 0 = monday (UOM should be 1)
            # 1 = tuesday (UOM should be 2)
            # 2 = wednesday (UOM should be 3)
            # 3 = thursday (UOM should be 4)
            # 4 = friday (UOM should be 5)
            # 5 = saturday (UOM should be 6)
            # 6 = sunday (UOM should be 0)
            dt = datetime.date.fromtimestamp(forecast['day_start_local'])
            self.setDriver('ST', ((dt.weekday() + 1) % 7), True, force, 75)
        if 'air_temp_high' in forecast:
            if self.units == 'f':
                value = round((forecast['air_temp_high'] * 1.8) + 32, 1)  # convert to F
                uom = 17
            else:
                value = forecast['air_temp_high']
                uom = 4
            self.setDriver('GV0', value, True, force, uom)
        if 'air_temp_low' in forecast:
            if self.units == 'f':
                value = round((forecast['air_temp_low'] * 1.8) + 32, 1)  # convert to F
                uom = 17
            else:
                value = forecast['air_temp_low']
                uom = 4
            self.setDriver('GV1', value, True, force, uom)
        if 'precip_probability' in forecast:
            self.setDriver('POP', forecast['precip_probability'], True, force, 51)
        if 'conditions' in forecast:
            # convert conditions string to value
            if forecast['conditions'] == 'Clear':
                condition_code = 0
            elif forecast['conditions'] == 'Rain Likely':
                condition_code = 1
            elif forecast['conditions'] == 'Rain Possible':
                condition_code = 2
            elif forecast['conditions'] == 'Snow':
                condition_code = 3
            elif forecast['conditions'] == 'Snow Possible':
                condition_code = 4
            elif forecast['conditions'] == 'Wintry Mix Likely':
                condition_code = 5
            elif forecast['conditions'] == 'Wintry Mix Possible':
                condition_code = 6
            elif forecast['conditions'] == 'Thunderstorms Likely':
                condition_code = 7
            elif forecast['conditions'] == 'Thunderstorms Possible':
                condition_code = 8
            elif forecast['conditions'] == 'Windy':
                condition_code = 9
            elif forecast['conditions'] == 'Foggy':
                condition_code = 10
            elif forecast['conditions'] == 'Cloudy':
                condition_code = 11
            elif forecast['conditions'] == 'Partly Cloudy':
                condition_code = 12
            elif forecast['conditions'] == 'Very Light Rain':
                condition_code = 13
            else:
                condition_code = 14

            self.setDriver('GV13', condition_code, True, force, 25)

