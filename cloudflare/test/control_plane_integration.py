#!/usr/bin/env python3
"""Test boîte noire du plan de contrôle T5 : formulaire, 4 captures, RenderJob et RenderResult."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time
from typing import Any
import urllib.error
import urllib.request

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SLOTS = ("S1", "S2", "S3", "S4")
DURATIONS = {"S1": 6000, "S2": 8000, "S3": 7000, "S4": 9000}
RANGES = {"S1": (0, 179), "S2": (180, 419), "S3": (420, 629), "S4": (630, 899)}


def call(base: str, path: str, *, method: str = "GET", body: bytes | None = None, headers: dict[str, str] | None = None, expected: int = 200) -> tuple[bytes, dict[str, str], int]:
    request = urllib.request.Request(base.rstrip("/") + path, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status, payload, response_headers = response.status, response.read(), dict(response.headers.items())
    except urllib.error.HTTPError as error:
        status, payload, response_headers = error.code, error.read(), dict(error.headers.items())
    if status != expected:
        raise AssertionError(f"{method} {path}: HTTP {status}, expected {expected}: {payload.decode(errors='replace')}")
    return payload, response_headers, status


def as_json(payload: bytes) -> dict[str, Any]:
    return json.loads(payload.decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8788")
    parser.add_argument("--client-token", default="test-client")
    parser.add_argument("--callback-token", default="test-callback")
    args = parser.parse_args()

    health = as_json(call(args.base, "/health")[0])
    assert health == {
        "status": "ok", "service": "t5-formule-control-plane",
        "control_plane": "cloudflare_worker", "render_plane": "github_actions", "cloudflare_rendering": False,
    }
    assert as_json(call(args.base, "/v1/contracts/form")[0]) == json.loads((ROOT / "form/questions_T5.json").read_text())
    flow = as_json(call(args.base, "/v1/contracts/capture-flow")[0])
    assert flow == json.loads((ROOT / "config/T5_CAPTURE_FLOW_V1_0_0.json").read_text())
    assert flow["counts"]["stable_capture_screens"] == 12
    root = call(args.base, "/")[0].decode("utf-8").lower()
    assert "6 questions" in root and "12 écrans" in root

    client = {"authorization": f"Bearer {args.client_token}"}
    callback = {"authorization": f"Bearer {args.callback_token}"}
    merchant = {
        "nom": "Burger Atelier Kandi",
        "offre": "Formule Double Burger",
        "contenu": "1 double burger, 1 portion de frites et 1 verre de cola",
        "prix": "5 000 FCFA",
        "whatsapp": "+229 01 97 00 00 00",
        "quartier": "Kandi, près du marché central",
    }
    unauthorized = as_json(call(args.base, "/v1/jobs", method="POST", body=b"{}", headers={"content-type": "application/json"}, expected=401)[0])
    assert unauthorized["code"] == "T5_UNAUTHORIZED"

    idem = f"integration-{time.time_ns()}"
    body = json.dumps({"merchant_payload": merchant}, ensure_ascii=False).encode()
    headers = {**client, "content-type": "application/json", "idempotency-key": idem}
    created = as_json(call(args.base, "/v1/jobs", method="POST", body=body, headers=headers, expected=201)[0])
    job_id = created["job_id"]
    assert created["required_captures"] == list(SLOTS)
    replay = as_json(call(args.base, "/v1/jobs", method="POST", body=body, headers=headers)[0])
    assert replay == {"job_id": job_id, "status": "UPLOADING", "idempotent_replay": True}

    media = b"t5-control-plane-integration-capture"
    media_sha = hashlib.sha256(media).hexdigest()
    for slot in SLOTS:
        duration = DURATIONS[slot]
        upload_headers = {
            **client, "content-type": "video/mp4", "content-length": str(len(media)),
            "x-content-sha256": media_sha, "x-video-width": "1080", "x-video-height": "1920",
            "x-video-fps": "30", "x-video-frames": str(duration * 30 // 1000),
            "x-video-duration-ms": str(duration), "x-video-codec": "h264",
            "x-has-audio": "true", "x-audio-codec": "aac",
        }
        uploaded = as_json(call(args.base, f"/v1/jobs/{job_id}/captures/{slot}", method="PUT", body=media, headers=upload_headers, expected=201)[0])
        assert uploaded["sha256"] == media_sha
    assert uploaded["status"] == "READY"

    dispatched = as_json(call(args.base, f"/v1/jobs/{job_id}/dispatch", method="POST", headers=client, expected=202)[0])
    assert dispatched == {"job_id": job_id, "status": "QUEUED"}
    job = as_json(call(args.base, f"/v1/jobs/{job_id}/payload", headers=callback)[0])["job"]
    Draft202012Validator(json.loads((ROOT / "schemas/T5_render_job.schema.json").read_text())).validate(job)
    assert job["merchant_payload"] == merchant
    assert job["render"]["visual_mode"] == "runtime_full_frame_render"
    assert job["render"]["production_render_plane"] == "github_actions"
    assert job["control_plane"] == "cloudflare_worker" and job["cloudflare_rendering_forbidden"] is True
    for slot in SLOTS:
        payload, response_headers, _ = call(args.base, f"/v1/jobs/{job_id}/captures/{slot}", headers=callback)
        assert payload == media and response_headers["x-content-sha256"] == media_sha

    rendered = b"t5-runtime-rendered-mp4-fixture"
    rendered_sha = hashlib.sha256(rendered).hexdigest()
    stored = as_json(call(
        args.base, f"/v1/jobs/{job_id}/output", method="PUT", body=rendered,
        headers={**callback, "content-type": "video/mp4", "content-length": str(len(rendered)), "x-content-sha256": rendered_sha},
        expected=201,
    )[0])
    assert stored["output"]["sha256"] == rendered_sha

    bindings = [
        {"scene": slot, "capture_slot": slot, "capture_sha256": media_sha, "timeline_start_frame": RANGES[slot][0], "timeline_end_frame": RANGES[slot][1]}
        for slot in SLOTS
    ]
    result = {
        "schema_version": "1.0.0", "status": "COMPLETED", "job_id": job_id, "idempotency_key": idem,
        "template_id": "RESTAURATION-T5", "template_version": "3.0.0-full-frame",
        "profile_used": "T5_GITHUB_ACTIONS_FULL_FRAME_V3", "control_plane": "cloudflare_worker",
        "output": {"uri": job["output"]["uri"], "file": job["output"]["filename"], "sha256": rendered_sha, "bytes": len(rendered)},
        "quality": {"status": "PASS", "report": "T5_RUNTIME_VALIDATION.json", "passed": 19, "total": 19},
        "inputs": {
            "merchant_payload_sha256": hashlib.sha256(json.dumps(merchant, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "capture_sha256": {slot: media_sha for slot in SLOTS},
            "runtime_manifest_sha256": "a" * 64,
            "resolved_text_sha256": "b" * 64,
        },
        "rendered_fields": ["nom", "offre", "contenu", "prix", "whatsapp", "quartier"],
        "scene_capture_bindings": bindings,
    }
    Draft202012Validator(json.loads((ROOT / "schemas/T5_render_result.schema.json").read_text())).validate(result)
    invalid = as_json(call(
        args.base, f"/v1/jobs/{job_id}/events", method="POST",
        body=json.dumps({"status": "COMPLETED", "result": {"job_id": "wrong"}}).encode(),
        headers={**callback, "content-type": "application/json"}, expected=422,
    )[0])
    assert invalid["code"] == "T5_INVALID_CALLBACK_PAYLOAD"
    event = {"status": "COMPLETED", "github_run_id": "123", "github_run_url": "https://github.com/example/actions/runs/123", "result": result}
    completed = as_json(call(args.base, f"/v1/jobs/{job_id}/events", method="POST", body=json.dumps(event).encode(), headers={**callback, "content-type": "application/json"})[0])
    assert completed == {"job_id": job_id, "status": "COMPLETED"}
    status = as_json(call(args.base, f"/v1/jobs/{job_id}")[0])
    assert status["status"] == "COMPLETED" and status["output_ready"] is True
    output, output_headers, _ = call(args.base, f"/v1/jobs/{job_id}/output", headers=client)
    assert output == rendered and output_headers["x-content-sha256"] == rendered_sha
    print("T5_CLOUDFLARE_CONTROL_PLANE_INTEGRATION_OK", job_id)


if __name__ == "__main__":
    main()
