#!/usr/bin/env python3
"""
Installer logic of Clean Vinyl Pro 2. install_windows.bat finds a Python and starts this file; fix_gpu_cuda.bat
starts it with the word "gpu". Only the standard library is used: nothing is installed yet when it runs.

    python setup_env.py install   everything below
    python setup_env.py gpu       re-install the GPU build of ONNX Runtime and run both models once
    python setup_env.py info      only show what is where; changes nothing

What "install" does
  1. Python libraries. With LIBS_DIR set in folders.ini they are kept ONCE, in <LIBS_DIR>/py312 (an ordinary
     virtual environment), and the program folder gets only a tiny server/.venv that points there. A new version,
     or a second copy of the program, then installs in seconds and downloads nothing.
     The libraries are taken, in this order:
       already in the shared folder  ->  copied from another copy of the program found on this PC (the original
       Clean Vinyl Pro, an earlier folder of Clean Vinyl Pro 2)  ->  downloaded with pip.
     If Python itself was moved or re-installed, the environments are re-linked to it and keep their libraries.
     Without LIBS_DIR everything lives in server/.venv, as in the earlier versions.
  2. AI models. They are used straight from MODELS_DIR. A missing file is copied from another copy of the program
     on this PC, and only if there is none it is downloaded - into MODELS_DIR, once.
  3. Both models are started on the video card, and the "start from Photoshop" launcher is registered.
"""
import ast
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time

SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

import cvpaths  # noqa: E402
import download_models  # noqa: E402

IS_WIN = os.name == "nt"
REQUIRED = ("numpy", "cv2", "PIL", "fastapi", "uvicorn", "onnxruntime")  # what server.py and engine.py import
# A "pointer" environment (server/.venv when the libraries are shared) holds two small files in its site-packages:
# <THIN_NAME>.pth - one line "import <THIN_NAME>", which Python runs at every start, and <THIN_NAME>.py - which
# adds the shared libraries to the search path. (A file named sitecustomize.py would be simpler, but another one
# found earlier on the path - some Python builds ship their own - silently wins over it.)
THIN_NAME = "cleanvinyl_shared_libs"
THIN_MARK = "# CLEANVINYL-SHARED-LIBS"  # first line of <THIN_NAME>.py
ENV_MARKER = "cleanvinyl_env.json"  # written into an environment once its libraries are complete
LOG_NAME = "install.log"
MIN_PYTHON = (3, 10)

_log_path = None
_interactive = False


class SetupError(Exception):
    """A message for the user; the installation stops."""


class DownloadError(SetupError):
    """pip could not get a package (no internet): trying another folder layout would not help."""


# ----------------------------------------------------------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------------------------------------------------------
def say(text: str = "") -> None:
    print(text, flush=True)
    if _log_path:
        try:
            with open(_log_path, "a", encoding="utf-8") as f:
                f.write(text + "\n")
        except OSError:
            pass


def _child_env() -> dict:
    """Environment for the Pythons started from here: nothing that could point them at another installation."""
    env = os.environ.copy()
    for name in ("PYTHONHOME", "PYTHONPATH", "__PYVENV_LAUNCHER__", "VIRTUAL_ENV", "PYTHONSTARTUP"):
        env.pop(name, None)
    env["PYTHONIOENCODING"] = "utf-8"  # what they print into a pipe is read here as UTF-8 (folder names in Cyrillic)
    return env


def run(cmd, capture: bool = False, timeout: float = None, extra_env: dict = None):
    """(exit code, text). A command that cannot even start gives exit code 9001."""
    env = _child_env()
    if extra_env:
        env.update(extra_env)
    try:
        if capture:
            p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, env=env)
            return p.returncode, p.stdout.decode("utf-8", errors="replace")
        return subprocess.run(cmd, timeout=timeout, env=env).returncode, ""
    except (OSError, subprocess.SubprocessError) as exc:
        return 9001, str(exc)


def env_python(env_dir: str) -> str:
    return os.path.join(env_dir, "Scripts", "python.exe") if IS_WIN else os.path.join(env_dir, "bin", "python")


def guess_site_packages(env_dir: str) -> str:
    """site-packages of an environment found by its layout - works for an environment whose Python no longer starts."""
    win = os.path.join(env_dir, "Lib", "site-packages")
    if os.path.isdir(win):
        return win
    hits = sorted(glob.glob(os.path.join(env_dir, "lib", "python3*", "site-packages")))
    return hits[0] if hits else ""


def base_python() -> str:
    """The real Python that runs this file (not the launcher of a virtual environment)."""
    cand = sys.executable
    if sys.prefix != sys.base_prefix:
        cand = getattr(sys, "_base_executable", "") or ""
        if not cand or not os.path.isfile(cand) or os.path.dirname(os.path.abspath(cand)).startswith(os.path.abspath(sys.prefix)):
            cand = os.path.join(sys.base_prefix, "python.exe") if IS_WIN else os.path.join(sys.base_prefix, "bin", "python3")
    return os.path.abspath(cand)


def py_tag(version) -> str:
    return f"py{version[0]}{version[1]}"


def program_version() -> str:
    try:
        with open(os.path.join(SERVER_DIR, "server.py"), encoding="utf-8") as f:
            m = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', f.read(), flags=re.MULTILINE)
        return m.group(1) if m else "?"
    except OSError:
        return "?"


def fmt_size(n: float) -> str:
    return f"{n / 1024 ** 3:.1f} ГБ" if n >= 1024 ** 3 else f"{n / 1024 ** 2:.0f} МБ"


def folder_size(path: str) -> int:
    total = 0
    for base, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in files:
            try:
                total += os.path.getsize(os.path.join(base, name))
            except OSError:
                pass
    return total


def free_space(path: str) -> int:
    """Free bytes on the drive of path (the nearest existing parent is asked); -1 when unknown."""
    probe_dir = os.path.abspath(path)
    while probe_dir and not os.path.isdir(probe_dir):
        parent = os.path.dirname(probe_dir)
        if parent == probe_dir:
            break
        probe_dir = parent
    try:
        return shutil.disk_usage(probe_dir).free
    except OSError:
        return -1


