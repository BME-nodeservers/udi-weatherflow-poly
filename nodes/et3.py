# Evapotranspiration calculation taken from
#
# Step by Step Calculation of the Penman-Monteith
# Evapotranspiration (FAO-56 Methos)
# http://edis.ifas.ufl.edu/pdffiles/ae/ae45900.pdf

import math
import udi_interface

LOGGER = udi_interface.LOGGER


# Variables
tMin = 0
tMax = 0
hMin = 0
hMax = 0
solarRadiation = None
elevation = 0
plantType = 0.23
latitude = 0
windSpeed = 0
julianDay = 0


# Formulas and constants
vaporRate = 237.3
enthalpy = 17.27
kelvin = 273.15
solarConstant = 0.0820

def FtoC(f):
    return (f - 32) / 1.8

def ft2m (ft):
    return ft * 0.3048

def w2mj (watt):  # watts/m2 to megajoul/m2
    return watt * 0.0864

def mph2ms (mph): # MPH to m/s
    return mph * 0.447

def kph2ms (kph): # KPH to m/s
    return kph / 3.6

def deg2rad(deg):
    return math.pi / 180 * deg

def saturation_vapor(t): # saturation vapor pressure at temp
    return (0.6108 * math.exp((enthalpy * t) / (t + vaporRate)))

def saturation_vapor_pressure_curve_slope(t):
    # other program uses 2503 here
    top = 4098 * saturation_vapor(t)
    bottom = math.pow((t + vaporRate), 2)
    return top / bottom

def atmospheric_pressure(elevation):  # elevation in meters
    inner = ((293 - 0.0065 * elevation) / 293)
    return 101.3 * math.pow(inner, 5.26)

def psychrometric_constant(atmo): 
    return 0.000665 * atmo

def delta_term(vapor_pressure_curve_slope, psychrometric_constant, avg_ws):
    bottom = vapor_pressure_curve_slope + psychrometric_constant * (1 + 0.34 * avg_ws)
    return vapor_pressure_curve_slope / bottom

def psi_term(vapor_pressure_curve_slope, psychrometric_constant, avg_ws):
    bottom = vapor_pressure_curve_slope + psychrometric_constant * (1 + 0.34 * avg_ws)
    return psychrometric_constant / bottom

def temperature_term(mean_t, avg_ws):
    return ((900) / (mean_t + kelvin) * avg_ws)

def saturation_vapor_pressure_actual(min_t, max_t, min_h, max_h):
    rel1 = saturation_vapor(min_t) * (max_h/100)
    rel2 = saturation_vapor(max_t) * (min_h/100)
    return (rel1 + rel2) / 2

def relative_earth_sun_distance(julian_day):
    return 1 + 0.033 * math.cos(((2 * math.pi) / 365) * julian_day)

def solar_declination(julian_day):
    return 0.409 * math.sin(((2 * math.pi) / 365) * julian_day - 1.39)

def sunset_hour_angle(latitude, solar_declination):
    return math.acos(-1 * math.tan(latitude) * math.tan(solar_declination))

def extraterrestrial_radiation(diff, angle, latitude, declination):
    rel1 = 24*60 / math.pi
    rel2 = solarConstant * diff
    rel3 = ((angle * math.sin(latitude) * math.sin(declination)) + (math.cos(latitude) * math.cos(declination) * math.sin(angle)))
    return rel1 * rel2 * rel3

def clear_sky_solar_radiation(elevation, ex_radiation):
    return (0.75 + (2 * math.pow(10, -5)) * elevation) * ex_radiation

def long_wave_radiation(min_t, max_t, vp, sr, clear_sky):
    rel1 = 4.903 * math.pow(10, -9);
    rel2 = (math.pow((max_t + kelvin), 4) + math.pow((min_t + kelvin), 4)) / 2
    rel3 = (0.34 - 0.14 * math.sqrt(vp));
    rel4 = 1.35 * sr / clear_sky - 0.35;
    return rel1 * rel2 * rel3 * rel4;

# calculate the approx. solar radiation  in mega-joules/m2
def calc_solar_radiation(t_min, t_max, lat, declination, julian_day):

    Dr = 1.0 + 0.033 * math.cos(2 * math.pi / 365 * julian_day)

    omega_pre = -math.tan(lat) * math.tan(declination)
    if omega_pre > 1.0:
        omega_pre = 1.0
    elif omega_pre < -1.0:
        omega_pre = -1.0

    omega = math.acos(omega_pre)

    Ra = 24.0 / math.pi * 4.92 * Dr * (omega * math.sin(lat) * math.sin(declination) + math.cos(lat) * math.cos(declination) * math.sin(omega))

    Rs = 0.17 * math.sqrt(t_max - t_min) * Ra

    return Rs
    

