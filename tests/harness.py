"""
Test harness for the Clean Vinyl Pro server: runs CleanVinylEngine WITHOUT the real AI models and without a GPU.

* The two neural networks are replaced by small deterministic stand-ins (FakeMatting / FakeLama), so every
  other line of the pipeline (detection, blending, grain, bit-depth conversion, session cache, HTTP packets)
  runs exactly as in production and gives reproducible pixels.
* make_studio_image() draws a synthetic studio frame: wall + floor with a corner line, a "person", a contact
  shadow, a vinyl seam, dust specks, hairs and scuffs.
* load_baseline() loads engine.py / server.py of v3.2.1 (kept in tests/baseline_v321), so the current code can
  be compared with it pixel by pixel on the same machine.
"""
import os
import sys
import tempfile
import time
import types

import cv2
import numpy as np

sys.dont_write_bytecode = True

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(REPO_ROOT, "CleanVinylPro2")  # the program these checks are about
SERVER_DIR = os.path.join(APP_DIR, "server")
# The original program (v3.2.1) is the reference for everything that was not meant to change. Its folder
# (CleanVinylPro, 666 MB with a Windows Python environment inside) left the repository in version 4.3.0; the files
# the checks compare with are kept in tests/baseline_v321 exactly as they were in the first commit:
BASELINE_COMMIT = "daae6ed072f93e109e10105574c211f698318b65"
BASELINE_FILES_DIR = os.path.join(REPO_ROOT, "tests", "baseline_v321")

if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)


def _ensure_onnxruntime_importable() -> None:
    """engine.py pip-installs onnxruntime when it is missing; tests must never trigger that."""
    try:
        import onnxruntime  # noqa: F401
    except Exception:
        stub = types.ModuleType("onnxruntime")
        stub.get_available_providers = lambda: ["CPUExecutionProvider"]
        sys.modules["onnxruntime"] = stub


def load_engine():
    """The engine module from this working copy."""
    _ensure_onnxruntime_importable()
    import engine
    return engine


def load_server():
    """The server module from this working copy (it binds the working-copy engine)."""
    load_engine()
    _protect_stdio()
    import server
    return server


def _protect_stdio() -> None:
    os.environ.setdefault("CLEANVINYL_DATA_DIR", tempfile.mkdtemp(prefix="cv_test_data_"))


_BASELINE = None


def load_baseline():
    """
    (engine_module, server_module) of v3.2.1 from tests/baseline_v321, or (None, None) when those files are missing.
    """
    global _BASELINE
    if _BASELINE is not None:
        return _BASELINE
    _ensure_onnxruntime_importable()
    tmp = tempfile.mkdtemp(prefix="cv_baseline_")
    try:
        for name in ("engine", "server"):
            with open(os.path.join(BASELINE_FILES_DIR, f"{name}.py"), "rb") as f:
                src = f.read()
            with open(os.path.join(tmp, f"{name}_v321.py"), "wb") as f:
                f.write(src)
    except Exception:
        _BASELINE = (None, None)
        return _BASELINE
    sys.path.insert(1, tmp)
    import engine_v321

    _protect_stdio()
    current_engine = sys.modules.get("engine")
    sys.modules["engine"] = engine_v321  # server_v321 does `from engine import CleanVinylEngine`
    try:
        import server_v321
    finally:
        if current_engine is not None:
            sys.modules["engine"] = current_engine
        else:
            sys.modules.pop("engine", None)
    _BASELINE = (engine_v321, server_v321)
    return _BASELINE


# ----------------------------------------------------------------------------------------------------------------------
# Stand-ins for the ONNX sessions
# ----------------------------------------------------------------------------------------------------------------------
class _Input:
    def __init__(self, name: str):
        self.name = name
        self.type = "tensor(float)"


class FakeMatting:
    """Returns a fixed 1024x1024 silhouette (0..1) whatever the input is."""

    def __init__(self, mask_1024: np.ndarray):
        self.mask_1024 = mask_1024
        self.calls = 0

    def get_inputs(self):
        return [_Input("input")]

    def get_providers(self):
        return ["CUDAExecutionProvider"]

    def run(self, _outputs, feed):
        self.calls += 1
        return [self.mask_1024[None, None].astype(np.float32)]


class FakeLama:
    """Deterministic inpainting stand-in: masked pixels become a blurred copy. Output range 0..255 like the real export."""

    def __init__(self):
        self.calls = 0

    def get_inputs(self):
        return [_Input("image"), _Input("mask")]

    def get_providers(self):
        return ["CUDAExecutionProvider"]

    def run(self, _outputs, feed):
        self.calls += 1
        img = feed["image"][0].transpose(1, 2, 0)
        m = feed["mask"][0, 0][..., None]
        out = (img * (1 - m) + cv2.blur(img, (31, 31)) * m) * 255.0
        return [np.ascontiguousarray(out.transpose(2, 0, 1)[None]).astype(np.float32)]


