#!/usr/bin/env python3
"""Contrôle le MP4 T5 runtime puis émet un RenderResult conforme."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any

from jsonschema import Draft202012Validator
from PIL import Image, ImageChops, ImageStat

ROOT = Path(__file__).resolve().parents[1]
SLOTS = ("S1", "S2", "S3", "S4")
FIELDS = ("nom", "offre", "contenu", "prix", "whatsapp", "quartier")


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
            "ffprobe", "-v", "error", "-count_frames", "-show_entries",
            "format=duration,size:stream=index,codec_type,codec_name,width,height,avg_frame_rate,pix_fmt,nb_read_frames",
            "-of", "json", str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def final_stability(path: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="t5-runtime-stability-") as folder_name:
        folder = Path(folder_name)
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error", "-i", str(path),
                "-vf", "select='eq(n,810)+eq(n,899)'", "-vsync", "0", str(folder / "%d.png"),
            ],
            check=True,
        )
        first = Image.open(folder / "1.png").convert("RGB")
        last = Image.open(folder / "2.png").convert("RGB")
        difference = ImageChops.difference(first, last)
        mean = sum(ImageStat.Stat(difference).mean) / 3
        return {
            "first_frame": 810,
            "last_frame": 899,
            "mean_absolute_pixel_difference": round(mean, 6),
            "threshold": 1.0,
            "pass": mean < 1.0,
        }


def intersects(a: list[int], b: list[int] | tuple[int, ...] | None) -> bool:
    if not b:
        return False
    return max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--render-job", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--render-report", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()

    job = json.loads(args.render_job.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    render_report = json.loads(args.render_report.read_text(encoding="utf-8"))
    info = probe(args.video)
    video_streams = [stream for stream in info["streams"] if stream["codec_type"] == "video"]
    audio_streams = [stream for stream in info["streams"] if stream["codec_type"] == "audio"]
    video = video_streams[0] if video_streams else {}
    field_evidence = render_report.get("field_pixel_evidence", {})
    scene_evidence = render_report.get("scene_capture_evidence", {})
    stability = final_stability(args.video)

    fields_are_dynamic = set(field_evidence) == set(FIELDS) and all(
        evidence.get("changed_pixels", 0) > 100
        and intersects(evidence.get("target_box", []), evidence.get("difference_bbox"))
        for evidence in field_evidence.values()
    )
    captures_are_bound = set(scene_evidence) == set(SLOTS) and all(
        scene_evidence[slot].get("capture_sha256") == job["captures"][slot]["sha256"]
        for slot in SLOTS
    )
    distinct_capture_pixels = len({scene_evidence[slot].get("hero_pixels_sha256") for slot in SLOTS}) == 4
    raw_media_absent = not any(
        path.name.startswith(tuple(SLOTS)) and path.suffix.lower() in {".mp4", ".mov", ".webm"}
        for path in args.video.parent.iterdir()
    )
    visual_policy = render_report.get("visual_policy", {})
    full_frame_policy = (
        visual_policy.get("rushes_fill_entire_frame") is True
        and visual_policy.get("permanent_cards") is False
        and visual_policy.get("rounded_video_frames") is False
        and visual_policy.get("split_screen") is False
        and visual_policy.get("progress_bars") is False
        and visual_policy.get("scene_or_technical_labels") is False
        and visual_policy.get("horizontal_color_seams") is False
        and visual_policy.get("readability_gradient_reaches_frame_bottom") is True
        and visual_policy.get("kinetic_text_motion") is False
        and visual_policy.get("timed_subtitle_blocks") is True
        and visual_policy.get("per_letter_animation") is False
        and visual_policy.get("static_text_stack") is False
        and visual_policy.get("max_simultaneous_text_fields") == 2
        and visual_policy.get("font_family") == "Playfair Display"
        and visual_policy.get("font_classification") == "readable editorial display serif"
        and visual_policy.get("large_white_bold_text") is True
        and visual_policy.get("uniform_baseline") is True
        and visual_policy.get("centered_horizontally") is True
        and visual_policy.get("constant_letter_spacing") is True
        and visual_policy.get("decorative_alternates_disabled") is True
        and visual_policy.get("maximum_text_lines") == 2
        and visual_policy.get("line_height_ratio") == 1.2
        and visual_policy.get("fine_dark_outline") is True
        and visual_policy.get("subtle_shadow") is True
        and visual_policy.get("readability_priority") == "maximum"
    )
    gradient = render_report.get("readability_gradient_evidence", {})
    gradient_is_continuous = (
        gradient.get("reaches_frame_bottom") is True
        and gradient.get("last_row") == int(render_report["output"]["height"]) - 1
        and gradient.get("bottom_alpha", 0) > 0
        and gradient.get("monotonic_non_decreasing") is True
        and gradient.get("max_adjacent_alpha_jump", 999) <= 1
    )
    motion = render_report.get("text_motion_evidence", {})
    motion_contract = motion.get("contract", {})
    motion_font = motion.get("font", {})
    motion_contract_path = ROOT / str(motion_contract.get("file", "missing"))
    motion_font_path = ROOT / str(motion_font.get("file", "missing"))
    stable_subtitles_are_contract_bound = (
        motion_contract_path.is_file()
        and motion_font_path.is_file()
        and motion_contract.get("sha256") == sha256(motion_contract_path)
        and motion_font.get("sha256") == sha256(motion_font_path)
        and motion_font.get("family") == "Playfair Display"
        and motion_font.get("classification") == "readable editorial display serif"
        and motion_font.get("style_reference") == "Didot-inspired editorial serif optimized for screen readability"
        and motion_font.get("license") == "OFL-1.1"
        and motion_font.get("variation_axes", {}).get("wght", {}).get("maximum") == 900
        and motion.get("reveal_unit") == "block"
        and motion.get("sequence") == "timed_field_blocks"
        and motion.get("alignment") == "center"
        and motion.get("per_letter_animation") is False
        and motion.get("uniform_baseline") is True
        and motion.get("rotation_degrees") == 0
        and motion.get("composition") == "centered_stable_subtitles"
        and motion.get("case_transform") == "none"
        and motion.get("opentype_features_disabled") == ["kern", "liga", "clig", "dlig", "calt", "salt", "swsh"]
        and motion.get("white_outlined_editorial_style") is True
        and motion.get("constant_letter_spacing") is True
        and motion.get("readability_policy") == {
            "priority": "maximum",
            "same_font_family": True,
            "uniform_baseline": True,
            "constant_letter_spacing": True,
            "regular_word_spacing": True,
            "decorative_alternates_disabled": True,
            "centered_horizontally": True,
            "line_height_ratio": 1.2,
            "maximum_lines": 2,
            "target_words_per_line": [4, 6],
            "minimum_preferred_size": 52,
            "minimum_weight": 800,
            "side_safe_margin_pixels": 50,
            "bottom_safe_margin_pixels": 150,
            "fine_dark_outline": True,
            "subtle_shadow": True,
            "block_entry_only": True,
        }
        and motion.get("static_all_fields_from_first_frame") is False
        and motion.get("text_background_boxes") is False
        and motion.get("max_simultaneous_fields") == 2
        and motion.get("scene_max_simultaneous_fields") == {"S1": 1, "S2": 1, "S3": 1, "S4": 2}
        and motion.get("stable_tail") == {
            "start_frame": 180,
            "end_frame": 269,
            "visible_fields": ["whatsapp", "quartier"],
        }
    )
    resolved_path = args.render_report.parent / render_report["resolved_text"]["file"]
    resolved = json.loads(resolved_path.read_text(encoding="utf-8"))
    exact_text_policy = (
        visual_policy.get("visible_text_source") == "merchant_payload_exact_values_only"
        and resolved.get("values") == job["merchant_payload"]
        and resolved.get("static_business_copy") == []
        and resolved.get("text_motion_contract") == "config/T5_TEXT_MOTION_V4_0_0.json"
        and resolved.get("font_family") == "Playfair Display"
        and resolved.get("font_style") == "Didot-inspired editorial serif optimized for screen readability"
        and resolved.get("reveal_unit") == "block"
        and resolved.get("per_letter_animation") is False
        and resolved.get("alignment") == "center"
        and resolved.get("uniform_baseline") is True
        and resolved.get("maximum_lines") == 2
        and resolved.get("line_height_ratio") == 1.2
    )
    transitions = render_report.get("transition_evidence", [])
    transitions_are_exact = (
        len(transitions) == 3
        and [item.get("cut_frame") for item in transitions] == [180, 420, 630]
        and [item.get("timeline_frames") for item in transitions] == [[176, 183], [416, 423], [626, 633]]
        and all(item.get("duration_frames") == 8 for item in transitions)
        and [item.get("direction") for item in transitions] == ["left", "right", "left"]
        and all(item.get("clean_first_frame") is True and item.get("clean_last_frame") is True for item in transitions)
    )

    checks = {
        "one_video_stream": len(video_streams) == 1,
        "no_audio_stream": len(audio_streams) == 0,
        "dimensions_720x1280": (video.get("width"), video.get("height")) == (720, 1280),
        "fps_30": video.get("avg_frame_rate") == "30/1",
        "frames_900": int(video.get("nb_read_frames", 0)) == 900,
        "duration_30_seconds": abs(float(info["format"]["duration"]) - 30.0) < 0.001,
        "h264_yuv420p": video.get("codec_name") == "h264" and video.get("pix_fmt") == "yuv420p",
        "output_sha_matches_render_report": sha256(args.video) == render_report["output"]["sha256"],
        "six_fields_change_real_pixels": fields_are_dynamic,
        "four_scenes_consume_declared_captures": captures_are_bound,
        "four_visual_windows_are_distinct": distinct_capture_pixels,
        "rushes_are_full_frame_without_cards": full_frame_policy,
        "readability_gradient_is_continuous_to_frame_bottom": gradient_is_continuous,
        "subtitles_are_centered_stable_blocks_and_contract_bound": stable_subtitles_are_contract_bound,
        "visible_text_is_exactly_from_merchant_payload": exact_text_policy,
        "three_t1_transitions_are_exactly_eight_frames": transitions_are_exact,
        "runtime_manifest_is_hash_bound": sha256(args.manifest) == render_report["runtime_manifest"]["sha256"],
        "resolved_text_is_from_render_job": render_report["merchant_payload_sha256"] == canonical_sha256(job["merchant_payload"]),
        "final_three_seconds_are_stable": stability["pass"],
        "raw_captures_are_not_in_output": raw_media_absent,
        "github_is_the_render_plane": render_report.get("render_plane") == "github_actions" and job["cloudflare_rendering_forbidden"] is True,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    validation = {
        "schema_version": "3.0.0",
        "template_id": "RESTAURATION-T5",
        "job_id": job["job_id"],
        "status": status,
        "video": {"file": args.video.name, "bytes": args.video.stat().st_size, "sha256": sha256(args.video)},
        "checks": checks,
        "passed": sum(checks.values()),
        "total": len(checks),
        "final_stability": stability,
        "probe": info,
    }
    args.validation.parent.mkdir(parents=True, exist_ok=True)
    args.validation.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if status != "PASS":
        raise SystemExit(json.dumps(validation, ensure_ascii=False, indent=2))

    scene_bindings = [
        {
            "scene": slot,
            "capture_slot": slot,
            "capture_sha256": job["captures"][slot]["sha256"],
            "timeline_start_frame": manifest["scenes"][index]["timeline_frames"][0],
            "timeline_end_frame": manifest["scenes"][index]["timeline_frames"][1],
        }
        for index, slot in enumerate(SLOTS)
    ]
    result = {
        "schema_version": "1.0.0",
        "status": "VISUAL_COMPLETED",
        "job_id": job["job_id"],
        "idempotency_key": job["idempotency_key"],
        "template_id": "RESTAURATION-T5",
        "template_version": "3.0.0-full-frame",
        "profile_used": "T5_GITHUB_ACTIONS_FULL_FRAME_V3",
        "control_plane": job["control_plane"],
        "output": {
            "uri": job["output"]["uri"],
            "file": args.video.name,
            "sha256": sha256(args.video),
            "bytes": args.video.stat().st_size,
        },
        "quality": {
            "status": "PASS",
            "report": "T5_RUNTIME_VALIDATION.json",
            "passed": validation["passed"],
            "total": validation["total"],
        },
        "inputs": {
            "merchant_payload_sha256": canonical_sha256(job["merchant_payload"]),
            "capture_sha256": {slot: job["captures"][slot]["sha256"] for slot in SLOTS},
            "runtime_manifest_sha256": sha256(args.manifest),
            "resolved_text_sha256": sha256(resolved_path),
        },
        "rendered_fields": list(FIELDS),
        "scene_capture_bindings": scene_bindings,
    }
    result_schema = json.loads((ROOT / "schemas/T5_render_result.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(result_schema).validate(result)
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"T5_RUNTIME_VALIDATION_PASS {validation['passed']}/{validation['total']} {args.result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
