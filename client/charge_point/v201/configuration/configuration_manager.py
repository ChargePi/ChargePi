import json
import os

path = os.path.dirname(os.path.realpath(__file__))


class Controller:
    _file_name = f"{path}/configuration.json"

    def __init__(self, name: str, configuration: dict):
        self.is_enabled: bool = configuration["Enabled"]
        self.name = name
        self._configuration: dict = configuration

    def update_configuration(self, attribute: str, value):
        if self.is_enabled:
            data: dict = self.__read_file()
            if not data[self.name][attribute]["readOnly"]:
                data[self.name][attribute]["value"] = value
                self._configuration[attribute]["value"] = value
                self.__write_to_file(data)
                return "Success"
        return "Failed"

    @property
    def get_configuration(self):
        return self._configuration

    def get_attribute(self, attribute: str):
        try:
            return self._configuration[attribute]["value"]
        except Exception as ex:
            return ""

    def get_attribute_with_units(self, attribute: str):
        if self.is_enabled:
            data: dict = self.__read_file()
            if "unit" in data[self.name][attribute].keys():
                return data[self.name][attribute]["value"], data[self.name][attribute]["unit"]
            return data[self.name][attribute]["value"], ""
        return None

    def __read_file(self) -> dict:
        with open(self._file_name, "r", buffering=True) as settings_file:
            config_data = settings_file.read()
            data: dict = json.loads(config_data)
            settings_file.close()
            return data

    def __write_to_file(self, data):
        with open(self._file_name, "w") as config_file:
            config_file.write(json.dumps(data, indent=2, sort_keys=True))
            config_file.close()


class AuthCtrlr(Controller):

    def __init__(self, configuration: dict):
        super().__init__("AuthCtrlr", configuration)
        self.AuthorizeRemoteStart: bool = self.get_attribute("AuthorizeRemoteStart")
        self.AuthEnabled: bool = self.get_attribute("AuthEnabled")
        self.OfflineTxForUnknownIdEnabled: bool = self.get_attribute("OfflineTxForUnknownIdEnabled")
        self.LocalAuthorizeOffline: bool = self.get_attribute("LocalAuthorizeOffline")
        self.LocalPreAuthorize: bool = self.get_attribute("LocalPreAuthorize")


class DeviceDataCtrlr(Controller):

    def __init__(self, configuration: dict):
        super().__init__("DeviceDataCtrlr", configuration)


class DisplayMessageCtrlr(Controller):

    def __init__(self, configuration: dict):
        super().__init__("DisplayMessageCtrlr", configuration)


class AuthCacheCtrlr(Controller):

    def __init__(self, configuration: dict):
        super().__init__("AuthCacheCtrlr", configuration)


class AlignedDataCtrlr(Controller):

    def __init__(self, configuration: dict):
        super().__init__("AlignedDataCtrlr", configuration)


class CustomizationCtrlr(Controller):

    def __init__(self, configuration: dict):
        super().__init__("CustomizationCtrlr", configuration)


class LocalAuthListCtrlr(Controller):

    def __init__(self, configuration: dict):
        super().__init__("LocalAuthListCtrlr", configuration)


class MonitoringCtrlr(Controller):

    def __init__(self, configuration: dict):
        super().__init__("MonitoringCtrlr", configuration)


class OCPPCommCtrlr(Controller):

    def __init__(self, configuration: dict):
        super().__init__("OCPPCommCtrlr", configuration)
        self.RetryBackOffRepeatTimes: int = self.get_attribute("RetryBackOffRepeatTimes")
        self.RetryBackOffRandomRange, self.RetryBackOffRandomRangeUnit = self.get_attribute_with_units(
            "RetryBackOffRandomRange")
        self.RetryBackOffWaitMinimum, self.RetryBackOffWaitMinimumUnit = self.get_attribute_with_units(
            "RetryBackOffWaitMinimum")
        self.DefaultMessageTimeout, self.DefaultMessageTimeoutUnit = self.get_attribute_with_units(
            "DefaultMessageTimeout")
        self.FileTransferProtocols: list = self.get_attribute("FileTransferProtocols")
        self.NetworkProfileConnectionAttempts: int = self.get_attribute("NetworkProfileConnectionAttempts")
        self.NetworkConfigurationPriority: list = self.get_attribute("NetworkConfigurationPriority")
        self.HeartbeatInterval, self.HeartbeatIntervalUnit = self.get_attribute_with_units(
            "HeartbeatInterval")
        self.OfflineThreshold, self.OfflineThresholdUnit = self.get_attribute_with_units(
            "OfflineThreshold")
        self.MessageAttemptInterval, self.MessageAttemptIntervalUnit = self.get_attribute_with_units(
            "MessageAttemptInterval")
        self.MessageAttempts: int = self.get_attribute("MessageAttempts")
        self.ResetRetries: int = self.get_attribute("ResetRetries")
        self.UnlockOnEVSideDisconnect: bool = self.get_attribute("UnlockOnEVSideDisconnect")


