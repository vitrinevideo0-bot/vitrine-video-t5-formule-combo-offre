from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess

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


def test_owner_approved_four_track_rotation_and_voice_b() -> None:
    config = load()
    music = config["music"]
    pack = json.loads((ROOT / music["pack"]).read_text(encoding="utf-8"))
    voice = config["voice"]
    assert music["selection_mode"] == "strict_success_cycle"
    assert music["variant_count"] == 4
    assert music["full_sources_bundled"] is False
    assert music["adapted_30s_instrumentals_bundled"] is True
    assert [track["pixabay_id"] for track in pack["tracks"]] == [300338, 324016, 292156, 345669]
    assert [track["id"] for track in pack["tracks"]] == pack["selection_contract"]["allowed_variant_ids"]
    assert pack["selection_contract"]["first_render_variant_id"] == "t5_music_300338"
    assert pack["selection_contract"]["state_update_policy"] == "after_completed_audio_qc_pass_only"
    for track in pack["tracks"]:
        path = ROOT / track["file"]
        assert path.is_file()
        assert path.stat().st_size == track["bytes"] == 721196
        assert sha256(path) == track["sha256"]
        assert track["duration_s"] == 30.0
        assert track["contains_voice"] is False
        assert track["owner_approved"] is True
        assert track["production_eligible"] is True
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
    assert approval["music"]["decision"] == "approve_four_track_rotation"
    assert [item["id"] for item in approval["music"]["approved_order"]] == [
        "t5_music_300338", "t5_music_324016", "t5_music_292156", "t5_music_345669"
    ]
    assert approval["music"]["automatic_cycle"] == "1→2→3→4→1"
    assert approval["voice"]["selected_option"] == "B_masculine"
    assert approval["voice"]["voice_id"] == "voice-11"


def test_render_job_transports_the_complete_owner_approved_audio_contract() -> None:
    job = json.loads((ROOT / "demo/render_job_runtime_demo.json").read_text(encoding="utf-8"))
    audio = job["audio"]
    assert job["render"]["audio_mode"] == "owner_approved_music_rotation_voice_b_complete"
    assert audio["contract"] == "config/T5_AUDIO_MIX_V1_0_0.json"
    assert audio["contract_sha256"] == sha256(CONFIG)
    assert audio["music_pack"] == "config/T5_MUSIC_PACK_V1_0_0.json"
    assert audio["music_pack_sha256"] == sha256(ROOT / audio["music_pack"])
    assert audio["music"]["selected_music_id"] == "t5_music_300338"
    assert audio["music"]["selected_choice"] == "1"
    assert audio["music"]["selection_mode"] == "strict_success_cycle"
    assert audio["music"]["last_successful_music_id"] is None
    assert audio["music"]["full_source_bundled"] is False
    assert audio["music"]["standalone_redistribution_forbidden"] is True
    assert sha256(ROOT / audio["music"]["file"]) == audio["music"]["sha256"]
    voice_manifest = ROOT / audio["voice"]["manifest"]
    assert audio["voice"]["manifest_sha256"] == sha256(voice_manifest)
    assert audio["voice"]["voice_id"] == "voice-11"
    assert audio["voice"]["clip_source_sha256"] == {
        f"S{clip['scene']}": clip["source_sha256"] for clip in load()["voice"]["clips"]
    }


def test_finalizer_emits_only_a_complete_audio_bound_render_result(tmp_path: Path) -> None:
    job = json.loads((ROOT / "demo/render_job_runtime_demo.json").read_text(encoding="utf-8"))
    result = json.loads((ROOT / "demo/render_result_runtime_example.json").read_text(encoding="utf-8"))
    visual = deepcopy(result)
    visual["status"] = "VISUAL_COMPLETED"
    visual["profile_used"] = "T5_GITHUB_ACTIONS_FULL_FRAME_V3"
    visual["job_id"] = job["job_id"]
    visual["idempotency_key"] = job["idempotency_key"]
    visual["control_plane"] = job["control_plane"]
    visual["output"] = {
        "uri": job["output"]["uri"],
        "file": job["output"]["filename"],
        "sha256": "a" * 64,
        "bytes": 123,
    }
    visual["inputs"]["merchant_payload_sha256"] = hashlib.sha256(
        json.dumps(job["merchant_payload"], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    visual["inputs"]["capture_sha256"] = {
        slot: job["captures"][slot]["sha256"] for slot in ("S1", "S2", "S3", "S4")
    }
    for key in (
        "audio_contract_sha256", "music_pack_sha256", "music_source_sha256",
        "music_program_sha256", "voice_manifest_sha256", "voice_clip_source_sha256",
    ):
        visual["inputs"].pop(key, None)
    for key in ("audio_quality", "audio", "audio_state_commit_allowed"):
        visual.pop(key, None)

    video = tmp_path / job["output"]["filename"]
    video.write_bytes(b"t5-complete-audio-video-fixture")
    config = load()
    report = {
        "status": "PASS",
        "summary": {"passed": 26, "failed": 0, "total": 26},
        "visual": {"input_file_sha256": "a" * 64, "bitstream_copy": True},
        "music": {
            "selected_music_id": job["audio"]["music"]["selected_music_id"],
            "source_sha256": job["audio"]["music"]["source_sha256"],
            "program_sha256": job["audio"]["music"]["sha256"],
        },
        "voice": {
            "voice_id": "voice-11",
            "clips": [
                {"scene": clip["scene"], "source_sha256": clip["source_sha256"]}
                for clip in config["voice"]["clips"]
            ],
        },
        "final_video": {
            "file": video.name,
            "sha256": sha256(video),
            "bytes": video.stat().st_size,
            "audio_codec": "aac",
            "audio_sample_rate": 48000,
            "audio_channels": 2,
            "integrated_lufs": -16.1,
            "true_peak_dbtp": -1.89,
            "duration_s": 30.0,
        },
    }
    job_path = tmp_path / "job.json"
    visual_path = tmp_path / "visual.json"
    report_path = tmp_path / "report.json"
    output_path = tmp_path / "result.json"
    job_path.write_text(json.dumps(job), encoding="utf-8")
    visual_path.write_text(json.dumps(visual), encoding="utf-8")
    report_path.write_text(json.dumps(report), encoding="utf-8")
    subprocess.run(
        [
            "python", "tools/finalize_t5_render_result.py",
            "--visual-result", str(visual_path),
            "--render-job", str(job_path),
            "--audio-config", "config/T5_AUDIO_MIX_V1_0_0.json",
            "--audio-report", str(report_path),
            "--video", str(video),
            "--output", str(output_path),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    final = json.loads(output_path.read_text(encoding="utf-8"))
    assert final["status"] == "COMPLETED"
    assert final["profile_used"] == "T5_GITHUB_ACTIONS_COMPLETE_V1"
    assert final["audio_quality"] == {
        "status": "PASS", "report": "T5_COMPLETE_AUDIO_RENDER_REPORT.json", "passed": 26, "total": 26
    }
    assert final["audio"]["music"]["title"] == "Afrofire"
    assert final["audio"]["voice"]["voice_id"] == "voice-11"
    assert final["audio_state_commit_allowed"] is True
