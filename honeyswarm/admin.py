import os
from uuid import uuid4
from datetime import datetime

import mimetypes
from flask import render_template, abort, jsonify, send_file, g, request, url_for
from flask import Blueprint, render_template, redirect, url_for, request, flash, abort, jsonify
from flask_login import login_user, logout_user, login_required
from flask_security.decorators import roles_required
from werkzeug.security import generate_password_hash, check_password_hash
from honeyswarm.models import AuthKey, User, Role

admin = Blueprint('admin', __name__)



@admin.route('/admin')
@roles_required('admin')
def admin_page():

    # Users
    users = User.objects

    # Roles
    roles = Role.objects

    for user in users:
        for role in roles:
            print(role.id, user.roles)
            print(role.id in [x.id for x in user.roles])

    # AuthKeys
    auth_keys = AuthKey.objects

    return render_template(
        "admin.html",
        users=users,
        roles=roles,
        auth_keys=auth_keys
        )


