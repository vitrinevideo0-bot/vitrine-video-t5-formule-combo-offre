from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from PIL import Image, ImageChops
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapter.t5_adapter import build_render_job
from engine.runtime_visual import FIELD_BOXES, changed_pixel_count, proof_timeline, render_scene_frame
PAYLOAD = {
    "nom": "Burger Atelier Kandi",
    "offre": "Formule Double Burger",
    "contenu": "1 double burger, 1 portion de frites et 1 verre de cola",
    "prix": "5 000 FCFA",
    "whatsapp": "+229 01 97 00 00 00",
    "quartier": "Kandi, près du marché central",
}
CASES = [
    ("nom", "S1", 42, "Autre Restaurant"),
    ("offre", "S1", 94, "Autre Formule"),
    ("contenu", "S2", 120, "2 burgers, 2 frites et 2 colas"),
    ("prix", "S3", 180, "7 500 FCFA"),
    ("whatsapp", "S4", 112, "+229 01 00 11 22 33"),
    ("quartier", "S4", 172, "Autre lieu de retrait"),
]


def intersects(a: tuple[int, int, int, int], b: tuple[int, int, int, int] | None) -> bool:
    return bool(b) and max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3])


@pytest.mark.parametrize(("field", "scene", "proof_frame", "replacement"), CASES)
def test_each_form_answer_changes_pixels_in_its_motion_proof_block(
    field: str, scene: str, proof_frame: int, replacement: str
) -> None:
    source = Image.new("RGB", (720, 1280), "#9d5c35")
    original, active = render_scene_frame(source, scene, proof_frame, PAYLOAD)
    modified_payload = deepcopy(PAYLOAD)
    modified_payload[field] = replacement
    modified, modified_active = render_scene_frame(source, scene, proof_frame, modified_payload)
    count, bbox = changed_pixel_count(original, modified)
    assert field in active
    assert active == modified_active
    assert count > 100
    assert intersects(FIELD_BOXES[scene][field], bbox)


def test_s1_motion_shows_only_the_current_field_instead_of_the_old_three_field_stack() -> None:
    source = Image.new("RGB", (720, 1280), "#9d5c35")
    baseline, _ = render_scene_frame(source, "S1", 94, PAYLOAD)
    changed_hidden = deepcopy(PAYLOAD)
    changed_hidden["nom"] = "Nom invisible à cet instant"
    hidden_variant, _ = render_scene_frame(source, "S1", 94, changed_hidden)
    assert ImageChops.difference(baseline, hidden_variant).getbbox() is None
    changed_visible = deepcopy(PAYLOAD)
    changed_visible["offre"] = "Autre formule visible"
    visible_variant, _ = render_scene_frame(source, "S1", 94, changed_visible)
    assert ImageChops.difference(baseline, visible_variant).getbbox() is not None


def test_substituting_one_capture_changes_only_its_scene_window() -> None:
    captures = {
        "S1": Image.new("RGB", (720, 1280), "#8c2d20"),
        "S2": Image.new("RGB", (720, 1280), "#c28c34"),
        "S3": Image.new("RGB", (720, 1280), "#315f53"),
        "S4": Image.new("RGB", (720, 1280), "#453465"),
    }
    first = proof_timeline(captures, PAYLOAD)
    substituted = dict(captures)
    substituted["S2"] = Image.new("RGB", (720, 1280), "#1678a3")
    second = proof_timeline(substituted, PAYLOAD)
    for slot in captures:
        difference = ImageChops.difference(first[slot], second[slot]).getbbox()
        assert (difference is not None) == (slot == "S2")


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required")
def test_runtime_manifest_is_built_from_the_four_verified_job_captures(tmp_path: Path) -> None:
    capture_dir = tmp_path / "captures"
    capture_dir.mkdir()
    durations = {"S1": 6, "S2": 8, "S3": 7, "S4": 9}
    captures = {}
    for index, (slot, duration) in enumerate(durations.items(), 1):
        path = capture_dir / f"{slot}.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                f"color=c=0x{index}{index}{index}{index}{index}{index}:s=320x320:r=12:d={duration}",
                "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path),
            ],
            check=True,
        )
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        captures[slot] = {
            "uri": f"rushes/runtime/t5-test/{slot}.mp4",
            "sha256": digest,
            "mime_type": "video/mp4",
            "width": 320,
            "height": 320,
            "fps": 12,
            "frame_count": duration * 12,
            "duration_ms": duration * 1000,
            "source_in_ms": 0,
            "video_codec": "h264",
            "audio_codec": None,
            "has_audio": False,
        }
    job = build_render_job(
        render_job_id="t5-runtime-test-0001",
        merchant_payload=PAYLOAD,
        captures=captures,
        control_plane="cloudflare_worker",
    )
    job_path = tmp_path / "job.json"
    manifest_path = tmp_path / "runtime-manifest.json"
    job_path.write_text(json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    subprocess.run(
        [
            "python", "tools/build_t5_runtime_visual_inputs.py",
            "--render-job", str(job_path), "--capture-dir", str(capture_dir),
            "--manifest", str(manifest_path),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert [scene["scene"] for scene in manifest["scenes"]] == ["S1", "S2", "S3", "S4"]
    assert [scene["sha256"] for scene in manifest["scenes"]] == [captures[slot]["sha256"] for slot in durations]
    assert [scene["duration_seconds"] for scene in manifest["scenes"]] == [6, 8, 7, 9]
    assert manifest["text_motion_contract"] == "config/T5_TEXT_MOTION_V4_0_0.json"
    assert manifest["font_file"] == "assets/fonts/playfair-display/PlayfairDisplay[wght].ttf"
    assert [scene["text_fields"] for scene in manifest["scenes"]] == [
        ["nom", "offre", "contenu"], ["contenu"], ["offre", "contenu", "prix"], ["nom", "whatsapp", "quartier"]
    ]
