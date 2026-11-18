#!/usr/bin/env python3
"""Construit le RenderJob T5 qui relie six réponses et quatre captures runtime."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/T5_render_job.schema.json"
QUESTIONS = ROOT / "form/questions_T5.json"
SLOTS = ("S1", "S2", "S3", "S4")
FIELDS = ("nom", "offre", "contenu", "prix", "whatsapp", "quartier")
ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{7,127}$")
OUTPUT_FILENAME = "VIDEO_T5_FORMULE_PLEIN_ECRAN_V3_A_VALIDER.mp4"
AUDIO_CONFIG = ROOT / "config/T5_AUDIO_MIX_V1_0_0.json"
MUSIC_PACK = ROOT / "config/T5_MUSIC_PACK_V1_0_0.json"
VOICE_MANIFEST = ROOT / "audio/voice/t5-voice-v1/manifest.json"
MUSIC_IDS = (
    "t5_music_300338",
    "t5_music_324016",
    "t5_music_292156",
    "t5_music_345669",
)
MUSIC_STATE_SCHEMA_VERSION = "1.0.0"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


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


def approved_music_tracks(pack_path: Path = MUSIC_PACK) -> list[dict[str, Any]]:
    pack = load_json(pack_path)
    tracks = list(pack.get("tracks", []))
    selection = pack.get("selection_contract", {})
    allowed = list(selection.get("allowed_variant_ids", []))
    if allowed != list(MUSIC_IDS) or [track.get("id") for track in tracks] != list(MUSIC_IDS):
        raise ValueError("T5 requires the four owner-approved tracks in strict order")
    if (
        selection.get("first_render_variant_id") != MUSIC_IDS[0]
        or selection.get("first_render_pool_size") != 1
        or selection.get("subsequent_pool_size") != 1
        or selection.get("explicit_selection_policy") != "exact_successor_only"
        or selection.get("idempotency_ledger_key") != "successful_render_jobs"
        or selection.get("state_update_policy") != "after_completed_audio_qc_pass_only"
        or selection.get("failed_render_state_policy") != "unchanged"
    ):
        raise ValueError("T5 music pack does not guarantee the strict success cycle")
    if [track.get("pixabay_id") for track in tracks] != [300338, 324016, 292156, 345669]:
        raise ValueError("T5 music pack diverges from the approved Pixabay order")
    for track in tracks:
        if not track.get("owner_approved") or not track.get("production_eligible"):
            raise ValueError("Every T5 track must be owner-approved and production-eligible")
        if track.get("content_id_status") != "not_displayed_on_source_page":
            raise ValueError("Every T5 track must retain the dated Content ID observation")
        if track.get("contains_voice") is not False or track.get("duration_s") != 30.0:
            raise ValueError("Every T5 production asset must be a clean 30-second instrumental")
        program = ROOT / track["file"]
        if not program.is_file() or file_sha256(program) != track["sha256"] or program.stat().st_size != track["bytes"]:
            raise ValueError(f"T5 music asset integrity failure: {track['id']}")
    return tracks


def select_music_variant(
    *,
    last_successful_music_id: str | None = None,
    explicit_music_id: str | None = None,
    pack_path: Path = MUSIC_PACK,
) -> dict[str, Any]:
    """Return the strict next T5 track; explicit production choices cannot skip it."""
    tracks = approved_music_tracks(pack_path)
    if last_successful_music_id is not None and last_successful_music_id not in MUSIC_IDS:
        raise ValueError("Unknown last successful T5 music ID")
    previous_index = -1 if last_successful_music_id is None else MUSIC_IDS.index(last_successful_music_id)
    expected = tracks[(previous_index + 1) % len(tracks)]
    if explicit_music_id is not None:
        if explicit_music_id not in MUSIC_IDS:
            raise ValueError("Explicit T5 music ID is not approved")
        if explicit_music_id != expected["id"]:
            raise ValueError(f"Strict T5 cycle expects {expected['id']}, got {explicit_music_id}")
    return {
        **expected,
        "selection_mode": "explicit" if explicit_music_id is not None else "strict_success_cycle",
        "last_successful_music_id": last_successful_music_id,
    }


def initial_music_state() -> dict[str, Any]:
    return {
        "schema_version": MUSIC_STATE_SCHEMA_VERSION,
        "last_successful_music_id": None,
        "last_successful_render_job_id": None,
        "successful_render_count": 0,
        "successful_render_jobs": {},
    }


def load_music_selection_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return initial_music_state()
    state = load_json(state_path)
    if set(state) != set(initial_music_state()) or state.get("schema_version") != MUSIC_STATE_SCHEMA_VERSION:
        raise ValueError("Invalid T5 music rotation state")
    if state["last_successful_music_id"] not in {None, *MUSIC_IDS}:
        raise ValueError("Unknown T5 music ID in persistent state")
    if type(state["successful_render_count"]) is not int or state["successful_render_count"] < 0:
        raise ValueError("Invalid T5 successful render count")
    receipts = state["successful_render_jobs"]
    if (
        not isinstance(receipts, dict)
        or any(not ID_PATTERN.fullmatch(job_id) or music_id not in MUSIC_IDS for job_id, music_id in receipts.items())
        or len(receipts) != state["successful_render_count"]
    ):
        raise ValueError("Invalid T5 successful render ledger")
    if (state["last_successful_music_id"] is None) != (state["last_successful_render_job_id"] is None):
        raise ValueError("T5 state must pair successful music and render job IDs")
    if (state["successful_render_count"] == 0) != (state["last_successful_music_id"] is None):
        raise ValueError("An empty T5 state cannot contain a successful render, and conversely")
    if state["last_successful_render_job_id"] is not None:
        if not ID_PATTERN.fullmatch(state["last_successful_render_job_id"]):
            raise ValueError("Invalid T5 successful render job ID")
        if receipts.get(state["last_successful_render_job_id"]) != state["last_successful_music_id"]:
            raise ValueError("The last T5 success must exist in the idempotency ledger")
    return state


def select_music_variant_from_state(
    *, state_path: Path, explicit_music_id: str | None = None
) -> dict[str, Any]:
    state = load_music_selection_state(state_path)
    return select_music_variant(
        last_successful_music_id=state["last_successful_music_id"],
        explicit_music_id=explicit_music_id,
    )


def _record_music_render_result_unlocked(
    *,
    state_path: Path,
    render_job_id: str,
    selected_music_id: str,
    completed: bool,
    quality_status: str,
) -> dict[str, Any]:
    if not ID_PATTERN.fullmatch(render_job_id) or selected_music_id not in MUSIC_IDS:
        raise ValueError("Invalid T5 music result")
    if type(completed) is not bool or quality_status not in {"PASS", "FAIL"}:
        raise ValueError("Invalid T5 music completion or quality status")
    current = load_music_selection_state(state_path)
    if not (completed and quality_status == "PASS"):
        return current
    if render_job_id in current["successful_render_jobs"]:
        if current["successful_render_jobs"][render_job_id] != selected_music_id:
            raise ValueError("An idempotent T5 success callback cannot change music")
        return current
    previous_id = current["last_successful_music_id"]
    previous_index = -1 if previous_id is None else MUSIC_IDS.index(previous_id)
    expected_id = MUSIC_IDS[(previous_index + 1) % len(MUSIC_IDS)]
    if selected_music_id != expected_id:
        raise ValueError(f"T5 success must follow the strict cycle: expected {expected_id}, got {selected_music_id}")
    updated = {
        "schema_version": MUSIC_STATE_SCHEMA_VERSION,
        "last_successful_music_id": selected_music_id,
        "last_successful_render_job_id": render_job_id,
        "successful_render_count": current["successful_render_count"] + 1,
        "successful_render_jobs": {**current["successful_render_jobs"], render_job_id: selected_music_id},
    }
    state_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{state_path.name}.", dir=state_path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(updated, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, state_path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
    return updated


def record_music_render_result(
    *,
    state_path: Path,
    render_job_id: str,
    selected_music_id: str,
    completed: bool,
    quality_status: str,
) -> dict[str, Any]:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = state_path.parent / f".{state_path.name}.lock"
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            return _record_music_render_result_unlocked(
                state_path=state_path,
                render_job_id=render_job_id,
                selected_music_id=selected_music_id,
                completed=completed,
                quality_status=quality_status,
            )
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def complete_audio_contract(selected: dict[str, Any]) -> dict[str, Any]:
    config = load_json(AUDIO_CONFIG)
    voice = config["voice"]
    clips = voice["clips"]
    return {
        "mode": "owner_approved_music_rotation_voice_b_complete",
        "contract": str(AUDIO_CONFIG.relative_to(ROOT)),
        "contract_sha256": file_sha256(AUDIO_CONFIG),
        "music_pack": str(MUSIC_PACK.relative_to(ROOT)),
        "music_pack_sha256": file_sha256(MUSIC_PACK),
        "music": {
            "selection_mode": selected["selection_mode"],
            "selected_music_id": selected["id"],
            "selected_choice": selected["choice"],
            "pixabay_id": selected["pixabay_id"],
            "title": selected["title"],
            "artist": selected["artist"],
            "file": selected["file"],
            "sha256": selected["sha256"],
            "bytes": selected["bytes"],
            "duration_s": selected["duration_s"],
            "contains_voice": selected["contains_voice"],
            "source_page": selected["page"],
            "source_url": selected["url"],
            "source_sha256": selected["source_sha256"],
            "source_bytes": selected["source_bytes"],
            "source_start_s": selected["source_start_s"],
            "license": "Pixabay Content License",
            "full_source_bundled": False,
            "standalone_redistribution_forbidden": True,
            "last_successful_music_id": selected["last_successful_music_id"],
            "state_update_policy": "after_completed_audio_qc_pass_only",
        },
        "voice": {
            "source_mode": "owner_approved_registered_clips",
            "selected_option": voice["selected_option"],
            "voice_id": voice["voice_id"],
            "language": voice["language"],
            "manifest": voice["manifest"],
            "manifest_sha256": file_sha256(VOICE_MANIFEST),
            "clip_source_sha256": {
                f"S{clip['scene']}": clip["source_sha256"] for clip in clips
            },
        },
        "mix_contract": config["mix_contract"],
        "state_update_policy": "after_completed_audio_qc_pass_only",
    }


def build_render_job(
    *,
    render_job_id: str,
    merchant_payload: dict[str, Any],
    captures: dict[str, dict[str, Any]],
    last_successful_music_id: str | None = None,
    explicit_music_id: str | None = None,
    control_plane: str = "cloudflare_worker",
) -> dict[str, Any]:
    if not ID_PATTERN.fullmatch(render_job_id):
        raise ValueError("render_job_id is invalid")
    if control_plane not in {"cloudflare_worker", "github_actions_fixture"}:
        raise ValueError("unsupported control plane")
    payload = normalize_payload(merchant_payload)
    verified_captures = validate_captures(captures)
    selected_music = select_music_variant(
        last_successful_music_id=last_successful_music_id,
        explicit_music_id=explicit_music_id,
    )
    job = {
        "schema_version": "1.0.0",
        "job_id": render_job_id,
        "idempotency_key": render_job_id,
        "template_id": "RESTAURATION-T5",
        "template_version": "3.0.0-full-frame",
        "merchant_payload": payload,
        "captures": verified_captures,
        "audio": complete_audio_contract(selected_music),
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
            "audio_mode": "owner_approved_music_rotation_voice_b_complete",
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
    parser.add_argument("--last-successful-music-id", choices=MUSIC_IDS)
    parser.add_argument("--explicit-music-id", choices=MUSIC_IDS)
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
        last_successful_music_id=args.last_successful_music_id,
        explicit_music_id=args.explicit_music_id,
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
