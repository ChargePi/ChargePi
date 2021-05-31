import json
import asyncio
import logging
from aiofiles import open
from string_utils import is_full_string
import os

path = os.path.dirname(os.path.realpath(__file__))
logger = logging.getLogger('chargepi_logger')


class AuthorizationCache:
    def __init__(self, is_cache_supported: bool = False):
        self.__is_cache_supported: bool = is_cache_supported
        self.__version: int = 1
        # structure of authorized tag : {"id": 123, "status":"Accepted", "expiry_date":""}
        self.__cached_tags: list = list()
        self.__max_cached_tags: int = 0
        self.__file_name: str = f"{path}/auth.json"

    @property
    def cached_tags(self) -> list:
        return self.__cached_tags

    def set_max_cached_tags(self, max_cached_tags: int):
        if self.__is_cache_supported and max_cached_tags >= 0:
            self.__max_cached_tags = max_cached_tags

    @property
    def get_version(self) -> int:
        if not self.__is_cache_supported:
            return -1
        if len(self.__cached_tags) == 0:
            return 0
        return self.__version

    async def is_tag_authorized(self, id_tag: str) -> bool:
        """
        Check if tag is in Authorization Cache.
        :param id_tag: Tag ID
        :return: True if it is present, false if not
        """
        return next((tag["status"] == "Accepted" for tag in self.__cached_tags if tag["id"] == id_tag), False)

    async def update_version(self, version: int):
        """
        Update the version of Authorization list.
        :param version: Version number
        :return:
        """
        async with open(self.__file_name, mode="r") as auth_file:
            tag_data = json.loads(await auth_file.read())
            await auth_file.close()
            async with open(self.__file_name, mode="w") as auth:
                tag_data["version"] = version
                await auth.write(json.dumps(tag_data, indent=2, sort_keys=True))
                await auth.close()
                self.__version = version

    async def update_cached_tags(self, tag_list: list):
        """
        Update the list with new authentication tags.
        :param tag_list:
        :return:
        """
        if not self.__is_cache_supported:
            return
        tasks = []
        for tag in tag_list:
            tasks.append(self.update_tag_info(tag["id"], tag["id_tag_info"]))
        await asyncio.gather(*tasks)

    async def update_tag_info(self, id_tag: str, tag_info: dict) -> str:
        """
        Update a specific tag information regarding authorization.
        :param id_tag: Tag ID
        :param tag_info: Tag status, expiry date and timestamp dictionary
        :return:
        """
        if is_full_string(id_tag) and is_full_string(tag_info["status"]) and \
                len(self.__cached_tags) < self.__max_cached_tags - 1 \
                and self.__is_cache_supported:
            tag = {"id": id_tag,
                   "status": tag_info["status"]}
            if "expiry_date" in tag_info.keys():
                tag["expiry_date"] = tag_info["expiry_date"]
            await self.__write_to_auth_file(tag)
            # Reload from file
            await self.__load_tags_from_file()
            return "Success"
        return "Failed"

    async def __write_to_auth_file(self, tag_info: dict):
        """
        Update auth.json file for caching tag information.
        :param tag_info:
        :return:
        """
        async with open(self.__file_name, mode="r") as auth_file:
            # Read the cache
            tag_data = json.loads(await auth_file.read())
            tag_copy = tag_data
            await auth_file.close()
            try:
                async with open(self.__file_name, mode="w") as auth:
                    tag_list: list = tag_data["authorized_tags"]
                    exists_in_cache: bool = False
                    # Find tag info, if exists overwrite current status
                    for index, tag in enumerate(tag_list):
                        if tag["id"] == tag_info["id"]:
                            tag_list[index] = tag_info
                            exists_in_cache = True
                    if not exists_in_cache:
                        tag_list.append(tag_info)
                    await auth.write(json.dumps(tag_data, indent=2, sort_keys=True))
                    await auth.close()
            except Exception as ex:
                logger.debug("Failed overwriting tag info", exc_info=ex)
                print(ex)
                # If overwriting fails, restore old information
                async with open(self.__file_name, mode="w") as backup:
                    await backup.write(json.dumps(tag_copy, indent=2, sort_keys=True))
                    await backup.close()

    async def __load_tags_from_file(self):
        """
        Load cached tag info from a file. If no file is present, create new auth.json file.
        :return: List version and tags
        """
        try:
            async with open(self.__file_name, "r") as auth_file:
                auth_data = json.loads(await auth_file.read())
                await auth_file.close()
                self.__cached_tags = auth_data["authorized_tags"]
                self.__version = auth_data["version"]
        except Exception as ex:
            print(ex)
            logger.debug("Failed loading tags from auth cache", exc_info=ex)
            # await self.clear_cache()

    async def clear_cache(self) -> str:
        """
        Clear the auth file.
        :return:
        """
        try:
            async with open(self.__file_name, "w+") as auth_file:
                auth_data = dict()
                auth_data["version"] = self.__version
                auth_data["authorized_tags"] = list()
                await auth_file.write(json.dumps(auth_data, indent=2, sort_keys=True))
            return "Success"
        except Exception as ex:
            logger.debug("Failed clearing the auth cache", exc_info=ex)
            return "Failed"
