# AGENTS.md — read this before you change anything

This repository belongs to one photographer (GitHub `malysh-sl2`). He is not a developer; an AI agent does all
the engineering. This file is the hand-over between agent sessions.

**Before you finish a session, update section 3 ("Current state") and push.** The next agent knows only what is
written here and in the repository.

## 1. The owner

- He writes short, informal Ukrainian. **Answer in Ukrainian**, in plain words, briefly. When he has to do
  something, give numbered steps with the exact file and button names. He does not know what a branch, a pull
  request or a virtual environment is: avoid the words, or explain them in one clause.
- Say honestly what was not tested. Nothing can be run on Windows or in Photoshop from the sandbox, so **he is
  the only tester**. Ask him for a screenshot or for the text of `server\install.log` when something fails.
- His PC: Windows 11 with a Ukrainian interface, NVIDIA RTX 5060 Ti, Photoshop with UXP plugins.
- His folders (they are also the defaults in `CleanVinylPro2/folders.ini`):

  | What | Where |
  |---|---|
  | the program | `D:\Plugin Photoshop\CleanVinylPro2` |
  | AI models, one copy for all versions | `D:\model AI fotoshop` |
  | Python 3.12 | `C:\Users\malys\AppData\Local\Programs\Python\Python312` |
  | Python libraries, one copy for all versions (folder chosen by the agent) | `D:\model AI fotoshop\CleanVinyl_python_libs` |

- Standing wishes, in his words:
  - one ZIP with the whole program in one folder ("зроби мені зіп з повністю цілою програмою");
  - models and libraries must never be downloaded a second time ("щоб не качало у різні версії");
  - he must always know where to download ("де качати") — see section 6.
- Decisions he made on 2026-11-18: the work may be published in this public repository, and finished versions
  are merged into `main`.

## 2. What is in the repository

| Path | What it is | Rule |
|---|---|---|
| `CleanVinylPro/` | the ORIGINAL program, v3.2.1 (plugin, server, a committed Windows `.venv`) | **Never modify.** The checks use it as the reference, and he may still run it. |
| `CleanVinylPro2/` | the program under development, «Чистий Вініл Pro 2» | all product work goes here |
| `CleanVinylPro2.zip` | the download for the owner: the folder `CleanVinylPro2`, zipped | never edit by hand; rebuild with `tools/build_zip.py` |
| `tests/` | self-checks that need no GPU, no models and no Photoshop; `tests/README.md` (Ukrainian) describes them | keep them passing |
| `tools/` | `build_ccx.py`, `build_zip.py`, `serve_download.py` | |
| `README.md` | the owner's own instruction (Ukrainian): download, install, how to continue with an agent | keep it true |

### The product

A Photoshop UXP panel plus a local Python server on the owner's GPU. It cleans vinyl studio backdrops in
portraits: dust, scuffs, the seam, the wall-floor corner, and optionally clothing wrinkles.

- `CleanVinylPro2/uxp-plugin/` — the panel (`main.js`, `index.html`, `styles.css`, `manifest.json`).
  `CleanVinylPro2/CleanVinylPro2.ccx` is this folder packaged; rebuild it with `tools/build_ccx.py`.
- `CleanVinylPro2/server/` — `server.py` (FastAPI, binds `127.0.0.1:18746` on purpose, API only),
  `engine.py` (all image processing), `cvpaths.py` (the shared folders), `setup_env.py` (the installer:
  `install | gpu | info`), `download_models.py`, `setup_launcher.py` (starts the server from Photoshop).
- The eight `.bat` files, `folders.ini` and `ІНСТРУКЦІЯ_ВСТАНОВЛЕННЯ.txt` at the top of `CleanVinylPro2/` are
  what the owner touches. The `.txt` is the full user manual; keep it true when behaviour changes.
- Models: `bria-rmbg-2.0.onnx` (at least 500 MB) and `lama_fp32.onnx` (at least 180 MB). They are not in the
  repository and not in the ZIP.

Both programs must be able to run side by side, so nothing is shared with the original:

| | original | CleanVinylPro2 |
|---|---|---|
| server port | 18745 | 18746 |
| plugin id | `com.cleanvinylpro.photoshop` | `com.cleanvinylpro2.photoshop` |
| panel id | `cleanVinylProPanel` | `cleanVinylPro2Panel` |
| URL scheme | `cleanvinyl://` | `cleanvinyl2://` |
| scheduled task | `CleanVinylProServer` | `CleanVinylPro2Server` |
| data folder | `%APPDATA%\CleanVinylPro` | `%APPDATA%\CleanVinylPro2` |
| layer names | «Чистий вініл (AI)», «Чистий вініл (Виділення)» | «Чистий вініл 2 (AI)», «Чистий вініл 2 (Виділення)», «Фон 5:7 (AI)» |

### What each version added

