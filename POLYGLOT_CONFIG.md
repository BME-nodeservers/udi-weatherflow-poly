## Configuration

The WeatherFlow node server has the following user configuration parameters:

- Token [required]: This is your API authorization token.  
- ListenPort [required]: Port to listen on for WeatherFlow data. Default is port 50222.
- Forecast [optional]: Station ID to get forecast data for.
- [Station ID]  [required]:  At least one station id must be entered.

You can enter multiple station id's. For each one, you need to specify
if you want local or remote data.  Local data will use the UDP data
broadcast from the hub (or hubs).  Remote will query the WeatherFlow
server for the data at the short poll interval.

For each station ID entered, the node server will query WeatherFlow for
the list of devices associated with the station and create a node for
device found.

If you specify a Forecast station id, a node will be created for each
available daily forecast.
