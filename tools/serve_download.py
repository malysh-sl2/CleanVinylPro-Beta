#!/usr/bin/env python3
"""
A one-page web site with a single button that downloads CleanVinylPro2.zip.

    python tools/serve_download.py            # http://0.0.0.0:18746/
    python tools/serve_download.py 8080       # another port
    python tools/serve_download.py --check    # self-test on a free local port, then exit (0 = everything is fine)

Why it exists: in a hosted workspace the archive is only a file in a list, and people who are not developers do
not find how to get it onto their PC. This page is what the workspace "preview" shows instead: the name of the
program, its version and one button.

* The archive, its size and its version are read from the disk on every request, so an archive rebuilt with
  tools/build_zip.py is served at once - the page never has to be restarted for that.
* Every address ending in /CleanVinylPro2.zip gives the archive, /icon.png the icon, any other address the page:
  whatever address a preview window opens, the button is there. The page uses only relative links.
* Nothing here is part of the program: the folder CleanVinylPro2 and the archive are only read, never changed.

Port 18746 is the default because the preview of this project is opened on that port. It is also the port of the
program's own server on the user's PC, so stop this page before starting that server in the same workspace.
(That server has no page of its own: it only answers the panel inside Photoshop and listens on 127.0.0.1.)
"""
import html
import json
import os
import sys
import threading
import time
import urllib.parse
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_FOLDER = "CleanVinylPro2"
ZIP_NAME = APP_FOLDER + ".zip"
ZIP_PATH = os.path.join(REPO_ROOT, ZIP_NAME)
ICON_PATH = os.path.join(REPO_ROOT, APP_FOLDER, "uxp-plugin", "icons", "plugin@2x.png")
MANIFEST_IN_ZIP = APP_FOLDER + "/uxp-plugin/manifest.json"
DEFAULT_PORT = 18746
DEFAULT_NAME = "Чистий Вініл Pro 2"

