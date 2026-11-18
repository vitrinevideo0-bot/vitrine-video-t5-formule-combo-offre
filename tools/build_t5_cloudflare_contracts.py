#!/usr/bin/env python3
"""Génère les contrats TypeScript Cloudflare depuis les JSON canoniques T5."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {
    ROOT / "cloudflare/src/form_contract.ts": ("FORM_CONTRACT", ROOT / "form/questions_T5.json"),
    ROOT / "cloudflare/src/capture_flow_contract.ts": ("CAPTURE_FLOW_CONTRACT", ROOT / "config/T5_CAPTURE_FLOW_V1_0_0.json"),
    ROOT / "cloudflare/src/audio_mix_contract.ts": ("AUDIO_MIX_CONTRACT", ROOT / "config/T5_AUDIO_MIX_V1_0_0.json"),
    ROOT / "cloudflare/src/music_pack_contract.ts": ("MUSIC_PACK_CONTRACT", ROOT / "config/T5_MUSIC_PACK_V1_0_0.json"),
}
VOICE_MANIFEST = ROOT / "audio/voice/t5-voice-v1/manifest.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rendered(name: str, source: Path) -> str:
    value = json.loads(source.read_text(encoding="utf-8"))
    payload = json.dumps(value, ensure_ascii=False, indent=2)
    content = f"// Generated from {source.relative_to(ROOT)}; do not edit.\nexport const {name} = {payload} as const;\n"
    if name == "AUDIO_MIX_CONTRACT":
        content += f'export const AUDIO_MIX_CONTRACT_SHA256 = "{sha256(source)}" as const;\n'
        content += f'export const T5_VOICE_MANIFEST_SHA256 = "{sha256(VOICE_MANIFEST)}" as const;\n'
    if name == "MUSIC_PACK_CONTRACT":
        content += f'export const MUSIC_PACK_CONTRACT_SHA256 = "{sha256(source)}" as const;\n'
    return content


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    changed: list[str] = []
    for destination, (name, source) in TARGETS.items():
        content = rendered(name, source)
        if args.check:
            if not destination.is_file() or destination.read_text(encoding="utf-8") != content:
                changed.append(str(destination.relative_to(ROOT)))
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")
            print(destination.relative_to(ROOT))
    if changed:
        raise SystemExit("Cloudflare contracts are stale: " + ", ".join(changed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
