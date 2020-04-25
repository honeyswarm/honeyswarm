import os

import mimetypes
from flask import Blueprint, redirect, url_for, request, abort
from flask import render_template, jsonify, send_file
from flask_login import login_required
from honeyswarm.models import Hive, PepperJobs, Honeypot, AuthKey, Config, HoneypotInstance
from flaskcode.utils import write_file, dir_tree, get_file_extension
from honeyswarm.saltapi import pepper_api
from honeyswarm import SALT_STATE_BASE

honeypots = Blueprint('honeypots', __name__)


@honeypots.route('/honeypots')
@login_required
def honeypot_list():

    # List of Availiable HoneyPots
    honey_list = Honeypot.objects

    # Installed Honeypots

    return render_template(
        "honeypots.html",
        honey_list=honey_list
        )


@honeypots.route('/honeypots/create/', methods=['POST'])
@login_required
def create_honeypot():

    json_response = {"success": False}

    try:
        new_honeypot = Honeypot()
        new_honeypot.name = request.form.get('honeypot_name')
        new_honeypot.honey_type = request.form.get('honeypot_type')
        new_honeypot.description = request.form.get('honeypot_description')
        new_honeypot.channels = request.form.get('honeypot_channels').split('/r/n')
        new_honeypot.honeypot_state_file = request.form.get(
            'honeypot_state_file'
            )

        # We need to save here to get the ID then carry on updating
        new_honeypot.save()
        honeypot_id = new_honeypot.id

        # Add a default state file so that we have something to edit.
        state_path = os.path.join(
            SALT_STATE_BASE, 'honeypots', str(honeypot_id)
            )
        state_name = "{0}.sls".format(new_honeypot.honeypot_state_file)
        state_file_path = os.path.join(state_path, state_name)
        if not os.path.exists(state_path):
            os.mkdir(state_path)
            os.mknod(state_file_path)
            os.chmod(state_file_path, 0o777)

        # Add all channels to the master subscriber
        channel_list = request.form.get('honeypot_channels').split('/r/n')

        sub_key = AuthKey.objects(identifier="honeyswarm").first()
        for channel in channel_list:
            if channel not in sub_key.subscribe:
                sub_key.subscribe.append(channel)
        sub_key.save()

        json_response['success'] = True
        json_response['message'] = "Honypot Created"

    except Exception as err:
        json_response['message'] = err
        print(err)

    return redirect(url_for('honeypots.honeypot_list'))



@honeypots.route('/honeypots/<honeypot_id>/edit/')
@login_required
def show_honeypot(honeypot_id):
    print(honeypot_id)
    honeypot_details = Honeypot.objects(id=honeypot_id).first()

    if not honeypot_details:
        abort(404)
    honeypotname = honeypot_details.name
    # Lets hack in flask code.
    honey_salt_base = os.path.join(SALT_STATE_BASE, 'honeypots', honeypot_id)

    dirname = os.path.basename(honey_salt_base)
    dtree = dir_tree(honey_salt_base, honey_salt_base + '/')

    # I want to rebuild the tree slightlt differently.
    new_tree = dict(
        name=os.path.basename(honey_salt_base),
        path_name='',
        children=[{
            'name': honeypot_id,
            'path_name': honeypot_id,
            'children': dtree['children']
        }]
    )

    return render_template(
        'flaskcode/honeypot_editor.html',
        honeypot_details=honeypot_details,
        dirname=dirname,
        dtree=new_tree,
        editor_theme="vs-dark",
        honeypot_id=honeypot_id,
        object_id=honeypot_id,
        data_url="honeypots"
        )


