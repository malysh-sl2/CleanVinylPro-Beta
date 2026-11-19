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

## 2. What is in the repository

| Path | What it is | Rule |
|---|---|---|
| `CleanVinylPro2/` | the program under development, «Чистий Вініл Pro 2» | all product work goes here |
| `tests/baseline_v321/` | six files of the ORIGINAL program, v3.2.1, byte for byte: `engine.py`, `server.py`, `setup_launcher.py`, `manifest.json`, `install_windows.bat`, `pyvenv.cfg` | **Never modify.** They are the reference the checks compare with. |
| `CleanVinylPro2.zip` | the download for the owner: the folder `CleanVinylPro2`, zipped | never edit by hand; rebuild with `tools/build_zip.py` |
| `tests/` | self-checks that need no GPU, no models and no Photoshop; `tests/README.md` (Ukrainian) describes them | keep them passing |
| `tools/` | `build_ccx.py`, `build_zip.py`, `serve_download.py` | |
| `README.md` | the owner's own instruction (Ukrainian): download, install, how to continue with an agent | keep it true |

The original program (folder `CleanVinylPro/`, 7,812 files, 666 MB with a committed Windows `.venv`) was removed
from the repository in 4.3.0 because the owner asked for it. It is still in the history (first commit
`daae6ed`), and it is still installed on his PC in `D:\CleanVinylPro` - the new program must keep running next
to it (table below). Removing the folder did not make the GitHub repository smaller; only rewriting the history
would, and he has not been asked about that.

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

## 3. Current state — update this at the end of every session

_Last updated: 2026-11-19, by the agent of the first session, after releasing 4.5.0._

- **Released:** 4.5.0, tag `cvp2-v4.5.0`, as a pre-release. Direct download:
  `https://github.com/malysh-sl2/CleanVinylPro-Beta/raw/cvp2-v4.5.0/CleanVinylPro2.zip`
- **Owner's progress:** 4.2.0, 4.3.0 and 4.4.0 are installed and work on his PC (program in
  `D:\Plugin Photoshop\CleanVinylPro2`, libraries copied from the old program without a download, models in
  `D:\model AI fotoshop`, LaMa on `CUDAExecutionProvider`, Python 3.12.10). So the `.bat` files, the
  installer, the GPU, the real models and the panel HAVE run on Windows. He reported on 4.4.0 on 2026-11-19
  with two screenshots (section 1); 4.5.0 answers that report.
  **He has not reported on 4.5.0 yet.**
- **Checks:** the quick run of `tests/run_checks.py` ended with ALL CHECKS PASSED (32 results in
  890 s; 58 scenarios of the panel test and 39 cases of the settings test among them) on
  2026-11-19, with NumPy 2.4.6 and OpenCV 5.1.0, set up as in section 4. Deliberate defects for what is new
  in 4.5.0: 71 put in one by one (25 into the engine, 8 into the server, 38 into the panel and the
  presets); the checks caught all of them in the end. The first run let five through. Four were holes in the new
  checks and are closed: a wrong "unevenly lit" rule and an overdone local noise (`check_dark` got a part
  that tests the rule on drawn noise maps); a file of another program that has the shape of a backup (the
  `http` check puts one into the folder); smoke protection switched on where `smokeEnabled` is declared (that
  value is read only when the settings file carries no `cfg`; the panel test has such a start now). The fifth
  changed nothing at all (`corner_skip` set with no corner line to skip) and was replaced by the defect it
  stood for. On the way the full run also showed that 4.4.0 took a faint floor joint for the wall-floor
  corner whenever the corner tool was on. Of the 41 defects tried for 4.4.0 two still pass every check; they
  are second lines of defence (the layer alpha keeps the person out even when the stain stage does not; the
  gradual end of the tone layers matters only on a frame of extreme contrast).
