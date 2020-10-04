import json
from datetime import datetime
from flask import Blueprint, request
from flask import jsonify, render_template, current_app

from flask_login import login_required
from honeyswarm.models import PepperJobs
from honeyswarm.saltapi import pepper_api

jobs = Blueprint('jobs', __name__, template_folder="templates")


@jobs.route('/')
@login_required
def jobs_list():
    return render_template("jobs.html")


@jobs.route('/paginate', methods=["POST"])
@login_required
def jobs_paginate():

    # Used to check for query strings
    # for k, v in request.form.items():
    #    print(k, v)

    draw = request.form.get("draw")
    start_offset = int(request.form.get("start"))
    per_page = int(request.form.get("length"))

    # Calculate the correct page number
    start_offset = start_offset + per_page
    start_page = int(start_offset / per_page)

    # print(start_offset, start_page, per_page)

    # Check for a column sort
    order_by = request.form.get("order[0][column]")
    order_direction = request.form.get("order[0][dir]")

    if order_direction == "asc":
        direction = "+"
    else:
        direction = "-"

    column = [
        "show_more",
        "hive_id",
        "job_type",
        "job_short",
        "created_at",
        "completed_at"
        ][int(order_by)]

    # Default sort
    if order_by == "0":
        order_string = "-created_at"
    else:
        order_string = "{0}{1}".format(direction, column)

    job_rows = PepperJobs.objects().order_by(
        order_string).paginate(
            page=start_page,
            per_page=per_page
        )
    job_count = job_rows.total

    # This should be how many matched a search. If no search then total rows
    filtered_records = job_count

    # Collect all the rows together
    data_rows = []
    for row in job_rows.items:
        try:
            single_row = {
                "DT_RowId": str(row.id),
                "hive_id": str(row.hive.name),
                "job_type": row.job_type,
                "job_short": row.job_short,
                "created_at": row.created_at,
                "completed_at": row.completed_at,
                "job_id": str(row.id)
            }

            data_rows.append(single_row)
        except Exception as err:
            error_message = "Error getting jobs: {0}".format(err)
            current_app.logger.error(error_message)
            print(error_message)
            continue

    # Final Json to return
    json_results = {
        "draw": draw,
        "recordsTotal": job_count,
        "recordsFiltered": filtered_records,
        "data": data_rows
    }

    return jsonify(json_results)


@jobs.route('/payload/<job_id>', methods=["POST"])
@login_required
def jobs_payload(job_id):
    single_job = PepperJobs.objects(id=job_id).first()

    json_response = {
        "valid": True,
        "payload": single_job.job_response
    }
    return jsonify(json_response)


@jobs.route('/poll')
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