@honeypots.route('/honeypots/<honeypot_id>/update/', methods=['POST'])
@login_required
def update_honeypot(honeypot_id):
    honeypot_details = Honeypot.objects(id=honeypot_id).first()

    if not honeypot_details:
        abort(404)

    form_vars = request.form.to_dict()
    json_response = {"success": False}

    honeypot_details.name = request.form.get('honeypot_name')
    honeypot_details.honeypot_type = request.form.get('honeypot_type')
    honeypot_details.description = request.form.get('honeypot_description')
    honeypot_details.channels = request.form.get('honeypot_channels').split('/r/n')
    honeypot_details.honeypot_state_file = request.form.get(
        'honeypot_state_file'
        )

    # Now add any Pillar States
    pillar_states = []
    for field in form_vars.items():
        if field[0].startswith('pillar-key'):
            key_id = field[0].split('-')[-1]
            key_name = field[1]
            key_value = request.form.get("pillar-value-{0}".format(key_id))
            if key_name == '' or key_value == '':
                continue
            pillar_pair = [key_name, key_value]
            pillar_states.append(pillar_pair)

    honeypot_details.pillar = pillar_states

    # Update HoneySwarm HP Master Subscriber
    channel_list = request.form.get('honeypot_channels').split('\r\n')

    honeyswarm_subscriber = AuthKey.objects(identifier="honeyswarm").first()

    if honeyswarm_subscriber:
        for channel in channel_list:
            if channel not in honeyswarm_subscriber.subscribe:
                honeyswarm_subscriber.subscribe.append(channel)
        honeyswarm_subscriber.save()

    honeypot_details.save()
    json_response['success'] = True

    return jsonify(json_response)


@honeypots.route(
    '/honeypots/<object_id>/resource-data/<path:file_path>.txt',
    methods=['GET', 'HEAD']
    )
@login_required
def resource_data(object_id, file_path):
    print("Read Resource", file_path)

    honey_salt_base = os.path.join(SALT_STATE_BASE, 'honeypots', object_id)

    file_path = os.path.join(honey_salt_base, file_path)
    if not (os.path.exists(file_path) and os.path.isfile(file_path)):
        abort(404)
    response = send_file(file_path, mimetype='text/plain', cache_timeout=0)
    mimetype, encoding = mimetypes.guess_type(file_path, False)
    if mimetype:
        response.headers.set('X-File-Mimetype', mimetype)
        extension = mimetypes.guess_extension(
            mimetype, False) or get_file_extension(file_path)
        if extension:
            response.headers.set(
                'X-File-Extension', extension.lower().lstrip('.'))
    if encoding:
        response.headers.set('X-File-Encoding', encoding)
    return response


@honeypots.route(
    '/honeypots/<object_id>/update-resource-data/<path:file_path>',
    methods=['POST']
    )
@login_required
def update_resource_data(object_id, file_path):
    honey_salt_base = os.path.join(
        SALT_STATE_BASE, 'honeypots', object_id
        )
    file_path = os.path.join(honey_salt_base, file_path)
    is_new_resource = bool(int(request.form.get('is_new_resource', 0)))

    if not is_new_resource and not (
            os.path.exists(file_path) and os.path.isfile(file_path)):
        abort(404)
    success = True
    message = 'File saved successfully'
    resource_data = request.form.get('resource_data', None)
    if resource_data:
        success, message = write_file(resource_data, file_path)
    else:
        success = False
        message = 'File data not uploaded'
    return jsonify({'success': success, 'message': message})


@honeypots.route('/honeypots/<honeypot_id>/deployments/', methods=['GET'])
@login_required
def honeypot_deployments(honeypot_id):
    honeypot_details = Honeypot.objects(id=honeypot_id).first()

    if not honeypot_details:
        abort(404)

    # Get a list of all hives that have a frame installed
    # and are responding to polls.
    # ToDo: Only permit based on frame supported OS?
    # Do we need to add Frames as a Reference Field to Honeypot?

    all_hives = Hive.objects(frame__exists=True, salt_alive=True)
    existing_honeypots = []
    for hive in all_hives:
        for honeypot in hive.honeypots:
            if str(honeypot.id) == honeypot_id:
                existing_honeypots.append(hive)

    # Get all currently installed honypts of this type
    return render_template(
        "honey_deployments.html",
        all_hives=all_hives,
        existing_honeypots=existing_honeypots,
        honeypot_details=honeypot_details
        )


