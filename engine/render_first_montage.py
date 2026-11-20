#!/usr/bin/env python3
"""Render the first silent T5 montage from one hash-locked licensed rush."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FPS = 30
TRANSITION_FRAMES = 8
TRANSITION_SECONDS = TRANSITION_FRAMES / FPS
FONT_BOLD = ROOT / "assets/fonts/DejaVuSans-Bold.ttf"
FONT_REGULAR = ROOT / "assets/fonts/DejaVuSans.ttf"


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, text=True, capture_output=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_text(work: Path, name: str, value: str) -> Path:
    path = work / f"{name}.txt"
    path.write_text(value, encoding="utf-8")
    return path


def drawtext(path: Path, y: int, size: int, *, color: str = "white", enable: str | None = None, bold: bool = True) -> str:
    font = FONT_BOLD if bold else FONT_REGULAR
    value = (
        f"drawtext=fontfile='{font}':textfile='{path}':fontcolor={color}:fontsize={size}:"
        f"x=(w-text_w)/2:y={y}:fix_bounds=true"
    )
    if enable:
        value += f":enable='{enable}'"
    return value


def render_scene(
    source: Path,
    destination: Path,
    work: Path,
    scene: dict[str, Any],
    payload: dict[str, str],
) -> None:
    n = int(scene["scene"][1:])
    duration = float(scene["render_input_duration_seconds"])
    motion = float(scene["motion_seconds"])
    desired_frames = round(duration * FPS)
    motion_frames = min(desired_frames, max(1, round(motion * FPS)))
    freeze_frames = desired_frames - motion_frames
    common = [
        "scale=-2:1280",
        "crop=720:1280:(in_w-720)/2:0",
        "fps=30",
        "setsar=1",
        f"trim=end_frame={motion_frames}",
        "setpts=PTS-STARTPTS",
    ]
    if freeze_frames > 0:
        common.append(f"loop=loop={freeze_frames}:size=1:start={motion_frames - 1}")
    common.append("setpts=N/(30*TB)")

    demo = write_text(work, f"s{n}_demo", "DÉMO — DONNÉES À REMPLACER")
    title_values = {
        1: (payload["nom"], payload["offre"], payload["contenu"]),
        2: ("DANS LA FORMULE", "1 GÂTEAU", "1 CAPPUCCINO"),
        3: (payload["offre"], payload["prix"], "LE PRIX SERA FOURNI PAR LE COMMERÇANT"),
        4: ("COMMANDER", payload["whatsapp"], payload["quartier"]),
    }
    title, line_1, line_2 = title_values[n]
    title_file = write_text(work, f"s{n}_title", title)
    line_1_file = write_text(work, f"s{n}_line1", line_1)
    line_2_file = write_text(work, f"s{n}_line2", line_2)

    filters = common + [
        "drawbox=x=24:y=54:w=672:h=235:color=black@0.62:t=fill",
        drawtext(title_file, 82, 27, color="#ffd48a"),
    ]
    if n == 2:
        filters += [
            drawtext(line_1_file, 146, 47, enable="between(t,0,4.0)"),
            drawtext(line_2_file, 146, 43, enable="gte(t,4.0)"),
            drawtext(write_text(work, "s2_sub", "MÊME FORMULE · VRAIES QUANTITÉS"), 222, 20, color="#f4e5d2"),
        ]
    else:
        filters += [
            drawtext(line_1_file, 140, 38),
            drawtext(line_2_file, 215, 19, color="#f4e5d2"),
        ]
    filters += [
        "drawbox=x=22:y=1192:w=676:h=58:color=black@0.64:t=fill",
        drawtext(demo, 1208, 18, color="#ffd48a"),
        "format=yuv420p",
    ]

    run([
        "ffmpeg", "-y", "-v", "error", "-ss", str(scene["trim_start_seconds"]), "-i", str(source),
        "-vf", ",".join(filters), "-an", "-frames:v", str(desired_frames),
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-r", str(FPS), str(destination),
    ])


def probe(path: Path) -> dict[str, Any]:
    result = run([
        "ffprobe", "-v", "error", "-count_frames", "-show_entries",
        "format=duration,size:stream=index,codec_type,codec_name,width,height,r_frame_rate,pix_fmt,nb_read_frames",
        "-of", "json", str(path),
    ])
    return json.loads(result.stdout)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "rushes/manifest.json")
    parser.add_argument("--render-job", type=Path, default=ROOT / "demo/render_job_silent_demo.json")
    parser.add_argument("--cache", type=Path, default=ROOT / "rushes/cache")
    parser.add_argument("--work", type=Path, default=ROOT / ".tmp/t5-first-montage")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output/t5-first-montage-v1")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    job = json.loads(args.render_job.read_text(encoding="utf-8"))
    source_record = manifest["source"]
    source = args.cache / source_record["cache_filename"]
    if not source.is_file() or source.stat().st_size != source_record["expected_bytes"] or sha256(source) != source_record["sha256"]:
        raise SystemExit("Run tools/fetch_t5_rush.py before rendering")

    args.work.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    clips: list[Path] = []
    for scene in manifest["scenes"]:
        clip = args.work / f"{scene['scene']}.mp4"
        render_scene(source, clip, args.work, scene, job["merchant_payload"])
        clips.append(clip)

    output = args.output_dir / job["output"]["filename"]
    assembled = args.work / "assembled_before_timescale_remux.mp4"
    duration = f"{TRANSITION_SECONDS:.9f}"
    filter_complex = (
        f"[0:v][1:v]xfade=transition=slideleft:duration={duration}:offset=6.0[x1];"
        f"[x1][2:v]xfade=transition=slideright:duration={duration}:offset=14.0[x2];"
        f"[x2][3:v]xfade=transition=slideleft:duration={duration}:offset=21.0,"
        "fps=30,trim=duration=30,setpts=PTS-STARTPTS,format=yuv420p[outv]"
    )
    command = ["ffmpeg", "-y", "-v", "error"]
    for clip in clips:
        command += ["-i", str(clip)]
    command += [
        "-filter_complex", filter_complex, "-map", "[outv]", "-an", "-frames:v", "900",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", str(assembled),
    ]
    run(command)
    # FFmpeg's xfade graph leaves the final packet duration unset. A stream-copy remux
    # writes the exact 30.000 s CFR track without changing the H.264 frames.
    run([
        "ffmpeg", "-y", "-v", "error", "-i", str(assembled), "-map", "0:v:0", "-an",
        "-c:v", "copy", "-video_track_timescale", "90000", "-movflags", "+faststart", str(output),
    ])

    proof = args.output_dir / "T5_PREMIER_MONTAGE_PLANCHE.jpg"
    run([
        "ffmpeg", "-y", "-v", "error", "-i", str(output),
        "-vf", "fps=1/2.5,scale=216:-1,tile=4x3:padding=5:margin=5:color=white",
        "-frames:v", "1", str(proof),
    ])
    report = {
        "schema_version": "1.0.0",
        "template_id": "RESTAURATION-T5",
        "status": "RENDERED_PENDING_OWNER_REVIEW",
        "is_demo": True,
        "output": {"file": output.name, "bytes": output.stat().st_size, "sha256": sha256(output)},
        "proof": {"file": proof.name, "bytes": proof.stat().st_size, "sha256": sha256(proof)},
        "source": {"pexels_id": source_record["pexels_id"], "sha256": source_record["sha256"], "raw_published": False},
        "transition_reference": "T1",
        "transition_duration_frames": TRANSITION_FRAMES,
        "probe": probe(output),
        "audio": False,
        "demo_text_requires_replacement": True,
    }
    report_path = args.output_dir / "T5_FIRST_MONTAGE_RENDER_REPORT.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"T5_FIRST_MONTAGE_RENDERED {output} {sha256(output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
