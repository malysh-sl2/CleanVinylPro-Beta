import base64
import gc
import os
import sys
import time
import threading
import uuid
import warnings
import cv2
import numpy as np

_DLL_HANDLES = []


def _register_nvidia_dlls():
    """Register pip-installed NVIDIA CUDA / cuDNN DLL folders on Windows before ONNX Runtime loads."""
    if sys.platform != "win32":
        return []
    candidates = []
    search_roots = set()
    for p in sys.path:
        if p and os.path.isdir(p):
            nv = os.path.join(p, "nvidia")
            if os.path.isdir(nv):
                search_roots.add(nv)
            tl = os.path.join(p, "torch", "lib")
            if os.path.isdir(tl):
                candidates.append(tl)

    for nv in search_roots:
        for dirpath, _, filenames in os.walk(nv):
            if any(fn.lower().endswith(".dll") for fn in filenames):
                candidates.append(dirpath)

    added = []
    cur_path = os.environ.get("PATH", "")
    path_parts = [x for x in cur_path.split(os.pathsep) if x]
    for d in candidates:
        if d not in path_parts:
            path_parts.insert(0, d)
        if hasattr(os, "add_dll_directory"):
            try:
                _DLL_HANDLES.append(os.add_dll_directory(d))
            except Exception:
                pass
        added.append(d)
    if added:
        os.environ["PATH"] = os.pathsep.join(path_parts)
    return added


_NVIDIA_DLL_DIRS = _register_nvidia_dlls()


def _pip_python() -> str:
    """
    The Python whose pip installs a missing package. When the libraries are shared between the installed versions
    (LIBS_DIR in folders.ini), server/.venv holds none of its own: the small module written there by setup_env.py
    names the shared environment, and a package must be installed there - not into this program folder.
    """
    shared = os.environ.get("CLEANVINYL_ENV_PYTHON", "")
    return shared if shared and os.path.isfile(shared) else sys.executable