@honeypots.route('/honeypots/<honeypot_id>/deploy/', methods=['POST'])
@login_required
def honeypot_deploy(honeypot_id):
    form_vars = request.form.to_dict()
    json_response = {"success": False}

    honeypot_details = Honeypot.objects(id=honeypot_id).first()

    if not honeypot_details:
        json_response['message'] = "Can not find honeypot"
        return jsonify(json_response)

    hive_id = request.form.get('target_hive')

    hive = Hive.objects(id=hive_id).first()
    if not hive:
        json_response['message'] = "Can not find Hive"
        return jsonify(json_response)

    # Does this hive have the correct frame installed
    if not hive.frame:
        json_response['message'] = "Can not find Hive"
        return jsonify(json_response)

    # Do we already have an instance of this honeypot type on this hive?#
    # Get it and its auth_key
    honeypot_instance = None
    for instance in hive.honeypots:
        if instance.honeypot == honeypot_details:
            honeypot_instance = instance
            auth_key = AuthKey.objects(identifier=str(honeypot_instance.id))

    # Else we create an instance and a new auth_key
    if not honeypot_instance:

        # Create honeypot instance
        honeypot_instance = HoneypotInstance(
            honeypot=honeypot_details
        )

        honeypot_instance.save()
        instance_id = str(honeypot_instance.id)

        # Create an AuthKey
        auth_key = AuthKey(
            identifier=instance_id,
            secret=instance_id,
            publish=honeypot_details.channels
        )
        auth_key.save()

    instance_id = str(honeypot_instance.id)

    # Now add any Pillar States
    base_config = Config.objects.first()
    config_pillar = {
        "HIVEID": hive_id,
        "HONEYPOTID": honeypot_id,
        "INSTANCEID": instance_id,
        "HPFIDENT": instance_id,
        "HPFSECRET": instance_id,
        "HPFPORT": 10000,
        "HPFSERVER": base_config.broker_host
    }

    for field in form_vars.items():
        if field[0].startswith('pillar-key'):
            key_id = field[0].split('-')[-1]
            key_name = field[1]
            key_value = request.form.get("pillar-value-{0}".format(key_id))
            if key_name == '' or key_value == '':
                continue
            config_pillar[key_name] = key_value

    # update key / config and save again
    auth_key.save()
    print(auth_key.identifier)
    print("Save")
    honeypot_instance.hpfeeds = auth_key
    honeypot_instance.pillar = config_pillar
    honeypot_instance.save()

    # Create the job
    honeypot_state_file = 'honeypots/{0}/{1}'.format(
        honeypot_details.id,
        honeypot_details.honeypot_state_file
        )

    pillar_string = ", ".join(
        ('"{}": "{}"'.format(*i) for i in config_pillar.items())
        )

    try:
        job_id = pepper_api.apply_state(
            hive_id,
            [
                honeypot_state_file,
                "pillar={{{0}}}".format(pillar_string)
            ]
        )

        hive = Hive.objects(id=hive_id).first()
        job = PepperJobs(
            hive=hive,
            job_id=job_id,
            job_short="Apply State {0}".format(honeypot_details.name),
            job_description="Apply honeypot {0} to Hive {1}".format(
                honeypot_state_file, hive_id
                )
        )
        job.save()

        if honeypot_instance not in hive.honeypots:
            hive.honeypots.append(honeypot_instance)

        hive.save()

        json_response['success'] = True
        json_response['message'] = "Job Created with Job ID: {0}".format(
            str(job.id)
            )
    except Exception as err:
        json_response['message'] = "Error creating job: {0}".format(err)

    return jsonify(json_response)
