import os
from flask import Flask, flash, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
import json
from os import path
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)

app.secret_key = 'ndsn'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.login_view = 'signin'
login_manager.init_app(app)

#user model
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(35), unique=True, nullable=False)
    email = db.Column(db.String(35), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def create_database(app):
    if not path.exists('users.db'):
        with app.app_context():
            db.create_all()
            print("Created Database!")


@app.route('/')
def home():
    return render_template("index.html")

#signup route
@app.route('/signup', methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        if User.query.filter_by(email=email).first():
            flash("Email already registered. Try logging in!", "error")
            return redirect(url_for("signup"))

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(name=name, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for("signin"))
    return render_template('signup.html')

#signin route
@app.route('/signin', methods=["GET", "POST"])
def signin():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("dashboard"))

        flash("Invalid email or password. Try again!", "error")
    return render_template('signin.html')

#dashboard route
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)


if __name__ == '__main__':
    create_database(app)
    app.run(debug=True)
