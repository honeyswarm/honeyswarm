# This should only run at first time setup
import os
import json
import logging
from secrets import token_hex
from io import BytesIO
from zipfile import ZipFile
from urllib.request import urlopen
from flask import current_app
from flask import Blueprint, render_template, redirect, url_for, request, flash

from honeyswarm.models import db, User, Role, Frame, Honeypot, AuthKey, Config
from flask_security.utils import encrypt_password
from flask_security import MongoEngineUserDatastore


logger = logging.getLogger(__name__)
installer = Blueprint('installer', __name__, template_folder="templates")

user_datastore = MongoEngineUserDatastore(db, User, Role)


def install_states(state_base):
    resp = urlopen(
        "https://github.com/honeyswarm/honeyswarm_states/archive/master.zip"
        )
    zipfile = ZipFile(BytesIO(resp.read()))

    frame_path = os.path.join(state_base, "frames")
    honeypot_path = os.path.join(state_base, "honeypots")

    # Extract all the states to the correct place
    for zip_info in zipfile.infolist():
        try:
            if zip_info.filename[-1] == '/' or zip_info.filename == '':
                continue

            if zip_info.filename == 'honeyswarm_states-master/top.sls':
                zip_info.filename = zip_info.filename.replace(
                    'honeyswarm_states-master/', '')
                zipfile.extract(zip_info, state_base)

            if zip_info.filename.startswith(
                    'honeyswarm_states-master/frames/'):
                zip_info.filename = zip_info.filename.replace(
                    'honeyswarm_states-master/frames/', '')
                zipfile.extract(zip_info, frame_path)

            if zip_info.filename.startswith(
                    'honeyswarm_states-master/honeypots/'):
                zip_info.filename = zip_info.filename.replace(
                    'honeyswarm_states-master/honeypots/', '')
                zipfile.extract(zip_info, honeypot_path)

        except Exception as err:
            logger.error("Error Installing Statest: {0}".format(err))


@installer.route('/', methods=["GET", "POST"])
def base_install():

    if request.method == "GET":

        # Do we already have an active installation and need a reboot?
        try:
            user_count = User.objects.count()
            if user_count > 0:
                reboot = True
            else:
                reboot = False
        except Exception as err:
            logger.error(err)
            reboot = False

        if reboot:
            flash('Honeyswarm has been installed. \
                   You need to stop / start the docker-compose \
                   to complete the installation')
            return redirect(url_for('installer.base_install'))

        token1 = token_hex(16)
        token2 = token_hex(16)
        return render_template(
            "install.html",
            token1=token1,
            token2=token2
            )

    # Assuming we are at post now.

    # Create user groups
    try:
        user_datastore.create_role(name="admin", description="Admin Role")
        user_datastore.create_role(
            name="user",
            description="Generic User accounts"
            )
        user_datastore.create_role(
            name="editor",
            description="Can create and edit frames and honeypots"
            )
        user_datastore.create_role(
            name="deploy",
            description="Can deploy honeypots and frames"
            )
    except Exception as err:
        flash('Error creating roles: {0}'.format(err))
        return redirect(url_for('installer.base_install'))

    # Create admin account from submitted details.
    try:
        user_email = request.form.get('adminEmail')
        user_pass = request.form.get('adminPassword1')
        user_name = request.form.get('adminName')
        if user_email and user_pass:
            new_admin = user_datastore.create_user(
                email=user_email,
                password=encrypt_password(user_pass),
                name=user_name,
                active=True
                )
        else:
            flash('No details provided')
            return redirect(url_for('installer.base_install'))

        admin_role = user_datastore.find_role('admin')
        user_datastore.add_role_to_user(new_admin, admin_role)

    except Exception as err:
        flash('Error creating admin user: {0}'.format(err))
        return redirect(url_for('installer.base_install'))

    # Create Master HPFeeds for the broker
    hpfeeds_subscriber = AuthKey(
        identifier="honeyswarm",
        secret=request.form.get('brokerSecret'),
        publish=[],
        subscribe=[]
    )

    # A Small Config
    configs = Config.objects
    if len(configs) > 0:
        master_config = Config.objects.first()
    else:
        master_config = Config()

    master_config.honeyswarm_host = request.form.get('honeyHost')
    master_config.broker_host = request.form.get("brokerHost")
    master_config.honeyswarm_api = request.form.get("honeyAPI")

    master_config.save()

    # Fetch and write all the states to the correct path
    try:
        install_states(current_app.config['SALT_BASE'])
    except Exception as err:
        flash('Error installing base states: {0}'.format(err))
        return redirect(url_for('installer.base_install'))

    # Add Frames
    try:
        frame_path = os.path.join(current_app.config['SALT_BASE'], 'frames')
        for frame in os.listdir(frame_path):
            state_config_file = os.path.join(frame_path, frame, "state.json")
            with open(state_config_file) as json_file:
                state_config = json.load(json_file)
                new_frame = Frame(**state_config)
                new_frame.save()
                frame_id = str(new_frame.id)
            os.rename(
                os.path.join(frame_path, frame),
                os.path.join(frame_path, frame_id)
                )
    except Exception as err:
        flash('Error creating frames: {0}'.format(err))
        return redirect(url_for('installer.base_install'))

    # Add honeypots
    try:
        honeypot_path = os.path.join(current_app.config['SALT_BASE'], 'honeypots')
        for honeypot in os.listdir(honeypot_path):
            state_config_file = os.path.join(
                honeypot_path,
                honeypot,
                "state.json"
                )
            with open(state_config_file) as json_file:
                state_config = json.load(json_file)
                new_honeypot = Honeypot(**state_config)
                new_honeypot.save()
                honeypot_id = str(new_honeypot.id)
                channels = state_config['channels']
            os.rename(
                os.path.join(honeypot_path, honeypot),
                os.path.join(honeypot_path, honeypot_id)
                )
            for channel in channels:
                hpfeeds_subscriber.subscribe.append(channel)

            new_honeypot.save()

    except Exception as err:
        flash('Error creating honeypots: {0}'.format(err))
        return redirect(url_for('installer.base_install'))

    # The master subscriber should now have all our channels so save it
    hpfeeds_subscriber.save()
    return redirect(url_for('index'))
