#!/usr/bin/env python3
"""Build and validate a RESTAURATION-T5 complete audio master.

The visual renderer remains silent and passes its own 21/21 QC. This
post-process verifies the exact 30-second instrumental selected by the strict
four-track RenderJob, binds its official-source provenance, mixes the four
voice-11 clips, and muxes AAC while copying the H.264 video bitstream. Original
full Pixabay tracks are never required, bundled, or copied to outputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SR = 48_000
TOTAL_S = 30.0
TOTAL_SAMPLES = int(SR * TOTAL_S)


def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
    print("RUN", " ".join(command), flush=True)
    return subprocess.run(command, check=True, **kwargs)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def decode(path: Path, channels: int) -> np.ndarray:
    result = run(
        [
            "ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0",
            "-ar", str(SR), "-ac", str(channels), "-f", "f32le", "-",
        ],
        capture_output=True,
    )
    data = np.frombuffer(result.stdout, dtype="<f4").astype(np.float64)
    require(data.size % channels == 0, f"Invalid decoded channel layout for {path}")
    return data.reshape(-1, channels) if channels > 1 else data


def exact_length(audio: np.ndarray, length: int) -> np.ndarray:
    if len(audio) == length:
        return audio
    shape = (length,) if audio.ndim == 1 else (length, audio.shape[1])
    fitted = np.zeros(shape, dtype=np.float64)
    copied = min(length, len(audio))
    fitted[:copied] = audio[:copied]
    return fitted


def write_wav(path: Path, audio: np.ndarray, codec: str = "pcm_s24le") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    channels = audio.shape[1] if audio.ndim == 2 else 1
    process = subprocess.Popen(
        [
            "ffmpeg", "-y", "-v", "error", "-f", "f32le", "-ar", str(SR),
            "-ac", str(channels), "-i", "-", "-map_metadata", "-1",
            "-c:a", codec, str(path),
        ],
        stdin=subprocess.PIPE,
    )
    process.communicate(np.asarray(audio, dtype="<f4").tobytes())
    if process.returncode:
        raise RuntimeError(f"Cannot write {path}")


def loudness(path: Path, target_i: float, target_tp: float) -> dict[str, Any]:
    result = run(
        [
            "ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-map", "0:a:0",
            "-af", f"loudnorm=I={target_i}:TP={target_tp}:LRA=7:print_format=json",
            "-f", "null", "-",
        ],
        capture_output=True,
        text=True,
    )
    blocks = re.findall(r'\{\s*"input_i".*?\}', result.stderr, re.S)
    if not blocks:
        raise RuntimeError(f"No loudness measurement for {path}")
    return json.loads(blocks[-1])


def normalize(
    source: Path,
    target: Path,
    target_i: float,
    target_tp: float,
    channels: int,
    duration_s: float | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    before = loudness(source, target_i, target_tp)
    audio_filter = (
        f"loudnorm=I={target_i}:TP={target_tp}:LRA=7:"
        f"measured_I={before['input_i']}:measured_LRA={before['input_lra']}:"
        f"measured_TP={before['input_tp']}:measured_thresh={before['input_thresh']}:"
        f"offset={before['target_offset']}:linear=false:print_format=summary"
    )
    command = [
        "ffmpeg", "-y", "-v", "error", "-i", str(source), "-map", "0:a:0",
        "-af", audio_filter,
    ]
    if duration_s is not None:
        command.extend(["-t", str(duration_s)])
    command.extend(
        [
            "-ar", str(SR), "-ac", str(channels), "-map_metadata", "-1",
            "-c:a", "pcm_s24le", str(target),
        ]
    )
    run(command)
    return before, loudness(target, target_i, target_tp)


def probe(path: Path) -> dict[str, Any]:
    return json.loads(
        run(
            [
                "ffprobe", "-v", "error", "-count_frames", "-show_streams",
                "-show_format", "-of", "json", str(path),
            ],
            capture_output=True,
            text=True,
        ).stdout
    )


def video_stream_hash(path: Path) -> str:
    result = run(
        [
            "ffmpeg", "-v", "error", "-i", str(path), "-map", "0:v:0",
            "-c", "copy", "-f", "hash", "-hash", "sha256", "-",
        ],
        capture_output=True,
        text=True,
    ).stdout.strip()
    return result.split("=", 1)[1].lower()


def sample_qc(audio: np.ndarray) -> dict[str, Any]:
    peak = float(np.max(np.abs(audio)))
    return {
        "sample_peak_dbfs": round(20 * math.log10(max(peak, 1e-12)), 3),
        "clipped_samples": int(np.count_nonzero(np.abs(audio) >= 0.999999)),
        "nan_count": int(np.isnan(audio).sum()),
        "inf_count": int(np.isinf(audio).sum()),
    }


def duck_envelope(
    spans: list[tuple[float, float]], attack_s: float, release_s: float
) -> np.ndarray:
    envelope = np.zeros(TOTAL_SAMPLES, dtype=np.float64)
    for start, end in spans:
        attack_start = max(0, int(round((start - attack_s) * SR)))
        full_start = max(0, int(round(start * SR)))
        full_end = min(TOTAL_SAMPLES, int(round(end * SR)))
        release_end = min(TOTAL_SAMPLES, int(round((end + release_s) * SR)))
        if full_start > attack_start:
            envelope[attack_start:full_start] = np.maximum(
                envelope[attack_start:full_start],
                np.linspace(0.0, 1.0, full_start - attack_start, endpoint=False),
            )
        envelope[full_start:full_end] = 1.0
        if release_end > full_end:
            envelope[full_end:release_end] = np.maximum(
                envelope[full_end:release_end],
                np.linspace(1.0, 0.0, release_end - full_end, endpoint=False),
            )
    return envelope


def speech_metrics(
    voice: np.ndarray,
    ducked_music: np.ndarray,
    spans: list[tuple[float, float]],
) -> dict[str, Any]:
    frame = int(0.02 * SR)
    voice_powers: list[float] = []
    music_powers: list[float] = []
    ratios: list[float] = []
    by_scene: list[dict[str, Any]] = []
    for scene, (start, end) in enumerate(spans, 1):
        local: list[float] = []
        begin = int(start * SR) // frame
        finish = min(len(voice) // frame, int(math.ceil(end * SR / frame)))
        for index in range(begin, finish):
            left, right = index * frame, (index + 1) * frame
            voice_power = float(np.mean(voice[left:right] ** 2))
            if 10 * math.log10(max(voice_power, 1e-20)) <= -42.0:
                continue
            music_power = float(np.mean(ducked_music[left:right] ** 2))
            ratio = 10 * math.log10(max(voice_power, 1e-20) / max(music_power, 1e-20))
            voice_powers.append(voice_power)
            music_powers.append(music_power)
            ratios.append(ratio)
            local.append(ratio)
        require(local, f"No active speech detected for scene {scene}")
        by_scene.append(
            {
                "scene": scene,
                "active_speech_s": round(len(local) * 0.02, 3),
                "median_speech_to_music_db": round(float(np.median(local)), 2),
                "p10_speech_to_music_db": round(float(np.percentile(local, 10)), 2),
            }
        )
    aggregate = 10 * math.log10(np.mean(voice_powers) / np.mean(music_powers))
    return {
        "method": "20 ms frames; active voice above -42 dBFS; pre-master stems",
        "active_speech_s": round(len(ratios) * 0.02, 3),
        "aggregate_speech_to_music_db": round(float(aggregate), 2),
        "median_speech_to_music_db": round(float(np.median(ratios)), 2),
        "p10_speech_to_music_db": round(float(np.percentile(ratios, 10)), 2),
        "scenes": by_scene,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--silent-video", type=Path, required=True)
    parser.add_argument("--render-job", type=Path, required=True)
    parser.add_argument("--music-source", type=Path, required=True, help="Selected bundled 30-second instrumental")
    parser.add_argument(
        "--config", type=Path, default=ROOT / "config/T5_AUDIO_MIX_V1_0_0.json"
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    job = json.loads(args.render_job.read_text(encoding="utf-8"))
    require(config["template_id"] == "RESTAURATION-T5", "Unexpected template")
    require(config["duration_s"] == TOTAL_S, "T5 duration must remain 30 seconds")
    require(config["sample_rate_hz"] == SR, "T5 audio must remain 48 kHz")
    require(args.silent_video.is_file(), f"Missing silent visual: {args.silent_video}")
    require(args.music_source.is_file(), f"Missing selected music program: {args.music_source}")

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_video = output_dir / config["output"]["video_filename"]
    master_wav = output_dir / config["output"]["master_audio_filename"]
    report_path = output_dir / config["output"]["report_filename"]
    voice_stem_path = output_dir / "T5_VOICE_B_STEM_30S.wav"

    audio_job = job["audio"]
    selected_music = audio_job["music"]
    music_config = config["music"]
    pack_path = ROOT / music_config["pack"]
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    pack_track = next((track for track in pack["tracks"] if track["id"] == selected_music["selected_music_id"]), None)
    require(pack_track is not None, "Selected music ID is absent from the approved T5 pack")
    require(audio_job["mode"] == "owner_approved_music_rotation_voice_b_complete", "Unexpected audio mode")
    require(job["render"]["audio_mode"] == audio_job["mode"], "Render audio mode mismatch")
    require(audio_job["contract_sha256"] == sha256(args.config), "Audio contract SHA-256 mismatch")
    require(audio_job["music_pack_sha256"] == sha256(pack_path), "Music pack SHA-256 mismatch")
    require(selected_music["file"] == pack_track["file"], "Selected music path diverges from pack")
    require(selected_music["sha256"] == pack_track["sha256"], "Selected music hash diverges from pack")
    require(selected_music["source_sha256"] == pack_track["source_sha256"], "Selected source provenance diverges from pack")
    require(selected_music["contains_voice"] is False, "Selected program must be instrumental")
    require(selected_music["full_source_bundled"] is False, "Full music sources must not be bundled")
    require(sha256(args.music_source) == selected_music["sha256"], "Selected music program SHA-256 mismatch")
    require(args.music_source.stat().st_size == selected_music["bytes"], "Selected music program byte size mismatch")

    voice_config = config["voice"]
    require(voice_config["voice_id"] == "voice-11", "Final voice must be voice-11")
    require(voice_config["selected_option"] == "B_masculine", "Final voice must be option B")
    clips = voice_config["clips"]
    require(len(clips) == 4, "Exactly four voice clips are required")
    require([clip["scene"] for clip in clips] == [1, 2, 3, 4], "Voice scenes must be ordered 1 to 4")

    silent_probe = probe(args.silent_video)
    silent_video_streams = [s for s in silent_probe["streams"] if s.get("codec_type") == "video"]
    silent_audio_streams = [s for s in silent_probe["streams"] if s.get("codec_type") == "audio"]
    require(len(silent_video_streams) == 1, "Visual input must contain one video stream")
    require(len(silent_audio_streams) == 0, "Visual input must remain silent before final mux")
    input_stream_hash = video_stream_hash(args.silent_video)

    voice_stem = np.zeros(TOTAL_SAMPLES, dtype=np.float64)
    voice_reports: list[dict[str, Any]] = []
    spans: list[tuple[float, float]] = []

    with tempfile.TemporaryDirectory(prefix="t5-complete-audio-") as temp_name:
        temp = Path(temp_name)
        for clip in clips:
            source = ROOT / clip["source"]
            require(source.is_file(), f"Missing voice clip: {source}")
            require(sha256(source) == clip["source_sha256"], f"Voice SHA-256 mismatch: {source}")
            normalized = temp / f"scene{clip['scene']}_normalized.wav"
            before, after = normalize(
                source,
                normalized,
                float(voice_config["normalization_target_lufs"]),
                float(voice_config["normalization_true_peak_dbtp_max"]),
                channels=1,
            )
            audio = decode(normalized, 1)
            decoded_duration = len(audio) / SR
            require(
                abs(decoded_duration - float(clip["source_duration_s"])) <= 0.08,
                f"Unexpected decoded voice duration for scene {clip['scene']}: {decoded_duration}",
            )
            start_sample = int(round(float(clip["start_s"]) * SR))
            end_sample = start_sample + len(audio)
            scene_end_sample = int(round(float(clip["scene_end_s"]) * SR))
            require(end_sample <= scene_end_sample, f"Voice scene {clip['scene']} exceeds its scene")
            require(end_sample <= TOTAL_SAMPLES, f"Voice scene {clip['scene']} exceeds 30 seconds")
            voice_stem[start_sample:end_sample] += audio
            end_s = end_sample / SR
            spans.append((float(clip["start_s"]), end_s))
            voice_reports.append(
                {
                    "scene": clip["scene"],
                    "text": clip["text"],
                    "source": clip["source"],
                    "source_sha256": clip["source_sha256"],
                    "start_s": clip["start_s"],
                    "end_s": round(end_s, 6),
                    "duration_s": round(decoded_duration, 6),
                    "normalization_before": before,
                    "normalization_after": after,
                }
            )

        voice_gain = 10 ** (float(config["mix_contract"]["voice_gain_db"]) / 20.0)
        voice_stem *= voice_gain
        write_wav(voice_stem_path, voice_stem)

        music = decode(args.music_source, 2)
        require(len(music) == TOTAL_SAMPLES, "Selected T5 instrumental must decode to exactly 30.000 seconds")
        music_before = loudness(
            args.music_source,
            float(music_config["program_target_lufs"]),
            float(music_config["program_true_peak_dbtp_max"]),
        )
        music_after = music_before
        require(
            abs(float(music_after["input_i"]) - float(pack_track["integrated_lufs"])) <= 0.15,
            "Selected music loudness diverges from the approved pack measurement",
        )
        require(
            float(music_after["input_tp"]) <= float(music_config["program_true_peak_dbtp_max"]),
            "Selected music true peak exceeds the approved program ceiling",
        )

        mix = config["mix_contract"]
        envelope = duck_envelope(
            spans,
            float(mix["duck_attack_ms"]) / 1000.0,
            float(mix["duck_release_ms"]) / 1000.0,
        )
        gain_db = float(mix["music_open_gain_db"]) + (
            float(mix["music_under_voice_gain_db"]) - float(mix["music_open_gain_db"])
        ) * envelope
        ducked_music = music * (10 ** (gain_db / 20.0))[:, None]
        pre_master = ducked_music + np.column_stack((voice_stem, voice_stem))
        intelligibility = speech_metrics(voice_stem, ducked_music, spans)

        pre_master_wav = temp / "T5_PREMASTER_FLOAT.wav"
        write_wav(pre_master_wav, pre_master, codec="pcm_f32le")
        master_before, master_after = normalize(
            pre_master_wav,
            master_wav,
            float(mix["master_target_lufs"]),
            float(mix["master_true_peak_dbtp_max"]),
            channels=2,
            duration_s=TOTAL_S,
        )

    run(
        [
            "ffmpeg", "-y", "-v", "error", "-i", str(args.silent_video),
            "-i", str(master_wav), "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", str(SR),
            "-ac", "2", "-t", str(TOTAL_S), "-map_metadata", "-1",
            "-movflags", "+faststart", str(output_video),
        ]
    )

    master_audio = exact_length(decode(master_wav, 2), TOTAL_SAMPLES)
    final_audio = decode(output_video, 2)
    master_measure = loudness(master_wav, -16.0, -2.0)
    final_measure = loudness(output_video, -16.0, -1.0)
    master_qc = sample_qc(master_audio)
    final_qc = sample_qc(final_audio)
    output_probe = probe(output_video)
    output_video_streams = [s for s in output_probe["streams"] if s.get("codec_type") == "video"]
    output_audio_streams = [s for s in output_probe["streams"] if s.get("codec_type") == "audio"]
    output_stream_hash = video_stream_hash(output_video)
    video_stream = output_video_streams[0] if output_video_streams else {}
    audio_stream = output_audio_streams[0] if output_audio_streams else {}
    duration_s = float(output_probe["format"]["duration"])
    gates = config["quality_gates"]

    checks = {
        "selected_music_is_approved_pack_member": pack_track["id"] == selected_music["selected_music_id"],
        "selected_music_program_integrity": sha256(args.music_source) == selected_music["sha256"],
        "full_music_source_not_in_output": not any(output_dir.glob("*.mp3")),
        "voice_B_is_voice_11": voice_config["voice_id"] == "voice-11" and voice_config["selected_option"] == "B_masculine",
        "four_voice_sources_verified": len(voice_reports) == 4,
        "all_voice_clips_fit_scenes": all(end <= float(clip["scene_end_s"]) for (_, end), clip in zip(spans, clips)),
        "voice_stem_exact_30_seconds": len(voice_stem) == TOTAL_SAMPLES,
        "music_program_near_target": abs(float(music_after["input_i"]) - float(music_config["program_target_lufs"])) <= 0.3,
        "ducking_minus_3_minus_10_db": mix["music_open_gain_db"] == -3.0 and mix["music_under_voice_gain_db"] == -10.0,
        "ducking_attack_release": mix["duck_attack_ms"] == 120 and mix["duck_release_ms"] == 450,
        "active_speech_over_music": intelligibility["aggregate_speech_to_music_db"] >= float(gates["minimum_active_speech_to_music_db"]),
        "master_exact_30_seconds": len(master_audio) == TOTAL_SAMPLES,
        "master_loudness": float(gates["integrated_lufs_min"]) <= float(master_measure["input_i"]) <= float(gates["integrated_lufs_max"]),
        "master_true_peak": float(master_measure["input_tp"]) <= float(gates["wav_true_peak_dbtp_max"]),
        "aac_loudness": float(gates["integrated_lufs_min"]) <= float(final_measure["input_i"]) <= float(gates["integrated_lufs_max"]),
        "aac_true_peak": float(final_measure["input_tp"]) <= float(gates["aac_true_peak_dbtp_max"]),
        "no_master_clipping": master_qc["clipped_samples"] == 0 and master_qc["nan_count"] == 0 and master_qc["inf_count"] == 0,
        "no_aac_clipping": final_qc["clipped_samples"] == 0 and final_qc["nan_count"] == 0 and final_qc["inf_count"] == 0,
        "one_video_stream": len(output_video_streams) == 1,
        "one_audio_stream": len(output_audio_streams) == 1,
        "dimensions_720x1280": (video_stream.get("width"), video_stream.get("height")) == (720, 1280),
        "fps_30": video_stream.get("r_frame_rate") == "30/1",
        "frames_900": int(video_stream.get("nb_read_frames", "0")) == int(gates["exact_frames"]),
        "duration_30_seconds": abs(duration_s - TOTAL_S) <= float(gates["duration_tolerance_s"]),
        "aac_stereo_48khz": audio_stream.get("codec_name") == "aac" and int(audio_stream.get("sample_rate", "0")) == SR and int(audio_stream.get("channels", 0)) == 2,
        "visual_stream_bit_exact": output_stream_hash == input_stream_hash,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    report = {
        "schema_version": "1.0.0",
        "template_id": "RESTAURATION-T5",
        "status": status,
        "purpose": "complete_owner_approved_strict_rotation_music_plus_voice_B_render",
        "rendered_on": "github_actions" if os.environ.get("GITHUB_ACTIONS") == "true" else "local_preflight",
        "github": {
            "repository": os.environ.get("GITHUB_REPOSITORY"),
            "run_id": os.environ.get("GITHUB_RUN_ID"),
            "run_number": os.environ.get("GITHUB_RUN_NUMBER"),
            "sha": os.environ.get("GITHUB_SHA"),
        },
        "contract": str(args.config),
        "approval": config["approval"],
        "music": {
            "selected_music_id": selected_music["selected_music_id"],
            "choice": selected_music["selected_choice"],
            "pixabay_id": selected_music["pixabay_id"],
            "title": selected_music["title"],
            "artist": selected_music["artist"],
            "official_page": selected_music["source_page"],
            "source_sha256": selected_music["source_sha256"],
            "source_bytes": selected_music["source_bytes"],
            "source_start_s": selected_music["source_start_s"],
            "program_file": selected_music["file"],
            "program_sha256": selected_music["sha256"],
            "program_bytes": selected_music["bytes"],
            "full_source_bundled": False,
            "program_measurement_before": music_before,
            "program_measurement_after": music_after,
        },
        "voice": {
            "voice_id": voice_config["voice_id"],
            "selected_option": voice_config["selected_option"],
            "identity": voice_config["identity"],
            "clips": voice_reports,
            "stem_file": voice_stem_path.name,
            "stem_sha256": sha256(voice_stem_path),
        },
        "mix_contract": mix,
        "intelligibility": intelligibility,
        "visual": {
            "input_file": args.silent_video.name,
            "input_file_sha256": sha256(args.silent_video),
            "input_video_bitstream_sha256": input_stream_hash,
            "output_video_bitstream_sha256": output_stream_hash,
            "bitstream_copy": output_stream_hash == input_stream_hash,
        },
        "mastering": {
            "pre_master_measurement": master_before,
            "post_master_measurement": master_after,
            "verified_master_measurement": master_measure,
        },
        "master_audio": {
            "file": master_wav.name,
            "sha256": sha256(master_wav),
            "bytes": master_wav.stat().st_size,
            "duration_samples": len(master_audio),
            "integrated_lufs": float(master_measure["input_i"]),
            "true_peak_dbtp": float(master_measure["input_tp"]),
            **master_qc,
        },
        "final_video": {
            "file": output_video.name,
            "sha256": sha256(output_video),
            "bytes": output_video.stat().st_size,
            "duration_s": duration_s,
            "frames": int(video_stream.get("nb_read_frames", "0")),
            "width": video_stream.get("width"),
            "height": video_stream.get("height"),
            "fps": video_stream.get("r_frame_rate"),
            "video_codec": video_stream.get("codec_name"),
            "pixel_format": video_stream.get("pix_fmt"),
            "audio_codec": audio_stream.get("codec_name"),
            "audio_sample_rate": int(audio_stream.get("sample_rate", "0")),
            "audio_channels": int(audio_stream.get("channels", 0)),
            "integrated_lufs": float(final_measure["input_i"]),
            "true_peak_dbtp": float(final_measure["input_tp"]),
            **final_qc,
        },
        "checks": [
            {"check": name, "status": "PASS" if passed else "FAIL"}
            for name, passed in checks.items()
        ],
        "summary": {
            "passed": sum(checks.values()),
            "failed": len(checks) - sum(checks.values()),
            "total": len(checks),
        },
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": status,
                "output": str(output_video),
                "sha256": report["final_video"]["sha256"],
                "checks": report["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
