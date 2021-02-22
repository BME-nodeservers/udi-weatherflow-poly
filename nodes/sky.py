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
            {'driver': 'GV2', 'value': 0, 'uom': 82}, # hourly
            {'driver': 'PRECIP', 'value': 0, 'uom': 82}, # daily
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
        self.prev = datetime.datetime.now()
        self.rd = {
                'hourly': 0,
                'daily': 0,
                'weekly': 0,
                'monthly': 0,
                'yearly': 0
                }
        
    def rain_update(self, current_rain):
        # Update the accumulators and drivers
        now = datetime.datetime.now()
        (y, w, d) = now.isocalendar()

        if now.hour != self.prev.hour:
            self.rd['hourly'] = 0 
        self.rd['hourly'] += current_rain

        if now.day != self.prev.day:
            self.rd['daily'] = 0
        self.rd['daily'] += current_rain

        if w != self.prev.isocalendar()[1]:
            self.rd['weekly'] = 0
        self.rd['weekly'] += current_rain

        if now.month != self.prev.month:
            self.rd['monthly'] = 0
        self.rd['monthly'] += current_rain

        if now.year != self.prev.year:
            self.rd['yearly'] = 0
        self.rd['yearly'] += current_rain

        # convert rain values if neccessary
        if self.units['rain'] == 'in':
            uom = 105  # inches
            self.setDriver('PRECIP', round(self.rd['daily'] * 0.03937, 2), uom=uom)
            self.setDriver('GV2', round(self.rd['hourly'] * 0.03937, 2), uom=uom)
            self.setDriver('GV3', round(self.rd['weekly'] * 0.03937, 2), uom=uom)
            self.setDriver('GV4', round(self.rd['monthly'] * 0.03937, 2), uom=uom)
            self.setDriver('GV5', round(self.rd['yearly'] * 0.03937, 2), uom=uom)
        else:
            uom = 82 # mm
            self.setDriver('PRECIP', self.rd['daily'], uom=uom)
            self.setDriver('GV2', self.rd['hourly'], uom=uom)
            self.setDriver('GV3', self.rd['weekly'], uom=uom)
            self.setDriver('GV4', self.rd['monthly'], uom=uom)
            self.setDriver('GV5', self.rd['yearly'], uom=uom)

        self.prev = now

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
            self.rain_update(ra)

            if self.units['rain'] == 'in':
                uom = 24  # in/hr
                ra = round(ra * 0.03937, 2) * 60
            else:
                uom = 46 # mm/hr
                ra = ra * 60
            self.setDriver('RAINRT', ra)

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

