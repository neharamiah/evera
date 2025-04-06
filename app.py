import os
from flask import Flask, flash, render_template, request, send_file, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
import json
from os import path
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from werkzeug.utils import secure_filename
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO
import pandas as pd
from sqlalchemy import extract
import matplotlib.pyplot as plt
import math
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

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

#certifications model
class Certificate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, default=db.func.current_timestamp())


emission_factors = {
    "road": 80,
    "rail": 15,
    "air": 550,
    "sea": 20
}

UPLOAD_FOLDER = "static/uploads"
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/upload_certificate", methods=["POST"])
def upload_certificate():
    if "certificate" not in request.files:
        flash("No file part")
        return redirect(request.referrer)

    file = request.files["certificate"]
    company_name = request.form.get("company_name")
    title = request.form.get("title")

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(file_path)

        new_certificate = Certificate(company_name=company_name, title=title, file_path=file_path)
        db.session.add(new_certificate)
        db.session.commit()

        flash("Certificate uploaded successfully!")
        return redirect(url_for("certifications_page"))

    flash("Invalid file type!")
    return redirect(request.referrer)

@app.route("/certifications")


def certifications_page():
    certificates = Certificate.query.order_by(Certificate.upload_date.desc()).all()
    return render_template("certifications.html", certificates=certificates)

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

@app.route('/calculate')
def calculate():
    return render_template('calculate.html')

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
    current_user.green_score = max(0, 100 - ((current_user.net_emission)*0.0000005)) 
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
    current_user.update_emission_and_score()

    progress = min(100, (current_user.total_offset / current_user.total_emission) * 100) if current_user.total_emission > 0 else 0

    return render_template('offset-emissions.html',
                           total_emission=current_user.total_emission,
                           total_offset=current_user.total_offset,
                           net_emission=current_user.net_emission,
                           progress=progress)


# renewable energy offset
@app.route('/offset/renewable', methods=['GET', 'POST'])
@login_required
def offset_renewable():

    if request.method == 'POST':
        try:

            kwh = float(request.form.get('kwh'))
            sunlight_hours = float(request.form.get('sunlight_hours'))
            days_run = int(request.form.get('days_run'))

            emission_factor = 850  


            total_energy = kwh * sunlight_hours * days_run
            offset_amount = round(total_energy * emission_factor, 2)


            new_offset = Offset(user_id=current_user.id, category='Renewable Energy', amount=offset_amount)
            db.session.add(new_offset)
            db.session.commit()


            current_user.update_emission_and_score()

            flash(f'Success! You offset {offset_amount} g of CO₂ from renewable energy.', 'success')
            return redirect(url_for('offset_emissions'))

        except (ValueError, TypeError):
            flash('Invalid input. Please enter valid numbers for kWh, sunlight hours, and days.', 'error')

    return render_template('offset_renewable.html')

# afforestation offset
@app.route('/offset/afforestation', methods=['GET', 'POST'])
@login_required
def offset_afforestation():
    if request.method == 'POST':
        try:
            trees_planted = int(request.form.get('trees_planted'))
            tree_age = int(request.form.get('tree_age'))

            if trees_planted <= 0 or tree_age <= 0:
                flash("Please enter valid positive numbers.", "error")
                return redirect(url_for('offset_afforestation'))

            offset_amount = round(trees_planted * tree_age * 21.77, 2)

            new_offset = Offset(user_id=current_user.id, category='Afforestation', amount=offset_amount)
            db.session.add(new_offset)
            db.session.commit()

            current_user.update_emission_and_score()

            flash(f'Success! You offset {offset_amount} kg of CO₂ by planting trees.', 'success')
            return redirect(url_for('offset_emissions'))

        except (ValueError, TypeError):
            flash("Invalid input. Please enter valid numbers.", "error")
            return redirect(url_for('offset_afforestation'))

    return render_template('offset_afforestation.html')

# #certifications route
# @app.route("/certifications")
# def certifications_page():
#     return render_template("certifications.html")


#badges route
@app.route('/badges')
def badges():
    return render_template('badges.html', badges=badges)



#logout
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))



#monthlyreportd
@app.route('/download_report/<int:month>/<int:year>')
@login_required
def download_report(month, year):
    user = current_user

    report_data = Emission.query.filter(
        Emission.user_id == user.id,
        extract('month', Emission.timestamp) == month,
        extract('year', Emission.timestamp) == year
    ).all()

    if not report_data:
        return "No report data available for this month/year.", 404

    categories = {'Road': 0, 'Rail': 0, 'Air': 0, 'Sea': 0}
    individual_emissions = []
    for e in report_data:
        mode = e.transport_mode.strip().capitalize() 
        if mode in categories:
            if isinstance(e.emission, (int, float)):
                categories[mode] += e.emission
                individual_emissions.append([e.timestamp.strftime('%Y-%m-%d'), mode, e.emission])

    offsets_data = Offset.query.filter(
        Offset.user_id == user.id,
        extract('month', Offset.timestamp) == month,
        extract('year', Offset.timestamp) == year
    ).all()

    if not offsets_data:
        return "No offset data available for this month/year.", 404

    offsets_methods = {'Renewable Energy': 0, 'Reforestation': 0, 'Community Service': 0}
    for o in offsets_data:
        if o.category in offsets_methods:
            if isinstance(o.amount, (int, float)): 
                offsets_methods[o.category] += o.amount

    emissions_table = [["Transport Mode", "Emissions (kg CO2)"]] + [[mode, f"{value} kg CO2"] for mode, value in categories.items()]
    offsets_table = [["Offset Method", "Offset Amount (kg CO2)"]] + [[method, f"{value} kg CO2"] for method, value in offsets_methods.items()]

    individual_emissions_table = [["Date", "Transport Mode", "Emission Value (kg CO2)"]] + individual_emissions

    pdf_file = BytesIO()
    c = canvas.Canvas(pdf_file, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 12)  
    c.drawString(50, height - 50, f"Emissions & Offsets Report - {user.name}")

    c.setFont("Helvetica", 10) 
    y_position = height - 80
    c.drawString(50, y_position - 20, f"Month: {month} {year}")

    y_position -= 120  
    c.drawString(50, y_position, "Emissions by Transport Mode:")
    y_position -= 20 

    emissions_table_data = Table(emissions_table, colWidths=[200, 100])
    emissions_table_data.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
    ]))

    emissions_table_data.wrapOn(c, width, height)
    emissions_table_data.drawOn(c, 50, y_position)  

    y_position -= 140  
    c.drawString(50, y_position, "Offsets by Method:")
    y_position -= 30 

    offsets_table_data = Table(offsets_table, colWidths=[200, 100])
    offsets_table_data.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
    ]))

    offsets_table_data.wrapOn(c, width, height)
    offsets_table_data.drawOn(c, 50, y_position) 

    c.showPage() 
    c.drawString(50, height - 50, "Individual Emissions for the Month:")
    y_position = height - 80
    individual_emissions_table_data = Table(individual_emissions_table, colWidths=[120, 150, 100])
    individual_emissions_table_data.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
    ]))

    individual_emissions_table_data.wrapOn(c, width, height)
    individual_emissions_table_data.drawOn(c, 50, y_position) 

    c.save()

    pdf_file.seek(0)

    return send_file(pdf_file, as_attachment=True, download_name=f"report_{user.id}_{month}_{year}.pdf", mimetype="application/pdf")


if __name__ == '__main__':
    create_database(app)
    app.run(debug=True)
