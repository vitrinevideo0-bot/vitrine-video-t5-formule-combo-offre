#!/usr/bin/env python3
"""Construit le RenderJob T5 qui relie six réponses et quatre captures runtime."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/T5_render_job.schema.json"
QUESTIONS = ROOT / "form/questions_T5.json"
SLOTS = ("S1", "S2", "S3", "S4")
FIELDS = ("nom", "offre", "contenu", "prix", "whatsapp", "quartier")
ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{7,127}$")
OUTPUT_FILENAME = "VIDEO_T5_FORMULE_PLEIN_ECRAN_V3_A_VALIDER.mp4"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def normalize_payload(raw: dict[str, Any]) -> dict[str, str]:
    if list(raw) != list(FIELDS):
        raise ValueError(f"merchant_payload keys must be exactly {list(FIELDS)} in order")
    questions = load_json(QUESTIONS)
    limits = {field["id"]: (field["minLength"], field["maxLength"]) for field in questions["fields"]}
    payload: dict[str, str] = {}
    for field in FIELDS:
        value = raw[field]
        if not isinstance(value, str):
            raise ValueError(f"merchant_payload.{field} must be a string")
        normalized = " ".join(value.split())
        minimum, maximum = limits[field]
        if not minimum <= len(normalized) <= maximum:
            raise ValueError(f"merchant_payload.{field} must contain between {minimum} and {maximum} characters")
        payload[field] = normalized
    return payload


def validate_captures(captures: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if list(captures) != list(SLOTS):
        raise ValueError("captures must be exactly S1, S2, S3 and S4 in order")
    required = {
        "uri", "sha256", "mime_type", "width", "height", "fps", "frame_count",
        "duration_ms", "source_in_ms", "video_codec", "audio_codec", "has_audio",
    }
    normalized: dict[str, dict[str, Any]] = {}
    for slot in SLOTS:
        capture = captures[slot]
        missing = required - set(capture)
        extra = set(capture) - required
        if missing or extra:
            raise ValueError(f"capture {slot} keys mismatch; missing={sorted(missing)} extra={sorted(extra)}")
        if not re.fullmatch(r"[0-9a-f]{64}", str(capture["sha256"])):
            raise ValueError(f"capture {slot} SHA-256 is invalid")
        normalized[slot] = dict(capture)
    return normalized


def captures_from_demo_manifest(manifest: dict[str, Any], render_job_id: str) -> dict[str, dict[str, Any]]:
    by_slot = {source["slot"]: source for source in manifest["sources"]}
    if set(by_slot) != set(SLOTS):
        raise ValueError("demo manifest must declare S1, S2, S3 and S4")
    return {
        slot: {
            "uri": f"rushes/runtime/{render_job_id}/{slot}.mp4",
            "sha256": by_slot[slot]["sha256"],
            "mime_type": "video/mp4",
            "width": by_slot[slot]["width"],
            "height": by_slot[slot]["height"],
            "fps": by_slot[slot]["fps"],
            "frame_count": by_slot[slot]["frame_count"],
            "duration_ms": by_slot[slot]["duration_ms"],
            "source_in_ms": next(scene["source_in_ms"] for scene in manifest["scenes"] if scene["scene"] == slot),
            "video_codec": "h264",
            "audio_codec": None,
            "has_audio": False,
        }
        for slot in SLOTS
    }


def build_render_job(
    *,
    render_job_id: str,
    merchant_payload: dict[str, Any],
    captures: dict[str, dict[str, Any]],
    control_plane: str = "cloudflare_worker",
) -> dict[str, Any]:
    if not ID_PATTERN.fullmatch(render_job_id):
        raise ValueError("render_job_id is invalid")
    if control_plane not in {"cloudflare_worker", "github_actions_fixture"}:
        raise ValueError("unsupported control plane")
    payload = normalize_payload(merchant_payload)
    verified_captures = validate_captures(captures)
    job = {
        "schema_version": "1.0.0",
        "job_id": render_job_id,
        "idempotency_key": render_job_id,
        "template_id": "RESTAURATION-T5",
        "template_version": "3.0.0-full-frame",
        "merchant_payload": payload,
        "captures": verified_captures,
        "render": {
            "visual_mode": "runtime_full_frame_render",
            "runtime_capture_manifest_required": True,
            "render_business_text": True,
            "business_text_source": "merchant_payload",
            "runtime_contract": "config/T5_RUNTIME_CONTRACT_V3_0_0.json",
            "transition_reference": "T1",
            "width": 720,
            "height": 1280,
            "fps": 30,
            "frames": 900,
            "duration_s": 30.0,
            "scene_durations_s": [6, 8, 7, 9],
            "audio_mode": "silent_no_audio_stream",
            "production_render_plane": "github_actions",
        },
        "output": {
            "uri": f"output/runtime/{render_job_id}/{OUTPUT_FILENAME}",
            "filename": OUTPUT_FILENAME,
        },
        "control_plane": control_plane,
        "cloudflare_rendering_forbidden": True,
    }
    Draft202012Validator(load_json(SCHEMA)).validate(job)
    return job


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render-job-id", required=True)
    parser.add_argument("--answers", type=Path, required=True)
    parser.add_argument("--captures", type=Path, required=True, help="Capture object or the four-source demo manifest")
    parser.add_argument("--control-plane", choices=["cloudflare_worker", "github_actions_fixture"], default="github_actions_fixture")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    answers = load_json(args.answers)
    capture_input = load_json(args.captures)
    captures = (
        captures_from_demo_manifest(capture_input, args.render_job_id)
        if "sources" in capture_input
        else capture_input
    )
    job = build_render_job(
        render_job_id=args.render_job_id,
        merchant_payload=answers,
        captures=captures,
        control_plane=args.control_plane,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "READY",
        "job_id": job["job_id"],
        "control_plane": job["control_plane"],
        "merchant_payload_sha256": canonical_sha256(job["merchant_payload"]),
        "capture_sha256": {slot: job["captures"][slot]["sha256"] for slot in SLOTS},
        "output": str(args.output),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
