# tools/build-catalog/build_catalog.py
"""Walks plugins/**/*.zip, computes sha256, reads plugin.json, emits catalog.json + index.html."""
from __future__ import annotations
import datetime
import hashlib
import html
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


def _normalize_permissions(value):
    """Coerce a manifest's requestedPermissions field to a clean list[str].

    Real-world manifests have shipped degenerate shapes that the host's
    tolerant JSON converter handles, but the catalog should publish only
    the canonical array form so naive consumers (jq, third-party tools,
    older host versions without the converter) don't choke. Accepts:

    * a list of strings (canonical) — non-string elements and empty
      strings are dropped
    * None / missing → []
    * the literal string "None" (any case) → [] (legacy "no permissions")
    * an empty string → []
    * any other non-empty string → single-element list
    """
    if value is None:
        return []
    if isinstance(value, str):
        if value == "" or value.lower() == "none":
            return []
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item != ""]
    return []


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
            perms = _normalize_permissions(manifest.get("requestedPermissions"))
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


def _fmt_size(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} MB"
    if n >= 1_024:
        return f"{n / 1_024:.1f} KB"
    return f"{n} B"


def render_index_html(catalog: dict) -> str:
    rows = []
    for e in catalog["entries"]:
        sha = (e.get("sha256") or "")[:12]
        risk = e.get("permissionRiskLevel", "low")
        risk_class = {
            "high": "risk-high",
            "medium": "risk-med",
            "low": "risk-low",
        }.get(risk, "risk-low")
        perms = ", ".join(e.get("requestedPermissions", [])) or "—"
        rows.append(f"""
        <tr>
          <td><strong>{html.escape(e.get("name", ""))}</strong>
              <div class="muted">{html.escape(e.get("id", ""))}</div></td>
          <td>{html.escape(e.get("version", ""))}</td>
          <td>{html.escape(e.get("author", ""))}</td>
          <td>{html.escape(e.get("category", ""))}</td>
          <td><span class="badge {risk_class}">{html.escape(risk)}</span></td>
          <td class="muted">{html.escape(perms)}</td>
          <td><code>{html.escape(sha)}…</code></td>
          <td>{_fmt_size(int(e.get("sizeBytes", 0) or 0))}</td>
          <td><a href="{html.escape(e.get("downloadUrl", ""))}">zip</a></td>
        </tr>""")
    rows_html = "".join(rows) if rows else "<tr><td colspan='9' class='muted'>No plugins yet.</td></tr>"

    feed_id = html.escape(catalog.get("feedId") or "")
    generated_at = html.escape(catalog.get("generatedAt") or "")
    count = len(catalog["entries"])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>ITToolkit Plugin Feed</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  :root {{
    --bg: #0e1116; --bg2: #161b22; --bg3: #21262d;
    --fg: #e6edf3; --fg2: #8b949e; --accent: #58a6ff; --accent2: #1f6feb;
    --green: #3fb950; --yellow: #d29922; --red: #f85149;
    --border: #30363d;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font: 14px/1.55 -apple-system, "Segoe UI", system-ui, sans-serif;
         background: var(--bg); color: var(--fg); }}
  header {{ padding: 32px 48px 16px; border-bottom: 1px solid var(--border); background: var(--bg2); }}
  h1 {{ margin: 0 0 6px; font-size: 24px; }}
  .tagline {{ color: var(--fg2); margin: 0 0 12px; }}
  .meta {{ color: var(--fg2); font-size: 12px; }}
  .meta code {{ color: var(--accent); }}
  main {{ padding: 24px 48px 64px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
  th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--border); vertical-align: top; }}
  th {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--fg2); font-weight: 500; }}
  tr:hover td {{ background: var(--bg2); }}
  .muted {{ color: var(--fg2); font-size: 12px; }}
  code {{ background: var(--bg3); padding: 2px 6px; border-radius: 4px; font-family: ui-monospace, "Cascadia Code", monospace; font-size: 12px; }}
  a {{ color: var(--accent); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; }}
  .risk-low  {{ background: rgba(63,185,80,0.15);  color: var(--green); }}
  .risk-med  {{ background: rgba(210,153,34,0.15); color: var(--yellow); }}
  .risk-high {{ background: rgba(248,81,73,0.15);  color: var(--red); }}
  .links a {{ margin-right: 16px; }}
  footer {{ padding: 16px 48px; color: var(--fg2); font-size: 12px; border-top: 1px solid var(--border); }}
</style>
</head><body>
<header>
  <h1>ITToolkit Plugin Feed</h1>
  <p class="tagline">Public catalog of plugins for the ITToolkit Windows admin app.</p>
  <p class="meta">
    <span class="links">
      <a href="catalog.json">catalog.json</a>
      <a href="https://github.com/ntatschner/plugin-feed">repo</a>
      <a href="https://github.com/ntatschner/plugin-feed/blob/main/CONTRIBUTING.md">submit a plugin</a>
    </span>
  </p>
  <p class="meta">Feed <code>{feed_id}</code> · {count} plugin{'s' if count != 1 else ''} · generated <code>{generated_at}</code></p>
</header>
<main>
  <table>
    <thead><tr>
      <th>Plugin</th><th>Version</th><th>Author</th><th>Category</th>
      <th>Risk</th><th>Permissions</th><th>SHA-256</th><th>Size</th><th>Download</th>
    </tr></thead>
    <tbody>{rows_html}
    </tbody>
  </table>
</main>
<footer>
  Configure your ITToolkit host's <code>Plugins.FeedUrl</code> to <code>https://ntatschner.github.io/plugin-feed/catalog.json</code>.
</footer>
</body></html>
"""


if __name__ == "__main__":
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    catalog = build(root)
    catalog_out = root / "catalog.json"
    catalog_out.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    index_out = root / "index.html"
    index_out.write_text(render_index_html(catalog), encoding="utf-8")
    print(f"Wrote {catalog_out} with {len(catalog['entries'])} entries.")
    print(f"Wrote {index_out}.")
