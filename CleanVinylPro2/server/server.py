from contextlib import asynccontextmanager
import json
import os
import re
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

import cvpaths

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# AI models: the shared folder named in folders.ini (MODELS_DIR), otherwise server/models as before
MODELS_DIR = cvpaths.resolve_models_dir()
LEGACY_PRESETS_PATH = os.path.join(BASE_DIR, "presets.json")
DEFAULTS_PRESETS_PATH = os.path.join(BASE_DIR, "presets_defaults.json")


def _resolve_user_data_dir() -> str:
    env_dir = os.environ.get("CLEANVINYL_DATA_DIR", "").strip()
    if env_dir:
        return env_dir
    if sys.platform == "win32":
        root = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(root, "CleanVinylPro2")
    return os.path.join(os.path.expanduser("~"), ".cleanvinylpro2")


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

from engine import CleanVinylEngine, DEFAULT_IDLE_UNLOAD_SEC

APP_ID = "cleanvinylpro2"  # tells this program apart from the original Clean Vinyl Pro (port 18745)
APP_PORT = 18746
APP_VERSION = "4.12.0"
# Settings written by plugin builds older than this schema still carry the former 30 s idle-unload default
SETTINGS_SCHEMA_IDLE_120 = 5
LEGACY_IDLE_UNLOAD_SEC = 30.0

ENGINE = None
ENGINE_ERROR = None

PROGRESS_LOCK = threading.Lock()
PROGRESS_STORE: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    eng = get_engine()
    idle_str = "вимкнено" if (eng and eng.idle_unload_sec <= 0) else f"{int(eng.idle_unload_sec)} с" if eng else f"{int(DEFAULT_IDLE_UNLOAD_SEC)} с"
    print("======================================================", flush=True)
    print(f"  Clean Vinyl Pro v{APP_VERSION} — Локальний AI GPU сервер", flush=True)
    print(f"  Адреса: http://127.0.0.1:{APP_PORT}", flush=True)
    print(f"  Автовивантаження моделей з GPU/ОЗУ: {idle_str}", flush=True)
    print(f"  AI-моделі: {MODELS_DIR}", flush=True)
    print("======================================================", flush=True)
    if eng is None:
        print(f"[УВАГА] Не вдалося ініціалізувати AI-рушій: {ENGINE_ERROR}", flush=True)
    yield


app = FastAPI(title="Clean Vinyl Pro Local GPU Server", version=APP_VERSION, lifespan=lifespan)
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


# ----------------------------------------------------------------------------------------------------------------------
# Backups of the settings. Everything the plugin remembers (the presets and the settings snapshot) is written into
# one JSON file in <program folder>/backup - a folder that stays where it is when Photoshop is reinstalled and that
# the owner can copy to another disk. The plugin itself may not write outside its own data folder.
BACKUP_DIR_NAME = "backup"
BACKUP_FILE_PREFIX = "CleanVinylPro2_backup_"
BACKUP_KIND = "cleanvinylpro2-settings-backup"
BACKUP_FORMAT = 1
BACKUP_MAX_BYTES = 8 * 1024 * 1024   # a real backup is a few dozen KB
BACKUP_LIST_MAX = 200                # newest files looked at when the folder is listed
BACKUP_AUTO_KEEP = 10                # copies made automatically before a restore: only the newest are kept


def _backup_dir() -> str:
    env_dir = os.environ.get("CLEANVINYL_BACKUP_DIR", "").strip()
    return env_dir or os.path.join(cvpaths.app_root(), BACKUP_DIR_NAME)


def _backup_summary(path: str) -> dict | None:
    """What a backup file holds, or None when the file is not a backup of this program."""
    try:
        size = os.path.getsize(path)
        if size <= 0 or size > BACKUP_MAX_BYTES:
            return None
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except Exception:
        return None
    if not isinstance(data, dict) or data.get("kind") != BACKUP_KIND:
        return None
    presets, settings = data.get("presets"), data.get("settings")
    if not isinstance(presets, list) or not presets or not isinstance(settings, dict):
        return None
    if not all(isinstance(x, dict) and x.get("id") and isinstance(x.get("cfg"), dict) for x in presets):
        return None
    saved_at = data.get("saved_at")
    if not isinstance(saved_at, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", saved_at):
        saved_at = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(os.path.getmtime(path)))
    return {
        "file": os.path.basename(path),
        "saved_at": saved_at,
        "version": str(data.get("version") or ""),
        "label": str(data.get("label") or ""),
        "presets": len(presets),
        "user_presets": sum(1 for x in presets if not x.get("builtin")),
        "size": size,
    }


