# OCPP 1.6 configuration

Configuration for protocol version 1.6 can be found in _/charge_point/v16/configuration/configuration.json_.

Each OCPP 1.6 configuration variable is represented as a dictionary with key equal to variable name, the **value** and
**permission** attributes. For more information regarding OCPP 1.6 configuration,
visit [this link](https://www.oasis-open.org/committees/download.php/58944/ocpp-1.6.pdf).

```json
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
