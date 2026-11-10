"""Project Repository & Similarity Detection Portal (prototype).

Run:  python -m portal.app        (from the repository root)
Env:
  GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET  Google OAuth client (Web application)
  ALLOWED_DOMAIN     only emails of this domain may sign in (default mlrit.ac.in)
  FACULTY_EMAILS     comma-separated emails that get the faculty role
  SECRET_KEY         Flask session + report signing key
  DEV_LOGIN=1        enables /dev-login for local demos without Google
"""
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from datetime import datetime
from functools import wraps
from pathlib import Path

import numpy as np
from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   send_from_directory, session, url_for)

from .ithenticate import IThenticateError, make_client
from .similarity import DOMAINS, band, engine

ROOT = Path(__file__).resolve().parent
SITE_ROOT = ROOT.parent
DB_PATH = ROOT / "instance" / "portal.db"

app = Flask(__name__, template_folder=str(ROOT / "templates"))
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
ALLOWED_DOMAIN = os.environ.get("ALLOWED_DOMAIN", "mlrit.ac.in")
FACULTY_EMAILS = {e.strip().lower() for e in os.environ.get("FACULTY_EMAILS", "").split(",") if e.strip()}
DEV_LOGIN = os.environ.get("DEV_LOGIN") == "1"
DOC_CHECKS_PER_WEEK = int(os.environ.get("DOC_CHECKS_PER_WEEK", "3"))
MAX_UPLOAD_MB = 20
ALLOWED_EXT = {".pdf", ".docx", ".doc", ".txt", ".rtf", ".odt"}
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
tii = make_client()

