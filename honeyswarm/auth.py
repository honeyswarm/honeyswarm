from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_security import login_required
from flask_security.utils import login_user, logout_user
from flask_security.utils import verify_and_update_password, encrypt_password
from honeyswarm.models import User
from honeyswarm import user_datastore

auth = Blueprint('auth', __name__)


@auth.route('/auth/login')
def login():
    return render_template("login.html")


@auth.route('/auth/login', methods=['POST'])
# @csrf_exempt
def login_post():
    email = request.form.get('email')
    password = request.form.get('password')
    remember = True if request.form.get('remember') else False

    user = User.objects(email=email).first()

    # ToDo: There is username enumeration here.

    # Check if enabled account
    if not user or not user.active:
        flash('This account has been disabled')
        return redirect(url_for('auth.login'))

    # check if user actually exists
    if not user or not verify_and_update_password(password, user):
        flash('Please check your login details and try again.')
        return redirect(url_for('auth.login'))

    # ToDo: Need to put a real check for remember me in here
    login_user(user, remember=remember)
    return redirect(url_for('dashboard.main_dashboard'))


@auth.route('/register')
def register():
    return render_template('register.html')


@auth.route('/register', methods=['POST'])
def register_post():
    email = request.form.get('email')
    name = request.form.get('name')
    password = request.form.get('password')

    user = User.objects(email=email).first()

    if user:
        flash('Email address already exists')
        return redirect(url_for('auth.register'))

    new_user = user_datastore.create_user(
        email=email,
        password=encrypt_password(password),
        name=name,
        active=False
        )

    userrole = user_datastore.find_role('user')
    user_datastore.add_role_to_user(new_user, userrole)

    return redirect(url_for('auth.login'))


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))
