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

    """
    # Post from Datatables Ajax
    draw 1
    columns[0][data] 0
    columns[0][name] 
    columns[0][searchable] true
    columns[0][orderable] true
    columns[0][search][value] 
    columns[0][search][regex] false
    columns[1][data] 1
    columns[1][name] 
    columns[1][searchable] true
    columns[1][orderable] true
    columns[1][search][value] 
    columns[1][search][regex] false
    columns[2][data] 2
    columns[2][name] 
    columns[2][searchable] true
    columns[2][orderable] true
    columns[2][search][value] 
    columns[2][search][regex] false
    columns[3][data] 3
    columns[3][name] 
    columns[3][searchable] true
    columns[3][orderable] true
    columns[3][search][value] 
    columns[3][search][regex] false
    columns[4][data] 4
    columns[4][name] 
    columns[4][searchable] true
    columns[4][orderable] true
    columns[4][search][value] 
    columns[4][search][regex] false
    order[0][column] 0
    order[0][dir] asc
    start 0
    length 10
    search[value] 
    search[regex] false
    """


    for k, v in request.form.items():
        print(k,v)


    start_page = int(request.form.get("start"))
    per_page = int(request.form.get("length"))
    draw = request.form.get("draw")

    print(start_page, per_page)

    events = HoneypotEvents.objects.paginate(page=1, per_page=per_page)
    current_page = events.page
    total_pages_for_query = events.pages
    item_per_page = events.per_page
    event_count = events.total
    list_of_items = events.items

    # This should be how many matched a search. If no search then total rows
    filtered_records = event_count

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



    json_results = {
        "draw": draw,
        "recordsTotal": event_count,
        "recordsFiltered": event_count,
        "data": data_rows
    }

    return jsonify(json_results)