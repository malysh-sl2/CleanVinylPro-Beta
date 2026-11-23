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
- Decisions he made for 4.3.0 (asked with two option cards): a button pressed while the server is starting is
  remembered and runs by itself, but **nothing opens without a press**; a full-length photo gets the preset
  «Дальній план» automatically (not «Студія (Стандарт)»).
- He reports problems as a short numbered list. When a point can be read two ways and the readings behave
  differently for him, ask with an option card (one click for him) instead of guessing.
- When the result of the cleaning is the complaint, he sends pairs of JPEGs: the frame as shot and the same
  frame retouched by hand the way he wants it (`1.jpg` and `1 (2).jpg`). His own retouch is the target: measure
  against it (section 4, "Working on his photos") instead of guessing a taste.
- He also sends screenshots of the big window. Measure them before you believe them: the window shows JPEG
  pictures of a reduced copy, and a defect seen there may not be in the layer (4.5.0: the "steps" on a dark
  backdrop were JPEG blocks of the preview).
- His message after 4.3.0: three frames as shot and the same frames retouched by hand (the «(2)» files). Its
  wording is not preserved here. Whether «шов» in it meant the floor joint or the wall-floor line was not
  confirmed with him; 4.4.0 treats both.
- His message of 2026-11-19 after trying 4.4.0 (two screenshots of a dark frame in the big window). **Its
  wording is not preserved here**; this is the list the agent of that session worked from: patches with hard
  edges on the dark and the dark-grey backdrop; the wall-floor corner left on the black frame; a spot left
  where he had clicked with the eraser by accident, so he asked for Ctrl+Z; the smoke checkbox should be off
  until he ticks it, and ticking it seemed to refresh nothing; a button that resets one preset; a backup of
  all settings that survives a reinstall; dark presets by framing. 4.5.0 answers these. No option card was
  shown for 4.5.0; what the agent decided alone is listed in section 3.
- His message after trying 4.5.0: two pairs of JPEGs, the frame as shot and the result of 4.5.0 with red
  ellipses drawn on what is wrong (`0Q5A3413`: black backdrop, a woman on a stool; `0Q5A3384`: grey backdrop,
  a woman sitting on the floor, hard shadows). **Its wording is not preserved here**; the agent worked from
  this list: the wall-floor corner on the black backdrop is still there; a halo next to the person and the
  stool; debris left on the grey floor (a scratch bottom right, blotches under the knee, a scratch next to
  the jeans, a spot inside the shadow of a hand, a light spot at the top-right border); a dark-grey backdrop
  should count as dark; and he asked what «злити в main» means. He also answered three questions of 4.5.0:
  Ctrl+Z works in Photoshop, the corner must go completely, dark grey is dark. He called 4.5.0 the best so
  far. 4.6.0 answers this report. Red ellipses on a result are his way to point: find each circled place
  in the original and in his result, at zoom, before changing anything.
- His message of 2026-11-20 after trying 4.6.0 (no files). **Its wording is not preserved here**; the agent
  worked from this list of four points: (1) the brush and the eraser of the big window leave a stripe with
  a hard edge - make the brush soft, with a switch between soft and hard; (2) of the two speed modes only
  the quality one should stay, the fast one and its button should go; (3) what do the three fraction
  buttons and AUTO do; (4) how can the old program (`D:\CleanVinylPro`) be removed without breaking the new
  one. He was asked three questions with option cards and chose: mode - quality only; fractions - leave
  them as they are and explain them; brush - soft, plus a switch for a hard edge. 4.7.0 answers this
  message. He did not write «зливай».
- His message of 2026-11-21 after trying 4.7.0 (three screenshots lay in the upload folder; the one that was
  opened belongs to an older report). **Its wording is not preserved here**; the agent worked from this
  list of five points: (1) after a brush stroke he has to press the full-recompute button to see the real
  result - the recompute should happen by itself; (2) after a stroke the window should show the result, not
  the green mask; (3) zoom with Ctrl + «+» / Ctrl + «−» as in Photoshop, and drag the photo with the right
  mouse button; (4) the plugin has no icon in Creative Cloud; (5) the «2» should go from the name. He also
  said that the old program is removed from his PC and that 4.7.0 works. He was asked two questions with
  option cards and chose: after a stroke - the cleaned photo stays on screen (not the mask); the name -
  yes, remove the 2. 4.8.0 answers this message. He did not write «зливай».
- While 4.8.0 was being built he added a sixth point, in his words: «і ще коли дивишся на фото у цьому вікні
  виглядає людина розмито але коли приміню все ок» - the person looks blurred in the big window and is fine
  after Apply. His screenshots show how he works: a 4K monitor (3840 x 2160), the window large, the view
  zoomed far in. The window was showing a 1080 px copy of a 5760 px frame. 4.8.0 answers this as well: the
  window gets pictures of twice the size.

- His message of 2026-11-21 after trying 4.8.0: the frame `0Q5A3417 копия.jpg` as shot (a woman in a long
  black dress with a train, full length, dark backdrop) and a screenshot of the big window with two blue
  ellipses - around the pointed shoe at the left hem, and on the floor to the right of the dress above its
  train. **Its wording is not preserved here**; the agent worked from this list of three points: (1) a
  «шов» is left on the floor; (2) a halo - a band around the person, seen along the hem and the shoe, that
  no slider removes; (3) the single hairs that stick out around the hairdo should be removed. No option
  card was shown. Which hairs he meant in (3) was not confirmed; the reply asks him. 4.9.0 answers this
  message. He did not write «зливай». Ellipses on a screenshot are his way to point (as the red ones on a
  result): the screenshot was laid over the frame (1 px of it = 2.985 px of the frame) and every circled
  place was measured in the frame, in the result of 4.8.0 and in the result of the new code.

- His message of 2026-11-22 after trying 4.9.0, answering the three questions of the reply, in his words:
  «пензель дуже довго і робе точки або тянути поленьку... ctrl+ не важливо ну на перегляд треба чекати
  від 60-400 секунд або зменш або верни нехай буде лице розміти як було я ітак знаю що все ок. головне
  швидкість.» With it the frame `0Q5A3411.jpg` as shot (3637 x 5456: a woman in a black dress on a stool,
  low key) and a screenshot with one blue ellipse around the floor left of the dress, the shoe and the hem.
  Read as: (1) the brush answers very slowly and its trace is a row of dots unless he drags slowly; (2) the
  zoom keys do not matter to him; (3) a preview takes 60 to 400 seconds - shorten that or bring the former
  way back; the soft face in the window is fine, he knows the result is right; speed is what matters.
  The screenshot was laid over the frame (1 px of it = 1.51 px of the frame, its corner = frame (-14,
  3186)): inside the ellipse the wavy shadows on the floor are gone and the floor is even, by 20-30 levels
  both ways - far more than the automatic stages do. So the ellipse very likely shows what he DOES with
  the brush: he paints whole areas of floor, many long strokes. He did not say so; the reply says how it
  was read. No option card was shown (he left the choice: "shorten or bring back"). 4.10.0 answers this
  message. He did not write «зливай».

- His message of 2026-11-22 after trying 4.10.0, in his words: «швидкий тепер пензель і  малює він
  лінію.Останній розрахунок: 30 с · Al-заливка: 121 пл. за 15 с (відеокарта) Автовивантаження моделей із
  VRAM. інколи лінія залишається і недобре розуміє де дим на світлому фоні удебільше розуміє де менше ні
  і я нажимаю що є дим воно каже ні нема.Збій відеокарти-цеяк і як провірити». No file came with it.
  Read as: (1) the brush is fast now and draws a line - 4.10.0 did what it was made for; (2) the time
  line of his window: one computation 30 s, of them the AI fill 15 s for 121 tiles on the video card - the
  GPU works on his PC; (3) «Автовивантаження моделей із VRAM.» is the caption that stands under the time
  line in the settings, copied along; whether it was a question is not known, the reply explains the
  setting in two sentences; (4) «інколи лінія залишається» - sometimes a line stays: either the wall-floor
  line or a floor joint on some frames (the answer to question 3 of the reply to 4.9.0), or the trace of
  the brush on the photo; not confirmed, the reply asks for the frame as shot and a screenshot (one cause
  was found and removed in 4.11.0 - with the smoke slider at 95-100 % the corner line of a light frame was
  itself "smoke" and the corner tool left it - whether that is HIS line is not known);
  (5) smoke on a light backdrop is understood badly: where there is more of it the program knows it,
  where there is less it does not, and when he presses "there is smoke" the program answers that there
  is none; (6) a question: what is a "GPU failure" (the words of the 4.10.0 warning) and how to check for
  it. No frame with smoke is among his files, so (5) was reproduced with drawn smoke laid over his frames
  (see the entry «4.11.0» in section 2) - a frame as shot is asked for in the reply. No option card was
  shown. 4.11.0 answers this message. He did not write «зливай».

- **2026-11-23, on 4.11.0** (two messages, three files; the first reply was stopped by him and he added
  the second message). Files: `0Q5A2507 копия.jpg` - his FIRST FRAME WITH REAL SMOKE, as shot (3765 x 5648:
  a woman in a red dress on a dark grey wall, a thick lit cloud at the right, haze at the left and on the
  floor, a black curtain at the left edge); `0Q5A2507 копия 2.jpg` - what the program made of it (4.11.0,
  preset «Зйомка з димом», «Прибирати стійки…» ticked: the unchanged zones of that file follow the smoke
  map of 4.11.0, not that of 4.10.0); and a screenshot of the big window during a computation - the first
  picture of the real window in Photoshop that was ever available. Verbatim:
  «і ще якщо я нажимаю галочку здимом то не перераховує і ще витяни кноку десь перерахувати. ще збільшити
  і зменшити розмір пензля зроби на [ -зменшити ] - збільшити.» and then «продож ЩЕ вкінці після чистки  я
  прохожу мікс кістю ти неможеж це додати але додай галочу наверху мікс кість. але йде перерахунок іде
  полоска якщо я нажимаю якус дію має перерахунок іти спочатку що треба перерахувати».
  Read as: (1) the smoke tick does not recompute - it gave a light refresh without the progress bar,
  which he does not take for a recompute; (2) pull the «Перерахувати» button out of the settings;
  (3) `[` smaller, `]` larger for the brush (the keys existed, but only by their Latin character: with the
  Ukrainian layout they type «х» and «ї»); (4) AFTER THE CLEANING HE GOES OVER THE BACKDROP WITH PHOTOSHOP'S
  MIXER BRUSH - that is what his retouches show (asked since 4.4.0 as "does he want the wall smoothed");
  he asks for a tick at the top that does it; (5) while the bar is running, an action must start the
  recompute over, computing what has to be computed. What the frames showed without his saying it: the
  brightest part of the cloud was painted over (thick smoke was "gear" and «Прибирати стійки» removed it).
  What the screenshot showed: the captions of the check boxes are drawn large and grey by Photoshop and run
  over the rows below; the time line read «17 с · AI-заливка: 38 пл. за 5,2 с (відеокарта)». No option
  card was shown. 4.12.0 answers these messages. He did not write «зливай».

## 2. What is in the repository

| Path | What it is | Rule |
|---|---|---|
| `CleanVinylPro2/` | the program under development, «Чистий Вініл Pro» (shown as «Чистий Вініл Pro 2» up to 4.7.0; the folder keeps its name) | all product work goes here |
| `tests/baseline_v321/` | six files of the ORIGINAL program, v3.2.1, byte for byte: `engine.py`, `server.py`, `setup_launcher.py`, `manifest.json`, `install_windows.bat`, `pyvenv.cfg` | **Never modify.** They are the reference the checks compare with. |
| `CleanVinylPro2.zip` | the download for the owner: the folder `CleanVinylPro2`, zipped | never edit by hand; rebuild with `tools/build_zip.py` |
| `tests/` | self-checks that need no GPU, no models and no Photoshop; `tests/README.md` (Ukrainian) describes them | keep them passing |
| `tools/` | `build_ccx.py`, `build_zip.py`, `serve_download.py` | |
| `README.md` | the owner's own instruction (Ukrainian): download, install, how to continue with an agent | keep it true |

The original program (folder `CleanVinylPro/`, 7,812 files, 666 MB with a committed Windows `.venv`) was removed
from the repository in 4.3.0 because the owner asked for it. It is still in the history (first commit
`daae6ed`). Removing the folder did not make the GitHub repository smaller; only rewriting the history would,
and he has not been asked about that.

With 4.7.0 he asked how to remove the original program from his PC and got numbered steps (manual, section 6;
also in the release notes of 4.7.0). **He has removed it** (said with his message of 2026-11-21), and 4.7.0
went on working. So on his PC there is one program now, and with 4.8.0 the «2» left its name (below). The
program needs nothing from the old folder: the libraries were copied (`adopt` in `setup_env.py`), the server
reads the models only from `MODELS_DIR` or from its own folder (`resolve_models_dir`), Python is the system
one. What the two programs REGISTER still differs (table below), so on another PC they can still stand side
by side - they would only carry the same name in Photoshop.

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

Nothing that is registered is shared with the original, so both can run side by side:

| | original | CleanVinylPro2 |
|---|---|---|
| name shown in Photoshop | «Чистий Вініл Pro» | «Чистий Вініл Pro» since 4.8.0 (he asked for it); «Чистий Вініл Pro 2» up to 4.7.0 |
| server port | 18745 | 18746 |
| plugin id | `com.cleanvinylpro.photoshop` | `com.cleanvinylpro2.photoshop` |
| panel id | `cleanVinylProPanel` | `cleanVinylPro2Panel` |
| URL scheme | `cleanvinyl://` | `cleanvinyl2://` |
| scheduled task | `CleanVinylProServer` | `CleanVinylPro2Server` |
| data folder | `%APPDATA%\CleanVinylPro` | `%APPDATA%\CleanVinylPro2` |
| layer names | «Чистий вініл (AI)», «Чистий вініл (Виділення)» | the same two since 4.8.0, and «Фон 5:7 (AI)»; up to 4.7.0 «Чистий вініл 2 (AI)», «Чистий вініл 2 (Виділення)» - still recognised (`PLUGIN_LAYER_NAMES` in `main.js`) |

Kept with the 2 on purpose, because nobody sees them in Photoshop and an update must land on the installed
copy: the folder `CleanVinylPro2`, `CleanVinylPro2.ccx`, `CleanVinylPro2.zip`, the plugin id and panel id, the
port, the scheme `cleanvinyl2`, the scheduled task, `%APPDATA%\CleanVinylPro2`, `APP_ID` (`cleanvinylpro2`),
the backup file names and the release tags `cvp2-v…`. Do not rename any of them: a new plugin id would add a
second plugin next to the installed one and lose his presets.

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
- **4.3.0** — the big window and the panel; the cleaning itself is unchanged from 4.1.0.
  - Three views of the photo, one at a time (`sessState.view`, `setView`): the window opens with the cleaned
    photo; «До / Після» switches original and cleaned photo; «Маска» shows the red/green mask. Brush, eraser and
    inversion switch the mask on by themselves. (Before, the window opened with the mask and «До / Після»
    compared the original with the mask.)
  - Automatic preset: the plugin sends its presets by kind of frame with `/session/start` (`scenePresets`), the
    engine looks at the frame (`_scene_info`: dark backdrop / close-up / cut at the waist or knees / whole
    figure) and cleans with the suitable set from the start; the answer carries `scene`. Mapping in `main.js`:
    `AUTO_PRESET_BY_SCENE` (dark → `lowkey`, close → `closeup`, medium → `medium_shot`, wide → `wide_shot`,
    default → `std`), matched by preset id. Checkbox «Авто: підбирати пресет під кадр» in the preset list.
  - Presets: a click gives one light refresh and a note in the corner of the photo telling what changed
    (`mask_share` in the answers = share of the frame that is green). Built-in presets that switch a fraction
    off («Ближній план», «Делікатний») now turn the AUTO button of the fractions off - AUTO used to overrule
    them (`presetFracAuto`, `fracAutoUser`).
  - Server start: one launch request, then a patient wait of up to 150 s (it was 9-12 s, shorter than a cold
    start); the status turns green by itself. A button pressed meanwhile is remembered
    (`ensureServerForAction`, `pendingPress`); a second press takes it back.
  - The panel shows a banner when the running server reports another version (`PLUGIN_VERSION`).
