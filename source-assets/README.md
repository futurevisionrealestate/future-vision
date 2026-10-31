# FV Management Software — Starter (Phase 1)

Responsive bilingual (Urdu/English) starter for **Future Vision Real Estate Network & Service Center**. Includes FO/dealer application submission, Head Office-only approval, unique IDs after approval, basic dashboard and SQLite schema.

## Current scope
- Responsive browser application for mobile and desktop
- Login with roles: `admin`, `fo`, `dealer`
- FO and dealer registration requests
- Head Office admin can approve/reject; only approvals generate `FVFO-000001` or `FVDE-000002` style IDs
- Urdu/English UI toggle (starter translations; some validation/system messages are bilingual)
- Basic audit logs and password hashing

## Important limitations before real business use
This is a **starter/MVP, not a production-certified system**. Before public deployment, add CSRF protection (for example Flask-WTF), login rate limiting, password reset, admin user management, stronger validation, HTTPS/reverse proxy configuration, database backup/restore tests, privacy/retention policy, monitoring, and a proper production database if traffic grows. SQLite is fine for a pilot with low concurrency; PostgreSQL is preferable for a larger live deployment. Have a developer perform a security review.

## Requirements
- Python 3.10+
- pip
- A computer for initial setup
- For internet access, a hosting account/server and domain (domain is optional for local testing)

## Local setup (Windows)
1. Install Python 3.10 or newer from python.org and enable “Add Python to PATH”.
2. Extract the ZIP to a folder.
3. Open Command Prompt in that folder.
4. Create a virtual environment:
   ```bat
   py -m venv .venv
   .venv\Scripts\activate
   ```
5. Install dependencies:
   ```bat
   pip install -r requirements.txt
   ```
6. Set admin credentials in the same Command Prompt (choose your own strong password):
   ```bat
   set FV_ADMIN_USERNAME=admin
   set FV_ADMIN_PASSWORD=Use-A-Unique-Long-Password-Here
   set FV_SECRET_KEY=replace-this-with-a-long-random-secret
   ```
7. Initialize database and start:
   ```bat
   python -c "from app import init_db; init_db()"
   python app.py
   ```
8. Open `http://127.0.0.1:5000` in your browser and log in using the admin credentials you set.

## Local setup (macOS/Linux)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export FV_ADMIN_USERNAME=admin
export FV_ADMIN_PASSWORD='Use-A-Unique-Long-Password-Here'
export FV_SECRET_KEY='replace-this-with-a-long-random-secret'
python -c "from app import init_db; init_db()"
python app.py
```
Then open `http://127.0.0.1:5000`.

## First pilot workflow
1. Log in as admin.
2. Submit FO and dealer requests (or provision separate accounts through a later admin-user screen).
3. Open **Requests** and approve/reject pending applications.
4. Approved requests receive a unique FV ID.
5. Test mobile view by opening the local server from the same network only after setting up a safe local network address; do not expose the development server to the public internet.

## Database
Tables created on first initialization:
- `users`: accounts, password hashes, roles, active flag
- `registration_requests`: FO/dealer profile/application and approval status
- `audit_logs`: login, submission, and approval/rejection events

Schema is created in `init_db()` in `app.py`.

## Deployment requirements
For public deployment:
- Use a maintained Linux server or reputable Python hosting provider.
- Configure environment variables (`FV_SECRET_KEY`, `FV_ADMIN_USERNAME`, `FV_ADMIN_PASSWORD`, `FV_DATABASE`) using the host's secret settings.
- Set `FV_HTTPS=1` only after HTTPS is correctly configured.
- Run with a production WSGI server such as Gunicorn behind a reverse proxy/platform HTTPS.
- Never run `debug=True` publicly. Keep secrets out of source control.
- Configure encrypted backups, access controls, logging, uptime monitoring, and a restore drill.
- Use a domain and TLS certificate if users need a stable public URL.
- Ensure hosting region, privacy terms, consent, and data retention meet the organization's needs.

## Example production command (Linux)
```bash
pip install gunicorn
gunicorn --workers 2 --bind 127.0.0.1:8000 app:app
```
Run database initialization once before starting the service:
```bash
python -c "from app import init_db; init_db()"
```

## Recommended next development tasks
1. CSRF protection and login rate limiting
2. Admin screen to create FO/dealer login accounts and deactivate users
3. Detailed dealer verification fields and attachment support, if required
4. CSV/Excel export and FO target/performance module
5. PostgreSQL migration and automated backups
6. Automated tests for approval permissions and ID uniqueness
