import os
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
