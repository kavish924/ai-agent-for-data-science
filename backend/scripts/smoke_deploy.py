"""Deployment smoke test (Spec 11 FR-DP-23, AC-5/7/15). Standard library only.

Drives a running deployment through its public entry point (the frontend), with the
shared password:

    python scripts/smoke_deploy.py --base http://127.0.0.1:3000 --user ci --password ci-password \
        --session-file /tmp/smoke_session
    # ...restart the backend, then:
    python scripts/smoke_deploy.py --base ... --user ... --password ... \
        --session-file /tmp/smoke_session --check-session

Also usable against the real Render URL after a deploy (runbook, docs/deployment.md).
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import random
import sys
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from pathlib import Path


class Client:
    def __init__(self, base: str, user: str | None, password: str | None, timeout: float):
        self.base = base.rstrip("/")
        self.timeout = timeout
        self.auth = (
            "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode() if user is not None else None
        )

    def call(self, method: str, path: str, *, body: bytes | None = None, content_type: str | None = None,
             auth: bool = True) -> tuple[int, dict, bytes]:
        request = urllib.request.Request(self.base + path, method=method, data=body)
        if auth and self.auth:
            request.add_header("Authorization", self.auth)
        if content_type:
            request.add_header("Content-Type", content_type)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.status, {k.lower(): v for k, v in response.headers.items()}, response.read()
        except urllib.error.HTTPError as error:
            return error.code, {k.lower(): v for k, v in error.headers.items()}, error.read()

    def json(self, method: str, path: str, payload: object | None = None, expect: tuple[int, ...] = (200,)):
        body = None if payload is None else json.dumps(payload).encode()
        status, _, raw = self.call(method, "/api/v1" + path, body=body,
                                   content_type="application/json" if body is not None else None)
        if status not in expect:
            raise AssertionError(f"{method} {path} -> {status}: {raw[:300]!r}")
        return json.loads(raw) if raw else None

    def upload(self, name: str, data: bytes) -> tuple[int, bytes]:
        boundary = uuid.uuid4().hex
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\n"
                f"Content-Type: text/csv\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()
        status, _, raw = self.call("POST", "/api/v1/sessions", body=body,
                                   content_type=f"multipart/form-data; boundary={boundary}")
        return status, raw


def wait_state(client: Client, sid: str, wanted: set[str], limit_s: float = 300) -> str:
    deadline = time.time() + limit_s
    while time.time() < deadline:
        session = client.json("GET", f"/sessions/{sid}")
        if session["state"] in wanted:
            return session["state"]
        if session.get("error"):
            raise AssertionError(f"session {sid} failed in {session.get('failed_stage')}: {session['error']}")
        time.sleep(1)
    raise AssertionError(f"session {sid} did not reach {wanted} in {limit_s:.0f} s")


def full_flow(client: Client, name: str, data: bytes, target: str) -> str:
    t0 = time.time()
    status, raw = client.upload(name, data)
    assert status == 201, f"upload {name} -> {status}: {raw[:300]!r}"
    sid = json.loads(raw)["id"]
    wait_state(client, sid, {"profiled"})
    plan = client.json("POST", f"/sessions/{sid}/plan", expect=(201,))
    steps = [dict(step, status="approved") for step in plan["steps"]]
    client.json("POST", f"/sessions/{sid}/plan/approve", {"steps": steps})
    client.json("POST", f"/sessions/{sid}/execute", expect=(202,))
    wait_state(client, sid, {"executed"})
    charts = client.json("GET", f"/sessions/{sid}/charts")
    assert charts["charts"], "no charts"
    client.json("POST", f"/sessions/{sid}/model", {"target": target}, expect=(202,))
    wait_state(client, sid, {"modeled"})
    client.json("POST", f"/sessions/{sid}/report", {}, expect=(201,))
    status, headers, html = client.call("GET", f"/api/v1/sessions/{sid}/report")
    assert status == 200 and b"<html" in html.lower(), f"report -> {status}"
    status, _, bundle = client.call("GET", f"/api/v1/sessions/{sid}/bundle.zip")
    names = zipfile.ZipFile(io.BytesIO(bundle)).namelist() if status == 200 else []
    assert "report.html" in names, f"bundle -> {status}, {names}"
    print(f"PASS {name}: {len(steps)} steps, {len(charts['charts'])} charts, report and bundle "
          f"({time.time() - t0:.0f} s)")
    return sid


def row_cap_csv(rows: int) -> bytes:
    """A synthetic dataset at the hosted row cap (FR-DP-20): numbers, a category, gaps, a target."""
    rng = random.Random(42)
    out = io.StringIO()
    out.write("x1,x2,x3,x4,segment,score\n")
    for _ in range(rows):
        x = [rng.gauss(0, 1) for _ in range(4)]
        segment = rng.choice("abcd")
        score = "high" if x[0] + 0.5 * x[1] + rng.gauss(0, 0.5) > 0 else "low"
        cells = [f"{v:.4f}" if rng.random() > 0.02 else "" for v in x]
        out.write(",".join(cells + [segment, score]) + "\n")
    return out.getvalue().encode()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", required=True)
    parser.add_argument("--user")
    parser.add_argument("--password")
    parser.add_argument("--session-file", type=Path)
    parser.add_argument("--check-session", action="store_true",
                        help="only check that the session in --session-file still has its report (AC-5)")
    parser.add_argument("--skip-row-cap", action="store_true", help="skip the row-cap file (slow on Render)")
    parser.add_argument("--timeout", type=float, default=320)
    args = parser.parse_args()
    client = Client(args.base, args.user, args.password, args.timeout)

    if args.check_session:
        sid = args.session_file.read_text().strip()
        state = client.json("GET", f"/sessions/{sid}")["state"]
        status, _, _ = client.call("GET", f"/api/v1/sessions/{sid}/report")
        assert state == "reported" and status == 200, f"after restart: state={state}, report={status}"
        print(f"PASS session {sid} and its report survived the restart")
        return 0

    status, _, body = client.call("GET", "/healthz", auth=False)
    assert status == 200 and json.loads(body) == {"status": "ok"}, f"/healthz -> {status}"
    print("PASS /healthz without password")
    status, headers, _ = client.call("GET", "/", auth=False)
    assert status == 401 and headers.get("www-authenticate", "").startswith("Basic"), f"/ -> {status}"
    print("PASS / without password -> 401")

    config = client.json("GET", "/config")
    assert config["hosted"] is True, config
    print(f"PASS /config: {config}")

    oversize = b"a,b\n" + b"1,2\n" * int((config["max_file_size_mb"] + 1) * 1024 * 1024 / 4)
    status, raw = client.upload("too_big.csv", oversize)
    error = json.loads(raw).get("error", {}) if raw.startswith(b"{") else {}
    assert status == 413 and error.get("code"), f"oversize -> {status}: {raw[:200]!r}"
    print(f"PASS oversize upload -> 413 {error['code']} (AC-7)")

    status, _, sample = client.call("GET", "/samples/titanic.csv")
    assert status == 200, f"sample -> {status}"
    sid = full_flow(client, "titanic.csv", sample, "Survived")
    if not args.skip_row_cap:
        full_flow(client, "row_cap.csv", row_cap_csv(int(config["max_rows"])), "score")
    if args.session_file:
        args.session_file.write_text(sid)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as failure:
        print(f"FAIL {failure}")
        sys.exit(1)
