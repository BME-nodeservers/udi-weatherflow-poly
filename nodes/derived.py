#!/usr/bin/env python3
"""
Polyglot v3 node server for WeatherFlow Weather Station data.
Copyright (c) 2018,2019,2021 Robert Paauwe

Derived metrics formulas.
"""
import math
import udi_interface
LOGGER = udi_interface.LOGGER

def Dewpoint(t, h):
    b = (17.625 * t) / (243.04 + t)
    rh = h / 100.0

    if rh <= 0:
        return 0

    c = math.log(rh)
    dewpt = (243.04 * (c + b)) / (17.625 - c - b)
    return round(dewpt, 1)

def ApparentTemp(t, ws, h):
    wv = h / 100.0 * 6.105 * math.exp(17.27 * t / (237.7 + t))
    at =  t + (0.33 * wv) - (0.70 * ws) - 4.0
    return round(at, 1)

def Windchill(t, ws):
    # really need temp in F and speed in MPH
    tf = (t * 1.8) + 32
    #mph = ws / 0.44704 # from m/s to mph
    mph = ws / 1.609  # from kph to mph

    wc = 35.74 + (0.6215 * tf) - (35.75 * math.pow(mph, 0.16)) + (0.4275 * tf * math.pow(mph, 0.16))

    if (tf <= 50.0) and (mph >= 5.0):
        return round((wc - 32) / 1.8, 1)
    else:
        return t

def Heatindex(t, h):
    tf = (t * 1.8) + 32
    c1 = -42.379
    c2 = 2.04901523
    c3 = 10.1433127
    c4 = -0.22475541
    c5 = -6.83783 * math.pow(10, -3)
    c6 = -5.481717 * math.pow(10, -2)
    c7 = 1.22874 * math.pow(10, -3)
    c8 = 8.5282 * math.pow(10, -4)
    c9 = -1.99 * math.pow(10, -6)

    hi = (c1 + (c2 * tf) + (c3 * h) + (c4 * tf * h) + (c5 * tf *tf) + (c6 * h * h) + (c7 * tf * tf * h) + (c8 * tf * h * h) + (c9 * tf * tf * h * h))

    if (tf < 80.0) or (h < 40.0):
        return t
    else:
        return round((hi - 32) / 1.8, 1)

# convert station pressure in millibars to sealevel pressure
def toSeaLevel(station, elevation):
    i = 287.05  # gas constant for dry air
    a = 9.80665 # gravity
    r = 0.0065  # standard atmosphere lapse rate
    s = 1013.35 # pressure at sealevel
    n = 288.15  # sea level temperature

    if station is None:
        return 0

    el = elevation * 1.0
    st = station * 1.0

    try:
        l = a / (i * r)

        c = i * r / a

        u = math.pow(1 + math.pow(s / st, c) * (r * el / n), l)

        slp = (round((st * u), 3))
    except Exception as e:
        LOGGER.error('Pressure conversion failed: ' + str(e.msg))
        slp = station

    return slp

# track pressures in a queue and calculate trend
def updateTrend(current, mytrend):
    t = 1  # Steady
    past = 0

    if len(mytrend) > 1:
        LOGGER.info('LAST entry = %f' % mytrend[-1])
    if len(mytrend) == 180:
        # This should be poping the last entry on the list (or the 
        # oldest item added to the list).
        past = mytrend.pop()

    if mytrend != []:
        # mytrend[0] seems to be the last entry inserted, not
        # the first.  So how do we get the last item from the
        # end of the array -- mytrend[-1]
        past = mytrend[-1]

    # calculate trend
    try:
        LOGGER.info('TREND %f to %f' % (past, current))
        if ((past - current) > 1):
            t = 0 # Falling
        elif ((past - current) < -1):
            t = 2 # Rising

        # inserts the value at index 0 and bumps all existing entries
        # up by one index
        mytrend.insert(0, current)
    except:
        LOGGER.error('Pressure value invalid. Trend not calculated.')

    return t


def hourly_accumulation(self, r):
    current_hour = datetime.datetime.now().hour
    if (current_hour != self.prev_hour):
        self.prev_hour = current_hour
        self.hourly_rain = 0

    self.hourly_rain += r
    return self.hourly_rain

def daily_accumulation(self, r):
    current_day = datetime.datetime.now().day
    if (current_day != self.prev_day):
        self.yesterday_rain = self.daily_rain
        self.prev_day = current_day
        self.daily_rain = 0

    self.daily_rain += r
    return self.daily_rain

def yesterday_accumulation(self):
    return self.yesterday_rain

def weekly_accumulation(self, r):
    (y, w, d) = datetime.datetime.now().isocalendar()
    if w != self.prev_week:
        self.prev_week = w
        self.weekly_rain = 0

    self.weekly_rain += r
    return self.weekly_rain

def monthly_accumulation(self, r):
    current_month = datetime.datetime.now().month
    if (current_month != self.prev_month):
        self.prev_month = current_month
        self.monthly_rain = 0

    self.monthly_rain += r
    return self.monthly_rain

def yearly_accumulation(self, r):
    current_year = datetime.datetime.now().year
    if (current_year != self.prev_year):
        self.prev_year = current_year
        self.yearly_rain = 0

    self.yearly_rain += r
    return self.yearly_rain

    
