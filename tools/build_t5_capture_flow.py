#!/usr/bin/env python3
"""Build the executable 12-screen T5 capture flow from approved JSON sources."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(guide: dict[str, Any], questions: dict[str, Any], guide_path: Path, questions_path: Path) -> dict[str, Any]:
    scenes = guide["scenes"]
    if len(scenes) != 4 or [scene["seconds"] for scene in scenes] != [6, 8, 7, 9]:
        raise ValueError("T5 requires exactly four scenes lasting 6/8/7/9 seconds")
    ids = [field["id"] for field in questions["fields"]]
    if ids != ["nom", "offre", "contenu", "prix", "whatsapp", "quartier"]:
        raise ValueError("T5 requires the six owner-approved merchant fields")
    if not all(field["required"] for field in questions["fields"]):
        raise ValueError("All six T5 answers are required")

    screens: list[dict[str, Any]] = []
    for scene in scenes:
        index = scene["n"]
        seconds = scene["seconds"]
        duration_ms = seconds * 1000
        scene_id = f"S{index}"
        prefix = f"T5_CAPTURE_{scene_id}"
        next_screen = f"T5_CAPTURE_S{index + 1}_A_GUIDE" if index < 4 else "T5_RENDER_CONFIRMATION"
        common = {
            "scene_id": scene_id,
            "scene_index": index,
            "scene_total": 4,
            "capture_duration_ms": duration_ms,
            "capture_slot": f"captures.{scene_id}",
            "data_used": scene["data_used"],
            "continuity_rule": guide["owner_rule"],
        }
        a = scene["guide"]
        b = scene["recording"]
        c = scene["review"]
        guide_ordinal = len(screens) + 1
        recording_ordinal = len(screens) + 2
        review_ordinal = len(screens) + 3

        screens.append({
            **common,
            "ordinal": guide_ordinal,
            "screen_id": f"{prefix}_A_GUIDE",
            "route_key": f"t5.capture.s{index}.guide",
            "state": "A_GUIDE",
            "display_state": "A / GUIDE",
            "bindings": {
                "title": f"capture-guide/consignes_T5.json#/scenes/{index - 1}/guide/title",
                "instruction": f"capture-guide/consignes_T5.json#/scenes/{index - 1}/guide/instruction",
                "film_list": f"capture-guide/consignes_T5.json#/scenes/{index - 1}/guide/film_list",
                "avoid_list": f"capture-guide/consignes_T5.json#/scenes/{index - 1}/guide/avoid_list",
                "required_action": f"capture-guide/consignes_T5.json#/scenes/{index - 1}/guide/required_action",
                "optional_example": f"capture-guide/consignes_T5.json#/scenes/{index - 1}/guide/optional_example",
                "speech_note": "capture-guide/consignes_T5.json#/speech_note",
            },
            "resolved_text": {
                "screen_label": a["screen_label"],
                "scene_counter": a["scene_counter"],
                "title": a["title"],
                "guide_section_title": guide["guide_section_title"],
                "instruction": a["instruction"],
                "film_section_title": guide["film_section_title"],
                "film_list": a["film_list"],
                "avoid_section_title": guide["avoid_section_title"],
                "avoid_list": a["avoid_list"],
                "action_section_title": guide["action_section_title"],
                "required_action": a["required_action"],
                "speech_section_title": guide["speech_section_title"],
                "speech_note": guide["speech_note"],
                "example_section_title": guide["example_section_title"],
                "optional_example": a["optional_example"],
                "primary_action": guide["primary_action"],
            },
            "visible_components": [
                "screen_label", "scene_counter", "title", "what_to_film", "film_list",
                "avoid_list", "required_action", "speech_note", "optional_example", "start_recording_button",
            ],
            "forbidden_components": ["recording_timer", "review_actions", "automatic_subtitles"],
            "actions": [{
                "event": "START_RECORDING",
                "label": guide["primary_action"],
                "effects": ["request_camera_permission", "request_microphone_permission", "run_COUNTDOWN_3_2_1"],
                "next_screen_id": f"{prefix}_B_RECORDING",
            }],
            "proof_png": f"ui-screens/{prefix}_A_GUIDE.png",
        })

        screens.append({
            **common,
            "ordinal": recording_ordinal,
            "screen_id": f"{prefix}_B_RECORDING",
            "route_key": f"t5.capture.s{index}.recording",
            "state": "B_RECORDING",
            "display_state": "B / ENREGISTREMENT",
            "bindings": {
                "elapsed_ms": "runtime.capture.elapsed_ms",
                "progress_0_to_1": "runtime.capture.progress",
                "instruction": f"capture-guide/consignes_T5.json#/scenes/{index - 1}/recording/instruction",
                "output_uri": f"runtime.captures.{scene_id}.uri",
            },
            "resolved_text": {
                "screen_label": b["screen_label"],
                "scene_counter": b["scene_counter"],
                "recording_status": b["status"],
                "timer_initial": b["timer_initial"],
                "timer_total": f"00:{seconds:02d}",
                "instruction": b["instruction"],
                "audio_status": guide["recording_audio_status"],
                "orientation_status": guide["recording_orientation_status"],
                "auto_stop_status": b["auto_stop_status"],
                "duration_seconds": seconds,
            },
            "visible_components": [
                "screen_label", "scene_counter", "recording_status", "recording_timer",
                "current_instruction", "microphone_active", "vertical_video_status", "automatic_stop_status",
            ],
            "forbidden_components": ["instruction_sheet", "manual_stop_button", "review_actions", "automatic_subtitles"],
            "capture": {
                "starts_after": "COUNTDOWN_3_2_1_COMPLETE",
                "video": True,
                "microphone_audio": True,
                "orientation": "vertical",
                "source_speed": 1.0,
                "duration_ms": duration_ms,
                "auto_stop": True,
                "manual_stop": False,
                "write_to": f"runtime.captures.{scene_id}.uri",
            },
            "actions": [{
                "event": "CAPTURE_DURATION_REACHED",
                "effects": ["stop_recorder", "finalize_capture_file", "probe_capture_metadata", "open_audio_review"],
                "next_screen_id": f"{prefix}_C_REVIEW",
            }],
            "proof_png": f"ui-screens/{prefix}_B_RECORDING.png",
        })

        screens.append({
            **common,
            "ordinal": review_ordinal,
            "screen_id": f"{prefix}_C_REVIEW",
            "route_key": f"t5.capture.s{index}.review",
            "state": "C_REVIEW",
            "display_state": "C / VÉRIFICATION",
            "bindings": {
                "preview_uri": f"runtime.captures.{scene_id}.uri",
                "capture_metadata": f"runtime.captures.{scene_id}.metadata",
                "review_question": f"capture-guide/consignes_T5.json#/scenes/{index - 1}/review/question",
                "review_checks": f"capture-guide/consignes_T5.json#/scenes/{index - 1}/review/checks",
            },
            "resolved_text": {
                "screen_label": c["screen_label"],
                "take_label": c["take_label"],
                "audio_status": guide["review_audio_status"],
                "review_question": c["question"],
                "review_checks": c["checks"],
                "redo_action": guide["redo_action"],
                "positive_action": c["positive_action"],
            },
            "visible_components": [
                "screen_label", "captured_video_preview", "captured_audio_playback", "review_question",
                "review_checklist", "redo_button", "accept_button",
            ],
            "forbidden_components": ["instruction_sheet", "recording_timer", "recording_progress", "automatic_subtitles"],
            "playback": {"audio": True, "loop": True, "source_speed": 1.0},
            "actions": [
                {
                    "event": "RETAKE",
                    "label": guide["redo_action"],
                    "effects": [f"delete:runtime.captures.{scene_id}", "reset_scene_capture_state"],
                    "next_screen_id": f"{prefix}_A_GUIDE",
                },
                {
                    "event": "ACCEPT_CAPTURE",
                    "label": c["positive_action"],
                    "effects": [f"persist:runtime.captures.{scene_id}", "mark_capture_accepted"],
                    "next_screen_id": next_screen,
                },
            ],
            "proof_png": f"ui-screens/{prefix}_C_REVIEW.png",
        })

    return {
        "schema_version": "1.0.0",
        "contract_id": "restauration_t5_formule_combo_offre_capture_flow_v1_0_0",
        "template_id": "RESTAURATION-T5",
        "template_version": "1.0.0",
        "status": "owner_approved_executable_contract",
        "copy_revision": guide["copy_revision"],
        "sources": {
            "guide": {"path": "capture-guide/consignes_T5.json", "sha256": sha256(guide_path)},
            "questions": {"path": "form/questions_T5.json", "sha256": sha256(questions_path)},
            "approval": "approvals/APPROBATION_QUESTIONS_ET_12_ECRANS_T5_2026-11-18.json",
        },
        "counts": {"merchant_questions": 6, "scenes": 4, "states_per_scene": 3, "stable_capture_screens": 12},
        "scene_durations_ms": [6000, 8000, 7000, 9000],
        "continuity_rules": {
            "one_offer_per_ad": True,
            "same_dish_drink_and_sides_across_all_scenes": True,
            "source_text": guide["owner_rule"],
        },
        "transient_states": [{
            "id": "COUNTDOWN_3_2_1", "counted_in_12_stable_screens": False,
            "sequence": [3, 2, 1], "trigger": "START_RECORDING", "then": "B_RECORDING",
            "must_not_be_written_into_capture": True,
        }],
        "runtime_rules": {
            "camera_required": True, "microphone_requested": True, "speech_optional": True,
            "playback_audio_enabled": True, "source_speed": 1.0, "video_orientation": "vertical",
            "automatic_subtitles": False, "retake_deletes_previous_capture": True,
        },
        "screens": screens,
        "session_model": {
            "name": "T5FormuleComboOffreSession",
            "fields": ["merchant_payload", "captures", "current_screen_id", "accepted_scene_ids"],
            "persistence": "persist accepted content URIs and media metadata until RenderJob submission",
        },
        "renderer_handoff": {
            "trigger": "ACCEPT_CAPTURE on T5_CAPTURE_S4_C_REVIEW",
            "render_job": "demo/render_job_silent_demo.json",
            "capture_bindings": {f"captures.S{i}": f"runtime.captures.S{i}.uri" for i in range(1, 5)},
            "merchant_payload_source": "form/questions_T5.json",
            "merchant_payload_targets": [f"merchant_payload.{name}" for name in ids],
            "production_render_plane": "github_actions",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--guide", type=Path, default=ROOT / "capture-guide/consignes_T5.json")
    parser.add_argument("--questions", type=Path, default=ROOT / "form/questions_T5.json")
    parser.add_argument("--output", type=Path, default=ROOT / "config/T5_CAPTURE_FLOW_V1_0_0.json")
    args = parser.parse_args()
    guide = json.loads(args.guide.read_text(encoding="utf-8"))
    questions = json.loads(args.questions.read_text(encoding="utf-8"))
    contract = build(guide, questions, args.guide, args.questions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"T5_CAPTURE_FLOW_BUILT {len(contract['screens'])} {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