PAGE = """<!doctype html>
<html lang="uk">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Завантажити «{{NAME}}»</title>
<link rel="icon" type="image/png" href="icon.png">
<style>
  /* the colours of the program's own panel in Photoshop (CleanVinylPro2/uxp-plugin/styles.css) */
  :root {
    --bg: #2b2b2b;
    --bg-dark: #1f1f1f;
    --card: #242424;
    --border: #3d3d3d;
    --text: #ececec;
    --muted: #a8a8a8;
    --blue: #1473e6;
    --blue-hover: #2680eb;
    --blue-edge: #4da0ff;
    --focus: #9ec4ff;
  }
  * { box-sizing: border-box; }
  [hidden] { display: none !important; }
  html { color-scheme: dark; -webkit-text-size-adjust: 100%; }
  body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font: 400 1rem/1.5 "Segoe UI", system-ui, -apple-system, Roboto, "Helvetica Neue", Arial, sans-serif;
  }
  main { max-width: 34rem; margin: 0 auto; padding: clamp(1.5rem, 6vw, 3.5rem) 1.25rem 3rem; }

  header { display: flex; align-items: center; gap: 0.875rem; margin-bottom: 1.75rem; }
  header img { width: 3rem; height: 3rem; flex: none; }
  h1 { margin: 0; font-size: 1.5rem; line-height: 1.2; font-weight: 700; color: #fff; }
  .version { margin: 0.2rem 0 0; color: var(--muted); font-size: 0.9375rem; }

  .download {
    display: flex; align-items: center; justify-content: center; gap: 0.625rem;
    min-height: 3.75rem; padding: 0.875rem 1.25rem;
    border: 1px solid var(--blue-edge); border-radius: 0.5rem;
    background: var(--blue); color: #fff;
    font-size: 1.1875rem; font-weight: 700; text-decoration: none;
  }
  .download:hover { background: var(--blue-hover); }
  .download:active { background: #0f62c9; }
  .download svg { width: 1.375rem; height: 1.375rem; flex: none; }
  a:focus-visible, button:focus-visible, textarea:focus-visible { outline: 3px solid var(--focus); outline-offset: 3px; }
  .meta { margin: 0.625rem 0 0; color: var(--muted); font-size: 0.9375rem; text-align: center; overflow-wrap: anywhere; }
  .missing { padding: 1rem 1.125rem; border: 1px solid #7a5a22; border-radius: 0.5rem; background: #3a2f1c; color: #ffe2ae; }

  section { margin-top: 2rem; }
  h2 { margin: 0 0 0.5rem; font-size: 1.0625rem; line-height: 1.3; font-weight: 600; color: #fff; }
  p { margin: 0 0 0.75rem; }
  .fallback { padding: 1rem 1.125rem 1.125rem; border: 1px solid var(--border); border-radius: 0.5rem; background: var(--card); }
  .fallback p:last-child { margin-bottom: 0; }
  .addr { display: grid; gap: 0.625rem; justify-items: start; }
  .addr textarea {
    justify-self: stretch; display: block; width: 100%; margin: 0; padding: 0.55rem 0.7rem;
    border: 1px solid var(--border); border-radius: 0.375rem;
    background: var(--bg-dark); color: var(--text);
    font: inherit; font-size: 0.875rem; line-height: 1.45;
    resize: none; overflow: auto; word-break: break-all;
    field-sizing: content;  /* as tall as the address needs; browsers without it show the two rows of the markup */
  }
  .addr button {
    padding: 0.55rem 0.9rem;
    border: 1px solid #4d6280; border-radius: 0.375rem;
    background: #2c384a; color: #eaf3ff; font: inherit; font-size: 0.9375rem; font-weight: 600; cursor: pointer;
  }
  .addr button:hover { background: #34435a; }
  .note { margin: 0; color: var(--muted); font-size: 0.875rem; }
  .note:not(:empty) { margin-top: 0.625rem; }

  ol { margin: 0; padding-left: 1.4rem; }
  li { margin-bottom: 0.6rem; padding-left: 0.2rem; }
  code {
    padding: 0.08em 0.35em; border-radius: 0.25rem; background: #383838; color: #fff;
    font-family: Consolas, "Cascadia Mono", "Courier New", monospace; font-size: 0.92em; overflow-wrap: anywhere;
  }
  .foot { margin: 1.5rem 0 0; padding-top: 1rem; border-top: 1px solid var(--border); color: var(--muted); font-size: 0.9375rem; }

  @media (prefers-reduced-motion: no-preference) {
    .download, .addr button { transition: background-color 0.12s ease-out; }
  }
</style>
</head>
<body>
<main>
  <header>
    <img src="icon.png" width="48" height="48" alt="">
    <div>
      <h1>{{NAME}}</h1>
      <p class="version">{{VERSION_LINE}}</p>
    </div>
  </header>

{{ACTION}}

  <section>
    <h2>Що робити після завантаження</h2>
    <ol>
      <li>Відкрийте архів і перетягніть із нього папку <code>CleanVinylPro2</code> у постійне місце, наприклад на диск D:. Якщо там уже є така папка — із заміною файлів.</li>
      <li>Клацніть правою кнопкою по <code>install_windows.bat</code> і виберіть «Запуск від імені адміністратора».</li>
      <li>Двічі клацніть <code>CleanVinylPro2.ccx</code> — плагін встановиться у Photoshop.</li>
    </ol>
    <p class="foot">AI-моделей і бібліотек Python в архіві немає: програма бере їх зі спільних папок, записаних у файлі <code>folders.ini</code>. Докладно — у файлі <code>ІНСТРУКЦІЯ_ВСТАНОВЛЕННЯ.txt</code> у папці програми.</p>
  </section>
</main>
{{SCRIPT}}
</body>
</html>
"""

ACTION_READY = """  <a class="download" id="download" href="{{ZIP}}" download="{{ZIP}}">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 4v11"/><path d="m7 10.5 5 5 5-5"/><path d="M5 19.5h14"/></svg>
    Завантажити ZIP
  </a>
  <p class="meta">{{ZIP}} · {{SIZE}} · усередині одна папка CleanVinylPro2</p>

  <section class="fallback" aria-labelledby="fallback-title">
    <h2 id="fallback-title">Кнопка не спрацювала?</h2>
    <div id="by-address" hidden>
      <p id="addr-help">Скопіюйте цю адресу, відкрийте нову вкладку браузера, вставте її в рядок адреси вгорі й натисніть Enter.</p>
      <div class="addr">
        <textarea id="addr" rows="2" readonly aria-label="Адреса архіву" aria-describedby="addr-help" spellcheck="false"></textarea>
        <button id="copy" type="button">Копіювати адресу</button>
      </div>
      <p class="note" id="copy-note" role="status"></p>
    </div>
    <noscript><p>Клацніть по синій кнопці правою кнопкою миші та виберіть «Зберегти посилання як…».</p></noscript>
  </section>"""

ACTION_MISSING = """  <p class="missing" role="alert">Архів зараз недоступний: його саме збирають заново. Оновіть цю сторінку за хвилину.</p>"""

UNAVAILABLE = "Архів зараз недоступний: його саме збирають заново. Спробуйте ще раз за хвилину.\n"

