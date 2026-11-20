#!/usr/bin/env python3
"""Transforme l'attestation visuelle T5 en RenderResult complet après le mix audio.

Le callback Cloudflare ne doit jamais accepter le résultat visuel silencieux. Ce
finaliseur lie donc explicitement Afrofire, la voix B voice-11, le rapport 26/26
et le MP4 final avant de produire un RenderResult au statut COMPLETED.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SLOTS = ("S1", "S2", "S3", "S4")


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--visual-result", type=Path, required=True)
    parser.add_argument("--render-job", type=Path, required=True)
    parser.add_argument("--audio-config", type=Path, required=True)
    parser.add_argument("--audio-report", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    audio_config_path = args.audio_config.resolve()
    visual = load(args.visual_result)
    job = load(args.render_job)
    config = load(audio_config_path)
    report = load(args.audio_report)
    schema = load(ROOT / "schemas/T5_render_result.schema.json")
    job_schema = load(ROOT / "schemas/T5_render_job.schema.json")
    Draft202012Validator(job_schema).validate(job)
    Draft202012Validator(schema).validate(visual)

    require(visual["status"] == "VISUAL_COMPLETED", "Expected a visual-stage result")
    require(visual["profile_used"] == "T5_GITHUB_ACTIONS_FULL_FRAME_V3", "Unexpected visual profile")
    require(visual["job_id"] == job["job_id"] and visual["idempotency_key"] == job["idempotency_key"], "Visual result belongs to another job")
    require(visual["control_plane"] == job["control_plane"], "Visual control plane diverges from RenderJob")
    require(visual["output"]["uri"] == job["output"]["uri"] and visual["output"]["file"] == job["output"]["filename"], "Visual output diverges from RenderJob")
    require(visual["inputs"]["merchant_payload_sha256"] == canonical_sha256(job["merchant_payload"]), "Visual merchant payload diverges from RenderJob")
    require(visual["inputs"]["capture_sha256"] == {slot: job["captures"][slot]["sha256"] for slot in SLOTS}, "Visual captures diverge from RenderJob")
    require(report["status"] == "PASS" and report["summary"]["failed"] == 0, "Audio QC is not PASS")
    require(report["summary"]["passed"] == report["summary"]["total"], "Audio QC summary is inconsistent")
    require(args.video.is_file(), "Final MP4 is missing")

    audio = job["audio"]
    music = audio["music"]
    voice = audio["voice"]
    config_music = config["music"]
    config_voice = config["voice"]
    voice_manifest = ROOT / config_voice["manifest"]
    clip_hashes = {f"S{clip['scene']}": clip["source_sha256"] for clip in config_voice["clips"]}

    require(audio["mode"] == "owner_approved_afrofire_voice_b_complete", "Unexpected audio mode")
    require(job["render"]["audio_mode"] == audio["mode"], "Render audio mode diverges from audio contract")
    require(audio["contract"] == str(audio_config_path.relative_to(ROOT)), "Audio contract path mismatch")
    require(audio["contract_sha256"] == sha256(audio_config_path), "Audio contract SHA-256 mismatch")
    require(voice["manifest_sha256"] == sha256(voice_manifest), "Voice manifest SHA-256 mismatch")
    require(voice["clip_source_sha256"] == clip_hashes, "Voice clip binding mismatch")
    require(music["source_sha256"] == config_music["source_sha256"], "Music source binding mismatch")
    require(music["source_bundled"] is False, "The full music source must not be bundled")
    require(music["standalone_redistribution_forbidden"] is True, "Standalone music redistribution must remain forbidden")

    final_video = report["final_video"]
    require(final_video["file"] == args.video.name, "Audio report names another final video")
    require(final_video["sha256"] == sha256(args.video), "Final MP4 SHA-256 mismatch")
    require(final_video["bytes"] == args.video.stat().st_size, "Final MP4 size mismatch")
    require(report["visual"]["input_file_sha256"] == visual["output"]["sha256"], "Audio stage did not consume the visual-QC MP4")
    require(report["visual"]["bitstream_copy"] is True, "Visual bitstream was re-encoded")
    require(report["music"]["source_sha256"] == music["source_sha256"], "Audio report music diverges from RenderJob")
    require(report["voice"]["voice_id"] == voice["voice_id"], "Audio report voice diverges from RenderJob")
    require(
        {f"S{item['scene']}": item["source_sha256"] for item in report["voice"]["clips"]} == clip_hashes,
        "Audio report voice clips diverge from RenderJob",
    )
    require(final_video["audio_codec"] == "aac", "Final audio codec must be AAC")
    require(final_video["audio_sample_rate"] == 48_000 and final_video["audio_channels"] == 2, "Final audio layout must be stereo 48 kHz")
    require(-16.6 <= float(final_video["integrated_lufs"]) <= -15.4, "Final loudness is out of contract")
    require(float(final_video["true_peak_dbtp"]) <= -1.0, "Final true peak is out of contract")
    require(abs(float(final_video["duration_s"]) - 30.0) <= 0.025, "Final duration is out of contract")

    result = deepcopy(visual)
    result["status"] = "COMPLETED"
    result["profile_used"] = "T5_GITHUB_ACTIONS_COMPLETE_V1"
    result["output"]["sha256"] = final_video["sha256"]
    result["output"]["bytes"] = final_video["bytes"]
    result["inputs"].update({
        "audio_contract_sha256": audio["contract_sha256"],
        "music_source_sha256": music["source_sha256"],
        "voice_manifest_sha256": voice["manifest_sha256"],
        "voice_clip_source_sha256": voice["clip_source_sha256"],
    })
    result["audio_quality"] = {
        "status": "PASS",
        "report": "T5_COMPLETE_AUDIO_RENDER_REPORT.json",
        "passed": report["summary"]["passed"],
        "total": report["summary"]["total"],
    }
    result["audio"] = {
        "mode": audio["mode"],
        "music": {
            "selected_choice": music["selected_choice"],
            "pixabay_id": music["pixabay_id"],
            "title": music["title"],
            "artist": music["artist"],
            "source_sha256": music["source_sha256"],
            "source_bundled": music["source_bundled"],
        },
        "voice": {
            "selected_option": voice["selected_option"],
            "voice_id": voice["voice_id"],
            "manifest_sha256": voice["manifest_sha256"],
            "clip_source_sha256": voice["clip_source_sha256"],
        },
        "final_mix": {
            "audio_codec": final_video["audio_codec"],
            "sample_rate_hz": final_video["audio_sample_rate"],
            "channels": final_video["audio_channels"],
            "integrated_lufs": final_video["integrated_lufs"],
            "true_peak_dbtp": final_video["true_peak_dbtp"],
            "duration_s": final_video["duration_s"],
            "one_audio_stream": True,
        },
        "visual_bitstream_copy": report["visual"]["bitstream_copy"],
    }
    result["audio_state_commit_allowed"] = True

    Draft202012Validator(schema).validate(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "T5_COMPLETE_RENDER_RESULT_PASS",
        f"visual={result['quality']['passed']}/{result['quality']['total']}",
        f"audio={result['audio_quality']['passed']}/{result['audio_quality']['total']}",
        result["output"]["sha256"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
