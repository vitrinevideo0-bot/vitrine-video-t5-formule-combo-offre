#!/usr/bin/env python3
"""Vérifie quatre captures SHA-256 et matérialise le manifeste consommé par le moteur T5."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SLOTS = ("S1", "S2", "S3", "S4")
DURATIONS = {"S1": 6, "S2": 8, "S3": 7, "S4": 9}
FRAME_RANGES = {"S1": [0, 179], "S2": [180, 419], "S3": [420, 629], "S4": [630, 899]}
TITLES = {"S1": "LA FORMULE", "S2": "CE QU’IL Y A DANS LA FORMULE", "S3": "LE PRIX", "S4": "COMMANDER"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def probe(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries",
            "stream=index,codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,nb_frames,duration:format=duration,size",
            "-of", "json", str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def rate(value: str) -> float:
    numerator, denominator = value.split("/", 1)
    return float(numerator) / float(denominator)


def capture_file(directory: Path, slot: str) -> Path:
    matches = sorted(path for path in directory.glob(f"{slot}*") if path.is_file() and path.suffix.lower() in {".mp4", ".mov", ".webm"})
    if len(matches) != 1:
        raise SystemExit(f"Expected exactly one capture for {slot}, found {len(matches)}")
    return matches[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render-job", type=Path, required=True)
    parser.add_argument("--capture-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    job = json.loads(args.render_job.read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "schemas/T5_render_job.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(job)
    if job["render"]["visual_mode"] != "runtime_full_frame_render" or job["render"]["runtime_capture_manifest_required"] is not True:
        raise SystemExit("RenderJob does not authorize a runtime capture manifest")
    if job["render"]["production_render_plane"] != "github_actions" or job["cloudflare_rendering_forbidden"] is not True:
        raise SystemExit("T5 must render on GitHub Actions, never on Cloudflare")

    contract = json.loads((ROOT / job["render"]["runtime_contract"]).read_text(encoding="utf-8"))
    fields_by_scene = {item["scene"]: item["text_fields"] for item in contract["scene_bindings"]}
    scenes: list[dict[str, Any]] = []
    for slot in SLOTS:
        declared = job["captures"][slot]
        source = capture_file(args.capture_dir, slot)
        actual_hash = sha256(source)
        if actual_hash != declared["sha256"]:
            raise SystemExit(f"Runtime capture SHA-256 mismatch for {slot}")
        metadata = probe(source)
        videos = [stream for stream in metadata["streams"] if stream.get("codec_type") == "video"]
        if len(videos) != 1:
            raise SystemExit(f"Capture {slot} must contain exactly one video stream")
        video = videos[0]
        width, height = int(video["width"]), int(video["height"])
        fps = rate(video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1")
        duration = float(metadata["format"].get("duration") or video.get("duration") or 0)
        source_in = int(declared["source_in_ms"]) / 1000.0
        if duration + 0.05 < source_in + DURATIONS[slot]:
            raise SystemExit(f"Capture {slot} is too short: {duration:.3f}s")
        if width < 320 or height < 320 or fps < 12 or fps > 120:
            raise SystemExit(f"Capture {slot} metadata is unsupported")
        if (width, height) != (int(declared["width"]), int(declared["height"])):
            raise SystemExit(f"Capture {slot} dimensions diverge from RenderJob")
        if abs(fps - float(declared["fps"])) > 1.0:
            raise SystemExit(f"Capture {slot} frame rate diverges from RenderJob")
        scenes.append({
            "scene": slot,
            "title": TITLES[slot],
            "capture_slot": slot,
            "capture_uri": declared["uri"],
            "local_file": source.name,
            "sha256": actual_hash,
            "bytes": source.stat().st_size,
            "source_width": width,
            "source_height": height,
            "source_fps": fps,
            "source_duration_seconds": duration,
            "source_in_seconds": source_in,
            "duration_seconds": DURATIONS[slot],
            "timeline_frames": FRAME_RANGES[slot],
            "text_fields": fields_by_scene[slot],
            "rush_fills_entire_frame": True,
            "visible_text_source": "merchant_payload_exact_values_only",
            "full_formula_visibility_required": True,
            "freeze_tail_seconds": 3 if slot == "S4" else 0,
        })

    manifest = {
        "schema_version": "1.0.0",
        "template_id": "RESTAURATION-T5",
        "template_version": "3.0.0-full-frame",
        "job_id": job["job_id"],
        "idempotency_key": job["idempotency_key"],
        "control_plane": job["control_plane"],
        "purpose": "Only the four SHA-256 verified captures in this manifest may feed the T5 runtime renderer.",
        "runtime_contract": job["render"]["runtime_contract"],
        "runtime_contract_sha256": sha256(ROOT / job["render"]["runtime_contract"]),
        "merchant_payload_sha256": canonical_sha256(job["merchant_payload"]),
        "output_contract": {
            "width": 720, "height": 1280, "fps": 30, "frames": 900,
            "duration_seconds": 30.0, "audio_streams": 0,
            "business_text_source": "merchant_payload_exact_values_only",
            "rushes_fill_entire_frame": True,
            "transition_frames_per_cut": 8,
            "transition_cut_frames": [180, 420, 630],
        },
        "scenes": scenes,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "READY",
        "job_id": job["job_id"],
        "manifest": str(args.manifest),
        "manifest_sha256": sha256(args.manifest),
        "capture_sha256": {scene["scene"]: scene["sha256"] for scene in scenes},
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
