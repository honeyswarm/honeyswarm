import os
from uuid import uuid4
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, request, flash, abort, jsonify
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from honeyswarm.models import Hive


hives = Blueprint('hives', __name__)

APITOKEN = os.environ.get("HIVE_API_TOKEN")

from app import pepper_api

@hives.route('/hives')
@login_required
def hives_list():

    hive_list = Hive.objects

    key_list = pepper_api.salt_keys()

    for hive in hive_list:
        print(hive.id)
        if str(hive.id) in key_list['minions']:
            hive.registered = True
        if str(hive.id) in key_list['minions_pre']:
            hive.registered = False
        hive.save()

    print(key_list)

    return render_template(
        "hives.html",
        apitoken=APITOKEN,
        hive_list=hive_list
        )

@hives.route('/hives/actions', methods=["POST", "GET"])
@login_required
def hive_actions():
    if request.method == "POST":
        form_vars = request.form.to_dict()
        print(form_vars)

        json_response = {"success": False}

        if 'action' not in form_vars and 'hive_id' not in form_vars:
            json_response['message'] = "Missing Hive ID or Action"
        
        else:
            hive_action = form_vars['action']
            hive_id = form_vars['hive_id']
            if hive_action == 'delete':
                try:
                    Hive.objects(id=hive_id).delete()
                    json_response['success'] = True
                    json_response['message'] = "Hive Deleted"
                except Exception as err:
                    json_response['message'] = "Error Deleting Hive: {0}".format(err)

            elif hive_action == 'swarm':
                try:
                    hive = Hive.objects(id=hive_id).first()

                    # Accept the key
                    print("adding Key")
                    add_key = pepper_api.accept_key(hive_id)
                    print(add_key)

                    # Get the ip address

                    print("Get IP")
                    ip_add_response = pepper_api.run_client_function(hive_id, "network.ip_addrs")
                    ip_add_list = ip_add_response[hive_id]

                    # Add the list of IPs or just the first ?
                    hive.ip_address = ip_add_list[0]

                    # Save the hive

                    print("Save")
                    hive.registered = True
                    hive.last_seen = datetime.utcnow
                    hive.save()

                    # Trigger the base stats sls

                    json_response['success'] = True
                    json_response['message'] = "Missing Hive ID or Action"
                except Exception as err:
                    json_response['message'] = "Error Adding to swarm: {0}".format(err)
            elif hive_action == 'poll':
                try:
                    hive = Hive.objects(id=hive_id).first()

                    # Get the ip address

                    print("Get IP")
                    ip_add_response = pepper_api.run_client_function(hive_id, "network.ip_addrs")
                    ip_add_list = ip_add_response[hive_id]

                    # Add the list of IPs or just the first ?
                    hive.ip_address = ip_add_list[0]

                    # Save the hive

                    print("Save")
                    hive.registered = True
                    hive.last_seen = datetime.utcnow
                    hive.save()
                except Exception as err:
                    json_response['message'] = "Error Polling Hive: {0}".format(err)
            elif hive_action == 'edit':
                try:
                    this = "that"
                    json_response['success'] = True
                    json_response['message'] = "Missing Hive ID or Action"
                except Exception as err:
                    json_response['message'] = "Missing Hive ID or Action"
            elif hive_action == 'restart':
                try:
                    this = "that"
                    json_response['success'] = True
                    json_response['message'] = "Missing Hive ID or Action"
                except Exception as err:
                    json_response['message'] = "Missing Hive ID or Action"

        return jsonify(json_response)



# This is an API call to return the salt installer
@hives.route('/api/hive/register')
def hives_register():
    authenticated = False
    # Check for the deployment token
    if 'Authorization' in request.headers:
        auth_token = request.headers['Authorization']
        if auth_token == APITOKEN:
            authenticated = True
    else:
        abort(403)

    # If incorrect APITOKEN
    if not authenticated:
        abort(403)


    # Lets create a new hive
    new_hive = Hive(
        name=str(uuid4())
    )

    new_hive.save()
    salt_id = new_hive.id

    # Return the Installation Script
    return render_template(
        "hive_registration.sh",
        honeyswarm_host="192.168.1.184",
        salt_minion_id=salt_id

    )