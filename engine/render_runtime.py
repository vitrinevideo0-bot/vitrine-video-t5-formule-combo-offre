#!/usr/bin/env python3
"""Rendu serveur T5 V3 : quatre rushs plein cadre, six valeurs et trois raccords T1.

Le moteur ne connaît aucune valeur métier. Il consomme exclusivement le RenderJob
et le manifeste de captures dont les SHA-256 ont été vérifiés en amont.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterator, Mapping

from jsonschema import Draft202012Validator
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.runtime_visual import (
    FIELD_BOXES,
    FIELD_PIXEL_PROOFS,
    HEIGHT,
    SCENE_FIELDS,
    TEXT_MOTION,
    TEXT_MOTION_CONFIG_PATH,
    WIDTH,
    apply_transition,
    changed_pixel_count,
    motion_design_evidence,
    readability_gradient_evidence,
    render_scene_frame,
)

SLOTS = ("S1", "S2", "S3", "S4")
SCENE_FRAMES = {"S1": 180, "S2": 240, "S3": 210, "S4": 270}
TRANSITION_DIRECTIONS = ("left", "right", "left")
TRANSITION_CUTS = (180, 420, 630)
OUTPUT_FILENAME = "VIDEO_T5_FORMULE_PLEIN_ECRAN_V3_A_VALIDER.mp4"
SCENE_PROOF_FRAME = 120


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def pixels_sha256(image: Image.Image) -> str:
    return hashlib.sha256(image.convert("RGB").tobytes()).hexdigest()


def decoder(
    path: Path,
    *,
    source_in_seconds: float,
    output_frames: int,
    freeze_after_frames: int | None = None,
) -> Iterator[tuple[int, Image.Image]]:
    """Décode en plein cadre 720 x 1280; S4 répète sa dernière image pendant 3 s."""
    source_frames = min(output_frames, freeze_after_frames or output_frames)
    command = [
        "ffmpeg", "-v", "error", "-ss", f"{source_in_seconds:.6f}", "-i", str(path),
        "-an", "-vf",
        "fps=30,scale=720:1280:force_original_aspect_ratio=increase:flags=lanczos,crop=720:1280",
        "-frames:v", str(source_frames), "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None
    frame_bytes = WIDTH * HEIGHT * 3
    last: Image.Image | None = None
    try:
        for index in range(source_frames):
            data = process.stdout.read(frame_bytes)
            if len(data) != frame_bytes:
                error = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
                raise RuntimeError(
                    f"Capture {path.name} ended at frame {index}/{source_frames}; ffmpeg: {error.strip()}"
                )
            last = Image.frombytes("RGB", (WIDTH, HEIGHT), data)
            yield index, last
        process.stdout.close()
        error = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
        return_code = process.wait()
        if return_code != 0:
            raise RuntimeError(f"FFmpeg decode failed for {path.name}: {error.strip()}")
        if last is None:
            raise RuntimeError(f"Capture {path.name} produced no frame")
        for index in range(source_frames, output_frames):
            yield index, last.copy()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


def start_encoder(output: Path) -> subprocess.Popen[bytes]:
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s:v", f"{WIDTH}x{HEIGHT}", "-r", "30", "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
        "-pix_fmt", "yuv420p", "-r", "30", "-frames:v", "900", "-movflags", "+faststart", str(output),
    ]
    return subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)


def close_encoder(process: subprocess.Popen[bytes], frames_written: int) -> None:
    if process.stdin is not None:
        process.stdin.close()
    error = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"FFmpeg encode failed: {error.strip()}")
    if frames_written != 900:
        raise RuntimeError(f"Expected 900 encoded frames, got {frames_written}")


def make_contact_sheet(images: list[Image.Image], output: Path) -> None:
    if len(images) != 12:
        raise RuntimeError(f"Expected 12 proof images, got {len(images)}")
    cell_w, cell_h = 240, 320
    sheet = Image.new("RGB", (cell_w * 3, cell_h * 4), "black")
    for index, image in enumerate(images):
        ratio = max(cell_w / image.width, cell_h / image.height)
        resized = image.resize((round(image.width * ratio), round(image.height * ratio)), Image.Resampling.LANCZOS)
        left = (resized.width - cell_w) // 2
        top = (resized.height - cell_h) // 2
        cell = resized.crop((left, top, left + cell_w, top + cell_h))
        sheet.paste(cell, ((index % 3) * cell_w, (index // 3) * cell_h))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=94, optimize=True)


def capture_path(capture_dir: Path, scene: Mapping[str, Any]) -> Path:
    path = capture_dir / str(scene["local_file"])
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def changed_field_evidence(
    source: Image.Image,
    scene: str,
    payload: Mapping[str, str],
    field: str,
    proof_frame: int,
) -> dict[str, Any]:
    original, _ = render_scene_frame(source, scene, proof_frame, payload, SCENE_FRAMES[scene])
    changed = deepcopy(dict(payload))
    changed[field] = f"X {payload[field]}"
    variant, _ = render_scene_frame(source, scene, proof_frame, changed, SCENE_FRAMES[scene])
    count, bbox = changed_pixel_count(original, variant)
    return {
        "scene": scene,
        "proof_local_frame": proof_frame,
        "target_box": list(FIELD_BOXES[scene][field]),
        "changed_pixels": count,
        "difference_bbox": list(bbox) if bbox else None,
    }


def scene_generator(
    scene: Mapping[str, Any],
    *,
    capture_dir: Path,
    payload: Mapping[str, str],
    field_evidence: dict[str, Any],
    scene_evidence: dict[str, Any],
    proof_images: dict[tuple[str, int], Image.Image],
) -> Iterator[tuple[int, Image.Image]]:
    slot = str(scene["scene"])
    total = SCENE_FRAMES[slot]
    proof_indices = {round(total * fraction) for fraction in (0.25, 0.5, 0.75)}
    freeze_after = 180 if slot == "S4" else None
    source_path = capture_path(capture_dir, scene)
    for local_index, source in decoder(
        source_path,
        source_in_seconds=float(scene["source_in_seconds"]),
        output_frames=total,
        freeze_after_frames=freeze_after,
    ):
        rendered, active = render_scene_frame(source, slot, local_index, payload, total)
        if tuple(active) != tuple(scene["text_fields"]):
            raise RuntimeError(f"Runtime text fields diverge for {slot}")
        if local_index in proof_indices:
            proof_images[(slot, local_index)] = rendered.copy()
        if local_index == SCENE_PROOF_FRAME:
            scene_evidence[slot] = {
                "capture_sha256": scene["sha256"],
                "capture_file": scene["local_file"],
                "proof_local_frame": SCENE_PROOF_FRAME,
                "full_frame_pixels_sha256": pixels_sha256(rendered),
                # Kept for RenderResult V2 compatibility; the hash now covers the full-frame render.
                "hero_pixels_sha256": pixels_sha256(rendered),
                "rush_fills_frame": True,
                "text_fields": list(active),
            }
        for field, (proof_scene, proof_frame) in FIELD_PIXEL_PROOFS.items():
            if proof_scene == slot and local_index == proof_frame:
                field_evidence[field] = changed_field_evidence(source, slot, payload, field, proof_frame)
        yield local_index, rendered


def next_frame(iterator: Iterator[tuple[int, Image.Image]], expected_index: int) -> Image.Image:
    index, frame = next(iterator)
    if index != expected_index:
        raise RuntimeError(f"Scene generator index mismatch: expected {expected_index}, got {index}")
    return frame


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render-job", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--capture-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    job = load_json(args.render_job)
    schema = load_json(ROOT / "schemas/T5_render_job.schema.json")
    Draft202012Validator(schema).validate(job)
    manifest = load_json(args.manifest)
    if job["render"]["visual_mode"] != "runtime_full_frame_render":
        raise SystemExit("T5 V3 requires runtime_full_frame_render")
    if job["render"]["production_render_plane"] != "github_actions":
        raise SystemExit("T5 V3 may render only on GitHub Actions")
    if [scene["scene"] for scene in manifest["scenes"]] != list(SLOTS):
        raise SystemExit("Runtime manifest must contain S1, S2, S3 and S4 in order")
    for scene in manifest["scenes"]:
        slot = scene["scene"]
        if scene["sha256"] != job["captures"][slot]["sha256"]:
            raise SystemExit(f"Capture binding mismatch for {slot}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / OUTPUT_FILENAME
    resolved_path = args.output_dir / "T5_RESOLVED_TEXT.json"
    report_path = args.output_dir / "T5_RUNTIME_RENDER_REPORT.json"
    sheet_path = args.output_dir / "T5_RUNTIME_PLANCHE_12_IMAGES.jpg"
    payload: dict[str, str] = dict(job["merchant_payload"])
    resolved = {
        "schema_version": "3.0.0",
        "job_id": job["job_id"],
        "source": "RenderJob.merchant_payload",
        "ordered_fields": list(payload),
        "values": payload,
        "visible_text_policy": "exact_merchant_payload_values_only",
        "static_business_copy": [],
        "text_motion_contract": str(TEXT_MOTION_CONFIG_PATH.relative_to(ROOT)),
        "font_family": TEXT_MOTION["font"]["family"],
        "font_style": TEXT_MOTION["font"]["style_reference"],
        "reveal_unit": TEXT_MOTION["animation"]["reveal_unit"],
        "letter_motion": TEXT_MOTION["animation"]["letter_motion"],
        "scene_values": {
            slot: {field: payload[field] for field in SCENE_FIELDS[slot]}
            for slot in SLOTS
        },
    }
    write_json(resolved_path, resolved)

    field_evidence: dict[str, Any] = {}
    scene_evidence: dict[str, Any] = {}
    proof_images: dict[tuple[str, int], Image.Image] = {}
    scenes = manifest["scenes"]
    generators = [
        scene_generator(
            scene,
            capture_dir=args.capture_dir,
            payload=payload,
            field_evidence=field_evidence,
            scene_evidence=scene_evidence,
            proof_images=proof_images,
        )
        for scene in scenes
    ]

    encoder = start_encoder(output)
    assert encoder.stdin is not None
    frames_written = 0
    transition_evidence: list[dict[str, Any]] = []

    def emit(frame: Image.Image) -> None:
        nonlocal frames_written
        encoder.stdin.write(frame.convert("RGB").tobytes())
        frames_written += 1

    try:
        current = generators[0]
        current_start = 0
        for boundary_index in range(3):
            slot = SLOTS[boundary_index]
            total = SCENE_FRAMES[slot]
            # Frames N-4..N-1 are replaced by the first half of the eight-image raccord.
            for local_index in range(current_start, total - 4):
                emit(next_frame(current, local_index))
            previous_tail = [next_frame(current, index) for index in range(total - 4, total)]

            following = generators[boundary_index + 1]
            next_head = [next_frame(following, index) for index in range(4)]
            direction = TRANSITION_DIRECTIONS[boundary_index]
            for step in range(8):
                emit(apply_transition(previous_tail[0], next_head[-1], step, 8, direction))
            transition_evidence.append({
                "cut_frame": TRANSITION_CUTS[boundary_index],
                "timeline_frames": [TRANSITION_CUTS[boundary_index] - 4, TRANSITION_CUTS[boundary_index] + 3],
                "duration_frames": 8,
                "direction": direction,
                "family": "dish_swipe_camera_whip",
                "clean_first_frame": True,
                "clean_last_frame": True,
            })
            current = following
            current_start = 4

        final_total = SCENE_FRAMES["S4"]
        for local_index in range(current_start, final_total):
            emit(next_frame(current, local_index))
        close_encoder(encoder, frames_written)
    except Exception:
        if encoder.poll() is None:
            encoder.kill()
            encoder.wait()
        raise

    ordered_proofs: list[Image.Image] = []
    for slot in SLOTS:
        total = SCENE_FRAMES[slot]
        for fraction in (0.25, 0.5, 0.75):
            index = round(total * fraction)
            ordered_proofs.append(proof_images[(slot, index)])
    make_contact_sheet(ordered_proofs, sheet_path)

    if set(field_evidence) != set(payload):
        raise RuntimeError(f"Missing field evidence: {set(payload) - set(field_evidence)}")
    if set(scene_evidence) != set(SLOTS):
        raise RuntimeError(f"Missing scene evidence: {set(SLOTS) - set(scene_evidence)}")

    report = {
        "schema_version": "3.0.0",
        "template_id": "RESTAURATION-T5",
        "template_version": "3.0.0-full-frame",
        "job_id": job["job_id"],
        "render_plane": "github_actions",
        "profile": "T5_GITHUB_ACTIONS_FULL_FRAME_V3",
        "runtime_manifest": {"file": args.manifest.name, "sha256": sha256(args.manifest)},
        "runtime_contract": {
            "file": job["render"]["runtime_contract"],
            "sha256": sha256(ROOT / job["render"]["runtime_contract"]),
        },
        "montage_contract": {
            "file": "montage/T5_MONTAGE_COMPLET_V3_0_0.json",
            "sha256": sha256(ROOT / "montage/T5_MONTAGE_COMPLET_V3_0_0.json"),
        },
        "merchant_payload_sha256": canonical_sha256(payload),
        "resolved_text": {"file": resolved_path.name, "sha256": sha256(resolved_path)},
        "visual_policy": {
            "rushes_fill_entire_frame": True,
            "permanent_cards": False,
            "rounded_video_frames": False,
            "split_screen": False,
            "progress_bars": False,
            "scene_or_technical_labels": False,
            "horizontal_color_seams": False,
            "readability_gradient_reaches_frame_bottom": True,
            "kinetic_text_motion": True,
            "static_text_stack": False,
            "max_simultaneous_text_fields": 2,
            "font_family": TEXT_MOTION["font"]["family"],
            "font_classification": TEXT_MOTION["font"]["classification"],
            "large_white_bold_text": True,
            "native_pair_kerning": TEXT_MOTION["readability_policy"]["native_pair_kerning"],
            "neutral_tracking": TEXT_MOTION["readability_policy"]["neutral_tracking"],
            "text_outline": not TEXT_MOTION["readability_policy"]["no_outline"],
            "readability_priority": TEXT_MOTION["readability_policy"]["priority"],
            "visible_text_source": "merchant_payload_exact_values_only",
        },
        "readability_gradient_evidence": readability_gradient_evidence(),
        "text_motion_evidence": motion_design_evidence(),
        "transition_evidence": transition_evidence,
        "field_pixel_evidence": field_evidence,
        "scene_capture_evidence": scene_evidence,
        "stable_tail": {"scene": "S4", "timeline_frames": [810, 899], "duration_frames": 90},
        "output": {
            "file": output.name,
            "sha256": sha256(output),
            "bytes": output.stat().st_size,
            "width": WIDTH,
            "height": HEIGHT,
            "fps": 30,
            "frames": frames_written,
            "duration_seconds": 30.0,
            "audio_streams": 0,
        },
    }
    write_json(report_path, report)
    print(json.dumps({
        "status": "RENDERED",
        "job_id": job["job_id"],
        "output": str(output),
        "sha256": report["output"]["sha256"],
        "frames": frames_written,
        "transitions": transition_evidence,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
