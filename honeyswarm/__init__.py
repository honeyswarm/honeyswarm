import atexit
import json
import os
import pytz
import importlib
from datetime import datetime

import flaskcode
from datetime import timedelta
from flask import Flask, render_template, url_for, redirect
from werkzeug.middleware.proxy_fix import ProxyFix
from honeyswarm.models import db, User, Role, PepperJobs, Hive
from honeyswarm.saltapi import pepper_api
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler

import mongoengine
from flask_security import Security, MongoEngineUserDatastore

from honeyswarm.admin import admin
from honeyswarm.installer import installer
from honeyswarm.auth import auth
from honeyswarm.hives import hives
from honeyswarm.jobs import jobs
from honeyswarm.honeypots import honeypots
from honeyswarm.frames import frames
from honeyswarm.events import events
from honeyswarm.dashboard import dashboard


app = Flask(__name__, static_folder='static', static_url_path='')
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1, x_proto=1)


def setup_config():
    app.config['installed'] = False
    app.secret_key = os.environ.get(
        'SESSION_SECRET', 'MuhktUNBDthagZkY477ZWcXfM41x5dRuao8eEXZK'
        )
    app.config['SECURITY_PASSWORD_SALT'] = os.environ.get(
        "SECURITY_PASSWORD_SALT", '146585145368132386173505678016728509634'
        )
    app.config['SALT_BASE'] = os.path.join(
        app.root_path,
        '../',
        'honeystates',
        'salt'
        )
    app.config['SECURITY_LOGIN_URL'] = '/nowhere'
    app.config['SECURITY_LOGIN_USER_TEMPLATE'] = "login.html"
    app.config['SECURITY_CONFIRMABLE'] = True
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)

    app.config['TIMEZONE'] = os.environ.get("TIMEZONE")

    # Flask code
    app.config.from_object(flaskcode.default_config)
    app.config['FLASKCODE_RESOURCE_BASEPATH'] = app.config['SALT_BASE']


def setup_blueprints():
    app.register_blueprint(admin.admin, url_prefix="/admin")
    app.register_blueprint(auth.auth, url_prefix="/auth")
    app.register_blueprint(hives.hives, url_prefix="/hives")
    app.register_blueprint(jobs.jobs, url_prefix="/jobs")
    app.register_blueprint(honeypots.honeypots, url_prefix="/honeypots")
    app.register_blueprint(frames.frames, url_prefix="/frames")
    app.register_blueprint(events.events, url_prefix="/events")
    app.register_blueprint(dashboard.dashboard, url_prefix="/dashboard")
    app.register_blueprint(flaskcode.blueprint, url_prefix='/flaskcode')

    # Dynamically register all reports.
    report_path = os.path.join(app.root_path, 'reports')
    REPORTS = []

    for report_blueprint in os.listdir(report_path):
        if os.path.isdir(
                os.path.join(report_path, report_blueprint)
                ) and not report_blueprint.startswith('__'):
            REPORTS.append({
                'path': '.reports.{0}.{0}'.format(report_blueprint),
                'blueprint': report_blueprint
            })

    for report in REPORTS:
        try:
            module = importlib.import_module(
                report['path'],
                package="honeyswarm"
                )
            app.register_blueprint(
                getattr(module, report['blueprint']),
                url_prefix="/report/{0}".format(report['blueprint'])
                )
        except Exception as err:
            error_message = "Erorr loading report blueprint{0}: {1}".format(
                report['blueprint'], err
                )
            app.logger.error(error_message)


