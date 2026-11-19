#!/usr/bin/env python3
"""
Rebuilds CleanVinylPro2.zip - the ONE file to download: it unpacks into the single folder CleanVinylPro2,
exactly as that folder must be copied to the PC.

What is machine-specific or written while the program runs is left out: the Python environment (.venv),
the AI models (models), caches and the files the server saves next to itself (presets.json and the like).

The Windows text files of the folder (*.bat, *.cmd, folders.ini and the instruction *.txt) must have CRLF line endings:
cmd.exe can lose a label (goto :name) in a batch file that has LF only. Copying the files through tools
that "normalise" text can silently turn CRLF into LF, so this script repairs them first.

Run it after every change inside CleanVinylPro2 (and after tools/build_ccx.py when plugin files changed),
otherwise the archive carries the previous build:

    python tools/build_zip.py            # repair line endings if needed, rebuild the archive
    python tools/build_zip.py --check    # only report: line endings and whether the archive matches the folder
"""
import hashlib
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDER = "CleanVinylPro2"
ZIP_PATH = os.path.join(ROOT, FOLDER + ".zip")
# (backup: the owner's settings backups, written by the server on his PC - they are his, never part of the program)
SKIP_DIRS = {".venv", ".venv_old", "venv", "models", "__pycache__", "node_modules", "backup"}
# presets.json and the like are written by the server; launch_server_minimized.vbs and _task_tmp.xml by setup_launcher.py
SKIP_FILES = {"presets.json", "user_presets.json", "user_settings.json", "launch_server_minimized.vbs", "_task_tmp.xml"}
SKIP_ENDINGS = (".pyc", ".pyo", ".log", ".tmp", ".part")
# ...of the files lying directly in the folder (not server/requirements.txt). folders.ini is edited in Notepad and
# read by install_windows.bat, so it is a Windows text file too.
CRLF_ENDINGS = (".bat", ".cmd", ".txt", ".ini")


def folder_files() -> list[str]:
    """Paths relative to the repository root, '/' separated: 'CleanVinylPro2/...'."""
    found = []
    for base, dirs, files in os.walk(os.path.join(ROOT, FOLDER)):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            if name in SKIP_FILES or name.endswith(SKIP_ENDINGS):
                continue
            found.append(os.path.relpath(os.path.join(base, name), ROOT).replace(os.sep, "/"))
    return found


def needs_crlf(rel: str) -> bool:
    return rel.count("/") == 1 and rel.lower().endswith(CRLF_ENDINGS)


def with_crlf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n").replace(b"\n", b"\r\n")


def wrong_line_endings() -> list[str]:
    bad = []
    for rel in folder_files():
        if needs_crlf(rel):
            with open(os.path.join(ROOT, rel), "rb") as f:
                data = f.read()
            if data != with_crlf(data):
                bad.append(rel)
    return bad


def repair_line_endings() -> list[str]:
    fixed = wrong_line_endings()
    for rel in fixed:
        path = os.path.join(ROOT, rel)
        with open(path, "rb") as f:
            data = f.read()
        with open(path, "wb") as f:
            f.write(with_crlf(data))
    return fixed


def packaged() -> dict[str, str]:
    if not os.path.exists(ZIP_PATH):
        return {}
    with zipfile.ZipFile(ZIP_PATH) as z:
        return {i.filename: hashlib.sha256(z.read(i)).hexdigest() for i in z.infolist() if not i.is_dir()}


def on_disk() -> dict[str, str]:
    out = {}
    for rel in folder_files():
        with open(os.path.join(ROOT, rel), "rb") as f:
            out[rel] = hashlib.sha256(f.read()).hexdigest()
    return out


def differences() -> list[str]:
    a, b = packaged(), on_disk()
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def build() -> None:
    tmp = ZIP_PATH + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel in folder_files():
            src = os.path.join(ROOT, rel)
            info = zipfile.ZipInfo.from_file(src, rel)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            with open(src, "rb") as f:
                z.writestr(info, f.read(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    os.replace(tmp, ZIP_PATH)


def main() -> int:
    if "--check" in sys.argv:
        bad_eol, diff = wrong_line_endings(), differences()
        if bad_eol:
            print(f"{len(bad_eol)} Windows text file(s) in {FOLDER} do NOT have CRLF line endings (run tools/build_zip.py):")
            for name in bad_eol:
                print("  ", name)
        if diff:
            print(f"{FOLDER}.zip is OUT OF DATE, differing files:")
            for name in diff:
                print("  ", name)
        if bad_eol or diff:
            return 1
        print(f"{FOLDER}.zip matches the folder {FOLDER} ({len(folder_files())} files, Windows text files have CRLF)")
        return 0

    fixed = repair_line_endings()
    if fixed:
        print(f"CRLF line endings restored in {len(fixed)} file(s): {', '.join(os.path.basename(n) for n in fixed)}")
    diff = differences()
    if not diff:
        print(f"{FOLDER}.zip is already up to date")
        return 0
    build()
    left = differences()
    if left:
        print("ERROR: archive still differs:", left)
        return 1
    print(f"{FOLDER}.zip rebuilt ({len(folder_files())} files, {os.path.getsize(ZIP_PATH)} bytes); updated: {', '.join(diff)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
