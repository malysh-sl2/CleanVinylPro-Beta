"""
Checks of everything around installing Clean Vinyl Pro 2 (used by run_checks.py, groups `folders`, `install`, `bat`).

  folders   folders.ini is read the same way by Python and by install_windows.bat; the AI models are found in the
            shared folder (also inside a sub-folder), a missing file is copied from another copy of the program
            and only then downloaded; the questions the installer asks.
  install   server/setup_env.py is really run, the way install_windows.bat runs it, in a sandbox that imitates
            a PC: a shared folder, two copies of the program, the old program next to them. pip works from a
            local folder of stand-in packages, so nothing needs the internet. Checked: the libraries are put once
            into the shared folder, a second copy of the program installs without pip, a moved Python is
            re-linked without re-installing, libraries are copied from another copy of the program, an
            interrupted installation is redone, the fall-back to the program folder.
  bat       the .bat files cannot be run here (no Windows), so they are read: brackets, labels, text that cmd.exe
            would take for a command, the little Python programs written inside them.

These checks imitate Windows on Linux. What stays unchecked is said in tests/README.md.
"""
import ast
import builtins
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

sys.dont_write_bytecode = True

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(REPO_ROOT, "CleanVinylPro2")
SERVER_DIR = os.path.join(APP_DIR, "server")
# What is kept of the original program (v3.2.1; its folder left the repository in version 4.3.0): the files the
# checks compare with, exactly as they were.
BASELINE_DIR = os.path.join(REPO_ROOT, "tests", "baseline_v321")
# The Python environment of the original program on the owner's PC: Windows layout, real file names (no contents)
OLD_ENV_FILES = (
    "Lib/site-packages/numpy/__init__.py", "Lib/site-packages/numpy/_core/_multiarray_umath.cp312-win_amd64.pyd",
    "Lib/site-packages/cv2/__init__.py", "Lib/site-packages/PIL/__init__.py", "Lib/site-packages/fastapi/__init__.py",
    "Lib/site-packages/uvicorn/__init__.py", "Lib/site-packages/onnxruntime/__init__.py",
    "Lib/site-packages/onnxruntime/capi/onnxruntime_providers_shared.dll",
    "Lib/site-packages/onnxruntime/capi/onnxruntime_providers_tensorrt.dll",
)
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

MODEL_BRIA, MODEL_LAMA = "bria-rmbg-2.0.onnx", "lama_fp32.onnx"
# The paths the owner of the program named: they must be exactly what the shipped folders.ini says.
SHIPPED = {"MODELS_DIR": r"D:\model AI fotoshop",
           "PYTHON_DIR": r"C:\Users\malys\AppData\Local\Programs\Python\Python312",
           "LIBS_DIR": r"D:\model AI fotoshop\CleanVinyl_python_libs"}


def _base_python() -> str:
    """The plain Python (install_windows.bat starts setup_env.py with one, never with a virtual environment)."""
    cand = getattr(sys, "_base_executable", "") or sys.executable
    return cand if os.path.isfile(cand) else sys.executable


# ----------------------------------------------------------------------------------------------------------------------
# Sandbox helpers
# ----------------------------------------------------------------------------------------------------------------------
def make_wheel(folder, dist, version, module, source, extras=()):
    """A tiny installable package, so that the real pip can run without the internet."""
    os.makedirs(folder, exist_ok=True)
    norm = dist.replace("-", "_")
    info = f"{norm}-{version}.dist-info"
    meta = f"Metadata-Version: 2.1\nName: {dist}\nVersion: {version}\n" + "".join(f"Provides-Extra: {e}\n" for e in extras)
    files = {f"{module}/__init__.py": source, f"{info}/METADATA": meta,
             f"{info}/WHEEL": "Wheel-Version: 1.0\nGenerator: cv-test\nRoot-Is-Purelib: true\nTag: py3-none-any\n"}
    record = "".join(f"{name},,\n" for name in files) + f"{info}/RECORD,,\n"
    with zipfile.ZipFile(os.path.join(folder, f"{norm}-{version}-py3-none-any.whl"), "w") as z:
        for name, text in files.items():
            z.writestr(name, text)
        z.writestr(f"{info}/RECORD", record)


def make_wheelhouse(folder):
    for dist, module in (("fastapi", "fastapi"), ("uvicorn", "uvicorn"), ("numpy", "numpy"),
                         ("opencv-python-headless", "cv2"), ("Pillow", "PIL")):
        make_wheel(folder, dist, "99.0", module, "__version__ = '99.0'\n")
    make_wheel(folder, "onnxruntime-gpu", "99.0", "onnxruntime",
               "__version__ = '99.0'\ndef get_available_providers():\n    return ['CUDAExecutionProvider', 'CPUExecutionProvider']\n",
               extras=("cuda", "cudnn"))
    make_wheel(folder, "onnxruntime", "98.0", "onnxruntime",
               "__version__ = '98.0'\ndef get_available_providers():\n    return ['CPUExecutionProvider']\n")
    return folder


def sparse(path, mb):
    """A file of the given size that takes no room on the disk."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.truncate(int(mb * 1024 * 1024))


def program_copy(dst):
    shutil.copytree(APP_DIR, dst, ignore=shutil.ignore_patterns("__pycache__", ".venv", ".venv_old", "models", "*.log",
                                                                "launch_server_minimized.vbs"))
    return dst


def set_ini(root, **kv):
    with open(os.path.join(root, "folders.ini"), "w", encoding="utf-8", newline="") as f:
        f.write("; test\r\n" + "".join(f"{k}={v}\r\n" for k, v in kv.items()))


def site_of(env_dir):
    hits = [p for p in (os.path.join(env_dir, "Lib", "site-packages"),) if os.path.isdir(p)]
    for name in sorted(os.listdir(os.path.join(env_dir, "lib"))) if os.path.isdir(os.path.join(env_dir, "lib")) else []:
        hits.append(os.path.join(env_dir, "lib", name, "site-packages"))
    return hits[0]


def env_python(env_dir):
    return os.path.join(env_dir, "Scripts", "python.exe") if os.name == "nt" else os.path.join(env_dir, "bin", "python")


def tree_stamp(folder):
    """Names, sizes and modification times of everything in a folder: equal stamps = nothing was touched."""
    h = hashlib.sha256()
    for base, dirs, files in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for name in sorted(files):
            st = os.stat(os.path.join(base, name))
            h.update(f"{os.path.relpath(os.path.join(base, name), folder)}|{st.st_size}|{st.st_mtime_ns}\n".encode())
    return h.hexdigest()


class Sandbox:
    """One imitated PC: <tmp>/D/model AI fotoshop (shared), <tmp>/D/<program folders>, <tmp>/home."""

    def __init__(self, tmp, wheelhouse):
        self.tmp = tmp
        self.wheelhouse = wheelhouse
        self.empty = os.path.join(tmp, "no-packages-here")
        os.makedirs(self.empty, exist_ok=True)
        self.home = os.path.join(tmp, "home")
        os.makedirs(self.home, exist_ok=True)
        self.drive = os.path.join(tmp, "D")
        self.shared = os.path.join(self.drive, "model AI fotoshop")
        self.libs = os.path.join(self.shared, "CleanVinyl_python_libs")
        self.tag = f"py{sys.version_info[0]}{sys.version_info[1]}"
        self.shared_env = os.path.join(self.libs, self.tag)

    def env(self, internet=True):
        """Environment of the installer; internet=False: pip finds nothing at all (any pip install must fail)."""
        e = {k: v for k, v in os.environ.items() if not k.startswith(("PIP_", "CLEANVINYL_", "PYTHON", "VIRTUAL_ENV"))}
        e.update(PIP_NO_INDEX="1", PIP_FIND_LINKS=self.wheelhouse if internet else self.empty, HOME=self.home,
                 PIP_DISABLE_PIP_VERSION_CHECK="1", PIP_NO_CACHE_DIR="1")
        return e

    def program(self, name="CleanVinylPro2", models=True, libs=True, **ini):
        root = program_copy(os.path.join(self.drive, name))
        values = {"MODELS_DIR": self.shared if models else "", "PYTHON_DIR": "", "LIBS_DIR": self.libs if libs else ""}
        values.update(ini)
        set_ini(root, **values)
        return root

    def models(self, folder=None, names=(MODEL_BRIA, MODEL_LAMA)):
        folder = folder or self.shared
        for name, mb in ((MODEL_BRIA, 501), (MODEL_LAMA, 181)):
            if name in names:
                sparse(os.path.join(folder, name), mb)

    def install(self, root, internet=True, python=None, command="install", extra_env=None):
        flags = ["--yes", "--skip-gpu-check"] if command == "install" else ["--yes"]
        t0 = time.perf_counter()
        try:
            r = subprocess.run([python or _base_python(), os.path.join(root, "server", "setup_env.py"), command, *flags],
                               env=dict(self.env(internet), **(extra_env or {})), capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
        except OSError as exc:  # the python that should run it does not exist: a failed run, reported by the caller
            return 9001, f"cannot start: {exc}", time.perf_counter() - t0
        return r.returncode, r.stdout + r.stderr, time.perf_counter() - t0

    def full_venv(self, env_dir):
        """An environment with its own libraries, like the ones the earlier versions of the installer made."""
        subprocess.run([_base_python(), "-m", "venv", env_dir], check=True, capture_output=True)
        subprocess.run([env_python(env_dir), "-m", "pip", "install", "-q", "fastapi", "uvicorn", "numpy",
                        "opencv-python-headless", "Pillow", "onnxruntime-gpu[cuda,cudnn]"],
                       check=True, capture_output=True, env=self.env(True))
        return env_dir


def _run(cmd):
    """subprocess.run that reports a program that cannot start as a failed run instead of raising."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except OSError as exc:
        return subprocess.CompletedProcess(cmd, 9001, "", str(exc))


