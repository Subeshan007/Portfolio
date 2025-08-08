import os
from datetime import datetime
from bson import ObjectId
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash

# Load environment variables
load_dotenv()

# Flask app setup
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret")

# Database setup
mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/healthcare_voice_agent")
client = MongoClient(mongo_uri)
db = client.get_database()
users_collection = db["users"]
appointments_collection = db["appointments"]

# Login manager setup
login_manager = LoginManager(app)
login_manager.login_view = "login"


class MongoUser(UserMixin):
    def __init__(self, user_document: dict):
        self.id = str(user_document.get("_id"))
        self.username = user_document.get("username")
        self.role = user_document.get("role", "patient")
        self.specialty = user_document.get("specialty")

    @property
    def is_doctor(self) -> bool:
        return self.role == "doctor"

    @property
    def is_patient(self) -> bool:
        return self.role == "patient"


@login_manager.user_loader
def load_user(user_id: str):
    try:
        doc = users_collection.find_one({"_id": ObjectId(user_id)})
    except Exception:
        return None
    return MongoUser(doc) if doc else None


@app.template_filter("datetimefmt")
def datetime_format_filter(value):
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(value)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "patient")
        specialty = request.form.get("specialty", "").strip() if role == "doctor" else None

        if not username or not password:
            flash("Username and password are required.", "error")
            return redirect(url_for("register"))

        existing = users_collection.find_one({"username": username})
        if existing:
            flash("Username already exists.", "error")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password)
        user_doc = {
            "username": username,
            "password_hash": password_hash,
            "role": role,
            "specialty": specialty,
            "created_at": datetime.utcnow(),
        }
        result = users_collection.insert_one(user_doc)
        user_doc["_id"] = result.inserted_id
        login_user(MongoUser(user_doc))
        flash("Registration successful!", "success")
        return redirect(url_for("doctor_dashboard" if role == "doctor" else "patient_portal"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")

        user_doc = users_collection.find_one({"username": username})
        if not user_doc or not check_password_hash(user_doc.get("password_hash", ""), password):
            flash("Invalid credentials.", "error")
            return redirect(url_for("login"))

        login_user(MongoUser(user_doc))
        flash("Welcome back!", "success")
        return redirect(url_for("doctor_dashboard" if user_doc.get("role") == "doctor" else "patient_portal"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/patient")
@login_required
def patient_portal():
    if not current_user.is_patient:
        flash("Access denied.", "error")
        return redirect(url_for("index"))
    doctors = list(users_collection.find({"role": "doctor"}, {"username": 1, "specialty": 1}))
    return render_template("patient.html", doctors=doctors)


@app.route("/doctor")
@login_required
def doctor_dashboard():
    if not current_user.is_doctor:
        flash("Access denied.", "error")
        return redirect(url_for("index"))
    doctor_id = ObjectId(current_user.id)
    appts = list(appointments_collection.find({"doctor_id": doctor_id}).sort("created_at", -1))
    return render_template("doctor.html", appointments=appts)


# API endpoints
@app.route("/api/doctors")
@login_required
def list_doctors():
    docs = list(users_collection.find({"role": "doctor"}, {"username": 1, "specialty": 1}))
    for d in docs:
        d["_id"] = str(d["_id"])
    return jsonify({"doctors": docs})


@app.route("/api/appointments", methods=["GET", "POST"]) 
@login_required
def appointments():
    if request.method == "POST":
        payload = request.get_json(force=True, silent=True) or {}
        try:
            patient_id = ObjectId(current_user.id)
            patient_name = payload.get("patient_name", "").strip()
            age = int(payload.get("age")) if str(payload.get("age", "")).isdigit() else None
            contact = payload.get("contact", "").strip()
            reason = payload.get("reason", "").strip()
            preferred_date = payload.get("preferred_date")
            preferred_time = payload.get("preferred_time")
            doctor_choice = payload.get("doctor_id")
            doctor_id = ObjectId(doctor_choice) if doctor_choice else None

            if not patient_name or not contact or not reason or not preferred_date or not preferred_time:
                return jsonify({"ok": False, "error": "Missing required fields."}), 400

            appointment_doc = {
                "patient_id": patient_id,
                "patient_name": patient_name,
                "age": age,
                "contact": contact,
                "reason": reason,
                "preferred_date": preferred_date,
                "preferred_time": preferred_time,
                "doctor_id": doctor_id,
                "status": "pending",
                "created_at": datetime.utcnow(),
            }
            result = appointments_collection.insert_one(appointment_doc)
            return jsonify({"ok": True, "appointment_id": str(result.inserted_id)})
        except Exception as ex:
            return jsonify({"ok": False, "error": str(ex)}), 500

    # GET
    if current_user.is_patient:
        appts = list(appointments_collection.find({"patient_id": ObjectId(current_user.id)}).sort("created_at", -1))
    else:
        appts = list(appointments_collection.find({"doctor_id": ObjectId(current_user.id)}).sort("created_at", -1))

    def serialize(doc):
        return {
            "_id": str(doc.get("_id")),
            "patient_name": doc.get("patient_name"),
            "age": doc.get("age"),
            "contact": doc.get("contact"),
            "reason": doc.get("reason"),
            "preferred_date": doc.get("preferred_date"),
            "preferred_time": doc.get("preferred_time"),
            "doctor_id": str(doc.get("doctor_id")) if doc.get("doctor_id") else None,
            "status": doc.get("status"),
            "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
        }

    return jsonify({"appointments": [serialize(a) for a in appts]})


@app.route("/api/appointments/<appointment_id>", methods=["PATCH"]) 
@login_required
def update_appointment(appointment_id):
    if not current_user.is_doctor:
        return jsonify({"ok": False, "error": "Only doctors can update appointments."}), 403
    payload = request.get_json(force=True, silent=True) or {}
    status = payload.get("status")
    if status not in {"pending", "confirmed", "completed", "cancelled"}:
        return jsonify({"ok": False, "error": "Invalid status."}), 400
    result = appointments_collection.update_one(
        {"_id": ObjectId(appointment_id), "doctor_id": ObjectId(current_user.id)},
        {"$set": {"status": status}}
    )
    if result.matched_count == 0:
        return jsonify({"ok": False, "error": "Appointment not found or not assigned to you."}), 404
    return jsonify({"ok": True})


# Error handlers for better UX
@app.errorhandler(404)
def handle_404(_):
    return render_template("index.html", error_message="Page not found"), 404


@app.errorhandler(500)
def handle_500(error):
    return render_template("index.html", error_message=str(error)), 500


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5000"))
    app.run(host=host, port=port, debug=os.getenv("FLASK_ENV") == "development")