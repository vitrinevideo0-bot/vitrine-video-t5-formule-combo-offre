#!/usr/bin/env python3
"""Télécharge les quatre prises Pexels de validation sans les versionner."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def valid(path: Path, expected_bytes: int, expected_sha256: str) -> bool:
    return path.is_file() and path.stat().st_size == expected_bytes and sha256(path) == expected_sha256


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "rushes/manifest.json")
    parser.add_argument("--cache", type=Path, default=ROOT / "rushes/cache-v4-aida")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    args.cache.mkdir(parents=True, exist_ok=True)
    fetched: dict[str, dict[str, object]] = {}
    for source in manifest["sources"]:
        destination = args.cache / source["cache_filename"]
        if not valid(destination, source["expected_bytes"], source["sha256"]):
            destination.unlink(missing_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=args.cache)
            os.close(descriptor)
            Path(temporary_name).unlink(missing_ok=True)
            try:
                request = urllib.request.Request(source["download_url"], headers={"User-Agent": "T5-GitHub-Renderer/3.0"})
                with urllib.request.urlopen(request, timeout=120) as response, open(temporary_name, "wb") as stream:
                    while block := response.read(1 << 20):
                        stream.write(block)
                temporary = Path(temporary_name)
                if not valid(temporary, source["expected_bytes"], source["sha256"]):
                    raise SystemExit(f"Integrity failure for {source['slot']}")
                temporary.replace(destination)
            finally:
                Path(temporary_name).unlink(missing_ok=True)
        fetched[source["slot"]] = {
            "file": str(destination),
            "bytes": destination.stat().st_size,
            "sha256": sha256(destination),
        }
    print(json.dumps({"status": "READY", "raw_media_publish": False, "captures": fetched}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
