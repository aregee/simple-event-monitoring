#!/usr/bin/env python3
import logging
import os
import traceback
from datetime import datetime
from email import message_from_string
from email.mime.text import MIMEText
from email.utils import format_datetime, mktime_tz, parsedate_tz
from imaplib import IMAP4_SSL
from random import SystemRandom
from smtplib import SMTP_SSL
from string import ascii_letters, digits
from tempfile import NamedTemporaryFile
from time import sleep
from typing import Optional
import asyncio, aiopubsub
from hub import Reducer, DispatchEvent
import config

random = SystemRandom()


# subject_identifier = ''.join(random.choice(ascii_letters + digits) for i in range(30))
# subject = config.TEST_MAIL['subject'].format(subject_identifier)
def check_delivery(metrics: dict):
    retry = 0
    while True:
        sleep(2)

        logging.info('trying to fetch test mail, retry %s', retry)
        date = get_email_date(metrics['subject'])
        if date:
            break
        retry += 1
        if retry > config.MAX_RETRIES:
            logging.error('failed to fetch test mail')
            return

    if not date:
        logging.error('failed to get the date of the last email')
        return

    after_receive = datetime.now()
    receive_time_seconds = (after_receive - metrics['after_send']).total_seconds()
    metrics['receive_time_seconds'] = receive_time_seconds

    metrics['mail_timestamp'] = date.timestamp()

    metrics['success'] = True
    return metrics


def get_email_date(subject: str) -> Optional[datetime]:
    """
    Get the date of the email with specified subject and delete it.

    Warning: no escaping of subject is performed.
    """
    most_recent_date = None

    with IMAP4_SSL(config.IMAP['host']) as conn:
        conn.login(config.IMAP['user'], config.IMAP['password'])
        conn.select(config.IMAP['mailbox'])

        logging.info('connected to mailbox %s', config.IMAP['mailbox'])

        state, matches = conn.search(None, '(SUBJECT "{}")'.format(subject))
        if state != 'OK':
            logging.error('failure listing messages')
            return
        matches = [match for match in matches[0].split(b' ') if match]
        logging.info('found %s matching message(s)', len(matches))
        for match in matches:
            state, msg = conn.fetch(match, '(RFC822)')
            if state != 'OK':
                logging.error('failure fetching message')
                return
            msg = message_from_string(msg[0][1].decode())
            msg_date = datetime.fromtimestamp(
                mktime_tz(parsedate_tz(msg['Date'])))
            logging.info('fetched message %s, date %s', int(match), msg_date)

            if most_recent_date is None or msg_date > most_recent_date:
                most_recent_date = msg_date

            conn.store(match, '+FLAGS', '\\Deleted')

        logging.info('expunging mailbox')
        conn.expunge()

    return most_recent_date


def send_test_message(subject: str):
    mail = MIMEText(
        'This is a test email. Its sole purpose is to act as a test email\n'
        'whose existence will confirm that email delivery is working\n'
        'as it should.')
    mail['Subject'] = subject
    mail['From'] = config.TEST_MAIL['sender']
    mail['To'] = config.TEST_MAIL['recipient']
    mail['Date'] = format_datetime(datetime.utcnow())
    with SMTP_SSL(config.SMTP['host'], config.SMTP['port']) as smtp:
        smtp_user = config.SMTP.get('user')
        smtp_password = config.SMTP.get('password')
        smtp_tls = config.SMTP.get('tls')
        if smtp_tls:
            smtp.starttls()
        if smtp_user and smtp_password:
            smtp.login(smtp_user, smtp_password)
        smtp.sendmail(config.TEST_MAIL['sender'],
                      config.TEST_MAIL['recipient'], mail.as_string())
    logging.info('sent test email with subject "%s"', subject)

def write_textfile(metrics: dict):
    with NamedTemporaryFile(mode='w', delete=False) as textfile:
        total_duration = metrics.pop('total_duration', None)
        if total_duration is not None:
            textfile.write(
                '# HELP probe_duration_seconds The total duration of the probe\n'
            )
            textfile.write('# TYPE probe_duration_seconds gauge\n')
            textfile.write(
                'probe_duration_seconds {}\n'.format(total_duration))

        send_duration = metrics.pop('send_time_seconds', None)
        if send_duration is not None:
            textfile.write(
                '# HELP probe_send_time_seconds The duration of sending the email\n'
            )
            textfile.write('# TYPE probe_send_time_seconds gauge\n')
            textfile.write(
                'probe_send_time_seconds {}\n'.format(send_duration))

        receive_duration = metrics.pop('receive_time_seconds', None)
        if receive_duration is not None:
            textfile.write(
                '# HELP probe_receive_time_seconds The duration of receiving the email '
                'from the IMAP mailbox\n')
            textfile.write('# TYPE probe_receive_time_seconds gauge\n')
            textfile.write(
                'probe_receive_time_seconds {}\n'.format(receive_duration))

        mail_timestamp = metrics.pop('mail_timestamp', None)
        if mail_timestamp is not None:
            textfile.write(
                '# HELP probe_mail_timestamp The timestamp of the email\n')
            textfile.write('# TYPE probe_mail_timestamp gauge\n')
            textfile.write('probe_mail_timestamp {}\n'.format(mail_timestamp))

        success = metrics.pop('success', None)
        if success is not None:
            textfile.write(
                '# HELP probe_success Whether the mail delivery was successful\n'
            )
            textfile.write('# TYPE probe_success gauge\n')
            textfile.write('probe_success {}\n'.format(int(success)))

        textfile.flush()
        os.fsync(textfile.fileno())
        file_name = textfile.name
    os.rename(file_name, config.TEXTFILE_PATH)

    if metrics:
        logging.warning('unhandled metrics remaining! %s', metrics)


def test_mail_delivery_subscription(redux):

    async def check_for_test_message(key: aiopubsub.Key, metrics: dict):
        state = check_delivery(metrics)
        if state['success'] == True:
            redux.dispatch_event(
                DispatchEvent(name="smm",
                              topic=["email", "received"],
                              payload=metrics))

    async def write_metrics_to_file(key: aiopubsub.Key, metrics: dict):
        write_textfile(metrics)

    def send_message_with_subject(key: aiopubsub.Key, payload: dict):
        start = datetime.now()
        payload['start'] = start
        before_send = datetime.now()
        payload['before_send'] = before_send
        print(payload)
        try:
            send_test_message(payload['subject'])
            after_send = datetime.now()
            send_time_seconds = (after_send - before_send).total_seconds()
            payload['after_send'] = after_send
            payload['send_time_seconds'] = send_time_seconds
            redux.dispatch_event(
                DispatchEvent(name="smm",
                              topic=["email", "sent"],
                              payload=payload))
        except Exception:
            logging.error('a failure occured: %s', traceback.format_exc())
            payload = {'success': False}

    send_email_reducer = Reducer(event=["*", "email", "send"],
                                 is_async=False,
                                 action=send_message_with_subject)

    check_email_reducer = Reducer(event=["*", "email", "sent"],
                                  action=check_for_test_message)

    write_file_reducer = Reducer(event=["*", "email", "received"],
                                 action=write_metrics_to_file)

    redux.combine_reducers(send_email_reducer, check_email_reducer,
                           write_file_reducer)
