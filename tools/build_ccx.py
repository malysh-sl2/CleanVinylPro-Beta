#!/usr/bin/env python3
"""
Rebuilds CleanVinylPro2/CleanVinylPro2.ccx from the files in CleanVinylPro2/uxp-plugin.
(The original program in the folder CleanVinylPro is never touched.)

A .ccx package is a plain zip archive with manifest.json at its root. Run this after every change of
the plugin files (main.js, index.html, styles.css, manifest.json, icons), otherwise double-clicking the
.ccx installs the previous plugin build:

    python tools/build_ccx.py            # rebuild
    python tools/build_ccx.py --check    # only report whether the package matches the folder
"""
import hashlib
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_DIR = os.path.join(ROOT, "CleanVinylPro2", "uxp-plugin")
CCX_PATH = os.path.join(ROOT, "CleanVinylPro2", "CleanVinylPro2.ccx")
TOP_ORDER = ["index.html", "main.js", "manifest.json", "styles.css"]  # same entry order as the original package


def plugin_files() -> list[str]:
    found = []
    for base, dirs, files in os.walk(PLUGIN_DIR):
        dirs.sort()
        for name in sorted(files):
            rel = os.path.relpath(os.path.join(base, name), PLUGIN_DIR).replace(os.sep, "/")
            found.append(rel)
    top = [f for f in TOP_ORDER if f in found]
    rest = sorted(f for f in found if f not in top)
    return top + rest


def packaged() -> dict[str, str]:
    if not os.path.exists(CCX_PATH):
        return {}
    with zipfile.ZipFile(CCX_PATH) as z:
        return {i.filename: hashlib.sha256(z.read(i)).hexdigest() for i in z.infolist() if not i.is_dir()}


def on_disk() -> dict[str, str]:
    out = {}
    for rel in plugin_files():
        with open(os.path.join(PLUGIN_DIR, rel), "rb") as f:
            out[rel] = hashlib.sha256(f.read()).hexdigest()
    return out


def differences() -> list[str]:
    a, b = packaged(), on_disk()
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def build() -> None:
    tmp = CCX_PATH + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel in plugin_files():
            src = os.path.join(PLUGIN_DIR, rel)
            info = zipfile.ZipInfo.from_file(src, rel)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            with open(src, "rb") as f:
                z.writestr(info, f.read(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    os.replace(tmp, CCX_PATH)


def main() -> int:
    diff = differences()
    if "--check" in sys.argv:
        if diff:
            print("CleanVinylPro2.ccx is OUT OF DATE, differing files:")
            for name in diff:
                print("  ", name)
            return 1
        print("CleanVinylPro2.ccx matches CleanVinylPro2/uxp-plugin")
        return 0
    if not diff:
        print("CleanVinylPro2.ccx is already up to date")
        return 0
    build()
    left = differences()
    if left:
        print("ERROR: package still differs:", left)
        return 1
    print(f"CleanVinylPro2.ccx rebuilt ({len(plugin_files())} files, {os.path.getsize(CCX_PATH)} bytes); updated: {', '.join(diff)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
