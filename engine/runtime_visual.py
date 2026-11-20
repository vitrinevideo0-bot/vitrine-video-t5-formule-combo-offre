"""Composition visuelle déterministe des textes T5 sur une prise runtime."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
FONT_BOLD = ROOT / "assets/fonts/DejaVuSans-Bold.ttf"
FONT_REGULAR = ROOT / "assets/fonts/DejaVuSans.ttf"
WIDTH, HEIGHT = 720, 1280
FPS = 30
SCENE_FRAMES = {"S1": 180, "S2": 240, "S3": 210, "S4": 270}
SCENE_FIELDS = {
    "S1": ("nom", "offre", "contenu"),
    "S2": ("contenu",),
    "S3": ("offre", "contenu", "prix"),
    "S4": ("nom", "whatsapp", "quartier"),
}
FIELD_BOXES = {
    "S1": {"nom": (48, 580, 672, 650), "offre": (48, 650, 672, 790), "contenu": (48, 805, 672, 1045)},
    "S2": {"contenu": (48, 690, 672, 1010)},
    "S3": {"offre": (48, 580, 672, 660), "prix": (48, 675, 672, 835), "contenu": (48, 875, 672, 1085)},
    "S4": {"nom": (48, 580, 672, 655), "whatsapp": (48, 700, 672, 855), "quartier": (48, 890, 672, 1035)},
}
ACCENT = "#F8B84E"
CREAM = "#FFF5DF"
MUTED = "#D6C9B6"
INK = "#130E0A"
RED = "#E45B3D"


@dataclass(frozen=True)
class SceneCopy:
    scene: str
    label: str
    eyebrow: str
    title: str
    body: str
    footer: str
    fields: tuple[str, ...]


def resolved_scene_copy(scene: str, payload: dict[str, str]) -> SceneCopy:
    if scene == "S1":
        return SceneCopy(scene, "LA FORMULE", payload["nom"], payload["offre"], payload["contenu"], "UNE SEULE FORMULE · TOUT EST INCLUS", SCENE_FIELDS[scene])
    if scene == "S2":
        return SceneCopy(scene, "DANS LA FORMULE", "REGARDE BIEN", "TOUT EST LÀ", payload["contenu"], "PLAT · BOISSON · ACCOMPAGNEMENT", SCENE_FIELDS[scene])
    if scene == "S3":
        return SceneCopy(scene, "LE PRIX", payload["offre"], payload["prix"], payload["contenu"], "LE PRIX DE LA FORMULE COMPLÈTE", SCENE_FIELDS[scene])
    if scene == "S4":
        return SceneCopy(scene, "COMMANDER", payload["nom"], "ÉCRIS-NOUS SUR WHATSAPP", payload["whatsapp"], payload["quartier"], SCENE_FIELDS[scene])
    raise ValueError(f"Unknown T5 scene: {scene}")


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size=size)


def _cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(image.convert("RGB"), size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def _rounded_image(image: Image.Image, size: tuple[int, int], radius: int) -> Image.Image:
    contained = ImageOps.contain(image.convert("RGB"), size, method=Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, "#080604")
    canvas.paste(contained, ((size[0] - contained.width) // 2, (size[1] - contained.height) // 2))
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    result = Image.new("RGBA", size)
    result.paste(canvas, (0, 0), mask)
    return result


def _ease(frame: int, start: int = 8, duration: int = 16) -> float:
    value = max(0.0, min(1.0, (frame - start) / max(1, duration)))
    return 1 - (1 - value) ** 3


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, width: int, max_lines: int = 4) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if draw.textlength(candidate, font=font) <= width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    if len(lines) <= max_lines:
        return lines
    kept = lines[: max_lines - 1]
    remainder = " ".join(lines[max_lines - 1 :])
    while draw.textlength(remainder + "…", font=font) > width and len(remainder) > 1:
        remainder = remainder[:-1]
    kept.append(remainder.rstrip() + "…")
    return kept


def _fit_font(draw: ImageDraw.ImageDraw, text: str, path: Path, maximum: int, minimum: int, width: int) -> ImageFont.FreeTypeFont:
    for size in range(maximum, minimum - 1, -1):
        font = _font(path, size)
        if draw.textlength(text, font=font) <= width:
            return font
    return _font(path, minimum)


def _draw_wrapped(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font: ImageFont.FreeTypeFont, fill: str, width: int, spacing: int = 10, max_lines: int = 4) -> tuple[int, int, int, int]:
    lines = _wrap(draw, text, font, width, max_lines=max_lines)
    x, y = xy
    line_height = int(font.size * 1.18)
    for index, line in enumerate(lines):
        draw.text((x, y + index * (line_height + spacing)), line, font=font, fill=fill)
    return (x, y, x + width, y + len(lines) * line_height + max(0, len(lines) - 1) * spacing)


def _scene_progress(draw: ImageDraw.ImageDraw, scene: str, local_frame: int) -> None:
    scene_index = int(scene[1:])
    draw.text((42, 38), f"FORMULE · SCÈNE {scene_index}/4", font=_font(FONT_BOLD, 18), fill=CREAM)
    total_width, gap = 636, 8
    segment = (total_width - gap * 3) // 4
    for index in range(4):
        x = 42 + index * (segment + gap)
        color = ACCENT if index < scene_index - 1 else "#5B4B3C"
        draw.rounded_rectangle((x, 86, x + segment, 94), radius=4, fill=color)
    active_x = 42 + (scene_index - 1) * (segment + gap)
    fraction = max(0.0, min(1.0, (local_frame + 1) / SCENE_FRAMES[scene]))
    draw.rounded_rectangle((active_x, 86, active_x + max(4, int(segment * fraction)), 94), radius=4, fill=ACCENT)


def render_scene_frame(source: Image.Image, scene: str, local_frame: int, payload: dict[str, str]) -> tuple[Image.Image, tuple[str, ...]]:
    """Rend une image 720×1280. Aucune valeur métier n'est lue ailleurs que dans payload."""
    if scene not in SCENE_FRAMES:
        raise ValueError(f"Unknown scene {scene}")
    local_frame = max(0, min(SCENE_FRAMES[scene] - 1, int(local_frame)))
    copy = resolved_scene_copy(scene, payload)

    small_background = _cover(source, (360, 640)).filter(ImageFilter.GaussianBlur(10))
    background = small_background.resize((WIDTH, HEIGHT), Image.Resampling.BILINEAR)
    background = ImageEnhance.Brightness(background).enhance(0.30).convert("RGBA")
    warm = Image.new("RGBA", (WIDTH, HEIGHT), (54, 25, 9, 70))
    canvas = Image.alpha_composite(background, warm)
    draw = ImageDraw.Draw(canvas)
    _scene_progress(draw, scene, local_frame)

    hero_box = (30, 120, 690, 518)
    draw.rounded_rectangle((24, 114, 696, 524), radius=32, fill=(0, 0, 0, 125), outline=ACCENT, width=2)
    hero = _rounded_image(source, (660, 398), 26)
    canvas.alpha_composite(hero, (hero_box[0], hero_box[1]))

    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((30, 548, 690, 1214), radius=38, fill=(15, 10, 7, 230), outline=(255, 255, 255, 28), width=2)
    draw.rounded_rectangle((50, 570, 218, 606), radius=18, fill=RED)
    label_font = _font(FONT_BOLD, 16)
    label_width = draw.textlength(copy.label, font=label_font)
    draw.text((134 - label_width / 2, 578), copy.label, font=label_font, fill="white")

    reveal = _ease(local_frame)
    text_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_layer)
    shift = int((1 - reveal) * 22)
    alpha = max(0, min(255, int(255 * reveal)))
    cream = (255, 245, 223, alpha)
    accent = (248, 184, 78, alpha)
    muted = (214, 201, 182, alpha)

    if scene == "S1":
        eyebrow_font = _fit_font(text_draw, copy.eyebrow.upper(), FONT_BOLD, 25, 18, 610)
        text_draw.text((52, 620 + shift), copy.eyebrow.upper(), font=eyebrow_font, fill=muted)
        title_font = _fit_font(text_draw, copy.title, FONT_BOLD, 52, 30, 612)
        _draw_wrapped(text_draw, (52, 667 + shift), copy.title, title_font, cream, 612, spacing=4, max_lines=2)
        body_font = _font(FONT_REGULAR, 31)
        _draw_wrapped(text_draw, (52, 836 + shift), copy.body, body_font, cream, 612, spacing=8, max_lines=4)
        text_draw.rounded_rectangle((52, 1114 + shift, 668, 1170 + shift), radius=20, fill=(248, 184, 78, int(36 * reveal)))
        text_draw.text((70, 1130 + shift), copy.footer, font=_font(FONT_BOLD, 17), fill=accent)
    elif scene == "S2":
        text_draw.text((52, 620 + shift), copy.eyebrow, font=_font(FONT_BOLD, 22), fill=accent)
        text_draw.text((52, 660 + shift), copy.title, font=_font(FONT_BOLD, 48), fill=cream)
        body_font = _font(FONT_BOLD, 37)
        _draw_wrapped(text_draw, (52, 742 + shift), copy.body, body_font, cream, 612, spacing=12, max_lines=4)
        text_draw.text((52, 1118 + shift), copy.footer, font=_font(FONT_BOLD, 16), fill=muted)
    elif scene == "S3":
        eyebrow_font = _fit_font(text_draw, copy.eyebrow.upper(), FONT_BOLD, 24, 17, 610)
        text_draw.text((52, 620 + shift), copy.eyebrow.upper(), font=eyebrow_font, fill=muted)
        price_font = _fit_font(text_draw, copy.title, FONT_BOLD, 78, 44, 610)
        text_draw.text((52, 684 + shift), copy.title, font=price_font, fill=accent)
        body_font = _font(FONT_REGULAR, 27)
        _draw_wrapped(text_draw, (52, 885 + shift), copy.body, body_font, cream, 612, spacing=8, max_lines=4)
        text_draw.text((52, 1120 + shift), copy.footer, font=_font(FONT_BOLD, 17), fill=muted)
    else:
        eyebrow_font = _fit_font(text_draw, copy.eyebrow.upper(), FONT_BOLD, 24, 17, 610)
        text_draw.text((52, 620 + shift), copy.eyebrow.upper(), font=eyebrow_font, fill=muted)
        text_draw.text((52, 680 + shift), copy.title, font=_font(FONT_BOLD, 29), fill=cream)
        phone_font = _fit_font(text_draw, copy.body, FONT_BOLD, 57, 35, 610)
        text_draw.text((52, 746 + shift), copy.body, font=phone_font, fill=accent)
        text_draw.rounded_rectangle((52, 878 + shift, 668, 1028 + shift), radius=24, fill=(255, 245, 223, int(20 * reveal)), outline=(248, 184, 78, int(110 * reveal)), width=2)
        text_draw.text((72, 900 + shift), "RETRAIT", font=_font(FONT_BOLD, 15), fill=muted)
        pickup_font = _font(FONT_BOLD, 27)
        _draw_wrapped(text_draw, (72, 935 + shift), copy.footer, pickup_font, cream, 570, spacing=6, max_lines=2)
        text_draw.text((52, 1118 + shift), "COMMANDE PRÊTE À ÊTRE RETIRÉE", font=_font(FONT_BOLD, 16), fill=muted)

    canvas = Image.alpha_composite(canvas, text_layer)
    return canvas.convert("RGB"), copy.fields


