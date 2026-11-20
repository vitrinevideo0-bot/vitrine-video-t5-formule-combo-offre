#!/usr/bin/env python3
"""Generate the twelve T5 proof screens from the approved simple-French capture flow."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
W, H = 720, 1280
FONT = ROOT / "assets/fonts/DejaVuSans.ttf"
BOLD = ROOT / "assets/fonts/DejaVuSans-Bold.ttf"
CREAM = (248, 242, 232)
PAPER = (255, 251, 245)
INK = (36, 29, 25)
MUTED = (103, 88, 78)
RED = (196, 62, 42)
GREEN = (47, 112, 82)
GOLD = (218, 145, 55)
DARK = (20, 16, 16)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(BOLD if bold else FONT), size)


def wrap(draw: ImageDraw.ImageDraw, text: str, selected_font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if draw.textlength(candidate, font=selected_font) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    selected_font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int] | str,
    max_width: int,
    line_gap: int = 4,
) -> int:
    y = xy[1]
    for line in wrap(draw, text, selected_font, max_width):
        draw.text((xy[0], y), line, font=selected_font, fill=fill)
        y += selected_font.size + line_gap
    return y


def center_wrapped(
    draw: ImageDraw.ImageDraw,
    y: int,
    text: str,
    selected_font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int] | str,
    max_width: int,
    line_gap: int = 5,
) -> int:
    lines = wrap(draw, text, selected_font, max_width)
    for line in lines:
        width = draw.textlength(line, font=selected_font)
        draw.text(((W - width) / 2, y), line, font=selected_font, fill=fill)
        y += selected_font.size + line_gap
    return y


def gradient_background(scene_index: int) -> Image.Image:
    palettes = [
        ((39, 23, 20), (131, 67, 41)),
        ((27, 35, 31), (93, 104, 70)),
        ((36, 24, 30), (132, 67, 69)),
        ((24, 22, 24), (88, 62, 46)),
    ]
    top, bottom = palettes[scene_index - 1]
    image = Image.new("RGB", (W, H), top)
    px = image.load()
    for y in range(H):
        q = y / max(1, H - 1)
        for x in range(W):
            glow = max(0.0, 1.0 - math.hypot((x - W * 0.55) / W, (y - H * 0.38) / H) * 1.8)
            px[x, y] = tuple(
                max(0, min(255, int(top[c] * (1 - q) + bottom[c] * q + glow * (16 if c != 2 else 10))))
                for c in range(3)
            )
    return image


def draw_person(draw: ImageDraw.ImageDraw, cx: int, cy: int, scale: float, shirt: tuple[int, int, int], skin: tuple[int, int, int] = (173, 112, 78)) -> None:
    r = int(34 * scale)
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=skin)
    draw.rounded_rectangle((cx - int(62 * scale), cy + int(30 * scale), cx + int(62 * scale), cy + int(175 * scale)), radius=int(35 * scale), fill=shirt)


def draw_scene_art(image: Image.Image, scene_index: int) -> None:
    """Draw the same cake-and-drink formula in every scene to prove continuity."""
    draw = ImageDraw.Draw(image, "RGBA")
    for i in range(13):
        x = 38 + (i * 113) % 670
        y = 85 + (i * 71) % 420
        radius = 6 + (i % 4) * 3
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(255, 196, 90, 70))
    # One tray, one cake plate and one hot drink are kept in all four scenes.
    draw.ellipse((55, 565, 665, 940), fill=(91, 54, 38, 245), outline=(224, 160, 77, 220), width=6)
    draw.ellipse((245, 620, 625, 850), fill=(236, 226, 207, 255), outline=(255, 248, 236, 255), width=5)
    draw.rounded_rectangle((330, 650, 540, 800), radius=34, fill=(225, 199, 125, 255), outline=(247, 227, 173, 255), width=4)
    draw.rectangle((347, 670, 523, 704), fill=(245, 235, 214, 255))
    draw.polygon([(355, 651), (402, 615), (447, 652)], fill=(235, 165, 56, 255))
    draw.polygon([(430, 651), (478, 611), (523, 652)], fill=(235, 165, 56, 255))
    draw.rounded_rectangle((92, 650, 255, 843), radius=35, fill=(243, 237, 220, 255), outline=(255, 249, 237, 255), width=5)
    draw.ellipse((104, 633, 243, 706), fill=(244, 236, 216, 255), outline=(255, 250, 238, 255), width=5)
    draw.ellipse((120, 651, 228, 691), fill=(168, 105, 53, 255))
    draw.ellipse((219, 705, 294, 793), outline=(244, 237, 220, 255), width=15)
    if scene_index == 2:
        # A pointing hand mirrors the owner's instruction without hiding the formula.
        draw.line((590, 505, 490, 620), fill=(160, 101, 70, 255), width=24)
        draw.ellipse((470, 605, 505, 640), fill=(160, 101, 70, 255))
    if scene_index == 4:
        draw.rounded_rectangle((72, 895, 648, 990), radius=22, fill=(57, 40, 32, 220), outline=(224, 160, 77, 190), width=4)


def preview(scene_index: int, dim: int = 0) -> Image.Image:
    image = gradient_background(scene_index).convert("RGBA")
    draw_scene_art(image, scene_index)
    if dim:
        image = Image.alpha_composite(image, Image.new("RGBA", (W, H), (0, 0, 0, dim)))
    return image.convert("RGB")


def pill(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, fill: tuple[int, int, int, int], selected_font: ImageFont.FreeTypeFont) -> None:
    draw.rounded_rectangle(box, radius=(box[3] - box[1]) // 2, fill=fill)
    width = draw.textlength(text, font=selected_font)
    draw.text((box[0] + (box[2] - box[0] - width) / 2, box[1] + 10), text, font=selected_font, fill="white")


def section_title(draw: ImageDraw.ImageDraw, y: int, text: str, color: tuple[int, int, int], text_size: int) -> int:
    draw.text((38, y), text, font=font(text_size, True), fill=color)
    return y + text_size + 7


def bullet_list(draw: ImageDraw.ImageDraw, y: int, items: list[str], text_size: int, color: tuple[int, int, int], marker_color: tuple[int, int, int]) -> int:
    selected_font = font(text_size)
    for item in items:
        draw.ellipse((42, y + 6, 50, y + 14), fill=marker_color)
        y = draw_wrapped(draw, (61, y), item, selected_font, color, W - 103, line_gap=2) + 3
    return y


def render_guide(screen: dict, scene: dict, guide: dict, body_size: int) -> tuple[Image.Image, int]:
    image = preview(screen["scene_index"], dim=100).convert("RGBA")
    draw = ImageDraw.Draw(image)
    resolved = screen["resolved_text"]
    draw.rounded_rectangle((24, 18, 324, 54), radius=18, fill=(12, 10, 10, 210))
    draw.text((40, 27), resolved["screen_label"], font=font(14, True), fill="white")
    draw.text((38, 70), resolved["scene_counter"], font=font(18, True), fill=(255, 237, 210))
    draw.text((38, 106), resolved["title"], font=font(29, True), fill="white")
    draw.rounded_rectangle((0, 154, W, H + 35), radius=30, fill=CREAM)

    y = 178
    heading_size = max(12, body_size - 1)
    y = section_title(draw, y, resolved["guide_section_title"], RED, heading_size)
    y = draw_wrapped(draw, (38, y), resolved["instruction"], font(body_size), INK, W - 76, line_gap=3) + 8
    y = section_title(draw, y, resolved["film_section_title"], GREEN, heading_size)
    y = bullet_list(draw, y, resolved["film_list"], body_size, INK, GREEN) + 4
    y = section_title(draw, y, resolved["avoid_section_title"], RED, heading_size)
    y = bullet_list(draw, y, resolved["avoid_list"], body_size, MUTED, RED) + 4
    y = section_title(draw, y, resolved["action_section_title"], (126, 76, 45), heading_size)
    y = draw_wrapped(draw, (38, y), resolved["required_action"], font(body_size), INK, W - 76, line_gap=3) + 7
    y = section_title(draw, y, resolved["speech_section_title"], GREEN, heading_size)
    y = draw_wrapped(draw, (38, y), resolved["speech_note"], font(max(12, body_size - 1)), MUTED, W - 76, line_gap=2) + 7
    y = section_title(draw, y, resolved["example_section_title"], (126, 76, 45), heading_size)
    example_top = y
    example_lines = wrap(draw, resolved["optional_example"], font(max(12, body_size - 1)), W - 112)
    example_height = len(example_lines) * (max(12, body_size - 1) + 3) + 18
    draw.rounded_rectangle((34, example_top, W - 34, example_top + example_height), radius=14, fill=(239, 224, 191), outline=(215, 187, 132), width=2)
    y = draw_wrapped(draw, (52, example_top + 8), resolved["optional_example"], font(max(12, body_size - 1)), INK, W - 104, line_gap=3) + 8

    button_top = 1200
    draw.rounded_rectangle((34, button_top, W - 34, 1260), radius=22, fill=RED)
    label_font = font(21, True)
    width = draw.textlength(resolved["primary_action"], font=label_font)
    draw.text(((W - width) / 2, button_top + 17), resolved["primary_action"], font=label_font, fill="white")
    return image.convert("RGB"), y


def guide_screen(screen: dict, scene: dict, guide: dict) -> Image.Image:
    for body_size in (20, 19, 18, 17, 16, 15):
        image, final_y = render_guide(screen, scene, guide, body_size)
        if final_y <= 1184:
            return image
    raise ValueError(f"Guide copy does not fit without truncation: {screen['screen_id']} y={final_y}")


def recording_screen(screen: dict) -> Image.Image:
    image = preview(screen["scene_index"], dim=30).convert("RGBA")
    draw = ImageDraw.Draw(image)
    resolved = screen["resolved_text"]
    draw.rounded_rectangle((24, 18, 386, 56), radius=19, fill=(9, 8, 8, 210))
    draw.text((40, 28), resolved["screen_label"], font=font(14, True), fill="white")
    draw.rounded_rectangle((24, 72, W - 24, 119), radius=20, fill=(9, 8, 8, 185))
    draw.text((43, 85), resolved["scene_counter"], font=font(18, True), fill=(255, 239, 217))
    pill(draw, (W - 144, 137, W - 28, 187), resolved["recording_status"], (174, 28, 25, 245), font(20, True))

    draw.rounded_rectangle((42, 455, W - 42, 576), radius=24, fill=(8, 8, 8, 200), outline=(236, 184, 113, 150), width=2)
    center_wrapped(draw, 490, resolved["instruction"], font(25, True), "white", W - 112, line_gap=5)
    draw.rounded_rectangle((74, 626, W - 74, 688), radius=20, fill=(8, 8, 8, 190))
    center_wrapped(draw, 645, resolved["timer_initial"], font(23, True), "white", W - 170)

    y = 925
    for text in [resolved["audio_status"], resolved["orientation_status"], resolved["auto_stop_status"]]:
        draw.rounded_rectangle((54, y, W - 54, y + 58), radius=18, fill=(10, 9, 9, 180))
        draw.ellipse((75, y + 23, 87, y + 35), fill=(90, 190, 132))
        draw.text((104, y + 17), text, font=font(17, True), fill="white")
        y += 72
    draw.rounded_rectangle((54, 1163, W - 54, 1176), radius=7, fill=(255, 255, 255, 90))
    draw.rounded_rectangle((54, 1163, 356, 1176), radius=7, fill=RED)
    return image.convert("RGB")


def review_screen(screen: dict) -> Image.Image:
    image = preview(screen["scene_index"], dim=15).convert("RGBA")
    draw = ImageDraw.Draw(image)
    resolved = screen["resolved_text"]
    draw.rectangle((0, 0, W, 150), fill=(9, 8, 8, 220))
    draw.text((34, 20), resolved["screen_label"], font=font(14, True), fill=(255, 231, 199))
    draw.text((34, 58), resolved["take_label"], font=font(24, True), fill="white")
    draw.ellipse((38, 110, 50, 122), fill=(92, 190, 134))
    draw.text((66, 102), resolved["audio_status"], font=font(16, True), fill=(238, 231, 222))

    draw.rounded_rectangle((0, 640, W, H + 30), radius=34, fill=(24, 19, 18, 248))
    y = 686
    y = draw_wrapped(draw, (38, y), resolved["review_question"], font(23, True), "white", W - 76, line_gap=5) + 22
    for item in resolved["review_checks"]:
        draw.ellipse((42, y + 3, 62, y + 23), outline=(93, 186, 135), width=3)
        draw.line((47, y + 13, 52, y + 19), fill=(93, 186, 135), width=3)
        draw.line((52, y + 19, 59, y + 7), fill=(93, 186, 135), width=3)
        y = draw_wrapped(draw, (75, y), item, font(18), (239, 232, 223), W - 117, line_gap=3) + 13

    draw.rounded_rectangle((34, 1145, 253, 1227), radius=24, fill=(68, 60, 57), outline=(225, 214, 201), width=2)
    redo_font = font(22, True)
    redo_width = draw.textlength(resolved["redo_action"], font=redo_font)
    draw.text((34 + (219 - redo_width) / 2, 1171), resolved["redo_action"], font=redo_font, fill="white")
    draw.rounded_rectangle((273, 1145, W - 34, 1227), radius=24, fill=RED)
    positive_font = font(20 if screen["scene_index"] < 4 else 18, True)
    positive_width = draw.textlength(resolved["positive_action"], font=positive_font)
    draw.text((273 + (W - 34 - 273 - positive_width) / 2, 1173), resolved["positive_action"], font=positive_font, fill="white")
    return image.convert("RGB")


def generate(flow: dict, guide: dict, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    scenes = guide["scenes"]
    records: list[dict] = []
    expected_states = ["A_GUIDE", "B_RECORDING", "C_REVIEW"] * 4
    if [screen["state"] for screen in flow["screens"]] != expected_states:
        raise ValueError("The flow must expose A/B/C for each of four scenes")
    for screen in flow["screens"]:
        scene = scenes[screen["scene_index"] - 1]
        if screen["state"] == "A_GUIDE":
            image = guide_screen(screen, scene, guide)
        elif screen["state"] == "B_RECORDING":
            image = recording_screen(screen)
        else:
            image = review_screen(screen)
        destination = output_dir / f"{screen['screen_id']}.png"
        image.save(destination, optimize=True)
        records.append({
            "screen_number": screen["ordinal"],
            "scene": screen["scene_index"],
            "state": screen["state"],
            "display_state": screen["display_state"],
            "screen_id": screen["screen_id"],
            "file": destination.name,
            "size": [W, H],
            "sha256": sha256(destination),
            "json_binding": f"config/T5_CAPTURE_FLOW_V1_0_0.json#/screens/{screen['ordinal'] - 1}",
        })

    tile_width, tile_height, padding, header = 270, 480, 22, 86
    board = Image.new("RGB", (3 * tile_width + 4 * padding, 4 * tile_height + 5 * padding + header), (235, 227, 216))
    draw = ImageDraw.Draw(board)
    draw.text((padding, 18), "T5 — 12 ÉCRANS EN FRANÇAIS SIMPLE", font=font(27, True), fill=(42, 32, 28))
    draw.text((padding, 56), "4 scènes × A Guide · B Enregistrement · C Vérification", font=font(17), fill=(94, 76, 65))
    for index, record in enumerate(records):
        row, column = divmod(index, 3)
        x = padding + column * (tile_width + padding)
        y = header + padding + row * (tile_height + padding)
        screen_image = Image.open(output_dir / record["file"]).resize((tile_width, tile_height), Image.Resampling.LANCZOS)
        board.paste(screen_image, (x, y))
    board_path = output_dir / "T5_PLANCHE_12_ECRANS.png"
    board.save(board_path, optimize=True)
    manifest = {
        "schema_version": "1.0.0",
        "template_id": "RESTAURATION-T5",
        "status": "owner_approved_simple_french_proof",
        "copy_revision": guide["copy_revision"],
        "sources": {
            "questions": "form/questions_T5.json",
            "guide": "capture-guide/consignes_T5.json",
            "capture_flow": "config/T5_CAPTURE_FLOW_V1_0_0.json",
        },
        "stable_screen_count": 12,
        "states": ["A_GUIDE", "B_RECORDING", "C_REVIEW"],
        "display_states": ["A / GUIDE", "B / ENREGISTREMENT", "C / VÉRIFICATION"],
        "screens": records,
        "board": board_path.name,
        "board_size": list(board.size),
        "board_sha256": sha256(board_path),
        "external_media_used": False,
        "text_truncation_used": False,
        "font_files": ["assets/fonts/DejaVuSans.ttf", "assets/fonts/DejaVuSans-Bold.ttf"],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--flow", type=Path, default=ROOT / "config/T5_CAPTURE_FLOW_V1_0_0.json")
    parser.add_argument("--guide", type=Path, default=ROOT / "capture-guide/consignes_T5.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "ui-screens")
    args = parser.parse_args()
    flow = json.loads(args.flow.read_text(encoding="utf-8"))
    guide = json.loads(args.guide.read_text(encoding="utf-8"))
    manifest = generate(flow, guide, args.output_dir)
    print(f"T5_UI_12_SCREENS_OK {manifest['board']} {manifest['board_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
