
# weatherflow-polyglot

This is a node server to pull weather data from WeatherFlow weather stations and
make it available to a [Universal Devices ISY994i](https://www.universal-devices.com/residential/ISY)
[Polyglot interface](http://www.universal-devices.com/developers/polyglot/docs/) with 
Polyglot V3 running on a [Polisy](https://www.universal-devices.com/product/polisy/)

(c) 2018-2021 Robert Paauwe

This node server is intended to support the [WeatherFlow Smart Weather Station](http://www.weatherflow.com/).
It supports both the current Tempest stations and older Air/Sky based stations. 
Multiple stations can be configured and used.

## Installation

1. Backup Your ISY in case of problems!
   * Really, do the backup, please
2. Go to the Polyglot Store in the UI and install.
3. From the Polyglot dashboard, select WeatherFlow node server and configure (see configuration options below).
4. Once configured, the WeatherFlow node server should update the ISY with the proper nodes and begin filling in the node data. Note that it can take up to 1 minute for data to appear.
5. Restart the Admin Console so that it can properly display the new node server nodes.

### Node Settings
The settings for this node are:

#### Short Poll
   * Interval used to poll the WeatherFlow server for stations marked as 'remote'
#### Long Poll
   * Interval used to poll the WeatherFlow server for forecast data
   * Sends a heartbeat as DON/DOF
#### Token
   * Your personal access to token. See https://tempestwx.com/settings/tokens
#### ListenPort
   * Port to listen on for WeatherFlow data. Default is port 50222
#### Rapid Wind
   * Enable or disable the sending of rapid wind data to the ISY.  Set to 'true' to enable.
   * Rapid wind data is collected every 3 seconds  
   * Rapid wind data is only available for stations configured as 'local'
#### Forecast
   * Specifies the station id used for forecast data.
   * If not set, no forecast data will be collected and not evaptrasnspiration calculations will done
#### Stations
   * A separate key/value for each station you want to collect data from
   * The key is the station id number
   * The value must be either 'local' or 'remote'
   * 'local' - the data comes from the hub UDP feed on your local network
   * 'remote' - the data comes from the WeatherFlow server at Short Poll intervals

## Node substitution variables
### Parent node
 * sys.node.controller.ST     (Node server online/offline)
 * sys.node.controller.ETO    (Evaptranspiration for yesterday)
 * sys.node.controller.GV4    (Number of seconds since an update was received from a station)

### Air node
 * sys.node.[deviceid].CLITEMP   (Current temperature)
 * sys.node.[deviceid].CLIHUM    (Current humidity)
 * sys.node.[deviceid].ATMPRES   (Current sea level pressure)
 * sys.node.[deviceid].BARPRES   (Current station pressure)
 * sys.node.[deviceid].GV1       (Current pressure trend)
 * sys.node.[deviceid].GV0       (Current feels like temperature)
 * sys.node.[deviceid].DEWPT     (Current dewpoint)
 * sys.node.[deviceid].HEATIX    (Current heat index)
 * sys.node.[deviceid].WINDCH    (Current windchill)
 * sys.node.[deviceid].GV2       (Current lightning strike count)
 * sys.node.[deviceid].DISTANC   (Current lightning strike distance)
 * sys.node.[deviceid].BATLVL    (Current air battery voltage)

### sky node
 * sys.node.[deviceid].SPEED     (Current wind speed)
 * sys.node.[deviceid].WINDDIR   (Current wind direction)
 * sys.node.[deviceid].GUST      (Current gust speed)
 * sys.node.[deviceid].GV1       (Current lull speed)
 * sys.node.[deviceid].RAINRT    (Current rain rate)
 * sys.node.[deviceid].PRECIP    (Current daily rain)
 * sys.node.[deviceid].GV2       (Current hourly rain)
 * sys.node.[deviceid].GV3       (Current weekly rain)
 * sys.node.[deviceid].GV4       (Current monthly rain)
 * sys.node.[deviceid].GV5       (Current yearly rain)
 * sys.node.[deviceid].GV6       (Current yesterday's rain)
 * sys.node.[deviceid].UV        (Current UV index)
 * sys.node.[deviceid].SOLRAD    (Current solar radiataion)
 * sys.node.[deviceid].LUMIN     (Current brightness)
 * sys.node.[deviceid].BATLVL    (Current sky battery voltage)

### tempest node
 * sys.node.[deviceid].CLITEMP   (Current temperature)
 * sys.node.[deviceid].CLIHUM    (Current humidity)
 * sys.node.[deviceid].ATMPRES   (Current sea level pressure)
 * sys.node.[deviceid].BARPRES   (Current station pressure)
 * sys.node.[deviceid].GV1       (Current pressure trend)
 * sys.node.[deviceid].GV0       (Current feels like temperature)
 * sys.node.[deviceid].DEWPT     (Current dewpoint)
 * sys.node.[deviceid].HEATIX    (Current heat index)
 * sys.node.[deviceid].WINDCH    (Current windchill)
 * sys.node.[deviceid].GV2       (Current lightning strike count)
 * sys.node.[deviceid].DISTANC   (Current lightning strike distance)
 * sys.node.[deviceid].SPEED     (Current wind speed)
 * sys.node.[deviceid].WINDDIR   (Current wind direction)
 * sys.node.[deviceid].GUST      (Current gust speed)
 * sys.node.[deviceid].GV3       (Current gust direction)
 * sys.node.[deviceid].GV4       (Current lull speed)
 * sys.node.[deviceid].RAINRT    (Current rain rate)
 * sys.node.[deviceid].PRECIP    (Current daily rain)
 * sys.node.[deviceid].GV5       (Current hourly rain)
 * sys.node.[deviceid].GV6       (Current weekly rain)
 * sys.node.[deviceid].GV7       (Current monthly rain)
 * sys.node.[deviceid].GV8       (Current yearly rain)
 * sys.node.[deviceid].GV9       (Current yesterday's rain)
 * sys.node.[deviceid].UV        (Current UV index)
 * sys.node.[deviceid].SOLRAD    (Current solar radiataion)
 * sys.node.[deviceid].LUMIN     (Current brightness)
 * sys.node.[deviceid].BATLVL    (Current tempest battery voltage)

### forecast node
 * sys.node.[forecast_x].ST      (day of week)
 * sys.node.[forecast_x].GV0     (daily predicted high temperature)
 * sys.node.[forecast_x].GV1     (daily predicted low temperature)
 * sys.node.[forecast_x].GV13    (expected weather conditions)
 * sys.node.[forecast_x].GV18    (chance of precipitation)

## Requirements

1. Polyglot V3.
2. ISY firmware 5.3.x or later.
3. A WeatherFlow weather station and assocated account

# Release Notes
- 3.0.0 02/23/2021
  - Full redsign with new node layout
  - Support for multiple stations
  - Support for daily forecasts
  - Support for evaptranspiration caluclation
  - Support for rapid wind events
  - Support both local and remote data
  - Support for personal access token
- 2.0.9 07/21/2020
  - Round values to 3 decimal places when doing metric conversions.
  - Skip bad/corrupt device records when querying WF server.
- 2.0.8 07/15/2020
  - Handle pressure value being none
- 2.0.7 06/23/2020
  - Handle missing pressure value.
- 2.0.6 05/09/2020
  - Add some details to the data processing exceptions.
  - Force pressure calculations to use floating values always.
- 2.0.5 03/20/2020
  - Pull rainfall data from WeatherFlow server on startup.
- 2.0.4 03/19/2020
  - Add additional error messages and debugging
- 2.0.3 02/28/2020
  - Fix data update for sky and air
  - Only delete sensor node when station changes.
- 2.0.2 02/27/2020
  - Make better use of the user units configuration
  - Improve field labeling for sensor status values
  - Restrict device list to one device of each type
- 2.0.1 02/26/2020
  - Fix startup sequence to only call discover once
  - Fix log level save/restore
- 2.0.0 02/26/2020
  - Add support for Tempest weather station.
  - Only process data packets that match station device serial numbers.
  - Add configurable log level.
  - Add new node with phyical sensor status.
- 0.1.18 02/11/2020
  - Trap the condition when wind speeds are none/null
- 0.1.17 10/29/2018
  - Add rain yesterday to rain node.
  - Ignore duplicate UDP packets.
- 0.1.16 10/22/2018
  - Clean up debugging log output
  - Add specific debug output of all raw rain values
- 0.1.15 10/19/2018
  - Fix pressure trend (at least during initial 3 hour window)
  - Reverse relative and absolut pressure values, the were mixed up.
- 0.1.14 10/18/2018
  - Add station id configuration option
  - Using station id, query WF servers for station elevation, Air height
    above ground, and user's unit preferences.
  - Add configuration option for Air sensor height above ground
- 0.1.13 10/17/2018
  - Use entered elevation for sealevel pressure calulation
- 0.1.12 10/16/2018
  - Fix typo in sea level pressure calculation
  - Add error checking to dewpoint calculation
- 0.1.11 10/15/2018
  - Change weekly rain accumulation to use week number instead of day of week.
  - Hourly rain was not reseting at begining of next hour
  - Clear old rain accumulations on restart
  - Fix pressure trend values, the values didn't match the NLS names.
  - Don't convert pressure trend when US units are selected, trying to do
    a mb -> inHg conversion on the trend value doesn't make sense.
- 0.1.10 10/09/2018
  - Add error checking to units entry.
  - Add configuration help text
- 0.1.9 10/04/2018
  - Set hint correctly
  - Fix bug with UDP thread start. 
- 0.1.8 09/16/2018
  - JimBo: Send DON/DOF for heartbeat
  - JimBo: Set initial Controller ST default to 1
  - JimBo: Set Hub Seconds Since Seen
- 0.1.7 09/26/2018
   - Add some error trapping in the config change handler
   - Make sure the configuration values are set before trying to use them
   - Fix bug in restoring rain accumulation.
   - Changed order of node creation so that nodes get added with the correct units.
- 0.1.6 09/25/2018
   - Fix bug in rain accumulation.
- 0.1.5 09/11/2018
   - Fix bug in UDP JSON parsing related to migration to python3
- 0.1.4 09/10/2018
   - Convert this to a python program instead of a node.js program
- 0.1.3 09/04/2018
   - Fix bug in NodeDef selections. 
- 0.1.2 07/10/2018
   - Add logging for the UDP port number used.
   - Add error trapping and logging for the UDP socket connection
- 0.1.1 05/08/2018
   - Add ListenPort option to change port we listen on for WeatherFlow data.
- 0.1.0 04/18/2018
   - Initial version published in the Polyglot node server store

- 0.0.1 04/15/2018
   - Initial version published to github
