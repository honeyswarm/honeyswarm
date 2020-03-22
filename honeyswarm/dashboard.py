import json
from flask import Blueprint, render_template
from flask_security import login_required
from honeyswarm.models import HoneypotEvents, Honeypot, HoneypotInstance, Hive

dashboard = Blueprint('dashboard', __name__)


@dashboard.route('/dashboard')
@login_required
def main_dashboard():
    hive_count = Hive.objects.count()
    event_count = HoneypotEvents.objects.count()
    instance_count = HoneypotInstance.objects.count()
    service_pipeline = [
        {"$group": {
            "_id": "$service",
            "count": {"$sum": 1}
        }},
        {"$group": {
            "_id": 0,
            "counts": {
                "$push": {"k": "$_id", "v": "$count"}
        }
        }},
        {"$replaceRoot": {
            "newRoot": {"$arrayToObject": "$counts"}
        }}
    ]

    service_graph_day = [x for x in HoneypotEvents.objects().aggregate(
        *service_pipeline)][0]
    service_graph_week = [x for x in HoneypotEvents.objects().aggregate(
        *service_pipeline)][0]
    service_graph_month = [x for x in HoneypotEvents.objects().aggregate(
        *service_pipeline)][0]

    service_graphs = {
        "serviceDay": [
            list(service_graph_day.keys()),
            list(service_graph_day.values())
            ],
        "serviceWeek": [
            list(service_graph_week.keys()),
            list(service_graph_week.values())
            ],
        "serviceMonth": [
            list(service_graph_month.keys()),
            list(service_graph_month.values())
            ]
    }

    return render_template(
        'dashboard.html',
        hive_count=hive_count,
        event_count=event_count,
        instance_count=instance_count,
        service_graphs=service_graphs
        )
