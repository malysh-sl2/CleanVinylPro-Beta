#!/usr/bin/env python3
"""
Puts deliberate defects into the program, one at a time, and tells whether the self-checks notice.

    python tests/try_defects.py             # every defect of the list below
    python tests/try_defects.py seam cyc    # only the defects whose check group or name contains one of the words
    python tests/try_defects.py --list      # show the list, change nothing

A check that lets a defect through is a hole in the checks, not a proof that the code is right. For every defect
the script replaces one exact piece of text in a program file, runs the check groups the defect belongs to
(tests/run_checks.py <groups>), puts the file back and reports "caught" or "NOT CAUGHT" - or "CRASHED" when the
checks ended without saying FAIL (killed, or an error of their own): that is not a catch, run the defect again.
Run nothing heavy next to this script: a check that runs out of memory is killed without a word.

A defect of the PANEL (the word "panel" instead of a check group) is put into a copy of the plugin folder, and the
two tests of the panel are pointed at that copy (CV_PLUGIN_DIR): the settings test, and the scenarios of the
window test whose names contain the text (or one of the texts) given with the defect. The program files are not
touched by these.
They need Node.js and the jsdom package (tests/README.md).

Do NOT edit the program files, build the package or run the checks yourself while this is going: the script
changes the files in place. It restores them when it ends, also after Ctrl+C or a plain `kill` (SIGINT and
SIGTERM are both taken as "stop and put the file back", also when the script runs as a background job, where a
shell switches SIGINT off). Only `kill -9` leaves the last defect in the file: `git diff` shows it, `git checkout
-- <file>` removes it (mind your own uncommitted work in that file - the script refuses to start when the list no
longer fits the files).

The list holds the defects for what was new in the last version. Replace it when the next version adds rules:
old entries stop fitting as the code moves on, and the script says so ("out of date") instead of guessing.
A defect that changes nothing the program does (a second line of defence, a dead branch) cannot be caught and
does not belong in the list.
"""
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = "CleanVinylPro2/server/engine.py"
SERVER = "CleanVinylPro2/server/server.py"
PLUGIN = "CleanVinylPro2/uxp-plugin"
MAINJS = PLUGIN + "/main.js"
PANEL_TESTS = ("plugin_settings.test.js", "plugin_preview.test.js")


def panel(*texts):
    """A defect of the panel: checked by the settings test and by the window scenarios whose names contain one of `texts`."""
    return ("panel",) + tuple(texts)


