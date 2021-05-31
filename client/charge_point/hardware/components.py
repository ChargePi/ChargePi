import asyncio
import time
import spidev
import RPi.GPIO as GPIO
from rpi_ws281x import Color
from RPLCD.i2c import CharLCD as i2c_lcd
from RPLCD.gpio import CharLCD as lcd
import board
import busio
from string_utils import is_full_string
from digitalio import DigitalInOut
from adafruit_pn532.i2c import PN532_I2C


class Relay:
    """
    A simple class for a Relay. Takes the pin number and default state of the pin as an argument.
    Performs on and off actions and tracks it's state.
    """

    def __init__(self, pin: int, relay_state: int):
        self._pin = pin
        self._relay_state = relay_state
        self._inverse_logic = False
        GPIO.setup(self._pin, GPIO.OUT)
        if relay_state == GPIO.HIGH:
            self._inverse_logic = True
        GPIO.output(self._pin, relay_state)

    def on(self):
        """
        Turn the relay on.
        :return:
        """
        if self._relay_state == GPIO.LOW:
            GPIO.output(self._pin, GPIO.HIGH)
            self._relay_state = GPIO.HIGH
        elif self._inverse_logic:
            self.off()

    def off(self):
        """
        Turn the relay off.
        :return:
        """
        if self._relay_state == GPIO.HIGH:
            GPIO.output(self._pin, GPIO.LOW)
            self._relay_state = GPIO.LOW
        elif self._inverse_logic:
            self.on()

    def toggle(self):
        """
        Toggle the relay state.
        :return:
        """
        if self._relay_state == GPIO.HIGH:
            GPIO.output(self._pin, GPIO.LOW)
            self._relay_state = GPIO.LOW
        else:
            GPIO.output(self._pin, GPIO.HIGH)
            self._relay_state = GPIO.HIGH


class LEDStrip:
    """
    Class with LED strip color values.
    """

    RED: Color = Color(255, 0, 0)
    GREEN: Color = Color(0, 255, 0)
    BLUE: Color = Color(0, 0, 255)
    YELLOW: Color = Color(245, 241, 29)
    ORANGE: Color = Color(255, 144, 59)
    WHITE: Color = Color(255, 255, 255)
    OFF: Color = Color(0, 0, 0)