class LightLama(FakeLama):
    """
    A stand-in that guesses the way the real network did on the owner's computer when a thing filled most of its
    tile (0Q5A3534, the black curtain: the fill came out 22 levels lighter than the wall beside it): every masked
    pixel becomes what the tile shows outside the mask - nearby where there is something nearby, else the average
    of the tile, and mid-grey for a tile that shows nothing - `lift` levels lighter.
    """

    def __init__(self, lift: float = 22.0):
        super().__init__()
        self.lift = float(lift)

    def run(self, _outputs, feed):
        self.calls += 1
        img = feed["image"][0].transpose(1, 2, 0)
        m = feed["mask"][0, 0][..., None]
        seen = 1.0 - m
        den = cv2.blur(seen[..., 0], (101, 101))[..., None]
        near = cv2.blur(img * seen, (101, 101)) / np.maximum(den, 1e-3)
        total = float(seen.sum())
        whole = (img * seen).sum(axis=(0, 1)) / total if total >= 1.0 else np.full(3, 0.5, np.float32)
        trust = np.clip(den / 0.05, 0.0, 1.0)
        around = near * trust + whole[None, None, :] * (1.0 - trust)
        out = (img * seen + np.clip(around + self.lift / 255.0, 0.0, 1.0) * m) * 255.0
        return [np.ascontiguousarray(out.transpose(2, 0, 1)[None]).astype(np.float32)]


def make_engine(engine_module, mask_1024: np.ndarray):
    """An engine instance with the stand-in networks; works for the current engine and for the v3.2.1 baseline."""
    import threading

    cls = engine_module.CleanVinylEngine
    try:
        eng = cls("/nonexistent-models", idle_unload_sec=0.0, load_models=False)
    except TypeError:  # v3.2.1 has no load_models switch
        eng = cls.__new__(cls)
        eng.models_dir = "/nonexistent-models"
        eng.idle_unload_sec = 0.0
        eng.lock = threading.Lock()
        eng._state_lock = threading.Lock()
        eng._active_jobs = 0
        eng._last_used_mono = time.monotonic()
        eng._unload_timer = None
        eng.gpu_error = ""
        eng.mat_path = None
        eng.lama_path = None
        eng._is_quant_lama = False
        eng._active_session = None
    eng.provider_name = "CUDAExecutionProvider"
    eng.gpu_name = "STUB"
    eng.matting_kind = "rmbg2"
    eng._scale_probed = True
    eng.lama_out_scale = 255.0
    eng.matting_sess = FakeMatting(mask_1024)
    eng.lama_sess = FakeLama()
    return eng


def fixed_fast_inpaint(old_engine):
    """
    Context manager: the v3.2.1 engine with ONLY its white-patch line corrected (fast inpaint result uint8 -> 0..1
    float inside apply_session). Used to prove that nothing else changed in apply_session.
    """

    class _Ctx:
        def __enter__(self):
            self.fn = old_engine._run_fast_inpaint

            def patched(*a, **k):
                img, tiles, specks = self.fn(*a, **k)
                return img.astype(np.float32) * (1.0 / 255.0), tiles, specks

            old_engine._run_fast_inpaint = patched

        def __exit__(self, *exc):
            old_engine._run_fast_inpaint = self.fn

    return _Ctx()


