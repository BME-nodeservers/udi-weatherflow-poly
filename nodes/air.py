#!/usr/bin/env python3
"""
Polyglot v3 node server for WeatherFlow Weather Station data.
Copyright (c) 2018,2019,2021 Robert Paauwe
"""
import udi_interface
import json
import math
import sys
from nodes import derived

LOGGER = udi_interface.LOGGER

class AirNode(udi_interface.Node):
    id = 'air'
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
            {'driver': 'BATLVL', 'value': 0, 'uom': 72},   # battery

            ]
    units = {}

    def __init__(self, polyglot, primary, address, name):
        super(AirNode, self).__init__(polyglot, primary, address, name)

        self.elevation = 0  # needed for pressure conversion
        self.trend = []
        self.windspeed = 0  

    def update(self, obs):
        # process air data
        try:
            tm = obs[0][0] # ts
            p = obs[0][1]  # pressure
            t = obs[0][2]  # temp
            h = obs[0][3]  # humidity
            ls = obs[0][4] # strikes
            ld = obs[0][5] # distance
            bv = obs[0][6] # battery

            sl = derived.toSeaLevel(p, self.elevation)
            trend = derived.updateTrend(p, self.trend)
            
            try:
                fl = derived.ApparentTemp(t, self.windspeed/3.6, h)
                dp = derived.Dewpoint(t, h)
                hi = derived.Heatindex(t, h)
                wc = derived.Windchill(t, self.windspeed)
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
        self.setDriver('CLITEMP', t, uom=uom)
        self.setDriver('GV0', fl, uom=uom)
        self.setDriver('DEWPT', dp, uom=uom)
        self.setDriver('HEATIX', hi, uom=uom)
        self.setDriver('WINDCH', wc, uom=uom)

        # pressures p, sl  (conversions)
        if self.units['pressure'] == 'inhg':
            p = round(p * 0.02952998751, 3)
            sl = round(sl * 0.02952998751, 3)
            uom = 23
        elif self.units['pressure'] == 'hpa':
            uom = 118
        else:
            uom = 117
        self.setDriver('ATMPRES', sl, uom=uom)
        self.setDriver('BARPRES', p, uom=uom)


        # distance ld  (conversions)
        if self.units['distance'] == 'mi':
            ld = round(ld / 1.609344, 1)
            uom = 116
        else:
            uom = 83
        self.setDriver('DISTANC', ld, uom=uom)

        # humidity h, strikes ls, battery bv, and trend (no conversions)
        self.setDriver('CLIHUM', h)
        self.setDriver('BATLVL', bv)
        self.setDriver('GV1', trend)
        self.setDriver('GV2', ls)

