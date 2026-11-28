from contextlib import asynccontextmanager
import json
import os
import struct
import sys
import threading
import time
import traceback
import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")
LEGACY_PRESETS_PATH = os.path.join(BASE_DIR, "presets.json")
DEFAULTS_PRESETS_PATH = os.path.join(BASE_DIR, "presets_defaults.json")


def _resolve_user_data_dir() -> str:
    env_dir = os.environ.get("CLEANVINYL_DATA_DIR", "").strip()
    if env_dir:
        return env_dir
    if sys.platform == "win32":
        root = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(root, "CleanVinylPro")
    return os.path.join(os.path.expanduser("~"), ".cleanvinylpro")


def _atomic_write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# Safe logging when started via Windows pythonw.exe (where stdout/stderr are None)
if sys.stdout is None:
    sys.stdout = open(os.path.join(BASE_DIR, "server.log"), "a", encoding="utf-8", buffering=1)
elif hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr is None:
    sys.stderr = sys.stdout
elif hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from engine import CleanVinylEngine

ENGINE = None
ENGINE_ERROR = None

PROGRESS_LOCK = threading.Lock()
PROGRESS_STORE: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    eng = get_engine()
    idle_str = "вимкнено" if (eng and eng.idle_unload_sec <= 0) else f"{int(eng.idle_unload_sec)} с" if eng else "30 с"
    print("======================================================", flush=True)
    print("  Clean Vinyl Pro v3.2.1 — Локальний AI GPU сервер", flush=True)
    print("  Адреса: http://127.0.0.1:18745", flush=True)
    print(f"  Автовивантаження моделей з GPU/ОЗУ: {idle_str}", flush=True)
    print("======================================================", flush=True)
    if eng is None:
        print(f"[УВАГА] Не вдалося ініціалізувати AI-рушій: {ENGINE_ERROR}", flush=True)
    yield


