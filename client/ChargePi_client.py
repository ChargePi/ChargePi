import asyncio
import logging
import atexit
import time
from urllib import parse
from datetime import datetime
from unsync import unsync
from websockets import InvalidURI, ConnectionClosedError, ConnectionClosedOK
from charge_point.data import logging_filter
from charge_point.hardware.components import LCDModule, PN532Reader
from charge_point.v16.ChargePoint16 import ChargePointV16, enums
from charge_point.v201.ChargePoint201 import ChargePointV201
from charge_point import responses
import RPi.GPIO as GPIO
import websockets
from string_utils import is_full_string
from mfrc522 import SimpleMFRC522
import charge_point.data.settings_manager as settings_reader
import os

lcd: LCDModule = None
charge_point_reference = None
logger = logging.getLogger('chargepi_logger')
path = os.path.dirname(os.path.realpath(__file__))
GPIO.setmode(GPIO.BCM)


@unsync
async def choose_protocol_version():
    global lcd, charge_point_reference
    charge_point_info, hardware_info = await settings_reader.read_settings()
    charge_point_id: str = charge_point_info["id"]
    charge_point_uri: str = charge_point_info["server_uri"]
    # Setup logger
    logging_filter.setup_logger(charge_point_info["log_server"], charge_point_id)
    # Run RFID reader and LCD display in separate threads
    lcd = LCDModule(hardware_info["lcd"])
    protocol_version = charge_point_info["protocol_version"]
    # Check URL validity
    if parse.urlparse(charge_point_uri).path.endswith("/"):
        charge_point_uri = charge_point_uri[:charge_point_uri.rfind("/")]
    # If the connection goes out, try reconnecting every 10 seconds
    threads = []
    while True:
        try:
            # Connect to the server using websockets.
            async with websockets.connect(f"ws://{charge_point_uri}/{charge_point_id}",
                                          subprotocols=[f"ocpp{protocol_version}"]) as ws:
                logger.info(f"Choosing protocol version {protocol_version}")
                if protocol_version == "1.6":
                    # Create a singleton
                    ChargePointV16(charge_point_id, ws, charge_point_info, hardware_info)
                    charge_point_reference = ChargePointV16.getInstance()
                elif protocol_version == "2.0.1":
                    # Create a singleton
                    ChargePointV201(charge_point_id, ws, charge_point_info, hardware_info)
                    charge_point_reference = ChargePointV201.getInstance()
                else:
                    # If the version is not supported, exit
                    version_unsupported_str: str = f"Unsupported OCPP version: {protocol_version}"
                    logger.debug(version_unsupported_str)
                    print(version_unsupported_str)
                    exit(-1)
                # Start listening for requests and send boot notification to the server
                display_current_status_LCD()
                read_rfid(hardware_info)
                await asyncio.gather(charge_point_reference.start(), charge_point_reference.send_boot_notification())
        except ConnectionClosedOK as closed_ok:
            logger.error("Connection closed, no error", exc_info=closed_ok)
        except ConnectionClosedError as error:
            logger.error("Connection closed with error", exc_info=error)
        except InvalidURI as invalid_uri:
            logger.error("Invalid URI specified, exiting", exc_info=invalid_uri)
            exit(-1)
        except KeyboardInterrupt:
            exit(-1)
        except Exception as ex:
            logger.error("Unknown error", exc_info=ex)
        for thread in threads:
            try:
                thread.future.cancel()
                thread.thread.set_exception()
            except Exception:
                pass
        await asyncio.sleep(10)


@unsync
def display_current_status_LCD():
    global lcd
    if lcd.is_lcd_supported:
        asyncio.run(display_status())


async def display_status():
    global charge_point_reference
    while True:
        try:
            for connector in charge_point_reference.get_connectors:
                await lcd.display_current_status(connector.connector_id,
                                                 connector.is_charging(),
                                                 connector.get_power_draw)
        except Exception as ex:
            print(ex)


def get_reader(reader_info):
    if reader_info["is_supported"]:
        if reader_info["reader_model"] == "MFRC522":
            return SimpleMFRC522()
        elif reader_info["reader_model"] == "PN532":
            try:
                return PN532Reader(int(reader_info["reset_pin"]))
            except Exception as ex:
                logger.error("Reader not found", exc_info=ex)
                print(ex)
                return None
    return None


@unsync
def read_rfid(charge_point_info: dict):
    global lcd
    reader_info = charge_point_info["rfid_reader"]
    reader = get_reader(reader_info)
    # Start listening for RFID tag
    while True:
        try:
            if reader is not None:
                print(f"{datetime.today()}: Scanning for a tag")
                uid: str = ""
                if reader_info["reader_model"] == "MFRC522":
                    try:
                        uid = hex(reader.read_id_no_block()).strip("0x").upper()[:-2]
                    except Exception:
                        pass
                    time.sleep(.3)
                elif reader_info["reader_model"] == "PN532":
                    try:
                        uid_byte: bytearray = reader.read_passive()
                        uid = uid_byte.hex().upper()
                    except Exception:
                        pass
                if is_full_string(uid):
                    read_tag_info: str = f"Read tag {uid} at {datetime.today()}"
                    logger.info(read_tag_info)
                    print(read_tag_info)
                    handle_request(uid)
                    # Wait to be sure the card is removed
                    time.sleep(4)
            else:
                # If no RFID reader is present, charging will begin at a request from server
                # Break the loop to end the thread and avoid performance issues
                break
        except Exception as e:
            logger.error("Exception while reading RFID", exc_info=e)
            print(str(e))
            asyncio.run(lcd.display_error(connector_id=-1, msg="Error reading card"))
            if isinstance(reader, PN532Reader):
                reader.reset()


@unsync
async def handle_request(rfid_id: str):
    global lcd, charge_point_reference
    await asyncio.gather(charge_point_reference.indicate_card_read(), lcd.display_card_detected())
    try:
        if charge_point_reference is not None and is_full_string(rfid_id):
            connector_id, response = await charge_point_reference.handle_charging_request(rfid_id)
            if response == responses.StartChargingSuccess:
                await lcd.start_charging_message(connector_id=connector_id)
            elif response == responses.StopChargingSuccess:
                await lcd.stop_charging_message(connector_id=connector_id)
            elif response == responses.ConnectorUnavailable:
                await lcd.connector_unavailable(connector_id=connector_id)
            elif response == responses.NoAvailableConnectors:
                await lcd.connector_unavailable(connector_id=connector_id)
            elif response == responses.UnauthorizedCard:
                await asyncio.gather(asyncio.sleep(2),
                                     charge_point_reference.indicate_card_rejected(),
                                     lcd.display_invalid_card())
            else:
                await lcd.display_error(connector_id=connector_id, msg=response)
    except Exception as ex:
        print(f"Exception while handling tag request: {ex}")
        logger.error("Exception while handling tag request", exc_info=ex)
        await lcd.display_error(-1, str(ex))


@atexit.register
def client_cleanup():
    """
    Clean up before exiting
    :return:
    """
    global lcd, charge_point_reference
    try:
        lcd.clear()
        charge_point_reference.cleanup(reason=enums.Reason.powerLoss)
    except Exception as ex:
        print("Problem at cleanup: {ex}".format(ex=str(ex)))
        logger.debug("Exception while cleaning up", exc_info=ex)
    finally:
        GPIO.cleanup()


if __name__ == '__main__':
    choose_protocol_version().result()
