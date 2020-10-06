import json
import sys
import struct
import string
import logging
from io import BytesIO
from binascii import unhexlify
from datetime import datetime
from honeyswarm.saltapi import pepper_api
from honeyswarm.models import PepperJobs, HoneypotInstance, Hive

logger = logging.getLogger(__name__)


def check_jobs():
    # Get all PepperJobs not marked as complete
    open_jobs = PepperJobs.objects(complete=False)
    for job in open_jobs:

        hive_id = str(job['hive']['id'])
        api_check = pepper_api.lookup_job(job.job_id)

        if job.job_type == "Docker State":
            # We need to parse the message as details are not in the API
            instance_id = job.job_description.split("id: ")[-1]
            if api_check:
                try:
                    api_response = api_check[hive_id]
                    if 'state' in api_response:
                        container_state = api_response['state']['new']
                    else:
                        container_state = api_response

                    job.complete = True
                    job.job_response = container_state
                    job.completed_at = datetime.utcnow
                    job.save()
                    instance = HoneypotInstance.objects(id=instance_id).first()
                    instance.status = container_state
                    instance.save()
                except Exception as err:
                    logger.error("Salt Error: {0} {1}".format(err, api_check))

        else:
            hive_id = str(job['hive']['id'])
            if api_check:
                job.complete = True
                job.job_response = json.dumps(
                    api_check['data'][hive_id],
                    sort_keys=True,
                    indent=4
                    )
                job.completed_at = datetime.utcnow
            job.save()


def poll_hives():
    for hive in Hive.objects(registered=True):
        hive_id = str(hive.id)
        grains_request = pepper_api.run_client_function(
            hive_id,
            'grains.items'
            )

        external_ip_request = pepper_api.run_client_function(
            hive_id,
            'cmd.run',
            'wget -qO- http://ipecho.net/plain'
        )
        external_ip = external_ip_request[hive_id]

        hive_grains = grains_request[hive_id]

        if hive_grains:
            hive_grains['external_ip'] = external_ip
            hive.grains = hive_grains
            hive.last_seen = datetime.utcnow
            hive.salt_alive = True
        else:
            hive.salt_alive = False
        hive.save()


def poll_instances():
    """
    This sets up an async salt call that is saved as a job per instance.
    """
    for instance in HoneypotInstance.objects():
        try:
            hive = instance.hive
            if hive.salt_alive:
                container_name = instance.honeypot.container_name
                pepper_job_id = pepper_api.docker_state(
                    str(hive.id),
                    container_name
                )

                job = PepperJobs(
                    hive=hive,
                    job_type="Docker State",
                    job_id=pepper_job_id,
                    job_short="Scheduled Docker State on {0}".format(
                        container_name
                        ),
                    job_description="Scheduled task to check Docker state for honeypot \
                        {0} on hive {1} with instance id: {2}".format(
                            container_name,
                            hive.name,
                            instance.id
                            )
                        )
                job.save()
            else:
                instance.status = "Unresponsive Hive"
                instance.save()
        except Exception as err:
            error_message = "Error Checking Container State: {0}".format(err)
            logger.error(error_message)
            instance.status = error_message
            instance.save()

 
# This is a modified version of the asciienam encoder from cowrie
# Origianal can be found at https://github.com/micheloosterhof/cowrie/blob/master/bin/asciinema
def asciinema_converter(tty_hex):
    tty_stream = unhexlify(tty_hex)
    fd = BytesIO(tty_stream)
    OP_OPEN, OP_CLOSE, OP_WRITE, OP_EXEC = 1, 2, 3, 4
    TYPE_INPUT, TYPE_OUTPUT, TYPE_INTERACT = 1, 2, 3

    COLOR_INTERACT = '\033[36m'
    COLOR_INPUT = '\033[33m'
    COLOR_RESET = '\033[0m'

    settings = {
        'colorify': True,
        'output': ""
    }

    thelog = {}
    thelog['version'] = 1
    thelog['width'] = 80
    thelog['height'] = 24
    thelog['duration'] = 0.0
    thelog['command'] = "/bin/bash"
    thelog['title'] = "Cowrie Recording"
    theenv = {}
    theenv['TERM'] = "xterm256-color"
    theenv['SHELL'] = "/bin/bash"
    thelog["env"] = theenv
    stdout = []
    thelog["stdout"] = stdout

    ssize = struct.calcsize('<iLiiLL')

    currtty, prevtime, prefdir = 0, 0, 0
    sleeptime = 0.0

    color = None

    while 1:
        try:
            (op, tty, length, dir, sec, usec) = \
                struct.unpack('<iLiiLL', fd.read(ssize))
            data = fd.read(length)
        except struct.error:
            break

        if currtty == 0: currtty = tty

        if str(tty) == str(currtty) and op == OP_WRITE:
            # the first stream seen is considered 'output'
            if prefdir == 0:
                prefdir = dir
            if dir == TYPE_INTERACT:
                color = COLOR_INTERACT
            elif dir == TYPE_INPUT:
                color = COLOR_INPUT
            if dir == prefdir:
                curtime = float(sec) + float(usec) / 1000000
                if prevtime != 0:
                    sleeptime = curtime - prevtime
                prevtime = curtime
                if settings['colorify'] and color:
                    sys.stdout.write(color)

                # Handle Unicode
                try:
                    data = data.decode('unicode-escape')
                except:
                    for char in data:
                        if char not in string.printable:
                            data.replace(char, '.')

                # rtrox: While playback works properly
                #        with the asciinema client, upload
                #        causes mangling of the data due to
                #        newlines being misinterpreted without
                #        carriage returns.
                data = data.replace("\n", "\r\n")

                thedata = [sleeptime, data]
                thelog['duration'] = curtime
                stdout.append(thedata)

                if settings['colorify'] and color:
                    sys.stdout.write(COLOR_RESET)
                    color = None

        elif str(tty) == str(currtty) and op == OP_CLOSE:
            break

    return json.dumps(thelog, indent=4, ensure_ascii=True)
    