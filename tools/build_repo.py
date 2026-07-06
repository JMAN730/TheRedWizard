#!/usr/bin/env python3
"""PROTOTYPE (wayfinder #15) — build the Kodi repository datadir tree.

Reads channels.json at the repo root and emits, per channel:

    out/<channel>/addons.xml          <addons> root wrapping each addon.xml verbatim
    out/<channel>/addons.xml.md5      bare lowercase hex md5 of addons.xml bytes
    out/<channel>/<id>/<id>-<version>.zip   single root folder <id>/
    out/<channel>/<id>/<asset files>  every path from the addon's <assets> block

Stdlib only. Run from anywhere: python3 tools/build_repo.py [--out DIR]

Format facts verified against Kodi source — see
docs/research/kodi-repo-artifact-format.md.
"""

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXCLUDE_NAMES = {".git", ".github", ".gitignore", ".gitattributes", ".DS_Store",
                 "__pycache__", "Thumbs.db", ".idea", ".vscode"}


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def load_manifest():
    manifest_path = REPO_ROOT / "channels.json"
    if not manifest_path.is_file():
        fail("channels.json not found at repo root")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Rule: every addon dir with an addon.xml must be consciously mapped.
    on_disk = {p.parent.name for p in REPO_ROOT.glob("*/addon.xml")}
    unmapped = on_disk - manifest.keys()
    if unmapped:
        fail(f"addon dirs missing from channels.json: {sorted(unmapped)}")
    # Rule: no dangling manifest entries.
    dangling = {a for a in manifest if not (REPO_ROOT / a / "addon.xml").is_file()}
    if dangling:
        fail(f"channels.json entries without an addon dir: {sorted(dangling)}")
    return manifest


def parse_addon(addon_dir):
    tree = ET.parse(addon_dir / "addon.xml")
    root = tree.getroot()
    addon_id, version = root.get("id"), root.get("version")
    if root.tag != "addon" or not addon_id or not version:
        fail(f"{addon_dir.name}/addon.xml lacks <addon id= version=>")
    if addon_id != addon_dir.name:
        fail(f"folder {addon_dir.name} != addon id {addon_id}")
    assets = []
    for assets_el in root.iter("assets"):
        for el in assets_el:
            if el.text and el.text.strip():
                assets.append(el.text.strip())
    return addon_id, version, assets


def zip_addon(addon_dir, zip_path):
    """Zip with exactly one root folder <id>/, excluding VCS/hidden junk."""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(addon_dir.rglob("*")):
            if any(part in EXCLUDE_NAMES for part in path.parts):
                continue
            if path.is_file():
                # arcname starts with the addon id folder — the single root entry
                zf.write(path, Path(addon_dir.name) / path.relative_to(addon_dir))


def addon_xml_fragment(addon_dir):
    """The addon.xml body verbatim, minus the XML declaration."""
    text = (addon_dir / "addon.xml").read_text(encoding="utf-8")
    if text.lstrip().startswith("<?xml"):
        text = text.split("?>", 1)[1]
    return text.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO_ROOT / "out"))
    args = ap.parse_args()
    out_root = Path(args.out)
    if out_root.exists():
        shutil.rmtree(out_root)

    manifest = load_manifest()
    channels = {}  # channel -> list of (id, fragment)
    warnings = []

    for addon_id in sorted(manifest):
        addon_dir = REPO_ROOT / addon_id
        parsed_id, version, assets = parse_addon(addon_dir)
        if not manifest[addon_id]:
            print(f"  skip  {addon_id} (mapped to no channels)")
            continue
        if not assets:
            warnings.append(f"{addon_id} has no <assets> block — no art will "
                            f"show in Kodi's addon browser")
        fragment = addon_xml_fragment(addon_dir)
        for channel in manifest[addon_id]:
            chan_dir = out_root / channel / addon_id
            chan_dir.mkdir(parents=True, exist_ok=True)
            zip_addon(addon_dir, chan_dir / f"{addon_id}-{version}.zip")
            for asset in assets:
                src = addon_dir / asset
                if not src.is_file():
                    warnings.append(f"{addon_id}: declared asset missing: {asset}")
                    continue
                dst = chan_dir / asset
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            channels.setdefault(channel, []).append((addon_id, fragment))
        print(f"  build {addon_id} {version} -> {', '.join(manifest[addon_id])}")

    for channel, entries in sorted(channels.items()):
        body = "\n\n".join(frag for _, frag in entries)
        xml_bytes = f'<?xml version="1.0" encoding="UTF-8"?>\n<addons>\n{body}\n</addons>\n'.encode("utf-8")
        (out_root / channel / "addons.xml").write_bytes(xml_bytes)
        md5 = hashlib.md5(xml_bytes).hexdigest()
        (out_root / channel / "addons.xml.md5").write_text(md5, encoding="utf-8")
        ET.fromstring(xml_bytes)  # self-check: generated file must parse
        print(f"  index {channel}: {len(entries)} addons, md5 {md5}")

    for w in warnings:
        print(f"  WARN  {w}")
    print(f"done -> {out_root}")


if __name__ == "__main__":
    main()