app = FastAPI(title="Clean Vinyl Pro Local GPU Server", version="3.2.1", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _user_presets_path() -> str:
    return os.path.join(_resolve_user_data_dir(), "user_presets.json")


def _user_settings_path() -> str:
    return os.path.join(_resolve_user_data_dir(), "user_settings.json")


def _read_saved_idle_unload(default_sec: float = 30.0) -> float:
    sp = _user_settings_path()
    if os.path.exists(sp):
        try:
            with open(sp, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "idleUnloadSec" in data:
                return max(0.0, float(data["idleUnloadSec"]))
        except Exception:
            pass
    return default_sec


def _set_progress(job_id: str | None, pct: int, stage: str, done: bool = False):
    if not job_id:
        return
    now = time.monotonic()
    with PROGRESS_LOCK:
        PROGRESS_STORE[job_id] = {
            "pct": int(max(0, min(100, pct))),
            "stage": stage,
            "done": bool(done),
            "ts": now,
        }
        if len(PROGRESS_STORE) > 24:
            stale = [k for k, v in PROGRESS_STORE.items() if now - v.get("ts", 0.0) > 120.0]
            for k in stale:
                PROGRESS_STORE.pop(k, None)


def get_engine():
    global ENGINE, ENGINE_ERROR
    if ENGINE is None and ENGINE_ERROR is None:
        try:
            ENGINE = CleanVinylEngine(MODELS_DIR, idle_unload_sec=_read_saved_idle_unload(30.0))
        except Exception as exc:
            ENGINE_ERROR = str(exc)
    return ENGINE


@app.get("/health")
def health():
    eng = get_engine()
    install_dir = os.path.dirname(BASE_DIR)
    if eng is None:
        return JSONResponse(
            status_code=200,
            content={
                "ok": False,
                "status": "error",
                "version": "3.2.1",
                "install_dir": install_dir,
                "error": ENGINE_ERROR or "Моделі не завантажені",
            },
        )
    return {
        "ok": True,
        "status": "ready",
        "version": "3.2.1",
        "install_dir": install_dir,
        "gpu": eng.gpu_name,
        "provider": eng.provider_name,
        "gpu_error": eng.gpu_error,
        "matting_model": eng.matting_kind,
        "models_loaded": eng.is_loaded,
        "idle_unload_sec": eng.idle_unload_sec,
    }


@app.get("/progress")
def get_progress(job_id: str = ""):
    if not job_id:
        return {"ok": False, "pct": 0, "stage": "", "done": False}
    with PROGRESS_LOCK:
        entry = PROGRESS_STORE.get(job_id)
        if not entry:
            return {"ok": False, "pct": 0, "stage": "", "done": False}
        return {
            "ok": True,
            "pct": entry["pct"],
            "stage": entry["stage"],
            "done": entry["done"],
        }


@app.post("/unload")
async def unload_now():
    eng = get_engine()
    if eng is None:
        return {"ok": False, "unloaded": False}
    unloaded = await run_in_threadpool(eng.unload_models, "запит API")
    return {"ok": True, "unloaded": bool(unloaded), "models_loaded": eng.is_loaded}


@app.get("/presets")
def get_presets():
    up = _user_presets_path()
    if os.path.exists(up):
        try:
            with open(up, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and len(data) > 0:
                return {"source": "user", "presets": data}
        except Exception:
            pass
    if os.path.exists(LEGACY_PRESETS_PATH):
        try:
            with open(LEGACY_PRESETS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and len(data) > 0:
                try:
                    _atomic_write_json(up, data)
                except Exception:
                    pass
                return {"source": "user", "presets": data}
        except Exception:
            pass
    if os.path.exists(DEFAULTS_PRESETS_PATH):
        try:
            with open(DEFAULTS_PRESETS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return {"source": "defaults", "presets": data}
        except Exception:
            pass
    return {"source": "defaults", "presets": []}


@app.post("/presets")
async def save_presets(request: Request):
    data = await request.json()
    if isinstance(data, dict) and isinstance(data.get("presets"), list):
        data = data["presets"]
    if not isinstance(data, list):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Expected list"})
    _atomic_write_json(_user_presets_path(), data)
    try:
        _atomic_write_json(LEGACY_PRESETS_PATH, data)
    except Exception:
        pass
    return {"ok": True, "count": len(data)}


@app.get("/settings")
def get_settings():
    sp = _user_settings_path()
    if os.path.exists(sp):
        try:
            with open(sp, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return {"ok": True, "exists": True, "settings": data}
        except Exception:
            pass
    return {"ok": True, "exists": False, "settings": {}}


@app.post("/settings")
async def save_settings(request: Request):
    data = await request.json()
    if not isinstance(data, dict):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Expected dict"})
    _atomic_write_json(_user_settings_path(), data)
    if "idleUnloadSec" in data:
        eng = get_engine()
        if eng is not None:
            try:
                eng.set_idle_unload(float(data["idleUnloadSec"]))
            except Exception:
                pass
    return {"ok": True}


@app.post("/process")
async def process_image(request: Request):
    eng = get_engine()
    if eng is None:
        return JSONResponse(status_code=503, content={"ok": False, "error": ENGINE_ERROR or "Engine not ready"})

    job_id = None
    try:
        raw = await request.body()
        if len(raw) < 8:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Empty payload"})

        meta_len = struct.unpack_from("<I", raw, 0)[0]
        meta_bytes = raw[4 : 4 + meta_len]
        meta = json.loads(meta_bytes.decode("utf-8"))

        w = int(meta["width"])
        h = int(meta["height"])
        channels = int(meta.get("channels", 4))
        bit_depth = int(meta.get("bitDepth", 8))
        has_selection = bool(meta.get("hasSelection", False))
        has_custom_protect = bool(meta.get("hasCustomProtect", False))
        has_custom_heal = bool(meta.get("hasCustomHeal", False))
        job_id = meta.get("jobId") or None
        params = meta.get("params", {})

        _set_progress(job_id, 11, "Отримано пікселі, старт обробки...", done=False)

        dtype = np.uint16 if bit_depth == 16 else np.uint8
        bps = 2 if bit_depth == 16 else 1
        img_byte_len = w * h * channels * bps
        offset = 4 + meta_len

        img_buf = raw[offset : offset + img_byte_len]
        if len(img_buf) != img_byte_len:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "error": f"Pixel buffer size mismatch: got {len(img_buf)}, expected {img_byte_len}"},
            )

        img_arr = np.frombuffer(img_buf, dtype=dtype).reshape((h, w, channels))
        cur_offset = offset + img_byte_len

        selection_alpha = None
        if has_selection:
            sel_bits = int(meta.get("selectionBitDepth", bit_depth))
            sel_dtype = np.uint16 if sel_bits == 16 else np.uint8
            sel_bps = 2 if sel_bits == 16 else 1
            sel_byte_len = w * h * sel_bps
            sel_buf = raw[cur_offset : cur_offset + sel_byte_len]
            if len(sel_buf) == sel_byte_len:
                selection_alpha = np.frombuffer(sel_buf, dtype=sel_dtype).reshape((h, w))
            cur_offset += sel_byte_len

        custom_fg_mask = None
        if has_custom_protect:
            prot_byte_len = w * h
            prot_buf = raw[cur_offset : cur_offset + prot_byte_len]
            if len(prot_buf) == prot_byte_len:
                custom_fg_mask = np.frombuffer(prot_buf, dtype=np.uint8).reshape((h, w))
            cur_offset += prot_byte_len

        custom_heal_mask = None
        if has_custom_heal:
            mw = int(meta.get("healMaskWidth", w))
            mh = int(meta.get("healMaskHeight", h))
            heal_byte_len = mw * mh
            heal_buf = raw[cur_offset : cur_offset + heal_byte_len]
            if len(heal_buf) == heal_byte_len:
                m_arr = np.frombuffer(heal_buf, dtype=np.uint8).reshape((mh, mw))
                if mw != w or mh != h:
                    custom_heal_mask = cv2.resize(m_arr, (w, h), interpolation=cv2.INTER_LINEAR)
                else:
                    custom_heal_mask = m_arr
            cur_offset += heal_byte_len

        def _pcb(pct: int, stage: str):
            _set_progress(job_id, pct, stage, done=False)

        out_rgba, stats = await run_in_threadpool(
            eng.process,
            img_arr,
            bit_depth,
            params,
            selection_alpha,
            custom_fg_mask,
            custom_heal_mask,
            _pcb,
        )
        _set_progress(job_id, 91, "Відправка результату в Photoshop...", done=True)

        resp_meta = json.dumps(
            {
                "ok": True,
                "width": w,
                "height": h,
                "channels": 4,
                "bitDepth": bit_depth,
                "stats": stats,
            },
            ensure_ascii=False,
        ).encode("utf-8")

        header = struct.pack("<I", len(resp_meta))
        payload = header + resp_meta + out_rgba.tobytes()
        return Response(content=payload, media_type="application/octet-stream")

    except Exception as exc:
        _set_progress(job_id, 0, f"Помилка: {exc}", done=True)
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})


@app.post("/preview-mask")
async def preview_mask(request: Request):
    eng = get_engine()
    if eng is None:
        return JSONResponse(status_code=503, content={"ok": False, "error": ENGINE_ERROR or "Engine not ready"})

    job_id = None
    try:
        raw = await request.body()
        if len(raw) < 8:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Empty payload"})

        meta_len = struct.unpack_from("<I", raw, 0)[0]
        meta_bytes = raw[4 : 4 + meta_len]
        meta = json.loads(meta_bytes.decode("utf-8"))

        w = int(meta["width"])
        h = int(meta["height"])
        channels = int(meta.get("channels", 4))
        bit_depth = int(meta.get("bitDepth", 8))
        mask_type = str(meta.get("maskType", "action")).lower()
        job_id = meta.get("jobId") or None
        params = meta.get("params", {})

        _set_progress(job_id, 11, "Підготовка шару для аналізу...", done=False)

        dtype = np.uint16 if bit_depth == 16 else np.uint8
        bps = 2 if bit_depth == 16 else 1
        img_byte_len = w * h * channels * bps
        offset = 4 + meta_len

        img_buf = raw[offset : offset + img_byte_len]
        if len(img_buf) != img_byte_len:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "error": f"Pixel buffer size mismatch: got {len(img_buf)}, expected {img_byte_len}"},
            )

        img_arr = np.frombuffer(img_buf, dtype=dtype).reshape((h, w, channels))

        def _pcb(pct: int, stage: str):
            _set_progress(job_id, pct, stage, done=False)

        preview_fn = eng.preview_protection_mask if mask_type == "protection" else eng.preview_action_mask
        mask_u8, stats = await run_in_threadpool(
            preview_fn,
            img_arr,
            bit_depth,
            params,
            _pcb,
        )
        _set_progress(job_id, 91, "Передача зеленої маски..." if mask_type != "protection" else "Передача червоної маски...", done=True)

        resp_meta = json.dumps(
            {
                "ok": True,
                "width": w,
                "height": h,
                "channels": 1,
                "bitDepth": 8,
                "maskType": mask_type,
                "stats": stats,
            },
            ensure_ascii=False,
        ).encode("utf-8")

        header = struct.pack("<I", len(resp_meta))
        payload = header + resp_meta + mask_u8.tobytes()
        return Response(content=payload, media_type="application/octet-stream")

    except Exception as exc:
        _set_progress(job_id, 0, f"Помилка: {exc}", done=True)
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})


