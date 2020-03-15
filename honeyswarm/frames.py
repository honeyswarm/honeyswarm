import os
from uuid import uuid4
from datetime import datetime

import mimetypes
from flask import render_template, abort, jsonify, send_file, g, request, url_for
from flask import Blueprint, render_template, redirect, url_for, request, flash, abort, jsonify
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from honeyswarm.models import Frame

from flaskcode.utils import write_file, dir_tree, get_file_extension


frames = Blueprint('frames', __name__)

from honeyswarm.saltapi import pepper_api

from honeyswarm import SALT_STATE_BASE


@frames.route('/frames')
@login_required
def frames_list():

    # List of Availiable Frames
    frame_list = Frame.objects

    return render_template(
        "frames.html",
        frame_list=frame_list
        )

@frames.route('/frames/<frame_id>/edit/')
@login_required
def show_frame(frame_id):
    print(frame_id)
    frame_details = Frame.objects(id=frame_id).first()

    if not frame_details:
        abort(404)
    framename = frame_details.name
    # Lets hack in flask code.
    honey_salt_base =  os.path.join(SALT_STATE_BASE, 'frames', frame_id)
    #honey_salt_base =  os.path.join(SALT_STATE_BASE, 'frames')

    dirname = os.path.basename(honey_salt_base)
    dtree = dir_tree(honey_salt_base, honey_salt_base + '/')

    # I want to rebuild the tree slightlt differently. 
    new_tree = dict(
        name=os.path.basename(honey_salt_base),
        path_name=dtree['path_name'],
        children=[{
            'name': framename,
            'path_name': framename,
            'children': dtree['children']
        }]
    )

    #print(new_tree)

    #for k, v in new_tree.items():
    #    print(k,v)

    return render_template(
        'flaskcode/frame_editor.html',
        frame_details=frame_details,
        dirname=dirname,
        dtree=new_tree,
        editor_theme="vs-dark",
        frame_id=frame_id,
        object_id=frame_id,
        data_url="frames"
        )


@frames.route('/frames/create/', methods=['POST'])
@login_required
def create_frame():

    json_response = {"success": False}

    try:
        new_frame = Frame()
        new_frame.name = request.form.get('frame_name')
        os_list = request.form.get('supported_os')
        new_frame.supported_os = [x for x in os_list.split(',')]
        new_frame.description = request.form.get('frame_description')
        new_frame.frame_state_file = request.form.get('frame_state_file')
        new_frame.save()

        frame_id = new_frame.id
        state_path = os.path.join(SALT_STATE_BASE, 'frames', str(frame_id))
        state_name = "{0}.sls".format(new_frame.frame_state_file)
        state_file_path = os.path.join(state_path, state_name)
        if not os.path.exists(state_path):
            os.mkdir(state_path)
            os.mknod(state_file_path)
            os.chmod(state_file_path, 0o777)

        json_response['success'] = True
        json_response['message'] = "Frame Created"

    except Exception as err:
        json_response['message'] = err
        print(err)

    return redirect(url_for('frames.frames_list'))

    return jsonify(json_response)


@frames.route('/frames/<frame_id>/update/', methods=['POST'])
@login_required
def update_frame(frame_id):
    frame_details = Frame.objects(id=frame_id).first()

    if not frame_details:
        abort(404)

    form_vars = request.form.to_dict()
    json_response = {"success": False}

    frame_details.name = request.form.get('frame_name')
    frame_details.frame_state_path = request.form.get('frame_state_path')
    frame_details.description = request.form.get('frame_description')
    os_list = request.form.get('supported_os')
    frame_details.supported_os = [x for x in os_list.split(',')]

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

    
    frame_details.pillar = pillar_states

    frame_details.save()

    json_response['success'] = True

    return jsonify(json_response)

@frames.route('/frames/<object_id>/resource-data/<path:file_path>.txt', methods=['GET', 'HEAD'])
@login_required
def resource_data(object_id, file_path):
    print(file_path)

    honey_salt_base =  os.path.join(SALT_STATE_BASE, 'frames', object_id)

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


@frames.route('/frames/<object_id>/update-resource-data/<path:file_path>', methods=['POST'])
@login_required
def update_resource_data(object_id, file_path):
    print(file_path)
    honey_salt_base =  os.path.join(SALT_STATE_BASE, 'frames', object_id)
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



@frames.route('/frames/<frame_id>/deploy/', methods=['POST'])
@login_required
def frame_deploy(frame_id):
    """Add Docker Frame"""
    form_vars = request.form.to_dict()
    json_response = {"success": False}
    hive_id = request.form.get('hive_id')
    frame_state_file = request.form.get('frame_state_file')
    frame_id = request.form.get('frame_id')


    frame_details = Frame.objects(id=frame_id).first()

    if not frame_details:
        json_response['message'] = "Can not find honeypot"

    hive_id = request.form.get('target_hive')

    hive = Hive.objects(id=hive_id).first()
    if not hive:
        json_response['message'] = "Can not find Hive"

    config_pillar = { 
        "HIVEID": hive_id,
        "FRAMEID": frame_id 
    }

    # Now add any Pillar States
    for field in form_vars.items():
        if field[0].startswith('pillar-key'):
            key_id = field[0].split('-')[-1]
            key_name = field[1]
            key_value = request.form.get("pillar-value-{0}".format(key_id))
            if key_name == '' or key_value == '':
                continue
            config_pillar[key_name] = key_value

    frame_state_file = 'frames/{0}/{1}'.format(frame_details.id, frame_details.frame_state_path)
    pillar_string = ", ".join(('"{}": "{}"'.format(*i) for i in config_pillar.items()))

    try:

        job_id = pepper_api.apply_state(
            hive_id, 
            [
                frame_state_file,
                "pillar={{{0}}}".format(pillar_string)
            ]
        )

        hive = Hive.objects(id=hive_id).first()
        job = PepperJobs(
            hive=hive,
            job_id=job_id,
            job_short="Apply State {0}".format(frame_details.name),
            job_description="Apply frame {0} to Hive {1}".format(frame_details, hive_id)
        )
        job.save()

        hive.frame = frame_details
        hive.save()

        json_response['success'] = True
        json_response['message'] = "Job Created with Job ID: {0}".format(str(job.id))
    except Exception as err:
        json_response['message'] = "Error creating job: {0}".format(err)


    return jsonify(json_response)
