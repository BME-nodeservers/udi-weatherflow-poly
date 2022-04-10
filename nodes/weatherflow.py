#!/usr/bin/env python3
"""
Polyglot v3 node server for WeatherFlow Weather Station data.
Copyright (c) 2018,2019,2021 Robert Paauwe
"""
import udi_interface
import sys
import time
import datetime
import requests
import requests
import json
import socket
import math
import threading
from nodes import air
from nodes import sky
from nodes import tempest
from nodes import forecast
from nodes import et3

LOGGER = udi_interface.LOGGER
Custom = udi_interface.Custom

class Controller(udi_interface.Node):
    def __init__(self, polyglot, primary, address, name):
        super(Controller, self).__init__(polyglot, primary, address, name)
        self.poly = polyglot
        self.name = name
        self.address = address
        self.primary = primary

        self.Parameters = Custom(polyglot, 'customparams')
        self.Notices = Custom(polyglot, 'notices')

        self.deviceList = {}
        self.rainList = {}
        self.isConfigured = False
        self.nodesAdded = 1
        self.nodesCreated = 1
        self.eto = et3.etO()

        self.stopping = False
        self.stopped = True
        self.latitude = 0
        self.longitude = 0
        self.hb = 0
        self.hub_timestamp = 0
        self.units = {
                'temperature': 'c',
                'wind': 'kph',
                'pressure': 'mb',
                'rain': 'mm',
                'distance': 'km',
                'other': 'metric',
                }
        self.poly.subscribe(self.poly.CUSTOMPARAMS, self.parameterHandler)
        self.poly.subscribe(self.poly.START, self.start, self.address)
        self.poly.subscribe(self.poly.POLL, self.poll)
        self.poly.subscribe(self.poly.ADDNODEDONE, self.nodesDoneHandler)
        self.poly.ready()
        self.poly.addNode(self)

    def nodesDoneHandler(self, node):
        self.nodesAdded += 1

    def parameterHandler(self, params):
        """
          Get the parameters that the user entered.  We need the API
          token and at least one station.

          Here we'll verify that we have a token (and can access the WF 
          server) and a list of stations.
        """
        validToken = False
        validWind = False
        stationList = []
        self.isConfigured = False
        self.Parameters.load(params)

        LOGGER.debug(self.Parameters.dump())
        if self.Parameters['Token'] is not None:
            # token length should be  about 37 and 5 groups
            if len(self.Parameters['Token'].split('-')) == 5:
                validToken = True # looks valid
            else:
                LOGGER.debug('token {} {}'.format(len(self.Parameters['Token'].split('-')), self.Parameters['Token']))
        else:
            LOGGER.error('Token not defined in parameters')

        if self.Parameters['Rapid Wind'] is not None:
            validWind = True

        # What format for station names?  Just look at key names?  
        # TODO: should station value be local/remote?
        for st in self.Parameters:
            LOGGER.debug('Found parameter {}'.format(st))
            if st == 'Token':
                continue
            if st == 'ListenPort':
                continue
            if st == 'Forecast':
                continue
            if st == 'Rapid Wind':
                continue

            if st.isdigit():
                stationList.append({'id': st, 'remote': self.Parameters[st]})
            else:
                LOGGER.debug(f'skipping {st} not a valid station id')

        if validToken and len(stationList) > 0 and validWind:
            self.Notices.clear()
            self.isConfigured = True
            self.discover(stationList)
        else:   # Configuration required
            if not validToken:
                LOGGER.warning('Please enter a valid access token')
                self.Notices['token'] = 'Please enter a valid access token'
            if len(stationList) == 0:
                LOGGER.warning('Please enter at least one station ID')
                self.Notices['stations'] = 'Please enter at least one station ID'
            if not validWind:
                LOGGER.warning('Please set rapid wind to true or false')
                self.Notices['stations'] = 'Please set Rapid Wind to true or false'


    def query_station(self, station):
        path_str = 'https://swd.weatherflow.com'
        path_str += '/swd/rest/stations/' + station 
        path_str += '?api_key=' + self.Parameters.Token

        try:
            c = requests.get(path_str)
            jdata = c.json()
        except Exception as e:
            LOGGER.error('Station Query failed for {}: {}'.format(station, e))
            return None

        c.close()

        if not 'stations' in jdata:
            LOGGER.error('Invalid station ID: {}'.format(station))
            self.Notices['invalid'] = 'Station ID {} is invalid.'.format(station)
            return None

        if len(jdata['stations']) < 1:
            LOGGER.error('No matching station ID: {}'.format(station))
            self.Notices['invalid'] = 'Station ID {} is invalid.'.format(station)
            return None

        info = {}
        rain_id = ''
        rain_type = ''
        # What info do we want from the station query?
        #  jdata['stations'][0]['name'] 
        #  jdata['stations'][0]['latitude']
        #  jdata['stations'][0]['longitude']
        #  jdata['stations'][0]['station_meta']
        #  jdata['stations'][0]['station_meta']['elevation']
        #  jdata['stations'][0]['devices']
        info['name'] = jdata['stations'][0]['name'] 
        info['elevation'] = jdata['stations'][0]['station_meta']['elevation']
        info['devices'] = []
        for d in jdata['stations'][0]['devices']:
            if d['device_type'] != 'HB':
                LOGGER.debug('Adding device {} {}'.format(d['device_id'], d['serial_number']))
                info['devices'].append(
                        {
                            'device_id': d['device_id'],
                            'device_type': d['device_type'],
                            'serial_number': d['serial_number']
                         })

                rain_type = d['device_type']
                if d['device_type'] == 'SK' or d['device_type'] == 'ST':
                    rain_id = d['device_id']
                    self.query_station_rain(station, rain_id, rain_type)

                if station == self.Parameters['Forecast']:
                    self.eto.addDevice(d['serial_number'])
                    self.eto.elevation = info['elevation']
                    self.eto.latitude = jdata['stations'][0]['latitude']
                    self.eto.day = datetime.datetime.now().timetuple().tm_yday


        info['units'] = self.query_station_uom(station)
        if info['units'] == None:
            LOGGER.error('Failed to get station units, unable to continue')
            self.poly.Notices['units'] = 'Failed to get station units, unable to continue.'
            self.isConfigured = False

        #LOGGER.error('{}'.format(jdata))
        return info

    def query_station_uom(self, station):
        path_str = 'https://swd.weatherflow.com'
        path_str += '/swd/rest/observations/station/' + station 
        path_str += '?api_key=' + self.Parameters.Token

        try:
            c = requests.get(path_str)
            jdata = c.json()
        except Exception as e:
            LOGGER.error('Station Query failed for {}: {}'.format(station, e))
            return None

        c.close()

        if 'status' in jdata:
            if 'status_code' in jdata['status']:
                if jdata['status']['status_code'] != 0:
                    LOGGER.error('Error querying station {} information:'.format(station, jdata['status']['status_message']))
                    return None

        units = {}
        units['temperature'] = jdata['station_units']['units_temp']
        units['wind'] = jdata['station_units']['units_wind']
        units['rain'] = jdata['station_units']['units_precip']
        units['pressure'] = jdata['station_units']['units_pressure']
        units['distance'] = jdata['station_units']['units_distance']
        units['other'] = jdata['station_units']['units_other']

        return units

    def query_station_rain(self, station, rain_id, rain_type):
        # Do we have the device array in jdata?
        if rain_type == 'SK' or rain_type == 'ST':
            t_rain = self.get_today_rain(rain_id, rain_type)
            p_rain = self.get_yesterday_rain(rain_id, rain_type)
            w_rain = self.get_weekly_rain(rain_id, rain_type)
            m_rain, y_rain = self.get_monthly_rain(rain_id, rain_type)

            self.rain_accumulation(rain_id, p_rain, d_rain, w_rain, m_rain, y_rain)
    def query_device(self, device_id):
        path_str = 'https://swd.weatherflow.com'
        path_str += '/swd/rest/observations/device/' + str(device_id) 
        path_str += '?api_key=' + self.Parameters.Token

        try:
            c = requests.get(path_str)
            jdata = c.json()
        except Exception as e:
            LOGGER.error('Device observation query failed for {}: {}'.format(device_id, e))
            return None

        c.close()

        if 'status' in jdata:
            if 'status_code' in jdata['status']:
                if jdata['status']['status_code'] != 0:
                    LOGGER.error('Error querying device {}:'.format(device_id, jdata['status']['status_message']))
                    return None

        node = self.poly.getNode(device_id)
        node.update(jdata['obs'], False)

    def create_device_node(self, station, device, units, elevation):
        """
          Create a device node.  There are 3 types of nodes:
            Tempest:
            Sky:
            Air:
        """

        if self.poly.getNode(device['serial_number']) is not None:
            # Already exists, don't create it
            return

        if device['device_type'] == 'AR':
            LOGGER.info('Add AIR device node {}'.format(device['serial_number']))
            node = air.AirNode(self.poly, self.address, device['device_id'], device['serial_number'])
            # TODO: do we need to account for agl too?
            node.elevation = elevation
        elif device['device_type'] == 'SK':
            LOGGER.info('Add SKY device node {}'.format(device['serial_number']))
            node = sky.SkyNode(self.poly, self.address, device['device_id'], device['serial_number'])
            node.rd = self.rainList[device['device_id']]
        elif device['device_type'] == 'ST':
            LOGGER.info('Add Tempest device node {}'.format(device['serial_number']))
            node = tempest.TempestNode(self.poly, self.address, device['device_id'], device['serial_number'])
            # TODO: do we need to account for agl too?
            node.elevation = elevation
            node.rd = self.rainList[device['device_id']]
        else:
            return

        node.units = units
        self.poly.addNode(node)
        self.nodesCreated += 1

    # Get observations data for each month of the year, so far
    def get_monthly_rain(self, device_id, device_type):
        # Do month by month query of rain info.
        today = datetime.datetime.today()
        y_rain = 0
        for month in range(1, today.month+1):
            try:
                m_rain = 0
                # get epoch time for start of month and end of month
                try:
                    datem = datetime.datetime(today.year, month, 1)
                    start_date = datem.replace(day=1)
                    if month == 12:
                        end_date = datem.replace(month=12, day=31)
                    else:
                        end_date = datem.replace(month=(month+1 % 12), day=1)
                except Exception as e:
                    LOGGER.error(f'Problem with dates: {e}')
                    continue

                # make request:
                #  /swd/rest/observations/device/<id>?time_start=start&time_end=end&api_key=
                path_str = 'https://swd.weatherflow.com'
                path_str += '/swd/rest/observations/device/'
                path_str += str(device_id) + '?'
                path_str += 'time_start=' + str(int(start_date.timestamp()))
                path_str += '&time_end=' + str(int(end_date.timestamp()))
                path_str += '&api_key=' + self.Parameters.Token

                LOGGER.info('path = ' + path_str)

                c = requests.get(path_str)
                awdata = c.json()

                # we should now have an array of observations
                for obs in awdata['obs']:
                    # for sky, index 3 is daily rain.  for tempest it is index 12
                    m_rain += obs[3] if device_type == 'SK' else obs[12]
                    y_rain += obs[3] if device_type == 'SK' else obs[12]

                LOGGER.info('Month ' + str(month) + ' had rain = ' + str(m_rain))

                c.close()
            except:
                LOGGER.error('Failed to get rain for month %d' % month);
                c.close()

        LOGGER.info('yearly rain total = ' + str(y_rain))

        return m_rain, y_rain

    # Get observations data for past week
    def get_weekly_rain(self, device_id, device_type):
        # Need to do a separate query for weekly rain
        today = datetime.datetime.today()
        start_date = today - datetime.timedelta(days=7)
        end_date = today
        path_str = 'https://swd.weatherflow.com'
        path_str += '/swd/rest/observations/device/'
        path_str += str(device_id) + '?'
        path_str += 'time_start=' + str(int(start_date.timestamp()))
        path_str += '&time_end=' + str(int(end_date.timestamp()))
        path_str += '&api_key=' + self.Parameters.Token

        LOGGER.info('path = ' + path_str)

        try:
            c = requests.get(path_str)
            awdata = c.json()
            w_rain = 0
            for obs in awdata['obs']:
                w_rain += obs[3] if device_type == 'SK' else obs[12]

            c.close()
        except:
            LOGGER.error('Failed to get weekly rain')
            c.close()

        LOGGER.info('weekly rain total = ' + str(w_rain))

        return w_rain

    def get_yesterday_rain(self, device_id, device_type):
        today = datetime.datetime.today()
        start_date = today - datetime.timedelta(days=1)
        start_date = datetime.datetime.combine(start_date, datetime.min.time())
        end_date = datetime.datetime.combine(today, datetime.min.time())
        path_str = 'https://swd.weatherflow.com'
        path_str += '/swd/rest/observations/device/'
        path_str += str(device_id) + '?'
        path_str += 'time_start=' + str(int(start_date.timestamp()))
        path_str += '&time_end=' + str(int(end_date.timestamp()))
        path_str += '&api_key=' + self.Parameters.Token

        LOGGER.info('path = ' + path_str)

        try:
            c = requests.get(path_str)
            awdata = c.json()
            y_rain = 0
            for obs in awdata['obs']:
                y_rain += obs[3] if device_type == 'SK' else obs[12]

            c.close()
        except:
            LOGGER.error('Failed to get yesterday rain')
            c.close()

        LOGGER.info('yesterday rain total = ' + str(y_rain))

        return y_rain

    def get_today_rain(self, device_id, device_type):
        today = datetime.datetime.today()
        start_date = datetime.datetime.combine(today, datetime.min.time())
        end_date = today
        path_str = 'https://swd.weatherflow.com'
        path_str += '/swd/rest/observations/device/'
        path_str += str(device_id) + '?'
        path_str += 'time_start=' + str(int(start_date.timestamp()))
        path_str += '&time_end=' + str(int(end_date.timestamp()))
        path_str += '&api_key=' + self.Parameters.Token

        LOGGER.info('path = ' + path_str)

        try:
            c = requests.get(path_str)
            awdata = c.json()
            t_rain = 0
            for obs in awdata['obs']:
                t_rain += obs[3] if device_type == 'SK' else obs[12]

            c.close()
        except:
            LOGGER.error('Failed to get today rain')
            c.close()

        LOGGER.info('today rain total = ' + str(t_rain))
        return t_rain


    def rain_accumulation(self, device, p_rain, d_rain, w_rain, m_rain, y_rain):
        rd = {
                'hourly': 0,
                'daily': d_rain,
                'weekly': w_rain,
                'monthly': m_rain,
                'yearly': y_rain,
                'yesterday': p_rain
                }

        self.rainList[device] = rd

    def start(self):
        LOGGER.info('Starting WeatherFlow Node Server')
        self.poly.updateProfile()
        self.poly.setCustomParamsDoc()

        while not self.isConfigured:
            # Wait for configuration.
            time.sleep(10)

        while self.nodesAdded < self.nodesCreated:
            # wait for all nodes to be added
            time.sleep(10)

        LOGGER.info('Starting thread for UDP data')
        self.udp = threading.Thread(target = self.udp_data)
        self.udp.daemon = True
        self.udp.start()

        #TODO: forecast is for a station, which station should we use?
        self.forecast_query(self.Parameters['Forecast'], True)

        #for node in self.nodes:
        #       LOGGER.info (self.nodes[node].name + ' is at index ' + node)
        LOGGER.info('WeatherFlow Node Server Started.')

    def poll(self, polltype):
        """
          Use this to query the WF server via REST for any stations
          that are marked 'remote'.  
        """
        if not self.isConfigured:
            return

        if polltype == 'shortPoll':
            for device in self.deviceList:
                if self.deviceList[device]['remote']:
                    LOGGER.info('TODO: REST query for device {}'.format(device))
                    self.query_device(device)
            if self.eto.day != datetime.datetime.now().timetuple().tm_yday:
                eto = self.eto.doETo()
                # Value returned is in mm/day.  If self.units['rain'] == 'in'
                # then we need to convert this to inches/day.
                LOGGER.info('Yesterday\'s ETo = {}'.format(eto))
                if self.units['rain'] == 'in':
                    uom = 120
                    eto = round(eto * 0.03937, 3)
                else:
                    uom = 106
                self.setDriver('ETO', eto, uom=uom)
                self.eto.reset(datetime.datetime.now().timetuple().tm_yday)

            self.set_hub_timestamp()
        else:
            self.heartbeat()
            self.forecast_query(self.Parameters['Forecast'], False)

    def query(self):
        for node in self.poly.nodes():
            node.reportDrivers()

    def discover(self, stationList):
        """
          Take a list of stations and validate that each station exists.
          Get station configuration and create nodes for each device 
          associated with the station.
        """
        for station in stationList:
            LOGGER.info('Query WF for information on station {}'.format(station['id']))
            info = self.query_station(station['id'])
            if info is not None:
                LOGGER.info('{} has {} devices.'.format(station['id'], len(info['devices'])))
                self.units = info['units']
                for device in info['devices']:
                    remote = False
                    self.create_device_node(station['id'], device, info['units'], info['elevation'])
                    if station['remote'].lower() == 'remote':
                        remote = True
                    self.deviceList[device['device_id']] = {'serial_number': device['serial_number'], 'type': device['device_type'], 'remote': remote, 'first': True}

        if self.Parameters['Forecast'] != 0:
            for day in range(0, 10):
                address = 'forecast_' + str(day)
                title = 'Forecast ' + str(day)
                try:
                    if not self.poly.getNode(address):
                        node = forecast.ForecastNode(self.poly, self.address, address, title)
                        node.SetUnits(self.units['temperature'])
                        self.poly.addNode(node)
                        self.nodesCreated += 1
                except Excepton as e:
                    LOGGER.error('Failed to create forecast node ' + title)
                    LOGGER.error(e)

        LOGGER.info('Finished discovery')

        """
        LOGGER.debug('Attempt to add sensor status node')

        if self.tempest:
            node = hub.HubNode(self, self.address, 'hub', 'Hub', self.devices);
        else:
            node = hub.HubNode(self, self.address, 'hub', 'Hub', self.devices);
        LOGGER.debug('Sensor status node has been created, so add it')
        try:
            self.addNode(node)
        except Exception as e:
            LOGGER.error('Error adding sensor status node: ' + str(e))
        
                # TODO: Can we query the current accumulation data from
                # weatherflow servers???

        self.nodes['rain'].InitializeRain(self.rain_data)

            # Might be able to get some information from API using station
            # number:
            # swd.weatherflow.com/swd/rest/observations/station/<num>?apikey=

        num_days = int(self.params.get('Forecast Days'))
        if num_days < 10:
            # delete any extra days
            for day in range(num_days, 10):
                address = 'forecast_' + str(day)
                try:
                    self.delNode(address)
                except:
                    LOGGER.debug('Failed to delete node ' + address)

        """




    def forecast_query(self, station, force=False):

        if station is None or station == 0:
            return

        #  https://swd.weatherflow.com/swd/rest/better_forecast?station_id={}&api_key={}&lat={}&lon={} 
        path_str = 'https://swd.weatherflow.com/swd/rest/better_forecast?'
        path_str += 'station_id=' + str(station)
        path_str += '&api_key=' + self.Parameters['Token']
        try:
            c = requests.get(path_str)
            try:
                jdata = c.json()
                c.close()
            except Exception as e:
                c.close()
                LOGGER.error(str(e))
                return

            #LOGGER.debug(jdata)
            # Main tags: current_conditions & forecast
            #  forcast has daily array and hourly array (maybe more)

            current = jdata['current_conditions']
            LOGGER.debug(current)

            daily = jdata['forecast']['daily']
            LOGGER.debug(daily)

            # focus on passing daily data to forecast nodes
            day = 0
            for forecast in daily:
                address = 'forecast_' + str(day)
                LOGGER.debug(' >>>>   period ' + str(forecast['day_start_local']) + '  ' + address)
                LOGGER.debug(forecast)

                # call node update with forecast
                node = self.poly.getNode(address)
                if node is not None:
                    node.update(forecast, force)

                day += 1
                #if day >= int(self.params.get('Forecast Days')):
                #    return

        except Exception as e:
            LOGGER.error(str(e))


    def heartbeat(self):
        LOGGER.debug('heartbeat hb={}'.format(self.hb))
        if self.hb == 0:
            self.reportCmd("DON",2)
            self.hb = 1
        else:
            self.reportCmd("DOF",2)
            self.hb = 0

    def set_hub_timestamp(self):
        s = int(time.time() - self.hub_timestamp)
        LOGGER.debug("set_hub_timestamp: {}".format(s))
        self.setDriver('GV4', s, report=True, force=True)

    def delete(self):
        self.stopping = True
        LOGGER.info('Removing WeatherFlow node server.')

    def my_stop(self):
        self.stopping = True
        # Is there something we should do here to really stop?
        while not self.stopped:
            self.stopping = True

        LOGGER.info('WeatherFlow node server UDP thread finished.')

    def stop(self):
        self.stopping = True
        LOGGER.debug('Stopping WeatherFlow node server.')

    def remove_notices_all(self,command):
        LOGGER.info('remove_notices_all:')
        # Remove all existing notices
        self.removeNoticesAll()

    def send_data(self, data):
        for d in self.deviceList:
            device = self.deviceList[d]
            if device['serial_number'] == data['serial_number']:
                if not device['remote']:
                    node = self.poly.getNode(d)
                    node.update(data['obs'], device['first'])
                    device['first'] = False
                else:
                    LOGGER.debug('device {} not local, ignore UDP data.'.format(d))

        if self.eto.isDevice(data['serial_number']):
            self.eto.addData(data)

    def send_rapid_wind(self, data):
        for d in self.deviceList:
            device = self.deviceList[d]
            if device['serial_number'] == data['serial_number']:
                if not device['remote']:
                    node = self.poly.getNode(d)
                    node.rapid_wind(data['ob'])
                else:
                    LOGGER.debug('device {} not local, ignore UDP data.'.format(d))


    def udp_data(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        try:
            s.bind(('0.0.0.0', self.Parameters['ListenPort']))
        except Exception as e:
            LOGGER.error('Failed to bind to port {}: {}'.format(self.Parameters['ListenPort'], e))
            s.close()
            self.stopped = True
            return

        self.windspeed = 0
        sky_tm = 0
        air_tm = 0
        st_tm  = 0

        LOGGER.info("Starting UDP receive loop")
        while self.stopping == False:
            self.stopped = False
            try:
                hub = s.recvfrom(1024)
                data = json.loads(hub[0].decode("utf-8")) # hub is a truple (json, ip, port)
            except:
                LOGGER.error('JSON processing of data failed')
                continue

            """
            # skip data that's not for the configured station
            if data['serial_number'] not in self.devices:
                #LOGGER.info('skipping data, serial number ' + data['serial_number'] + ' not listed')
                continue
            """

            try:
                if (data["type"] == "obs_air"):
                    self.send_data(data)

                if (data["type"] == "obs_st"):
                    self.send_data(data)

                if (data["type"] == "obs_sky"):
                    self.send_data(data)

                if (data["type"] == "rapid_wind"):
                    if self.Parameters['Rapid Wind'].lower() == 'true':
                        self.send_rapid_wind(data)
            except Exception as e:
                LOGGER.error('Failed to send data to ISY: {}'.format(e))


            """
            if (data["type"] == "device_status"):
                if "AR" in data["serial_number"]:
                    #self.setDriver('GV2', data['rssi'], report=True, force=True)
                    self.nodes['hub'].update_rssi(data['rssi'], None)
                    self.nodes['hub'].update_sensors(data['sensor_status'])
                if "SK" in data["serial_number"]:
                    #self.setDriver('GV3', data['rssi'], report=True, force=True)
                    self.nodes['hub'].update_rssi(None, data['rssi'])
                    self.nodes['hub'].update_sensors(data['sensor_status'])
                if "ST" in data["serial_number"]:
                    #self.setDriver('GV2', data['rssi'], report=True, force=True)
                    self.nodes['hub'].update_rssi(data['rssi'])
                    self.nodes['hub'].update_sensors(data['sensor_status'])
            """

            if (data["type"] == "hub_status"):
                # This comes every 10 seconds, but we only update the driver
                # during longPoll, so just save it.
                #LOGGER.debug("hub_status: time={} {}".format(time.time(),data))
                if "timestamp" in data:
                    self.hub_timestamp = data['timestamp']

        s.close()
        self.stopped = True
        self.stop()


    id = 'WeatherFlow'

    commands = {
    }

    # Hub status information here: battery and rssi values.
    drivers = [
            {'driver': 'ST', 'value': 1, 'uom': 2},
            {'driver': 'GV4', 'value': 0, 'uom': 57},   # Hub seconds since seen
            {'driver': 'ETO', 'value': 0, 'uom': 106}   # Yesterday's etO
            ]


