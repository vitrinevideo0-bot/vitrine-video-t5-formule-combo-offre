#!/usr/bin/env python3
"""Fetch and hash-lock the single licensed T5 demo rush."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "rushes/manifest.json")
    parser.add_argument("--cache", type=Path, default=ROOT / "rushes/cache")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    source = manifest["source"]
    args.cache.mkdir(parents=True, exist_ok=True)
    destination = args.cache / source["cache_filename"]
    if not destination.is_file() or destination.stat().st_size != source["expected_bytes"] or sha256(destination) != source["sha256"]:
        temporary = destination.with_suffix(destination.suffix + ".part")
        request = urllib.request.Request(source["download_url"], headers={"User-Agent": "T5-formule-demo/1.0"})
        with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as output:
            while block := response.read(1 << 20):
                output.write(block)
        temporary.replace(destination)
    actual = sha256(destination)
    if destination.stat().st_size != source["expected_bytes"] or actual != source["sha256"]:
        raise SystemExit("T5 rush size or SHA-256 mismatch")
    print(f"T5_RUSH_VERIFIED {destination} {destination.stat().st_size} {actual}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
