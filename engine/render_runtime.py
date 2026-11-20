#!/usr/bin/env python3
"""Rendu T5 dynamique : quatre captures vérifiées et six réponses du RenderJob."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, BinaryIO, Iterator

from jsonschema import Draft202012Validator
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapter.t5_adapter import canonical_sha256
from engine.runtime_visual import (
    FIELD_BOXES,
    HEIGHT,
    SCENE_FRAMES,
    WIDTH,
    changed_pixel_count,
    render_scene_frame,
    resolved_scene_copy,
    slide_transition,
)

SLOTS = ("S1", "S2", "S3", "S4")
TRANSITIONS = {"S2": "slideleft", "S3": "slideright", "S4": "slideleft"}
TRANSITION_FRAMES = 8
MUTATIONS = {
    "nom": "Autre Restaurant",
    "offre": "Autre Formule",
    "contenu": "2 burgers, 2 portions de frites et 2 colas",
    "prix": "7 500 FCFA",
    "whatsapp": "+229 01 00 11 22 33",
    "quartier": "Autre lieu de retrait",
}
FIELD_PROOF_SCENE = {"nom": "S1", "offre": "S1", "contenu": "S2", "prix": "S3", "whatsapp": "S4", "quartier": "S4"}
FIELD_PROOF_LOCAL_FRAME = {"S1": 105, "S2": 135, "S3": 110, "S4": 120}
CONTACT_FRAMES = {45, 120, 165, 225, 315, 390, 465, 555, 600, 675, 780, 870}
OUTPUT_FILENAME = "VIDEO_T5_FORMULE_RUNTIME_DYNAMIQUE_V2_A_VALIDER.mp4"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_exact(stream: BinaryIO, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        block = stream.read(remaining)
        if not block:
            break
        chunks.append(block)
        remaining -= len(block)
    return b"".join(chunks)


def decode_frames(path: Path, start_seconds: float, count: int) -> Iterator[Image.Image]:
    command = [
        "ffmpeg", "-v", "error", "-ss", f"{start_seconds:.3f}", "-i", str(path),
        "-an", "-vf", "scale=720:405:force_original_aspect_ratio=decrease,pad=720:405:(ow-iw)/2:(oh-ih)/2:color=black,fps=30",
        "-frames:v", str(count), "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1",
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None
    frame_size = 720 * 405 * 3
    produced = 0
    try:
        for _ in range(count):
            raw = read_exact(process.stdout, frame_size)
            if len(raw) != frame_size:
                break
            produced += 1
            yield Image.frombytes("RGB", (720, 405), raw)
    finally:
        process.stdout.close()
        stderr = process.stderr.read().decode("utf-8", "replace") if process.stderr else ""
        return_code = process.wait()
        if return_code or produced != count:
            raise RuntimeError(f"FFmpeg decoded {produced}/{count} frames from {path}: {stderr[-2000:]}")


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


def capture_path(directory: Path, local_file: str) -> Path:
    path = directory / local_file
    if not path.is_file():
        raise FileNotFoundError(f"Runtime capture missing: {path}")
    return path


def make_contact_sheet(images: dict[int, Image.Image], destination: Path) -> None:
    ordered = [images[frame] for frame in sorted(images)]
    if len(ordered) != 12:
        raise RuntimeError(f"Expected 12 contact images, got {len(ordered)}")
    thumb_size = (180, 320)
    sheet = Image.new("RGB", (thumb_size[0] * 4, thumb_size[1] * 3), "white")
    draw = ImageDraw.Draw(sheet)
    for index, image in enumerate(ordered):
        thumb = image.resize(thumb_size, Image.Resampling.LANCZOS)
        x = (index % 4) * thumb_size[0]
        y = (index // 4) * thumb_size[1]
        sheet.paste(thumb, (x, y))
        draw.rectangle((x, y, x + 60, y + 24), fill="#130E0A")
        draw.text((x + 6, y + 5), f"{sorted(images)[index] / 30:.1f}s", fill="white")
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination, quality=92, subsampling=0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render-job", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--capture-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    job = json.loads(args.render_job.read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "schemas/T5_render_job.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(job)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest.get("job_id") != job["job_id"] or manifest.get("idempotency_key") != job["idempotency_key"]:
        raise SystemExit("Runtime manifest is attached to another RenderJob")
    if [scene["scene"] for scene in manifest["scenes"]] != list(SLOTS):
        raise SystemExit("Runtime manifest must bind S1, S2, S3 and S4 in order")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / OUTPUT_FILENAME
    temporary = args.output_dir / ".rendering.mp4"
    payload = job["merchant_payload"]
    resolved = {
        "schema_version": "1.0.0",
        "job_id": job["job_id"],
        "source": "merchant_payload",
        "merchant_payload": payload,
        "scenes": [asdict(resolved_scene_copy(slot, payload)) for slot in SLOTS],
    }
    resolved_path = args.output_dir / "T5_RESOLVED_TEXT.json"
    resolved_path.write_text(json.dumps(resolved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    encoder = subprocess.Popen(
        [
            "ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", f"{WIDTH}x{HEIGHT}", "-r", "30", "-i", "pipe:0", "-an",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
            "-r", "30", "-frames:v", "900", "-movflags", "+faststart", str(temporary),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    assert encoder.stdin is not None

    contact_images: dict[int, Image.Image] = {}
    field_evidence: dict[str, Any] = {}
    capture_evidence: dict[str, Any] = {}
    previous_final: Image.Image | None = None
    global_frame = 0
    try:
        for scene_record in manifest["scenes"]:
            slot = scene_record["scene"]
            declared = job["captures"][slot]
            source = capture_path(args.capture_dir, scene_record["local_file"])
            if sha256(source) != declared["sha256"] or scene_record["sha256"] != declared["sha256"]:
                raise RuntimeError(f"Capture {slot} diverges after manifest materialization")
            total_frames = SCENE_FRAMES[slot]
            freeze_frames = int(scene_record["freeze_tail_seconds"] * 30)
            moving_frames = total_frames - freeze_frames
            decoder = decode_frames(source, float(scene_record["source_in_seconds"]), moving_frames)
            last_source: Image.Image | None = None
            scene_mid_image: Image.Image | None = None
            for local_frame in range(total_frames):
                if local_frame < moving_frames:
                    last_source = next(decoder)
                if last_source is None:
                    raise RuntimeError(f"Capture {slot} produced no frame")
                display_frame = total_frames - 1 if freeze_frames and local_frame >= moving_frames else local_frame
                current, active_fields = render_scene_frame(last_source, slot, display_frame, payload)
                if previous_final is not None and local_frame < TRANSITION_FRAMES:
                    current = slide_transition(previous_final, current, (local_frame + 1) / TRANSITION_FRAMES, TRANSITIONS[slot])
                encoder.stdin.write(current.tobytes())

                if global_frame in CONTACT_FRAMES:
                    contact_images[global_frame] = current.copy()
                if local_frame == total_frames // 2:
                    scene_mid_image = current.copy()
                proof_frame = FIELD_PROOF_LOCAL_FRAME[slot]
                if local_frame == proof_frame:
                    for field, proof_scene in FIELD_PROOF_SCENE.items():
                        if proof_scene != slot:
                            continue
                        modified = dict(payload)
                        modified[field] = MUTATIONS[field]
                        changed, _ = render_scene_frame(last_source, slot, display_frame, modified)
                        pixel_count, bbox = changed_pixel_count(current, changed)
                        if pixel_count < 100:
                            raise RuntimeError(f"Field {field} did not change real pixels in {slot}")
                        field_evidence[field] = {
                            "scene": slot,
                            "global_frame": global_frame,
                            "time_seconds": global_frame / 30,
                            "target_box": FIELD_BOXES[slot][field],
                            "changed_pixels": pixel_count,
                            "difference_bbox": bbox,
                            "rendered_value_sha256": sha256_bytes(payload[field].encode("utf-8")),
                            "active_fields": list(active_fields),
                        }
                previous_final = current.copy() if local_frame == total_frames - 1 else previous_final
                global_frame += 1
            decoder.close()
            if scene_mid_image is None:
                raise RuntimeError(f"No proof image for {slot}")
            hero = scene_mid_image.crop((30, 120, 690, 518))
            capture_evidence[slot] = {
                "capture_sha256": declared["sha256"],
                "timeline_frames": scene_record["timeline_frames"],
                "hero_pixels_sha256": sha256_bytes(hero.tobytes()),
                "local_file": scene_record["local_file"],
            }
        encoder.stdin.close()
        stderr = encoder.stderr.read().decode("utf-8", "replace") if encoder.stderr else ""
        return_code = encoder.wait()
        if return_code:
            raise RuntimeError(f"FFmpeg encoder failed: {stderr[-4000:]}")
    except Exception:
        try:
            encoder.stdin.close()
        except Exception:
            pass
        encoder.kill()
        encoder.wait()
        temporary.unlink(missing_ok=True)
        raise

    if global_frame != 900 or set(field_evidence) != set(MUTATIONS) or set(capture_evidence) != set(SLOTS):
        raise RuntimeError("Runtime evidence is incomplete")
    temporary.replace(output)
    contact = args.output_dir / "T5_RUNTIME_PLANCHE_12_IMAGES.jpg"
    make_contact_sheet(contact_images, contact)

    report = {
        "schema_version": "2.0.0",
        "template_id": "RESTAURATION-T5",
        "template_version": "2.0.0-runtime",
        "job_id": job["job_id"],
        "status": "RENDERED_PENDING_QC",
        "profile": "T5_GITHUB_ACTIONS_RUNTIME_V2",
        "control_plane": job["control_plane"],
        "render_plane": "github_actions",
        "visual_mode": "runtime_hybrid_render",
        "output": {"file": output.name, "bytes": output.stat().st_size, "sha256": sha256(output)},
        "contact_sheet": {"file": contact.name, "bytes": contact.stat().st_size, "sha256": sha256(contact)},
        "runtime_manifest": {"file": args.manifest.name, "sha256": sha256(args.manifest)},
        "resolved_text": {"file": resolved_path.name, "sha256": sha256(resolved_path)},
        "merchant_payload_sha256": canonical_sha256(payload),
        "rendered_fields": list(MUTATIONS),
        "field_pixel_evidence": field_evidence,
        "scene_capture_evidence": capture_evidence,
        "probe": probe(output),
        "raw_media_published": False,
    }
    report_path = args.output_dir / "T5_RUNTIME_RENDER_REPORT.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"T5_RUNTIME_RENDERED {output} {report['output']['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