- **4.4.0** — the cleaning itself, after his three sample frames with his own retouch next to them.
  - Floor joint (`_detect_vinyl_seam_mask`): the pieces of one line on both sides of the person are judged
    together (`seamJoin`, default on; judged one by one, the shorter side stayed). A dark, obvious joint is taken
    too: the thickness of a line is judged at 40 % of its own strength (before, only faint joints passed).
  - Stains (`_smooth_backdrop_stains`, slider «Сліди взуття та розводи»): a new stage. The backdrop, with its
    light taken out (`_light_plane`), is averaged with neighbours of similar tone (`_even_by_tone`) right up to
    the silhouette. The old stage was switched off around every person by the "shadow" map and the feather ramp.
    Bends of the light (the rim of a lamp's pool, soft shadow edges) are left alone (`STAIN_SLOPE_*`).
    `feather` now belongs to the background blur only.
  - Corner: found once on the untouched frame (`_corner_line_of_frame`, cached as stage `corner`); the seam
    search leaves its strip alone when the corner tool is on; a thin line (a floor joint) is no longer taken for
    the corner (`one_way` in `_find_corner_line`). `cycCurve` is 65 in the built-in presets `std`,
    `medium_shot`, `wide_shot`, `clean_stands` and 0 in the others. Inside a selection the corner goes only
    when the selection holds the whole line (`_selection_holds_line`).
  - Smoke: the plugin sends `smokeAuto`; smoke is then protected only when the frame has it
    (`SMOKE_MIN_SHARE`, `SMOKE_MIN_CLOUD`; on his frames the "smoke" was dirt next to the feet). From 95 % on
    the slider it is protected on trust (`SMOKE_ALWAYS_FROM`). Every answer of the window carries `smoke`
    (what was seen); the plugin turns it into a note when a smoke control is used (`smokeNoteText`).
  - Mask: with the stages that work on the whole backdrop (stains, blur, corner) the layer covers the whole
    backdrop. The session therefore keeps two masks: `auto_mask_small_u8` (the layer) and
    `repair_mask_small_u8` (found and repaired). «Маска» shows them as pale and bright green; `mask_share`
    counts the bright part, `layer_share` the layer; a brush stroke outside the repaired zones is repaired at
    Apply (before, a stroke inside the layer did nothing).
  - A changed default reaches installed PCs through `PRESET_DEFAULT_MOVES` in `main.js` (made once, only where
    the stored value is still the former default, remembered in the settings as `presetMoves`).
- **4.5.0** — dark backdrops, steps back for the mask edits, smoke off until asked, backups.
  - Dust against the local noise (`_local_grain_gain`, request parameter `grainLocal`, default on). The fine
    pass of `_detect_spots_mask` used one noise value for the whole frame. On a low-key frame that is the noise
    of the dark majority; the lit floor is 1.5-2.2 times noisier and its plain noise passed for dust (his black
    frame: 5.1 % of the frame inpainted, his dark-grey one 13.2 % - the "patches with hard edges"). The
    thresholds now follow the noise of each cell wherever it is clearly above the frame's (`GRAIN_LOCAL_*`).
    An evenly lit frame is searched exactly as before (`GRAIN_UNEVEN_*`; his light-grey frame gives the
    identical mask).
  - Corner. With the corner tool at 0 the seam search may still take the corner for a joint, as it always
    could, but only whole: `_whole_line_repair_only` keeps a repair inside the corner strip when it covers
    85 % of the visible line and drops it otherwise (on his black frame pieces of the line were repaired: a
    dashed, hard-edged remainder). The corner finder takes the slope of the light out before it judges "one
    step or two" (`tilt` in `_find_corner_line`): a faint joint on a floor that darkens towards the camera
    passed for the corner and was smeared instead of repaired - with the corner tool on, since 4.4.0.
  - Window pictures: JPEG 100 for dark frames, 90 otherwise (`_preview_quality`, `PREVIEW_JPEG_QUALITY_DARK`,
    session field `preview_q`; `previewQuality` in the request overrules). At 90 a dark backdrop comes out as
    flat 8x8 blocks one grey level apart.
  - Steps back and forward for the mask edits: ops `undo` / `redo` of `/session/mask-edit`
    (`_edit_history_push`, `_edit_history_step`, `_edit_restore`; `EDIT_HISTORY_MAX` 40). Answers about the
    mask carry `history: {undo, redo}`; a step answers `stepped`. A snapshot taken before a recompute is put
    back onto the frame as it is computed now (`base_gen`). Plugin: Ctrl+Z, Ctrl+Shift+Z, Ctrl+Y (told by
    `e.code`, so the Ukrainian layout works), two buttons in the left bar (`dlgBtnUndo`, `dlgBtnRedo`), edits
    sent one after another (`maskEditQueue`).
  - Smoke protection is off until asked: `smokeOn: false` in every built-in preset except `smoke`. The window
    says at once when it opens with the protection off and the frame seems to have smoke
    (`smokeOffHintText`); the answer after a smoke control is also kept in the hint strip (`sayInWindow`).
  - Dark presets by framing: `lowkey_medium`, `lowkey_close`, `lowkey_wide` («Темний середній / ближній /
    дальній план»). `lowkey` stays the general dark preset, now with dust 80 and `cycCurve` 65. Scene keys in
    `start_session`: on a dark backdrop `dark_<framing>`, then `dark`, then the framing, then `default`
    (`AUTO_PRESET_BY_SCENE` in `main.js`).
  - «Скинути пресет» (`gBtnResetPreset`, `resetActivePresetToDefault`): the active built-in preset gets the
    values of `DEFAULT_PRESETS` after a second press within 6 s. A preset the user made has nothing to be
    reset to.
  - Backup of the settings: panel buttons `btnBackupSave` / `btnBackupRestore`; the server writes
    `<program folder>\backup\CleanVinylPro2_backup_<date>_<time>.json` (`/backup/save`, `/backup/list`,
    `/backup/read`, `/backup/open-folder`; the environment variable `CLEANVINYL_BACKUP_DIR` moves the folder,
    the checks use it). The plugin cannot write the file itself: its manifest gives it its own data folder
    only (`localFileSystem: "plugin"`), and that folder is what a reinstall of Photoshop wipes. A restore
    first saves what is there as a backup labelled `before-restore` (the newest 10 stay), replaces presets and
    settings, then runs the default moves and adds the new built-in presets. The folder `backup` is never
    packed (`tools/build_zip.py`) and is git-ignored.
  - New entries of `PRESET_DEFAULT_MOVES`: `smokeOff` (a switch, see `PRESET_SWITCHES`), `lowkeySpots80`,
    `lowkeyCyc65`. A new built-in preset is inserted under the built-in preset it follows
    (`appendNewDefaultPresets`).

- **4.6.0** — what the search takes for what, after his two frames tried with 4.5.0. No new controls; two
  request parameters, both on by default and off in the legacy regime of the checks.
  - Studio gear by its body (`_edge_blobs_with_body`, parameter `gearBody`). `_compute_protection_maps_small`
    kept every long strong edge as gear, and gear is left untouched by every stage. The hard edge of a cast
    shadow and a long scratch were "gear", with all the dirt around them: untouched rectangles on his grey
    frame. A group of strong edges is now gear when something stands there - most of the light is missing
    (or added) in a thin body with backdrop on both sides (`GEAR_BODY_*`) - or when it touches the left,
    right or top border of the frame. Share of light missing, measured: stands, cables, a softbox 0.62-0.93;
    shadow edges 0.03-0.12; his scratch 0.07; folds of a white dress 0.28. An edge that is no gear is kept
    out of the smoke search all the same (`edges_any`): its outline read as wisps and "smoke" was found.
  - Corner on a black backdrop (`_find_corner_line`, rule 2b, `CORNER_UPPER_*`). The corner is half an L*
    there; the rim of a pool of light or the shadow of a stool lower on the floor scores five times as much.
    4.5.0 bent the light at that line and left the corner. A line above the strongest one is now the corner
    when it scores 0.15, runs along half of the visible backdrop and its step is 4 % of the brightness
    around it (on a light backdrop that is 2.5 L*, so nothing changes there). His frame: 0.26 at 0.589 of
    the height against 1.54 at 0.768.
  - Floor joint, only with `seamJoin` (`_seam_piece_check`, `_seam_piece_path`, `_seam_floor_in_view`). A
    thin piece is looked at once more on its own profile, taken along its own course. A tone step of
    `SEAM_LIGHT_EDGE` levels right at it is the edge of a lit area, not a joint; a piece that shows less
    than `SEAM_OWN_LINE` of what the search saw lies on nothing (the search answers to slanted edges of
    light). Pieces are one line only when the floor between them is mostly hidden: with more open floor
    without a line between them than they are long, they are two scratches (his grey frame: a band of
    93,000 px across the floor was repaired). `_detect_vinyl_seam_mask(info=...)` returns every piece and
    group with its numbers and the reason it was dropped.
  - A dirty spot inside a cast shadow (`_shadow_spots`, `SHADOW_SPOT_*`, parameter `shadowSpots`). The dust
    search dropped every blob over 28 px that lies in a shadow. A small compact blob that is clearly darker
    than an even shadow around it, away from the person, the gear and the frame border, is now taken
    whole. The limits come from his frames and are written next to the constants.
  - A dark key is a backdrop below 40 of 255 (`SCENE_DARK_LUMA`, was 26): his dark grey (31) is dark to
    him, his grey (52) is not.
  - `tests/try_defects.py`: the deliberate defects for these rules, kept in the repository. (Its list is
    replaced with every version; the one of 4.6.0 is in the history, commit `50bae15`.)

- **4.7.0** — the brush and the eraser of the big window, and one mode instead of two, after his message
  about 4.6.0. In `engine.py` all of it sits under the comment "the brush and the eraser of the big window".
  Read that comment before you touch anything there: each rule names the frame that asked for it.
  - The edge of a stroke (`_stroke_alpha`). Soft: full strength inside half the brush radius, half at the
    circle the user sees, nothing beyond 1.5 radii (`BRUSH_SOFT_BAND`). Hard: a band of a fifth of the
    radius (`BRUSH_HARD_BAND`), about the edge every stroke had before. The edge travels with each stroke:
    `softness` 1 / 0 in the body of `/session/mask-edit`, `edit_session_mask(..., softness=None)`; a
    stroke that names no edge is a soft one.
  - The soft BRUSH never touches the person and fades out over `BRUSH_PERSON_MARGIN` window pixels around
    it (`_stroke_off_person`, `_session_person_small`). The hard brush repaints whatever it crosses, so a
    prop that the search took for a part of the person can still be painted away. The eraser is not limited.
  - A painted zone is not inpainted any more (`_brush_fill`; the same code draws the window and the
    layer). Its tone is continued from the even part of the backdrop right around it (`_even_part`,
    `_brush_fill_zone`) and stretched over the zone like a membrane (`_smooth_fill`); its grain is real
    grain of the frame, taken from a clean square nearby (`_grain_blocks`). Three rules, each a PAIR of
    numbers with a gradual change between them (`_ramp`):
    - `BRUSH_MOST` - when one even surface is most of the surroundings, the rest (a shadow that the stroke
      only touches) is left out of the tone;
    - `BRUSH_SECOND` - a second even surface holds a share of the surroundings (the stroke crosses the
      edge of a shadow or runs along it): the tone of the zone stays, only its grain and fine dirt are
      renewed;
    - `BRUSH_RING_MIN` - next to no backdrop is left around the zone (the whole backdrop was painted): the
      tone and the studio gear stay.
  - "Fill" (Ctrl + click on the brush) sets the session field `fill_all`: the whole layer becomes visible
    and nothing is repainted; `layer_share` is 1.0, `mask_share` stays what the search found; a step back
    undoes it. Up to 4.6.0 it marked the whole frame as painted, the person included.
  - Session parameter `brushSoft` (on by default). Off = the stroke, the preview and the repair of 4.6.0;
    `_legacy` of the checks switches it off, because v3.2.1 must still be matched there.
  - Panel: two buttons under the brush size, `dlgBrushSoft` (the default) and `dlgBrushHard`
    (`setBrushSoft`, `updateBrushEdgeUI`; `sessState.brushSoft`, kept in the settings and in a backup as
    `brushSoft`; icons `icons/ui/edge_soft.png`, `edge_hard.png`). One choice serves the brush and the
    eraser. The cursor ring was left as it is on purpose: it is the middle of the fade, and the tooltip
    says so.
  - One mode: the speed button is gone and `main.js` has `const speedMode = "quality"`; a `fast` stored by
    an older version (settings, presets, backups) is ignored. The engine still has both fills: the light
    preview draws with the fast one and the request parameter `speedMode` still works.
  - The fraction buttons were only explained to him (manual, release notes); nothing changed there.
  - Checks: the new group `brush`; `mask` and `scene` follow the new "fill"; four panel scenarios and five
    settings cases for the edge buttons and the one mode. `tests/try_defects.py` now holds the 29
    deliberate defects of 4.7.0 (18 for the engine and the server, 11 for the panel) and can put a defect
    of the panel into a copy of the plugin folder (`panel("<text in the scenario names>")`,
    `CV_PLUGIN_DIR`).
- **4.8.0** — the big window: the exact picture comes by itself, the brush works on the cleaned photo,
  the pictures are twice as large (the person is sharp), zoom keys, dragging with the right button; the
  name without the 2; an opaque plugin icon. The cleaning itself and the brush are unchanged from 4.7.0.
  - **The exact picture by itself.** Up to 4.7.0 a slider gave a light (quick) preview, and the real frame
    was computed only by the button «↻ Точний перегляд» or by Apply. Now the panel asks for it by itself:
    `scheduleExactPreview` → after `EXACT_DELAY_MS` (700 ms) in which nothing is touched →
    `runExactPreview` posts `/session/recompute` with `background: true`, without the progress card. The
    corner label (`updateModeBadge`, `previewKind`) says «ПІСЛЯ · швидкий перегляд · уточнюється… N %»
    until the exact picture is there, then «ПІСЛЯ · чисте фото». State: `sessState.exactShown`,
    `exactTimer`, `exactSig`, `exactJob`, `exactHold`, `exactError`, `bgUnsupported`, and `exactJobs` (a
    Set that belongs to one window).
  - Engine: `recompute_session(..., background=True)`. `_recompute_full` computes the frame WITHOUT the
    session lock; `_session_lock` is held only while the request is read and while the result is put in
    place (`_recompute_commit`), so mask edits and the clothing switch are answered meanwhile and what was
    drawn stays in the result. `_compute_lock` (always through `_compute_turn`) says who may compute a
    frame. **Lock order: `_compute_lock` before `_session_lock`.**
  - Giving way: `self._checkpoint()` stands at 27 places of the pipeline where nothing shared is
    half-written. In the thread of a background run it raises `JobSuperseded` as soon as another request
    waits for the frame (`_compute_waiters > 0`: a recompute of any kind, Apply, a new photo) or the
    session is no longer the active one (the window was closed). The answer is
    `{ok, session_id, superseded: true}`; the session is untouched and the finished stages stay in the
    stage cache, so the run that follows is shorter. `JobSuperseded` is a `BaseException` on purpose: the
    pipeline has `except Exception` fallbacks that must let it through.
  - `{ok, skipped: true}`: the settings are the ones the preview shows and the mask is the user's own
    drawing (`mask_detached`, after "invert + brush") - a recompute would put the automatic mask back, and
    that must not happen by itself. Apply computes the real frame in that case, as before.
  - Every answer of the window carries `rev` (grows with each recompute and each mask edit) and `exact`
    (`_picture_state`). A stroke is answered while a background run is on its way, so two answers can
    arrive the other way round: the panel drops pictures with a lower `rev` than the one on screen
    (`takeSessionPictures`, `takeRecomputeAnswer`).
  - The clothing switch during a run: `sess["dress_live"]` holds the clothing state the window named
    last; a background run draws its pictures with it.
  - Apply: the panel sends `followBackground: true` when a background run for the very values on the
    sliders is on its way; `apply_session(follow_background=True)` then waits for it
    (`_compute_turn(ask_way=False, follower=…)`) instead of stopping it, and its progress bar goes on
    from the numbers of that run. The frame is computed once.
  - 2 passes have no light way: `requestPreviewRefresh` goes straight to the background run; the former
    picture stays meanwhile and the badge says «↻ Перераховую перегляд із новими значеннями…».
  - The button `gBtnRecompute` stays, as «↻ Перерахувати зараз (не обов’язково)»: the full recompute with
    the progress card, for the case that the exact picture did not come by itself.
  - A server before 4.8.0 (its start answer has no `exact`): `bgUnsupported`, nothing is asked in the
    background, the window behaves as 4.7.0.
  - **The brush on the cleaned photo.** Nothing switches the mask on by itself any more: not a stroke, not
    picking a tool (button or key), not the inversion, not Ctrl + click on the brush or the eraser. The
    trace of a stroke (`dlgStrokeDots`) is shown over the cleaned photo and over the mask alike, until the
    answer comes. A mask the user switched on stays on through his strokes. A stroke over «ДО» brings the
    cleaned photo back. The three actions on the whole mask say in words what they did (`sayInWindow`).
  - **Zoom keys**: Ctrl + «+» / Ctrl + «−» / Ctrl + 0 (`zoomKeyOf` asks `e.code`, `e.key` and `e.keyCode`;
    `zoomBy(factor, cx, cy)`, `ZOOM_KEY_STEP`); the keys zoom around the middle of the view, the wheel
    around the pointer, as before. **Right button**: `startPan` / `panTo` / `endPan` in `initEvents`;
    `mousedown` with button 2, the `contextmenu` event suppressed over the photo, and pointer events as a
    second way for a host that reports the right button only through them.
  - **The name**: see the table above. In `main.js` the history steps and command names lost the 2 as
    well; the layers are made under `LAYER_NAME_AI` / `LAYER_NAME_SELECTION`.
  - **The plugin icon**: `icons/plugin*.png` are opaque now (a full dark square instead of a rounded one
    cut out of transparency) and the manifest names the theme `all` too - what Adobe asks of a plugin
    icon. This is the icon Photoshop shows in its own list of plugins. The list of the Creative Cloud
    desktop app shows no custom icon for a plugin installed from a local `.ccx` (answers of Adobe staff on
    the developer forum, found in this session); nothing inside the plugin changes that, and he was told
    so.
  - **A slider that is taken stops the background run at once.** `stopBackgroundRun()` in the panel posts
    `/session/stop-background` on the `mousedown` of a slider that changes the frame (not Blend, not
    Clothing) while an exact request is on its way. `stop_background(session_id)` raises `_bg_stop`; a
    run whose mark (`stop_mark`, taken when its request enters `recompute_session`) is older stops at its
    next safe place, or does not start at all if it still waited for its turn. Runs asked for later are
    not affected. Without this the run stopped only when the refresh after the release arrived, and that
    refresh had to wait for it. What was put off when Blend or Clothing was taken - a light refresh, the
    exact picture - goes on after the release.
  - **The pictures of the window are twice the working size** (his sixth point). The session still works
    at <= 1080 px: masks, strokes, the cleaned proxy, `preview_w` / `preview_h`, the brush radius. Only
    the three JPEGs are larger: `DISPLAY_LONG` = 2160 px on the long side, never larger than the frame,
    and not at all where less than `DISPLAY_MIN_GAIN` (1.25) would be gained (`_display_size`).
    `sess["orig_disp_bgr"]` is the photo at that size; `_compose_display` lays the layer of the working
    size, enlarged, over it: where the layer shows nothing the result IS the photo, pixel for pixel.
    Ironed clothing takes only the change the ironing makes (`relit_small`), so the weave of the cloth
    stays sharp. `_overlay_display` draws the mask view of that size: the same tints as
    `_encode_overlay_jpg`, as three maps that are made at the working size and enlarged (the old way took
    147 ms at that size, this one about 25).
    `previewLong` of the start request overrules the size. The legacy regime of the checks asks for 1080
    and gets the working pictures, byte for byte as before. (Like `previewQuality`, it is read from the
    parameters that are in force after the automatic preset was put in place: a request that names it
    next to `scene_presets` loses it. Only the checks pass it, and they pass no scene presets with it.)
    The panel needed no change: the stage is sized by `preview_w` x zoom and each `<img>` fills it.
    `main.js` must never ask a picture for its size (`naturalWidth`); the group `server` checks that.
    "Window pixels" and "the window pictures" in this file and in comments written before 4.8.0 mean the
    WORKING size: the brush radius, band widths, margins and masks are all in working pixels.
    Measured on his 3840 x 5760 frame in the sandbox: drawing the two pictures of an answer takes about
    90 ms at 2160 px (about 70 ms at 1080 px before), a stroke takes the same time as before within the
    noise of the measurement; a picture weighs about 220 KB instead of 66 KB (quality 90; on a dark
    frame, quality 100, about 0.5 MB). 2880 px was measured too: 170 ms and 400 KB. 2160 was chosen
    because every answer carries two pictures and nobody knows how fast Photoshop decodes them.
    What did NOT gain: the cleaned backdrop is still the working-size proxy, enlarged. The next step, if
    he asks for more: load the visible part of the frame at full resolution when the view is zoomed in
    (the real frame is in the session once the exact picture is there). Not built.
    A risk that could not be looked at: the window opens at 1020 x 740 every time, and a 2160 px picture is
    then drawn into a box of a third of its size. If Photoshop scales it down without care (bilinear, no
    smaller copies), fine detail may look grainy there. He is asked to say so; the remedy would be a
    second, smaller picture for small boxes, or a size chosen from the size of the window.
  - Checks: the new groups `exact` and `sharp`; `http` sends `background` / `followBackground` /
    `stop-background` through the HTTP layer; `server` checks the name, the layer names, the icon and
    that the panel never reads the size of a picture; `mask` and `dark` read the larger pictures. The
    scripted server of the panel test speaks the protocol of 4.8.0 (`bgAware`, `rev`, `exact`,
    background runs that give way or are stopped, `skipped`); without `rev` / `exact` in its answers the
    panel would take it for an older server and ask nothing. `env.recomputes()` are the requests a
    control asked for, `env.exacts()` the background ones.
    `tests/try_defects.py` holds the 71 deliberate defects of 4.8.0 (14 `exact`, 16 `sharp`, 3 `http`, 38
    for the panel); a panel defect can now name several scenario texts (`panel("a", "b")`). The runner
    says CRASHED, not "caught", when a check run ends without a FAIL line (section 4).

- **4.9.0** — answers his report on 4.8.0 (frame `0Q5A3417`): the tone stages reach the person itself, so no
  rim of the old tone is left along a hem or around a shoe; the thin line of a vinyl joint goes with the
  corner; a new tool takes the single hairs that stick out of the hairdo (off until its slider is moved).
  The window, the brush and the server are unchanged from 4.8.0.
  - **Why the rim (his "halo") was there.** The mask of `_clean_fg_mask` is a PROTECTION: the person with
    a margin (the slider «Захист моделі та країв», `edge`), gaps closed. It says where nothing may be
    repaired. The stages that only shift the tone of the backdrop - the corner (`_apply_cyclorama_curve`)
    and the stains (`_smooth_backdrop_stains`) - were gated by it too, so a band around the person kept
    the tone of the shot. Next to a floor that got lighter or darker the band shows as a rim, and the
    slider only made it wider or narrower. On 3417 the floor above the train was lifted by 14-17 levels,
    the 10 px right at the dress by nothing.
  - **`_tone_gate`** (`TONE_GATE_*`): how much of a tone shift a pixel takes (255 = backdrop). Outside
    the protected band it is the former gate. Inside the band it is the matte WITHOUT the margin
    (`_tight_person_1024`: the raw matte, only the blobs that are no person dropped), with its edge moved
    to where the photo has an edge: a guided filter of the matte by the brightness of the photo, window
    `TONE_GATE_R` (1.5 px of the 1024 matte). Zero wherever the network is sure of the person
    (`TONE_GATE_SURE`, 224 of 255): a bare leg as light as the floor behind it has no edge to go by, and
    the fit alone let a part of the shift onto it (`cyc` said "the person was changed"). Never less than
    the former gate. Both tone stages take it as `tone_gate`; the stage cache keeps it as "tgate".
  - With `toneEdge` a repair (dust, seam, hairs) is no longer blended into the frame under the protected
    band and merely hidden there by the layer alpha (`heal_gated` in `process`): now that the layer shows
    right up to the person, the frame itself must be untouched wherever the protection says so.
  - Request parameter `toneEdge` (default on; off = the former way, which the comparisons with v3.2.1
    ask for). It is not in the panel.
  - **Why the "seam" stayed.** On 3417 the front sheet of vinyl begins at 0.77 of the height. The joint is
    a thin dark line, 1-2.3 levels deep, with the edge of the lit floor along it - so the corner finder
    takes it for the wall-floor corner. The cove turns a step into a slope; a thin line is no step, and
    about a third of it stayed lying on the slope. The seam search leaves the strip of the corner to the
    corner tool. Tried, and no cure: the corner tool at 0; forcing the exact line; the seam repair plus
    the cove; the exact line with the fit off (a bright patch next to the dress).
  - **The thin line of the corner** (`cornerHair`, default on, works only with `cycCurve` > 0, not in the
    panel). `_corner_line_of_frame(..., hair=True)` also gives `zone` (`CORNER_HAIR_ZONE`, 2 % of the
    height: the line need not lie in the middle of the step) and `hair`, the pieces of a thin line found
    inside that zone by `_corner_hairline` - the seam search once more on the untouched frame, at its
    most sensitive, the step allowed (`corner_own=True`). After the cove, part F of
    `_apply_cyclorama_curve` (`_remove_corner_hairline`) lays the band of each piece straight, averages
    the profile ACROSS the line ALONG it (the grain averages out, the line stays) and subtracts what the
    profile has beyond the straight line between its two shoulders, at most `CORNER_HAIR_CAP`. Nothing is
    painted: every pixel keeps its grain. The seam search then leaves the whole zone alone (one line, one
    tool). `stats["corner_hair"]` is the number of pieces.
  - `level_seen` / `CORNER_OVER` (on together with `cornerHair`): a piece of backdrop in plain view is not
    left lighter than its own slope. On 3417 the pool of light reaches below the joint next to the hem,
    where the train hides the floor further down; the cove lifted that strip as if it were as dark as
    the open floor, which left a lighter streak right at the dress.
  - **Single hairs** (`strayHair` 0..100, 0 = off; the slider «Волоски довкола зачіски», `gSlHair`, its
    badge reads «Вимк.» at 0; no built-in preset carries the key, and a preset without it means 0).
    `_detect_stray_hairs`, block "4b" of `engine.py`: read its comment first. Every size is in head widths
    (`_head_of_person`); a close-up is searched on a copy with the head at most `HAIR_HEAD_REF` px wide.
    The zone: up to `HAIR_REACH` (0.6) head widths from the person, from the top of the head down
    `HAIR_ZONE_DOWN` (1.8). Black-hat and top-hat responses are averaged along 8 directions
    (`_line_kernels`) and thinned to centre lines. Then:
    1. pieces: strong enough, no tuft (`HAIR_TUFT`), leading away from the person (`HAIR_AWAY`; and
       `HAIR_OUTWARD` of the piece, weighed by strength, points across the outline rather than along it);
    2. a hair = the pieces within `HAIR_GAP`: it begins at the outline (`HAIR_ATTACH`), sticks out
       (`HAIR_STICK_OUT`), is long enough (`HAIR_MIN_LEN`: 0.16 → 0.05 head widths over the slider; the
       fuzz is not counted) and reaches neither the end of the zone (`leaves`) nor the border of the
       frame (`at_border`);
    3. a dark hair grows out of something dark (`HAIR_ROOT`; a light hair is not asked);
    4. the line does not go on beyond its far end (`goes_on`, `HAIR_TAIL`, `HAIR_GOES_ON`): the piece of a
       cable between the head and a knot of hairs ends in the open like a hair.
    Never searched: the person with a guard strip (`HAIR_GUARD`, `_person_solid`), the fuzz beyond it
    (`HAIR_FRINGE`), the bodies of gear (`wide_only`), smoke. Every slider step below the one asked for is
    searched too (`HAIR_STEPS`), so a higher position never takes less. A mark is grown to about 13 px.
  - The marks join the heal mask (`near_mask`; cache key `k_hair`, stage "hair"). Around a marked hair
    (`HAIR_SRC_NEAR`, 16 px of the 1024 matte) the inpainting is shown the photo right up to the person
    with the guard strip (`hair_solid`), not the protected band painted over with a wide average of the
    backdrop: next to a head that average is not the tone of the wall right there. Everywhere else the
    band is painted over as always, so every other repair of the frame is pixel for pixel what it is with
    the slider at 0. (The first version showed the photo along the whole outline as soon as one hair was
    marked: on 3417 that changed 7,696 px of the other repairs, more than 100 px away from any hair, by
    more than one level, up to 33 - a tool that is asked for hairs must not touch the floor. Now: 222 px,
    up to 4 levels, all in the LaMa tiles around the head, where another hole in a tile changes its
    neighbours a little; below the waist nothing.) The repair itself obeys the protected
    band like every repair, so the first pixels of a removed hair, next to the hairdo, stay. (For a
    while the mark was blended at full strength inside the band; that gained a stub a few pixels
    shorter, no check could tell the two apart, and it was taken out.)
  - Traps met on the way - do not undo them: the cast-shadow map calls the wall next to a light hair a
    shadow, so it is not asked; the gear map flags a strong hair as a thin thing, so only its bodies
    count; a mark narrower than about 13 px only fades the hair; a lower threshold joins a hair with its
    neighbours into a "tuft", hence `HAIR_STEPS`; the length of a hair is counted outside the fuzz of the
    outline, so the first shortest length at 100 (0.07 head widths) asked for a reach of 0.09 and the
    clearest hair on top of the head of 3417 stayed (36 px where 38 were asked); next to a strong line
    the kernels that cross it leave faint centre pixels that point across it, hence the weighing in
    rule 1; `stats["hair_px"]` in every answer broke the comparison with v3.2.1, so it is there only when
    the tool is on.
  - Panel: `gSlHair` is one of `ALL_SLIDER_IDS`; `readCurrentConfig` sends it as `strayHair`,
    `normalizedPresetConfig` keeps it within 0..100 (0 when a preset has no such key), `applyConfig`
    puts it on the slider, `previewSettingsSignature` holds it. The tooltips of «Циклорама» and «Захист
    моделі та країв» say what changed; one new rotating tip. `presets_defaults.json` is unchanged.
  - Checks: the new groups `edge`, `line` and `hair`; `_legacy()` sets `toneEdge=False`,
    `cornerHair=False`, `strayHair=0`; five new cases of the settings test and the scenario «the hair
    slider…» of the window test. `tests/try_defects.py` holds the 36 deliberate defects of 4.9.0 (30 in
    the engine, 6 in the panel).

- **4.10.0** — speed, after his report on 4.9.0 («пензель дуже довго і робе точки… на перегляд треба чекати
  від 60-400 секунд… головне швидкість»). The cleaning is unchanged: the layers are those of 4.9.0.
  - **The fast window is the default again.** `detailPreview` (panel, `main.js`; saved with the settings
    under that name; the checkbox «Детальний перегляд (повільніше)», `gChkDetail`, in the settings of the
    big window above «↻ Перерахувати зараз») is `false` unless he ticks it. Off means what 4.7.0 did:
    - the start request carries `params.previewLong = PREVIEW_LONG_FAST` (1080), so the window pictures are
      the working pictures themselves (`_display_size`): every answer to a stroke is 0.54 MB instead of
      1.75 MB on frame 3411. On: `PREVIEW_LONG_DETAIL` (2160), the pictures of 4.8.0. The size is fixed
      when the window opens, so ticking shows from the next opening (the tooltip says so);
    - `exactPreviewWanted()` returns false, so nothing is computed by itself after a light refresh or a
      stroke; `previewKind()` says "quick" (corner: «ПІСЛЯ · швидкий перегляд»); the real frame comes from
      Apply or from the button, which reads «↻ Перерахувати зараз (точний перегляд)» (with the box ticked:
      «… (не обов’язково)»); with 2 passes, where there is no light way, the corner names the button;
    - `setDetailPreview(on, announce)`: ticking asks for the exact picture of a quick preview that is on
      screen; unticking stops a background run (`stopBackgroundRun` → `/session/stop-background`) and
      starts none; `updateRecomputeButton` also writes the note at the top of the settings (`gLiveNote`).
    - Engine: `start_session` reads `previewLong` from the REQUEST also when the automatic preset
      replaces `params` by the values of a preset (those have no such key; before, the request's word was
      lost there and the window would have got the large pictures all the same).
    - Why it was slow for him is not known. Measured here (stand-in networks, 2 CPUs): the server needs
      about the same time for a stroke at either size (290-610 ms as the painted area grows from 3 % to
      15 % of the frame, brush radius 60; the whole painted zone is filled anew with every stroke -
      `_brush_fill` works per connected zone); what differs is the answer (3.2 times the bytes, two JPEGs
      of four times the pixels for Photoshop to decode) and the background run that started 0.7 s after
      every stroke. Neither can be timed without Photoshop.
  - **The brush: a line, not dots** (three faults, all in the panel; the server always joined the points
    of a stroke):
    - the trace under the pointer was one dot per mouse event. Now the way from the last dot is filled
      (`renderBrushCursorAndDot`: a dot every `STROKE_DOT_STEP` = 0.3 brush diameters, at least
      `STROKE_DOT_MIN_PX`; at most `STROKE_DOTS_PER_MOVE` = 120 per event and `STROKE_DOTS_MAX` = 1,500 on
      screen);
    - a stroke ends where the button was released: the `mouseup` handler adds the place of the release
      when the last move was not there. A quick stroke whose moves never arrived (the window busy with the
      picture of the stroke before - an assumption, read from «робе точки або тянути поленьку») was a dot
      at the place of the press. A release at client (0, 0) counts as "no place" and adds nothing (a
      seatbelt against a line to the corner of the photo; never seen);
    - every dot knows its stroke (`sessState.strokeNo`, `sessState.strokeDots`), and the answer to a mask
      edit takes away the traces of the strokes that were finished before that request
      (`clearStrokeDots(upTo)`, `tracesUpTo` in `sendMaskEditOp`). Up to 4.9.0 any answer wiped every dot,
      also those of a stroke being drawn or waiting in the queue, and reset the trace mid-stroke.
  - **A GPU error costs one run, not the session.** Up to 4.9.0 one error of the GPU during the AI fill
    (or the matting) replaced `self.lama_sess` (`self.matting_sess`) by a processor session with ONE
    thread until the models were loaded anew, and nothing on screen said so - the panel went on naming
    the video card. Minutes per frame is what that looks like, which makes it the SUSPECTED cause of his
    «60-400 секунд» - a guess, not confirmed on his PC. Now:
    - `_run_lama_tiles`: the tile that the GPU refused and the rest of THAT call go to
      `self._lama_cpu_sess` (`_lama_on_cpu`; made when first needed with `_fallback_threads()` = all
      processors but one; dropped with the models); `self.lama_sess` stays and the next call asks it
      again. If the processor session fails too, the error comes out. `_predict_fg_raw` does the same for
      the matting (`_matting_cpu_sess`).
    - `self.cpu_fallback` = `{"lama": reason, "matting": reason}` while the last use of that model ran on
      the processor (popped by the next use that the GPU does alone). `/health` carries it.
    - `stats["timing"]` of `process` (only when LaMa tiles ran): `{fill_tiles, fill_s, fill_ep,
      fallback}`; `_fill_log` collects it over the calls of one `process`. It travels with the answers of
      start and recompute. `_refresh_stale_base` keeps it in `sess["last_timing"]`, and `apply_session`
      passes it on when it computed the real frame itself (`recomputed`) - with the fast window that is
      where the real frame is computed.
    - Panel: `noteComputeStats` writes the line `gTimeLine` in the settings («Останній розрахунок: 12 с ·
      AI-заливка: 90 пл. за 6,3 с (відеокарта)»; marked when it says «процесор») and, on a fallback, puts
      `sessState.cpuWarn` into the corner of the photo for 20 s (`updatePreviewBadge` shows it before the
      preview note; it is set AFTER the auto-preset note, which used to overwrite it); the health banner
      of the panel warns too; after Apply the footer of the panel says «„Застосувати“: N с · AI-заливка:
      …» and the warning (`commitApplyPayloadToPhotoshop`, `fillTimeText`, `cpuFallbackText`).
  - Checks: the new groups `fallback` and `fastwin`; `timing` is left out of the comparisons with v3.2.1;
    `check_http` asserts `cpu_fallback` of `/health`; the window test has 12 new scenarios (92) and the
    settings test 5 new cases (54). In the window test `scenario()` ticks the detailed preview unless the
    scenario says `detail: false` - everything written before 4.10.0 tests the detailed preview - and
    `release()` happens where the pointer was last. `tests/try_defects.py` holds the 54 deliberate
    defects of 4.10.0 (19 in the engine and the server, 35 in the panel).

- **4.11.0** — smoke on a light backdrop, after his report on 4.10.0 («недобре розуміє де дим на світлому
  фоні удебільше розуміє де менше ні і я нажимаю що є дим воно каже ні нема»). Decided alone, no option
  card. NO FRAME WITH SMOKE is among his files: everything below was tuned on smoke DRAWN over his seven
  frames (fractal noise, see section 4) and has never seen real smoke.
  - **What was wrong.** The search of 4.4.0 knows smoke by its fine wisps (band-pass 5 - 35 px of the
    1024 px copy), which only thick smoke has; on a light backdrop the same smoke has about a third of the
    contrast. With `smokeAuto` the protection worked only when the wisps proved smoke (`SMOKE_MIN_SHARE`,
    `SMOKE_MIN_CLOUD`), otherwise the window answered «Диму в кадрі не знайдено…» to the user's own tick.
    A medium cloud drawn over his light frame 1 gave share 0.0216 and largest 0.0053: "no smoke".
  - **The switch is the user's word.** The panel sends `smokeFaint: true` (and still `smokeAuto: true`,
    which a server before 4.11.0 obeys). With it `_smoke_auto` is false whatever was sent, no evidence is
    asked for at any value of the slider, and thin smoke is looked for as well. `stats["smoke"]` carries
    `faint`; `k_maps` and `_clean_signature` carry the key. Without `smokeFaint` the engine does exactly
    what 4.10.0 did (the checks against v3.2.1 and the old presets rely on that).
  - **Thin smoke = soft structure without a direction** (`_smoke_soft_structure`): the smaller eigenvalue
    of the structure tensor of the smoothed lightness, at `SMOKE_SOFT_SCALES` = 2.5 / 5 / 10 px, each on a
    copy reduced so that the scale is 2.5 px there; measure = scale * sqrt(lambda2), and lambda2 must be
    at least `SMOKE_SOFT_MIN_RATIO` = 0.10 of lambda1. A straight edge has one direction and leaves
    nothing. Two things had to be added before that held on real frames:
    - the light is taken out first (`SMOKE_SOFT_FLATTEN` = 40 px, on a quarter-size copy): the fall-off
      of the light along the wall CROSSED by the wall-floor line has two directions too, and read as
      smoke all along the line (12 % of the test frame of the checks at 80 %);
    - past the frame border the values are continued as they came to it (`_continued_past_border`:
      mirrored about the border value). With the usual mirrored border the smoothing bends every slope
      at the border, and both ends of every line that reaches the border were "smoke".
  - **The slider** (`_smoke_by_word`): threshold `SMOKE_SOFT_AT_FULL` = 0.30 at 100 %, +0.003 per percent
    down to `SMOKE_SOFT_USUAL` = 80 (0.36), +0.006 per percent below (0.48 at 60); under `SMOKE_SOFT_FROM`
    = 40 only the wisps count. His backdrops themselves give up to about 0.30 (at 0.30 a fifth of frame 1
    is "smoke", at 0.315 nothing): the thresholds are ABSOLUTE and sit right above the unevenness of HIS
    backdrops - a rougher backdrop or more grain will show more false smoke at the same value.
  - **What is believed where** (`SMOKE_FLOOR_FROM` = 0.70 of the height, the line below which the dust
    search does not listen to the smoke map anyway): above it every cloud of wisps and every soft area;
    below it - the floor next to the feet, where footprints and shadows are soft structure of the same
    kind - a piece counts only when it hangs together (`SMOKE_PIECE_GAP` = 17 px) with at least
    `SMOKE_SOFT_MIN_AREA` = 0.4 % of the frame above the line, or holds a cloud of wisps that proves smoke
    alone. At 100 % everything counts, the floor too («дим стелиться всюди»). So what 4.4.0 gave stays:
    dirt next to the feet is cleaned with the tick on, at any value under 100.
  - **A line is not smoke.** (a) `_smoke_without_lines`: a cloud of wisps that is a thin straight band
    (`SMOKE_LINE_WIDTH` 30 px across at most, `SMOKE_LINE_ASPECT` 4 times as long, filling its box by
    `SMOKE_LINE_FILL` 0.60) is dropped. In 4.10.0 with the slider at 95-100 % ("trust") the wisps along
    the wall-floor corner of his light frame 1 were smoke, the corner tool was gated there and the LINE
    STAYED (steepest change 0.67-0.69 levels/px left of 0.69-0.89; with the tick off 0.03-0.31). This
    may be his «інколи лінія залишається» - not confirmed. (b) The tools for lines get their own map:
    `_smoke_zone_small` returns (all the smoke, its thick part = the clouds of wisps); the second goes to
    `_corner_line_of_frame`, `_detect_vinyl_seam_mask` and `_apply_cyclorama_curve` as `smoke_lines_s`
    (sixth element of the `maps` record of the stage cache, `"smoke_lines_s"` of the analysis). The dust
    search, the stains and the hair search keep the whole map. Without `smokeFaint` both maps are one.
    The price, measured: under thin smoke the corner goes (0.44 -> 0.08 levels/px on the test frame),
    and the smoke in the zone of the cove keeps 39 % (test frame, cloud centred on the corner) to
    76-79 % (his frame 1, drawn haze) of its curls - the cove estimates its correction from the picture
    WITH the smoke. Giving the tools the whole map keeps 98-99 % of the smoke and leaves the line under
    it. The manual says so and offers «Циклорама 0 %» to who prefers the smoke.
  - **Panel.** `smokeNoteText` has a branch for answers that carry `faint`: with the tick on it says the
    share kept and which way the slider goes («…21 % кадру програма бере за дим і не чистить. Частину
    диму все одно зачищено — потягніть «Захист диму» вище (до 100 %); береже бруд — нижче.»), nothing
    kept: «…не розпізнала в кадрі диму… до 100 %», off: «…увесь фон чиститься як звичайний — і дим, якщо
    він там є». An answer without `faint` (a server before 4.11.0) gets the old notes. Two tooltips.
  - **Measured** (GrabCut silhouettes, stand-in fill - indications only). Share of the frame taken for
    smoke on his frames WITHOUT smoke at 60 / 80 / 95 / 98 / 100: frame 1: 0 / 0 / 0 / 0 / 24.0; 3384:
    1.1 / 2.0 / 2.3 / 2.4 / 19.7; 2: 0 / 0 / 0 / 0 / 24.3; 3: 0 / 0.7 / 0.7 / 0.7 / 17.9; 3413: 0 / 0 / 0
    / 0 / 17.9; 3411: 0 / 0 / 0 / 0 / 13.5; 3417: 5.7 / 7.8 / 14.1 / 16.2 / 31.5 (the rim of the lamp's
    light). Curls kept after cleaning, by curl contrast >= 6 / 3-6 / 1.5-3 / 0.7-1.5 / 0.3-0.7 levels:
    frame 1, one cloud of density 0.25 - tick off or 4.10.0 at 80: 80 / 59 / 55 / 60 / 59 %; 4.10.0 at
    95: 87 / 75 / 62 / 61 / 48; now at 80: 96 / 95 / 89 / 76 / 58; at 95: 96 / 95 / 91 / 90 / 55; at 100:
    96 / 96 / 92 / 92 / 60. Frame 1, haze of density 0.08 over the whole frame - 4.10.0: 96 / 86 / 50 /
    50 / 39; now at 80: 98 / 98 / 89 / 71 / 45; at 95: 96 / 96 / 92 / 84 / 82. Frame 2 (dark), density
    0.25 - 4.10.0 at 80: 98 / 87 / 63 / 60 / 55; now at 80: 100 / 91 / 83 / 96 / 67. The maps take
    about 0.68 s instead of 0.51 s (2 CPUs).
  - Checks: `check_smoke` covers every rule above with drawn thin smoke (soft billows of two levels, no
    wisps), a soft line across the wall, the seam at 100 %, the corner with and without thin smoke over
    it and the window answers; the random walks of `stage`, `quick` and `session` toggle `smokeFaint`
    (they did NOT notice a `_clean_signature` without the key - `check_smoke` asks for that itself: Apply
    that brings the word back must compute the real frame anew); the window test has 4 new scenarios
    (96; its stand-in server mirrors the rules, `smokeOld` plays a server before 4.11.0).
    `tests/try_defects.py` holds the 30 deliberate defects of 4.11.0 (23 in the engine, 7 in the panel).

