import aiopubsub
import dataclasses


@dataclasses.dataclass
class Reducer:
    event: str or [str]
    action: object
    name: str = 'sem'
    is_async: bool = True


@dataclasses.dataclass
class DispatchEvent:
    name: str
    topic: str or [str]
    payload: object


class Store:

    def __init__(self, *args, **kwargs):
        self.hub = aiopubsub.Hub()
        self.publishers = {}
        self.subscribers = {}

    def add_reducer(self, config: Reducer):
        sub = None
        if config.name in self.subscribers:
            sub = self.subscribers[config.name]
        else:
            sub = aiopubsub.Subscriber(self.hub, config.name)
            self.subscribers[config.name] = sub

        subscribe_key = aiopubsub.Key.__call__(*config.event)
        if config.is_async is False:
            sub.add_sync_listener(subscribe_key, config.action)
        else:
            sub.add_async_listener(subscribe_key, config.action)
        return self

    def combine_reducers(self, *args: [Reducer]):
        for reducer in args:
            self.add_reducer(reducer)

    def dispatch_event(self, event: DispatchEvent):
        pub = None
        if event.name in self.publishers:
            pub = self.publishers[event.name]
        else:
            pub = aiopubsub.Publisher(self.hub,
                                      prefix=aiopubsub.Key(event.name))
        publish_key = aiopubsub.Key.__call__(*event.topic)
        pub.publish(publish_key, event.payload)

    async def destroy(self):
        for sub in self.subscribers.values():
            await sub.remove_all_listeners()
