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

BASE_PATH = '/home/thehermit/github/honeyswarm/honeystates/salt/'

@frames.route('/frames')
@login_required
def frames_list():

    # List of Availiable Frames
    frame_list = Frame.objects

    return render_template(
        "frames.html",
        frame_list=frame_list
        )

@frames.route('/frames/<frame_id>')
@login_required
def show_frame(frame_id):
    print(frame_id)
    frame_details = Frame.objects(id=frame_id).first()

    if not frame_details:
        abort(404)
    framename = frame_details.name
    # Lets hack in flask code.
    honey_salt_base =  os.path.join(BASE_PATH, 'frames', frame_id)
    #honey_salt_base =  os.path.join(BASE_PATH, 'frames')

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

@frames.route('/frames/<frame_id>/update/', methods=['POST'])
@login_required
def update_frame(frame_id):
    frame_details = Frame.objects(id=frame_id).first()

    if not frame_details:
        abort(404)

    form_vars = request.form.to_dict()
    json_response = {"success": False}

    frame_details.name = request.form.get('frame_name')
    frame_details.frame_type = request.form.get('frame_type')
    frame_details.description = request.form.get('frame_description')

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

    honey_salt_base =  os.path.join(BASE_PATH, 'frames', object_id)

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
    honey_salt_base =  os.path.join(BASE_PATH, 'frames', object_id)
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

