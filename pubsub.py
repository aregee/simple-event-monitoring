import asyncio
import dataclasses
import decimal
import uuid, logging, config
import json

from hub import Reducer, DispatchEvent, SimpleEventMonitor, run_every
from random import SystemRandom

from reducers.test_mail_delivery_reducer import test_mail_delivery_subscription
from string import ascii_letters, digits


random = SystemRandom()


@run_every(180)
def email_publisher(redux):
    subject_identifier = ''.join(
        random.choice(ascii_letters + digits) for i in range(30))
    subject = config.TEST_MAIL['subject'].format(subject_identifier)
    metrics = {'subject': subject}

    ocp_event = DispatchEvent(name="smm",
                              topic=['email', 'send'],
                              payload=metrics)

    redux.dispatch_event(ocp_event)


def main(redux):

    test_mail_delivery_subscription(redux)
    email_publisher(redux)


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)-15s: %(message)s',
                        level=config.LOG_LEVEL)
    event = SimpleEventMonitor(boot=main)
    asyncio.run(event.run())