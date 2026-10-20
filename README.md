# Météo-France Observation

Home Assistant integration that reads the **measurements of Météo-France ground stations** in real time. Each station publishes an observation every 6 minutes: temperature, humidity, pressure, wind and precipitation.

It was built to provide the **outdoor temperature** of [Versatile Thermostat](https://github.com/jmcollin78/versatile_thermostat). A real, frequent measurement improves the regulation, especially with Auto-TPI.

Météo-France covers metropolitan France and the French overseas territories.

> [!NOTE]
> The built-in `meteo_france` integration provides forecasts and model values for a grid point. This one provides the value **measured** by the station you choose.

## Highlights

- Météo-France credentials are stored in Home Assistant's built-in **Application credentials**.
- Tokens are renewed automatically every hour: no more API key expiring silently.
- Find the station **around a point on the map**, **by department** or **by ID**.
- No YAML to write.

## Installation

[![Open the repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bontiv&repository=ha-meteofrance-observation&category=integration)

1. In HACS, add this repository as a custom repository of type **Integration** (or use the button above).
2. Install **Météo-France Observation**, then restart Home Assistant.

## 1. Get access to the Météo-France API

The API is free.

1. Create an account on the [Météo-France API portal](https://portail-api.meteofrance.fr) and sign in.
2. Open the [Données Publiques Observation](https://portail-api.meteofrance.fr/web/fr/api/DonneesPubliquesObservation) API and subscribe to it.
3. In **Mes API**, click **Générer token** for this API and pick **OAuth2**.
4. At the bottom of the page, the `curl` example contains `Authorization: Basic APPLICATION_ID`. Copy this **Application ID**.

> [!TIP]
> The Application ID is your application's *consumer key* and *consumer secret* encoded together. If the portal shows you these two values, you can enter them instead.

## 2. Add the station in Home Assistant

[![Add the integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=meteofrance_observation)

1. **Settings > Devices & services > Add integration > Météo-France Observation**.
2. Home Assistant first asks for the application credentials. Paste the **Application ID** in both fields, **Client ID** and **Client secret**. The steps above are recalled in this dialog.
3. Choose how to find the station:
   - **Around a point on the map**: the pin starts on your home. The 20 nearest stations are proposed with their distance and altitude.
   - **By department**: every station of the department, sorted by name.
   - **I know the station ID**: 8 digits, for example `75110001` for Paris-Lariboisière.
4. Pick the station. The integration checks that it publishes observations every 6 minutes.

Prefer a close station at an altitude similar to your home's. To follow several stations, add the integration several times: the same credentials are used for all of them.

## 3. Use with Versatile Thermostat

In the **central configuration** of Versatile Thermostat (or in each VTherm), select the `sensor.<station>_temperature` sensor as the **outdoor temperature sensor**.

## Sensors

| Sensor | Unit | Enabled by default |
| --- | --- | --- |
| Temperature | °C | yes |
| Humidity | % | yes |
| Dew point | °C | no |
| Atmospheric pressure | hPa | no |
| Sea level pressure | hPa | no |
| Wind speed | m/s | no |
| Wind direction | ° | no |
| Wind gust (over 10 min) | m/s | no |
| Precipitation (over 6 min) | mm | no |

Each sensor shows the observation time (`observation_time`) and the station location. A value the station did not measure makes the sensor **unavailable** instead of reporting a wrong value.

## Options

**Update interval**: 10 minutes by default, 6 minutes minimum. Stations do not publish more often.

## Troubleshooting

- **"The application is not subscribed to the API"**: subscribe to *Données Publiques Observation* on the portal, then confirm the reauthentication offered by Home Assistant.
- **"This station publishes no 6-minute observation"**: some stations of the network do not report in real time. Pick another one.
- **Changed or removed credentials**: update them in **Settings > Devices & services > three dots menu > Application credentials**.

## Migrate from the REST sensor

If you used the `rest:` configuration of the [VTherm discussion #1552 guide](https://github.com/jmcollin78/versatile_thermostat/discussions/1552):

1. Add the station with this integration.
2. In Versatile Thermostat, replace the old sensor with the new one.
3. Remove the `rest:` block from `configuration.yaml` and restart.

## Data

Data comes from the Météo-France public API, which only keeps the last 24 hours. This project is independent and not affiliated with Météo-France.
