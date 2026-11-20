#!/usr/bin/env python3
"""Primitives visuelles T5 V3 : rush plein écran et typographie motion issue du JSON.

Aucun titre éditorial, carte, cadre vidéo, barre de progression ou libellé de scène
n'est produit ici. Les seuls glyphes brûlés sont des caractères des valeurs exactes
du RenderJob, révélés selon config/T5_TEXT_MOTION_V3_0_0.json.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping
import re

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT = 720, 1280
TEXT_MOTION_CONFIG_PATH = ROOT / "config/T5_TEXT_MOTION_V3_0_0.json"
TEXT_MOTION: dict[str, Any] = json.loads(TEXT_MOTION_CONFIG_PATH.read_text(encoding="utf-8"))
FONT_FILE = ROOT / TEXT_MOTION["font"]["file"]
FONT_LICENSE_FILE = ROOT / TEXT_MOTION["font"]["license_file"]

SCENE_FIELDS: dict[str, tuple[str, ...]] = {
    scene: tuple(field["id"] for field in scene_contract["fields"])
    for scene, scene_contract in TEXT_MOTION["scenes"].items()
}
FIELD_SPECS: dict[str, dict[str, dict[str, Any]]] = {
    scene: {field["id"]: field for field in scene_contract["fields"]}
    for scene, scene_contract in TEXT_MOTION["scenes"].items()
}
FIELD_BOXES: dict[str, dict[str, tuple[int, int, int, int]]] = {
    scene: {field_id: tuple(spec["box"]) for field_id, spec in fields.items()}
    for scene, fields in FIELD_SPECS.items()
}
FIELD_PIXEL_PROOFS: dict[str, tuple[str, int]] = {
    field: (proof["scene"], int(proof["frame"]))
    for field, proof in TEXT_MOTION["field_pixel_proofs"].items()
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_motion_contract() -> None:
    expected_frames = {"S1": 180, "S2": 240, "S3": 210, "S4": 270}
    if set(SCENE_FIELDS) != set(expected_frames):
        raise RuntimeError("T5 text motion contract must define S1, S2, S3 and S4")
    if not FONT_FILE.is_file() or not FONT_LICENSE_FILE.is_file():
        raise RuntimeError("The contract-bound Playfair Display font and its OFL license are required")
    if TEXT_MOTION["font"]["family"] != "Playfair Display":
        raise RuntimeError("The active T5 readable editorial family must be Playfair Display")
    readability = TEXT_MOTION["readability_policy"]
    if TEXT_MOTION["render_style"]["fill"] != "#FFFFFF" or TEXT_MOTION["render_style"]["stroke_width"] != 0:
        raise RuntimeError("The active T5 text must remain solid white without an outline")
    if TEXT_MOTION["animation"]["letter_motion"] != "staggered_soft_rise_and_fade":
        raise RuntimeError("The active T5 letters must use the readable soft motion")
    if readability != {
        "priority": "maximum",
        "native_pair_kerning": True,
        "neutral_tracking": True,
        "minimum_preferred_size": 48,
        "minimum_weight": 800,
        "white_only": True,
        "no_outline": True,
        "long_copy_max_lines": 3,
    }:
        raise RuntimeError("The T5 maximum-readability policy must remain contract-bound")
    maximum_active = 0
    for scene, total in expected_frames.items():
        contract = TEXT_MOTION["scenes"][scene]
        if int(contract["scene_frames"]) != total:
            raise RuntimeError(f"Text motion scene length diverges for {scene}")
        for field in contract["fields"]:
            start = int(field["start_frame"])
            type_end = int(field["type_on_end_frame"])
            hold_end = int(field["hold_end_frame"])
            end = int(field["end_frame"])
            if not (0 <= start < type_end <= hold_end <= end <= total):
                raise RuntimeError(f"Invalid kinetic text interval for {scene}.{field['id']}")
            x0, y0, x1, y1 = map(int, field["box"])
            if not (0 <= x0 < x1 <= WIDTH and 0 <= y0 < y1 <= HEIGHT):
                raise RuntimeError(f"Invalid kinetic text box for {scene}.{field['id']}")
            if (
                int(field["weight"]) < int(readability["minimum_weight"])
                or int(field["preferred_size"]) < int(readability["minimum_preferred_size"])
                or float(field["tracking"]) != 0.0
            ):
                raise RuntimeError(f"Editorial text must remain large, bold and naturally spaced for {scene}.{field['id']}")
        for frame in range(total):
            active = sum(
                int(field["start_frame"]) <= frame < int(field["end_frame"])
                for field in contract["fields"]
            )
            maximum_active = max(maximum_active, active)
    if maximum_active > int(TEXT_MOTION["animation"]["max_simultaneous_fields"]):
        raise RuntimeError("The motion schedule exceeds the approved simultaneous-field limit")
    for field, (scene, proof_frame) in FIELD_PIXEL_PROOFS.items():
        spec = FIELD_SPECS[scene][field]
        if not (int(spec["type_on_end_frame"]) <= proof_frame < int(spec["hold_end_frame"])):
            raise RuntimeError(f"Pixel proof frame must show the complete value for {field}")
    tail = TEXT_MOTION["scenes"]["S4"]["stable_tail"]
    if tail != {"start_frame": 180, "end_frame": 269, "visible_fields": ["whatsapp", "quartier"]}:
        raise RuntimeError("The final three-second stable motion state must remain contract-bound")


_validate_motion_contract()


def motion_design_evidence() -> dict[str, Any]:
    scene_maximums: dict[str, int] = {}
    schedules: dict[str, list[dict[str, Any]]] = {}
    for scene, contract in TEXT_MOTION["scenes"].items():
        maximum = 0
        for frame in range(int(contract["scene_frames"])):
            maximum = max(
                maximum,
                sum(
                    int(field["start_frame"]) <= frame < int(field["end_frame"])
                    for field in contract["fields"]
                ),
            )
        scene_maximums[scene] = maximum
        schedules[scene] = [
            {
                "field": field["id"],
                "start_frame": field["start_frame"],
                "type_on_end_frame": field["type_on_end_frame"],
                "hold_end_frame": field["hold_end_frame"],
                "end_frame": field["end_frame"],
            }
            for field in contract["fields"]
        ]
    animation = TEXT_MOTION["animation"]
    return {
        "contract": {
            "file": str(TEXT_MOTION_CONFIG_PATH.relative_to(ROOT)),
            "sha256": _sha256(TEXT_MOTION_CONFIG_PATH),
            "revision": TEXT_MOTION["revision"],
        },
        "font": {
            "family": TEXT_MOTION["font"]["family"],
            "classification": TEXT_MOTION["font"]["classification"],
            "style_reference": TEXT_MOTION["font"]["style_reference"],
            "file": TEXT_MOTION["font"]["file"],
            "sha256": _sha256(FONT_FILE),
            "license": TEXT_MOTION["font"]["license"],
            "license_file": TEXT_MOTION["font"]["license_file"],
            "variation_axes": TEXT_MOTION["font"]["variation_axes"],
        },
        "reveal_unit": animation["reveal_unit"],
        "sequence": animation["sequence"],
        "alignment": animation["alignment"],
        "letter_motion": animation["letter_motion"],
        "composition": animation["composition"],
        "case_transform": animation["case_transform"],
        "white_bold_editorial_style": (
            TEXT_MOTION["render_style"]["fill"] == "#FFFFFF"
            and TEXT_MOTION["render_style"]["stroke_width"] == 0
            and min(field["weight"] for scene in TEXT_MOTION["scenes"].values() for field in scene["fields"])
                >= TEXT_MOTION["readability_policy"]["minimum_weight"]
            and min(field["preferred_size"] for scene in TEXT_MOTION["scenes"].values() for field in scene["fields"])
                >= TEXT_MOTION["readability_policy"]["minimum_preferred_size"]
        ),
        "native_pair_kerning": True,
        "readability_policy": TEXT_MOTION["readability_policy"],
        "static_all_fields_from_first_frame": animation["static_all_fields_from_first_frame"],
        "text_background_boxes": animation["text_background_boxes"],
        "max_simultaneous_fields": animation["max_simultaneous_fields"],
        "scene_max_simultaneous_fields": scene_maximums,
        "field_schedules": schedules,
        "stable_tail": TEXT_MOTION["scenes"]["S4"]["stable_tail"],
    }


def _resample() -> int:
    return getattr(Image, "Resampling", Image).LANCZOS


@lru_cache(maxsize=128)
def load_font(size: int, weight: int = 900) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(str(FONT_FILE), size)
    variation_axes = TEXT_MOTION["font"].get("variation_axes", {})
    if variation_axes and hasattr(font, "set_variation_by_axes"):
        axis_values: list[int] = []
        for tag, axis in variation_axes.items():
            if tag == "wght":
                axis_values.append(int(weight))
            else:
                axis_values.append(int(axis.get("render_value", axis["default"])))
        font.set_variation_by_axes(axis_values)
    return font


def cover(source: Image.Image, size: tuple[int, int] = (WIDTH, HEIGHT)) -> Image.Image:
    """Recadre au centre sans jamais créer de bord ni de cadre."""
    source = source.convert("RGB")
    target_w, target_h = size
    scale = max(target_w / source.width, target_h / source.height)
    resized = source.resize((round(source.width * scale), round(source.height * scale)), _resample())
    left = max(0, (resized.width - target_w) // 2)
    top = max(0, (resized.height - target_h) // 2)
    return resized.crop((left, top, left + target_w, top + target_h))


def _cover_with_motion(source: Image.Image, progress: float, mode: str) -> Image.Image:
    progress = max(0.0, min(1.0, progress))
    motion_progress = min(progress, 0.66) if mode == "lock" else progress
    if mode == "pull":
        zoom = 1.055 - 0.04 * motion_progress
    elif mode == "lock":
        eased = min(1.0, motion_progress / 0.66)
        zoom = 1.025 + 0.018 * eased
    else:
        zoom = 1.01 + 0.045 * motion_progress
    base = cover(source)
    crop_w = max(1, round(WIDTH / zoom))
    crop_h = max(1, round(HEIGHT / zoom))
    drift_x = round(10 * (motion_progress - 0.5))
    drift_y = round(8 * (0.5 - motion_progress))
    left = max(0, min(WIDTH - crop_w, (WIDTH - crop_w) // 2 + drift_x))
    top = max(0, min(HEIGHT - crop_h, (HEIGHT - crop_h) // 2 + drift_y))
    return base.crop((left, top, left + crop_w, top + crop_h)).resize((WIDTH, HEIGHT), _resample())


def _normalize(value: str) -> str:
    return " ".join(str(value).split())


def _tokens(value: str) -> list[str]:
    return re.findall(r"\S+", _normalize(value))


def _tracked_width(value: str, font: ImageFont.FreeTypeFont, tracking: float) -> float:
    if not value:
        return 0.0
    # Mesurer la chaîne complète conserve le kerning natif des paires (AV, To, etc.).
    return float(font.getlength(value)) + tracking * max(0, len(value) - 1)


def _wrap_lines(value: str, font: ImageFont.FreeTypeFont, max_width: int, tracking: float) -> list[str]:
    words = _tokens(value) or [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if _tracked_width(candidate, font, tracking) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


@lru_cache(maxsize=256)
def _layout_text(
    value: str,
    max_width: int,
    max_height: int,
    preferred_size: int,
    minimum_size: int,
    weight: int,
    max_lines: int,
    tracking: float,
    line_spacing: int,
) -> tuple[tuple[str, ...], int, int, int]:
    normalized = _normalize(value)
    fallback: tuple[tuple[str, ...], int, int, int] | None = None
    for size in range(preferred_size, minimum_size - 1, -1):
        font = load_font(size, weight)
        lines = _wrap_lines(normalized, font, max_width, tracking)
        line_bbox = font.getbbox("Ag", anchor="lt")
        line_height = max(1, line_bbox[3] - line_bbox[1])
        total_height = line_height * len(lines) + line_spacing * max(0, len(lines) - 1)
        fallback = (tuple(lines), size, line_height, total_height)
        if (
            len(lines) <= max_lines
            and max((_tracked_width(line, font, tracking) for line in lines), default=0) <= max_width
            and total_height <= max_height
        ):
            return fallback
    if fallback is None:
        font = load_font(minimum_size, weight)
        line_height = max(1, font.getbbox("Ag", anchor="lt")[3])
        return ((normalized,), minimum_size, line_height, line_height)
    return fallback


@lru_cache(maxsize=1)
def _readability_gradient() -> Image.Image:
    """Dégradé continu jusqu'au dernier pixel, sans trait ni rupture de teinte."""
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    top = 680
    for y in range(top, HEIGHT):
        p = (y - top) / max(1, HEIGHT - top - 1)
        alpha = round(150 * (p ** 1.25))
        draw.line((0, y, WIDTH, y), fill=(6, 5, 4, alpha), width=1)
    return overlay