def _backup_files(folder: str) -> list:
    """*.json files of the backup folder, newest first (by the time the file was written)."""
    try:
        names = [n for n in os.listdir(folder) if n.lower().endswith(".json")]
    except OSError:
        return []
    stamped = []
    for n in names:
        full = os.path.join(folder, n)
        try:
            if os.path.isfile(full):
                stamped.append((os.path.getmtime(full), n))
        except OSError:
            pass
    stamped.sort(reverse=True)
    return [n for _, n in stamped[:BACKUP_LIST_MAX]]


def _prune_auto_backups(folder: str, label: str) -> None:
    """Keeps the newest BACKUP_AUTO_KEEP files the program made by itself under `label`; files made by the owner stay."""
    mine = [n for n in _backup_files(folder) if n.startswith(BACKUP_FILE_PREFIX) and n.endswith("_" + label + ".json")]
    for n in mine[BACKUP_AUTO_KEEP:]:
        try:
            os.remove(os.path.join(folder, n))
        except OSError:
            pass


def _idle_unload_from_settings(data, default_sec: float = DEFAULT_IDLE_UNLOAD_SEC) -> float:
    """
    Idle-unload delay stored in a settings snapshot.
    Snapshots saved before schema 5 always contain the old default (30 s) even if the user never touched the
    option, so that one value is treated as "default" and follows the new default (2 minutes). Any other
    value, and every value saved by a schema >= 5 plugin (including an explicit 30 s), is used as is.
    """
    if not isinstance(data, dict) or "idleUnloadSec" not in data:
        return default_sec
    sec = max(0.0, float(data["idleUnloadSec"]))
    try:
        schema = int(data.get("schemaVersion") or 0)
    except (TypeError, ValueError):
        schema = 0
    if schema < SETTINGS_SCHEMA_IDLE_120 and sec == LEGACY_IDLE_UNLOAD_SEC:
        return default_sec
    return sec


def _read_saved_idle_unload(default_sec: float = DEFAULT_IDLE_UNLOAD_SEC) -> float:
    sp = _user_settings_path()
    if os.path.exists(sp):
        try:
            with open(sp, "r", encoding="utf-8") as f:
                data = json.load(f)
            return _idle_unload_from_settings(data, default_sec)
        except Exception:
            pass
    return default_sec


def _packet_array(raw: bytes, offset: int, shape: tuple, dtype):
    """
    Pixel block of a binary request as a numpy array WITHOUT copying it out of the request body
    (the old `raw[a:b]` slice duplicated up to 190 MB per request). Returns None when the body is too short.
    A 16-bit block that starts at an odd byte offset is still copied so the array stays aligned.
    """
    dt = np.dtype(dtype)
    count = 1
    for dim in shape:
        count *= int(dim)
    nbytes = count * dt.itemsize
    if offset < 0 or offset + nbytes > len(raw):
        return None
    if offset % dt.itemsize == 0:
        return np.frombuffer(raw, dtype=dt, count=count, offset=offset).reshape(shape)
    return np.frombuffer(raw[offset : offset + nbytes], dtype=dt).reshape(shape)