def sees_libs_from(python, env=None):
    """Where the python of a program folder takes numpy from ('' when it cannot import the libraries)."""
    code = ("import numpy, cv2, PIL, fastapi, uvicorn, onnxruntime, os;"
            "print('FROM=' + os.path.dirname(os.path.dirname(os.path.abspath(numpy.__file__))))")
    try:
        r = subprocess.run([python, "-c", code], capture_output=True, text=True, env=env)
    except OSError:  # the python of the environment does not even start
        return ""
    m = re.search(r"FROM=(.*)", r.stdout)
    return m.group(1).strip() if r.returncode == 0 and m else ""


def own_libs(root):
    """Library folders lying inside the program folder itself."""
    env_dir = os.path.join(root, "server", ".venv")
    if not os.path.isdir(env_dir):
        return None
    return sorted(n for n in os.listdir(site_of(env_dir)) if n not in ("__pycache__",) and not n.startswith("cleanvinyl_shared_libs"))


def break_python(env_dir):
    """
    What a moved / re-installed Python looks like from an environment: the environment still names the old place
    (pyvenv.cfg: home = ...), so its python does not start. The libraries inside are intact.
    """
    gone = "/python-was-here-before-it-moved/bin"
    for name in sorted(os.listdir(os.path.join(env_dir, "bin"))):
        path = os.path.join(env_dir, "bin", name)
        if name.startswith("python"):
            os.remove(path)
            os.symlink(os.path.join(gone, "python3"), path)
    cfg = os.path.join(env_dir, "pyvenv.cfg")
    text = open(cfg, encoding="utf-8").read()
    text = re.sub(r"(?m)^home = .*$", f"home = {gone}", text)
    text = re.sub(r"(?m)^executable = .*$", f"executable = {gone}/python3", text)
    open(cfg, "w", encoding="utf-8").write(text)


# ----------------------------------------------------------------------------------------------------------------------
# folders: folders.ini, where the models are, what is copied / downloaded / asked
# ----------------------------------------------------------------------------------------------------------------------
def _bat_reads(ini_bytes: bytes, key: str) -> str:
    """What `findstr /b /i /c:"KEY=" folders.ini` + `for /f "tokens=1,* delims=="` + %%~b gives in install_windows.bat."""
    value = None
    for line in ini_bytes.split(b"\n"):
        line = line.rstrip(b"\r")
        if line[:len(key) + 1].upper() == (key + "=").encode():
            rest = line.split(b"=", 1)[1].lstrip(b"=").decode("utf-8", errors="replace")
            value = rest[1:-1] if len(rest) >= 2 and rest[0] == rest[-1] == '"' else rest
    return value