- **What 4.5.0 gives on his three frames** (stand-in networks, section 4; the share of the frame marked as dust):
  black frame `3.jpg` with «Темний ключ»: 5.11 % with 4.4.0, 0.85 % with the local noise at the former dust
  value 92, 0.18 % at the new value 80; nothing is repaired inside the corner strip any more, and with
  `cycCurve` 65 the line is gone (found at 0.532 of the height). Dark-grey frame `2.jpg` with «Дальній план»:
  13.24 % -> 0.82 %; what is left are real specks and scratches on the lit floor (looked at one by one at
  zoom). Light-grey frame `1.jpg`: the identical mask. The window picture of the black frame: the share of
  pixels equal to their right neighbour in four dark zones is 0.58-0.72 in the data, was 0.84-0.91 after
  JPEG 90 (0.98 in his screenshot) and is 0.50-0.65 after JPEG 100.
- **Against his own retouch** (measured with 4.4.0, not measured again with 4.5.0; band energy kept, fine to
  coarse): the floor is evened to about the level of his retouch - his frame 2: his 0.57 0.61 1.01 1.12, ours
  0.61 0.56 0.90 1.00; his frame 3: his 0.86 0.84 0.93 0.96, ours 0.84 0.85 1.04 0.99. His retouch of frame 2
  smooths the WALL much more than the program does (his 0.29 0.67, ours 0.77 0.92): that would be «Розмиття
  фону», which stays 0 in these presets. The floor joint is repaired on both sides of the person on all three.
- **Decided by the agent alone for 4.5.0** (he was not asked; change them if he says otherwise):
  - the corner goes on dark backdrops too (`cycCurve` 65 in `lowkey`, `lowkey_medium`, `lowkey_wide`). His
    own retouch of the black frame keeps a soft step there; 65 leaves about that. One number per preset;
  - the values of `lowkey_medium` and `lowkey_close` are set by analogy with the light presets (dust 72 / 62,
    more edge protection, no seam search and no large fraction in the close-up). No dark frame of those
    framings was available: they were only tried on crops of his black frame;
  - the smoke switch of the user's own presets is left as saved (only built-in presets are moved);
  - the reset button does nothing for a preset the user made;
  - backups go to `<program folder>\backup` (his program folder is on drive D:, which a reinstall of Windows
    usually leaves alone); the folder cannot be chosen in the panel;
  - his dark-grey frame (backdrop about 31 of 255) still counts as light and gets «Дальній план».
- **Not run in Photoshop yet (4.5.0):** all of it. In particular:
  - whether Ctrl+Z, Ctrl+Shift+Z and Ctrl+Y reach the modal window at all (Photoshop may keep them; the two
    buttons do not depend on that) - **ask him**;
  - `os.startfile` on the backup folder from the server process (the panel shows the path as text anyway);
  - the two new icons `icons/ui/undo.png`, `redo.png` and the backup box in the narrow panel;
  - the look of the window pictures at JPEG 100 on his dark frames, and the real LaMa fill of what the dust
    search still marks there;
  - the one-time moves on his stored presets (smoke off, «Темний ключ» 80 / 65) and the three new presets
    appearing under «Темний ключ» (they ran only in the simulated panel).
- **Merging:** pull request #1 (`arena/33f1ced8-cleanvinylpro-beta` into `main`) is open and deliberately not
  merged yet: fixes that follow his report on 4.5.0 should come from the session that knows the code. Merge it
  when that session ends or when he writes «зливай» (section 6). If `main` already contains this file, that
  has happened. Merging also removes the folder `CleanVinylPro/` from `main`.

### Open questions (not asked yet; ask when he reports on 4.5.0)

- Do the keys Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y work in the big window on his PC?
- Is the corner on a black backdrop meant to go completely, to stay as a soft step, or to stay as shot? Now:
  `cycCurve` 65 in the dark presets that usually show a floor.
- Should his dark-grey backdrop count as dark (`SCENE_DARK_LUMA` 26; his frame is about 31)? It would then get
  the dark presets (dust 80 instead of 85, more edge protection).
