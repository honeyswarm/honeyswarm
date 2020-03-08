import os
import time
from uuid import uuid4
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, request, flash, abort, jsonify
from flask_security import login_required
from flask_security.core import current_user
from flask_security.decorators import roles_accepted
from honeyswarm.models import Hive, HoneypotEvents, Config


events = Blueprint('events', __name__)


@events.route('/events')
@login_required
def events_page():

    return render_template(
        "events.html"

        )



@events.route('/events/paginate', methods=["POST"])
@login_required
def event_stream():

    #for k, v in request.form.items():
    #    print(k,v)


    draw = request.form.get("draw")
    start_offset = int(request.form.get("start"))
    per_page = int(request.form.get("length"))

    # Calculate the correct page number
    start_offset = start_offset + per_page
    start_page = int(start_offset / per_page)
    
    #print(start_offset, start_page, per_page)

    events = HoneypotEvents.objects.paginate(page=start_page, per_page=per_page)
    event_count = events.total

    # This should be how many matched a search. If no search then total rows
    filtered_records = event_count


    # Collect all the rows together
    data_rows = []
    for event in events.items:
        try:
            single_row = [
                event["channel"],
                event["ident"],
                event["payload"]["sensor"]
            ]

            #print(event)
            data_rows.append(single_row)
        except:
            continue


    # Final Json to return
    json_results = {
        "draw": draw,
        "recordsTotal": event_count,
        "recordsFiltered": event_count,
        "data": data_rows
    }

    return jsonify(json_results)