def _import_or_install_ort():
    try:
        import onnxruntime as _ort
        return _ort
    except ModuleNotFoundError:
        import importlib
        import re
        import shutil
        import subprocess

        print("[Engine] Пакунок onnxruntime відсутній — запускаємо автоматичне встановлення...", flush=True)
        smi = shutil.which("nvidia-smi")
        if not smi:
            for cand in [r"C:\Windows\System32\nvidia-smi.exe", r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"]:
                if os.path.exists(cand):
                    smi = cand
                    break
        cuda_maj = 0
        if smi:
            try:
                out = subprocess.check_output([smi], stderr=subprocess.DEVNULL, timeout=4).decode("utf-8", errors="ignore")
                m = re.search(r"CUDA Version:\s*(\d+)\.(\d+)", out)
                if m:
                    cuda_maj = int(m.group(1))
            except Exception:
                pass

        if cuda_maj == 12:
            pkgs = ["onnxruntime-gpu[cuda,cudnn]==1.26.0", "onnxruntime-gpu==1.26.0", "onnxruntime-gpu", "onnxruntime"]
        elif cuda_maj >= 13 or smi:
            pkgs = ["onnxruntime-gpu[cuda,cudnn]>=1.27.0", "onnxruntime-gpu", "onnxruntime"]
        else:
            pkgs = ["onnxruntime-gpu", "onnxruntime"]

        for pkg in pkgs:
            try:
                print(f"[Engine] Встановлюємо: {pkg} ...", flush=True)
                subprocess.check_call([_pip_python(), "-m", "pip", "install", "--no-cache-dir", pkg])
                break
            except Exception as e:
                print(f"[Engine] Не вдалося встановити {pkg}: {e}", flush=True)

        _NVIDIA_DLL_DIRS.extend(_register_nvidia_dlls())
        importlib.invalidate_caches()
        import onnxruntime as _ort
        return _ort


ort = _import_or_install_ort()


DEFAULT_IDLE_UNLOAD_SEC = 120.0


def _cudnn_algo_from_env() -> str:
    """
    cuDNN convolution algorithm search used when a model is (re)loaded onto the GPU.
    ONNX Runtime's own default is EXHAUSTIVE: it benchmarks every algorithm on the first run after each
    model load, which costs seconds every time the models were unloaded while the photographer was retouching.
    HEURISTIC picks an algorithm without benchmarking. Override with the environment variable
    CLEANVINYL_CUDNN_ALGO = HEURISTIC | DEFAULT | EXHAUSTIVE (EXHAUSTIVE restores the pre-3.3 behaviour).
    """
    val = os.environ.get("CLEANVINYL_CUDNN_ALGO", "HEURISTIC").strip().upper()
    if val in ("HEURISTIC", "DEFAULT"):
        return val
    if val in ("EXHAUSTIVE", "", "OFF", "NONE", "0"):
        return ""
    return "HEURISTIC"


class CleanVinylEngine:
    # Largest amount of healed 128px cells an interactive session may keep for instant re-use (bytes).
    # A typical dusty 24 MP frame needs ~100 MB; above the limit the heal stage is simply recomputed.
    STAGE_CACHE_HEAL_MAX_BYTES = 256 * 1024 * 1024
    # Quick preview of the interactive window: after a slider moves, the search still runs on the real frame, but
    # the repair and the tone are drawn on a copy reduced to this long side (the preview itself is <= 1080 px).
    # 1800 px keeps every tone stage at the working size it has on the real frame in the fast mode.
    PREVIEW_PROXY_DIM = 1800
    # Frames smaller than this are simply recomputed in full: nothing to gain from a copy.
    PREVIEW_PROXY_MIN_DIM = 2520
    # Smoke protection in the automatic mode ("smokeAuto"): the frame is said to have smoke when the smoke-like areas
    # cover at least this share of it, or one of them alone covers at least SMOKE_MIN_CLOUD. A dirty floor gives a
    # few small smoke-like patches next to the feet (0.2-1.5% on real studio frames) - protecting those would keep
    # exactly the dirt that has to go. A puff from a smoke machine covers 5% and more.
    SMOKE_MIN_SHARE = 0.03
    SMOKE_MIN_CLOUD = 0.015
    # Stains ("Сліди взуття та розводи") are not evened on a bend of the light (the rim of a lamp's pool, the soft
    # edge of a shadow). The bend is measured as its change across the reach of the filter, in units of the
    # tolerance: evened in full up to ..._FROM, not at all from ..._TO (see _smooth_backdrop_stains).
    STAIN_SLOPE_FROM = 1.0
    STAIN_SLOPE_TO = 2.5
    # From this value of the smoke slider up the user says "this frame has smoke": everything smoke-like is protected
    # without asking for that evidence (the built-in preset for smoke shoots sits here).
    SMOKE_ALWAYS_FROM = 95.0

    def __init__(self, models_dir: str, idle_unload_sec: float = DEFAULT_IDLE_UNLOAD_SEC, load_models: bool = True):
        """load_models=False builds the engine without touching the model files (used by tests/ with stub sessions)."""
        self.models_dir = models_dir
        self.idle_unload_sec = float(idle_unload_sec)
        self.lock = threading.Lock()
        self._state_lock = threading.Lock()
        # Serializes start / recompute / brush / apply of the interactive session (they share its cached state)
        self._session_lock = threading.RLock()
        self._active_jobs = 0
        self._last_used_mono = time.monotonic()
        self._unload_timer = None
        self.provider_name = "CPUExecutionProvider"
        self.gpu_name = "CPU"
        self.gpu_error = ""
        self.matting_kind = None
        self.mat_path = None
        self.lama_path = None
        self._is_quant_lama = False
        self._scale_probed = False
        self.lama_out_scale = 255.0
        self.matting_sess = None
        self.lama_sess = None
        self._active_session = None
        self._cudnn_algo = _cudnn_algo_from_env()
        if not load_models:
            return
        self._resolve_model_paths()
        self._ensure_models_loaded(need_matting=True, need_lama=True)
        self._schedule_idle_unload()

    @property
    def is_loaded(self) -> bool:
        return (self.matting_sess is not None) or (self.lama_sess is not None)

    def set_idle_unload(self, sec: float):
        with self._state_lock:
            self.idle_unload_sec = max(0.0, float(sec))
            if self._unload_timer is not None:
                try:
                    self._unload_timer.cancel()
                except Exception:
                    pass
                self._unload_timer = None
        if self.idle_unload_sec > 0 and self.is_loaded:
            self._schedule_idle_unload()

    def _begin_job(self):
        with self._state_lock:
            self._active_jobs += 1
            self._last_used_mono = time.monotonic()
            if self._unload_timer is not None:
                try:
                    self._unload_timer.cancel()
                except Exception:
                    pass
                self._unload_timer = None

    def _end_job(self):
        with self._state_lock:
            self._active_jobs = max(0, self._active_jobs - 1)
            self._last_used_mono = time.monotonic()
        self._schedule_idle_unload()

    def _schedule_idle_unload(self):
        if self.idle_unload_sec <= 0:
            return
        with self._state_lock:
            if self._unload_timer is not None:
                try:
                    self._unload_timer.cancel()
                except Exception:
                    pass
                self._unload_timer = None
            if self._active_jobs > 0 or not self.is_loaded:
                return
            t = threading.Timer(self.idle_unload_sec, self._on_idle_timeout)
            t.daemon = True
            t.start()
            self._unload_timer = t

    def _on_idle_timeout(self):
        with self._state_lock:
            if self._active_jobs > 0 or not self.is_loaded:
                return
            if self._active_session is not None:
                # Keep models and session warm while user is actively working in the interactive window
                t = threading.Timer(max(5.0, self.idle_unload_sec), self._on_idle_timeout)
                t.daemon = True
                t.start()
                self._unload_timer = t
                return
            idle_for = time.monotonic() - self._last_used_mono
            rem = self.idle_unload_sec - idle_for
            if rem > 0.25:
                t = threading.Timer(rem, self._on_idle_timeout)
                t.daemon = True
                t.start()
                self._unload_timer = t
                return
        self.unload_models(reason=f"{int(round(self.idle_unload_sec))} с бездіяльності")

    def unload_models(self, reason: str = "вручну", clear_session: bool = False) -> bool:
        with self.lock:
            with self._state_lock:
                if self._active_jobs > 0:
                    return False
                if self._unload_timer is not None:
                    try:
                        self._unload_timer.cancel()
                    except Exception:
                        pass
                    self._unload_timer = None
            had_any = self.is_loaded or (clear_session and self._active_session is not None)
            self.matting_sess = None
            self.lama_sess = None
            if clear_session:
                self._active_session = None
        if had_any:
            gc.collect()
            if sys.platform == "win32":
                try:
                    import ctypes
                    ctypes.windll.kernel32.SetProcessWorkingSetSize(-1, -1, -1)
                except Exception:
                    pass
            print(f"[Engine] Моделі вивантажено з пам'яті GPU/ОЗУ ({reason}).", flush=True)
        return had_any

    def _find_nvidia_smi(self) -> str:
        for cand in [
            "nvidia-smi",
            r"C:\Windows\System32\nvidia-smi.exe",
            r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
        ]:
            try:
                import shutil
                if cand == "nvidia-smi":
                    found = shutil.which(cand)
                    if found:
                        return found
                elif os.path.exists(cand):
                    return cand
            except Exception:
                pass
        return "nvidia-smi"

    def _detect_gpu_name(self) -> str:
        try:
            import subprocess
            smi = self._find_nvidia_smi()
            out = subprocess.check_output(
                [smi, "--query-gpu=name,memory.total", "--format=csv,noheader"],
                stderr=subprocess.DEVNULL,
                timeout=3,
            ).decode("utf-8", errors="ignore").strip()
            if out:
                return out.splitlines()[0].strip()
        except Exception:
            pass
        return "GPU"

    def _preload_ort_cuda(self):
        if not hasattr(ort, "preload_dlls"):
            return
        try:
            ort.preload_dlls()
        except Exception:
            pass
        # Explicit fallback for onnxruntime-gpu 1.27+ CUDA 13 consolidated wheel layout on Windows
        for d in _NVIDIA_DLL_DIRS:
            dl = d.lower()
            try:
                if "cu13" in dl or "cuda_runtime" in dl or "cublas" in dl:
                    ort.preload_dlls(cuda=True, cudnn=False, directory=d)
                if "cudnn" in dl:
                    ort.preload_dlls(cuda=False, cudnn=True, directory=d)
            except Exception:
                pass

    def _create_cpu_session(self, model_path: str):
        so_cpu = ort.SessionOptions()
        so_cpu.log_severity_level = 3
        so_cpu.enable_cpu_mem_arena = False
        so_cpu.enable_mem_pattern = False
        so_cpu.intra_op_num_threads = 1
        so_cpu.inter_op_num_threads = 1
        sess = ort.InferenceSession(model_path, sess_options=so_cpu, providers=["CPUExecutionProvider"])
        return sess, "CPUExecutionProvider"

    def _create_session(self, model_path: str, allow_dml: bool = True):
        self._preload_ort_cuda()
        avail = ort.get_available_providers()
        has_gpu_ep = ("CUDAExecutionProvider" in avail) or (allow_dml and "DmlExecutionProvider" in avail)

        has_cuda = "CUDAExecutionProvider" in avail

        def _providers(algo: str):
            providers = []
            if has_cuda:
                cuda_opts = {
                    "device_id": 0,
                    "arena_extend_strategy": "kSameAsRequested",
                }
                if algo:
                    cuda_opts["cudnn_conv_algo_search"] = algo
                providers.append(("CUDAExecutionProvider", cuda_opts))
            if allow_dml and "DmlExecutionProvider" in avail:
                providers.append("DmlExecutionProvider")
            providers.append("CPUExecutionProvider")
            return providers

        if not has_gpu_ep:
            return self._create_cpu_session(model_path)

        def _session_options():
            so = ort.SessionOptions()
            so.log_severity_level = 2
            so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            return so

        def _open(algo: str):
            cand = ort.InferenceSession(model_path, sess_options=_session_options(), providers=_providers(algo))
            return cand, (cand.get_providers()[0] if cand.get_providers() else "CPUExecutionProvider")

        sess, active, last_exc = None, "CPUExecutionProvider", None

        # 1st attempt: fast cuDNN algorithm selection (see _cudnn_algo_from_env).
        tuned = self._cudnn_algo if has_cuda else ""
        tuned_failed = False
        if tuned:
            try:
                sess, active = _open(tuned)
            except Exception as exc:
                last_exc, sess = exc, None
            if sess is None or active != "CUDAExecutionProvider":
                # Either this ONNX Runtime rejects the option (it then quietly falls back to CPU instead of raising)
                # or CUDA itself is unavailable. Drop the session and retry with exactly the provider options used
                # before v3.3, so the option can never be the reason for running on the CPU.
                sess, active, tuned_failed = None, "CPUExecutionProvider", True
                self._cudnn_algo = ""  # do not pay for two attempts on every later model reload
                gc.collect()

        # Legacy attempt (ONNX Runtime default = EXHAUSTIVE search)
        if sess is None:
            try:
                sess, active = _open("")
            except Exception as exc:
                last_exc, sess = exc, None
            if sess is not None and tuned_failed and active == "CUDAExecutionProvider":
                print(
                    f"[Engine] Опцію cudnn_conv_algo_search={tuned} не прийнято цією версією ONNX Runtime — "
                    "працюємо зі стандартними налаштуваннями CUDA.",
                    flush=True,
                )

        if sess is None:
            self.gpu_error = str(last_exc)
            print(f"[Engine][УВАГА] Помилка ініціалізації GPU ({model_path}): {last_exc}", flush=True)
            return self._create_cpu_session(model_path)
        if has_cuda and active == "CPUExecutionProvider":
            self.gpu_error = "CUDAExecutionProvider не зміг завантажитись (ймовірно, відсутні CUDA/cuDNN DLL або невідповідність драйвера NVIDIA)."
        return sess, active

    def _resolve_model_paths(self):
        bria2 = os.path.join(self.models_dir, "bria-rmbg-2.0.onnx")
        rmbg14 = os.path.join(self.models_dir, "rmbg14.onnx")
        lama_fp32 = os.path.join(self.models_dir, "lama_fp32.onnx")
        lama_legacy = os.path.join(self.models_dir, "lama.onnx")

        if os.path.exists(bria2):
            self.matting_kind = "rmbg2"
            mat_path = bria2
        elif os.path.exists(rmbg14):
            self.matting_kind = "rmbg14"
            mat_path = rmbg14
        else:
            raise FileNotFoundError(
                f"Не знайдено модель маскування у {self.models_dir}. Запустіть download_models.py."
            )

        # Prefer pure FP32 LaMa (no DequantizeLinear nodes, 100% compatible with CUDA 13 / RTX 5060 Ti)
        lama_p = None
        if os.path.exists(lama_fp32) and os.path.getsize(lama_fp32) >= 180 * 1024 * 1024:
            lama_p = lama_fp32
        else:
            # Check if legacy lama.onnx is actually FP32 (> 180 MB) or quantized (< 120 MB)
            is_legacy_quantized = os.path.exists(lama_legacy) and os.path.getsize(lama_legacy) < 150 * 1024 * 1024
            if not os.path.exists(lama_legacy) or is_legacy_quantized:
                try:
                    import download_models
                    print("[Engine] Завантажуємо неквантизовану FP32 модель LaMa для GPU (198 MB)...", flush=True)
                    for u in [
                        "https://huggingface.co/Carve/LaMa-ONNX/resolve/main/lama_fp32.onnx",
                        "https://huggingface.co/edgetools/lama/resolve/main/lama_fp32.onnx",
                    ]:
                        if download_models.download_file(u, lama_fp32):
                            lama_p = lama_fp32
                            break
                except Exception as exc:
                    print(f"[Engine] Автозавантаження lama_fp32.onnx не вдалося: {exc}", flush=True)

            if lama_p is None:
                if os.path.exists(lama_legacy):
                    lama_p = lama_legacy
                else:
                    raise FileNotFoundError(
                        f"Не знайдено модель заливки lama_fp32.onnx у {self.models_dir}. Запустіть download_models.py."
                    )

        self.mat_path = mat_path
        self.lama_path = lama_p
        self._is_quant_lama = os.path.getsize(lama_p) < 150 * 1024 * 1024

    def _ensure_models_loaded(self, need_matting: bool = True, need_lama: bool = True, progress_cb=None):
        loading_mat = need_matting and (self.matting_sess is None)
        loading_lama = need_lama and (self.lama_sess is None)
        if not loading_mat and not loading_lama:
            return

        if progress_cb is not None:
            progress_cb(15, "Завантаження AI-моделей у GPU...")

        p1 = self.provider_name
        p2 = self.provider_name
        if loading_mat:
            self.matting_sess, p1 = self._create_session(self.mat_path, allow_dml=True)

        if loading_lama:
            if self._is_quant_lama:
                # Quantized legacy model fails DequantizeLinear on CUDA 13 and MatMul_5 on DirectML -> run safely on CPU
                print("[Engine] Виявлено стару квантовану lama.onnx — запускаємо на CPU (для GPU запустіть download_models.py).", flush=True)
                self.lama_sess, p2 = self._create_cpu_session(self.lama_path)
            else:
                self.lama_sess, p2 = self._create_session(self.lama_path, allow_dml=False)

        if loading_mat or loading_lama:
            providers_now = []
            if self.matting_sess is not None:
                providers_now.append(self.matting_sess.get_providers()[0])
            if self.lama_sess is not None:
                providers_now.append(self.lama_sess.get_providers()[0])
            cuda_p = [p for p in providers_now if "CUDA" in p]
            dml_p = [p for p in providers_now if "Dml" in p]
            self.provider_name = cuda_p[0] if cuda_p else (dml_p[0] if dml_p else "CPUExecutionProvider")

            if cuda_p and self.gpu_name in ("CPU", "GPU", "CPU (без прискорення GPU)"):
                self.gpu_name = self._detect_gpu_name()
            elif dml_p and not cuda_p:
                self.gpu_name = "DirectML GPU (маска) + CPU (заливка)"
                if not self.gpu_error:
                    self.gpu_error = "Встановлено DirectML замість CUDA. Для максимальної швидкості на RTX 5060 Ti запустіть fix_gpu_cuda.bat."
            elif not cuda_p and not dml_p:
                self.gpu_name = "CPU (без прискорення GPU)"

        if loading_lama and not self._scale_probed:
            self.lama_out_scale = 255.0
            try:
                in_names = [i.name for i in self.lama_sess.get_inputs()]
                probe_i = np.full((1, 3, 512, 512), 0.5, dtype=np.float32)
                probe_m = np.zeros((1, 1, 512, 512), dtype=np.float32)
                probe_out = self.lama_sess.run(None, {in_names[0]: probe_i, in_names[1]: probe_m})[0]
                self.lama_out_scale = 255.0 if float(np.mean(probe_out)) > 10.0 else 1.0
            except Exception as exc:
                print(f"[Engine] Probe LaMa scale fallback=255.0: {exc}", flush=True)
                self.lama_out_scale = 255.0
            self._scale_probed = True

        print(f"[Engine] Matting: {self.matting_kind} ({p1}), LaMa: ({p2}), Device: {self.gpu_name}", flush=True)

    # ------------------------------------------------------------------
    # 1. Foreground Subject Matting (1024x1024) with Shadow-Lift for Dark Clothing
    # ------------------------------------------------------------------
    def _run_matting_single(self, im_1024: np.ndarray) -> np.ndarray:
        if self.matting_kind == "rmbg2":
            mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
            std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
            im_norm = (im_1024 - mean) / std
        else:
            im_norm = im_1024 - 0.5

        inp = im_norm.transpose(2, 0, 1)[None, ...]
        in_info = self.matting_sess.get_inputs()[0]
        if "float16" in in_info.type:
            inp = inp.astype(np.float16)

        try:
            raw_res = self.matting_sess.run(None, {in_info.name: inp})[0]
        except Exception as exc:
            print(f"[Engine][УВАГА] Помилка GPU при маскуванні, перемикаємося на CPU: {exc}", flush=True)
            self.gpu_error = f"GPU fallback (маскування): {exc}"
            self.matting_sess, _ = self._create_cpu_session(self.mat_path)
            in_info = self.matting_sess.get_inputs()[0]
            if "float16" in in_info.type:
                inp = inp.astype(np.float16)
            else:
                inp = inp.astype(np.float32)
            raw_res = self.matting_sess.run(None, {in_info.name: inp})[0]

        out = np.squeeze(raw_res).astype(np.float32)
        del raw_res, inp
        if out.ndim == 3:
            out = out[0]
        mi, ma = float(out.min()), float(out.max())
        # Some ONNX exports of BRIA-RMBG-2.0 emit raw logits outside [0, 1] prior to sigmoid
        if mi < -0.05 or ma > 1.05:
            out = 1.0 / (1.0 + np.exp(-np.clip(out, -30.0, 30.0)))
            mi, ma = float(out.min()), float(out.max())
        if (ma - mi) < 0.5:
            # Nobody in the frame (an empty backdrop): the network answers with a faint blob. Stretching that blob to a
            # full 0..1 mask used to invent a "person" who was then protected and outlined. A weak answer stays weak.
            return np.clip(out, 0.0, 1.0)
        return (out - mi) / (ma - mi + 1e-8)

    def _predict_fg_raw(self, img_rgb_u8: np.ndarray, progress_cb=None, fast_mode: bool = False) -> np.ndarray:
        if progress_cb is not None:
            progress_cb(18, "Розпізнавання моделі та одягу (AI)...")
        im_1024 = cv2.resize(img_rgb_u8, (1024, 1024), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0
        m = self._run_matting_single(im_1024)

        # On dark / low-key photos, run a shadow-lifted pass so dark dresses & hair in shadow are seen clearly.
        # The same rule in both speed modes (it used to be 0.22 in the fast one, so the two modes outlined the
        # person differently on some dark photos); `fast_mode` is kept in the signature for compatibility only.
        p30_thr = 0.28
        if float(np.percentile(im_1024, 30)) < p30_thr:
            if progress_cb is not None:
                progress_cb(27, "Додатковий аналіз темного одягу й тіней...")
            gc.collect()
            im_lifted = np.power(np.clip(im_1024, 0.0, 1.0), 0.48)
            m_lift = self._run_matting_single(im_lifted)
            luma = 0.299 * im_1024[:, :, 0] + 0.587 * im_1024[:, :, 1] + 0.114 * im_1024[:, :, 2]
            dark_w = np.clip((0.36 - luma) / 0.20, 0.30, 1.0)
            m = np.maximum(m, m_lift * dark_w)
            del im_lifted, m_lift
            gc.collect()

        return np.clip(m * 255.0, 0, 255).astype(np.uint8)

    # ------------------------------------------------------------------
    # 1b. The scene of the frame (for the automatic choice of a preset)
    # ------------------------------------------------------------------
    SCENE_GRID = 256            # long side of the small grid the silhouette is measured on
    # median brightness of the backdrop (0..255) below which the frame is a dark key. 26 until 4.5.0; the owner's
    # dark-grey backdrop (about 31) is dark to him, his grey one (about 52) is not
    SCENE_DARK_LUMA = 40.0
    SCENE_CLOSE_VISIBLE = 0.37  # less than this share of the body is in the frame -> close-up
    SCENE_SMALL_HEAD = 0.15     # head narrower than this share of the visible figure -> the whole person is in the frame

    @staticmethod
    def _scene_person_mask(matte_u8: np.ndarray) -> np.ndarray:
        """
        The people of the frame on the small grid: the largest silhouette and everything of at least half its size
        (a second person standing apart). Lamps, softboxes on stands and specks are left out - they must not decide
        the framing.
        """
        bin_m = (matte_u8 > 102).astype(np.uint8)
        n, lbl, st, _ = cv2.connectedComponentsWithStats(bin_m, 8)
        if n <= 1:
            return np.zeros(matte_u8.shape, dtype=bool)
        areas = st[:, cv2.CC_STAT_AREA].astype(np.int64)
        peaks = np.zeros(n, dtype=np.uint8)
        np.maximum.at(peaks, lbl.ravel(), matte_u8.ravel())
        sure = peaks >= 184  # the model is certain somewhere inside (the rule of _clean_fg_mask)
        sure[0] = False
        if not sure.any():
            return np.zeros(matte_u8.shape, dtype=bool)
        keep = sure & (areas >= 0.5 * int(areas[sure].max()))
        return keep[lbl]

    @staticmethod
    def _longest_run(row: np.ndarray) -> int:
        """Length of the longest unbroken stretch of True in a 1-D boolean array."""
        if not row.any():
            return 0
        edges = np.flatnonzero(np.diff(np.concatenate(([False], row, [False])).astype(np.int8)))
        return int((edges[1::2] - edges[0::2]).max())

    def _scene_info(self, fg_raw_1024: np.ndarray, img_rgb_u8: np.ndarray, w: int, h: int) -> dict:
        """
        What kind of frame this is, measured before anything is cleaned:
          framing  "wide"   - the whole figure with the floor under it,
                   "medium" - the figure is cut by the bottom edge at the waist / hips / knees,
                   "close"  - head and shoulders,
                   "none"   - no person found;
          dark     the backdrop is dark (low key);
          kind     "dark" for a dark backdrop, otherwise the framing - the key a preset is chosen by.
        The framing is read from the silhouette alone:
          1. not cut by the bottom edge of the frame            -> the whole figure;
          2. cut, but the head is small against what is visible -> still the whole figure (only a hem, a train or
             the feet reach the edge): the head is about 1/8 of a standing person, measured as the width of the
             silhouette just under its top;
          3. otherwise, how much of the body is above the cut. The body height is estimated from the widest part
             of the silhouette (the largest circle that fits into it has a radius of about 0.11 body heights).
        """
        g = float(self.SCENE_GRID)
        sc = g / float(max(w, h, 1))
        gw, gh = max(8, int(round(w * sc))), max(8, int(round(h * sc)))
        matte = cv2.resize(fg_raw_1024, (gw, gh), interpolation=cv2.INTER_AREA)
        person = self._scene_person_mask(matte)

        # Brightness of the backdrop: everything that is neither a person nor an object, with a margin around them
        small = cv2.resize(img_rgb_u8, (gw, gh), interpolation=cv2.INTER_AREA).astype(np.float32)
        luma = 0.299 * small[:, :, 0] + 0.587 * small[:, :, 1] + 0.114 * small[:, :, 2]
        k = int(round(g * 0.03)) * 2 + 1
        near = cv2.dilate((matte > 76).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
        backdrop = near == 0
        backdrop_luma = float(np.median(luma[backdrop])) if int(backdrop.sum()) >= 0.02 * gw * gh else None
        dark = backdrop_luma is not None and backdrop_luma < self.SCENE_DARK_LUMA

        framing, cut, visible, height_share, head = "none", False, 0.0, 0.0, 0.0
        share = float(person.mean())
        rows = np.flatnonzero(person.any(axis=1))
        if rows.size and share >= 0.004:
            top, bottom = int(rows[0]), int(rows[-1]) + 1
            vis = float(bottom - top)
            height_share = vis / gh
            edge_rows = max(1, int(round(gh * 0.012)))
            contact = float(person[gh - edge_rows:].sum(axis=1).mean())
            cut = contact >= 0.05 * gw and contact >= 0.12 * vis
            # width of the head: the widest unbroken stretch of the silhouette in a band just under its top
            band_a = top + int(round(vis * 0.03))
            band_b = min(gh, max(band_a + 1, top + int(round(vis * 0.12))))
            head = max(self._longest_run(person[y]) for y in range(band_a, band_b)) / vis
            # the frame is thought to go on below its bottom edge: a body cut there keeps its width
            ext = np.vstack([person, np.repeat(person[-1:], gh // 2, axis=0)]).astype(np.uint8)
            ext = cv2.copyMakeBorder(ext, 1, 0, 1, 1, cv2.BORDER_CONSTANT, value=0)
            radius = float(cv2.distanceTransform(ext, cv2.DIST_L2, 3).max())
            visible = 0.11 * vis / max(radius, 1.0)
            if not cut or head < self.SCENE_SMALL_HEAD:
                framing = "wide"
            elif visible < self.SCENE_CLOSE_VISIBLE:
                framing = "close"
            else:
                framing = "medium"

        return {
            "kind": "dark" if dark else framing,
            "framing": framing,
            "dark": bool(dark),
            "backdrop_luma": None if backdrop_luma is None else round(backdrop_luma, 1),
            "person_share": round(share, 4),
            "person_height": round(height_share, 3),
            "cut": bool(cut),
            "visible": round(float(visible), 3),
            "head": round(float(head), 3),
        }

    def _clean_fg_mask(self, fg_raw_1024: np.ndarray, w: int, h: int, edge_protection: float):
        m = fg_raw_1024.astype(np.float32) / 255.0
        bin_m = (m > 0.40).astype(np.uint8)
        n, lbl, st, _ = cv2.connectedComponentsWithStats(bin_m, 8)
        keep_lut = np.zeros(n, dtype=np.uint8)
        best_idx = -1
        best_area = 0
        min_area = 0.002 * (1024 * 1024)
        for i in range(1, n):
            area = int(st[i, cv2.CC_STAT_AREA])
            if area < min_area:
                continue
            x0, y0, bw, bh = int(st[i, cv2.CC_STAT_LEFT]), int(st[i, cv2.CC_STAT_TOP]), int(st[i, cv2.CC_STAT_WIDTH]), int(st[i, cv2.CC_STAT_HEIGHT])
            sub_lbl = lbl[y0:y0 + bh, x0:x0 + bw]
            sub_m = m[y0:y0 + bh, x0:x0 + bw]
            peak = float(sub_m[sub_lbl == i].max())
            if peak >= 0.72:
                keep_lut[i] = 1
                if area > best_area:
                    best_area = area
                    best_idx = i

        clean_bin = keep_lut[lbl]

        # Core subject mask (main largest subject silhouette, separate from isolated lamps/stands)
        core_bin = (lbl == best_idx).astype(np.uint8) if best_idx > 0 else np.zeros_like(bin_m)

        # Tighter edge dilation so dirt/hair right next to feet & hem gets cleaned properly
        # 70% default -> ~5px at 1024 scale
        # Close tiny (< 7px) internal crevices (e.g. narrow shadow slits between arm & dress)
        clean_closed = cv2.morphologyEx(
            clean_bin, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        )
        dil_k = int(round(1 + (edge_protection / 100.0) * 6))
        if dil_k > 1 and dil_k % 2 == 0:
            dil_k += 1

        m_clean = np.maximum(m, clean_closed.astype(np.float32) * 0.85) * cv2.GaussianBlur(
            clean_closed.astype(np.float32), (5, 5), 0
        )
        if dil_k > 1:
            m_dil = cv2.dilate(m_clean, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dil_k, dil_k)))
        else:
            m_dil = m_clean
        m_dil = cv2.GaussianBlur(m_dil, (7, 7), 0)

        fg_full = cv2.resize(np.clip(m_dil * 255.0, 0, 255).astype(np.uint8), (w, h), interpolation=cv2.INTER_LINEAR)
        core_k = max(3, dil_k)
        core_closed = cv2.morphologyEx(
            core_bin, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        )
        core_dil = cv2.dilate(core_closed, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (core_k, core_k)))
        core_full = cv2.resize(core_dil * 255, (w, h), interpolation=cv2.INTER_LINEAR)
        return fg_full, core_full

    # ------------------------------------------------------------------
    # 2. Protection & Stand Detection Maps (1024px)
    # ------------------------------------------------------------------
    GEAR_BODY_K = 31             # px of the 1024 copy: a stand leg, a pole or a cable is thinner than this
    GEAR_STEP_COHERENCE = 0.75   # edges of a blob that point one way this much: a one-sided step, not a thin thing
    GEAR_BODY_STEP = 0.20        # a step-like blob is gear when this share of the light is missing / added in it
    GEAR_BODY_THIN = 0.16        # ...and a blob of thin lines when its lines are at least this strong

    @staticmethod
    def _edge_blobs_with_body(L: np.ndarray, gx: np.ndarray, gy: np.ndarray, grad: np.ndarray,
                              strong_edges: np.ndarray, labels: np.ndarray, stats: np.ndarray,
                              cand: np.ndarray) -> np.ndarray:
        """
        Which groups of strong edges are studio gear. `cand`: one flag per label 1..n (the groups big enough to
        be looked at); returns the flags of those that are gear. Everything on the 1024 copy, L in 0..255.
        Any long strong edge used to be gear, and gear is left untouched by every stage. Two things that are no
        gear at all were kept that way, with all the dirt inside them:
          - the hard edge of a cast shadow (under a leg, next to an arm). It is a one-sided step: light on one
            side, shadow on the other, nothing standing there;
          - a scratch on a lit floor: a thin line like a cable, but a faint one.
        Gear has a body. A leg, a pole or a cable is a thin dark (or shiny) thing: the backdrop is on BOTH its
        sides, and most of the light is missing in it (or added, on chrome). That is measured against the
        backdrop a little way off (what a closing / an opening with GEAR_BODY_K leaves), as a share of that
        backdrop, so it works on a black frame as on a white one.
          - a group whose edges point one way (a step): gear only when such a body is inside it
            (the outline of a dark train or of a softbox has thin parts; a shadow edge has none);
          - a group of thin lines: gear unless the lines are faint (a scratch takes away a tenth of the light,
            a cable nearly all of it; the folds of a white dress on a light floor about a third);
          - a group that touches the left, right or top border of the frame is gear as before: that is where
            stands, softboxes and reflectors come in. (Not the bottom border: the scratches of the floor
            nearest to the camera end there.)
        """
        sh, sw = L.shape
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (CleanVinylEngine.GEAR_BODY_K, CleanVinylEngine.GEAR_BODY_K))
        l_closed = cv2.morphologyEx(L, cv2.MORPH_CLOSE, k)
        l_opened = cv2.morphologyEx(L, cv2.MORPH_OPEN, k)
        body = np.maximum((l_closed - L) / (l_closed + 6.0), (L - l_opened) / (L + 6.0))
        sg = 7.0
        one_way = np.hypot(cv2.GaussianBlur(gx, (0, 0), sg), cv2.GaussianBlur(gy, (0, 0), sg)) / (cv2.GaussianBlur(grad, (0, 0), sg) + 1e-3)
        gear = np.zeros(cand.shape, dtype=bool)
        for i in np.flatnonzero(cand):
            x0, y0 = int(stats[i + 1, cv2.CC_STAT_LEFT]), int(stats[i + 1, cv2.CC_STAT_TOP])
            bw, bh = int(stats[i + 1, cv2.CC_STAT_WIDTH]), int(stats[i + 1, cv2.CC_STAT_HEIGHT])
            if x0 <= 2 or x0 + bw >= sw - 2 or y0 <= 2:
                gear[i] = True
                continue
            box = (slice(y0, y0 + bh), slice(x0, x0 + bw))
            m = labels[box] == (i + 1)
            edges = m & (strong_edges[box] > 0)
            step_like = bool(edges.any()) and float(np.median(one_way[box][edges])) >= CleanVinylEngine.GEAR_STEP_COHERENCE
            vals = body[box][m]
            if step_like:
                gear[i] = float(np.percentile(vals, 90)) >= CleanVinylEngine.GEAR_BODY_STEP
            else:
                gear[i] = float(np.percentile(vals, 95)) >= CleanVinylEngine.GEAR_BODY_THIN
        return gear

    def _compute_protection_maps_small(
        self,
        img_rgb_u8: np.ndarray,
        fg_mask_u8: np.ndarray,
        core_mask_u8: np.ndarray,
        smoke_strength: float,
        protect_smoke: bool,
        keep_shadows: bool,
        smoke_auto: bool = False,
        info: dict | None = None,
        gear_body: bool = False,
    ):
        """
        Returns (stand protection, stand removal, smoke protection, shadow) maps, uint8, long side 1024.
        gear_body: a group of strong edges counts as studio gear only when something stands there (see
            _edge_blobs_with_body). Without it every long strong edge is gear, as before - the hard edge of a
            cast shadow and a scratch on a lit floor included, and what is "gear" is left untouched.
        smoke_auto: protect smoke only when the frame really has it (see SMOKE_MIN_SHARE); without it everything
            smoke-like is protected, as before.
        info: optional dict that receives what was seen of smoke: "share" / "largest" (smoke-like areas and the
            biggest of them, as a share of the frame), "found" (enough of it to call it smoke) and "protected"
            (share of the frame the returned smoke map covers). Filled even when the protection is switched off.
        """
        h, w = img_rgb_u8.shape[:2]
        scale = 1024.0 / max(h, w)
        sw, sh = int(round(w * scale)), int(round(h * scale))
        small = cv2.resize(img_rgb_u8, (sw, sh), interpolation=cv2.INTER_AREA)
        lab = cv2.cvtColor(small, cv2.COLOR_RGB2LAB).astype(np.float32)
        L, A, B = lab[:, :, 0], lab[:, :, 1] - 128.0, lab[:, :, 2] - 128.0

        fg_s = cv2.resize(fg_mask_u8, (sw, sh), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
        core_s = cv2.resize(core_mask_u8, (sw, sh), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
        # Exclude the model's own contrast edge from being treated as studio gear/stands
        fg_border_excl = cv2.dilate((fg_s > 0.12).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))) > 0

        # A. Stands, tripods, cables & studio curtains
        bg_l = cv2.medianBlur(L.astype(np.uint8), 51).astype(np.float32)
        gx = cv2.Sobel(L, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(L, cv2.CV_32F, 0, 1, ksize=3)
        grad = np.hypot(gx, gy)
        strong_edges = (grad > 26.0).astype(np.uint8)
        # Strip long horizontal studio wall-to-floor corner lines BEFORE dilate so corners are never mistaken for stands/cables,
        # while keeping thin dark floor cables (dark trough surrounded by brighter floor above & below) protected!
        L_up10 = np.roll(L, 10, axis=0)
        L_dn10 = np.roll(L, -10, axis=0)
        L_mid_min = cv2.erode(L, np.ones((7, 1), np.uint8))
        is_dark_cable = L_mid_min < (np.minimum(L_up10, L_dn10) - 20.0)
        horiz_edge = ((np.abs(gy) > 2.0 * np.abs(gx)) & (grad > 16.0) & (~is_dark_cable)).astype(np.uint8)
        horiz_corner = cv2.morphologyEx(horiz_edge, cv2.MORPH_CLOSE, np.ones((3, 15), np.uint8))
        horiz_corner = cv2.morphologyEx(horiz_corner, cv2.MORPH_OPEN, np.ones((1, max(24, int(sw * 0.24))), np.uint8))
        horiz_corner = cv2.dilate(horiz_corner, np.ones((7, 7), np.uint8))
        strong_edges[horiz_corner > 0] = 0
        strong_edges[fg_border_excl] = 0
        k_line = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        edge_blobs = cv2.dilate(strong_edges, k_line)
        num_lbl, labels, stats, _ = cv2.connectedComponentsWithStats(edge_blobs, connectivity=8)
        edge_lut = np.zeros(num_lbl, dtype=np.float32)
        any_lut = np.zeros(num_lbl, dtype=np.float32)
        if num_lbl > 1:
            bw_e = stats[1:, cv2.CC_STAT_WIDTH]
            bh_e = stats[1:, cv2.CC_STAT_HEIGHT]
            area_e = stats[1:, cv2.CC_STAT_AREA]
            is_horiz_corner = (bw_e > 0.24 * sw) & (bh_e < 0.055 * sh) & ((bw_e / np.maximum(bh_e, 1)) > 5.0)
            valid_edge = ((area_e > 950) | (np.maximum(bw_e, bh_e) > 85)) & (~is_horiz_corner)
            any_lut[1:] = valid_edge.astype(np.float32)
            if gear_body and bool(valid_edge.any()):
                valid_edge = valid_edge & self._edge_blobs_with_body(L, gx, gy, grad, strong_edges, labels, stats, valid_edge)
            edge_lut[1:] = valid_edge.astype(np.float32)
        stand_mask = edge_lut[labels]
        # every group of strong edges, gear or not: a shadow edge is no gear, and no smoke either (see B)
        edges_any = any_lut[labels]

        # Large dark borders / curtains / lamps / edge-cropped caster feet (exclude tiny dark floor crumbs & model outline!)
        border_dark = ((L < 24.0) & (np.abs(L - bg_l) > 18.0)).astype(np.uint8)
        # Compare left/right edge dark strips against each row's OWN middle brightness so dark room vignettes are ignored!
        edge_strip = np.zeros_like(border_dark)
        edge_strip[:, :max(6, int(sw * 0.08))] = 1
        edge_strip[:, -max(6, int(sw * 0.08)):] = 1
        row_mid_l = np.median(L[:, int(sw * 0.16):int(sw * 0.84)], axis=1, keepdims=True)
        row_mid_l = cv2.GaussianBlur(row_mid_l.astype(np.float32), (1, 15), 0)
        solid_edge_dark = (
            (edge_strip > 0)
            & (core_s < 0.15)
            & (
                ((L < 4.5) & (row_mid_l > 8.5))
                | ((L < 18.0) & ((row_mid_l - L) > 13.0))
            )
        ).astype(np.uint8)
        border_dark = np.maximum(border_dark, solid_edge_dark)
        border_dark[horiz_corner > 0] = 0
        border_dark[fg_border_excl] = 0
        n_bd, lbl_bd, st_bd, _ = cv2.connectedComponentsWithStats(border_dark, connectivity=8)
        bd_lut = np.zeros(n_bd, dtype=np.uint8)
        if n_bd > 1:
            x1s = st_bd[1:, cv2.CC_STAT_LEFT]
            x2s = x1s + st_bd[1:, cv2.CC_STAT_WIDTH]
            bw_b = st_bd[1:, cv2.CC_STAT_WIDTH]
            bh_b = st_bd[1:, cv2.CC_STAT_HEIGHT]
            touches_lr = (x1s <= 2) | (x2s >= sw - 2)
            is_horiz_band = (bw_b > 0.25 * sw) & (bh_b < 0.06 * sh)
            valid_bd = (
                (st_bd[1:, cv2.CC_STAT_AREA] > 950)
                | (np.maximum(bw_b, bh_b) > 75)
                | (touches_lr & (st_bd[1:, cv2.CC_STAT_AREA] > 140))
            ) & (~is_horiz_band)
            bd_lut[1:] = valid_bd.astype(np.uint8)
        bd_keep = bd_lut[lbl_bd]
        stand_mask = np.maximum(stand_mask, cv2.dilate(bd_keep, k_line).astype(np.float32))
        stand_protect = cv2.GaussianBlur(cv2.dilate(stand_mask, np.ones((7, 7), np.uint8)), (15, 15), 0)

        # Precise thin/dark stand removal mask (strictly dark gear/cables/edge stands outside model core)
        separate_fg = ((fg_s > 0.45) & (core_s < 0.25)).astype(np.float32)
        dark_gear = ((L < 72.0) & (stand_mask > 0.3) & (core_s < 0.20)).astype(np.float32)
        # Include bottom-corner caster feet / equipment edges touching frame left/right borders even if slightly above L=24
        edge_gear = ((grad > 18.0) | (L < 38.0)) & (edge_strip > 0) & (stand_mask > 0.25) & (core_s < 0.15)
        stand_remove = np.maximum(separate_fg, np.maximum(dark_gear, edge_gear.astype(np.float32)))
        stand_remove = cv2.dilate(stand_remove, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)))
        stand_remove[core_s > 0.35] = 0.0

        # B. White & colored smoke protection
        smoke_mask = np.zeros((sh, sw), dtype=np.float32)
        want_smoke = bool(protect_smoke) and smoke_strength > 5
        if info is not None:
            info.update({"share": 0.0, "largest": 0.0, "found": False, "protected": 0.0})
        if want_smoke or (info is not None and smoke_strength > 5):
            # Smoke is looked for in the backdrop only. The person and the gear are left out of every average (instead of
            # being blurred into their surroundings): otherwise their contrast outline reads as "wisps" and a thick ring
            # around every person gets protected as smoke - nothing is cleaned or smoothed there.
            bg_only = ((fg_s < 0.06) & (stand_mask < 0.4) & (edges_any < 0.4)).astype(np.uint8)
            bg_only = cv2.erode(bg_only, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))).astype(np.float32)
            den5 = np.maximum(cv2.GaussianBlur(bg_only, (5, 5), 0), 1e-3)
            den35 = np.maximum(cv2.GaussianBlur(bg_only, (35, 35), 0), 1e-3)

            def band(x):
                return (cv2.GaussianBlur(x * bg_only, (5, 5), 0) / den5 - cv2.GaussianBlur(x * bg_only, (35, 35), 0) / den35) * bg_only

            def spread(x):
                return np.sqrt(np.maximum(0.0, cv2.GaussianBlur(x * bg_only, (35, 35), 0) / den35))

            l_wisp = band(L)
            wisp_rms = spread(l_wisp * l_wisp)
            a_wisp, b_wisp = band(A), band(B)
            chroma_wisp = spread(a_wisp * a_wisp + b_wisp * b_wisp)

            # Slider 80% default -> threshold ~1.45; higher slider -> lower threshold (protects fainter smoke!)
            thr_scale = 1.65 - (smoke_strength / 100.0) * 0.65  # 100% -> 1.00, 80% -> 1.13, 0% -> 1.65
            y_upper = np.linspace(1.0, 0.0, sh, dtype=np.float32)[:, None] > 0.45
            wisp_raw = (
                (wisp_rms > (1.30 * thr_scale)) | (chroma_wisp > (1.35 * thr_scale)) | ((L > 246.0) & y_upper)
            ) & (bg_only > 0)
            wisp_open = cv2.morphologyEx(
                wisp_raw.astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
            )
            n_sm, lbl_sm, st_sm, _ = cv2.connectedComponentsWithStats(wisp_open, 8)
            sm_lut = np.zeros(n_sm, dtype=np.float32)
            if n_sm > 1:
                sm_lut[1:] = (st_sm[1:, cv2.CC_STAT_AREA] > 1200).astype(np.float32)
            # How much of the frame looks like smoke at all, and how big the biggest such area is
            kept_areas = st_sm[1:, cv2.CC_STAT_AREA][sm_lut[1:] > 0] if n_sm > 1 else np.zeros(0)
            smoke_share = float(kept_areas.sum()) / float(sh * sw)
            smoke_largest = (float(kept_areas.max()) / float(sh * sw)) if kept_areas.size else 0.0
            smoke_found = smoke_share >= self.SMOKE_MIN_SHARE or smoke_largest >= self.SMOKE_MIN_CLOUD
            if want_smoke and (smoke_found or not smoke_auto):
                smoke_bin = sm_lut[lbl_sm]
                smoke_mask = cv2.GaussianBlur(
                    cv2.dilate(smoke_bin, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (33, 33))), (25, 25), 0
                )
            if info is not None:
                info.update({
                    "share": round(smoke_share, 4), "largest": round(smoke_largest, 4), "found": bool(smoke_found),
                    "protected": round(float((smoke_mask > 0.5).mean()), 4),
                })

        # C. Cast & contact shadows (multi-scale close catches both tight contact & wide full-body shadows!)
        if keep_shadows:
            l_256 = cv2.resize(L, (max(16, sw // 4), max(16, sh // 4)), interpolation=cv2.INTER_AREA)
            l_ref_256 = cv2.morphologyEx(l_256, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (45, 45)))
            l_floor_wide = cv2.resize(cv2.GaussianBlur(l_ref_256, (15, 15), 0), (sw, sh), interpolation=cv2.INTER_LINEAR)
            l_floor_tight = cv2.GaussianBlur(cv2.morphologyEx(L, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (65, 65))), (31, 31), 0)
            l_floor_ref = np.maximum(l_floor_wide, l_floor_tight)
            shadow_drop = np.clip((l_floor_ref - L - 4.5) / 14.5, 0.0, 1.0)
            shadow_smooth = cv2.GaussianBlur(shadow_drop, (17, 17), 0)
            fg_dist = cv2.distanceTransform((fg_s < 0.3).astype(np.uint8), cv2.DIST_L2, 5)
            prox = np.clip(1.0 - fg_dist / (0.68 * max(sh, sw)), 0.0, 1.0)
            shadow_mask = np.clip(shadow_smooth * (0.55 + 0.45 * prox), 0.0, 1.0)
        else:
            shadow_mask = np.zeros((sh, sw), dtype=np.float32)

        return (
            np.clip(stand_protect * 255, 0, 255).astype(np.uint8),
            np.clip(stand_remove * 255, 0, 255).astype(np.uint8),
            np.clip(smoke_mask * 255, 0, 255).astype(np.uint8),
            np.clip(shadow_mask * 255, 0, 255).astype(np.uint8),
        )

    # ------------------------------------------------------------------
    # 3. Vinyl Join Seam Detector (Multi-scale thin/wide ratio)
    # ------------------------------------------------------------------
    SEAM_LIGHT_EDGE = 8.0  # levels (0..255): a tone step this big right at a thin piece = the edge of a lit area
    SEAM_OWN_LINE = 0.30   # a piece must show, on its own profile, at least this share of what the search saw in it

    @staticmethod
    def _seam_piece_path(comp: np.ndarray, strength: np.ndarray, y0: int) -> np.ndarray:
        """
        Where a thin piece runs: for every column of its box, the row (of the frame at working size) where the
        search answered strongest; columns the piece skips are filled in from their neighbours, lone jumps are
        taken out (a median over 9 columns) and the rest is smoothed a little.
        """
        bh, bw = comp.shape
        s = np.where(comp, strength, -1.0)
        has = comp.any(axis=0)
        rows = np.argmax(s, axis=0).astype(np.float32)
        cols = np.arange(bw)
        path = np.interp(cols, cols[has], rows[has]).astype(np.float32)
        if bw >= 9:
            pad = np.pad(path, 4, mode="edge")
            path = np.median(np.lib.stride_tricks.sliding_window_view(pad, 9), axis=1).astype(np.float32)
            pad = np.pad(path, 4, mode="edge")
            path = np.convolve(pad, np.full(9, 1.0 / 9.0, dtype=np.float32), mode="valid").astype(np.float32)
        return path + float(y0)

    @staticmethod
    def _seam_piece_check(Ls: np.ndarray, backdrop_s: np.ndarray, piece: dict):
        """
        A thin piece of the seam search, looked at once more on its own: the tone of the backdrop across the
        piece, averaged along the whole piece (the person left out). "Across the piece" follows the piece itself,
        column by column (piece["path"]): a joint of two sheets is never quite straight, and across a straight
        line laid through a wavy or bent piece the line smears out and reads as "nothing there".
        Returns (line, step) or None when there is not enough backdrop around the piece to tell:
          line - how strongly that profile shows a thin line or a sharp edge at the piece, measured the way the
                 search measures it. The search averages along short stretches of rows turned by a few degrees;
                 where such a stretch crosses the slanted rim of a pool of light it answers as to a line, and a
                 row of such answers makes a "piece" that lies on nothing. Its own profile is a smooth slope;
          step - the step of the tone right at the line (levels, signed), the slope of the light taken out: the
                 two bands next to the line give the step, the two further out say how the light climbs or
                 falls anyway, on each side apart. A joint on a floor that gets lighter towards the camera
                 gives about zero; the straight edge of a lit area gives its height.
        """
        sh, sw = Ls.shape
        x0, _, bw, _ = piece["box"]
        xs = np.arange(x0, x0 + bw)
        line = piece["path"] if piece.get("path") is not None else piece["slope"] * xs + piece["offs"]
        n0 = max(4, int(round(0.0025 * sh)))          # the close band starts beyond the line and its rim...
        n1 = n0 + max(4, int(round(0.004 * sh)))      # ...and is this high
        f0 = max(n1 + 4, int(round(0.012 * sh)))      # the further band
        f1 = f0 + (n1 - n0)
        reach = f1 + 1
        d = np.arange(-reach, reach + 1)
        rows = np.rint(line[None, :] + d[:, None]).astype(np.int64)
        inside = (rows >= 0) & (rows < sh)
        rows = np.clip(rows, 0, sh - 1)
        cols = np.broadcast_to(xs[None, :], rows.shape)
        ok = inside & (backdrop_s[rows, cols] > 0.5)
        cnt = ok.sum(axis=1)
        if int(cnt.min()) < 0.3 * bw:
            return None
        prof = (np.where(ok, Ls[rows, cols], 0.0).sum(axis=1) / cnt).astype(np.float32).reshape(-1, 1)
        # the two signals of the search (see _detect_vinyl_seam_mask), on this one profile
        thin_sig = np.abs(cv2.GaussianBlur(prof, (1, 13), 0) - cv2.GaussianBlur(prof, (1, 3), 0))
        gy = np.zeros_like(prof)
        gy[1:-1] = np.abs(prof[2:] - prof[:-2])
        thin_step = np.maximum(0.0, gy - 1.3 * cv2.GaussianBlur(gy, (1, 13), 0))
        mid = slice(reach - 4, reach + 5)             # the piece itself is a few rows thick
        line_here = float((thin_sig + thin_step)[mid].max())

        def band(a: int, b: int) -> float:
            return float(prof[reach + a:reach + b].mean())

        a1, b1, a2, b2 = band(-n1, -n0), band(n0 + 1, n1 + 1), band(-f1, -f0), band(f0 + 1, f1 + 1)
        per_row = 0.5 * ((b2 - b1) + (a1 - a2)) / float(f0 - n0)   # how the light changes away from the line
        return line_here, (b1 - a1) - per_row * float(n0 + n1 + 1)

    @staticmethod
    def _seam_floor_in_view(spans, lead: dict, cand_rows: np.ndarray, allow_s: np.ndarray, tol: float) -> int:
        """
        How many columns of floor are in plain view between the pieces of one would-be line, along that line, with
        no line on them. (A joint is seen wherever the floor is seen: when more floor lies open between the pieces
        than the pieces are long, they are not one line.)
        spans: (first column, width) of every piece; lead: the piece that gives the line ("slope", "offs", "xc");
        cand_rows: the thin candidates of the search summed down the rows (np.cumsum(cand, axis=0));
        allow_s: 1 where the backdrop is seen (no person, gear or smoke); tol: how far from the line a piece may lie.
        "A line on them" is anything thin the search saw there, close to the line - also what it could not take as
        a piece (the joint running along the rim of a pool of light is such a stretch).
        """
        sh = allow_s.shape[0]
        xa = min(x0 for x0, _ in spans)
        xb = max(x0 + bw for x0, bw in spans)
        cols = np.arange(xa, xb)
        lined = np.zeros(cols.size, dtype=bool)
        for x0, bw in spans:
            lined[x0 - xa:x0 + bw - xa] = True
        line_y = lead["slope"] * cols + lead["offs"]
        rows_l = np.clip(np.rint(line_y).astype(np.int64), 0, sh - 1)
        near = tol + 0.004 * np.abs(cols - lead["xc"])
        r_hi = np.clip(np.rint(line_y + near).astype(np.int64), 0, sh - 1)
        r_lo = np.clip(np.rint(line_y - near).astype(np.int64) - 1, 0, sh - 1)
        lined |= (cand_rows[r_hi, cols] - cand_rows[r_lo, cols]) > 0
        return int(np.count_nonzero((allow_s[rows_l, cols] > 0.5) & ~lined))

    def _detect_vinyl_seam_mask(
        self,
        img_rgb_u8: np.ndarray,
        fg_mask_u8: np.ndarray,
        stand_s: np.ndarray,
        smoke_s: np.ndarray,
        seam_strength: float,
        edge_protection: float,
        fast_mode: bool = False,
        join: bool = True,
        skip_line: dict | None = None,
        step_ok_line: dict | None = None,
        info: dict | None = None,
    ) -> np.ndarray:
        """
        Thin, long, nearly horizontal lines of the floor: the joint of two backdrop sheets, tape, a crease.
        join: the person (or the gear) hides the middle of such a line, so what is seen of it are two or more pieces.
            They are judged together - a line counts when its visible pieces add up to a quarter of the frame width.
            (Judged one by one, the shorter side was dropped and the joint was removed on one side of the person
            only.) join=False judges every piece on its own, as the original program did.
            Two things are told from a joint only in this mode (the original program took both):
            - the sharp edge of a lit area - the rim of a pool of light, the shadow of a stool. A joint is a line
              ON the floor: the floor has the same tone on its two sides. Where the tone steps by SEAM_LIGHT_EDGE
              levels right at the line (the slope of the light taken out), two differently lit areas meet there,
              and a strip repaired along that edge only smears the light. A slanted edge of that kind gives
              "pieces" that lie on nothing at all; they do not show in their own profile (_seam_piece_check);
            - pieces that stand at one height by chance: a scratch at the right border and the shadow line under
              a leg at the left one. A joint is seen wherever the floor is seen, so between the pieces of one
              joint the floor is mostly hidden. When more of the floor between them is in plain view (with no
              line on it) than the pieces themselves are long, they are not one line.
        skip_line: {"row", "slope", "half"} in pixels of the frame - a line that belongs to the corner tool (the
            wall-floor corner). Nothing is marked along it: a repaired strip there would only blur the corner on
            one side and hide it from the corner tool.
        step_ok_line: the wall-floor corner of the frame when no tool takes it (the same form). The tone does step
            there, and a crease in the corner is still repaired as a line, as before (see _whole_line_repair_only).
        info: a dict that receives what the search saw (join only): "pieces" - every thin piece with its place
            (shares of the frame), its numbers and why it was dropped, if it was; "groups" - the lines tried, with
            their length, their numbers and the verdict. For the self-checks and for looking into a frame.
        """
        h, w = img_rgb_u8.shape[:2]
        max_dim = 1400.0 if fast_mode else 2400.0
        scale = min(max_dim / max(h, w), 1.0)
        sw, sh = int(round(w * scale)), int(round(h * scale))
        Ls = cv2.cvtColor(cv2.resize(img_rgb_u8, (sw, sh), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2GRAY).astype(np.float32)

        # Allow seam cleanup closer to legs/dress & beside stands without leaving short stubs
        fg_s = cv2.resize(fg_mask_u8, (sw, sh), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
        if edge_protection < 80:
            fg_s = cv2.erode(fg_s, np.ones((5, 5), np.uint8))
        st_s = cv2.resize(stand_s, (sw, sh), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0
        sm_s = cv2.resize(smoke_s, (sw, sh), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0
        allow_s = ((fg_s < 0.40) & (st_s < 0.55) & (sm_s < 0.50)).astype(np.float32)
        # (the pieces are checked on everything but the person: the edge of a shadow is often inside a zone kept
        # as gear, and "no backdrop there to tell" would let it through)
        not_person_s = (fg_s < 0.40).astype(np.float32)

        box_w = 110 if fast_mode else 160
        den_min = 18.0 if fast_mode else 28.0
        angles = (-1.6, 0.0, 1.6) if fast_mode else (-2.5, -1.2, 0.0, 1.2, 2.5)

        best_thin = np.zeros((sh, sw), dtype=np.float32)
        best_wide = np.zeros((sh, sw), dtype=np.float32)
        for angle in angles:
            M = cv2.getRotationMatrix2D((sw / 2.0, sh / 2.0), angle, 1.0)
            M_inv = cv2.getRotationMatrix2D((sw / 2.0, sh / 2.0), -angle, 1.0)
            Lr = cv2.warpAffine(Ls, M, (sw, sh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            ar = cv2.warpAffine(allow_s, M, (sw, sh), flags=cv2.INTER_LINEAR)

            num = cv2.boxFilter(Lr * ar, -1, (box_w, 1), normalize=False)
            den = cv2.boxFilter(ar, -1, (box_w, 1), normalize=False) + 1e-4
            L_horiz = num / den

            L_1 = cv2.GaussianBlur(L_horiz, (1, 3), 0)
            L_13 = cv2.GaussianBlur(L_horiz, (1, 13), 0)
            L_55 = cv2.GaussianBlur(L_horiz, (1, 55), 0)

            thin_sig = np.abs(L_13 - L_1)
            gy = np.abs(cv2.Sobel(L_horiz, cv2.CV_32F, 0, 1, ksize=3)) / 4.0
            gy_13 = cv2.GaussianBlur(gy, (1, 13), 0)
            thin_step = np.maximum(0.0, gy - 1.3 * gy_13)
            wide_sig = np.abs(L_55 - L_13)

            valid = (den > den_min) * (ar > 0.4)
            best_thin = np.maximum(best_thin, cv2.warpAffine((thin_sig + thin_step) * valid, M_inv, (sw, sh)))
            best_wide = np.maximum(best_wide, cv2.warpAffine(wide_sig * valid, M_inv, (sw, sh)))

        best_thin[:int(0.45 * sh), :] = 0.0
        best_thin[int(0.97 * sh):, :] = 0.0
        if skip_line is not None:
            xs_l = np.arange(sw, dtype=np.float32)
            line_y = (float(skip_line["row"]) + float(skip_line["slope"]) * ((xs_l + 0.5) / scale - 0.5 - (w - 1) / 2.0) + 0.5) * scale - 0.5
            half_l = max(6.0, float(skip_line.get("half", 0.012 * h)) * scale)
            best_thin[np.abs(np.arange(sh, dtype=np.float32)[:, None] - line_y[None, :]) <= half_l] = 0.0

        # Higher seam_strength -> detects fainter vinyl seams too
        thin_thr = max(0.28, 0.72 - (seam_strength / 100.0) * 0.32)  # 85% -> 0.45
        # "thin" means the same strip of the real floor whatever the working size is (13 px at 2400 = 7.6 px at 1400)
        thick_lim = 13.0 * (max_dim / 2400.0)
        cand_b = best_thin > thin_thr
        if join:
            # A dark line answers over many rows, so the band above the threshold got thick and the line was dropped
            # as "not thin": the more visible the joint, the surer it stayed in the photo. The thickness of a line is
            # therefore judged at 40% of its own strength - a hair-thin line stays thin however dark it is. (For a
            # faint line 40% of its strength is below the threshold, so nothing changes for it.)
            reach = int(round(1.5 * thick_lim)) * 2 + 1
            cand_b &= best_thin > 0.4 * cv2.dilate(best_thin, np.ones((reach, 1), np.uint8))
        cand = cand_b.astype(np.uint8)
        close_w = 75 if fast_mode else 110
        cand_horiz = cv2.morphologyEx(cand, cv2.MORPH_CLOSE, np.ones((1, close_w), np.uint8))
        num_lbl, labels, stats, _ = cv2.connectedComponentsWithStats(cand_horiz, connectivity=8)

        seam_s = np.zeros((sh, sw), dtype=np.uint8)
        # Every thin piece: where it is, the straight line through it, how line-like it is (thin against wide signal)
        min_w = (0.05 if join else 0.24) * sw
        pieces = []
        for idx in range(1, num_lbl):
            bw, bh = int(stats[idx, cv2.CC_STAT_WIDTH]), int(stats[idx, cv2.CC_STAT_HEIGHT])
            area = stats[idx, cv2.CC_STAT_AREA]
            if bw > min_w and (area / max(bw, 1)) < thick_lim and bh < 0.04 * sh:
                x0, y0 = int(stats[idx, cv2.CC_STAT_LEFT]), int(stats[idx, cv2.CC_STAT_TOP])
                comp = (labels[y0:y0 + bh, x0:x0 + bw] == idx) & (cand[y0:y0 + bh, x0:x0 + bw] > 0)
                if not comp.any():
                    continue
                ya, yb = max(0, y0 - 7), min(sh, y0 + bh + 7)  # the piece with 7 rows above and below it
                tall = np.zeros((yb - ya, bw), dtype=np.uint8)
                tall[y0 - ya:y0 - ya + bh] = comp
                band_dil = cv2.dilate(tall, np.ones((15, 1), np.uint8)) > 0
                mean_thin = float(best_thin[y0:y0 + bh, x0:x0 + bw][comp].mean())
                mean_wide = float(best_wide[ya:yb, x0:x0 + bw][band_dil].mean())
                piece = {"box": (x0, y0, bw, bh), "comp": comp, "thin": mean_thin, "wide": mean_wide, "bw": bw}
                if join:
                    ys_p, xs_p = np.nonzero(comp)
                    # (the piece may hold a couple of points only: a fit through one column has no direction)
                    fit_ok = bw >= 40 and int(xs_p.max()) - int(xs_p.min()) >= 20
                    slope, offs = (np.polyfit(xs_p + x0, ys_p + y0, 1) if fit_ok else (0.0, float(ys_p.mean()) + y0))
                    if abs(slope) > 0.06:  # steeper than the search looks for: take the piece as level
                        slope, offs = 0.0, float(ys_p.mean()) + y0
                    piece.update(slope=float(slope), offs=float(offs), xc=x0 + 0.5 * bw)
                    piece["path"] = self._seam_piece_path(comp, best_thin[y0:y0 + bh, x0:x0 + bw], y0)
                    in_corner = False
                    if step_ok_line is not None:
                        xc_f = (piece["xc"] + 0.5) / scale - 0.5
                        yc_f = (piece["slope"] * piece["xc"] + piece["offs"] + 0.5) / scale - 0.5
                        y_cor = float(step_ok_line["row"]) + float(step_ok_line["slope"]) * (xc_f - (w - 1) / 2.0)
                        in_corner = abs(yc_f - y_cor) <= float(step_ok_line.get("half", 0.012 * h))
                    why = None
                    own = None if in_corner else self._seam_piece_check(Ls, not_person_s, piece)
                    if own is not None:
                        if abs(own[1]) >= self.SEAM_LIGHT_EDGE:
                            why = "edge of light"     # two differently lit areas meet there: not a joint
                        elif own[0] < self.SEAM_OWN_LINE * mean_thin:
                            why = "no line of its own"
                    if info is not None:
                        info.setdefault("pieces", []).append({
                            "x0": x0 / sw, "x1": (x0 + bw) / sw, "y0": y0 / sh, "y1": (y0 + bh) / sh,
                            "thin": mean_thin, "wide": mean_wide, "in_corner": bool(in_corner),
                            "own": None if own is None else float(own[0]), "step": None if own is None else float(own[1]),
                            "dropped": why,
                        })
                    if why is not None:
                        continue
                    piece["no"] = len(info["pieces"]) - 1 if info is not None else -1
                pieces.append(piece)

        accepted = []
        if not join:
            accepted = [pc for pc in pieces if pc["thin"] / (pc["wide"] + 0.05) >= 1.05]
        else:
            pieces.sort(key=lambda pc: -pc["bw"])
            tol = max(5.0 * (max_dim / 2400.0), 0.005 * sh)
            free = [True] * len(pieces)
            cand_rows = None
            for i, lead in enumerate(pieces):
                if not free[i] or lead["bw"] < 0.12 * sw:
                    continue  # a line is started by a piece long enough to give its direction
                group = [i]
                for j, other in enumerate(pieces):
                    if j == i or not free[j]:
                        continue
                    y_other = other["slope"] * other["xc"] + other["offs"]
                    y_line = lead["slope"] * other["xc"] + lead["offs"]
                    if abs(y_other - y_line) > tol + 0.004 * abs(other["xc"] - lead["xc"]):
                        continue
                    ox0, ox1 = other["box"][0], other["box"][0] + other["bw"]
                    side_by_side = all(
                        ox1 <= pieces[g]["box"][0] + 0.02 * sw or ox0 >= pieces[g]["box"][0] + pieces[g]["bw"] - 0.02 * sw
                        for g in group
                    )
                    if side_by_side:  # one above the other would be two lines, not two pieces of one
                        group.append(j)
                total_w = float(sum(pieces[g]["bw"] for g in group))
                thin_g = sum(pieces[g]["thin"] * pieces[g]["bw"] for g in group) / total_w
                wide_g = sum(pieces[g]["wide"] * pieces[g]["bw"] for g in group) / total_w
                for g in group:
                    free[g] = False
                if len(group) > 1:
                    if cand_rows is None:
                        cand_rows = np.cumsum(cand, axis=0, dtype=np.int32)
                    in_view = self._seam_floor_in_view(
                        [(pieces[g]["box"][0], pieces[g]["bw"]) for g in group], lead, cand_rows, allow_s, tol)
                else:
                    in_view = 0
                is_line = in_view <= total_w and total_w > 0.24 * sw and thin_g / (wide_g + 0.05) >= 1.05
                if info is not None:
                    info.setdefault("groups", []).append({
                        "pieces": [pieces[g]["no"] for g in group], "length": total_w / sw, "in_view": in_view / sw,
                        "thin": thin_g, "wide": wide_g, "accepted": bool(is_line),
                    })
                if is_line:
                    accepted.extend(pieces[g] for g in group)
        for pc in accepted:
            x0, y0, bw, bh = pc["box"]
            seam_s[y0:y0 + bh, x0:x0 + bw][pc["comp"]] = 255

        # Bridge small horizontal gaps along confirmed seams near stands/dress edges
        if np.any(seam_s > 0):
            seam_s = cv2.morphologyEx(seam_s, cv2.MORPH_CLOSE, np.ones((1, 45), np.uint8))
            seam_s[st_s > 0.65] = 0
        seam_s = cv2.dilate(seam_s, np.ones((13, 11), np.uint8))
        out = (cv2.resize(seam_s, (w, h), interpolation=cv2.INTER_LINEAR) > 80).astype(np.uint8)
        # Never paint into core subject
        return out

    # ------------------------------------------------------------------
    # 4. Dust, Crumbs, Hair & Scuff Spots Detector
    # ------------------------------------------------------------------
    # Local noise against the noise of the whole frame (their ratio, cell by cell).
    # An evenly lit backdrop: the ratio stays within about 0.9-1.25, and the frame noise is the right measure
    # everywhere. Nothing changes below GRAIN_LOCAL_FROM; the local value is used in full from GRAIN_LOCAL_FULL up
    # (a rare cell).
    # A frame lit unevenly - a dark backdrop with a pool of light, a dark wall over a lit floor: the frame noise is
    # the noise of its dark majority, the lit parts reach 1.6-2.1. There the local value is used wherever it is the
    # higher one. "Unevenly" is read from the ratio that a tenth of the backdrop exceeds: from GRAIN_UNEVEN_FROM
    # (still even) to GRAIN_UNEVEN_FULL.
    GRAIN_LOCAL_FROM = 1.30
    GRAIN_LOCAL_FULL = 1.60
    GRAIN_UNEVEN_FROM = 1.28
    GRAIN_UNEVEN_FULL = 1.45
    GRAIN_LOCAL_CELLS = 45  # cells along the long side of the frame

    @classmethod
    def _local_grain_gain(cls, hp_abs: np.ndarray, valid: np.ndarray, grain_frame: float) -> np.ndarray | None:
        """
        How much noisier every part of the frame is than the frame as a whole (>= 1), on a coarse grid; None when
        no part is - the usual case of an evenly lit backdrop, where the dust search then works exactly as before.
        hp_abs: |pixel - its smoothed neighbourhood| on the grid the frame noise was measured on,
        valid: the pixels that count (not the person), grain_frame: the noise of the whole frame (same measure).
        The noise of a camera grows with the light, so a pool of light on a dark backdrop is far noisier than the
        dark wall the frame noise is measured on. The local value is a median, cell by cell: dust and edges, which
        are a small part of a cell, do not raise it.
        """
        hh, ww = hp_abs.shape[:2]
        b = max(8, int(round(max(hh, ww) / float(cls.GRAIN_LOCAL_CELLS))))
        ny, nx = -(-hh // b), -(-ww // b)
        if ny < 2 or nx < 2:
            return None
        cells = np.full((ny * b, nx * b), np.nan, dtype=np.float32)
        cells[:hh, :ww] = np.where(valid, hp_abs, np.float32(np.nan))
        cells = cells.reshape(ny, b, nx, b).transpose(0, 2, 1, 3).reshape(ny, nx, b * b)
        seen = np.count_nonzero(~np.isnan(cells), axis=2)
        enough = seen >= 0.25 * b * b
        if not enough.any():
            return None
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # cells with nothing but the person in them
            med = np.nanmedian(cells, axis=2).astype(np.float32) * np.float32(1.4826)
        del cells
        # cells that are mostly the person take the value of their neighbours
        wgt = enough.astype(np.float32)
        num = cv2.GaussianBlur(np.where(enough, med, np.float32(0.0)), (0, 0), 1.0)
        den = cv2.GaussianBlur(wgt, (0, 0), 1.0)
        loc = np.where(enough, med, np.where(den > 1e-3, num / np.maximum(den, 1e-3), np.float32(grain_frame)))
        loc = cv2.GaussianBlur(loc.astype(np.float32), (0, 0), 0.8)
        ratio = loc / np.float32(max(float(grain_frame), 1e-6))
        uneven = float(np.clip((float(np.percentile(ratio[enough], 90)) - cls.GRAIN_UNEVEN_FROM)
                               / (cls.GRAIN_UNEVEN_FULL - cls.GRAIN_UNEVEN_FROM), 0.0, 1.0))
        start = cls.GRAIN_LOCAL_FROM + (1.0 - cls.GRAIN_LOCAL_FROM) * uneven
        full = cls.GRAIN_LOCAL_FULL + (1.0 - cls.GRAIN_LOCAL_FULL) * uneven
        if float(ratio.max()) <= start:
            return None
        share = np.clip((ratio - start) / max(full - start, 1e-6), 0.0, 1.0)
        return (1.0 + share * np.maximum(ratio - 1.0, 0.0)).astype(np.float32)

    # A dirty spot INSIDE a cast shadow. The search drops every blob of more than a few pixels that lies in a
    # shadow: the darker parts of a shadow are the shadow itself. A scuff mark under a hand's shadow was kept with
    # them. It is told apart by what a part of a shadow is not, all at once:
    #   small and compact; clearly darker than the shadow around it (PEAK x the threshold of the place, which is
    #   already more than twice the usual one inside a shadow); the shadow around it is even on every side and
    #   empty of other finds (RING_BUSY) - so not the soft rim of the shadow, not a fold of it, not the place
    #   where two shadows cross (there the lit floor comes up to the dark patch); it does not touch the person
    #   or the gear - so not a contact shadow.
    #   "Even": the shadow around the spot (the darkest against the lightest twentieth of the ring) varies by less
    #   than RING_DEPTH of the depth of the spot, and never by more than RING_FLAT_MAX levels.
    # Only dark spots: a light patch inside a shadow is a gap in the shadow.
    # What cannot be told apart: the small shadow of a small thing that lies wholly inside a bigger shadow, away
    # from the thing itself. It goes too (the eraser of the big window brings it back).
    # The limits come from the owner's frames (2048 / 1400 px working copies):
    #   the scuff inside a hand's shadow on the grey floor: 1.36 / 1.41 x the threshold, its surroundings vary by
    #   0.61 / 0.50 of its depth (the shadow of a hand is small, its rim is near);
    #   faint patches along the soft rim of a pool of light on the black floor: 1.07 and 1.13 x the threshold;
    #   a piece of a hard shadow edge: 4.6 x the threshold, surroundings vary by 0.98 of its depth.
    SHADOW_SPOT_MAX_DIM = 0.035   # of the long side
    SHADOW_SPOT_PEAK = 1.25
    SHADOW_SPOT_FILL = 0.30
    SHADOW_SPOT_ASPECT = 3.5
    SHADOW_SPOT_RING_DEPTH = 0.75
    SHADOW_SPOT_RING_FLAT_MAX = 12.0   # levels (0..255)
    SHADOW_SPOT_RING_BUSY = 0.08
    SHADOW_SPOT_TRY = 600

    @classmethod
    def _shadow_spots(cls, idxs, stats, labels, spot_cand, dark_diff, d_thr_map, L, L_med, bg_safe, low_thr: float,
                      info: list | None = None) -> np.ndarray:
        """
        The blobs `idxs` (labels of the medium pass that lie in a cast shadow) which are dirt and not shadow (see
        SHADOW_SPOT_* above), as a mask of the working size. A blob that qualifies is taken whole: its darkest part
        passed the (raised) threshold of the shadow, the rest of it is added down to `low_thr`, otherwise the repair
        would cut the middle out and leave the rim as a ring.
        """
        sh, sw = labels.shape
        out = np.zeros((sh, sw), dtype=np.uint8)
        lim = cls.SHADOW_SPOT_MAX_DIM * max(sh, sw)
        for idx in list(idxs)[:cls.SHADOW_SPOT_TRY]:
            x, y, bw, bh, area = (int(v) for v in stats[idx, :5])
            why = None
            if max(bw, bh) > lim:
                why = "large"
            elif area < cls.SHADOW_SPOT_FILL * bw * bh or max(bw, bh) > cls.SHADOW_SPOT_ASPECT * max(1, min(bw, bh)):
                why = "not compact"
            m = max(6, int(round(0.5 * max(bw, bh))))
            x0, x1, y0, y1 = max(0, x - m), min(sw, x + bw + m), max(0, y - m), min(sh, y + bh + m)
            box = (slice(y0, y1), slice(x0, x1))
            comp = labels[box] == idx
            peak = flat = busy = None
            depth = 0.0
            if why is None:
                dd = dark_diff[box]
                # (how dark the spot is, is read from a slightly smoothed copy: in a faint patch of a dark frame
                # single pixels stick out by half as much again, in a real spot they do not)
                dd_s = cv2.GaussianBlur(dd, (0, 0), 1.2)
                peak = float((dd_s[comp] / np.maximum(d_thr_map[box][comp], 1e-3)).max())
                depth = float(dd_s[comp].max())
                if peak < cls.SHADOW_SPOT_PEAK or float((L[box][comp] - L_med[box][comp]).mean()) >= 0.0:
                    why = "faint"
            if why is None:
                near = cv2.dilate(comp.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
                ring = ~near
                if (x1 - x0) < bw + 2 * m or (y1 - y0) < bh + 2 * m or not bool(bg_safe[box].all()):
                    why = "touches the person, the gear or the border"
                else:
                    ring_l = L_med[box][ring]
                    flat = float(np.percentile(ring_l, 95) - np.percentile(ring_l, 5))
                    busy = float(np.count_nonzero(spot_cand[box][ring])) / float(max(1, ring_l.size))
                    if flat > min(cls.SHADOW_SPOT_RING_FLAT_MAX, cls.SHADOW_SPOT_RING_DEPTH * depth):
                        why = "the shadow around it is not even"
                    elif busy > cls.SHADOW_SPOT_RING_BUSY:
                        why = "other finds around it"
            if why is None:
                # the whole spot: what hangs together with its dark middle, down to the low threshold
                soft = ((dark_diff[box] > low_thr) | comp).astype(np.uint8)
                n_s, lab_s = cv2.connectedComponents(soft, connectivity=8)
                keep = np.isin(lab_s, np.unique(lab_s[comp]))
                out[box][keep] = 255
            if info is not None:
                info.append({"x": (x + 0.5 * bw) / sw, "y": (y + 0.5 * bh) / sh, "w": bw / sw, "h": bh / sh, "area": area,
                             "peak": peak, "depth": depth, "ring_flat": flat, "ring_busy": busy,
                             "taken": why is None, "why": why})
        return out

    def _detect_spots_mask(
        self,
        img_rgb_u8: np.ndarray,
        fg_mask_u8: np.ndarray,
        stand_s: np.ndarray,
        smoke_s: np.ndarray,
        shadow_s: np.ndarray,
        spots_strength: float,
        fast_mode: bool = False,
        frac_fine: bool = True,
        frac_med: bool = True,
        frac_large: bool = True,
        local_grain: bool = False,
        shadow_spots: bool = False,
        info: dict | None = None,
    ):
        """
        shadow_spots: a dirty spot inside a cast shadow is found too (see SHADOW_SPOT_* above); without it nothing
        larger than a speck is ever touched inside a shadow, as in the original program.
        info: a dict that receives "shadow_spots" - every blob tried by that rule, with its numbers and the verdict.
        local_grain: the fine pass judges every place against the noise found THERE, wherever that is clearly above
        the noise of the frame as a whole (see _local_grain_gain). A dark frame with a pool of light needs it: the
        frame noise is measured on the dark majority, the lit floor is twice as noisy, and that plain noise was
        taken for dust all over the pool. Where the noise is even the thresholds are exactly the former ones.
        """
        if not (frac_fine or frac_med or frac_large) or spots_strength <= 0:
            return np.zeros(img_rgb_u8.shape[:2], dtype=np.uint8), 1.5

        h, w = img_rgb_u8.shape[:2]
        scale = min((1400.0 if fast_mode else 2048.0) / max(h, w), 1.0)
        sw, sh = int(round(w * scale)), int(round(h * scale))
        small = cv2.resize(img_rgb_u8, (sw, sh), interpolation=cv2.INTER_AREA)
        lab = cv2.cvtColor(small, cv2.COLOR_RGB2LAB).astype(np.float32)
        L, A, B = lab[:, :, 0], lab[:, :, 1], lab[:, :, 2]

        L_med = cv2.medianBlur(L.astype(np.uint8), 31).astype(np.float32)
        A_med = cv2.medianBlur(A.astype(np.uint8), 35).astype(np.float32)
        B_med = cv2.medianBlur(B.astype(np.uint8), 35).astype(np.float32)

        dark_diff = np.maximum(0.0, L_med - L)
        bright_diff = np.maximum(0.0, L - L_med)
        chroma_diff = np.hypot(A - A_med, B - B_med)

        fg_m = cv2.resize(fg_mask_u8, (sw, sh), interpolation=cv2.INTER_AREA)
        fg_guard_s = cv2.dilate((fg_m > 22).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
        st_m = cv2.resize(stand_s, (sw, sh), interpolation=cv2.INTER_LINEAR)
        sm_m = cv2.resize(smoke_s, (sw, sh), interpolation=cv2.INTER_LINEAR)
        sh_m = cv2.resize(shadow_s, (sw, sh), interpolation=cv2.INTER_LINEAR)

        bg_safe_geom = (fg_guard_s == 0) & (st_m < 75) & (sm_m < 65)
        bg_ok = bg_safe_geom & (L_med > 16.0)
        bg_lit = bg_ok & (L_med > 26.0)
        hp1 = np.abs(L - cv2.GaussianBlur(L, (5, 5), 0))
        if np.any(bg_lit):
            grain_sigma = max(0.75, float(np.median(hp1[bg_lit])) * 1.4826)
        elif np.any(bg_ok):
            grain_sigma = max(0.75, float(np.median(hp1[bg_ok])) * 1.4826)
        else:
            grain_sigma = 1.5

        # Sensitivity scale from Spots slider (75% default -> 1.03, 100% -> 0.80, 150%+ turbo -> 0.62)
        sens = max(0.62, 1.72 - (spots_strength / 100.0) * 0.92)
        dark_thr = max(3.6, 2.5 * grain_sigma * sens)
        bright_thr = max(5.0, 3.3 * grain_sigma * sens)

        # In deep dark zones (L < 34) and inside cast shadows, avoid picking up subtle gradient/shadow rim as spots
        shadow_zone = L_med < 34.0
        shadow_damp = 1.0 + 1.35 * np.clip((sh_m - 35.0) / 110.0, 0.0, 1.0)
        d_thr_map = np.where(shadow_zone, dark_thr * 2.10, dark_thr) * shadow_damp
        b_thr_map = np.where(shadow_zone, bright_thr * 1.85, bright_thr) * shadow_damp
        # Disable chroma-only triggers inside shadows/dark areas so warm/cool falloff never marks yellow spots
        chroma_allowed = (~shadow_zone) & (sh_m < 35.0)
        c_thr_map = 4.8 * sens

        # Still catch unmistakable bright dust/lint on very dark vinyl (L <= 16)
        bright_on_dark = bg_safe_geom & (L_med <= 16.0) & (bright_diff > max(16.0, bright_thr * 2.7))
        spot_cand = (
            (bg_ok & ((dark_diff > d_thr_map) | (bright_diff > b_thr_map) | (chroma_allowed & (chroma_diff > c_thr_map))))
            | bright_on_dark
        ).astype(np.uint8)
        pad_s = max(4, min(12, int(0.012 * min(sh, sw))))
        spot_cand[:pad_s, :] = 0; spot_cand[-pad_s:, :] = 0; spot_cand[:, :pad_s] = 0; spot_cand[:, -pad_s:] = 0

        num_lbl, labels, stats, _ = cv2.connectedComponentsWithStats(spot_cand, connectivity=8)
        spot_lut = np.zeros(num_lbl, dtype=np.uint8)
        if num_lbl > 1:
            areas = stats[1:, cv2.CC_STAT_AREA].astype(np.float32)
            max_dim = np.maximum(stats[1:, cv2.CC_STAT_WIDTH], stats[1:, cv2.CC_STAT_HEIGHT])
            sh_sums = np.bincount(labels.ravel(), weights=sh_m.ravel(), minlength=num_lbl)[1:]
            sh_means = sh_sums / np.maximum(1.0, areas)
            frac_ok = (
                ((areas <= 45) & frac_fine)
                | ((areas > 45) & (areas <= 650) & frac_med)
                | ((areas > 650) & frac_large)
            )
            sized_ok = (areas >= 2) & (areas <= 3500) & (max_dim <= 180) & frac_ok
            in_shadow = (sh_means > 48.0) & (areas > 28)
            valid_sp = sized_ok & ~in_shadow
            spot_lut[1:] = valid_sp.astype(np.uint8) * 255
        clean_spots = spot_lut[labels]
        if shadow_spots and num_lbl > 1 and bool(np.any(sized_ok & in_shadow)):
            tried = [] if info is not None else None
            clean_spots = np.maximum(clean_spots, self._shadow_spots(
                np.nonzero(sized_ok & in_shadow)[0] + 1, stats, labels, spot_cand, dark_diff, d_thr_map, L, L_med,
                bg_safe_geom, max(1.5, 0.5 * dark_thr), tried,
            ))
            if info is not None:
                info["shadow_spots"] = tried

        spot_full = (cv2.resize(clean_spots, (w, h), interpolation=cv2.INTER_LINEAR) > 64).astype(np.uint8)

        if not (frac_fine or frac_med):
            heal_large = cv2.dilate(spot_full, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13)))
            hard_bad_full = (
                (cv2.dilate((fg_mask_u8 > 22).astype(np.uint8), np.ones((7, 7), np.uint8)) > 0)
                | (cv2.resize(st_m, (w, h), interpolation=cv2.INTER_LINEAR) > 75)
                | ((cv2.resize(sm_m, (w, h), interpolation=cv2.INTER_LINEAR) > 65) & (np.arange(h)[:, None] < int(0.70 * h)))
            )
            heal_large[hard_bad_full] = 0
            return heal_large, grain_sigma

        # Fine blackhat/tophat dust & stray hair pass: full-res in Quality mode, <= 1800px in Fast mode
        if fast_mode and max(h, w) > 1800:
            f_scale = 1800.0 / max(h, w)
            fw, fh = int(round(w * f_scale)), int(round(h * f_scale))
            L_work = cv2.cvtColor(cv2.resize(img_rgb_u8, (fw, fh), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2GRAY)
            fg_work = cv2.resize(fg_mask_u8, (fw, fh), interpolation=cv2.INTER_AREA)
            bh_k = 13
            dil_k = 7
        else:
            fw, fh = w, h
            L_work = cv2.cvtColor(img_rgb_u8, cv2.COLOR_RGB2GRAY)
            fg_work = fg_mask_u8
            bh_k = 19
            dil_k = 13

        L_bg_work = cv2.resize(
            cv2.medianBlur(cv2.resize(L_work, (sw, sh), interpolation=cv2.INTER_AREA), 35),
            (fw, fh),
            interpolation=cv2.INTER_LINEAR,
        )
        step_g = 2 if (fast_mode and max(fh, fw) <= 1800) else 4
        L_sub = L_work[::step_g, ::step_g].astype(np.float32)
        hp_full = np.abs(L_sub - cv2.GaussianBlur(L_sub, (5, 5), 0))
        fg_sub = fg_work[::step_g, ::step_g] < 60
        grain_full = max(0.85, float(np.median(hp_full[fg_sub])) * 1.4826) if np.any(fg_sub) else 2.0

        k_bh = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (bh_k, bh_k))
        bh_full = cv2.morphologyEx(L_work, cv2.MORPH_BLACKHAT, k_bh)
        th_full = cv2.morphologyEx(L_work, cv2.MORPH_TOPHAT, k_bh)

        thr_strong = max(8, int(round(6.0 * grain_full * sens)))
        thr_hair = max(5, int(round(3.8 * grain_full * sens)))
        thr_top = max(12, int(round(7.5 * grain_full * sens)))
        thr_top_shadow = int(round(1.65 * max(12, 7.5 * grain_full * sens)))
        thr_strong_shadow = int(round(thr_strong * 1.85))
        gain_s = self._local_grain_gain(hp_full, fg_sub, grain_full) if (local_grain and np.any(fg_sub)) else None
        if gain_s is not None:
            # the same thresholds, computed with the noise of every place instead of the noise of the frame
            def thr_map(base: float, floor: float, mult: float = 1.0):
                t = cv2.resize(np.maximum(floor, base * gain_s) * mult, (fw, fh), interpolation=cv2.INTER_LINEAR)
                return np.clip(np.rint(t), 0, 255).astype(np.uint8)

            g_sens = grain_full * sens
            thr_strong = thr_map(6.0 * g_sens, 8.0)
            thr_hair = thr_map(3.8 * g_sens, 5.0)
            thr_top = thr_map(7.5 * g_sens, 12.0)
            thr_top_shadow = thr_map(7.5 * g_sens, 12.0, 1.65)
            thr_strong_shadow = np.clip(np.rint(thr_strong.astype(np.float32) * 1.85), 0, 255).astype(np.uint8)
        fine_strong = ((bh_full > thr_strong) | (th_full > thr_top)).astype(np.uint8)
        fine_soft = (bh_full > thr_hair).astype(np.uint8)

        stand_work_bad = cv2.resize(st_m, (fw, fh), interpolation=cv2.INTER_LINEAR) > 75
        smoke_work_bad = cv2.resize(sm_m, (fw, fh), interpolation=cv2.INTER_LINEAR) > 65
        shadow_work_bad = cv2.resize(sh_m, (fw, fh), interpolation=cv2.INTER_LINEAR) > 65
        fg_work_bad = cv2.dilate((fg_work > 22).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))) > 0
        y_smoke_protect = np.zeros((fh, 1), dtype=bool)
        y_smoke_protect[:int(0.70 * fh), 0] = True
        dark_bg_bad = (L_bg_work < 18) & (th_full <= 20)
        hard_bad_work = fg_work_bad | stand_work_bad | (smoke_work_bad & y_smoke_protect) | dark_bg_bad

        fine_strong[hard_bad_work] = 0
        fine_strong[shadow_work_bad & (bh_full <= thr_strong_shadow) & (th_full <= thr_top_shadow)] = 0
        fine_soft[hard_bad_work | shadow_work_bad] = 0
        pad_b = max(4, min(14, int(0.012 * min(fh, fw))))
        for arr in (fine_strong, fine_soft):
            arr[:pad_b, :] = 0; arr[-pad_b:, :] = 0; arr[:, :pad_b] = 0; arr[:, -pad_b:] = 0

        num_f, lbl_f, st_f, _ = cv2.connectedComponentsWithStats(fine_strong, connectivity=8)
        lut_f = np.zeros(num_f, dtype=np.uint8)
        if num_f > 1:
            ar_f = st_f[1:, cv2.CC_STAT_AREA]
            f_frac_ok = ((ar_f <= 160) & frac_fine) | ((ar_f > 160) & (ar_f <= 900) & frac_med) | ((ar_f > 900) & frac_large)
            lut_f[1:] = ((ar_f >= (3 if fast_mode else 5)) & (ar_f <= 2500) & f_frac_ok).astype(np.uint8)
        fine_keep = lut_f[lbl_f]

        num_s, lbl_s, st_s, _ = cv2.connectedComponentsWithStats(fine_soft, connectivity=8)
        lut_s = np.zeros(num_s, dtype=np.uint8)
        if num_s > 1:
            ar_s = st_s[1:, cv2.CC_STAT_AREA]
            md_s = np.maximum(st_s[1:, cv2.CC_STAT_WIDTH], st_s[1:, cv2.CC_STAT_HEIGHT])
            s_frac_ok = ((ar_s <= 200) & frac_fine) | ((ar_s > 200) & frac_med)
            lut_s[1:] = ((ar_s >= (8 if fast_mode else 12)) & (ar_s <= 2200) & (md_s >= (11 if fast_mode else 16)) & s_frac_ok).astype(np.uint8)
        fine_keep = np.maximum(fine_keep, lut_s[lbl_s])
        fine_keep = cv2.dilate(fine_keep, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dil_k, dil_k)))
        fine_keep[hard_bad_work] = 0

        if fw != w or fh != h:
            fine_full = (cv2.resize(fine_keep * 255, (w, h), interpolation=cv2.INTER_LINEAR) > 64).astype(np.uint8)
            spot_full_dil = cv2.dilate(spot_full, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11 if fast_mode else 13, 11 if fast_mode else 13)))
            heal = np.maximum(spot_full_dil, fine_full)
            hard_bad_full = (
                (cv2.dilate((fg_mask_u8 > 22).astype(np.uint8), np.ones((7, 7), np.uint8)) > 0)
                | (cv2.resize(st_m, (w, h), interpolation=cv2.INTER_LINEAR) > 75)
                | ((cv2.resize(sm_m, (w, h), interpolation=cv2.INTER_LINEAR) > 65) & (np.arange(h)[:, None] < int(0.70 * h)))
            )
            heal[hard_bad_full] = 0
        else:
            spot_full_dil = cv2.dilate(spot_full, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13)))
            heal = np.maximum(spot_full_dil, fine_keep)
            heal[hard_bad_work] = 0
        return heal, grain_sigma

    # ------------------------------------------------------------------
    # 5. Tile LaMa Inpainting (GPU / CPU) + Hybrid Fast Inpaint
    # ------------------------------------------------------------------
    def _run_lama_tiles(
        self,
        img_rgb_u8: np.ndarray,
        heal_mask_u8: np.ndarray,
        progress_cb=None,
        pad: int = 96,
    ) -> tuple[np.ndarray, int]:
        h, w = img_rgb_u8.shape[:2]
        out_acc = np.zeros((h, w, 3), dtype=np.float32)
        w_acc = np.zeros((h, w, 1), dtype=np.float32)

        tile_size = 512
        step = tile_size - 2 * pad
        ys = list(range(0, max(1, h - tile_size + 1), step))
        if ys[-1] + tile_size < h:
            ys.append(max(0, h - tile_size))
        xs = list(range(0, max(1, w - tile_size + 1), step))
        if xs[-1] + tile_size < w:
            xs.append(max(0, w - tile_size))

        # Smooth cosine/ramp tile weight
        wy = np.ones((tile_size,), dtype=np.float32)
        ramp = np.linspace(0.05, 1.0, pad, dtype=np.float32)
        wy[:pad] = ramp
        wy[-pad:] = ramp[::-1]
        weight_2d = np.outer(wy, wy)[..., None]

        in_names = [i.name for i in self.lama_sess.get_inputs()]
        active_tiles = []
        for y in ys:
            y2 = min(h, y + tile_size)
            y1 = max(0, y2 - tile_size)
            for x in xs:
                x2 = min(w, x + tile_size)
                x1 = max(0, x2 - tile_size)
                mt = heal_mask_u8[y1:y2, x1:x2]
                if np.any(mt > 0):
                    active_tiles.append((y1, y2, x1, x2, mt))

        total_tiles = len(active_tiles)
        tiles_run = 0
        if total_tiles > 0:
            ep_now = self.lama_sess.get_providers()[0] if self.lama_sess.get_providers() else "CPU"
            print(f"[Engine] Заливка LaMa: {total_tiles} тайлів ({ep_now})...", flush=True)
            if progress_cb is not None:
                progress_cb(52, f"AI-заливка дефектів: 0/{total_tiles} тайлів...")

        for y1, y2, x1, x2, mt in active_tiles:
            patch_u8 = img_rgb_u8[y1:y2, x1:x2]
            ph, pw = patch_u8.shape[:2]
            if ph != tile_size or pw != tile_size:
                patch_in = cv2.copyMakeBorder(patch_u8, 0, tile_size - ph, 0, tile_size - pw, cv2.BORDER_REFLECT_101)
                mask_in = cv2.copyMakeBorder(mt, 0, tile_size - ph, 0, tile_size - pw, cv2.BORDER_CONSTANT, value=0)
            else:
                patch_in = patch_u8
                mask_in = mt

            inp_img = (patch_in.astype(np.float32) / 255.0).transpose(2, 0, 1)[None, ...]
            inp_msk = (mask_in > 0).astype(np.float32)[None, None, ...]
            try:
                pred = self.lama_sess.run(None, {in_names[0]: inp_img, in_names[1]: inp_msk})[0][0]
            except Exception as exc:
                print(f"[Engine][УВАГА] Помилка GPU при заливці LaMa, перемикаємося на CPU: {exc}", flush=True)
                self.gpu_error = f"GPU fallback (LaMa): {exc}"
                self.lama_sess, _ = self._create_cpu_session(self.lama_path)
                in_names = [i.name for i in self.lama_sess.get_inputs()]
                pred = self.lama_sess.run(None, {in_names[0]: inp_img, in_names[1]: inp_msk})[0][0]

            pred_hwc = pred.transpose(1, 2, 0)[:ph, :pw]
            pred_rgb = np.clip(pred_hwc / self.lama_out_scale, 0.0, 1.0)

            w_tile = weight_2d[:ph, :pw]
            out_acc[y1:y2, x1:x2] += pred_rgb * w_tile
            w_acc[y1:y2, x1:x2] += w_tile
            tiles_run += 1
            if progress_cb is not None and total_tiles > 0:
                tile_pct = 52 + int(round((tiles_run / total_tiles) * 26))
                progress_cb(tile_pct, f"AI-заливка дефектів: {tiles_run}/{total_tiles}...")
            if total_tiles >= 6 and (tiles_run % 5 == 0 or tiles_run == total_tiles):
                print(f"  LaMa: {tiles_run}/{total_tiles}", flush=True)

        # Normalize where LaMa ran (same arithmetic as before, but without boolean fancy-indexing over the whole frame)
        lut_div = np.arange(256, dtype=np.float32) / 255.0
        result_f32 = cv2.LUT(img_rgb_u8, lut_div)
        if tiles_run > 0:
            ty0 = min(t[0] for t in active_tiles)
            ty1 = max(t[1] for t in active_tiles)
            tx0 = min(t[2] for t in active_tiles)
            tx1 = max(t[3] for t in active_tiles)
            acc_v = out_acc[ty0:ty1, tx0:tx1]
            w_v = w_acc[ty0:ty1, tx0:tx1]
            has_w = w_v > 1e-6
            np.divide(acc_v, w_v, out=acc_v, where=has_w)
            np.copyto(result_f32[ty0:ty1, tx0:tx1], acc_v, where=has_w)
        return result_f32, tiles_run

    def _run_fast_inpaint(
        self,
        img_rgb_u8: np.ndarray,
        heal_mask_u8: np.ndarray,
        progress_cb=None,
        size_scale: float = 1.0,
    ) -> tuple[np.ndarray, int, int]:
        """
        Ultra-fast hybrid heal for v2.0.0 (~3-5s full 22MP target, minimal RAM):
        1) Small-to-medium isolated dust/crumbs/scratches (<= 60px bbox, area <= 2800) -> local Telea crop (~15-35ms total).
        2) Larger defects (vinyl seams, stands, cables, big scuffs) -> LaMa at <= 1536px working resolution (pad=40).
        Returns uint8 RGB image (zero 265MB float32 duplication!).
        size_scale < 1: the frame is a reduced copy of the real one (quick preview) - the "small defect" limits, which
        are meant in real pixels, shrink with it, so the same defects go to LaMa as on the real frame.
        """
        lim_side = 60.0 * size_scale
        lim_area = 2800.0 * size_scale * size_scale
        h, w = img_rgb_u8.shape[:2]
        m_bin = (heal_mask_u8 > 0).astype(np.uint8)
        num_c, lbl_c, st_c, _ = cv2.connectedComponentsWithStats(m_bin, connectivity=8)
        del m_bin

        work_u8 = img_rgb_u8.copy()
        big_lut = np.zeros(num_c, dtype=np.uint8)
        small_specks = 0

        for idx in range(1, num_c):
            area = int(st_c[idx, cv2.CC_STAT_AREA])
            x, y, bw, bh = (
                int(st_c[idx, cv2.CC_STAT_LEFT]),
                int(st_c[idx, cv2.CC_STAT_TOP]),
                int(st_c[idx, cv2.CC_STAT_WIDTH]),
                int(st_c[idx, cv2.CC_STAT_HEIGHT]),
            )
            if max(bw, bh) <= lim_side and area <= lim_area:
                pad_crop = 14
                x0 = max(0, x - pad_crop)
                y0 = max(0, y - pad_crop)
                x1 = min(w, x + bw + pad_crop)
                y1 = min(h, y + bh + pad_crop)
                sub_m = (lbl_c[y0:y1, x0:x1] == idx).astype(np.uint8) * 255
                patch = work_u8[y0:y1, x0:x1]
                healed_patch = cv2.inpaint(patch, sub_m, 4, cv2.INPAINT_TELEA)
                sel = sub_m > 0
                patch[sel] = healed_patch[sel]
                small_specks += 1
            else:
                big_lut[idx] = 1

        big_mask = big_lut[lbl_c]
        del lbl_c
        tiles_run = 0

        if np.any(big_mask > 0):
            self._ensure_models_loaded(need_matting=False, need_lama=True, progress_cb=progress_cb)
            lama_scale = min(1.0, 1536.0 / max(h, w))
            if lama_scale < 0.99:
                lw = max(8, int(round(w * lama_scale)))
                lh = max(8, int(round(h * lama_scale)))
                img_l = cv2.resize(work_u8, (lw, lh), interpolation=cv2.INTER_AREA)
                mask_l = cv2.resize(big_mask, (lw, lh), interpolation=cv2.INTER_NEAREST)
                mask_l = cv2.dilate(mask_l, np.ones((3, 3), np.uint8))
                lama_l_f32, tiles_run = self._run_lama_tiles(img_l, mask_l, progress_cb=progress_cb, pad=40)
                del img_l, mask_l
                lama_l_u8 = np.clip(np.round(lama_l_f32 * 255.0), 0, 255).astype(np.uint8)
                del lama_l_f32
                lama_full_u8 = cv2.resize(lama_l_u8, (w, h), interpolation=cv2.INTER_LINEAR)
                del lama_l_u8
                big_bool = big_mask > 0
                work_u8[big_bool] = lama_full_u8[big_bool]
                del lama_full_u8
            else:
                lama_full_f32, tiles_run = self._run_lama_tiles(work_u8, big_mask, progress_cb=progress_cb, pad=40)
                big_bool = big_mask > 0
                work_u8[big_bool] = np.clip(np.round(lama_full_f32[big_bool] * 255.0), 0, 255).astype(np.uint8)
                del lama_full_f32
        elif progress_cb is not None:
            progress_cb(78, f"Швидке очищення пилу ({small_specks}) завершено...")

        return work_u8, tiles_run, small_specks

    # ------------------------------------------------------------------
    # 5b. Dress / Clothing Soft Wrinkle & Specular Smoothing (Skin/Hair/Edge Safe)
    # ------------------------------------------------------------------
    @staticmethod
    def _fabric_texture_small(img_rgb_u8: np.ndarray, max_dim: int = 1024) -> np.ndarray:
        """
        How much pixel-level detail every spot of the FULL-SIZE frame has (RMS of the finest luminance detail),
        returned at the size of the clothing mask. Denim, knitwear, lace, prints and lit hair score high here,
        smooth fabric scores at the level of the camera grain. Read only by _build_dress_mask_small.
        """
        h, w = img_rgb_u8.shape[:2]
        scale = min(1.0, float(max_dim) / max(h, w))
        sw, sh = max(8, int(round(w * scale))), max(8, int(round(h * scale)))
        gray = cv2.cvtColor(img_rgb_u8, cv2.COLOR_RGB2GRAY)
        fine = cv2.absdiff(gray, cv2.GaussianBlur(gray, (0, 0), 1.6))
        del gray
        sq = cv2.multiply(fine, fine, scale=16.0, dtype=cv2.CV_16U)
        del fine
        return np.sqrt(cv2.resize(sq, (sw, sh), interpolation=cv2.INTER_AREA).astype(np.float32) * (1.0 / 16.0))

    @staticmethod
    def _build_dress_mask_small(
        img_rgb_u8: np.ndarray, core_mask_u8: np.ndarray, max_dim: int = 1024, tex_rms: np.ndarray | None = None
    ) -> np.ndarray:
        """
        Returns float32 mask [0..1] over clothing/dress regions strictly inside the subject (`core_mask_u8`),
        protecting human skin tones (without misclassifying red/pink/magenta dresses as skin),
        head/hair zone (plus long hair connected from head onto shoulders/chest), and crisp silhouette edges.
        With `tex_rms` (see _fabric_texture_small) fabrics that have a texture of their own - denim, knitwear,
        lace, prints - are left out too: ironing is meant for smooth cloth only.
        """
        h, w = img_rgb_u8.shape[:2]
        scale = min(1.0, float(max_dim) / max(h, w))
        sw, sh = max(8, int(round(w * scale))), max(8, int(round(h * scale)))
        small = cv2.resize(img_rgb_u8, (sw, sh), interpolation=cv2.INTER_AREA)
        core_s = cv2.resize(core_mask_u8, (sw, sh), interpolation=cv2.INTER_AREA)

        fg_bin = (core_s > 140).astype(np.uint8)
        if not np.any(fg_bin):
            return np.zeros((sh, sw), dtype=np.float32)

        # Stay slightly inside outer garment silhouette so lace/tulle silhouette never blurs
        er_k = max(3, int(round(min(sw, sh) * 0.006)) | 1)
        fg_inner = cv2.erode(fg_bin, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (er_k, er_k)))

        # Strict human skin detector: warm peach/tan hue (H in 2..21), moderate saturation (28..165),
        # never misclassifies crimson red (Cr > 172 or Cr-Cb > 52) or pastel/hot pink (H >= 165) dresses!
        hsv = cv2.cvtColor(small, cv2.COLOR_RGB2HSV)
        H, S = hsv[:, :, 0], hsv[:, :, 1]
        ycrcb = cv2.cvtColor(small, cv2.COLOR_RGB2YCrCb).astype(np.int16)
        Y, Cr, Cb = ycrcb[:, :, 0], ycrcb[:, :, 1], ycrcb[:, :, 2]
        skin = (
            (Y > 35)
            & (H >= 2) & (H <= 21)
            & (S >= 28) & (S <= 165)
            & (Cr >= 134) & (Cr <= 172)
            & (Cb >= 80) & (Cb <= 126)
            & ((Cr - Cb) >= 14) & ((Cr - Cb) <= 52)
        ).astype(np.uint8)
        skin = cv2.morphologyEx(skin, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        skin_k = max(7, int(round(min(sw, sh) * 0.015)) | 1)
        skin_prot = cv2.dilate(skin, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (skin_k, skin_k)))

        ys, xs = np.where(fg_bin > 0)
        y_top, y_bot = int(ys.min()), int(ys.max())
        subj_h = max(1, y_bot - y_top)
        band = y_top + int(round(subj_h * 0.22))  # the head is somewhere in the top 22% of the subject

        # The head itself is protected completely; shoulders and chest below the chin are clothing like any other.
        # The chin line is read from the face: the biggest skin patch of the head band.
        head_cut = band
        hair_line = band  # rows above it hold hair (never the collar): the place to read the hair colour from
        hair_box = None  # (x0, x1, y1): how far loose hair can reach, judged by the size of the face
        n_fc, lbl_fc, st_fc, _ = cv2.connectedComponentsWithStats((skin[:band] > 0).astype(np.uint8) & fg_bin[:band], 8)
        if n_fc > 1:
            i_fc = 1 + int(np.argmax(st_fc[1:, cv2.CC_STAT_AREA]))
            if int(st_fc[i_fc, cv2.CC_STAT_AREA]) >= (0.03 * subj_h) ** 2:
                f_top = int(st_fc[i_fc, cv2.CC_STAT_TOP])
                rows = (lbl_fc[f_top:f_top + max(3, int(round(0.11 * subj_h)))] == i_fc).sum(axis=1)
                f_w = float(rows.max())
                head_cut = int(np.clip(f_top + 1.45 * f_w, y_top + 0.10 * subj_h, band))
                hair_line = int(np.clip(f_top + 0.6 * f_w, y_top + 0.04 * subj_h, head_cut))
                f_x0 = int(st_fc[i_fc, cv2.CC_STAT_LEFT])
                f_x1 = f_x0 + int(st_fc[i_fc, cv2.CC_STAT_WIDTH])
                hair_box = (int(f_x0 - 1.4 * f_w), int(f_x1 + 1.4 * f_w), int(head_cut + 2.2 * f_w))
        head_prot = np.zeros((sh, sw), dtype=np.uint8)
        head_prot[:head_cut, :] = 1

        # Protect long hair connected down onto upper chest/shoulders (down to 48% of subject height)
        upper_lim = y_top + int(round(subj_h * 0.48))
        head_hair_zone = (fg_bin > 0) & (skin_prot == 0)
        head_hair_zone[upper_lim:, :] = False
        if hair_box is not None:
            # a dark dress under dark hair has the hair's colour too: hair is looked for around the head only
            head_hair_zone[max(head_cut, hair_box[2]):, :] = False
            head_hair_zone[head_cut:, :max(0, hair_box[0])] = False
            head_hair_zone[head_cut:, max(0, hair_box[1]):] = False
        # Hair colour = what surrounds the face from above. (It used to be read from the whole head band: with a
        # high collar or a hood the "hair colour" turned out to be the colour of the dress, and the whole upper
        # half of the dress was then protected as hair - exactly where the wrinkles are.)
        top_fg = fg_bin[:hair_line, :] > 0
        if np.any(top_fg):
            lab_s = cv2.cvtColor(small, cv2.COLOR_RGB2LAB).astype(np.float32)
            head_non_skin = top_fg & (skin_prot[:hair_line, :] == 0)
            if np.sum(head_non_skin) > 20:
                hair_ref = np.median(lab_s[:hair_line, :][head_non_skin], axis=0)
                dist_hair = np.linalg.norm(lab_s - hair_ref[None, None, :], axis=2)
                hair_cand = (dist_hair < 24.0) & head_hair_zone
                n_hc, lbl_hc, _, _ = cv2.connectedComponentsWithStats(hair_cand.astype(np.uint8), 8)
                if n_hc > 1:
                    top_labels = set(np.unique(lbl_hc[:head_cut, :])) - {0}
                    if top_labels:
                        keep_hair = np.isin(lbl_hc, list(top_labels)).astype(np.uint8)
                        keep_hair = cv2.dilate(keep_hair, np.ones((7, 7), np.uint8))
                        head_prot = np.maximum(head_prot, keep_hair)

        lower_y = y_top + int(round(subj_h * 0.55))
        skin_prot_f = skin_prot.astype(np.float32)
        skin_prot_f[lower_y:, :] *= 0.85

        # Protect only crisp structural outlines / jewelry / eyes (allow soft fabric folds to smooth!)
        gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY).astype(np.float32)
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        grad = np.hypot(gx, gy)
        edge_prot = np.clip((grad - 135.0) / 90.0, 0.0, 1.0)
        edge_prot = cv2.GaussianBlur(edge_prot, (5, 5), 0)

        dress_f = fg_inner.astype(np.float32) * (1.0 - skin_prot_f) * (1.0 - head_prot.astype(np.float32))
        dress_f = dress_f * (1.0 - 0.72 * edge_prot)
        dress_f = cv2.GaussianBlur(dress_f, (11, 11), 0)
        # Strictly clamp inside inner foreground silhouette so dress smoothing never bleeds onto floor/backdrop
        dress_f *= fg_bin.astype(np.float32) * np.clip((core_s.astype(np.float32) / 255.0 - 0.35) / 0.45, 0.0, 1.0)

        if tex_rms is not None and tex_rms.shape[:2] == (sh, sw):
            # Texture above the camera grain. The grain level is read from the backdrop of the same photo, separately
            # for every brightness (grain is stronger in the light parts), so ISO and exposure do not matter.
            bg = core_s < 20
            edges = np.linspace(0.0, 256.0, 13)
            xs_n, ys_n = [], []
            for i in range(12):
                sel = bg & (gray >= edges[i]) & (gray < edges[i + 1])
                if int(np.count_nonzero(sel)) >= 200:
                    xs_n.append(0.5 * (edges[i] + edges[i + 1]))
                    ys_n.append(float(np.median(tex_rms[sel])))
            noise = np.interp(gray, xs_n, ys_n).astype(np.float32) if xs_n else 0.012 * (gray + 5.0)
            excess = np.sqrt(np.maximum(tex_rms * tex_rms - (1.15 * noise) ** 2, 0.0)) / (gray + 5.0)
            # texture covers a surface, a crease is a line: erosion keeps the former and drops the latter
            excess = cv2.GaussianBlur(cv2.erode(excess, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))), (0, 0), 3.0)
            dress_f *= 1.0 - np.clip((excess - 0.006) / 0.010, 0.0, 1.0)
        return np.clip(dress_f, 0.0, 1.0).astype(np.float32)

    @staticmethod
    def _smooth_dress_fabric(
        cleaned_f32: np.ndarray,
        dress_mask_small: np.ndarray,
        strength: float,
        fast_mode: bool = False,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Irons the wrinkles of smooth clothing and touches nothing else.

        A wrinkle is a narrow, weak light/dark streak. It is removed the way a retoucher does it by hand with
        "dodge & burn": every pixel is multiplied by a smooth gain map that lightens the dark side of a crease and
        darkens the light side. Because the pixels are only re-lit (never blurred, never replaced):
          * the weave, the grain and every fine detail of the cloth stay exactly as they were;
          * the colour does not change (all three channels get the same gain);
          * the gain map has no broad component, so the volume, the light and the shadows of the garment stay;
          * deep folds, seams, edges and drapery (strong streaks) keep their shape - the stronger the slider,
            the bigger the creases it reaches;
          * where there is no wrinkle the gain is exactly 1, so smooth areas are not repainted.
        `strength` 0..150. `fast_mode` is accepted for compatibility: both speed modes iron the same way.
        Returns (image, alpha); the image is edited in place, alpha marks the pixels that changed.
        """
        h, w = cleaned_f32.shape[:2]
        alpha_full = np.zeros((h, w), dtype=np.float32)
        if strength <= 0 or not np.any(dress_mask_small > 0.02):
            return cleaned_f32, alpha_full

        s = float(np.clip(strength / 100.0, 0.0, 1.5))
        sc = min(1.0, 2000.0 / max(h, w))
        dw, dh = max(8, int(round(w * sc))), max(8, int(round(h * sc)))
        dm = cv2.resize(dress_mask_small, (dw, dh), interpolation=cv2.INTER_LINEAR).astype(np.float32)
        # enlarging the mask must not let it spill over the outline of the garment, not even by a pixel
        inside = cv2.erode((dress_mask_small > 0.0).astype(np.uint8), np.ones((3, 3), np.uint8))
        dm *= cv2.resize(inside, (dw, dh), interpolation=cv2.INTER_NEAREST)
        ys, xs = np.where(dm > 0.02)
        if ys.size == 0:
            return cleaned_f32, alpha_full

        # work only inside the box around the clothing
        ref = float(max(dw, dh))
        sig_low = max(3.0, (0.005 + 0.004 * s) * ref)  # widest streak that still counts as a wrinkle
        sig_fine = max(0.8, 0.0005 * ref)
        mg = int(3.0 * 1.6 * sig_low) + 4
        bx0, bx1 = max(0, int(xs.min()) - mg), min(dw, int(xs.max()) + 1 + mg)
        by0, by1 = max(0, int(ys.min()) - mg), min(dh, int(ys.max()) + 1 + mg)
        fx0, fx1 = int(bx0 / sc), min(w, int(np.ceil(bx1 / sc)))
        fy0, fy1 = int(by0 / sc), min(h, int(np.ceil(by1 / sc)))
        cw, ch = bx1 - bx0, by1 - by0
        crop = cleaned_f32[fy0:fy1, fx0:fx1]
        m = np.ascontiguousarray(dm[by0:by1, bx0:bx1])
        m_src = np.clip((m - 0.10) / 0.50, 0.0, 1.0)

        lum = cv2.resize(cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY), (cw, ch), interpolation=cv2.INTER_AREA)
        l_log = np.log(lum + 0.02)

        def inside_blur(x, sigma):  # blur that only "sees" the clothing: skin, hair and backdrop never leak in
            den = cv2.GaussianBlur(m_src, (0, 0), sigma) + 1e-4
            return cv2.GaussianBlur(x * m_src, (0, 0), sigma) / den

        streaks = (inside_blur(l_log, sig_fine) - inside_blur(l_log, sig_low)) * (m_src > 0.02)

        # strong streaks are the shape of the garment (folds, seams, edges): they stay
        k_pk = max(3, int(round(0.0025 * ref)) | 1)
        peak = cv2.dilate(np.abs(streaks), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_pk, k_pk)))
        peak = cv2.GaussianBlur(peak, (0, 0), max(0.8, 0.001 * ref))
        t_lo = 0.06 + 0.07 * s
        keep = np.clip((peak - t_lo) / (1.2 * t_lo), 0.0, 1.0)
        keep = keep * keep * (3.0 - 2.0 * keep)
        # in deep shadow there is nothing to iron, only sensor noise
        lit = np.clip((lum - 0.03) / 0.05, 0.0, 1.0)
        amount = (1.0 - np.exp(-2.4 * s)) * (1.0 - keep) * lit * m

        g_log = cv2.GaussianBlur(-amount * streaks, (0, 0), 0.7)
        g_log = (g_log - inside_blur(g_log, sig_low * 1.6)) * np.clip(m * 1.5, 0.0, 1.0)  # no broad component
        g_log[(np.abs(g_log) < 0.0015) | (m <= 0.02)] = 0.0  # untouched means untouched
        if not np.any(g_log):
            return cleaned_f32, alpha_full

        gain = cv2.resize(np.exp(g_log), (fx1 - fx0, fy1 - fy0), interpolation=cv2.INTER_LINEAR)
        crop += 0.02
        crop *= gain[..., None]
        crop -= 0.02
        np.clip(crop, 0.0, 1.0, out=crop)
        del gain

        changed = cv2.GaussianBlur(np.clip(np.abs(g_log) / 0.006, 0.0, 1.0), (0, 0), 1.2)
        alpha_full[fy0:fy1, fx0:fx1] = cv2.resize(changed, (fx1 - fx0, fy1 - fy0), interpolation=cv2.INTER_LINEAR)
        return cleaned_f32, alpha_full

    # ------------------------------------------------------------------
    # 5b-2. Cyclorama: removes the wall-to-floor corner line (the corner becomes a smooth "infinity cove" gradient)
    # ------------------------------------------------------------------
    @staticmethod
    def _box_norm_x(img: np.ndarray, weight: np.ndarray, k: int):
        """Mask-aware horizontal average (two box passes = triangle window). Returns (average, visible fraction)."""
        k = max(3, int(k) | 1)
        den = cv2.blur(cv2.blur(weight, (k, 1)), (k, 1))
        src = img * (weight[..., None] if img.ndim == 3 else weight)
        num = cv2.blur(cv2.blur(src, (k, 1)), (k, 1))
        return num / (np.maximum(den, 1e-4)[..., None] if img.ndim == 3 else np.maximum(den, 1e-4)), den

    @staticmethod
    def _blur_rows(img: np.ndarray, sigma: float) -> np.ndarray:
        """Vertical Gaussian blur with a large sigma (three box passes: the cost does not grow with sigma)."""
        k = max(3, int(round(np.sqrt(4.0 * sigma * sigma + 1.0))) | 1)
        out = img
        for _ in range(3):
            out = cv2.blur(out, (1, k), borderType=cv2.BORDER_REPLICATE)
        return out

    @staticmethod
    def _shift_columns(img: np.ndarray, delta: np.ndarray, border=cv2.BORDER_REPLICATE) -> np.ndarray:
        """out(y, x) = img(y + delta[x], x): moves every column vertically (sub-pixel), used to straighten the corner line."""
        hh, ww = img.shape[:2]
        map_x = np.tile(np.arange(ww, dtype=np.float32), (hh, 1))
        map_y = np.arange(hh, dtype=np.float32)[:, None] + delta.astype(np.float32)[None, :]
        return cv2.remap(img, map_x, map_y, cv2.INTER_LINEAR, borderMode=border, borderValue=0)

    CORNER_MIN_SCORE = 0.12        # a line scoring less is no corner (faint joints score about 0.002, a real corner 0.3-2)
    CORNER_UPPER_MIN_SCORE = 0.15  # a line above the strongest one: wins when it scores at least this...
    CORNER_UPPER_MIN_REL = 0.04    # ...and its step is this share of the brightness around it (L* + 1)

    @staticmethod
    def _find_corner_line(L: np.ndarray, valid: np.ndarray, y_lo: float = 0.25, y_hi: float = 0.82,
                          max_slope: float = 0.10, n_slopes: int = 21, scales=((2, 6), (4, 12))):
        """
        Finds the wall-to-floor corner on a small luminance image.
        L: HxW float32 (L*), valid: HxW float32 (1 = clean visible background).
        The corner is the straight, nearly horizontal line along which the background brightness makes a SHARP step
        of one sign over most of the visible width, and stays different well away from the line (two differently lit
        surfaces). A slow light fall-off, the soft edge of a pool of light, a thin floor seam or a short edge is not
        a corner. When several lines score about alike, the highest one is the corner: shadows, pools of light and
        seams all lie on the floor, below it.
        The same holds when the lines do NOT score alike. On a dark frame the corner is a step of half an L* (wall
        and floor are both nearly black) while the shadow of a stool or the rim of a pool of light, lower on the
        floor, is ten times that - and sharp enough to pass every test above. Bending the light there ruins the
        floor. So a line above the strongest one is the corner when it is one in its own right: it passes the
        usual limit with a margin (CORNER_UPPER_MIN_SCORE), runs along at least half of the visible backdrop and
        can be seen - its step is at least CORNER_UPPER_MIN_REL of the brightness around it. (On a light backdrop
        that is a step of well over one L*, which is no faint line; a faint one never wins there.)
        Returns dict(slope [rows per column], row [at the centre column], step [L*], cov, score) or None.
        """
        h, w = L.shape
        k = max(9, int(w * 0.05) | 1)
        Lh, den = CleanVinylEngine._box_norm_x(L, valid, k)
        ok = (den > 0.30).astype(np.float32)
        Lh_ok = Lh * ok
        cx = (w - 1) / 2.0
        n_seg = 8
        edges = [int(i * w / n_seg) for i in range(n_seg + 1)]
        rows = np.arange(h)

        def shifted(arr, dy):
            idx = np.clip(rows + dy, 0, h - 1)
            return arr[idx]

        def scores_for(a):
            """For the slope `a`: the score of every row, with the step and the coverage it was got from."""
            M = np.float32([[1, 0, 0], [-a, 1, a * cx]])  # y' = y - a (x - cx): the candidate line becomes a row
            L_s = cv2.warpAffine(Lh_ok, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            o_s = cv2.warpAffine(ok, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            num = np.stack([L_s[:, edges[i]:edges[i + 1]].sum(axis=1) for i in range(n_seg)], axis=1)
            cnt = np.stack([o_s[:, edges[i]:edges[i + 1]].sum(axis=1) for i in range(n_seg)], axis=1)
            seg_ok = cnt > (0.5 * w / n_seg)
            P = num / np.maximum(cnt, 1e-3)  # h x n_seg: mean luminance of every stripe along the candidate rows
            cs = np.cumsum(np.vstack([np.zeros((1, n_seg), np.float32), P]), axis=0)

            def band_mean(lo, hi):
                a0 = np.clip(rows + lo, 0, h)
                a1 = np.clip(rows + hi + 1, 0, h)
                return (cs[a1] - cs[a0]) / np.maximum(a1 - a0, 1)[:, None]

            score = np.zeros(h, np.float32)
            mean_sharp_best = np.zeros(h, np.float32)
            cov_best = np.zeros(h, np.float32)
            level_best = np.zeros(h, np.float32)
            for r1, r2 in scales:  # a sharp corner and a slightly out-of-focus one
                okb = seg_ok & shifted(seg_ok, r2) & shifted(seg_ok, -r2)
                step = shifted(P, r1) - shifted(P, -r1)
                wide = shifted(P, r2) - shifted(P, -r2)
                trend = wide * (r1 / r2)  # what a smooth gradient alone would give
                sharp = (step - trend) * okb
                lasting = (band_mean(r2 // 2 + 3, r2 + 10) - band_mean(-(r2 + 10), -(r2 // 2 + 3))) * okb
                n_ok = okb.sum(axis=1)
                mean_sharp = sharp.sum(axis=1) / np.maximum(n_ok, 1)
                sgn = np.sign(mean_sharp)
                same = ((np.sign(sharp) == sgn[:, None]) & okb & (np.abs(sharp) > 0.25 * np.abs(mean_sharp)[:, None])).sum(axis=1)
                consist = same / np.maximum(n_ok, 1)
                cov = n_ok / n_seg
                mean_last = lasting.sum(axis=1) / np.maximum(n_ok, 1)
                # a corner separates two differently lit surfaces: the difference must still be there well away
                # from the line (a thin seam or a crease returns to the same tone on the other side)
                keeps = np.clip((mean_last * sgn / np.maximum(np.abs(mean_sharp), 1e-3) - 0.2) / 0.4, 0.0, 1.0)
                # ...and the change must be a step, not a slope: across a real corner most of the difference is there
                # within a few rows (sharp part / whole difference about 0.4-0.7); across the soft edge of a pool of
                # light the brightness climbs steadily, however big the climb is (about 0.03-0.15)
                mean_wide = (wide * okb).sum(axis=1) / np.maximum(n_ok, 1)
                abrupt = np.clip((np.abs(mean_sharp) / (np.abs(mean_wide) + 0.15) - 0.15) / 0.20, 0.0, 1.0)
                # ...and it must be ONE step. A thin dark or light line - a floor joint, tape, a crease - is two steps
                # of opposite sign a few rows apart: next to a step that goes down there is one that goes up again.
                # (On a floor that gets lighter or darker towards the camera such a line also "keeps" a difference
                # on one of its sides and used to be taken for the corner.)
                # Looked for in every stripe on its own: when the candidate line is not quite parallel to such a
                # thin line, the stripes meet its two steps at different rows.
                # The light itself may climb or fall across the candidate line (a vignette, a pool of light), and
                # that slope adds to the steps of one direction and takes from the steps of the other: a faint
                # joint on a floor that darkens towards the camera kept more of its "down" step than of its "up"
                # step and passed for a one-way step, a corner. So the slope is taken out first. It is measured on
                # each side of the candidate line apart, between two bands of ONE side: neither a step at the line
                # nor a thin line next to it gets into it.
                f0, f1 = r2 // 2 + 3, r2 + 10
                slope_dn = (band_mean(f1 - 2, f1) - band_mean(f0, f0 + 2)) / float(f1 - f0 - 2)
                slope_up = (band_mean(-(f0 + 2), -f0) - band_mean(-f1, -(f1 - 2))) / float(f1 - f0 - 2)
                far_ok = shifted(seg_ok, f1) & shifted(seg_ok, -f1) & shifted(seg_ok, f0) & shifted(seg_ok, -f0)
                tilt = np.where(far_ok, 0.5 * (slope_dn + slope_up) * (2 * r1), 0.0).astype(np.float32)
                back = np.zeros_like(step)
                for dy in range(-(r2 + 2), r2 + 3):
                    if dy != 0:
                        back = np.maximum(back, -sgn[:, None] * (shifted(step, dy) - tilt))
                forth = (np.maximum(0.0, sgn[:, None] * (step - tilt)) * okb).sum(axis=1)
                one_way = np.clip((0.8 - (back * okb).sum(axis=1) / np.maximum(forth, 1e-3)) / 0.4, 0.0, 1.0)
                sc_r = (np.abs(mean_sharp) * np.clip((consist - 0.5) / 0.35, 0.0, 1.0) * cov ** 0.75
                        * (1.0 - 3.0 * abs(a)) * (cov >= 0.25) * keeps * abrupt * one_way)
                better = sc_r > score
                score = np.where(better, sc_r, score)
                mean_sharp_best = np.where(better, mean_sharp, mean_sharp_best)
                cov_best = np.where(better, cov, cov_best)
                level_best = np.where(better, (P * okb).sum(axis=1) / np.maximum(n_ok, 1), level_best)
            score[: int(h * y_lo)] = 0.0
            score[int(h * y_hi):] = 0.0
            return score, mean_sharp_best, cov_best, level_best

        # 1) every slope of the coarse grid: what each row scores at best
        row_score = np.zeros(h, np.float32)
        row_slope = np.zeros(h, np.float32)
        row_step = np.zeros(h, np.float32)
        row_cov = np.zeros(h, np.float32)
        row_level = np.zeros(h, np.float32)
        step_a = 2.0 * max_slope / (n_slopes - 1)
        for a in np.linspace(-max_slope, max_slope, n_slopes):
            sc_a, st_a, cov_a, lv_a = scores_for(float(a))
            better = sc_a > row_score
            row_score = np.where(better, sc_a, row_score)
            row_slope = np.where(better, np.float32(a), row_slope)
            row_step = np.where(better, st_a, row_step)
            row_cov = np.where(better, cov_a, row_cov)
            row_level = np.where(better, lv_a, row_level)
        top = float(row_score.max())
        i0 = int(np.argmax(row_score))
        if top > 0:
            # 2) the lines that score about as well as the best one; the highest of them is the corner
            apart = max(4, int(round(0.03 * h)))
            left = row_score.copy()
            while True:
                j = int(np.argmax(left))
                if float(left[j]) < 0.6 * top:
                    break
                i0 = min(i0, j)
                left[max(0, j - apart):j + apart + 1] = 0.0
            # 2b) ...and a visible line above it, however faint next to it (see the doc): the highest such line
            seen = ((row_score >= CleanVinylEngine.CORNER_UPPER_MIN_SCORE) & (row_cov >= 0.5)
                    & (np.abs(row_step) >= CleanVinylEngine.CORNER_UPPER_MIN_REL * (row_level + 1.0)))
            seen[max(0, i0 - apart):] = False
            if bool(seen.any()):
                j = int(np.flatnonzero(seen)[0])
                i0 = j + int(np.argmax(np.where(seen[j:j + apart + 1], row_score[j:j + apart + 1], 0.0)))
        best = {"slope": float(row_slope[i0]), "row": float(i0), "step": float(row_step[i0]),
                "cov": float(row_cov[i0]), "score": float(row_score[i0])}
        if best["score"] > 0:
            # 3) the exact tilt: finer slopes, the rows next to the chosen one
            near = max(3, int(round(0.01 * h)))
            lo_r, hi_r = max(0, i0 - near), min(h, i0 + near + 1)
            for t in (-0.75, -0.5, -0.25, 0.25, 0.5, 0.75):
                a = float(row_slope[i0]) + step_a * t
                sc_a, st_a, cov_a, _ = scores_for(a)
                j = lo_r + int(np.argmax(sc_a[lo_r:hi_r]))
                if float(sc_a[j]) > best["score"]:
                    best = {"slope": float(a), "row": float(j), "step": float(st_a[j]), "cov": float(cov_a[j]),
                            "score": float(sc_a[j])}
        return best

    @staticmethod
    def _selection_holds_line(selection_alpha: np.ndarray, line: dict, fg_u8: np.ndarray) -> bool:
        """
        True when the selection contains (nearly) all of the corner line that is visible in the frame.
        `line`: as _corner_line_of_frame gives it; `fg_u8`: the person (the part of the line behind it does not count).
        """
        h, w = selection_alpha.shape[:2]
        half_on = 0.5 * float(np.iinfo(selection_alpha.dtype).max if selection_alpha.dtype == np.uint8 else 32768)
        xs = np.linspace(0, w - 1, 96).astype(np.int32)
        ys = np.clip(np.round(float(line["row"]) + float(line["slope"]) * (xs - (w - 1) / 2.0)), 0, h - 1).astype(np.int32)
        seen = fg_u8[ys, xs] < 40
        if not np.any(seen):
            return True
        return float(np.mean(selection_alpha[ys, xs][seen] > half_on)) >= 0.9

    @staticmethod
    def _whole_line_repair_only(seam_mask: np.ndarray, line: dict, fg_u8: np.ndarray, need: float = 0.85) -> np.ndarray:
        """
        The wall-floor corner when no tool takes it: the corner tool is at 0, or the selection holds only a part of
        the line. The seam search may still mark it. Repaired along its whole visible length it stays a clean line,
        as before. Repaired in pieces it becomes a dashed, hard-edged remainder (a dark backdrop, where the corner
        is a thin line here and nothing there). So a repair inside the corner strip is kept only when it covers at
        least `need` of the line that is visible next to the person; otherwise the strip is left as it was shot.
        `line`: as _corner_line_of_frame gives it; `seam_mask` is edited in place and returned.
        """
        h, w = seam_mask.shape[:2]
        half = float(line["half"])
        yc = float(line["row"]) + float(line["slope"]) * (np.arange(w, dtype=np.float32) - (w - 1) / 2.0)
        y_lo = int(max(0, np.floor(float(yc.min()) - half)))
        y_hi = int(min(h, np.ceil(float(yc.max()) + half) + 1))
        if y_hi <= y_lo:
            return seam_mask
        slab = seam_mask[y_lo:y_hi]  # a view: clearing it clears the mask
        strip = np.abs(np.arange(y_lo, y_hi, dtype=np.float32)[:, None] - yc[None, :]) <= half
        marked = (slab > 0) & strip
        if not marked.any():
            return seam_mask
        yi = np.round(yc).astype(np.int64)
        cols = np.flatnonzero((yi >= 0) & (yi < h))
        seen = cols[fg_u8[yi[cols], cols] < 40]  # the columns where the line is not behind the person
        if seen.size == 0 or float(marked.any(axis=0)[seen].mean()) >= need:
            return seam_mask
        slab[strip] = 0
        return seam_mask

    def _corner_line_of_frame(self, img_rgb_u8: np.ndarray, eff_fg_u8: np.ndarray, stand_protect_s: np.ndarray,
                              smoke_s: np.ndarray) -> dict | None:
        """
        The wall-floor corner of the untouched frame, in pixels of the frame: {"row": row of the line at the centre
        column, "slope": rows per column, "half": half-height of the strip the line lies in, "step": brightness step
        across it (L*, its sign says which side is lighter)}, or None.
        Found once, on the frame as it was shot and always on the same small copy, so the answer depends neither on
        the speed mode nor on what the repair did to the floor. The corner tool removes this line
        (_apply_cyclorama_curve) and the seam search leaves its strip alone.
        """
        h, w = img_rgb_u8.shape[:2]
        sc = min(1.0, 768.0 / max(h, w))
        sw, sh = max(16, int(round(w * sc))), max(16, int(round(h * sc)))
        sm = cv2.resize(img_rgb_u8, (sw, sh), interpolation=cv2.INTER_AREA).astype(np.float32) * (1.0 / 255.0)
        fg_s = cv2.resize(eff_fg_u8, (sw, sh), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
        st_s = cv2.resize(stand_protect_s, (sw, sh), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0
        sk_s = cv2.resize(smoke_s, (sw, sh), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0
        L = cv2.cvtColor(sm, cv2.COLOR_RGB2LAB)[:, :, 0]
        bad = (fg_s > 0.04) | (st_s > 0.25) | (sk_s > 0.20)
        valid = 1.0 - cv2.dilate(bad.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(np.float32)
        line = self._find_corner_line(L, valid)
        if line is None or line["score"] < self.CORNER_MIN_SCORE:
            return None
        return {"row": (line["row"] + 0.5) / sc - 0.5, "slope": float(line["slope"]), "half": 0.012 * h + 2.0 / sc,
                "step": float(line["step"])}

    # ------------------------------------------------------------------
    # 5b-3. Stains, smears and shoe marks: the backdrop is evened, the light and the shadows stay
    # ------------------------------------------------------------------
    @staticmethod
    def _blur_valid(img: np.ndarray, weight: np.ndarray, sigma: float) -> np.ndarray:
        """Gaussian blur that averages only the pixels `weight` marks (normalised convolution)."""
        den = cv2.GaussianBlur(weight, (0, 0), sigma) + 1e-4
        if img.ndim == 3:
            return cv2.GaussianBlur(img * weight[..., None], (0, 0), sigma) / den[..., None]
        return cv2.GaussianBlur(img * weight, (0, 0), sigma) / den

    @staticmethod
    def _light_plane(img: np.ndarray, weight: np.ndarray, sigma: float) -> np.ndarray:
        """
        The light of the backdrop: around every pixel a plane is fitted through the pixels `weight` marks (Gaussian
        window `sigma`) and read at the pixel itself.
        A plain average (see _blur_valid) is pulled towards the side its window can see: at the borders of the frame
        and next to the person, where half of the window is missing, it bends towards the open side, and on a
        backdrop that gets darker towards the edges everything built on it lightened a strip along the borders of
        the frame. The plane follows the slope of the light, so it has no such pull.
        The field is smooth, so the fit runs on a grid reduced until the window is about 6 cells wide.
        """
        h, w = img.shape
        f = max(1, int(round(sigma / 6.0)))
        gw, gh = max(8, int(round(w / f))), max(8, int(round(h / f)))
        wt = cv2.resize(weight, (gw, gh), interpolation=cv2.INTER_AREA).astype(np.float64)
        wl = cv2.resize(img * weight, (gw, gh), interpolation=cv2.INTER_AREA).astype(np.float64)
        sg = max(0.8, sigma * gw / float(w))
        # coordinates in units of the window, so that the sums below are all of the same order
        xs = (np.arange(gw, dtype=np.float64) / sg)[None, :]
        ys = (np.arange(gh, dtype=np.float64) / sg)[:, None]

        def gsum(a):  # (nothing outside the frame takes part: the window is simply cut there)
            return cv2.GaussianBlur(a, (0, 0), sg, borderType=cv2.BORDER_CONSTANT)

        s0, sx, sy = gsum(wt), gsum(wt * xs), gsum(wt * ys)
        sxx, sxy, syy = gsum(wt * xs * xs), gsum(wt * xs * ys), gsum(wt * ys * ys)
        t0, tx, ty = gsum(wl), gsum(wl * xs), gsum(wl * ys)
        # the same sums about the pixel itself
        mx, my = sx - xs * s0, sy - ys * s0
        mxx = sxx - 2.0 * xs * sx + xs * xs * s0
        myy = syy - 2.0 * ys * sy + ys * ys * s0
        mxy = sxy - xs * sy - ys * sx + xs * ys * s0
        ux, uy = tx - xs * t0, ty - ys * t0
        # a little weight on "no slope": with next to nothing to fit through, the plane becomes the plain average
        ridge = 0.02 * s0 + 1e-6
        a11, a22 = mxx + ridge, myy + ridge
        det = s0 * (a11 * a22 - mxy * mxy) - mx * (mx * a22 - mxy * my) + my * (mx * mxy - a11 * my)
        num = t0 * (a11 * a22 - mxy * mxy) - mx * (ux * a22 - mxy * uy) + my * (ux * mxy - a11 * uy)
        plain = t0 / np.maximum(s0, 1e-9)
        fit = np.where(det > 1e-12, num / np.maximum(det, 1e-12), plain)
        # (a plane through a handful of pixels may point anywhere: never further from the plain average than 25 L*)
        fit = np.where(s0 > 1e-4, np.clip(fit, plain - 25.0, plain + 25.0), plain)
        return cv2.resize(fit.astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)

    @staticmethod
    def _even_by_tone(guide: np.ndarray, values: np.ndarray, valid: np.ndarray, sigma_s: float, sigma_r: float):
        """
        Edge-keeping average (a joint bilateral filter): every pixel becomes the average of the `valid` pixels around
        it (reach `sigma_s`) whose `guide` value is close to its own (closeness `sigma_r`). A pixel on the other side
        of a real edge - a shadow, a hem, a prop - has a different guide value and takes no part, so edges stay.
        The guide axis is cut into a few layers and the space is handled on a reduced grid: the cost does not grow
        with the reach. Returns (averaged values, how much backdrop of the same tone was found around each pixel).
        The layers cover every tone the backdrop has - the darkest corner of a shadow and a dark spot inside it
        included. (Covering "nearly all" of them was not enough: the darkest half percent stayed untouched while
        everything around it was evened, and showed as specks and ragged patches.) Only on a frame of extreme
        contrast the far ends are left out: there a pixel is changed less and less, down to nothing one layer
        further - gradually, a sharp limit would be a visible border.
        The layers sit at fixed tones (multiples of the layer step), so they are the same for the frame and for its
        reduced copy in the light preview.
        """
        h, w = guide.shape
        picked = guide[valid > 0.5]
        conf = np.zeros((h, w), np.float32)
        if picked.size < 64:
            return values.copy(), conf
        step = 0.8 * sigma_r
        max_layers = 48
        k_lo, k_hi = int(np.floor(float(picked.min()) / step)), int(np.ceil(float(picked.max()) / step))
        if k_hi - k_lo + 1 > max_layers:
            # a frame of extreme contrast: keep the layers as fine as they are, around the tone the backdrop mostly has
            k_mid = int(round(float(np.median(picked)) / step))
            k_lo, k_hi = max(k_lo, k_mid - max_layers // 2), min(k_hi, k_mid + max_layers // 2 - 1)
        k_hi = max(k_hi, k_lo + 1)
        lo, n_layers = k_lo * step, k_hi - k_lo + 1
        shrink = max(1, int(round(sigma_s / 3.0)))
        gw, gh = max(4, int(round(w / shrink))), max(4, int(round(h / shrink)))
        sigma_g = max(0.8, sigma_s / shrink)
        out = np.zeros_like(values)
        w_sum = np.zeros((h, w), np.float32)
        inv_2r2 = 1.0 / (2.0 * sigma_r * sigma_r)
        for j in range(n_layers):
            level = lo + j * step
            tent = np.maximum(0.0, 1.0 - np.abs(guide - level) / step)
            if not np.any(tent > 0):
                continue
            w_l = valid * np.exp(-((guide - level) ** 2) * inv_2r2)
            den = cv2.GaussianBlur(cv2.resize(w_l, (gw, gh), interpolation=cv2.INTER_AREA), (0, 0), sigma_g)
            num = cv2.GaussianBlur(cv2.resize(w_l[..., None] * values, (gw, gh), interpolation=cv2.INTER_AREA), (0, 0), sigma_g)
            den_u = cv2.resize(den, (w, h), interpolation=cv2.INTER_LINEAR)
            num_u = cv2.resize(num, (w, h), interpolation=cv2.INTER_LINEAR)
            out += tent[..., None] * (num_u / np.maximum(den_u, 1e-5)[..., None])
            conf += tent * den_u
            w_sum += tent
        # Inside the range of the layers two neighbouring layers always add up to 1; beyond its ends the sum falls
        # to 0 within one layer step - that is the gradual limit described above.
        inside = w_sum > 1e-3
        share = np.clip(w_sum, 0.0, 1.0)
        norm = 1.0 / np.maximum(w_sum, 1e-6)
        out = np.where(inside[..., None], values + (out * norm[..., None] - values) * share[..., None], values)
        return out.astype(np.float32), np.where(inside, conf * norm * share, 0.0).astype(np.float32)

    def _smooth_backdrop_stains(self, small_rgb: np.ndarray, fg_s: np.ndarray, st_s: np.ndarray, sm_s: np.ndarray,
                                strength: float):
        """
        Stains, smears and shoe marks of the backdrop ("Сліди взуття та розводи").
        small_rgb: the frame at the working size (float32 RGB 0..1); fg_s / st_s / sm_s: person, gear and smoke maps of
        the same size (0..1); strength: slider / 100 (0..2 with Turbo).
        The backdrop is averaged with its own neighbourhood, but only with pixels of a similar tone (_even_by_tone):
        a stain, a smear or a footprint is a small departure from the tone around it and dissolves; a cast shadow, the
        pool of a lamp, a hem or a prop is a large one and stays. Only backdrop pixels are sources, so nothing of the
        person, of the gear or of protected smoke leaks in, and the result is carried right up to the silhouette
        (the old way faded out a few hundred pixels before the person - exactly where the floor is dirtiest).
        "Similar" is judged after the light itself (anything wider than 6% of the frame) is taken out, and more
        strictly on a dark backdrop, where a difference of one L* is already a visible shape of light.
        A bend of the light narrower than that - the rim of a lamp's pool, the soft edge of a shadow - is not an even
        surface with a stain on it either. Where such a shape changes across the reach by more than a stain may
        differ, the backdrop is left as it is: an edge-keeping average flattens the two shoulders of the bend and so
        sharpens it into a line. (A steady gradient, however steep, has no shoulders and is evened as usual.)
        What cannot be told apart: a soft shadow no bigger than a stain. It is evened in proportion to its size
        (about a fifth of the depth for a soft shadow of 8% of the frame height); contact and large shadows stay.
        The correction is computed at this working size and added to the full frame, so the fine grain of the
        vinyl is not touched. Returns (RGB correction, layer alpha), both at the working size.
        """
        sh, sw = fg_s.shape
        s = float(np.clip(strength, 0.0, 2.0))
        lab = cv2.cvtColor(np.clip(small_rgb, 0.0, 1.0).astype(np.float32), cv2.COLOR_RGB2LAB)
        # (the gear map is a soft zone around the stands; from 0.45 down it is plain backdrop next to them)
        valid = ((fg_s < 0.05) & (st_s < 0.45) & (sm_s < 0.30)).astype(np.float32)
        long_side = float(max(sh, sw))
        sigma_r = 1.0 + 3.2 * s                                   # how far from the tone around it a stain may be (L*)
        sigma_s = (0.010 + 0.016 * min(1.0, s)) * long_side      # how far around the tone is taken from
        light = self._light_plane(lab[..., 0], valid, 0.06 * long_side)  # anything wider than this is light, not dirt
        dark_tol = np.clip((light + 6.0) / 40.0, 0.35, 1.0)       # 1 from L* 34 up, 0.35 on a black backdrop
        # What is evened is the backdrop with its light taken out; the light is put back unchanged afterwards. (An
        # average of the brightness itself would flatten the light wherever the neighbourhood is one-sided.)
        flat = lab.copy()
        flat[..., 0] -= light
        guide = flat[..., 0] / dark_tol
        evened, conf = self._even_by_tone(guide, flat, valid, sigma_s, sigma_r)
        # A pixel with next to no backdrop of its tone within reach has nothing to be evened with (the average
        # would be a guess from a few pixels). The bar is low on purpose: a stain inside a small dark corner has
        # only that corner to be evened with, and must still go.
        even_w = np.clip(conf / 0.03, 0.0, 1.0)
        # the shapes of light that the wide estimate above could not follow (larger than a stain, narrower than 6%):
        # how much they change across the reach (L*), against what a stain may differ by
        bend = self._blur_valid(flat[..., 0], valid, 1.5 * sigma_s)
        span = np.hypot(cv2.Sobel(bend, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(bend, cv2.CV_32F, 0, 1, ksize=3)) * (sigma_s / 4.0)
        slope_w = 1.0 - np.clip((span / (sigma_r * dark_tol) - self.STAIN_SLOPE_FROM) / (self.STAIN_SLOPE_TO - self.STAIN_SLOPE_FROM), 0.0, 1.0)
        slope_w = slope_w * slope_w * (3.0 - 2.0 * slope_w)
        corr = (evened - flat) * (even_w * slope_w * valid)[..., None]
        del flat, evened
        # A stain is a small change of tone: anything bigger is left to the repair (dust, hair) or is not dirt at all.
        # The colour may move only a little, so a petal, a toy or coloured tape never fades into the backdrop.
        l_cap, c_cap = 3.0 * sigma_r * dark_tol, 2.5 + 3.0 * s
        corr[..., 0] = np.clip(corr[..., 0], -l_cap, l_cap)
        np.clip(corr[..., 1:], -c_cap, c_cap, out=corr[..., 1:])
        # Carry the correction under the soft edge of the silhouette and into the soft zone around the gear from the
        # backdrop next to it, so that it ends gradually there instead of at a visible border
        sigma_e = max(1.5, 0.010 * long_side)
        corr_near = self._blur_valid(corr, valid, sigma_e)
        reach = np.clip(cv2.GaussianBlur(valid, (0, 0), sigma_e) / 0.25, 0.0, 1.0)
        corr = corr * valid[..., None] + corr_near * ((1.0 - valid) * reach)[..., None]
        lab_new = lab + corr
        np.clip(lab_new[..., 0], 0.0, 100.0, out=lab_new[..., 0])
        rgb_new = np.clip(cv2.cvtColor(lab_new.astype(np.float32), cv2.COLOR_LAB2RGB), 0.0, 1.0)
        gate = (
            (1.0 - np.clip((fg_s - 0.15) / 0.55, 0.0, 1.0))
            * (1.0 - np.clip((st_s - 0.15) / 0.65, 0.0, 1.0))
            * (1.0 - np.clip(sm_s * 1.6, 0.0, 1.0))
            * min(1.0, s / 0.35)
        )
        diff_s = ((rgb_new - small_rgb) * gate[..., None]).astype(np.float32)
        # Layer alpha: the zones where the backdrop was really evened. It is judged over a wide neighbourhood, so it
        # rises and falls slowly: a threshold on every single pixel would switch the correction on and off along
        # thin contours, and those contours would be new lines in the photo.
        active = cv2.GaussianBlur(np.max(np.abs(diff_s), axis=2), (0, 0), 0.02 * long_side)
        alpha_s = np.clip((active - 0.0003) / 0.0009, 0.0, 1.0) * (1.0 - np.clip((fg_s - 0.15) / 0.66, 0.0, 1.0))
        return diff_s, alpha_s.astype(np.float32)

    def _apply_cyclorama_curve(
        self,
        cleaned_f32: np.ndarray,
        eff_fg_u8: np.ndarray,
        stand_protect_s: np.ndarray,
        smoke_s: np.ndarray,
        shadow_s: np.ndarray,
        cyc_strength: float,
        feather_str: float,
        fast_mode: bool = False,
        line: dict | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Turns the wall-to-floor corner (`кут`) into a seamless cyclorama gradient.

        How: the background is split into "what a row looks like on average along the corner line" (this holds the
        brightness step of the corner, sharp) and everything else (grain, dust, texture). Only the first part is
        replaced by its own vertical blur - the cove. The correction is one smooth field, so the person's shadows keep
        their depth, the grain is untouched and the line disappears right up to the silhouette.
        Strength: width of the cove (from about 60 the line is gone, lower values only soften it).
        The corner is looked for between 25% and 82% of the frame height; no corner found -> nothing is changed.
        `line`: the corner as _corner_line_of_frame gave it for this frame (pixels of THIS frame). process() passes it,
        so the line is looked for once, on the untouched frame; without it the line is looked for here.
        `shadow_s` and `feather_str` are accepted for compatibility with the old call and are not used: the old
        version skipped every shadowed area, which is exactly where the line stayed visible.
        Returns (image, layer alpha of the changed zone).
        """
        h, w = cleaned_f32.shape[:2]
        s = float(np.clip(cyc_strength / 100.0, 0.0, 1.0))
        if s <= 0:
            return cleaned_f32, np.zeros((h, w), dtype=np.float32)

        # ---------- A. find the corner on a small copy ----------
        sc = min(1.0, (768.0 if fast_mode else 1024.0) / max(h, w))
        sw, sh = max(16, int(round(w * sc))), max(16, int(round(h * sc)))
        sm = np.clip(cv2.resize(cleaned_f32, (sw, sh), interpolation=cv2.INTER_AREA), 0.0, 1.0)
        fg_s = cv2.resize(eff_fg_u8, (sw, sh), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
        st_s = cv2.resize(stand_protect_s, (sw, sh), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0
        sk_s = cv2.resize(smoke_s, (sw, sh), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0
        L = cv2.cvtColor(sm, cv2.COLOR_RGB2LAB)[:, :, 0]

        def background(st_map, st_lim=0.25):
            bad = (fg_s > 0.04) | (st_map > st_lim) | (sk_s > 0.20)
            return 1.0 - cv2.dilate(bad.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(np.float32)

        if line is None:
            found = self._find_corner_line(L, background(st_s))
            if found is None or found["score"] < self.CORNER_MIN_SCORE:
                return cleaned_f32, np.zeros((h, w), dtype=np.float32)
            a_lin, row_small, step_sign = found["slope"], found["row"], found["step"]
        else:
            a_lin, step_sign = float(line["slope"]), float(line.get("step", -1.0))
            row_small = (float(line["row"]) + 0.5) * sc - 0.5
        cx_s, cx = (sw - 1) / 2.0, (w - 1) / 2.0
        row_c = (row_small + 0.5) / sc - 0.5  # corner row at the centre column, full-res
        xs_s = np.arange(sw, dtype=np.float32)
        xs = np.arange(w, dtype=np.float32)

        # The stand detector takes a SHORT visible piece of the corner for a cable. Along the found line such a thin,
        # line-hugging piece is the corner itself -> stop protecting it (real stands cross the line and stay protected).
        hb = max(4, int(round(0.022 * sh)))
        line_rows_s = row_small + a_lin * (xs_s - cx_s)
        yy_s = np.arange(sh, dtype=np.float32)[:, None]
        dist_s = np.abs(yy_s - line_rows_s[None, :])
        near = dist_s <= hb
        ring = (dist_s > hb) & (dist_s <= 2.6 * hb)
        crossing = (np.where(ring, st_s, 0.0).max(axis=0) > 0.25)[None, :]  # columns where the gear continues beyond the band
        st_s = np.where(near & ~crossing, 0.0, st_s)
        # The line is LOOKED FOR well away from the gear (above), but it is REMOVED right up to it: the gear map is a
        # wide soft zone around every stand, and a corner line left inside that zone showed as a short stub next to
        # the stand. Only the stand itself (the core of the zone) is left out of the estimate; whatever else differs
        # from the backdrop is dropped by the "alike" test below.
        ST_CORE = 0.60
        valid_s = background(st_s, ST_CORE)

        # ---------- B. exact shape of the line at full resolution (tilt + slight lens curvature) ----------
        r_sharp = int(max(40, 0.022 * h))
        fit = np.zeros(3, np.float64)  # extra offset: c0 + c1*u + c2*u^2 with u = (x - cx) / w

        def line_rows(xv):
            u = (xv - cx) / w
            return row_c + a_lin * (xv - cx) + fit[0] + fit[1] * u + fit[2] * u * u

        def strip_inputs(half):
            """Straightened full-res strip around the line: (y0, y1, delta, gray, valid weight)."""
            ext = float(np.max(np.abs(line_rows(xs) - line_rows(np.float32(cx)))))
            y0 = int(max(0, np.floor(line_rows(np.float32(cx)) - half - 4)))
            y1 = int(min(h, np.ceil(line_rows(np.float32(cx)) + half + 5)))
            delta = (line_rows(xs) - line_rows(np.float32(cx))).astype(np.float32)
            ya, yb = int(max(0, y0 - np.ceil(ext) - 2)), int(min(h, y1 + np.ceil(ext) + 3))
            src = cleaned_f32[ya:yb]
            fgb = cv2.dilate(eff_fg_u8[ya:yb], np.ones((9, 9), np.uint8))
            M = np.float32([[sw / w, 0, 0.5 * sw / w - 0.5], [0, sh / h, (ya + 0.5) * sh / h - 0.5]])
            st_up = cv2.warpAffine(st_s, M, (w, yb - ya), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
            sk_up = cv2.warpAffine(sk_s, M, (w, yb - ya), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
            ok_f = ((fgb < 10) & (st_up < ST_CORE) & (sk_up < 0.20)).astype(np.float32)
            d_in = delta + (y0 - ya)  # rows of `src` that hold strip row 0
            straight = self._shift_columns(src, d_in)[: y1 - y0]
            ok_s = self._shift_columns(ok_f, d_in, border=cv2.BORDER_CONSTANT)[: y1 - y0]
            return y0, y1, ya, yb, delta, straight, ok_s

        try:
            half_fit = int(r_sharp + 0.012 * h)
            y0, y1, ya, yb, delta, straight, ok_s = strip_inputs(half_fit)
            gray = cv2.cvtColor(straight, cv2.COLOR_RGB2GRAY) * 255.0
            n_blk = 24
            bx = [int(i * w / n_blk) for i in range(n_blk + 1)]
            r0 = line_rows(np.float32(cx)) - y0
            sgn = 1.0 if step_sign >= 0 else -1.0
            pts = []
            for i in range(n_blk):
                wv = ok_s[:, bx[i]:bx[i + 1]]
                cnt = wv.sum(axis=1)
                if float(np.median(cnt)) < 0.5 * (bx[i + 1] - bx[i]):
                    continue
                prof = (gray[:, bx[i]:bx[i + 1]] * wv).sum(axis=1) / np.maximum(cnt, 1.0)
                prof = cv2.GaussianBlur(prof.reshape(-1, 1).astype(np.float32), (1, 0), sigmaX=0.1, sigmaY=2.0).ravel()
                d = np.zeros_like(prof)
                d[3:-3] = (prof[6:] - prof[:-6]) * sgn
                lo, hi = int(max(3, r0 - 0.02 * h - 6)), int(min(len(prof) - 3, r0 + 0.02 * h + 7))
                if hi - lo < 8:
                    continue
                j = lo + int(np.argmax(d[lo:hi]))
                if d[j] <= 0.12:
                    continue
                j0, j1 = max(lo, j - 5), min(hi, j + 6)
                wj = np.maximum(d[j0:j1], 0.0) ** 2
                pos = float((np.arange(j0, j1) * wj).sum() / max(float(wj.sum()), 1e-6))
                pts.append(((bx[i] + bx[i + 1]) * 0.5, pos - r0, float(d[j])))
            if len(pts) >= 3:
                px = np.array([(p[0] - cx) / w for p in pts]); py = np.array([p[1] for p in pts]); pw_ = np.array([p[2] for p in pts])
                deg = 2 if (len(pts) >= 8 and (px.max() - px.min()) > 0.45) else 1
                keep = np.ones(len(pts), bool)
                coef = np.zeros(deg + 1)
                for _ in range(3):
                    if keep.sum() < deg + 2:
                        break
                    coef = np.polyfit(px[keep], py[keep], deg, w=np.sqrt(pw_[keep]))
                    res = np.abs(np.polyval(coef, px) - py)
                    tol = max(2.5, 2.5 * float(np.median(res[keep])))
                    keep = res <= tol
                if keep.sum() >= deg + 2:
                    c = coef[::-1]  # c0, c1[, c2]
                    cand = np.array([c[0], c[1], c[2] if deg == 2 else 0.0])
                    off = cand[0] + cand[1] * ((xs - cx) / w) + cand[2] * ((xs - cx) / w) ** 2
                    if float(np.max(np.abs(off))) <= 0.02 * h + 6:  # a wild fit is worse than the straight estimate
                        fit = cand
        except Exception:
            fit = np.zeros(3, np.float64)

        # ---------- C. cove = vertical blur of the row-wise background, on the small copy ----------
        sig_v = (0.012 + 0.058 * s) * h  # half-width of the cove, full-res px
        mix_max = min(1.0, 0.35 + 1.3 * s)
        delta_s = ((line_rows((xs_s + 0.5) / sc - 0.5) - line_rows(np.float32(cx))) * sc).astype(np.float32)
        row_s = (line_rows(np.float32(cx)) + 0.5) * sc - 0.5
        sm_st = self._shift_columns(sm, delta_s)
        va_st = self._shift_columns(valid_s, delta_s, border=cv2.BORDER_CONSTANT)
        k_loc, k_wide = int(sw * 0.045), int(sw * 0.30)
        rows_idx = np.arange(sh)

        def reference(weight):
            """
            Backdrop tone of every row judged by its wider surroundings: the MEDIAN of the visible backdrop in a wide
            window, so that a small foreign patch (a hand in a gap between people, a prop) cannot shift it.
            Falls back to the whole row, then to the nearest rows that have any backdrop.
            """
            vis = weight > 0.5
            data = np.where(vis[..., None], sm_st, np.float32(np.inf))

            def row_median(x0, x1):
                cnt = vis[:, x0:x1].sum(axis=1)
                srt = np.sort(data[:, x0:x1], axis=1)  # hidden pixels (inf) go to the end
                mid = np.clip((cnt - 1) // 2, 0, x1 - x0 - 1)
                return srt[rows_idx, mid], cnt

            whole, cnt_all = row_median(0, sw)
            have = cnt_all >= 3
            if not bool(have.any()):
                return None
            whole = np.stack([np.interp(rows_idx, rows_idx[have], whole[have, c]) for c in range(3)], axis=1).astype(np.float32)
            n_win = 9
            centres = np.linspace(0.0, sw - 1.0, n_win)
            cols = []
            for cxw in centres:
                x0, x1 = int(max(0, round(cxw - k_wide))), int(min(sw, round(cxw + k_wide) + 1))
                med, cnt = row_median(x0, x1)
                enough = cnt >= max(3, int(0.04 * (x1 - x0)))
                cols.append(np.where(enough[:, None], med, whole))
            stack = np.stack(cols, axis=1).astype(np.float32)  # sh x n_win x 3
            pos = np.interp(np.arange(sw), centres, np.arange(n_win))
            i0 = np.clip(np.floor(pos).astype(np.int64), 0, n_win - 2)
            fr = (pos - i0).astype(np.float32)[None, :, None]
            return stack[:, i0] * (1.0 - fr) + stack[:, i0 + 1] * fr

        ref = reference(va_st)
        if ref is None:
            return cleaned_f32, np.zeros((h, w), dtype=np.float32)
        ref_gray = cv2.cvtColor(ref, cv2.COLOR_RGB2GRAY)
        # A visible patch far darker or lighter than the backdrop around it is something the masks missed - it is not
        # the backdrop, so it takes no part in the estimate.
        px_gray = cv2.GaussianBlur(cv2.cvtColor(sm_st, cv2.COLOR_RGB2GRAY), (0, 0), 1.0)
        ratio = (px_gray + 0.004) / (ref_gray + 0.004)
        alike = np.clip((ratio - 0.40) / 0.15, 0.0, 1.0) * np.clip((2.6 - ratio) / 0.6, 0.0, 1.0)
        va_st = va_st * cv2.erode(alike, np.ones((3, 3), np.uint8))

        lf_loc, den_s = self._box_norm_x(sm_st, va_st, k_loc)
        conf = np.clip((den_s - 0.01) / 0.04, 0.0, 1.0)  # 1 = this row's backdrop is visible right here
        lf_s = lf_loc * conf[..., None] + ref * (1.0 - conf[..., None])
        sv = max(1.5, sig_v * sc)
        d_rel = np.abs(yy_s - row_s) / sv
        W_s = np.clip((3.2 - d_rel) / 2.0, 0.0, 1.0)
        W_s = (W_s * W_s * (3.0 - 2.0 * W_s) * mix_max)[..., None]

        # (1) what the corner needs judging by the wider surroundings: robust, smooth along the line, defined everywhere
        c_ref = (self._blur_rows(ref, sv) - ref) * W_s
        # (2) the same from the backdrop visible right here: exact, but only where the column is visible above and below
        trust = conf * (0.2 + 0.8 * np.clip(den_s / 0.3, 0.0, 1.0)) + 0.15 * (1.0 - conf) + 1e-3
        cove_s = self._blur_rows(lf_s * trust[..., None], sv) / self._blur_rows(trust, sv)[..., None]
        gain = np.clip((cv2.cvtColor(lf_loc, cv2.COLOR_RGB2GRAY) + 1e-4) / (ref_gray + 1e-4), 0.0, 2.5)
        gain = gain * conf + (1.0 - conf)  # how much lighter/darker the backdrop is here than around
        c_exp = c_ref * gain[..., None]
        # the local answer may differ from the expected one only moderately: this keeps the subject's own shadows
        # from being washed out and stops anything unusual from being "evened"
        tol = 0.012 + 0.6 * np.abs(c_exp)
        c_loc = np.clip((cove_s - lf_s) * W_s, c_exp - tol, c_exp + tol)
        seen = self._blur_rows(conf, sv)
        full = (np.clip((seen - 0.55) / 0.35, 0.0, 1.0) * conf)[..., None]
        corr_s = c_loc * full + c_exp * (1.0 - full)

        # Nothing needs a bigger change than a few times the brightness step of the corner itself.
        gray_st = cv2.cvtColor(lf_s, cv2.COLOR_RGB2GRAY)
        r_i = int(round(row_s))
        up_rows = slice(max(0, r_i - 18), max(1, r_i - 5))
        dn_rows = slice(min(sh - 1, r_i + 6), min(sh, r_i + 19))
        w_up, w_dn = conf[up_rows], conf[dn_rows]
        if float(w_up.sum()) > 1.0 and float(w_dn.sum()) > 1.0:
            step_gray = abs(float((gray_st[up_rows] * w_up).sum() / w_up.sum()) - float((gray_st[dn_rows] * w_dn).sum() / w_dn.sum()))
        else:
            step_gray = 0.04
        cap = 0.02 + 3.0 * step_gray
        np.clip(corr_s, -cap, cap, out=corr_s)
        corr_s = self._shift_columns(corr_s, -delta_s)
        lf_gray_s = self._shift_columns(gray_st, -delta_s)
        amp_s = np.max(np.abs(corr_s), axis=2)
        alpha_s = cv2.GaussianBlur(np.clip(amp_s / 0.004, 0.0, 1.0), (0, 0), 2.0)

        # rows of the frame the correction can reach
        reach = 3.2 * sig_v + float(np.max(np.abs(line_rows(xs) - line_rows(np.float32(cx))))) + 2.0 / sc + 4
        ra = int(max(0, np.floor(line_rows(np.float32(cx)) - reach)))
        rb = int(min(h, np.ceil(line_rows(np.float32(cx)) + reach)))
        if rb - ra < 4:
            return cleaned_f32, np.zeros((h, w), dtype=np.float32)
        M_up = np.float32([[sw / w, 0, 0.5 * sw / w - 0.5], [0, sh / h, (ra + 0.5) * sh / h - 0.5]])
        up = dict(flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
        corr = cv2.warpAffine(corr_s, M_up, (w, rb - ra), **up)

        # ---------- D. the sharp part of the step, which the small copy cannot hold, in a thin full-res strip ----------
        try:
            y0, y1, ya, yb, delta, straight, ok_s = strip_inputs(r_sharp)
            lf_f, den_f = self._box_norm_x(straight, ok_s, int(w * 0.045))
            lf_f = cv2.GaussianBlur(lf_f, (1, 0), sigmaX=0.1, sigmaY=1.0)
            hs = y1 - y0
            lo_size = (max(8, int(round(w * sc))), max(4, int(round(hs * sc))))
            lf_lo = cv2.resize(cv2.resize(lf_f, lo_size, interpolation=cv2.INTER_AREA), (w, hs), interpolation=cv2.INTER_LINEAR)
            df = np.abs(np.arange(hs, dtype=np.float32)[:, None] + y0 - line_rows(np.float32(cx)))
            Wf = np.clip((r_sharp - df) / (0.45 * r_sharp), 0.0, 1.0)
            Wf = Wf * Wf * (3.0 - 2.0 * Wf) * mix_max
            # only where the small copy trusted the backdrop too, and never more than the corner step itself
            M_st = np.float32([[sw / w, 0, 0.5 * sw / w - 0.5], [0, sh / h, (y0 + 0.5) * sh / h - 0.5]])
            conf_f = cv2.warpAffine(conf, M_st, (w, hs), **up)
            gain_f = cv2.warpAffine(gain, M_st, (w, hs), **up)
            lim = (0.004 + 0.75 * step_gray * gain_f)[..., None]
            resid = np.clip(lf_f - lf_lo, -lim, lim) * (Wf * conf_f * np.clip((den_f - 0.02) / 0.06, 0.0, 1.0))[..., None]
            # back to the original (un-straightened) geometry; rows ya..yb of the frame
            pad_top = y0 - ya
            canvas = np.zeros((yb - ya, w, 3), np.float32)
            canvas[pad_top:pad_top + hs] = resid
            resid_back = self._shift_columns(canvas, -delta, border=cv2.BORDER_CONSTANT)
            c0, c1 = max(ya, ra), min(yb, rb)
            if c1 > c0:
                corr[c0 - ra:c1 - ra] -= resid_back[c0 - ya:c1 - ya]
        except Exception:
            pass

        # ---------- E. apply to the background only ----------
        # right up to the silhouette: the correction is a soft tone shift of a few levels, it cannot hurt hair or hems
        gate_lut = 1.0 - np.clip((np.arange(256, dtype=np.float32) / 255.0 - 0.30) / 0.40, 0.0, 1.0)
        gate = cv2.LUT(np.ascontiguousarray(eff_fg_u8[ra:rb]), gate_lut)
        # Stands and cables are NOT left out here: the correction is a slow change of tone, it cannot damage them,
        # while a zone around every stand that keeps the old tone shows as a sleeve once the backdrop next to it
        # has moved. (They take no part in the estimate above; a dark stand receives less - see below.)
        sk_up = cv2.warpAffine(sk_s, M_up, (w, rb - ra), **up)
        gate *= 1.0 - np.clip(sk_up * 1.6, 0.0, 1.0)
        band = cleaned_f32[ra:rb]
        # The correction is meant for the lit backdrop. A pixel much darker than the backdrop around it (deep shadow,
        # a dark object or hair the masks missed) receives proportionally less: light scaled, not paint added.
        g_band = cv2.GaussianBlur(cv2.cvtColor(band, cv2.COLOR_RGB2GRAY), (0, 0), 1.5)
        lf_up = cv2.warpAffine(lf_gray_s, M_up, (w, rb - ra), **up)
        gate *= np.clip(g_band / (0.85 * lf_up + 0.004), 0.0, 1.0)
        corr *= gate[..., None]
        band += corr
        np.clip(band, 0.0, 1.0, out=band)
        cyc_alpha = np.zeros((h, w), dtype=np.float32)
        cyc_alpha[ra:rb] = np.clip(cv2.warpAffine(alpha_s, M_up, (w, rb - ra), **up), 0.0, 1.0) * gate
        return cleaned_f32, cyc_alpha

    # ------------------------------------------------------------------
    # 5c. Print format (5:7): the canvas grows and the studio backdrop is continued into the new strips
    # ------------------------------------------------------------------
    @staticmethod
    def _extension_plan(w: int, h: int, ratio_short: float = 5.0, ratio_long: float = 7.0) -> dict:
        """
        Pixels to add on each side so the frame becomes short:long (5:7) in its own orientation. Only one
        dimension grows, nothing is cropped. Both added strips are equal, so the photo stays centred.
        """
        rs, rl = (float(ratio_short), float(ratio_long)) if ratio_short <= ratio_long else (float(ratio_long), float(ratio_short))
        target = (rs / rl) if h >= w else (rl / rs)  # width / height
        left = right = top = bottom = 0
        if (w / h) < target:
            add = max(0, int(round(h * target)) - w)
            add += add & 1
            left = right = add // 2
        else:
            add = max(0, int(round(w / target)) - h)
            add += add & 1
            top = bottom = add // 2
        return {"left": left, "right": right, "top": top, "bottom": bottom, "new_w": w + left + right, "new_h": h + top + bottom}

    @staticmethod
    def _continue_backdrop(band: np.ndarray, valid: np.ndarray, pad: int, rng) -> np.ndarray:
        """
        One new strip of backdrop next to a frame edge.
          band  - rows x cols x 3 float32 (0..1), column 0 is the frame edge, columns go INTO the frame (cols >= pad)
          valid - rows x cols float32, 1 = backdrop, 0 = a person or an object
        Returns rows x pad x 3: column 0 touches the frame edge.

        The strip is the mirror image of the neighbouring backdrop (so its grain and texture are real and it joins
        the frame without a seam), with the lighting corrected: a mirror would also turn the light fall-off around,
        which shows as a crease along the old edge. Instead every row keeps the tone it has at the edge and carries
        on with the same, slowly fading, slope. A mirrored person or object is never drawn: the backdrop tone of
        the nearby rows and the texture of the backdrop a little higher or lower take its place.
        """
        rows, cols = valid.shape
        sig_x = max(6.0, 0.35 * pad)

        # Small things that are clearly not backdrop but that no mask caught (the foot of a stand, a cable end, a
        # piece of tape) must not be mirrored either. They are found by comparing every spot with the typical tone
        # of the backdrop around it (a median over a wide window follows the lighting and ignores small objects).
        f = max(1, min(rows, cols) // 90)
        size = (max(2, cols // f), max(2, rows // f))
        g_small = cv2.resize(cv2.cvtColor(band, cv2.COLOR_RGB2GRAY), size, interpolation=cv2.INTER_AREA)
        v_small = cv2.resize(valid, size, interpolation=cv2.INTER_AREA)
        if float(v_small.mean()) > 0.2:
            sg = max(2.0, 2.0 * pad / f)
            tone = cv2.GaussianBlur(g_small * v_small, (0, 0), sg) / np.maximum(cv2.GaussianBlur(v_small, (0, 0), sg), 1e-3)
            filled = np.where(v_small > 0.5, g_small, tone)  # people do not take part in the median
            k_med = int(min(255, max(3, 4 * pad // f))) | 1
            typical = cv2.medianBlur(np.clip(filled * 255.0 + 0.5, 0, 255).astype(np.uint8), k_med).astype(np.float32) / 255.0
            odd = (np.abs(g_small - typical) > (0.05 + 0.18 * typical)) & (v_small > 0.5)
            if 0.0 < float(odd.mean()) < 0.35:
                odd = cv2.dilate(odd.astype(np.uint8), np.ones((3, 3), np.uint8))
                valid = valid * (cv2.resize(odd, (cols, rows), interpolation=cv2.INTER_LINEAR) == 0)

        weighted = band * valid[..., None]

        def backdrop_tone(sx, sy):
            """Average of the visible backdrop around every pixel, and how much of it there was (0..1)."""
            fx, fy = max(1, int(sx // 8.0)), max(1, int(sy // 8.0))  # a wide average is taken on a shrunk copy
            if fx > 1 or fy > 1:
                size = (max(2, cols // fx), max(2, rows // fy))
                sxy = dict(sigmaX=sx / fx, sigmaY=sy / fy)
                num = cv2.GaussianBlur(cv2.resize(weighted, size, interpolation=cv2.INTER_AREA), (0, 0), **sxy)
                den = cv2.GaussianBlur(cv2.resize(valid, size, interpolation=cv2.INTER_AREA), (0, 0), **sxy)
                tone = cv2.resize(num / np.maximum(den, 1e-4)[..., None], (cols, rows), interpolation=cv2.INTER_LINEAR)
                return tone, cv2.resize(den, (cols, rows), interpolation=cv2.INTER_LINEAR)
            den = cv2.GaussianBlur(valid, (0, 0), sigmaX=sx, sigmaY=sy)
            return cv2.GaussianBlur(weighted, (0, 0), sigmaX=sx, sigmaY=sy) / np.maximum(den, 1e-4)[..., None], den

        lf, den = backdrop_tone(sig_x, 2.0)
        conf = np.clip((den - 0.02) / 0.10, 0.0, 1.0)
        if float(conf.min()) < 1.0:
            # Where the backdrop is hidden right at this edge its tone is taken, in this order, from the same row
            # farther into the frame (a wall-floor line then stays a line), from the rows above and below, and
            # from the whole band.
            lf_w, den_w = backdrop_tone(4.0 * sig_x, 2.0)
            conf_w = np.clip((den_w - 0.02) / 0.10, 0.0, 1.0)[..., None]
            lf_t, den_t = backdrop_tone(sig_x, max(8.0, 0.04 * rows))
            conf_t = np.clip((den_t - 0.01) / 0.05, 0.0, 1.0)[..., None]
            total = float(valid.sum())
            overall = weighted.sum(axis=(0, 1)) / total if total > 1.0 else band.mean(axis=(0, 1))
            lf_t = lf_t * conf_t + overall[None, None, :] * (1.0 - conf_t)
            lf_w = lf_w * conf_w + lf_t * (1.0 - conf_w)
            lf = lf * conf[..., None] + lf_w * (1.0 - conf[..., None])
        del weighted

        k = max(2, min(cols - 1, pad))
        edge = lf[:, 0]
        slope = (lf[:, 0] - lf[:, k]) / float(k)  # per pixel, outwards
        k_v = max(3, int(0.06 * rows) | 1)
        slope = cv2.blur(cv2.blur(slope[:, None, :], (1, k_v)), (1, k_v))[:, 0, :]
        reach = max(2.0, 0.6 * pad)
        dist = reach * (1.0 - np.exp(-(np.arange(pad, dtype=np.float32) + 1.0) / reach))  # the slope fades out
        delta = 0.7 * slope[:, None, :] * dist[None, :, None]
        lim = 0.25 * edge[:, None, :] + 0.01
        target = edge[:, None, :] + np.clip(delta, -lim, lim)

        res = band[:, :pad] - lf[:, :pad]
        ok = cv2.erode((valid[:, :pad] > 0.5).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
        if not bool(ok.all()):
            filled = ok.copy()
            step = max(17, int(0.011 * rows) | 1)
            for i in range(1, 25):
                if bool(filled.all()):
                    break
                for sh in (i * step, -i * step):
                    if abs(sh) >= rows:
                        continue
                    src_ok = np.roll(ok, sh, axis=0)
                    if sh > 0:
                        src_ok[:sh] = False
                    else:
                        src_ok[sh:] = False
                    take = (~filled) & src_ok
                    if bool(take.any()):
                        res[take] = np.roll(res, sh, axis=0)[take]
                        filled |= take
            if not bool(filled.all()):
                sigma = res[ok].std(axis=0) if bool(ok.any()) else np.full(3, 0.004, np.float32)
                noise = rng.standard_normal(res.shape).astype(np.float32) * sigma[None, None, :].astype(np.float32)
                res[~filled] = noise[~filled]
        out = target + res
        np.clip(out, 0.0, 1.0, out=out)
        return out

    def extend_canvas(self, img_rgba: np.ndarray, bit_depth: int, params: dict, progress_cb=None) -> tuple[np.ndarray | None, dict]:
        """
        Makes the frame 5:7 (params ratioShort / ratioLong) by ADDING backdrop on two opposite sides.
        Returns (rgba, info). rgba is the picture for a new layer of the enlarged document, new_h x new_w x 4 at
        the document bit depth: opaque in the added strips, fully transparent over the existing photo.
        rgba is None when the frame already has this format (or would have to grow by more than a half).
        """
        t0 = time.perf_counter()
        self._begin_job()
        try:
            h, w = img_rgba.shape[:2]
            ps_max = 32768.0 if bit_depth == 16 else 255.0
            p = dict(params or {})
            plan = self._extension_plan(w, h, float(p.get("ratioShort", 5)), float(p.get("ratioLong", 7)))
            info = dict(plan)
            info.update({"orig_w": w, "orig_h": h, "unchanged": False, "subject_at_edge": False})
            add_x, add_y = plan["left"], plan["top"]
            if add_x + add_y < 2:
                info["unchanged"] = True
                info["reason"] = "already"
                return None, info
            if add_x > 0.5 * w or add_y > 0.5 * h:
                info["unchanged"] = True
                info["reason"] = "too_far"
                return None, info

            rgb = self._rgb_planes(img_rgba)
            rgb_u8 = self._to_analysis_u8(rgb, ps_max)
            if progress_cb is not None:
                progress_cb(20, "Пошук людей у кадрі...")
            with self.lock:
                self._ensure_models_loaded(need_matting=True, need_lama=False, progress_cb=progress_cb)
                fg_raw_1024 = self._predict_fg_raw(rgb_u8, progress_cb=None)
                fg_mask_u8, core_u8 = self._clean_fg_mask(fg_raw_1024, w, h, float(p.get("edge", 70)))
                # Stands, lamps and cables that reach the frame edge are not backdrop either: mirrored into the
                # new strip they would become twice as big. (They are the same things "Прибирати стійки" removes.)
                gear_s = self._compute_protection_maps_small(rgb_u8, fg_mask_u8, core_u8, 80.0, False, False)[1]
            not_bg = np.maximum(fg_mask_u8, ((cv2.resize(gear_s, (w, h), interpolation=cv2.INTER_LINEAR) > 80) * np.uint8(255)))
            # a person (or a dress) cut by the frame edge cannot be continued - the caller is told about it
            if add_x > 0:
                cut = np.concatenate([core_u8[:, :3], core_u8[:, -3:]], axis=1) > 120
                info["subject_at_edge"] = bool(cut.any(axis=1).mean() > 0.004)
            else:
                cut = np.concatenate([core_u8[:3, :], core_u8[-3:, :]], axis=0) > 120
                info["subject_at_edge"] = bool(cut.any(axis=0).mean() > 0.004)
            del rgb_u8, core_u8, fg_mask_u8, gear_s, cut

            if progress_cb is not None:
                progress_cb(55, "Продовження фону...")
            sideways = add_x > 0
            pad = add_x if sideways else add_y
            if not sideways:  # top / bottom: the same code on the transposed frame
                rgb = np.ascontiguousarray(rgb.transpose(1, 0, 2))
                not_bg = np.ascontiguousarray(not_bg.T)
            rows, length = rgb.shape[:2]
            cols = int(min(length, pad + int(3.0 * 4.0 * max(6.0, 0.35 * pad)) + 8))
            k_p = max(5, int(0.004 * max(h, w)) | 1)
            rng = np.random.default_rng(20240705)
            strips = []
            for first in (True, False):  # the side at index 0, then the opposite one
                src = rgb[:, :cols] if first else rgb[:, length - cols:][:, ::-1]
                fgb = not_bg[:, :cols] if first else not_bg[:, length - cols:][:, ::-1]
                band = self._to_unit_f32(np.ascontiguousarray(src), ps_max)
                person = cv2.dilate((np.ascontiguousarray(fgb) > 22).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_p, k_p)))
                strip = self._continue_backdrop(band, 1.0 - person.astype(np.float32), pad, rng)
                strips.append(self._quantize_unit(strip, ps_max, img_rgba.dtype))
                del band, person, strip

            out = np.zeros((plan["new_h"], plan["new_w"], 4), dtype=img_rgba.dtype)
            opaque = int(ps_max)
            first_s, second_s = strips[0][:, ::-1], strips[1]  # strip column 0 touches the frame
            if sideways:
                out[:, :pad, :3] = first_s
                out[:, pad + w:, :3] = second_s
                out[:, :pad, 3] = opaque
                out[:, pad + w:, 3] = opaque
            else:
                out[:pad, :, :3] = first_s.transpose(1, 0, 2)
                out[pad + h:, :, :3] = second_s.transpose(1, 0, 2)
                out[:pad, :, 3] = opaque
                out[pad + h:, :, 3] = opaque
            info["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
            info["gpu"] = self.gpu_name
            info["provider"] = self.provider_name
            return out, info
        finally:
            self._end_job()

    # ------------------------------------------------------------------
    # 5d. Fast Mask Previews (Green-on-Red Action Mask + Legacy Protection)
    # ------------------------------------------------------------------
    def preview_action_mask(self, img_rgba: np.ndarray, bit_depth: int, params: dict, progress_cb=None) -> tuple[np.ndarray, dict]:
        """
        Computes a 0..255 uint8 Green Action Mask (255 = areas CleanVinylPro will clean/heal;
        0 = untouched red-tinted background/subject). Runs in ~0.2-0.5s on a ~1280px UXP proxy.
        """
        t0 = time.perf_counter()
        self._begin_job()
        try:
            h, w = img_rgba.shape[:2]
            ps_max = 32768.0 if bit_depth == 16 else 255.0
            img_rgb_u8 = np.clip((img_rgba[:, :, :3].astype(np.float32) / ps_max) * 255.0 + 0.5, 0, 255).astype(np.uint8)

            spots_str = float(params.get("spots", 75))
            seam_on = bool(params.get("seamOn", True))
            seam_str = float(params.get("seam", 85))
            edge_prot = float(params.get("edge", 70))
            smoke_on = bool(params.get("smokeOn", True))
            smoke_auto = self._smoke_auto(params)
            smoke_str = float(params.get("smoke", 80))
            keep_shadow = bool(params.get("shadow", True))
            remove_stands = bool(params.get("removeStands", False))
            master_val = float(params.get("master", 100))
            seam_join = bool(params.get("seamJoin", True))
            gear_body = bool(params.get("gearBody", True))
            cyc_str = float(params.get("cycCurve", 0))
            frac_fine = bool(params.get("fracFine", True))
            frac_med = bool(params.get("fracMed", True))
            frac_large = bool(params.get("fracLarge", True))

            boost = max(1.0, min(2.0, master_val / 100.0))
            spots_eff = min(160.0, spots_str * boost)
            seam_eff = min(155.0, seam_str * boost)

            with self.lock:
                self._ensure_models_loaded(need_matting=True, need_lama=False, progress_cb=progress_cb)
                fg_raw_1024 = self._predict_fg_raw(img_rgb_u8, progress_cb=progress_cb)
                if progress_cb is not None:
                    progress_cb(65, "Пошук дефектів для зеленої маски...")
                fg_mask_u8, core_mask_u8 = self._clean_fg_mask(fg_raw_1024, w, h, edge_prot)
                stand_protect_s, stand_remove_s, smoke_s, shadow_s = self._compute_protection_maps_small(
                    img_rgb_u8, fg_mask_u8, core_mask_u8, smoke_str, smoke_on, keep_shadow, smoke_auto=smoke_auto,
                    gear_body=gear_body,
                )
                eff_stand_protect = np.zeros_like(stand_protect_s) if remove_stands else stand_protect_s
                eff_fg_for_spots = core_mask_u8 if remove_stands else fg_mask_u8

                seam_mask = np.zeros((h, w), dtype=np.uint8)
                if seam_on and seam_eff > 0 and frac_large:
                    corner_line = None
                    if cyc_str > 0 or seam_join:  # the wall-floor corner, treated exactly as in process()
                        corner_line = self._corner_line_of_frame(img_rgb_u8, eff_fg_for_spots, eff_stand_protect, smoke_s)
                    seam_mask = self._detect_vinyl_seam_mask(
                        img_rgb_u8, eff_fg_for_spots, eff_stand_protect, smoke_s, seam_eff, edge_prot, fast_mode=False,
                        join=seam_join, skip_line=(corner_line if cyc_str > 0 else None),
                        step_ok_line=(corner_line if cyc_str <= 0 else None),
                    )
                    if cyc_str <= 0 and corner_line is not None:
                        seam_mask = self._whole_line_repair_only(seam_mask, corner_line, eff_fg_for_spots)
                    seam_mask[core_mask_u8 > 140] = 0

                spot_mask, _ = self._detect_spots_mask(
                    img_rgb_u8,
                    eff_fg_for_spots,
                    eff_stand_protect,
                    smoke_s,
                    shadow_s,
                    spots_eff,
                    fast_mode=False,
                    frac_fine=frac_fine,
                    frac_med=frac_med,
                    frac_large=frac_large,
                    local_grain=bool(params.get("grainLocal", True)),
                    shadow_spots=bool(params.get("shadowSpots", True)),
                )

                action_bin = np.maximum(seam_mask, spot_mask)
                if remove_stands:
                    stand_rm_full = (cv2.resize(stand_remove_s, (w, h), interpolation=cv2.INTER_LINEAR) > 80).astype(np.uint8)
                    stand_rm_full[core_mask_u8 > 120] = 0
                    action_bin = np.maximum(action_bin, stand_rm_full)

                # Slightly crisp soft edge so green spots are clearly visible like Retouch4me
                action_u8 = cv2.GaussianBlur((action_bin > 0).astype(np.float32) * 255.0, (3, 3), 0)
                action_u8 = np.clip(action_u8, 0, 255).astype(np.uint8)
                if progress_cb is not None:
                    progress_cb(90, "Передача зеленої маски у Photoshop...")

            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            return action_u8, {
                "elapsed_ms": elapsed_ms,
                "mask_type": "action",
                "action_px": int((action_u8 > 32).sum()),
                "gpu": self.gpu_name,
                "provider": self.provider_name,
            }
        finally:
            self._end_job()

    def preview_protection_mask(self, img_rgba: np.ndarray, bit_depth: int, params: dict, progress_cb=None) -> tuple[np.ndarray, dict]:
        t0 = time.perf_counter()
        self._begin_job()
        try:
            h, w = img_rgba.shape[:2]
            ps_max = 32768.0 if bit_depth == 16 else 255.0
            img_rgb_u8 = np.clip((img_rgba[:, :, :3].astype(np.float32) / ps_max) * 255.0 + 0.5, 0, 255).astype(np.uint8)
            edge_prot = float(params.get("edge", 70))

            with self.lock:
                self._ensure_models_loaded(need_matting=True, need_lama=False, progress_cb=progress_cb)
                fg_raw_1024 = self._predict_fg_raw(img_rgb_u8, progress_cb=progress_cb)
                if progress_cb is not None:
                    progress_cb(76, "Уточнення контуру маски...")
                fg_mask_u8, _ = self._clean_fg_mask(fg_raw_1024, w, h, edge_prot)
                if progress_cb is not None:
                    progress_cb(90, "Передача маски у Photoshop...")

            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            return fg_mask_u8, {"elapsed_ms": elapsed_ms, "gpu": self.gpu_name, "provider": self.provider_name}
        finally:
            self._end_job()

    @staticmethod
    def _outward_transition_ramp(fg_s: np.ndarray, feather_pct: float) -> np.ndarray:
        """
        Smooth S-curve ramp that stays strictly 0.0 on the subject (fg_s > 0.14)
        and glides from 0.0 -> 1.0 outward over `ramp_px` pixels so blur/scuffs never create a halo rim.
        """
        sh, sw = fg_s.shape[:2]
        fg_solid = (fg_s > 0.14).astype(np.uint8)
        d_out = cv2.distanceTransform(1 - fg_solid, cv2.DIST_L2, 5).astype(np.float32)
        ramp_px = max(3.0, (0.004 + (np.clip(feather_pct, 0.0, 100.0) / 100.0) * 0.060) * max(sh, sw))
        t = np.clip(d_out / ramp_px, 0.0, 1.0)
        ramp = t * t * (3.0 - 2.0 * t)
        return np.minimum(ramp, np.clip(1.0 - fg_s * 1.18, 0.0, 1.0))

    # ------------------------------------------------------------------
    # 5c. Fast pixel-format conversions (multi-threaded OpenCV instead of single-threaded numpy).
    #     Every helper is bit-identical to the numpy formula it replaces (checked by tests/run_checks.py).
    # ------------------------------------------------------------------
    _UNIT_LUT_8 = None

    @staticmethod
    def _proxy_grain_gain(scale: float) -> float:
        """
        How much weaker the vinyl grain looks on a copy reduced by `scale` (averaging several pixels into one).
        Used only by the quick preview, so that repaired spots do not look noisier than the vinyl around them.
        """
        return float(np.clip(scale, 0.2, 1.0) ** 0.8)

    @staticmethod
    def _fg_stage_key(edge_prot: float):
        """Stage-cache key of the subject masks (_clean_fg_mask) - shared by process() and start_session()."""
        return (float(edge_prot),)

    @staticmethod
    def _heal_cells(heal_alpha: np.ndarray, cell: int = 128):
        """
        Splits the frame into `cell`-px blocks.
        Returns (cells, bbox):
          cells - [(y0, y1, x0, x1), ...] of every block that contains heal_alpha > 0 (row-major order);
          bbox  - (y0, y1, x0, x1) bounding box of heal_alpha > 0.002, or None when nothing passes.
        """
        h, w = heal_alpha.shape[:2]
        x_edges = np.arange(0, w, cell)
        cells = []
        col_hit = np.zeros(w, dtype=bool)
        row_first = row_last = None
        for y0 in range(0, h, cell):
            y1 = min(h, y0 + cell)
            blk = heal_alpha[y0:y1]
            col_max = cv2.reduce(blk, 0, cv2.REDUCE_MAX).ravel()
            cell_max = np.maximum.reduceat(col_max, x_edges)
            for gx in np.flatnonzero(cell_max > 0.0):
                x0 = int(gx) * cell
                cells.append((y0, y1, x0, min(w, x0 + cell)))
            hit = col_max > 0.002
            if hit.any():
                col_hit |= hit
                rows = np.flatnonzero(cv2.reduce(blk, 1, cv2.REDUCE_MAX).ravel() > 0.002)
                if row_first is None:
                    row_first = y0 + int(rows[0])
                row_last = y0 + int(rows[-1])
        if row_first is None:
            return cells, None
        cols = np.flatnonzero(col_hit)
        return cells, (row_first, row_last + 1, int(cols[0]), int(cols[-1]) + 1)

    @staticmethod
    def _rgb_planes(img: np.ndarray) -> np.ndarray:
        """
        C-contiguous H x W x 3 colour planes of an RGB / RGBA frame.
        For 3-channel input this is the caller's own array (no copy) -> treat the result as READ-ONLY.
        """
        if img.ndim == 3 and img.shape[2] == 4 and img.dtype in (np.uint8, np.uint16, np.float32):
            return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)  # only drops the 4th channel, channel order is kept
        return np.ascontiguousarray(img[:, :, :3])

    @classmethod
    def _to_unit_f32(cls, rgb: np.ndarray, ps_max: float) -> np.ndarray:
        """Source pixels -> NEW float32 array in 0..1  ==  clip(rgb.astype(float32) * (1 / ps_max), 0, 1)."""
        if rgb.dtype == np.uint8 and ps_max == 255.0:
            lut = cls._UNIT_LUT_8
            if lut is None:
                lut = np.arange(256, dtype=np.float32)
                lut *= (1.0 / 255.0)
                np.clip(lut, 0.0, 1.0, out=lut)
                cls._UNIT_LUT_8 = lut
            return cv2.LUT(rgb, lut)
        if rgb.dtype == np.uint16 and ps_max == 32768.0:
            s = 1.0 / 32768.0  # power of two -> exact in float32
            out = cv2.multiply(rgb, (s, s, s, s), dtype=cv2.CV_32F)
            cv2.threshold(out, 1.0, 1.0, cv2.THRESH_TRUNC, dst=out)
            return out
        out = rgb.astype(np.float32)
        out *= (1.0 / ps_max)
        np.clip(out, 0.0, 1.0, out=out)
        return out

    @classmethod
    def _to_analysis_u8(cls, rgb: np.ndarray, ps_max: float) -> np.ndarray:
        """
        8-bit copy used by the detectors  ==  clip(unit_f32 * 255 + 0.5, 0, 255).astype(uint8).
        For 8-bit sources that formula returns the source itself, so `rgb` is returned as is (READ-ONLY!).
        """
        if rgb.dtype == np.uint8 and ps_max == 255.0:
            return rgb
        if rgb.dtype == np.uint16 and ps_max == 32768.0:
            return cv2.convertScaleAbs(rgb, alpha=255.0 / 32768.0)
        return np.clip(cls._to_unit_f32(rgb, ps_max) * 255.0 + 0.5, 0, 255).astype(np.uint8)

    @staticmethod
    def _quantize_unit(arr_f32: np.ndarray, ps_max: float, out_dtype) -> np.ndarray:
        """
        float 0..1 -> integer pixels  ==  clip(round(arr * ps_max), 0, ps_max).astype(out_dtype).
        float32 input is clamped in place (no caller needs it afterwards).
        float64 input (the dress-smoothing alpha is float64 under NumPy 2) keeps the plain NumPy formula:
        OpenCV would round it through float32 first, which flips a pixel by one level now and then.
        """
        if arr_f32.dtype == np.float32:
            cv2.threshold(arr_f32, 0.0, 0.0, cv2.THRESH_TOZERO, dst=arr_f32)
            if out_dtype == np.uint8 and ps_max == 255.0:
                return cv2.convertScaleAbs(arr_f32, alpha=255.0)
            if out_dtype == np.uint16 and ps_max == 32768.0:
                cv2.threshold(arr_f32, 1.0, 1.0, cv2.THRESH_TRUNC, dst=arr_f32)
                return cv2.multiply(arr_f32, (32768.0, 32768.0, 32768.0, 32768.0), dtype=cv2.CV_16U)
        tmp = arr_f32 * ps_max
        np.round(tmp, out=tmp)
        np.clip(tmp, 0, ps_max, out=tmp)
        return tmp.astype(out_dtype)

    @classmethod
    def _pack_rgba(cls, rgb_f32: np.ndarray, alpha_f32: np.ndarray, ps_max: float, bit_depth: int):
        """(float RGB 0..1, float alpha 0..1) -> RGBA at the document bit depth, plus the integer alpha plane."""
        dt = np.uint16 if bit_depth == 16 else np.uint8
        h, w = rgb_f32.shape[:2]
        rgb_i = cls._quantize_unit(rgb_f32, ps_max, dt)
        alpha_i = cls._quantize_unit(alpha_f32, ps_max, dt)
        out_rgba = np.empty((h, w, 4), dtype=dt)
        cv2.mixChannels([rgb_i, alpha_i], [out_rgba], [0, 0, 1, 1, 2, 2, 3, 3])
        return out_rgba, alpha_i

    # ------------------------------------------------------------------
    # 6. Full Pipeline (8-bit or 16-bit Native Float32 Blending + Grain)
    # ------------------------------------------------------------------
    def process(
        self,
        img_rgba: np.ndarray,
        bit_depth: int,
        params: dict,
        selection_alpha: np.ndarray | None = None,
        custom_fg_mask: np.ndarray | None = None,
        custom_heal_mask: np.ndarray | None = None,
        progress_cb=None,
        cached_fg_raw_1024: np.ndarray | None = None,
        out_cache: dict | None = None,
        stage_cache: dict | None = None,
        analysis: dict | None = None,
        analysis_only: bool = False,
        render_scale: float = 1.0,
        proxy_seed: dict | None = None,
    ):
        """
        stage_cache: optional dict owned by an interactive session (same image, same selection, same
        `cached_fg_raw_1024` on every call). Each pipeline stage stores its result there together with the
        parameter values it depends on; on the next call a stage whose inputs did not change is replayed from
        the dict instead of being recomputed. The output is bit-identical to a call without the cache.

        The next four exist for the quick preview of the interactive window (see recompute_session):
        analysis_only: stop after the search (person, stands / smoke / shadows, seam, dust) and return what was found
            as a dict instead of a cleaned frame. Nothing is repaired or drawn.
        analysis: such a dict (its masks resized to this frame). Nothing is searched for; the frame is only repaired
            and toned with the given masks.
        render_scale: < 1 when `img_rgba` is a reduced copy of the real frame; sizes meant in real pixels follow it.
        proxy_seed: {"size": (w, h)} -> receives the frame as it is right after the repair, reduced to that size,
            so a quick preview that changes only the tone starts from the real repair.
        Without them the function behaves exactly as before.
        """
        t0 = time.perf_counter()
        self._begin_job()
        try:
            def _prog(pct: int, txt: str):
                if progress_cb is not None:
                    progress_cb(pct, txt)

            h, w = img_rgba.shape[:2]
            ps_max = 32768.0 if bit_depth == 16 else 255.0

            _prog(12, "Підготовка зображення та профілю...")

            spots_str = float(params.get("spots", 75))
            scuffs_str = float(params.get("scuffs", 65))
            blur_str = float(params.get("blur", 0))
            cyc_str = float(params.get("cycCurve", 0))
            feather_str = float(params.get("feather", 60))
            seam_on = bool(params.get("seamOn", True))
            seam_str = float(params.get("seam", 85))
            edge_prot = float(params.get("edge", 70))
            smoke_on = bool(params.get("smokeOn", True))
            smoke_str = float(params.get("smoke", 80))
            # "smokeAuto": protect smoke only on frames that really have it (the plugin asks for it; see SMOKE_MIN_SHARE)
            smoke_auto = self._smoke_auto(params)
            grain_keep = float(params.get("grain", 90))
            keep_shadow = bool(params.get("shadow", True))
            remove_stands = bool(params.get("removeStands", False))
            master_val = float(params.get("master", 100))
            speed_mode = "fast" if str(params.get("speedMode", "quality")).lower() == "fast" else "quality"
            fast_mode = speed_mode == "fast"
            # "seamJoin": the pieces of one floor line on both sides of the person are judged together
            seam_join = bool(params.get("seamJoin", True))
            # "grainLocal": dust is judged against the noise of the place it lies in (see _detect_spots_mask)
            grain_local = bool(params.get("grainLocal", True))
            # "gearBody": studio gear is told by its body; a shadow edge or a scratch is not gear (_edge_blobs_with_body)
            gear_body = bool(params.get("gearBody", True))
            # "shadowSpots": a dirty spot inside a cast shadow is found too (see SHADOW_SPOT_*)
            shadow_spots = bool(params.get("shadowSpots", True))

            frac_fine = bool(params.get("fracFine", True))
            frac_med = bool(params.get("fracMed", True))
            frac_large = bool(params.get("fracLarge", True))
            dress_smooth_on = bool(params.get("dressSmooth", False))
            dress_strength = float(params.get("dressStrength", 45)) if dress_smooth_on else 0.0
            clean_passes = 2 if int(params.get("cleanPasses", 1)) >= 2 else 1

            # Turbo boost when master intensity slider > 100% (100..200% -> 1.0..2.0x)
            boost = max(1.0, min(2.0, master_val / 100.0))
            spots_eff = min(160.0, spots_str * boost)
            scuffs_eff = min(200.0, scuffs_str * boost)
            seam_eff = min(155.0, seam_str * boost)
            has_any_frac = frac_fine or frac_med or frac_large

            if custom_heal_mask is not None:
                needs_lama_work = bool(np.any(custom_heal_mask > 16))
            else:
                needs_lama_work = has_any_frac and ((spots_eff > 0) or (seam_on and seam_eff > 0) or remove_stands)

            need_bg_maps = (scuffs_eff > 0) or (blur_str > 0) or (cyc_str > 0) or (dress_strength > 0) or (custom_heal_mask is None)

            # ---- Stage cache: every key lists exactly the inputs its stage reads (plus the key of the stage before it) ----
            sc = None
            if (
                stage_cache is not None
                and custom_fg_mask is None
                and custom_heal_mask is None
                and (cached_fg_raw_1024 is not None or analysis is not None)
            ):
                sc_sig = (h, w, int(bit_depth), int(img_rgba.shape[2]), selection_alpha is not None)
                if stage_cache.get("sig", sc_sig) != sc_sig:
                    stage_cache.clear()  # not the frame this cache was filled for
                stage_cache["sig"] = sc_sig
                sc = stage_cache
            reused_stages: list[str] = []

            def _sc_get(name: str, key):
                rec = sc.get(name) if sc is not None else None
                if rec is not None and rec[0] == key:
                    reused_stages.append(name)
                    return rec[1]
                return None

            def _sc_put(name: str, key, value):
                if sc is not None:
                    for arr in (value if isinstance(value, tuple) else ()):
                        if isinstance(arr, np.ndarray):
                            arr.setflags(write=False)  # a cached array must never be edited in place
                    sc[name] = (key, value)

            k_fg = self._fg_stage_key(edge_prot)
            k_maps = (k_fg, smoke_str, smoke_on, smoke_auto, keep_shadow, gear_body)
            # The wall-floor corner and the seam search. With the corner tool on, the line is left to that tool: the
            # seam search skips its strip. With the tool at 0 (or when the selection holds only a part of the line,
            # so the tool leaves it) the seam search may take the line for a joint, as it always could - but only
            # whole: a line repaired in pieces is a dashed, hard-edged remainder, and that is what a dark backdrop
            # gave (see _whole_line_repair_only). "seamJoin" off = the former way, pieces included.
            seam_wanted = seam_on and seam_eff > 0 and frac_large
            corner_skip = bool(cyc_str > 0 and seam_wanted)
            corner_whole = bool(seam_wanted and seam_join)
            corner_wanted = bool(cyc_str > 0 or corner_whole)
            # What gets found does not depend on the speed mode any more (both use the thorough search); the speed mode
            # only chooses HOW the found defects are repaired, so it enters the cache at the "heal" stage.
            k_detect = (
                k_maps, remove_stands, seam_on, (seam_eff if seam_on else 0.0),
                spots_eff, frac_fine, frac_med, frac_large, (seam_join if seam_on else True), corner_skip, grain_local,
                shadow_spots,
            )
            # The two searches inside "detect" are also remembered one by one: moving the dust slider does not look
            # for the seam again, and the other way round.
            k_seam = (k_maps, remove_stands, seam_eff, seam_join, corner_skip)
            k_corner = (k_maps, remove_stands)  # the wall-floor corner of the untouched frame
            k_spots = (k_maps, remove_stands, spots_eff, frac_fine, frac_med, frac_large, grain_local, shadow_spots)
            k_heal = (k_detect, fast_mode, grain_keep)
            # Order of the tone stages: corner -> stains -> blur. The corner goes first: once the wall-floor step is a
            # smooth slope, the stain stage sees no edge there and evens the backdrop across it.
            k_cyc = (k_heal, cyc_str)
            k_scuffs = (k_cyc, scuffs_eff)
            k_blur = (k_scuffs, blur_str, (boost if blur_str > 0 else 0.0), (feather_str if blur_str > 0 else 0.0))

            def corner_of_this_run(line, fg_u8):
                """
                The corner the tools of this run work with. "Clean inside the selection" with only a part of the
                corner selected: bending the line there and leaving it outside would break it at the border of the
                selection. The corner is a matter of the whole frame: then it stays, as with the slider at 0.
                """
                if line is not None and selection_alpha is not None and not self._selection_holds_line(selection_alpha, line, fg_u8):
                    return None
                return line

            if analysis_only and sc is not None:
                r_fg, r_maps, r_det, r_cor = sc.get("fg"), sc.get("maps"), sc.get("detect"), sc.get("corner")
                cor_ok = not corner_wanted or (r_cor is not None and r_cor[0] == k_corner)
                if (r_fg is not None and r_fg[0] == k_fg and r_maps is not None and r_maps[0] == k_maps
                        and r_det is not None and r_det[0] == k_detect and cor_ok):
                    # everything was found already for these settings: no pixel has to be read
                    return {
                        "fg_mask_u8": r_fg[1][0], "core_mask_u8": r_fg[1][1],
                        "stand_protect_s": r_maps[1][0], "stand_remove_s": r_maps[1][1],
                        "smoke_s": r_maps[1][2], "shadow_s": r_maps[1][3], "smoke_info": r_maps[1][4],
                        "heal_mask": r_det[1][0], "seam_px": r_det[1][1], "spot_px": r_det[1][2],
                        "grain_sigma": float(r_det[1][3]), "reused_stages": ["fg", "maps", "detect"],
                        "corner_line": (corner_of_this_run(r_cor[1][0], r_fg[1][1] if remove_stands else r_fg[1][0])
                                        if cyc_str > 0 else None),
                    }

            hit_heal = _sc_get("heal", k_heal) if not analysis_only else None

            # Normalize original image to float32 [0..1] (preserving full 16-bit precision!).
            # img_rgb_u8 may alias the caller's pixels for 8-bit RGB input -> it is never written to below.
            src_rgb = self._rgb_planes(img_rgba)
            orig_rgb_f32 = None if analysis_only else self._to_unit_f32(src_rgb, ps_max)
            img_rgb_u8 = self._to_analysis_u8(src_rgb, ps_max)
            del src_rgb

            fg_mask_u8 = np.zeros((h, w), dtype=np.uint8)
            core_mask_u8 = np.zeros((h, w), dtype=np.uint8)
            stand_protect_s = np.zeros((1, 1), dtype=np.uint8)
            smoke_s = np.zeros((1, 1), dtype=np.uint8)
            shadow_s = np.zeros((1, 1), dtype=np.uint8)
            eff_stand_protect = np.zeros((1, 1), dtype=np.uint8)
            eff_fg_for_spots = np.zeros((h, w), dtype=np.uint8)
            seam_mask = np.zeros((h, w), dtype=np.uint8)
            spot_mask = np.zeros((h, w), dtype=np.uint8)
            grain_sigma = 1.5
            smoke_info = None  # what was seen of smoke (see _compute_protection_maps_small); None = not looked for
            corner_line = None  # the wall-floor corner (_corner_line_of_frame); None = not looked for or not there
            corner_frame = None  # the same before the selection rule (the line as the frame has it)
            dress_src_1024 = None
            dress_tex_1024 = None
            if dress_strength > 0:
                d_sc = min(1.0, 1024.0 / max(h, w))
                dress_src_1024 = cv2.resize(
                    img_rgb_u8,
                    (max(8, int(round(w * d_sc))), max(8, int(round(h * d_sc)))),
                    interpolation=cv2.INTER_AREA,
                )
                dress_tex_1024 = self._fabric_texture_small(img_rgb_u8, max_dim=1024)

            with self.lock:
                self._ensure_models_loaded(
                    need_matting=(need_bg_maps and custom_fg_mask is None and cached_fg_raw_1024 is None and analysis is None),
                    need_lama=(needs_lama_work and not fast_mode and hit_heal is None and not analysis_only),
                    progress_cb=progress_cb,
                )

                fg_raw_1024 = cached_fg_raw_1024
                if analysis is not None:
                    # Found earlier on the real frame (recompute_session, quick preview): nothing is searched for here
                    fg_mask_u8, core_mask_u8 = analysis["fg_mask_u8"], analysis["core_mask_u8"]
                    stand_protect_s, stand_remove_s = analysis["stand_protect_s"], analysis["stand_remove_s"]
                    smoke_s, shadow_s = analysis["smoke_s"], analysis["shadow_s"]
                    smoke_info = analysis.get("smoke_info")
                    corner_line = analysis.get("corner_line")
                    if corner_line is not None and render_scale != 1.0:
                        # found on the real frame; this frame is its reduced copy
                        corner_line = dict(corner_line, row=(corner_line["row"] + 0.5) * render_scale - 0.5,
                                           half=corner_line["half"] * render_scale)
                    eff_stand_protect = np.zeros_like(stand_protect_s) if remove_stands else stand_protect_s
                    eff_fg_for_spots = core_mask_u8 if remove_stands else fg_mask_u8
                    heal_mask = analysis["heal_mask"]
                    seam_px, spot_px = int(analysis["seam_px"]), int(analysis["spot_px"])
                    grain_sigma = float(analysis["grain_sigma"])
                    do_inpaint = needs_lama_work and hit_heal is None and bool(np.any(heal_mask > 0))
                else:
                    if need_bg_maps:
                        if custom_fg_mask is not None:
                            _prog(32, "Використання маски захисту...")
                            fg_mask_u8 = custom_fg_mask.astype(np.uint8)
                            core_mask_u8 = fg_mask_u8
                        else:
                            rec = _sc_get("fg", k_fg)
                            if rec is not None:
                                fg_mask_u8, core_mask_u8 = rec
                            else:
                                if fg_raw_1024 is None:
                                    fg_raw_1024 = self._predict_fg_raw(img_rgb_u8, progress_cb=progress_cb)
                                _prog(35, "Уточнення контуру моделі...")
                                fg_mask_u8, core_mask_u8 = self._clean_fg_mask(fg_raw_1024, w, h, edge_prot)
                                _sc_put("fg", k_fg, (fg_mask_u8, core_mask_u8))

                        rec = _sc_get("maps", k_maps)
                        if rec is not None:
                            stand_protect_s, stand_remove_s, smoke_s, shadow_s, smoke_info = rec
                        else:
                            _prog(40, "Аналіз стійок, диму й тіней...")
                            smoke_info = {}
                            stand_protect_s, stand_remove_s, smoke_s, shadow_s = self._compute_protection_maps_small(
                                img_rgb_u8, fg_mask_u8, core_mask_u8, smoke_str, smoke_on, keep_shadow,
                                smoke_auto=smoke_auto, info=smoke_info, gear_body=gear_body,
                            )
                            smoke_info.update({"on": bool(smoke_on), "auto": bool(smoke_auto)})
                            _sc_put("maps", k_maps, (stand_protect_s, stand_remove_s, smoke_s, shadow_s, smoke_info))
                        eff_stand_protect = np.zeros_like(stand_protect_s) if remove_stands else stand_protect_s
                        eff_fg_for_spots = core_mask_u8 if remove_stands else fg_mask_u8
                        if corner_wanted:
                            rec = _sc_get("corner", k_corner)
                            if rec is not None:
                                (corner_frame,) = rec
                            else:
                                corner_frame = self._corner_line_of_frame(img_rgb_u8, eff_fg_for_spots, eff_stand_protect, smoke_s)
                                _sc_put("corner", k_corner, (corner_frame,))
                            if cyc_str > 0:
                                corner_line = corner_of_this_run(corner_frame, eff_fg_for_spots)
                    else:
                        stand_remove_s = np.zeros((1, 1), dtype=np.uint8)

                    rec = _sc_get("detect", k_detect)
                    if rec is not None:
                        heal_mask, seam_px, spot_px, grain_sigma = rec
                        do_inpaint = bool(np.any(heal_mask > 0)) if hit_heal is None else False
                    else:
                        if custom_heal_mask is not None:
                            _prog(46, "Застосування відредагованої зеленої маски...")
                            heal_mask = (custom_heal_mask > 16).astype(np.uint8)
                            # Estimate grain_sigma quickly from subsampled luma so grain transfer matches studio noise
                            step_g = 4
                            L_sub = cv2.cvtColor(img_rgb_u8[::step_g, ::step_g], cv2.COLOR_RGB2GRAY).astype(np.float32)
                            hp_sub = np.abs(L_sub - cv2.GaussianBlur(L_sub, (5, 5), 0))
                            bg_sub = heal_mask[::step_g, ::step_g] == 0
                            if np.any(bg_sub):
                                grain_sigma = max(0.85, float(np.median(hp_sub[bg_sub])) * 1.4826)
                        else:
                            _prog(46, "Пошук швів, пилу та дефектів...")
                            if seam_wanted:
                                rec_part = _sc_get("seam", k_seam)
                                if rec_part is not None:
                                    (seam_mask,) = rec_part
                                else:
                                    seam_mask = self._detect_vinyl_seam_mask(
                                        img_rgb_u8, eff_fg_for_spots, eff_stand_protect, smoke_s, seam_eff, edge_prot, fast_mode=False,
                                        join=seam_join, skip_line=(corner_line if corner_skip else None),
                                        step_ok_line=(corner_frame if corner_line is None else None),
                                    )
                                    if corner_whole and corner_frame is not None and corner_line is None:
                                        seam_mask = self._whole_line_repair_only(seam_mask, corner_frame, eff_fg_for_spots)
                                    seam_mask[core_mask_u8 > 140] = 0
                                    _sc_put("seam", k_seam, (seam_mask,))

                            if spots_eff > 0 and has_any_frac:
                                rec_part = _sc_get("spots", k_spots)
                                if rec_part is not None:
                                    spot_mask, grain_sigma = rec_part
                                else:
                                    spot_mask, grain_sigma = self._detect_spots_mask(
                                        img_rgb_u8,
                                        eff_fg_for_spots,
                                        eff_stand_protect,
                                        smoke_s,
                                        shadow_s,
                                        spots_eff,
                                        fast_mode=False,
                                        frac_fine=frac_fine,
                                        frac_med=frac_med,
                                        frac_large=frac_large,
                                        local_grain=grain_local,
                                        shadow_spots=shadow_spots,
                                    )
                                    _sc_put("spots", k_spots, (spot_mask, grain_sigma))

                            heal_mask = np.maximum(seam_mask, spot_mask)
                            if remove_stands and has_any_frac:
                                stand_rm_full = (cv2.resize(stand_remove_s, (w, h), interpolation=cv2.INTER_LINEAR) > 80).astype(np.uint8)
                                stand_rm_full[core_mask_u8 > 120] = 0
                                heal_mask = np.maximum(heal_mask, stand_rm_full)

                        # Restrict tiles to selection if active selection was provided
                        if selection_alpha is not None:
                            sel_bin = (selection_alpha > 1).astype(np.uint8)
                            sel_pad = cv2.dilate(sel_bin, np.ones((65, 65), np.uint8))
                            heal_mask = heal_mask * sel_pad

                            sel_area = int(sel_bin.sum())
                            if custom_heal_mask is None and sel_area > 0 and sel_area < int(0.25 * h * w):
                                manual_heal = sel_bin.copy()
                                if not remove_stands:
                                    manual_heal[eff_fg_for_spots > 120] = 0
                                manual_heal = cv2.dilate(manual_heal, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
                                heal_mask = np.maximum(heal_mask, manual_heal)

                        do_inpaint = needs_lama_work and bool(np.any(heal_mask > 0))
                        if not do_inpaint:
                            heal_mask[:] = 0
                        seam_px, spot_px = int(seam_mask.sum()), int(spot_mask.sum())
                        del seam_mask, spot_mask
                        _sc_put("detect", k_detect, (heal_mask, seam_px, spot_px, grain_sigma))

                if analysis_only:
                    return {
                        "fg_mask_u8": fg_mask_u8, "core_mask_u8": core_mask_u8,
                        "stand_protect_s": stand_protect_s, "stand_remove_s": stand_remove_s,
                        "smoke_s": smoke_s, "shadow_s": shadow_s, "smoke_info": smoke_info,
                        "heal_mask": heal_mask, "seam_px": seam_px, "spot_px": spot_px,
                        "grain_sigma": float(grain_sigma), "reused_stages": reused_stages,
                        "corner_line": corner_line,
                    }

                small_specks_healed = 0
                lama_f32 = None
                tiles_run = 0
                if hit_heal is not None:
                    tiles_run, small_specks_healed = hit_heal["tiles_run"], hit_heal["small_specks"]
                    _prog(78, "Підготовка шару...")
                elif not do_inpaint:
                    _prog(78, "Підготовка шару...")
                else:
                    # Sanitize subject/prop colors out of heal source so warm skin/shoes/flowers never bleed yellow halos onto vinyl!
                    heal_src_u8 = img_rgb_u8
                    if custom_heal_mask is None and np.any(eff_fg_for_spots > 22):
                        s_sc = min(1.0, 640.0 / max(h, w))
                        sw_s, sh_s_dim = max(16, int(round(w * s_sc))), max(16, int(round(h * s_sc)))
                        src_s = cv2.resize(img_rgb_u8, (sw_s, sh_s_dim), interpolation=cv2.INTER_AREA).astype(np.float32)
                        fg_bad_s = cv2.resize(eff_fg_for_spots, (sw_s, sh_s_dim), interpolation=cv2.INTER_AREA) > 22
                        hm_s = cv2.resize(heal_mask, (sw_s, sh_s_dim), interpolation=cv2.INTER_NEAREST) > 0
                        bg_valid = (~fg_bad_s) & (~hm_s)
                        if np.any(bg_valid) and np.any(fg_bad_s):
                            w_bg = bg_valid.astype(np.float32)
                            den_bg = cv2.GaussianBlur(w_bg, (0, 0), sigmaX=12.0, sigmaY=12.0) + 1e-4
                            fill_s = cv2.GaussianBlur(src_s * w_bg[:, :, None], (0, 0), sigmaX=12.0, sigmaY=12.0) / den_bg[:, :, None]
                            fg_blend = cv2.GaussianBlur(fg_bad_s.astype(np.float32), (5, 5), 0)[:, :, None]
                            fill_full = cv2.resize(np.clip(fill_s, 0, 255).astype(np.uint8), (w, h), interpolation=cv2.INTER_LINEAR)
                            fg_m_full = (eff_fg_for_spots > 22)
                            heal_src_u8 = img_rgb_u8.copy()
                            heal_src_u8[fg_m_full] = fill_full[fg_m_full]
                    if fast_mode:
                        lama_f32, tiles_run, small_specks_healed = self._run_fast_inpaint(
                            heal_src_u8, heal_mask, progress_cb=progress_cb, size_scale=render_scale
                        )
                        _prog(79, "Відновлення мікрозерна вінілу...")
                    else:
                        lama_f32, tiles_run = self._run_lama_tiles(heal_src_u8, heal_mask, progress_cb=progress_cb)
                        _prog(79, "Відновлення мікрозерна вінілу...")
                    del heal_src_u8

            # ------------------------------------------------------------------
            # 7. Fast High-Pass Grain Transfer + Float32 Lab Scuffs + Blur + Dress Smooth
            # ------------------------------------------------------------------
            del img_rgb_u8
            cleaned_f32 = orig_rgb_f32  # reuse in-place to avoid extra 265MB allocation on 22MP
            final_alpha = np.zeros((h, w), dtype=np.float32)

            if hit_heal is not None:
                # Replay the healed + grained 128px cells stored by an earlier call of this session
                for (cy0, cy1, cx0, cx1), rgb_blk, a_blk in zip(hit_heal["cells"], hit_heal["rgb"], hit_heal["alpha"]):
                    cleaned_f32[cy0:cy1, cx0:cx1] = rgb_blk
                    final_alpha[cy0:cy1, cx0:cx1] = a_blk
            else:
                heal_cells: list = []
                if lama_f32 is not None:
                    k_ha = 11 if fast_mode else 15
                    if render_scale < 1.0:
                        k_ha = max(3, int(round(k_ha * render_scale)) | 1)  # the soft edge is meant in real pixels
                    heal_alpha = cv2.GaussianBlur((heal_mask > 0).astype(np.float32), (k_ha, k_ha), 0)
                    # Only the 128px cells that contain healed pixels are touched: everywhere else heal_alpha is
                    # exactly 0, so the old full-frame blend added 0 there. The noise fields keep the old layout
                    # (same generator, same draw order), therefore every pixel gets the same grain as before.
                    heal_cells, heal_bbox = self._heal_cells(heal_alpha)
                    if heal_bbox is not None:
                        y0h, y1h, x0h, x1h = heal_bbox
                        rng = np.random.default_rng(42)
                        g_ratio = grain_keep / 100.0
                        noise_std = (grain_sigma / 255.0) * 0.55 * g_ratio if (grain_keep > 0 and (tiles_run > 0 or small_specks_healed > 0)) else 0.0
                        if render_scale < 1.0:
                            noise_std *= self._proxy_grain_gain(render_scale)  # grain of a reduced copy is weaker
                        add_grain = noise_std > 1e-5
                        lama_is_u8 = lama_f32.dtype == np.uint8
                        bw_h = x1h - x0h
                        for ys_b in range(y0h, y1h, 1024):
                            ye_b = min(y1h, ys_b + 1024)
                            bh_h = ye_b - ys_b
                            n_full = n_fine = None
                            if add_grain:
                                n_small = rng.normal(0.0, noise_std, (max(1, bh_h // 2), max(1, bw_h // 2), 1)).astype(np.float32)
                                n_full = cv2.resize(n_small, (bw_h, bh_h), interpolation=cv2.INTER_LINEAR)
                                n_fine = rng.normal(0.0, noise_std * 0.50, (bh_h, bw_h, 1)).astype(np.float32)
                                del n_small
                            for cy0, cy1, cx0, cx1 in heal_cells:
                                yy0, yy1 = max(cy0, ys_b), min(cy1, ye_b)
                                xx0, xx1 = max(cx0, x0h), min(cx1, x1h)
                                if yy0 >= yy1 or xx0 >= xx1:
                                    continue
                                ha_crop = heal_alpha[yy0:yy1, xx0:xx1, None]
                                dst = cleaned_f32[yy0:yy1, xx0:xx1]
                                lama_crop = lama_f32[yy0:yy1, xx0:xx1]
                                if lama_is_u8:
                                    lama_crop = lama_crop.astype(np.float32) * (1.0 / 255.0)
                                if add_grain:
                                    ny0, nx0 = yy0 - ys_b, xx0 - x0h
                                    ny1, nx1 = yy1 - ys_b, xx1 - x0h
                                    luma_ref = dst.mean(axis=2, keepdims=True)
                                    dark_g_scale = np.clip(luma_ref / 0.14, 0.12, 1.0)
                                    lama_crop = np.clip(
                                        lama_crop + (n_full[ny0:ny1, nx0:nx1, None] + n_fine[ny0:ny1, nx0:nx1]) * dark_g_scale * ha_crop,
                                        0.0,
                                        1.0,
                                    )
                                dst += (lama_crop - dst) * ha_crop
                            del n_full, n_fine
                    del lama_f32
                    # Layer alpha of the healed zones (final_alpha is still all zeros here, so max(0, a) == a)
                    for cy0, cy1, cx0, cx1 in heal_cells:
                        a_blk = heal_alpha[cy0:cy1, cx0:cx1]
                        if custom_heal_mask is None:
                            protect_h = np.clip((eff_fg_for_spots[cy0:cy1, cx0:cx1].astype(np.float32) - 40.0) / 170.0, 0.0, 1.0)
                            a_blk = a_blk * (1.0 - protect_h)
                        final_alpha[cy0:cy1, cx0:cx1] = a_blk
                    del heal_alpha
                if sc is not None:
                    heal_bytes = sum((cy1 - cy0) * (cx1 - cx0) for cy0, cy1, cx0, cx1 in heal_cells) * 16
                    if heal_bytes <= self.STAGE_CACHE_HEAL_MAX_BYTES:
                        sc["heal"] = (k_heal, {
                            "cells": heal_cells,
                            "rgb": [cleaned_f32[cy0:cy1, cx0:cx1].copy() for cy0, cy1, cx0, cx1 in heal_cells],
                            "alpha": [final_alpha[cy0:cy1, cx0:cx1].copy() for cy0, cy1, cx0, cx1 in heal_cells],
                            "tiles_run": tiles_run,
                            "small_specks": small_specks_healed,
                        })
                    else:
                        sc.pop("heal", None)  # almost the whole frame was healed: recomputing is cheaper than the RAM

            if proxy_seed is not None:
                # The frame right after the repair, at the size of the quick-preview copy (a tone-only change of the
                # preview then starts from this real repair instead of a rough one). Always stored as a "fast" record:
                # the quick preview draws in the fast geometry whatever the speed mode of the session is.
                seed_size = tuple(int(v) for v in proxy_seed["size"])
                proxy_seed["heal"] = {
                    "key": (k_detect, True, grain_keep),
                    "rgb": cv2.resize(cleaned_f32, seed_size, interpolation=cv2.INTER_AREA),
                    "alpha": cv2.resize(final_alpha, seed_size, interpolation=cv2.INTER_AREA),
                    "tiles_run": tiles_run,
                    "small_specks": small_specks_healed,
                }

            # Cyclorama Corner-Rounding (infinity-cove smoothing of sharp wall-to-floor studio angle)
            if cyc_str > 0 and corner_line is not None:
                _prog(81, "Заокруглення кута під циклораму...")
                cleaned_f32, cyc_alpha = self._apply_cyclorama_curve(
                    cleaned_f32,
                    eff_fg_for_spots,
                    eff_stand_protect,
                    smoke_s,
                    shadow_s,
                    cyc_str,
                    feather_str,
                    fast_mode=fast_mode,
                    line=corner_line,
                )
                np.maximum(final_alpha, cyc_alpha, out=final_alpha)
                del cyc_alpha

            # Stains, smears and shoe marks: found and evened on a reduced copy, the correction is added to the frame
            # (see _smooth_backdrop_stains). The low-res correction is what the stage cache keeps.
            scuff_rec = _sc_get("scuffs", k_scuffs) if scuffs_eff > 0 else None
            if scuff_rec is None and scuffs_eff > 0:
                _prog(83, "Вирівнювання розводів та слідів...")
                sc_max = 900.0 if fast_mode else 1400.0
                scale_sc = min(0.5, sc_max / max(h, w))
                sh, sw = max(8, int(round(h * scale_sc))), max(8, int(round(w * scale_sc)))
                small_f32 = cv2.resize(cleaned_f32, (sw, sh), interpolation=cv2.INTER_AREA).astype(np.float32)
                np.clip(small_f32, 0.0, 1.0, out=small_f32)
                fg_half = cv2.resize(eff_fg_for_spots, (sw, sh), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
                st_half = cv2.resize(eff_stand_protect, (sw, sh), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0
                sm_half = cv2.resize(smoke_s, (sw, sh), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0
                scuff_rec = self._smooth_backdrop_stains(small_f32, fg_half, st_half, sm_half, scuffs_eff / 100.0)
                del small_f32, fg_half, st_half, sm_half
                _sc_put("scuffs", k_scuffs, scuff_rec)
            if scuff_rec is not None:
                diff_s, scuff_s = scuff_rec
                diff_full = cv2.resize(diff_s, (w, h), interpolation=cv2.INTER_LINEAR)
                cleaned_f32 += diff_full
                del diff_full
                np.clip(cleaned_f32, 0.0, 1.0, out=cleaned_f32)
                scuff_alpha = cv2.resize(scuff_s, (w, h), interpolation=cv2.INTER_LINEAR)
                np.maximum(final_alpha, scuff_alpha, out=final_alpha)
                del scuff_alpha

            # Normalized Shadow-Safe Masked Background Blur (smooths vinyl wrinkles with zero dark-backdrop wash or halo!)
            blur_rec = _sc_get("blur", k_blur) if blur_str > 0 else None
            if blur_rec is not None:
                blur_diff_s, blur_s = blur_rec
                blur_diff_full = cv2.resize(blur_diff_s, (w, h), interpolation=cv2.INTER_LINEAR)
                cleaned_f32 += blur_diff_full
                del blur_diff_full
                np.clip(cleaned_f32, 0.0, 1.0, out=cleaned_f32)
                blur_alpha = cv2.resize(blur_s, (w, h), interpolation=cv2.INTER_LINEAR)
                np.maximum(final_alpha, blur_alpha, out=final_alpha)
                del blur_alpha
            elif blur_str > 0:
                _prog(86, "Розмиття фону й плавний перехід...")
                scale_b = min(1.0, (950.0 if fast_mode else 1400.0) / max(h, w))
                bw, bh = max(8, int(round(w * scale_b))), max(8, int(round(h * scale_b)))
                small_b = cv2.resize(cleaned_f32, (bw, bh), interpolation=cv2.INTER_AREA).astype(np.float32)
                fg_b = cv2.resize(eff_fg_for_spots, (bw, bh), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
                st_b = cv2.resize(eff_stand_protect, (bw, bh), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0
                sh_b = cv2.resize(shadow_s, (bw, bh), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0
                sh_b_smooth = cv2.GaussianBlur(sh_b, (25, 25), 0)

                ramp_b = self._outward_transition_ramp(fg_b, feather_str)
                env_b = cv2.GaussianBlur((1.0 - 0.85 * st_b) * (1.0 - np.clip(sh_b_smooth * 1.35, 0.0, 1.0)), (21, 21), 0)
                bg_w = np.clip(ramp_b * env_b, 0.0, 1.0)
                bg_src_w = (fg_b < 0.08).astype(np.float32) * (1.0 - 0.88 * st_b) * (1.0 - np.clip(sh_b_smooth * 1.35, 0.0, 1.0))

                blur_eff = min(140.0, blur_str * (1.0 + 0.35 * max(0.0, boost - 1.0)))
                sigma_b = 1.5 + (blur_eff / 100.0) * (max(bw, bh) * 0.024)
                num_b = cv2.GaussianBlur(small_b * bg_src_w[..., None], (0, 0), sigmaX=sigma_b, sigmaY=sigma_b)
                den_b = cv2.GaussianBlur(bg_src_w, (0, 0), sigmaX=sigma_b, sigmaY=sigma_b) + 1e-5
                blurred_s = np.clip(num_b / den_b[..., None], 0.0, 1.0)

                # Guard dark low-key areas against bright spotlight/floor bleed when blurring
                luma_b = 0.299 * small_b[:, :, 0] + 0.587 * small_b[:, :, 1] + 0.114 * small_b[:, :, 2]
                luma_blur = 0.299 * blurred_s[:, :, 0] + 0.587 * blurred_s[:, :, 1] + 0.114 * blurred_s[:, :, 2]
                dark_keep_b = np.clip((luma_b - 0.04) / 0.14, 0.0, 1.0)
                excess_up = np.maximum(0.0, luma_blur - luma_b - 0.015) * (1.0 - dark_keep_b)
                if np.any(excess_up > 1e-4):
                    scale_dn = np.clip((luma_blur - excess_up) / (luma_blur + 1e-5), 0.0, 1.0)[:, :, None]
                    blurred_s = blurred_s * scale_dn

                blur_mix = min(1.0, (blur_eff / 100.0) * 1.10)
                blur_s = np.clip(bg_w * blur_mix, 0.0, 1.0)
                blur_diff_s = (blurred_s - small_b) * blur_s[..., None]
                blur_diff_full = cv2.resize(blur_diff_s, (w, h), interpolation=cv2.INTER_LINEAR)
                cleaned_f32 += blur_diff_full
                del blur_diff_full
                np.clip(cleaned_f32, 0.0, 1.0, out=cleaned_f32)

                blur_s *= np.clip(1.0 - np.clip((fg_b - 0.15) / 0.66, 0.0, 1.0), 0.0, 1.0)
                _sc_put("blur", k_blur, (blur_diff_s, blur_s))
                blur_alpha = cv2.resize(blur_s, (w, h), interpolation=cv2.INTER_LINEAR)
                np.maximum(final_alpha, blur_alpha, out=final_alpha)
                del blur_alpha

            # Optional 2nd Pass Clean (when user enables cleanPasses=2 for extra-dirty studio vinyl)
            if clean_passes >= 2 and custom_heal_mask is None and has_any_frac and spots_eff > 0:
                _prog(87, "2-й прохід додаткового очищення...")
                pass2_u8 = np.clip(cleaned_f32 * 255.0 + 0.5, 0, 255).astype(np.uint8)
                spot2_mask, _ = self._detect_spots_mask(
                    pass2_u8,
                    eff_fg_for_spots,
                    eff_stand_protect,
                    smoke_s,
                    shadow_s,
                    min(150.0, spots_eff * 0.88),
                    fast_mode=True,
                    frac_fine=frac_fine,
                    frac_med=frac_med,
                    frac_large=frac_large,
                    local_grain=grain_local,
                    shadow_spots=shadow_spots,
                )
                spot2_mask[heal_mask > 0] = 0
                if np.any(spot2_mask > 0):
                    p2_src = pass2_u8
                    if np.any(eff_fg_for_spots > 22):
                        p2_src = pass2_u8.copy()
                        p2_s = min(1.0, 640.0 / max(h, w))
                        sw2, sh2 = max(16, int(round(w * p2_s))), max(16, int(round(h * p2_s)))
                        s2_img = cv2.resize(pass2_u8, (sw2, sh2), interpolation=cv2.INTER_AREA).astype(np.float32)
                        fg2_b = cv2.resize(eff_fg_for_spots, (sw2, sh2), interpolation=cv2.INTER_AREA) > 22
                        w2 = (~fg2_b).astype(np.float32)
                        den2 = cv2.GaussianBlur(w2, (0, 0), sigmaX=12.0, sigmaY=12.0) + 1e-4
                        f2 = cv2.resize(np.clip(cv2.GaussianBlur(s2_img * w2[:, :, None], (0, 0), sigmaX=12.0, sigmaY=12.0) / den2[:, :, None], 0, 255).astype(np.uint8), (w, h), interpolation=cv2.INTER_LINEAR)
                        fg2_m = eff_fg_for_spots > 22
                        p2_src[fg2_m] = f2[fg2_m]
                    lama2_f32, _, _ = self._run_fast_inpaint(p2_src, spot2_mask, progress_cb=None)
                    if lama2_f32 is not None:
                        if lama2_f32.dtype == np.uint8:
                            lama2_f32 = lama2_f32.astype(np.float32) * (1.0 / 255.0)
                        else:
                            lama2_f32 = lama2_f32.astype(np.float32)
                        a2 = cv2.GaussianBlur((spot2_mask > 0).astype(np.float32), (9, 9), 0)
                        protect2 = np.clip((eff_fg_for_spots.astype(np.float32) - 22.0) / 140.0, 0.0, 1.0)
                        a2 *= (1.0 - protect2)
                        cleaned_f32 += (lama2_f32 - cleaned_f32) * a2[:, :, None]
                        np.clip(cleaned_f32, 0.0, 1.0, out=cleaned_f32)
                        np.maximum(final_alpha, a2, out=final_alpha)
                        del a2, lama2_f32
                    del p2_src
                    if out_cache is not None:
                        out_cache["heal_mask_pass2"] = spot2_mask  # repaired by the second pass (see _session_proxies)
                del pass2_u8, spot2_mask

            # Optional Dress / Clothing Soft Wrinkle & Specular Smoothing (Skin/Hair/Edge Safe)
            dress_s_cached = None
            if dress_strength > 0 and dress_src_1024 is not None:
                _prog(89, "Делікатне вирівнювання одягу...")
                dress_s_cached = self._build_dress_mask_small(dress_src_1024, core_mask_u8, max_dim=1024, tex_rms=dress_tex_1024)
                del dress_src_1024, dress_tex_1024
                cleaned_f32, dress_alpha = self._smooth_dress_fabric(
                    cleaned_f32, dress_s_cached, dress_strength, fast_mode=fast_mode
                )
                np.maximum(final_alpha, dress_alpha, out=final_alpha)
                del dress_alpha
            elif dress_src_1024 is not None:
                del dress_src_1024

            if out_cache is not None:
                out_cache["fg_raw_1024"] = fg_raw_1024
                out_cache["core_mask_u8"] = core_mask_u8
                out_cache["fg_mask_u8"] = fg_mask_u8
                out_cache["heal_mask_full"] = heal_mask
                out_cache["seam_px"] = seam_px
                out_cache["spot_px"] = spot_px
                out_cache["grain_sigma"] = float(grain_sigma)
                out_cache["smoke_info"] = smoke_info
                if dress_s_cached is not None:
                    out_cache["dress_s"] = dress_s_cached

            _prog(92, "Передача результату у Photoshop...")
            if selection_alpha is not None:
                np.clip(final_alpha, 0.0, 1.0, out=final_alpha)
                sel_f = np.clip(selection_alpha.astype(np.float32) / (255.0 if selection_alpha.dtype == np.uint8 else ps_max), 0.0, 1.0)
                final_alpha = final_alpha * sel_f
            # (without a selection the 0..1 clamp happens inside _pack_rgba)

            # Pack back to exact source bit depth (0..255 uint8 or 0..32768 uint16)
            out_rgba, alpha_int = self._pack_rgba(cleaned_f32, final_alpha, ps_max, bit_depth)
            del cleaned_f32, final_alpha

            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            changed_px = int(np.count_nonzero(alpha_int > int(0.05 * ps_max)))
            del alpha_int
            stats = {
                "elapsed_ms": elapsed_ms,
                "tiles_run": tiles_run,
                "small_specks": small_specks_healed,
                "speed_mode": speed_mode,
                "seam_px": seam_px,
                "spot_px": spot_px,
                "dress_smooth": dress_smooth_on,
                "changed_px": changed_px,
                "reused_stages": reused_stages,
                "gpu": self.gpu_name,
                "provider": self.provider_name,
            }
            if smoke_info is not None:
                stats["smoke"] = dict(smoke_info)
            if cyc_str > 0:
                # where the wall-floor corner was found (share of the frame height), None = this frame has none
                stats["corner_row"] = None if corner_line is None else round(float((corner_line["row"] + 0.5) / max(h, 1)), 4)
            return out_rgba, stats
        finally:
            self._end_job()

    # ------------------------------------------------------------------
    # 7. Interactive Retouch4me-Style Session API (Cache + Instant Edits)
    # ------------------------------------------------------------------
    @staticmethod
    def _encode_b64_jpg(bgr_u8: np.ndarray, quality: int = 90) -> str:
        ok, buf = cv2.imencode(".jpg", bgr_u8, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
        return base64.b64encode(buf.tobytes()).decode("ascii") if ok else ""

    # JPEG quality of the pictures the big window shows. At 90 a smooth dark backdrop comes out as flat 8x8 blocks
    # one grey level apart: on a black or dark grey backdrop that is one step in fifteen, and the window showed
    # "patches with hard edges" that are in neither the photo nor the layer. At 100 the fine noise that hides those
    # steps survives. A frame counts as dark when PREVIEW_DARK_SHARE of it is darker than PREVIEW_DARK_LEVEL (0..255);
    # light frames keep 90 (the steps cannot be seen there, and the pictures stay five times smaller).
    PREVIEW_JPEG_QUALITY = 90
    PREVIEW_JPEG_QUALITY_DARK = 100
    PREVIEW_DARK_LEVEL = 56
    PREVIEW_DARK_SHARE = 0.20

    @classmethod
    def _preview_quality(cls, orig_small_bgr: np.ndarray, asked=None) -> int:
        """The JPEG quality for the previews of this frame; `asked` ("previewQuality" of the request) overrules it."""
        if asked is not None:
            try:
                return int(np.clip(int(asked), 50, 100))
            except (TypeError, ValueError):
                pass
        gray = cv2.cvtColor(orig_small_bgr, cv2.COLOR_BGR2GRAY)
        dark = int(np.count_nonzero(gray < cls.PREVIEW_DARK_LEVEL))
        return cls.PREVIEW_JPEG_QUALITY_DARK if dark >= cls.PREVIEW_DARK_SHARE * gray.size else cls.PREVIEW_JPEG_QUALITY

    @staticmethod
    def _encode_green_mask_png(mask_u8: np.ndarray) -> str:
        mh, mw = mask_u8.shape[:2]
        rgba = np.zeros((mh, mw, 4), dtype=np.uint8)
        # OpenCV imencode PNG expects BGRA channel order
        rgba[:, :, 0] = 56    # B
        rgba[:, :, 1] = 255   # G
        rgba[:, :, 2] = 0     # R
        rgba[:, :, 3] = mask_u8
        ok, buf = cv2.imencode(".png", rgba, [int(cv2.IMWRITE_PNG_COMPRESSION), 1])
        return base64.b64encode(buf.tobytes()).decode("ascii") if ok else ""

    # Share of green in the "Маска" view: the zones that were found and repaired (or painted) / the rest of the layer
    OVERLAY_GREEN = 0.72
    OVERLAY_GREEN_PALE = 0.20

    @staticmethod
    def _encode_overlay_jpg(comp_bgr: np.ndarray, mask_u8: np.ndarray, quality: int = 90,
                            marked_u8: np.ndarray | None = None) -> str:
        """
        Pre-composited Retouch4me red-protected + bright-green-mask JPEG preview.
        Guaranteed 100% opaque JPEG — immune to UXP canvas/alpha compositor quirks!
        mask_u8: the layer (everything that will change); outside it the photo is tinted red (protected).
        marked_u8 (optional, a part of the layer): only this part is bright green, the rest of the layer is pale
        green - the backdrop that is evened as a whole, see _compute_marked_mask_small.
        """
        m = mask_u8.astype(np.float32)[:, :, None] * (1.0 / 255.0)
        base_f = comp_bgr.astype(np.float32)
        red_a = 0.36 * (1.0 - m)
        tinted = base_f * (1.0 - red_a) + np.array([18.0, 18.0, 178.0], dtype=np.float32) * red_a
        if marked_u8 is None:
            grn_a = CleanVinylEngine.OVERLAY_GREEN * m
        else:
            mk = marked_u8.astype(np.float32)[:, :, None] * (1.0 / 255.0)
            grn_a = CleanVinylEngine.OVERLAY_GREEN * mk + CleanVinylEngine.OVERLAY_GREEN_PALE * np.maximum(m - mk, 0.0)
        overlay_bgr = np.clip(
            tinted * (1.0 - grn_a) + np.array([52.0, 255.0, 16.0], dtype=np.float32) * grn_a,
            0,
            255,
        ).astype(np.uint8)
        ok, buf = cv2.imencode(".jpg", overlay_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
        return base64.b64encode(buf.tobytes()).decode("ascii") if ok else ""

    def _compute_effective_mask_small(self, sess: dict) -> np.ndarray:
        auto_m = sess["auto_mask_small_u8"].astype(np.float32)
        paint_m = sess["user_paint_u8"].astype(np.float32)
        erase_m = sess["user_erase_u8"].astype(np.float32) / 255.0
        eff = np.maximum(auto_m, paint_m) * (1.0 - erase_m)
        eff_u8 = np.clip(np.round(eff), 0, 255).astype(np.uint8)
        if sess.get("inverted"):
            eff_u8 = 255 - eff_u8
        return eff_u8

    def _compute_marked_mask_small(self, sess: dict, eff_u8: np.ndarray) -> np.ndarray:
        """
        The part of the layer mask (`eff_u8`, see above) that is shown in bright green and counted as "found":
        what the search repaired plus what the brush added, minus the eraser. The rest of the layer - the backdrop
        that the stain / blur / corner stages evened - is shown in pale green.
        Without those stages, and for an inverted mask, the whole layer is "marked": `eff_u8` itself is returned.
        """
        repaired = sess.get("repair_mask_small_u8")
        if repaired is None or repaired is sess["auto_mask_small_u8"] or sess.get("inverted"):
            return eff_u8
        marked = np.maximum(repaired, sess["user_paint_u8"]).astype(np.float32)
        marked *= 1.0 - sess["user_erase_u8"].astype(np.float32) / 255.0
        return np.minimum(np.clip(np.round(marked), 0, 255).astype(np.uint8), eff_u8)

    def _render_session_previews(
        self,
        sess: dict,
        dress_smooth: bool,
        dress_strength: float,
        need_comp: bool = True,
        need_mask: bool = True,
    ) -> dict:
        eff_mask = self._compute_effective_mask_small(sess)
        marked_mask = self._compute_marked_mask_small(sess, eff_mask)
        # How much of the frame is bright green (found and repaired, or painted): lets the plugin say what a preset
        # changed. "layer_share": how much of the frame the layer changes at all (with the stain / blur / corner
        # stages that is the whole backdrop).
        out: dict = {
            "mask_share": round(float(np.count_nonzero(marked_mask > 127)) / max(1, marked_mask.size), 5),
            "layer_share": round(float(np.count_nonzero(eff_mask > 127)) / max(1, eff_mask.size), 5),
        }

        if need_mask:
            # Only on explicit request: the plugin shows the pre-composited overlay JPEG, not this PNG.
            out["mask_png_b64"] = self._encode_green_mask_png(eff_mask)

        if need_comp:
            orig_s = sess["orig_small_bgr"]
            base_clean_s = sess["clean_paint_small_bgr"]

            # Apply dress smooth cleanly on small proxy (~12 ms) when enabled, respecting user eraser!
            if dress_smooth and dress_strength > 0 and sess.get("dress_s") is not None:
                clean_rgb_f32 = cv2.cvtColor(base_clean_s, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
                ds = sess["dress_s"].copy()
                # If user erased over parts of the dress, protect those from dress smoothing too
                erase_s = cv2.resize(sess["user_erase_u8"], (ds.shape[1], ds.shape[0]), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
                ds *= (1.0 - erase_s)
                dressed_f32, dress_alpha_s = self._smooth_dress_fabric(clean_rgb_f32, ds, float(dress_strength), fast_mode=True)
                dressed_bgr = cv2.cvtColor(np.clip(dressed_f32 * 255.0 + 0.5, 0, 255).astype(np.uint8), cv2.COLOR_RGB2BGR)
                # Blend: background areas use eff_mask; dress areas use dress_alpha_s
                m_bg = eff_mask.astype(np.float32) / 255.0
                m_comb = np.maximum(m_bg, np.clip(dress_alpha_s * 1.15, 0.0, 1.0))[:, :, None]
                comp_bgr = np.clip(
                    orig_s.astype(np.float32) * (1.0 - m_comb) + dressed_bgr.astype(np.float32) * m_comb,
                    0, 255,
                ).astype(np.uint8)
            else:
                m_f = (eff_mask.astype(np.float32) / 255.0)[:, :, None]
                comp_bgr = np.clip(
                    orig_s.astype(np.float32) * (1.0 - m_f) + base_clean_s.astype(np.float32) * m_f,
                    0, 255,
                ).astype(np.uint8)

            quality = int(sess.get("preview_q", self.PREVIEW_JPEG_QUALITY))
            out["comp_jpg_b64"] = self._encode_b64_jpg(comp_bgr, quality=quality)
            out["overlay_jpg_b64"] = self._encode_overlay_jpg(
                comp_bgr, eff_mask, quality=quality, marked_u8=(None if marked_mask is eff_mask else marked_mask)
            )
        return out

    # ---- brush / eraser history ("undo") --------------------------------------------------------------------------
    EDIT_HISTORY_MAX = 40                      # steps that can be taken back
    EDIT_HISTORY_MAX_BYTES = 96 * 1024 * 1024  # ...as long as they fit into this much memory

    @staticmethod
    def _pack_plane(arr: np.ndarray):
        """A mostly empty mask in a compact form: None, or (y0, y1, x0, x1, copy of the part that is not zero)."""
        rows = np.flatnonzero(arr.any(axis=1))
        if rows.size == 0:
            return None
        cols = np.flatnonzero(arr.any(axis=0))
        y0, y1, x0, x1 = int(rows[0]), int(rows[-1]) + 1, int(cols[0]), int(cols[-1]) + 1
        return y0, y1, x0, x1, arr[y0:y1, x0:x1].copy()

    @staticmethod
    def _pack_diff(cur: np.ndarray, base: np.ndarray):
        """Where `cur` differs from `base`: None, or (y0, y1, x0, x1, copy of that part of `cur`)."""
        diff = cv2.absdiff(cur, base)
        if diff.ndim == 3:
            diff = diff.max(axis=2)
        rows = np.flatnonzero(diff.any(axis=1))
        if rows.size == 0:
            return None
        cols = np.flatnonzero(diff.any(axis=0))
        y0, y1, x0, x1 = int(rows[0]), int(rows[-1]) + 1, int(cols[0]), int(cols[-1]) + 1
        return y0, y1, x0, x1, cur[y0:y1, x0:x1].copy()

    def _edit_snapshot(self, sess: dict) -> dict:
        """
        Everything the brush, the eraser, "fill", "clear" and "invert" change, as it is right now (see _edit_restore).
        The two edit layers are stored by their non-empty part, the preview by what the brush redrew in it.
        """
        return {
            "paint": self._pack_plane(sess["user_paint_u8"]),
            "erase": self._pack_plane(sess["user_erase_u8"]),
            "inverted": bool(sess.get("inverted")),
            "detached": bool(sess.get("mask_detached")),
            # (these two arrays are replaced, never edited in place - keeping the reference is enough)
            "auto": sess["auto_mask_small_u8"],
            "repair": sess.get("repair_mask_small_u8"),
            "gen": int(sess.get("base_gen", 0)),
            "preview": self._pack_diff(sess["clean_paint_small_bgr"], sess["clean_base_small_bgr"]),
        }

    @staticmethod
    def _snapshot_bytes(snap: dict) -> int:
        return sum(rec[4].nbytes for rec in (snap["paint"], snap["erase"], snap["preview"]) if rec is not None)

    def _paint_preview_from_base(self, sess: dict) -> np.ndarray:
        """
        The cleaned preview with the brush strokes redrawn on it: what the window shows inside painted zones until
        Apply repairs them for real. Built from the clean preview and the paint layer alone.
        """
        out = sess["clean_base_small_bgr"].copy()
        if np.any(sess["user_paint_u8"] > 16):
            paint_bin = (sess["user_paint_u8"] > 64).astype(np.uint8)
            inpainted = cv2.inpaint(out, paint_bin, inpaintRadius=7, flags=cv2.INPAINT_TELEA)
            p_alpha = cv2.GaussianBlur(paint_bin.astype(np.float32), (5, 5), 0)[:, :, None]
            out = np.clip(out.astype(np.float32) * (1.0 - p_alpha) + inpainted.astype(np.float32) * p_alpha, 0, 255).astype(np.uint8)
        return out

    def _edit_restore(self, sess: dict, snap: dict) -> None:
        """
        Puts the edit layers back the way `snap` holds them.
        The frame was not recomputed since: the mask and the preview come back exactly as they were.
        The sliders were moved since: the strokes are put back onto the frame as it is computed now.
        """
        for key, name in (("paint", "user_paint_u8"), ("erase", "user_erase_u8")):
            arr = sess[name]
            arr[:] = 0
            if snap[key] is not None:
                y0, y1, x0, x1, part = snap[key]
                arr[y0:y1, x0:x1] = part
        sess["inverted"] = bool(snap["inverted"])
        if snap["gen"] == int(sess.get("base_gen", 0)):
            sess["auto_mask_small_u8"] = snap["auto"]
            sess["repair_mask_small_u8"] = snap["repair"]
            sess["mask_detached"] = bool(snap["detached"])
            preview = sess["clean_base_small_bgr"].copy()
            if snap["preview"] is not None:
                y0, y1, x0, x1, part = snap["preview"]
                preview[y0:y1, x0:x1] = part
            sess["clean_paint_small_bgr"] = preview
        else:
            sess["clean_paint_small_bgr"] = self._paint_preview_from_base(sess)

    def _edit_history_push(self, sess: dict) -> None:
        """Remembers the state before an edit; whatever was taken back before can no longer be redone."""
        hist = sess.setdefault("history", {"undo": [], "redo": []})
        hist["redo"].clear()
        undo = hist["undo"]
        undo.append(self._edit_snapshot(sess))
        total = sum(self._snapshot_bytes(s) for s in undo)
        while len(undo) > 1 and (len(undo) > self.EDIT_HISTORY_MAX or total > self.EDIT_HISTORY_MAX_BYTES):
            total -= self._snapshot_bytes(undo.pop(0))

    def _edit_history_step(self, sess: dict, back: bool) -> bool:
        """One step back (undo) or forward again (redo). False when there is nothing to step to."""
        hist = sess.setdefault("history", {"undo": [], "redo": []})
        src, dst = (hist["undo"], hist["redo"]) if back else (hist["redo"], hist["undo"])
        if not src:
            return False
        snap = src.pop()
        dst.append(self._edit_snapshot(sess))
        self._edit_restore(sess, snap)
        return True

    @staticmethod
    def _edit_history_counts(sess: dict) -> dict:
        hist = sess.get("history") or {}
        return {"undo": len(hist.get("undo", ())), "redo": len(hist.get("redo", ()))}

    def _analyze_auto_fractions(self, img_rgb_u8: np.ndarray, fg_mask_u8: np.ndarray, core_mask_u8: np.ndarray, edge_prot: float) -> dict:
        """
        Quick scan (<60ms) to automatically detect which defect fractions (Fine / Medium / Large+Seam)
        are genuinely present on this studio backdrop.
        """
        h, w = img_rgb_u8.shape[:2]
        scale = min(1.0, 960.0 / max(h, w))
        sw, sh = max(8, int(round(w * scale))), max(8, int(round(h * scale)))
        small = cv2.resize(img_rgb_u8, (sw, sh), interpolation=cv2.INTER_AREA)
        fg_s = cv2.resize(fg_mask_u8, (sw, sh), interpolation=cv2.INTER_AREA)
        core_s = cv2.resize(core_mask_u8, (sw, sh), interpolation=cv2.INTER_AREA)
        bg = (fg_s < 64) & (core_s < 64)
        if not np.any(bg):
            return {"fracFine": True, "fracMed": True, "fracLarge": False}

        lab = cv2.cvtColor(small, cv2.COLOR_RGB2LAB).astype(np.float32)
        L = lab[:, :, 0]
        # Fine/medium residual dust energy outside subject
        hp = np.abs(L - cv2.GaussianBlur(L, (15, 15), 0))
        hp[~bg] = 0.0
        fine_px = int((hp > 2.2).sum())
        med_blobs = cv2.morphologyEx(((hp > 2.6) & bg).astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        med_px = int(med_blobs.sum())

        # Check lower 55% of image for horizontal vinyl seam / wide floor scuffs
        y0_floor = int(sh * 0.42)
        gy = np.abs(cv2.Sobel(cv2.GaussianBlur(L, (5, 5), 0), cv2.CV_32F, 0, 1, ksize=3))
        gy[~bg] = 0.0
        row_energy = gy[y0_floor:, :].mean(axis=1)
        has_seam = bool(row_energy.size > 0 and np.max(row_energy) > 1.35)
        large_blobs = cv2.morphologyEx(((hp > 3.0) & bg).astype(np.uint8), cv2.MORPH_OPEN, np.ones((11, 11), np.uint8))
        has_large = has_seam or (int(large_blobs.sum()) > 160)

        return {
            "fracFine": bool(fine_px > 25),
            "fracMed": bool(med_px > 45),
            "fracLarge": bool(has_large),
        }

    def close_session(self, session_id: str | None = None) -> bool:
        with self._state_lock:
            if self._active_session is None:
                return False
            if session_id and self._active_session.get("id") != session_id:
                return False
            self._active_session = None
        gc.collect()
        self._schedule_idle_unload()
        return True

    def _session_or_raise(self, session_id: str, msg: str = "Сесія застаріла.") -> dict:
        sess = self._active_session
        if not sess or sess["id"] != session_id:
            raise ValueError(msg)
        return sess

    def _auto_fractions_cached(self, fr_cache: dict, stage_cache: dict, img_rgba: np.ndarray, bit_depth: int,
                               fg_raw_1024: np.ndarray, edge_prot: float) -> dict:
        """
        Automatic Fine / Medium / Large choice. It only depends on the photo and on the Edge slider, so the
        answer is remembered per Edge value instead of being re-analysed on every recompute.
        """
        hit = fr_cache.get(edge_prot)
        if hit is None:
            h, w = img_rgba.shape[:2]
            fg_key = self._fg_stage_key(edge_prot)
            rec = stage_cache.get("fg")
            if rec is not None and rec[0] == fg_key:
                fg_m, core_m = rec[1]
            else:
                fg_m, core_m = self._clean_fg_mask(fg_raw_1024, w, h, edge_prot)
                fg_m.setflags(write=False)
                core_m.setflags(write=False)
                stage_cache["fg"] = (fg_key, (fg_m, core_m))  # process() needs exactly these masks right after
            orig_rgb_u8 = self._to_analysis_u8(self._rgb_planes(img_rgba), 32768.0 if bit_depth == 16 else 255.0)
            hit = self._analyze_auto_fractions(orig_rgb_u8, fg_m, core_m, edge_prot)
            if not (hit["fracFine"] or hit["fracMed"] or hit["fracLarge"]):
                hit["fracFine"] = True
            fr_cache[edge_prot] = hit
        return dict(hit)

    @staticmethod
    def _repair_mask_small(auto_mask_small: np.ndarray, heal_s: np.ndarray | None, tone: bool) -> np.ndarray:
        """
        The zones the search found and repaired (dust, seam, gear), as a part of the layer mask.
        Without the tone stages the layer consists of exactly these zones: the very same array is returned.
        With them (stains, blur, corner) the layer also covers the evened backdrop; the repaired zones are then
        shown brighter, counted for "mask_share", and a brush stroke outside them is repaired at Apply.
        """
        if not tone:
            return auto_mask_small
        if heal_s is None:
            return np.zeros_like(auto_mask_small)
        return np.minimum(heal_s, auto_mask_small)

    def _session_proxies(self, cleaned_rgba: np.ndarray, heal_full: np.ndarray | None, pw: int, ph: int, ps_max: float,
                         tone: bool = False, heal_pass2: np.ndarray | None = None):
        """<=1080px proxies of the cleaned frame: (BGR preview, layer mask, repaired zones - see _repair_mask_small)."""
        clean_small_u8 = self._to_analysis_u8(
            cv2.resize(self._rgb_planes(cleaned_rgba), (pw, ph), interpolation=cv2.INTER_AREA), ps_max
        )
        clean_small_bgr = cv2.cvtColor(clean_small_u8, cv2.COLOR_RGB2BGR)

        # Green Action Mask for preview from healed spots/seams + visible background alpha
        alpha_small = cv2.resize(cv2.extractChannel(cleaned_rgba, 3), (pw, ph), interpolation=cv2.INTER_AREA)
        alpha_u8_s = self._to_analysis_u8(alpha_small, ps_max)
        heal_s = None
        if heal_full is not None and np.any(heal_full > 0):
            heal_s = cv2.resize((heal_full > 0).astype(np.uint8) * 255, (pw, ph), interpolation=cv2.INTER_AREA)
            auto_mask_small = np.maximum(heal_s, alpha_u8_s)
        else:
            auto_mask_small = alpha_u8_s
        if tone and heal_pass2 is not None and np.any(heal_pass2 > 0):
            pass2_s = cv2.resize((heal_pass2 > 0).astype(np.uint8) * 255, (pw, ph), interpolation=cv2.INTER_AREA)
            heal_s = pass2_s if heal_s is None else np.maximum(heal_s, pass2_s)
        return clean_small_bgr, auto_mask_small, self._repair_mask_small(auto_mask_small, heal_s, tone)

    # ---- quick preview: the reduced copy of the frame and what belongs to it -------------------------------------
    def _make_session_proxy(self, img_rgba: np.ndarray, selection_alpha) -> dict | None:
        """Reduced copy of the frame for the quick preview, or None when this session always recomputes in full."""
        h, w = img_rgba.shape[:2]
        if max(h, w) < self.PREVIEW_PROXY_MIN_DIM:
            return None  # a small frame is recomputed in full about as fast
        scale = self.PREVIEW_PROXY_DIM / float(max(h, w))
        qw, qh = max(16, int(round(w * scale))), max(16, int(round(h * scale)))
        img = cv2.resize(self._rgb_planes(img_rgba), (qw, qh), interpolation=cv2.INTER_AREA)
        img.setflags(write=False)
        sel = None
        if selection_alpha is not None:
            sel = cv2.resize(selection_alpha, (qw, qh), interpolation=cv2.INTER_AREA)
            sel.setflags(write=False)
        return {"scale": scale, "w": qw, "h": qh, "img": img, "sel": sel, "cache": {}, "masks": {}}

    @staticmethod
    def _seed_session_proxy(proxy: dict | None, seed: dict | None) -> None:
        """Hands the real repair (reduced by process(), see `proxy_seed`) to the quick preview as its own heal stage."""
        rec = seed.get("heal") if (proxy is not None and seed is not None) else None
        if rec is None:
            return
        for arr in (rec["rgb"], rec["alpha"]):
            arr.setflags(write=False)
        proxy["cache"]["heal"] = (rec["key"], {
            "cells": [(0, proxy["h"], 0, proxy["w"])],
            "rgb": [rec["rgb"]],
            "alpha": [rec["alpha"]],
            "tiles_run": rec["tiles_run"],
            "small_specks": rec["small_specks"],
        })

    @classmethod
    def _smoke_auto(cls, p: dict) -> bool:
        """
        True when smoke is protected only on frames that really have it ("smokeAuto", sent by the plugin). Not so
        with the protection off, and not from SMOKE_ALWAYS_FROM up on the slider (then smoke is taken on trust).
        """
        return (bool(p.get("smokeOn", True)) and bool(p.get("smokeAuto", False))
                and float(p.get("smoke", 80)) < cls.SMOKE_ALWAYS_FROM)

    @staticmethod
    def _tone_stages_on(p: dict) -> bool:
        """
        True when a stage that works on the whole backdrop takes part (stains, blur, corner). The layer then covers
        the backdrop, not only the repaired zones - see _session_proxies.
        """
        return float(p.get("scuffs", 65)) > 0 or float(p.get("blur", 0)) > 0 or float(p.get("cycCurve", 0)) > 0

    @staticmethod
    def _clean_signature(p: dict) -> tuple:
        """
        Every setting the base clean reads, in the form process() reads it. Two parameter sets with the same
        signature give the same cleaned frame; clothing (layered live) and unknown keys are not part of it.
        """
        fl = lambda key, default: float(p.get(key, default))  # noqa: E731
        return (
            fl("spots", 75), fl("scuffs", 65), fl("blur", 0), fl("cycCurve", 0), fl("feather", 60),
            bool(p.get("seamOn", True)), fl("seam", 85), fl("edge", 70),
            bool(p.get("smokeOn", True)), fl("smoke", 80), fl("grain", 90),
            CleanVinylEngine._smoke_auto(p), bool(p.get("seamJoin", True)), bool(p.get("grainLocal", True)),
            bool(p.get("gearBody", True)), bool(p.get("shadowSpots", True)),
            bool(p.get("shadow", True)), bool(p.get("removeStands", False)),
            max(100.0, fl("master", 100)),
            "fast" if str(p.get("speedMode", "quality")).lower() == "fast" else "quality",
            bool(p.get("fracFine", True)), bool(p.get("fracMed", True)), bool(p.get("fracLarge", True)),
            2 if int(p.get("cleanPasses", 1)) >= 2 else 1,
        )

    def _adopt_session_params(self, sess: dict, params: dict) -> bool:
        """
        Apply came with the settings that are on the sliders right now. When they are not the ones the real frame
        was computed for, the frame is marked as outdated (Apply then computes it once). Returns True in that case.
        """
        p = dict(params or {})
        if p.get("autoFractions", False):
            auto_fracs = self._auto_fractions_cached(
                sess.setdefault("auto_fracs_by_edge", {}), sess.setdefault("stage_cache", {}), sess["img_rgba_orig"],
                sess["bit_depth"], sess["fg_raw_1024"], float(p.get("edge", 70)),
            )
            p["fracFine"] = auto_fracs["fracFine"]
            p["fracMed"] = auto_fracs["fracMed"]
            p["fracLarge"] = auto_fracs["fracLarge"]
        changed = self._clean_signature(p) != self._clean_signature(sess["params"])
        sess["params"] = p
        if changed:
            sess["base_stale"] = True
        return changed

    @staticmethod
    def _session_clean_params(p: dict) -> dict:
        """Session parameters -> parameters of the base clean (clothing is layered live, Turbo is baked at 100%+)."""
        clean_params = dict(p)
        clean_params["dressSmooth"] = False
        clean_params["master"] = max(100.0, float(p.get("master", 100)))  # bake 100%+; Blend slider handles 0..100 live
        return clean_params

    def _quick_preview_possible(self, sess: dict, clean_params: dict) -> bool:
        if sess.get("proxy") is None:
            return False
        # The second pass searches the already cleaned frame once more - that needs the real pixels.
        return int(clean_params.get("cleanPasses", 1)) < 2

    def _quick_preview(self, sess: dict, clean_params: dict, progress_cb=None):
        """
        The preview for new slider values without recomputing the real frame.
          1. The search (person, stands / smoke / shadows, seam, dust) runs on the REAL frame, exactly as for the
             final result, and only the parts whose sliders moved - so the green mask is the true one.
          2. The repair and the tone are drawn on the reduced copy with those masks.
        Returns (what was found, cleaned reduced copy as RGBA, stats).
        """
        px = sess["proxy"]
        bit_depth = sess["bit_depth"]
        found = self.process(
            sess["img_rgba_orig"], bit_depth, clean_params,
            selection_alpha=sess.get("selection_alpha"),  # the search is limited by the selection, as in the full way
            progress_cb=progress_cb, cached_fg_raw_1024=sess["fg_raw_1024"],
            stage_cache=sess.setdefault("stage_cache", {}), analysis_only=True,
        )
        qw, qh = px["w"], px["h"]
        memo = px["masks"]

        def reduced(name: str, full: np.ndarray, binary: bool = False) -> np.ndarray:
            hit = memo.get(name)
            if hit is not None and hit[0] is full:  # the same array as last time -> the same reduced copy
                return hit[1]
            if binary:
                # a defect keeps at least one pixel of the copy, however small it is on the real frame
                out = (cv2.resize(full * np.uint8(255), (qw, qh), interpolation=cv2.INTER_AREA) > 24).astype(np.uint8)
            else:
                out = cv2.resize(full, (qw, qh), interpolation=cv2.INTER_AREA)
            out.setflags(write=False)
            memo[name] = (full, out)
            return out

        small = dict(found)
        small["fg_mask_u8"] = reduced("fg", found["fg_mask_u8"])
        small["core_mask_u8"] = reduced("core", found["core_mask_u8"])
        small["heal_mask"] = reduced("heal", found["heal_mask"], binary=True)
        draw_params = dict(clean_params)
        draw_params["speedMode"] = "fast"  # the copy is always drawn the fast way; the real mode is used for the real frame
        cleaned_small, stats = self.process(
            px["img"], bit_depth, draw_params, selection_alpha=px.get("sel"),
            progress_cb=progress_cb, stage_cache=px["cache"], analysis=small, render_scale=px["scale"],
        )
        stats["speed_mode"] = "fast" if str(clean_params.get("speedMode", "quality")).lower() == "fast" else "quality"
        stats["changed_px"] = int(round(stats["changed_px"] / (px["scale"] * px["scale"])))
        stats["reused_stages"] = list(found.get("reused_stages", [])) + ["preview:" + s for s in stats.get("reused_stages", [])]
        return found, cleaned_small, stats

    def _session_proxies_quick(self, sess: dict, cleaned_small_rgba: np.ndarray, heal_full: np.ndarray, ps_max: float,
                               tone: bool = False):
        """
        The same proxies as _session_proxies (BGR preview, layer mask, repaired zones), made from the cleaned reduced
        copy of the quick preview.
        Only what the clean CHANGED is taken from the reduced copy and added to the exact small original, so every
        untouched area (the person above all) is pixel for pixel what the full way shows.
        """
        px = sess["proxy"]
        pw, ph = sess["preview_w"], sess["preview_h"]
        delta = cv2.subtract(self._rgb_planes(cleaned_small_rgba), px["img"], dtype=cv2.CV_32F)
        delta = cv2.resize(delta, (pw, ph), interpolation=cv2.INTER_AREA)
        if ps_max != 255.0:
            delta *= (255.0 / ps_max)
        clean = cv2.add(sess["orig_small_bgr"], cv2.cvtColor(delta, cv2.COLOR_RGB2BGR), dtype=cv2.CV_32F)
        clean_small_bgr = np.clip(np.rint(clean), 0, 255).astype(np.uint8)

        alpha_small = cv2.resize(cv2.extractChannel(cleaned_small_rgba, 3), (pw, ph), interpolation=cv2.INTER_AREA)
        auto_mask_small = self._to_analysis_u8(alpha_small, ps_max)
        memo = px["masks"]
        hit = memo.get("heal_preview")
        if hit is None or hit[0] is not heal_full:
            heal_s = None
            if np.any(heal_full > 0):
                # from the real-size search result, exactly as in the full way
                heal_s = cv2.resize((heal_full > 0).astype(np.uint8) * 255, (pw, ph), interpolation=cv2.INTER_AREA)
                heal_s.setflags(write=False)
            hit = memo["heal_preview"] = (heal_full, heal_s)
        if hit[1] is not None:
            auto_mask_small = np.maximum(hit[1], auto_mask_small)
        return clean_small_bgr, auto_mask_small, self._repair_mask_small(auto_mask_small, hit[1], tone)

    def _refresh_stale_base(self, sess: dict, progress_cb=None) -> None:
        """
        The preview was last updated the quick way, so the real frame still belongs to older slider values.
        Compute it now, once, with the values the preview shows. Everything the search found is re-used.
        The brush / eraser edits are not touched.
        """
        bit_depth = sess["bit_depth"]
        ps_max = 32768.0 if bit_depth == 16 else 255.0
        px = sess.get("proxy")
        seed = {"size": (px["w"], px["h"])} if px is not None else None
        out_cache: dict = {}
        cleaned_rgba, _ = self.process(
            sess["img_rgba_orig"],
            bit_depth,
            self._session_clean_params(sess["params"]),
            selection_alpha=sess.get("selection_alpha"),
            progress_cb=progress_cb,
            cached_fg_raw_1024=sess["fg_raw_1024"],
            out_cache=out_cache,
            stage_cache=sess.setdefault("stage_cache", {}),
            proxy_seed=seed,
        )
        self._seed_session_proxy(px, seed)
        sess["cleaned_base_rgba"] = cleaned_rgba
        sess["core_mask_u8"] = out_cache["core_mask_u8"]
        if not sess.get("mask_detached"):
            # (after "invert + brush" the mask on screen is the user's own drawing - it stays as it is)
            _, sess["auto_mask_small_u8"], sess["repair_mask_small_u8"] = self._session_proxies(
                cleaned_rgba, out_cache.get("heal_mask_full"), sess["preview_w"], sess["preview_h"], ps_max,
                tone=self._tone_stages_on(sess["params"]), heal_pass2=out_cache.get("heal_mask_pass2"),
            )
            sess["base_gen"] = int(sess.get("base_gen", 0)) + 1
        sess["base_stale"] = False

    def start_session(
        self,
        img_rgba: np.ndarray,
        bit_depth: int,
        params: dict,
        selection_alpha: np.ndarray | None = None,
        progress_cb=None,
        scene_presets: dict | None = None,
    ) -> dict:
        """
        scene_presets (optional): parameters by kind of frame - {"dark": {...}, "close": {...}, "medium": {...},
        "wide": {...}, "default": {...}}. The frame is looked at first (see _scene_info) and the set that suits it
        is used INSTEAD of `params`, before anything is cleaned - the window opens with the right preset at once.
        The answer tells what was seen and which set was used ("scene").
        """
        t0 = time.perf_counter()
        self._begin_job()
        try:
            with self._session_lock:
                self._active_session = None
                gc.collect()

                h, w = img_rgba.shape[:2]
                ps_max = 32768.0 if bit_depth == 16 else 255.0
                p = dict(params or {})

                if progress_cb is not None:
                    progress_cb(12, "Завантаження AI-моделей...")

                # Own copy first: the session (and its stage cache) must not depend on the HTTP request buffer
                img_rgba = img_rgba.copy()
                img_rgba.setflags(write=False)
                sel_own = selection_alpha.copy() if selection_alpha is not None else None
                orig_rgb_u8 = self._to_analysis_u8(self._rgb_planes(img_rgba), ps_max)  # read-only use below

                # Quick initial subject detection & automatic fraction selection
                with self.lock:
                    self._ensure_models_loaded(need_matting=True, need_lama=False, progress_cb=progress_cb)
                    fg_raw_1024 = self._predict_fg_raw(orig_rgb_u8, progress_cb=progress_cb, fast_mode=(str(p.get("speedMode", "fast")).lower() == "fast"))

                    # What kind of frame is it? With scene_presets the set made for this kind replaces `params`.
                    scene = self._scene_info(fg_raw_1024, orig_rgb_u8, w, h)
                    scene["applied"] = None
                    if isinstance(scene_presets, dict):
                        # A dark backdrop has its own sets by framing ("dark_close", "dark_medium", "dark_wide"); the
                        # general dark set stands in for a missing one, then the set of the framing.
                        keys = ("dark_" + scene["framing"], "dark") if scene["dark"] else ()
                        for key in keys + (scene["framing"], "default"):
                            if isinstance(scene_presets.get(key), dict):
                                p = dict(scene_presets[key])
                                scene["applied"] = key
                                break

                    edge_prot = float(p.get("edge", 70))
                    fg_mask_u8, core_mask_u8 = self._clean_fg_mask(fg_raw_1024, w, h, edge_prot)
                fg_mask_u8.setflags(write=False)
                core_mask_u8.setflags(write=False)

                # Everything process() computes for this frame is remembered here and re-used by recompute_session
                stage_cache: dict = {"fg": (self._fg_stage_key(edge_prot), (fg_mask_u8, core_mask_u8))}
                fr_cache: dict = {}

                if p.get("autoFractions", True):
                    if progress_cb is not None:
                        progress_cb(30, "Автопідбір фракцій дефектів...")
                    auto_fracs = self._auto_fractions_cached(fr_cache, stage_cache, img_rgba, bit_depth, fg_raw_1024, edge_prot)
                    p["fracFine"] = auto_fracs["fracFine"]
                    p["fracMed"] = auto_fracs["fracMed"]
                    p["fracLarge"] = auto_fracs["fracLarge"]
                else:
                    auto_fracs = {
                        "fracFine": bool(p.get("fracFine", True)),
                        "fracMed": bool(p.get("fracMed", True)),
                        "fracLarge": bool(p.get("fracLarge", True)),
                    }

                # Run full base clean WITHOUT dress smooth (dress smooth is layered dynamically!)
                clean_params = self._session_clean_params(p)

                # Reduced copy for the quick preview of later slider moves (None for small frames / selections)
                proxy = self._make_session_proxy(img_rgba, sel_own)
                seed = {"size": (proxy["w"], proxy["h"])} if proxy is not None else None

                out_cache: dict = {}
                cleaned_rgba, stats = self.process(
                    img_rgba,
                    bit_depth,
                    clean_params,
                    selection_alpha=sel_own,
                    progress_cb=progress_cb,
                    cached_fg_raw_1024=fg_raw_1024,
                    out_cache=out_cache,
                    stage_cache=stage_cache,
                    proxy_seed=seed,
                )
                self._seed_session_proxy(proxy, seed)

                # Build proxy previews (<=1080px)
                prev_scale = min(1.0, 1080.0 / max(h, w))
                pw = max(16, int(round(w * prev_scale)))
                ph = max(16, int(round(h * prev_scale)))

                orig_small_bgr = cv2.cvtColor(cv2.resize(orig_rgb_u8, (pw, ph), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2BGR)
                clean_small_bgr, auto_mask_small, repair_mask_small = self._session_proxies(
                    cleaned_rgba, out_cache.get("heal_mask_full"), pw, ph, ps_max,
                    tone=self._tone_stages_on(clean_params), heal_pass2=out_cache.get("heal_mask_pass2"),
                )

                # Cache dress mask once at 1024px so toggling dress icon inside window takes ~12 ms!
                d_sc = min(1.0, 1024.0 / max(h, w))
                dress_src_1024 = cv2.resize(orig_rgb_u8, (max(8, int(round(w * d_sc))), max(8, int(round(h * d_sc)))), interpolation=cv2.INTER_AREA)
                dress_s = self._build_dress_mask_small(
                    dress_src_1024, out_cache["core_mask_u8"], max_dim=1024,
                    tex_rms=self._fabric_texture_small(orig_rgb_u8, max_dim=1024),
                )
                del orig_rgb_u8, dress_src_1024

                sess_id = uuid.uuid4().hex[:12]
                sess = {
                    "id": sess_id,
                    "width": w,
                    "height": h,
                    "bit_depth": bit_depth,
                    "preview_w": pw,
                    "preview_h": ph,
                    "img_rgba_orig": img_rgba,
                    "cleaned_base_rgba": cleaned_rgba,
                    "selection_alpha": sel_own,
                    "fg_raw_1024": fg_raw_1024,
                    "core_mask_u8": out_cache["core_mask_u8"],
                    "dress_s": dress_s,
                    "orig_small_bgr": orig_small_bgr,
                    "clean_base_small_bgr": clean_small_bgr,
                    "clean_paint_small_bgr": clean_small_bgr.copy(),
                    "auto_mask_small_u8": auto_mask_small,      # the layer: everything the clean changes
                    "repair_mask_small_u8": repair_mask_small,  # ...and the part of it that was found and repaired
                    "user_paint_u8": np.zeros((ph, pw), dtype=np.uint8),
                    "user_erase_u8": np.zeros((ph, pw), dtype=np.uint8),
                    "inverted": False,
                    "params": p,
                    "stage_cache": stage_cache,
                    "auto_fracs_by_edge": fr_cache,
                    "proxy": proxy,
                    "base_stale": False,     # True: the preview is ahead of `cleaned_base_rgba` (quick preview)
                    "mask_detached": False,  # True: the mask on screen was flattened by "invert + brush"
                    "base_gen": 0,           # goes up every time the frame is computed anew (see _edit_restore)
                    "history": {"undo": [], "redo": []},  # brush / eraser steps that can be taken back
                    "preview_q": self._preview_quality(orig_small_bgr, p.get("previewQuality")),
                }
                self._active_session = sess

                dress_on = bool(p.get("dressSmooth", False))
                dress_str = float(p.get("dressStrength", 45))
                previews = self._render_session_previews(sess, dress_on, dress_str, need_comp=True, need_mask=False)
                orig_jpg_b64 = self._encode_b64_jpg(orig_small_bgr, quality=sess["preview_q"])

                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                stats["elapsed_ms"] = elapsed_ms
                scene["smoke"] = stats.get("smoke")  # was smoke seen, and is it being protected (see "smokeAuto")
                return {
                    "ok": True,
                    "session_id": sess_id,
                    "width": w,
                    "height": h,
                    "preview_w": pw,
                    "preview_h": ph,
                    "auto_fractions": auto_fracs,
                    "orig_jpg_b64": orig_jpg_b64,
                    "comp_jpg_b64": previews["comp_jpg_b64"],
                    "overlay_jpg_b64": previews["overlay_jpg_b64"],
                    "stats": stats,
                    "scene": scene,
                    "smoke": stats.get("smoke"),
                    "mask_share": previews["mask_share"],
                    "layer_share": previews["layer_share"],
                }
        finally:
            self._end_job()

    def recompute_session(self, session_id: str, params: dict, preserve_edits: bool = True, progress_cb=None,
                          quick: bool = False) -> dict:
        """
        New slider values for the open window.
        quick=False: the real frame is recomputed right away (only the stages whose sliders moved).
        quick=True:  only the preview is updated (see _quick_preview); the real frame is computed once, when Apply
                     needs it. Falls back to the full way by itself where the quick one cannot be used (small frame,
                     selection, 2 passes). The answer says which way was taken ("quick").
        """
        stale_msg = "Сесія застаріла. Закрийте вікно й запустіть «Очистити фон» ще раз."
        self._session_or_raise(session_id, stale_msg)

        t0 = time.perf_counter()
        self._begin_job()
        try:
            with self._session_lock:
                sess = self._session_or_raise(session_id, stale_msg)
                p = dict(params or {})
                w, h = sess["width"], sess["height"]
                pw, ph = sess["preview_w"], sess["preview_h"]
                bit_depth = sess["bit_depth"]
                ps_max = 32768.0 if bit_depth == 16 else 255.0
                stage_cache = sess.setdefault("stage_cache", {})

                if p.get("autoFractions", False):
                    auto_fracs = self._auto_fractions_cached(
                        sess.setdefault("auto_fracs_by_edge", {}), stage_cache, sess["img_rgba_orig"], bit_depth,
                        sess["fg_raw_1024"], float(p.get("edge", 70)),
                    )
                    p["fracFine"] = auto_fracs["fracFine"]
                    p["fracMed"] = auto_fracs["fracMed"]
                    p["fracLarge"] = auto_fracs["fracLarge"]

                clean_params = self._session_clean_params(p)

                took_quick = bool(quick) and self._quick_preview_possible(sess, clean_params)
                if took_quick:
                    found, cleaned_small, stats = self._quick_preview(sess, clean_params, progress_cb)
                    clean_small_bgr, auto_mask_small, repair_mask_small = self._session_proxies_quick(
                        sess, cleaned_small, found["heal_mask"], ps_max, tone=self._tone_stages_on(clean_params),
                    )
                    del cleaned_small
                    sess["core_mask_u8"] = found["core_mask_u8"]
                    sess["base_stale"] = True  # `cleaned_base_rgba` is behind the preview until Apply asks for it
                else:
                    px = sess.get("proxy")
                    seed = {"size": (px["w"], px["h"])} if px is not None else None
                    out_cache: dict = {}
                    cleaned_rgba, stats = self.process(
                        sess["img_rgba_orig"],
                        bit_depth,
                        clean_params,
                        selection_alpha=sess.get("selection_alpha"),
                        progress_cb=progress_cb,
                        cached_fg_raw_1024=sess["fg_raw_1024"],
                        out_cache=out_cache,
                        stage_cache=stage_cache,
                        proxy_seed=seed,
                    )
                    self._seed_session_proxy(px, seed)

                    clean_small_bgr, auto_mask_small, repair_mask_small = self._session_proxies(
                        cleaned_rgba, out_cache.get("heal_mask_full"), pw, ph, ps_max,
                        tone=self._tone_stages_on(clean_params), heal_pass2=out_cache.get("heal_mask_pass2"),
                    )

                    sess["cleaned_base_rgba"] = cleaned_rgba
                    sess["core_mask_u8"] = out_cache["core_mask_u8"]
                    sess["base_stale"] = False
                sess["mask_detached"] = False  # the automatic mask is back on screen
                sess["clean_base_small_bgr"] = clean_small_bgr
                sess["auto_mask_small_u8"] = auto_mask_small
                sess["repair_mask_small_u8"] = repair_mask_small
                sess["params"] = p
                sess["base_gen"] = int(sess.get("base_gen", 0)) + 1  # the steps taken before belong to the former frame
                if "previewQuality" in p:
                    sess["preview_q"] = self._preview_quality(sess["orig_small_bgr"], p.get("previewQuality"))

                if not preserve_edits:
                    sess["user_paint_u8"][:] = 0
                    sess["user_erase_u8"][:] = 0
                    sess["inverted"] = False
                    sess["history"] = {"undo": [], "redo": []}  # the edits were dropped on purpose
                sess["clean_paint_small_bgr"] = self._paint_preview_from_base(sess)

                dress_on = bool(p.get("dressSmooth", False))
                dress_str = float(p.get("dressStrength", 45))
                previews = self._render_session_previews(sess, dress_on, dress_str, need_comp=True, need_mask=False)
                stats["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)

                return {
                    "ok": True,
                    "session_id": session_id,
                    "auto_fractions": {
                        "fracFine": bool(p.get("fracFine", True)),
                        "fracMed": bool(p.get("fracMed", True)),
                        "fracLarge": bool(p.get("fracLarge", True)),
                    },
                    "comp_jpg_b64": previews["comp_jpg_b64"],
                    "overlay_jpg_b64": previews["overlay_jpg_b64"],
                    "stats": stats,
                    "quick": took_quick,
                    "smoke": stats.get("smoke"),
                    "mask_share": previews["mask_share"],
                    "layer_share": previews["layer_share"],
                    "history": self._edit_history_counts(sess),
                }
        finally:
            self._end_job()

    def edit_session_mask(
        self,
        session_id: str,
        op: str,
        points: list | None = None,
        radius_px: float = 24.0,
        erase: bool = True,
        dress_smooth: bool = False,
        dress_strength: float = 45.0,
    ) -> dict:
        self._session_or_raise(session_id)

        self._begin_job()
        try:
            with self._session_lock:
                sess = self._session_or_raise(session_id)
                pw, ph = sess["preview_w"], sess["preview_h"]
                paint_u8 = sess["user_paint_u8"]
                erase_u8 = sess["user_erase_u8"]

                # "undo" / "redo": one step of the brush, the eraser, fill / clear / invert back, or forward again.
                # Every other edit first remembers the state it is about to change.
                stepped = None
                if op in ("undo", "redo"):
                    stepped = self._edit_history_step(sess, back=(op == "undo"))
                elif op in ("fill", "clear", "invert", "reset_auto") or (op == "stroke" and points):
                    self._edit_history_push(sess)

                if op == "fill":
                    paint_u8[:] = 255
                    erase_u8[:] = 0
                    sess["inverted"] = False
                elif op == "clear":
                    erase_u8[:] = 255
                    paint_u8[:] = 0
                    sess["inverted"] = False
                elif op == "invert":
                    sess["inverted"] = not bool(sess.get("inverted", False))
                elif op == "reset_auto":
                    paint_u8[:] = 0
                    erase_u8[:] = 0
                    sess["inverted"] = False
                    sess["clean_paint_small_bgr"] = sess["clean_base_small_bgr"].copy()
                elif op == "stroke" and points:
                    pts = []
                    for pt in points:
                        px = int(round(float(pt["x"]) * pw)) if float(pt.get("norm", False)) else int(round(float(pt["x"])))
                        py = int(round(float(pt["y"]) * ph)) if float(pt.get("norm", False)) else int(round(float(pt["y"])))
                        pts.append((max(0, min(pw - 1, px)), max(0, min(ph - 1, py))))
                    r = max(2, int(round(float(radius_px))))
                    stroke_mask = np.zeros((ph, pw), dtype=np.uint8)
                    if len(pts) == 1:
                        cv2.circle(stroke_mask, pts[0], r, 255, -1, lineType=cv2.LINE_AA)
                    else:
                        for i in range(len(pts) - 1):
                            cv2.line(stroke_mask, pts[i], pts[i + 1], 255, thickness=max(2, r * 2), lineType=cv2.LINE_AA)
                        cv2.circle(stroke_mask, pts[-1], r, 255, -1, lineType=cv2.LINE_AA)

                    blur_k = max(3, (r // 5) | 1)
                    stroke_soft = cv2.GaussianBlur(stroke_mask, (blur_k, blur_k), 0)

                    eff_is_erase = bool(erase)
                    if sess.get("inverted"):
                        flat_eff = self._compute_effective_mask_small(sess)
                        sess["inverted"] = False
                        sess["auto_mask_small_u8"] = flat_eff
                        sess["repair_mask_small_u8"] = flat_eff
                        sess["mask_detached"] = True  # from here on the mask is the user's drawing, not the search result
                        paint_u8[:] = 0
                        erase_u8[:] = 0

                    if eff_is_erase:
                        np.maximum(erase_u8, stroke_soft, out=erase_u8)
                        paint_u8[:] = np.clip(paint_u8.astype(np.int16) - stroke_soft.astype(np.int16), 0, 255).astype(np.uint8)
                    else:
                        np.maximum(paint_u8, stroke_soft, out=paint_u8)
                        erase_u8[:] = np.clip(erase_u8.astype(np.int16) - stroke_soft.astype(np.int16), 0, 255).astype(np.uint8)

                        xs = [p[0] for p in pts]
                        ys = [p[1] for p in pts]
                        pad = max(24, r + 16)
                        x0, x1 = max(0, min(xs) - pad), min(pw, max(xs) + pad + 1)
                        y0, y1 = max(0, min(ys) - pad), min(ph, max(ys) + pad + 1)
                        crop_mask = (stroke_mask[y0:y1, x0:x1] > 128).astype(np.uint8)
                        if np.any(crop_mask):
                            crop_src = sess["clean_paint_small_bgr"][y0:y1, x0:x1]
                            healed_crop = cv2.inpaint(crop_src, crop_mask, inpaintRadius=max(5, min(15, r // 2)), flags=cv2.INPAINT_TELEA)
                            alpha_c = (stroke_soft[y0:y1, x0:x1].astype(np.float32) / 255.0)[:, :, None]
                            sess["clean_paint_small_bgr"][y0:y1, x0:x1] = np.clip(
                                crop_src.astype(np.float32) * (1.0 - alpha_c) + healed_crop.astype(np.float32) * alpha_c,
                                0, 255,
                            ).astype(np.uint8)

                previews = self._render_session_previews(sess, dress_smooth, dress_strength, need_comp=True, need_mask=False)
                out = {"ok": True, "inverted": bool(sess.get("inverted", False)), **previews,
                       "history": self._edit_history_counts(sess)}
                if stepped is not None:
                    out["stepped"] = bool(stepped)  # False: there was nothing to take back / to redo
                return out
        finally:
            self._end_job()

    def dress_preview_session(self, session_id: str, dress_smooth: bool, dress_strength: float) -> dict:
        self._session_or_raise(session_id)
        self._begin_job()
        try:
            with self._session_lock:
                sess = self._session_or_raise(session_id)
                previews = self._render_session_previews(sess, dress_smooth, dress_strength, need_comp=True, need_mask=False)
                return {"ok": True, **previews}
        finally:
            self._end_job()

    def apply_session(
        self,
        session_id: str,
        blend: float = 100.0,
        make_mask: bool = False,
        dress_smooth: bool = False,
        dress_strength: float = 45.0,
        progress_cb=None,
        params: dict | None = None,
    ) -> tuple[np.ndarray, np.ndarray | None, dict]:
        """
        params: the settings on the sliders at the moment of Apply (optional). The layer is always made for them:
        if the real frame was computed for other values (quick preview, or sliders moved without any refresh),
        it is computed here, once.
        """
        self._session_or_raise(session_id)

        t0 = time.perf_counter()
        self._begin_job()
        try:
            with self._session_lock:
                sess = self._session_or_raise(session_id)
                w, h = sess["width"], sess["height"]
                bit_depth = sess["bit_depth"]
                ps_max = 32768.0 if bit_depth == 16 else 255.0
                out_dtype = np.uint16 if bit_depth == 16 else np.uint8
                if params is not None:
                    self._adopt_session_params(sess, params)
                fast_mode = str(sess["params"].get("speedMode", "fast")).lower() == "fast"
                recomputed = bool(sess.get("base_stale"))

                if sess.get("base_stale"):
                    # Sliders were moved with the quick preview: this is the one full computation for all of them.
                    user_cb = progress_cb
                    self._refresh_stale_base(
                        sess,
                        (lambda pct, txt: user_cb(int(4 + 0.58 * pct), txt)) if user_cb is not None else None,
                    )
                    if user_cb is not None:
                        # the rest of Apply continues the same progress bar (it used to start at 45%)
                        progress_cb = lambda pct, txt: user_cb(int(60 + (pct - 45) * 0.62), txt)  # noqa: E731

                if progress_cb is not None:
                    progress_cb(45, "Фінальна збірка шару...")

                eff_small = self._compute_effective_mask_small(sess)
                eff_full_f = cv2.LUT(
                    cv2.resize(eff_small, (w, h), interpolation=cv2.INTER_LINEAR),
                    np.arange(256, dtype=np.float32) / 255.0,
                )

                cleaned_planes = self._rgb_planes(sess["cleaned_base_rgba"])
                cleaned_f32 = self._to_unit_f32(cleaned_planes, ps_max)

                # Heal any user-painted brush spots that were outside the zones the search repaired. (Not "outside the
                # layer": with the stain / blur / corner stages the layer covers the whole backdrop, and a stroke
                # over a defect that was left there has to be repaired all the same.)
                repaired_s = sess.get("repair_mask_small_u8")
                if repaired_s is None:
                    repaired_s = sess["auto_mask_small_u8"]
                extra_paint_s = np.maximum(0, sess["user_paint_u8"].astype(np.int16) - repaired_s.astype(np.int16))
                extra_paint_s[sess["user_erase_u8"] > 128] = 0
                if np.any(extra_paint_s > 64):
                    if progress_cb is not None:
                        progress_cb(60, "Дочищаємо домальовані пензлем зони...")
                    extra_full = (cv2.resize(extra_paint_s.astype(np.uint8), (w, h), interpolation=cv2.INTER_LINEAR) > 64).astype(np.uint8)
                    rows = np.flatnonzero(extra_full.any(axis=1))
                    if rows.size > 0:
                        cols = np.flatnonzero(extra_full.any(axis=0))
                        cur_rgb_u8 = self._to_analysis_u8(cleaned_planes, ps_max)
                        with self.lock:
                            if fast_mode:
                                # Returns uint8 0..255 (LaMa tiles return float 0..1). Blending it as if it were
                                # 0..1 turned every brushed-in zone pure white in the applied layer.
                                healed, _, _ = self._run_fast_inpaint(cur_rgb_u8, extra_full, progress_cb=progress_cb)
                            else:
                                self._ensure_models_loaded(need_matting=False, need_lama=True, progress_cb=progress_cb)
                                healed, _ = self._run_lama_tiles(cur_rgb_u8, extra_full, progress_cb=progress_cb)
                        del cur_rgb_u8
                        if healed is not None:
                            # The 11x11 soft edge is exactly 0 farther than 5px from the brushed zones, so only their
                            # bounding box needs blending. The blur runs on full-width rows on purpose: OpenCV rounds
                            # the last columns of a narrower crop differently (1 ulp), full-width rows match exactly.
                            y0, y1 = max(0, int(rows[0]) - 8), min(h, int(rows[-1]) + 9)
                            x0, x1 = max(0, int(cols[0]) - 8), min(w, int(cols[-1]) + 9)
                            by0, by1 = max(0, y0 - 16), min(h, y1 + 16)
                            p_soft = cv2.GaussianBlur(extra_full[by0:by1].astype(np.float32), (11, 11), 0)
                            p_soft = p_soft[y0 - by0:y1 - by0, x0:x1, None]
                            healed_c = np.ascontiguousarray(healed[y0:y1, x0:x1])
                            if healed_c.dtype == np.uint8:
                                healed_c = self._to_unit_f32(healed_c, 255.0)
                            dst = cleaned_f32[y0:y1, x0:x1]
                            dst[...] = dst * (1.0 - p_soft) + healed_c * p_soft
                            del healed_c, p_soft
                        del healed
                    del extra_full
                del cleaned_planes

                # Optional full-res dress fabric smoothing (only once at Apply!)
                dress_alpha_full = None
                if dress_smooth and dress_strength > 0 and sess.get("dress_s") is not None:
                    if progress_cb is not None:
                        progress_cb(82, "Вирівнювання одягу у повній роздільності...")
                    ds = sess["dress_s"].copy()
                    erase_s = cv2.resize(sess["user_erase_u8"], (ds.shape[1], ds.shape[0]), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
                    ds *= (1.0 - erase_s)
                    cleaned_f32, dress_alpha_full = self._smooth_dress_fabric(cleaned_f32, ds, float(dress_strength), fast_mode=fast_mode)

                # Layer opacity in Photoshop handles Blend 0..100 cleanly without double-scaling pixels/mask
                combined_alpha_f = np.maximum(eff_full_f, dress_alpha_full) if dress_alpha_full is not None else eff_full_f
                changed_px = int(np.count_nonzero(combined_alpha_f > 0.05))

                rgb_out = self._quantize_unit(cleaned_f32, ps_max, out_dtype)
                del cleaned_f32
                layer_mask_u8 = None
                if make_mask:
                    # Opaque pixels over cleaned areas, plus explicit Layer Mask matching user's green/red mask!
                    alpha_out = np.full((h, w), int(ps_max), dtype=out_dtype)
                    layer_mask_u8 = self._quantize_unit(combined_alpha_f, 255.0, np.uint8)
                else:
                    alpha_out = self._quantize_unit(combined_alpha_f, ps_max, out_dtype)
                out_rgba = np.empty((h, w, 4), dtype=out_dtype)
                cv2.mixChannels([rgb_out, alpha_out], [out_rgba], [0, 0, 1, 1, 2, 2, 3, 3])
                del rgb_out, alpha_out

                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                stats = {
                    "elapsed_ms": elapsed_ms,
                    "changed_px": changed_px,
                    "make_mask": bool(make_mask),
                    "dress_smooth": bool(dress_smooth),
                    "blend": float(blend),
                    "gpu": self.gpu_name,
                    "provider": self.provider_name,
                    "recomputed": recomputed,  # True: the real frame was computed inside this Apply
                }
                return out_rgba, layer_mask_u8, stats
        finally:
            self._end_job()