# (name, check groups - or panel(<text>, ...), file, exact text, replacement)
DEFECTS = [
    # ---- what "Прибирати стійки" takes away (4.13.0: the owner's 0Q5A3534, the edges of two cast shadows smeared)
    ("stands: every dark pixel of a gear group is taken away again (the edge of a wide shadow)", "stands", ENGINE,
     "            thin_dark = ((l_shut - L) / (l_shut + 6.0) >= self.GEAR_TAKE_DEPTH).astype(np.uint8)\n",
     "            thin_dark = np.ones(L.shape, np.uint8)\n"),
    ("stands: a thin shadow that is no black thing is taken away (the depth that counts is too low)", "stands", ENGINE,
     "    GEAR_TAKE_DEPTH = 0.62\n",
     "    GEAR_TAKE_DEPTH = 0.50\n"),
    ("stands: a dark-grey pole is not taken away (the depth that counts is too high)", "stands", ENGINE,
     "    GEAR_TAKE_DEPTH = 0.62\n",
     "    GEAR_TAKE_DEPTH = 0.95\n"),
    ("stands: a nearly black shadow along the person is taken away (the groups along the person are not asked for)", "stands", ENGINE,
     "                takeable = valid_edge & ~self._edge_blobs_along_person(fg_s, labels, stats, valid_edge,\n"
     "                                                                       self.GEAR_PERSON_REACH, self.GEAR_ALONG_PERSON)\n",
     "                takeable = valid_edge\n"),
    ("stands: 'along the person' reaches next to nowhere", "stands", ENGINE,
     "    GEAR_PERSON_REACH = 0.03\n",
     "    GEAR_PERSON_REACH = 0.003\n"),
    ("stands: the black curtain is not taken away (what is black and large is forgotten)", "stands", ENGINE,
     "        take_mask = np.maximum(take_mask, bd_zone)\n",
     ""),
    ("stands: with the tick the gear that stays is worked on like backdrop (nothing is protected, as up to 4.12.0)", "stands", ENGINE,
     "        return gear_kept_s if gear_kept_s is not None else np.zeros_like(stand_protect_s)\n",
     "        return np.zeros_like(stand_protect_s)\n"),
    ("stands: with the tick everything stays protected, the stand too (the fill is told to leave it)", "stands", ENGINE,
     "        if not remove_stands:\n            return stand_protect_s\n        return gear_kept_s if gear_kept_s is not None else np.zeros_like(stand_protect_s)\n",
     "        return stand_protect_s\n"),
    # ---- smoke and the tools that move the tone (4.13.0: the owner's 0Q5A2507 with the tick and an ordinary preset)
    ("haze: a line seen through smoke only is a corner again", "haze", ENGINE,
     "    CORNER_IN_SMOKE = 0.60\n",
     "    CORNER_IN_SMOKE = 2.0\n"),
    ("haze: the corner finder is not told what is protected as smoke", "haze", ENGINE,
     "                                    img_rgb_u8, eff_fg_for_spots, eff_stand_protect, smoke_lines_s, hair=hair_line,\n"
     "                                    smoke_all_s=smoke_s)\n",
     "                                    img_rgb_u8, eff_fg_for_spots, eff_stand_protect, smoke_lines_s, hair=hair_line)\n"),
    ("haze: any smoke on its line and the corner is given up (a corner in plain view beside a cloud stays)", "haze", ENGINE,
     "    CORNER_IN_SMOKE = 0.60\n",
     "    CORNER_IN_SMOKE = 0.0\n"),
    ("haze: the corner tool works at full strength right up to the outline of thick smoke", "haze", ENGINE,
     "            gate *= 1.0 - cv2.warpAffine(np.clip(near_s * 2.0, 0.0, 1.0), M_up, (w, rb - ra), **up)\n",
     ""),
    ("haze: the stains stage works right up to the smoke map", "haze", ENGINE,
     "        sm_s = self._smoke_with_halo(sm_s)   # the haze goes on beyond its map (see SMOKE_TONE_HALO)\n",
     ""),
    ("haze: the mixer brush works right up to the smoke map", "haze", ENGINE,
     "        sm_b = self._smoke_with_halo(cv2.resize(smoke_u8, (bw, bh), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0)\n",
     "        sm_b = cv2.resize(smoke_u8, (bw, bh), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0\n"),
    ("haze: the rim around the smoke does not fade (the tone tools do not come back a little further off)", "haze", ENGINE,
     "        halo = np.clip(cv2.GaussianBlur((sm > 0.3).astype(np.float32), (0, 0), sigma) * 2.0, 0.0, 1.0)\n",
     "        halo = np.clip(cv2.GaussianBlur((sm > 0.3).astype(np.float32), (0, 0), sigma) * 40.0, 0.0, 1.0)\n"),
    # ---- the panel: the ring of the brush
    ("panel: the ring of the brush waits for a mouse move after '[' and ']'", panel("the ring of the brush"), MAINJS,
     "  if (el(\"dlgBrushSizeVal\")) el(\"dlgBrushSizeVal\").textContent = String(sessState.brushSize);\n  refreshBrushCursor();\n  scheduleSaveSettings();\n",
     "  if (el(\"dlgBrushSizeVal\")) el(\"dlgBrushSizeVal\").textContent = String(sessState.brushSize);\n  scheduleSaveSettings();\n"),
    ("panel: the ring does not follow the keys of the tools", panel("the ring of the brush"), MAINJS,
     "  refreshBrushCursor();  // (B / E / H: the ring takes the colour of the tool, or goes away, without a mouse move)\n",
     ""),
    ("panel: a key draws the ring where the pointer was last seen over the photo, although it has left it", panel("the ring of the brush"), MAINJS,
     "    sessState.hoverClient = pt && pt.inside ? { x: e.clientX, y: e.clientY } : null;\n",
     "    if (pt && pt.inside) sessState.hoverClient = { x: e.clientX, y: e.clientY };\n"),
    # ---- the panel: the smoke preset is gone
    ("panel: the smoke preset stays in the list of the PC until the server answers", panel("smoke preset leaves the list"), MAINJS,
     "  const retired = dropRetiredPresets();\n",
     "  const retired = false;\n"),
    ("panel: the smoke preset comes back with the copy of the server", panel("reinstalled Photoshop"), MAINJS,
     "    if (dropRetiredPresets()) {\n      changed = true;\n      updateSliderVisuals();\n    }\n    if (applyPresetDefaultMoves()) {\n",
     "    if (applyPresetDefaultMoves()) {\n"),
    ("panel: a backup of an earlier version brings the smoke preset back", panel("restoring a backup made by an older version"), MAINJS,
     "  dropRetiredPresets();\n  applyPresetDefaultMoves();\n  appendNewDefaultPresets();\n  settingsMigrated = false;\n",
     "  applyPresetDefaultMoves();\n  appendNewDefaultPresets();\n  settingsMigrated = false;\n"),
    ("panel: the preset that is gone leaves its values on the controls", panel("PC of 4.12.0"), MAINJS,
     "    if (wasActive) applyConfig(presetsList[0].cfg);\n",
     ""),
    ("panel: the user's own preset of the same name is taken out with it", panel("PC of 4.12.0"), MAINJS,
     "  presetsList = presetsList.filter((p) => !(p && RETIRED_PRESET_IDS.includes(p.id)));\n",
     "  presetsList = presetsList.filter((p) => !(p && (RETIRED_PRESET_IDS.includes(p.id) || p.name === \"Зйомка з димом\")));\n"),
    ("panel: no preset is retired (the list of retired presets is empty)", panel("PC of 4.12.0"), MAINJS,
     "const RETIRED_PRESET_IDS = [\"smoke\"];\n",
     "const RETIRED_PRESET_IDS = [];\n"),
    # ---- the panel: the stands tick on the top bar
    ("panel: the stands tick gives a light refresh only", panel("'Стійки'", "every tick and switch"), MAINJS,
     "      : \"Стійки, дроти й прилади лишаються в кадрі недоторканими.\");\n    recomputeExactNow();\n",
     "      : \"Стійки, дроти й прилади лишаються в кадрі недоторканими.\");\n    requestPreviewRefresh(PREVIEW_DELAY_CLICK_MS, false);\n"),
    ("panel: the stands tick is not read (the server is never told)", panel("'Стійки'"), MAINJS,
     "    removeStands: el(\"dlgChkStands\") ? el(\"dlgChkStands\").checked : false,\n",
     "    removeStands: false,\n"),
    ("panel: a preset does not set the stands tick", panel("'Стійки'"), MAINJS,
     "  if (el(\"dlgChkStands\")) el(\"dlgChkStands\").checked = c.removeStands;\n",
     ""),
    ("panel: the pill of the stands does not light up", panel("'Стійки'"), MAINJS,
     "  if (el(\"dlgWrapStands\")) el(\"dlgWrapStands\").classList.toggle(\"active\", !!(el(\"dlgChkStands\") && el(\"dlgChkStands\").checked));\n",
     ""),
    ("panel: the stands tick has no box (a click on its word does nothing)", panel("'Стійки'", "a check box is ticked"), PLUGIN + "/index.html",
     '<div class="r4m-stands-pill" id="dlgWrapStands" data-check="dlgChkStands" data-tip=',
     '<div class="r4m-stands-pill" id="dlgWrapStands" data-tip='),
    ("panel: the row of the stands is back in the settings", panel("'Стійки'"), PLUGIN + "/index.html",
     '                <div class="g-passes-row" data-tip="Проходи чистки',
     '                <div class="ps-check remove-mode" data-check="gChkRemoveStands"><input type="checkbox" id="gChkRemoveStands" /><span>Прибирати стійки</span></div>\n'
     '                <div class="g-passes-row" data-tip="Проходи чистки'),
    # ---- the panel: every tick and switch asks for the exact frame
    ("panel: the mixer tick gives a light refresh only", panel("every tick and switch", "'Мікс-пензель'"), MAINJS,
     "      : \"Мікс-пензель вимкнено: фон лишається таким, яким його залишила чистка.\");\n    recomputeExactNow();\n",
     "      : \"Мікс-пензель вимкнено: фон лишається таким, яким його залишила чистка.\");\n    requestPreviewRefresh(PREVIEW_DELAY_CLICK_MS, false);\n"),
    ("panel: the mixer switch of the settings gives a light refresh only", panel("every tick and switch"), MAINJS,
     "      sayInWindow(mixEnabled ? `✓ Мікс-пензель увімкнено (${getSliderVal(\"gSlMix\")}%)` : \"Мікс-пензель вимкнено\");\n      recomputeExactNow();\n",
     "      sayInWindow(mixEnabled ? `✓ Мікс-пензель увімкнено (${getSliderVal(\"gSlMix\")}%)` : \"Мікс-пензель вимкнено\");\n      requestPreviewRefresh(PREVIEW_DELAY_CLICK_MS, false);\n"),
    ("panel: the seam switch gives a light refresh only", panel("every tick and switch", "several sliders one after another"), MAINJS,
     "    sayInWindow(seamEnabled ? \"✓ Шов з’єднання вінілу: шукаю й прибираю\" : \"Шов з’єднання вінілу не прибирається\");\n    recomputeExactNow();\n",
     "    sayInWindow(seamEnabled ? \"✓ Шов з’єднання вінілу: шукаю й прибираю\" : \"Шов з’єднання вінілу не прибирається\");\n    requestPreviewRefresh(PREVIEW_DELAY_CLICK_MS, false);\n"),
    ("panel: the shadows tick gives a light refresh only", panel("every tick and switch", "ticks recompute the exact frame"), MAINJS,
     "    sayInWindow(el(\"gChkShadow\").checked ? \"✓ Тіні під моделлю зберігаються\" : \"Тіні під моделлю не захищаються: чистка може їх послабити\");\n    recomputeExactNow();\n",
     "    sayInWindow(el(\"gChkShadow\").checked ? \"✓ Тіні під моделлю зберігаються\" : \"Тіні під моделлю не захищаються: чистка може їх послабити\");\n    requestPreviewRefresh(PREVIEW_DELAY_CLICK_MS, false);\n"),
    ("panel: the clothing tick asks for a recompute of the frame as well", panel("every tick and switch"), MAINJS,
     "    await sendDressPreviewUpdate();\n    if (el(\"dlgHoverHint\")) {\n      el(\"dlgHoverHint\").textContent = dressSmoothEnabled\n        ? \"✓ Рівняння одягу увімкнено\"\n",
     "    await sendDressPreviewUpdate();\n    recomputeExactNow();\n    if (el(\"dlgHoverHint\")) {\n      el(\"dlgHoverHint\").textContent = dressSmoothEnabled\n        ? \"✓ Рівняння одягу увімкнено\"\n"),
    # ---- the panel: what a recompute took and what was taken ready
    ("panel: nothing is said after an exact recompute", panel("what was taken ready", "'Стійки'"), MAINJS,
     "      if (!quick && d.stats) sayInWindow(recomputeSummary(d.stats));\n",
     ""),
    ("panel: the same sentence after a light refresh", panel("what was taken ready"), MAINJS,
     "      if (!quick && d.stats) sayInWindow(recomputeSummary(d.stats));\n",
     "      if (d.stats) sayInWindow(recomputeSummary(d.stats));\n"),
    ("panel: 'the AI fill taken ready' is said whenever anything was taken ready", panel("what was taken ready", "'Стійки'"), MAINJS,
     "  if (ready.includes(\"heal\")) return `✓ Перераховано${took}: людину, пошук дефектів і AI-заливку взято готовими — рахувалося лише те, що змінилося.`;\n",
     "  if (ready.length) return `✓ Перераховано${took}: людину, пошук дефектів і AI-заливку взято готовими — рахувалося лише те, що змінилося.`;\n"),
    ("panel: the time line keeps the time of the run before when the AI fill was taken ready", panel("what was taken ready"), MAINJS,
     "    if (ready && lineReady && typeof stats.elapsed_ms === \"number\") {\n",
     "    if (false) {\n"),
    # ---- the panel: the list of the settings
    ("panel: the list of the settings keeps its 360 px whatever the window", panel("list of the settings takes"), MAINJS,
     "    togglePopover(\"dlgGearPopover\");\n    fitGearList();\n",
     "    togglePopover(\"dlgGearPopover\");\n"),
    ("panel: the list of the settings may grow past the window", panel("list of the settings takes"), MAINJS,
     "  list.style.maxHeight = Math.max(GEAR_LIST_MIN, Math.min(GEAR_LIST_MAX, Math.round(high - GEAR_LIST_AROUND))) + \"px\";\n",
     "  list.style.maxHeight = Math.max(GEAR_LIST_MIN, Math.round(high - GEAR_LIST_AROUND)) + \"px\";\n"),
    ("panel: the rows of the settings shrink again (styles.css)", panel("list of the settings takes"), PLUGIN + "/styles.css",
     ".gear-scroll > * {\n  flex-shrink: 0;\n}\n",
     ".gear-scroll > * {\n}\n"),
    ("panel: a kind of row is not named in the rule against shrinking (styles.css)", panel("list of the settings takes"), PLUGIN + "/styles.css",
     ".gear-scroll .g-row,\n.gear-scroll .ps-check,\n",
     ".gear-scroll .g-row,\n"),
    # (Not in the list, because the checks cannot tell:
    #   - GEAR_KEPT_MAX: a group of which a part is taken away - with the drawn frame every group is taken whole
    #     or not at all;
    #   - the corner finder of the green preview (preview_action_mask) without `smoke_all_s`: the preview is
    #     compared with the cleaning on frames without smoke only;
    #   - the ring after a zoom: the simulated browser lays nothing out, the ring has one size at every zoom there.)
]

