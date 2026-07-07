#!/usr/bin/env python3
"""Blocking source validation shared by the CI and Release workflows.

Checks, in order:
  1. every .xml under each addon dir (dirs containing an addon.xml) parses
  2. every strings.po under each addon dir parses (needs polib)
  3. every .py in the repo compiles (excluding out/ and tools/)

Exits non-zero on any failure so workflow jobs can gate on it directly.
"""

import pathlib
import py_compile
import sys
import xml.etree.ElementTree as ET

import polib


def main() -> int:
    bad = 0
    addon_dirs = sorted(p.parent for p in pathlib.Path(".").glob("*/addon.xml"))

    xml_ok = 0
    for d in addon_dirs:
        for f in sorted(d.rglob("*.xml")):
            try:
                ET.parse(f)
                xml_ok += 1
            except ET.ParseError as e:
                bad += 1
                print(f"FAIL {f}: {e}")
    print(f"xml: {xml_ok} files ok")

    po_ok = 0
    for d in addon_dirs:
        for f in sorted(d.rglob("strings.po")):
            try:
                polib.pofile(str(f))
                po_ok += 1
            except Exception as e:
                bad += 1
                print(f"FAIL {f}: {e}")
    print(f"po: {po_ok} files ok")

    py_ok = 0
    for f in sorted(pathlib.Path(".").rglob("*.py")):
        if f.parts[0] in ("out", "tools"):
            continue
        try:
            py_compile.compile(str(f), doraise=True)
            py_ok += 1
        except Exception as e:
            bad += 1
            print(f"FAIL {f}: {e}")
    print(f"py: {py_ok} files ok")

    print(f"{bad} failures")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
