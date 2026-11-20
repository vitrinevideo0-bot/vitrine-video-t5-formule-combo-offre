from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/T5_AUDIO_MIX_V1_0_0.json"
SCHEMA = ROOT / "schemas/T5_audio_mix.schema.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def test_audio_contract_validates_strictly() -> None:
    Draft202012Validator(
        json.loads(SCHEMA.read_text(encoding="utf-8")),
        format_checker=FormatChecker(),
    ).validate(load())


def test_owner_selected_afrofire_and_voice_b() -> None:
    config = load()
    music = config["music"]
    voice = config["voice"]
    assert music["selection_choice"] == "4"
    assert music["pixabay_id"] == 300338
    assert music["title"] == "Afrofire"
    assert music["owner_approved"] is True
    assert music["source_bundled"] is False
    assert music["standalone_redistribution_forbidden"] is True
    assert voice["voice_id"] == "voice-11"
    assert voice["selected_option"] == "B_masculine"
    assert voice["owner_selected_by_comparison"] is True


def test_exactly_four_locked_voice_clips_fit_their_scenes() -> None:
    clips = load()["voice"]["clips"]
    assert [clip["scene"] for clip in clips] == [1, 2, 3, 4]
    assert [clip["start_s"] for clip in clips] == [0.45, 6.35, 18.15, 21.2]
    for clip in clips:
        path = ROOT / clip["source"]
        assert path.is_file(), path
        assert sha256(path) == clip["source_sha256"], path
        assert clip["scene_start_s"] <= clip["start_s"]
        assert clip["start_s"] + clip["source_duration_s"] <= clip["scene_end_s"]


def test_voice_integrity_file_passes() -> None:
    voice_dir = ROOT / "audio/voice/t5-voice-v1"
    expected = {}
    for line in (voice_dir / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        expected[relative] = digest
    assert set(expected) == {f"source/scene{index}.mp3" for index in range(1, 5)}
    for relative, digest in expected.items():
        assert sha256(voice_dir / relative) == digest


def test_t1_ducking_and_delivery_gates() -> None:
    config = load()
    mix = config["mix_contract"]
    gates = config["quality_gates"]
    assert mix["music_open_gain_db"] == -3.0
    assert mix["music_under_voice_gain_db"] == -10.0
    assert mix["duck_attack_ms"] == 120
    assert mix["duck_release_ms"] == 450
    assert mix["master_target_lufs"] == -16.0
    assert mix["master_true_peak_dbtp_max"] == -2.0
    assert gates["exact_frames"] == 900
    assert gates["visual_bitstream_copy_required"] is True
    assert gates["audio_codec"] == "aac"
    assert gates["audio_sample_rate_hz"] == 48000


def test_approval_matches_contract() -> None:
    config = load()
    approval = json.loads((ROOT / config["approval"]).read_text(encoding="utf-8"))
    assert approval["status"] == "owner_approved_for_complete_mix_and_github_publication"
    assert approval["music"]["selected_option"] == "4_afrofire"
    assert approval["voice"]["selected_option"] == "B_masculine"
    assert approval["voice"]["voice_id"] == "voice-11"
