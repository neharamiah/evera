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
    total_emission = db.Column(db.Float, default=0.0)
    green_score = db.Column(db.Float, nullable=False, default=100.0)
    total_offset = db.Column(db.Float, default=0.0)
    net_emission = db.Column(db.Float, default=0.0)
    badges = db.Column(db.String(200), default="")

    def update_emission_and_score(self):
        self.total_offset = sum(offset.amount for offset in self.offsets)
        self.net_emission = max(0, self.total_emission - self.total_offset)
        self.green_score = max(0, 100 - (self.net_emission / 1000) * 100)

        db.session.commit()

#offset model
class Offset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('offsets', lazy=True))


#emission model
class Emission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    weight = db.Column(db.Float, nullable=False)
    distance = db.Column(db.Float, nullable=False)
    transport_mode = db.Column(db.String(20), nullable=False)
    emission = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('emissions', lazy=True))

emission_factors = {
    "road": 80,
    "rail": 15,
    "air": 550,
    "sea": 20
}



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


#emissionsroute and caclulation
@app.route("/emissions", methods=["GET", "POST"])
@login_required
def emissions():
    if request.method == "POST":
        try:
            weight = float(request.form["weight"])
            distance = float(request.form["distance"])
            transport_mode = request.form["transport_mode"]

            if transport_mode not in emission_factors:
                return jsonify({"success": False, "error": "Invalid transport mode"}), 400

            emission_value = weight * distance * emission_factors[transport_mode] / 1000 # in g
            current_user.total_emission += emission_value
            current_user.update_emission_and_score()

            db.session.add(current_user)

            new_emission = Emission(
                user_id=current_user.id,
                weight=weight,
                distance=distance,
                transport_mode=transport_mode,
                emission=emission_value
            )
            db.session.add(new_emission)
            db.session.commit()

            return jsonify({"success": True, "emission": emission_value})

        except Exception as e:
            db.session.rollback()
            return jsonify({"success": False, "error": str(e)}), 500

    return render_template("emissions.html")



#might need for graphs
@app.route("/data")
@login_required
def get_emission_data():
    emissions = Emission.query.filter_by(user_id=current_user.id).all()
    data = [
        {
            "weight": e.weight,
            "distance": e.distance,
            "transport_mode": e.transport_mode,
            "emission": e.emission,
            "timestamp": e.timestamp.isoformat(),
        }
        for e in emissions
    ]
    return jsonify(data)


#greencore route
@app.route('/greenscore')
@login_required
def green_score():
    current_user.net_emission = max(0, current_user.total_emission - current_user.total_offset)
    current_user.green_score = max(0, 100 - ((current_user.net_emission)*0.0005)) 
    db.session.commit()

    leaderboard = User.query.order_by(User.green_score.desc()).limit(10).all()

    return render_template('greenscore.html',
                           total_emissions=current_user.total_emission,
                           total_offset=current_user.total_offset,
                           net_emissions=current_user.net_emission,
                           green_score=current_user.green_score,
                           leaderboard=leaderboard,
                           enumerate=enumerate)



#offset route
@app.route('/offset-emissions')
@login_required
def offset_emissions():
    return render_template('offset-emissions.html')


#certifications route
@app.route("/certifications")
def certifications_page():
    return render_template("certifications.html")


#badges route
@app.route('/badges')
def badges():
    return render_template('badges.html')


#logout
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))


if __name__ == '__main__':
    create_database(app)
    app.run(debug=True)
