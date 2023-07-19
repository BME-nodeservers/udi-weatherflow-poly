#!/usr/bin/env python3
"""
Polyglot v3 node server for WeatherFlow Weather Station data.
Copyright (c) 2018,2019,2021 Robert Paauwe
"""
import udi_interface
import json
import math
import datetime
import sys

LOGGER = udi_interface.LOGGER

class NCRainNode(udi_interface.Node):
    id = 'ncrain'
    drivers = [
            {'driver': 'GV2',     'value': 0, 'uom': 82, 'name': 'Hourly Rain'}, # hourly
            {'driver': 'PRECIP',  'value': 0, 'uom': 82, 'name': 'Daily Rain'}, # daily
            {'driver': 'GV3',     'value': 0, 'uom': 82, 'name': 'Weekly Rain'}, # weekly
            {'driver': 'GV4',     'value': 0, 'uom': 82, 'name': 'Monthly Rain'}, # monthly
            {'driver': 'GV5',     'value': 0, 'uom': 82, 'name': 'Yearly Rain'}, # yearly
            {'driver': 'GV6',     'value': 0, 'uom': 82, 'name': 'Rain Yesterday'}, # yesterday
            ]

    units = {}

    def __init__(self, polyglot, primary, address, name):
        super(NCRainNode, self).__init__(polyglot, primary, address, name)

        self.prev = datetime.datetime.now()
        self.device_type = ''
        self.rd = {
                'nc_hourly': 0,
                'nc_daily': 0,
                'nc_weekly': 0,
                'nc_monthly': 0,
                'nc_yearly': 0,
                'nc_yesterday': 0
                }
        
    def rain_update(self, current_rain):
        # Update the accumulators and drivers
        now = datetime.datetime.now()
        (y, w, d) = now.isocalendar()

        if now.hour != self.prev.hour:
            self.rd['nc_hourly'] = 0 
        self.rd['nc_hourly'] += current_rain

        if now.day != self.prev.day:
            self.rd['nc_yesterday'] = self.rd['daily']
            self.rd['nc_daily'] = 0
        self.rd['nc_daily'] += current_rain

        if w != self.prev.isocalendar()[1]:
            self.rd['nc_weekly'] = 0
        self.rd['nc_weekly'] += current_rain

        if now.month != self.prev.month:
            self.rd['nc_monthly'] = 0
        self.rd['nc_monthly'] += current_rain

        if now.year != self.prev.year:
            self.rd['nc_yearly'] = 0
        self.rd['nc_yearly'] += current_rain

        # convert rain values if neccessary
        if self.units['rain'] == 'in':
            uom = 105  # inches
            self.setDriver('PRECIP', round(self.rd['nc_daily'] * 0.03937, 2), uom=uom)
            self.setDriver('GV2', round(self.rd['nc_hourly'] * 0.03937, 2), uom=uom)
            self.setDriver('GV3', round(self.rd['nc_weekly'] * 0.03937, 2), uom=uom)
            self.setDriver('GV4', round(self.rd['nc_monthly'] * 0.03937, 2), uom=uom)
            self.setDriver('GV5', round(self.rd['nc_yearly'] * 0.03937, 2), uom=uom)
            self.setDriver('GV6', round(self.rd['nc_yesterday'] * 0.03937, 2), uom=uom)
        else:
            uom = 82 # mm
            self.setDriver('PRECIP', round(self.rd['nc_daily'], 3), uom=uom)
            self.setDriver('GV2', round(self.rd['nc_hourly'], 3), uom=uom)
            self.setDriver('GV3', round(self.rd['nc_weekly'], 3), uom=uom)
            self.setDriver('GV4', round(self.rd['nc_monthly'], 3), uom=uom)
            self.setDriver('GV5', round(self.rd['nc_yearly'], 3), uom=uom)
            self.setDriver('GV6', round(self.rd['nc_yesterday'], 3), uom=uom)

        self.prev = now

    def update(self, obs, force):
        try:
            tm = obs[0][0]  # epoch

            # NC Rain value from obs
            ra = float(obs[0][14]) if self.device_type == 'SK' else float(obs[0][19])

            self.rain_update(ra)

        except Exception as e:
            LOGGER.error('Failure in NCRain data: ' + str(e))

