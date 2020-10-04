import json
import logging
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

        print(api_check)

        if job.job_type == "Docker State":
            # We need to parse the message as details are not in the API
            instance_id = job.job_description.split("id: ")[-1]
            if api_check:
                try:
                    container_state = api_check[hive_id]
                    job.complete = True
                    job.job_response = container_state
                    job.completed_at = datetime.utcnow
                    job.save()
                    instance = HoneypotInstance.objects(id=instance_id).first()
                    instance.status = container_state
                    instance.save()
                except Exception as err:
                    logger.error("API Response: {0}".format(err))

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
    for hive in Hive.objects():
        for instance in hive.honeypots:
            container_name = instance.honeypot.container_name
            status = pepper_api.docker_state(str(hive.id), container_name)
            instance.status = str(status)
            instance.save()