def _binary_response(meta: dict, *arrays) -> Response:
    """[uint32 meta length][meta JSON][raw pixels ...] assembled with a single copy of the pixels."""
    resp_meta = json.dumps(meta, ensure_ascii=False).encode("utf-8")
    parts = [struct.pack("<I", len(resp_meta)), resp_meta]
    parts += [np.ascontiguousarray(a).data for a in arrays if a is not None]
    return Response(content=b"".join(parts), media_type="application/octet-stream")


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
            ENGINE = CleanVinylEngine(MODELS_DIR, idle_unload_sec=_read_saved_idle_unload())
        except Exception as exc:
            hint = cvpaths.models_problem()
            ENGINE_ERROR = str(exc) + ((" " + hint) if hint else "")
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
                "app": APP_ID,
                "version": APP_VERSION,
                "install_dir": install_dir,
                "models_dir": MODELS_DIR,
                "backup_dir": _backup_dir(),
                "error": ENGINE_ERROR or "Моделі не завантажені",
            },
        )
    return {
        "ok": True,
        "status": "ready",
        "app": APP_ID,
        "version": APP_VERSION,
        "install_dir": install_dir,
        "models_dir": MODELS_DIR,
        "backup_dir": _backup_dir(),
        "gpu": eng.gpu_name,
        "provider": eng.provider_name,
        "gpu_error": eng.gpu_error,
        # what the processor computed in its last run although a GPU session exists ("lama" / "matting" -> why)
        "cpu_fallback": dict(getattr(eng, "cpu_fallback", {}) or {}),
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
                eng.set_idle_unload(_idle_unload_from_settings(data))
            except Exception:
                pass
    return {"ok": True}


@app.post("/backup/save")
async def backup_save(request: Request):
    """
    Body: {"presets": [...], "settings": {...}, "label": ""} - what the plugin holds right now. Written as one file
    into the backup folder. "label" (letters, digits, "-") marks a copy the program makes by itself, for example
    "before-restore"; only the newest of those are kept.
    """
    raw = await request.body()
    if len(raw) > BACKUP_MAX_BYTES:
        return JSONResponse(status_code=413, content={"ok": False, "error": "Завеликий обсяг налаштувань для бекапа."})
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Очікується JSON."})
    presets = data.get("presets") if isinstance(data, dict) else None
    settings = data.get("settings") if isinstance(data, dict) else None
    if not isinstance(presets, list) or not presets or not isinstance(settings, dict):
        return JSONResponse(status_code=400, content={"ok": False, "error": "У запиті немає пресетів або налаштувань."})
    if not all(isinstance(x, dict) and x.get("id") and isinstance(x.get("cfg"), dict) for x in presets):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Список пресетів пошкоджено."})
    label = re.sub(r"[^A-Za-z0-9-]", "", str(data.get("label") or ""))[:24]

    folder = _backup_dir()
    now = time.localtime()
    stem = BACKUP_FILE_PREFIX + time.strftime("%Y-%m-%d_%H-%M-%S", now)
    try:
        os.makedirs(folder, exist_ok=True)
        name, n = stem + (("_" + label) if label else "") + ".json", 1
        while os.path.exists(os.path.join(folder, name)):   # two backups within one second
            n += 1
            name = f"{stem}-{n}" + (("_" + label) if label else "") + ".json"
        _atomic_write_json(os.path.join(folder, name), {
            "kind": BACKUP_KIND,
            "format": BACKUP_FORMAT,
            "app": APP_ID,
            "version": APP_VERSION,
            "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S", now),
            "label": label,
            "presets": presets,
            "settings": settings,
        })
        if label:
            _prune_auto_backups(folder, label)
    except OSError as exc:
        return JSONResponse(status_code=500, content={"ok": False, "error": f"Не вдалося записати бекап у «{folder}»: {exc}"})
    return {"ok": True, "file": name, "path": os.path.join(folder, name), "folder": folder,
            "presets": len(presets), "user_presets": sum(1 for x in presets if not x.get("builtin"))}


@app.get("/backup/list")
def backup_list():
    """The backups found in the backup folder, newest first. Files that are not backups of this program are skipped."""
    folder = _backup_dir()
    found = [s for s in (_backup_summary(os.path.join(folder, n)) for n in _backup_files(folder)) if s]
    found.sort(key=lambda s: s["saved_at"], reverse=True)
    return {"ok": True, "folder": folder, "backups": found}


