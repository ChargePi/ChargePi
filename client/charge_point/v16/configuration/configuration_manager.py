import json
import logging
from aiofiles import open as asyncopen
import os

logger = logging.getLogger('chargepi_logger')


class ConfigurationManager:
    """
    Class for I/O operations of charge point configuration.
    """

    __path = os.path.dirname(os.path.realpath(__file__))
    __file_name = f"{__path}/configuration.json"

    def __init__(self):
        self.__configuration: dict = dict()
        self.__version: int = None
        self.get_configuration_from_file()

    @property
    def get_configuration(self) -> dict:
        return self.__configuration

    def get_configuration_variable_value(self, key) -> str:
        if key in self.__configuration.keys():
            return self.__configuration[key]["value"]
        return ""

    def get_configuration_variable(self, key) -> dict:
        if key in self.__configuration.keys():
            return self.__configuration[key]
        return {"key": "not_found"}

    async def update_configuration_variable(self, key: str, value: str) -> str:
        update_success: str = "Failed"
        file_data: dict
        async with asyncopen(ConfigurationManager.__file_name, mode="r") as config_file:
            file_data = json.loads(await config_file.read())
            await config_file.close()
            async with asyncopen(ConfigurationManager.__file_name, mode="w") as settings:
                if not (key in file_data["configuration"].keys()):
                    return update_success
                attribute: dict = file_data["configuration"][key]
                if not attribute["readOnly"]:
                    file_data["configuration"][key]["value"] = value
                    update_success = "Success"
                await settings.write(json.dumps(file_data, indent=2, sort_keys=True))
                await settings.close()
                await self._reload_configuration()
        return update_success

    async def _reload_configuration(self):
        async with asyncopen(ConfigurationManager.__file_name, mode="r") as config_file:
            attribute_data = json.loads(await config_file.read())
            await config_file.close()
            self.__version = attribute_data["configuration"]["version"]
            # Core configuration
            self.__configuration["AllowOfflineTxForUnknownId"] = attribute_data["configuration"][
                "AllowOfflineTxForUnknownId"]
            self.__configuration["AuthorizationCacheEnabled"] = attribute_data["configuration"][
                "AuthorizationCacheEnabled"]
            self.__configuration["TransactionMessageAttempts"] = attribute_data["configuration"][
                "TransactionMessageAttempts"]
            self.__configuration["TransactionMessageRetryInterval"] = attribute_data["configuration"][
                "TransactionMessageRetryInterval"]
            self.__configuration["LocalAuthListEnabled"] = attribute_data["configuration"]["LocalAuthListEnabled"]
            self.__configuration["SendLocalListMaxLength"] = attribute_data["configuration"][
                "SendLocalListMaxLength"]
            self.__configuration["LocalAuthListMaxLength"] = attribute_data["configuration"][
                "LocalAuthListMaxLength"]
            self.__configuration["ReserveConnectorZeroSupported"] = attribute_data["configuration"][
                "ReserveConnectorZeroSupported"]
            self.__configuration["UnlockConnectorOnEVSideDisconnect"] = attribute_data["configuration"][
                "UnlockConnectorOnEVSideDisconnect"]
            self.__configuration["SupportedFeatureProfiles"] = attribute_data["configuration"][
                "SupportedFeatureProfiles"]
            self.__configuration["StopTxnAlignedData"] = attribute_data["configuration"]["StopTxnAlignedData"]
            self.__configuration["ResetRetries"] = attribute_data["configuration"]["ResetRetries"]
            self.__configuration["StopTransactionOnEVSideDisconnect"] = attribute_data["configuration"][
                "StopTransactionOnEVSideDisconnect"]
            self.__configuration["MeterValuesSampledData"] = attribute_data["configuration"][
                "MeterValuesSampledData"]
            self.__configuration["NumberOfConnectors"] = attribute_data["configuration"][
                "NumberOfConnectors"]
            self.__configuration["MeterValueSampleInterval"] = attribute_data["configuration"][
                "MeterValueSampleInterval"]
            self.__configuration["ClockAlignedDataInterval"] = attribute_data["configuration"][
                "ClockAlignedDataInterval"]
            self.__configuration["ConnectionTimeOut"] = attribute_data["configuration"]["ConnectionTimeOut"]
            self.__configuration["GetConfigurationMaxKeys"] = attribute_data["configuration"]["GetConfigurationMaxKeys"]
            self.__configuration["HeartbeatInterval"] = attribute_data["configuration"]["HeartbeatInterval"]
            self.__configuration["LocalAuthorizeOffline"] = attribute_data["configuration"]["LocalAuthorizeOffline"]
            self.__configuration["LocalPreAuthorize"] = attribute_data["configuration"]["LocalPreAuthorize"]
            self.__configuration["MeterValuesAlignedData"] = attribute_data["configuration"]["MeterValuesAlignedData"]

    def get_configuration_from_file(self):
        with open(ConfigurationManager.__file_name, mode="r") as config_file:
            attribute_data = json.loads(config_file.read())
            config_file.close()
            self.__version = attribute_data["configuration"]["version"]
            self.__configuration["AllowOfflineTxForUnknownId"] = attribute_data["configuration"][
                "AllowOfflineTxForUnknownId"]
            self.__configuration["AuthorizationCacheEnabled"] = attribute_data["configuration"][
                "AuthorizationCacheEnabled"]
            self.__configuration["TransactionMessageAttempts"] = attribute_data["configuration"][
                "TransactionMessageAttempts"]
            self.__configuration["TransactionMessageRetryInterval"] = attribute_data["configuration"][
                "TransactionMessageRetryInterval"]
            self.__configuration["LocalAuthListEnabled"] = attribute_data["configuration"]["LocalAuthListEnabled"]
            self.__configuration["SendLocalListMaxLength"] = attribute_data["configuration"][
                "SendLocalListMaxLength"]
            self.__configuration["LocalAuthListMaxLength"] = attribute_data["configuration"][
                "LocalAuthListMaxLength"]
            self.__configuration["ReserveConnectorZeroSupported"] = attribute_data["configuration"][
                "ReserveConnectorZeroSupported"]
            self.__configuration["UnlockConnectorOnEVSideDisconnect"] = attribute_data["configuration"][
                "UnlockConnectorOnEVSideDisconnect"]
            self.__configuration["SupportedFeatureProfiles"] = attribute_data["configuration"][
                "SupportedFeatureProfiles"]
            self.__configuration["StopTxnAlignedData"] = attribute_data["configuration"]["StopTxnAlignedData"]
            self.__configuration["ResetRetries"] = attribute_data["configuration"]["ResetRetries"]
            self.__configuration["StopTransactionOnEVSideDisconnect"] = attribute_data["configuration"][
                "StopTransactionOnEVSideDisconnect"]
            self.__configuration["MeterValuesSampledData"] = attribute_data["configuration"][
                "MeterValuesSampledData"]
            self.__configuration["NumberOfConnectors"] = attribute_data["configuration"][
                "NumberOfConnectors"]
            self.__configuration["MeterValueSampleInterval"] = attribute_data["configuration"][
                "MeterValueSampleInterval"]
            self.__configuration["ClockAlignedDataInterval"] = attribute_data["configuration"][
                "ClockAlignedDataInterval"]
            self.__configuration["ConnectionTimeOut"] = attribute_data["configuration"]["ConnectionTimeOut"]
            self.__configuration["GetConfigurationMaxKeys"] = attribute_data["configuration"]["GetConfigurationMaxKeys"]
            self.__configuration["HeartbeatInterval"] = attribute_data["configuration"]["HeartbeatInterval"]
            self.__configuration["LocalAuthorizeOffline"] = attribute_data["configuration"]["LocalAuthorizeOffline"]
            self.__configuration["LocalPreAuthorize"] = attribute_data["configuration"]["LocalPreAuthorize"]
            self.__configuration["MeterValuesAlignedData"] = attribute_data["configuration"]["MeterValuesAlignedData"]