class PowerMeter:
    """
    Class representing a CS5460 power meter chip. Reads values from the meter to log consumption on a connector.
    """

    def __init__(self, pin: int = 0, bus: int = 0, voltage_divider_offset: float = 52,
                 current_shunt_offset: float = 0.01):
        # Init spi
        self.pin: int = pin
        self.bus: int = bus
        GPIO.setup(self.pin, GPIO.OUT)
        # Input range (+-) in mV
        self.VOLTAGE_RANGE: float = 0.250
        self.CURRENT_RANGE: float = 0.250
        # (R1 + R2) / R2
        self.VOLTAGE_DIVIDER: float = voltage_divider_offset
        # Shunt resistance in ohms
        self.CURRENT_SHUNT: float = current_shunt_offset
        self.VOLTAGE_MULTIPLIER: float = (self.VOLTAGE_RANGE * self.VOLTAGE_DIVIDER)
        self.CURRENT_MULTIPLIER: float = (self.CURRENT_RANGE / self.CURRENT_SHUNT)
        self.POWER_MULTIPLIER = self.VOLTAGE_MULTIPLIER * self.CURRENT_MULTIPLIER
        # Set power meter constants
        self.START_SINGLE_CONVERT = 0xE0
        self.START_MULTI_CONVERT = 0xE8
        self.SYNC0 = 0xFE
        self.SYNC1 = 0xFF
        self.POWER_UP_HALT_CONTROL = 0xA0
        self.POWER_DOWN_MODE_0 = 0x80
        self.POWER_DOWN_MODE_1 = 0x88
        self.POWER_DOWN_MODE_2 = 0x90
        self.POWER_DOWN_MODE_3 = 0x98
        self.CALIBRATE_CONTROL = 0xC0
        self.CALIBRATE_CURRENT = 0x08
        self.CALIBRATE_VOLTAGE = 0x10
        self.CALIBRATE_CURRENT_VOLTAGE = 0x18
        self.CALIBRATE_GAIN = 0x02
        self.CALIBRATE_OFFSET = 0x01
        self.CALIBRATE_ALL = 0x1B
        self.CONFIG_REGISTER = (0x00 << 1)
        self.CURRENT_OFFSET_REGISTER = (0x01 << 1)
        self.CURRENT_GAIN_REGISTER = (0x02 << 1)
        self.VOLTAGE_OFFSET_REGISTER = (0x03 << 1)
        self.VOLTAGE_GAIN_REGISTER = (0x04 << 1)
        self.CYCLE_COUNT_REGISTER = (0x05 << 1)
        self.PULSE_RATE_REGISTER = (0x06 << 1)
        self.LAST_CURRENT_REGISTER = (0x07 << 1)
        self.LAST_VOLTAGE_REGISTER = (0x08 << 1)
        self.LAST_POWER_REGISTER = (0x09 << 1)
        self.TOTAL_ENERGY_REGISTER = (0x0A << 1)
        self.RMS_CURRENT_REGISTER = (0x0B << 1)
        self.RMS_VOLTAGE_REGISTER = (0x0C << 1)
        self.TIME_BASE_CALI_REGISTER = (0x0D << 1)
        self.STATUS_REGISTER = (0x0F << 1)
        self.INTERRUPT_MASK_REGISTER = (0x1A << 1)
        self.WRITE_REGISTER = 0x40
        self.READ_REGISTER = (~self.WRITE_REGISTER)
        self.CHIP_RESET = 0x01 << 7
        self.SIGN_BIT = 0x01 << 23
        self.DATA_READY = 0x01 << 23
        self.CONVERSION_READY = 0x01 << 20
        self._spi = spidev.SpiDev()
        self._spi.open(bus, 0)
        self._spi.max_speed_hz = 500000
        self._spi.no_cs = True

        # initial sync
        try:
            GPIO.output(self.pin, GPIO.LOW)
            self._spi.writebytes([self.SYNC1, self.SYNC1, self.SYNC1, self.SYNC0])
            GPIO.output(self.pin, GPIO.HIGH)
        except Exception as ex:
            print(ex)
        self._start_converting()

    def __send(self, data):
        """
        Send data to the chip.
        :param data: Byte to send
        """
        try:
            GPIO.output(self.pin, GPIO.LOW)
            # Send data
            self._spi.writebytes([data])
            GPIO.output(self.pin, GPIO.HIGH)
        except Exception as ex:
            print(ex)

    def _send_to_register(self, register, data):
        """
        Send data to a certain register.
        :param register: Register address (5 bits << 1)
        :param data: data to write (3 bytes)
        :return:
        """
        try:
            GPIO.output(self.pin, GPIO.LOW)
            # Select register for writing
            self._spi.writebytes([register | self.WRITE_REGISTER])
            # Send data
            self._spi.writebytes([(data & 0xFF0000) >> 16, (data & 0xFF00) >> 8, data & 0xFF])
            GPIO.output(self.pin, GPIO.HIGH)
        except Exception as ex:
            print(ex)

    def reset(self):
        self._send_to_register(self.CONFIG_REGISTER, self.CHIP_RESET)
        try:
            GPIO.output(self.pin, GPIO.LOW)
            self._spi.writebytes([self.SYNC1, self.SYNC1, self.SYNC1, self.SYNC0])
            GPIO.output(self.pin, GPIO.HIGH)
        except Exception as ex:
            print(ex)
        self._start_converting()
        while not (self.__get_status() & self.CONVERSION_READY):
            # Wait until conversion starts
            pass

    def _start_converting(self):
        self.__clear_status(self.CONVERSION_READY)
        self.__send(self.START_MULTI_CONVERT)
        while not (self.__get_status() & self.CONVERSION_READY):
            # Wait until conversion starts
            pass

    def _stop_converting(self):
        self.__send(self.POWER_UP_HALT_CONTROL)

    def __read_value_from_register(self, register):
        """
        Get the current value of the desired register
        :return: Register value between 0 and 0xFFFFFF
        """
        value = 0
        try:
            GPIO.output(self.pin, GPIO.LOW)
            # Select register for reading
            self._spi.writebytes([register & self.READ_REGISTER])
            # Read the register
            read_list = self._spi.readbytes(3)

            for i in range(0, 3):
                value <<= 8
                value |= read_list[i]
            GPIO.output(self.pin, GPIO.HIGH)
        except Exception as ex:
            print(ex)
        return value

    def __signed_to_float(self, data):
        """
        Convert signed int value to float
        :param data: Raw register value
        :return: Float from -1 to 1
        """
        if data & self.SIGN_BIT:
            data = data - (self.SIGN_BIT << 1)
        return data / self.SIGN_BIT

    def get_current(self) -> float:
        """
        Get current measured in the last conversion cycle in Amps (A).
        :return: Electric current value
        """
        current_value_raw = self.__read_value_from_register(self.LAST_CURRENT_REGISTER)
        return self.__signed_to_float(current_value_raw) * self.CURRENT_MULTIPLIER

    def get_voltage(self) -> float:
        """
        Get voltage measured in the last conversion cycle in Volts (V).
        :return: Voltage value
        """
        voltage_value_raw = self.__read_value_from_register(self.LAST_VOLTAGE_REGISTER)
        return self.__signed_to_float(voltage_value_raw) * self.VOLTAGE_MULTIPLIER

    def get_current_power_draw(self) -> float:
        """
        Get instantaneous power from the last conversion cycle in Watts (W).
        :return: Power value
        """
        power_value_raw = self.__read_value_from_register(self.LAST_POWER_REGISTER)
        return self.__signed_to_float(power_value_raw) * self.POWER_MULTIPLIER

    def get_energy_consumption(self) -> float:
        """
        Get energy consumed in the last computation cycle in Joules (J)
        This should be called every second and the result added to total
        energy.
        :return: Energy value
        """
        energy_value_raw = self.__read_value_from_register(self.TOTAL_ENERGY_REGISTER)
        return self.__signed_to_float(energy_value_raw) * self.POWER_MULTIPLIER

    def __get_status(self):
        return self.__read_value_from_register(self.STATUS_REGISTER)

    def __clear_status(self, cmd):
        self._send_to_register(self.STATUS_REGISTER, cmd)

    def __calibrate(self, cmd):
        """
        Performs the calibration and stores the value in the appropriate
        register. The value needs to be written to the register after
        every reset. The calibration doesn't seem to work very well,
        it's better to read the value and then invert it manually.
        :param cmd:
        :return:
        """
        # Stop any conversions
        self._stop_converting()
        self.__clear_status(self.DATA_READY)
        cmd = self.CALIBRATE_CONTROL | (cmd & self.CALIBRATE_ALL)
        self.__send(cmd)
        while not (self.__get_status() & self.DATA_READY):
            # Wait until data ready
            pass
        self.__clear_status(self.DATA_READY)
        self._start_converting()

    def calibrate_voltage_offset(self) -> int:
        """
        Short the VIN+ and VIN- pins and call the function.
        The value will be stored until next reset.
        :return: VOLTAGE_OFFSET_REGISTER value
        """
        self.__calibrate(self.CALIBRATE_VOLTAGE | self.CALIBRATE_OFFSET)
        return self.__read_value_from_register(self.VOLTAGE_OFFSET_REGISTER)

    def set_voltage_offset(self, value):
        """
        Sets the VOLTAGE_OFFSET_REGISTER, use to restore
        a previously measured calibration value.
        A good default value is 400000
        :param value: VOLTAGE_OFFSET_REGISTER value
        """
        self._stop_converting()
        self._send_to_register(self.VOLTAGE_OFFSET_REGISTER, value)
        self._start_converting()

    def calibrate_current_offset(self) -> int:
        """
        Short the VIN+ and VIN- pins and call the function.
        The value will be stored until next reset.
        :return: VOLTAGE_OFFSET_REGISTER value
        """
        self.__calibrate(self.CALIBRATE_CURRENT | self.CALIBRATE_OFFSET)
        return self.__read_value_from_register(self.CURRENT_OFFSET_REGISTER)

    def set_current_offset(self, value):
        """
        Sets the CURRENT_OFFSET_REGISTER, use to restore
        a previously measured calibration value.
        A good default value is -70000
        :param value: CURRENT_OFFSET_REGISTER value
        """
        self._stop_converting()
        self._send_to_register(self.CURRENT_OFFSET_REGISTER, value)
        self._start_converting()


