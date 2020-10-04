from datetime import datetime, timedelta
from flask import Blueprint, render_template, current_app
from flask_security import login_required
from honeyswarm.models import HoneypotEvents, HoneypotInstance, Hive

dashboard = Blueprint('dashboard', __name__, template_folder="templates")


def get_dashboard_data(days):
    today = datetime.utcnow()
    start_date = today - timedelta(days)
    service_pipeline = [
        {"$match": {
            "date": {"$gte": start_date, "$lte": today}
        }},
        {"$group": {
            "_id": "$service",
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}},
        {"$limit": 10},
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

    try:
        graph_data = [x for x in HoneypotEvents.objects().aggregate(
            *service_pipeline)][0]

    except Exception as err:
        current_app.logger.error("Error Creating Dashboard: {0}".format(err))
        graph_data = {}
    return graph_data


@dashboard.route('/')
@login_required
def main_dashboard():

    hive_count = Hive.objects.count()
    alive_hives = Hive.objects(salt_alive=True).count()
    event_count = HoneypotEvents.objects.count()
    instance_count = HoneypotInstance.objects.count()
    alive_instances = HoneypotInstance.objects(status="running").count()

    service_graph_day = get_dashboard_data(1)
    service_graph_week = get_dashboard_data(7)
    service_graph_month = get_dashboard_data(30)

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
        alive_hives=alive_hives,
        event_count=event_count,
        instance_count=instance_count,
        alive_instances=alive_instances,
        service_graphs=service_graphs
        )
