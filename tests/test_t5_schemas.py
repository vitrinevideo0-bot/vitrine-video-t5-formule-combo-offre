from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]

CASES = [
    ("schemas/T5_questions.schema.json", "form/questions_T5.json"),
    ("schemas/T5_text_motion.schema.json", "config/T5_TEXT_MOTION_V1_0_0.json"),
    ("schemas/T5_text_motion_v2.schema.json", "config/T5_TEXT_MOTION_V2_0_0.json"),
    ("schemas/T5_text_motion_v3.schema.json", "config/T5_TEXT_MOTION_V3_0_0.json"),
    ("schemas/T5_text_motion_v4.schema.json", "config/T5_TEXT_MOTION_V4_0_0.json"),
    ("schemas/T5_capture_flow.schema.json", "config/T5_CAPTURE_FLOW_V1_0_0.json"),
    ("schemas/T5_rush_manifest.schema.json", "rushes/manifest.json"),
    ("schemas/T5_render_job.schema.json", "demo/render_job_runtime_demo.json"),
    ("schemas/T5_render_result.schema.json", "demo/render_result_runtime_example.json"),
    ("schemas/T5_render_error.schema.json", "demo/render_error_runtime_example.json"),
]


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


@pytest.mark.parametrize(("schema_path", "instance_path"), CASES)
def test_canonical_json_validates_against_published_schema(schema_path: str, instance_path: str) -> None:
    schema = load(schema_path)
    instance = load(instance_path)
    jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.path))
    assert not errors, "\n".join(f"{list(error.path)}: {error.message}" for error in errors)


def test_schemas_reject_static_or_incomplete_variants() -> None:
    questions = load("form/questions_T5.json")
    questions["fields"][5]["required"] = False
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(questions, load("schemas/T5_questions.schema.json"))

    altered_copy = load("form/questions_T5.json")
    altered_copy["fields"][0]["question"] = "Une autre formulation ?"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(altered_copy, load("schemas/T5_questions.schema.json"))

    static_motion = load("config/T5_TEXT_MOTION_V4_0_0.json")
    static_motion["animation"]["static_all_fields_from_first_frame"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(static_motion, load("schemas/T5_text_motion_v4.schema.json"))

    rejected_bodoni_motion = load("config/T5_TEXT_MOTION_V4_0_0.json")
    rejected_bodoni_motion["font"]["family"] = "Bodoni Moda"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(rejected_bodoni_motion, load("schemas/T5_text_motion_v4.schema.json"))

    per_letter_motion = load("config/T5_TEXT_MOTION_V4_0_0.json")
    per_letter_motion["animation"]["per_letter_animation"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(per_letter_motion, load("schemas/T5_text_motion_v4.schema.json"))

    broken_baseline = load("config/T5_TEXT_MOTION_V4_0_0.json")
    broken_baseline["animation"]["baseline_motion_pixels"] = 1
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(broken_baseline, load("schemas/T5_text_motion_v4.schema.json"))

    three_lines = load("config/T5_TEXT_MOTION_V4_0_0.json")
    three_lines["scenes"]["S2"]["fields"][0]["max_lines"] = 3
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(three_lines, load("schemas/T5_text_motion_v4.schema.json"))

    job = load("demo/render_job_runtime_demo.json")
    job["render"]["visual_mode"] = "approved_master_stream_copy"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(job, load("schemas/T5_render_job.schema.json"))

    silent_job = load("demo/render_job_runtime_demo.json")
    silent_job["render"]["audio_mode"] = "silent_no_audio_stream"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(silent_job, load("schemas/T5_render_job.schema.json"))

    wrong_voice_job = load("demo/render_job_runtime_demo.json")
    wrong_voice_job["audio"]["voice"]["voice_id"] = "voice-10"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(wrong_voice_job, load("schemas/T5_render_job.schema.json"))

    rushes = load("rushes/manifest.json")
    rushes["license"]["raw_media_published_as_artifact"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(rushes, load("schemas/T5_rush_manifest.schema.json"))

    result = load("demo/render_result_runtime_example.json")
    del result["inputs"]["capture_sha256"]["S4"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(result, load("schemas/T5_render_result.schema.json"))

    no_audio_result = load("demo/render_result_runtime_example.json")
    del no_audio_result["audio_quality"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(no_audio_result, load("schemas/T5_render_result.schema.json"))

    wrong_profile_result = load("demo/render_result_runtime_example.json")
    wrong_profile_result["profile_used"] = "T5_GITHUB_ACTIONS_FULL_FRAME_V3"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(wrong_profile_result, load("schemas/T5_render_result.schema.json"))
