"""Registration, cookie sessions, and private text-file storage in SQLite."""

import hmac
import io
import os
import re
import secrets
import sqlite3
from datetime import timedelta
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, g, jsonify, request, send_file, send_from_directory, session
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

ROOT = Path(__file__).resolve().parent.parent
MAX_FILE_BYTES = 1024 * 1024


class ValidationError(ValueError):
    pass


def create_app(test_config=None):
    load_dotenv(ROOT / ".env")
    app = Flask(__name__, static_folder=None, instance_path=str(ROOT / "instance"))
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY"),
        DATABASE=str(Path(os.getenv("DATABASE_PATH") or ROOT / "instance/users.db").resolve()),
        FRONTEND_DIST=str(ROOT / "frontend/dist"),
        MAX_CONTENT_LENGTH=2 * MAX_FILE_BYTES,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    )
    if test_config:
        app.config.update(test_config)
    if not app.config["SECRET_KEY"]:
        if os.getenv("APP_ENV") == "production":
            raise RuntimeError("Set SECRET_KEY before running in production.")
        # Persist the development key so restarts do not invalidate sessions.
        key_path = Path(app.instance_path) / "secret.key"
        key_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with key_path.open("x", encoding="utf-8") as key_file:
                key_file.write(secrets.token_hex(32))
            key_path.chmod(0o600)
        except FileExistsError:
            pass
        app.config["SECRET_KEY"] = key_path.read_text(encoding="utf-8").strip()

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"], timeout=10)
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
        return g.db

    @app.teardown_appcontext
    def close_db(_error):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    def init_db():
        Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
        db = get_db()
        db.execute("PRAGMA journal_mode = WAL")
        db.executescript((ROOT / "backend/schema.sql").read_text(encoding="utf-8"))
        db.commit()

    @app.cli.command("init-db")
    def init_db_command():
        """Create tables without deleting existing users or files."""
        init_db()
        print(f"Initialized SQLite tables at {app.config['DATABASE']}")

    with app.app_context():
        init_db()

    def current_user():
        user_id = session.get("user_id")
        if user_id is None:
            return None
        row = get_db().execute(
            "SELECT id, username, first_name, last_name, email, address FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        user = dict(row)
        upload = get_db().execute(
            "SELECT filename, word_count, uploaded_at FROM uploads WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        user["upload"] = dict(upload) if upload else None
        return user

    def csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        return session["csrf_token"]

    def start_session(user_id):
        session.clear()
        session["user_id"] = user_id
        session.permanent = True
        return jsonify(user=current_user(), csrf_token=csrf_token())

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if current_user() is None:
                return jsonify(error="Please sign in to continue."), 401
            return view(*args, **kwargs)
        return wrapped

    @app.before_request
    def check_csrf():
        if request.path.startswith("/api/") and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            expected = session.get("csrf_token", "")
            supplied = request.headers.get("X-CSRF-Token", "")
            if not expected or not hmac.compare_digest(expected.encode(), supplied.encode()):
                return jsonify(error="Your session expired. Refresh the page and try again."), 403

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(ValidationError)
    def handle_validation(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        if request.path.startswith("/api/"):
            message = "The upload is too large. Choose a text file of 1 MB or less." if error.code == 413 else error.description
            return jsonify(error=message), error.code
        return error

    def read_upload(file):
        if file is None or not file.filename:
            raise ValidationError("Choose a .txt file to upload.")
        filename = secure_filename(file.filename.replace("\\", "/").rsplit("/", 1)[-1])
        if not filename.lower().endswith(".txt"):
            raise ValidationError("Please upload a .txt file.")
        if len(filename) > 200:
            raise ValidationError("Please use a shorter filename (200 characters or less).")
        content = file.stream.read(MAX_FILE_BYTES + 1)
        if len(content) > MAX_FILE_BYTES:
            raise ValidationError("The upload is too large. Choose a text file of 1 MB or less.")
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ValidationError("Save the text file with UTF-8 encoding and try again.") from None
        if "\x00" in text:
            raise ValidationError("The file must contain plain text.")
        return filename, content, len(text.split())

    def store_upload(db, user_id, upload):
        db.execute(
            """INSERT INTO uploads (user_id, filename, content, word_count) VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET filename=excluded.filename,
               content=excluded.content, word_count=excluded.word_count, uploaded_at=CURRENT_TIMESTAMP""",
            (user_id, *upload),
        )

    @app.get("/api/health")
    def health():
        get_db().execute("SELECT 1 FROM users LIMIT 1")
        return jsonify(status="ok")

    @app.get("/api/session")
    def get_session():
        return jsonify(user=current_user(), csrf_token=csrf_token())

    @app.post("/api/register")
    def register():
        limits = {"username": 30, "first_name": 100, "last_name": 100, "email": 254, "address": 500}
        fields = {}
        for name, limit in limits.items():
            value = request.form.get(name, "").strip()
            if not value or len(value) > limit:
                raise ValidationError(f"{name.replace('_', ' ').capitalize()} is required (up to {limit} characters).")
            fields[name] = value
        if not re.fullmatch(r"[A-Za-z0-9_.-]{3,30}", fields["username"]):
            raise ValidationError("Username must be 3–30 letters, numbers, dots, dashes, or underscores.")
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", fields["email"]):
            raise ValidationError("Enter a valid email address.")
        password = request.form.get("password", "")
        if not 8 <= len(password) <= 128:
            raise ValidationError("Password must be between 8 and 128 characters.")
        file = request.files.get("file")
        upload = read_upload(file) if file and file.filename else None
        db = get_db()
        try:
            with db:
                cursor = db.execute(
                    """INSERT INTO users (username, password_hash, first_name, last_name, email, address)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (fields["username"], generate_password_hash(password, method="pbkdf2:sha256:600000"),
                     fields["first_name"], fields["last_name"], fields["email"], fields["address"]),
                )
                user_id = cursor.lastrowid
                if upload:
                    store_upload(db, user_id, upload)
        except sqlite3.IntegrityError:
            return jsonify(error="That username is already taken. Choose another or sign in."), 409
        return start_session(user_id), 201

    @app.post("/api/login")
    def login():
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            raise ValidationError("Enter a username and password.")
        username = data.get("username", "")
        password = data.get("password", "")
        if not isinstance(username, str) or not isinstance(password, str) or len(username) > 30 or len(password) > 128:
            raise ValidationError("Enter a valid username and password.")
        user = get_db().execute(
            "SELECT id, password_hash FROM users WHERE username = ?", (username.strip(),)
        ).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            return jsonify(error="Incorrect username or password."), 401
        return start_session(user["id"])

    @app.post("/api/logout")
    def logout():
        session.clear()
        return jsonify(user=None, csrf_token=csrf_token())

    @app.get("/api/profile")
    @login_required
    def profile():
        return jsonify(user=current_user())

    @app.post("/api/upload")
    @login_required
    def upload_file():
        upload = read_upload(request.files.get("file"))
        db = get_db()
        with db:
            store_upload(db, session["user_id"], upload)
        return jsonify(user=current_user())

    @app.get("/api/download")
    @login_required
    def download_file():
        upload = get_db().execute(
            "SELECT filename, content FROM uploads WHERE user_id = ?", (session["user_id"],)
        ).fetchone()
        if upload is None:
            return jsonify(error="You have not uploaded a file yet."), 404
        return send_file(io.BytesIO(upload["content"]), mimetype="text/plain", as_attachment=True,
                         download_name=upload["filename"], max_age=0)

    @app.get("/")
    @app.get("/register")
    @app.get("/login")
    @app.get("/profile")
    def frontend():
        dist = Path(app.config["FRONTEND_DIST"])
        if not (dist / "index.html").is_file():
            return "Build the React UI with npm run build, or open http://localhost:5173 during development.", 503
        return send_from_directory(dist, "index.html", max_age=0)

    @app.get("/assets/<path:filename>")
    def frontend_asset(filename):
        return send_from_directory(Path(app.config["FRONTEND_DIST"]) / "assets", filename)

    return app
