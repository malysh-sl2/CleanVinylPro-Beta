import base64
import gc
import os
import sys
import time
import threading
import uuid
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


def _import_or_install_ort():
    try:
        import onnxruntime as _ort
        return _ort
    except ModuleNotFoundError:
        import importlib
        import re
        import shutil
        import subprocess

        print("[Engine] Пакунок onnxruntime відсутній у .venv — запускаємо автоматичне встановлення...", flush=True)
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
                subprocess.check_call([sys.executable, "-m", "pip", "install", "--no-cache-dir", pkg])
                break
            except Exception as e:
                print(f"[Engine] Не вдалося встановити {pkg}: {e}", flush=True)

        _NVIDIA_DLL_DIRS.extend(_register_nvidia_dlls())
        importlib.invalidate_caches()
        import onnxruntime as _ort
        return _ort


ort = _import_or_install_ort()


class CleanVinylEngine:
    def __init__(self, models_dir: str, idle_unload_sec: float = 30.0):
        self.models_dir = models_dir
        self.idle_unload_sec = float(idle_unload_sec)
        self.lock = threading.Lock()
        self._state_lock = threading.Lock()
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

        providers = []
        if "CUDAExecutionProvider" in avail:
            providers.append(("CUDAExecutionProvider", {
                "device_id": 0,
                "arena_extend_strategy": "kSameAsRequested",
            }))
        if allow_dml and "DmlExecutionProvider" in avail:
            providers.append("DmlExecutionProvider")
        providers.append("CPUExecutionProvider")

        so = ort.SessionOptions()
        so.log_severity_level = 2
        if not has_gpu_ep:
            return self._create_cpu_session(model_path)
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        try:
            sess = ort.InferenceSession(model_path, sess_options=so, providers=providers)
            active = sess.get_providers()[0] if sess.get_providers() else "CPUExecutionProvider"
            if "CUDAExecutionProvider" in avail and active == "CPUExecutionProvider":
                self.gpu_error = "CUDAExecutionProvider не зміг завантажитись (ймовірно, відсутні CUDA/cuDNN DLL або невідповідність драйвера NVIDIA)."
            return sess, active
        except Exception as exc:
            self.gpu_error = str(exc)
            print(f"[Engine][УВАГА] Помилка ініціалізації GPU ({model_path}): {exc}", flush=True)
            return self._create_cpu_session(model_path)

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
        return (out - mi) / (ma - mi + 1e-8)

    def _predict_fg_raw(self, img_rgb_u8: np.ndarray, progress_cb=None, fast_mode: bool = False) -> np.ndarray:
        if progress_cb is not None:
            progress_cb(18, "Розпізнавання моделі та одягу (AI)...")
        im_1024 = cv2.resize(img_rgb_u8, (1024, 1024), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0
        m = self._run_matting_single(im_1024)

        # On dark / low-key photos, run a shadow-lifted pass so dark dresses & hair in shadow are seen clearly
        p30_thr = 0.22 if fast_mode else 0.28
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
    def _compute_protection_maps_small(
        self,
        img_rgb_u8: np.ndarray,
        fg_mask_u8: np.ndarray,
        core_mask_u8: np.ndarray,
        smoke_strength: float,
        protect_smoke: bool,
        keep_shadows: bool,
    ):
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
        if num_lbl > 1:
            bw_e = stats[1:, cv2.CC_STAT_WIDTH]
            bh_e = stats[1:, cv2.CC_STAT_HEIGHT]
            area_e = stats[1:, cv2.CC_STAT_AREA]
            is_horiz_corner = (bw_e > 0.24 * sw) & (bh_e < 0.055 * sh) & ((bw_e / np.maximum(bh_e, 1)) > 5.0)
            valid_edge = ((area_e > 950) | (np.maximum(bw_e, bh_e) > 85)) & (~is_horiz_corner)
            edge_lut[1:] = valid_edge.astype(np.float32)
        stand_mask = edge_lut[labels]

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
        if protect_smoke and smoke_strength > 5:
            l_wisp = cv2.GaussianBlur(L, (5, 5), 0) - cv2.GaussianBlur(L, (35, 35), 0)
            wisp_rms = np.sqrt(np.maximum(0.0, cv2.GaussianBlur(l_wisp * l_wisp, (35, 35), 0)))
            a_wisp = cv2.GaussianBlur(A, (5, 5), 0) - cv2.GaussianBlur(A, (35, 35), 0)
            b_wisp = cv2.GaussianBlur(B, (5, 5), 0) - cv2.GaussianBlur(B, (35, 35), 0)
            chroma_wisp = np.sqrt(np.maximum(0.0, cv2.GaussianBlur(a_wisp * a_wisp + b_wisp * b_wisp, (35, 35), 0)))

            # Slider 80% default -> threshold ~1.45; higher slider -> lower threshold (protects fainter smoke!)
            thr_scale = 1.65 - (smoke_strength / 100.0) * 0.65  # 100% -> 1.00, 80% -> 1.13, 0% -> 1.65
            y_upper = np.linspace(1.0, 0.0, sh, dtype=np.float32)[:, None] > 0.45
            wisp_raw = (
                (wisp_rms > (1.30 * thr_scale)) | (chroma_wisp > (1.35 * thr_scale)) | ((L > 246.0) & y_upper)
            ) & (fg_s < 0.06) & (stand_mask < 0.4)
            wisp_open = cv2.morphologyEx(
                wisp_raw.astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
            )
            n_sm, lbl_sm, st_sm, _ = cv2.connectedComponentsWithStats(wisp_open, 8)
            sm_lut = np.zeros(n_sm, dtype=np.float32)
            if n_sm > 1:
                sm_lut[1:] = (st_sm[1:, cv2.CC_STAT_AREA] > 1200).astype(np.float32)
            smoke_bin = sm_lut[lbl_sm]
            smoke_mask = cv2.GaussianBlur(
                cv2.dilate(smoke_bin, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (33, 33))), (25, 25), 0
            )
        else:
            smoke_mask = np.zeros((sh, sw), dtype=np.float32)

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
    def _detect_vinyl_seam_mask(
        self,
        img_rgb_u8: np.ndarray,
        fg_mask_u8: np.ndarray,
        stand_s: np.ndarray,
        smoke_s: np.ndarray,
        seam_strength: float,
        edge_protection: float,
        fast_mode: bool = False,
    ) -> np.ndarray:
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

        # Higher seam_strength -> detects fainter vinyl seams too
        thin_thr = max(0.28, 0.72 - (seam_strength / 100.0) * 0.32)  # 85% -> 0.45
        cand = (best_thin > thin_thr).astype(np.uint8)
        close_w = 75 if fast_mode else 110
        cand_horiz = cv2.morphologyEx(cand, cv2.MORPH_CLOSE, np.ones((1, close_w), np.uint8))
        num_lbl, labels, stats, _ = cv2.connectedComponentsWithStats(cand_horiz, connectivity=8)

        seam_s = np.zeros((sh, sw), dtype=np.uint8)
        for idx in range(1, num_lbl):
            bw, bh = stats[idx, cv2.CC_STAT_WIDTH], stats[idx, cv2.CC_STAT_HEIGHT]
            area = stats[idx, cv2.CC_STAT_AREA]
            if bw > 0.24 * sw and (area / max(bw, 1)) < 13.0 and bh < 0.04 * sh:
                comp = (labels == idx) & (cand > 0)
                band_dil = cv2.dilate(comp.astype(np.uint8), np.ones((15, 1), np.uint8)) > 0
                mean_thin = float(best_thin[comp].mean())
                mean_wide = float(best_wide[band_dil].mean())
                ratio = mean_thin / (mean_wide + 0.05)
                if ratio >= 1.05:
                    seam_s[comp] = 255

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
    ):
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
            valid_sp = (areas >= 2) & (areas <= 3500) & (max_dim <= 180) & frac_ok & ~((sh_means > 48.0) & (areas > 28))
            spot_lut[1:] = valid_sp.astype(np.uint8) * 255
        clean_spots = spot_lut[labels]

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
        fine_strong = ((bh_full > thr_strong) | (th_full > max(12, int(round(7.5 * grain_full * sens))))).astype(np.uint8)
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
        fine_strong[shadow_work_bad & (bh_full <= int(round(thr_strong * 1.85))) & (th_full <= int(round(1.65 * max(12, 7.5 * grain_full * sens))))] = 0
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

        # Normalize where LaMa ran
        result_f32 = img_rgb_u8.astype(np.float32) / 255.0
        has_w = w_acc[:, :, 0] > 1e-6
        result_f32[has_w] = out_acc[has_w] / w_acc[has_w]
        return result_f32, tiles_run

    def _run_fast_inpaint(
        self,
        img_rgb_u8: np.ndarray,
        heal_mask_u8: np.ndarray,
        progress_cb=None,
    ) -> tuple[np.ndarray, int, int]:
        """
        Ultra-fast hybrid heal for v2.0.0 (~3-5s full 22MP target, minimal RAM):
        1) Small-to-medium isolated dust/crumbs/scratches (<= 60px bbox, area <= 2800) -> local Telea crop (~15-35ms total).
        2) Larger defects (vinyl seams, stands, cables, big scuffs) -> LaMa at <= 1536px working resolution (pad=40).
        Returns uint8 RGB image (zero 265MB float32 duplication!).
        """
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
            if max(bw, bh) <= 60 and area <= 2800:
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
    def _build_dress_mask_small(img_rgb_u8: np.ndarray, core_mask_u8: np.ndarray, max_dim: int = 1024) -> np.ndarray:
        """
        Returns float32 mask [0..1] over clothing/dress regions strictly inside the subject (`core_mask_u8`),
        protecting human skin tones (without misclassifying red/pink/magenta dresses as skin),
        head/hair zone (plus long hair connected from head onto shoulders/chest), and crisp silhouette edges.
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
        head_cut = y_top + int(round(subj_h * 0.22))
        head_prot = np.zeros((sh, sw), dtype=np.uint8)
        head_prot[:head_cut, :] = 1

        # Protect long hair connected down onto upper chest/shoulders (below 22% down to 48% of subject height)
        upper_lim = y_top + int(round(subj_h * 0.48))
        head_hair_zone = (fg_bin > 0) & (skin_prot == 0)
        head_hair_zone[upper_lim:, :] = False
        # Sample dark/warm hair pixels in top 22% head zone if available
        top_fg = fg_bin[:head_cut, :] > 0
        if np.any(top_fg):
            lab_s = cv2.cvtColor(small, cv2.COLOR_RGB2LAB).astype(np.float32)
            head_non_skin = top_fg & (skin_prot[:head_cut, :] == 0)
            if np.sum(head_non_skin) > 20:
                hair_ref = np.median(lab_s[:head_cut, :][head_non_skin], axis=0)
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
        return np.clip(dress_f, 0.0, 1.0).astype(np.float32)

    @staticmethod
    def _smooth_dress_fabric(
        cleaned_f32: np.ndarray,
        dress_mask_small: np.ndarray,
        strength: float,
        fast_mode: bool = False,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Frequency-separation wrinkle & specular smoothing on clothing:
        irons harsh mid-band fabric folds/creases while keeping fine weave texture, 3D volume, skin, and hair crisp.
        Returns (updated_f32, dress_alpha_full).
        """
        if strength <= 0 or not np.any(dress_mask_small > 0.02):
            h, w = cleaned_f32.shape[:2]
            return cleaned_f32, np.zeros((h, w), dtype=np.float32)

        h, w = cleaned_f32.shape[:2]
        scale_d = min(1.0, (960.0 if fast_mode else 1400.0) / max(h, w))
        dw, dh = max(8, int(round(w * scale_d))), max(8, int(round(h * scale_d)))

        small = cv2.resize(cleaned_f32, (dw, dh), interpolation=cv2.INTER_AREA).astype(np.float32)
        dm = cv2.resize(dress_mask_small, (dw, dh), interpolation=cv2.INTER_LINEAR).astype(np.float32)

        lab = cv2.cvtColor(np.clip(small, 0.0, 1.0), cv2.COLOR_RGB2LAB)
        L, A, B = lab[:, :, 0], lab[:, :, 1], lab[:, :, 2]

        # Normalized wide volume strictly inside dress pixels (zero background/skin bleed on black or colored dresses!)
        sig_wide = max(11.0, max(dw, dh) * 0.026)
        dm_src = np.clip((dm - 0.12) / 0.50, 0.0, 1.0)
        den_l = cv2.GaussianBlur(dm_src, (0, 0), sigmaX=sig_wide, sigmaY=sig_wide) + 1e-4
        L_wide = cv2.GaussianBlur(L * dm_src, (0, 0), sigmaX=sig_wide, sigmaY=sig_wide) / den_l
        L_fine = L - cv2.GaussianBlur(L, (5, 5), 0)
        L_u8 = np.clip(L * 2.55, 0, 255).astype(np.uint8)
        L_bil = cv2.bilateralFilter(L_u8, d=17 if fast_mode else 23, sigmaColor=28, sigmaSpace=28).astype(np.float32) / 2.55
        L_steamed = 0.58 * (L_wide + 0.35 * L_fine) + 0.42 * (L_bil + 0.25 * L_fine)

        den_c = cv2.GaussianBlur(dm_src, (0, 0), sigmaX=sig_wide * 0.75, sigmaY=sig_wide * 0.75) + 1e-4
        A_wide = cv2.GaussianBlur(A * dm_src, (0, 0), sigmaX=sig_wide * 0.75, sigmaY=sig_wide * 0.75) / den_c
        B_wide = cv2.GaussianBlur(B * dm_src, (0, 0), sigmaX=sig_wide * 0.75, sigmaY=sig_wide * 0.75) / den_c

        s_ratio = np.clip(strength / 100.0, 0.0, 1.5)
        mix = np.clip(s_ratio * 0.92, 0.0, 0.95) * dm

        glare_excess = np.maximum(0.0, L - (L_wide + 4.5))
        glare_fix = np.minimum(glare_excess * 0.55 * min(1.25, s_ratio), 12.0)

        lab[:, :, 0] = np.clip(L * (1.0 - mix) + (L_steamed - glare_fix) * mix, 0.0, 100.0)
        lab[:, :, 1] = np.clip(A * (1.0 - mix * 0.45) + A_wide * (mix * 0.45), -127.0, 127.0)
        lab[:, :, 2] = np.clip(B * (1.0 - mix * 0.45) + B_wide * (mix * 0.45), -127.0, 127.0)

        rgb_out_s = np.clip(cv2.cvtColor(lab, cv2.COLOR_LAB2RGB), 0.0, 1.0)
        diff_s = rgb_out_s - small
        changed_s = cv2.GaussianBlur(np.clip((np.max(np.abs(diff_s), axis=2) - 0.002) / 0.012, 0.0, 1.0), (5, 5), 0)
        alpha_s = np.clip(mix, 0.0, 1.0) * changed_s

        diff_full = cv2.resize(diff_s, (w, h), interpolation=cv2.INTER_LINEAR)
        out_f32 = cleaned_f32
        out_f32 += diff_full
        del diff_full
        np.clip(out_f32, 0.0, 1.0, out=out_f32)
        alpha_full = cv2.resize(alpha_s, (w, h), interpolation=cv2.INTER_LINEAR)
        return out_f32, alpha_full

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
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Softly rounds a sharp studio wall-to-floor corner angle (`гострий кут`) into a seamless
        curved cyclorama (`циклорама`) transition while preserving subject, shadows, smoke, and wall lighting.
        """
        h, w = cleaned_f32.shape[:2]
        if cyc_strength <= 0:
            return cleaned_f32, np.zeros((h, w), dtype=np.float32)

        sc = min(1.0, (512.0 if fast_mode else 768.0) / max(h, w))
        sw, sh = max(16, int(round(w * sc))), max(16, int(round(h * sc)))
        sm = np.clip(cv2.resize(cleaned_f32, (sw, sh), interpolation=cv2.INTER_AREA), 0.0, 1.0).astype(np.float32)
        lab = cv2.cvtColor(sm, cv2.COLOR_RGB2LAB)
        L, A, B = lab[:, :, 0], lab[:, :, 1], lab[:, :, 2]

        fg_s = cv2.resize(eff_fg_u8, (sw, sh), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
        st_s = cv2.resize(stand_protect_s, (sw, sh), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0
        sm_s = cv2.resize(smoke_s, (sw, sh), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0
        sh_s = cv2.resize(shadow_s, (sw, sh), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0

        # Protect cast/contact shadows near the subject while allowing horizontal wall-floor corner troughs to round smoothly
        fg_dist_c = cv2.distanceTransform((fg_s < 0.18).astype(np.uint8), cv2.DIST_L2, 5)
        fg_near = fg_dist_c < (0.28 * max(sh, sw))
        fg_touch = cv2.dilate((fg_s > 0.15).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (23, 23))) > 0
        sh_bin = (sh_s > 0.25).astype(np.uint8)
        n_sh, lbl_sh, _, _ = cv2.connectedComponentsWithStats(sh_bin, 8)
        keep_sh = set(np.unique(lbl_sh[fg_touch])) - {0}
        subj_sh_s = np.where(np.isin(lbl_sh, list(keep_sh)) & fg_near, sh_s, 0.0).astype(np.float32) if keep_sh else np.zeros_like(sh_s)

        # Erode clean background strictly away from subject/stands/smoke/subject-shadows so dark walls & cast shadows stay intact
        bg_core = ((fg_s < 0.04) & (st_s < 0.25) & (sm_s < 0.20) & (subj_sh_s < 0.18) & (L > 2.5)).astype(np.uint8)
        bg_er = cv2.erode(bg_core, np.ones((7, 7), np.uint8)).astype(np.float32)
        if float(np.sum(bg_er)) < sw * sh * 0.05:
            bg_er = (fg_s < 0.08).astype(np.float32)

        # Locate the horizontal wall-to-floor corner row y_c in [0.30..0.82] via coherent horizontal Sobel-Y energy
        den_h = cv2.boxFilter(bg_er, -1, (45, 1), normalize=False) + 1e-4
        L_h = cv2.boxFilter(L * bg_er, -1, (45, 1), normalize=False) / den_h
        valid_h = (den_h > 10.0).astype(np.float32)
        gy_signed = cv2.Sobel(L_h, cv2.CV_32F, 0, 1, ksize=3)
        gy_abs = np.abs(gy_signed) * valid_h
        gy_wide = cv2.GaussianBlur(gy_abs, (1, 25), 0)
        corner_map = np.maximum(0.0, gy_abs - 0.52 * gy_wide)
        row_cnt = np.sum(valid_h, axis=1) + 1e-4
        row_consistency = np.abs(np.sum(gy_signed * valid_h, axis=1)) / row_cnt
        row_score = (np.sum(corner_map, axis=1) / row_cnt) * 0.65 + row_consistency * 0.55
        row_score[np.sum(valid_h, axis=1) < sw * 0.14] = 0.0
        row_score[:int(sh * 0.30)] = 0.0
        row_score[int(sh * 0.82):] = 0.0
        y_c = int(np.argmax(row_score)) if np.any(row_score > 0) else int(sh * 0.62)
        corner_peak = float(row_score[y_c]) if np.any(row_score > 0) else 0.0
        corner_strength = float(np.clip((corner_peak - 3.0) / 9.0, 0.0, 1.0))
        if corner_strength <= 0.02:
            return cleaned_f32, np.zeros((h, w), dtype=np.float32)

        # Smoothly unblock the horizontal corner band around y_c outside tight subject silhouette so corner trough rounds cleanly
        yy_full = np.arange(sh, dtype=np.float32)[:, None]
        trough_unblock = np.exp(-0.5 * ((yy_full - y_c) / max(12.0, sh * 0.055)) ** 2).astype(np.float32)
        subj_sh_cove = subj_sh_s * (1.0 - trough_unblock * np.clip((fg_dist_c - 6.0) / 14.0, 0.0, 1.0))

        # Rebuild bg_er using subj_sh_cove so real corner pixels participate in L_clean (no false hole interpolation!)
        bg_core_c = ((fg_s < 0.04) & (st_s < 0.25) & (sm_s < 0.20) & (subj_sh_cove < 0.22) & (L > 2.5)).astype(np.uint8)
        bg_er_c = cv2.erode(bg_core_c, np.ones((7, 7), np.uint8)).astype(np.float32)
        if float(np.sum(bg_er_c)) < sw * sh * 0.05:
            bg_er_c = bg_er

        # Gap-free horizontal interpolation across subject/stand/cast-shadow holes
        den_x = cv2.GaussianBlur(bg_er_c, (0, 0), sigmaX=max(12.0, sw * 0.08), sigmaY=1.5) + 1e-4
        L_fill = cv2.GaussianBlur(L * bg_er_c, (0, 0), sigmaX=max(12.0, sw * 0.08), sigmaY=1.5) / den_x
        A_fill = cv2.GaussianBlur(A * bg_er_c, (0, 0), sigmaX=max(12.0, sw * 0.08), sigmaY=1.5) / den_x
        B_fill = cv2.GaussianBlur(B * bg_er_c, (0, 0), sigmaX=max(12.0, sw * 0.08), sigmaY=1.5) / den_x

        L_clean = L * bg_er_c + L_fill * (1.0 - bg_er_c)
        A_clean = A * bg_er_c + A_fill * (1.0 - bg_er_c)
        B_clean = B * bg_er_c + B_fill * (1.0 - bg_er_c)

        wall_slice = L_clean[max(0, y_c - int(sh * 0.16)):max(1, y_c - 6), :]
        wall_l_med = float(np.median(wall_slice)) if wall_slice.size > 0 else 40.0
        lowkey_damp = float(np.clip((wall_l_med - 3.5) / 14.0, 0.65, 1.0))

        s_ratio = np.clip(cyc_strength / 100.0, 0.0, 1.0)
        sigma_x = max(2.0, sw * 0.008)
        sigma_y_cove = max(10.0, sh * (0.025 + 0.070 * s_ratio) * lowkey_damp)

        L_cove = cv2.GaussianBlur(L_clean, (0, 0), sigmaX=sigma_x, sigmaY=sigma_y_cove)
        A_cove = cv2.GaussianBlur(A_clean, (0, 0), sigmaX=sigma_x, sigmaY=sigma_y_cove)
        B_cove = cv2.GaussianBlur(B_clean, (0, 0), sigmaX=sigma_x, sigmaY=sigma_y_cove)

        band_sig = max(14.0, sigma_y_cove * 1.40)
        W_cove = np.exp(-0.5 * ((yy_full - y_c) / band_sig) ** 2).astype(np.float32)

        fg_guard_c = cv2.dilate((fg_s > 0.03).astype(np.uint8), np.ones((9, 9), np.uint8)).astype(np.float32)
        ramp_c = self._outward_transition_ramp(np.maximum(fg_s, fg_guard_c), feather_str)
        env_c = cv2.GaussianBlur((1.0 - 0.90 * st_s) * (1.0 - sm_s) * np.clip(1.0 - subj_sh_cove * 2.2, 0.0, 1.0), (19, 19), 0)
        allow_c = np.clip(ramp_c * env_c, 0.0, 1.0)
        mix = W_cove * allow_c * (0.45 + 0.55 * s_ratio) * corner_strength

        # Glide smoothly directly toward L_cove (impossible to overshoot or form bright bands!)
        dL = (L_cove - L) * mix
        dark_up_guard = np.clip((L - 2.0) / 5.5, 0.15, 1.0)
        dL = np.where(dL > 0.0, np.minimum(dL * dark_up_guard, 3.5 + 0.55 * np.maximum(L, 4.0)), dL)
        chroma_guard = np.clip((L - 10.0) / 22.0, 0.0, 1.0)
        dA = (A_cove - A) * (mix * 0.30 * chroma_guard)
        dB = (B_cove - B) * (mix * 0.30 * chroma_guard)

        lab_new_s = np.stack(
            [np.clip(L + dL, 0.0, 100.0), np.clip(A + dA, -127.0, 127.0), np.clip(B + dB, -127.0, 127.0)],
            axis=2,
        ).astype(np.float32)
        rgb_new_s = np.clip(cv2.cvtColor(lab_new_s, cv2.COLOR_LAB2RGB), 0.0, 1.0)
        diff_s = rgb_new_s - sm
        changed_s = cv2.GaussianBlur(np.clip((np.max(np.abs(diff_s), axis=2) - 0.004) / 0.022, 0.0, 1.0), (7, 7), 0)
        cyc_s = np.clip(allow_c * s_ratio, 0.0, 1.0) * changed_s * np.clip(1.0 - np.clip((fg_s - 0.15) / 0.66, 0.0, 1.0), 0.0, 1.0)

        diff_full = cv2.resize(diff_s, (w, h), interpolation=cv2.INTER_LINEAR)
        cleaned_f32 += diff_full
        del diff_full
        np.clip(cleaned_f32, 0.0, 1.0, out=cleaned_f32)
        cyc_alpha = cv2.resize(cyc_s, (w, h), interpolation=cv2.INTER_LINEAR)
        return cleaned_f32, cyc_alpha

    # ------------------------------------------------------------------
    # 5c. Fast Mask Previews (v2.0.0 Green-on-Red Action Mask + Legacy Protection)
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
            smoke_str = float(params.get("smoke", 80))
            keep_shadow = bool(params.get("shadow", True))
            remove_stands = bool(params.get("removeStands", False))
            master_val = float(params.get("master", 100))
            frac_fine = bool(params.get("fracFine", True))
            frac_med = bool(params.get("fracMed", True))
            frac_large = bool(params.get("fracLarge", True))

            boost = max(1.0, min(2.0, master_val / 100.0))
            spots_eff = min(160.0, spots_str * boost)
            seam_eff = min(155.0, seam_str * boost)

            with self.lock:
                self._ensure_models_loaded(need_matting=True, need_lama=False, progress_cb=progress_cb)
                fg_raw_1024 = self._predict_fg_raw(img_rgb_u8, progress_cb=progress_cb, fast_mode=True)
                if progress_cb is not None:
                    progress_cb(65, "Пошук дефектів для зеленої маски...")
                fg_mask_u8, core_mask_u8 = self._clean_fg_mask(fg_raw_1024, w, h, edge_prot)
                stand_protect_s, stand_remove_s, smoke_s, shadow_s = self._compute_protection_maps_small(
                    img_rgb_u8, fg_mask_u8, core_mask_u8, smoke_str, smoke_on, keep_shadow
                )
                eff_stand_protect = np.zeros_like(stand_protect_s) if remove_stands else stand_protect_s
                eff_fg_for_spots = core_mask_u8 if remove_stands else fg_mask_u8

                seam_mask = np.zeros((h, w), dtype=np.uint8)
                if seam_on and seam_eff > 0 and frac_large:
                    seam_mask = self._detect_vinyl_seam_mask(
                        img_rgb_u8, eff_fg_for_spots, eff_stand_protect, smoke_s, seam_eff, edge_prot, fast_mode=True
                    )
                    seam_mask[core_mask_u8 > 140] = 0

                spot_mask, _ = self._detect_spots_mask(
                    img_rgb_u8,
                    eff_fg_for_spots,
                    eff_stand_protect,
                    smoke_s,
                    shadow_s,
                    spots_eff,
                    fast_mode=True,
                    frac_fine=frac_fine,
                    frac_med=frac_med,
                    frac_large=frac_large,
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
    ):
        t0 = time.perf_counter()
        self._begin_job()
        try:
            def _prog(pct: int, txt: str):
                if progress_cb is not None:
                    progress_cb(pct, txt)

            h, w = img_rgba.shape[:2]
            ps_max = 32768.0 if bit_depth == 16 else 255.0

            _prog(12, "Підготовка зображення та профілю...")
            # Normalize original image to float32 [0..1] in-place (preserving full 16-bit precision!)
            orig_rgb_f32 = img_rgba[:, :, :3].astype(np.float32)
            orig_rgb_f32 *= (1.0 / ps_max)
            np.clip(orig_rgb_f32, 0.0, 1.0, out=orig_rgb_f32)
            img_rgb_u8 = np.clip(orig_rgb_f32 * 255.0 + 0.5, 0, 255).astype(np.uint8)

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
            grain_keep = float(params.get("grain", 90))
            keep_shadow = bool(params.get("shadow", True))
            remove_stands = bool(params.get("removeStands", False))
            master_val = float(params.get("master", 100))
            speed_mode = "fast" if str(params.get("speedMode", "quality")).lower() == "fast" else "quality"
            fast_mode = speed_mode == "fast"

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
            dress_src_1024 = None
            if dress_strength > 0:
                d_sc = min(1.0, 1024.0 / max(h, w))
                dress_src_1024 = cv2.resize(
                    img_rgb_u8,
                    (max(8, int(round(w * d_sc))), max(8, int(round(h * d_sc)))),
                    interpolation=cv2.INTER_AREA,
                )

            with self.lock:
                self._ensure_models_loaded(
                    need_matting=(need_bg_maps and custom_fg_mask is None and cached_fg_raw_1024 is None),
                    need_lama=(needs_lama_work and not fast_mode),
                    progress_cb=progress_cb,
                )

                fg_raw_1024 = cached_fg_raw_1024
                if need_bg_maps:
                    if custom_fg_mask is not None:
                        _prog(32, "Використання маски захисту...")
                        fg_mask_u8 = custom_fg_mask.astype(np.uint8)
                        core_mask_u8 = fg_mask_u8
                    else:
                        if fg_raw_1024 is None:
                            fg_raw_1024 = self._predict_fg_raw(img_rgb_u8, progress_cb=progress_cb, fast_mode=fast_mode)
                        _prog(35, "Уточнення контуру моделі...")
                        fg_mask_u8, core_mask_u8 = self._clean_fg_mask(fg_raw_1024, w, h, edge_prot)

                    _prog(40, "Аналіз стійок, диму й тіней...")
                    stand_protect_s, stand_remove_s, smoke_s, shadow_s = self._compute_protection_maps_small(
                        img_rgb_u8, fg_mask_u8, core_mask_u8, smoke_str, smoke_on, keep_shadow
                    )
                    eff_stand_protect = np.zeros_like(stand_protect_s) if remove_stands else stand_protect_s
                    eff_fg_for_spots = core_mask_u8 if remove_stands else fg_mask_u8
                else:
                    stand_remove_s = np.zeros((1, 1), dtype=np.uint8)

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
                    if seam_on and seam_eff > 0 and frac_large:
                        seam_mask = self._detect_vinyl_seam_mask(
                            img_rgb_u8, eff_fg_for_spots, eff_stand_protect, smoke_s, seam_eff, edge_prot, fast_mode=fast_mode
                        )
                        seam_mask[core_mask_u8 > 140] = 0

                    if spots_eff > 0 and has_any_frac:
                        spot_mask, grain_sigma = self._detect_spots_mask(
                            img_rgb_u8,
                            eff_fg_for_spots,
                            eff_stand_protect,
                            smoke_s,
                            shadow_s,
                            spots_eff,
                            fast_mode=fast_mode,
                            frac_fine=frac_fine,
                            frac_med=frac_med,
                            frac_large=frac_large,
                        )

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

                small_specks_healed = 0
                if not needs_lama_work or not np.any(heal_mask > 0):
                    lama_f32 = None
                    tiles_run = 0
                    heal_mask[:] = 0
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
                            heal_src_u8, heal_mask, progress_cb=progress_cb
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

            if lama_f32 is not None:
                heal_alpha = cv2.GaussianBlur((heal_mask > 0).astype(np.float32), (11 if fast_mode else 15, 11 if fast_mode else 15), 0)
                ys_h, xs_h = np.where(heal_alpha > 0.002)
                if ys_h.size > 0:
                    y0h, y1h = int(ys_h.min()), int(ys_h.max()) + 1
                    x0h, x1h = int(xs_h.min()), int(xs_h.max()) + 1
                    rng = np.random.default_rng(42)
                    g_ratio = grain_keep / 100.0
                    noise_std = (grain_sigma / 255.0) * 0.55 * g_ratio if (grain_keep > 0 and (tiles_run > 0 or small_specks_healed > 0)) else 0.0
                    # Process in 1024-row bands so lama_crop uses ~45MB instead of 265MB
                    for ys_b in range(y0h, y1h, 1024):
                        ye_b = min(y1h, ys_b + 1024)
                        bh_h, bw_h = ye_b - ys_b, x1h - x0h
                        ha_crop = heal_alpha[ys_b:ye_b, x0h:x1h, None]
                        lama_crop = lama_f32[ys_b:ye_b, x0h:x1h]
                        if lama_crop.dtype == np.uint8:
                            lama_crop = lama_crop.astype(np.float32) * (1.0 / 255.0)
                        else:
                            lama_crop = lama_crop.copy()

                        if noise_std > 1e-5:
                            n_small = rng.normal(0.0, noise_std, (max(1, bh_h // 2), max(1, bw_h // 2), 1)).astype(np.float32)
                            n_full = cv2.resize(n_small, (bw_h, bh_h), interpolation=cv2.INTER_LINEAR)[..., None]
                            n_fine = rng.normal(0.0, noise_std * 0.50, (bh_h, bw_h, 1)).astype(np.float32)
                            luma_ref = cleaned_f32[ys_b:ye_b, x0h:x1h].mean(axis=2, keepdims=True)
                            dark_g_scale = np.clip(luma_ref / 0.14, 0.12, 1.0)
                            lama_crop = np.clip(
                                lama_crop + (n_full + n_fine) * dark_g_scale * ha_crop,
                                0.0,
                                1.0,
                            )

                        cleaned_f32[ys_b:ye_b, x0h:x1h] += (lama_crop - cleaned_f32[ys_b:ye_b, x0h:x1h]) * ha_crop
                        del lama_crop
                del lama_f32
                if custom_heal_mask is None:
                    protect_h = np.clip((eff_fg_for_spots.astype(np.float32) - 40.0) / 170.0, 0.0, 1.0)
                    heal_alpha *= (1.0 - protect_h)
                    del protect_h
                np.maximum(final_alpha, heal_alpha, out=final_alpha)
                del heal_alpha
            else:
                pass

            # Mid-band Frequency Separation in pure 32-bit float32 Lab (normalized convolution + zero dress bleed!)
            if scuffs_eff > 0:
                _prog(83, "Вирівнювання розводів та слідів...")
                sc_max = 900.0 if fast_mode else 1400.0
                scale_sc = min(0.5, sc_max / max(h, w))
                sh, sw = max(8, int(round(h * scale_sc))), max(8, int(round(w * scale_sc)))
                small_f32 = cv2.resize(cleaned_f32, (sw, sh), interpolation=cv2.INTER_AREA).astype(np.float32)
                np.clip(small_f32, 0.0, 1.0, out=small_f32)
                lab_s = cv2.cvtColor(small_f32, cv2.COLOR_RGB2LAB)
                L_s, A_s, B_s = lab_s[:, :, 0], lab_s[:, :, 1], lab_s[:, :, 2]

                fg_half = cv2.resize(eff_fg_for_spots, (sw, sh), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
                st_half = cv2.resize(eff_stand_protect, (sw, sh), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0
                sm_half = cv2.resize(smoke_s, (sw, sh), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0
                sh_half = cv2.resize(shadow_s, (sw, sh), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0

                k_low = 71 if fast_mode else 111
                k_mid = 15 if fast_mode else 21
                k_ab = 61 if fast_mode else 95
                # Strictly exclude subject edges & cast shadows from reference pools so neither light nor warm skin bleeds into shadows!
                sc_src_w = (fg_half < 0.05).astype(np.float32) * (1.0 - 0.90 * st_half) * (1.0 - np.clip(sh_half * 1.4, 0.0, 1.0))
                den_111 = cv2.GaussianBlur(sc_src_w, (k_low, k_low), 0) + 1e-4
                L_low = cv2.GaussianBlur(L_s * sc_src_w, (k_low, k_low), 0) / den_111
                den_21 = cv2.GaussianBlur(sc_src_w, (k_mid, k_mid), 0) + 1e-4
                L_21 = cv2.GaussianBlur(L_s * sc_src_w, (k_mid, k_mid), 0) / den_21
                L_mid = L_21 - L_low
                den_95 = cv2.GaussianBlur(sc_src_w, (k_ab, k_ab), 0) + 1e-4
                A_low = cv2.GaussianBlur(A_s * sc_src_w, (k_ab, k_ab), 0) / den_95
                B_low = cv2.GaussianBlur(B_s * sc_src_w, (k_ab, k_ab), 0) / den_95

                ramp_sc = self._outward_transition_ramp(fg_half, feather_str)
                env_sc = cv2.GaussianBlur((1.0 - st_half) * (1.0 - sm_half) * (1.0 - np.clip(sh_half * 1.35, 0.0, 1.0)), (19, 19), 0)
                allow_scuff = np.clip(ramp_sc * env_sc, 0.0, 1.0)

                dark_damp = np.clip((np.minimum(L_s, L_low) - 6.0) / 22.0, 0.0, 1.0)
                sc_ratio = min(2.0, scuffs_eff / 100.0)
                strength = min(0.95, sc_ratio * 0.68)
                l_cap = 4.7 + max(0.0, sc_ratio - 0.6) * 5.0
                c_cap = 3.6 + max(0.0, sc_ratio - 0.6) * 2.5
                # Prevent lifting dark vignettes/shadow tails upward on low-key backgrounds
                l_delta = -((strength * dark_damp) * allow_scuff * np.clip(L_mid, -l_cap, l_cap))
                l_up_guard = np.clip((L_s - 12.0) / 22.0, 0.0, 1.0)
                l_delta = np.where(l_delta > 0.0, l_delta * l_up_guard, l_delta)
                L_new = L_s + l_delta
                chroma_damp = dark_damp * np.clip((L_s - 10.0) / 22.0, 0.0, 1.0)
                A_new = A_s - (min(0.85, strength * 0.72) * chroma_damp) * allow_scuff * np.clip(A_s - A_low, -c_cap, c_cap)
                B_new = B_s - (min(0.85, strength * 0.72) * chroma_damp) * allow_scuff * np.clip(B_s - B_low, -c_cap, c_cap)

                lab_new = np.stack(
                    [np.clip(L_new, 0.0, 100.0), np.clip(A_new, -127.0, 127.0), np.clip(B_new, -127.0, 127.0)],
                    axis=2,
                ).astype(np.float32)
                rgb_new_s = np.clip(cv2.cvtColor(lab_new, cv2.COLOR_LAB2RGB), 0.0, 1.0)
                diff_s = rgb_new_s - small_f32
                changed_s = cv2.GaussianBlur(
                    np.clip((np.max(np.abs(diff_s), axis=2) - 0.0045) / 0.018, 0.0, 1.0),
                    (7, 7),
                    0,
                )
                scuff_s = np.clip(allow_scuff * min(1.0, sc_ratio), 0.0, 1.0) * changed_s * np.clip(1.0 - np.clip((fg_half - 0.15) / 0.66, 0.0, 1.0), 0.0, 1.0)
                diff_full = cv2.resize(diff_s, (w, h), interpolation=cv2.INTER_LINEAR)
                cleaned_f32 += diff_full
                del diff_full
                np.clip(cleaned_f32, 0.0, 1.0, out=cleaned_f32)
                scuff_alpha = cv2.resize(scuff_s, (w, h), interpolation=cv2.INTER_LINEAR)
                np.maximum(final_alpha, scuff_alpha, out=final_alpha)
                del scuff_alpha

            # Normalized Shadow-Safe Masked Background Blur (smooths vinyl wrinkles with zero dark-backdrop wash or halo!)
            if blur_str > 0:
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
                del pass2_u8, spot2_mask

            # Cyclorama Corner-Rounding (infinity-cove smoothing of sharp wall-to-floor studio angle)
            if cyc_str > 0:
                _prog(88, "Заокруглення кута під циклораму...")
                cleaned_f32, cyc_alpha = self._apply_cyclorama_curve(
                    cleaned_f32,
                    eff_fg_for_spots,
                    eff_stand_protect,
                    smoke_s,
                    shadow_s,
                    cyc_str,
                    feather_str,
                    fast_mode=fast_mode,
                )
                np.maximum(final_alpha, cyc_alpha, out=final_alpha)
                del cyc_alpha

            # Optional Dress / Clothing Soft Wrinkle & Specular Smoothing (Skin/Hair/Edge Safe)
            dress_s_cached = None
            if dress_strength > 0 and dress_src_1024 is not None:
                _prog(89, "Делікатне вирівнювання одягу...")
                dress_s_cached = self._build_dress_mask_small(dress_src_1024, core_mask_u8, max_dim=1024)
                del dress_src_1024
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
                out_cache["seam_px"] = int(seam_mask.sum())
                out_cache["spot_px"] = int(spot_mask.sum())
                out_cache["grain_sigma"] = float(grain_sigma)
                if dress_s_cached is not None:
                    out_cache["dress_s"] = dress_s_cached

            _prog(92, "Передача результату у Photoshop...")
            np.clip(final_alpha, 0.0, 1.0, out=final_alpha)

            if selection_alpha is not None:
                sel_f = np.clip(selection_alpha.astype(np.float32) / (255.0 if selection_alpha.dtype == np.uint8 else ps_max), 0.0, 1.0)
                final_alpha = final_alpha * sel_f

            # Pack back to exact source bit depth (0..255 uint8 or 0..32768 uint16)
            out_rgba = np.empty((h, w, 4), dtype=np.uint16 if bit_depth == 16 else np.uint8)
            cleaned_f32 *= ps_max
            np.round(cleaned_f32, out=cleaned_f32)
            np.clip(cleaned_f32, 0, ps_max, out=cleaned_f32)
            out_rgba[:, :, :3] = cleaned_f32.astype(out_rgba.dtype)
            final_alpha *= ps_max
            np.round(final_alpha, out=final_alpha)
            np.clip(final_alpha, 0, ps_max, out=final_alpha)
            out_rgba[:, :, 3] = final_alpha.astype(out_rgba.dtype)

            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            changed_px = int((final_alpha > (0.05 * ps_max)).sum())
            stats = {
                "elapsed_ms": elapsed_ms,
                "tiles_run": tiles_run,
                "small_specks": small_specks_healed,
                "speed_mode": speed_mode,
                "seam_px": int(seam_mask.sum()),
                "spot_px": int(spot_mask.sum()),
                "dress_smooth": dress_smooth_on,
                "changed_px": changed_px,
                "gpu": self.gpu_name,
                "provider": self.provider_name,
            }
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

    @staticmethod
    def _encode_overlay_jpg(comp_bgr: np.ndarray, mask_u8: np.ndarray, quality: int = 90) -> str:
        """
        Pre-composited Retouch4me red-protected + bright-green-mask JPEG preview.
        Guaranteed 100% opaque JPEG — immune to UXP canvas/alpha compositor quirks!
        """
        m = mask_u8.astype(np.float32)[:, :, None] * (1.0 / 255.0)
        base_f = comp_bgr.astype(np.float32)
        red_a = 0.36 * (1.0 - m)
        tinted = base_f * (1.0 - red_a) + np.array([18.0, 18.0, 178.0], dtype=np.float32) * red_a
        grn_a = 0.72 * m
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

    def _render_session_previews(
        self,
        sess: dict,
        dress_smooth: bool,
        dress_strength: float,
        need_comp: bool = True,
        need_mask: bool = True,
    ) -> dict:
        eff_mask = self._compute_effective_mask_small(sess)
        out: dict = {}

        if need_mask:
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

            out["comp_jpg_b64"] = self._encode_b64_jpg(comp_bgr, quality=90)
            out["overlay_jpg_b64"] = self._encode_overlay_jpg(comp_bgr, eff_mask, quality=90)
        return out

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

    def start_session(
        self,
        img_rgba: np.ndarray,
        bit_depth: int,
        params: dict,
        selection_alpha: np.ndarray | None = None,
        progress_cb=None,
    ) -> dict:
        t0 = time.perf_counter()
        self._begin_job()
        try:
            self._active_session = None
            gc.collect()

            h, w = img_rgba.shape[:2]
            ps_max = 32768.0 if bit_depth == 16 else 255.0
            p = dict(params or {})

            if progress_cb is not None:
                progress_cb(12, "Завантаження AI-моделей...")

            orig_rgb_u8 = np.clip((img_rgba[:, :, :3].astype(np.float32) / ps_max) * 255.0 + 0.5, 0, 255).astype(np.uint8)

            # Quick initial subject detection & automatic fraction selection
            with self.lock:
                self._ensure_models_loaded(need_matting=True, need_lama=False, progress_cb=progress_cb)
                fg_raw_1024 = self._predict_fg_raw(orig_rgb_u8, progress_cb=progress_cb, fast_mode=(str(p.get("speedMode", "fast")).lower() == "fast"))
                fg_mask_u8, core_mask_u8 = self._clean_fg_mask(fg_raw_1024, w, h, float(p.get("edge", 70)))

            if p.get("autoFractions", True):
                if progress_cb is not None:
                    progress_cb(30, "Автопідбір фракцій дефектів...")
                auto_fracs = self._analyze_auto_fractions(orig_rgb_u8, fg_mask_u8, core_mask_u8, float(p.get("edge", 70)))
                if not (auto_fracs["fracFine"] or auto_fracs["fracMed"] or auto_fracs["fracLarge"]):
                    auto_fracs["fracFine"] = True
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
            clean_params = dict(p)
            clean_params["dressSmooth"] = False
            clean_params["master"] = max(100.0, float(p.get("master", 100)))  # bake 100%+; Blend slider handles 0..100 live

            out_cache: dict = {}
            cleaned_rgba, stats = self.process(
                img_rgba,
                bit_depth,
                clean_params,
                selection_alpha=selection_alpha,
                progress_cb=progress_cb,
                cached_fg_raw_1024=fg_raw_1024,
                out_cache=out_cache,
            )

            # Build proxy previews (<=1080px)
            prev_scale = min(1.0, 1080.0 / max(h, w))
            pw = max(16, int(round(w * prev_scale)))
            ph = max(16, int(round(h * prev_scale)))

            orig_small_bgr = cv2.cvtColor(cv2.resize(orig_rgb_u8, (pw, ph), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2BGR)
            clean_small_u8 = np.clip((cv2.resize(cleaned_rgba[:, :, :3], (pw, ph), interpolation=cv2.INTER_AREA).astype(np.float32) / ps_max) * 255.0 + 0.5, 0, 255).astype(np.uint8)
            clean_small_bgr = cv2.cvtColor(clean_small_u8, cv2.COLOR_RGB2BGR)

            # Build Green Action Mask for preview from healed spots/seams + visible background alpha
            alpha_small = cv2.resize(cleaned_rgba[:, :, 3], (pw, ph), interpolation=cv2.INTER_AREA)
            alpha_u8_s = np.clip((alpha_small.astype(np.float32) / ps_max) * 255.0 + 0.5, 0, 255).astype(np.uint8)
            heal_full = out_cache.get("heal_mask_full")
            if heal_full is not None and np.any(heal_full > 0):
                heal_s = cv2.resize((heal_full > 0).astype(np.uint8) * 255, (pw, ph), interpolation=cv2.INTER_AREA)
                auto_mask_small = np.maximum(heal_s, alpha_u8_s)
            else:
                auto_mask_small = alpha_u8_s

            # Cache dress mask once at 1024px so toggling dress icon inside window takes ~12 ms!
            d_sc = min(1.0, 1024.0 / max(h, w))
            dress_src_1024 = cv2.resize(orig_rgb_u8, (max(8, int(round(w * d_sc))), max(8, int(round(h * d_sc)))), interpolation=cv2.INTER_AREA)
            dress_s = self._build_dress_mask_small(dress_src_1024, out_cache["core_mask_u8"], max_dim=1024)

            sess_id = uuid.uuid4().hex[:12]
            sess = {
                "id": sess_id,
                "width": w,
                "height": h,
                "bit_depth": bit_depth,
                "preview_w": pw,
                "preview_h": ph,
                "img_rgba_orig": img_rgba.copy(),
                "cleaned_base_rgba": cleaned_rgba,
                "selection_alpha": selection_alpha.copy() if selection_alpha is not None else None,
                "fg_raw_1024": fg_raw_1024,
                "core_mask_u8": out_cache["core_mask_u8"],
                "dress_s": dress_s,
                "orig_small_bgr": orig_small_bgr,
                "clean_base_small_bgr": clean_small_bgr,
                "clean_paint_small_bgr": clean_small_bgr.copy(),
                "auto_mask_small_u8": auto_mask_small,
                "user_paint_u8": np.zeros((ph, pw), dtype=np.uint8),
                "user_erase_u8": np.zeros((ph, pw), dtype=np.uint8),
                "inverted": False,
                "params": p,
            }
            self._active_session = sess

            dress_on = bool(p.get("dressSmooth", False))
            dress_str = float(p.get("dressStrength", 45))
            previews = self._render_session_previews(sess, dress_on, dress_str, need_comp=True, need_mask=True)
            orig_jpg_b64 = self._encode_b64_jpg(orig_small_bgr, quality=90)

            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            stats["elapsed_ms"] = elapsed_ms
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
                "mask_png_b64": previews["mask_png_b64"],
                "stats": stats,
            }
        finally:
            self._end_job()

    def recompute_session(self, session_id: str, params: dict, preserve_edits: bool = True, progress_cb=None) -> dict:
        sess = self._active_session
        if not sess or sess["id"] != session_id:
            raise ValueError("Сесія застаріла. Закрийте вікно й запустіть «Очистити фон» ще раз.")

        t0 = time.perf_counter()
        self._begin_job()
        try:
            p = dict(params or {})
            w, h = sess["width"], sess["height"]
            pw, ph = sess["preview_w"], sess["preview_h"]
            bit_depth = sess["bit_depth"]
            ps_max = 32768.0 if bit_depth == 16 else 255.0

            if p.get("autoFractions", False):
                orig_rgb_u8 = np.clip((sess["img_rgba_orig"][:, :, :3].astype(np.float32) / ps_max) * 255.0 + 0.5, 0, 255).astype(np.uint8)
                fg_m, core_m = self._clean_fg_mask(sess["fg_raw_1024"], w, h, float(p.get("edge", 70)))
                auto_fracs = self._analyze_auto_fractions(orig_rgb_u8, fg_m, core_m, float(p.get("edge", 70)))
                if not (auto_fracs["fracFine"] or auto_fracs["fracMed"] or auto_fracs["fracLarge"]):
                    auto_fracs["fracFine"] = True
                p["fracFine"] = auto_fracs["fracFine"]
                p["fracMed"] = auto_fracs["fracMed"]
                p["fracLarge"] = auto_fracs["fracLarge"]

            clean_params = dict(p)
            clean_params["dressSmooth"] = False
            clean_params["master"] = max(100.0, float(p.get("master", 100)))

            out_cache: dict = {}
            cleaned_rgba, stats = self.process(
                sess["img_rgba_orig"],
                bit_depth,
                clean_params,
                selection_alpha=sess.get("selection_alpha"),
                progress_cb=progress_cb,
                cached_fg_raw_1024=sess["fg_raw_1024"],
                out_cache=out_cache,
            )

            clean_small_u8 = np.clip((cv2.resize(cleaned_rgba[:, :, :3], (pw, ph), interpolation=cv2.INTER_AREA).astype(np.float32) / ps_max) * 255.0 + 0.5, 0, 255).astype(np.uint8)
            clean_small_bgr = cv2.cvtColor(clean_small_u8, cv2.COLOR_RGB2BGR)

            alpha_small = cv2.resize(cleaned_rgba[:, :, 3], (pw, ph), interpolation=cv2.INTER_AREA)
            alpha_u8_s = np.clip((alpha_small.astype(np.float32) / ps_max) * 255.0 + 0.5, 0, 255).astype(np.uint8)
            heal_full = out_cache.get("heal_mask_full")
            if heal_full is not None and np.any(heal_full > 0):
                heal_s = cv2.resize((heal_full > 0).astype(np.uint8) * 255, (pw, ph), interpolation=cv2.INTER_AREA)
                auto_mask_small = np.maximum(heal_s, alpha_u8_s)
            else:
                auto_mask_small = alpha_u8_s

            sess["cleaned_base_rgba"] = cleaned_rgba
            sess["core_mask_u8"] = out_cache["core_mask_u8"]
            sess["clean_base_small_bgr"] = clean_small_bgr
            sess["clean_paint_small_bgr"] = clean_small_bgr.copy()
            sess["auto_mask_small_u8"] = auto_mask_small
            sess["params"] = p

            if not preserve_edits:
                sess["user_paint_u8"][:] = 0
                sess["user_erase_u8"][:] = 0
                sess["inverted"] = False
            elif np.any(sess["user_paint_u8"] > 16):
                paint_bin = (sess["user_paint_u8"] > 64).astype(np.uint8)
                inpainted = cv2.inpaint(sess["clean_paint_small_bgr"], paint_bin, inpaintRadius=7, flags=cv2.INPAINT_TELEA)
                p_alpha = cv2.GaussianBlur(paint_bin.astype(np.float32), (5, 5), 0)[:, :, None]
                sess["clean_paint_small_bgr"] = np.clip(
                    sess["clean_paint_small_bgr"].astype(np.float32) * (1.0 - p_alpha) + inpainted.astype(np.float32) * p_alpha,
                    0, 255,
                ).astype(np.uint8)

            dress_on = bool(p.get("dressSmooth", False))
            dress_str = float(p.get("dressStrength", 45))
            previews = self._render_session_previews(sess, dress_on, dress_str, need_comp=True, need_mask=True)
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
                "mask_png_b64": previews["mask_png_b64"],
                "stats": stats,
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
        sess = self._active_session
        if not sess or sess["id"] != session_id:
            raise ValueError("Сесія застаріла.")

        self._begin_job()
        try:
            pw, ph = sess["preview_w"], sess["preview_h"]
            paint_u8 = sess["user_paint_u8"]
            erase_u8 = sess["user_erase_u8"]

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

            previews = self._render_session_previews(sess, dress_smooth, dress_strength, need_comp=True, need_mask=True)
            return {"ok": True, "inverted": bool(sess.get("inverted", False)), **previews}
        finally:
            self._end_job()

    def dress_preview_session(self, session_id: str, dress_smooth: bool, dress_strength: float) -> dict:
        sess = self._active_session
        if not sess or sess["id"] != session_id:
            raise ValueError("Сесія застаріла.")
        self._begin_job()
        try:
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
    ) -> tuple[np.ndarray, np.ndarray | None, dict]:
        sess = self._active_session
        if not sess or sess["id"] != session_id:
            raise ValueError("Сесія застаріла.")

        t0 = time.perf_counter()
        self._begin_job()
        try:
            w, h = sess["width"], sess["height"]
            bit_depth = sess["bit_depth"]
            ps_max = 32768.0 if bit_depth == 16 else 255.0
            fast_mode = str(sess["params"].get("speedMode", "fast")).lower() == "fast"

            if progress_cb is not None:
                progress_cb(45, "Фінальна збірка шару...")

            eff_small = self._compute_effective_mask_small(sess)
            eff_full_f = cv2.resize(eff_small, (w, h), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0

            cleaned_rgba = sess["cleaned_base_rgba"]
            cleaned_f32 = cleaned_rgba[:, :, :3].astype(np.float32) * (1.0 / ps_max)
            base_alpha_f32 = cleaned_rgba[:, :, 3].astype(np.float32) * (1.0 / ps_max)

            # Heal any user-painted brush spots that were outside the initial AI auto_mask
            extra_paint_s = np.maximum(0, sess["user_paint_u8"].astype(np.int16) - sess["auto_mask_small_u8"].astype(np.int16))
            extra_paint_s[sess["user_erase_u8"] > 128] = 0
            if np.any(extra_paint_s > 64):
                if progress_cb is not None:
                    progress_cb(60, "Дочищаємо домальовані пензлем зони...")
                extra_full = (cv2.resize(extra_paint_s.astype(np.uint8), (w, h), interpolation=cv2.INTER_LINEAR) > 64).astype(np.uint8)
                cur_rgb_u8 = np.clip(cleaned_f32 * 255.0 + 0.5, 0, 255).astype(np.uint8)
                with self.lock:
                    if fast_mode:
                        healed_f32, _, _ = self._run_fast_inpaint(cur_rgb_u8, extra_full, progress_cb=progress_cb)
                    else:
                        self._ensure_models_loaded(need_matting=False, need_lama=True, progress_cb=progress_cb)
                        healed_f32, _ = self._run_lama_tiles(cur_rgb_u8, extra_full, progress_cb=progress_cb)
                if healed_f32 is not None:
                    p_soft = cv2.GaussianBlur(extra_full.astype(np.float32), (11, 11), 0)[:, :, None]
                    cleaned_f32 = cleaned_f32 * (1.0 - p_soft) + healed_f32 * p_soft
                    np.maximum(base_alpha_f32, p_soft[:, :, 0], out=base_alpha_f32)

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
            combined_alpha_f = np.clip(combined_alpha_f, 0.0, 1.0)

            out_rgba = np.empty((h, w, 4), dtype=np.uint16 if bit_depth == 16 else np.uint8)
            cleaned_f32 *= ps_max
            np.round(cleaned_f32, out=cleaned_f32)
            np.clip(cleaned_f32, 0, ps_max, out=cleaned_f32)
            out_rgba[:, :, :3] = cleaned_f32.astype(out_rgba.dtype)

            layer_mask_u8 = None
            if make_mask:
                # Opaque pixels over cleaned areas, plus explicit Layer Mask matching user's green/red mask!
                out_rgba[:, :, 3] = int(ps_max)
                layer_mask_u8 = np.clip(np.round(combined_alpha_f * 255.0), 0, 255).astype(np.uint8)
            else:
                alpha_out = combined_alpha_f * ps_max
                np.round(alpha_out, out=alpha_out)
                np.clip(alpha_out, 0, ps_max, out=alpha_out)
                out_rgba[:, :, 3] = alpha_out.astype(out_rgba.dtype)

            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            changed_px = int((combined_alpha_f > 0.05).sum())
            stats = {
                "elapsed_ms": elapsed_ms,
                "changed_px": changed_px,
                "make_mask": bool(make_mask),
                "dress_smooth": bool(dress_smooth),
                "blend": float(blend),
                "gpu": self.gpu_name,
                "provider": self.provider_name,
            }
            return out_rgba, layer_mask_u8, stats
        finally:
            self._end_job()

