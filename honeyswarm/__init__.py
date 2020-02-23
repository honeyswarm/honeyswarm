import atexit
import json
import os
import pytz
from datetime import datetime

import flaskcode
from flask import Flask, Blueprint, render_template, abort, request, g, jsonify, send_file, session, url_for, flash
from flask_mongoengine import MongoEngine
from werkzeug.middleware.proxy_fix import ProxyFix
from honeyswarm.models import User, Role, PepperJobs, Hive
from honeyswarm.saltapi import PepperApi
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler

from flask_security import Security, MongoEngineUserDatastore, auth_required, hash_password
from flask_security import login_required
from flask_security.core import current_user
from flask_security.decorators import roles_accepted
from flask_wtf.csrf import CSRFProtect


# Set the Core Application
app = Flask(__name__, static_folder='static', static_url_path='')
app.secret_key = 'MuhktUNBDthagZkY477ZWcXfM41x5dRuao8eEXZK'
app.config['SECURITY_PASSWORD_SALT'] = os.environ.get("SECURITY_PASSWORD_SALT", '146585145368132386173505678016728509634')
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1, x_proto=1)
TZ = pytz.timezone('Europe/London')
SALT_STATE_BASE = os.path.join(app.root_path, '../', 'honeystates', 'salt')

# Mongo next

# MongoEngine doesnt support AUTH_SOURCE so we manully construct
MONGODB_SETTINGS = {
    "host" : "mongodb://{0}:{1}@{2}:{3}/{4}?authSource={5}".format(
        os.environ.get("MONGODB_USERNAME"),
        os.environ.get("MONGODB_PASSWORD"),
        os.environ.get("MONGODB_HOST"),
        os.environ.get("MONGODB_PORT"),
        os.environ.get("MONGODB_DATABASE"),
        os.environ.get("MONGODB_AUTH_SOURCE")
    )
}


app.config['MONGODB_SETTINGS'] = MONGODB_SETTINGS



# Init the DB and the login managers
db = MongoEngine(app)

# Setup Flask-Security
user_datastore = MongoEngineUserDatastore(db, User, Role)
app.config['SECURITY_LOGIN_URL'] = '/nowhere'
app.config['SECURITY_LOGIN_USER_TEMPLATE'] = "login.html"
security = Security(app, user_datastore)

#CSRFProtect(app)

# Global App Scheduler
executors = dict(default=ThreadPoolExecutor())
app.scheduler = BackgroundScheduler(executors=executors, timezone='Europe/London')
app.scheduler.start()
atexit.register(app.scheduler.shutdown)

# Jobs Schedule

def check_jobs():
    # Get all PepperJobs not marked as complete
    print("checking PepperJobs")
    open_jobs = PepperJobs.objects(complete=False)
    for job in open_jobs:
        api_check = pepper_api.lookup_job(job.job_id)
        hive_id = str(job['hive']['id'])
        if api_check:
            job.complete = True
            job.job_response = json.dumps(api_check['data'][hive_id], sort_keys=True, indent=4)
            job.completed_at = datetime.utcnow
        job.save()

def poll_hives():
    print("Polling all registered hives")
    for hive in Hive.objects(registered=True):
        hive_id = str(hive.id)
        grains_request = pepper_api.run_client_function(hive_id, 'grains.items')
        hive_grains = grains_request[hive_id]
        if hive_grains:
            hive.grains = hive_grains
            hive.last_seen = datetime.utcnow
            hive.salt_alive = True
        else:
            hive.salt_alive = False
        hive.save()


app.scheduler.add_job(check_jobs,'interval', minutes=1,args=[])

# ToDo: Set sensible intervals
app.scheduler.add_job(poll_hives,'interval', minutes=10,args=[])



##
# Flask Code
##

app.config.from_object(flaskcode.default_config)
app.config['FLASKCODE_RESOURCE_BASEPATH'] = SALT_STATE_BASE
app.register_blueprint(flaskcode.blueprint, url_prefix='/flaskcode')


# Import the Blueprints after the app has loaded else we get import errors. 
from honeyswarm.saltapi import pepper_api
from honeyswarm.auth import auth
from honeyswarm.hives import hives
from honeyswarm.jobs import jobs
from honeyswarm.honeypots import honeypots
from honeyswarm.frames import frames

# Register the Blueprints
app.register_blueprint(auth)
app.register_blueprint(hives)
app.register_blueprint(jobs)
app.register_blueprint(honeypots)
app.register_blueprint(frames)



# Filters

@app.template_filter('dateformat')
def format_datetime(datetime_object):
    if isinstance(datetime_object, datetime):
        return datetime_object.replace(tzinfo=pytz.utc).astimezone(TZ).strftime('%d %b %Y %H:%M')
    else:
        return str()


@app.template_filter('prettyjson')
def format_prettyjson(json_string):

    pretty_json = json.dumps(json.loads(json_string), sort_keys=True,
                        indent=4, separators=(',', ': '))

    return pretty_json

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html', name='kev')