@app.post("/backup/read")
async def backup_read(request: Request):
    """Body: {"file": "<name from /backup/list>"} -> the presets and the settings stored in that backup."""
    try:
        body = await request.json()
    except Exception:
        body = None
    name = body.get("file") if isinstance(body, dict) else None
    folder = _backup_dir()
    # Only a file that really lies in the backup folder, named exactly as the folder lists it (never a path)
    if not isinstance(name, str) or not name or name not in _backup_files(folder):
        return JSONResponse(status_code=404, content={"ok": False, "error": "Такого бекапа в папці немає."})
    path = os.path.join(folder, name)
    summary = _backup_summary(path)
    if summary is None:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Файл не є бекапом налаштувань цієї програми або пошкоджений."})
    with open(path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    return {"ok": True, **summary, "path": path, "folder": folder, "presets_list": data["presets"], "settings": data["settings"]}


@app.post("/backup/open-folder")
async def backup_open_folder():
    """Shows the backup folder in Windows Explorer (the plugin cannot open a folder by itself)."""
    folder = _backup_dir()
    opened = False
    try:
        os.makedirs(folder, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(folder)  # noqa: S606 - a folder of this program, opened in Explorer
            opened = True
    except Exception:
        opened = False
    return {"ok": True, "folder": folder, "opened": opened}


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

        img_arr = _packet_array(raw, offset, (h, w, channels), dtype)
        if img_arr is None:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "error": f"Pixel buffer size mismatch: got {max(0, len(raw) - offset)}, expected {img_byte_len}"},
            )
        cur_offset = offset + img_byte_len

        selection_alpha = None
        if has_selection:
            sel_bits = int(meta.get("selectionBitDepth", bit_depth))
            sel_dtype = np.uint16 if sel_bits == 16 else np.uint8
            sel_bps = 2 if sel_bits == 16 else 1
            sel_byte_len = w * h * sel_bps
            selection_alpha = _packet_array(raw, cur_offset, (h, w), sel_dtype)
            cur_offset += sel_byte_len

        custom_fg_mask = None
        if has_custom_protect:
            prot_byte_len = w * h
            custom_fg_mask = _packet_array(raw, cur_offset, (h, w), np.uint8)
            cur_offset += prot_byte_len

        custom_heal_mask = None
        if has_custom_heal:
            mw = int(meta.get("healMaskWidth", w))
            mh = int(meta.get("healMaskHeight", h))
            heal_byte_len = mw * mh
            m_arr = _packet_array(raw, cur_offset, (mh, mw), np.uint8)
            if m_arr is not None:
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

        return _binary_response(
            {
                "ok": True,
                "width": w,
                "height": h,
                "channels": 4,
                "bitDepth": bit_depth,
                "stats": stats,
            },
            out_rgba,
        )

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

        img_arr = _packet_array(raw, offset, (h, w, channels), dtype)
        if img_arr is None:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "error": f"Pixel buffer size mismatch: got {max(0, len(raw) - offset)}, expected {img_byte_len}"},
            )

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

        return _binary_response(
            {
                "ok": True,
                "width": w,
                "height": h,
                "channels": 1,
                "bitDepth": 8,
                "maskType": mask_type,
                "stats": stats,
            },
            mask_u8,
        )

    except Exception as exc:
        _set_progress(job_id, 0, f"Помилка: {exc}", done=True)
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})


