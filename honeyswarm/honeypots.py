import os
import stat
from uuid import uuid4
from datetime import datetime

import mimetypes
from flask import render_template, abort, jsonify, send_file, g, request
from flask import Blueprint, render_template, redirect, url_for, request, flash, abort, jsonify
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from honeyswarm.models import Hive, PepperJobs, Honeypot

from flaskcode.utils import write_file, dir_tree, get_file_extension


honeypots = Blueprint('honeypots', __name__)

from honeyswarm.saltapi import pepper_api
from honeyswarm import SALT_STATE_BASE


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
        new_honeypot.honeypot_state_file = request.form.get('honeypot_state_file')
        new_honeypot.save()

        honeypot_id = new_honeypot.id
        state_path = os.path.join(SALT_STATE_BASE, 'honeypots', str(honeypot_id))
        state_name = "{0}.sls".format(new_honeypot.honeypot_state_file)
        state_file_path = os.path.join(state_path, state_name)
        if not os.path.exists(state_path):
            os.mkdir(state_path)
            os.mknod(state_file_path)
            os.chmod(state_file_path, stat.S_IRWXO)

        json_response['success'] = True
        json_response['message'] = "Honypot Created"

    except Exception as err:
        json_response['message'] = err
        print(err)

    return redirect(url_for('honeypots.honeypot_list'))

    return jsonify(json_response)


@honeypots.route('/honeypots/<honeypot_id>/edit/')
@login_required
def show_honeypot(honeypot_id):
    print(honeypot_id)
    honeypot_details = Honeypot.objects(id=honeypot_id).first()

    if not honeypot_details:
        abort(404)
    honeypotname = honeypot_details.name
    # Lets hack in flask code.
    honey_salt_base =  os.path.join(SALT_STATE_BASE, 'honeypots', honeypot_id)
    #honey_salt_base =  os.path.join(SALT_STATE_BASE, 'honeypots')

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

    #print(new_tree)

    #for k, v in new_tree.items():
    #    print(k,v)

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
    honeypot_details.honeypot_state_file = request.form.get('honeypot_state_file')

    # Now add any Pillar States
    pillar_states = []
    for field in form_vars.items():
        print(field)
        if field[0].startswith('pillar-key'):
            key_id = field[0].split('-')[-1]
            key_name = field[1]
            key_value = request.form.get("pillar-value-{0}".format(key_id))
            if key_name == '' or key_value == '':
                continue
            pillar_pair = [key_name, key_value]
            pillar_states.append(pillar_pair)

    
    honeypot_details.pillar = pillar_states

    honeypot_details.save()

    json_response['success'] = True

    return jsonify(json_response)

@honeypots.route('/honeypots/<object_id>/resource-data/<path:file_path>.txt', methods=['GET', 'HEAD'])
@login_required
def resource_data(object_id, file_path):
    print("Read Resource", file_path)

    honey_salt_base =  os.path.join(SALT_STATE_BASE, 'honeypots', object_id)

    file_path = os.path.join(honey_salt_base, file_path)
    if not (os.path.exists(file_path) and os.path.isfile(file_path)):
        abort(404)
    response = send_file(file_path, mimetype='text/plain', cache_timeout=0)
    mimetype, encoding = mimetypes.guess_type(file_path, False)
    if mimetype:
        response.headers.set('X-File-Mimetype', mimetype)
        extension = mimetypes.guess_extension(mimetype, False) or get_file_extension(file_path)
        if extension:
            response.headers.set('X-File-Extension', extension.lower().lstrip('.'))
    if encoding:
        response.headers.set('X-File-Encoding', encoding)
    return response


@honeypots.route('/honeypots/<object_id>/update-resource-data/<path:file_path>', methods=['POST'])
@login_required
def update_resource_data(object_id, file_path):


    print("Update REsource", file_path)
    honey_salt_base =  os.path.join(SALT_STATE_BASE, 'honeypots', object_id)
    file_path = os.path.join(honey_salt_base, file_path)
    is_new_resource = bool(int(request.form.get('is_new_resource', 0)))


    if not is_new_resource and not (os.path.exists(file_path) and os.path.isfile(file_path)):
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

    # Get a list of all hives that have a frame installed and are responding to polls.
    #ToDo: Only permit based on frame supported OS?
    # Do we need to add Frames as a Reference Field to Honeypot?

    all_hives = Hive.objects(frame__exists=True, salt_alive=True)

    # there is no join so we need multiple queries. 
    # There shouldnt by thousands or rows so we shouldnt need to worry about effeciency. 

    existing_honeypots = []

    for hive in all_hives:
        for honeypot in hive.honeypots:
            print(honeypot_id, honeypot.id)
            print(honeypot.id == honeypot_id)
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

    hive_id = request.form.get('target_hive')

    hive = Hive.objects(id=hive_id).first()
    if not hive:
        json_response['message'] = "Can not find Hive"


    config_pillar = {}

    # Now add any Pillar States
    for field in form_vars.items():
        if field[0].startswith('pillar-key'):
            key_id = field[0].split('-')[-1]
            key_name = field[1]
            key_value = request.form.get("pillar-value-{0}".format(key_id))
            if key_name == '' or key_value == '':
                continue
            config_pillar[key_name] = key_value

    print(config_pillar)
    print(hive.name)
    honeypot_state_file = 'honeypots/{0}/{1}'.format(honeypot_details.id, honeypot_details.honeypot_state_file)
    pillar_string = ", ".join(("{}: {}".format(*i) for i in config_pillar.items()))


    print("pillar={{{0}}}".format(pillar_string))


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
            job_short="Apply State Cowrie",
            job_description="Apply honeypot {0} to Hive {1}".format('honeypots/cowrie/cowrie', hive_id)
        )
        job.save()

        if honeypot_details not in hive.honeypots:
            hive.honeypots.append(honeypot_details)

        hive.save()

        json_response['success'] = True
        json_response['message'] = "Job Created with Job ID: {0}".format(str(job.id))
    except Exception as err:
        json_response['message'] = "Error creating job: {0}".format(err)


    return jsonify(json_response)