- Does he want the wall smoothed as strongly as in his retouch of frame 2? Then «Розмиття фону» should get a
  default above 0 in «Дальній план». (Open since 4.4.0.)
- His retouch removes the studio gear at the frame edges; the presets leave it (`removeStands` off, as before).
- A series shot with smoke and the automatic preset: every frame opens with smoke protection off and a note
  that smoke was seen. The manual tells him to untick «Авто…» and pick «Зйомка з димом» for such a series.
  If that is a nuisance, the smoke switch could be kept as the user left it when the automatic preset is put
  on the controls.

### Offered to the owner, not built (he has not asked for them)

- rewriting the history so that the 666 MB of the removed original program really leave GitHub (needs a force
  push of `main`; ask him first, and do it only at the very start of a session);
- a switch "update nothing until I press a button" for the big window;
- a turnkey preset, a wall/floor switch, batch processing.

### Ideas worth doing when the installer is touched next

- Write the install log as `install_log.txt` instead of `install.log`: Arena accepts `.txt` uploads and
  rejects `.log`, so today he has to paste the text.

### Known limits of the automatic preset

- The framing is read from the silhouette only. Checked on 44 real photos: 40 as judged by eye; the misses were
  neighbouring classes in unusual frames (a tight group, a jump). A raised hand above the head, a hat or very
  big hair can shift the answer by one class.
- "Dark" means: median brightness of the backdrop below 26 of 255 (`SCENE_DARK_LUMA`). His dark-grey sample
  (about 31) is therefore NOT dark and gets «Дальній план»; his black sample (about 20) gets «Темний дальній
  план» (before 4.5.0: «Темний ключ»). If he disagrees, this one number moves.
- Presets differ mostly in search sensitivity, so the cleaned photo changes little between them; the difference
  shows in the mask. That is why the note after a preset click gives the share of the frame where defects were
  found (the bright green).

### Known limits of the image processing

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
  A hair-thin dark crease right in the corner stays as a faint line after the corner tool: the seam search
  leaves the corner strip alone when the tool is on. (Letting the seam repair run there first gave the same
  tone on his frames and removed the crease on a drawn frame, but puts a long inpainted strip next to the
  person; it could not be judged without the real LaMa. One line decides: `corner_skip` in `process`.)
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

The sandbox is Linux with no Windows, no GPU, no models and no Photoshop. It is recreated often and `/tmp` is
then empty. The system `python3` has no NumPy.

```bash
# once per sandbox
python3 -m venv /tmp/cvenv
/tmp/cvenv/bin/pip install numpy opencv-python-headless fastapi uvicorn httpx Pillow
npm install --prefix tests jsdom@24      # for the panel test; the folder is git-ignored

# the checks: the quick run takes about 15 minutes and ends with "ALL CHECKS PASSED"
/tmp/cvenv/bin/python tests/run_checks.py
/tmp/cvenv/bin/python tests/run_checks.py install bat    # only the groups named
/tmp/cvenv/bin/python tests/run_checks.py --full         # more random cases

# after ANY change inside CleanVinylPro2: the .ccx first, because it is inside the ZIP
python3 tools/build_ccx.py && python3 tools/build_zip.py
python3 tools/build_ccx.py --check && python3 tools/build_zip.py --check
```

- Run the 15-minute check in the background and poll it; a single blocking wait times out.
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
- **The owner's photos** arrive in `/tmp/arena-coding-uploads/`. They show his clients: never commit them and
  never publish previews made from them. `_local/` is git-ignored for such experiments.

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
  right: put the defects in one at a time with a small runner (apply an exact text replacement, run the
  group it belongs to, restore the file, log caught / not caught) and close the holes it shows. Do not edit
  the program files or build while such a run is going: it patches them in place.
- The plugin has no file dialog (`localFileSystem: "plugin"` in the manifest): anything the owner must find
  on disk is written by the server, and the panel shows the full path.

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