def remove_tree(path: str) -> bool:
    def on_error(func, target, _exc):
        try:
            os.chmod(target, 0o700)
            func(target)
        except OSError:
            pass

    if os.path.islink(path) or os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass
    elif os.path.isdir(path):
        shutil.rmtree(path, onerror=on_error)
    return not os.path.lexists(path)


def ask(lines, default: str = "") -> str:
    """Shows the question and returns the typed answer; without a keyboard (or with --yes) returns the default."""
    for line in lines:
        say(line)
    if not _interactive:
        return default
    try:
        answer = cvpaths.clean_path(input("> "))
    except (EOFError, KeyboardInterrupt):
        return default
    return answer or default


# ----------------------------------------------------------------------------------------------------------------------
# Looking inside an environment
# ----------------------------------------------------------------------------------------------------------------------
_PROBE = r"""
import importlib.util, json, sys, sysconfig
mods, dists = sys.argv[1].split(","), [d for d in sys.argv[2].split(",") if d]
missing = [m for m in mods if importlib.util.find_spec(m) is None]
versions = {}
try:
    from importlib import metadata
    for d in dists:
        try:
            versions[d] = metadata.version(d)
        except Exception:
            versions[d] = ""
except Exception:
    pass
print("CVPROBE" + json.dumps({
    "version": list(sys.version_info[:3]), "prefix": sys.prefix, "base_prefix": sys.base_prefix,
    "purelib": sysconfig.get_path("purelib"), "missing": missing, "versions": versions,
    "bits": 64 if sys.maxsize > 2 ** 32 else 32}))
"""


def probe(python: str, dists=()) -> dict:
    """What the Python of an environment reports about itself, or None when it does not start."""
    if not os.path.isfile(python):
        return None
    rc, out = run([python, "-c", _PROBE, ",".join(REQUIRED), ",".join(dists)], capture=True, timeout=180)
    if rc != 0:
        return None
    for line in reversed(out.splitlines()):
        if line.startswith("CVPROBE"):
            try:
                return json.loads(line[len("CVPROBE"):])
            except ValueError:
                return None
    return None


def import_check(python: str):
    """Really imports every library (a missing DLL shows up only here). Returns (ok, last lines of the error)."""
    rc, out = run([python, "-c", "import " + ", ".join(REQUIRED)], capture=True, timeout=600)
    return rc == 0, "\n".join(out.strip().splitlines()[-6:])


def read_requirements(path: str) -> list:
    """[(distribution name, smallest version as a tuple or None, the line itself)] of requirements.txt."""
    out = []
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return out
    for line in lines:
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        m = re.match(r"([A-Za-z0-9_.\-]+)\s*(?:>=\s*([0-9][0-9.]*))?", line)
        if m:
            out.append((m.group(1), _version_tuple(m.group(2)) if m.group(2) else None, line))
    return out


def _version_tuple(text: str):
    nums = []
    for part in (text or "").split("."):
        m = re.match(r"\d+", part)
        if not m:
            break
        nums.append(int(m.group(0)))
    return tuple(nums)


def unsatisfied(info: dict, requirements: list) -> list:
    """Lines of requirements.txt that the environment does not fulfil (not installed, or an older version)."""
    bad = []
    versions = (info or {}).get("versions", {})
    for name, minimum, line in requirements:
        have = _version_tuple(versions.get(name, ""))
        if not have or (minimum and have < minimum):
            bad.append(line)
    return bad


# ----------------------------------------------------------------------------------------------------------------------
# Creating and re-linking environments
# ----------------------------------------------------------------------------------------------------------------------
def create_venv(base: str, env_dir: str, with_pip: bool, clear: bool = False) -> bool:
    cmd = [base, "-m", "venv"] + (["--clear"] if clear else []) + ([] if with_pip else ["--without-pip"]) + [env_dir]
    rc, out = run(cmd, capture=True, timeout=900)
    if rc != 0:
        say("    " + "\n    ".join(out.strip().splitlines()[-5:]))
    return rc == 0 and os.path.isfile(env_python(env_dir))