# temperature in C
# elevation in meters
# latitude in degrees
# avg_ws in m/s
# solar_radiation in W/m2
def evapotranspriation(max_t, min_t, solar_radiation, avg_ws, elevation, max_h, min_h, latitude, canopy_coefficient, day):

    julian_day = day

    # step 1, mean daily air temperature C
    mean_daily_temp = (max_t + min_t) / 2.0

    # step 2, mean solar radiation in mgajoules / m2
    #Rs = w2mj(solar_radiation)

    # step 4, slope of saturation vapor pressure curve
    vp_slope = saturation_vapor_pressure_curve_slope(mean_daily_temp)

    # step 5, atmospheric pressure
    pressure = atmospheric_pressure(elevation)

    # step 6, psychrometric constant
    psychrometric = psychrometric_constant(pressure)

    # step 7, delta term
    delta = delta_term(vp_slope, psychrometric, avg_ws)

    # step 8, psi term
    psi = psi_term(vp_slope, psychrometric, avg_ws)

    # step 9, temperature term
    t_term = temperature_term(mean_daily_temp, avg_ws)

    # step 10, mean saturation vapor pressure curve
    vp_curve = (saturation_vapor(max_t) + saturation_vapor(min_t)) / 2

    # step 11, actual vapor pressure
    vp_actual = saturation_vapor_pressure_actual(min_t, max_t, min_h, max_h)

    # step 11.1, vapor pressure deficit
    vp_deficit = vp_curve - vp_actual

    # step 12.1, relative sun earth distance
    dist = relative_earth_sun_distance(julian_day)

    # step 12.2, solar declination
    declination = solar_declination(julian_day)

    # step 13, latitude in radians
    latitude_r = deg2rad(latitude)

    ## Testing solar radiation calculation
    if solar_radiation is None:
        Rs = calc_solar_radiation(min_t, max_t, latitude_r, declination, julian_day)
    else:
        Rs = w2mj(solar_radiation)

    # step 14, sunset hour angle
    angle = sunset_hour_angle(latitude_r, declination)

    # step 15, extraerrestrial radiation
    Ra = extraterrestrial_radiation(dist, angle, latitude_r, declination)

    # step 16, clear sky solar radiation
    Rso = clear_sky_solar_radiation(elevation, Ra)

    # step 17, net solar radiation
    Rns = (1 - canopy_coefficient) * Rs

    # step 18, net outgoing long wave solar radiation
    Rnl = long_wave_radiation(min_t, max_t, vp_actual, Rs, Rso)

    # step 19, net radiation
    Rn = Rns - Rnl

    # step 19.1, net radiation in mm
    Rng = Rn * 0.408

    # step FS1, radiation term ETrad
    radiation_term = delta * Rng


    # step FS2, wind term ETwind
    wind_term = psi * t_term * (vp_curve - vp_actual)

    # step final
    return radiation_term + wind_term