- **4.0.0** — the new program next to the original: new cyclorama (wall-floor line), clothing wrinkles, format
  5:7 (`extend_canvas`, `POST /extend-canvas`), smoke protection, one defect detection for both speed modes.
- **4.1.0** — light preview: nothing is computed while a slider is dragged; one light refresh 450 ms after
  release; the full frame is computed once at «Застосувати». In `engine.py` see `_quick_preview`,
  `_session_proxies_quick`, `PREVIEW_PROXY_DIM`; in `main.js` see `requestPreviewRefresh`.
- **4.2.0** — shared folders (`folders.ini`: `MODELS_DIR`, `PYTHON_DIR`, `LIBS_DIR`). Libraries live once in
  `<LIBS_DIR>\py312`; the program folder keeps only a pointer `server\.venv`. The installer takes libraries
  and models from another copy of the program on the PC before it downloads anything, and re-links
  everything after Python moves. Image processing is unchanged from 4.1.0.

## 3. Current state — update this at the end of every session

_Last updated: 2026-11-18, by the agent of the first session._

- **Released:** 4.2.0, tag `cvp2-v4.2.0`, as a pre-release. Direct download:
  `https://github.com/malysh-sl2/CleanVinylPro-Beta/raw/cvp2-v4.2.0/CleanVinylPro2.zip`
- **Owner's progress:** he downloaded 4.2.0, unpacked it to `D:\Plugin Photoshop\CleanVinylPro2`, and was
  given the install steps (run `install_windows.bat` as administrator, then double-click the `.ccx`).
  **The result of his first install is not known yet.** Expect a screenshot or log text next.
- **Checks:** the quick run of `tests/run_checks.py` ended with ALL CHECKS PASSED (26 results) on 2026-11-18,
  with NumPy 2.4.6 and OpenCV 5.1.0, set up exactly as in section 4.
- **Never run so far:** the `.bat` files in a real `cmd.exe` (they were only linted), the installer on Windows
  with the real CUDA libraries, the GPU, the real BRIA and LaMa models, the panel inside Photoshop. Treat every
  one of these as likely to need a fix after his first report.
- **Merging:** pull request #1 (`arena/33f1ced8-cleanvinylpro-beta` into `main`) is open and deliberately not
  merged yet: the owner is installing 4.2.0 for the first time, and the fixes that follow should come from the
  session that knows the code. Merge it when that session ends (section 6). If `main` already contains this
  file, that has happened.

### Offered to the owner, not built (he has not asked for them)

- make the original 3.2.1 use the shared folders too (after his moves it probably no longer starts);
- a switch "update nothing until I press a button" for the big window;
- a turnkey preset, a wall/floor switch, batch processing.

### Ideas worth doing when the installer is touched next

- Write the install log as `install_log.txt` instead of `install.log`: Arena accepts `.txt` uploads and
  rejects `.log`, so today he has to paste the text.

### Known limits of the image processing

- The cyclorama corner is searched between 25 % and 82 % of the frame height and must be nearly horizontal.
- The clothing tool is delicate: deep folds stay, near-black clothes are not touched.
- Format 5:7: equipment cut by the frame edge stays cut; the added strips near the feet can look streaky.

## 4. Working in the sandbox

The sandbox is Linux with no Windows, no GPU, no models and no Photoshop. It is recreated often and `/tmp` is
then empty. The system `python3` has no NumPy.

```bash
# once per sandbox
python3 -m venv /tmp/cvenv
/tmp/cvenv/bin/pip install numpy opencv-python-headless fastapi uvicorn httpx Pillow
npm install --prefix tests jsdom@24      # for the panel test; the folder is git-ignored

# the checks: the quick run takes about 9 minutes and ends with "ALL CHECKS PASSED"
/tmp/cvenv/bin/python tests/run_checks.py
/tmp/cvenv/bin/python tests/run_checks.py install bat    # only the groups named
/tmp/cvenv/bin/python tests/run_checks.py --full         # more random cases

# after ANY change inside CleanVinylPro2: the .ccx first, because it is inside the ZIP
python3 tools/build_ccx.py && python3 tools/build_zip.py
python3 tools/build_ccx.py --check && python3 tools/build_zip.py --check
```

- Run the 9-minute check in the background and poll it; a single blocking wait times out.
- `tools/*.py`, `server/setup_env.py` and `tests/install_checks.py` need only the standard library.
- The group `install` runs the real `setup_env.py` in imitated PCs with stand-in packages. The group `bat`
  only reads the `.bat` files the way `cmd.exe` does; it cannot run them.
- **Line endings:** the eight `.bat`, `folders.ini` and the `.txt` manual must stay CRLF, or `cmd.exe` can lose
  labels. `.gitattributes` stores them untouched (`-text`), `build_zip.py` restores CRLF, and `--check` proves it.
- **Version number:** it lives in `server/server.py` (`APP_VERSION`), `uxp-plugin/manifest.json`, the `echo`
  lines of `install_windows.bat`, `start_gpu_server.bat` and `restart_gpu_server.bat`, and the manual. The
  group `server` fails if they disagree.
