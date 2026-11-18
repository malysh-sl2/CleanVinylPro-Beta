"""
Where the heavy, shared things of Clean Vinyl Pro 2 live on this computer.

The file folders.ini (next to install_windows.bat) names three folders:

    MODELS_DIR   AI models (*.onnx) - one copy for every installed version of the program
    PYTHON_DIR   the folder with python.exe (read by install_windows.bat)
    LIBS_DIR     Python libraries (OpenCV, ONNX Runtime, CUDA ...) - one copy for every installed version

An empty or missing line means "inside the program folder, as before" (server/models, server/.venv).

Only the standard library is used: the installer imports this module before any package is installed.
"""
import os
import re

SETTINGS_NAME = "folders.ini"
KEYS = ("MODELS_DIR", "PYTHON_DIR", "LIBS_DIR")

# Smallest size (MB) of a complete file. A shorter file is an interrupted download and counts as missing.
MODEL_MIN_MB = {
    "bria-rmbg-2.0.onnx": 500,
    "lama_fp32.onnx": 180,
    "rmbg14.onnx": 100,  # the lighter stand-in of bria-rmbg-2.0
    "lama.onnx": 50,  # the old export of LaMa
}
# How much a folder is worth as "the folder with the models": the two main files count double.
_MODEL_POINTS = {"bria-rmbg-2.0.onnx": 2, "lama_fp32.onnx": 2, "rmbg14.onnx": 1, "lama.onnx": 1}
_SEARCH_DEPTH = 2  # MODELS_DIR itself, its folders and their folders
_SEARCH_MAX_FOLDERS = 400


