import os
import pytz
from datetime import datetime

from flask import Flask, Blueprint, render_template, abort, request, g, jsonify, send_file, session, url_for, flash
from flask_mongoengine import MongoEngine
from flask_login import LoginManager
from flask_login import login_required, current_user
from werkzeug.middleware.proxy_fix import ProxyFix
from honeyswarm.models import User
from honeyswarm.saltapi import PepperApi

# Import the Blueprints
from honeyswarm.auth import auth
from honeyswarm.hives import hives

# Set the Core Application
app = Flask(__name__, static_folder='static', static_url_path='')
app.secret_key = 'MuhktUNBDthagZkY477ZWcXfM41x5dRuao8eEXZK'
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1, x_proto=1)
TZ = pytz.timezone('Europe/London')

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

# Register the Blueprints
app.register_blueprint(auth)
app.register_blueprint(hives)

# Init the DB and the login managers
db = MongoEngine(app)

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)


pepper_api = PepperApi(app)

@login_manager.user_loader
def load_user(user_id):
    return User.objects(id=user_id).first()


# Routes

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', name=current_user.name)

# Filters

@app.template_filter('dateformat')
def format_datetime(datetime_object):
    if isinstance(datetime_object, datetime):
        return datetime_object.replace(tzinfo=pytz.utc).astimezone(TZ).strftime('%d %b %Y %H:%M')
    else:
        return str()