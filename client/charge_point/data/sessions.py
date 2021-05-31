from datetime import datetime
from statistics import mean
from string_utils import is_full_string


class ChargingSession:
    """
    A class representing a Charging Session.
    Each session is unique by a transaction ID and a tag ID.
    The program also logs the energy consumption for each session.
    """

    SessionStartSuccess = "Started"
    SessionStartFailure = "Failed"
    SessionResumeSuccess = "Resumed"
    SessionResumeFailure = "Failed"
    SessionStopSuccess = "Stopped"
    SessionStopFailed = "Failed"
    AlreadyReserved = "Already reserved"
    MeasurementSuccess = "Success"
    MeasurementFailed = "Failed"
    ReservationSuccess = "Reserved"
    ReservationFailed = "Failed"

    def __init__(self):
        self._transaction_id: str = ""
        self._tag_id: str = ""
        self._is_active: bool = False
        # Structure of entries in the list must be:
        # "timestamp": <time>, "sampledValue": [{ "value": <value>, "measurand": <meas>}]
        self._started: str = ""
        self._meter_samples: list = list()
        self._power: list = list()
        self._avg_power: float = 0.0

    def start_charging_session(self, tag_id: str, transaction_id: str = "") -> str:
        """
        Start the charging session.
        :param transaction_id: Transaction ID
        :param tag_id: User or RFID tag ID
        :return:
        """
        if not self._is_active and is_full_string(tag_id) and is_full_string(transaction_id):
            self._transaction_id = transaction_id
            self._tag_id = tag_id
            self._meter_samples = list()
            self._avg_power: float = 0.0
            self._power: list = [self._avg_power]
            self._started: str = datetime.now().isoformat()
            self._is_active = True
            return ChargingSession.SessionStartSuccess
        return ChargingSession.SessionStartFailure

    def stop_charging_session(self) -> str:
        """
        Stop the charging session.
        :return:
        """
        self._is_active = False
        self._tag_id = ""
        self._transaction_id = ""
        return ChargingSession.SessionStopSuccess

    def resume_charging_session(self, tag_id: str, meter_samples: list, transaction_id: str = "",
                                started: str = "") -> str:
        """
        Resume a charging session from previous state which is stored in non-volatile memory.
        :param tag_id: Tag ID
        :param meter_samples: A list of meter samples
        :param transaction_id: Transaction ID
        :param started: Date of the transaction start
        :return:
        """
        if not self._is_active and is_full_string(transaction_id) and is_full_string(tag_id):
            self._transaction_id = transaction_id
            self._tag_id = tag_id
            self._started = started
            self._meter_samples = meter_samples
            self._is_active = True
            return ChargingSession.SessionResumeSuccess
        return ChargingSession.SessionResumeFailure

    def add_power_sample(self, power: float):
        self._power.append(power)
        self._avg_power = mean(self._power)
        if len(self._power) > 30:
            self._power = [self._avg_power]

    def add_meter_sample(self, sample: float):
        """
        Log energy consumption in a list while charging.
        :param: sample:
        :return:
        """
        self._meter_samples.append({"timestamp": datetime.utcnow().isoformat(),
                                    "sampled_value": [
                                        {
                                            "value": f"{sample}"
                                            # "measurand" : <measurand>
                                        }]
                                    })

    @property
    def get_meter_samples(self) -> list:
        return self._meter_samples

    @property
    def get_last_sample(self) -> float:
        try:
            return self._meter_samples[len(self._meter_samples) - 1]
        except Exception as ex:
            print(ex)
            return -1

    @property
    def get_max_sample_value(self) -> float:
        return max(self._power)

    @property
    def get_avg_power(self) -> float:
        return self._avg_power

    @property
    def get_tag_id(self) -> str:
        return self._tag_id

    @property
    def get_session_started(self) -> str:
        return self._started

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def get_transaction_id(self) -> str:
        return self._transaction_id


class Reservation(ChargingSession):
    def __init__(self, tag_id: str, to_date: str, reservation_id: str):
        super().__init__()
        super().__tag_id = tag_id
        self.to_date: str = to_date
        self.reservation_id: str = reservation_id

    @property
    def get_reservation_id(self) -> str:
        return self.reservation_id

    @property
    def get_to_date(self) -> str:
        return self.to_date
