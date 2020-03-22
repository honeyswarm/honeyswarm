from flask import Blueprint, render_template
from flask_security.decorators import roles_required
from honeyswarm.models import AuthKey, User, Role

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