@app.post("/session/start")
async def session_start(request: Request):
    eng = get_engine()
    if eng is None:
        return JSONResponse(status_code=503, content={"ok": False, "error": ENGINE_ERROR or "Engine not ready"})

    job_id = None
    try:
        raw = await request.body()
        if len(raw) < 8:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Empty payload"})

        meta_len = struct.unpack_from("<I", raw, 0)[0]
        meta_bytes = raw[4 : 4 + meta_len]
        meta = json.loads(meta_bytes.decode("utf-8"))

        w = int(meta["width"])
        h = int(meta["height"])
        channels = int(meta.get("channels", 4))
        bit_depth = int(meta.get("bitDepth", 8))
        has_selection = bool(meta.get("hasSelection", False))
        job_id = meta.get("jobId") or None
        params = meta.get("params", {})

        _set_progress(job_id, 10, "Сканування людини та фону...", done=False)

        dtype = np.uint16 if bit_depth == 16 else np.uint8
        bps = 2 if bit_depth == 16 else 1
        img_byte_len = w * h * channels * bps
        offset = 4 + meta_len

        img_buf = raw[offset : offset + img_byte_len]
        if len(img_buf) != img_byte_len:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "error": f"Pixel buffer size mismatch: got {len(img_buf)}, expected {img_byte_len}"},
            )
        img_arr = np.frombuffer(img_buf, dtype=dtype).reshape((h, w, channels))
        cur_offset = offset + img_byte_len

        selection_alpha = None
        if has_selection:
            sel_bits = int(meta.get("selectionBitDepth", bit_depth))
            sel_dtype = np.uint16 if sel_bits == 16 else np.uint8
            sel_bps = 2 if sel_bits == 16 else 1
            sel_byte_len = w * h * sel_bps
            sel_buf = raw[cur_offset : cur_offset + sel_byte_len]
            if len(sel_buf) == sel_byte_len:
                selection_alpha = np.frombuffer(sel_buf, dtype=sel_dtype).reshape((h, w))

        def _pcb(pct: int, stage: str):
            _set_progress(job_id, pct, stage, done=False)

        res = await run_in_threadpool(eng.start_session, img_arr, bit_depth, params, selection_alpha, _pcb)
        _set_progress(job_id, 100, "Готово!", done=True)
        return JSONResponse(status_code=200, content=res)
    except Exception as exc:
        _set_progress(job_id, 0, f"Помилка: {exc}", done=True)
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})


