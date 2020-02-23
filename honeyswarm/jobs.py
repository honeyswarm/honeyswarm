import os
import json
from uuid import uuid4
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, request, flash, abort, jsonify
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from honeyswarm.models import Hive, PepperJobs


jobs = Blueprint('jobs', __name__)

from honeyswarm.saltapi import pepper_api

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
            job.job_response = json.dumps(api_check['data'][hive_id], sort_keys=True, indent=4)
            job.completed_at = datetime.utcnow
        job.save()
        json_response['success'] = True
        json_response['job_complete'] = job.complete
    except Exception as err:
        json_response['message'] = err

    return jsonify(json_response)