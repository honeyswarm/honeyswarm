from flask import Blueprint, render_template, request, jsonify
from flask_security import login_required
from honeyswarm.models import HoneypotEvents

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
        "date",
        "source_ip",
        "service",
        "port",
        "honeypot_type",
        "honeypot_instance_id"
        ][int(order_by)]

    order_string = "{0}{1}".format(direction, column)

    events = HoneypotEvents.objects.order_by(order_string).paginate(
        page=start_page,
        per_page=per_page
        )
    event_count = events.total

    # This should be how many matched a search. If no search then total rows
    filtered_records = event_count

    # Collect all the rows together
    data_rows = []
    for event in events.items:
        try:
            single_row = [
                event["date"],
                event["source_ip"],
                event["service"],
                event["port"],
                event["honeypot_type"],
                event["honeypot_instance_id"]
            ]

            # print(event)
            data_rows.append(single_row)
        except Exception as err:
            print(err)
            continue

    # Final Json to return
    json_results = {
        "draw": draw,
        "recordsTotal": event_count,
        "recordsFiltered": filtered_records,
        "data": data_rows
    }

    return jsonify(json_results)
