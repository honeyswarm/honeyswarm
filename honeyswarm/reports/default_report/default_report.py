from honeyswarm.saltapi import pepper_api

from datetime import datetime

from flask import Blueprint, render_template, request, abort, jsonify
from flask_security import login_required
from honeyswarm.models import HoneypotEvents, Config

default_report = Blueprint('default_report', __name__, template_folder="templates")

@default_report.route('/')
@login_required
def report_main():

    honeypot = request.args.get('honeypot')
    table_list = request.args.get('tables')
    limit = int(request.args.get('limit', 10))

    if not honeypot or not table_list:
        return abort(404)

    tables = table_list.split(',')

    base_pipeline = {"$facet": {}
        }

    # ToDo: Possible Mongo Injection
    for table in tables:
        table_name = table
        base_pipeline['$facet'][table_name] = [
                {"$group": {
            "_id": {
                "fieldname": "$payload.{0}".format(table.replace('__', '.'))
                },
            "count": {"$sum":1}
                }},
                {"$sort": {"count": -1}},
                {"$limit": limit}
            ]

    counters = [x for x in HoneypotEvents.objects(honeypot_type=honeypot).aggregate(base_pipeline)][0]

    return render_template(
        "default_report.html",
        honeypot=honeypot,
        tables=tables,
        counters=counters
        )