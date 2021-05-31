import asyncio
import ocpp.v201.enums as enums
import subprocess
import wget
from ocpp.v201.enums import ReasonType as ReasonType
from ocpp.v201 import call, call_result
from ocpp.v201 import ChargePoint as cp201
from ocpp.routing import on
from ocpp.v201.enums import ConnectorStatusType as status, Action as action
from semantic_version import Version
from charge_point.data.sessions import ChargingSession as s_responses
import logging
import time
import os, sys
import charge_point.responses as responses
from datetime import datetime, timedelta
from charge_point.connectors.ChargingConnector import ConnectorSettingsManager
from charge_point.data.update_manager import get_next_version, update_target_version, perform_update
from charge_point.hardware.components import LEDStrip
from charge_point.scheduler import SchedulerManager
from charge_point.v201.configuration import configuration_manager
from charge_point.v201.connector_v201 import ConnectorV201
from charge_point.data.auth.authorization_cache import AuthorizationCache as AuthCache
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from string_utils import is_full_string

logger = logging.getLogger('chargepi_logger')
_path = os.path.dirname(os.path.realpath(__file__))


class ChargePointV201(cp201):
    """
     ChargePoint specific class.
     The class implements OCPP 2.01 JSON/WS protocol requests and responses with all the background logic.
     It consists of a list of connectors, basic info and availability status.
    """
    __instance = None
    _path = os.path.dirname(os.path.realpath(__file__))

    @staticmethod
    def getInstance():
        if ChargePointV201.__instance is not None:
            return ChargePointV201.__instance
        else:
            raise Exception("Not initialized")

    def __init__(self, id, connection, charge_point_info, hardware_info: dict, response_timeout=30):
        if ChargePointV201.__instance is not None:
            return
        self.__charging_configuration = configuration_manager
        self.__charging_configuration.read_configuration()
        super().__init__(id, connection, response_timeout)
        ChargePointV201.__instance = self
        self.__scheduler: AsyncIOScheduler = SchedulerManager.getScheduler()
        # Add a heartbeat to the scheduler
        self.__scheduler.add_job(self.heartbeat, 'interval',
                                 seconds=self.__charging_configuration.ocppcomm_ctrlr.HeartbeatInterval)
        self.__is_available: bool = True
        self.charge_point_info: dict = charge_point_info
        self.hardware_info: dict = hardware_info
        self._ChargePointConnectors: list = list()
        self.__authorization_cache: AuthCache = AuthCache(self.__charging_configuration.auth_cache_ctrlr.is_enabled)
        self.__authorization_cache.set_max_cached_tags(self.__charging_configuration.local_auth_list_ctrlr)
        # Add all the connectors specified in the connectors.json
        for evse in ConnectorSettingsManager.get_evses():
            for connector in ConnectorSettingsManager.get_connectors_from_evse(evse["id"]):
                relay_settings: dict = connector["relay"]
                power_meter_settings: dict = connector["power_meter"]
                self.__add_connector(evse_id=evse["id"],
                                     connector_id=connector["id"],
                                     connector_type=connector["type"],
                                     relay_settings=relay_settings,
                                     power_meter_settings=power_meter_settings)
        # Sort by EVSE ID for performance
        self._ChargePointConnectors.sort(key=(lambda conn: conn.evse_id))
        # Display the status of each connector
        for connector in self.get_connectors:
            self._update_LED_status(connector)

    def __add_connector(self, evse_id: int, connector_id: int, connector_type: str, power_meter_settings: dict,
                        relay_settings: dict):
        """
        Add a new Connector to the list of connectors if it doesn't exist already.
        Connector ID must be greater than the previous' connector ID.
        :param connector_id: Consecutive connector ID
        :return:
        """
        if self.__find_connector_with_id(evse_id, connector_id) is None and connector_id > 0:
            list_length: int = len(self._ChargePointConnectors)
            if list_length != 0 and connector_id != self._ChargePointConnectors[list_length - 1].connector_id + 1:
                return
            connector: ConnectorV201 = ConnectorV201(evse_id=evse_id,
                                                     connector_id=connector_id,
                                                     conn_type=connector_type,
                                                     relay_pin=int(relay_settings["relay_pin"]),
                                                     relay_state=int(relay_settings["default_state"]),
                                                     power_meter_pin=int(power_meter_settings["power_meter_pin"]),
                                                     power_meter_bus=int(power_meter_settings["spi_bus"]),
                                                     power_meter_voltage_divider_offset=int(
                                                         power_meter_settings["voltage_divider_offset"]),
                                                     power_meter_shunt_offset=int(power_meter_settings["shunt_offset"]),
                                                     max_charging_time=self.charge_point_info["max_charging_time"],
                                                     stop_transaction_function=self.__stop_charging_connector_with_id,
                                                     send_meter_values_function=self.send_meter_values)
            self._ChargePointConnectors.append(connector)

    @property
    def get_connectors(self) -> list:
        return self._ChargePointConnectors

    @property
    def is_available(self) -> bool:
        return self.__is_available

    def __get_connector_index(self, connector: ConnectorV201):
        """
        Get index of a connector in the connector list.
        :param connector: A connector
        :return: Index of the connector
        """
        try:
            return self.get_connectors.index(connector)
        except ValueError as ex:
            return -1

    def __find_charging_connectors(self) -> list:
        """
        Find all connectors which are currently charging.
        :return: List of connectors.
        """
        return [(connector for connector in self.get_connectors if connector.is_charging())]

    def __find_available_connector(self) -> ConnectorV201:
        """
        Find the first available connector.
        :return: A connector
        """
        return next((connector for connector in self.get_connectors if
                     self.__is_connector_permitted_to_charge(connector)), None)

    def __find_available_connector_type(self, connector_type: enums.ConnectorType) -> ConnectorV201:
        """
        Find the first available connector.
        :return: A connector
        """
        return next((connector for connector in self.get_connectors if
                     self.__is_connector_permitted_to_charge(connector)
                     and connector.get_type == connector_type.value), None)

    def __find_connector_from_evse_connector_type(self, evse_id: int,
                                                  connector_type: enums.ConnectorType) -> ConnectorV201:
        """
        Find the first connector from EVSE with a certain type
        :return: A connector
        """
        return next((connector for connector in self.__get_connectors_from_evse(evse_id) if
                     self.__is_connector_permitted_to_charge(connector)
                     and connector.get_type == connector_type.value), None)

    def __find_connector_with_id(self, evse_id: int, connector_id: int) -> ConnectorV201:
        """
        Find a specific connector.
        :param connector_id: A connector ID
        :return: A connector
        """
        return next((connector for connector in self.get_connectors
                     if connector.evse_id == evse_id and connector.connector_id == connector_id), None)

    def __get_connectors_from_evse(self, evse_id: int) -> list:
        """
        Get connectors from an EVSE.
        :return: A connector
        """
        return [connector for connector in self.get_connectors if connector.evse_id == evse_id]

    def __is_connector_permitted_to_charge(self, connector: ConnectorV201) -> bool:
        """
        Check if no others connectors in EVSE are charging
        :return: A connector
        """
        for evse_connector in self.__get_connectors_from_evse(connector.evse_id):
            if not connector.is_available() and evse_connector.is_charging() \
                    and evse_connector.connector_id != connector.connector_id:
                return False
        return True

    def __find_connector_with_transaction_id(self, transaction_id: str) -> ConnectorV201:
        """
        Find a connector that has a transaction ID equal to the one specified.
        :param transaction_id: A transaction ID
        :return: A connector
        """
        return next((connector for connector in self.get_connectors
                     if connector.get_current_transaction_id == transaction_id), None)

    def __find_connector_with_tag_id(self, id_tag: str) -> ConnectorV201:
        """
        Find a connector that has a RFID ID equal to the one specified.
        :param id_tag: A RFID ID
        :return: A connector
        """
        return next((connector for connector in self.get_connectors
                     if connector.get_tag_id() == id_tag), None)

    async def __is_tag_authorized(self, id_tag: str, is_remote_request: bool) -> bool:
        """
        Check if the tag is authorized in Authentication cache and/or authorize with the central system.
        :param id_tag: Tag ID
        :return: True or false
        """
        print("Authorizing tag")
        if await self.__authorization_cache.is_tag_authorized(id_tag):
            # If the tag is in auth cache and valid, don't wait for authorization
            self.__scheduler.add_job(self.__authorize_tag, args=[id_tag])
            return True
        elif self.__charging_configuration.auth_ctrlr.OfflineTxForUnknownIdEnabled:
            return True
        elif is_remote_request and not self.__charging_configuration.auth_ctrlr.AuthorizeRemoteStart:
            return True
        else:
            id_tag_info: dict = await self.__authorize_tag(id_tag)
            print(id_tag_info)
            return id_tag_info["status"] == enums.AuthorizationStatusType.accepted

    async def __authorize_tag(self, id_tag: str):
        """
        Authorize the RFID card with the server. If Authorization Cache is enabled, (re)write the tag info in the cache.
        :param id_tag: Tag ID
        :return: Response of the authentication request
        """
        request = call.AuthorizePayload(id_token={"id_tag": id_tag})
        auth_response = await self.call(request)
        tag_info: dict = auth_response.id_tag_info
        if self.__charging_configuration.auth_cache_ctrlr.is_enabled:
            self.__scheduler.add_job(self.__authorization_cache.update_tag_info,
                                     args=[id_tag, tag_info])
        if tag_info["status"] == enums.AuthorizationStatusType.blocked:
            connector: ConnectorV201 = self.__find_connector_with_tag_id(id_tag)
            if isinstance(connector, ConnectorV201):
                self.__scheduler.add_job(self.__stop_charging_connector_with_id,
                                         args=[connector.connector_id, id_tag, ReasonType.de_authorized])
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
        :return:
        """
        if self.hardware_info["LED_indicator"]["type"] == "WS281x":
            command = f"sudo python3 {_path}/../hardware/leds/LEDStrip.py {colors}"
            print(command)
            subprocess.Popen(command, shell=True)
        elif self.hardware_info["LED_indicator"]["type"] == "simple":
            pass

    async def handle_charging_request(self, id_tag: str) -> (str, str):
        """
        Handle a charging request initiated by the RFID reader.
        It will stop charging if it finds a connector with the same RFID ID, else it will start charging.
        :param id_tag: Tag ID
        :return: Connector ID and response
        """
        logger.info("Handling request for tag {tag_id}".format(tag_id=id_tag))
        connector = self.__find_connector_with_tag_id(id_tag)
        if isinstance(connector, ConnectorV201):
            connector_id: int = connector.connector_id
            evse_id: int = connector.evse_id
            response = evse_id, await self.__stop_charging_connector_with_id(evse_id=evse_id,
                                                                             connector_id=connector_id,
                                                                             reason=ReasonType.local)
        else:
            response = await self.__start_charging(id_tag=id_tag)
        return response

    async def __start_charging(self, id_tag: str) -> (int, str):
        """
        Start the charging process on the first available connector.
        :param id_tag: RFID tag
        :return: Connector ID and response
        """
        connector = self.__find_available_connector()
        if isinstance(connector, ConnectorV201):
            evse_id: int = connector.evse_id
            connector_id: int = connector.connector_id
            response = await self.__start_charging_connector_with_id(id_tag=id_tag,
                                                                     evse_id=evse_id,
                                                                     connector_id=connector_id)
            print(response)
            if response == responses.StartChargingSuccess:
                pass
                # await self._show_charging_connector(connector)
            return evse_id, response
        return -1, responses.NoAvailableConnectors

    async def __start_charging_connector_with_id(self, id_tag: str, evse_id: int, connector_id: int,
                                                 is_remote_request: bool = False, retry_attempt: int = 0) -> str:
        """
        Start the charging process on a specific connector. Charging starts with checking the card
        authorization in the cache and/or server, then sending a transaction request.
         If all goes well, enable the hardware to charge.
        :param id_tag: RFID ID
        :param connector_id: A connector ID
        :return: Response
        """
        connector = self.__find_connector_with_id(evse_id, connector_id)
        if isinstance(connector, ConnectorV201) \
                and self.is_available \
                and self.__is_connector_permitted_to_charge(connector) \
                and self.__find_connector_with_tag_id(id_tag) is None:
            # Authorize the card before charging
            if not await self.__is_tag_authorized(id_tag=id_tag, is_remote_request=is_remote_request):
                return responses.UnauthorizedCard
            await self.change_connector_status(evse_id=evse_id,
                                               connector_id=connector_id,
                                               connector_status=status.occupied)
            # Send a transaction request to the server
            request = call.StartTransactionPayload(id_token={"id_tag": id_tag},
                                                   remote_start_id=1,
                                                   evse_id=connector.evse_id)
            server_response = await self.call(request)
            tag_info = server_response.id_tag_info
            # If the server accepts, start charging
            if tag_info["status"] == enums.RequestStartStopStatusType.accepted or tag_info["status"] == "ConcurrentTx":
                connector_response = connector.start_charging(id_tag=id_tag,
                                                              meter_sample_time=self.__charging_configuration.sampled_data_ctrlr.TxUpdatedInterval,
                                                              connector_timeout=self.__charging_configuration.tx_ctrlr.EVConnectionTimeOut)
                print(connector_response)
                if connector_response == s_responses.SessionStartSuccess:
                    print("Started charging at connector {conn_id}".format(conn_id=str(connector_id)))
                    logger.info("Started charging at connector {conn_id}".format(conn_id=str(connector_id)))
                    await self.change_connector_status(evse_id=evse_id,
                                                       connector_id=connector_id,
                                                       connector_status=status.charging)
                    return responses.StartChargingSuccess
                else:
                    print("Session rejected at connector {conn_id}".format(conn_id=str(connector_id)))
                    logger.info("Session rejected at connector {conn_id}".format(conn_id=str(connector_id)))
                    await self.__stop_charging_connector_with_id(evse_id=evse_id,
                                                                 connector_id=connector_id,
                                                                 reason=ReasonType.local)
                    return responses.StartChargingFail
            else:
                print("Transaction rejected at connector {conn_id}".format(conn_id=str(connector_id)))
                logger.info("Transaction rejected at connector {conn_id}".format(conn_id=str(connector_id)))
                return responses.StartChargingFail
        else:
            logger.info("Connector {conn_id} unavailable or already charging".format(conn_id=str(connector_id)))
            return responses.ConnectorUnavailable

    async def __stop_charging_connector_with_id(self, evse_id: int, connector_id: int, reason: ReasonType):
        """
        Stop the charging process on a connector.
        :param connector_id: A connector ID
        :return: Returns "OK" or "Failed"
        """
        try:
            self.__scheduler.get_job(job_id="StopRemoteTx").remove()
        except Exception as ex:
            print(ex)
        connector = self.__find_connector_with_id(evse_id, connector_id)
        if isinstance(connector, ConnectorV201) and connector.is_charging():
            # Edge case
            if reason == reason.ev_disconnected \
                    and not self.__charging_configuration.tx_ctrlr.StopTxOnEVSideDisconnect:
                print("Connector {conn_id} disconnected from EV".format(conn_id=str(connector_id)))
                logger.info("Connector {conn_id} disconnected from EV".format(conn_id=str(connector_id)))
                await self.change_connector_status(evse_id=evse_id,
                                                   connector_id=connector_id,
                                                   connector_status=status.occupied)
                connector.stop_charging()
                await self.change_connector_status(evse_id=evse_id,
                                                   connector_id=connector_id,
                                                   connector_status=status.available)
                return responses.StopChargingSuccess
            request = call.TransactionEventPayload(event_type=enums.TransactionEventType.ended,
                                                   timestamp=str(datetime.now().isoformat()),
                                                   trigger_reason=reason,
                                                   transaction_info={
                                                       "transactionId": connector.get_current_transaction_id},
                                                   seq_no=123)
            await self.call(request)
            logger.info("Stopping transaction " + str(connector.get_current_transaction_id)
                        + "at " + str(datetime.today()))
            connector.stop_charging()
            self._update_LED_status(self._get_LED_colors())
            return responses.StopChargingSuccess
        logger.info("Rejected stopping a transaction")
        return responses.StopChargingFail

    async def __stop_charging_connector_with_transaction(self, transaction_id: str):
        """
        Stop the charging process on a connector with a certain transaction ID.
        :param transaction_id: A transaction ID
        :return:
        """
        connector = self.__find_connector_with_transaction_id(transaction_id)
        if isinstance(connector, ConnectorV201):
            return await self.__stop_charging_connector_with_id(connector.evse_id,
                                                                connector.connector_id,
                                                                ReasonType.remote)
        else:
            return responses.NoConnectorWithTransaction

    async def send_boot_notification(self):
        """
        Notify and connect to the central system at boot.
        :return:
        """
        request = call.BootNotificationPayload(charging_station={
            "model": self.charge_point_info["model"],
            "vendor_name": self.charge_point_info["vendor"]},
            reason=enums.BootReasonType.power_up)
        response = await self.call(request)
        if response.status == enums.ChangeAvailabilityStatusType.accepted:
            logger.info("Connected to central system.")
            await self.restore_state()

    async def restore_state(self):
        # Restore state from connectors.json file
        for connector in self._ChargePointConnectors:
            connector_id: int = connector.connector_id
            evse_id: int = connector.evse_id
            previous_status, session_info = ConnectorSettingsManager.get_connector_status(evse_id, connector_id)
            # Notify the central system of the previous state
            await self.change_connector_status(evse_id=evse_id,
                                               connector_id=connector_id,
                                               connector_status=status(previous_status))
            if previous_status == status.charging:
                # Try to resume charging & notify about success
                response = connector.resume_charging(session_info=session_info,
                                                     meter_sample_time=self.__charging_configuration.sampled_data_ctrlr.TxEndedMeasurands,
                                                     connector_timeout=self.__charging_configuration.tx_ctrlr.EVConnectionTimeOut)
                if response == s_responses.SessionResumeSuccess:
                    await self.change_connector_status(evse_id=evse_id,
                                                       connector_id=connector_id,
                                                       connector_status=status.charging)
                else:
                    await self.change_connector_status(evse_id=evse_id,
                                                       connector_id=connector_id,
                                                       connector_status=status.available)
                    self.__scheduler.add_job(self.__stop_charging_connector_with_transaction,
                                             args=[session_info["transaction_id"]])
            elif previous_status == status.preparing:
                await self.change_connector_status(evse_id=evse_id,
                                                   connector_id=connector_id,
                                                   connector_status=status.available)
                self.__scheduler.add_job(self.__start_charging_connector_with_id,
                                         args=[session_info["tag_id"], evse_id, connector.connector_id, False])
            else:
                await self.change_connector_status(evse_id=evse_id,
                                                   connector_id=connector_id,
                                                   connector_status=status(previous_status))

    async def send_meter_values(self, evse_id: int, connector_id: int, event_trigger: enums.TriggerReasonType):
        """
        Send updates of the power meter on a specific connector.
        :param evse_id:
        :param event_trigger:
        :param connector_id: A Connector ID
        :return:
        """
        connector = self.__find_connector_with_id(evse_id, connector_id)
        if isinstance(connector, ConnectorV201) and connector.is_charging():
            request = call.TransactionEventPayload(
                seq_no=123,
                event_type=enums.TransactionEventType.updated,
                trigger_reason=event_trigger,
                evse={"id": evse_id, "connectorId": connector_id},
                meter_value=[{"timestamp": datetime.now().isoformat(),
                              "sampledValue": {"value": connector.get_energy_consumption,
                                               "context": enums.ReadingContextType.sample_periodic}
                              }],
                transaction_info={"transactionId": connector.get_current_transaction_id},
                timestamp=datetime.now().isoformat())
            logger.info("Sent meter value")
            print("Sent meter value: {power_value}".format(power_value=connector.get_energy_consumption))
            await self.call(request)

    async def change_connector_status(self, evse_id: int, connector_id: int,
                                      connector_status: enums.ConnectorStatusType):
        """
        Notify the system with a specific connector's state.
        :param evse_id:
        :param connector_id: A connector ID
        :param connector_status: Status of the connector
        :return:
        """
        connector = self.__find_connector_with_id(evse_id, connector_id)
        if isinstance(connector, ConnectorV201):
            connector.set_status(connector_status)
            print("Changing status to {conn_status}".format(conn_status=str(connector_status)))
            await self.notify_current_connector_status(evse_id, connector_id)
            if connector.is_charging() or connector.is_available() or connector.is_faulted() or connector.is_unavailable() \
                    or connector.is_occupied():
                self._update_LED_status(self._get_LED_colors())

    async def notify_current_connector_status(self, evse_id: int, connector_id: int):
        connector = self.__find_connector_with_id(evse_id, connector_id)
        if isinstance(connector, ConnectorV201):
            request = call.StatusNotificationPayload(evse_id=evse_id,
                                                     connector_id=connector_id,
                                                     timestamp=datetime.now().isoformat(),
                                                     connector_status=connector.get_status())
            await self.call(request)

    def cleanup(self):
        """
        Stops the schedulers and ongoing transactions before exiting.
        :return:
        """
        logger.info("Cleaning up..")
        print("Cleaning up..")
        try:
            # Try to stop all ongoing transactions
            for connector in self.__find_charging_connectors():
                evse_id: int = connector.evse_id
                job_id: str = "cleanup_connector_{evse_id}_{conn_id}".format(conn_id=str(connector.connector_id),
                                                                             evse_id=str(evse_id))
                self.__scheduler.add_job(self.__stop_charging_connector_with_id,
                                         args=[evse_id, connector.connector_id, ReasonType.local],
                                         id=job_id)
                print(job_id)
            # Save status of each connector
            for connector in self._ChargePointConnectors:
                connector.save_status_at_cleanup()
            # Wait for all jobs to be complete
            while len(self.__scheduler.get_jobs()) != 0:
                time.sleep(.3)
                print("Waiting for schedulers to clear..")
            print("Cleaned up")
        except Exception as ex:
            msg: str = "Exception at ChargePoint cleanup: {msg}".format(msg=str(ex))
            print(msg)
            logger.debug(msg, exc_info=ex)
        finally:
            leds = ""
            for _ in range(len(self.get_connectors)):
                leds += " 0"
            subprocess.Popen(f"sudo python3 {_path}/../hardware/leds/LEDStrip.py{leds}", shell=True)
            self.__scheduler.shutdown(wait=False)

    async def heartbeat(self):
        """
        Sends a heartbeat to the central system.
        :return:
        """
        print("Sent heartbeat")
        logger.info("Sent heartbeat")
        await self.call(call.HeartbeatPayload())

    @on(action.RequestStartTransaction)
    async def remote_start_transaction(self, evse_id: int, connector_id: int, id_tag: str):
        """
        Handles server's request to start a charging session.
        :param evse_id: 
        :param connector_id: A connector ID
        :param id_tag: RFID or user ID
        :return:
        """
        job_id: str = "StartRemoteTx"
        if connector_id == 0:
            self.__scheduler.add_job(self.__start_charging, 'date',
                                     run_date=(datetime.now() + timedelta(seconds=3)),
                                     args=[id_tag], id=job_id)
            return call_result.RequestStartTransactionPayload(enums.RequestStartStopStatusType.accepted)
        else:
            connector = self.__find_connector_with_id(evse_id, connector_id)
            if isinstance(connector, ConnectorV201) and self.__is_connector_permitted_to_charge(connector):
                self.__scheduler.add_job(self.__start_charging_connector_with_id, 'date',
                                         run_date=(datetime.now() + timedelta(seconds=3)),
                                         args=[id_tag, evse_id, connector_id, True],
                                         id=job_id)
                return call_result.RequestStartTransactionPayload(enums.RequestStartStopStatusType.accepted)
        return call_result.RequestStartTransactionPayload(enums.RequestStartStopStatusType.rejected)

    @on(action.RequestStopTransaction)
    async def remote_stop_transaction(self, transaction_id: str):
        """
        Handles server's request to stop a charging session.
        :param transaction_id: Transaction ID
        :return: Accepted or Rejected constants
        """
        connector = self.__find_connector_with_transaction_id(transaction_id=transaction_id)
        if isinstance(connector, ConnectorV201):
            self.__scheduler.add_job(self.__stop_charging_connector_with_transaction,
                                     'date',
                                     run_date=(datetime.now() + timedelta(seconds=3)),
                                     args=[transaction_id])
            return call_result.RequestStopTransactionPayload(enums.RequestStartStopStatusType.accepted)
        return call_result.RequestStopTransactionPayload(enums.RequestStartStopStatusType.rejected)

    @on(action.ChangeAvailability)
    async def change_availability(self, operational_status: str, evse: dict):
        """
        Set availability of a connector.
        :param operational_status:
        :param evse:
        :return:
        """
        connector = self.__find_connector_with_id(evse["connector_id"], evse["evse_id"])
        if isinstance(connector, ConnectorV201) \
                and not connector.is_charging():
            if operational_status == enums.ChangeAvailabilityStatusType.inoperative:
                connector.set_status(status=status.unavailable)
            else:
                connector.set_status(status=status.availabled)
            return call_result.ChangeAvailabilityPayload(enums.ChangeAvailabilityStatusType.accepted)
        else:
            return call_result.ChangeAvailabilityPayload(enums.ChangeAvailabilityStatusType.rejected)

    @on(action.UnlockConnector)
    async def unlock_connector(self, evse_id: int, connector_id: int):
        """
        Unlock the specified connector.
        :param evse_id:
        :param connector_id: A connector ID
        :return: Unlocked or Unsupported
        """
        response = await self.__stop_charging_connector_with_id(evse_id, connector_id, reason=ReasonType.remote)
        if response == "OK":
            return call_result.UnlockConnectorPayload(enums.UnlockStatusType.unlocked)
        else:
            return call_result.UnlockConnectorPayload(enums.UnlockStatusType.notSupported)

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
            return call_result.UpdateFirmwarePayload(enums.UpdateFirmwareStatusType.rejected)
        return call_result.UpdateFirmwarePayload(enums.UpdateFirmwareStatusType.accepted)

    @on(action.ReserveNow)
    async def reserve_connector(self, id: int, expiry_date_time: str, id_token: str,
                                connector_type: str = "", evse_id: int = -1, group_id_token: dict = None):
        """
        Reserve a connector
        :param id:
        :param expiry_date_time:
        :param id_token:
        :param connector_type:
        :param evse_id:
        :param group_id_token:
        :return:
        """
        connector_type = enums.ConnectorType(connector_type)
        if connector_type.value != "" and evse_id != -1:
            connector = self.__find_connector_from_evse_connector_type(evse_id, connector_type)
        elif evse_id != -1 and connector_type.value == "":
            connector = self.__get_connectors_from_evse(connector_type)[0]
        elif connector_type.value != "" and evse_id == -1:
            connector = self.__find_available_connector_type(connector_type)
        else:
            connector = self.__find_available_connector()
        if isinstance(connector, ConnectorV201):
            connector.add_reservation(expiry_date=expiry_date_time,
                                      reservation_id=str(id),
                                      tag_id=id_token)
            return call_result.ReserveNowPayload(enums.ReserveNowStatusType.accepted)
        else:
            return call_result.ReserveNowPayload(enums.ReserveNowStatusType.rejected)

    @on(action.GetVariables)
    async def get_variables(self, get_variable_data: list):
        response_list: list = []
        for variable in get_variable_data:
            component_name: str = variable["component"]["name"]
            variable_name: str = variable["variable"]["name"]
            response = {"attribute_status": enums.GetVariableStatusType.unknown_variable,
                        "component": {"name": component_name},
                        "attribute_value": ""}
            if component_name == "AuthCtrlr":
                configuration_variable = configuration_manager.auth_ctrlr.get_attribute(variable_name)
                response["attribute_status"] = enums.GetVariableStatusType.accepted
                response["attribute_value"] = configuration_variable
            elif component_name == "DeviceDataCtrlr":
                configuration_variable = configuration_manager.device_data_ctrlr.get_attribute(variable_name)
                response["attribute_status"] = enums.GetVariableStatusType.accepted
                response["attribute_value"] = configuration_variable
            elif component_name == "DisplayMessageCtrlr":
                configuration_variable = configuration_manager.display_message_ctrlr.get_attribute(variable_name)
                response["attribute_status"] = enums.GetVariableStatusType.accepted
                response["attribute_value"] = configuration_variable
            elif component_name == "CustomizationCtrlr":
                configuration_variable = configuration_manager.customization_ctrlr.get_attribute(variable_name)
                response["attribute_status"] = enums.GetVariableStatusType.accepted
                response["attribute_value"] = configuration_variable
            elif component_name == "SecurityCtrlr":
                configuration_variable = configuration_manager.security_ctrlr.get_attribute(variable_name)
                response["attribute_status"] = enums.GetVariableStatusType.accepted
                response["attribute_value"] = configuration_variable
            elif component_name == "SampledDataCtrlr":
                configuration_variable = configuration_manager.sampled_data_ctrlr.get_attribute(variable_name)
                response["attribute_status"] = enums.GetVariableStatusType.accepted
                response["attribute_value"] = configuration_variable
            elif component_name == "SmartChargingCtrlr":
                configuration_variable = configuration_manager.smart_charging_ctrlr.get_attribute(variable_name)
                response["attribute_status"] = enums.GetVariableStatusType.accepted
                response["attribute_value"] = configuration_variable
            elif component_name == "OCPPCommCtrlr":
                configuration_variable = configuration_manager.ocppcomm_ctrlr.get_attribute(variable_name)
                response["attribute_status"] = enums.GetVariableStatusType.accepted
                response["attribute_value"] = configuration_variable
            elif component_name == "TxCtrlr":
                configuration_variable = configuration_manager.tx_ctrlr.get_attribute(variable_name)
                response["attribute_status"] = enums.GetVariableStatusType.accepted
                response["attribute_value"] = configuration_variable
            elif component_name == "MonitoringCtrlr":
                configuration_variable = configuration_manager.monitoring_ctrlr.get_attribute(variable_name)
                response["attribute_status"] = enums.GetVariableStatusType.accepted
                response["attribute_value"] = configuration_variable
            elif component_name == "LocalAuthListCtrlr":
                configuration_variable = configuration_manager.local_auth_list_ctrlr.get_attribute(variable_name)
                response["attribute_status"] = enums.GetVariableStatusType.accepted
                response["attribute_value"] = configuration_variable
            elif component_name == "AuthCacheCtrlr":
                configuration_variable = configuration_manager.auth_cache_ctrlr.get_attribute(variable_name)
                response["attribute_status"] = enums.GetVariableStatusType.accepted
                response["attribute_value"] = configuration_variable
            elif component_name == "AlignedDataCtrlr":
                configuration_variable = configuration_manager.aligned_data_ctrlr.get_attribute(variable_name)
                response["attribute_status"] = enums.GetVariableStatusType.accepted
                response["attribute_value"] = configuration_variable
            elif component_name == "ClockCtrlr":
                configuration_variable = configuration_manager.clock_ctrlr.get_attribute(variable_name)
                response["attribute_status"] = enums.GetVariableStatusType.accepted
                response["attribute_value"] = configuration_variable
            elif component_name == "ReservationCtrlr":
                configuration_variable = configuration_manager.reservation_ctrlr.get_attribute(variable_name)
                response["attribute_status"] = enums.GetVariableStatusType.accepted
                response["attribute_value"] = configuration_variable
            else:
                response["attribute_status"] = enums.GetVariableStatusType.unknown_component
            response_list.append(response)
        return call_result.GetVariablesPayload(response_list)

    @on(action.SetVariables)
    async def set_variables(self, set_variable_data: list):
        response_list: list = []
        for variable in set_variable_data:
            component_name: str = variable["component"]["name"]
            variable_name: str = variable["variable"]["name"]
            attribute_value = variable["attribute_value"]
            response = {"attribute_status": enums.GetVariableStatusType.unknown_variable,
                        "component": {"name": component_name},
                        "variable": {"name": variable_name}}
            update_status = "Failed"
            if component_name == "AuthCtrlr":
                update_status = configuration_manager.auth_ctrlr.update_configuration(variable_name, attribute_value)
            elif component_name == "DeviceDataCtrlr":
                update_status = configuration_manager.device_data_ctrlr.update_configuration(variable_name,
                                                                                             attribute_value)
            elif component_name == "DisplayMessageCtrlr":
                update_status = configuration_manager.display_message_ctrlr.update_configuration(variable_name,
                                                                                                 attribute_value)
            elif component_name == "CustomizationCtrlr":
                update_status = configuration_manager.customization_ctrlr.update_configuration(variable_name,
                                                                                               attribute_value)
            elif component_name == "SecurityCtrlr":
                update_status = configuration_manager.security_ctrlr.update_configuration(variable_name,
                                                                                          attribute_value)
            elif component_name == "SampledDataCtrlr":
                update_status = configuration_manager.sampled_data_ctrlr.update_configuration(variable_name,
                                                                                              attribute_value)
            elif component_name == "SmartChargingCtrlr":
                update_status = configuration_manager.smart_charging_ctrlr.update_configuration(variable_name,
                                                                                                attribute_value)
            elif component_name == "OCPPCommCtrlr":
                update_status = configuration_manager.ocppcomm_ctrlr.update_configuration(variable_name,
                                                                                          attribute_value)
            elif component_name == "TxCtrlr":
                update_status = configuration_manager.tx_ctrlr.update_configuration(variable_name, attribute_value)
            elif component_name == "MonitoringCtrlr":
                update_status = configuration_manager.monitoring_ctrlr.update_configuration(variable_name,
                                                                                            attribute_value)
            elif component_name == "LocalAuthListCtrlr":
                update_status = configuration_manager.local_auth_list_ctrlr.update_configuration(variable_name,
                                                                                                 attribute_value)
            elif component_name == "AuthCacheCtrlr":
                update_status = configuration_manager.auth_cache_ctrlr.update_configuration(variable_name,
                                                                                            attribute_value)
            elif component_name == "AlignedDataCtrlr":
                update_status = configuration_manager.aligned_data_ctrlr.update_configuration(variable_name,
                                                                                              attribute_value)
            elif component_name == "ClockCtrlr":
                update_status = configuration_manager.clock_ctrlr.update_configuration(variable_name, attribute_value)
            elif component_name == "ReservationCtrlr":
                update_status = configuration_manager.reservation_ctrlr.update_configuration(variable_name,
                                                                                             attribute_value)
            else:
                response["attribute_status"] = enums.GetVariableStatusType.unknown_component
            if update_status == "Success":
                response["attribute_status"] = enums.GetVariableStatusType.accepted
            response_list.append(response)
        return call_result.SetVariablesPayload(response_list)

    @on(action.CancelReservation)
    async def cancel_reservation(self, reservation_id: int):
        """
        Cancel a reservation on a connector with a reservation ID.
        :param reservation_id:
        :return:
        """
        for connector in self.get_connectors:
            if connector.has_reservation_with_id(str(reservation_id)):
                connector.cancel_reservation(reservation_id)
                return call_result.CancelReservationPayload(enums.CancelReservationStatusType.accepted)
        return call_result.CancelReservationPayload(enums.CancelReservationStatusType.rejected)

    @on(action.ClearCache)
    async def clear_cache(self):
        if await self.__authorization_cache.clear_cache() == "Success":
            return call_result.ClearCachePayload(enums.ClearCacheStatusType.accepted)
        else:
            return call_result.ClearCachePayload(enums.ClearCacheStatusType.rejected)

    @on(action.SendLocalList)
    async def get_list(self, list_version: int, update_type: enums.UpdateType, local_authorization_list: list):
        if self.__authorization_cache.get_version != list_version:
            return call_result.SendLocalListPayload(enums.UpdateType.versionMismatch)
        elif update_type == enums.UpdateType.full:
            await self.__authorization_cache.update_cached_tags(local_authorization_list)
            return call_result.SendLocalListPayload(enums.UpdateType.accepted)
        elif update_type == enums.UpdateType.differential:
            return call_result.SendLocalListPayload(enums.UpdateType.accepted)
        else:
            return call_result.SendLocalListPayload(enums.UpdateType.notSupported)

    @on(action.DataTransfer)
    async def transfer_data(self, vendor_id: str, message_id: str, data: str):
        return call_result.DataTransferPayload(enums.DataTransferStatusType.rejected)

    def __soft_reset(self):
        self.cleanup()
        os.execv(sys.executable, ['sudo python3'] + sys.argv)

    def __hard_reset(self):
        self.cleanup()
        os.system("sudo reboot")

    @on(action.Reset)
    async def reset_request(self, type: str, evse_id: int):
        """
        Respond to reset request. When requested to hard reset, reboot the system, else just reset the program.
        :param evse_id:
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
        return call_result.ResetPayload(status=enums.ResetStatusType.scheduled)

    @on(action.TriggerMessage)
    async def trigger_message(self, requested_message: enums.MessageTriggerType, evse: dict):
        """
        :param requested_message:
        :param evse:
        :return:
        """
        if requested_message == enums.MessageTriggerType.status_notification:
            if evse is not None:
                self.__scheduler.add_job(self.notify_current_connector_status, 'date',
                                         run_date=(datetime.now() + timedelta(seconds=2)),
                                         args=[evse["id"], evse["connectorId"]])
                return call_result.TriggerMessagePayload(status=enums.TriggerMessageStatusType.accepted)
            return call_result.TriggerMessagePayload(status=enums.TriggerMessageStatusType.rejected)
        elif requested_message == enums.MessageTriggerType.heartbeat:
            self.__scheduler.add_job(self.heartbeat)
            return call_result.TriggerMessagePayload(status=enums.TriggerMessageStatusType.accepted)
        elif requested_message == enums.MessageTriggerType.firmware_status_notification:
            return call_result.TriggerMessagePayload(status=enums.TriggerMessageStatusType.not_implemented)
            pass
        return call_result.TriggerMessagePayload(status=enums.TriggerMessageStatusType.not_implemented)