- **The owner's photos** arrive in `/tmp/arena-coding-uploads/`. They show his clients: never commit them and
  never publish previews made from them. `_local/` is git-ignored for such experiments.

### Traps already paid for

- The quick preview must be built by `_session_proxies_quick`. A preview made from a twice-reduced frame
  changed the person; do not go back to it.
- "Pixels outside the mask equal the original" is a wrong check. Compare the person core against the exact preview.
- In the pointer environment a `sitecustomize.py` is silently ignored. The pointer is a `.pth` file plus a
  module; keep it that way.
- `python -m venv` does not replace a dangling `python` link: `relink_venv` removes dead links first.
- The completeness marker `cleanvinyl_env.json` is written only when missing, so a second install changes nothing.
- A failed download must not fall back to the program-folder layout (`DownloadError` is re-raised).
- jsdom: run the panel with `vm.Script(...).runInContext(dom.getInternalVMContext())` and close the window only
  after its requests and timers have finished.
- Badge texts in the panel avoid the glyphs ⚙ and ⟳; keep avoiding them.
- Pyflakes reports "undefined name 'weighted'" in `engine.py` and an unused `k` in `tests/run_checks.py`. Both
  are harmless; leave them.
- `pkill -f "server/server.py"` also kills the shell that runs it. Use `pkill -f "serve[r]/serve[r].py"`.
- `gh repo view --json visibility` is invalid; use `isPrivate`.

## 5. What the owner can send you

Arena's Agent Mode accepts only these uploads: PNG, JPEG, WebP, GIF, PDF, TXT, Markdown, CSV, HTML, XML, CSS,
JavaScript, JSON. Limits: 25 MB per file, 10 MB per PDF, 50 MB per message.
Source: <https://help.arena.ai/articles/5595418316-arena-how-to-file-upload>

So `.log`, `.bat`, `.zip`, `.ccx`, `.py`, `.ini`, `.psd`, TIFF and RAW cannot be attached. Ask for:

- an error on screen → a screenshot (PNG);
- `server\install.log` → the text pasted into the message, or a copy renamed to `.txt`;
- a photo with a bad result → JPEG, at most about five of his frames per message.

Never ask him to upload program files: you have them in the repository.

## 6. Delivering work — the part that went wrong before

Read this twice. The owner lost two days because a download link died.

1. **Arena has no ZIP download in a chat that is connected to a repository.** Work reaches him through
   GitHub only.
2. **Sandbox links are useless for delivery.** A preview address (`https://<port>-<id>.e2b.app`) stops working
   as soon as the turn ends and the sandbox sleeps; he then sees "Sandbox not found".
   `tools/serve_download.py` exists, but do not rely on it.
3. **Push at the end of every turn.** Local commits do not survive a sandbox restart, and work that was not
   pushed cannot be carried into a new session.
4. **Merging or closing the session's pull request ends the session's ability to push** (Arena rule,
   <https://help.arena.ai/articles/5432423882-how-to-use-agent-mode>). Therefore:
   - open the pull request early, but **merge it only as the last action of the session**, when the owner says
     so or when the work is finished; tell him that after the merge this chat can deliver nothing more and
     that the next job needs a new chat;
   - if you start a session and `main` lacks the previous work, find the open pull request
     (`gh pr list --state open`), merge it (`gh pr merge <number> --merge`), then bring `main` into your own
     branch (`git fetch origin main && git merge origin/main`).
5. **A version he should install** is delivered like this:
   1. set the version number everywhere (section 4), rebuild the `.ccx` and the ZIP, run the checks;
   2. commit and push;
   3. create a pre-release whose notes are in Ukrainian and contain the direct link to the ZIP at the tag:

      ```bash
      gh release create cvp2-vX.Y.Z --target "$(git rev-parse HEAD)" --prerelease \
        --title "Чистий Вініл Pro 2 — версія X.Y.Z" --notes-file notes.md
      # link for him: https://github.com/malysh-sl2/CleanVinylPro-Beta/raw/cvp2-vX.Y.Z/CleanVinylPro2.zip
      ```

      Release assets cannot be uploaded from the sandbox (`uploads.github.com` is unreachable), which is why
      the ZIP is committed and linked by tag. Tell him in the notes not to click "Source code".
   4. prove the ZIP on GitHub is the ZIP you built: `raw.githubusercontent.com` is unreachable too, so fetch
      the blob through the API and compare the bytes:

      ```bash
      gh api "repos/malysh-sl2/CleanVinylPro-Beta/git/blobs/$(git hash-object CleanVinylPro2.zip)" \
        --jq .content | base64 -d | cmp - CleanVinylPro2.zip
      ```

   5. give him that one link in the chat, and update the link and version in `README.md`.
6. Ask before anything that changes what the public sees in a new way. He agreed to the branch, the releases
   and merging into `main`; he has not been asked about anything else.