- **4.12.0** — thick smoke, the mixer brush, a recompute that starts over, after his messages of
  2026-11-23. Decided alone, no option card. The smoke part was made on ONE real frame (`0Q5A2507`).
  - **Thick smoke is not gear.** Thick smoke lit against a darker wall has strong edges (Sobel sum > 26
    on the 1024 px copy). Groups of strong edges were left out of the smoke search since 4.4.0 ("the
    outline of a thing is no smoke") and, when they had a "body" or touched the left / right / top
    border, were GEAR - and with «Прибирати стійки…» on, `stand_remove` took the dark wall inside those
    groups (`L < 72`) and what touched the frame border: on his frame the top band of the cloud was
    inpainted (his result: mean change 3.4 levels there, p95 12; the curtain was removed as it should).
    With the user's word (`smokeFaint` and the switch on) `_edge_groups_of_smoke` now decides per group:
    smoke when (a) it has no direction - `_smoke_soft_structure` computed with nothing but the person
    left out is at least `SMOKE_EDGE_SOFT` = 1.0 over `SMOKE_EDGE_SHARE` = 0.70 of the group - and (b) it
    has no hard edge - over the steepest fifth of its edge pixels (`SMOKE_EDGE_STEEP` = 0.80) the median
    of "contrast within `SMOKE_EDGE_SPAN` = 13 px over the slope" is at least `SMOKE_EDGE_WIDTH` = 4 px.
    Such a group leaves `stand_mask` and `edges_any`: it is searched for smoke like any backdrop (and
    found as wisps, so it is THICK smoke), it is not kept as gear and never marked for removal.
    Measured on `0Q5A2507` (GrabCut silhouette): the seven groups of the cloud: share 0.99-1.00, width
    4.6-7.2 px, slope p90 4.5-9.0 levels/px; the black curtain: share 0.00 and 0.32; a shadow's edge:
    share 0.00 (width 8-9 px - soft, but it has a direction). On his six other frames with the tick ON
    the rule would also take five groups of real gear for smoke - out-of-focus things at the frame edge
    (`0Q5A3413` left softbox: width 5.2; `0Q5A3417` left softbox 4.7; `0Q5A3384` 4.8, 4.8, 4.8): they
    are then kept untouched as smoke, as they were kept as gear, but «Прибирати стійки…» no longer
    removes them while the smoke tick is on (their black cores stay gear through the dark-border rule).
    A cap on the slope (smoke at most 9.0, that gear 17-26) would keep them gear and was NOT built: it
    scales with the contrast of the smoke, and smoke taken for gear is the worse mistake.
    After the change, his frame, slider 95: smoke 45 % of the frame (thick 18 %), nothing of the cloud
    marked for removal, the curtain still is; a full run changes no pixel of the cloud. The maps take
    0.98 s here (4.11.0: 0.65 s): the soft measure is computed twice.
  - **The mixer brush** (`mixOn`, `mix` 0-100; `_mix_strength`, `_mix_brush_small`, stage `"mix"`, key
    `k_mix`). What he does by hand was measured on his retouch of frame 2 against the frame as shot
    (aligned by template matching: no scaling, offset -80 / +36 px): in flat backdrop cells the texture
    is at 0.51 / 0.47 / 0.40 / 0.43 / 0.57 of the frame's in the bands 0-2 / 2-6 / 6-16 / 16-40 / 40-100 px
    - about a half in EVERY band, the grain included. That is a blend, not a blur. So the stage blends
    the cleaned frame towards a smooth copy of itself: at every pixel the value of the PLANE that fits
    the backdrop alone around it (`_plane_average`: Gaussian weights of `MIX_SIGMA` = 1.6 % of the long
    side, nine weighted sums in float64, Cramer's rule; the plain average where too little is around),
    made on a copy of 1400 px (950 in the light preview) - 1.9 s here. A plain masked average is
    one-sided next to the person, a shadow or smoke and pulls the tone there towards what lies further
    away: 1.6 levels next to the person of the test frame at 100 %, a faint rim; the plane: 0.2. Weight =
    strength x where the brush may go (the outward ramp of the person, not the gear, not the shadows
    x 1.35, not the smoke map x 1.25, only where the average had something to lean on). Above 65 % the
    grain that the blend would take below `MIX_GRAIN_MIN` = 0.35 is put back (band below
    `MIX_GRAIN_SIGMA` = 1.5 px, in bands of 1024 rows): at 100 % without it the texture of 6-40 px rose
    to 1.5-1.75 of the frame's - the staircase of 8 bits. The layer alpha is the brush map, not times
    the strength (the blur stage multiplies both and so works with the square of its strength). The
    stage runs after the second pass and before the clothing; its strength is not part of its cache key.
    On `0Q5A2507` at 50: wall 0.51 / 0.51 / 0.54 / 0.85 / 0.92, cloud 1.00, person untouched; no
    measurable time. The blur stage was NOT changed (it still ignores the smoke map: the comparisons with
    v3.2.1 run with blur and smoke on).
  - **The newest values win** (`recompute_session`, not background): every such call takes a number
    (`_fg_seq`); a call that finds a higher number when its turn comes answers `{"superseded": True}`
    at once, and a running one raises `JobSuperseded` at its next `_checkpoint()` (the hook of the
    background runs, `_bg_local.check`, set and cleared around the computation). The session is
    untouched, the finished stages stay cached. A brush stroke, Apply and the background runs are as
    they were.
  - **Panel.** (a) `recomputeInteractiveSession` no longer queues: a call during a run sends its request
    at once, counts as the newest (`recomputeRun`) and whatever an older request brings back is dropped
    (a server before 4.12.0 finishes the older run first: the same code handles it); while the progress
    card is up the newer run is a full one too. (b) The smoke tick and `gBtnSmoke` call
    `recomputeExactNow()` (full, with the card) instead of a light refresh. (c) `dlgBtnRecompute` on the
    bottom bar. (d) `brushKeyOf`: `e.code`, the characters `[ { х` / `] } ї ъ`, `keyCode` 219 / 221; step
    by size (`brushKeyStep`); a focused check box no longer swallows the tool keys. (e) `mixEnabled`,
    slider `gSlMix`, pill `dlgWrapMix`, switch `gBtnMix`: a setting of the user (kept in
    `user_settings.json` as `mixOn` / `mixStrength`), sent with every request and in every set of the
    automatic preset, never written into a preset. (f) NO `<label>` ANY MORE: his screenshot shows the
    text of every `<label>` (three rows of the settings, «Make Mask») large, grey and running over the
    rows below, whatever the style sheet says. The boxes are `<div data-check="id">` now;
    `bindCheckBoxes` ticks the check box on a click anywhere in the box and calls the handler kept by
    `onCheck(id, fn)` - no synthetic event. Whether that cures the look can only be seen on his PC.
  - Checks: groups `restart` and `mix` are new; `check_smoke` got the thick-smoke part (a drawn cloud
    with strong soft edges, a stand in focus, a soft straight pole, a knot of hard pieces, on a dark and
    on a light wall); the walks toggle the mixer brush with random numbers of their own; the window
    test has 106 scenarios, the settings test 63 cases; `tests/try_defects.py` holds the 44 defects of
    4.12.0.

## 3. Current state — update this at the end of every session

_Last updated: by the agent of the first session, after releasing 4.12.0 (the answer to his messages of
2026-11-23 on 4.11.0)._

- **Released:** 4.12.0, tag `cvp2-v4.12.0`, as a pre-release. Direct download:
  `https://github.com/malysh-sl2/CleanVinylPro-Beta/raw/cvp2-v4.12.0/CleanVinylPro2.zip`
- **Owner's progress:** 4.2.0 to 4.11.0 have been installed and work on his PC (program in
  `D:\Plugin Photoshop\CleanVinylPro2`, models in `D:\model AI fotoshop`, LaMa on `CUDAExecutionProvider`,
  Python 3.12.10). So the `.bat` files, the installer, the GPU, the real models and the panel HAVE run on
  Windows. The old program (`D:\CleanVinylPro`) is removed from his PC. His report on 4.9.0 (2026-11-22,
  section 1) is about speed only: the brush is very slow and leaves dots, a preview takes 60 to 400
  seconds, the soft face of the earlier window is fine, speed is what matters; 4.10.0 answers it. He said
  nothing about what 4.9.0 was made for (the line right of the dress, the rim, the hairs) and the zoom
  keys do not matter to him. His report on 4.10.0 (the same day, section 1): the brush is fast and draws a
  line; one computation took 30 s, of them the AI fill 15 s for 121 tiles ON THE VIDEO CARD; smoke on a
  light backdrop is understood badly and the tick is answered with "no smoke"; «інколи лінія залишається»;
  what is a "GPU failure" and how to check for one. 4.11.0 answers the smoke; the rest was answered in
  words (reply #19). On 4.11.0 (2026-11-23, section 1) he sent his first frame with real smoke, its
  result and a screenshot, and a list of wishes; 4.12.0 answers them (reply #20). In that result thin
  smoke and the floor were kept, the top of the thick cloud was painted over. One computation took 17 s
  there, 38 tiles in 5.2 s on the video card. **He has not reported on 4.12.0 yet.**
  The path to the plugin list of Creative Cloud (Stock & Marketplace → Plugins → Manage plugins → the three
  dots → Uninstall; the same list opens from Photoshop with Plugins → Manage Plugins) is in section 6 of
  the manual since 4.8.0. Whether his Creative Cloud shows these names in English or in Ukrainian is not
  known.
- **Checks:** the quick run of `tests/run_checks.py` ended with ALL CHECKS PASSED (42 results in
  1,567 s; 96 scenarios of the panel test and 54 cases of the settings test among them) on
  2026-11-22 (the clock of the sandbox), with NumPy 2.4.6 and OpenCV 5.1.0, set up as in section 4, with
  nothing running next to it. (One sentence of the manual and the archive were changed while that run
  was at the group `dark`; the two groups that read them, `server` and `plugin`, came after it.)
  Deliberate defects for what is new in 4.11.0 (`tests/try_defects.py`), put in one by one: 30 (23 in the
  engine, all checked by the group `smoke`, and 7 in the panel). All are caught by the checks as they
  are now, each by the check of the rule it breaks. They ran in a copy of the tree after the last
  change of the engine, the panel and the checks: 29 in one run of 1,739 s, the thirtieth
  (`SMOKE_PIECE_GAP`) by itself in 78 s.
  Holes found while 4.11.0 was built, all closed:
  - "under 40 % only the wisps count" was asked with the thin cloud of the check, which the threshold
    of 40 % (0.60) never reaches: a soft search that also ran under 40 % passed. There is a strong soft
    cloud without wisps now (95 % of it is smoke at 40 %, nothing at 39 %);
  - `_clean_signature` without the new key passed the random walks of `quick` and `session`: a step
    that changes this one key, with the protection on and no other change before the next Apply, hardly
    ever comes up. `check_smoke` asks for it itself now (Apply that brings the word back must compute
    the real frame anew). A new key of the signature needs its own question, not the walk;
  - "every step up reaches thinner smoke" was first asked of a cloud that 80 % already takes to 92 %,
    with three points of room. Two defects that only made the search MORE sensitive (the light not
    taken out, the mirrored border) were then "caught" by that rule before their own check was read.
    It is asked of a thinner cloud now (74 % at 80, 86 % at 95), and the two are caught by the line
    across the wall;
  - limits of `check_smoke` had been set on a frame where 12 % was false smoke (the light that a line
    crosses); when that was cured they failed. They are set on what is drawn into the frame now.
  Added without having seen a hole: a thin arc among the shapes that must NOT count as a line, so that
  the condition "fills its box" has a shape of its own.
  Not in the list, because no check here can tell: which smoke map the corner finder and the seam
  search get (on every frame of the checks the gate of the cove decides).
  Holes found while earlier versions were built are told in the history of this file (4.10.0: at
  `64700aa`; 4.9.0: at `78a08b8`; 4.8.0: at `0f4cb46`). Their lessons stay rules: read the reason after
  "<-" of every caught defect - when it names another rule than the one the defect breaks, the check
  that should have noticed is too weak (the runner shows only the FIRST failed rule: put the defect in
  by hand and read the whole list when in doubt); read the NUMBERS in that reason; a new rule can empty
  an older scenario, so run ALL the defects again after the last change; and a defect that changes
  nothing visible does not belong in the list.
  The runners of earlier versions are gone or replaced (4.10.0: 54 defects, in the history at `64700aa`;
  4.9.0: 35, at `78a08b8`;
  4.8.0: 71, at `0f4cb46`; 4.7.0: 29, at `c3be3ed`; 4.6.0: 34, at `50bae15`; 4.5.0: 71 and 4.4.0: 41,
  never committed); their checks are still in `tests/run_checks.py`.
- **Decided by the agent alone for 4.12.0** (no option card; change it if he says otherwise):
  - the smoke tick and the smoke switch of the settings recompute IN FULL, with the progress card (he
    asked for "a recompute"; every other control still gives its light refresh, and the button is at
    hand now). The smoke slider is a slider like the others: light refresh;
  - while the card is up, a change restarts a FULL run; while a light refresh runs, a light one;
  - the button on the bottom bar leaves the settings open (in his screenshot they are open while the bar
    runs); the button inside the settings still closes them, as before;
  - `[` and `]` change the size by 2 / 5 / 10 / 20 for a brush under 20 / 60 / 120 / above (it was 6);
  - the mixer brush: a blend at 50 % by default (his own retouch of frame 2); its tick is a setting of
    the user, NOT a part of the presets - so the automatic preset cannot switch it off from frame to
    frame; a slider row in the settings although he asked for the tick only; the grain never under 35 %;
    it leaves the shadows, the gear and protected smoke alone; it is drawn in the light refresh;
  - thick smoke: decided per group of strong edges, leaning towards smoke (see section 2, «4.12.0», for
    the gear that goes with it while the smoke tick is on);
  - the floor of his smoke frame stays protected (45 % of the frame is smoke at 95 %): only dust is
    taken there. He did not complain about the floor;
  - the `<label>` rewrite, on the evidence of one screenshot.
- **Not run in Photoshop yet (4.12.0):** all of it. In particular:
  - whether the captions of the check boxes are drawn in place now, and whether a click on a caption
    ticks its box there (it does in jsdom). If they still look wrong, the cause is not `<label>`;
  - whether `[` and `]` reach the window at all (Ctrl + Z does; plain keys were never confirmed), and
    what Photoshop says about them (`e.code`, `e.key` or only `keyCode`);
  - the look of the pill «Мікс», of the new slider row (the settings are crowded: 13 rows) and of the
    third button on the bottom bar;
  - how fast the real server lets go of a run: between two tiles of the AI fill, between stages - a
    second at most is expected, nothing was measured with the real networks;
  - the mixer brush on his taste, and next to a real silhouette (hair, a veil);
  - thick smoke on other frames: a brighter cloud on a black wall, gear standing in the smoke.
- **What 4.11.0 gives on his frames:** the tables are in section 2, «4.11.0» («Measured»): the share of
  each of his seven frames that is taken for smoke at 60 / 80 / 95 / 98 / 100 %, the curls of drawn smoke
  that survive the cleaning, the corner of frame 1 with the tick on. All of it with DRAWN smoke, GrabCut
  silhouettes and the stand-in fill. How to draw such smoke again: section 4, «Traps already paid for»
  («Drawn smoke»); the probe scripts were not kept.
- **Decided by the agent alone for 4.11.0** (no option card was shown; he had described the fault and
  the wish in one sentence; change it if he says otherwise):
  - the tick is his word at EVERY value of the slider (before, only 95-100 % meant "trust me"), and the
    slider now means "how thin a smoke to keep". Nothing was changed in the presets: «Зйомка з димом»
    keeps the protection on at 95 % (with «Циклорама» 0 - the corner tool is off in that preset anyway),
    every other preset keeps it off with the slider at 80 % (the dark ones 70, «Делікатний» 85) - that
    is the value the tick at the top of the window then works with;
  - the usual value stays 80 %; under 40 % only wisps count; 100 % keeps everything soft, the floor too,
    although that is 13-32 % of a frame without smoke (the manual says so);
  - the floor next to the feet keeps the rule of 4.4.0 (dirt is cleaned) at every value under 100 %:
    thin smoke that lies on the floor only is therefore lost unless he goes to 100 %;
  - a line is never smoke, and under THIN smoke the corner tool works although it smooths the smoke
    next to the line (40-80 % of the curls stay). The other way round (the smoke wins, the line stays)
    keeps 98-99 % of the smoke; he was told in the manual and in the reply that «Циклорама 0 %» gives
    that, and asked to say which he prefers;
  - the note in the corner always names the share of the frame and both directions of the slider, also
    when everything is fine - it is the only way he can see what the program took for smoke. A picture
    of the protected zone in the window (as the mask view shows the cleaned zone) was NOT built; it is
    the natural next step if the words are not enough;
  - `smokeAuto: true` is still sent, so a server before 4.11.0 behaves as it did.
- **Not run in Photoshop yet (4.11.0):** all of it. In particular:
  - REAL SMOKE. Not one frame with smoke was ever available. Whether the soft search finds his smoke,
    whether 80 % is a sensible usual value for it and whether the floor rule cuts his smoke off at the
    floor line (a straight edge of "kept / cleaned" at 70 % of the frame height would be the sign) can
    only be seen on a frame of his;
  - how much false smoke there is next to the person with the real silhouette: the matting network
    draws hair and veils differently than GrabCut, and a soft half-transparent edge is soft structure;
  - the fill: with the smoke map larger than before, the real LaMa gets other holes to fill next to
    smoke. Not looked at;
  - which line «інколи залишається» for him. One cause was found on his frame 1 and removed (the tick
    with the slider at 95-100 %); whether he ever had the tick on is not known;
  - the look of the longer smoke notes in the corner of the photo and of the two rewritten tooltips
    (drawn only in jsdom).
- **What was measured for 4.10.0** (stand-in networks, the two processors of the sandbox, frame
  `0Q5A3411` at the working size 720 x 1080; an indication of the server's share only - what Photoshop
  needs to take the answer and to show two JPEGs cannot be measured here):

  | window pictures | a stroke on the server | answer to a stroke | answer of the start |
  |---|---|---|---|
  | 2160 px («Детальний перегляд») | 225-274 ms | 1.75 MB | about 3.2 MB |
  | 1080 px (the fast window) | 147-183 ms | 0.54 MB | about 0.85 MB |

  - That is for the first strokes of a small brush (radius 28). 40 such strokes side by side, 1080 px:
    150-200 ms at first, 250-290 ms once 8.6 % of the window is painted; Apply after them 1.4 s.
  - A wide brush (radius 60) over the whole left floor, 30 strokes, the bright green growing from 3.5 %
    to 17 % of the window: 289, 297, 341, 485, 560, 609, 434 ms at strokes 1, 5, 10, 15, 20, 25, 30 with
    1080 px and 323, 311, 407, 522, 618, 509, 545 ms with 2160 px. So with a large painted area the
    server needs the same time for either size: the whole connected painted zone is filled anew with
    every stroke (`_brush_fill`). **4.10.0 does not shorten that part.**
  - Where 250 ms of such a stroke go (1080 px, 8.6 % painted): `_brush_fill` 119 ms, the two JPEGs 94 ms
    (57 of them the mask picture `_encode_overlay_jpg`, which travels with every answer although the
    mask view is usually off), the step-back history 25 ms.
  - How to measure again (the probe scripts were not kept): `H.make_engine(E, sil)`,
    `eng.start_session(img, 8, dict(H.STD, speedMode="quality", cycCurve=65, previewLong=1080))`, then
    time `eng.edit_session_mask(sid, "stroke", pts, radius, False, False, 45.0, 1.0)` with `pts` a list
    of `{"x": .., "y": .., "norm": True}`; `cProfile` around ten of them.
- **Decided by the agent alone for 4.10.0** (he left the choice - «або зменш або верни»; no option card
  was shown; change it if he says otherwise):
  - the fast window comes back as the DEFAULT, and what 4.8.0 brought stays as a checkbox («Детальний
    перегляд (повільніше)»). An existing installation gets the fast window too: the setting did not
    exist before, so nothing keeps the behaviour of 4.8.0 for him;
  - the size of the window pictures changes with the next opening of the window, not at once;
  - after a GPU error the processor session gets all processors but one;
  - the warning stays in the corner of the photo for 20 s; the time line of the settings and the time in
    the footer after Apply are always written, not only when something is slow;
  - a mouse release at (0, 0) counts as "no place";
  - the server's own time for a stroke was left as it is (above), and so was the mask picture that
    travels with every answer: both are named in the reply as the next steps if the brush is still slow.
- **Not confirmed about 4.10.0** (it runs on his PC - report of 2026-11-22: the brush is fast and draws a
  line; «Останній розрахунок: 30 с · AI-заливка: 121 пл. за 15 с (відеокарта)», so the GPU works and one
  computation of a frame takes half a minute there):
  - WHY the brush was slow before. The assumption was that Photoshop needed long to take and show two
    JPEGs of 2160 x 3240 per answer, and that a background run started after every stroke; the cure
    worked, the cause was never seen;
  - whether Photoshop really drops mouse moves while the window is busy (read from «робе точки або
    тянути поленьку»), and whether `mouseup` carries the place of the pointer there. If it does not, the
    end point is simply not added and a stroke is what it was in 4.9.0;
  - the GPU: whether an error such as "out of memory" leaves the GPU session usable for the next run (if
    not, every run falls back and the warning shows every time - visible now, and a restart of the
    server cures it as before); how fast LaMa is on his processor with all cores but one; that the
    second copy of a model fits into his RAM. He asked what a "GPU failure" is and how to check for one
    (reply #19: nothing to check - the time line says «(відеокарта)»; «(процесор)» and the ⚠ note in the
    corner of the photo mean that the card refused);
  - **whether a GPU error is what made his previews take 60-400 s at all.** It is the one cause found in
    the code that gives such times; nothing from his PC confirms it, and his one time line shows the
    video card at work. The warning never came up in what he wrote;
  - whether he has seen the checkbox «Детальний перегляд» and the footer text after «Застосувати» (he
    quoted the time line, so the settings were open).
- **What 4.9.0 gives on his frames** (stand-in networks, section 4: the same engine code as on his PC,
  but another silhouette and another fill - an indication, not a proof):
  - `0Q5A3417` (automatic preset «Темний дальній план»): the thin line right of the dress is gone
    (`corner_hair` 5 pieces). The rim at the left hem, row 4500, x 808-828 of the frame: 50 50 48 50 38
    where 4.8.0 gave 53 55 58 59 42 (the last number is the dress). The floor above the train, 10 px from
    the dress against 30 px from it: 4.8.0 28 / 46 at x 2250 and 17.5 / 33 at x 2850; now 42 / 47 and
    32 / 33. The window flow (light refresh 2.2 s, background recompute 8.4 s here) gives the same frame
    as the direct call.
  - the five other frames (`1.jpg`, `2.jpg`, `3.jpg`, `0Q5A3384`, `0Q5A3413`), slider at 0, against
    4.8.0: 0.11-0.37 % of the frame differs by more than one level, almost all of it within 12 px of
    the person; inside the person nothing.
  - the hair slider, marked pixels at 25 / 50 / 75 / 100: 3417: 2,482 / 3,094 / 4,798 / 8,679; `1.jpg`:
    4,119 / 8,340 / 8,511 / 8,511; `2.jpg`: 0 / 3,235 / 5,882 / 7,070; `3.jpg`: 0 / 0 / 0 / 3,314;
    `0Q5A3384`: 30,196 / 32,161 / 44,869 / 59,582; `0Q5A3413`: 0 / 0 / 3,603 / 4,761. Every mark was
    looked at: at 100 one to three places per frame, all at the hairdo, real hairs in each; nothing at a
    face, a hand or the clothes. The search takes 0.5-1.6 s per frame here.
    What stays at 100 on 3417, seen in a strongly stretched view: the loops of hair around the forehead
    and the long hairs that lie along the back of the head (a wisp, and hairs along the outline, stay by
    rule), and single hairs fainter than the threshold. He may well mean those too - he was asked.
  - with the slider at 100 on 3417 the frame away from the marked hairs (more than 100 px) differs from
    the slider at 0 on 2,020 px, by 4 levels at most, all above the waist (see «4.9.0» in section 2).
- **Decided by the agent alone for 4.9.0** (no option card was shown; change it if he says otherwise):
  - the hair slider is at 0 in every built-in preset, and a preset saved before 4.9.0 means 0: the tool
    repaints the wall next to a head, so he switches it on himself;
  - what a hair is: it begins at the hairdo, lies within 0.6 head widths of the person and between the
    top of the head and 1.8 head widths below it, and ends in the open. A line that is still there at
    the end of that zone or at the frame border is a cable or a stand and stays;
  - the tool is careful rather than thorough: a wisp, the fuzz of the outline and the finest hairs stay;
  - the first pixels of a removed hair stay (the repair obeys «Захист моделі та країв» like every repair);
  - the tone stages reach the person at every position of «Захист моделі та країв»; `toneEdge` and
    `cornerHair` are request parameters without a switch in the panel;
  - the thin line of a joint is taken only where the corner tool works on that joint; nothing new
    happens with «Циклорама» at 0.
- **Not confirmed about 4.9.0** (it runs on his PC - his report of 2026-11-22 is about its speed - but he
  wrote nothing about the cleaning). Still unknown:
  - the rim along the hem and the shoe with the REAL matte. The tone gate follows the matte of the real
    network and the edges of the photo; here the silhouette of 3417 was a GrabCut outline corrected by
    hand (MediaPipe alone is not usable on that frame). Where the real matte is soft over a wide stretch
    (tulle, loose hair) the tone shift is partial across it; that is meant, but nobody has seen it;
  - whether the thin line right of the dress is found on his PC as it is here (the corner finder and the
    line search do not use the networks, but the visible part of the floor depends on the silhouette);
  - the hair tool with the real matte and the real LaMa. Which hairs are found depends on the outline:
    a hair that the network draws as part of the person is inside the person and stays; a looser
    outline swallows the root of a hair. How the wall is refilled depends on LaMa (here: OpenCV's
    Telea in the fast mode and a stand-in in the quality mode);
  - whether the hairs he meant are the ones the tool takes - he was asked to circle them;
  - the look of the new slider row in the panel (it was only drawn in jsdom).
- **Decided by the agent alone for 4.8.0** (he chose "the cleaned photo stays on screen" and "remove the
  2"; the rest was not asked - change it if he says otherwise):
  - the exact picture is asked for after 0.7 s of quiet (`EXACT_DELAY_MS`);
  - a mask he switched on himself stays on through his strokes; a stroke over «ДО» brings the cleaned
    photo back; the three actions on the whole mask say in words what they did;
  - Ctrl + 0 (fit) was added to the two keys he asked for;
  - new layers lose the 2 as well («Чистий вініл (AI)»); the folder, the files, the ids and the port keep it;
  - with his own mask ("invert + brush") the exact picture does not come by itself; Apply computes it;
  - the corner label is amber while a quick preview is being refined and green for the exact picture;
  - a slider that is taken stops the background run at once (Blend and Clothing do not);
  - the window pictures are 2160 px and not more (section 2 says why); the cleaned backdrop is no sharper
    than before;
  - the icon: nothing can be done about Creative Cloud; the plugin icon was made opaque for Photoshop's
    own list of plugins.
- **Not confirmed about 4.8.0** (it runs on his PC - his screenshot shows its big window - but he wrote
  only about the cleaning). Still unknown:
  - whether Photoshop passes Ctrl + «+» / «−» / 0 and the right mouse button to the window of the plugin
    (if not, they do nothing; the wheel, Space + mouse, the middle button and the Hand tool stay);
  - how long the background recompute takes on his GPU, and whether the percent in the corner label moves;
  - whether pictures of four times the pixels slow the brush down in Photoshop (two JPEGs are decoded
    per answer); measured here: the server needs about 20 ms more per answer;
  - how Photoshop scales a 2160 px picture down in a small window (the window opens at 1020 x 740): it
    may look grainy there (section 2);
  - the look of the opaque plugin icon in Photoshop's list of plugins;
  - the renamed panel: the plugin id is the same, so the settings and presets should stay - not seen.
- **What the brush of 4.7.0 does on his frames** (stand-in silhouette, section 4; strokes made by script,
  radius in window pixels; "change" = largest / mean difference from the layer without the stroke, in
  levels of 255):

  | frame | stroke | 4.7.0 |
  |---|---|---|
  | `0Q5A3384` grey | soft, r 28, over the light spot at the top-right border | change 12 / 3.59; the spot goes from 56.1 to 52.8 with 52 around it; no edge at five-fold contrast (the stroke of 4.6.0 left an arc with a hard edge) |
  | | soft, r 16, floor in front of the knee | 8 / 1.53 |
  | | soft, r 16, across the shadow of the hand | 7 / 1.26; the edge of the shadow stays sharp (32 / 2.78 with one-number thresholds) |
  | | soft, r 8, a dab inside a shadow | 6 / 1.29; the shadow stays a shadow |
  | | soft, r 10, along the edge of a shadow | 7 / 1.32 (14 / 3.69 and a faint lighter patch before `BRUSH_SECOND` was gradual) |
  | | soft, r 12, the floor bottom right | 16 / 1.93 |
  | `1.jpg` light grey | soft, r 30, a sweep under the toes | 14 / 2.42; the person untouched (before `BRUSH_MOST` the zone came out 7-14 levels darker than the floor had been) |
  | | nearly the whole backdrop painted (69 % of the window) | mean change 2.76 (36.6 before `BRUSH_RING_MIN`), the person 0; Apply 4.5-6.5 s, peak memory 1.9 → 2.2 GB |
  | | "fill", then Apply | 0.21 s; the person untouched; a step back gives the same layer |

  The window against the layer inside the painted zones: mean 0.7-1.4 levels (1.0 outside them), 99 % of
  the pixels within 4. A stroke took 100-270 ms and Apply 0.4-1.0 s on the two CPUs of the sandbox.
- **What the cleaning gives on his frames since 4.6.0** (stand-in networks, section 4; the same engine code
  as on his PC, but another silhouette and another fill; 4.7.0 did not change the cleaning):

  | frame | preset the automatic picks | 4.5.0 | 4.6.0 |
  |---|---|---|---|
  | `0Q5A3413` black, stool | «Темний дальній план» | corner looked for at 0.766 (the stool's shadow); the real corner at 0.59 stays, the floor at 0.69-0.80 is flattened | corner at 0.589; the tone down the frame at x 0.88 runs 18.6, 19.0, 19.3, 19.8 where it stepped 18.6, 18.2, 15.1; nothing changes inside the stool or along it |
  | `0Q5A3384` grey, hard shadows | «Дальній план» | "joint" of 93,033 px across the floor; gear zones 5.2 % of the frame with the dirt kept in them | no joint; gear zones 2.3 %; the scratch bottom right, the blotches under the knee, the scratch next to the jeans and the spot inside the hand's shadow are marked and repaired |
  | `1.jpg` light grey | «Дальній план» | | the real joint at 0.79-0.81 of the height, on both sides, as before |
  | `2.jpg` dark grey | now «Темний дальній план» (was «Дальній план») | | the two presets differ on 0.19 % of the frame by more than one level |
  | `3.jpg` black | «Темний дальній план» | | the same lines as 4.5.0 (104,706 px marked by the seam search in both) |

  Not solved on these frames, and said to him: the light spot at the top-right border of the grey frame is
  evened (no patches any more) but still about 10 levels lighter than the wall around it - the stain stage
  takes a spot of that size for light. (The soft brush of 4.7.0 evens it: the table above.) On the right
  side of frame 3 the joint runs along the rim of a pool of light and is not taken as a line; the dust
  search repairs bits of it and a dashed remainder shows in a stretched view (4.5.0 did the same).
- **Decided by the agent alone for 4.6.0** (he was not asked; change them if he says otherwise):
  - 40 as the limit of a dark backdrop: between his dark grey (31) and his grey (52), nearer to the first;
  - the light spot at the frame border stays (he is told that the brush of the big window repaints it);
  - the two new rules cannot be switched off in the panel (`gearBody`, `shadowSpots` exist only as request
    parameters);
  - a small shadow of a small thing that lies wholly inside a bigger shadow is repaired like a dirty spot
    (it cannot be told apart; the eraser brings it back);
  - nothing was done about the three questions he has not answered (below).
- **Decided by the agent alone for 4.7.0** (he chose "soft, plus a switch" and "quality only"; the rest
  was not asked - change it if he says otherwise):
  - the fade of the soft brush is one brush radius wide and centred on the cursor circle; there is no
    softness slider; soft is the default; one choice serves the brush and the eraser;
  - the soft brush keeps off the person, the hard one does not;
  - a painted zone is made of the backdrop's own tone and grain, with no AI fill (LaMa is not called for
    strokes any more): whatever lies under a stroke - a stain, a cable, a stand - becomes plain backdrop;
  - a stroke across or along the edge of a shadow keeps the tone and renews only the grain;
  - nearly the whole backdrop painted over keeps its tone;
  - Ctrl + click on the brush shows the whole layer and repaints nothing;
  - for removing the old program he got steps, not a helper `.bat` (it could not be tried on Windows).
- **Not confirmed about 4.7.0** (he wrote only that it works and that the old program is removed):
  - the look and the place of the two edge buttons (36 x 36 icons under the size box of the left column);
  - the soft brush next to the real silhouette: it keeps off whatever the real model calls the person, a
    prop included, and paints over a part of the person that the model misses;
  - time: every opening of the window and every Apply now uses the full AI fill; if he worked in the fast
    mode, both take longer. It cannot be timed here;
  - the steps for removing the old program were written from the files of both programs; nobody has
    walked them on Windows. They rename the old folder before it is deleted so that he can go back.
- **Not run in Photoshop yet (4.6.0)** (he wrote about 4.6.0 without saying how these went): in particular:
  - the real silhouette. The stand-in missed the stool, a leg and a shoe under the dress on the black frame
    and the train of the dress on frame 1; they were added to the stand-in matte by hand. His result of
    4.5.0 left the stool untouched, so the real model very likely takes the stool as part of the person;
    with the stool NOT in the silhouette the stand-in run darkened a narrow wedge between two stool legs
    (700 px, up to 50 levels; the old gear rule did the same);
  - the real LaMa fill of what is newly marked (the scratch, the spot inside the shadow): Telea leaves
    faint dotted remnants along the scratch;
  - of 4.5.0, still unconfirmed: opening the backup folder from the panel, the look of the new buttons,
    the one-time preset moves. (Ctrl+Z works in Photoshop: he confirmed it.)
- **Merging:** pull request #1 (`arena/33f1ced8-cleanvinylpro-beta` into `main`) is open and deliberately not
  merged yet: fixes that follow his report on 4.12.0 should come from the session that knows the code. He
  asked what merging into `main` means and was told: the version is already published and can be downloaded;
  merging only marks it on GitHub as the main one and changes nothing on his PC; he should write «зливай»
  when he wants it. Merge it when he writes that or when the session ends (section 6). If `main` already
  contains this file, that has happened. Merging also removes the folder `CleanVinylPro/` from `main`.

### Open questions (ask when he reports on 4.12.0)

- New with 4.12.0: is the thick smoke of `0Q5A2507` kept now with «Прибирати стійки…» on, and is the
  curtain still removed? Is the mixer brush what he does by hand - is 50 % right, should it go over the
  shadows or closer to the person? Do `[` and `]` work in Photoshop? Do the captions of the check boxes
  look right now (a screenshot of the settings was asked for)? Does a change during the bar restart the
  run fast enough? More frames with smoke were asked for.

- From 4.11.0: he sent a frame with real smoke (dark grey wall, not a light one) and its result: thin
  smoke and the floor were kept, thick smoke was not (4.12.0). Not answered: what share the note names
  on his frames and where he ends up with the slider. Which line «інколи залишається»: the wall-floor line, a floor joint or the trace of the brush;
  on which frames; was the smoke tick on (a frame as shot and a screenshot were asked for)? Under thin
  smoke the corner tool now takes the line and makes the smoke around it smoother - is that what he
  wants, or should the smoke win there?
- From 4.10.0, answered: the brush is fast and draws a line; the time line read «30 с · AI-заливка: 121
  пл. за 15 с (відеокарта)». Not answered: does he paint whole areas of floor with the brush (the reading
  of his ellipse, section 1); was «Автовивантаження моделей із VRAM.» in his message a question (the
  reply explained the setting anyway); why a computation took 60-400 s before 4.10.0 (never found out).
- From 4.9.0, not answered: is the rim along the hem and the shoe gone on his PC? Is the line right of the dress
  gone? Does the hair slider take the hairs he meant - and does it take anything it should not (a thin
  earring, a chain, a ribbon)? He was asked for a screenshot with the hairs circled.
- From 4.8.0: the zoom keys do not matter to him (2026-11-22); the brush did get slower and the exact
  picture took 60-400 s (hence 4.10.0). Not answered: does the right mouse button drag the photo? Does
  the photo look grainy in a small window with «Детальний перегляд» on?
- From 4.7.0, not answered: is the soft edge as soft as he wants (the fade is one brush radius;
  `BRUSH_SOFT_BAND`)? Is the one mode fast enough on his PC? (The old program is removed: that went through.)
- Answered after 4.5.0: Ctrl+Z works in Photoshop; the corner on a black backdrop must go completely;
  dark grey counts as dark (the limit is 40 now).
- Should a light spot at the frame border (a lamp that shines into the frame) be removed by the program?
  Now it is evened and stays.
- Does he want the wall smoothed as strongly as in his retouch of frame 2? Then «Розмиття фону» should get a
  default above 0 in «Дальній план». (Open since 4.4.0.)
- His retouch removes the studio gear at the frame edges; the presets leave it (`removeStands` off, as before).
  (Open since 4.5.0, asked once, not answered.)
- A series shot with smoke and the automatic preset: every frame opens with smoke protection off and a note
  that smoke was seen. The manual tells him to untick «Авто…» and pick «Зйомка з димом» for such a series.
  If that is a nuisance, the smoke switch could be kept as the user left it when the automatic preset is put
  on the controls.

### Offered to the owner, not built (he has not asked for them)

- a bolder hair tool (named in the reply about 4.9.0 as the next step once he has circled the hairs he
  means): today a wisp, the loops of hair around the forehead, hairs that lie along the hairdo and the
  faintest hairs stay by rule. Taking them means repainting more of the wall next to the head, so it
  needs his frames with the hairs marked and the real LaMa to judge the fill;
- rewriting the history so that the 666 MB of the removed original program really leave GitHub (needs a force
  push of `main`; ask him first, and do it only at the very start of a session);
- if the brush is still slow after 4.10.0 (named in the reply): (a) send the mask picture only while the
  mask view is on - it is half of every answer and 57 of 250 ms on the server; the panel must then ask
  for it when «Маска» is pressed; (b) fill only what a stroke changed instead of the whole painted zone
  (the server's time grows with the painted area - section 3, «What was measured for 4.10.0»); the
  window and the layer must stay the same picture, which the group `brush` checks; (c) draw the stroke
  in the panel at once and let the server's picture replace it (not named to him);
- a switch "update nothing until I press a button" for the big window (the fast window of 4.10.0 still
  makes the light refresh by itself);
- a softness slider for the brush instead of the two buttons; a helper `.bat` that removes the old program
  (neither was offered to him in words; both came up while 4.7.0 was built);
- the visible part of the frame at full resolution when the view is zoomed in (named in the release notes
  of 4.8.0 as the next step if the sharper window is not enough);
- a turnkey preset, a wall/floor switch, batch processing.

### Ideas worth doing when the installer is touched next

- Write the install log as `install_log.txt` instead of `install.log`: Arena accepts `.txt` uploads and
  rejects `.log`, so today he has to paste the text.

### Known limits of the automatic preset

- The framing is read from the silhouette only. Checked on 44 real photos: 40 as judged by eye; the misses were
  neighbouring classes in unusual frames (a tight group, a jump). A raised hand above the head, a hat or very
  big hair can shift the answer by one class.
- "Dark" means: median brightness of the backdrop below 40 of 255 (`SCENE_DARK_LUMA`; 26 until 4.5.0). His
  black samples measure 13 and 20, his dark grey 31, his grey 52, his light grey 78. The grey one is close
  enough to the limit that a darker exposure of the same backdrop could cross it; if he complains that a
  grey frame got a dark preset, this one number moves.
- Presets differ mostly in search sensitivity, so the cleaned photo changes little between them; the difference
  shows in the mask. That is why the note after a preset click gives the share of the frame where defects were
  found (the bright green).

### Known limits of the image processing

- The brush (4.7.0) makes a zone like what surrounds it. A stroke that covers only the middle of a large
  spot is surrounded by the spot and changes next to nothing; he is told to paint a spot whole, with a
  margin. Whatever lies under a stroke becomes plain backdrop - it cannot draw a texture or a pattern.
- The brush at a shadow (4.7.0): where the surroundings of a stroke are two even surfaces - it crosses the
  edge of a shadow or runs along it - the tone stays and only grain and fine dirt (finer than
  `BRUSH_TONE_SIGMA`) are renewed. So a stain right at the edge of a shadow is not evened by a stroke
  that also covers the shadow; a smaller brush that stays off the shadow does it. Between the two numbers
  of `BRUSH_SECOND` the rule holds in part.
- The soft brush and the person (4.7.0): it follows the silhouette of the session
  (`_session_person_small`). What the model takes for the person is not painted (the hard brush does it);
  what the model misses is painted like backdrop. Right next to the person the stroke fades over 8 window
  pixels, so dirt that touches a shoe stays in that rim.
- The brush where almost nothing but people is left around the zone (`BRUSH_RING_MIN`): the tone and the
  gear stay, only the grain is renewed. Painting 69 % of the window took Apply 4.5-6.5 s here.
- The pictures of the window show a painted zone with 88-93 % of the grain around it (a reduced JPEG);
  the layer has all of it (1.05 against 1.05 on the drawn frame of the check).
- The cursor ring of the soft brush is the middle of the fade: the stroke reaches half a radius beyond it.
- Gear (4.6.0): a cast shadow or a broad light panel that leaves the frame over the left, right or top
  border is still gear, as before - nothing is cleaned along its edge. A dark thing with backdrop on both
  sides is gear whatever it is; the narrow shadow of a finger (a quarter of the light missing) counts.
- Corner on a dark backdrop (4.6.0): when the corner cannot be seen at all, a sharp edge across the floor
  (the rim of a pool of light, a shadow) is still the only line and is taken for the corner; the corner tool
  then bends the light there. `cycCurve` 0 is the cure. A straight edge of light from border to border
  between 25 % and 82 % of the height is a corner to the finder by definition.
- Floor joint (4.6.0): pieces that lie closer than about 18 % of the frame width at one height merge into
  one piece before they are judged, so a joint that runs along an edge of light for part of its length is
  judged by the average step along it: all of it stays or all of it goes. A joint along the rim of a pool
  of light is not taken as a line (right side of his frame 3); the dust search then repairs bits of it.
- A spot inside a shadow (4.6.0): the small shadow of a small thing that lies wholly inside a bigger shadow
  is repaired like dirt; so is the darker crossing of two faint thin shadows when each of them alone is
  just below the threshold. The owner's scuff passes with little to spare (1.36 against the limit 1.25;
  its surroundings vary by 7 levels against the limit 8.6): a fainter one stays, and that is the safe side.
- Smoke: the soft rim of a broad shadow reads as wisps. On a drawn frame with such a shadow and the
  protection ON, smoke was "found" and the whole shadow was protected (nothing cleaned in it). With the
  built-in presets the protection is off, so only the note "smoke was seen" can be wrong.
- Smoke by the user's word (4.11.0) HAS NEVER SEEN REAL SMOKE. Its thresholds are absolute numbers tuned
  on smoke drawn over seven frames (section 2, «4.11.0»); a rougher backdrop or more grain will give more
  false smoke at the same slider value. Known on his frames: on `0Q5A3417` the rim of the lamp's light is
  taken for smoke (5.7 % of the frame at 60 %, 7.8 at 80, 16 at 98); curls weaker than about 0.7 levels
  are kept only in part below 95 %; at 100 % 13-32 % of a frame WITHOUT smoke is protected, so dust
  stays there.
- Thick smoke against gear (4.12.0) was made on ONE real frame. Known to go wrong: soft (out-of-focus)
  gear that has no single direction counts as smoke while the smoke tick is on and is then not removed
  by «Прибирати стійки…» (five such groups on his frames, section 2). Not known: a much brighter cloud
  on a black wall (the gaps between its curls are "dark thin things", which `_edge_blobs_with_body`
  calls gear - the new rule decides before that, but only for groups that pass its two tests), gear
  standing inside smoke, smoke in front of the person's outline.
- The mixer brush (4.12.0) smooths what is smaller than about 1.6 % of the long side (90 px of his
  frames): larger blotches stay, at any strength - on the test frame blotches of 9 px sigma are still at
  37 % at 100. It goes over the wall-floor line like over anything else (half of its sharpness at 50 %).
  It is weaker wherever the shadow map answers, also in broad soft shadows of the wall (p90 of that map
  on his walls: 0.36-0.59). It does not add noise: in 8 bit, at 100 %, a third of the grain is all that
  hides the steps of a slow gradient.
- The «Маска» view of a LIGHT refresh is not the exact one when «Сліди взуття» stands very low (found
  when the random walk of `quick` changed its steps, as old as the light refresh): at 6 % the layer
  covers 11 % of the frame in the light picture and 67 % in the exact one; at 20 % and at 65 % the mask
  pictures still differ by 3.5-5.8 levels on that walk's settings (the check allows 3). The alpha of the
  stains stage is a threshold on the size of the correction (`alpha_s` in `_smooth_backdrop_stains`),
  and the reduced copy of the light refresh sees smaller corrections. The cleaned photo itself is right
  (0.05 levels apart). Not fixed; the walk was put back on its old steps.
- With the tick OFF nothing new is looked for (4.11.0): the note «Схоже, у кадрі є дим…» at the opening
  of the window still comes from the search by wisps alone (`found`), so THIN smoke is cleaned without a
  word when the tick is off - as in every version before. The soft search was not used for that note on
  purpose: it marks 0-2 % of most of his frames without smoke and 8 % of `0Q5A3417` at 80 %, and a note
  that cries smoke on frames without any would be ignored soon. A series with smoke needs the preset
  «Зйомка з димом» with «Авто…» unticked (the manual says so; the reply repeated it).
- Smoke and the wall-floor corner (4.11.0). Under THIN smoke the corner tool works: the line goes and
  the smoke in the zone of the cove keeps 40-80 % of its curls (the cove estimates its correction from
  the picture with the smoke in it). Under THICK smoke nothing is touched and the line stays; where the
  gate of the cove ends at the rim of thick smoke the tone moves by the size of the correction over the
  soft edge of the map (on dense smoke drawn over frame 1 the column profile across the line was steeper
  after the tool than before: 1.1-1.3 against 0.56 levels/px). Not looked into. A cove that takes only
  what is constant ALONG the line would keep the smoke and remove the line; not built.
- Smoke that lies on the floor only (nothing of it above 70 % of the frame height) is protected only at
  100 %, unless it holds a cloud of wisps big enough to prove smoke alone (`SMOKE_MIN_CLOUD`): below
  100 % it cannot be told from footprints. This is also a CHANGE for the preset «Зйомка з димом»
  (slider 95 %): 4.10.0 kept every wisp at 95 %, small patches on the floor too (smoke or dirt alike);
  4.11.0 keeps a patch on the floor only when it hangs together with smoke above the line. Low fog of
  medium density that hugs the floor is the case that can lose by it; the manual and the tooltip send
  him to 100 % for smoke on the floor. If he reports it, moving the preset to 100 % is NOT the cure
  (13-32 % of a frame without smoke would keep its dust): the floor rule would need a better cue.
- 8-bit frames: the tone stages round without dithering. On a backdrop without noise (his black JPEG: 96 %
  of neighbouring pixels are equal) the one-level contour lines of a gradient change their course where
  the corner tool or the stain stage worked. It shows only when the darks are stretched about thirty times;
  measured against his result of 4.5.0 the new run is no blotchier (0.42 against 0.58 levels between the
  scales of 6 and 60 px). Dithering the corrections would remove it; not asked for.
- A light spot at the frame border (a lamp shining into the frame, 300 px across) is evened, not removed:
  the stain stage takes it for light.

- Dust on a dark backdrop: at «Пил і цятки» 92 some plain noise of the lit part is still marked (his black
  frame: 0.85 % of the frame, about 145 small zones on the lit wall); at 80 it is 0.18 %. That is why the dark
  presets ship with 80 and lower. Only the fine pass follows the local noise; the coarse pass (`spot_cand`,
  on a copy of at most 2048 px) measures its noise on the lit part of the backdrop and was left as it is.
- The corner finder scores a real corner on a black backdrop low (his black frame: 0.65; the limit is 0.12; a
  brightness step of 1 L*). Before the slope of the light was taken out, faint joints scored 0.13-0.26; now
  0.002. There is room to raise the limit if false corners turn up.
- With the corner tool at 0 a corner that the seam search marks along its whole visible length is still
  repaired as a line (as in every version before); only a partly marked one is left alone.
- The eraser means "touch nothing here", the evening of the backdrop included: an erased place keeps the tone
  of the shot and shows against the evened backdrop. That is by design (the layer is
  `max(found, painted) x (1 - erased)`); Ctrl+Z is the cure for an accidental click.
- A `user_settings.json` without `cfg` (the program never writes one; a file cut by hand): no preset is put
  on the controls at the start, they show what `index.html` is drawn with while the active preset is
  highlighted. Harmless today. If settings are ever written without `cfg`, apply the active preset in
  `bootstrap` of `main.js` (a restore from a backup already does).
- The cyclorama corner is searched between 25 % and 82 % of the frame height and must be nearly horizontal.
  A hair-thin dark line in the corner or within 2 % of the frame height of it (`CORNER_HAIR_ZONE`) goes
  with the corner since 4.9.0: what its profile has beyond the straight line between its two shoulders is
  subtracted, at most 0.045 of the range (`CORNER_HAIR_CAP`, about 11 levels) - a deeper or wider crease
  stays in part, and a line that the search does not find stays whole. The seam search leaves that zone
  alone when the corner tool is on, so a second, real seam that close to the corner is not repaired as a
  seam. With «Циклорама» at 0 none of this runs.
- The tone stages and the person (4.9.0): the corner and the stains now shift the tone up to the matte
  itself, not up to the margin of «Захист моделі та країв». A thin part of the person that the matte
  misses and that only the margin used to cover (a strap, a heel, the tip of a shoe) gets the smooth
  shift of the floor next to it - a few levels, no repainting. Where the matte is soft, the shift is
  partial. Where the network is sure of the person (`TONE_GATE_SURE`) nothing shifts at all.
- Single hairs (4.9.0), found on drawn frames and on his six frames, not cured:
  - a narrow strong rim of light around the head is gear to the gear map: hardly a hair is marked there;
  - a strong wisp next to a cable is one "body" with the cable and is not searched;
  - a thick hair that is exactly vertical in a close-up gives several centre pixels per row and is
    dropped as a tuft;
  - the first pixels of a hair, inside the protected band, stay: a stub at the hairdo, wider with a
    higher «Захист моделі та країв»;
  - the finest hairs (below `HAIR_FLOOR` / `HAIR_SIGMA` of the backdrop's own response) stay at 100;
  - a hair longer than the zone (0.6 head widths from the person) is taken for a cable and stays whole;
  - a thin thing that begins at the head and ends in the open - a thin earring, a chain, the end of a
    ribbon, a feather - passes for a hair. The eraser of the big window brings it back; a lower slider
    asks for longer hairs and may leave it;
  - a light hair is not asked what it grows out of (a dark one must grow out of something dark), so a
    thin light line that touches the head on a dark wall is taken.
- The brush and large areas (measured for 4.10.0): every stroke fills the whole connected painted zone
  anew, so a stroke takes the longer the more is painted - here 0.3 s with 3 % of the window painted and
  0.6 s with 15 %, on two slow processors. Many strokes side by side over a floor are one zone. The size
  of the window pictures does not change this.
- A GPU error (4.10.0): the tile that failed and the rest of that run are computed by the processor,
  which is many times slower than the GPU - one slow run, with a warning, instead of every run slow
  without a word. Nothing tries the GPU a second time within the same run.
- The stain stage reaches about 2 % of the frame. At the default 65 a round stain of 1 % of the frame height
  loses 85 %, one of 2.4 % loses 70 %, one of 4 % half, one of 6 % a fifth; from 10 % up it is taken for light
  and stays. A small soft shadow is evened like a stain of its size (a drawn one of 8 % of the height kept
  80 % of its depth); contact shadows and large shadows stay. On a dark backdrop the tolerance is a third of
  the one on a light backdrop, so less is evened there (a drawn test: 65 % left against 40 %). A stain inside
  a small dark corner (a soft shadow of under half a percent of the frame) has less of its own tone around it:
  42 % of it was left where 7 % was left on the open floor.
- The seam search takes the straight lower edge of a silhouette for a line when it is level and long (seen
  only on a drawn frame with a rectangular "dress"); it was so in v3.2.1 too.
- The clothing tool is delicate: deep folds stay, near-black clothes are not touched.
- Format 5:7: equipment cut by the frame edge stays cut; the added strips near the feet can look streaky.

## 4. Working in the sandbox

The sandbox is Linux with no Windows, no GPU, no models and no Photoshop. It is recreated often - also in
the middle of a turn - and `/tmp` is then empty. The system `python3` has no NumPy.

A recreated sandbox can come back at an OLDER state of the branch, with the folder `CleanVinylPro/` (666 MB,
the original program of the base commit) in the root. Only what was pushed is safe. To get back:

```bash
git fetch origin && git reset --mixed origin/<the session branch> && git status --short
rm -rf CleanVinylPro        # the stray copy of the original program; never commit it
```

Then build the environment below again. Push work in progress after every finished step for that reason.

```bash
# once per sandbox
python3 -m venv /tmp/cvenv
/tmp/cvenv/bin/pip install numpy opencv-python-headless fastapi uvicorn httpx Pillow
npm install --prefix tests jsdom@24      # for the panel test; the folder is git-ignored

# the checks: the quick run takes 30 to 45 minutes here and ends with "ALL CHECKS PASSED"
/tmp/cvenv/bin/python tests/run_checks.py
/tmp/cvenv/bin/python tests/run_checks.py install bat    # only the groups named
/tmp/cvenv/bin/python tests/run_checks.py --full         # more random cases

# the deliberate defects of the latest version: about 30 minutes for 4.11.0 (29 for the 23 of the engine - each
# runs the group smoke, 75 s - and 1 for the 7 of the panel); it patches engine.py in place - run those in a
# copy of the tree (below)
/tmp/cvenv/bin/python tests/try_defects.py               # ends with "N of N defects caught"
/tmp/cvenv/bin/python tests/try_defects.py "called a line" "the slider"   # only the defects whose name or group has these words
/tmp/cvenv/bin/python tests/try_defects.py panel:        # only the defects of the panel (they go into a copy
                                                         # of the plugin folder by themselves)
/tmp/cvenv/bin/python tests/try_defects.py --list

# after ANY change inside CleanVinylPro2: the .ccx first, because it is inside the ZIP
python3 tools/build_ccx.py && python3 tools/build_zip.py
python3 tools/build_ccx.py --check && python3 tools/build_zip.py --check
```

- Run the full check and the deliberate defects in the background (`start_process`, output to a file in
  `/tmp`) and wait for the exit; a single blocking command times out. While either runs, do not edit
  anything under `CleanVinylPro2/` or `tests/`, do not build and do not `git add -A`: the checks read the
  files when each group starts, and the defects runner holds a deliberate defect in the working tree.
- **The engine and server defects are better run in a copy of the tree**: the working tree then never
  holds a defect, and the docs can be written meanwhile.

  ```bash
  mkdir -p /tmp/tree && tar cf - --exclude=node_modules --exclude=__pycache__ CleanVinylPro2 tests tools \
    | (cd /tmp/tree && tar xf -)
  cd /tmp/tree && PYTHONUNBUFFERED=1 /tmp/cvenv/bin/python tests/try_defects.py edge: line: hair:
  ```

  The copy must be made from the final state; throw it away afterwards.
- **One heavy job at a time.** The sandbox has 3.9 GB of memory and two CPUs. A session on a 22 MP frame of
  his takes about 2 GB. A check run that is killed for memory ends without a word and without a FAIL
  line: `try_defects.py` reports that as CRASHED (not caught), and a full run simply stops. Do not start a
  measurement, a second check run or the panel test next to a running check. (Paid for twice. In 4.9.0
  a full run next to a run of the hair defects was killed in its group `exact`, which takes 2.4 GB by
  itself; `dmesg | tail` names the killed process. The single groups `hair`, `edge` and `line` are
  small enough to run next to a defect run; the full run is not.)
- The comparisons with v3.2.1 (`process`, `session`, `http`) load the old engine and server from
  `tests/baseline_v321/`. If that folder is missing they are skipped and the group `server` fails.
- No real AI models here, so what the person-matting model returns is faked (`FakeMatting`). To try something
  on real photos with real silhouettes, MediaPipe's person segmentation is a usable stand-in:
  `python3 -m venv /tmp/mpenv && /tmp/mpenv/bin/pip install mediapipe==0.10.14 opencv-python-headless==4.10.0.84`
  (uninstall `opencv-contrib-python` first: it needs libGL). Public test photos of people:
  `https://codeload.github.com/xuebinqin/U-2-Net/tar.gz/refs/heads/master`, folder `test_data`. The framing rule
  of the automatic preset was tuned this way.
- `tools/*.py`, `server/setup_env.py` and `tests/install_checks.py` need only the standard library.
- The group `install` runs the real `setup_env.py` in imitated PCs with stand-in packages. The group `bat`
  only reads the `.bat` files the way `cmd.exe` does; it cannot run them.
- **Line endings:** the eight `.bat`, `folders.ini` and the `.txt` manual must stay CRLF, or `cmd.exe` can lose
  labels. `.gitattributes` stores them untouched (`-text`), `build_zip.py` restores CRLF, and `--check` proves it.
- **Version number:** it lives in `server/server.py` (`APP_VERSION`), `uxp-plugin/manifest.json`,
  `uxp-plugin/main.js` (`PLUGIN_VERSION`), the `echo` lines of `install_windows.bat`, `start_gpu_server.bat`
  and `restart_gpu_server.bat`, and the manual. The group `server` fails if they disagree.
  `start_gpu_server.bat` also compares the version of a running server in two Python one-liners
  (`d.get('version')=='X'`). In the three `.bat` the old number stands in 1, 1 and 6 places and nowhere
  else: replace it as bytes, so that CRLF stays. `README.md` (link and number) and the manual (title, the
  update heading, a new «ЩО ЗМІНИЛОСЯ» block, section 5) are done by hand.
- **The manual** is CRLF with lines of at most 80 characters; patch it with exact replacements that keep
  both, and check the longest line afterwards.
- **The owner's photos** arrive in `/tmp/arena-coding-uploads/`. They show his clients: never commit them and
  never publish previews made from them. `_local/` is git-ignored for such experiments.
- `H.make_studio_image` returns the silhouette as float 0..1 at 1024 x 1024, not as uint8: `> 127` selects
  nothing. A check that measures something inside a zone must fail when the zone is empty: write
  `if not value >= limit` (a NaN then fails) and test the size of the zone.
- Two JPEGs of the window hold the same blocks wherever their pictures are the same, so "this part of the
  cleaned picture IS the picture of the original" can be checked pixel for pixel on the decoded pictures,
  a few blocks away from anything that differs (`check_sharp`).

### Working on his photos

- The engine runs on them with stand-ins: the silhouette from MediaPipe (see above; `_clean_fg_mask` wants the
  raw matte as uint8 0..255 - a float matte gives nonsense masks) and `cv2.inpaint` in place of LaMa (a class
  with `get_inputs` / `get_providers` / `run`, as `FakeLama` in `tests/harness.py`). **What the stand-in repair
  draws is not evidence**: Telea leaves scalloped blotches on big masks and smears long strips. Judge the
  search (what is marked), the tone stages and the masks; never the quality of the fill or the hair edges.
- Look at zoom, with a strong local-contrast boost (CLAHE) next to the plain crop: the defects he complains about
  are a few levels deep and invisible in a reduced overview.
- His retouched frame can be laid over the original when it was not re-cropped (ORB + affine fit gave scale
  1.0004 for two of the three; the third was re-framed and could not be aligned). Then compare band energies of
  the backdrop (wall and floor apart) between original, program and his retouch.
- Useful numbers for a tone stage: what is left of a known stain pattern; depth of shadows before and after;
  growth of the gradient of the low-passed frame (new edges); change of a row profile across a slope of light.
- Do not open a picture in the same step that writes it: the viewer shows the previous file.
- Brush strokes on his frames are made by script, the way `check_brush` in `tests/run_checks.py` does it:
  `r = eng.start_session(image, 8, params)`, then
  `eng.edit_session_mask(r["session_id"], "stroke", [{"x": 0.5, "y": 0.5, "norm": 1}, ...], radius, erase,
  False, 45.0, softness)` (radius in window pixels, softness 1 / 0) and
  `eng.apply_session(r["session_id"], 100.0, False, False, 45.0)[0]` for the layer (RGBA). `"reset_auto"`
  as the operation takes all strokes back. Compare the layer with the layer without the stroke, look at
  the pair at five-fold contrast, and compare the window picture (`comp_jpg_b64` of the answer) with the
  reduced layer.

### Traps already paid for

- The quick preview must be built by `_session_proxies_quick`. A preview made from a twice-reduced frame
  changed the person; do not go back to it.
- A rule about what a run does (for example "a corner that the selection holds only partly is left alone")
  must also be applied on the "everything is remembered" shortcut at the top of `process` (the early return
  for `analysis_only`). In 4.4.0 it was missing there at first, and the light preview bent a corner that Apply
  left alone.
- "Pixels outside the mask equal the original" is a wrong check. Compare the person core against the exact preview.
- In the pointer environment a `sitecustomize.py` is silently ignored. The pointer is a `.pth` file plus a
  module; keep it that way.
- `python -m venv` does not replace a dangling `python` link: `relink_venv` removes dead links first.
- The completeness marker `cleanvinyl_env.json` is written only when missing, so a second install changes nothing.
- A failed download must not fall back to the program-folder layout (`DownloadError` is re-raised).
- jsdom: run the panel with `vm.Script(...).runInContext(dom.getInternalVMContext())` and close the window only
  after its requests and timers have finished.
- The panel test can move the plugin's clock (`cvClockSkewMs`) - that is how the 150 s wait for a server that
  never starts is lived through in a second.
- `check_http` compares whole JSON answers of the old and the new server: a new key in an answer must be added
  to the ignore list in its `norm()`.
- The built-in presets are stored on the owner's PC (`presets_local.json`, `user_presets.json`) the way they
  were when first seen: changing a value in `DEFAULT_PRESETS` / `presets_defaults.json` does NOT reach an
  existing installation by itself. Either derive the behaviour in code (as `presetFracAuto` does) or add an
  entry to `PRESET_DEFAULT_MOVES` in `main.js` (a one-time move of one value; `tests/plugin_settings.test.js`
  and the "PC with the presets of 4.3.0" scenarios show how it is checked). `DEFAULT_PRESETS` and
  `presets_defaults.json` must say the same; the settings test compares them.
- The engine's "shadow" map (`shadow_s`) is not a shadow detector: it is a wide halo around every person
  (22-42 % of his frames). Anything damped by it does nothing where the floor is dirtiest. The same goes for a
  ramp that grows with the distance from the person.
- An edge-keeping average (bilateral) flattens the two shoulders of a soft slope and so sharpens it into a
  line; cut off sharply, its range limit draws ragged patches; with a plain average as its notion of "light"
  it lightens a strip along the frame borders of a vignetted backdrop. All three were seen on his frames or on
  drawn ones; the answers are in `_smooth_backdrop_stains`, `_even_by_tone` and `_light_plane` - read their
  comments before you touch the stage.
- The floor joint drawn by `make_studio_image` is too thick for the seam search and was never found by any
  version. `tests/run_checks.py` draws its own (`_joint_frame`).
- The light (quick) preview exists only for frames whose long side is at least `PREVIEW_PROXY_MIN_DIM` (2520
  px): a check of the light way needs a frame that large, smaller ones silently take the full way.
- The legacy regime of the checks (`_legacy`, `_legacy_window`) is where v3.2.1 must still be matched pixel for
  pixel. A new stage must be off in it by default or be switched off there explicitly.
- A preset click often changes almost nothing in the cleaned preview. Measure before you conclude that a click
  "does not work": the engine recomputes, the picture just stays within a few levels.
- Badge texts in the panel avoid the glyphs ⚙ and ⟳; keep avoiding them.
- Pyflakes reports "undefined name 'weighted'" in `engine.py` and an unused `k` in `tests/run_checks.py`. Both
  are harmless; leave them.
- `pkill -f "server/server.py"` also kills the shell that runs it. Use `pkill -f "serve[r]/serve[r].py"`.
- `gh repo view --json visibility` is invalid; use `isPrivate`.
- `gh pr edit` fails here with a GraphQL error about "Projects (classic)". Change the title or the text of a
  pull request through the API instead:
  `gh api -X PATCH repos/malysh-sl2/CleanVinylPro-Beta/pulls/<number> -f title="..." -F body=@file.md`.
- Running the real `server.py` from the working copy (for an end-to-end try) leaves `server/presets.json` in
  the program folder. Delete it before you build or commit.
- The pictures the big window gets are JPEGs of a reduced copy. Banding, blocks and lost grain seen in a
  screenshot must be measured on the session arrays (`orig_small_bgr`, `clean_paint_small_bgr`) before the
  cleaning is blamed: at quality 90 the JPEG alone flattens a dark backdrop.
- To reproduce "noise taken for dust" on a drawn frame, the frame must be big (about 12 megapixels) and its
  noise mostly the same in the three channels: the two passes of the dust search work at different scales,
  and independent noise per channel sets off the colour test instead. `_low_key_frame` in
  `tests/run_checks.py` is such a frame.
- A new default of the engine (`grainLocal`, the preview quality) must be switched off in `_legacy` of the
  checks, or the comparisons with v3.2.1 fail for a reason that is not a regression.
- A deliberate defect that every check lets through is a hole in the checks, not a proof that the code is
  right: put the defects in one at a time with `tests/try_defects.py` (it applies an exact text
  replacement, runs the group the defect belongs to, restores the file and logs caught / not caught) and
  close the holes it shows. Replace its list when you add rules. Do not edit the program files or build
  while it runs: it patches them in place.
- `_local/`, `/tmp` and every commit that was not pushed do not survive a new sandbox; the working tree
  comes back at an older pushed state (top of this section). Whatever the next session needs - a runner,
  release notes, a probe - belongs in the repository or in this file, pushed.
- The brush (4.7.0), ways that were tried and dropped - do not go back to them:
  - looking for "most of the surroundings" with the wide tolerance (`BRUSH_MOST_TOL`): a plane tilted across
    the two sides of a shadow edge passes for one uneven surface, and a stroke along the edge smears it
    (+9.9 / -10.2 levels on a drawn frame). The slope is found with the narrow `BRUSH_FIT_TOL` (`_even_part`);
  - rules that switch at one number: a stroke across the shadow of a hand on his grey frame had shares of
    0.73 and 0.236 against limits of 0.55 and 0.25 and ate into the shadow (largest change 32). And the
    window and the layer, which work on copies of different size, landed on different sides of a limit.
    Hence the pairs and `_ramp`;
  - taking the tone of a zone from the strip that is left around the people when the whole backdrop is
    painted: mean change 37 levels on his frame 1, and a stand in the zone became a dark smear (213);
  - a zone that ends sharply at the person stands there in a tone of its own (a halo); one that takes its
    tone from the strip next to the person spreads the contact shadow of a foot over the whole zone;
  - raising the floor of the tone sigma to keep more grain in the window pictures gives next to nothing.
- Measuring grain inside a painted zone at the size of the window: specks of 3 px fall into the edge band
  at the reduced scale and look like "grain 0.78 in the core, 3.42 in the band". That was the probe.
- A debug copy of the engine with prints: `sys.path.insert(0, <its folder>)` works only AFTER
  `import harness`, which puts the server folder first. And never leave such a copy where it can be
  imported as the engine.
- A deliberate defect is "caught" only if the same command passes without it IN THE SAME SETTING. The first
  run of the panel defects reported all 11 caught, in 0 s each: the copy of the plugin folder lacked
  `server/presets_defaults.json`, which the window test reads next to the plugin, and the test crashed
  before any scenario. `tests/try_defects.py` now runs the panel tests on an untouched copy first. Read
  the reason printed after "<-": a stack trace there is a crash, not a catch.
- A panel scenario that needs a user preset: add it with `env.state(...)`. A `disk["presets_local.json"]`
  that holds only that preset leaves the built-in ones out, and the automatic preset then offers 6 sets
  instead of 8.
- A check run tests the engine as it was when the run STARTED (the module is imported once). After the last
  edit, run the groups again.
- The search for defects always works at the "quality" size (`fast_mode=False` in `process` and in
  `preview_action_mask`); `fast_mode=True` is only the optional second pass. Probing a detector with
  `fast_mode=True` says nothing about what he gets.
- Drawing frames for the seam and corner checks: a straight step from border to border between 25 % and
  82 % of the height IS the wall-floor corner to the finder, and pieces at the corner are exempt from the
  "edge of light" rule - draw edges of light lower than 0.82 (`_joint_frame(..., y_left=0.88, step=...)`).
  A corner must be sharp to be found when it is faint: nine tenths of the step within one percent of the
  height (`_two_line_frame`), as on his frame.
- Drawing a stain for the medium pass of the dust search: it must cover less than half of the 31 x 31
  median window at the working size (2048 px), or the median follows it and it splits into two half-moons;
  and it must be too big or too faint for the fine pass (kernel 19 px at full size, threshold x 1.85 inside
  shadows), or the fine pass finds it and the rule under test is never asked (`_shadow_frame`).
- `STD` of the test harness has the smoke protection ON. On a drawn frame with a soft-rimmed shadow smoke
  is then "found" and nothing in the shadow is cleaned. Checks about shadows pass `smokeOn=False`.
  `STD` does not send `smokeFaint`: a check of the new smoke rules passes `smokeAuto=True, smokeFaint=True`
  as the panel does.
- A measure of "structure without a direction" (the smaller eigenvalue of a structure tensor) answers
  wherever two straight things cross - the fall-off of the light and a line - and along every mirrored
  border. 4.11.0 takes the slow light out first and continues the values past the border
  (`_continued_past_border`). Before trusting such a measure on smoke, try it on a straight soft line
  across a vignetted frame, up to both frame edges.
- A threshold of a check that leaned on a false alarm broke when the false alarm was cured (12 % of the
  test frame was "smoke" until the light was taken out; the check wanted "more than 8 % protected").
  Thresholds of a check must come from what was DRAWN into the frame.
- Drawn smoke. The wisps of the old smoke check (noise blurred 10 px, 6 levels) are DENSE smoke: the old
  search protects them in full. Thin smoke for a check is soft billows (noise blurred 22 px, 2 levels of
  RMS, in a soft oval). The probes used fractal smoke: 7 octaves of bicubic-enlarged Gaussian grids
  (largest billow 0.22 of the long side, weight 2^(-0.75 k)), bent by a slow flow, squashed by
  1 / (1 + exp(-1.6 n)), times a soft elliptic envelope and a density (0.9 dense, 0.25 medium, 0.08
  thin), laid over in linear light with the colour (238, 240, 243), people in front. "Curl contrast" =
  local RMS (Gaussian 40) of the band-pass (6 - 45 px) of smoky minus plain. Never use a client frame in
  a check.
- His frame with smoke: `/tmp/arena-coding-uploads/0Q5A2507 копия.jpg` (as shot) and `… копия 2.jpg` (the
  result of 4.11.0). A usable silhouette: GrabCut on a copy 1400 px high, started from a mask - sure
  background outside x 0.20-0.62 / y 0.105-0.975, sure person where the picture is saturated red, likely
  person in an ellipse around the head and a column around the body; six rounds; the largest piece,
  closed by 9 px, resized to 1024 x 1024 for `H.make_engine`. Which version made a result can be read
  from the pair: smooth |as shot - result| by 5 px, times 40, and draw the outline of each version's
  smoke map over it - the unchanged zones follow one of them.
- His retouches (`1 (2).jpg`, `2 (2).jpg`, `3 (2).jpg`) are 5:7 crops of the frames with canvas added at
  the sides. To compare one with its frame: match a central patch of the retouch (both at a quarter of
  the size, the retouch also scaled by 0.9-1.1) in the frame; pair 2 matches at scale 1.00 (0.97), pair 3
  at 1.00 (0.99), pair 1 only at 1.06 (0.86: it was resized, the grain cannot be compared). Texture is
  compared in cells of 256 px that are flat in the frame, band by band (differences of Gaussians).
- Panel tests: `env.key(code, key, mods, target)` already exists; a second helper of the same name in
  the object silently replaced it and every key test "passed nothing". The new one is `env.keyDown`.
  jsdom does not take `keyCode` from the description of an event. A scenario starts with «Детальний
  перегляд» TICKED unless it says `{ detail: false }` (the owner's window has it unticked).
- Adding keys to the list of `_mutate` shifts every random walk; a check that passed for years can then
  fail on a difference that was always there (it did: known limits, the «Маска» view). New keys get
  random numbers of their own, drawn from where the walk stands without moving it on.
- A probe that monkeypatches a rule away (`eng.SMOKE_EDGE_SHARE = 0`) tells at once whether a drawn
  frame can catch that rule's defect at all - cheaper than a round of `try_defects.py`. The soft pole of
  `check_smoke` shows the direction rule only on the LIGHT wall (on the dark one it has no strong edge).
- `image_search` writes what it finds into `image-search/` INSIDE the repository: delete the folder
  before a commit. It found no usable frame of studio smoke on a light backdrop (AI pictures, dark
  backdrops, weddings).
- MediaPipe as the stand-in silhouette misses a leg and a shoe under a dress, the train of a dress and a
  stool. What then looks like a fault of the engine (a cut shoe toe, a smudge on the train, a "joint" on
  the train) is the matte: fix the matte by hand first.
- `cv2.morphologyEx(MORPH_CLOSE)` with a kernel of even width (1 x 110, the quality size of the seam search)
  shifts its result by one pixel in OpenCV 5.1; a piece can then hold a single candidate point, and a line
  fit through it warns (`fit_ok` guards that).
- The plugin has no file dialog (`localFileSystem: "plugin"` in the manifest): anything the owner must find
  on disk is written by the server, and the panel shows the full path.

- A background process runs only while a turn runs. Between two turns the sandbox stands still: a defect
  run started at the end of a turn stood at the same defect eight hours later and went on when the next
  turn began. Start a long run early in the turn and wait for its exit (`get_process_output` with
  `wait_for`) before the turn ends; never tell the owner that something "is running" and will be ready.
- A tool that is switched on must not change what the other tools do. For a new tool compare, on one of
  his frames, the result with the tool on and off AWAY from what the tool marks: the hair tool of 4.9.0
  changed the dust repairs along the whole person (it showed the inpainting another source picture) and
  no drawn check had a speck of dust in its hair frame.
- A check proves nothing where the code does not look. Two checks of 4.9.0 drew their test object in such
  a place - the thin line in the middle of the step (a strip the seam search skips anyway), the fill
  source looked at beyond the protected band - and their defects went through. When a defect is not
  caught, first ask whether the scene of the check can show the rule at all.
- Read the NUMBERS in the reason of a caught defect, not only its words: one defect of 4.9.0 was "caught"
  by a difference of 0.0 levels (a threshold on a quantity that the rule did not move). The rule could
  not be told from its absence and was taken out.

- A key that `process` puts into EVERY `stats` breaks the comparisons with v3.2.1 (`hair_px` of 4.9.0 is
  only there when the tool is on; `timing` of 4.10.0 is left out in three comparisons of
  `run_checks.py`: search for `"timing"`).
- A check that depends on the machine proves nothing on another one: "all processors but one" is one
  thread on the two processors of the sandbox, exactly what the old code gave. Fix the number inside the
  check (`os.cpu_count = lambda: 8` around the call).
- The window has ONE line for notes in the corner of the photo (`updatePreviewBadge`): what is written
  into `sessState.note` is replaced by the next note (the automatic preset writes one right after the
  start) and hidden by the "out of date" texts. Something that must be read gets its own field and its
  own place in the order of that function.
- jsdom lays nothing out: `offsetWidth` is 0 and every rectangle is what the test says. A scenario that
  places things on the photo sets `previewSize` equal to the stage rectangle (400 x 600) and defines
  `offsetWidth` / `offsetHeight` of `dlgStage` itself.
- `tests/plugin_settings.test.js` has two harnesses (`run` and `runMoves`); both take
  `buildSettingsSnapshot` / `applySettingsSnapshot` out of `main.js`, so whatever those two functions
  call must exist in both.
- `grep -c "await scenario("` is not the number of scenarios (some are made in loops); the test prints
  the number. In that test `env.server.disk` is null unless the scenario passes `disk`: read the bodies
  of the POST `/settings` requests instead.
- Nothing compares version numbers as text, so 4.10.0 after 4.9.0 is safe: the panel and the `.bat` files
  only ask whether the server's version EQUALS their own. Keep it that way.
- The date in the instructions of a session can be days behind: the clock of the sandbox (`date -u`),
  the commit dates and the names of his screenshots agree with each other; use those.

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
        --title "Чистий Вініл Pro — версія X.Y.Z" --notes-file notes.md
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
   6. bring pull request #1 up to date through the API (`gh pr edit` fails here, section 4): the version in
      its title and in its first list, and a new «Версія X.Y.Z» paragraph above the older ones. Keep it
      open.
6. Ask before anything that changes what the public sees in a new way. He agreed to the branch, the releases
   and merging into `main`; he has not been asked about anything else.
