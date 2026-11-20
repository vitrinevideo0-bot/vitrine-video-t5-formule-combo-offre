from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_simulation_is_reproducible_and_embeds_six_plus_twelve(tmp_path: Path) -> None:
    generated = tmp_path / "simulation.html"
    subprocess.run(
        ["python3", "tools/build_t5_simulation.py", "--output", str(generated)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    approved = ROOT / "simulation/T5_12_ECRANS_EXECUTABLE.html"
    assert generated.read_bytes() == approved.read_bytes()
    text = approved.read_text(encoding="utf-8")
    q = re.search(r'<script type="application/json" id="questions">(.*?)</script>', text, re.S)
    f = re.search(r'<script type="application/json" id="flow">(.*?)</script>', text, re.S)
    assert q and f
    questions = json.loads(q.group(1))
    assert len(questions["fields"]) == 6
    assert [field["label"] for field in questions["fields"]] == [
        "Nom du restaurant", "Nom de la formule", "Ce qu'il y a dans la formule",
        "Prix", "Numéro WhatsApp", "Lieu de retrait",
    ]
    assert len(json.loads(f.group(1))["screens"]) == 12
    assert "esc(f.label)" in text
    assert 'class="field-question"' in text
    assert 'class="field-example"' in text
    for copy in [
        "VOICI NOTRE FORMULE !",
        "REGARDE TOUT CE QU'IL Y A DEDANS !",
        "VOICI LE PRIX DE LA FORMULE !",
        "ENVIE DE COMMANDER ?",
        "EXEMPLE DE PHRASE (FACULTATIF)",
    ]:
        assert copy in text
    assert "REFAIRESCÈNE" not in text
    assert "REFAIREVOIR" not in text
    assert "T5_RENDER_CONFIRMATION" in text
    assert "Ton montage peut être créé" in text
    assert "https://" not in text and "http://" not in text


@pytest.mark.skipif(not shutil.which("node"), reason="Node.js required")
def test_simulation_javascript_syntax(tmp_path: Path) -> None:
    text = (ROOT / "simulation/T5_12_ECRANS_EXECUTABLE.html").read_text(encoding="utf-8")
    scripts = re.findall(r"<script(?: [^>]*)?>(.*?)</script>", text, re.S)
    script = tmp_path / "simulation.js"
    script.write_text(scripts[-1], encoding="utf-8")
    subprocess.run(["node", "--check", str(script)], check=True, capture_output=True, text=True)