def relink_cfg(env_dir: str, base: str, home: str = None) -> bool:
    """Writes the new place of Python into pyvenv.cfg (what `python -m venv` does, done by hand as a second way)."""
    home = home or os.path.dirname(base)
    cfg = os.path.join(env_dir, "pyvenv.cfg")
    try:
        with open(cfg, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return False
    out = []
    for line in lines:
        key = line.split("=", 1)[0].strip().lower()
        if key == "home":
            line = f"home = {home}"
        elif key == "executable":
            line = f"executable = {base}"
        elif key == "command":
            line = f"command = {base} -m venv {env_dir}"
        out.append(line)
    try:
        with open(cfg, "w", encoding="utf-8") as f:
            f.write("\n".join(out) + "\n")
        return True
    except OSError:
        return False


def env_exists(env_dir: str) -> bool:
    return os.path.isfile(os.path.join(env_dir, "pyvenv.cfg"))


def relink_venv(base: str, env_dir: str) -> bool:
    """
    Python was moved or re-installed: the environment still has its libraries but its python no longer starts.
    `python -m venv <the same folder>` writes the new place into it and leaves the libraries alone.
    """
    if not IS_WIN:  # there the python of an environment is a link; `venv` does not replace a link that leads nowhere
        bin_dir = os.path.join(env_dir, "bin")
        for name in (os.listdir(bin_dir) if os.path.isdir(bin_dir) else ()):
            path = os.path.join(bin_dir, name)
            if name.startswith("python") and os.path.islink(path) and not os.path.exists(path):
                os.remove(path)
    create_venv(base, env_dir, with_pip=False)
    if probe(env_python(env_dir)) is not None:
        return True
    relink_cfg(env_dir, base)
    return probe(env_python(env_dir)) is not None


def usable(info: dict, base_info: dict) -> bool:
    """The environment starts and runs the same Python version (3.12 with 3.12) - its libraries fit."""
    return bool(info) and list(info.get("version", [0, 0])[:2]) == list(base_info["version"][:2])


def same_python(info: dict, base_info: dict) -> bool:
    """The environment is linked to exactly the Python installation that runs the setup."""
    if not usable(info, base_info):
        return False
    a, b = info.get("base_prefix", ""), base_info.get("base_prefix", "")
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def other_version(env_dir: str, tag: str) -> bool:
    """The libraries inside were built for another Python version (3.11 against 3.12): they cannot be kept."""
    found = cfg_tag(env_dir) or files_tag(guess_site_packages(env_dir) or env_dir)
    return bool(found) and found != tag


def ensure_pip(python: str) -> bool:
    rc, _ = run([python, "-m", "pip", "--version"], capture=True, timeout=300)
    if rc == 0:
        return True
    rc, _ = run([python, "-m", "ensurepip", "--upgrade", "--default-pip"], capture=True, timeout=900)
    return rc == 0


def pip(python: str, *args) -> int:
    return run([python, "-m", "pip", *args, "--disable-pip-version-check"])[0]


# ----------------------------------------------------------------------------------------------------------------------
# NVIDIA driver and ONNX Runtime
# ----------------------------------------------------------------------------------------------------------------------
def find_nvidia_smi() -> str:
    smi = shutil.which("nvidia-smi")
    if smi:
        return smi
    for cand in (r"C:\Windows\System32\nvidia-smi.exe", r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"):
        if os.path.exists(cand):
            return cand
    return ""


def cuda_major() -> int:
    """CUDA version supported by the installed NVIDIA driver (0 when there is no driver)."""
    smi = find_nvidia_smi()
    if not smi:
        return 0
    rc, out = run([smi], capture=True, timeout=30)
    m = re.search(r"CUDA Version:\s*(\d+)\.(\d+)", out) if rc == 0 else None
    return int(m.group(1)) if m else 0


def onnxruntime_specs(cuda: int) -> list:
    """pip arguments to try, in order - the same choice install_windows.bat always made."""
    if cuda >= 13:
        first = ["--upgrade", "onnxruntime-gpu[cuda,cudnn]>=1.27.0"]
    elif cuda == 12:
        first = ["onnxruntime-gpu[cuda,cudnn]==1.26.0"]
    else:
        first = ["onnxruntime-gpu[cuda,cudnn]>=1.27.0"]
    return [first, ["onnxruntime-gpu"]]


def onnxruntime_state(python: str) -> str:
    """'gpu' (the build with the CUDA provider), 'cpu', or 'missing' (not installed or does not import)."""
    code = "import onnxruntime as o; print('CVORT=' + ('gpu' if 'CUDAExecutionProvider' in o.get_available_providers() else 'cpu'))"
    rc, out = run([python, "-c", code], capture=True, timeout=600)
    m = re.search(r"CVORT=(gpu|cpu)", out)
    return m.group(1) if rc == 0 and m else "missing"


def install_onnxruntime(python: str) -> bool:
    cuda = cuda_major()
    if cuda >= 13:
        say(f"    Драйвер NVIDIA підтримує CUDA {cuda}: ставимо onnxruntime-gpu з бібліотеками CUDA 13...")
    elif cuda == 12:
        say("    Драйвер NVIDIA підтримує CUDA 12: ставимо onnxruntime-gpu 1.26.0 з бібліотеками CUDA 12...")
    else:
        say("    [УВАГА] Драйвер NVIDIA не знайдено. Ставимо onnxruntime-gpu...")
    run([python, "-m", "pip", "uninstall", "-y", "onnxruntime", "onnxruntime-gpu", "onnxruntime-directml",
         "--disable-pip-version-check"], capture=True, timeout=1800)
    for spec in onnxruntime_specs(cuda):
        if pip(python, "install", "--no-cache-dir", *spec) == 0:
            break
        say("    Не вдалося, пробуємо запасний варіант...")
    if onnxruntime_state(python) == "missing":
        say("    Ставимо запасний onnxruntime (без відеокарти), щоб сервер точно запускався...")
        pip(python, "install", "--no-cache-dir", "onnxruntime")
    return onnxruntime_state(python) != "missing"


# ----------------------------------------------------------------------------------------------------------------------
# Libraries that are already on this PC (another copy of the program) - copied instead of downloaded
# ----------------------------------------------------------------------------------------------------------------------
def cfg_tag(env_dir: str) -> str:
    """'py312' read from pyvenv.cfg of an environment ('' when unknown)."""
    try:
        with open(os.path.join(env_dir, "pyvenv.cfg"), encoding="utf-8", errors="replace") as f:
            for line in f:
                key, _, value = line.partition("=")
                if key.strip().lower() in ("version", "version_info"):
                    m = re.match(r"\s*(\d+)\.(\d+)", value)
                    if m:
                        return f"py{m.group(1)}{m.group(2)}"
    except OSError:
        pass
    return ""


def files_tag(site: str) -> str:
    """'py312' read from the names of the compiled files of numpy ('' when unknown)."""
    for pattern in ("numpy/_core/*.pyd", "numpy/core/*.pyd", "numpy/_core/*.so", "numpy/core/*.so"):
        for path in glob.glob(os.path.join(site, *pattern.split("/"))):
            m = re.search(r"\.cp(\d)(\d+)-|cpython-(\d)(\d+)", os.path.basename(path))
            if m:
                return "py" + (m.group(1) or m.group(3)) + (m.group(2) or m.group(4))
    return ""


def has_cuda_provider(site: str) -> bool:
    capi = os.path.join(site, "onnxruntime", "capi")
    return bool(glob.glob(os.path.join(capi, "onnxruntime_providers_cuda.dll")) or
                glob.glob(os.path.join(capi, "libonnxruntime_providers_cuda.so")))


def donor_info(env_dir: str) -> dict:
    """An environment that really holds the libraries (not a pointer one), or None."""
    site = guess_site_packages(env_dir)
    if not site or is_thin(env_dir):
        return None
    if not all(os.path.isdir(os.path.join(site, m)) for m in REQUIRED):
        return None
    return {"env": env_dir, "site": site, "tag": cfg_tag(env_dir) or files_tag(site), "cuda": has_cuda_provider(site)}


def find_donors(root: str, tag: str, skip_env: str = "") -> list:
    """Environments of other copies of the program that fit this Python; the complete GPU ones first."""
    env_dirs = [os.path.join(root, "server", ".venv"), os.path.join(root, "server", ".venv_old")]
    libs_dir = cvpaths.read_settings(root).get("LIBS_DIR", "")
    if libs_dir and os.path.isfile(marker_path(os.path.join(libs_dir, tag))):
        env_dirs.append(os.path.join(libs_dir, tag))
    env_dirs += [os.path.join(other, "server", ".venv") for other in cvpaths.other_install_roots(root)]
    need_cuda = IS_WIN and bool(find_nvidia_smi())
    out = []
    for env_dir in env_dirs:
        if skip_env and os.path.normcase(os.path.abspath(env_dir)) == os.path.normcase(os.path.abspath(skip_env)):
            continue
        info = donor_info(env_dir)
        if info is None or info["tag"] != tag:
            continue
        if need_cuda and not info["cuda"]:
            continue  # a copy without the CUDA files would only give a CPU installation
        out.append(info)
    out.sort(key=lambda d: not d["cuda"])
    return out


_ADOPT_SKIP = {"__pycache__", "sitecustomize.py", "pip", THIN_NAME + ".py", THIN_NAME + ".pth", ENV_MARKER}


def adopt(donor: dict, target_site: str) -> bool:
    """Copies the libraries of another copy of the program into target_site. Nothing is downloaded."""
    src_site = donor["site"]
    os.makedirs(target_site, exist_ok=True)
    present = set(os.listdir(target_site))  # pip (and setuptools) of the fresh environment stay as they are
    names = [n for n in sorted(os.listdir(src_site))
             if n not in _ADOPT_SKIP and n not in present and not (n.startswith("pip-") and n.endswith(".dist-info"))]
    total = sum(folder_size(os.path.join(src_site, n)) if os.path.isdir(os.path.join(src_site, n))
                else os.path.getsize(os.path.join(src_site, n)) for n in names)
    free = free_space(target_site)
    if 0 <= free < total * 1.05:
        say(f"    [УВАГА] На диску замало місця для копії: потрібно {fmt_size(total)}, вільно {fmt_size(free)}.")
        return False
    say(f"    Копіюємо бібліотеки ({fmt_size(total)}) з: {donor['env']}")
    state = {"done": 0, "shown": time.monotonic()}

    def copy_counted(src, dst):
        shutil.copy2(src, dst)
        try:
            state["done"] += os.path.getsize(dst)
        except OSError:
            pass
        if time.monotonic() - state["shown"] >= 5.0:
            state["shown"] = time.monotonic()
            say(f"      {int(state['done'] * 100 / max(1, total)):3d}%  ({fmt_size(state['done'])} з {fmt_size(total)})")

    started = []
    try:
        for name in names:
            src, dst = os.path.join(src_site, name), os.path.join(target_site, name)
            started.append(dst)
            if os.path.isdir(src):
                shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"), copy_function=copy_counted)
            else:
                copy_counted(src, dst)
    except (OSError, shutil.Error) as exc:
        say(f"    [УВАГА] Копіювання не вдалося: {str(exc)[:300]}")
        for dst in started:  # a half-copied library must not look like an installed one
            remove_tree(dst)
        return False
    if state["done"] != total:  # every byte must have arrived: the big CUDA files are never imported by Python itself
        say(f"    [УВАГА] Скопійовано {fmt_size(state['done'])} із {fmt_size(total)} - копію відкинуто.")
        for dst in started:
            remove_tree(dst)
        return False
    say("      100%")
    return True


def ask_for_donor(tag: str, target_site: str) -> bool:
    """
    No ready libraries were found on this PC. With a keyboard, the user may name a folder that has them (another
    copy of the program that stands somewhere unusual); they are then copied instead of downloaded.
    """
    if not _interactive:
        return False
    answer = ask(["    Готових бібліотек Python на цьому комп'ютері не знайдено.",
                  "    Якщо вони вже встановлені в іншій папці програми (наприклад у старій CleanVinylPro) -",
                  "    вставте сюди шлях до тієї папки і натисніть Enter: вони скопіюються без інтернету.",
                  "    Якщо такої папки немає - просто натисніть Enter: бібліотеки завантажаться з інтернету",
                  "    (2-4 ГБ, один раз для всіх версій)."])
    if not answer:
        return False
    for env_dir in (os.path.join(answer, "server", ".venv"), os.path.join(answer, ".venv"), answer):
        donor = donor_info(env_dir)
        if donor is None:
            continue
        if donor["tag"] != tag:
            say(f"    Бібліотеки в цій папці зроблено для іншої версії Python ({donor['tag'] or 'невідомої'}), потрібна {tag} - "
                "не підходять.")
            return False
        if IS_WIN and find_nvidia_smi() and not donor["cuda"]:
            say("    У цій папці немає файлів для відеокарти (CUDA) - не підходить.")
            return False
        return adopt(donor, target_site)
    say("    У цій папці готових бібліотек не знайдено.")
    return False


# ----------------------------------------------------------------------------------------------------------------------
# Filling an environment with the libraries
# ----------------------------------------------------------------------------------------------------------------------
def marker_path(env_dir: str) -> str:
    return os.path.join(env_dir, ENV_MARKER)


def write_marker(env_dir: str, info: dict) -> None:
    try:
        with open(marker_path(env_dir), "w", encoding="utf-8") as f:
            json.dump({"complete": True, "python": ".".join(str(v) for v in info["version"]),
                       "program": program_version(), "time": time.strftime("%Y-%m-%d %H:%M:%S")}, f, indent=2)
    except OSError:
        pass


def fill_env(python: str, env_dir: str, root: str, tag: str) -> None:
    """Makes sure the environment holds every library: nothing to do -> copy from this PC -> pip."""
    requirements = read_requirements(os.path.join(root, "server", "requirements.txt"))
    dists = [name for name, _minimum, _line in requirements]
    info = probe(python, dists)
    if info is None:
        raise SetupError(f"Python середовища не запускається: {python}")
    todo = info["missing"] or unsatisfied(info, requirements)

    if not todo and os.path.isfile(marker_path(env_dir)):
        say("    Бібліотеки вже на місці - нічого не завантажуємо.")
    else:
        try:
            os.remove(marker_path(env_dir))
        except OSError:
            pass
        if len(info["missing"]) == len(REQUIRED):  # an empty environment: look for a copy on this PC first
            copied = False
            for donor in find_donors(root, tag, skip_env=env_dir):
                if adopt(donor, info["purelib"]):
                    copied = True
                    break
            if not copied:
                ask_for_donor(tag, info["purelib"])  # before 2-4 GB are downloaded: maybe a copy lies where nobody looked
            info = probe(python, dists) or info
        if info["missing"] or unsatisfied(info, requirements):
            if not ensure_pip(python):
                raise SetupError("У середовищі немає pip і його не вдалося додати.")
            wanted = [m for m in info["missing"] if m != "onnxruntime"] or unsatisfied(info, requirements)
            if wanted:
                say("    Завантажуємо бібліотеки сервера та OpenCV (потрібен інтернет)...")
                if pip(python, "install", "-r", os.path.join(root, "server", "requirements.txt")) != 0:
                    raise DownloadError("Не вдалося завантажити бібліотеки (requirements.txt). Перевірте інтернет-з'єднання "
                                        "і запустіть install_windows.bat ще раз.")
            info = probe(python, dists) or info
            if "onnxruntime" in info["missing"]:
                say("    Завантажуємо ONNX Runtime для відеокарти (близько 2 ГБ, потрібен інтернет)...")
                install_onnxruntime(python)
            info = probe(python, dists) or info
            if info["missing"]:
                raise DownloadError("Не вдалося завантажити: " + ", ".join(info["missing"]) + ". Перевірте "
                                    "інтернет-з'єднання і запустіть install_windows.bat ще раз.")

    # the video card needs the GPU build; a CPU-only one is replaced (only when there is an NVIDIA driver)
    if find_nvidia_smi() and onnxruntime_state(python) == "cpu":
        say("    Встановлено ONNX Runtime без підтримки відеокарти - замінюємо на GPU-версію...")
        if ensure_pip(python):
            install_onnxruntime(python)

    ok, err = import_check(python)
    if not ok and "onnxruntime" in err and ensure_pip(python):
        say("    ONNX Runtime не завантажується - перевстановлюємо його...")
        install_onnxruntime(python)
        ok, err = import_check(python)
    if not ok:
        raise SetupError("Бібліотеки встановлено, але вони не завантажуються:\n" + err +
                         f"\nВидаліть папку {env_dir} і запустіть install_windows.bat ще раз.")
    if not os.path.isfile(marker_path(env_dir)):  # a complete environment is left exactly as it is
        write_marker(env_dir, probe(python) or info)


# ----------------------------------------------------------------------------------------------------------------------
# The three kinds of environment
# ----------------------------------------------------------------------------------------------------------------------
def is_thin(env_dir: str) -> bool:
    site = guess_site_packages(env_dir)
    if not site:
        return False
    try:
        with open(os.path.join(site, THIN_NAME + ".py"), encoding="utf-8", errors="replace") as f:
            return f.readline().startswith(THIN_MARK) and os.path.isfile(os.path.join(site, THIN_NAME + ".pth"))
    except OSError:
        return False


def thin_target(env_dir: str) -> str:
    """The python of the shared environment a pointer environment refers to ('' when it is not a pointer one)."""
    if not is_thin(env_dir):
        return ""
    try:
        with open(os.path.join(guess_site_packages(env_dir), THIN_NAME + ".py"), encoding="utf-8") as f:
            m = re.search(r"^SHARED_PYTHON = (.+)$", f.read(), flags=re.MULTILINE)
        return ast.literal_eval(m.group(1)) if m else ""
    except (OSError, ValueError, SyntaxError):
        return ""


def is_full(env_dir: str) -> bool:
    site = guess_site_packages(env_dir)
    return bool(site) and not is_thin(env_dir) and any(os.path.isdir(os.path.join(site, m)) for m in ("numpy", "cv2", "onnxruntime"))


def thin_module(shared_site: str, shared_python: str) -> str:
    return f'''{THIN_MARK}
# Written by setup_env.py of Clean Vinyl Pro 2. Do not edit: install_windows.bat writes this file again.
# Python runs it at every start (see {THIN_NAME}.pth next to it).
#
# This small environment has no libraries of its own. It takes them from the shared folder named below, so every
# installed version of the program uses one and the same copy and nothing is downloaded twice.
import os
import site
import sys

SHARED_SITE_PACKAGES = {ascii(shared_site)}
SHARED_PYTHON = {ascii(shared_python)}

if os.path.isdir(SHARED_SITE_PACKAGES):
    site.addsitedir(SHARED_SITE_PACKAGES)
    os.environ["CLEANVINYL_ENV_PYTHON"] = SHARED_PYTHON
else:
    sys.stderr.write(
        "\\n[Clean Vinyl Pro 2] Не знайдено спільну папку бібліотек Python:\\n    " + SHARED_SITE_PACKAGES + "\\n"
        "Якщо диск від'єднано - під'єднайте його. Якщо папку перенесли або видалили - виправте рядок LIBS_DIR\\n"
        "у файлі folders.ini і запустіть install_windows.bat.\\n\\n"
    )
'''


def ensure_shared_env(base: str, base_info: dict, env_dir: str, root: str) -> str:
    """The one environment with the real libraries, shared by every installed version. Returns its python."""
    python = env_python(env_dir)
    tag = py_tag(base_info["version"])
    info = probe(python)
    if env_exists(env_dir) and not same_python(info, base_info) and not other_version(env_dir, tag):
        say("    Python перенесено або перевстановлено - оновлюємо посилання (бібліотеки залишаються на місці)...")
        if not relink_venv(base, env_dir):
            say("    Не вдалося - створюємо середовище заново.")
        info = probe(python)
    if not usable(info, base_info) or other_version(env_dir, tag):
        leftovers = os.path.isdir(env_dir) and bool(os.listdir(env_dir))
        say(f"    Створюємо спільне середовище: {env_dir}")
        os.makedirs(os.path.dirname(env_dir), exist_ok=True)
        if not create_venv(base, env_dir, with_pip=True, clear=leftovers):
            raise SetupError(f"Не вдалося створити середовище Python у {env_dir}")
    elif not os.path.isfile(marker_path(env_dir)) and len((info or {}).get("missing", ())) < len(REQUIRED):
        # libraries without the "complete" mark: an installation that was interrupted half-way
        say("    Минуле встановлення бібліотек було перерване - починаємо його заново.")
        if not create_venv(base, env_dir, with_pip=True, clear=True):
            raise SetupError(f"Не вдалося створити середовище Python у {env_dir}")
    fill_env(python, env_dir, root, tag)
    return python


def ensure_thin_env(base: str, base_info: dict, root: str, shared_python: str) -> str:
    """server/.venv that only points at the shared libraries. Returns its python."""
    local = os.path.join(root, "server", ".venv")
    trash = local + "_old"
    python = env_python(local)
    shared_site = (probe(shared_python) or {}).get("purelib", "")
    if not shared_site:
        raise SetupError("Спільне середовище не відповідає.")

    if is_full(local):  # the libraries of an earlier installation of this folder: the shared ones replace them
        size = folder_size(local)
        remove_tree(trash)
        try:
            os.rename(local, trash)
        except OSError:
            if not remove_tree(local):
                raise SetupError(f"Не вдалося прибрати стару папку {local} - закрийте сервер і спробуйте ще раз.")
        say(f"    Стару папку бібліотек у програмі (server\\.venv, {fmt_size(size)}) прибрано: тепер вони спільні.")
    info = probe(python)
    if not same_python(info, base_info) or not is_thin(local):
        if not create_venv(base, local, with_pip=False, clear=os.path.isdir(local)):
            raise SetupError(f"Не вдалося створити {local}")
        info = probe(python)
        if info is None:
            raise SetupError(f"Python не запускається: {python}")
    with open(os.path.join(info["purelib"], THIN_NAME + ".py"), "w", encoding="utf-8") as f:
        f.write(thin_module(shared_site, shared_python))
    with open(os.path.join(info["purelib"], THIN_NAME + ".pth"), "w", encoding="ascii") as f:
        f.write(f"import {THIN_NAME}\n")

    code = "import json, os, numpy; print('CVLIBS=' + json.dumps(os.path.dirname(os.path.dirname(os.path.abspath(numpy.__file__)))))"
    rc, out = run([python, "-c", code], capture=True, timeout=600)
    m = re.search(r"CVLIBS=(\".*\")", out)
    try:
        seen = json.loads(m.group(1)) if m else ""
    except ValueError:
        seen = ""
    if rc != 0 or os.path.normcase(os.path.abspath(seen)) != os.path.normcase(os.path.abspath(shared_site)):
        raise SetupError("Програма не бачить спільних бібліотек:\n" + "\n".join(out.strip().splitlines()[-4:]))
    ok, err = import_check(python)
    if not ok:
        raise SetupError("Спільні бібліотеки не завантажуються з папки програми:\n" + err)
    if os.path.isdir(trash) and not remove_tree(trash):
        say(f"    [УВАГА] Папку {trash} не вдалося видалити повністю - видаліть її вручну, вона більше не потрібна.")
    return python


def ensure_classic_env(base: str, base_info: dict, root: str) -> str:
    """Everything inside the program folder (server/.venv), as in the earlier versions. Returns its python."""
    local = os.path.join(root, "server", ".venv")
    python = env_python(local)
    if is_thin(local):  # it used to point at shared libraries: make it an ordinary environment again
        for ending in (".pth", ".py"):
            try:
                os.remove(os.path.join(guess_site_packages(local), THIN_NAME + ending))
            except OSError:
                pass
    tag = py_tag(base_info["version"])
    info = probe(python)
    if env_exists(local) and not same_python(info, base_info) and not other_version(local, tag):
        say("    Python перенесено або перевстановлено - оновлюємо посилання (бібліотеки залишаються на місці)...")
        relink_venv(base, local)
        info = probe(python)
    if not usable(info, base_info) or other_version(local, tag):
        say(f"    Створюємо середовище: {local}")
        if not create_venv(base, local, with_pip=True, clear=os.path.isdir(local)):
            raise SetupError(f"Не вдалося створити {local}")
    fill_env(python, local, root, tag)
    return python


# ----------------------------------------------------------------------------------------------------------------------
# Steps of the installation
# ----------------------------------------------------------------------------------------------------------------------
def step_libraries(root: str, base: str, base_info: dict):
    """Returns (python of server/.venv, folder that really holds the libraries, True when it is the shared one)."""
    settings = cvpaths.read_settings(root)
    tag = py_tag(base_info["version"])
    libs_dir = settings.get("LIBS_DIR", "")
    local = os.path.join(root, "server", ".venv")
    if not libs_dir:
        say("    У folders.ini не вказано LIBS_DIR - бібліотеки будуть у папці програми (server\\.venv).")

    if libs_dir:
        try:
            os.makedirs(libs_dir, exist_ok=True)
        except OSError as exc:
            answer = ask([f"    Не вдалося відкрити папку для бібліотек: {libs_dir}", f"    ({str(exc)[:200]})",
                          "    Вставте шлях до іншої папки і натисніть Enter.",
                          "    Або просто натисніть Enter - тоді бібліотеки буде встановлено в папку програми."])
            libs_dir = ""
            if answer:
                try:
                    os.makedirs(answer, exist_ok=True)
                    libs_dir = answer
                    cvpaths.write_setting("LIBS_DIR", answer, root)
                except OSError:
                    say("    Цю папку теж не вдалося відкрити - ставимо в папку програми.")

    if libs_dir:
        env_dir = os.path.join(libs_dir, tag)
        say(f"    Спільна папка бібліотек: {env_dir}")
        try:
            shared_python = ensure_shared_env(base, base_info, env_dir, root)
            return ensure_thin_env(base, base_info, root, shared_python), env_dir, True
        except DownloadError:
            raise
        except SetupError as exc:
            say(f"    [УВАГА] Зі спільною папкою не вийшло: {exc}")
            say("    Встановлюємо бібліотеки в папку програми (server\\.venv), як у попередніх версіях.")
            if is_full(local + "_old") and not is_full(local):  # they were put aside a moment ago: take them back
                if remove_tree(local):
                    try:
                        os.rename(local + "_old", local)
                    except OSError:
                        pass
    return ensure_classic_env(base, base_info, root), local, False


def step_models(root: str) -> str:
    """Returns the folder with the models, or '' when a model could not be obtained."""
    shared = cvpaths.read_settings(root).get("MODELS_DIR", "")
    for _attempt in range(3):
        if not shared or os.path.isdir(shared):
            break
        answer = ask([f"    Папку з моделями не знайдено: {shared}",
                      "    Якщо моделі лежать в іншій папці - вставте сюди її шлях і натисніть Enter.",
                      "    Якщо моделей ще немає - просто натисніть Enter: папку буде створено,",
                      "    моделі (близько 1,2 ГБ) завантажаться в неї один раз."])
        if answer:
            if os.path.isdir(answer):
                cvpaths.write_setting("MODELS_DIR", answer, root)
                shared = answer
            else:
                say(f"    Такої папки немає: {answer}")
            continue
        try:
            os.makedirs(shared, exist_ok=True)
        except OSError as exc:
            say(f"    Не вдалося створити цю папку ({str(exc)[:160]}) - моделі будуть у папці програми (server\\models).")
        break

    target = cvpaths.install_models_dir(root)
    sources = cvpaths.model_sources(root, exclude=target)
    missing = download_models.missing_models(target)
    if missing and shared and _interactive and not all(download_models.find_copy(n, sources) for n in missing):
        answer = ask([f"    У папці {target} немає: {', '.join(missing)}",
                      "    Якщо ці файли лежать в іншій папці - вставте сюди її шлях і натисніть Enter.",
                      "    Якщо їх ще немає - просто натисніть Enter: вони завантажаться в цю папку один раз."])
        if answer and os.path.isdir(answer):
            cvpaths.write_setting("MODELS_DIR", answer, root)
            target = cvpaths.install_models_dir(root)
            sources = cvpaths.model_sources(root, exclude=target)
        elif answer:
            say(f"    Такої папки немає: {answer} - завантажуємо в {target}")
    say(f"    Папка з моделями: {target}")
    return target if download_models.ensure_models(target, False, sources) else ""


_GPU_CHECK = r"""
import sys
sys.path.insert(0, sys.argv[1])
import engine
eng = engine.CleanVinylEngine(sys.argv[2])
print("Active Device:", eng.gpu_name)
print("Active Provider:", eng.provider_name)
print("GPU Warning:", eng.gpu_error or "None")
"""

_GPU_TEST = r"""
import sys
import numpy as np
sys.path.insert(0, sys.argv[1])
import engine, onnxruntime as ort
print("DLL dirs registered:", len(engine._NVIDIA_DLL_DIRS))
print("Available providers:", ort.get_available_providers())
eng = engine.CleanVinylEngine(sys.argv[2])
print("Active Provider:", eng.provider_name)
print("Active GPU:", eng.gpu_name)
test_rgba = np.zeros((512, 512, 4), dtype=np.uint8)
test_sel = np.zeros((512, 512), dtype=np.uint8)
test_sel[100:140, 100:140] = 255
out, st = eng.process(test_rgba, 8, {'spots': 75, 'scuffs': 65, 'seamOn': False, 'seam': 0, 'edge': 70, 'smokeOn': False,
                                     'smoke': 0, 'grain': 90, 'shadow': True, 'removeStands': False, 'master': 100}, test_sel)
print("REAL GPU TEST OK:", st)
print("GPU Error (if any):", eng.gpu_error or "None")
"""


def step_gpu_check(python: str, root: str, models_dir: str, full_test: bool = False) -> bool:
    rc, _ = run([python, "-c", _GPU_TEST if full_test else _GPU_CHECK, os.path.join(root, "server"), models_dir])
    if rc != 0:
        say("    [УВАГА] Перевірка на відеокарті завершилась помилкою (див. вище). Спробуйте fix_gpu_cuda.bat.")
    return rc == 0


def step_launcher(python: str, root: str) -> bool:
    rc, _ = run([python, os.path.join(root, "server", "setup_launcher.py")])
    return rc == 0


def summary(root: str, base: str, libs_at: str, shared: bool, models_dir: str) -> None:
    say("")
    say("  Що де лежить:")
    say(f"    Python:      {os.path.dirname(base)}")
    say(f"    Бібліотеки:  {libs_at}" + ("   (спільні для всіх версій)" if shared else "   (у папці програми)"))
    say(f"    AI-моделі:   {models_dir or 'НЕ ЗНАЙДЕНО'}")
    local_models = cvpaths.local_models_dir(root)
    if models_dir and os.path.normcase(os.path.abspath(models_dir)) != os.path.normcase(os.path.abspath(local_models)) \
            and cvpaths.model_score(local_models) > 0:
        say(f"    У папці {local_models} залишилися старі копії моделей ({fmt_size(folder_size(local_models))}) -")
        say("    вони більше не потрібні, їх можна видалити.")
    say(f"  Змінити ці папки: файл {cvpaths.SETTINGS_NAME} у папці програми, потім знову install_windows.bat.")


# ----------------------------------------------------------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------------------------------------------------------
def _base_info(base: str) -> dict:
    info = probe(base)
    if info is None:
        raise SetupError(f"Python не запускається: {base}")
    if tuple(info["version"][:2]) < MIN_PYTHON or info.get("bits") != 64:
        raise SetupError(f"Потрібен 64-бітний Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} або новіший, а знайдено "
                         f"{'.'.join(str(v) for v in info['version'])} ({info.get('bits')}-біт): {base}")
    return info


def cmd_install(root: str, skip_gpu: bool, skip_launcher: bool) -> int:
    base = base_python()
    base_info = _base_info(base)
    say(f"  Clean Vinyl Pro 2 v{program_version()}")
    say(f"  Python {'.'.join(str(v) for v in base_info['version'])}: {base}")
    wanted = cvpaths.read_settings(root).get("PYTHON_DIR", "")
    if not wanted or os.path.normcase(os.path.abspath(wanted)) != os.path.normcase(os.path.dirname(base)):
        if wanted and not os.path.isfile(os.path.join(wanted, "python.exe" if IS_WIN else "python3")):
            say(f"  (у {cvpaths.SETTINGS_NAME} записано {wanted}, але Python там немає - запам'ятовуємо справжнє місце)")
            cvpaths.write_setting("PYTHON_DIR", os.path.dirname(base), root)
        elif not wanted:
            cvpaths.write_setting("PYTHON_DIR", os.path.dirname(base), root)

    say("")
    say("[1/4] Бібліотеки Python (OpenCV, ONNX Runtime, CUDA)")
    python, libs_at, shared = step_libraries(root, base, base_info)

    say("")
    say("[2/4] AI-моделі (bria-rmbg-2.0 та LaMa)")
    models_dir = step_models(root)
    if not models_dir:
        raise SetupError("Не вдалося отримати AI-моделі. Перевірте інтернет-з'єднання і запустіть ще раз.")

    say("")
    say("[3/4] Перевіряємо реальний запуск моделей на відеокарті...")
    if skip_gpu:
        say("    (пропущено)")
    else:
        step_gpu_check(python, root, models_dir)

    say("")
    say("[4/4] Реєстрація запуску GPU-сервера прямо з Photoshop (без автозапуску ПК)...")
    if skip_launcher:
        say("    (пропущено)")
    else:
        step_launcher(python, root)

    summary(root, base, libs_at, shared, models_dir)
    return 0


def cmd_gpu(root: str) -> int:
    """fix_gpu_cuda.bat: started with the python of server/.venv."""
    local = os.path.join(root, "server", ".venv")
    python = env_python(local)
    if probe(python) is None:
        raise SetupError("Середовище програми не запускається. Запустіть install_windows.bat.")
    shared_python = thin_target(local)
    if is_thin(local) and not os.path.isfile(shared_python):
        raise SetupError("Не знайдено спільну папку бібліотек. Запустіть install_windows.bat.")
    target = shared_python or python  # pip must work where the libraries really are
    target_env = os.path.dirname(os.path.dirname(target))

    say("[1/4] Версія CUDA драйвера NVIDIA...")
    smi = find_nvidia_smi()
    say(f"    nvidia-smi: {smi or 'не знайдено'};  підтримувана драйвером CUDA: {cuda_major() or 'невідомо'}")

    say("")
    say(f"[2/4] Перевстановлюємо onnxruntime-gpu (CUDA) у {target_env} ...")
    if not ensure_pip(target):
        raise SetupError("У середовищі немає pip і його не вдалося додати. Запустіть install_windows.bat.")
    if not install_onnxruntime(target):
        raise SetupError("Не вдалося встановити ONNX Runtime. Перевірте інтернет.")
    rc, out = run([python, "-c", "import onnxruntime as o; print('    Встановлено onnxruntime:', o.__version__, o.get_available_providers())"],
                  capture=True, timeout=600)
    say(out.rstrip())
    if os.path.isfile(marker_path(target_env)):
        write_marker(target_env, probe(target) or {"version": sys.version_info[:3]})

    say("")
    say("[3/4] Перевіряємо AI-моделі...")
    models_dir = step_models(root)
    if not models_dir:
        raise SetupError("Не вдалося отримати AI-моделі. Перевірте інтернет-з'єднання.")

    say("")
    say("[4/4] Тестуємо реальний прогін обох моделей на відеокарті...")
    return 0 if step_gpu_check(python, root, models_dir, full_test=True) else 1


def cmd_info(root: str) -> int:
    settings = cvpaths.read_settings(root)
    base = base_python()
    local = os.path.join(root, "server", ".venv")
    say(f"  Clean Vinyl Pro 2 v{program_version()}   папка програми: {root}")
    say(f"  {cvpaths.SETTINGS_NAME}: " + ", ".join(f"{k}={settings[k] or '(порожньо)'}" for k in cvpaths.KEYS))
    say(f"  Python, яким запущено: {base}")
    kind = "немає" if not os.path.isdir(local) else ("вказує на спільні бібліотеки" if is_thin(local) else
                                                      ("власні бібліотеки" if is_full(local) else "порожнє"))
    info = probe(env_python(local))
    say(f"  server/.venv: {kind}; " + ("не запускається" if info is None else
                                        ("усі бібліотеки на місці" if not info["missing"] else "бракує: " + ", ".join(info["missing"]))))
    if settings["LIBS_DIR"]:
        for env_dir in sorted(glob.glob(os.path.join(settings["LIBS_DIR"], "py3*"))):
            shared = probe(env_python(env_dir))
            state = "не запускається" if shared is None else ("повне" if not shared["missing"] else "бракує: " + ", ".join(shared["missing"]))
            say(f"  спільне середовище {env_dir}: {state}, {fmt_size(folder_size(env_dir))}")
    models_dir = cvpaths.resolve_models_dir(root)
    missing = download_models.missing_models(models_dir)
    say(f"  AI-моделі: {models_dir}  ->  " + ("усі на місці" if not missing else "бракує: " + ", ".join(missing)))
    problem = cvpaths.models_problem(root)
    if problem:
        say("  " + problem)
    return 0


def main(argv=None) -> int:
    global _log_path, _interactive
    argv = list(sys.argv[1:] if argv is None else argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass
    flags = {a for a in argv if a.startswith("--")}
    words = [a for a in argv if not a.startswith("--")]
    command = words[0] if words else "install"
    root = os.path.abspath(words[1]) if len(words) > 1 else cvpaths.app_root()
    _interactive = "--yes" not in flags and sys.stdin is not None and sys.stdin.isatty()
    if command != "info":
        _log_path = os.path.join(root, "server", LOG_NAME)
        try:
            if os.path.getsize(_log_path) > 512 * 1024:
                os.remove(_log_path)
        except OSError:
            pass
        say("")
        say(f"===== {time.strftime('%Y-%m-%d %H:%M:%S')}  setup_env.py {' '.join(argv)} =====")
    try:
        if command == "install":
            return cmd_install(root, "--skip-gpu-check" in flags, "--skip-launcher" in flags)
        if command == "gpu":
            return cmd_gpu(root)
        if command == "info":
            return cmd_info(root)
        say(f"Невідома команда: {command}  (install | gpu | info)")
        return 2
    except SetupError as exc:
        say("")
        say(f"[ПОМИЛКА] {exc}")
        return 1
    except KeyboardInterrupt:
        say("")
        say("[Перервано]")
        return 130


if __name__ == "__main__":
    sys.exit(main())
