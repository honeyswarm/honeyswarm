from flask import Blueprint, render_template, request, abort
from flask_security import login_required
from honeyswarm.models import HoneypotEvents

default_report = Blueprint(
    'default_report',
    __name__,
    template_folder="templates"
    )


@default_report.route('/')
@login_required
def report_main():

    honeypot = request.args.get('honeypot')
    table_list = request.args.get('tables')
    limit = int(request.args.get('limit', 10))

    if not honeypot or not table_list:
        return abort(404)

    tables = table_list.split(',')

    # Some default tables
    tables.append("source_ip")

    base_pipeline = {"$facet": {
            "source_ip": [{"$group": {
                    "_id": {
                        "fieldname": "$source_ip"
                        },
                    "count": {"$sum": 1}
                }},
                {"$sort": {"count": -1}},
                {"$limit": limit}
            ]
    }
        }

    # ToDo: Possible Mongo Injection

    # We can not use . in the table name so to make it easier from the URL
    #  we just replace __ with .
    # So payload['http_post']['log'] would be http_post__log
    for table in tables:
        base_pipeline['$facet'][table] = [
                {"$group": {
                    "_id": {
                        "fieldname": "$payload.{0}".format(
                            table.replace('__', '.')
                            )
                    },
                    "count": {"$sum": 1}
                }},
                {"$sort": {"count": -1}},
                {"$limit": limit}
            ]

    counters = [x for x in HoneypotEvents.objects(
        honeypot_type=honeypot
        ).aggregate(base_pipeline)][0]

    # Get a list of fields we can filter on.
    # single_event = HoneypotEvents.objects(honeypot_type=honeypot).first()
    # this = json.loads(single_event.to_json())

    return render_template(
        "default_report.html",
        honeypot=honeypot,
        tables=tables,
        counters=counters
        )

# def pairs(d):
#     for k, v in d.items():
#         if isinstance(v, dict):
#             yield from pairs(v)
#         else:
#             yield k

# def getKeys(object, prev_key=None, keys=[]):
#     if type(object) != type({}):
#         keys.append(prev_key)
#         return keys
#     new_keys = []
#     for k, v in object.items():
#         if prev_key is not None:
#             new_key = "{}.{}".format(prev_key, k)
#         else:
#             new_key = k
#         new_keys.extend(getKeys(v, new_key, []))
#     return new_keys
