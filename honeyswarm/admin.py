from flask import Blueprint, render_template, jsonify, request
from flask_security.decorators import roles_required
from honeyswarm.models import AuthKey, User, Role
from flask_security.utils import encrypt_password
from honeyswarm import user_datastore

admin = Blueprint('admin', __name__)


@admin.route('/admin')
@roles_required('admin')
def admin_page():

    # Users
    users = User.objects

    # Roles
    roles = Role.objects

    # AuthKeys
    auth_keys = AuthKey.objects

    return render_template(
        "admin.html",
        users=users,
        roles=roles,
        auth_keys=auth_keys
        )


@admin.route('/admin/keys/', methods=['POST'])
@roles_required('admin')
def update_keys():

    json_response = {"success": False, "message": None}

    action = request.form.get('action')
    key_id = request.form.get('object_id')

    key = AuthKey.objects(id=key_id).first()
    
    if not key:
        json_response['message'] = "Not a valid key"
        return jsonify(json_response)

    if action == "delete":
        key.delete()
        json_response['success'] = True
        json_response['message'] = "Deleted HPFeeds Authkey {0}".format(key.identifier)

    elif action == "update":
        key.identifier = request.form.get('identifier')
        key.secret = request.form.get('secret')
        key.publish = request.form.get('publish').split(',')
        key.subscribe = request.form.get('subscribe').split(',')
        key.save()
        json_response['success'] = True
        json_response['message'] = "Update HPFeeds Authkey {0}".format(key.identifier)

    return jsonify(json_response)


@admin.route('/admin/users/', methods=['POST'])
@roles_required('admin')
def updte_users():

    json_response = {"success": False, "message": None}

    action = request.form.get('action')
    user_id = request.form.get('object_id')

    user = User.objects(id=user_id).first()
    
    if not user:
        json_response['message'] = "Not a valid user"
        return jsonify(json_response)

    if action == "delete":
        user_datastore.delete_user(user)
        json_response['success'] = True
        json_response['message'] = "Deleted User {0}".format(user.name)

    elif action == "update":

        user.name = request.form.get('name')
        user.email = request.form.get('email')
        activate_user = request.form.get('active')

        password = request.form.get('password')
        
        if password:
            user.password = encrypt_password(password)

        if activate_user == "false":
            user_datastore.deactivate_user(user)
        else:
            user_datastore.activate_user(user)

        # Remove all roles
        all_roles = Role.objects()
        for role in all_roles:
            user_datastore.remove_role_from_user(user, role)

        # add new roles
        for role_id in request.form.getlist('roles[]'):
            role = Role.objects(id=role_id).first()
            if role:
                user_datastore.add_role_to_user(user, role)

        user.save()

        json_response['success'] = True
        json_response['message'] = "Updated details for {0}".format(user.name)

    return jsonify(json_response)