def check_folders(report):
    import cvpaths
    import download_models
    import setup_env
    bad = []
    tmp = tempfile.mkdtemp(prefix="cv_folders_")
    keep_env = {k: os.environ.pop(k) for k in list(os.environ) if k.startswith("CLEANVINYL_MODELS_DIR")}
    keep_env["HOME"] = os.environ.get("HOME", "")
    os.environ["HOME"] = tmp  # "install folders remembered on this PC" must come from the sandbox only
    try:
        # ---- the shipped file ----
        raw = open(os.path.join(APP_DIR, "folders.ini"), "rb").read()
        got = cvpaths.read_settings(APP_DIR)
        if got != SHIPPED:
            bad.append(f"shipped folders.ini says {got}")
        for key, want in SHIPPED.items():
            if _bat_reads(raw, key) != want:
                bad.append(f"install_windows.bat would read {key} as {_bat_reads(raw, key)!r}")
        if raw.startswith(b"\xef\xbb\xbf") or b'"' in raw or raw.count(b"\r\n") != raw.count(b"\n"):
            bad.append("shipped folders.ini: BOM, a quote character or a line without CRLF")
        for line in raw.decode("utf-8").splitlines():
            if line.strip() and not line.startswith(";") and not re.match(r"[A-Z_]+=", line):
                bad.append(f"shipped folders.ini: line is neither a comment nor KEY=value: {line[:40]!r}")

        # ---- reading what people really type ----
        root = os.path.join(tmp, "prog")
        os.makedirs(os.path.join(root, "server"))
        cases = [
            (b"\xef\xbb\xbf; c\r\nMODELS_DIR=D:\\model AI fotoshop\r\npython_dir = \"C:\\Py 312\\\"  \r\nLIBS_DIR=\r\n",
             {"MODELS_DIR": r"D:\model AI fotoshop", "PYTHON_DIR": r"C:\Py 312", "LIBS_DIR": ""}),
            ("; пояснення\nMODELS_DIR=D:\\Моделі\\\n# x\nLIBS_DIR='D:\\libs/'\nOTHER=1\n".encode("cp1251"),
             {"MODELS_DIR": "D:\\Моделі", "PYTHON_DIR": "", "LIBS_DIR": r"D:\libs"}),
            (b"MODELS_DIR=D:\\\r\n", {"MODELS_DIR": "D:\\", "PYTHON_DIR": "", "LIBS_DIR": ""}),
        ]
        for data, want in cases:
            with open(os.path.join(root, "folders.ini"), "wb") as f:
                f.write(data)
            if cvpaths.read_settings(root) != want:
                bad.append(f"read_settings({data[:30]!r}...) -> {cvpaths.read_settings(root)}")
        os.remove(os.path.join(root, "folders.ini"))
        if any(cvpaths.read_settings(root).values()):
            bad.append("a missing folders.ini must mean 'everything in the program folder'")

        # ---- writing one line leaves the rest alone ----
        before = b"\xef\xbb\xbf; \xd0\xbf\xd0\xbe\xd1\x8f\xd1\x81\xd0\xbd\xd0\xb5\xd0\xbd\xd0\xbd\xd1\x8f\r\nMODELS_DIR=D:\\a\r\n\r\n; two\r\nPYTHON_DIR=C:\\old\r\n"
        with open(os.path.join(root, "folders.ini"), "wb") as f:
            f.write(before)
        cvpaths.write_setting("python_dir", r"C:\new place", root)
        cvpaths.write_setting("LIBS_DIR", r"D:\libs", root)
        after = open(os.path.join(root, "folders.ini"), "rb").read()
        if after != before.replace(b"C:\\old", b"C:\\new place") + b"LIBS_DIR=D:\\libs\r\n":
            bad.append(f"write_setting changed more than its line: {after!r}")

        # ---- where the models are ----
        shared = os.path.join(tmp, "model AI fotoshop")
        local = cvpaths.local_models_dir(root)

        def ini(models=shared, libs=""):
            set_ini(root, MODELS_DIR=models, PYTHON_DIR="", LIBS_DIR=libs)

        def both(folder):
            sparse(os.path.join(folder, MODEL_BRIA), 501)
            sparse(os.path.join(folder, MODEL_LAMA), 181)

        ini()
        if cvpaths.resolve_models_dir(root) != local or not cvpaths.models_problem(root):
            bad.append("shared folder missing: the program folder must be used and the problem named")
        os.makedirs(shared)
        if cvpaths.resolve_models_dir(root) != shared or cvpaths.models_problem(root):
            bad.append("empty shared folder (and no models in the program): the shared folder is where they go")
        both(local)
        if cvpaths.resolve_models_dir(root) != local or cvpaths.install_models_dir(root) != shared:
            bad.append("shared folder still empty, models in the program folder: server uses them, installer fills the shared one")
        both(shared)
        if cvpaths.resolve_models_dir(root) != shared:
            bad.append("models in the shared folder are not preferred")
        shutil.rmtree(local)
        for sub in ("models", os.path.join("CleanVinyl", "models")):
            shutil.rmtree(shared)
            both(os.path.join(shared, sub))
            if cvpaths.resolve_models_dir(root) != os.path.join(shared, sub):
                bad.append(f"models inside {sub} of the shared folder are not found")
        shutil.rmtree(shared)
        both(os.path.join(shared, "a", "b", "c"))
        if cvpaths.resolve_models_dir(root) != shared:
            bad.append("models three folders deep must not be searched for")
        shutil.rmtree(shared)
        sparse(os.path.join(shared, MODEL_BRIA), 120)  # an interrupted download
        both(os.path.join(shared, "good"))
        if cvpaths.resolve_models_dir(root) != os.path.join(shared, "good") or cvpaths.model_ok(shared, MODEL_BRIA):
            bad.append("a cut-off model file is taken for a complete one")
        shutil.rmtree(shared)
        libs = os.path.join(shared, "CleanVinyl_python_libs")
        for trap in (libs, os.path.join(shared, "Python312")):  # models are never looked for inside Python folders
            both(os.path.join(trap, "x"))
        open(os.path.join(shared, "Python312", "python.exe"), "w").close()
        ini(libs=libs)
        if cvpaths.resolve_models_dir(root) != shared or any("Python312" in f or "python_libs" in f for f in cvpaths.model_folders(shared, (libs,))):
            bad.append("the libraries folder / a Python folder inside the shared folder is searched for models")
        os.environ["CLEANVINYL_MODELS_DIR"] = os.path.join(tmp, "forced")
        if cvpaths.resolve_models_dir(root) != os.path.join(tmp, "forced") or cvpaths.install_models_dir(root) != os.path.join(tmp, "forced"):
            bad.append("CLEANVINYL_MODELS_DIR is not honoured")
        del os.environ["CLEANVINYL_MODELS_DIR"]

        # ---- other copies of the program on the PC ----
        shutil.rmtree(shared)
        os.makedirs(shared)
        ini()
        old_prog = os.path.join(tmp, "CleanVinylPro")
        sparse(os.path.join(old_prog, "server", "models", MODEL_LAMA), 181)
        os.makedirs(os.path.join(tmp, "Photos"))
        roots = cvpaths.other_install_roots(root)
        if roots != [old_prog]:
            bad.append(f"other copies of the program: {roots}")
        if os.path.join(old_prog, "server", "models") not in cvpaths.model_sources(root, exclude=shared):
            bad.append("the models folder of the old program is not offered as a source")

        # ---- a missing model: copy first, download only when there is no copy ----
        calls = []

        def fake_download(url, dest):
            calls.append(url)
            if "fail" in os.environ.get("CV_TEST_DL", "") and len(calls) == 1:
                return False
            sparse(dest, 501 if "bria" in dest else 181)
            return True

        real_download, download_models.download_file = download_models.download_file, fake_download
        real_stdout = sys.stdout
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
        try:
            sparse(os.path.join(shared, MODEL_BRIA), 501)
            ok = download_models.ensure_models(shared, False, cvpaths.model_sources(root, exclude=shared))
            if not ok or calls or not cvpaths.model_ok(shared, MODEL_LAMA):
                bad.append(f"a model lying in the old program was not copied (downloads: {len(calls)})")
            if not cvpaths.model_ok(os.path.join(old_prog, "server", "models"), MODEL_LAMA):
                bad.append("copying a model damaged the old program")
            ok = download_models.ensure_models(shared, False, cvpaths.model_sources(root, exclude=shared))
            if not ok or calls:
                bad.append("complete models were downloaded again")
            os.remove(os.path.join(shared, MODEL_LAMA))
            shutil.rmtree(old_prog)
            ok = download_models.ensure_models(shared, False, cvpaths.model_sources(root, exclude=shared))
            if not ok or len(calls) != 1 or "lama_fp32" not in calls[0] or not cvpaths.model_ok(shared, MODEL_LAMA):
                bad.append(f"a model that is nowhere on the PC must be downloaded once into the shared folder: {calls}")
            if download_models.missing_models(shared) or download_models.missing_models(os.path.join(tmp, "nowhere")) != [MODEL_BRIA, MODEL_LAMA]:
                bad.append("missing_models")

            # ---- the questions of the installer ----
            answers, asked = [], []

            def fake_input(prompt=""):
                asked.append(prompt)
                return answers.pop(0) if answers else ""

            real_input, builtins.input = builtins.input, fake_input
            setup_env._interactive, setup_env._log_path = True, None
            try:
                # the folder named in folders.ini does not exist; the user names the right one
                wrong = os.path.join(tmp, "model AI photoshop")
                ini(models=wrong)
                answers[:] = ['"' + shared + '"']
                calls.clear()
                got_dir = setup_env.step_models(root)
                if got_dir != shared or calls or cvpaths.read_settings(root)["MODELS_DIR"] != shared or os.path.isdir(wrong):
                    bad.append(f"wrong MODELS_DIR + the right folder typed in: got {got_dir}, downloads {len(calls)}")
                # ... or presses Enter: the folder is created and filled once
                ini(models=wrong)
                answers[:] = [""]
                calls.clear()
                got_dir = setup_env.step_models(root)
                if got_dir != wrong or len(calls) != 2 or download_models.missing_models(wrong):
                    bad.append(f"wrong MODELS_DIR + Enter: got {got_dir}, downloads {len(calls)}")
                # the folder exists but is empty and there is no copy anywhere: ask before downloading 1.2 GB
                empty = os.path.join(tmp, "empty shared")
                os.makedirs(empty)
                ini(models=empty)
                answers[:] = [shared]
                asked.clear()
                calls.clear()
                got_dir = setup_env.step_models(root)
                if got_dir != shared or calls or len(asked) != 1:
                    bad.append(f"empty shared folder: the installer must ask first (asked {len(asked)}, downloads {len(calls)})")
                # without a keyboard nothing is asked
                setup_env._interactive = False
                ini(models=empty)
                asked.clear()
                calls.clear()
                got_dir = setup_env.step_models(root)
                if got_dir != empty or asked or len(calls) != 2:
                    bad.append("without a keyboard the installer must not wait for an answer")
            finally:
                builtins.input = real_input
                setup_env._interactive = False
        finally:
            sys.stdout.close()
            sys.stdout = real_stdout
            download_models.download_file = real_download
    finally:
        os.environ.update(keep_env)
        shutil.rmtree(tmp, ignore_errors=True)
    report("folders", not bad, "folders.ini (shipped: models in D:\\model AI fotoshop, Python in ...\\Python312) is read alike by Python "
                               "and by the .bat; models found in the shared folder and its sub-folders; a missing one is copied, "
                               "then downloaded; the installer asks before a 1.2 GB download" if not bad else f"wrong: {bad}")


