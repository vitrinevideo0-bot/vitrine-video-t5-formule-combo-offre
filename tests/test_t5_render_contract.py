from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapter.t5_adapter import build_render_job, captures_from_demo_manifest
from engine.runtime_visual import (
    HEIGHT,
    _tracked_width,
    load_font,
    motion_design_evidence,
    readability_gradient_evidence,
    text_motion_state,
)


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
    assert manifest["continuity_rule"]["formula_items"] == [
        "double burger", "portion de frites", "verre de soda"
    ]
    assert [source["slot"] for source in manifest["sources"]] == ["S1", "S2", "S3", "S4"]
    assert [source["pexels_id"] for source in manifest["sources"]] == [32092904, 32092902, 32092903, 32092901]
    assert {source["creator"] for source in manifest["sources"]} == {"Aida Shukuhi"}
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
    assert rebuilt["render"]["visual_mode"] == "runtime_full_frame_render"
    assert rebuilt["render"]["runtime_capture_manifest_required"] is True
    assert rebuilt["render"]["render_business_text"] is True
    assert rebuilt["render"]["production_render_plane"] == "github_actions"
    assert rebuilt["cloudflare_rendering_forbidden"] is True


def test_every_answer_and_capture_has_an_explicit_runtime_target() -> None:
    contract = load("config/T5_RUNTIME_CONTRACT_V3_0_0.json")
    assert [item["source"] for item in contract["merchant_bindings"]] == [
        "merchant_payload.nom", "merchant_payload.offre", "merchant_payload.contenu",
        "merchant_payload.prix", "merchant_payload.whatsapp", "merchant_payload.quartier",
    ]
    assert all(item["targets"] for item in contract["merchant_bindings"])
    assert [item["capture"] for item in contract["scene_bindings"]] == [
        "captures.S1", "captures.S2", "captures.S3", "captures.S4"
    ]
    assert [item["duration_ms"] for item in contract["scene_bindings"]] == [6000, 8000, 7000, 9000]
    assert contract["text_motion_contract"] == "config/T5_TEXT_MOTION_V3_0_0.json"
    assert contract["visual_contract"]["text_motion"] == "readable_editorial_character_staggered_soft_rise_and_fade"
    assert contract["visual_contract"]["font_family"] == "Playfair Display"
    assert contract["visual_contract"]["font_classification"] == "readable editorial display serif"
    assert contract["visual_contract"]["text_color"] == "#FFFFFF"
    assert contract["visual_contract"]["minimum_font_weight"] == 800
    assert contract["visual_contract"]["large_readable_editorial_composition"] is True
    assert contract["visual_contract"]["native_pair_kerning"] is True
    assert contract["visual_contract"]["neutral_tracking"] is True
    assert contract["visual_contract"]["text_outline"] is False
    assert contract["visual_contract"]["readability_priority"] == "maximum"
    assert contract["visual_contract"]["static_text_stack"] is False
    assert contract["runtime_order"][3]["render_plane"] == "github_actions"


def test_v3_montage_is_full_frame_and_uses_three_exact_eight_frame_transitions() -> None:
    montage = load("montage/T5_MONTAGE_COMPLET_V3_0_0.json")
    assert montage["format"]["scene_durations_seconds"] == [6, 8, 7, 9]
    assert montage["visual_policy"]["rushes_fill_entire_frame"] is True
    assert montage["visual_policy"]["permanent_cards_forbidden"] is True
    assert montage["visual_policy"]["rounded_video_frames_forbidden"] is True
    assert montage["visual_policy"]["technical_or_test_labels_forbidden"] is True
    assert montage["visual_policy"]["horizontal_color_seams_forbidden"] is True
    assert montage["visual_policy"]["readability_gradient_must_reach_frame_bottom"] is True
    assert montage["visual_policy"]["static_text_stack_forbidden"] is True
    assert montage["visual_policy"]["character_by_character_reveal_required"] is True
    assert montage["visual_policy"]["font_family"] == "Playfair Display"
    assert montage["visual_policy"]["font_classification"] == "readable editorial display serif"
    assert montage["visual_policy"]["text_color"] == "#FFFFFF"
    assert montage["visual_policy"]["minimum_font_weight"] == 800
    assert montage["visual_policy"]["large_readable_editorial_composition"] is True
    assert montage["visual_policy"]["native_pair_kerning_required"] is True
    assert montage["visual_policy"]["neutral_tracking_required"] is True
    assert montage["visual_policy"]["text_outline_forbidden"] is True
    assert montage["visual_policy"]["readability_priority"] == "maximum"
    assert montage["visual_policy"]["max_simultaneous_text_fields"] == 2
    assert montage["rejected_revisions"] == [{
        "revision": "T5_TYPOGRAPHIE_EDITORIALE_BODONI_2026-11-18",
        "release": "t5-full-frame-v3-candidate-5",
        "reason": "Bodoni Moda appliquée au texte long est illisible ; ne pas réutiliser cette variante.",
    }]
    assert montage["merchant_payload"]["ordered_fields"] == [
        "nom", "offre", "contenu", "prix", "whatsapp", "quartier"
    ]
    assert [item["cut_frame"] for item in montage["transitions"]] == [180, 420, 630]
    assert [item["frames"] for item in montage["transitions"]] == [[176, 183], [416, 423], [626, 633]]
    assert all(item["duration_frames"] == 8 for item in montage["transitions"])