"""
Use the global scope'd variables instead of passing in everything. 
This is to simulate what we might do with a class that may want to
build up the values over time.  I.E. get humidity values every 5
minutes during the day and tack min/max.
"""
def get_et0():

    # step 1, mean daily air temperature C
    mean_daily_temp = (tMax + tMin) / 2.0

    # step 2, mean solar radiation in mgajoules / m2
    #Rs = w2mj(solarRadiation)

    # step 4, slope of saturation vapor pressure curve
    vp_slope = saturation_vapor_pressure_curve_slope(mean_daily_temp)

    # step 5, atmospheric pressure
    pressure = atmospheric_pressure(elevation)

    # step 6, psychrometric constant
    psychrometric = psychrometric_constant(pressure)

    # step 7, delta term
    delta = delta_term(vp_slope, psychrometric, windSpeed)

    # step 8, psi term
    psi = psi_term(vp_slope, psychrometric, windSpeed)

    # step 9, temperature term
    t_term = temperature_term(mean_daily_temp, windSpeed)

    # step 10, mean saturation vapor pressure curve
    vp_curve = (saturation_vapor(tMax) + saturation_vapor(tMin)) / 2

    # step 11, actual vapor pressure
    vp_actual = saturation_vapor_pressure_actual(tMin, tMax, hMin, hMax)

    # step 11.1, vapor pressure deficit
    vp_deficit = vp_curve - vp_actual

    # step 12.1, relative sun earth distance
    dist = relative_earth_sun_distance(julianDay)

    # step 12.2, solar declination
    declination = solar_declination(julianDay)

    # step 13, latitude in radians
    latitude_r = deg2rad(latitude)

    ## Testing solar radiation calculation
    if solarRadiation is None:
        Rs = calc_solar_radiation(tMin, tMax, latitude_r, declination, julianDay)
    else:
        Rs = w2mj(solarRadiation)

    # step 14, sunset hour angle
    angle = sunset_hour_angle(latitude_r, declination)

    # step 15, extraerrestrial radiation
    Ra = extraterrestrial_radiation(dist, angle, latitude_r, declination)

    # step 16, clear sky solar radiation
    Rso = clear_sky_solar_radiation(elevation, Ra)

    # step 17, net solar radiation
    Rns = (1 - plantType) * Rs

    # step 18, net outgoing long wave solar radiation
    Rnl = long_wave_radiation(tMin, tMax, vp_actual, Rs, Rso)

    # step 19, net radiation
    Rn = Rns - Rnl

    # step 19.1, net radiation in mm
    Rng = Rn * 0.408

    # step FS1, radiation term ETrad
    radiation_term = delta * Rng


    # step FS2, wind term ETwind
    wind_term = psi * t_term * (vp_curve - vp_actual)

    # step final
    return radiation_term + wind_term


"""
  Class to hold data needed to calculate etO.  Update this throughout the
  day from current condition data and at the end of the day, use it to 
  calculate ETo.
"""
class etO(object):
    def __init__(self):
        self.temp_max = 0
        self.temp_min = 100
        self.rh_max = 0
        self.rh_min = 100
        self.ws_max = 0
        self.ws_min = 1000
        self.elevation = 0
        self.latitude = 0
        self.canopy = 0.26
        self.day = 0
        self.devices = []
        self.valid = False

    def reset(self, day):
        self.temp_max = 0
        self.temp_min = 100
        self.rh_max = 0
        self.rh_min = 100
        self.ws_max = 0
        self.ws_min = 1000
        self.day = day
        
    def addDevice(self, serial_num):
        self.devices.append(serial_num)
        self.valid = True

    def isDevice(self, serial_num):
        if serial_num in self.devices:
            return True
        return False

    def WindSpeed(self):
        return (self.ws_max + self.ws_min) / 2

    def Temperature(self, temp):
        self.temp_max = temp if temp > self.temp_max else self.temp_max
        self.temp_min = temp if temp < self.temp_min else self.temp_min

    def Humidity(self, humidity):
        self.rh_max = humidity if humidity > self.rh_max else self.rh_max
        self.rh_min = humidity if humidity < self.rh_min else self.rh_min

    def Wind(self, wind):
        self.ws_max = wind if wind > self.ws_max else self.ws_max
        self.ws_min = wind if wind < self.ws_min else self.ws_min

    def doETo(self):
        if not self.valid:
            return 0
        try:
            eto = evapotranspriation(self.temp_max, self.temp_min, None, self.WindSpeed(), self.elevation, self.rh_max, self.rh_min, self.latitude, self.canopy, self.day)
        except Exception as e:
            eto = 0
            LOGGER.error('ET0 caclulation failed: {}'.format(e))

        return eto
            

    def addData(self, data):
        if data['type'] == 'obs_air':
            self.Temperature(data['obs'][0][2])
            self.Humidity(data['obs'][0][3])
        elif data['type'] == 'obs_sky':
            self.Wind(data['obs'][0][5])
        elif data['type'] == 'obs_st':
            self.Temperature(data['obs'][0][7])
            self.Humidity(data['obs'][0][8])
            self.Wind(data['obs'][0][2])

        LOGGER.debug('GOT DATA  intermediate ETo = {}'.format(self.doETo()))


if __name__ == '__main__':
    #et0 = evapotranspriation(27.3, 10.7, 16.502, 1.3, 98.5, 36, 91, 36.82, 0.17, 289)

    # 0.23 is the crop / type coefficent
    # 289 is day of year

    et0 = evapotranspriation(27.3, 10.7, None, 1.3, 401.33, 91, 36, 36.82, 0.23, 289)
    print("et0 = ", et0)




