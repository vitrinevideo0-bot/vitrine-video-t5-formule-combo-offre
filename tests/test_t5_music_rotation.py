from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
import pytest

from adapter.t5_adapter import (
    MUSIC_IDS,
    approved_music_tracks,
    build_render_job,
    captures_from_demo_manifest,
    load_music_selection_state,
    record_music_render_result,
    select_music_variant,
    select_music_variant_from_state,
)

ROOT = Path(__file__).resolve().parents[1]


def load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_music_pack_and_persistent_state_contracts_are_strict() -> None:
    pack_schema = load("schemas/T5_music_pack.schema.json")
    pack = load("config/T5_MUSIC_PACK_V1_0_0.json")
    state_schema = load("schemas/T5_music_selection_state.schema.json")
    for schema in (pack_schema, state_schema):
        Draft202012Validator.check_schema(schema)
    Draft202012Validator(pack_schema, format_checker=FormatChecker()).validate(pack)
    Draft202012Validator(state_schema).validate(
        {
            "schema_version": "1.0.0",
            "last_successful_music_id": "t5_music_300338",
            "last_successful_render_job_id": "t5-rotation-contract-0001",
            "successful_render_count": 1,
            "successful_render_jobs": {"t5-rotation-contract-0001": MUSIC_IDS[0]},
        }
    )
    assert tuple(pack["selection_contract"]["allowed_variant_ids"]) == MUSIC_IDS
    assert pack["selection_contract"]["explicit_selection_policy"] == "exact_successor_only"
    assert pack["selection_contract"]["idempotency_ledger_key"] == "successful_render_jobs"
    assert [track["pixabay_id"] for track in approved_music_tracks()] == [300338, 324016, 292156, 345669]


def test_all_four_clean_instrumentals_match_locked_assets() -> None:
    tracks = approved_music_tracks()
    assert [track["id"] for track in tracks] == list(MUSIC_IDS)
    for track in tracks:
        path = ROOT / track["file"]
        assert path.is_file()
        assert path.stat().st_size == track["bytes"] == 721196
        assert sha256(path) == track["sha256"]
        assert track["duration_s"] == 30.0
        assert track["sample_rate_hz"] == 48_000
        assert track["channels"] == 2
        assert track["bitrate_kbps"] == 192
        assert track["contains_voice"] is False
        assert track["content_id_status"] == "not_displayed_on_source_page"


def test_automatic_selection_repeats_the_exact_strict_cycle_10000_times() -> None:
    previous = None
    observed: list[str] = []
    for _ in range(10_000):
        selected = select_music_variant(last_successful_music_id=previous)
        observed.append(selected["id"])
        previous = selected["id"]
    assert observed == list(MUSIC_IDS) * 2500
    assert all(left != right for left, right in zip(observed, observed[1:]))


def test_explicit_selection_can_confirm_but_never_skip_the_successor() -> None:
    expected = select_music_variant(
        last_successful_music_id="t5_music_300338",
        explicit_music_id="t5_music_324016",
    )
    assert expected["id"] == "t5_music_324016"
    assert expected["selection_mode"] == "explicit"
    with pytest.raises(ValueError, match="expects t5_music_324016"):
        select_music_variant(
            last_successful_music_id="t5_music_300338",
            explicit_music_id="t5_music_292156",
        )
    with pytest.raises(ValueError, match="expects t5_music_324016"):
        select_music_variant(
            last_successful_music_id="t5_music_300338",
            explicit_music_id="t5_music_300338",
        )


