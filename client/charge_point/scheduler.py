from apscheduler.schedulers.asyncio import AsyncIOScheduler


class SchedulerManager:
    """
    A singleton class for getting a asyncio scheduler for connectors.
    """
    __connector_scheduler: AsyncIOScheduler = None

    @staticmethod
    def getScheduler():
        if SchedulerManager.__connector_scheduler is None:
            SchedulerManager.__connector_scheduler = AsyncIOScheduler()
            SchedulerManager.__connector_scheduler.start()
        return SchedulerManager.__connector_scheduler
