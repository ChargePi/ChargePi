# Configuring connectivity and basic information of the Charging Point

Settings can be found in the _settings.json_ and feature basic Charge Point information such as:

- vendor and model,
- unique registered charging point ID, server URI and logging server IP,
- default max charging time,
- OCPP protocol version,
- client current and target version for tracking updates,
- display and input hardware settings for LCD, RFID/NFC reader and LEDs.

The table represents attributes, their values and descriptions that require more attention and might not be
self-explanatory. Some examples can have multiple possible values, if any are empty, they will be treated as disabled or
might not work properly.

| Attribute| Description |Possible values | 
| :---:    | :---:    | :---:    | 
| id | ID of the charging point. Must be registered in the Central System | Default:"ChargePi" |
| protocol_version | Version of the OCPP protocol. | "1.6", "2.0.1" |
| server_uri | URI of the Central System with the port and endpoint. | Default: "172.0.1.121:8080/steve/websocket/CentralSystemService" | 
| log_server | IP of the logging server. | Any valid IP | 
| info: max_charging_time | Max charging time allowed on the Charging point in minutes. | Default:180 |
| rfid_reader: reader_model | RFID/NFC reader model used. |  "PN532", "MFRC522" | 
| LED_indicator: type | Type of the led indicator.  | "WS281x", ""|
| hardware: min_power| Minimum power draw needed to continue charging, if Power meter is configured. | Default:20|

Example settings:

```json
{
  "charge_point": {
    "info": {
      "vendor": "UL FE",
      "model": "ChargePi",
      "id": "ChargePi",
      "protocol_version": "1.6",
      "current_client_version": "1.0",
      "target_client_version": "1.0",
      "server_uri": "<ip>",
      "log_server": "<ip>",
      "max_charging_time": 180
    },
    "hardware": {
      "lcd": {
        "is_supported": true,
        "i2c_address": "0x27"
      },
      "rfid_reader": {
        "is_supported": true,
        "reader_model": "PN532",
        "reset_pin": 19
      },
      "LED_indicator": {
        "indicate_card_read": true,
        "type": "WS281x",
        "invert": false
      },
      "min_power": 20
    }
  }
}
```

## Configuring EVSEs and connectors

Connector (or equipment, hardware) settings can be found in `charge_point/connectors/connectors.json`. EVSEs property
contains a list of Electric Vehicle Charging Equipment objects. Charging point can have multiple EVSEs. Each EVSE can
have one or more connectors, but only one connector can charge at a time.

Connector object contains a connector type and an ID of the connector, which must start with 1 and increment by one. The
status attribute changes according to the OCPP specification.The session object represents a Charging session and is
used to restore the connector's previous state when rebooted/powered back up.

The relay and power meter objects are configurable to specific GPIO pins and SPI bus. The default_state attribute in the
relay object indicates the logic of the relay. If default_state is 1, the relay is operated with inverse logic and vice
versa. The power meter also contains some attributes for measurement.

The table represents attributes, their values and descriptions that require more attention and might not be
self-explanatory. Some examples can have multiple possible values, if any are empty, they will be treated as disabled or
might not work properly.

| Attribute| Description |Possible values | 
| :---:    | :---:    | :---:    | 
| EVSEs | List of EVSEs, which each contain a list of connectors. | Default: example |
| connector: type | A type of the connector used in the build.  | Refer to OCPP documentation. Default: "Schuko" |
| relay: default_state | Logic of the relay. It is used to combat different relay configurations. |0, 1| 
| power_meter: shunt_offset | Value of the shunt resistor used in the build to measure power. | Default: 0.1 | 
| power_meter: voltage_divider_offset| Value of the voltage divider used in the build to measure power.| Default:1333 |

Example with two connectors:

```json
{
  "EVSEs": [
    {
      "id": 1,
      "connectors": [
        {
          "id": 1,
          "type": "Schuko",
          "status": "Available",
          "session": {
            "is_active": false,
            "transaction_id": "",
            "tag_id": "",
            "started": "",
            "consumption": []
          },
          "relay": {
            "relay_pin": 26,
            "default_state": 1
          },
          "power_meter": {
            "power_meter_pin": 0,
            "spi_bus": 0,
            "power_units": "kWh",
            "consumption": 0,
            "shunt_offset": 0.01,
            "voltage_divider_offset": 1333
          }
        },
        {
          "id": 2,
          "type": "Schuko",
          "status": "Available",
          "session": {
            "is_active": false,
            "transaction_id": "",
            "tag_id": "",
            "started": "",
            "consumption": []
          },
          "relay": {
            "relay_pin": 13,
            "default_state": 1
          },
          "power_meter": {
            "spi_bus": 0,
            "power_meter_pin": 25,
            "power_units": "kWh",
            "consumption": 0,
            "shunt_offset": 0.01,
            "voltage_divider_offset": 1333
          }
        }
      ]
    }
  ]
}
```
