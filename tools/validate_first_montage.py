#!/usr/bin/env python3
"""Validate the first T5 montage and its stable final three seconds."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, text=True, capture_output=True)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probe(path: Path) -> dict:
    return json.loads(run([
        "ffprobe", "-v", "error", "-count_frames", "-show_entries",
        "format=duration,size:stream=index,codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,pix_fmt,nb_read_frames",
        "-of", "json", str(path),
    ]).stdout)


def final_stability(path: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="t5-stable-") as name:
        folder = Path(name)
        run([
            "ffmpeg", "-y", "-v", "error", "-i", str(path),
            "-vf", "select='eq(n,810)+eq(n,899)'", "-vsync", "0", str(folder / "%d.png"),
        ])
        a = Image.open(folder / "1.png").convert("RGB")
        b = Image.open(folder / "2.png").convert("RGB")
        bytes_a = a.tobytes()
        bytes_b = b.tobytes()
        total = sum(abs(x - y) for x, y in zip(bytes_a, bytes_b))
        samples = len(bytes_a)
        mean_absolute_difference = total / samples
        return {
            "first_frame": 810,
            "last_frame": 899,
            "mean_absolute_pixel_difference": round(mean_absolute_difference, 6),
            "threshold": 1.0,
            "pass": mean_absolute_difference < 1.0,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--video", type=Path,
        default=ROOT / "output/t5-first-montage-v1/VIDEO_T5_PREMIER_MONTAGE_SILENCIEUX_V1_A_JUGER.mp4",
    )
    parser.add_argument(
        "--report", type=Path,
        default=ROOT / "output/t5-first-montage-v1/T5_FIRST_MONTAGE_VALIDATION.json",
    )
    args = parser.parse_args()
    manifest = json.loads((ROOT / "rushes/manifest.json").read_text(encoding="utf-8"))
    info = probe(args.video)
    video_streams = [stream for stream in info["streams"] if stream["codec_type"] == "video"]
    audio_streams = [stream for stream in info["streams"] if stream["codec_type"] == "audio"]
    checks = {
        "one_video_stream": len(video_streams) == 1,
        "no_audio_stream": len(audio_streams) == 0,
        "dimensions_720x1280": bool(video_streams) and (video_streams[0]["width"], video_streams[0]["height"]) == (720, 1280),
        "fps_30": bool(video_streams) and video_streams[0]["avg_frame_rate"] == "30/1",
        "frames_900": bool(video_streams) and int(video_streams[0]["nb_read_frames"]) == 900,
        "duration_30_seconds": abs(float(info["format"]["duration"]) - 30.0) < 0.001,
        "h264_yuv420p": bool(video_streams) and video_streams[0]["codec_name"] == "h264" and video_streams[0]["pix_fmt"] == "yuv420p",
        "one_licensed_source": manifest["continuity_rule"]["source_count"] == 1,
        "raw_media_not_published": manifest["license"]["raw_media_published_as_artifact"] is False,
        "same_formula_rule": manifest["continuity_rule"]["same_dish_drink_and_sides_across_four_scenes"] is True,
        "three_t1_swipes": len(manifest["transition_contract"]["offsets_seconds"]) == 3,
    }
    stability = final_stability(args.video)
    checks["final_three_seconds_stable"] = stability["pass"]
    status = "PASS" if all(checks.values()) else "FAIL"
    report = {
        "schema_version": "1.0.0",
        "template_id": "RESTAURATION-T5",
        "status": status,
        "video": {"path": args.video.name, "bytes": args.video.stat().st_size, "sha256": sha256(args.video)},
        "checks": checks,
        "passed": sum(checks.values()),
        "total": len(checks),
        "final_stability": stability,
        "probe": info,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if status != "PASS":
        raise SystemExit(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"T5_FIRST_MONTAGE_VALIDATION_PASS {report['passed']}/{report['total']} {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
