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

class SkyNode(udi_interface.Node):
    id = 'sky'
    drivers = [
            {'driver': 'SPEED', 'value': 0, 'uom': 32},  # speed
            {'driver': 'WINDDIR', 'value': 0, 'uom': 76}, # direction
            {'driver': 'GUST', 'value': 0, 'uom': 32}, # gust
            {'driver': 'GV1', 'value': 0, 'uom': 32}, # lull
            {'driver': 'RAINRT', 'value': 0, 'uom': 46},  # rate
            {'driver': 'PRECIP', 'value': 0, 'uom': 82}, # hourly
            {'driver': 'GV2', 'value': 0, 'uom': 82}, # daily
            {'driver': 'GV3', 'value': 0, 'uom': 82}, # weekly
            {'driver': 'GV4', 'value': 0, 'uom': 82}, # monthly
            {'driver': 'GV5', 'value': 0, 'uom': 82}, # yearly
            {'driver': 'GV6', 'value': 0, 'uom': 82},  # yesterday
            {'driver': 'UV', 'value': 0, 'uom': 71},  # UV
            {'driver': 'SOLRAD', 'value': 0, 'uom': 74},  # solar radiation
            {'driver': 'LUMIN', 'value': 0, 'uom': 36},  # Lux
            {'driver': 'BATLVL', 'value': 0, 'uom': 72},  # battery
            ]

    units = {}

    def __init__(self, polyglot, primary, address, name):
        super(SkyNode, self).__init__(polyglot, primary, address, name)

        self.windspeed = 0
        self.rain = 0
        self.rain_day = datetime.datetime.now().day
        
    def rapid_wind(self, obs):
        tm = obs[0]
        ws = obs[1] * (18 / 5)  # wind speed from m/s to kph
        wd = obs[2]

        if self.units['wind'] == 'mph':
            ws = round(ws / 1.609344, 2)
            uom = 48
        elif self.units['wind'] == 'kph':
            uom = 32
        else:  # m/s
            ws = round(wg * 5 / 18, 2)
            uom = 40
        self.setDriver('SPEED', ws, uom=uom)
        self.setDriver('WINDDIR', wd)

    def update(self, obs):
        # process sky data
        try:
            tm = obs[0][0]  # epoch
            il = obs[0][1]  # Illumination
            uv = obs[0][2]  # UV Index
            bv = obs[0][8]  # battery
            ra = float(obs[0][3])  # rain
            if (obs[0][4] is not None):
                wl = obs[0][4] * (18 / 5) # wind lull
            else:
                wl = 0
            if (obs[0][5] is not None):
                ws = obs[0][5] * (18 / 5) # wind speed
            else:
                ws = 0
            if (obs[0][6] is not None):
                wg = obs[0][6] * (18 / 5) # wind gust
            else:
                wg = 0
            wd = obs[0][7]  # wind direction
            it = obs[0][9]  # reporting interval
            sr = obs[0][10]  # solar radiation

            sky_tm = tm
            self.windspeed = ws

            # ra == mm/minute (or interval)  (conversion necessary)
            if self.rain_day != datetime.datetime.now().day:
                self.rain_day = datetime.datetime.now().day
                self.rain = 0
            self.rain += ra

            if self.units['rain'] == 'in':
                uom = 24  # in/hr
                ra = round(ra * 0.03937, 2) * 60
                self.rain = round(self.rain * 0.03937, 2)
            else:
                uom = 46 # mm/hr
                ra = ra * 60
            self.setDriver('RAINRT', ra)
            self.setDriver('PRECIP', self.rain)

            # ws, wl, wg (conversion)
            if self.units['wind'] == 'mph':
                ws = round(ws / 1.609344, 2)
                wl = round(wl / 1.609344, 2)
                wg = round(wg / 1.609344, 2)
                uom = 48
            elif self.units['wind'] == 'kph':
                uom = 32
            else:
                uom = 40
            self.setDriver('SPEED', ws, uom=uom)
            self.setDriver('GV1', wl, uom=uom)
            self.setDriver('GUST', wg, uom=uom)

            # il, uv, sr, wd (no conversion)
            self.setDriver('LUMIN', il)
            self.setDriver('UV', uv)
            self.setDriver('SOLRAD', sr)
            self.setDriver('WINDDIR', wd)
            self.setDriver('BATLVL', bv)

        except Exception as e:
            (t, v, tb) = sys.exec_info()
            LOGGER.error('Failure in SKY data: ' + str(e))
            LOGGER.error('  At: ' + str(tb.tb_lineno));