@app.post("/extend-canvas")
async def extend_canvas(request: Request):
    """
    Print format 5:7. Request: the usual packet [meta length][meta JSON][pixels] with params.ratioShort / ratioLong.
    Answer: the same kind of packet with an RGBA picture of the NEW canvas size (opaque in the added strips,
    transparent over the photo), or plain JSON {"ok": true, "unchanged": true, "reason": ...} when there is
    nothing to add.
    """
    eng = get_engine()
    if eng is None:
        return JSONResponse(status_code=503, content={"ok": False, "error": ENGINE_ERROR or "Engine not ready"})

    job_id = None
    try:
        raw = await request.body()
        if len(raw) < 8:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Empty payload"})

        meta_len = struct.unpack_from("<I", raw, 0)[0]
        meta = json.loads(raw[4 : 4 + meta_len].decode("utf-8"))
        w = int(meta["width"])
        h = int(meta["height"])
        channels = int(meta.get("channels", 4))
        bit_depth = int(meta.get("bitDepth", 8))
        job_id = meta.get("jobId") or None
        params = meta.get("params", {})

        _set_progress(job_id, 11, "Отримано пікселі...", done=False)
        dtype = np.uint16 if bit_depth == 16 else np.uint8
        img_arr = _packet_array(raw, 4 + meta_len, (h, w, channels), dtype)
        if img_arr is None:
            expected = w * h * channels * (2 if bit_depth == 16 else 1)
            return JSONResponse(
                status_code=400,
                content={"ok": False, "error": f"Pixel buffer size mismatch: got {max(0, len(raw) - 4 - meta_len)}, expected {expected}"},
            )

        def _pcb(pct: int, stage: str):
            _set_progress(job_id, pct, stage, done=False)

        out_rgba, info = await run_in_threadpool(eng.extend_canvas, img_arr, bit_depth, params, _pcb)
        _set_progress(job_id, 91, "Відправка результату в Photoshop...", done=True)
        if out_rgba is None:
            return JSONResponse(content={"ok": True, "unchanged": True, "reason": info.get("reason", ""), "info": info})

        return _binary_response(
            {
                "ok": True,
                "width": int(info["new_w"]),
                "height": int(info["new_h"]),
                "channels": 4,
                "bitDepth": bit_depth,
                "left": int(info["left"]),
                "top": int(info["top"]),
                "origWidth": w,
                "origHeight": h,
                "subjectAtEdge": bool(info.get("subject_at_edge", False)),
                "info": info,
            },
            out_rgba,
        )

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
        # Automatic preset: parameters by kind of frame; the engine looks at the frame and uses the suitable set
        scene_presets = meta.get("scenePresets")
        if not isinstance(scene_presets, dict):
            scene_presets = None

        _set_progress(job_id, 10, "Сканування людини та фону...", done=False)

        dtype = np.uint16 if bit_depth == 16 else np.uint8
        bps = 2 if bit_depth == 16 else 1
        img_byte_len = w * h * channels * bps
        offset = 4 + meta_len

        img_arr = _packet_array(raw, offset, (h, w, channels), dtype)
        if img_arr is None:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "error": f"Pixel buffer size mismatch: got {max(0, len(raw) - offset)}, expected {img_byte_len}"},
            )
        cur_offset = offset + img_byte_len

        selection_alpha = None
        if has_selection:
            sel_bits = int(meta.get("selectionBitDepth", bit_depth))
            sel_dtype = np.uint16 if sel_bits == 16 else np.uint8
            sel_bps = 2 if sel_bits == 16 else 1
            sel_byte_len = w * h * sel_bps
            selection_alpha = _packet_array(raw, cur_offset, (h, w), sel_dtype)

        def _pcb(pct: int, stage: str):
            _set_progress(job_id, pct, stage, done=False)

        res = await run_in_threadpool(eng.start_session, img_arr, bit_depth, params, selection_alpha, _pcb, scene_presets)
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
        # quick: update only the preview; the real frame is computed later (the answer repeats "quick")
        quick = bool(body.get("quick", False))
        # background: the window asks by itself for the exact picture; such a run gives way to every other request
        # of the window and then answers {"ok": true, "superseded": true} (see engine.recompute_session)
        background = bool(body.get("background", False))
        job_id = body.get("jobId") or None

        def _pcb(pct: int, stage: str):
            _set_progress(job_id, pct, stage, done=False)

        res = await run_in_threadpool(eng.recompute_session, session_id, params, preserve_edits, _pcb, quick, background)
        gave_way = bool(res.get("superseded") or res.get("skipped"))
        _set_progress(job_id, 0 if gave_way else 100, "" if gave_way else "Оновлено!", done=True)
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
        # "softness": the edge of the brush / eraser, 0 (hard) .. 1 (soft); a request without it means soft
        softness = body.get("softness")
        res = await run_in_threadpool(
            eng.edit_session_mask,
            str(body.get("session_id", "")),
            str(body.get("op", "stroke")),
            body.get("points"),
            float(body.get("radius_px", 24.0)),
            bool(body.get("erase", True)),
            bool(body.get("dressSmooth", False)),
            float(body.get("dressStrength", 45.0)),
            None if softness is None else float(softness),
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
        # The settings on the sliders at the moment of Apply: the layer is always made for exactly these
        params = body.get("params")
        if not isinstance(params, dict):
            params = None
        # A background recompute is on its way for these very settings: wait for it instead of stopping it
        follow_background = bool(body.get("followBackground", False))
        job_id = body.get("jobId") or None

        def _pcb(pct: int, stage: str):
            _set_progress(job_id, pct, stage, done=False)

        out_rgba, layer_mask_u8, stats = await run_in_threadpool(
            eng.apply_session, session_id, blend, make_mask, dress_smooth, dress_strength, _pcb, params, follow_background
        )
        _set_progress(job_id, 95, "Запис шару у Photoshop...", done=True)

        h, w = out_rgba.shape[:2]
        bit_depth = 16 if out_rgba.dtype == np.uint16 else 8
        return _binary_response(
            {
                "ok": True,
                "width": w,
                "height": h,
                "channels": 4,
                "bitDepth": bit_depth,
                "hasLayerMask": layer_mask_u8 is not None,
                "stats": stats,
            },
            out_rgba,
            layer_mask_u8,
        )
    except Exception as exc:
        _set_progress(job_id, 0, f"Помилка: {exc}", done=True)
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})


@app.post("/session/stop-background")
async def session_stop_background(request: Request):
    """
    The user took hold of a slider of the big window: the exact picture that is being computed in the background
    will not be wanted. That run stops at its next safe place (its own request answers "superseded").
    """
    eng = get_engine()
    if eng is None:
        return {"ok": True, "stopped": False}
    try:
        body = await request.json()
        sid = str(body.get("session_id", ""))
    except Exception:
        sid = ""
    return eng.stop_background(sid)


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
    uvicorn.run(app, host="127.0.0.1", port=APP_PORT, log_level="info", access_log=False)