def slide_transition(previous: Image.Image, current: Image.Image, progress: float, direction: str) -> Image.Image:
    progress = max(0.0, min(1.0, progress))
    eased = 1 - (1 - progress) ** 3
    result = Image.new("RGB", (WIDTH, HEIGHT), INK)
    if direction == "slideright":
        shift = int(WIDTH * eased)
        result.paste(previous, (shift, 0))
        result.paste(current, (-WIDTH + shift, 0))
    else:
        shift = int(WIDTH * eased)
        result.paste(previous, (-shift, 0))
        result.paste(current, (WIDTH - shift, 0))
    return result


def changed_pixel_count(first: Image.Image, second: Image.Image) -> tuple[int, tuple[int, int, int, int] | None]:
    difference = ImageChops.difference(first.convert("RGB"), second.convert("RGB"))
    histogram = difference.convert("L").histogram()
    return sum(histogram[1:]), difference.getbbox()


def proof_timeline(captures: dict[str, Image.Image], payload: dict[str, str]) -> dict[str, Image.Image]:
    """Rend une image témoin par scène ; utile pour prouver l'isolation des quatre captures."""
    return {
        slot: render_scene_frame(captures[slot], slot, SCENE_FRAMES[slot] // 2, payload)[0]
        for slot in ("S1", "S2", "S3", "S4")
    }
