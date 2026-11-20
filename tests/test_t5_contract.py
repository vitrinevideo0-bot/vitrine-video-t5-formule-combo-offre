from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_six_owner_approved_questions_are_required_and_bound() -> None:
    questions = load("form/questions_T5.json")
    fields = questions["fields"]
    assert questions["status"] == "owner_approved"
    assert questions["copy_revision"] == "T5_6_QUESTIONS_SIMPLIFIEES_2026-11-18"
    assert [field["id"] for field in fields] == ["nom", "offre", "contenu", "prix", "whatsapp", "quartier"]
    assert [field["label"] for field in fields] == [
        "Nom du restaurant", "Nom de la formule", "Ce qu'il y a dans la formule",
        "Prix", "Numéro WhatsApp", "Lieu de retrait",
    ]
    assert [field["question"] for field in fields] == [
        "Comment s'appelle ton restaurant ?",
        "Comment tu appelles cette formule ?",
        "Dans cette formule, tu mets quoi ? Dis-nous aussi combien il y a de chaque chose.",
        "Tu vends cette formule à combien ?",
        "Quel est ton numéro WhatsApp pour que les clients puissent commander ?",
        "Les clients peuvent venir chercher leur commande où ?",
    ]
    assert [field["example"] for field in fields] == [
        "Burger Atelier Kandi",
        "Formule Double Burger",
        "1 double burger\n1 portion de frites\n1 verre de cola",
        "5 000 FCFA",
        "+229 01 97 00 00 00",
        "Kandi, près du marché central",
    ]
    assert fields[2]["example_items"] == [
        "1 double burger", "1 portion de frites", "1 verre de cola"
    ]
    assert all(field["required"] for field in fields)
    assert [field["json_target"] for field in fields] == [
        "merchant_payload.nom", "merchant_payload.offre", "merchant_payload.contenu",
        "merchant_payload.prix", "merchant_payload.whatsapp", "merchant_payload.quartier",
    ]
    assert [field["used_in_scenes"] for field in fields] == [
        ["S1", "S4"], ["S1", "S3"], ["S1", "S2", "S3"], ["S3"], ["S4"], ["S4"]
    ]
    assert questions["approval"]["selected_option_id"] == "apply_exact_user_copy"


def test_owner_copy_and_continuity_rule_are_exact() -> None:
    guide = load("capture-guide/consignes_T5.json")
    assert guide["copy_revision"] == "T5_12_ECRANS_CORRIGES_2026-11-18"
    assert guide["owner_rule"] == (
        "Une seule formule par publicité. Le même plat, la même boisson et les mêmes "
        "accompagnements restent présents dans les quatre scènes."
    )
    assert [scene["scene_name"] for scene in guide["scenes"]] == [
        "LA FORMULE", "CE QU'IL Y A DANS LA FORMULE", "LE PRIX", "COMMANDER"
    ]
    assert [scene["seconds"] for scene in guide["scenes"]] == [6, 8, 7, 9]
    assert [scene["guide"]["title"] for scene in guide["scenes"]] == [
        "VOICI NOTRE FORMULE !", "REGARDE TOUT CE QU'IL Y A DEDANS !",
        "VOICI LE PRIX DE LA FORMULE !", "ENVIE DE COMMANDER ?",
    ]
    assert [scene["recording"]["instruction"] for scene in guide["scenes"]] == [
        "MONTRE TOUTE TA FORMULE.",
        "MONTRE LE PLAT, LA BOISSON ET L'ACCOMPAGNEMENT.",
        "GARDE TOUTE LA FORMULE DANS LA VIDÉO.",
        "MONTRE TA FORMULE BIEN PRÉSENTÉE.",
    ]
    assert guide["button_spacing_interpretation"]["implemented_as_two_buttons"] is True