def readability_gradient_evidence() -> dict[str, int | bool]:
    overlay = _readability_gradient()
    alpha = [overlay.getpixel((WIDTH // 2, y))[3] for y in range(HEIGHT)]
    jumps = [abs(current - previous) for previous, current in zip(alpha, alpha[1:])]
    return {
        "start_row": 680,
        "last_row": HEIGHT - 1,
        "bottom_alpha": alpha[-1],
        "max_adjacent_alpha_jump": max(jumps),
        "monotonic_non_decreasing": all(current >= previous for previous, current in zip(alpha, alpha[1:])),
        "reaches_frame_bottom": alpha[-1] > 0,
    }


def _gradient_overlay(base: Image.Image) -> Image.Image:
    return Image.alpha_composite(base.convert("RGBA"), _readability_gradient()).convert("RGB")


def _smoothstep(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def text_motion_state(scene: str, field: str, local_frame: int, value: str) -> dict[str, Any]:
    spec = FIELD_SPECS[scene][field]
    start = int(spec["start_frame"])
    type_end = int(spec["type_on_end_frame"])
    hold_end = int(spec["hold_end_frame"])
    end = int(spec["end_frame"])
    total_characters = len(_normalize(value))
    reveal_duration = max(1, type_end - start)
    if local_frame < start or local_frame >= end or total_characters == 0:
        return {
            "phase": "hidden",
            "visible_characters": 0,
            "total_characters": total_characters,
            "elapsed_frames": 0,
            "reveal_duration": reveal_duration,
            "alpha": 0,
            "y_offset": 0,
        }
    elapsed_frames = local_frame - start + 1
    letter_fade_frames = int(TEXT_MOTION["animation"]["letter_fade_frames"])
    stagger_span = max(0.0, float(reveal_duration - letter_fade_frames))
    if total_characters <= 1 or stagger_span == 0:
        visible_characters = total_characters
    else:
        visible_characters = sum(
            elapsed_frames > character_index * stagger_span / (total_characters - 1)
            for character_index in range(total_characters)
        )
    visible_characters = min(total_characters, max(1, visible_characters))
    entry_frames = int(TEXT_MOTION["animation"]["entry_fade_frames"])
    entry_progress = min(1.0, (local_frame - start + 1) / max(1, entry_frames))
    entry_eased = _smoothstep(entry_progress)
    alpha_factor = entry_eased
    y_offset = float(TEXT_MOTION["animation"]["entry_rise_pixels"]) * (1.0 - entry_eased)
    phase = "type_on" if local_frame < type_end else "hold"
    if hold_end < end and local_frame >= hold_end:
        exit_progress = (local_frame - hold_end + 1) / max(1, end - hold_end)
        exit_eased = _smoothstep(exit_progress)
        alpha_factor *= 1.0 - exit_eased
        y_offset -= float(TEXT_MOTION["animation"]["exit_rise_pixels"]) * exit_eased
        phase = "exit"
    return {
        "phase": phase,
        "visible_characters": visible_characters,
        "total_characters": total_characters,
        "elapsed_frames": elapsed_frames,
        "reveal_duration": reveal_duration,
        "alpha": max(0, min(255, round(255 * alpha_factor))),
        "y_offset": round(y_offset, 3),
    }


def _hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))


def _draw_characters(
    draw: ImageDraw.ImageDraw,
    lines: tuple[str, ...],
    *,
    state: Mapping[str, Any],
    font: ImageFont.FreeTypeFont,
    x: float,
    y: float,
    line_height: int,
    line_spacing: int,
    tracking: float,
    fill: tuple[int, int, int, int],
    stroke_width: int = 0,
    stroke_fill: tuple[int, int, int, int] | None = None,
) -> None:
    visible_characters = int(state["visible_characters"])
    total_characters = int(state["total_characters"])
    elapsed_frames = float(state["elapsed_frames"])
    reveal_duration = float(state["reveal_duration"])
    letter_fade_frames = float(TEXT_MOTION["animation"]["letter_fade_frames"])
    letter_rise_pixels = float(TEXT_MOTION["animation"]["letter_rise_pixels"])
    stagger_span = max(0.0, reveal_duration - letter_fade_frames)
    character_index = 0
    for line_index, line in enumerate(lines):
        for line_character_index, character in enumerate(line):
            if character_index >= visible_characters:
                return
            # Position cumulative avec la paire courante afin de conserver le kerning natif.
            shaped_prefix = line[:line_character_index + 1]
            cursor_x = (
                x
                + float(font.getlength(shaped_prefix))
                - float(font.getlength(character))
                + tracking * line_character_index
            )
            if state["phase"] == "type_on" and total_characters > 1 and stagger_span > 0:
                start_offset = character_index * stagger_span / (total_characters - 1)
                letter_progress = _smoothstep((elapsed_frames - start_offset) / max(1.0, letter_fade_frames))
            else:
                letter_progress = 1.0
            character_fill = (*fill[:3], round(fill[3] * letter_progress))
            character_stroke = None
            if stroke_fill is not None:
                character_stroke = (*stroke_fill[:3], round(stroke_fill[3] * letter_progress))
            character_y = (
                y
                + line_index * (line_height + line_spacing)
                + letter_rise_pixels * (1.0 - letter_progress)
            )
            draw.text(
                (cursor_x, character_y),
                character,
                font=font,
                anchor="lt",
                fill=character_fill,
                stroke_width=stroke_width,
                stroke_fill=character_stroke,
            )
            character_index += 1
        if line_index < len(lines) - 1:
            # Le wrapping remplace exactement un espace de la valeur normalisée.
            character_index += 1


def _draw_kinetic_value(
    frame: Image.Image,
    value: str,
    spec: Mapping[str, Any],
    state: Mapping[str, Any],
) -> None:
    if int(state["alpha"]) <= 0 or int(state["visible_characters"]) <= 0:
        return
    x0, y0, x1, y1 = map(int, spec["box"])
    box_width, box_height = x1 - x0, y1 - y0
    tracking = float(spec["tracking"])
    line_spacing = int(spec["line_spacing"])
    lines, size, line_height, total_height = _layout_text(
        _normalize(value),
        box_width,
        box_height,
        int(spec["preferred_size"]),
        int(spec["minimum_size"]),
        int(spec["weight"]),
        int(spec["max_lines"]),
        tracking,
        line_spacing,
    )
    font = load_font(size, int(spec["weight"]))
    style = TEXT_MOTION["render_style"]
    blur = int(style["shadow_blur_radius"])
    shadow_offset_x, shadow_offset_y = map(int, style["shadow_offset"])
    padding = max(12, blur * 2 + max(abs(shadow_offset_x), abs(shadow_offset_y)) + 3)
    layer_size = (box_width + padding * 2, box_height + padding * 2)
    alpha = int(state["alpha"])
    text_rgb = _hex_rgb(style["accent_fill"] if spec["accent"] else style["fill"])
    shadow_rgb = _hex_rgb(style["shadow"])
    text_y = padding + max(0, (box_height - total_height) / 2) + float(state["y_offset"])
    text_x = float(padding)

    shadow_layer = Image.new("RGBA", layer_size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_layer)
    _draw_characters(
        shadow_draw,
        lines,
        state=state,
        font=font,
        x=text_x + shadow_offset_x,
        y=text_y + shadow_offset_y,
        line_height=line_height,
        line_spacing=line_spacing,
        tracking=tracking,
        fill=(*shadow_rgb, round(int(style["shadow_alpha"]) * alpha / 255)),
    )
    if blur:
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=blur))

    text_layer = Image.new("RGBA", layer_size, (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_layer)
    stroke_alpha = round(int(style["stroke_alpha"]) * alpha / 255)
    _draw_characters(
        text_draw,
        lines,
        state=state,
        font=font,
        x=text_x,
        y=text_y,
        line_height=line_height,
        line_spacing=line_spacing,
        tracking=tracking,
        fill=(*text_rgb, alpha),
        stroke_width=int(style["stroke_width"]),
        stroke_fill=(*shadow_rgb, stroke_alpha),
    )
    composed = Image.alpha_composite(shadow_layer, text_layer)
    frame.paste(composed, (x0 - padding, y0 - padding), composed)


def render_scene_frame(
    source: Image.Image,
    scene: str,
    local_frame: int,
    merchant_payload: Mapping[str, str],
    scene_frames: int | None = None,
) -> tuple[Image.Image, tuple[str, ...]]:
    """Rend une image plein cadre et applique le planning typographique du JSON."""
    fields = SCENE_FIELDS[scene]
    configured_frames = int(TEXT_MOTION["scenes"][scene]["scene_frames"])
    if scene_frames is not None and int(scene_frames) != configured_frames:
        raise ValueError(f"Scene frame count diverges from text motion contract for {scene}")
    denominator = max(1, configured_frames - 1)
    progress = max(0.0, min(1.0, local_frame / denominator))
    mode = "pull" if scene == "S2" else "lock" if scene == "S4" else "push"
    frame = _gradient_overlay(_cover_with_motion(source, progress, mode))
    for field in fields:
        value = str(merchant_payload[field])
        state = text_motion_state(scene, field, local_frame, value)
        _draw_kinetic_value(frame, value, FIELD_SPECS[scene][field], state)
    return frame, fields


def apply_transition(
    previous_frame: Image.Image,
    next_frame: Image.Image,
    step: int,
    duration_frames: int = 8,
    direction: str = "left",
) -> Image.Image:
    """Raccord dish swipe / camera whip T1 sur exactement huit images."""
    if duration_frames != 8:
        raise ValueError("T5 V3 transitions must last exactly 8 frames")
    if direction not in {"left", "right"}:
        raise ValueError("direction must be left or right")
    step = max(0, min(duration_frames - 1, step))
    if step == 0:
        return previous_frame.copy()
    if step == duration_frames - 1:
        return next_frame.copy()
    p = step / (duration_frames - 1)
    eased = p * p * (3.0 - 2.0 * p)
    shift = round(WIDTH * eased)
    canvas = Image.new("RGB", (WIDTH, HEIGHT))
    if direction == "left":
        canvas.paste(previous_frame, (-shift, 0))
        canvas.paste(next_frame, (WIDTH - shift, 0))
    else:
        canvas.paste(previous_frame, (shift, 0))
        canvas.paste(next_frame, (shift - WIDTH, 0))
    blur = round(5.0 * (1.0 - abs(2.0 * p - 1.0)))
    if blur:
        canvas = canvas.filter(ImageFilter.GaussianBlur(radius=blur))
    return canvas


def proof_timeline(captures: Mapping[str, Image.Image], merchant_payload: Mapping[str, str]) -> dict[str, Image.Image]:
    return {
        scene: render_scene_frame(captures[scene], scene, 120, merchant_payload)[0]
        for scene in ("S1", "S2", "S3", "S4")
    }


def changed_pixel_count(a: Image.Image, b: Image.Image) -> tuple[int, tuple[int, int, int, int] | None]:
    difference = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
    bbox = difference.getbbox()
    if bbox is None:
        return 0, None
    pixels = difference.get_flattened_data() if hasattr(difference, "get_flattened_data") else difference.getdata()
    return sum(1 for pixel in pixels if pixel != (0, 0, 0)), bbox
