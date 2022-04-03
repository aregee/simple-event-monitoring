# Simple Event Monitoring 

Originally, started as a fork of  [simple mail monitoring](https://github.com/wichmannpas/simple-mail-monitoring) , but instead of doing cron for scheduling, this light weight patterns incorporates a very Simple Publish Subscribe Pattern levearging [aiopubsub](https://gitlab.com/quantlane/libs/aiopubsub)

# Why 
> When building big applications, separation of concerns is a great way to keep things manageable. In messaging systems, the publish-subscribe pattern is often used to decouple data producers and data consumers. We went a step ahead and designed even the internals of our applications around this pattern.: [aiopubsub](https://gitlab.com/quantlane/libs/aiopubsub)


To understand the thinking and the workings of aiopubsub in detail, read through their article [Design your app using the pub-sub pattern with aiopubsub](https://quantlane.com/blog/aiopubsub/).


Simple Event Monitor is a small framework that allows you develop integrations with Pull based systems such as monitoring a website, or checking email etc and adding hooks or events that should occur, like a typical IFTT framework.
SEM utilizes a [Redux](https://redux.js.org/) like store abstraction and API over aiopubsub to allow for more consise and clean way to add producers and consumers.


# How 

```py

import asyncio
import aiopubsub

from hub import Reducer, DispatchEvent, SimpleEventMonitor, Store, run_every


def test_mail_delivery_subscription(redux: Store):

    async def log_subject(key: aiopubsub.Key, payload: str):
        print(payload['subject'])

    async def on_test_event_ack(key: aiopubsub.Key, payload: dict):
        print(f'Received Event {payload} for key = {key}')
        redux.dispatch_event(
            DispatchEvent(name="smm",
                          topic=["log", "event"],
                          payload=payload['subject']))

    test_reducer = Reducer(event=['*', 'test', 'event'],
                           action=on_test_event_ack)
    log_reducer = Reducer(event=['*', 'test', 'event'], action=log_subject)

    redux.combine_reducers(test_reducer, log_reducer)


@run_every(180)
def test_publisher(redux):

    event_payload = {'subject': 'hello world'}

    some_event = DispatchEvent(name='smm',
                               topic=['test', 'event'],
                               payload=event_payload)

    redux.dispatch_event(some_event)


def main(redux):
    test_mail_delivery_subscription(redux)
    test_publisher(redux)


if __name__ == '__main__':
    event = SimpleEventMonitor(boot=main)
    asyncio.run(event.run())

```



## Simple Mail Monitoring

This is a very simple script for email delivery checking/monitoring. It sends a test email with a random subject to the configured recipient address using a configured SMTP configuration (e.g., SMTP on localhost).

Afterwards, it tries to retrieve that email using IMAP authenticating *on the remote mail server*. When it has successfully fetched the email.
It writes a scrape result in the prometheus textfile format.
This can be read by prometheus to collect metrics and allow alerts using alertmanager.

The script’s purpose is to be executed on a *different server* than the tested mailhost.
This way, it can check whether external email delivery works as intended.
Running it directly on the mailhost can cause some errors to go unnoticed, i.e., if only external email submission is affected.

To deploy this script, adapt the `config.py.example` as `config.py` and run pubsub.py with something like [Supervisor](http://supervisord.org/)