def _label(groups) -> str:
    return groups if isinstance(groups, str) else groups[0]


def _plugin_copy(tmp):
    """A copy of the plugin folder inside tmp, with the one file of the server that the window test reads next to it."""
    copy = os.path.join(tmp, "uxp-plugin")
    shutil.copytree(os.path.join(ROOT, PLUGIN), copy)
    os.makedirs(os.path.join(tmp, "server"))
    shutil.copy2(os.path.join(ROOT, "CleanVinylPro2", "server", "presets_defaults.json"), os.path.join(tmp, "server"))
    return copy


def _run_panel_tests(plugin_dir, texts):
    """(exit code, output) of the settings test and of the window scenarios named by `texts`, on the plugin in plugin_dir."""
    env = dict(os.environ, CV_PLUGIN_DIR=plugin_dir)
    code, out = 0, ""
    for test, args in ((PANEL_TESTS[0], []), (PANEL_TESTS[1], list(texts))):
        try:
            r = subprocess.run(["node", os.path.join(ROOT, "tests", test)] + args, env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        except OSError as exc:
            return None, f"Node.js could not be started: {exc}"
        if "SKIPPED" in r.stdout:
            return None, r.stdout.strip()
        code, out = code or r.returncode, out + r.stdout
    return code, out


def _stop(signum, frame):
    raise KeyboardInterrupt


def main() -> int:
    for sig in (signal.SIGINT, signal.SIGTERM):  # stop = put the file back first (the `finally` blocks below)
        signal.signal(sig, _stop)
    words = [a for a in sys.argv[1:] if not a.startswith("-")]
    chosen = [d for d in DEFECTS if not words or any(wd in _label(d[1]) or wd in d[0] for wd in words)]
    if "--list" in sys.argv:
        for name, groups, rel, _, _ in chosen:
            print(f"{_label(groups):8s} {name}   [{rel}]")
        return 0
    for texts in sorted({d[1][1:] for d in chosen if not isinstance(d[1], str)}):
        # a defect of the panel counts as caught only if the same tests pass without it, on such a copy
        tmp = tempfile.mkdtemp(prefix="cv_panel_")
        try:
            code, out = _run_panel_tests(_plugin_copy(tmp), texts)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if code is None:
            print(f"the panel tests cannot run here ({out[:200]}). Nothing was changed.")
            return 2
        if code != 0:
            print(f"the panel tests {texts} fail without any defect - nothing can be told. Nothing was changed.\n{out[-600:]}")
            return 2
    texts = {}
    for name, _, rel, old, _ in chosen:  # nothing is touched unless the whole list fits
        if rel not in texts:
            with open(os.path.join(ROOT, rel), encoding="utf-8", newline="") as f:
                texts[rel] = f.read()
        if texts[rel].count(old) != 1:
            print(f"out of date: '{name}' - its text occurs {texts[rel].count(old)} times in {rel}, expected once. Nothing was changed.")
            return 2
    t0 = time.perf_counter()
    missed = []
    touched = set()
    try:
        for i, (name, groups, rel, old, new) in enumerate(chosen, 1):
            t1 = time.perf_counter()
            if isinstance(groups, str):
                path = os.path.join(ROOT, rel)
                touched.add(rel)
                with open(path, "w", encoding="utf-8", newline="") as f:
                    f.write(texts[rel].replace(old, new))
                try:
                    r = subprocess.run([sys.executable, os.path.join(ROOT, "tests", "run_checks.py")] + groups.split(),
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
                finally:
                    with open(path, "w", encoding="utf-8", newline="") as f:
                        f.write(texts[rel])
                code, out = r.returncode, r.stdout
            else:  # the panel: the defect goes into a copy of the plugin folder
                tmp = tempfile.mkdtemp(prefix="cv_panel_")
                try:
                    copy = _plugin_copy(tmp)
                    with open(os.path.join(copy, os.path.relpath(rel, PLUGIN)), "w", encoding="utf-8", newline="") as f:
                        f.write(texts[rel].replace(old, new))
                    code, out = _run_panel_tests(copy, groups[1:])
                finally:
                    shutil.rmtree(tmp, ignore_errors=True)
            # "Caught" means: a check said FAIL. A run that ended badly WITHOUT such a line did not finish - it
            # crashed, or was killed (out of memory when something heavy runs next to it). That proves nothing.
            lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
            at = next((k for k, ln in enumerate(lines) if ln.startswith(("[FAIL]", "FAIL "))), None)
            caught = bool(code) and at is not None
            why = ""
            if caught:
                nxt = lines[at + 1] if at + 1 < len(lines) else ""
                why = (nxt if nxt and not nxt.startswith(("[", "FAIL ", "FAILED", "plugin ")) else lines[at])[:190]
                state = "caught    "
            elif code:
                why = f"the checks did not finish (exit code {code}); last line: {(lines[-1] if lines else '')[:110]}"
                state = "CRASHED   "
                missed.append(name + "  (the checks crashed: run it again by itself)")
            else:
                state = "NOT CAUGHT"
                missed.append(name)
            print(f"[{i:2d}/{len(chosen)}] {state} {name}  ({time.perf_counter() - t1:.0f} s){'  <- ' + why if why else ''}", flush=True)
    finally:
        for rel in touched:  # whatever happened, the files are as they were
            with open(os.path.join(ROOT, rel), "w", encoding="utf-8", newline="") as f:
                f.write(texts[rel])
    print(f"\n{len(chosen) - len(missed)} of {len(chosen)} defects caught in {time.perf_counter() - t0:.0f} s"
          + ("" if not missed else "; NOT caught:\n  " + "\n  ".join(missed)))
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