SCRIPT_READY = """<script>
(function () {
  // The address is taken from the window itself, so it is right behind any proxy or preview frame.
  var url = new URL("{{ZIP}}", window.location.href).href;
  var box = document.getElementById("addr");
  var note = document.getElementById("copy-note");
  box.value = url;
  document.getElementById("by-address").hidden = false;
  box.addEventListener("focus", function () { box.select(); });
  document.getElementById("copy").addEventListener("click", function () {
    function done(ok) {
      note.textContent = ok
        ? "Скопійовано. Відкрийте нову вкладку, вставте адресу (Ctrl+V) і натисніть Enter."
        : "Адресу виділено. Натисніть Ctrl+C, щоб скопіювати її.";
    }
    // The old command first: unlike the Clipboard API it also works inside a frame from another address,
    // and that is where a preview window shows this page.
    var ok = false;
    box.focus();
    box.select();
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    if (ok) {
      done(true);
    } else if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(function () { done(true); }, function () { done(false); });
    } else {
      done(false);
    }
  });
})();
</script>"""

_info_cache = {"key": None, "info": None}
_info_lock = threading.Lock()


def size_text(n: int) -> str:
    """284 КБ / 1,3 МБ - the way Windows Explorer shows a size, with the Ukrainian decimal comma."""
    if n < 1024 * 1024:
        return f"{max(1, round(n / 1024))} КБ"
    return f"{n / (1024 * 1024):.1f}".replace(".", ",") + " МБ"


def archive_info() -> dict:
    """What is on the disk right now: {'ok', 'size', 'name', 'version'}; ok=False when the archive cannot be read."""
    try:
        st = os.stat(ZIP_PATH)
    except OSError:
        return {"ok": False, "size": 0, "name": DEFAULT_NAME, "version": ""}
    key = (st.st_mtime_ns, st.st_size)
    with _info_lock:
        if _info_cache["key"] == key:
            return _info_cache["info"]
    info = {"ok": False, "size": st.st_size, "name": DEFAULT_NAME, "version": ""}
    try:
        with zipfile.ZipFile(ZIP_PATH) as z:
            manifest = json.loads(z.read(MANIFEST_IN_ZIP).decode("utf-8"))
            tops = {n.split("/", 1)[0] for n in z.namelist()}
        info["name"] = str(manifest.get("name") or DEFAULT_NAME)
        info["version"] = str(manifest.get("version") or "")
        info["ok"] = tops == {APP_FOLDER}  # exactly one folder inside, as the page promises
    except (OSError, KeyError, ValueError, zipfile.BadZipFile):
        pass  # a half-written archive (it is being rebuilt): the page says so instead of offering it
    with _info_lock:
        _info_cache.update(key=key, info=info)
    return info


