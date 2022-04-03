import asyncio
import collections
import functools
from .redux import Store


class SimpleEventMonitor:
    """Callback based implementation, this time we'll use the `AbstractEventLoop.call_later`
    synchronous call to schedule again the run of a callable callback.
    """

    def __init__(self, boot):
        self.boot = boot
        self.store = Store()
        self.event = None

    async def run(self):
        loop = asyncio.get_running_loop()
        self.event = asyncio.Event()
        loop.call_later(0, self.boot, self.store)
        try:
            await self.event.wait()
        except KeyboardInterrupt:
            await self.shutdown()

    async def shutdown(self):
        self.event.set()
        await self.store.destroy()


def run_every(seconds):

    def inner_func(func):

        @functools.wraps(func)
        def func_wrapper(*args, **kwargs):
            loop = asyncio.get_running_loop()
            func(*args, **kwargs)
            loop.call_later(seconds, func_wrapper, *args, **kwargs)

        return func_wrapper

    return inner_func
