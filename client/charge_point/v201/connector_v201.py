from datetime import datetime
from charge_point.hardware.components import PowerMeter
from charge_point.data.sessions import ChargingSession as SessionResponses
from ocpp.v201.enums import ConnectorStatusType, ReasonType, TriggerReasonType
import logging
import uuid
from charge_point.connectors.ChargingConnector import ChargingConnector, ConnectorSettingsManager
import charge_point.v201.configuration.configuration_manager as configuration_manager

logger = logging.getLogger('chargepi_logger')


class ConnectorV201(ChargingConnector):
    """
    Class representing a Connector. A connector is an abstraction layer for a relay and a power meter.
    It tracks the current transaction, its power consumption, availability and operates with the relay.
    """

    _sampling_info: configuration_manager.SampledDataCtrlr = configuration_manager.sampled_data_ctrlr

    def __init__(self, evse_id: int, connector_id: int, conn_type: str, relay_pin: int, relay_state,
                 power_meter_pin: int, power_meter_bus: int, power_meter_shunt_offset: float,
                 power_meter_voltage_divider_offset: float, power_meter_min_power: float,
                 max_charging_time: int,
                 stop_transaction_function, send_meter_values_function):
        super().__init__(evse_id, connector_id, conn_type, relay_pin, relay_state, power_meter_pin, power_meter_bus,
                         power_meter_shunt_offset, power_meter_voltage_divider_offset, power_meter_min_power,
                         max_charging_time, stop_transaction_function, send_meter_values_function)
        self.set_status(ConnectorStatusType.available)

    def start_charging(self, id_tag: str, transaction_id: str = "", meter_sample_time: int = 60,
                       connector_timeout: int = 30) -> str:
        if self.is_available() or not self.is_reserved(id_tag):
            connector_id: str = f"{self.evse_id}_{self.connector_id}"
            try:
                self._charging_scheduler.get_job(f"cancel_reservation_{connector_id}").remove()
            except Exception as ex:
                logger.debug(f"Cancelling reservation schedule failed at {connector_id}", exc_info=ex)
                print(ex)
                response = self._ChargingSession.start_charging_session(id_tag, str(uuid.uuid4()))
                if response == SessionResponses.SessionStartSuccess:
                    self._relay.on()
                self._power_meter.reset()
                self.__set_watchdogs(meter_sample_time=meter_sample_time,
                                     connector_timeout=connector_timeout)
                self._charging_scheduler.add_job(ConnectorSettingsManager.update_session,
                                                 args=[self.evse_id, self.connector_id,
                                                       {
                                                           "is_active": True,
                                                           "transaction_id": self.get_current_transaction_id,
                                                           "tag_id": self.get_current_tag_id,
                                                           "started": datetime.now().isoformat()
                                                       }])
            return SessionResponses.SessionStartSuccess
        return SessionResponses.SessionStartFailure

    def __set_watchdogs(self, meter_sample_time: int, connector_timeout: int, max_charging_time=180):
        connector_id = f"{self.evse_id}_{self.connector_id}"
        # Add a watchdog for the max charging time
        self._charging_scheduler.add_job(self._stop_transaction_function, 'interval',
                                         minutes=self._max_charging_time,
                                         id=f"charging_watchdog_{connector_id}",
                                         args=[self.evse_id, self.connector_id, "", ReasonType.time_limit_reached],
                                         max_instances=1)
        if isinstance(self._power_meter, PowerMeter) and ConnectorV201._sampling_info.SampledDataEnabled:
            # Add a job for sampling the meter values
            self._charging_scheduler.add_job(self._sample_meter,
                                             'interval',
                                             seconds=1,
                                             id=f"meter_sampling_{connector_id}",
                                             max_instances=1)
            self._charging_scheduler.add_job(self._update_meter_values,
                                             'interval',
                                             seconds=meter_sample_time,
                                             id=f"update_meter_values_{connector_id}",
                                             max_instances=1)
            # Check if connector is plugged periodically
            self._charging_scheduler.add_job(self.__check_if_connector_plugged, 'interval',
                                             seconds=connector_timeout,
                                             id=f"connector_timeout_{connector_id}",
                                             max_instances=1)

    def __check_if_connector_plugged(self):
        # If the power is still not being drawn, stop charging
        if self.get_power_draw < self._power_meter_min_power and self.is_charging():
            self._charging_scheduler.add_job(self._send_meter_values_function,
                                             args=[self.evse_id, self.connector_id,
                                                   TriggerReasonType.ev_connect_timeout])
            self._charging_scheduler.add_job(self._stop_transaction_function,
                                             args=[self.evse_id, self.connector_id,
                                                   self.get_current_tag_id,
                                                   ReasonType.ev_disconnected],
                                             max_instances=1)

    def is_available(self) -> bool:
        return self._connector_status == ConnectorStatusType.available

    def is_charging(self) -> bool:
        return self._ChargingSession.is_active and self._connector_status == ConnectorStatusType.charging

    def is_faulted(self) -> bool:
        return self._connector_status == ConnectorStatusType.faulted

    def is_unavailable(self) -> bool:
        return self._connector_status == ConnectorStatusType.unavailable

    def is_occupied(self) -> bool:
        return self._connector_status == ConnectorStatusType.reserved

    def get_status(self) -> str:
        return super(ConnectorV201, self).get_status().value

    def set_status(self, status: ConnectorStatusType):
        super(ConnectorV201, self).set_status(status)
