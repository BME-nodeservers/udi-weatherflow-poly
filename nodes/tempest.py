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
from nodes import derived

LOGGER = udi_interface.LOGGER

class TempestNode(udi_interface.Node):
    id = 'tempest'
    drivers = [
            {'driver': 'CLITEMP', 'value': 0, 'uom': 17},  # temperature
            {'driver': 'CLIHUM', 'value': 0, 'uom': 22},   # humidity
            {'driver': 'ATMPRES', 'value': 0, 'uom': 117}, # abs (station) press
            {'driver': 'BARPRES', 'value': 0, 'uom': 117}, # rel (sealevel) press
            {'driver': 'GV0', 'value': 0, 'uom': 17},      # feels like
            {'driver': 'DEWPT', 'value': 0, 'uom': 17},    # dewpoint
            {'driver': 'HEATIX', 'value': 0, 'uom': 17},   # heat index
            {'driver': 'WINDCH', 'value': 0, 'uom': 17},   # windchill
            {'driver': 'GV1', 'value': 0, 'uom': 25},      # pressure trend
            {'driver': 'GV2', 'value': 0, 'uom': 25},      # lightning Strikes
            {'driver': 'DISTANC', 'value': 0, 'uom': 83},  # lightning Distance
            {'driver': 'SPEED', 'value': 0, 'uom': 32},  # speed
            {'driver': 'WINDDIR', 'value': 0, 'uom': 76}, # direction
            {'driver': 'GUST', 'value': 0, 'uom': 32}, # gust
            {'driver': 'GV3', 'value': 0, 'uom': 76}, # gust direction
            {'driver': 'GV4', 'value': 0, 'uom': 32}, # lull
            {'driver': 'RAINRT', 'value': 0, 'uom': 46},  # rate
            {'driver': 'GV5', 'value': 0, 'uom': 82}, # hourly
            {'driver': 'PRECIP', 'value': 0, 'uom': 82}, # daily
            {'driver': 'GV6', 'value': 0, 'uom': 82}, # weekly
            {'driver': 'GV7', 'value': 0, 'uom': 82}, # monthly
            {'driver': 'GV8', 'value': 0, 'uom': 82}, # yearly
            {'driver': 'GV9', 'value': 0, 'uom': 82},  # yesterday
            {'driver': 'UV', 'value': 0, 'uom': 71},  # UV
            {'driver': 'SOLRAD', 'value': 0, 'uom': 74},  # solar radiation
            {'driver': 'LUMIN', 'value': 0, 'uom': 36},  # Lux
            {'driver': 'BATLVL', 'value': 0, 'uom': 72},  # battery

            ]
    units = {}

    def __init__(self, polyglot, primary, address, name):
        super(TempestNode, self).__init__(polyglot, primary, address, name)

        self.elevation = 0  # needed for pressure conversion
        self.trend = []
        self.prev = datetime.datetime.now()
        self.rd = {
                'hourly': 0,
                'daily': 0,
                'weekly': 0,
                'monthly': 0,
                'yearly': 0,
                'yesterday': 0
                }
        
    def rain_update(self, current_rain, force=False):
        # Update the accumulators and drivers
        now = datetime.datetime.now()
        (y, w, d) = now.isocalendar()

        if now.hour != self.prev.hour:
            self.rd['hourly'] = 0
        self.rd['hourly'] += current_rain
        if now.day != self.prev.day:
            self.rd['yesterday'] = self.rd['daily']
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
            self.setDriver('PRECIP', round(self.rd['daily'] * 0.03937, 2), uom=uom, force=force)
            self.setDriver('GV5', round(self.rd['hourly'] * 0.03937, 2), uom=uom, force=force)
            self.setDriver('GV6', round(self.rd['weekly'] * 0.03937, 2), uom=uom, force=force)
            self.setDriver('GV7', round(self.rd['monthly'] * 0.03937, 2), uom=uom, force=force)
            self.setDriver('GV8', round(self.rd['yearly'] * 0.03937, 2), uom=uom, force=force)
            self.setDriver('GV9', round(self.rd['yesterday'] * 0.03937, 2), uom=uom, force=force)
        else:
            uom = 82 # mm
            self.setDriver('PRECIP', round(self.rd['daily'], 3), uom=uom, force=force)
            self.setDriver('GV5', round(self.rd['hourly'], 3), uom=uom, force=force)
            self.setDriver('GV6', round(self.rd['weekly'], 3), uom=uom, force=force)
            self.setDriver('GV7', round(self.rd['monthly'], 3), uom=uom, force=force)
            self.setDriver('GV8', round(self.rd['yearly'], 3), uom=uom, force=force)
            self.setDriver('GV9', round(self.rd['yesterday'], 3), uom=uom, force=force)

        self.prev = now

    def rapid_wind(self, obs, force=False):
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
        self.setDriver('SPEED', ws, uom=uom, force=force)
        self.setDriver('WINDDIR', wd, force=force)

    def update(self, obs, force=False):
        # process air data
        try:
            tm = obs[0][0] # ts
            wd = obs[0][4]  # wind direction
            p = obs[0][6]   # pressure
            t = obs[0][7]   # temp
            h = obs[0][8]   # humidity
            il = obs[0][9]  # Illumination
            uv = obs[0][10] # UV Index
            sr = obs[0][11] # solar radiation
            ra = float(obs[0][12])  # rain
            ls = obs[0][14] # strikes
            ld = obs[0][15] # distance
            bv = obs[0][16] # battery
            it = obs[0][17] # reporting interval

            # convert wind speed from m/s to kph
            if (obs[0][1] is not None):
                wl = obs[0][1] * (18 / 5) # wind lull
            else:
                wl = 0
            if (obs[0][2] is not None):
                ws = obs[0][2] * (18 / 5) # wind speed
            else:
                ws = 0
            if (obs[0][3] is not None):
                wg = obs[0][3] * (18 / 5) # wind gust
            else:
                wg = 0

            sl = derived.toSeaLevel(p, self.elevation)
            trend = derived.updateTrend(p, self.trend)
            
            try:
                fl = derived.ApparentTemp(t, ws/3.6, h)
                dp = derived.Dewpoint(t, h)
                hi = derived.Heatindex(t, h)
                wc = derived.Windchill(t, ws)
            except Exception as e:
                LOGGER.error('Failure to calculate Air temps: ' + str(e))

        except Exception as e:
            (t, v, tb) = sys.exec_info()
            LOGGER.error('Failure in processing AIR data: ' + str(e))
            LOGGER.error('  At: ' + str(tb.tb_lineno));

        # temperatures t, fl, dp, hi, wc  (conversions)
        if self.units['temperature'] != 'c':
            t = round((t * 1.8) + 32, 2)  # convert to F
            fl = round((fl * 1.8) + 32, 2)  # convert to F
            dp = round((dp * 1.8) + 32, 2)  # convert to F
            hi = round((hi * 1.8) + 32, 2)  # convert to F
            wc = round((wc * 1.8) + 32, 2)  # convert to F
            uom = 17
        else:
            uom = 4
        self.setDriver('CLITEMP', t, uom=uom, force=force)
        self.setDriver('GV0', fl, uom=uom, force=force)
        self.setDriver('DEWPT', dp, uom=uom, force=force)
        self.setDriver('HEATIX', hi, uom=uom, force=force)
        self.setDriver('WINDCH', wc, uom=uom, force=force)

        # pressures p, sl  (conversions)
        if self.units['pressure'] == 'inhg':
            p = round(p * 0.02952998751, 3)
            sl = round(sl * 0.02952998751, 3)
            uom = 23
        elif self.units['pressure'] == 'hpa':
            uom = 118
        else:
            uom = 117
        self.setDriver('ATMPRES', sl, uom=uom, force=force)
        self.setDriver('BARPRES', p, uom=uom, force=force)

        # distance ld  (conversions)
        if self.units['distance'] == 'mi':
            ld = round(ld / 1.609344, 1)
            uom = 116
        else:
            uom = 83
        self.setDriver('DISTANC', ld, uom=uom, force=force)

        # humidity h, strikes ls, battery bv, and trend (no conversions)
        self.setDriver('CLIHUM', h, force=force)
        self.setDriver('BATLVL', bv, force=force)
        self.setDriver('GV1', trend, force=force)
        self.setDriver('GV2', ls, force=force)

        # ra == mm/minute (or interval)  (conversion necessary)
        self.rain_update(ra, force)
        if self.units['rain'] == 'in':
            uom = 24  # in/hr
            ra = round((ra * 0.03937 * 60), 3)
        else:
            uom = 46 # mm/hr
            ra = round((ra * 60), 3)
        self.setDriver('RAINRT', ra, uom=uom, force=force)

        # ws, wl, wg (conversion)
        if self.units['wind'] == 'mph':
            ws = round(ws / 1.609344, 2)
            wl = round(wl / 1.609344, 2)
            wg = round(wg / 1.609344, 2)
            uom = 48
        elif self.units['wind'] == 'kph':
            ws = round(ws, 2)
            wl = round(wl, 2)
            wg = round(wg, 2)
            uom = 32
        else:  # m/s
            ws = round(ws * 5 / 18, 2)
            wl = round(wl * 5 / 18, 2)
            wg = round(wg * 5 / 18, 2)
            uom = 40
        self.setDriver('SPEED', ws, uom=uom, force=force)
        self.setDriver('GV4', wl, uom=uom, force=force)
        self.setDriver('GUST', wg, uom=uom, force=force)

        # il, uv, sr, wd (no conversion)
        self.setDriver('LUMIN', il, force=force)
        self.setDriver('UV', uv, force=force)
        self.setDriver('SOLRAD', sr, force=force)
        self.setDriver('WINDDIR', wd, force=force)
        self.setDriver('GV3', wd, force=force)
        self.setDriver('BATLVL', bv, force=force)