# ----------------------------------------------------------------------------------------------------------------------
# install: setup_env.py really run in an imitated PC
# ----------------------------------------------------------------------------------------------------------------------
def _unit_checks(bad):
    """Pieces that can be checked without running the installer; the real old environment of the repository is used."""
    import setup_env as S
    if S.onnxruntime_specs(13)[0] != ["--upgrade", "onnxruntime-gpu[cuda,cudnn]>=1.27.0"] or \
            S.onnxruntime_specs(12)[0] != ["onnxruntime-gpu[cuda,cudnn]==1.26.0"] or \
            S.onnxruntime_specs(0)[0] != ["onnxruntime-gpu[cuda,cudnn]>=1.27.0"] or S.onnxruntime_specs(14)[-1] != ["onnxruntime-gpu"]:
        bad.append("the choice of ONNX Runtime by CUDA version changed")
    reqs = S.read_requirements(os.path.join(SERVER_DIR, "requirements.txt"))
    if [r[0] for r in reqs] != ["fastapi", "uvicorn", "numpy", "opencv-python-headless", "Pillow"] or reqs[2][1] != (1, 26, 0):
        bad.append(f"requirements.txt is read as {reqs}")
    have = {"versions": {"fastapi": "0.162.4", "uvicorn": "0.31.9", "numpy": "2.5.4", "opencv-python-headless": "", "Pillow": "13.0.0"}}
    if S.unsatisfied(have, reqs) != ["uvicorn>=0.32.0", "opencv-python-headless>=4.10.0"]:
        bad.append(f"unsatisfied requirements: {S.unsatisfied(have, reqs)}")
    if S.py_tag((3, 12, 10)) != "py312":
        bad.append("py_tag")

    # the environment of the original program as the owner's PC has it: its real pyvenv.cfg in the Windows layout
    old_cfg = os.path.join(BASELINE_DIR, "pyvenv.cfg")
    if not os.path.isfile(old_cfg):
        bad.append("tests/baseline_v321/pyvenv.cfg is missing")
    else:
        old_env = tempfile.mkdtemp(prefix="cv_oldenv_")
        shutil.copy(old_cfg, old_env)
        for rel in OLD_ENV_FILES:
            os.makedirs(os.path.dirname(os.path.join(old_env, rel)), exist_ok=True)
            open(os.path.join(old_env, rel), "wb").close()
        site = S.guess_site_packages(old_env)
        info = S.donor_info(old_env)
        if not site.endswith(os.path.join("Lib", "site-packages")) or S.cfg_tag(old_env) != "py312" or S.files_tag(site) != "py312":
            bad.append(f"the real environment of the old program is not understood: {site}, {S.cfg_tag(old_env)}, {S.files_tag(site)}")
        if info is None or info["tag"] != "py312" or S.is_thin(old_env) or not S.is_full(old_env):
            bad.append(f"the real environment of the old program is not accepted as a source of libraries: {info}")
        elif info["cuda"]:
            bad.append("that environment has no CUDA provider file, yet one was reported")
        if not S.other_version(old_env, "py313") or S.other_version(old_env, "py312"):
            bad.append("other_version on the real environment")
        tmp = tempfile.mkdtemp(prefix="cv_cfg_")
        try:
            shutil.copy(os.path.join(old_env, "pyvenv.cfg"), tmp)
            new_py = r"C:\Users\malys\AppData\Local\Programs\Python\Python312\python.exe"
            S.relink_cfg(tmp, new_py, home=new_py.rsplit("\\", 1)[0])  # (os.path.dirname of a Windows path needs Windows)
            cfg = open(os.path.join(tmp, "pyvenv.cfg"), encoding="utf-8").read()
            if "home = C:\\Users\\malys\\AppData\\Local\\Programs\\Python\\Python312\n" not in cfg or f"executable = {new_py}\n" not in cfg \
                    or "version = 3.12.10" not in cfg or "include-system-site-packages = false" not in cfg or "C:\\python.exe" in cfg.replace(new_py, ""):
                bad.append(f"pyvenv.cfg of the old program after re-linking: {cfg!r}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
            shutil.rmtree(old_env, ignore_errors=True)

    # copying the libraries of another copy of the program: all or nothing
    tmp = tempfile.mkdtemp(prefix="cv_adopt_")
    keep_out, keep_copy = sys.stdout, shutil.copy2
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
    try:
        donor, target = os.path.join(tmp, "donor"), os.path.join(tmp, "target")
        for rel, size in (("numpy/__init__.py", 10), ("numpy/core/big.dll", 300_000), ("numpy/__pycache__/x.pyc", 50),
                          ("nvidia/cudnn/bin/cudnn.dll", 500_000), ("pip/__init__.py", 5), ("pip-24.0.dist-info/METADATA", 5),
                          ("numpy-2.0.dist-info/METADATA", 20), ("six.py", 7), ("sitecustomize.py", 3),
                          (S.THIN_NAME + ".py", 3), (S.THIN_NAME + ".pth", 3), ("setuptools/__init__.py", 9)):
            os.makedirs(os.path.dirname(os.path.join(donor, rel)), exist_ok=True)
            with open(os.path.join(donor, rel), "wb") as f:
                f.write(b"d" * size)
        os.makedirs(os.path.join(target, "setuptools"))
        with open(os.path.join(target, "setuptools", "__init__.py"), "wb") as f:
            f.write(b"own")

        def lossy_copy(src, dst):  # a copy that silently loses the end of one big file
            keep_copy(src, dst)
            if src.endswith("cudnn.dll"):
                with open(dst, "r+b") as f:
                    f.truncate(1000)

        shutil.copy2 = lossy_copy
        if S.adopt({"site": donor, "env": donor}, target) or sorted(os.listdir(target)) != ["setuptools"]:
            bad.append(f"a copy that lost bytes was accepted or left pieces behind: {sorted(os.listdir(target))}")
        shutil.copy2 = keep_copy
        ok = S.adopt({"site": donor, "env": donor}, target)
        got = sorted(os.path.relpath(os.path.join(b, n), target).replace(os.sep, "/") for b, _d, fs in os.walk(target) for n in fs)
        want = ["numpy-2.0.dist-info/METADATA", "numpy/__init__.py", "numpy/core/big.dll", "nvidia/cudnn/bin/cudnn.dll",
                "setuptools/__init__.py", "six.py"]
        if not ok or got != want or open(os.path.join(target, "setuptools", "__init__.py"), "rb").read() != b"own" \
                or os.path.getsize(os.path.join(target, "nvidia", "cudnn", "bin", "cudnn.dll")) != 500_000:
            bad.append(f"copying libraries: ok={ok}, files {got}")
    finally:
        shutil.copy2 = keep_copy
        sys.stdout.close()
        sys.stdout = keep_out
        shutil.rmtree(tmp, ignore_errors=True)

    # the pointer module: valid Python for any path, and the path can be read back
    for site, python in ((r"D:\model AI fotoshop\CleanVinyl_python_libs\py312\Lib\site-packages",
                          r"D:\model AI fotoshop\CleanVinyl_python_libs\py312\Scripts\python.exe"),
                         ("D:\\Моделі «AI»\\it's\\libs", "D:\\Моделі «AI»\\it's\\python.exe")):
        text = S.thin_module(site, python)
        try:
            tree = ast.parse(text)
            values = {t.targets[0].id: ast.literal_eval(t.value) for t in tree.body if isinstance(t, ast.Assign)}
        except Exception as exc:
            bad.append(f"pointer module is not valid Python for {site!r}: {exc}")
            continue
        if values != {"SHARED_SITE_PACKAGES": site, "SHARED_PYTHON": python} or not text.startswith(S.THIN_MARK) \
                or any(ord(c) > 127 for line in text.splitlines() if line.startswith("SHARED_") for c in line):
            bad.append(f"pointer module does not carry the path {site!r} safely")


def _pc_empty(tmp, wheelhouse, report):
    import cvpaths
    import setup_env as S
    # ---- PC 1: nothing installed yet; then a second copy; then Python "moves" ---------------------------------
    bad, pc = [], Sandbox(os.path.join(tmp, "pc1"), wheelhouse)
    pc.models()
    prog = pc.program()
    rc, out, _ = pc.install(prog)
    py = env_python(os.path.join(prog, "server", ".venv"))
    shared_site = site_of(pc.shared_env) if os.path.isdir(pc.shared_env) else ""
    if rc != 0 or sees_libs_from(py) != shared_site or not shared_site:
        bad.append(f"first installation: exit {rc}, libraries seen from {sees_libs_from(py)!r}\n{out[-1500:]}")
    if own_libs(prog):
        bad.append(f"libraries were put into the program folder: {own_libs(prog)}")
    if not os.path.isfile(os.path.join(pc.shared_env, S.ENV_MARKER)) or os.path.isdir(os.path.join(prog, "server", "models")):
        bad.append("no 'complete' mark in the shared folder, or a models folder appeared in the program")
    if f"AI-моделі:   {pc.shared}" not in out or not os.path.isfile(os.path.join(prog, "server", "install.log")):
        bad.append("the summary does not name the shared models folder, or no install.log")
    if cvpaths.read_settings(prog)["PYTHON_DIR"] != os.path.dirname(_base_python()):
        bad.append("the real place of Python was not written into folders.ini")
    if bad:
        report("install", False, "empty PC, first installation - wrong: " + "\n".join(bad))
        return
    stamp = tree_stamp(pc.shared_env)

    rc, out, sec = pc.install(prog, internet=False)
    if rc != 0 or "нічого не завантажуємо" not in out or tree_stamp(pc.shared_env) != stamp:
        bad.append(f"second run must change nothing and need no pip: exit {rc}\n{out[-800:]}")

    prog_b = pc.program("CleanVinylPro2 v4.3")
    rc, out, sec_b = pc.install(prog_b, internet=False)
    py_b = env_python(os.path.join(prog_b, "server", ".venv"))
    if rc != 0 or sees_libs_from(py_b) != shared_site or own_libs(prog_b) or tree_stamp(pc.shared_env) != stamp:
        bad.append(f"a second copy of the program must install without pip and without touching the shared folder: exit {rc}\n{out[-800:]}")

    code = ("import os, sys; src = open(os.path.join(sys.argv[1], 'engine.py'), encoding='utf-8').read(); ns = {}; "
            "exec(src[src.index('def _pip_python'):src.index('def _import_or_install_ort')], {'os': os, 'sys': sys}, ns); "
            "print('PIP=' + ns['_pip_python']())")
    r = _run([py, "-c", code, os.path.join(prog, "server")])
    if f"PIP={env_python(pc.shared_env)}" not in r.stdout:
        bad.append(f"engine.py would install a missing package into the program folder: {r.stdout.strip()} {r.stderr.strip()[-200:]}")

    break_python(pc.shared_env)
    break_python(os.path.join(prog, "server", ".venv"))
    if sees_libs_from(py):
        bad.append("the imitation of a moved Python does not break the environment")
    rc, out, _ = pc.install(prog, internet=False)
    if rc != 0 or "оновлюємо посилання" not in out or sees_libs_from(py) != shared_site or own_libs(prog):
        bad.append(f"moved Python: environments must be re-linked without pip: exit {rc}\n{out[-1200:]}")
    lib_files = lambda: tree_stamp(os.path.join(shared_site, "numpy")) + tree_stamp(os.path.join(shared_site, "onnxruntime"))
    if sees_libs_from(py_b) != shared_site:
        bad.append("after re-linking, the other copy of the program lost the shared libraries")
    kept = lib_files()

    # the repair of the video card libraries goes into the shared folder, not into the program
    rc, out, _ = pc.install(prog, python=py, command="gpu")
    if "Successfully installed onnxruntime-gpu-99.0" not in out or own_libs(prog) or sees_libs_from(py) != shared_site \
            or "Тестуємо реальний прогін" not in out or f"у {pc.shared_env}" not in out:
        bad.append(f"fix_gpu_cuda: ONNX Runtime must be re-installed in the shared folder\n{out[-1200:]}")
    if tree_stamp(os.path.join(shared_site, "numpy")) + tree_stamp(os.path.join(shared_site, "onnxruntime")) == kept:
        bad.append("fix_gpu_cuda did not re-install ONNX Runtime")

    # the shared folder disappears (drive unplugged): a clear message, no crash of Python itself
    os.rename(pc.libs, pc.libs + " (gone)")
    r = _run([py, "-c", "print('alive')"])
    if r.returncode != 0 or "alive" not in r.stdout or "LIBS_DIR" not in r.stderr or "folders.ini" not in r.stderr:
        bad.append(f"shared folder gone: expected a hint on stderr, got {r.stderr[-300:]!r}")
    os.rename(pc.libs + " (gone)", pc.libs)
    report("install", not bad, f"empty PC: libraries go once into the shared folder, the program folder keeps none; a second run and "
                               f"a second copy of the program need no pip ({sec:.1f} s / {sec_b:.1f} s); a moved Python is re-linked, "
                               f"libraries untouched; GPU repair works in the shared folder" if not bad else "wrong: " + "\n".join(bad))


def _pc_with_old_program(tmp, wheelhouse, report):
    import cvpaths
    import setup_env as S
    # ---- PC 2: the old program is installed; the new one must take its libraries and models, without internet ---
    bad, pc = [], Sandbox(os.path.join(tmp, "pc2"), wheelhouse)
    old_prog = os.path.join(pc.drive, "CleanVinylPro")
    pc.full_venv(os.path.join(old_prog, "server", ".venv"))
    pc.models(os.path.join(old_prog, "server", "models"), names=(MODEL_LAMA,))
    pc.models(names=(MODEL_BRIA,))
    old_stamp = tree_stamp(old_prog)
    prog = pc.program()
    rc, out, _ = pc.install(prog, internet=False)
    py = env_python(os.path.join(prog, "server", ".venv"))
    shared_site = site_of(pc.shared_env) if os.path.isdir(pc.shared_env) else ""
    if rc != 0 or "Копіюємо бібліотеки" not in out or sees_libs_from(py) != shared_site or own_libs(prog):
        bad.append(f"libraries of the old program were not re-used: exit {rc}\n{out[-1500:]}")
    if tree_stamp(old_prog) != old_stamp:
        bad.append("the old program was changed")
    if not cvpaths.model_ok(pc.shared, MODEL_LAMA) or "[Копіювання]" not in out or "[Завантаження]" in out:
        bad.append("the model lying in the old program was not copied into the shared folder")
    if "pip" in (os.listdir(shared_site) if shared_site else []) and not os.path.isdir(os.path.join(shared_site, "numpy-99.0.dist-info")):
        bad.append("the copied libraries are not registered (pip would download them again)")

    # ---- PC 3: this folder was installed by an earlier version (its own full environment) -----------------------
    pc3 = Sandbox(os.path.join(tmp, "pc3"), wheelhouse)
    pc3.models()
    prog3 = pc3.program()
    pc3.full_venv(os.path.join(prog3, "server", ".venv"))
    py3 = env_python(os.path.join(prog3, "server", ".venv"))
    break_python(os.path.join(prog3, "server", ".venv"))  # and Python was moved since then
    rc, out, _ = pc3.install(prog3, internet=False)
    shared_site3 = site_of(pc3.shared_env) if os.path.isdir(pc3.shared_env) else ""
    if rc != 0 or sees_libs_from(py3) != shared_site3 or own_libs(prog3) or os.path.exists(os.path.join(prog3, "server", ".venv_old")) \
            or "прибрано" not in out:
        bad.append(f"upgrade of a folder with its own libraries: exit {rc}, own libraries left: {own_libs(prog3)}\n{out[-1500:]}")

    # an installation interrupted while the libraries were being copied is started again, not trusted
    if not os.path.isfile(os.path.join(pc3.shared_env, S.ENV_MARKER)):
        bad.append("no 'complete' mark after the upgrade of a folder with its own libraries")
    else:
        os.remove(os.path.join(pc3.shared_env, S.ENV_MARKER))
        shutil.rmtree(os.path.join(shared_site3, "cv2"))
        rc, out, _ = pc3.install(prog3, internet=True)
        if rc != 0 or "перерване" not in out or sees_libs_from(py3) != shared_site3:
            bad.append(f"interrupted installation: exit {rc}\n{out[-1200:]}")
    _fallback_gives_libraries_back(tmp, wheelhouse, bad)
    _asks_before_library_download(tmp, wheelhouse, bad)
    report("install", not bad, "PC with the old program: its libraries and model are copied (no internet needed), the old program is "
                               "untouched; a folder with its own libraries is switched to the shared ones (and gets them back "
                               "if the switch fails half-way); an interrupted installation is redone; before a download of the "
                               "libraries the installer asks, and copies them from the folder that was named"
           if not bad else "wrong: " + "\n".join(bad))


def _pc_classic(tmp, wheelhouse, report):
    import setup_env as S
    # ---- PC 4: without shared folders, and the fall-back --------------------------------------------------------
    bad, pc = [], Sandbox(os.path.join(tmp, "pc4"), wheelhouse)
    prog = pc.program(models=False, libs=False)
    pc.models(os.path.join(prog, "server", "models"))
    rc, out, _ = pc.install(prog)
    py = env_python(os.path.join(prog, "server", ".venv"))
    if rc != 0 or sees_libs_from(py) != site_of(os.path.join(prog, "server", ".venv")) or os.path.exists(pc.shared) \
            or f"AI-моделі:   {os.path.join(prog, 'server', 'models')}" not in out:
        bad.append(f"empty folders.ini lines must give the classic layout: exit {rc}\n{out[-1200:]}")
    rc, out, _ = pc.install(prog, internet=False)
    if rc != 0 or "нічого не завантажуємо" not in out:
        bad.append(f"classic layout, second run: exit {rc}\n{out[-600:]}")
    break_python(os.path.join(prog, "server", ".venv"))
    rc, out, _ = pc.install(prog, internet=False)
    if rc != 0 or "оновлюємо посилання" not in out or sees_libs_from(py) != site_of(os.path.join(prog, "server", ".venv")):
        bad.append(f"classic layout, moved Python: exit {rc}\n{out[-1200:]}")

    blocker = os.path.join(pc.drive, "not a folder")
    open(blocker, "w").close()
    prog2 = pc.program("CleanVinylPro2 B", models=False, LIBS_DIR=os.path.join(blocker, "libs"))
    pc.models(os.path.join(prog2, "server", "models"))
    rc, out, _ = pc.install(prog2, internet=False)  # libraries are copied from the first folder
    py2 = env_python(os.path.join(prog2, "server", ".venv"))
    if rc != 0 or "Не вдалося відкрити папку для бібліотек" not in out or sees_libs_from(py2) != site_of(os.path.join(prog2, "server", ".venv")):
        bad.append(f"unusable LIBS_DIR must fall back to the program folder: exit {rc}\n{out[-1200:]}")

    # switching the classic folder to shared libraries later, and back
    set_ini(prog, MODELS_DIR="", PYTHON_DIR="", LIBS_DIR=pc.libs)
    rc, out, _ = pc.install(prog, internet=False)
    if rc != 0 or own_libs(prog) or sees_libs_from(py) != site_of(pc.shared_env):
        bad.append(f"classic -> shared: exit {rc}, own libraries: {own_libs(prog)}\n{out[-1000:]}")
    set_ini(prog, MODELS_DIR="", PYTHON_DIR="", LIBS_DIR="")
    rc, out, _ = pc.install(prog, internet=False)
    if rc != 0 or sees_libs_from(py) != site_of(os.path.join(prog, "server", ".venv")) or not own_libs(prog):
        bad.append(f"shared -> classic: exit {rc}\n{out[-1000:]}")

    # no internet and nothing on the PC: a clear failure, not a half-made installation
    pc5 = Sandbox(os.path.join(tmp, "pc5"), wheelhouse)
    pc5.models()
    prog5 = pc5.program()
    rc, out, _ = pc5.install(prog5, internet=False)
    if rc == 0 or "[ПОМИЛКА]" not in out or os.path.isfile(os.path.join(pc5.shared_env, S.ENV_MARKER)):
        bad.append(f"no libraries anywhere and no internet must end with an error: exit {rc}\n{out[-600:]}")
    half = os.path.join(tmp, "wheels-without-onnxruntime")
    shutil.copytree(wheelhouse, half, ignore=shutil.ignore_patterns("onnxruntime*"))
    pc5.wheelhouse = half
    rc, out, _ = pc5.install(prog5, internet=True)
    if rc == 0 or "[ПОМИЛКА]" not in out or os.path.isfile(os.path.join(pc5.shared_env, S.ENV_MARKER)):
        bad.append(f"the internet dropping half-way must end with an error and no 'complete' mark: exit {rc}\n{out[-600:]}")
    pc5.wheelhouse = wheelhouse
    rc, out, _ = pc5.install(prog5, internet=True)
    if rc != 0 or sees_libs_from(env_python(os.path.join(prog5, "server", ".venv"))) != site_of(pc5.shared_env):
        bad.append(f"the next run with internet must finish the installation: exit {rc}\n{out[-1000:]}")
    report("install", not bad, "empty lines in folders.ini give the old layout (everything in the program folder); an unusable "
                               "LIBS_DIR falls back to it; switching between the layouts works; no internet + nothing to copy "
                               "ends with a clear error and the next run finishes" if not bad else "wrong: " + "\n".join(bad))


def _pc_cyrillic(tmp, wheelhouse, report):
    """Folder names in Ukrainian, with spaces - and a Windows-like console encoding instead of UTF-8."""
    import cvpaths
    import setup_env as S
    bad, pc = [], Sandbox(os.path.join(tmp, "ПК «Фото» №7"), wheelhouse)
    pc.shared = os.path.join(pc.drive, "Моделі AI для фотошопу")
    pc.libs = os.path.join(pc.shared, "бібліотеки Python")
    pc.shared_env = os.path.join(pc.libs, pc.tag)
    pc.models(os.path.join(pc.shared, "моделі"))
    prog = pc.program("Чистий Вініл 2")
    windows_like = {"PYTHONIOENCODING": "cp1251"}  # what one program reads from another on a Ukrainian Windows
    rc, out, _ = pc.install(prog, extra_env=windows_like)
    local = os.path.join(prog, "server", ".venv")
    py = env_python(local)
    shared_site = site_of(pc.shared_env) if os.path.isdir(pc.shared_env) else ""
    if rc != 0 or not shared_site or sees_libs_from(py) != shared_site or own_libs(prog) or S.thin_target(local) != env_python(pc.shared_env):
        bad.append(f"first installation: exit {rc}, libraries seen from {sees_libs_from(py)!r}")
    elif cvpaths.resolve_models_dir(prog) != os.path.join(pc.shared, "моделі"):
        bad.append(f"models in a sub-folder with a Ukrainian name: {cvpaths.resolve_models_dir(prog)}")
    else:
        break_python(pc.shared_env)
        break_python(local)
        rc, out, _ = pc.install(prog, internet=False, extra_env=windows_like)
        if rc != 0 or sees_libs_from(py) != shared_site or own_libs(prog):
            bad.append(f"moved Python: exit {rc}")
        r = _run([py, os.path.join(prog, "server", "setup_env.py"), "info"])
        if r.returncode != 0 or "усі бібліотеки на місці" not in r.stdout or "усі на місці" not in r.stdout or pc.shared_env not in r.stdout:
            bad.append(f"setup_env.py info: {r.stdout[-400:]} {r.stderr[-300:]}")
    report("install", not bad, "folder names in Ukrainian with spaces (program, models in a sub-folder, libraries) and a "
                               "non-UTF-8 console encoding: installation, re-linking and `setup_env.py info` work"
           if not bad else "wrong: " + "\n".join(bad))


def _fallback_gives_libraries_back(tmp, wheelhouse, bad):
    """
    Switching a folder to the shared libraries puts its own ones aside first. If the next step then fails, the
    installer must put them back and carry on with them - not leave the program without libraries.
    The failure is imitated at exactly that point.
    """
    import setup_env as S
    pc = Sandbox(os.path.join(tmp, "pc6"), wheelhouse)
    pc.models()
    prog = pc.program()
    local = os.path.join(prog, "server", ".venv")
    pc.full_venv(local)
    witness = os.path.join(site_of(local), "numpy", "__init__.py")
    ident = os.stat(witness).st_ino

    def failing_thin(_base, _base_info, _root, _shared_python):
        os.rename(local, local + "_old")  # the real function has done this much ...
        raise S.SetupError("imitated failure")  # ... when something goes wrong

    keep_env, keep_thin, keep_out = dict(os.environ), S.ensure_thin_env, sys.stdout
    os.environ.clear()
    os.environ.update(pc.env(internet=False))
    S.ensure_thin_env, S._interactive, S._log_path = failing_thin, False, None
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
    try:
        base = _base_python()
        _python, libs_at, shared = S.step_libraries(prog, base, S._base_info(base))
    except Exception as exc:
        libs_at, shared = f"{type(exc).__name__}: {exc}", None
    finally:
        sys.stdout.close()
        sys.stdout = keep_out
        S.ensure_thin_env = keep_thin
        os.environ.clear()
        os.environ.update(keep_env)
    if shared is not False or libs_at != local or os.path.exists(local + "_old") or not os.path.isfile(witness) \
            or os.stat(witness).st_ino != ident or sees_libs_from(env_python(local)) != site_of(local):
        bad.append(f"a failed switch to the shared libraries left the folder without its own ones: {libs_at}, shared={shared}")


def _asks_before_library_download(tmp, wheelhouse, bad):
    """
    No libraries where the installer looks by itself. With a keyboard it must ask before downloading 2-4 GB, and
    a folder named by the user (another copy of the program, standing somewhere unusual) is used instead.
    """
    import setup_env as S
    pc = Sandbox(os.path.join(tmp, "pc8"), wheelhouse)
    far = os.path.join(pc.tmp, "E", "Архів програм", "Old Vinyl")  # not next to the program, not remembered anywhere
    pc.full_venv(os.path.join(far, "server", ".venv"))
    prog = pc.program(models=False)
    answers, asked = ['"' + far + '"'], []

    def fake_input(prompt=""):
        asked.append(prompt)
        return answers.pop(0) if answers else ""

    keep_env, keep_out, keep_input = dict(os.environ), sys.stdout, builtins.input
    os.environ.clear()
    os.environ.update(pc.env(internet=False))  # a download is impossible: only the copy can succeed
    builtins.input, S._interactive, S._log_path = fake_input, True, None
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
    try:
        base = _base_python()
        python, libs_at, shared = S.step_libraries(prog, base, S._base_info(base))
    except Exception as exc:
        python, libs_at, shared = "", f"{type(exc).__name__}: {exc}", None
    finally:
        sys.stdout.close()
        sys.stdout, builtins.input, S._interactive = keep_out, keep_input, False
        os.environ.clear()
        os.environ.update(keep_env)
    if shared is not True or len(asked) != 1 or not python or sees_libs_from(python) != site_of(pc.shared_env) or own_libs(prog):
        bad.append(f"the installer must ask before downloading the libraries and use the folder that was named: "
                   f"asked {len(asked)} time(s), result {libs_at}, shared={shared}")


def check_install(report):
    if os.name == "nt":
        report("install", True, "SKIPPED - this imitation of a PC is written for Linux")
        return
    bad = []
    _unit_checks(bad)
    report("install", not bad, "installer pieces: ONNX Runtime choice by CUDA version, requirements, the real environment of the "
                               "old program (Windows layout, Python 3.12) is recognised and re-linked, pointer module for any path"
           if not bad else f"wrong: {bad}")

    tmp = tempfile.mkdtemp(prefix="cv_install_")
    try:
        wheelhouse = make_wheelhouse(os.path.join(tmp, "wheels"))

        for scenario in (_pc_empty, _pc_with_old_program, _pc_classic, _pc_cyrillic):
            try:
                scenario(tmp, wheelhouse, report)
            except Exception as exc:  # a scenario that breaks is a failed check; the others still run
                import traceback
                report("install", False, f"{scenario.__name__} crashed: {type(exc).__name__}: {exc}\n{traceback.format_exc()[-900:]}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ----------------------------------------------------------------------------------------------------------------------
# bat: reading the .bat files the way cmd.exe does
# ----------------------------------------------------------------------------------------------------------------------
_KNOWN_VARS = {"LOCALAPPDATA", "APPDATA", "PROGRAMFILES", "ERRORLEVEL", "USERPROFILE", "SYSTEMROOT", "WINDIR", "TEMP", "CD"}


def _outside_quotes(line: str) -> str:
    """The line with everything between double quotes blanked out."""
    out, inside = [], False
    for ch in line:
        if ch == '"':
            inside = not inside
            out.append('"')
        else:
            out.append(" " if inside else ch)
    return "".join(out)


def lint_bat(name: str, text: str, folder: str = APP_DIR) -> list:
    """Problems cmd.exe would have with the file (a list of sentences; empty = none found)."""
    bad = []
    lines = text.split("\r\n")
    if "\n" in text.replace("\r\n", "") or not text.endswith("\r\n"):
        bad.append("line endings are not CRLF")
    if text.startswith("\ufeff"):
        bad.append("starts with a BOM (cmd.exe would not understand the first line)")
    if len(lines) < 2 or lines[0].strip().lower() != "@echo off" or lines[1].strip().lower() != "chcp 65001 >nul":
        bad.append("must start with '@echo off' and 'chcp 65001 >nul' (the texts are UTF-8)")

    labels = {m.group(1).lower() for line in lines for m in [re.match(r"\s*:([A-Za-z_][\w]*)\s*$", line)] if m}
    used = {m.group(1).lower() for line in lines if not line.lstrip().startswith("::")
            for m in re.finditer(r"\b(?:goto|call)\s+:([A-Za-z_]\w*)", line, flags=re.IGNORECASE)}
    for target in sorted(used - labels - {"eof"}):
        bad.append(f"goto/call :{target} - there is no such label")
    for label in sorted(labels - used):
        bad.append(f"label :{label} is never used")

    defined = {m.group(1).upper() for line in lines for m in re.finditer(r'\bset\s+"?([A-Za-z_]\w*)=', line, flags=re.IGNORECASE)}
    depth, block_sets = 0, []
    for no, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line:
            continue
        where = f"line {no}"
        comment = line.startswith("::") or line.lower().startswith("rem ")
        bare = _outside_quotes(line)
        if comment:
            if depth > 0:
                bad.append(f"{where}: a '::' comment inside a ( ) block breaks the block")
            if re.search(r"%~|%\d", line):
                bad.append(f"{where}: %~ or %1 in a comment is still expanded by cmd.exe")
            continue
        is_echo = bool(re.match(r"echo\b", line, flags=re.IGNORECASE)) and not line.lower().startswith("echo.") or \
            line.lower().startswith("echo.") and len(line) > 5
        if is_echo:
            body = line[4:]
            if re.search(r'(?<!\^)[&|<>]', _outside_quotes(body)):
                bad.append(f"{where}: echo text has an unescaped & | < or > (cmd.exe would run or redirect it)")
            if depth > 0 and re.search(r"(?<!\^)[()]", _outside_quotes(body)):
                bad.append(f"{where}: echo text has ( or ) inside a ( ) block - the block would end early")
            if body.count("%") % 2 and "%%" not in body:
                bad.append(f"{where}: a single % in echo text disappears")
        else:
            for m in re.finditer(r"""in\s*\('(.*)'\)\s*do""", line, flags=re.IGNORECASE):
                inner = _outside_quotes(m.group(1))
                if re.search(r"(?<!\^)[|&<>]", inner):
                    bad.append(f"{where}: | & < > inside for /f ('...') must be written ^| ^& ^< ^>")
                if re.search(r"[=,;]", inner):
                    bad.append(f"{where}: = , ; outside quotes inside for /f ('...') are turned into spaces by cmd.exe")
        for m in re.finditer(r"%([A-Za-z_]\w*)(?::[^%]*)?%", line):
            var = m.group(1).upper()
            if var not in defined and var not in _KNOWN_VARS:
                bad.append(f"{where}: %{m.group(1)}% is never set")
            if depth > 0 and var in {v for v, d in block_sets if d <= depth}:
                bad.append(f"{where}: %{m.group(1)}% is set inside the same ( ) block - cmd.exe would use the old value")
        if depth > 0:
            for m in re.finditer(r'\bset\s+"?([A-Za-z_]\w*)=', line, flags=re.IGNORECASE):
                block_sets.append((m.group(1).upper(), depth))
        # the little Python programs written inside the .bat
        for m in re.finditer(r'-c "([^"]*)"', line):
            code = m.group(1)
            if "%" in code:
                bad.append(f"{where}: % inside python -c \"...\" is eaten by cmd.exe")
            try:
                compile(code, f"{name}:{no}", "exec")
            except SyntaxError as exc:
                bad.append(f"{where}: the Python inside is not valid: {exc.msg}")
        for m in re.finditer(r'"(?:%~dp0)?(server\\[\w.]+\.(?:py|bat))"', line):
            if not os.path.isfile(os.path.join(folder, *m.group(1).split("\\"))):
                bad.append(f"{where}: {m.group(1)} does not exist in the program folder")
        # brackets
        opens = len(re.findall(r"\($", bare)) if not is_echo else 0
        closes = 1 if bare.startswith(")") else 0
        depth += opens - closes
        if depth < 0:
            bad.append(f"{where}: a ) without its (")
            depth = 0
        if depth == 0:
            block_sets = []
    if depth != 0:
        bad.append(f"{depth} ( ) block(s) are never closed")
    return bad


def check_bat(report):
    bad, names = [], sorted(f for f in os.listdir(APP_DIR) if f.lower().endswith(".bat"))
    for name in names:
        text = open(os.path.join(APP_DIR, name), "rb").read().decode("utf-8")
        bad += [f"{name}: {problem}" for problem in lint_bat(name, text)]

    install = open(os.path.join(APP_DIR, "install_windows.bat"), "rb").read().decode("utf-8")
    fix = open(os.path.join(APP_DIR, "fix_gpu_cuda.bat"), "rb").read().decode("utf-8")
    for needle, why in (
        ('findstr /b /i /c:"PYTHON_DIR=" "folders.ini"', "install_windows.bat must read PYTHON_DIR of folders.ini"),
        ('call :try_python "%CVP_PYDIR%\\python.exe"', "the folder named in folders.ini must be tried first"),
        ('"%LOCALAPPDATA%\\Programs\\Python\\Python%%v\\python.exe"', "the standard place of Python must be tried"),
        ('"%CVP_PY%" "server\\setup_env.py" install', "the found Python must start setup_env.py"),
        ("if errorlevel 1 goto :setup_failed", "a failed setup must not be reported as done"),
    ):
        if needle not in install:
            bad.append(f"install_windows.bat: {why}")
    order = [install.find(s) for s in ('call :try_python "%CVP_PYDIR%', "%LOCALAPPDATA%\\Programs", "where python", ":no_python\r\n")]
    if order != sorted(order) or -1 in order:
        bad.append("install_windows.bat: the order of the places where Python is looked for changed")
    for old in ("activate.bat", "pip install", "rmdir /s", "server/models", "server\\models"):
        if old in install or old in fix:
            bad.append(f"the .bat files must leave '{old}' to setup_env.py")
    if '"server\\.venv\\Scripts\\python.exe" "server\\setup_env.py" gpu' not in fix:
        bad.append("fix_gpu_cuda.bat must start setup_env.py gpu")

    # the reader itself must notice the classic mistakes (each of them was made in a real .bat once)
    good = "@echo off\r\nchcp 65001 >nul\r\nset \"A=1\"\r\nif exist \"x\" (\r\n    echo ok\r\n)\r\ngoto :end\r\n:end\r\n"
    if lint_bat("good.bat", good):
        bad.append(f"the reader reports a correct file: {lint_bat('good.bat', good)}")
    for mutation, what in (
        (good.replace("echo ok", "echo   1) first"), "echo with ) inside a block"),
        (good.replace("echo ok", "echo a -> b"), "echo with >"),
        (good.replace("goto :end", "goto :finish"), "missing label"),
        (good.replace("    echo ok\r\n)\r\n", "    echo ok\r\n"), "unclosed block"),
        (good.replace("\r\n", "\n"), "LF line endings"),
        (good.replace("echo ok", ":: note"), "comment inside a block"),
        (good.replace("echo ok", "set \"B=2\"\r\n    echo %B%"), "variable set and used in one block"),
        (good.replace("echo ok", "echo %UNKNOWN_THING%"), "unknown variable"),
        (good.replace("echo ok", "python -c \"import sys; sys.exit(0 if else 1)\""), "broken Python inside"),
        (good.replace("echo ok", "for /f %%a in ('findstr x y | sort') do echo %%a"), "unescaped | in for /f"),
        (good.replace("echo ok", "\"server\\no_such_file.py\""), "missing server file"),
    ):
        if not lint_bat("bad.bat", mutation):
            bad.append(f"the reader misses: {what}")
    old_install = os.path.join(BASELINE_DIR, "install_windows.bat")
    if not os.path.isfile(old_install):
        bad.append("tests/baseline_v321/install_windows.bat is missing")
    else:  # the installer of v3.2.1 has two of these mistakes in its last lines
        found = lint_bat("old", open(old_install, "rb").read().decode("utf-8").replace("\r\n", "\n").replace("\n", "\r\n"), BASELINE_DIR)
        if not any("block would end early" in p for p in found) or not any("unescaped" in p for p in found):
            bad.append("the reader misses the two known mistakes of the v3.2.1 installer")
    report("bat", not bad, f"{len(names)} .bat files read the way cmd.exe does: brackets, labels, texts, variables, the Python inside "
                           f"them; install_windows.bat looks for Python in folders.ini first, then in the standard places"
           if not bad else "wrong:\n  " + "\n  ".join(bad))