def render_page() -> bytes:
    info = archive_info()
    version_line = (f"Версія {info['version']} · " if info["version"] else "") + "плагін для Photoshop"
    page = PAGE.replace("{{ACTION}}", ACTION_READY if info["ok"] else ACTION_MISSING)
    page = page.replace("{{SCRIPT}}", SCRIPT_READY if info["ok"] else "")
    for mark, value in (("{{NAME}}", info["name"]), ("{{VERSION_LINE}}", version_line),
                        ("{{SIZE}}", size_text(info["size"])), ("{{ZIP}}", ZIP_NAME)):
        page = page.replace(mark, html.escape(value, quote=True))
    return page.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "CleanVinylDownload"
    sys_version = ""

    def do_GET(self):
        self._answer(body=True)

    def do_HEAD(self):
        self._answer(body=False)

    def _answer(self, body: bool) -> None:
        name = urllib.parse.urlsplit(self.path).path.rsplit("/", 1)[-1]
        if name == ZIP_NAME:
            self._archive(body)
        elif name in ("icon.png", "favicon.ico"):
            self._icon(body)
        else:
            self._send(200, "text/html; charset=utf-8", render_page(), body)

    def _archive(self, body: bool) -> None:
        data = b""
        try:
            with open(ZIP_PATH, "rb") as f:
                data = f.read()
        except OSError:
            pass
        info = archive_info()
        if not data or not info["ok"] or len(data) != info["size"]:
            # missing, or being rebuilt right now: better no file than a broken one
            self._send(503, "text/plain; charset=utf-8", UNAVAILABLE.encode("utf-8"), body, {"Retry-After": "30"})
            return
        self._send(200, "application/zip", data, body, {"Content-Disposition": f'attachment; filename="{ZIP_NAME}"'})
        if body:
            self.log_message("archive sent: %d bytes", len(data))

    def _icon(self, body: bool) -> None:
        try:
            with open(ICON_PATH, "rb") as f:
                data = f.read()
        except OSError:
            self._send(404, "text/plain; charset=utf-8", b"no icon\n", body)
            return
        self._send(200, "image/png", data, body)

    def _send(self, status: int, content_type: str, data: bytes, body: bool, extra: dict = None) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")  # always the archive that is on the disk now
            self.send_header("X-Content-Type-Options", "nosniff")
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            if body:
                self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass  # the browser went away; nothing to do

    def log_message(self, fmt, *args):
        print(f"{time.strftime('%H:%M:%S')}  {fmt % args}", flush=True)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def self_check() -> int:
    """Starts the page on a free local port and asks it for everything a browser would ask for."""
    import urllib.request

    bad = []
    quiet = Handler.log_message
    Handler.log_message = lambda *a, **k: None
    server = Server(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def ask(path, method="GET"):
        with opener.open(urllib.request.Request(base + path, method=method), timeout=10) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()

    try:
        with open(ZIP_PATH, "rb") as f:
            on_disk = f.read()
        info = archive_info()
        if not info["ok"] or not info["version"]:
            bad.append(f"the archive on the disk is not usable: {info}")

        for path in ("/", "/index.html", "/some/other/address?x=1"):
            status, head, data = ask(path)
            text = data.decode("utf-8")
            if status != 200 or not head.get("content-type", "").startswith("text/html") or "{{" in text:
                bad.append(f"page at {path}: status {status}, type {head.get('content-type')}")
            for needle in (f'href="{ZIP_NAME}" download="{ZIP_NAME}"', f"Версія {info['version']}", html.escape(info["name"]),
                           size_text(len(on_disk)), 'id="addr"', "<noscript>"):
                if needle not in text:
                    bad.append(f"page at {path}: no {needle!r}")
            for needle in ("http://", "https://", "localhost", "127.0.0.1", 'href="/', 'src="/'):
                if needle in text:  # the page must work behind any proxy: relative links only
                    bad.append(f"page at {path}: contains {needle!r}")

        for path in ("/" + ZIP_NAME, "/a/b/" + ZIP_NAME, "/" + ZIP_NAME + "?again=1"):
            status, head, data = ask(path)
            if status != 200 or data != on_disk:
                bad.append(f"{path}: status {status}, {len(data)} bytes instead of the {len(on_disk)} on the disk")
            if head.get("content-type") != "application/zip" or head.get("content-length") != str(len(on_disk)) \
                    or head.get("content-disposition") != f'attachment; filename="{ZIP_NAME}"' or head.get("cache-control") != "no-store":
                bad.append(f"{path}: headers {head}")
        status, head, data = ask("/" + ZIP_NAME, "HEAD")
        if status != 200 or data or head.get("content-length") != str(len(on_disk)):
            bad.append(f"HEAD of the archive: status {status}, {len(data)} bytes of body")

        status, head, data = ask("/icon.png")
        if status != 200 or head.get("content-type") != "image/png" or data[:8] != b"\x89PNG\r\n\x1a\n":
            bad.append("the icon is not served as a PNG")

        for path in ("/", "/" + ZIP_NAME, "/icon.png"):  # the preview shows the page inside a frame
            head = ask(path)[1]
            if "x-frame-options" in head or "frame-ancestors" in head.get("content-security-policy", ""):
                bad.append(f"{path}: forbids being shown in a frame")
    except Exception as exc:  # a request that fails is a failed check
        bad.append(f"{type(exc).__name__}: {exc}")
    finally:
        server.shutdown()
        server.server_close()
        Handler.log_message = quiet
    if bad:
        print("download page: WRONG")
        for line in bad:
            print("   " + line)
        return 1
    print(f"download page: the page and the archive are served correctly ({ZIP_NAME} v{info['version']}, "
          f"{len(on_disk)} bytes, identical to the file on the disk)")
    return 0


def main(argv) -> int:
    if "--check" in argv:
        return self_check()
    ports = [a for a in argv if a.isdigit()]
    port = int(ports[0]) if ports else DEFAULT_PORT
    try:
        server = Server(("0.0.0.0", port), Handler)
    except OSError as exc:
        print(f"Cannot open port {port}: {exc}. Is another server (or a second copy of this page) running on it?", flush=True)
        return 1
    info = archive_info()
    state = f"{ZIP_NAME} v{info['version']}, {info['size']} bytes" if info["ok"] else f"{ZIP_NAME} is MISSING or unreadable"
    print(f"Download page: http://0.0.0.0:{port}/  ({state})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
