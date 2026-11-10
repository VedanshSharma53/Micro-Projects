"""Client for the iThenticate v2 API (Turnitin Core API).

Endpoints follow Turnitin's published integration (see the open-source
moodle-plagiarism_turnitinsim plugin). Configure with:
  ITHENTICATE_URL      tenant URL, e.g. https://<tenant>.turnitin.com
  ITHENTICATE_API_KEY  key created by the college's iThenticate administrator
Without a key the portal uses DemoClient, whose results are simulated and
clearly labelled as such in the interface.
"""
import hashlib
import os
import uuid
from datetime import datetime, timezone

import requests

INTEGRATION_NAME = "MLRIT-Originality-Portal"
INTEGRATION_VERSION = "0.2"


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class IThenticateError(RuntimeError):
    pass


class IThenticateClient:
    demo = False

    def __init__(self, base_url, api_key, timeout=60):
        base = base_url.rstrip("/")
        self.base = base[:-4] if base.endswith("/api") else base
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "X-Turnitin-Integration-Name": INTEGRATION_NAME,
            "X-Turnitin-Integration-Version": INTEGRATION_VERSION,
        })

    def _call(self, method, path, **kw):
        if "json" in kw:
            kw.setdefault("headers", {})["Content-Type"] = "application/json"
        r = self.session.request(method, f"{self.base}/api/v1{path}", timeout=self.timeout, **kw)
        if r.status_code >= 400:
            raise IThenticateError(f"{method} {path} -> HTTP {r.status_code}: {r.text[:300]}")
        return r.json() if r.content else {}

    # --- account information -------------------------------------------
    def features(self):
        return self._call("GET", "/features-enabled")

    def latest_eula(self):
        """Returns {'version': ..., 'url': ...}. Students must accept it before submitting."""
        return self._call("GET", "/eula/latest")

    # --- submission lifecycle -------------------------------------------
    def create_submission(self, owner_id, title, owner, eula_version):
        body = {
            "owner": owner_id,
            "submitter": owner_id,
            "title": title,
            "owner_default_permission_set": "LEARNER",
            "submitter_default_permission_set": "LEARNER",
            "metadata": {
                "owners": [owner | {"id": owner_id}],
                "submitter": owner | {"id": owner_id},
                "original_submitted_time": _now_iso(),
            },
        }
        if eula_version:
            body["eula"] = {"accepted_timestamp": _now_iso(), "language": "en-US", "version": eula_version}
        return self._call("POST", "/submissions", json=body)["id"]

    def upload(self, submission_id, filename, data):
        safe = filename.replace('"', "")
        self._call("PUT", f"/submissions/{submission_id}/original", data=data, headers={
            "Content-Type": "binary/octet-stream",
            "Content-Disposition": f'inline; filename="{safe}"'})

    def submission_status(self, submission_id):
        return self._call("GET", f"/submissions/{submission_id}").get("status")

    def request_similarity(self, submission_id):
        repos = (self.features().get("similarity", {}).get("generation_settings", {})
                 .get("search_repositories")) or ["INTERNET", "PUBLICATION", "CROSSREF", "SUBMITTED_WORK"]
        body = {
            "generation_settings": {
                "search_repositories": repos,
                "auto_exclude_self_matching_scope": "ALL",
            },
            # Draft checks are never added to the repository, otherwise the final
            # report would later match the student's own drafts.
            "indexing_settings": {"add_to_index": False},
            "view_settings": {"exclude_quotes": True, "exclude_bibliography": True},
        }
        self._call("PUT", f"/submissions/{submission_id}/similarity", json=body)

    def similarity(self, submission_id):
        """Returns (status, overall_match_percentage or None)."""
        r = self._call("GET", f"/submissions/{submission_id}/similarity")
        return r.get("status"), r.get("overall_match_percentage")

    def viewer_url(self, submission_id, viewer_id, instructor=False):
        body = {"viewer_user_id": viewer_id, "locale": "en-US",
                "viewer_default_permission_set": "INSTRUCTOR" if instructor else "LEARNER"}
        return self._call("POST", f"/submissions/{submission_id}/viewer-url", json=body)["viewer_url"]


class DemoClient:
    """Stand-in used until the college issues an API key. Results are SIMULATED."""
    demo = True
    _store = {}

    def latest_eula(self):
        return {"version": "demo", "url": "https://www.turnitin.com/agreement.asp"}

    def create_submission(self, owner_id, title, owner, eula_version):
        sid = str(uuid.uuid4())
        self._store[sid] = {"polls": 0}
        return sid

    def upload(self, submission_id, filename, data):
        self._store.setdefault(submission_id, {"polls": 0})["hash"] = hashlib.sha256(data).digest()

    def submission_status(self, submission_id):
        return "COMPLETE"

    def request_similarity(self, submission_id):
        self._store.setdefault(submission_id, {"polls": 0})["requested"] = True

    def similarity(self, submission_id):
        s = self._store.get(submission_id)
        if not s:
            return "COMPLETE", 0
        s["polls"] += 1
        if s["polls"] < 2:
            return "PROCESSING", None
        return "COMPLETE", 4 + s.get("hash", b"\0")[0] % 27

    def viewer_url(self, submission_id, viewer_id, instructor=False):
        return None


def make_client():
    url, key = os.environ.get("ITHENTICATE_URL"), os.environ.get("ITHENTICATE_API_KEY")
    if url and key:
        return IThenticateClient(url, key)
    return DemoClient()
