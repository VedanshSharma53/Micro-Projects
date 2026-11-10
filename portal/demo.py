"""Start the portal in demo mode (no Google or iThenticate keys needed).

Run from the repository root:  python -m portal.demo
Then open http://127.0.0.1:5000 and use the "Demo student" / "Demo faculty" buttons.
"""
import os

os.environ.setdefault("DEV_LOGIN", "1")
os.environ.setdefault("SECRET_KEY", "demo-secret-key")  # same key as the demo data, so existing codes verify

from portal.app import main  # noqa: E402  (env must be set before the app reads it)

if __name__ == "__main__":
    main()
