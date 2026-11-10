"""Exercise IThenticateClient against a local mock of the iThenticate v2 API.

Run from the repository root:  python -m portal.tests.test_ithenticate
"""
import threading

from flask import Flask, jsonify, request
from werkzeug.serving import make_server

from portal.ithenticate import IThenticateClient

KEY = "test-key"
calls = []
state = {}
mock = Flask("mock_tca")


@mock.before_request
def auth():
    calls.append((request.method, request.path))
    assert request.headers["Authorization"] == f"Bearer {KEY}"
    assert request.headers["X-Turnitin-Integration-Name"]


@mock.get("/api/v1/eula/latest")
def eula():
    return jsonify(version="v1beta", url="https://example.invalid/eula")


@mock.get("/api/v1/features-enabled")
def features():
    return jsonify(similarity={"generation_settings": {"search_repositories": ["INTERNET", "CROSSREF"]}})


@mock.post("/api/v1/submissions")
def create():
    body = request.get_json()
    assert body["owner"] == body["submitter"] and body["eula"]["version"] == "v1beta"
    state["sub"] = {"status": "CREATED"}
    return jsonify(id="sub-1", status="CREATED"), 201


@mock.put("/api/v1/submissions/sub-1/original")
def upload():
    assert request.headers["Content-Type"] == "binary/octet-stream"
    assert "filename=" in request.headers["Content-Disposition"] and request.data == b"%PDF-demo"
    state["sub"]["status"] = "COMPLETE"
    return jsonify(message="uploaded"), 202


@mock.get("/api/v1/submissions/sub-1")
def info():
    return jsonify(id="sub-1", status=state["sub"]["status"])


@mock.put("/api/v1/submissions/sub-1/similarity")
def gen():
    body = request.get_json()
    assert body["indexing_settings"]["add_to_index"] is False
    assert body["generation_settings"]["search_repositories"] == ["INTERNET", "CROSSREF"]
    state["sim"] = 0
    return jsonify(message="requested"), 202


@mock.get("/api/v1/submissions/sub-1/similarity")
def sim():
    state["sim"] += 1
    if state["sim"] < 2:
        return jsonify(status="PROCESSING")
    return jsonify(status="COMPLETE", overall_match_percentage=12)


@mock.post("/api/v1/submissions/sub-1/viewer-url")
def viewer():
    assert request.get_json()["viewer_default_permission_set"] == "LEARNER"
    return jsonify(viewer_url="https://example.invalid/viewer/sub-1")


def main():
    server = make_server("127.0.0.1", 5099, mock)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    c = IThenticateClient("http://127.0.0.1:5099/api", KEY)
    eula_v = c.latest_eula()["version"]
    sid = c.create_submission("owner-1", "report.pdf", {"given_name": "A", "family_name": "B", "email": "a@x"}, eula_v)
    c.upload(sid, "report.pdf", b"%PDF-demo")
    assert c.submission_status(sid) == "COMPLETE"
    c.request_similarity(sid)
    assert c.similarity(sid) == ("PROCESSING", None)
    assert c.similarity(sid) == ("COMPLETE", 12)
    assert c.viewer_url(sid, "owner-1").endswith("sub-1")
    server.shutdown()
    print(f"OK: {len(calls)} API calls in the expected order")
    for m, p in calls:
        print(f"  {m:4s} {p}")


if __name__ == "__main__":
    main()