def test_state_advances_only_after_completed_audio_qc_pass_and_replay_is_idempotent(tmp_path: Path) -> None:
    state_path = tmp_path / "music-state.json"
    first = select_music_variant_from_state(state_path=state_path)
    assert first["id"] == MUSIC_IDS[0]

    unchanged_incomplete = record_music_render_result(
        state_path=state_path,
        render_job_id="t5-state-0001",
        selected_music_id=first["id"],
        completed=False,
        quality_status="PASS",
    )
    assert unchanged_incomplete["last_successful_music_id"] is None
    assert not state_path.exists()

    unchanged_failed_qc = record_music_render_result(
        state_path=state_path,
        render_job_id="t5-state-0001",
        selected_music_id=first["id"],
        completed=True,
        quality_status="FAIL",
    )
    assert unchanged_failed_qc["last_successful_music_id"] is None
    assert not state_path.exists()

    committed = record_music_render_result(
        state_path=state_path,
        render_job_id="t5-state-0001",
        selected_music_id=first["id"],
        completed=True,
        quality_status="PASS",
    )
    assert committed["last_successful_music_id"] == MUSIC_IDS[0]
    assert committed["successful_render_count"] == 1
    assert committed["successful_render_jobs"] == {"t5-state-0001": MUSIC_IDS[0]}
    assert load_music_selection_state(state_path) == committed

    replay = record_music_render_result(
        state_path=state_path,
        render_job_id="t5-state-0001",
        selected_music_id=first["id"],
        completed=True,
        quality_status="PASS",
    )
    assert replay == committed
    assert select_music_variant_from_state(state_path=state_path)["id"] == MUSIC_IDS[1]

    with pytest.raises(ValueError, match="expected t5_music_324016"):
        record_music_render_result(
            state_path=state_path,
            render_job_id="t5-state-0002",
            selected_music_id=MUSIC_IDS[2],
            completed=True,
            quality_status="PASS",
        )
    assert load_music_selection_state(state_path) == committed


def test_old_success_replay_after_full_cycle_is_idempotent(tmp_path: Path) -> None:
    state_path = tmp_path / "music-state.json"
    job_ids = [f"t5-history-{index:04d}" for index in range(1, 5)]
    for job_id, music_id in zip(job_ids, MUSIC_IDS):
        record_music_render_result(
            state_path=state_path,
            render_job_id=job_id,
            selected_music_id=music_id,
            completed=True,
            quality_status="PASS",
        )
    after_cycle = load_music_selection_state(state_path)
    assert after_cycle["last_successful_music_id"] == MUSIC_IDS[3]
    assert after_cycle["successful_render_count"] == 4
    assert after_cycle["successful_render_jobs"] == dict(zip(job_ids, MUSIC_IDS))

    replayed = record_music_render_result(
        state_path=state_path,
        render_job_id=job_ids[0],
        selected_music_id=MUSIC_IDS[0],
        completed=True,
        quality_status="PASS",
    )
    assert replayed == after_cycle
    assert load_music_selection_state(state_path) == after_cycle

    with pytest.raises(ValueError, match="cannot change music"):
        record_music_render_result(
            state_path=state_path,
            render_job_id=job_ids[0],
            selected_music_id=MUSIC_IDS[1],
            completed=True,
            quality_status="PASS",
        )
    assert load_music_selection_state(state_path) == after_cycle


def test_concurrent_stale_successes_cannot_advance_twice(tmp_path: Path) -> None:
    state_path = tmp_path / "music-state.json"

    def commit(job_id: str) -> str:
        try:
            record_music_render_result(
                state_path=state_path,
                render_job_id=job_id,
                selected_music_id=MUSIC_IDS[0],
                completed=True,
                quality_status="PASS",
            )
            return "committed"
        except ValueError:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(commit, ["t5-concurrent-0001", "t5-concurrent-0002"]))
    assert sorted(outcomes) == ["committed", "rejected"]
    state = load_music_selection_state(state_path)
    assert state["last_successful_music_id"] == MUSIC_IDS[0]
    assert state["successful_render_count"] == 1
    assert len(state["successful_render_jobs"]) == 1


def test_each_track_builds_a_schema_valid_render_job_at_its_exact_turn() -> None:
    schema = load("schemas/T5_render_job.schema.json")
    payload = load("demo/reponses_runtime_demo.json")
    manifest = load("rushes/manifest.json")
    captures = captures_from_demo_manifest(manifest, "t5-rotation-job-0001")
    predecessors = {
        MUSIC_IDS[0]: MUSIC_IDS[3],
        MUSIC_IDS[1]: MUSIC_IDS[0],
        MUSIC_IDS[2]: MUSIC_IDS[1],
        MUSIC_IDS[3]: MUSIC_IDS[2],
    }
    for selected_id in MUSIC_IDS:
        job = build_render_job(
            render_job_id="t5-rotation-job-0001",
            merchant_payload=payload,
            captures=captures,
            last_successful_music_id=predecessors[selected_id],
            explicit_music_id=selected_id,
            control_plane="github_actions_fixture",
        )
        Draft202012Validator(schema).validate(job)
        music = job["audio"]["music"]
        assert music["selected_music_id"] == selected_id
        assert music["last_successful_music_id"] == predecessors[selected_id]
        assert music["selection_mode"] == "explicit"
        assert sha256(ROOT / music["file"]) == music["sha256"]