@app.post("/session/recompute")
async def session_recompute(request: Request):
    eng = get_engine()
    if eng is None:
        return JSONResponse(status_code=503, content={"ok": False, "error": ENGINE_ERROR or "Engine not ready"})
    job_id = None
    try:
        body = await request.json()
        session_id = str(body.get("session_id", ""))
        params = body.get("params", {})
        preserve_edits = bool(body.get("preserve_edits", True))
        job_id = body.get("jobId") or None

        def _pcb(pct: int, stage: str):
            _set_progress(job_id, pct, stage, done=False)

        res = await run_in_threadpool(eng.recompute_session, session_id, params, preserve_edits, _pcb)
        _set_progress(job_id, 100, "Оновлено!", done=True)
        return JSONResponse(status_code=200, content=res)
    except Exception as exc:
        _set_progress(job_id, 0, f"Помилка: {exc}", done=True)
        return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})


@app.post("/session/mask-edit")
async def session_mask_edit(request: Request):
    eng = get_engine()
    if eng is None:
        return JSONResponse(status_code=503, content={"ok": False, "error": ENGINE_ERROR or "Engine not ready"})
    try:
        body = await request.json()
        res = await run_in_threadpool(
            eng.edit_session_mask,
            str(body.get("session_id", "")),
            str(body.get("op", "stroke")),
            body.get("points"),
            float(body.get("radius_px", 24.0)),
            bool(body.get("erase", True)),
            bool(body.get("dressSmooth", False)),
            float(body.get("dressStrength", 45.0)),
        )
        return JSONResponse(status_code=200, content=res)
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})


