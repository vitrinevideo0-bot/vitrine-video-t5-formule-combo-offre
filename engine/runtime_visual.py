#!/usr/bin/env python3
"""Primitives visuelles T5 V3 : rush plein écran et texte exact du merchant_payload.

Aucun titre éditorial, carte, cadre vidéo, barre de progression ou libellé de scène
n'est produit ici. Les seules chaînes brûlées viennent du RenderJob.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Mapping
import re

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

WIDTH, HEIGHT = 720, 1280
FONT_REGULAR = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
FONT_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")

SCENE_FIELDS: dict[str, tuple[str, ...]] = {
    "S1": ("nom", "offre", "contenu"),
    "S2": ("contenu",),
    "S3": ("offre", "contenu", "prix"),
    "S4": ("nom", "whatsapp", "quartier"),
}

# Zones de texte transparentes, exprimées dans le plein cadre 720 x 1280.
FIELD_BOXES: dict[str, dict[str, tuple[int, int, int, int]]] = {
    "S1": {
        "nom": (52, 758, 668, 820),
        "offre": (52, 832, 668, 928),
        "contenu": (52, 942, 668, 1074),
    },
    "S2": {
        "contenu": (52, 872, 668, 1074),
    },
    "S3": {
        "offre": (52, 750, 668, 826),
        "contenu": (52, 840, 668, 952),
        "prix": (52, 972, 668, 1082),
    },
    "S4": {
        "nom": (52, 758, 668, 820),
        "whatsapp": (52, 838, 668, 932),
        "quartier": (52, 948, 668, 1056),
    },
}

SCENE_TEXT_STYLE: dict[str, dict[str, tuple[int, int]]] = {
    # (taille préférée, taille minimale) — la réduction permet toujours d'afficher la valeur entière.
    "S1": {"nom": (34, 24), "offre": (50, 32), "contenu": (31, 22)},
    "S2": {"contenu": (42, 24)},
    "S3": {"offre": (36, 24), "contenu": (28, 20), "prix": (58, 40)},
    "S4": {"nom": (34, 24), "whatsapp": (43, 30), "quartier": (31, 22)},
}


def _resample() -> int:
    return getattr(Image, "Resampling", Image).LANCZOS


@lru_cache(maxsize=128)
def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = FONT_BOLD if bold else FONT_REGULAR
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        return ImageFont.load_default()


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
    # Un mouvement discret dynamise même une capture stable, sans la placer dans une carte.
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


def _tokens(value: str) -> list[str]:
    return re.findall(r"\S+", " ".join(value.split()))


def _fit_lines(
    draw: ImageDraw.ImageDraw,
    value: str,
    *,
    max_width: int,
    max_height: int,
    preferred_size: int,
    minimum_size: int,
    bold: bool,
    max_lines: int,
) -> tuple[list[str], ImageFont.ImageFont, int]:
    words = _tokens(value)
    if not words:
        words = [""]
    fallback: tuple[list[str], ImageFont.ImageFont, int] | None = None
    for size in range(preferred_size, minimum_size - 1, -1):
        font = load_font(size, bold)
        spacing = max(5, round(size * 0.2))
        lines: list[str] = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if draw.textbbox((0, 0), candidate, font=font, stroke_width=1)[2] <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        fallback = (lines, font, spacing)
        bbox = draw.multiline_textbbox((0, 0), "\n".join(lines), font=font, spacing=spacing, stroke_width=1)
        if len(lines) <= max_lines and bbox[2] <= max_width and bbox[3] <= max_height:
            return lines, font, spacing
    if fallback is None:
        font = load_font(minimum_size, bold)
        return [" ".join(words)], font, max(4, round(minimum_size * 0.18))
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
    """Mesure le profil réellement appliqué afin que le QC interdise le retour du trait horizontal."""
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
    """Assombrit seulement le bord inférieur; aucune carte rectangulaire n'est dessinée."""
    return Image.alpha_composite(base.convert("RGBA"), _readability_gradient()).convert("RGB")


def _draw_exact_value(
    frame: Image.Image,
    value: str,
    box: tuple[int, int, int, int],
    *,
    preferred_size: int,
    minimum_size: int,
    bold: bool,
    accent: bool = False,
) -> None:
    draw = ImageDraw.Draw(frame)
    x0, y0, x1, y1 = box
    lines, font, spacing = _fit_lines(
        draw,
        value,
        max_width=x1 - x0,
        max_height=y1 - y0,
        preferred_size=preferred_size,
        minimum_size=minimum_size,
        bold=bold,
        max_lines=3,
    )
    text = "\n".join(lines)
    bbox = draw.multiline_textbbox((0, 0), text, font=font, spacing=spacing, stroke_width=1)
    y = y0 + max(0, (y1 - y0 - (bbox[3] - bbox[1])) // 2)
    fill = (255, 229, 117) if accent else (255, 255, 255)
    # Ombre/contour uniquement : il ne s'agit pas d'un texte commercial ajouté.
    draw.multiline_text(
        (x0 + 3, y + 4), text, font=font, fill=(0, 0, 0), spacing=spacing,
        stroke_width=3, stroke_fill=(0, 0, 0),
    )
    draw.multiline_text(
        (x0, y), text, font=font, fill=fill, spacing=spacing,
        stroke_width=1, stroke_fill=(20, 16, 12),
    )


def render_scene_frame(
    source: Image.Image,
    scene: str,
    local_frame: int,
    merchant_payload: Mapping[str, str],
    scene_frames: int | None = None,
) -> tuple[Image.Image, tuple[str, ...]]:
    """Rend une image plein cadre. Retourne aussi les champs effectivement brûlés."""
    fields = SCENE_FIELDS[scene]
    denominator = max(1, (scene_frames or 270) - 1)
    progress = max(0.0, min(1.0, local_frame / denominator))
    mode = "pull" if scene == "S2" else "lock" if scene == "S4" else "push"
    frame = _cover_with_motion(source, progress, mode)
    frame = _gradient_overlay(frame)
    for field in fields:
        preferred, minimum = SCENE_TEXT_STYLE[scene][field]
        _draw_exact_value(
            frame,
            str(merchant_payload[field]),
            FIELD_BOXES[scene][field],
            preferred_size=preferred,
            minimum_size=minimum,
            bold=field in {"offre", "prix", "whatsapp"},
            accent=field in {"prix", "whatsapp"},
        )
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
    # Flou horizontal maximal au milieu, simulant le whip sans masquer les rushs.
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
