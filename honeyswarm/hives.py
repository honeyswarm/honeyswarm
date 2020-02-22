import os
from uuid import uuid4
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, request, flash, abort, jsonify
from flask_security import login_required
from flask_security.core import current_user
from flask_security.decorators import roles_accepted
from honeyswarm.models import Hive, PepperJobs


hives = Blueprint('hives', __name__)

APITOKEN = os.environ.get("HIVE_API_TOKEN")

from honeyswarm.saltapi import pepper_api

@hives.route('/hives')
@login_required
def hives_list():

    hive_list = Hive.objects

    key_list = pepper_api.salt_keys()

    for hive in hive_list:
        if str(hive.id) in key_list['minions']:
            hive.registered = True
        if str(hive.id) in key_list['minions_pre']:
            hive.registered = False
        hive.save()

    return render_template(
        "hives.html",
        apitoken=APITOKEN,
        hive_list=hive_list,
        key_list=key_list['minions_pre']
        )


##
# Hive Actions
##
@hives.route('/hives/actions/delete', methods=["POST"])
@login_required
def hive_delete():
    """Delete hiveid from Mongo and salt master"""
    form_vars = request.form.to_dict()
    json_response = {"success": False}
    hive_id = request.form.get('hive_id')
    if not hive_id:
        json_response['message'] = "Missing Hive ID"
    else:
        try:
            hive = Hive.objects(id=hive_id).first()

            # Delete Jobs
            PepperJobs.objects(hive).delete()

            # Delete Hive
            Hive.objects(id=hive_id).delete()


            # Remove Key
            pepper_api.delete_key(hive_id)
            json_response['success'] = True
            json_response['message'] = "Hive Deleted"
        except Exception as err:
            json_response['message'] = "Error Deleting Hive: {0}".format(err)

    return jsonify(json_response)


@hives.route('/hives/actions/poll', methods=["POST"])
@login_required
def hive_poll():
    """Poll a hive and get its grains"""
    form_vars = request.form.to_dict()
    json_response = {"success": False}
    hive_id = request.form.get('hive_id')

    if not hive_id:
        json_response['message'] = "Missing Hive ID"
    else:
        try:
            hive = Hive.objects(id=hive_id).first()
            grains_request = pepper_api.run_client_function(hive_id, 'grains.items')

            hive_grains = grains_request[hive_id]
            if hive_grains:
                hive.grains = hive_grains
                hive.last_seen = datetime.utcnow
                hive.salt_alive = True
            else:
                hive.salt_alive = False
            hive.save()
            json_response = {"success": True}
            json_response['message'] = "Poll Complete"
        except Exception as err:
            json_response['message'] = "Error Polling Hive: {0}".format(err)

    return jsonify(json_response)

@hives.route('/hives/actions/swarm', methods=["POST"])
@login_required
def hive_swarm():
    """Add a hive to the swarm"""
    form_vars = request.form.to_dict()
    json_response = {"success": False}
    hive_id = request.form.get('hive_id')

    if not hive_id:
        json_response['message'] = "Missing Hive ID"
    else:
        try:
            hive = Hive.objects(id=hive_id).first()
            # Accept the key
            add_key = pepper_api.accept_key(hive_id)
            grains_request = pepper_api.run_client_function(hive_id, 'grains.items')
            hive_grains = grains_request[hive_id]

            # If we run too quickly grains may not be ready.
            # Try one more time. 
            if not hive_grains:
                print("Grains round 2")
                grains_request = pepper_api.run_client_function(hive_id, 'grains.items')
                hive_grains = grains_request[hive_id]

            if hive_grains:
                hive.grains = hive_grains
                hive.last_seen = datetime.utcnow
                hive.salt_alive = True
            else:
                hive.salt_alive = False

            hive.save()
            json_response = {"success": True}

            json_response['success'] = True
            json_response['message'] = "Added Hive"
        except Exception as err:
            json_response['message'] = "Error Adding to swarm: {0}".format(err)

    return jsonify(json_response)


@hives.route('/hives/actions/frame', methods=["POST"])
@login_required
def hive_test():
    """Add Docker Frame"""
    form_vars = request.form.to_dict()
    json_response = {"success": False}
    hive_id = request.form.get('hive_id')

    if not hive_id:
        json_response['message'] = "Missing Hive ID"
    else:
        try:

            job_id = pepper_api.apply_state(hive_id, ['docker/docker_linux'])

            hive = Hive.objects(id=hive_id).first()
            job = PepperJobs(
                hive=hive,
                job_id=job_id,
                job_short="Apply State",
                job_description="Apply {0} state to Hive {1}".format('docker/docker_linux', hive_id)
            )
            job.save()

            json_response['success'] = True
            json_response['message'] = "Add Frame submitted with JID: {0}".format(job.id)
        except Exception as err:
            json_response['message'] = "Error Adding to swarm: {0}".format(err)

    return jsonify(json_response)


@hives.route('/hives/actions/cowrie', methods=["POST"])
@login_required
def hive_cowrie():
    """Add Cowrie Honeypot"""
    form_vars = request.form.to_dict()
    json_response = {"success": False}
    hive_id = request.form.get('hive_id')

    if not hive_id:
        json_response['message'] = "Missing Hive ID"
    else:
        try:

            job_id = pepper_api.apply_state(
                hive_id, 
                [
                    'honeypots/cowrie/cowrie',
                    "pillar={HPFSERVER: localhost, HPFPORT: 20000, HPFIDENT: cowrie, HPFSECRET: cowrie}"
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

            json_response['success'] = True
            json_response['message'] = "Job Created with Job ID: {0}".format(str(job.id))
        except Exception as err:
            json_response['message'] = "Error creating job: {0}".format(err)

    return jsonify(json_response)




@hives.route('/hives/actions', methods=["POST", "GET"])
@login_required
def hive_actions():
    if request.method == "POST":
        form_vars = request.form.to_dict()

        json_response = {"success": False}

        if 'action' not in form_vars and 'hive_id' not in form_vars:
            json_response['message'] = "Missing Hive ID or Action"
        
        else:
            hive_action = form_vars['action']
            hive_id = form_vars['hive_id']

            ##
            # Add hive to swarm - Approve the key and poll
            ##
            if hive_action == 'swarm':
                pass

            ##
            # Poll the hive to update its grains
            ##
            elif hive_action == 'poll':
                pass


            elif hive_action == 'edit':
                pass

            ##
            # Can we trigger a hive restart
            ##
            elif hive_action == 'restart':
                # Windows triggers a 5 minute warning for restart
                try:
                    pepper_api.run_client_function(hive_id, 'system.reboot')
                except Exception as err:
                    json_response['message'] = "Missing Hive ID or Action"



            ##
            # Frames
            ##
            elif hive_action == 'frame':
                # Update the hive now


                # Trigger the base stats sls
                print("adding job")
                new_job = PepperJobs(
                    job_short="Install Base State",
                    job_description="salt '' state.apply docker/docker_linux",
                    hive=hive
                )

                job_id = pepper_api.apply_state(hive_id, 'docker/docker_linux')

                new_job.job_id = job_id
                new_job.save()

                print(job_id)

        return jsonify(json_response)



# This is an API call to return the salt installer
@hives.route('/api/hive/register/<operating_system>')
def hives_register(operating_system):
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

    if operating_system == "windows":
        registration_template = "hive_registration.ps1"
    elif operating_system == "linux":
        registration_template = "hive_registration.sh"
    else:
        abort(404)


    # Return the Installation Script
    return render_template(
        registration_template,
        honeyswarm_host="192.168.1.184",
        salt_minion_id=salt_id
    )