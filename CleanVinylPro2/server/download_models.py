import os
import shutil
import sys
import urllib.request

import cvpaths

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MODELS = [
    {
        "filename": "bria-rmbg-2.0.onnx",
        "min_mb": 500,
        "urls": [
            "https://github.com/danielgatis/rembg/releases/download/v0.0.0/bria-rmbg-2.0.onnx",
        ],
        "fallback_filename": "rmbg14.onnx",
        "fallback_urls": [
            "https://huggingface.co/briaai/RMBG-1.4/resolve/main/onnx/model.onnx",
        ],
    },
    {
        "filename": "lama_fp32.onnx",
        "min_mb": 180,
        "urls": [
            "https://huggingface.co/Carve/LaMa-ONNX/resolve/main/lama_fp32.onnx",
            "https://huggingface.co/edgetools/lama/resolve/main/lama_fp32.onnx",
            "https://huggingface.co/Gaurox/frameshift-models/resolve/main/lama-onnx/lama_fp32.onnx",
        ],
        "fallback_filename": "lama.onnx",
        "fallback_urls": [
            "https://huggingface.co/opencv/inpainting_lama/resolve/main/inpainting_lama_2025jan.onnx",
        ],
    },
]


def download_file(url: str, dest_path: str) -> bool:
    tmp_path = dest_path + ".part"
    print(f"[Завантаження] {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "CleanVinylPro/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            last_pct = -1
            with open(tmp_path, "wb") as out:
                while True:
                    chunk = resp.read(1024 * 512)
                    if not chunk:
                        break
                    out.write(chunk)
                    done += len(chunk)
                    if total > 0:
                        pct = int(done * 100 / total)
                        if pct != last_pct and (pct % 5 == 0 or pct == 100):
                            mb_done = done / (1024 * 1024)
                            mb_tot = total / (1024 * 1024)
                            print(f"  Прогрес: {pct:3d}% ({mb_done:.1f} / {mb_tot:.1f} MB)", flush=True)
                            last_pct = pct
        os.replace(tmp_path, dest_path)
        return True
    except Exception as exc:
        print(f"  [Помилка завантаження] {exc}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return False


def _wanted(lite_mode: bool) -> list:
    """(file name, download addresses, smallest complete size in MB, stand-in entry or None) for each model."""
    out = []
    for m in MODELS:
        if lite_mode and m["fallback_filename"]:
            out.append((m["fallback_filename"], m["fallback_urls"], cvpaths.MODEL_MIN_MB.get(m["fallback_filename"], 0), None))
        else:
            out.append((m["filename"], m["urls"], m["min_mb"], m))
    return out


def missing_models(models_dir: str, lite_mode: bool = False) -> list:
    """Names of the model files that are not (completely) in models_dir."""
    return [name for name, _urls, _mb, _m in _wanted(lite_mode) if not cvpaths.model_ok(models_dir, name)]


def find_copy(name: str, sources) -> str:
    """A complete copy of the file in one of the folders, or ''."""
    for folder in sources or ():
        if cvpaths.model_ok(folder, name):
            return os.path.join(folder, name)
    return ""


def copy_file(src: str, dest_path: str) -> bool:
    tmp_path = dest_path + ".part"
    print(f"[Копіювання] {src}")
    try:
        total = os.path.getsize(src)
        done, last_pct = 0, -1
        with open(src, "rb") as fin, open(tmp_path, "wb") as out:
            while True:
                chunk = fin.read(1024 * 1024 * 8)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                pct = int(done * 100 / total) if total else 100
                if pct != last_pct and (pct % 25 == 0 or pct == 100):
                    print(f"  Прогрес: {pct:3d}% ({done / (1024 * 1024):.1f} / {total / (1024 * 1024):.1f} MB)", flush=True)
                    last_pct = pct
        shutil.copystat(src, tmp_path, follow_symlinks=True)
        os.replace(tmp_path, dest_path)
        return True
    except Exception as exc:
        print(f"  [Помилка копіювання] {exc}")
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        return False


def ensure_models(models_dir: str, lite_mode: bool = False, sources=None, allow_download: bool = True) -> bool:
    """
    Makes sure both models are in models_dir. A missing file is first looked for in `sources` (other copies of
    the program on this PC) and copied; only when there is no copy it is downloaded - into models_dir, once.
    """
    os.makedirs(models_dir, exist_ok=True)
    for fname, urls, _min_mb, m in _wanted(lite_mode):
        dest = os.path.join(models_dir, fname)

        if cvpaths.model_ok(models_dir, fname):
            print(f"[OK] Модель на місці: {fname} ({os.path.getsize(dest) // (1024*1024)} MB)")
            continue

        ok = False
        copy = find_copy(fname, sources)
        if copy:
            ok = copy_file(copy, dest)
        if not ok and not allow_download:
            print(f"[ПОМИЛКА] Немає моделі {fname} у {models_dir}.")
            return False

        if not ok:
            for u in urls:
                if download_file(u, dest):
                    ok = True
                    break

        if not ok and m is not None and m["fallback_urls"]:
            print(f"[Запасний варіант] Переходимо на {m['fallback_filename']}...")
            fb_dest = os.path.join(models_dir, m["fallback_filename"])
            if cvpaths.model_ok(models_dir, m["fallback_filename"]):
                ok = True
            else:
                copy = find_copy(m["fallback_filename"], sources)
                if copy and copy_file(copy, fb_dest):
                    ok = True
            if not ok:
                for u in m["fallback_urls"]:
                    if download_file(u, fb_dest):
                        ok = True
                        break

        if not ok:
            print(f"[ПОМИЛКА] Не вдалося завантажити {fname}. Перевірте інтернет.")
            return False

    print(f"\nУсі AI-моделі готові до роботи: {models_dir}")
    return True


def main():
    lite_mode = "--lite" in sys.argv
    models_dir = cvpaths.resolve_models_dir()
    if not ensure_models(models_dir, lite_mode, cvpaths.model_sources(exclude=models_dir)):
        sys.exit(1)


if __name__ == "__main__":
    main()