def app_root() -> str:
    """The program folder (the one with install_windows.bat); this file lies in <root>/server."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def settings_path(root: str = None) -> str:
    return os.path.join(root or app_root(), SETTINGS_NAME)


def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp1251"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def clean_path(value: str) -> str:
    """A path as people type it: spaces and quotes around it, a slash at the end."""
    value = (value or "").strip().strip('"').strip("'").strip()
    if not value:
        return ""
    value = os.path.expandvars(value)
    while len(value) > 1 and value[-1] in "\\/" and not re.fullmatch(r"[A-Za-z]:[\\/]", value):
        value = value[:-1]
    return value


def read_settings(root: str = None) -> dict:
    """{'MODELS_DIR': ..., 'PYTHON_DIR': ..., 'LIBS_DIR': ...}; a missing or empty line gives ''."""
    out = {k: "" for k in KEYS}
    try:
        with open(settings_path(root), "rb") as f:
            text = _decode(f.read())
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line or line[0] in ";#[" or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().upper()
        if key in out:
            out[key] = clean_path(value)
    return out


def write_setting(key: str, value: str, root: str = None) -> bool:
    """Replaces (or adds) one KEY=value line of folders.ini; every other line stays as it is."""
    key = key.upper()
    path = settings_path(root)
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError:
        raw = b""
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = _decode(raw)
    newline = "\r\n" if ("\r\n" in text or not text) else "\n"
    lines = text.splitlines()
    new_line = f"{key}={value}"
    for i, line in enumerate(lines):
        if re.match(rf"\s*{re.escape(key)}\s*=", line, flags=re.IGNORECASE):
            lines[i] = new_line
            break
    else:
        lines.append(new_line)
    data = (newline.join(lines) + newline).encode("utf-8")
    try:
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write((b"\xef\xbb\xbf" if bom else b"") + data)
        os.replace(tmp, path)
        return True
    except OSError:
        return False


# ----------------------------------------------------------------------------------------------------------------------
# AI models
# ----------------------------------------------------------------------------------------------------------------------
def local_models_dir(root: str = None) -> str:
    """The folder used before shared folders existed: <program>/server/models."""
    return os.path.join(root or app_root(), "server", "models")


def model_ok(folder: str, name: str) -> bool:
    """The file exists and is not a cut-off download."""
    try:
        return os.path.getsize(os.path.join(folder, name)) >= MODEL_MIN_MB.get(name, 0) * 1024 * 1024
    except OSError:
        return False


def model_score(folder: str) -> int:
    return sum(points for name, points in _MODEL_POINTS.items() if model_ok(folder, name))


def _same(a: str, b: str) -> bool:
    return bool(a) and bool(b) and os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _is_python_folder(folder: str) -> bool:
    """A Python installation or a virtual environment: thousands of files and never a model inside."""
    return any(os.path.exists(os.path.join(folder, n)) for n in ("pyvenv.cfg", "python.exe", "site-packages"))


def model_folders(base: str, skip=()) -> list:
    """base, its folders and their folders - the places where the models may lie."""
    found, level = [], [base]
    for depth in range(_SEARCH_DEPTH + 1):
        nxt = []
        for folder in level:
            if len(found) >= _SEARCH_MAX_FOLDERS:
                return found
            found.append(folder)
            if depth == _SEARCH_DEPTH:
                continue
            try:
                names = sorted(os.listdir(folder))
            except OSError:
                continue
            for name in names:
                sub = os.path.join(folder, name)
                if name[:1] in ".$" or not os.path.isdir(sub) or any(_same(sub, s) for s in skip):
                    continue
                if _is_python_folder(sub):
                    continue
                nxt.append(sub)
        level = nxt
    return found


def find_models_dir(base: str, skip=()) -> str:
    """The folder inside base that holds the models (base itself when there are none yet)."""
    best, best_score = base, 0
    for folder in model_folders(base, skip):
        score = model_score(folder)
        if score > best_score:
            best, best_score = folder, score
    return best


def resolve_models_dir(root: str = None, settings: dict = None) -> str:
    """
    The folder the server loads the models from (and download_models.py downloads into).
    Order: CLEANVINYL_MODELS_DIR -> MODELS_DIR of folders.ini -> <program>/server/models.
    The shared folder is preferred as soon as it exists; the program folder is used only when the shared one
    is missing, or is still empty while the program folder already holds the models.
    """
    env = clean_path(os.environ.get("CLEANVINYL_MODELS_DIR", ""))
    if env:
        return env
    settings = read_settings(root) if settings is None else settings
    local = local_models_dir(root)
    shared = settings.get("MODELS_DIR", "")
    if shared and os.path.isdir(shared):
        folder = find_models_dir(shared, skip=(settings.get("LIBS_DIR", ""),))
        if model_score(folder) > 0 or model_score(local) == 0:
            return folder
    return local


def install_models_dir(root: str = None) -> str:
    """
    The folder the installer fills: the shared one whenever it exists (models found in the program folder are
    copied into it), otherwise <program>/server/models.
    """
    env = clean_path(os.environ.get("CLEANVINYL_MODELS_DIR", ""))
    if env:
        return env
    settings = read_settings(root)
    shared = settings.get("MODELS_DIR", "")
    if shared and os.path.isdir(shared):
        return find_models_dir(shared, skip=(settings.get("LIBS_DIR", ""),))
    return local_models_dir(root)


def models_problem(root: str = None) -> str:
    """One sentence for the user when the folder named in folders.ini cannot be used; '' when all is well."""
    if clean_path(os.environ.get("CLEANVINYL_MODELS_DIR", "")):
        return ""
    shared = read_settings(root).get("MODELS_DIR", "")
    if shared and not os.path.isdir(shared):
        return (f"Папку з моделями «{shared}» (файл {SETTINGS_NAME}, рядок MODELS_DIR) не знайдено - "
                f"перевірте шлях або запустіть install_windows.bat.")
    return ""


# ----------------------------------------------------------------------------------------------------------------------
# Other copies of the program on this PC (their models and libraries can be re-used instead of a download)
# ----------------------------------------------------------------------------------------------------------------------
def _remembered_install_paths() -> list:
    """Folders written by setup_launcher.py of Clean Vinyl Pro 2 and of the original Clean Vinyl Pro."""
    out = []
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        files = [os.path.join(base, name, "install_path.txt") for name in ("CleanVinylPro2", "CleanVinylPro")]
    else:
        home = os.path.expanduser("~")
        files = [os.path.join(home, name, "install_path.txt") for name in (".cleanvinylpro2", ".cleanvinylpro")]
    for path in files:
        try:
            with open(path, "rb") as f:
                folder = clean_path(_decode(f.read()))
        except OSError:
            continue
        if folder:
            out.append(folder)
    return out


def other_install_roots(root: str = None) -> list:
    """Folders next to this program and remembered install folders that look like a copy of the program."""
    root = os.path.abspath(root or app_root())
    candidates = []
    parent = os.path.dirname(root)
    try:
        candidates += [os.path.join(parent, name) for name in sorted(os.listdir(parent))]
    except OSError:
        pass
    candidates += _remembered_install_paths()
    out = []
    for folder in candidates:
        if _same(folder, root) or any(_same(folder, o) for o in out):
            continue
        if os.path.isdir(os.path.join(folder, "server")):
            out.append(folder)
    return out


def model_sources(root: str = None, exclude: str = None) -> list:
    """Folders that may already hold a model file: it is copied from there instead of being downloaded."""
    root = root or app_root()
    settings = read_settings(root)
    folders = [local_models_dir(root)]
    shared = settings.get("MODELS_DIR", "")
    if shared and os.path.isdir(shared):
        folders += model_folders(shared, skip=(settings.get("LIBS_DIR", ""),))
    folders += [os.path.join(other, "server", "models") for other in other_install_roots(root)]
    out = []
    for folder in folders:
        if os.path.isdir(folder) and not _same(folder, exclude) and not any(_same(folder, o) for o in out):
            out.append(folder)
    return out