class LCDModule:
    """
    A class for LCD module with I2C support.
    Displays the current consumption/power of the power meter, connector availability and other important messages.
    """

    def __init__(self, lcd_info: dict):
        self._lcd = None
        self.is_lcd_supported: bool = lcd_info["is_supported"]
        self._i2c_address: str = lcd_info["i2c_address"]
        try:
            if self.is_lcd_supported:
                if is_full_string(self._i2c_address):
                    self._lcd = i2c_lcd(i2c_expander="PCF8574", address=int(self._i2c_address, 16), cols=16, rows=2)
                else:
                    self._lcd = lcd(pin_rs=15,
                                    pin_rw=18,
                                    pin_e=16,
                                    pins_data=[21, 22, 23, 24],
                                    rows=2,
                                    cols=16)
                self.clear()
        except Exception as ex:
            self.is_lcd_supported = False
            print(ex)

    def clear(self):
        if self._lcd is None:
            return
        self._lcd.clear()

    async def __display_in_rows(self, row1_msg: str, row2_msg: str, delay: int):
        if self._lcd is None or not self.is_lcd_supported:
            return
        self.clear()
        self._lcd.cursor_pos = (0, 0)
        self._lcd.write_string(row1_msg)
        self._lcd.cursor_pos = (1, 0)
        self._lcd.write_string(row2_msg)
        await asyncio.sleep(delay)

    async def display_current_status(self, connector_id: int, is_charging: bool, consumption: float):
        """
        Display the connector's current status to the LCD.
        :param connector_id: A connector ID
        :param is_charging: Connector's charging state
        :param consumption: Current value of the meter
        :return:
        """
        row2_msg: str = "Available"
        if is_charging:
            if consumption > 1000:
                appendix = "kWh"
            else:
                appendix = "Wh"
            row2_msg = f"Consumed: {consumption} {appendix}"
        await self.__display_in_rows(row1_msg=f"Connector: {connector_id}",
                                     row2_msg=row2_msg,
                                     delay=10)

    async def display_card_detected(self):
        await self.__display_in_rows(row1_msg="Card read", row2_msg="", delay=3)

    async def display_invalid_card(self):
        await self.__display_in_rows(row1_msg="Card", row2_msg="Unauthorized", delay=3)

    async def start_charging_message(self, connector_id: int):
        await self.__display_in_rows(row1_msg="Started charging",
                                     row2_msg=f"on {connector_id}",
                                     delay=4)

    async def stop_charging_message(self, connector_id: int):
        await self.__display_in_rows(row1_msg="Stopped charging",
                                     row2_msg=f"on {connector_id}",
                                     delay=4)

    async def connector_unavailable(self, connector_id: int):
        if connector_id == -1:
            await self.__display_in_rows(row1_msg="No available",
                                         row2_msg="connectors",
                                         delay=4)
        else:
            await self.__display_in_rows(row1_msg=f"Connector {connector_id}",
                                         row2_msg="unavailable",
                                         delay=4)

    async def display_error(self, connector_id: int, msg: str):
        if connector_id == -1:
            await self.__display_in_rows(row1_msg="Error",
                                         row2_msg="",
                                         delay=3)
        else:
            await self.__display_in_rows(row1_msg="Fault on",
                                         row2_msg=f"Connector {connector_id}:",
                                         delay=3)
            await self.__display_in_rows(row1_msg=msg,
                                         row2_msg="",
                                         delay=5)

    async def not_connected_error(self):
        await self.__display_in_rows(row1_msg="Charging",
                                     row2_msg="unavailable",
                                     delay=4)


class PN532Reader:
    def __init__(self, hard_reset_pin):
        GPIO.setup(hard_reset_pin, GPIO.OUT)
        self._hard_reset_pin = hard_reset_pin
        self.reset()
        self._i2c = busio.I2C(board.SCL, board.SDA)
        self._reset_pin = DigitalInOut(board.D6)
        self._req_pin = DigitalInOut(board.D12)
        self._reader: PN532_I2C = PN532_I2C(self._i2c, debug=False, reset=self._reset_pin, req=self._req_pin)
        self._reader.SAM_configuration()

    def read_passive(self):
        return self._reader.read_passive_target(timeout=.3)

    def reset(self):
        print("Reset PN532")
        GPIO.output(self._hard_reset_pin, GPIO.LOW)
        time.sleep(.2)
        GPIO.output(self._hard_reset_pin, GPIO.HIGH)
        time.sleep(.2)
