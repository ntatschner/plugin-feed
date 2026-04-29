# tools/build-catalog/build_catalog.py
"""Walks plugins/**/*.zip, computes sha256, reads plugin.json, emits catalog.json."""
from __future__ import annotations
import datetime
import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path

BASE_URL = os.environ.get("PAGES_BASE_URL", "https://ntatschner.github.io/plugin-feed")
FEED_ID = os.environ.get("FEED_ID", "ittoolkit-public")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def manifest_from_zip(path: Path):
    try:
        with zipfile.ZipFile(path) as z:
            with z.open("plugin.json") as f:
                return json.load(f)
    except (KeyError, zipfile.BadZipFile, json.JSONDecodeError):
        return None


def risk_level(perms):
    danger = {"ProcessExec", "FileSystemUser", "Network"}
    perms_set = set(perms or [])
    if danger.issubset(perms_set):
        return "high"
    if "ProcessExec" in perms_set or "FileSystemUser" in perms_set:
        return "medium"
    return "low"


def build(repo_root: Path):
    plugins_dir = repo_root / "plugins"
    entries = []
    if plugins_dir.exists():
        for zip_path in sorted(plugins_dir.rglob("*.zip")):
            manifest = manifest_from_zip(zip_path)
            if manifest is None:
                continue
            rel = zip_path.relative_to(repo_root).as_posix()
            perms = manifest.get("requestedPermissions", [])
            entries.append({
                "id": manifest["id"],
                "name": manifest.get("name", manifest["id"]),
                "author": manifest.get("author", ""),
                "description": manifest.get("description", ""),
                "version": manifest["version"],
                "category": manifest.get("category", "Other"),
                "license": manifest.get("license"),
                "iconKey": manifest.get("iconKey", "package"),
                "requestedPermissions": perms,
                "downloadUrl": f"{BASE_URL}/{rel}",
                "sha256": sha256_of(zip_path),
                "sizeBytes": zip_path.stat().st_size,
                "verified": True,
                "permissionRiskLevel": risk_level(perms),
                "minHostVersion": manifest.get("minHostVersion", "2.0"),
                "featured": manifest.get("featured", False),
                "lastUpdated": datetime.datetime.utcfromtimestamp(zip_path.stat().st_mtime).isoformat() + "Z",
            })
    entries.sort(key=lambda e: (e["id"], e["version"]))
    return {
        "schemaVersion": 2,
        "feedId": FEED_ID,
        "generatedAt": datetime.datetime.utcnow().isoformat() + "Z",
        "entries": entries,
    }


if __name__ == "__main__":
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    catalog = build(root)
    out = root / "catalog.json"
    out.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    print(f"Wrote {out} with {len(catalog['entries'])} entries.")
