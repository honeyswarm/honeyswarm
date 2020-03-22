import json
from datetime import datetime
from flask import Blueprint, request
from flask import jsonify, render_template

from flask_login import login_required
from honeyswarm.models import PepperJobs
from honeyswarm.saltapi import pepper_api

jobs = Blueprint('jobs', __name__)


@jobs.route('/jobs')
@login_required
def jobs_list():

    # shoudl probably add a filter in here this could get noisy
    job_list = PepperJobs.objects

    # Probably want a way to update / delete a job

    return render_template(
        "jobs.html",
        job_list=job_list
        )


@jobs.route('/jobs/poll')
@login_required
def jobs_poll():

    json_response = {"success": False, "job_complete": False}

    try:
        job_id = request.forms.get('job_id')
        job = PepperJobs.objects(id=job_id)

        api_check = pepper_api.lookup_job(job.job_id)
        hive_id = str(job['hive']['id'])
        if api_check:
            job.complete = True
            job.job_response = json.dumps(
                api_check['data'][hive_id],
                sort_keys=True, indent=4)
            job.completed_at = datetime.utcnow
        job.save()
        json_response['success'] = True
        json_response['job_complete'] = job.complete
    except Exception as err:
        json_response['message'] = err

    return jsonify(json_response)
