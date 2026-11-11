"""Production entry point for the public demo (gunicorn portal.wsgi:app).

Demo logins are on so reviewers can try the student and faculty views without
Google credentials. Set GOOGLE_CLIENT_ID / ITHENTICATE_API_KEY on the host to
switch those features to the real services.
"""
import os

os.environ.setdefault("DEV_LOGIN", "1")
os.environ.setdefault("SECRET_KEY", "public-demo-change-me")

from portal.app import app, init_db  # noqa: E402  (env must be set before the app reads it)

init_db()