# ----------------------------------------------------------------------------------------------------------------------
# Synthetic studio frame
# ----------------------------------------------------------------------------------------------------------------------
def make_studio_image(w=3000, h=2000, n_dust=120, n_hair=10, seed=1, bit16=False, lowkey=False, rgba=False):
    """Returns (image, silhouette_1024). image: uint8 0..255 or uint16 0..32768 (Photoshop 16-bit range), RGB or RGBA."""
    rng = np.random.default_rng(seed)
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    xx = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    base_wall, base_floor = (38.0, 60.0) if lowkey else (150.0, 172.0)
    t = 1.0 / (1.0 + np.exp(-np.clip((yy - 0.62) * 220.0, -50, 50)))
    lum = base_wall * (1 - t) + base_floor * t
    lum = (lum * (1.0 - 0.22 * (((xx - 0.5) * 2) ** 2) - 0.10 * (((yy - 0.45) * 2) ** 2))).astype(np.float32)

    scuff = np.zeros((max(8, h // 8), max(8, w // 8)), np.float32)
    for _ in range(14):
        cx = int(rng.integers(0, scuff.shape[1]))
        cy = int(rng.integers(int(scuff.shape[0] * 0.64), scuff.shape[0]))
        cv2.ellipse(scuff, (cx, cy), (int(rng.integers(20, 70)), int(rng.integers(8, 26))), float(rng.uniform(0, 180)),
                    0, 360, float(rng.uniform(-7, -3)), -1)
    lum += cv2.resize(cv2.GaussianBlur(scuff, (0, 0), 9), (w, h), interpolation=cv2.INTER_LINEAR)

    img = np.empty((h, w, 3), np.uint8)
    for c, gain in enumerate((1.02, 1.0, 0.97)):
        img[:, :, c] = np.clip(lum * gain, 0, 255).astype(np.uint8)

    ys = int(h * 0.80)  # vinyl seam
    img[max(0, ys - 9):ys + 9] = np.clip(img[max(0, ys - 9):ys + 9].astype(np.int16) - 3, 0, 255).astype(np.uint8)
    img[max(0, ys - 1):ys + 2] = np.clip(img[max(0, ys - 1):ys + 2].astype(np.int16) - 16, 0, 255).astype(np.uint8)

    mx, my = min(60, w // 8), min(60, h // 8)
    for _ in range(n_dust):
        on_floor = rng.random() < 0.8
        cx = int(rng.integers(mx, w - mx))
        cy = int(rng.integers(int(h * 0.64), h - my)) if on_floor else int(rng.integers(my, int(h * 0.60)))
        r = int(rng.choice([1, 1, 2, 2, 3, 3, 4, 6, 9]))
        d = int(rng.integers(14, 48)) * (1 if rng.random() < 0.8 else -1)
        col = tuple(int(np.clip(int(v) - d, 0, 255)) for v in img[cy, cx])
        cv2.circle(img, (cx, cy), r, col, -1, lineType=cv2.LINE_AA)
    mx, my = min(100, w // 6), min(100, h // 6)
    for _ in range(n_hair):
        cx = int(rng.integers(mx, w - mx))
        cy = int(rng.integers(int(h * 0.64), h - my))
        pts = np.cumsum(rng.normal(0, 14, (6, 2)), axis=0) + (cx, cy)
        col = tuple(int(np.clip(int(v) - 30, 0, 255)) for v in img[cy, cx])
        cv2.polylines(img, [pts.astype(np.int32)], False, col, 2, lineType=cv2.LINE_AA)

    sil = np.zeros((h, w), np.uint8)  # the "person": head, dress, two legs
    cx = int(w * 0.5)
    cv2.ellipse(sil, (cx, int(h * 0.20)), (int(w * 0.035), int(h * 0.07)), 0, 0, 360, 255, -1)
    dress = np.array([[cx - int(w * 0.05), int(h * 0.26)], [cx + int(w * 0.05), int(h * 0.26)],
                      [cx + int(w * 0.12), int(h * 0.72)], [cx - int(w * 0.12), int(h * 0.72)]], np.int32)
    cv2.fillPoly(sil, [dress], 255)
    cv2.rectangle(sil, (cx - int(w * 0.045), int(h * 0.72)), (cx - int(w * 0.012), int(h * 0.90)), 255, -1)
    cv2.rectangle(sil, (cx + int(w * 0.012), int(h * 0.72)), (cx + int(w * 0.045), int(h * 0.90)), 255, -1)

    sh = np.zeros((max(8, h // 8), max(8, w // 8)), np.float32)  # contact shadow under the feet
    cv2.ellipse(sh, (cx // 8 + 30, int(h * 0.905) // 8), (max(1, int(w * 0.11) // 8), max(1, int(h * 0.022) // 8)),
                0, 0, 360, 1.0, -1)
    sh = cv2.resize(cv2.GaussianBlur(sh, (0, 0), 6), (w, h))
    for c in range(3):
        img[:, :, c] = (img[:, :, c] * (1.0 - 0.38 * sh)).astype(np.uint8)

    subj = np.empty((h, w, 3), np.uint8)
    subj[:] = (30, 30, 36)
    subj[: int(h * 0.27)] = (205, 160, 135)
    subj[int(h * 0.72):] = (200, 158, 132)
    fold = (np.sin(xx * 240.0) * 9).astype(np.int16)
    subj = np.clip(subj.astype(np.int16) + fold[..., None], 0, 255).astype(np.uint8)
    img[sil > 0] = subj[sil > 0]

    for c in range(3):  # sensor grain
        n = rng.standard_normal((h, w), dtype=np.float32) * 1.8
        img[:, :, c] = np.clip(img[:, :, c].astype(np.float32) + n, 0, 255).astype(np.uint8)

    sil_1024 = cv2.resize(sil, (1024, 1024), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    if bit16:
        out = (img.astype(np.uint16) * 128) + rng.integers(0, 128, img.shape, dtype=np.uint16)
        out = np.minimum(out, 32768).astype(np.uint16)
    else:
        out = img
    if rgba:
        a = np.full((h, w, 1), 32768 if bit16 else 255, out.dtype)
        out = np.ascontiguousarray(np.concatenate([out, a], axis=2))
    return out, sil_1024


# The plugin's "Standard" preset
STD = dict(spots=75, scuffs=65, blur=0, cycCurve=0, feather=60, seamOn=True, seam=85, edge=70,
           smokeOn=True, smoke=80, grain=90, shadow=True, removeStands=False, master=100,
           fracFine=True, fracMed=True, fracLarge=True, dressSmooth=False, dressStrength=45, cleanPasses=1)
