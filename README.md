# AWS Authenticator

A simple React registration and sign-in UI with a Flask API, SQLite storage, and an Apache/mod_wsgi deployment for Ubuntu 24.04 on EC2. Built to match [Task.md](Task.md).

## What it does

- Register with a username, password, first name, last name, email, and address.
- Optionally upload `Limerick (1).txt` in the registration form.
- Automatically open the profile page after registration and show the saved details.
- Sign out and sign back in with the same username and password.
- Show the uploaded file’s word count and download its original contents.
- Upload or replace the file later from the profile page.

Passwords are hashed. SQLite stores users and file contents; each user can only download their own file. Session cookies are HttpOnly, and POST requests require a CSRF token. Usernames are unique without regard to letter case. Text files must be UTF-8 `.txt` files, at most 1 MB. The word count is the number of whitespace-separated tokens; punctuation stays attached to a word. Download filenames are sanitized, but file bytes are preserved.

The assignment’s actual `Limerick (1).txt` was not in this repository. Download it from your course and select it in the registration form for your demonstration.

## Run locally on Windows

Requirements: Python 3.12 or newer, Node.js 22.12 or newer, and npm. Run these commands in this repository in PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm ci
```

Start Flask in terminal 1:

```powershell
.\.venv\Scripts\python.exe -m flask --app backend.app:create_app run --host 127.0.0.1 --port 5000
```

Start React in terminal 2:

```powershell
npm run dev
```

Open **http://localhost:5173**. Vite forwards `/api` requests to Flask, so no CORS configuration is needed. Stop either server with Ctrl+C.

For Linux/macOS, create the environment with `python3 -m venv .venv` and use `.venv/bin/python` instead of `.\.venv\Scripts\python.exe`.

Local data lives in `instance/users.db`. A development session key is generated in `instance/secret.key` and reused after restarts. Optional settings are documented in [.env.example](.env.example); copy it to `.env` if needed. Neither secrets nor database files belong in GitHub.

## Test and build

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm run build
py -3 tools/package_deploy.py
```

Backend tests cover registration, re-login after an application restart, hashing, validation, CSRF, upload replacement, word counts, downloads, and isolation between users. The last command creates `dist/aws-authenticator.zip` with the React build and server code, excluding passwords, keys, local users, and dependencies.

Optional browser tests run the actual forms on desktop and mobile Chromium:

```powershell
npx playwright install chromium
npm run test:ui
```

These tests use an isolated database under `test-results/`, start their own Flask server on port 5001, and save registration/profile screenshots there.

After building, Flask also serves the entire app directly at **http://127.0.0.1:5000**. Refreshing `/login`, `/register`, or `/profile` works. `npm run preview` only previews the static build; use Flask to exercise authentication.

## Deploy and submit

Follow [the AWS deployment guide](docs/AWS_DEPLOYMENT.md) for EC2 creation, key-pair setup, security-group rules, uploading the ZIP, installing Apache/Flask/SQLite, and the screenshot checklist. The setup uses [AWS’s EC2 launch process](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/EC2_GetStarted.html) and [mod_wsgi daemon mode with a virtual environment](https://modwsgi.readthedocs.io/en/develop/user-guides/virtual-environments.html).

The server installer is [deploy/install.sh](deploy/install.sh); the Apache configuration is [deploy/apache.conf](deploy/apache.conf). No AWS access keys are needed by this app. The EC2 instance serves React and the API from the same public URL.

Use sample personal details and a unique demonstration password on the assignment’s HTTP URL. Enable HTTPS before using real credentials. This is a coursework implementation; a public production service would also need login throttling and account recovery.

## Project layout

```text
frontend/              React forms, profile page, and plain CSS
backend/app.py         Flask API and session handling
backend/schema.sql     SQLite tables (users and uploads)
tests/test_auth.py     Backend integration tests
deploy/                Ubuntu installer and Apache site config
docs/AWS_DEPLOYMENT.md AWS steps and grading checklist
tools/package_deploy.py Deployment ZIP builder
wsgi.py                Apache application entry point
```
