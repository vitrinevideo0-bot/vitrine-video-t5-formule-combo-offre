from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_single_licensed_source_and_continuity() -> None:
    manifest = load("rushes/manifest.json")
    assert manifest["license"]["provider"] == "Pexels"
    assert manifest["license"]["raw_media_committed"] is False
    assert manifest["license"]["raw_media_published_as_artifact"] is False
    assert manifest["continuity_rule"] == {
        "one_offer_per_ad": True,
        "same_dish_drink_and_sides_across_four_scenes": True,
        "demo_offer": "Gâteau et cappuccino",
        "source_count": 1,
    }
    assert manifest["source"]["pexels_id"] == 25724633
    assert manifest["source"]["expected_bytes"] == 11277371
    assert manifest["source"]["sha256"] == "2301f2f293451064a03d1eb67a70e36e4b43fae9f8ae039c043c7770576de7ab"
    assert [scene["catalog_duration_seconds"] for scene in manifest["scenes"]] == [6, 8, 7, 9]


def test_t1_transition_and_output_contract() -> None:
    manifest = load("rushes/manifest.json")
    transition = manifest["transition_contract"]
    assert transition["reference"] == "T1"
    assert transition["family"] == "dish_swipe"
    assert transition["offsets_seconds"] == [6.0, 14.0, 21.0]
    assert transition["variants"] == ["slideleft", "slideright", "slideleft"]
    assert manifest["output_contract"]["total_frames"] == 900
    assert manifest["output_contract"]["audio_streams"] == 0


def test_demo_job_cannot_be_mistaken_for_merchant_delivery() -> None:
    job = load("demo/render_job_silent_demo.json")
    assert job["is_demo"] is True
    assert job["output"]["demo_only"] is True
    assert job["render_profile"]["demo_disclaimer_required"] is True
    assert job["render_profile"]["include_audio"] is False
    assert "À RENSEIGNER" in job["merchant_payload"]["prix"]
    assert "DU COMMERCE" in job["merchant_payload"]["whatsapp"]


def test_raw_media_is_not_versioned() -> None:
    tracked = ROOT / "rushes/cache/pexels_25724633.mp4"
    # The local cache may exist, but it must be ignored and never part of the source tree contract.
    assert not (ROOT / "rushes/pexels_25724633.mp4").exists()
    if tracked.exists():
        assert hashlib.sha256(tracked.read_bytes()).hexdigest() == load("rushes/manifest.json")["source"]["sha256"]
