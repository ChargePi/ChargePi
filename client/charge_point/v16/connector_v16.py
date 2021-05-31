from charge_point.hardware.components import PowerMeter
from charge_point.data.sessions import ChargingSession as SessionResponses
import ocpp.v16.enums as enums
import logging
from charge_point.connectors.ChargingConnector import ChargingConnector, ConnectorSettingsManager

logger = logging.getLogger('chargepi_logger')


class ConnectorV16(ChargingConnector):

    def __init__(self, evse_id: int, connector_id: int, conn_type: str, relay_pin: int, relay_state,
                 power_meter_pin: int, power_meter_bus: int, power_meter_voltage_divider_offset: float,
                 power_meter_shunt_offset: float, power_meter_min_power: float,
                 max_charging_time: int, stop_transaction_function,
                 send_meter_values_function):
        super().__init__(evse_id, connector_id, conn_type, relay_pin, relay_state, power_meter_pin, power_meter_bus,
                         power_meter_voltage_divider_offset, power_meter_shunt_offset, power_meter_min_power,
                         max_charging_time, stop_transaction_function, send_meter_values_function)
        self.set_status(enums.ChargePointStatus.available)

    def start_charging(self, id_tag: str, transaction_id: str = "", meter_sample_time: int = 60,
                       connector_timeout: int = 30) -> str:
        response = SessionResponses.SessionStartFailure
        if self.is_available() or self.is_preparing() or not self.is_reserved(id_tag):
            try:
                job_id: str = f"cancel_reservation_{self.evse_id}_{self.connector_id}"
                self._charging_scheduler.get_job(job_id).remove()
            except Exception as ex:
                logger.debug(f"Cancelling reservation failed at {self.connector_id}")
                print(ex)
            response = self._ChargingSession.start_charging_session(tag_id=id_tag, transaction_id=transaction_id)
            if response == SessionResponses.SessionStartSuccess:
                self._relay.on()
                if isinstance(self._power_meter, PowerMeter):
                    self._power_meter.reset()
                self.__set_watchdogs(meter_sample_time=meter_sample_time,
                                     connector_timeout=connector_timeout,
                                     max_charging_time=self._max_charging_time)
                self._charging_scheduler.add_job(ConnectorSettingsManager.update_session,
                                                 args=[self.evse_id, self.connector_id,
                                                       {
                                                           "is_active": True,
                                                           "transaction_id": self.get_current_transaction_id,
                                                           "tag_id": self.get_current_tag_id,
                                                           "started": self._ChargingSession.get_session_started
                                                       }])
        return response

    def __set_watchdogs(self, meter_sample_time: int, connector_timeout: int, max_charging_time: int = 180):
        connector_id: str = f"{self.evse_id}_{self.connector_id}"
        # Add a watchdog for the max charging time
        self._charging_scheduler.add_job(self._stop_transaction_function, 'interval',
                                         minutes=max_charging_time,
                                         id=f"charging_watchdog_{connector_id}",
                                         args=[self.connector_id, "", enums.Reason.local],
                                         max_instances=1)
        if isinstance(self._power_meter, PowerMeter):
            # Sample each second
            self._charging_scheduler.add_job(super()._sample_meter,
                                             'interval',
                                             seconds=1,
                                             id=f"meter_sampling_{connector_id}",
                                             max_instances=1)
            # Add a job for notifying the central system with samples
            self._charging_scheduler.add_job(self._update_meter_values,
                                             'interval',
                                             seconds=meter_sample_time,
                                             id=f"update_meter_values_{connector_id}",
                                             max_instances=1)
            # Check if connector is (still) plugged periodically
            self._charging_scheduler.add_job(self.__check_if_connector_plugged, 'interval',
                                             seconds=connector_timeout,
                                             id=f"connector_timeout_{connector_id}",
                                             max_instances=1)

    def __check_if_connector_plugged(self):
        # If the power is still not being drawn, stop charging
        if self.get_avg_power < self._power_meter_min_power and self.is_charging():
            print(f"Avg power: {self.get_avg_power} below limit, stopping..")
            self._charging_scheduler.add_job(self._stop_transaction_function,
                                             args=[self.connector_id,
                                                   self.get_current_tag_id,
                                                   enums.Reason.evDisconnected],
                                             max_instances=1)

    def is_available(self) -> bool:
        return self._connector_status == enums.ChargePointStatus.available

    def is_preparing(self) -> bool:
        return self._connector_status == enums.ChargePointStatus.preparing

    def is_charging(self) -> bool:
        return self._ChargingSession.is_active and self._connector_status == enums.ChargePointStatus.charging

    def is_faulted(self) -> bool:
        return self._connector_status == enums.ChargePointStatus.faulted

    def is_unavailable(self) -> bool:
        return self._connector_status == enums.ChargePointStatus.unavailable

    def is_occupied(self) -> bool:
        return self._connector_status == enums.ChargePointStatus.reserved

    def get_status(self) -> str:
        return self._connector_status.value

    def set_status(self, status: enums.ChargePointStatus):
        super().set_status(status)