def test_exact_twelve_screen_flow_and_runtime() -> None:
    flow = load("config/T5_CAPTURE_FLOW_V1_0_0.json")
    screens = flow["screens"]
    assert len(screens) == 12
    assert flow["counts"] == {"merchant_questions": 6, "scenes": 4, "states_per_scene": 3, "stable_capture_screens": 12}
    assert flow["scene_durations_ms"] == [6000, 8000, 7000, 9000]
    assert flow["continuity_rules"]["one_offer_per_ad"] is True
    assert flow["continuity_rules"]["same_dish_drink_and_sides_across_all_scenes"] is True
    expected_states = ["A_GUIDE", "B_RECORDING", "C_REVIEW"] * 4
    assert [screen["state"] for screen in screens] == expected_states
    assert [screen["ordinal"] for screen in screens] == list(range(1, 13))
    expected_data_used = (
        [["merchant_payload.nom", "merchant_payload.offre", "merchant_payload.contenu"]] * 3
        + [["merchant_payload.contenu"]] * 3
        + [["merchant_payload.offre", "merchant_payload.contenu", "merchant_payload.prix"]] * 3
        + [["merchant_payload.nom", "merchant_payload.whatsapp", "merchant_payload.quartier"]] * 3
    )
    assert [screen["data_used"] for screen in screens] == expected_data_used
    expected_labels = []
    for scene in range(4):
        expected_labels += [
            f"ÉCRAN {scene * 3 + 1:02d} — A / GUIDE",
            f"ÉCRAN {scene * 3 + 2:02d} — B / ENREGISTREMENT",
            f"ÉCRAN {scene * 3 + 3:02d} — C / VÉRIFICATION",
        ]
    assert [screen["resolved_text"]["screen_label"] for screen in screens] == expected_labels
    recordings = screens[1::3]
    assert [screen["capture"]["duration_ms"] for screen in recordings] == [6000, 8000, 7000, 9000]
    assert all(screen["capture"]["auto_stop"] and not screen["capture"]["manual_stop"] for screen in recordings)
    assert all(screen["resolved_text"]["audio_status"] == "Micro activé." for screen in recordings)
    reviews = screens[2::3]
    assert all(screen["resolved_text"]["redo_action"] == "REFAIRE" for screen in reviews)
    assert [screen["resolved_text"]["positive_action"] for screen in reviews] == [
        "SCÈNE SUIVANTE", "SCÈNE SUIVANTE", "SCÈNE SUIVANTE", "VOIR MON MONTAGE"
    ]
    assert reviews[-1]["actions"][1]["next_screen_id"] == "T5_RENDER_CONFIRMATION"


def test_flow_source_hashes_and_approval_are_current() -> None:
    flow = load("config/T5_CAPTURE_FLOW_V1_0_0.json")
    for source in ("guide", "questions"):
        record = flow["sources"][source]
        assert sha256(ROOT / record["path"]) == record["sha256"]
    approval = load("approvals/APPROBATION_QUESTIONS_ET_12_ECRANS_T5_2026-11-18.json")
    assert approval["status"] == "owner_approved_for_implementation"
    assert approval["publication_authorized"] is True
    assert sha256(ROOT / approval["screen_copy"]["source"]) == approval["screen_copy"]["sha256"]
    assert sha256(ROOT / approval["questions"]["source"]) == approval["questions"]["sha256"]


def test_cloudflare_form_displays_label_question_and_examples_separately() -> None:
    app = (ROOT / "cloudflare/public/app.js").read_text(encoding="utf-8")
    styles = (ROOT / "cloudflare/public/styles.css").read_text(encoding="utf-8")
    assert "escapeHtml(field.label)" in app
    assert 'class="field-question"' in app and "escapeHtml(field.question)" in app
    assert 'class="field-example"' in app and "field.example_items" in app
    assert "<textarea ${commonAttributes}" in app
    assert ".field-question{" in styles
    assert ".field-example{" in styles


def test_twelve_png_proofs_are_hash_locked_and_not_truncated() -> None:
    manifest = load("ui-screens/manifest.json")
    assert manifest["stable_screen_count"] == 12
    assert manifest["text_truncation_used"] is False
    assert manifest["external_media_used"] is False
    assert len(manifest["screens"]) == 12
    for record in manifest["screens"]:
        path = ROOT / "ui-screens" / record["file"]
        assert path.is_file()
        assert sha256(path) == record["sha256"]
        with Image.open(path) as image:
            assert image.size == (720, 1280)
    board = ROOT / "ui-screens" / manifest["board"]
    assert sha256(board) == manifest["board_sha256"]