@app.post("/session/dress-preview")
async def session_dress_preview(request: Request):
    eng = get_engine()
    if eng is None:
        return JSONResponse(status_code=503, content={"ok": False, "error": ENGINE_ERROR or "Engine not ready"})
    try:
        body = await request.json()
        res = await run_in_threadpool(
            eng.dress_preview_session,
            str(body.get("session_id", "")),
            bool(body.get("dressSmooth", False)),
            float(body.get("dressStrength", 45.0)),
        )
        return JSONResponse(status_code=200, content=res)
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})


@app.post("/session/apply")
async def session_apply(request: Request):
    eng = get_engine()
    if eng is None:
        return JSONResponse(status_code=503, content={"ok": False, "error": ENGINE_ERROR or "Engine not ready"})
    job_id = None
    try:
        body = await request.json()
        session_id = str(body.get("session_id", ""))
        blend = float(body.get("blend", 100.0))
        make_mask = bool(body.get("makeMask", False))
        dress_smooth = bool(body.get("dressSmooth", False))
        dress_strength = float(body.get("dressStrength", 45.0))
        job_id = body.get("jobId") or None

        def _pcb(pct: int, stage: str):
            _set_progress(job_id, pct, stage, done=False)

        out_rgba, layer_mask_u8, stats = await run_in_threadpool(
            eng.apply_session, session_id, blend, make_mask, dress_smooth, dress_strength, _pcb
        )
        _set_progress(job_id, 95, "Запис шару у Photoshop...", done=True)

        h, w = out_rgba.shape[:2]
        bit_depth = 16 if out_rgba.dtype == np.uint16 else 8
        resp_meta = json.dumps(
            {
                "ok": True,
                "width": w,
                "height": h,
                "channels": 4,
                "bitDepth": bit_depth,
                "hasLayerMask": layer_mask_u8 is not None,
                "stats": stats,
            },
            ensure_ascii=False,
        ).encode("utf-8")

        header = struct.pack("<I", len(resp_meta))
        payload = header + resp_meta + out_rgba.tobytes() + (layer_mask_u8.tobytes() if layer_mask_u8 is not None else b"")
        return Response(content=payload, media_type="application/octet-stream")
    except Exception as exc:
        _set_progress(job_id, 0, f"Помилка: {exc}", done=True)
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})


@app.post("/session/close")
async def session_close(request: Request):
    eng = get_engine()
    if eng is None:
        return {"ok": True}
    try:
        body = await request.json()
        sid = body.get("session_id")
    except Exception:
        sid = None
    closed = await run_in_threadpool(eng.close_session, sid)
    return {"ok": True, "closed": bool(closed)}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=18745, log_level="info", access_log=False)

