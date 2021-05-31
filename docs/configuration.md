## Configuring connectivity and basic information of the Charging Point

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

```
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

## Configuration variables

### For OCPP 1.6

Configuration for protocol version 1.6 can be found in _/charge_point/v16/configuration/configuration.json_.

Each OCPP 1.6 configuration variable is represented as a dictionary with key equal to variable name, the **value** and
**permission** attributes. For more information regarding OCPP 1.6 configuration,
visit [this link](https://www.oasis-open.org/committees/download.php/58944/ocpp-1.6.pdf).

```
{
  "configuration": {
    "version": 1,
    "AllowOfflineTxForUnknownId": {
      "readOnly": false,
      "value": "false"
    },
    "AuthorizationCacheEnabled": {
      "readOnly": false,
      "value": "true"
    },
    "AuthorizeRemoteTxRequests": {
      "readOnly": false,
      "value": "false"
    },
    "ClockAlignedDataInterval": {
      "readOnly": false,
      "value": "0"
    },
    "ConnectionTimeOut": {
      "readOnly": false,
      "value": "50"
    },
    "GetConfigurationMaxKeys": {
      "readOnly": false,
      "value": "30"
    },
    "HeartbeatInterval": {
      "readOnly": false,
      "value": "60"
    },
    "LocalAuthorizeOffline": {
      "readOnly": false,
      "value": "true"
    },
    "LocalPreAuthorize": {
      "readOnly": false,
      "value": "true"
    },
    "MaxEnergyOnInvalidId": {
      "readOnly": false,
      "value": "0"
    },
    "MeterValuesSampledData": {
      "readOnly": false,
      "value": "Energy.Active.Import.Register"
    },
    "MeterValuesAlignedData": {
      "readOnly": false,
      "value": "false"
    },
    "NumberOfConnectors": {
      "readOnly": false,
      "value": "6"
    },
    "MeterValueSampleInterval": {
      "readOnly": false,
      "value": "0"
    },
    "ResetRetries": {
      "readOnly": false,
      "value": "3"
    },
    "ConnectorPhaseRotation": {
      "readOnly": false,
      "value": "0.RST, 1.RST, 2.RTS"
    },
    "StopTransactionOnEVSideDisconnect": {
      "readOnly": false,
      "value": "true"
    },
    "StopTransactionOnInvalidId": {
      "readOnly": false,
      "value": "true"
    },
    "StopTxnAlignedData": {
      "readOnly": false,
      "value": ""
    },
    "StopTxnSampledData": {
      "readOnly": false,
      "value": ""
    },
    "SupportedFeatureProfiles": {
      "readOnly": false,
      "value": "Core, LocalAuthListManagement, Reservation, RemoteTrigger"
    },
    "TransactionMessageAttempts": {
      "readOnly": false,
      "value": "3"
    },
    "TransactionMessageRetryInterval": {
      "readOnly": false,
      "value": "60"
    },
    "UnlockConnectorOnEVSideDisconnect": {
      "readOnly": false,
      "value": "true"
    },
    "ReserveConnectorZeroSupported": {
      "readOnly": false,
      "value": "false"
    },
    "SendLocalListMaxLength": {
      "readOnly": false,
      "value": "20"
    },
    "LocalAuthListEnabled": {
      "readOnly": false,
      "value": "true"
    },
    "LocalAuthListMaxLength": {
      "readOnly": false,
      "value": "20"
    }
  }
}
```

### For OCPP 2.0.1

Configuration for protocol version 2.0.1 can be found in _/charge_point/v201/configuration/configuration.json_.

In the protocol version 2.0.1, configuration variables are nested in Controllers (postfix - Ctrlr). Each controller has
variables represented as a dictionary with attributes: **readOnly**, **value** and _optionally_ **unit**. Some
controllers aren't completely supported. For more information regarding OCPP 2.0.1 configuration,
visit [the official website](https://www.openchargealliance.org/protocols/ocpp-201/).

```
{
  "AlignedDataCtrlr": {
    "Enabled": false,
    "Measurands": {
      "readOnly": false,
      "value": []
    },
    "Interval": {
      "readOnly": false,
      "value": 50,
      "unit": "seconds"
    },
    "TxEndedMeasurands": {
      "readOnly": false,
      "value": []
    },
    "TxEndedInterval": {
      "readOnly": false,
      "value": 50,
      "unit": "seconds"
    }
  },
  "AuthCacheCtrlr": {
    "Enabled": false,
    "AuthCacheEnabled": {
      "readOnly": false,
      "value": true
    },
    "AuthCacheLifeTime": {
      "readOnly": false,
      "value": true
    }
  },
  "AuthCtrlr": {
    "Enabled": true,
    "AuthorizeRemoteStart": {
      "readOnly": true,
      "value": true
    },
    "AuthEnabled": {
      "readOnly": false,
      "value": true
    },
    "OfflineTxForUnknownIdEnabled": {
      "readOnly": false,
      "value": false
    },
    "LocalAuthorizeOffline": {
      "readOnly": false,
      "value": true
    },
    "LocalPreAuthorize": {
      "readOnly": false,
      "value": true
    }
  },
  "CHAdeMOCtrlr": {
    "Enabled": false
  },
  "ClockCtrlr": {
    "Enabled": false,
    "DateTime": {
      "readOnly": true,
      "value": 1
    },
    "TimeSource": {
      "readOnly": false,
      "value": [
        "Heartbeat",
        "MobileNetwork"
      ]
    }
  },
  "CustomizationCtrlr": {
    "Enabled": false
  },
  "DeviceDataCtrlr": {
    "Enabled": false,
    "ItemsPerMessage": {
      "readOnly": true,
      "value": 1
    },
    "BytesPerMessage": {
      "readOnly": true,
      "value": 1
    }
  },
  "DisplayMessageCtrlr": {
    "Enabled": false
  },
  "ISO15118Ctrlr": {
    "Enabled": false
  },
  "LocalAuthListCtrlr": {
    "Enabled": false
  },
  "MonitoringCtrlr": {
    "Enabled": false
  },
  "OCPPCommCtrlr": {
    "Enabled": true,
    "RetryBackOffRepeatTimes": {
      "readOnly": false,
      "value": 1
    },
    "RetryBackOffRandomRange": {
      "readOnly": false,
      "unit": "seconds",
      "value": 1
    },
    "RetryBackOffWaitMinimum": {
      "readOnly": false,
      "unit": "seconds",
      "value": 1
    },
    "WebSocketPingInterval": {
      "readOnly": false,
      "unit": "seconds",
      "value": 1
    },
    "DefaultMessageTimeout": {
      "readOnly": true,
      "unit": "seconds",
      "value": 1
    },
    "FileTransferProtocols": {
      "readOnly": true,
      "value": [
        "HTTP",
        "HTTPS"
      ]
    },
    "HeartbeatInterval": {
      "readOnly": false,
      "unit": "seconds",
      "value": 60
    },
    "NetworkConfigurationPriority": {
      "readOnly": false,
      "value": []
    },
    "NetworkProfileConnectionAttempts": {
      "readOnly": false,
      "value": 1
    },
    "OfflineThreshold": {
      "readOnly": false,
      "unit": "seconds",
      "value": 150
    },
    "MessageAttempts": {
      "readOnly": false,
      "value": 1
    },
    "MessageAttemptInterval": {
      "unit": "seconds",
      "value": 90,
      "readOnly": false
    },
    "UnlockOnEVSideDisconnect": {
      "value": true,
      "readOnly": false
    },
    "ResetRetries": {
      "readOnly": false,
      "value": 90
    }
  },
  "ReservationCtrlr": {
    "Enabled": false
  },
  "SampledDataCtrlr": {
    "Enabled": true,
    "SampledDataEnabled": {
      "readOnly": false,
      "value": true
    },
    "TxEndedMeasurands": {
      "readOnly": false,
      "value": []
    },
    "TxEndedInterval": {
      "readOnly": false,
      "value": 60,
      "unit": "seconds"
    },
    "TxStartedMeasurands": {
      "readOnly": false,
      "value": []
    },
    "TxUpdatedMeasurands": {
      "readOnly": false,
      "value": []
    },
    "TxUpdatedInterval": {
      "readOnly": false,
      "value": []
    }
  },
  "SecurityCtrlr": {
    "Enabled": false,
    "OrganizationName": {
      "readOnly": false,
      "value": "UL FE"
    },
    "CertificateEntries": {
      "readOnly": true,
      "value": 1
    },
    "SecurityProfile": {
      "readOnly": true,
      "value": 1
    }
  },
  "SmartChargingCtrlr": {
    "Enabled": false
  },
  "TariffCostCtrlr": {
    "Enabled": false
  },
  "TxCtrlr": {
    "Enabled": true,
    "EVConnectionTimeOut": {
      "readOnly": false,
      "value": 60,
      "unit": "seconds"
    },
    "StopTxOnEVSideDisconnect": {
      "readOnly": true,
      "value": true
    },
    "TxStartPoint": {
      "readOnly": true,
      "value": [
        "Authorized"
      ]
    },
    "TxStopPoint": {
      "readOnly": true,
      "value": [
        "PowerPathClosed"
      ]
    },
    "StopTxOnInvalidId": {
      "readOnly": false,
      "value": true
    }
  }
}
```

## Configuring EVSEs and connectors

Connector (or equipment, hardware) settings can be found in _charge_point/connectors/connectors.json_. EVSEs property
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

```
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
