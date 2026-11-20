from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapter.t5_adapter import build_render_job, captures_from_demo_manifest


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_four_distinct_licensed_captures_preserve_one_formula() -> None:
    manifest = load("rushes/manifest.json")
    assert manifest["license"]["provider"] == "Pexels"
    assert manifest["license"]["raw_media_committed"] is False
    assert manifest["license"]["raw_media_published_as_artifact"] is False
    assert manifest["continuity_rule"]["source_count"] == 4
    assert manifest["continuity_rule"]["one_offer_per_ad"] is True
    assert manifest["continuity_rule"]["same_dish_drink_and_sides_across_four_scenes"] is True
    assert manifest["continuity_rule"]["visible_in_every_scene"] == [
        "double burger", "portion de frites", "verre de cola"
    ]
    assert [source["slot"] for source in manifest["sources"]] == ["S1", "S2", "S3", "S4"]
    assert [source["pexels_id"] for source in manifest["sources"]] == [4731057, 4731063, 4731066, 4731132]
    assert len({source["sha256"] for source in manifest["sources"]}) == 4
    assert [scene["duration_seconds"] for scene in manifest["scenes"]] == [6, 8, 7, 9]


def test_demo_answers_build_the_checked_runtime_job() -> None:
    manifest = load("rushes/manifest.json")
    answers = load("demo/reponses_runtime_demo.json")
    rebuilt = build_render_job(
        render_job_id="t5-runtime-demo-0001",
        merchant_payload=answers,
        captures=captures_from_demo_manifest(manifest, "t5-runtime-demo-0001"),
        control_plane="github_actions_fixture",
    )
    assert rebuilt == load("demo/render_job_runtime_demo.json")
    assert rebuilt["merchant_payload"] == answers
    assert rebuilt["render"]["visual_mode"] == "runtime_hybrid_render"
    assert rebuilt["render"]["runtime_capture_manifest_required"] is True
    assert rebuilt["render"]["render_business_text"] is True
    assert rebuilt["render"]["production_render_plane"] == "github_actions"
    assert rebuilt["cloudflare_rendering_forbidden"] is True


def test_every_answer_and_capture_has_an_explicit_runtime_target() -> None:
    contract = load("config/T5_RUNTIME_CONTRACT_V2_0_0.json")
    assert [item["source"] for item in contract["merchant_bindings"]] == [
        "merchant_payload.nom", "merchant_payload.offre", "merchant_payload.contenu",
        "merchant_payload.prix", "merchant_payload.whatsapp", "merchant_payload.quartier",
    ]
    assert all(item["targets"] for item in contract["merchant_bindings"])
    assert [item["capture"] for item in contract["scene_bindings"]] == [
        "captures.S1", "captures.S2", "captures.S3", "captures.S4"
    ]
    assert [item["duration_ms"] for item in contract["scene_bindings"]] == [6000, 8000, 7000, 9000]
    assert contract["runtime_order"][3]["render_plane"] == "github_actions"


def test_rejected_generic_copy_is_absent_from_runtime_engine() -> None:
    source = (ROOT / "engine/render_runtime.py").read_text(encoding="utf-8") + (ROOT / "engine/runtime_visual.py").read_text(encoding="utf-8")
    for rejected in ("CAFÉ DÉMO T5", "FORMULE PAUSE GOURMANDE", "DÉMO — DONNÉES À REMPLACER", "GÂTEAU", "CAPPUCCINO"):
        assert rejected not in source
    assert "4731057" not in source
    assert "rushes/manifest.json" not in source


def test_raw_media_paths_are_ignored_and_not_tracked() -> None:
    ignored = subprocess.run(
        ["git", "check-ignore", "rushes/cache-v2/S1_4731057.mp4"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert ignored.stdout.strip()
    tracked = subprocess.run(
        ["git", "ls-files", "rushes"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    assert not any(path.endswith((".mp4", ".mov", ".webm")) for path in tracked)


def test_demo_source_hashes_match_local_cache_when_present() -> None:
    manifest = load("rushes/manifest.json")
    for source in manifest["sources"]:
        path = ROOT / "rushes/cache-v2" / source["cache_filename"]
        if path.exists():
            assert path.stat().st_size == source["expected_bytes"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]
