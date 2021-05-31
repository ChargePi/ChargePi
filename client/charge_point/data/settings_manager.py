import json
from aiofiles import open
import os

_path = os.path.dirname(os.path.realpath(__file__))


async def read_settings() -> (dict, dict):
    async with open("{path}/../../settings.json".format(path=_path), "r", buffering=True) as settings_file:
        config_data = await settings_file.read()
        data: dict = json.loads(config_data)
        charge_point_info: dict = data["charge_point"]["info"]
        hardware_info: dict = data["charge_point"]["hardware"]
        await settings_file.close()
        return charge_point_info, hardware_info