oauth = None
if os.environ.get("GOOGLE_CLIENT_ID"):
    from authlib.integrations.flask_client import OAuth
    oauth = OAuth(app)
    oauth.register(
        name="google",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT, picture TEXT,
  role TEXT NOT NULL DEFAULT 'student', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS projects(
  id INTEGER PRIMARY KEY, title TEXT NOT NULL, abstract TEXT, domain TEXT,
  year INTEGER, team TEXT, status TEXT NOT NULL DEFAULT 'approved',
  source TEXT NOT NULL DEFAULT 'seed', owner_id INTEGER REFERENCES users(id),
  report_code TEXT, embedding BLOB NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS checks(
  id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, user_id INTEGER REFERENCES users(id),
  title TEXT NOT NULL, abstract TEXT, result TEXT NOT NULL, top_score REAL,
  originality REAL, band TEXT, domain TEXT, digest TEXT NOT NULL,
  project_id INTEGER REFERENCES projects(id), created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS doc_checks(
  id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, user_id INTEGER NOT NULL REFERENCES users(id),
  filename TEXT NOT NULL, sha256 TEXT NOT NULL, size INTEGER NOT NULL, tii_id TEXT,
  status TEXT NOT NULL, score REAL, error TEXT, demo INTEGER NOT NULL DEFAULT 0,
  digest TEXT, created_at TEXT NOT NULL, completed_at TEXT);
CREATE TABLE IF NOT EXISTS reviews(
  id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id),
  faculty_id INTEGER NOT NULL REFERENCES users(id), decision TEXT NOT NULL,
  comment TEXT, created_at TEXT NOT NULL);
"""


# ---------------------------------------------------------------- database
def db():
    if "db" not in g:
        DB_PATH.parent.mkdir(exist_ok=True)
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def now():
    return datetime.now().isoformat(timespec="seconds")


def init_db():
    with app.app_context():
        conn = db()
        conn.executescript(SCHEMA)
        if conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0:
            from .data.seed import REPOSITORY, SITE_PROJECTS
            from .similarity import combined
            vecs = engine.embed(combined(t, a) for _d, t, a in REPOSITORY)
            for i, ((domain, title, abstract), vec) in enumerate(zip(REPOSITORY, vecs)):
                conn.execute(
                    "INSERT INTO projects(title, abstract, domain, year, status, source, embedding, created_at)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    (title, abstract, domain, 2019 + i % 7, "approved",
                     "site" if title in SITE_PROJECTS else "seed", vec.tobytes(), now()))
            conn.commit()


def repository(include_pending=True):
    statuses = ("approved", "pending") if include_pending else ("approved",)
    rows = db().execute(
        f"SELECT * FROM projects WHERE status IN ({','.join('?' * len(statuses))})", statuses).fetchall()
    return [dict(r) | {"embedding": np.frombuffer(r["embedding"], dtype=np.float32)} for r in rows]


# ------------------------------------------------------------------- auth
def current_user():
    uid = session.get("uid")
    if uid is None:
        return None
    return db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()


@app.context_processor
def inject():
    return {"me": current_user(), "dev_login": DEV_LOGIN, "google_enabled": oauth is not None,
            "allowed_domain": ALLOWED_DOMAIN, "tii_demo": tii.demo}


def login_required(role=None):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            user = current_user()
            if user is None:
                return redirect(url_for("login", next=request.full_path))
            if role and user["role"] != role:
                abort(403)
            return fn(*a, **kw)
        return wrapper
    return deco


def sign_in(email, name, picture=None):
    email = email.lower()
    conn = db()
    row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    role = "faculty" if email in FACULTY_EMAILS else None
    if row is None:
        conn.execute("INSERT INTO users(email, name, picture, role, created_at) VALUES (?,?,?,?,?)",
                     (email, name, picture, role or "student", now()))
    else:
        conn.execute("UPDATE users SET name=?, picture=?, role=COALESCE(?, role) WHERE email=?",
                     (name, picture, role, email))
    conn.commit()
    session.clear()
    session["uid"] = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()["id"]


def safe_next(target):
    return target if target and target.startswith("/") and not target.startswith("//") else None


@app.route("/login")
def login():
    session["next"] = safe_next(request.args.get("next"))
    return render_template("login.html")


@app.route("/auth/google")
def auth_google():
    if oauth is None:
        abort(404)
    redirect_uri = url_for("auth_callback", _external=True)
    # hd= only pre-selects the college account; the domain is enforced in the callback.
    return oauth.google.authorize_redirect(redirect_uri, hd=ALLOWED_DOMAIN, prompt="select_account")


@app.route("/auth/callback")
def auth_callback():
    if oauth is None:
        abort(404)
    token = oauth.google.authorize_access_token()
    info = token.get("userinfo") or {}
    email = (info.get("email") or "").lower()
    if not info.get("email_verified") or not email.endswith("@" + ALLOWED_DOMAIN) or info.get("hd") != ALLOWED_DOMAIN:
        flash(f"Please sign in with your @{ALLOWED_DOMAIN} college account.", "danger")
        return redirect(url_for("login"))
    nxt = session.get("next")
    sign_in(email, info.get("name") or email, info.get("picture"))
    return redirect(nxt or url_for("home"))


@app.route("/dev-login")
def dev_login():
    if not DEV_LOGIN:
        abort(404)
    who = request.args.get("as", "student")
    if who == "faculty":
        FACULTY_EMAILS.add(f"kamesh.faculty@{ALLOWED_DOMAIN}")
        sign_in(f"kamesh.faculty@{ALLOWED_DOMAIN}", "Dr. D.B.K. Kamesh (demo)")
    else:
        sign_in(f"23r21a05ex@{ALLOWED_DOMAIN}", "Vedansh (demo student)")
    return redirect(safe_next(request.args.get("next")) or url_for("home"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ----------------------------------------------------------------- report
def digest_for(code, title, abstract, top_score, matches, created_at):
    payload = json.dumps({"code": code, "title": title, "abstract": abstract, "top": top_score,
                          "matches": [(m["id"], m["semantic"]) for m in matches],
                          "at": created_at}, sort_keys=True)
    return hmac.new(app.config["SECRET_KEY"].encode(), payload.encode(), hashlib.sha256).hexdigest()


def new_code():
    return f"OR-{datetime.now():%y%m}-{secrets.token_hex(3).upper()}"


def load_check(code):
    row = db().execute("SELECT * FROM checks WHERE code=?", (code,)).fetchone()
    if row is None:
        abort(404)
    return row, json.loads(row["result"])


# ----------------------------------------------------------------- routes
@app.route("/assets/<folder>/<path:name>")
def assets(folder, name):
    if folder not in {"css", "js", "fonts", "images"}:
        abort(404)
    return send_from_directory(SITE_ROOT / folder, name)


@app.route("/")
def home():
    user = current_user()
    if user is None:
        return redirect(url_for("login"))
    return redirect(url_for("faculty" if user["role"] == "faculty" else "check"))


@app.route("/check", methods=["GET", "POST"])
@login_required()
def check():
    if request.method == "GET":
        return render_template("check.html")
    title = request.form.get("title", "").strip()
    abstract = request.form.get("abstract", "").strip()
    if len(title) < 5 or len(abstract.split()) < 15:
        flash("Enter a title and an abstract of at least 15 words.", "warning")
        return render_template("check.html", title=title, abstract=abstract)
    user = current_user()
    records = [r for r in repository() if r["owner_id"] != user["id"]]
    res = engine.check(title, abstract, records)
    res.pop("embedding")
    code, created = new_code(), now()
    digest = digest_for(code, title, abstract, res["top_score"], res["matches"], created)
    db().execute(
        "INSERT INTO checks(code, user_id, title, abstract, result, top_score, originality, band, domain, digest, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (code, user["id"], title, abstract, json.dumps(res), res["top_score"], res["originality"],
         res["band"], res["domain"], digest, created))
    db().commit()
    return redirect(url_for("report", code=code))


@app.route("/report/<code>")
@login_required()
def report(code):
    row, res = load_check(code)
    user = current_user()
    if user["role"] != "faculty" and row["user_id"] != user["id"]:
        abort(403)
    return render_template("report.html", c=row, r=res)


@app.route("/report/<code>/submit", methods=["POST"])
@login_required()
def submit(code):
    row, res = load_check(code)
    user = current_user()
    if row["user_id"] != user["id"] or row["project_id"]:
        abort(403)
    from .similarity import combined
    vec = engine.embed([combined(row["title"], row["abstract"])])[0]
    cur = db().execute(
        "INSERT INTO projects(title, abstract, domain, year, team, status, source, owner_id, report_code, embedding, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (row["title"], row["abstract"], res["domain"], datetime.now().year,
         request.form.get("team", "").strip(), "pending", "student", user["id"], code, vec.tobytes(), now()))
    db().execute("UPDATE checks SET project_id=? WHERE id=?", (cur.lastrowid, row["id"]))
    db().commit()
    flash("Submitted to faculty for review. Your report code has been attached.", "success")
    return redirect(url_for("mine"))


# ------------------------------------------------- full-document check (iThenticate)
def doc_digest(code, sha, score, completed_at):
    # float(): SQLite returns REAL, so sign the same representation that is read back
    payload = json.dumps({"code": code, "sha256": sha, "score": float(score), "at": completed_at}, sort_keys=True)
    return hmac.new(app.config["SECRET_KEY"].encode(), payload.encode(), hashlib.sha256).hexdigest()


def checks_this_week(user_id):
    return db().execute("SELECT COUNT(*) FROM doc_checks WHERE user_id=? AND replace(created_at,'T',' ') >= datetime('now','-7 days','localtime')",
                        (user_id,)).fetchone()[0]


def tii_owner_id(user):
    # A stable pseudonymous id; iThenticate never needs our database ids.
    return hashlib.sha256(f"{app.config['SECRET_KEY']}:{user['email']}".encode()).hexdigest()[:32]


def advance(doc):
    """Move a document check one step through iThenticate's asynchronous pipeline."""
    if doc["status"] in ("COMPLETE", "ERROR"):
        return
    try:
        status = doc["status"]
        if status == "PROCESSING" and tii.submission_status(doc["tii_id"]) == "COMPLETE":
            tii.request_similarity(doc["tii_id"])
            status = "SIMILARITY"
        if status == "SIMILARITY":
            s, score = tii.similarity(doc["tii_id"])
            if s == "COMPLETE":
                done = now()
                db().execute("UPDATE doc_checks SET status='COMPLETE', score=?, completed_at=?, digest=? WHERE id=?",
                             (score, done, doc_digest(doc["code"], doc["sha256"], score, done), doc["id"]))
                db().commit()
                return
        db().execute("UPDATE doc_checks SET status=? WHERE id=?", (status, doc["id"]))
        db().commit()
    except (IThenticateError, OSError) as exc:
        db().execute("UPDATE doc_checks SET status='ERROR', error=? WHERE id=?", (str(exc)[:500], doc["id"]))
        db().commit()


@app.route("/document-check", methods=["GET", "POST"])
@login_required()
def doc_check():
    user = current_user()
    used = checks_this_week(user["id"])
    eula = tii.latest_eula()
    if request.method == "POST":
        f = request.files.get("file")
        ext = Path(f.filename).suffix.lower() if f and f.filename else ""
        if not f or ext not in ALLOWED_EXT:
            flash("Upload a PDF, Word, ODT, RTF or text file.", "warning")
        elif not request.form.get("eula"):
            flash("You must accept the iThenticate user agreement before checking a document.", "warning")
        elif used >= DOC_CHECKS_PER_WEEK:
            flash(f"Weekly limit reached ({DOC_CHECKS_PER_WEEK} checks). This protects the college's iThenticate quota.", "danger")
        else:
            data = f.read()
            code = f"DC-{datetime.now():%y%m}-{secrets.token_hex(3).upper()}"
            first, _, last = (user["name"] or user["email"]).partition(" ")
            try:
                sid = tii.create_submission(tii_owner_id(user), f.filename,
                                            {"given_name": first, "family_name": last or "-", "email": user["email"]},
                                            eula.get("version"))
                tii.upload(sid, f.filename, data)
                status, error = "PROCESSING", None
            except (IThenticateError, OSError) as exc:
                sid, status, error = None, "ERROR", str(exc)[:500]
            # The file itself is not stored by the portal; only its fingerprint.
            db().execute(
                "INSERT INTO doc_checks(code, user_id, filename, sha256, size, tii_id, status, error, demo, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (code, user["id"], f.filename, hashlib.sha256(data).hexdigest(), len(data), sid, status, error,
                 int(tii.demo), now()))
            db().commit()
            return redirect(url_for("doc_report", code=code))
    docs = db().execute("SELECT * FROM doc_checks WHERE user_id=? ORDER BY id DESC", (user["id"],)).fetchall()
    return render_template("doc_check.html", used=used, limit=DOC_CHECKS_PER_WEEK, eula=eula, docs=docs,
                           max_mb=MAX_UPLOAD_MB, exts=", ".join(sorted(ALLOWED_EXT)))


def load_doc(code):
    doc = db().execute("SELECT d.*, u.name, u.email FROM doc_checks d JOIN users u ON u.id=d.user_id WHERE code=?",
                       (code,)).fetchone()
    if doc is None:
        abort(404)
    return doc


@app.route("/document-check/<code>")
@login_required()
def doc_report(code):
    doc = load_doc(code)
    user = current_user()
    if user["role"] != "faculty" and doc["user_id"] != user["id"]:
        abort(403)
    advance(doc)
    return render_template("doc_report.html", d=load_doc(code))


@app.route("/document-check/<code>/viewer")
@login_required()
def doc_viewer(code):
    doc = load_doc(code)
    user = current_user()
    if user["role"] != "faculty" and doc["user_id"] != user["id"]:
        abort(403)
    url = tii.viewer_url(doc["tii_id"], tii_owner_id(user), instructor=user["role"] == "faculty")
    if not url:
        flash("The full iThenticate report viewer is available once the college's API key is configured.", "info")
        return redirect(url_for("doc_report", code=code))
    return redirect(url)


@app.errorhandler(413)
def too_large(_e):
    flash(f"File is larger than {MAX_UPLOAD_MB} MB.", "warning")
    return redirect(url_for("doc_check"))


@app.route("/my")
@login_required()
def mine():
    user = current_user()
    checks = db().execute(
        "SELECT c.*, p.status FROM checks c LEFT JOIN projects p ON p.id=c.project_id"
        " WHERE c.user_id=? ORDER BY c.id DESC", (user["id"],)).fetchall()
    docs = db().execute("SELECT * FROM doc_checks WHERE user_id=? ORDER BY id DESC", (user["id"],)).fetchall()
    return render_template("mine.html", checks=checks, docs=docs)


@app.route("/search")
@login_required()
def search():
    q = request.args.get("q", "").strip()
    domain = request.args.get("domain", "")
    results = []
    if q:
        records = repository(include_pending=False)
        if domain:
            records = [r for r in records if r["domain"] == domain]
        if records:
            qv = engine.embed([q])[0]
            sem = np.stack([r["embedding"] for r in records]) @ qv
            kw = [q.lower() in (r["title"] + " " + (r["abstract"] or "")).lower() for r in records]
            order = np.argsort(-(sem + 0.15 * np.array(kw)))[:10]
            results = [records[i] | {"score": float(sem[i]), "keyword": kw[i]} for i in order]
    return render_template("search.html", q=q, domain=domain, results=results, domains=list(DOMAINS))


@app.route("/insights")
@login_required()
def insights():
    rows = db().execute(
        "SELECT domain, COUNT(*) n FROM projects WHERE status IN ('approved','pending') GROUP BY domain ORDER BY n DESC").fetchall()
    bands = db().execute("SELECT band, COUNT(*) n FROM checks GROUP BY band").fetchall()
    return render_template("insights.html", rows=rows, bands=bands,
                           total=sum(r["n"] for r in rows))


@app.route("/faculty")
@login_required(role="faculty")
def faculty():
    pending = db().execute(
        "SELECT p.*, u.name student, c.top_score, c.originality, c.band, c.code FROM projects p"
        " JOIN users u ON u.id=p.owner_id LEFT JOIN checks c ON c.code=p.report_code"
        " WHERE p.source='student' ORDER BY CASE p.status WHEN 'pending' THEN 0 ELSE 1 END, p.id DESC").fetchall()
    return render_template("faculty.html", rows=pending)


@app.route("/faculty/review/<int:pid>", methods=["GET", "POST"])
@login_required(role="faculty")
def review(pid):
    proj = db().execute("SELECT p.*, u.name student, u.email FROM projects p JOIN users u ON u.id=p.owner_id"
                        " WHERE p.id=?", (pid,)).fetchone()
    if proj is None:
        abort(404)
    if request.method == "POST":
        decision = request.form.get("decision")
        if decision not in {"approved", "rejected", "revision"}:
            abort(400)
        db().execute("INSERT INTO reviews(project_id, faculty_id, decision, comment, created_at) VALUES (?,?,?,?,?)",
                     (pid, current_user()["id"], decision, request.form.get("comment", ""), now()))
        db().execute("UPDATE projects SET status=? WHERE id=?", (decision, pid))
        db().commit()
        flash(f"Decision recorded: {decision}.", "success")
        return redirect(url_for("faculty"))
    row, res = load_check(proj["report_code"])
    reviews = db().execute("SELECT r.*, u.name FROM reviews r JOIN users u ON u.id=r.faculty_id"
                           " WHERE project_id=? ORDER BY r.id", (pid,)).fetchall()
    docs = db().execute("SELECT * FROM doc_checks WHERE user_id=? AND status='COMPLETE' ORDER BY id DESC LIMIT 3",
                        (proj["owner_id"],)).fetchall()
    return render_template("review.html", p=proj, c=row, r=res, reviews=reviews, docs=docs)


@app.route("/verify")
def verify():
    code = request.args.get("code", "").strip().upper()
    row, res, valid, status = None, None, None, None
    if code.startswith("DC-"):
        doc = db().execute("SELECT d.*, u.name FROM doc_checks d JOIN users u ON u.id=d.user_id WHERE code=?",
                           (code,)).fetchone()
        if doc and doc["status"] == "COMPLETE":
            valid = hmac.compare_digest(doc["digest"] or "",
                                        doc_digest(doc["code"], doc["sha256"], doc["score"], doc["completed_at"]))
        return render_template("verify.html", code=code, doc=doc, valid=valid, c=None)
    if code:
        row = db().execute("SELECT * FROM checks WHERE code=?", (code,)).fetchone()
        if row:
            res = json.loads(row["result"])
            valid = hmac.compare_digest(
                row["digest"], digest_for(row["code"], row["title"], row["abstract"], res["top_score"],
                                          res["matches"], row["created_at"]))
            if row["project_id"]:
                status = db().execute("SELECT status FROM projects WHERE id=?", (row["project_id"],)).fetchone()["status"]
    return render_template("verify.html", code=code, c=row, r=res, valid=valid, status=status)


@app.template_filter("pct")
def pct(x):
    return f"{max(0.0, float(x)) * 100:.1f}%"


app.jinja_env.globals["band"] = band


def main():
    init_db()
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=False)


if __name__ == "__main__":
    main()
