import json
import os
from datetime import datetime
from aiofiles import open as a_open
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from charge_point.data.sessions import ChargingSession, Reservation
from charge_point.hardware.components import Relay, PowerMeter
from charge_point.scheduler import SchedulerManager


class ChargingConnector:
    """
    Class representing a Connector. A connector is an abstraction layer for a relay and a power meter.
    It tracks the current transaction, its power consumption, availability and operates with the relay.
    """

    def __init__(self, evse_id: int, connector_id: int, conn_type: str, relay_pin: int, relay_state,
                 power_meter_pin: int, power_meter_bus: int,
                 power_meter_voltage_divider_offset: float, power_meter_shunt_offset: float,
                 power_meter_min_power: float,
                 max_charging_time: int,
                 stop_transaction_function, send_meter_values_function):
        self.evse_id: int = evse_id
        self.connector_id: int = connector_id
        self._type: str = conn_type
        self._relay: Relay = Relay(pin=relay_pin, relay_state=relay_state)
        self._max_charging_time: int = max_charging_time
        self._stop_transaction_function = stop_transaction_function
        self._send_meter_values_function = send_meter_values_function
        self._power_meter: PowerMeter = None
        self._power_meter_min_power = power_meter_min_power
        if power_meter_pin > 0:
            self._power_meter = PowerMeter(power_meter_pin, power_meter_bus,
                                           power_meter_voltage_divider_offset,
                                           power_meter_shunt_offset)
        self._ChargingSession: ChargingSession = ChargingSession()
        self._Reservation: Reservation = None
        self._charging_scheduler: AsyncIOScheduler = SchedulerManager.getScheduler()
        self._connector_status = None

    def start_charging(self, id_tag: str, transaction_id: str = "", meter_sample_time: int = 60,
                       connector_timeout: int = 30) -> str:
        """
        Turn on the relay and start the charging process.
        :param connector_timeout: Set timeout for connector
        :param transaction_id: ID of the current transaction
        :param id_tag: RFID tag ID or user ID
        :param meter_sample_time:
        :return:
        """
        pass

    def stop_charging(self):
        """
        Stop the charging by switching the relay off, resetting the watchdogs and
        clearing the session information stored in volatile and non-volatile memory.
        :return:
        """
        self._ChargingSession.stop_charging_session()
        self._relay.off()
        self.__stop_watchdogs()
        self._Reservation = None
        self._charging_scheduler.add_job(ConnectorSettingsManager.clear_session, args=[self.evse_id, self.connector_id])

    def resume_charging(self, session_info, meter_sample_time: int = 60, connector_timeout: int = 30):
        """
        Restore and resume charging after reading non-volatile memory.
        :param session_info: Information retrieved from non-volatile memory
        :param meter_sample_time:
        :param connector_timeout:
        :return:
        """
        try:
            _max_time_left = ((datetime.now() - datetime.fromisoformat(
                session_info["started"])).seconds // 60) % 60
        except Exception as ex:
            _max_time_left: int = 60
            print(ex)
        if self.is_charging() and _max_time_left > 0:
            response = self._ChargingSession.resume_charging_session(tag_id=session_info["tag_id"],
                                                                     transaction_id=session_info["transaction_id"],
                                                                     meter_samples=session_info["consumption"])
            if response == ChargingSession.SessionResumeSuccess:
                self._relay.on()
                self.__set_watchdogs(meter_sample_time=meter_sample_time,
                                     connector_timeout=connector_timeout,
                                     max_charging_time=_max_time_left)
                self._charging_scheduler.add_job(ConnectorSettingsManager.update_session,
                                                 args=[self.evse_id, self.connector_id,
                                                       {
                                                           "is_active": True,
                                                           "transaction_id": self.get_current_transaction_id,
                                                           "tag_id": self.get_current_tag_id
                                                       }])
            return response
        return ChargingSession.SessionResumeFailure

    def __set_watchdogs(self, meter_sample_time: int, connector_timeout: int, max_charging_time=180):
        """
        Set a timer for charging. When the time limit is reached, stop charging.
        Will stop charging if it is interrupted before the timer ends.
        :param connector_timeout: Connector timeout in seconds
        :param meter_sample_time: Sample time in seconds
        :return:
        """
        pass

    def __stop_watchdogs(self):
        self._charging_scheduler.get_job(
            job_id=f"charging_watchdog_{self.evse_id}_{self.connector_id}").remove()
        try:
            self._charging_scheduler.get_job(
                job_id=f"meter_sampling_{self.evse_id}_{self.connector_id}").remove()
            self._charging_scheduler.get_job(
                job_id=f"update_meter_values_{self.evse_id}_{self.connector_id}").remove()
            self._charging_scheduler.get_job(
                job_id=f"connector_timeout_{self.evse_id}_{self.connector_id}").remove()
        except Exception as e:
            print(e)

    async def _update_meter_values(self):
        """
        Sample the meter values and monitor if the connector is still charging. If not, wait for the timeout.
        :return:
        """
        job_id = f"charging_watchdog_{self.evse_id}_{self.connector_id}"
        if self._charging_scheduler.get_job(job_id).next_run_time is None or not self.is_charging():
            return
        print(f"Notifying central system about the power consumption {self.get_max_sample}")
        await self._send_meter_values_function(self.connector_id, [{"timestamp": datetime.utcnow().isoformat(),
                                                                    "sampled_value": [
                                                                        {
                                                                            "value": f"{self.get_max_sample}"
                                                                        }]
                                                                    }])
        await ConnectorSettingsManager.update_session_attribute(evse_id=self.evse_id,
                                                                connector_id=self.connector_id,
                                                                key="consumption",
                                                                value=self.get_meter_samples)

    def _sample_meter(self):
        """
        Sample the power meter periodically each second and add energy to consumption.
        :return:
        """
        if isinstance(self._power_meter, PowerMeter):
            print(f"Power: {self._power_meter.get_current_power_draw()}")
            power_draw = self.get_power_draw
            self._ChargingSession.add_power_sample(power_draw)
            if power_draw > 0:
                self._ChargingSession.add_meter_sample(power_draw)

    def __check_if_connector_plugged(self):
        """
        Check if the connector is (re)connected and drawing power.
        :return:
        """
        pass

    def add_reservation(self, tag_id: str, expiry_date: str, reservation_id: str) -> str:
        """
        Add a new reservation of the connector.
        :param tag_id:
        :param expiry_date:
        :param reservation_id:
        :return: "OK" if successful and "Failed" if failed
        """
        if not self.is_available():
            return ChargingSession.ReservationFailed
        if not self.is_reserved(tag_id):
            self._Reservation = Reservation(tag_id=tag_id,
                                            to_date=expiry_date,
                                            reservation_id=reservation_id)
            connector_id: str = f"{self.evse_id}_{self.connector_id}"
            self._charging_scheduler.add_job(self.cancel_reservation,
                                             date=expiry_date,
                                             args=[reservation_id],
                                             id=f"cancel_reservation_{connector_id}")
            return ChargingSession.ReservationSuccess
        return ChargingSession.AlreadyReserved

    def cancel_reservation(self, reservation_id: int) -> str:
        """
        Cancel a reservation.
        :param reservation_id:
        :return:
        """
        if isinstance(self._Reservation, Reservation) and \
                self._Reservation.get_reservation_id == str(reservation_id):
            self._Reservation = None
            return ChargingSession.ReservationSuccess
        return ChargingSession.ReservationFailed

    def is_reserved(self, tag_id: str = "") -> bool:
        """
        Check if the connector has a reservation.
        :param tag_id: Tag ID
        :return:
        """
        if self.is_occupied():
            # If the reservation has the same tag ID to the one provided, it's permitted to charge
            if tag_id != "" and tag_id == self._Reservation.get_tag_id:
                return False
            return True
        return False

    def save_status_at_cleanup(self):
        """
        Before client shutdown, store the session info to non-volatile memory in a connectors.json file,
        so it can be restored when rebooted.
        :return:
        """
        self._charging_scheduler.add_job(ConnectorSettingsManager.update_connector_status,
                                         args=[self.evse_id, self.connector_id,
                                               str(self.get_status().value)],
                                         max_instances=1)
        self._charging_scheduler.add_job(ConnectorSettingsManager.update_session,
                                         args=[self.evse_id, self.connector_id,
                                               {
                                                   "is_active": self._ChargingSession.is_active,
                                                   "transaction_id": self.get_current_transaction_id,
                                                   "tag_id": self.get_current_tag_id
                                               }],
                                         max_instances=1)

    @property
    def get_current_transaction_id(self) -> str:
        return self._ChargingSession.get_transaction_id

    @property
    def get_current_tag_id(self) -> str:
        return self._ChargingSession.get_tag_id

    def is_available(self) -> bool:
        pass

    def is_charging(self) -> bool:
        pass

    def is_faulted(self) -> bool:
        pass

    def is_unavailable(self) -> bool:
        pass

    def is_occupied(self) -> bool:
        pass

    def get_status(self):
        return self._connector_status

    def set_status(self, status):
        self._connector_status = status

    @property
    def get_energy_consumption(self) -> float:
        if isinstance(self._power_meter, PowerMeter):
            return self._power_meter.get_energy_consumption()
        return 0.0

    @property
    def get_meter_samples(self) -> list:
        return self._ChargingSession.get_meter_samples

    @property
    def get_max_sample(self) -> float:
        return self._ChargingSession.get_max_sample_value

    @property
    def get_power_draw(self) -> float:
        if isinstance(self._power_meter, PowerMeter):
            return self._power_meter.get_current_power_draw()
        return 0.0

    @property
    def get_avg_power(self) -> float:
        return self._ChargingSession.get_avg_power

    @property
    def get_session_started(self) -> str:
        return self._ChargingSession.get_session_started

    def has_reservation(self, reservation_id: str) -> bool:
        if isinstance(self._Reservation, Reservation):
            return self._Reservation.get_reservation_id == str(reservation_id)
        return False

    @property
    def get_type(self) -> str:
        return self._type


class ConnectorSettingsManager:
    """
    A singleton class for I/O operations for the connectors.json file.
    Performs status change and session information write to the file.
    """
    path = os.path.dirname(os.path.realpath(__file__))
    file_name = "{path}/connectors.json".format(path=path)

    @staticmethod
    def get_evses() -> list:
        """
        Get connectors from connectors.json
        :return:
        """
        with open(ConnectorSettingsManager.file_name, "r") as connector_file:
            file = connector_file.read()
            evses = json.loads(file)["EVSEs"]
            connector_file.close()
            return evses

    @staticmethod
    def get_evse_with_id(evse_id: int) -> dict:
        """
        Get connectors from connectors.json
        :return:
        """
        return next((evse for evse in ConnectorSettingsManager.get_evses() if evse["id"] == evse_id), None)

    @staticmethod
    def get_connectors_from_evse(evse_id: int) -> list:
        """
        Get connectors from connectors.json
        :return:
        """
        evse: dict = ConnectorSettingsManager.get_evse_with_id(evse_id)
        if evse is not None:
            return evse["connectors"]
        else:
            return list()

    @staticmethod
    def get_all_connectors() -> list:
        """
        Get connectors from connectors.json
        :return:
        """
        evses: list = ConnectorSettingsManager.get_evses()
        connector_list: list = []
        for evse in evses:
            connector_list.extend(ConnectorSettingsManager.get_connectors_from_evse(evse.evse_id))
        return connector_list

    @staticmethod
    def get_connector_status(evse_id: int, connector_id: int) -> (str, dict):
        """
        Get connector status from connectors.json
        :return:
        """
        evse: dict = ConnectorSettingsManager.get_evse_with_id(evse_id)
        if evse is not None:
            for connector in evse["connectors"]:
                if connector["id"] == connector_id:
                    return connector["status"], connector["session"]
        return "NoConnectorFound", {}

    @staticmethod
    def get_session(evse_id: int, connector_id: int) -> dict:
        """
        Get session information from connectors.json
        :return:
        """
        evse: dict = ConnectorSettingsManager.get_evse_with_id(evse_id)
        for connector in evse["connectors"]:
            if connector["id"] == connector_id:
                return connector["session"]
        return {}

    @staticmethod
    async def update_connector_status(evse_id: int, connector_id: int, status: str):
        async with a_open(ConnectorSettingsManager.file_name, "r") as connector_settings:
            file = json.loads(await connector_settings.read())
            await connector_settings.close()
            for evse in file["EVSEs"]:
                if evse["id"] == evse_id:
                    for connector in evse["connectors"]:
                        if connector["id"] == connector_id:
                            connector["status"] = status
            await ConnectorSettingsManager.__write_to_file(file)

    @staticmethod
    async def __write_to_file(content):
        async with a_open(ConnectorSettingsManager.file_name, "w") as w_connector_settings:
            await w_connector_settings.write(json.dumps(content, indent=2))
            await w_connector_settings.close()

    @staticmethod
    async def update_session_attribute(evse_id: int, connector_id: int, key, value):
        """
        Update session object/info of a certain connector.
        :param evse_id:
        :param connector_id:
        :param key:
        :param value:
        :return:
        """
        async with a_open(ConnectorSettingsManager.file_name, "r") as connector_settings:
            file = json.loads(await connector_settings.read())
            await connector_settings.close()
            for evse in file["EVSEs"]:
                if evse["id"] == evse_id:
                    for index, connector in enumerate(evse["connectors"]):
                        if connector["id"] == connector_id and key in connector["session"].keys():
                            connector["session"][key] = value
            await ConnectorSettingsManager.__write_to_file(file)

    @staticmethod
    async def update_session(evse_id: int, connector_id: int, session_info: dict):
        """
        Update session info by parsing a dictionary with a structure and filled with desired values:
        "session": {
            "is_active": True,
            "transaction_id": "",
            "tag_id": "",
            "started": "",
            "consumption": []
        }
        :param evse_id:
        :param connector_id:
        :param session_info:
        :return:
        """
        for key in session_info.keys():
            await ConnectorSettingsManager.update_session_attribute(evse_id, connector_id, key, session_info[key])

    @staticmethod
    async def clear_session(evse_id: int, connector_id: int):
        """
        Clear session by inserting default values to the connectors.json file.
        :param evse_id:
        :param connector_id:
        :return:
        """
        async with a_open(ConnectorSettingsManager.file_name, "r") as connector_settings:
            file = json.loads(await connector_settings.read())
            await connector_settings.close()
            for evse in file["EVSEs"]:
                if evse["id"] == evse_id:
                    for connector in evse["connectors"]:
                        if connector["id"] == connector_id:
                            connector["session"] = {
                                "is_active": False,
                                "transaction_id": "",
                                "tag_id": "",
                                "started": "",
                                "consumption": []
                            }
            await ConnectorSettingsManager.__write_to_file(file)

    @staticmethod
    async def find_connector_with_transaction_id(transaction_id) -> ChargingConnector:
        async with a_open(ConnectorSettingsManager.file_name, "r") as connector_settings:
            file = json.loads(await connector_settings.read())
            await connector_settings.close()
            for evse in file["EVSEs"]:
                for connector in evse["connectors"]:
                    if connector["session"]["transaction_id"] == transaction_id:
                        return connector
            return None
