# Loan Payment Record Manager (Flask + CSV)

A small Flask app which stores each customer's loan payment history in a per-user CSV file under `records/`.

Features
- Add new users (creates `<username>.csv` with headers)
- Record daily payments (appends to the user's CSV)
- View payment history (rendered from CSV)
- Download CSV files for each user

Requirements
- Python 3.10+ recommended
- Flask 3.x (requirements.txt includes Flask==3.0.3)

Quick run (local)
1. Create a virtual environment and install deps:

```powershell
python -m venv venv; .\venv\Scripts\Activate.ps1; pip install -r requirements.txt
```

2. Run the app:

```powershell
python app.py
```

3. Visit http://127.0.0.1:5000

Deploying to Render

1. Add `gunicorn` to `requirements.txt` (already included in this repo). This ensures Render installs it.
2. Add a `Procfile` with the content:

```
web: gunicorn app:app
```

3. Push the repository to GitHub.
4. On Render.com create a new Web Service, connect your GitHub repo, choose the branch, and set the Start Command to:

```
gunicorn app:app
```

Render will install dependencies from `requirements.txt` during build.

Notes about persistence
- The app stores CSV files in the `records/` directory on the instance filesystem. Those files remain available across normal requests and sessions. However, Render's web service filesystem is ephemeral across deploys and some restarts: data may be lost when the service is redeployed or when the instance is replaced. This matches your stated requirement "remain accessible between sessions unless the app restarts." If you need stronger persistence across deploys, you would need to use Render Disks or external storage (not included here per your requirements).

Environment variables
- It's a good idea to set a `SECRET_KEY` in your Render service environment settings for production (the app uses `SECRET_KEY` if present). You can set it in Render's Environment tab for your service.

Verify after deploy
- Visit the Render URL and create a user; then record a payment and download the CSV to confirm everything works.

If you want, I can add a `render.yaml` manifest for automatic deploys or include a small health-check route. Which would you prefer?

Notes
- The app stores CSVs in the `records/` directory next to `app.py`.
- No database is used — all persistence is via local CSV files.
- The app uses a simple `sanitize_username` function to build filenames. Avoid duplicate names.

Database
- This repository now includes an optional SQLite database (via Flask-SQLAlchemy). When the app starts it will create `app.db` in the project root and use it to store users and payments.
- CSV download/export is still supported — the app generates the CSV from the database on demand and returns it via `send_file()`.
- If you prefer to keep using per-user CSV files on disk as the primary source of truth, we can add an import script to migrate existing CSVs into the database.
