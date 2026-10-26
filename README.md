# HomeFix – Appliances Troubleshooting Assistant

Flask + SQLite + HTML/CSS/JavaScript project.

## Run
```
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000 in your browser. You will be redirected to the login page. Create an account first; the database (`homefix.db`) and user table are created automatically on first run.

For production, set a strong random `HOMEFIX_SECRET_KEY` environment variable before starting the app. The built-in default key is for local development only.

## Modules
| Module | Where |
|---|---|
| 1. Appliance Selection | `/api/appliances`, step 1 of the UI |
| 2. Problem / Symptom Detection | `/api/problems/<id>`, `/api/match` (free-text), step 2 |
| 3. Troubleshooting Engine | `/api/troubleshoot/<problem_id>` matches stored rules (`rules` table) |
| 4. Solution & Safety Guide | steps + safety warning shown for every cause |
| 5. Repair History & Technician Suggestion | `/api/history`; technician advised after 2 failed attempts or for risky problems |

## Files
- `app.py` – Flask routes and technician logic
- `database.py` – SQLite schema and the appliance/problem/rule knowledge base
- `templates/login.html`, `templates/register.html` – authentication pages
- `templates/index.html`, `static/style.css`, `static/script.js` – front end
