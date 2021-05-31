import logging
import graypy

logger = logging.getLogger('chargepi_logger')


def setup_logger(log_server_ip: str, id: str):
    handler = graypy.GELFUDPHandler(log_server_ip, 12201)
    handler.extra_fields = True
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(cp_id)s : %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    f = ContextFilter(id, "")
    logger.addFilter(f)


class ContextFilter(logging.Filter):

    def __init__(self, CP_ID: str, name: str = ...) -> None:
        super().__init__(name)
        self.CP_ID = CP_ID

    def filter(self, record):
        record.cp_id = self.CP_ID
        return True
