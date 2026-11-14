import os
import sys
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")
os.makedirs(MODELS_DIR, exist_ok=True)

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


def main():
    lite_mode = "--lite" in sys.argv
    for m in MODELS:
        fname = m["fallback_filename"] if (lite_mode and m["fallback_filename"]) else m["filename"]
        urls = m["fallback_urls"] if (lite_mode and m["fallback_urls"]) else m["urls"]
        dest = os.path.join(MODELS_DIR, fname)

        if os.path.exists(dest) and os.path.getsize(dest) >= m["min_mb"] * 1024 * 1024:
            print(f"[OK] Модель уже завантажена: {fname} ({os.path.getsize(dest) // (1024*1024)} MB)")
            continue

        ok = False
        for u in urls:
            if download_file(u, dest):
                ok = True
                break

        if not ok and m["fallback_urls"]:
            print(f"[Запасний варіант] Переходимо на {m['fallback_filename']}...")
            fb_dest = os.path.join(MODELS_DIR, m["fallback_filename"])
            for u in m["fallback_urls"]:
                if download_file(u, fb_dest):
                    ok = True
                    break

        if not ok:
            print(f"[ПОМИЛКА] Не вдалося завантажити {fname}. Перевірте інтернет.")
            sys.exit(1)

    print("\nУсі AI-моделі готові до роботи!")


if __name__ == "__main__":
    main()
