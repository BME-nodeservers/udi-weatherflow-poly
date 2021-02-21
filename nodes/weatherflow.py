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
import urllib3
from nodes import air
from nodes import sky
from nodes import tempest
from nodes import forecast
#import node_funcs
#from nodes import temperature
#from nodes import humidity
#from nodes import pressure
#from nodes import rain
#from nodes import wind
#from nodes import light
#from nodes import lightning
#from nodes import hub

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
        self.RainData = Custom(polyglot, 'rain')

        self.deviceList = {}
        self.isConfigured = False

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
        self.poly.ready()
        self.poly.addNode(self)

    def parameterHandler(self, params):
        """
          Get the parameters that the user entered.  We need the API
          token and at least one station.

          Here we'll verify that we have a token (and can access the WF 
          server) and a list of stations.
        """
        validToken = False
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
            stationList.append({'id': st, 'remote': self.Parameters[st]})

        if validToken and len(stationList) > 0:
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

        info = {}
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
            """
              TODO:
              station UOM's come from station observation data so should
              we query that here?
            """
            info['units'] = self.query_station_uom(station)

            if d['device_type'] != 'HB':
                LOGGER.debug('Adding device {} {}'.format(d['device_id'], d['serial_number']))
                info['devices'].append(
                        {
                            'device_id': d['device_id'],
                            'device_type': d['device_type'],
                            'serial_number': d['serial_number']
                         })

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

        units = {}
        units['temperature'] = jdata['station_units']['units_temp']
        units['wind'] = jdata['station_units']['units_wind']
        units['rain'] = jdata['station_units']['units_precip']
        units['pressure'] = jdata['station_units']['units_pressure']
        units['distance'] = jdata['station_units']['units_distance']
        units['other'] = jdata['station_units']['units_other']

        # TODO: Should we pull other data from here also, like precipitation
        #       accumulations?
        d_rain = jdata['obs'][0]['precip_accum_local_day']
        LOGGER.info('daily rainfall = %f' % d_rain)
        p_rain = jdata['obs'][0]['precip_accum_local_yesterday']
        LOGGER.info('yesterday rainfall = %f' % p_rain)

        return units


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

        node = self.poly.getNode(device_id)
        node.update(jdata['obs'])

    def create_device_node(self, station, device, units):
        """
          Create a device node.  There are 3 types of nodes:
            Tempest:
            Sky:
            Air:
        """
        if device['device_type'] == 'AR':
            LOGGER.info('Add AIR device node {}'.format(device['serial_number']))
            node = air.AirNode(self.poly, self.address, device['device_id'], device['serial_number'])
        elif device['device_type'] == 'SK':
            LOGGER.info('Add SKY device node {}'.format(device['serial_number']))
            node = sky.SkyNode(self.poly, self.address, device['device_id'], device['serial_number'])
        elif device['device_type'] == 'ST':
            LOGGER.info('Add Tempest device node {}'.format(device['serial_number']))
            node = tempest.TempestNode(self.poly, self.address, device['device_id'], device['serial_number'])
        else:
            return

        node.units = units
        self.poly.addNode(node)

    def get_monthly_rain(self):
        # Do month by month query of rain info.
        today = datetime.datetime.today()
        y_rain = 0
        for month in range(1,today.month+1):
            try:
                m_rain = 0
                # get epoch time for start of month and end of month
                datem = datetime.datetime(today.year, month, 1)
                start_date = datem.replace(day=1)
                #end_date = datem.replace(month=(month+1 % 12), day=1) - datetime.timedelta(days=1)
                end_date = datem.replace(month=(month+1 % 12), day=1)

                # make request:
                #  /swd/rest/observations/device/<id>?time_start=start&time_end=end&api_key=
                path_str = '/swd/rest/observations/device/'
                path_str += str(device_id) + '?'
                path_str += 'time_start=' + str(int(start_date.timestamp()))
                path_str += '&time_end=' + str(int(end_date.timestamp()))
                path_str += '&api_key=6c8c96f9-e561-43dd-b173-5198d8797e0a'

                LOGGER.info('path = ' + path_str)

                c = http.request('GET', path_str)
                awdata = json.loads(c.data.decode('utf-8'))

                # we should now have an array of observations
                for obs in awdata['obs']:
                    # for sky, index 3 is daily rain.  for tempest it is index 12
                    if sky_found:
                        m_rain += obs[3]
                        y_rain += obs[3]
                    elif tempest_found:
                        m_rain += obs[12]
                        y_rain += obs[12]

                LOGGER.info('Month ' + str(month) + ' had rain = ' + str(m_rain))

                c.close()
            except:
                LOGGER.error('Failed to get rain for month %d' % month);
                c.close()

        LOGGER.info('yearly rain total = ' + str(y_rain))

    def get_weekly_rain(self):
        # Need to do a separate query for weekly rain
        start_date = today - datetime.timedelta(days=7)
        end_date = today
        path_str = '/swd/rest/observations/device/'
        path_str += str(device_id) + '?'
        path_str += 'time_start=' + str(int(start_date.timestamp()))
        path_str += '&time_end=' + str(int(end_date.timestamp()))
        path_str += '&api_key=6c8c96f9-e561-43dd-b173-5198d8797e0a'

        LOGGER.info('path = ' + path_str)

        try:
            c = http.request('GET', path_str)
            awdata = json.loads(c.data.decode('utf-8'))
            w_rain = 0
            for obs in awdata['obs']:
                if sky_found:
                    w_rain += obs[3]
                elif tempest_found:
                    w_rain += obs[12]

            c.close()
        except:
            LOGGER.error('Failed to get weekly rain')
            c.close()

        LOGGER.info('weekly rain total = ' + str(w_rain))

        http.close()

        """
        if y_rain > 0:
            self.rain_data['yearly'] = y_rain
            self.rain_data['year'] = datetime.datetime.now().year
        if m_rain > 0:
            self.rain_data['monthly'] = m_rain
            self.rain_data['month'] = datetime.datetime.now().month
        if w_rain > 0:
            self.rain_data['weekly'] = w_rain
            self.rain_data['week'] = datetime.datetime.now().isocalendar()[1]
        if d_rain > 0:
            self.rain_data['daily'] = d_rain
            self.rain_data['day'] = datetime.datetime.now().day
        if p_rain > 0:
            self.rain_data['yesterday'] = p_rain

        self.rain_data['hourly'] = 0

        self.params.save_params(self)
        """

    def start(self):
        LOGGER.info('Starting WeatherFlow Node Server')
        self.poly.updateProfile()
        self.poly.setCustomParamsDoc()

        while not self.isConfigured:
            # Wait for configuration.
            time.sleep(10)

        LOGGER.info('Starting thread for UDP data')
        self.udp = threading.Thread(target = self.udp_data)
        self.udp.daemon = True
        self.udp.start()

        #TODO: forecast is for a station, which station should we use?
        self.forecast_query(self.Parameters['Forecast'])

        #for node in self.nodes:
        #       LOGGER.info (self.nodes[node].name + ' is at index ' + node)
        LOGGER.info('WeatherFlow Node Server Started.')

    def poll(self, polltype):
        """
          Use this to query the WF server via REST for any stations
          that are marked 'remote'.  
        """
        if polltype == 'shortPoll':
            for device in self.deviceList:
                if self.deviceList[device]['remote']:
                    LOGGER.info('TODO: REST query for device {}'.format(device))
                    self.query_device(device)
        else:
            self.heartbeat()
            self.forecast_query(self.Parameters['Forecast'])

    def query(self):
        for node in self.nodes:
            self.nodes[node].reportDrivers()

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
                for device in info['devices']:
                    remote = False
                    self.create_device_node(station['id'], device, info['units'])
                    # TODO: Do we need to keep a list of devices for UDP updates and Polling?
                    if station['remote'].lower() == 'remote':
                        remote = True
                    self.deviceList[device['device_id']] = {'serial_number': device['serial_number'], 'type': device['device_type'], 'remote': remote}

        for day in range(0, 10):
            address = 'forecast_' + str(day)
            title = 'Forecast ' + str(day)
            try:
                node = forecast.ForecastNode(self.poly, self.address, address, title)
                node.SetUnits(self.units['temperature'])
                self.poly.addNode(node)
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




    def forecast_query(self, station):

        if station is None:
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
                    node.update(forecast)

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
                    node.update(data['obs'])
                else:
                    LOGGER.debug('device {} not local, ignore UDP data.'.format(d))

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
        s.bind(('0.0.0.0', self.Parameters['ListenPort']))
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

            if (data["type"] == "obs_air"):
                self.send_data(data)

            if (data["type"] == "obs_st"):
                self.send_data(data)

            if (data["type"] == "obs_sky"):
                self.send_data(data)

            if (data["type"] == "rapid_wind"):
                self.send_rapid_wind(data)


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

            if (data["type"] == "hub_status"):
                # This comes every 10 seconds, but we only update the driver
                # during longPoll, so just save it.
                #LOGGER.debug("hub_status: time={} {}".format(time.time(),data))
                if "timestamp" in data:
                    self.hub_timestamp = data['timestamp']
            """

        s.close()
        self.stopped = True
        self.stop()


    id = 'WeatherFlow'

    commands = {
        'DISCOVER': discover,
    }

    # Hub status information here: battery and rssi values.
    drivers = [
            {'driver': 'ST', 'value': 1, 'uom': 2},
            {'driver': 'GV2', 'value': 0, 'uom': 25},  # Air RSSI
            {'driver': 'GV3', 'value': 0, 'uom': 25},  # Sky RSSI
            {'driver': 'GV4', 'value': 0, 'uom': 57}   # Hub seconds since seen
            ]