def test_readability_gradient_is_continuous_through_the_last_pixel() -> None:
    evidence = readability_gradient_evidence()
    assert evidence == {
        "start_row": 680,
        "last_row": HEIGHT - 1,
        "bottom_alpha": 150,
        "max_adjacent_alpha_jump": 1,
        "monotonic_non_decreasing": True,
        "reaches_frame_bottom": True,
    }


def test_motion_design_is_character_staggered_left_aligned_and_font_bound() -> None:
    evidence = motion_design_evidence()
    assert evidence["font"]["family"] == "Playfair Display"
    assert evidence["font"]["classification"] == "readable editorial display serif"
    assert evidence["font"]["style_reference"] == "Didot-inspired editorial serif optimized for screen readability"
    assert evidence["font"]["variation_axes"]["wght"]["maximum"] == 900
    assert evidence["font"]["license"] == "OFL-1.1"
    assert evidence["font"]["sha256"] == hashlib.sha256(
        (ROOT / evidence["font"]["file"]).read_bytes()
    ).hexdigest()
    assert evidence["reveal_unit"] == "character"
    assert evidence["sequence"] == "staggered_one_field_after_another"
    assert evidence["alignment"] == "left"
    assert evidence["letter_motion"] == "staggered_soft_rise_and_fade"
    assert evidence["composition"] == "large_readable_editorial_serif"
    assert evidence["case_transform"] == "none"
    assert evidence["white_bold_editorial_style"] is True
    assert evidence["native_pair_kerning"] is True
    assert evidence["readability_policy"] == {
        "priority": "maximum",
        "native_pair_kerning": True,
        "neutral_tracking": True,
        "minimum_preferred_size": 48,
        "minimum_weight": 800,
        "white_only": True,
        "no_outline": True,
        "long_copy_max_lines": 3,
    }
    assert evidence["static_all_fields_from_first_frame"] is False
    assert evidence["text_background_boxes"] is False
    assert evidence["max_simultaneous_fields"] == 2
    assert evidence["scene_max_simultaneous_fields"] == {"S1": 1, "S2": 1, "S3": 1, "S4": 2}
    assert evidence["stable_tail"] == {
        "start_frame": 180,
        "end_frame": 269,
        "visible_fields": ["whatsapp", "quartier"],
    }
    montage = load("montage/T5_MONTAGE_COMPLET_V3_0_0.json")
    for source_name in ("text_motion", "motion_font", "motion_typography_approval"):
        source = montage["approved_sources"][source_name]
        assert hashlib.sha256((ROOT / source["path"]).read_bytes()).hexdigest() == source["sha256"]


def test_readable_editorial_layout_preserves_native_pair_kerning() -> None:
    font = load_font(64, 900)
    full_pair_width = float(font.getlength("AV"))
    unkerned_width = sum(float(font.getlength(character)) for character in "AV")
    assert _tracked_width("AV", font, 0.0) == full_pair_width
    assert full_pair_width < unkerned_width


def test_motion_state_reveals_characters_and_never_restores_the_three_field_stack() -> None:
    payload = load("demo/reponses_runtime_demo.json")
    start = text_motion_state("S1", "nom", 10, payload["nom"])
    complete = text_motion_state("S1", "nom", 35, payload["nom"])
    assert start["phase"] == "type_on"
    assert 0 < start["visible_characters"] < start["total_characters"]
    assert complete["visible_characters"] == complete["total_characters"]
    assert text_motion_state("S1", "offre", 35, payload["offre"])["phase"] == "hidden"
    assert text_motion_state("S1", "nom", 94, payload["nom"])["phase"] == "hidden"
    assert text_motion_state("S1", "offre", 94, payload["offre"])["phase"] == "hold"
    final_states = {
        field: text_motion_state("S4", field, 180, payload[field])["phase"]
        for field in ("nom", "whatsapp", "quartier")
    }
    assert final_states == {"nom": "hidden", "whatsapp": "hold", "quartier": "hold"}


def test_rejected_generic_copy_is_absent_from_runtime_engine() -> None:
    source = (ROOT / "engine/render_runtime.py").read_text(encoding="utf-8") + (ROOT / "engine/runtime_visual.py").read_text(encoding="utf-8")
    for rejected in (
        "CAFÉ DÉMO T5", "FORMULE PAUSE GOURMANDE", "DÉMO — DONNÉES À REMPLACER",
        "GÂTEAU", "CAPPUCCINO", "LA FORMULE", "CE QU’IL Y A DANS LA FORMULE",
        "LE PRIX", "COMMANDER", "PREUVE RUNTIME",
    ):
        assert rejected not in source
    assert "rounded_rectangle" not in source
    assert "4731057" not in source
    assert "rushes/manifest.json" not in source


def test_raw_media_paths_are_ignored_and_not_tracked() -> None:
    ignored = subprocess.run(
        ["git", "check-ignore", "rushes/cache-v4-aida/S1_32092904.mp4"],
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
        path = ROOT / "rushes/cache-v4-aida" / source["cache_filename"]
        if path.exists():
            assert path.stat().st_size == source["expected_bytes"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]
