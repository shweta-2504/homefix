"""
HomeFix - Appliances Troubleshooting Assistant (Flask backend)

Run:  python app.py      then open  http://127.0.0.1:5000
"""
import re
import os
from functools import wraps
from flask import Flask, jsonify, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db, init_db

app = Flask(__name__)
# Set HOMEFIX_SECRET_KEY in the environment for deployments; this fallback is for local development.
app.secret_key = os.environ.get("HOMEFIX_SECRET_KEY", "homefix-local-dev-key-change-before-deployment")
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Please log in first", "login_required": True}), 401
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped

# After this many unsuccessful attempts on the same problem, suggest a technician
MAX_FAILED_ATTEMPTS = 2


# ------------------------------------------------------------------ pages
@app.route("/")
def index():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("index.html", user_name=session.get("user_name", "User"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("index"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if not name or not email or not password:
            flash("Please fill in every field.", "error")
        elif len(password) < 8:
            flash("Password must be at least 8 characters long.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        else:
            db = get_db()
            try:
                cur = db.execute("INSERT INTO users(name, email, password_hash) VALUES (?, ?, ?)",
                                 (name, email, generate_password_hash(password)))
                db.commit()
                session.clear()
                session["user_id"] = cur.lastrowid
                session["user_name"] = name
                return redirect(url_for("index"))
            except Exception as exc:
                if "UNIQUE" in str(exc).upper():
                    flash("An account with this email already exists. Please log in.", "error")
                else:
                    flash("Could not create your account. Please try again.", "error")
            finally:
                db.close()
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute("SELECT id, name, email, password_hash FROM users WHERE email=?", (email,)).fetchone()
        db.close()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("index"))
        flash("Invalid email or password.", "error")
    return render_template("login.html")


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ------------------------------------------------------ Module 1: Appliances
@app.get("/api/appliances")
@login_required
def appliances():
    db = get_db()
    rows = db.execute("SELECT id, name, icon FROM appliances ORDER BY id").fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


# -------------------------------------------------- Module 2: Symptom detection
@app.get("/api/problems/<int:appliance_id>")
@login_required
def problems(appliance_id):
    db = get_db()
    rows = db.execute(
        "SELECT id, symptom FROM problems WHERE appliance_id=? ORDER BY id", (appliance_id,)
    ).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@app.get("/api/match")
@login_required
def match_problem():
    """Free-text problem entry, e.g. 'my ac is not cooling'. Returns best matches."""
    appliance_id = request.args.get("appliance_id", type=int)
    text = request.args.get("q", "").lower()
    words = set(re.findall(r"[a-z]+", text))
    if not words or not appliance_id:
        return jsonify([])
    db = get_db()
    rows = db.execute(
        "SELECT id, symptom, keywords FROM problems WHERE appliance_id=?", (appliance_id,)
    ).fetchall()
    db.close()
    scored = []
    for r in rows:
        vocab = set(re.findall(r"[a-z]+", (r["symptom"] + " " + r["keywords"]).lower()))
        score = len(words & vocab)
        if score:
            scored.append((score, {"id": r["id"], "symptom": r["symptom"]}))
    scored.sort(key=lambda x: -x[0])
    return jsonify([s[1] for s in scored[:3]])


# ----------------------------------- Module 3 + 4: Engine & Solution/Safety guide
@app.get("/api/troubleshoot/<int:problem_id>")
@login_required
def troubleshoot(problem_id):
    db = get_db()
    prob = db.execute(
        """SELECT p.id, p.symptom, p.risky, a.id AS appliance_id, a.name AS appliance
           FROM problems p JOIN appliances a ON a.id = p.appliance_id WHERE p.id=?""",
        (problem_id,)).fetchone()
    if not prob:
        db.close()
        return jsonify({"error": "Problem not found"}), 404
    rules = db.execute(
        "SELECT id, cause, steps, safety, priority FROM rules WHERE problem_id=? ORDER BY priority",
        (problem_id,)).fetchall()
    fails = db.execute(
        "SELECT COUNT(*) FROM repair_history WHERE user_id=? AND problem_id=? AND resolved=0",
        (session["user_id"], problem_id)).fetchone()[0]
    db.close()
    return jsonify({
        "problem": dict(prob),
        "causes": [{"id": r["id"], "cause": r["cause"], "steps": r["steps"].split("\n"),
                    "safety": r["safety"], "priority": r["priority"]} for r in rules],
        "previous_failed_attempts": fails,
    })


# ------------------------------------- Module 5: History & technician suggestion
@app.post("/api/history")
@login_required
def save_history():
    data = request.get_json(force=True)
    problem_id = data.get("problem_id")
    resolved = 1 if data.get("resolved") else 0
    cause_tried = data.get("cause_tried", "")

    db = get_db()
    prob = db.execute("SELECT appliance_id, risky FROM problems WHERE id=?", (problem_id,)).fetchone()
    if not prob:
        db.close()
        return jsonify({"error": "Problem not found"}), 404

    failed_before = db.execute(
        "SELECT COUNT(*) FROM repair_history WHERE user_id=? AND problem_id=? AND resolved=0", (session["user_id"], problem_id)
    ).fetchone()[0]

    technician = 0
    reason = ""
    if not resolved:
        if prob["risky"]:
            technician, reason = 1, ("This problem can involve electrical or safety risks, so a "
                                     "professional technician should handle it.")
        elif failed_before + 1 >= MAX_FAILED_ATTEMPTS:
            technician, reason = 1, ("The basic steps did not solve this problem more than once. "
                                     "Please call a technician instead of trying risky repairs.")

    db.execute(
        """INSERT INTO repair_history(user_id, appliance_id, problem_id, cause_tried, resolved, technician_suggested)
           VALUES (?,?,?,?,?,?)""",
        (session["user_id"], prob["appliance_id"], problem_id, cause_tried, resolved, technician))
    db.commit()
    db.close()
    return jsonify({"saved": True, "resolved": bool(resolved),
                    "technician_suggested": bool(technician), "reason": reason})


@app.get("/api/history")
@login_required
def history():
    db = get_db()
    rows = db.execute(
        """SELECT h.id, a.name AS appliance, p.symptom, h.cause_tried, h.resolved,
                  h.technician_suggested, h.created_at
           FROM repair_history h
           JOIN appliances a ON a.id = h.appliance_id
           JOIN problems p ON p.id = h.problem_id
           WHERE h.user_id=?
           ORDER BY h.id DESC""", (session["user_id"],)).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@app.delete("/api/history")
@login_required
def clear_history():
    db = get_db()
    db.execute("DELETE FROM repair_history WHERE user_id=?", (session["user_id"],))
    db.commit()
    db.close()
    return jsonify({"cleared": True})


init_db()

if __name__ == "__main__":
    app.run(debug=True)
