import io
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from werkzeug.security import check_password_hash

from backend.app import MAX_FILE_BYTES, create_app


class AuthFlowTests(unittest.TestCase):
    def setUp(self):
        temp_root = Path(__file__).resolve().parent.parent / "test-results/backend"
        temp_root.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=temp_root)
        self.db_path = str(Path(self.directory.name) / "users.db")
        self.config = {"TESTING": True, "SECRET_KEY": "test-key", "DATABASE": self.db_path}
        self.app = create_app(self.config)
        self.client = self.app.test_client()
        self.token = self.client.get("/api/session").json["csrf_token"]

    def tearDown(self):
        self.directory.cleanup()

    def post(self, path, **kwargs):
        response = self.client.post(path, headers={"X-CSRF-Token": self.token}, **kwargs)
        if response.is_json and response.json.get("csrf_token"):
            self.token = response.json["csrf_token"]
        return response

    def register(self, username="student", content=None, filename="Limerick (1).txt", **fields):
        data = {
            "username": username, "password": "assignment123", "first_name": "Ada",
            "last_name": "Lovelace", "email": "ada@example.com", "address": "1 Example Street\nBoston, MA",
            **fields,
        }
        if content is not None:
            data["file"] = (io.BytesIO(content), filename)
        return self.post("/api/register", data=data)

    def test_registration_logout_relogin_and_download_persist_after_restart(self):
        content = b"One two\nthree\t four  five.\n"
        response = self.register(content=content)
        self.assertEqual(response.status_code, 201)
        user = response.json["user"]
        self.assertEqual(user["upload"]["word_count"], 5)
        self.assertEqual(user["first_name"], "Ada")
        self.assertEqual(user["last_name"], "Lovelace")
        self.assertEqual(user["email"], "ada@example.com")
        self.assertEqual(user["address"], "1 Example Street\nBoston, MA")
        self.assertNotIn("password", user)
        self.assertNotIn("password_hash", user)
        with closing(sqlite3.connect(self.db_path)) as db:
            password_hash = db.execute("SELECT password_hash FROM users").fetchone()[0]
        self.assertNotEqual(password_hash, "assignment123")
        self.assertTrue(check_password_hash(password_hash, "assignment123"))
        downloaded = self.client.get("/api/download")
        self.assertEqual(downloaded.data, content)
        self.assertIn("attachment", downloaded.headers["Content-Disposition"])
        self.assertEqual(self.post("/api/logout").status_code, 200)
        self.assertEqual(self.client.get("/api/profile").status_code, 401)
        self.assertEqual(self.client.get("/api/download").status_code, 401)
        # Recreate the Flask app to prove data persists outside process memory.
        self.client = create_app(self.config).test_client()
        self.token = self.client.get("/api/session").json["csrf_token"]
        login = self.post("/api/login", json={"username": "STUDENT", "password": "assignment123"})
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json["user"], user)
        self.assertEqual(self.client.get("/api/download").data, content)

    def test_duplicate_username_is_rejected_case_insensitively(self):
        self.assertEqual(self.register().status_code, 201)
        self.assertEqual(self.register(username="STUDENT").status_code, 409)
        with closing(sqlite3.connect(self.db_path)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)

    def test_wrong_password_and_sql_injection_do_not_log_in(self):
        self.register()
        self.post("/api/logout")
        for username, password in [("student", "wrong"), ("' OR 1=1 --", "assignment123")]:
            response = self.post("/api/login", json={"username": username, "password": password})
            self.assertEqual(response.status_code, 401)
            self.assertIsNone(self.client.get("/api/session").json["user"])

    def test_csrf_required_and_rotated_on_login(self):
        old_token = self.token
        self.assertEqual(self.client.post("/api/register", data={}).status_code, 403)
        self.assertEqual(self.register().status_code, 201)
        self.assertNotEqual(old_token, self.token)
        stale = self.client.post("/api/logout", headers={"X-CSRF-Token": old_token})
        self.assertEqual(stale.status_code, 403)
        self.assertIsNotNone(self.client.get("/api/session").json["user"])

    def test_invalid_registration_does_not_store_a_partial_user(self):
        cases = [
            {"password": "short"}, {"email": "not-an-email"}, {"address": " "},
            {"username": "has spaces"}, {"first_name": "x" * 101},
            {"content": b"not text", "filename": "file.exe"},
            {"content": b"\xff\xfe"}, {"content": b"a\x00b"},
            {"content": b"a" * (MAX_FILE_BYTES + 1)},
        ]
        for fields in cases:
            with self.subTest(fields=list(fields)):
                self.assertEqual(self.register(**fields).status_code, 400)
        with closing(sqlite3.connect(self.db_path)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 0)

    def test_upload_replacement_and_empty_file(self):
        self.register(content=b"original text")
        replaced = self.post("/api/upload", data={"file": (io.BytesIO(b"new\nfile\nhere"), "replacement.txt")})
        self.assertEqual(replaced.status_code, 200)
        self.assertEqual(replaced.json["user"]["upload"]["word_count"], 3)
        self.assertEqual(self.client.get("/api/download").data, b"new\nfile\nhere")
        self.post("/api/upload", data={"file": (io.BytesIO(b""), "empty.txt")})
        self.assertEqual(self.client.get("/api/profile").json["user"]["upload"]["word_count"], 0)
        self.assertEqual(self.client.get("/api/download").data, b"")

    def test_users_can_only_access_their_own_files(self):
        self.register(username="alice", content=b"Alice private file")
        self.post("/api/logout")
        self.register(username="bob", content=b"Bob private file")
        self.assertEqual(self.client.get("/api/download?user_id=1").data, b"Bob private file")
        self.assertEqual(self.client.get("/api/profile?username=alice").json["user"]["username"], "bob")

    def test_utf8_bom_and_whitespace_count(self):
        response = self.register(content="\ufeffHello\t世界\r\nthree  four".encode("utf-8"))
        self.assertEqual(response.json["user"]["upload"]["word_count"], 4)

    def test_missing_upload_and_body_limit(self):
        self.register()
        self.assertEqual(self.client.get("/api/download").status_code, 404)
        self.assertEqual(self.post("/api/upload", data={}).status_code, 400)
        response = self.post("/api/upload", data={"file": (io.BytesIO(b"x" * (MAX_FILE_BYTES * 2)), "big.txt")})
        self.assertEqual(response.status_code, 413)
        self.assertIn("error", response.json)

    def test_json_errors_and_session_cookie_flags(self):
        self.assertEqual(self.client.get("/api/unknown").status_code, 404)
        self.assertIn("error", self.client.get("/api/unknown").json)
        self.assertEqual(self.post("/api/login", json=["invalid"]).status_code, 400)
        response = self.register()
        cookie = response.headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)
        self.assertEqual(self.client.get("/api/profile").headers["Cache-Control"], "no-store")

    def test_frontend_routes_and_private_paths(self):
        dist = Path(self.directory.name) / "ui"
        (dist / "assets").mkdir(parents=True)
        (dist / "index.html").write_text("<html>React UI</html>", encoding="utf-8")
        (dist / "assets/app.js").write_text("console.log('test')", encoding="utf-8")
        self.app.config["FRONTEND_DIST"] = str(dist)
        for route in ["/", "/register", "/login", "/profile"]:
            with self.client.get(route) as response:
                self.assertEqual(response.status_code, 200)
        with self.client.get("/assets/app.js") as response:
            self.assertEqual(response.status_code, 200)
        for route in ["/instance/users.db", "/backend/app.py", "/.env", "/assets/../../users.db"]:
            self.assertEqual(self.client.get(route).status_code, 404)


if __name__ == "__main__":
    unittest.main()
