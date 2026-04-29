# tools/validate-submission/validate.py
"""Runs on PRs. Validates a single zip submission. Exits non-zero on failure.

Outputs lines like:
  RISK_LEVEL=low|medium|high
to GITHUB_OUTPUT so the workflow can set labels accordingly.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import sys
import zipfile
from pathlib import Path

ID_RE = re.compile(r"^[a-z0-9][a-z0-9.\-]*[a-z0-9]$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(-[A-Za-z0-9.\-]+)?$")


def fail(msg):
    print(f"::error::{msg}")
    sys.exit(1)


def ok(msg):
    print(f"::notice::{msg}")


def emit_output(key, value):
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")
    # Always echo so local runs / logs show the value.
    print(f"{key}={value}")


def risk_level(perms):
    danger = {"ProcessExec", "FileSystemUser", "Network"}
    perms_set = set(perms or [])
    if danger.issubset(perms_set):
        return "high"
    if "ProcessExec" in perms_set or "FileSystemUser" in perms_set:
        return "medium"
    return "low"


def main(zip_path: Path):
    if not zip_path.exists():
        fail(f"zip not found: {zip_path}")
    if zip_path.suffix != ".zip":
        fail("submission must be a .zip")

    # zip_path = .../plugins/{id}/{version}/{file}.zip
    # parents[0]=version, parents[1]=id, parents[2]=plugins, parents[3]=repo root.
    parts = zip_path.relative_to(zip_path.parents[3]).parts
    if len(parts) != 4 or parts[0] != "plugins":
        fail(f"path layout must be plugins/{{id}}/{{version}}/{{id}}.zip - got {parts}")
    path_id, path_ver = parts[1], parts[2]

    with zipfile.ZipFile(zip_path) as z:
        names = set(z.namelist())
        if "plugin.json" not in names:
            fail("zip missing plugin.json at root")
        if not any(n.upper() == "LICENSE" or n.upper().startswith("LICENSE.") for n in names):
            fail("zip missing LICENSE file")
        manifest = json.loads(z.read("plugin.json"))

    if manifest.get("id") != path_id:
        fail(f"manifest id '{manifest.get('id')}' != path id '{path_id}'")
    if manifest.get("version") != path_ver:
        fail(f"manifest version '{manifest.get('version')}' != path version '{path_ver}'")
    if not ID_RE.match(manifest.get("id", "")):
        fail(f"invalid id format: {manifest.get('id')}")
    if not VERSION_RE.match(manifest.get("version", "")):
        fail(f"invalid semver: {manifest.get('version')}")

    perms = manifest.get("requestedPermissions", [])
    level = risk_level(perms)
    emit_output("RISK_LEVEL", level)
    if level == "high":
        print("::warning::high-risk permission combo detected; needs-human-review")

    sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    ok(f"sha256={sha}")
    ok(f"risk={level}")
    ok("validation passed")


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
