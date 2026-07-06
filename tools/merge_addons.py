#!/usr/bin/env python3
"""Splice repo-owned addon entries into a server addons.xml.

Usage: python3 merge_addons.py <server-addons.xml> <addons.repo-owned.xml>

Replaces (by id) or appends every <addon> from the second file into the
first, leaving all other entries untouched, then rewrites the server file
and its .md5 sidecar (bare lowercase hex of the exact bytes — what Kodi's
repository <checksum> expects). Third-party addons are never modified.

Stdlib only; ships as a GitHub Release asset alongside the channel zips.
"""

import hashlib
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__.strip())
    server_path, ours_path = Path(sys.argv[1]), Path(sys.argv[2])

    server = ET.parse(server_path)
    ours = ET.parse(ours_path)
    root = server.getroot()
    if root.tag != "addons" or ours.getroot().tag != "addons":
        sys.exit("ERROR: both files must have an <addons> root")

    replaced, added = [], []
    existing = {el.get("id"): el for el in root.findall("addon")}
    for el in ours.getroot().findall("addon"):
        addon_id = el.get("id")
        if addon_id in existing:
            root.remove(existing[addon_id])
            root.append(el)
            replaced.append(addon_id)
        else:
            root.append(el)
            added.append(addon_id)

    ET.indent(root)
    xml_bytes = ET.tostring(root, encoding="UTF-8", xml_declaration=True) + b"\n"
    server_path.write_bytes(xml_bytes)
    md5 = hashlib.md5(xml_bytes).hexdigest()
    (server_path.parent / (server_path.name + ".md5")).write_text(md5, encoding="utf-8")

    ET.fromstring(xml_bytes)  # self-check: merged file must re-parse
    for a in replaced:
        print(f"  replaced {a}")
    for a in added:
        print(f"  added    {a}")
    untouched = len(root.findall("addon")) - len(replaced) - len(added)
    print(f"done: {len(replaced)} replaced, {len(added)} added, "
          f"{untouched} third-party entries untouched; new md5 {md5}")


if __name__ == "__main__":
    main()
