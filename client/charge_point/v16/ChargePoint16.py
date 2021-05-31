import asyncio
import logging
import time
import os
import sys
import subprocess
from semantic_version import Version
from string_utils import is_full_string
from ocpp.v16 import call, call_result
from ocpp.v16 import ChargePoint as cp
import ocpp.v16.enums as enums
from ocpp.v16.enums import ChargePointStatus as status, ChargePointErrorCode as error_code, Reason as reason, \
    Action as action
from ocpp.routing import on
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import charge_point.responses as responses
from charge_point.data.sessions import ChargingSession as s_responses
from datetime import datetime, timedelta
from charge_point.hardware.components import LEDStrip
from charge_point.v16.connector_v16 import ConnectorV16
from charge_point.connectors.ChargingConnector import ConnectorSettingsManager
from charge_point.scheduler import SchedulerManager
from charge_point.data.auth.authorization_cache import AuthorizationCache as AuthCache
from charge_point.v16.configuration.configuration_manager import ConfigurationManager
import wget
from charge_point.data.update_manager import update_target_version, get_next_version, perform_update

logger = logging.getLogger('chargepi_logger')
_path = os.path.dirname(os.path.realpath(__file__))


class ChargePointV16(cp):
    """
     ChargePoint specific class.
     The class implements OCPP 1.6 JSON/WS protocol requests/responses and handles background logic.
    """

    __instance = None

    @staticmethod
    def getInstance():
        if ChargePointV16.__instance is not None:
            return ChargePointV16.__instance
        else:
            raise Exception("Not initialized")

    def __init__(self, id, connection, charge_point_info: dict, hardware_info: dict):
        if ChargePointV16.__instance is not None:
            return
        self.__charging_configuration: ConfigurationManager = ConfigurationManager()
        super().__init__(id, connection,
                         int(self.__charging_configuration.get_configuration_variable_value("ConnectionTimeOut")))
        self.__scheduler: AsyncIOScheduler = SchedulerManager.getScheduler()
        ChargePointV16.__instance = self
        # Add a heartbeat to the scheduler
        self.__scheduler.add_job(self.heartbeat, 'interval',
                                 seconds=int(self.__charging_configuration.get_configuration_variable_value(
                                     "HeartbeatInterval")))
        self.__is_available: bool = True
        self.charge_point_info: dict = charge_point_info
        self.hardware_info: dict = hardware_info
        self._ChargePointConnectors: list = list()
        self.__authorization_cache: AuthCache = AuthCache(
            self.__charging_configuration.get_configuration_variable_value("AuthorizationCacheEnabled") == "true")
        self.__authorization_cache.set_max_cached_tags(
            self.__charging_configuration.get_configuration_variable_value("LocalListMaxLength") == "true")
        connectors = ConnectorSettingsManager.get_connectors_from_evse(1)
        # Add all the connectors specified in the connectors.json
        for connector in connectors:
            relay_settings: dict = connector["relay"]
            power_meter_settings: dict = connector["power_meter"]
            power_meter_settings["min_power"] = hardware_info["min_power"]
            self.__add_connector(connector_id=connector["id"],
                                 connector_type=connector["type"],
                                 relay_settings=relay_settings,
                                 power_meter_settings=power_meter_settings)
        # Sort by EVSE ID
        # self._ChargePointConnectors.sort(key=(lambda conn: (conn.evse_id, conn.connector_id)))
        self._update_LED_status(self._get_LED_colors())

    def __add_connector(self, connector_id: int, connector_type: str, power_meter_settings: dict, relay_settings: dict):
        """
        Add a new Connector to the list of connectors if it doesn't exist already.
        Connector ID must be greater than the previous' connector ID.
        :param connector_id: Consecutive connector ID
        :return:
        """
        if self.__find_connector_with_id(connector_id) is None and connector_id > 0:
            list_length: int = len(self._ChargePointConnectors)
            if list_length != 0 and connector_id != self._ChargePointConnectors[list_length - 1].connector_id + 1:
                return
            connector: ConnectorV16 = ConnectorV16(evse_id=1,
                                                   connector_id=connector_id,
                                                   conn_type=connector_type,
                                                   relay_pin=int(relay_settings["relay_pin"]),
                                                   relay_state=int(relay_settings["default_state"]),
                                                   power_meter_pin=int(power_meter_settings["power_meter_pin"]),
                                                   power_meter_bus=int(power_meter_settings["spi_bus"]),
                                                   power_meter_shunt_offset=float(
                                                       power_meter_settings["shunt_offset"]),
                                                   power_meter_voltage_divider_offset=float(
                                                       power_meter_settings["voltage_divider_offset"]),
                                                   power_meter_min_power=float(power_meter_settings["min_power"]),
                                                   max_charging_time=self.charge_point_info["max_charging_time"],
                                                   stop_transaction_function=self.__stop_charging_connector_with_id,
                                                   send_meter_values_function=self.send_meter_values)
            self._ChargePointConnectors.append(connector)

    @property
    def get_connectors(self) -> list:
        return self._ChargePointConnectors

    def __get_connector_index(self, connector: ConnectorV16):
        """
        Get index of a connector in the connector list.
        :param connector: A connector
        :return: An index of the connector
        """
        try:
            return self.get_connectors.index(connector)
        except ValueError as ex:
            logger.debug("Unable to get connector index", exc_info=ex)
            return -1

    def __find_charging_connectors(self) -> list:
        """
        Find all connectors with charging status.
        :return: List of connectors
        """
        array = []
        for connector in self.get_connectors:
            if connector.is_charging():
                array.append(connector)
        return array

    def __find_available_connector(self) -> ConnectorV16:
        """
        Find the first available connector.
        :return: A connector
        """
        return next((connector for connector in self.get_connectors if connector.is_available()), None)

    def __find_connector_with_id(self, connector_id: int) -> ConnectorV16:
        """
        Find a specific connector.
        :param connector_id: A connector ID
        :return: A connector
        """
        return next((connector for connector in self.get_connectors
                     if connector.connector_id == connector_id), None)

    def __find_connector_with_transaction_id(self, transaction_id: str) -> ConnectorV16:
        """
        Find a connector that has a transaction ID equal to the one specified.
        :param transaction_id: A transaction ID
        :return: A connector
        """
        return next((connector for connector in self.__find_charging_connectors()
                     if connector.get_current_transaction_id == str(transaction_id)), None)

    def __find_connector_with_tag_id(self, id_tag: str) -> ConnectorV16:
        """
        Find a connector that has a tag ID equal to the one specified.
        :param id_tag: A tag ID
        :return: A connector
        """
        return next((connector for connector in self.get_connectors
                     if connector.get_current_tag_id == id_tag), None)

    async def __is_tag_authorized(self, id_tag: str, is_remote_request: bool) -> bool:
        """
        Check if the tag exists in Authentication cache and/or authorize with the central system.
        :param id_tag: Tag ID
        :return: True or false
        """
        print("Authorizing tag")
        if self.__charging_configuration.get_configuration_variable_value("LocalPreAuthorize") == "true" \
                and self.__charging_configuration.get_configuration_variable_value(
            "AuthorizationCacheEnabled") == "true":
            if await self.__authorization_cache.is_tag_authorized(id_tag):
                # If the tag is in auth cache and valid, don't wait for authorization
                self.__scheduler.add_job(self.__authorize_tag, 'date',
                                         run_date=(datetime.now() + timedelta(seconds=5)),
                                         args=[id_tag])
                return True
        elif is_remote_request and \
                not self.__charging_configuration.get_configuration_variable_value("AuthorizeRemoteTx") == "true":
            return True
        id_tag_info: dict = await self.__authorize_tag(id_tag)
        print(id_tag_info)
        return id_tag_info["status"] == enums.AuthorizationStatus.accepted

    async def __authorize_tag(self, id_tag: str):
        """
        Authorize the tag with the server. If Authorization Cache is enabled, (re)write the tag info in the cache.
        :param id_tag: Tag ID
        :return: Response of the authentication request
        """
        request = call.AuthorizePayload(id_tag=id_tag)
        auth_response = await self.call(request)
        tag_info: dict = auth_response.id_tag_info
        if self.__charging_configuration.get_configuration_variable_value("AuthorizationCacheEnabled") == "true":
            self.__scheduler.add_job(self.__authorization_cache.update_tag_info,
                                     args=[id_tag, tag_info])
        if tag_info["status"] == enums.AuthorizationStatus.blocked:
            connector: ConnectorV16 = self.__find_connector_with_tag_id(id_tag)
            if isinstance(connector, ConnectorV16):
                self.__scheduler.add_job(self.__stop_charging_connector_with_id,
                                         args=[connector.connector_id, id_tag, reason.deAuthorized])
        return tag_info

    async def indicate_card_read(self):
        print("Indicate card read")
        if self.hardware_info["LED_indicator"]["type"] == "WS281x":
            colors = self._get_LED_colors()
            for _ in range(2):
                self._update_LED_status(f"{colors} {LEDStrip.WHITE}")
                await asyncio.sleep(.3)
                self._update_LED_status(f"{colors} {LEDStrip.OFF}")
                await asyncio.sleep(.3)
            pass
        elif self.hardware_info["LED_indicator"]["type"] == "simple":
            pass

    async def indicate_card_rejected(self):
        print("Indicate card rejected")
        if self.hardware_info["LED_indicator"]["type"] == "WS281x":
            colors = self._get_LED_colors()
            for _ in range(2):
                self._update_LED_status(f"{colors} {LEDStrip.RED}")
                await asyncio.sleep(.3)
                self._update_LED_status(f"{colors} {LEDStrip.OFF}")
                await asyncio.sleep(.3)
        elif self.hardware_info["LED_indicator"]["type"] == "simple":
            pass

    def _get_LED_colors(self) -> str:
        """
        Get the status of all the connectors and determine which color they should have. Return the colors as a string.
        """
        colors = ""
        for index, connector in enumerate(self.get_connectors):
            status_color = LEDStrip.RED
            if connector.is_available():
                status_color = LEDStrip.GREEN
            elif connector.is_charging():
                status_color = LEDStrip.BLUE
            elif connector.is_occupied():
                status_color = LEDStrip.YELLOW
            elif connector.is_unavailable():
                status_color = LEDStrip.ORANGE
            colors += f" {status_color}"
        return colors

    def _update_LED_status(self, colors: str):
        """
        Update status of an LED of a connector
        :param colors: Colors of the LEDs in a string
        :return:
        """
        if self.hardware_info["LED_indicator"]["type"] == "WS281x":
            command = f"sudo python3 {_path}/../hardware/leds/LEDStrip.py{colors}"
            print(command)
            subprocess.Popen(command, shell=True)
        elif self.hardware_info["LED_indicator"]["type"] == "simple":
            pass

    @property
    def is_available(self) -> bool:
        return self.__is_available

    async def handle_charging_request(self, id_tag: str) -> (int, str):
        """
        Handle a charging request initiated by the tag reader.
        Stop charging if it finds a connector with the same tag ID, else it will start charging.
        :param id_tag: Tag ID
        :return: Connector ID and response
        """
        handle_tag_str: str = f"Handling request for tag {id_tag}"
        logger.info(handle_tag_str)
        print(handle_tag_str)
        connector = self.__find_connector_with_tag_id(id_tag)
        if isinstance(connector, ConnectorV16):
            connector_id: int = connector.connector_id
            connector_index: int = self.__get_connector_index(connector)
            response = connector_index + 1, await self.__stop_charging_connector_with_id(connector_id=connector_id,
                                                                                         id_tag=id_tag,
                                                                                         stop_reason=reason.local)
        else:
            response = await self.__start_charging(id_tag=id_tag)
        response_str: str = f"Response for tag {response}"
        logger.debug(response_str)
        print(response_str)
        return response

    async def __start_charging(self, id_tag: str) -> (int, str):
        """
        Start the charging process on the first available connector.
        :param id_tag: RFID tag
        :return: Connector index and response
        """
        connector = self.__find_available_connector()
        if isinstance(connector, ConnectorV16):
            response = await self.__start_charging_connector_with_id(id_tag=id_tag,
                                                                     connector_id=connector.connector_id)
            connector_index: int = self.__get_connector_index(connector)
            return connector_index + 1, response
        return -1, responses.NoAvailableConnectors

    async def __start_charging_connector_with_id(self, id_tag: str, connector_id: int,
                                                 is_remote_request: bool = False, retry_attempt: int = 0) -> str:
        """
        Start the charging process on a specific connector. Charging starts with checking the card
        authorization in the cache and/or server, then sending a transaction request.
        If all goes well, allow the hardware to start charging.
        :param id_tag: tag ID
        :param connector_id: A connector ID
        :return: Response
        """
        connector = self.__find_connector_with_id(connector_id)
        if isinstance(connector, ConnectorV16) \
                and (connector.is_available() or connector.is_preparing()) \
                and self.is_available \
                and self.__find_connector_with_tag_id(id_tag) is None:
            # Authorize the card before charging
            if not await self.__is_tag_authorized(id_tag=id_tag, is_remote_request=is_remote_request):
                return responses.UnauthorizedCard
            # Send a transaction request to the server
            await self._change_connector_status(connector_id=connector_id,
                                                err_code=error_code.noError,
                                                connector_status=status.preparing)
            request = call.StartTransactionPayload(timestamp=datetime.utcnow().isoformat(),
                                                   meter_start=0,
                                                   id_tag=id_tag,
                                                   connector_id=connector_id)
            server_response = await self.call(request)
            tag_info = server_response.id_tag_info
            # If the server accepts, start charging
            if tag_info["status"] == enums.RemoteStartStopStatus.accepted or tag_info["status"] == "ConcurrentTx":
                connector_response = connector.start_charging(transaction_id=str(server_response.transaction_id),
                                                              id_tag=id_tag,
                                                              meter_sample_time=int(
                                                                  self.__charging_configuration.get_configuration_variable_value(
                                                                      "MeterValueSampleInterval")),
                                                              connector_timeout=int(
                                                                  self.__charging_configuration.get_configuration_variable_value(
                                                                      "ConnectionTimeOut")))
                if connector_response == s_responses.SessionStartSuccess:
                    start_charging_log: str = f"Started charging at connector {connector_id}"
                    print(start_charging_log)
                    logger.debug(start_charging_log)
                    await self._change_connector_status(connector_id=connector_id,
                                                        err_code=error_code.noError,
                                                        connector_status=status.charging)
                    return responses.StartChargingSuccess
                else:
                    rejected_log: str = f"Session rejected at connector {connector_id}"
                    print(rejected_log)
                    logger.debug(rejected_log)
                    await self.__stop_charging_connector_with_id(connector_id=connector_id,
                                                                 id_tag=id_tag,
                                                                 stop_reason=reason.local,
                                                                 is_remote_request=is_remote_request)
                    return responses.StartChargingFail
            else:
                transaction_rejected_log: str = f"Transaction rejected at connector {connector_id}"
                print(transaction_rejected_log)
                logger.debug(transaction_rejected_log)
                await self._change_connector_status(connector_id=connector_id,
                                                    err_code=error_code.noError,
                                                    connector_status=status.available)
                return responses.StartChargingFail
        else:
            already_charging_log: str = f"Connector {connector_id} unavailable or already charging"
            logger.debug(already_charging_log)
            print(already_charging_log)
            return responses.ConnectorUnavailable

    async def __stop_charging_connector_with_id(self, connector_id: int, id_tag: str, stop_reason: reason,
                                                is_remote_request: bool = False) -> str:
        """
        Stop the charging process on a connector.
        :param connector_id: A connector ID
        :return: Response
        """
        connector = self.__find_connector_with_id(connector_id)
        if isinstance(connector, ConnectorV16) and (connector.is_charging() or connector.is_preparing()):
            # Edge case
            if stop_reason == reason.evDisconnected:
                ev_disconnected_str: str = f"Connector {connector_id} disconnected from EV"
                print(ev_disconnected_str)
                logger.debug(ev_disconnected_str)
                if self.__charging_configuration.get_configuration_variable_value(
                        "StopTransactionOnEVSideDisconnect") == "false":
                    connector.stop_charging()
                    await self._update_status_at_stoppage(connector_id=connector_id, reason=stop_reason)
                    return responses.StopChargingSuccess
            # If the tag supplied is not the same as tag supplied at the start, reauthorize
            if id_tag != "" and id_tag != connector.get_current_tag_id:
                if not await self.__is_tag_authorized(id_tag=id_tag, is_remote_request=is_remote_request):
                    return responses.UnauthorizedCard
            energy_consumed: int = 0
            if connector.get_avg_power > 0:
                try:
                    charging_time_seconds = (
                            datetime.now() - datetime.fromisoformat(connector.get_session_started)).total_seconds()
                    energy_consumed = int(connector.get_avg_power * charging_time_seconds)
                except Exception:
                    pass
            request = call.StopTransactionPayload(transaction_id=int(connector.get_current_transaction_id),
                                                  meter_stop=energy_consumed,
                                                  id_tag=id_tag,
                                                  timestamp=datetime.utcnow().isoformat(),
                                                  reason=stop_reason)
            await self.call(request)
            connector.stop_charging()
            await self._update_status_at_stoppage(connector_id=connector_id, reason=stop_reason)
            stop_transaction_log: str = f"Stopping transaction {connector.get_current_transaction_id} at connector {connector_id}"
            print(stop_transaction_log)
            logger.debug(stop_transaction_log)
            return responses.StopChargingSuccess
        not_charging_connector: str = f"Connector {connector_id} not found or is not charging"
        logger.debug(not_charging_connector)
        print(not_charging_connector)
        return responses.ConnectorUnavailable

    async def __stop_charging_connector_with_transaction(self, transaction_id: str) -> str:
        """
        Stop the charging process on a connector with a certain transaction ID.
        :param transaction_id: A transaction ID
        :return: Status
        """
        connector = self.__find_connector_with_transaction_id(transaction_id)
        if isinstance(connector, ConnectorV16):
            return await self.__stop_charging_connector_with_id(connector_id=connector.connector_id,
                                                                id_tag="",
                                                                stop_reason=reason.remote,
                                                                is_remote_request=True)
        return responses.NoConnectorWithTransaction

    async def send_boot_notification(self):
        """
        Connect and notify the central system at boot. Perform self diagnostics and restore any transactions.
        :return:
        """
        request = call.BootNotificationPayload(charge_point_vendor=self.charge_point_info["vendor"],
                                               charge_point_model=self.charge_point_info["model"])
        server_response = await self.call(request)
        if server_response.status == enums.RegistrationStatus.accepted:
            logger.debug("Connected to central system.")
            print("Connected to central system.")
            self.__is_available = True
            await self._restore_state()
        else:
            logger.debug("Cannot connect to the central system.")
            print("Cannot connect to the central system.")
            self.__is_available = False

    async def _restore_state(self):
        """
        Try to restore the state from connectors.json file with session attributes.
        :return:
        """
        for connector in self.get_connectors:
            connector_id: int = connector.connector_id
            evse_id: int = connector.evse_id
            previous_status, session_info = ConnectorSettingsManager.get_connector_status(evse_id, connector_id)
            # Notify the central system of the previous state
            await self._change_connector_status(connector_id=connector_id,
                                                connector_status=status(previous_status),
                                                err_code=enums.ChargePointErrorCode.noError)
            if previous_status == status.charging:
                # Try to resume charging & notify about success
                response = connector.resume_charging(session_info=session_info,
                                                     meter_sample_time=int(
                                                         self.__charging_configuration.get_configuration_variable_value(
                                                             "MeterValueSampleInterval")),
                                                     connector_timeout=int(
                                                         self.__charging_configuration.get_configuration_variable_value(
                                                             "ConnectionTimeOut")))
                logger.debug(f"Restoring to charging state at connector {connector.connector_id} returned {response}")
                if response == s_responses.SessionResumeSuccess:
                    await self._change_connector_status(connector_id=connector_id,
                                                        connector_status=status.charging,
                                                        err_code=enums.ChargePointErrorCode.noError)
                else:
                    await self._change_connector_status(connector_id=connector_id,
                                                        connector_status=status.available,
                                                        err_code=enums.ChargePointErrorCode.noError)
                    self.__scheduler.add_job(self.__stop_charging_connector_with_transaction,
                                             args=[session_info["transaction_id"]])
            elif previous_status == status.preparing:
                await self._change_connector_status(connector_id=connector_id,
                                                    connector_status=status.available,
                                                    err_code=enums.ChargePointErrorCode.noError)
                self.__scheduler.add_job(self.__start_charging_connector_with_id,
                                         args=[session_info["tag_id"], connector.connector_id, False])
                logger.debug(
                    f"Attempting to (re)start transaction at connector {connector.connector_id} with state {previous_status}")
            else:
                await self._change_connector_status(connector_id=connector_id,
                                                    connector_status=status(previous_status),
                                                    err_code=enums.ChargePointErrorCode.noError)

    async def send_meter_values(self, connector_id: int, samples: list):
        """
        Send updates of the power meter on a specific connector.
        :param connector_id: A Connector ID
        :return:
        """
        connector = self.__find_connector_with_id(connector_id)
        if isinstance(connector, ConnectorV16) and connector.is_charging():
            send_meter_values_str: str = f"Sending values to the central system at connector {connector_id}"
            logger.debug(send_meter_values_str)
            print(send_meter_values_str)
            for sample in samples:
                for value in sample:
                    if float(value["sampled_value"]["value"]) < float(self.hardware_info["min_power"]):
                        samples.remove(sample)
                        continue
                    value["sampled_value"][
                        "measurand"] = self.__charging_configuration.get_configuration_variable_value(
                        "MeterValuesSampledData")
            request = call.MeterValuesPayload(meter_value=samples,
                                              transaction_id=int(connector.get_current_transaction_id),
                                              connector_id=connector_id)
            await self.call(request)

    async def _change_connector_status(self, connector_id: int, connector_status: status, err_code: error_code):
        """
        Notify the system with a specific connector's state.
        :param err_code: Error code
        :param connector_id: A connector ID
        :param connector_status: Status of the connector
        :return:
        """
        connector = self.__find_connector_with_id(connector_id)
        if isinstance(connector, ConnectorV16):
            changing_status_str: str = f"Changing status to {connector_status.value}"
            print(changing_status_str)
            logger.debug(changing_status_str)
            connector.set_status(connector_status)
            await self.notify_connector_status(connector_id, err_code)
            await ConnectorSettingsManager.update_connector_status(connector.evse_id, connector.connector_id,
                                                                   connector.get_status())
            if connector.is_charging() or connector.is_available() or connector.is_faulted() or connector.is_reserved() \
                    or connector.is_unavailable():
                self._update_LED_status(self._get_LED_colors())

    async def notify_connector_status(self, connector_id: int, err_code: error_code = error_code.noError):
        connector = self.__find_connector_with_id(connector_id)
        if isinstance(connector, ConnectorV16):
            request = call.StatusNotificationPayload(connector_id=connector_id,
                                                     timestamp=datetime.now().isoformat(),
                                                     error_code=err_code,
                                                     status=connector.get_status())
            await self.call(request)

    async def _update_status_at_stoppage(self, connector_id: int, reason: reason):
        if reason == reason.local or reason == reason.powerLoss:
            await self._change_connector_status(connector_id=connector_id,
                                                err_code=error_code.noError,
                                                connector_status=status.available)
        elif reason == reason.remote or reason == reason.deAuthorized:
            await self._change_connector_status(connector_id=connector_id,
                                                err_code=error_code.noError,
                                                connector_status=status.suspendedevse)
            await self._change_connector_status(connector_id=connector_id,
                                                err_code=error_code.noError,
                                                connector_status=status.finishing)
            await self._change_connector_status(connector_id=connector_id,
                                                err_code=error_code.noError,
                                                connector_status=status.available)
        elif reason == reason.emergencyStop or reason == reason.other:
            await self._change_connector_status(connector_id=connector_id,
                                                err_code=error_code.noError,
                                                connector_status=status.finishing)
            await self._change_connector_status(connector_id=connector_id,
                                                err_code=error_code.noError,
                                                connector_status=status.faulted)
        elif reason == reason.evDisconnected:
            await self._change_connector_status(connector_id=connector_id,
                                                err_code=error_code.noError,
                                                connector_status=status.suspendedev)
            await self._change_connector_status(connector_id=connector_id,
                                                err_code=error_code.noError,
                                                connector_status=status.finishing)
            await self._change_connector_status(connector_id=connector_id,
                                                err_code=error_code.noError,
                                                connector_status=status.available)
        else:
            await self._change_connector_status(connector_id=connector_id,
                                                err_code=error_code.noError,
                                                connector_status=status.unavailable)

    def cleanup(self, reason: reason):
        """
        Stops the schedulers and ongoing transactions before exiting.
        :return:
        """
        logger.debug("Cleaning up..")
        print("Cleaning up..")
        try:
            # Try to stop all ongoing transactions
            for connector in self.__find_charging_connectors():
                job_id: str = f"cleanup_connector_{connector.connector_id}"
                self.__scheduler.add_job(self.__stop_charging_connector_with_id,
                                         args=[connector.connector_id, "", reason],
                                         id=job_id)
                print(job_id)
            # Wait for all jobs to be complete
            while len(self.__scheduler.get_jobs()) != 0:
                time.sleep(.3)
                print("Waiting for schedulers to clear..")
            # Save status of each connector
            for connector in self.get_connectors:
                connector.save_status_at_cleanup()
            print("Cleaned up")
            logger.debug("Cleaned up")
        except Exception as ex:
            msg: str = f"Exception at ChargePoint cleanup: {ex}"
            print(msg)
            logger.debug(msg, exc_info=ex)
        finally:
            self.__scheduler.shutdown(wait=False)
            self._clear_leds()

    def _clear_leds(self):
        # Clear all LEDs
        leds = ""
        for _ in range(len(self.get_connectors)):
            leds += " 0"
        subprocess.Popen(f"sudo python3 {_path}/../hardware/leds/LEDStrip.py{leds}", shell=True)

    async def heartbeat(self):
        """
        Sends a heartbeat to the central system.
        :return:
        """
        print("Sent heartbeat")
        await self.call(call.HeartbeatPayload())

    @on(action.RemoteStartTransaction)
    async def remote_start_transaction(self, id_tag: str, connector_id: int = 0):
        """
        Handles server's request to start a charging session.
        :param connector_id: A connector ID
        :param id_tag: RFID ID
        :return:
        """
        remote_transaction_log: str = f"Requested remote start for tag {id_tag} at connector {connector_id}"
        logger.debug(remote_transaction_log)
        print(remote_transaction_log)
        if connector_id == 0:
            connector = self.__find_available_connector()
            connector_id = connector.connector_id
        else:
            connector = self.__find_connector_with_id(connector_id)
        if isinstance(connector, ConnectorV16) and connector.is_available():
            self.__scheduler.add_job(self.__start_charging_connector_with_id, 'date',
                                     run_date=(datetime.now() + timedelta(seconds=3)),
                                     args=[id_tag, connector_id, True],
                                     id="StartRemoteTx")
            return call_result.RemoteStartTransactionPayload(enums.RemoteStartStopStatus.accepted)
        return call_result.RemoteStartTransactionPayload(enums.RemoteStartStopStatus.rejected)

    @on(action.RemoteStopTransaction)
    async def remote_stop_transaction(self, transaction_id: int):
        """
        Handles server's request to stop a charging session.
        :param transaction_id: Transaction ID
        :return: Accepted or Rejected constants
        """
        remote_transaction_log: str = f"Requested remote stop for transaction {transaction_id}"
        logger.debug(remote_transaction_log)
        print(remote_transaction_log)
        connector = self.__find_connector_with_transaction_id(transaction_id=str(transaction_id))
        if isinstance(connector, ConnectorV16):
            self.__scheduler.add_job(self.__stop_charging_connector_with_transaction, 'date',
                                     run_date=(datetime.now() + timedelta(seconds=3)),
                                     args=[str(transaction_id)],
                                     id="StopRemoteTx")
            return call_result.RemoteStopTransactionPayload(enums.RemoteStartStopStatus.accepted)
        return call_result.RemoteStopTransactionPayload(enums.RemoteStartStopStatus.rejected)

    @on(action.ChangeAvailability)
    async def change_availability(self, connector_id: int, type: str):
        """
        Set availability status of a connector.
        :param type:
        :param connector_id: A connector ID
        :return: Accepted, rejected or scheduled
        """
        connector = self.__find_connector_with_id(connector_id)
        if connector_id == 0:
            if type == enums.AvailabilityType.inoperative:
                self.__is_available = False
            else:
                self.__is_available = True
            return call_result.ChangeAvailabilityPayload(enums.AvailabilityStatus.accepted)
        if isinstance(connector, ConnectorV16):
            if type == enums.AvailabilityType.inoperative:
                status: enums.ChargePointStatus = enums.ChargePointStatus.unavailable
            else:
                status = enums.ChargePointStatus.available
            if connector.is_charging() or connector.is_preparing():
                self.__scheduler.add_job(self._update_LED_status, args=[self._get_LED_colors()])
                return call_result.ChangeAvailabilityPayload(enums.AvailabilityStatus.scheduled)
            else:
                self.__scheduler.add_job(self._change_connector_status,
                                         args=[connector.connector_id,
                                               status,
                                               error_code.noError])
                return call_result.ChangeAvailabilityPayload(enums.AvailabilityStatus.accepted)
        return call_result.ChangeAvailabilityPayload(enums.AvailabilityStatus.rejected)

    @on(action.UnlockConnector)
    async def unlock_connector(self, connector_id: int):
        """
        Unlock the specified connector.
        :param connector_id: A connector ID
        :return: Unlocked or Unsupported
        """
        connector = self.__find_connector_with_id(connector_id)
        if isinstance(connector, ConnectorV16) and connector.is_charging():
            self.__scheduler.add_job(self.__stop_charging_connector_with_id, 'date',
                                     run_date=(datetime.now() + timedelta(seconds=3)),
                                     args=[connector_id, "", reason.unlockCommand],
                                     id="StopRemoteTx")
            return call_result.UnlockConnectorPayload(enums.UnlockStatus.unlocked)
        return call_result.UnlockConnectorPayload(enums.UnlockStatus.unlockFailed)

    @on(action.UpdateFirmware)
    async def update_firmware(self, location: str, retrieve_date: str, retries: int = 3, retry_interval: int = 60):
        """
        Download and update the firmware.
        :param location: URI of the firmware
        :param retrieve_date:
        :param retries:
        :param retry_interval:
        :return:
        """
        debug_str: str = "Requested firmware update"
        logger.debug(debug_str)
        print(debug_str)
        try:
            next_version: Version = await get_next_version()
            file_name: str = f"client_{next_version}"
            file_path: str = f"{_path}/../../updates/{file_name}.tar.gz"
            wget.download(location, file_path)
            os.system("tar -xf " + file_path)
            await update_target_version(version=str(next_version))
            update_date = (datetime.now() + timedelta(seconds=3))
            if is_full_string(retrieve_date):
                update_date = retrieve_date
            self.__scheduler.add_job(perform_update, 'date',
                                     run_date=update_date,
                                     args=[file_name, retries, retry_interval])
        except Exception as ex:
            logger.debug("Firmware update failed", exc_info=ex)
            print("Firmware update failed")
        return call_result.UpdateFirmwarePayload()

    @on(action.ReserveNow)
    async def reserve_connector(self, expiry_date: str, id_tag: str, reservation_id: int, connector_id: int = 0):
        """
        Reserve a connector for a charging session on a set date.
        :param connector_id: Connector ID
        :param expiry_date: Expiry Date
        :param id_tag: RFID tag
        :param reservation_id: Reservation ID
        :return: Success response
        """
        if connector_id == 0:
            connector = self.__find_available_connector()
        else:
            connector = self.__find_connector_with_id(connector_id)
        if isinstance(connector, ConnectorV16):
            response = connector.add_reservation(expiry_date=expiry_date,
                                                 reservation_id=str(reservation_id),
                                                 tag_id=id_tag)
            reserve_log: str = f"Reserve connector {connector_id} response {response}"
            logger.debug(reserve_log)
            print(reserve_log)
            if response == s_responses.ReservationSuccess:
                self.__scheduler.add_job(self._change_connector_status,
                                         args=[connector.connector_id,
                                               status.reserved,
                                               error_code.noError])
                return call_result.ReserveNowPayload(enums.ReservationStatus.accepted)
            elif response == s_responses.AlreadyReserved:
                return call_result.ReserveNowPayload(enums.ReservationStatus.occupied)
            elif response == s_responses.ReservationFailed:
                return call_result.ReserveNowPayload(enums.ReservationStatus.faulted)
        return call_result.ReserveNowPayload(enums.ReservationStatus.rejected)

    @on(action.CancelReservation)
    async def cancel_reservation(self, reservation_id: int):
        """
        Cancel a reservation on a connector with a reservation ID.
        :param reservation_id:
        :return:
        """
        for connector in self.get_connectors:
            if connector.has_reservation(str(reservation_id)):
                connector.cancel_reservation(reservation_id)
                self.__scheduler.add_job(self._change_connector_status,
                                         args=[connector.connector_id,
                                               status.available,
                                               error_code.noError])
                return call_result.CancelReservationPayload(enums.CancelReservationStatus.accepted)
        return call_result.CancelReservationPayload(enums.CancelReservationStatus.rejected)

    @on(action.GetConfiguration)
    async def get_configuration(self, key: list = None):
        """
        Respond to server's request to get configuration information
        :param key: list of configuration keys
        :return:
        """
        configuration: list = []
        unknown_keys: list = []
        if key is None:
            configuration = [({"key": key,
                               "readonly": self.__charging_configuration.get_configuration_variable(key)["readOnly"],
                               "value": self.__charging_configuration.get_configuration_variable(key)["value"]}) for
                             key in self.__charging_configuration.get_configuration.keys()]
        else:
            for item in key:
                attribute = self.__charging_configuration.get_configuration_variable(key=item)
                if attribute["key"] != "not_found":
                    configuration.append(attribute)
                else:
                    unknown_keys.append(item)
        return call_result.GetConfigurationPayload(configuration_key=configuration, unknown_key=unknown_keys)

    @on(action.ChangeConfiguration)
    async def change_configuration(self, key: str, value: str):
        """
        Change configuration attribute with key and if writable, replace the value
        :param key: Key of the attribute
        :param value: Value to be replaced with
        :return:
        """
        if self.__charging_configuration.get_configuration_variable(key) is not {"key": "not_found"}:
            response = await self.__charging_configuration.update_configuration_variable(key=key, value=value)
            logger.info(f"Change configuration response {response}")
            if response == "Success":
                return call_result.ChangeConfigurationPayload(enums.ConfigurationStatus.accepted)
            else:
                return call_result.ChangeConfigurationPayload(enums.ConfigurationStatus.rejected)
        return call_result.ChangeConfigurationPayload(enums.ConfigurationStatus.notSupported)

    @on(action.ClearCache)
    async def clear_cache(self):
        """
        Clear authorization cache
        :return:
        """
        if await self.__authorization_cache.clear_cache() == "Success":
            return call_result.ClearCachePayload(enums.ClearCacheStatus.accepted)
        else:
            return call_result.ClearCachePayload(enums.ClearCacheStatus.rejected)

    @on(action.GetLocalListVersion)
    async def get_list_version(self):
        """
        Synchronize server's and client authorization list.
        :return:
        """
        return call_result.GetLocalListVersionPayload(list_version=self.__authorization_cache.get_version)

    @on(action.SendLocalList)
    async def get_list(self, list_version: int, update_type: enums.UpdateType, local_authorization_list: list):
        """
        Synchronize server's and client authorization list.
        :param list_version:
        :param update_type:
        :param local_authorization_list:
        :return:
        """
        if self.__authorization_cache.get_version != list_version:
            return call_result.SendLocalListPayload(enums.UpdateStatus.versionMismatch)
        elif update_type == enums.UpdateType.differential or update_type == enums.UpdateType.full:
            await self.__authorization_cache.update_cached_tags(local_authorization_list)
            return call_result.SendLocalListPayload(enums.UpdateStatus.accepted)
        else:
            return call_result.SendLocalListPayload(enums.UpdateStatus.notSupported)

    def __soft_reset(self):
        self.cleanup(reason=reason.softReset)
        os.execv(sys.executable, ['sudo python3'] + sys.argv)

    def __hard_reset(self):
        self.cleanup(reason=reason.hardReset)
        os.system("sudo reboot")

    @on(action.Reset)
    async def reset_request(self, type: str):
        """
        Respond to reset request. When requested to hard reset, reboot the system, else just reset the program.
        :param type: Hard or soft reset type
        :return:
        """
        if type == enums.ResetType.hard:
            self.__scheduler.add_job(self.__hard_reset, 'date',
                                     run_date=(datetime.now() + timedelta(seconds=5)),
                                     id="hard_reset")
        else:
            self.__scheduler.add_job(self.__soft_reset, 'date',
                                     run_date=(datetime.now() + timedelta(seconds=5)),
                                     id="soft_reset")
        return call_result.ResetPayload(status=enums.ResetStatus.accepted)

    @on(action.DataTransfer)
    async def transfer_data(self, vendor_id: str, message_id: str, data: str):
        """
        Transfer data from the central system
        :param vendor_id:
        :param message_id:
        :param data:
        :return:
        """
        return call_result.DataTransferPayload(enums.DataTransferStatus.rejected)

    @on(enums.Action.TriggerMessage)
    async def trigger_message(self, requested_message: enums.MessageTrigger, connector_id: int):
        """
        Respond to a trigger message.
        :param requested_message:
        :param connector_id:
        :return:
        """
        trigger_msg_str: str = f"Received trigger message: {requested_message.value}"
        logger.debug(trigger_msg_str)
        print(trigger_msg_str)
        connector: ConnectorV16 = self.__find_connector_with_id(connector_id)
        if not isinstance(connector, ConnectorV16):
            return call_result.DataTransferPayload(enums.DataTransferStatus.rejected)
        if requested_message == enums.MessageTrigger.statusNotification:
            self.__scheduler.add_job(self.notify_connector_status, args=[connector_id], max_instances=1)
        elif requested_message == enums.MessageTrigger.heartbeat:
            self.__scheduler.add_job(self.heartbeat)
        elif requested_message == enums.MessageTrigger.firmwareStatusNotification:
            await self.call(call.FirmwareStatusNotificationPayload(enums.FirmwareStatus.downloadFailed))
        elif requested_message == enums.MessageTrigger.bootNotification:
            pass
        else:
            return call_result.TriggerMessagePayload(enums.TriggerMessageStatus.notImplemented)
        return call_result.TriggerMessagePayload(enums.TriggerMessageStatus.accepted)