def setup_mongo():
    # MongoEngine doesnt support AUTH_SOURCE so we manully construct
    MONGODB_SETTINGS = [{
        "host": "mongodb://{0}:{1}@{2}:{3}/{4}?authSource={5}".format(
            os.environ.get("MONGODB_USERNAME"),
            os.environ.get("MONGODB_PASSWORD"),
            os.environ.get("MONGODB_HOST"),
            os.environ.get("MONGODB_PORT"),
            os.environ.get("MONGODB_DATABASE"),
            os.environ.get("MONGODB_AUTH_SOURCE")
        ),
        "alias": mongoengine.DEFAULT_CONNECTION_NAME
    }, {
        "host": "mongodb://{0}:{1}@{2}:{3}/{4}?authSource={5}".format(
            os.environ.get("MONGODB_USERNAME"),
            os.environ.get("MONGODB_PASSWORD"),
            os.environ.get("MONGODB_HOST"),
            os.environ.get("MONGODB_PORT"),
            "hpfeeds",
            os.environ.get("MONGODB_AUTH_SOURCE")
        ),
        "alias": "hpfeeds_db"
    }
    ]

    app.config['MONGODB_SETTINGS'] = MONGODB_SETTINGS
    db.init_app(app)


def setup_scheduler():
    # Global App Scheduler
    executors = dict(default=ThreadPoolExecutor())
    app.scheduler = BackgroundScheduler(
        executors=executors, timezone=app.config['TIMEZONE']
        )
    app.scheduler.start()
    atexit.register(app.scheduler.shutdown)

    # ToDo: Set sensible intervals
    app.scheduler.add_job(check_jobs, 'interval', minutes=1, args=[])
    app.scheduler.add_job(poll_instances, 'interval', minutes=30, args=[])
    app.scheduler.add_job(poll_hives, 'interval', minutes=60, args=[])


def setup_installation():
    # Only show installer pages if we have no users
    try:
        user_count = User.objects.count()
        if user_count > 0:
            app.config['installed'] = True
        else:
            app.register_blueprint(installer.installer, url_prefix="/install")
    except Exception as err:
        app.logger.error(err)


# Jobs Schedule
def check_jobs():
    # Get all PepperJobs not marked as complete
    open_jobs = PepperJobs.objects(complete=False)
    for job in open_jobs:
        api_check = pepper_api.lookup_job(job.job_id)
        hive_id = str(job['hive']['id'])
        if api_check:
            job.complete = True
            job.job_response = json.dumps(
                api_check['data'][hive_id],
                sort_keys=True,
                indent=4
                )
            job.completed_at = datetime.utcnow
        job.save()


def poll_hives():
    for hive in Hive.objects(registered=True):
        hive_id = str(hive.id)
        grains_request = pepper_api.run_client_function(
            hive_id,
            'grains.items'
            )
        hive_grains = grains_request[hive_id]
        if hive_grains:
            hive.grains = hive_grains
            hive.last_seen = datetime.utcnow
            hive.salt_alive = True
        else:
            hive.salt_alive = False
        hive.save()


def poll_instances():
    for hive in Hive.objects():
        for instance in hive.honeypots:
            container_name = instance.honeypot.container_name
            status = pepper_api.docker_state(str(hive.id), container_name)
            instance.status = str(status)
            instance.save()


# Filters
@app.template_filter('dateformat')
def format_datetime(datetime_object):
    if isinstance(datetime_object, datetime):
        timezone = pytz.timezone(app.config['TIMEZONE'])
        return datetime_object.replace(
            tzinfo=pytz.utc
            ).astimezone(timezone).strftime('%d %b %Y %H:%M')
    else:
        return str()


@app.template_filter('prettyjson')
def format_prettyjson(json_string):
    pretty_json = json.dumps(
        json.loads(json_string),
        sort_keys=True,
        indent=4,
        separators=(',', ': ')
        )
    return pretty_json


@app.template_filter('userroles')
def format_userroles(userroles):
    return [x.name for x in userroles]


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.route('/')
def index():
    if not app.config['installed']:
        return redirect(url_for('installer.base_install'))
    return render_template('index.html')


setup_config()
setup_mongo()
setup_blueprints()
setup_installation()
setup_scheduler()

user_datastore = MongoEngineUserDatastore(db, User, Role)
security = Security(app, user_datastore)
