from flask import Blueprint, render_template, redirect, url_for, request, flash
from werkzeug.security import generate_password_hash, check_password_hash
from honeyswarm.models import User, Role

from flask_security import login_required
from flask_security.utils import login_user, verify_and_update_password, encrypt_password, logout_user 

from honeyswarm import user_datastore


auth = Blueprint('auth', __name__)

@auth.route('/login')
def login():
    return render_template("login.html")


@auth.route('/login', methods=['POST'])
def login_post():
    email = request.form.get('email')
    password = request.form.get('password')
    remember = True if request.form.get('remember') else False

    user = User.objects(email=email).first()

    # check if user actually exists
    # take the user supplied password, hash it, and compare it to the hashed password in database
    if not user or not verify_and_update_password(password, user):
        flash('Please check your login details and try again.')
        return redirect(url_for('auth.login')) # if user doesn't exist or password is wrong, reload the page

    # if the above check passes, then we know the user has the right credentials

    # ToDo: Need to put a real check for remember me in here
    login_user(user, remember=remember)
    return redirect(url_for('dashboard'))   

@auth.route('/register')
def register():
    return render_template('register.html')


@auth.route('/register', methods=['POST'])
def register_post():
    email = request.form.get('email')
    name = request.form.get('name')
    password = request.form.get('password')

    user = User.objects(email=email).first()


    if user: # if a user is found, we want to redirect back to register page so user can try again
        flash('Email address already exists')
        return redirect(url_for('auth.register'))

    # create new user hash the password with bcrypt and add them to users group by default. 

    new_user = user_datastore.create_user(
        email=email,
        password=encrypt_password(password),
        name=name
        )

    userrole = user_datastore.find_role('user')
    user_datastore.add_role_to_user(new_user, userrole)

    return redirect(url_for('auth.login'))

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))