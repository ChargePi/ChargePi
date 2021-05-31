import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from semantic_version import Version
from string_utils import is_full_string
from charge_point.scheduler import SchedulerManager

_path = os.path.dirname(os.path.realpath(__file__))
logger = logging.getLogger('chargepi_logger')


async def update_target_version(version: str):
    current_version = await get_current_version()
    if Version(current_version) > Version(version):
        return
    async with open("{path}/../../settings.json", "w") as current_settings_file:
        current_settings = await current_settings_file.read()
        current_settings_attributes: dict = json.loads(current_settings)
        current_settings_attributes["charge_point"]["info"]["target_client_version"] = version
        await current_settings_file.write(json.dumps(current_settings_attributes))
        await current_settings_file.close()


async def update_current_version():
    version = await get_target_version()
    if is_full_string(version):
        async with open("{path}/../../settings.json", "w") as current_settings_file:
            current_settings = await current_settings_file.read()
            current_settings_attributes: dict = json.loads(current_settings)
            if Version(current_settings_attributes["charge_point"]["info"]["target_client_version"]) < Version(version):
                await current_settings_file.close()
                return
            current_settings_attributes["charge_point"]["info"]["target_client_version"] = version
            await current_settings_file.write(json.dumps(current_settings_attributes))
            await current_settings_file.close()


async def get_current_version() -> str:
    async with open("{path}/../../updates/settings.json".format(path=_path), "r") as settings_file:
        settings = await settings_file.read()
        settings_attributes: dict = json.loads(settings)
        await settings_file.close()
        return settings_attributes["charge_point"]["info"]["current_client_version"]


async def get_target_version() -> str:
    async with open("{path}/../../updates/settings.json".format(path=_path), "r") as settings_file:
        settings = await settings_file.read()
        settings_attributes: dict = json.loads(settings)
        await settings_file.close()
        return settings_attributes["charge_point"]["info"]["target_client_version"]


async def get_next_version() -> Version:
    next_version: Version = Version(await get_current_version()).next_patch()
    if next_version.next_patch() > 10:
        next_version = next_version.next_minor()
    if next_version.next_minor() > 10:
        next_version = next_version.next_major()
    return next_version


async def perform_update(directory: str, retries: int = 5, retry_interval: int = 60):
    _scheduler = SchedulerManager.getScheduler()
    while retries != 0:
        try:
            os.system(f"cp {directory} {_path}/../../")
            _scheduler.add_job(update_current_version, args=[])
            _scheduler.add_job(os.execv,
                               'date',
                               run_date=(datetime.now() + timedelta(seconds=10)),
                               args=[sys.executable, ['sudo python3'] + sys.argv])
            break
        except Exception as ex:
            retries -= 1
            logger.debug("Firmware update failed", exc_info=ex)
            print("Firmware update failed")
            await asyncio.sleep(retry_interval)