class SecurityCtrlr(Controller):

    def __init__(self, configuration: dict):
        super().__init__("SecurityCtrlr", configuration)
        self.OrganizationName: str = self.get_attribute("OrganizationName")
        self.CertificateEntries: int = self.get_attribute("CertificateEntries")
        self.SecurityProfile: int = self.get_attribute("SecurityProfile")


class SampledDataCtrlr(Controller):

    def __init__(self, configuration: dict):
        super().__init__("SampledDataCtrlr", configuration)
        self.SampledDataEnabled: bool = self.get_attribute("SampledDataEnabled")
        self.TxEndedMeasurands: list = self.get_attribute("TxEndedMeasurands")
        self.TxEndedInterval, self.TxEndedIntervalUnit = self.get_attribute_with_units("TxEndedInterval")
        self.TxStartedMeasurands = self.get_attribute("TxStartedMeasurands")
        self.TxUpdatedMeasurands = self.get_attribute("TxUpdatedMeasurands")
        self.TxUpdatedInterval = self.get_attribute("TxUpdatedInterval")


class SmartChargingCtrlr(Controller):

    def __init__(self, configuration: dict):
        super().__init__("SmartChargingCtrlr", configuration)


class TxCtrlr(Controller):

    def __init__(self, configuration: dict):
        super().__init__("TxCtrlr", configuration)
        self.EVConnectionTimeOut, self.EVConnectionTimeOut = self.get_attribute_with_units("EVConnectionTimeOut")
        self.StopTxOnEVSideDisconnect: bool = self.get_attribute("StopTxOnEVSideDisconnect")
        self.TxStartPoint: list = self.get_attribute("TxStartPoint")
        self.TxStopPoint: list = self.get_attribute("TxStopPoint")
        self.StopTxOnInvalidId: bool = self.get_attribute("StopTxOnInvalidId")


class ClockCtrlr(Controller):

    def __init__(self, configuration: dict):
        super().__init__("ClockCtrlr", configuration)


class ReservationCtrlr(Controller):

    def __init__(self, configuration: dict):
        super().__init__("ReservationCtrlr", configuration)


device_data_ctrlr: DeviceDataCtrlr = None
display_message_ctrlr: DisplayMessageCtrlr = None
auth_ctrlr: AuthCtrlr = None
clock_ctrlr: ClockCtrlr = None
auth_cache_ctrlr: AuthCacheCtrlr = None
aligned_data_ctrl: AlignedDataCtrlr = None
customization_ctrlr: CustomizationCtrlr = None
local_auth_list_ctrlr: LocalAuthListCtrlr = None
monitoring_ctrlr: MonitoringCtrlr = None
ocppcomm_ctrlr: OCPPCommCtrlr = None
security_ctrlr: SecurityCtrlr = None
sampled_data_ctrlr: SampledDataCtrlr = None
smart_charging_ctrlr: SmartChargingCtrlr = None
reservation_ctrlr: ReservationCtrlr = None
tx_ctrlr: TxCtrlr = None


def read_configuration():
    global auth_ctrlr, auth_cache_ctrlr, device_data_ctrlr, display_message_ctrlr, \
        clock_ctrlr, customization_ctrlr, sampled_data_ctrlr, smart_charging_ctrlr, security_ctrlr, \
        ocppcomm_ctrlr, tx_ctrlr, monitoring_ctrlr, local_auth_list_ctrlr, reservation_ctrlr, aligned_data_ctrl
    with open("{path}/configuration.json".format(path=path), "r",
              buffering=True) as configuration:
        config_data = configuration.read()
        data: dict = json.loads(config_data)
        configuration.close()
        auth_ctrlr = AuthCtrlr(data["AuthCtrlr"])
        device_data_ctrlr = DeviceDataCtrlr(data["DeviceDataCtrlr"])
        display_message_ctrlr = DeviceDataCtrlr(data["DisplayMessageCtrlr"])
        customization_ctrlr = CustomizationCtrlr(data["CustomizationCtrlr"])
        security_ctrlr = SecurityCtrlr(data["SecurityCtrlr"])
        sampled_data_ctrlr = SampledDataCtrlr(data["SampledDataCtrlr"])
        smart_charging_ctrlr = SmartChargingCtrlr(data["SmartChargingCtrlr"])
        ocppcomm_ctrlr = OCPPCommCtrlr(data["OCPPCommCtrlr"])
        tx_ctrlr = TxCtrlr(data["TxCtrlr"])
        monitoring_ctrlr = MonitoringCtrlr(data["MonitoringCtrlr"])
        local_auth_list_ctrlr = LocalAuthListCtrlr(data["LocalAuthListCtrlr"])
        auth_cache_ctrlr = AuthCacheCtrlr(data["AuthCacheCtrlr"])
        aligned_data_ctrlr = AlignedDataCtrlr(data["AlignedDataCtrlr"])
        clock_ctrlr = ClockCtrlr(data["ClockCtrlr"])
        reservation_ctrlr = ReservationCtrlr(data["ReservationCtrlr"])
