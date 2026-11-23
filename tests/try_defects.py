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
    # ---- thick smoke is not gear (4.12.0: the owner's first frame with real smoke)
    ("smoke: thick smoke stays gear although the user says the frame has smoke", "smoke", ENGINE,
     "        if smoke_faint and protect_smoke and smoke_strength > 5 and bool(any_lut.any()):\n",
     "        if False:\n"),
    ("smoke: a group of strong edges that has a direction counts as smoke (a soft pole)", "smoke", ENGINE,
     "    SMOKE_EDGE_SHARE = 0.70\n",
     "    SMOKE_EDGE_SHARE = 0.0\n"),
    ("smoke: a group with hard edges counts as smoke (a knot of dark pieces)", "smoke", ENGINE,
     "    SMOKE_EDGE_WIDTH = 4.0\n",
     "    SMOKE_EDGE_WIDTH = 0.0\n"),
    ("smoke: thick smoke is no gear any more, but the smoke search still leaves it out", "smoke", ENGINE,
     "            edge_lut[1:][is_smoke] = 0.0\n            any_lut[1:][is_smoke] = 0.0\n",
     "            edge_lut[1:][is_smoke] = 0.0\n"),
    ("smoke: thick smoke is searched for smoke, but stays gear and is marked for removal", "smoke", ENGINE,
     "            edge_lut[1:][is_smoke] = 0.0\n            any_lut[1:][is_smoke] = 0.0\n",
     "            any_lut[1:][is_smoke] = 0.0\n"),
    # ---- the mixer brush
    ("mix: the brush works although it is switched off", "mix", ENGINE,
     '        if not bool(p.get("mixOn", False)):\n            return 0.0\n',
     '        if False:\n            return 0.0\n'),
    ("mix: the strength is ignored (always a half)", "mix", ENGINE,
     "                blend = mix_w * np.float32(mix_str / 100.0)\n",
     "                blend = mix_w * np.float32(0.5)\n"),
    ("mix: the smooth copy is not smooth", "mix", ENGINE,
     "    MIX_SIGMA = 0.016\n",
     "    MIX_SIGMA = 0.0008\n"),
    ("mix: the grain goes altogether at full strength", "mix", ENGINE,
     "    MIX_GRAIN_MIN = 0.35\n",
     "    MIX_GRAIN_MIN = 0.0\n"),
    ("mix: the shadow is brushed over", "mix", ENGINE,
     "        open_w = ((1.0 - np.clip(st_b * 1.25, 0.0, 1.0)) * (1.0 - np.clip(sh_b * 1.35, 0.0, 1.0))\n",
     "        open_w = ((1.0 - np.clip(st_b * 1.25, 0.0, 1.0))\n"),
    ("mix: the gear is brushed over", "mix", ENGINE,
     "        open_w = ((1.0 - np.clip(st_b * 1.25, 0.0, 1.0)) * (1.0 - np.clip(sh_b * 1.35, 0.0, 1.0))\n",
     "        open_w = ((1.0 - np.clip(sh_b * 1.35, 0.0, 1.0))\n"),
    ("mix: protected smoke is brushed over", "mix", ENGINE,
     "                  * (1.0 - np.clip(sm_b * 1.25, 0.0, 1.0)))\n",
     "                  )\n"),
    ("mix: the person takes part in the smooth copy (its colour bleeds into the backdrop)", "mix", ENGINE,
     "        src_w = (fg_b < 0.08).astype(np.float32) * open_w\n        sigma = max(1.5, self.MIX_SIGMA * max(bw, bh))\n",
     "        src_w = open_w\n        sigma = max(1.5, self.MIX_SIGMA * max(bw, bh))\n"),
    ("mix: the smooth copy is a plain average (the tone next to the person is pulled away)", "mix", ENGINE,
     "            out[:, :, ch] = np.where(firm, plane, plain)\n",
     "            out[:, :, ch] = plain\n"),
    ("mix: the layer does not cover what was brushed", "mix", ENGINE,
     "                np.maximum(final_alpha, mix_w, out=final_alpha)\n",
     "                pass\n"),
    ("mix: the brush is no stage of the whole backdrop for the window", "mix", ENGINE,
     "                or CleanVinylEngine._mix_strength(p) > 0)\n",
     "                )\n"),
    ("mix: the smooth copy is kept when the transition next to the person changes", "mix", ENGINE,
     "            k_mix = (k_blur, clean_passes, feather_str)\n",
     "            k_mix = (k_blur, clean_passes)\n"),
    ("mix: the cleaned frame is kept when only the brush changes (Apply)", "mix", ENGINE,
     "            CleanVinylEngine._smoke_auto(p), CleanVinylEngine._smoke_faint(p),\n            CleanVinylEngine._mix_strength(p),\n",
     "            CleanVinylEngine._smoke_auto(p), CleanVinylEngine._smoke_faint(p),\n"),
    # (Not in the list, because the checks cannot tell: the person is kept out of the brush twice - by the ramp
    # and by the last line of _mix_brush_small; either alone is enough.)
    # ---- the newest values win
    ("restart: a recompute does not give way to a newer one", "restart", ENGINE,
     "                        if self._fg_seq != my_seq or self._active_session is not sess:\n",
     "                        if self._active_session is not sess:\n"),
    ("restart: a request overtaken while it waited computes all the same", "restart", ENGINE,
     '                    if self._fg_seq != my_seq:\n                        return {"ok": True, "session_id": session_id, "superseded": True}\n',
     '                    if False:\n                        return {"ok": True, "session_id": session_id, "superseded": True}\n'),
    ("restart: the stopped run leaves its hook in the thread (the next request there is stopped)", "restart", ENGINE,
     '                    except JobSuperseded:\n                        return {"ok": True, "session_id": session_id, "superseded": True}\n'
     "                    finally:\n                        self._bg_local.check = None\n                    return self._recompute_commit(sess, p, computed, preserve_edits, t0)\n",
     '                    except JobSuperseded:\n                        return {"ok": True, "session_id": session_id, "superseded": True}\n'
     "                    return self._recompute_commit(sess, p, computed, preserve_edits, t0)\n"),
    # ---- the panel
    ("panel: the smoke tick gives a light refresh only", panel("the smoke tick recomputes"), MAINJS,
     '      : "Захист диму вимкнено (повзунок у налаштуваннях неактивний)" + (live ? " — перераховую…" : ""));\n    recomputeExactNow();\n',
     '      : "Захист диму вимкнено (повзунок у налаштуваннях неактивний)" + (live ? " — перераховую…" : ""));\n    refreshPreviewAfterClick(false);\n'),
    ("panel: the smoke switch of the settings gives a light refresh only", panel("the smoke tick recomputes"), MAINJS,
     "    recomputeExactNow();  // (as the tick at the top of the window: the same switch)\n",
     "    requestPreviewRefresh(PREVIEW_DELAY_CLICK_MS, false);\n"),
    ("panel: the button of the bottom bar does nothing", panel("on the bottom bar"), MAINJS,
     '      sayInWindow("↻ Перераховую точний кадр для значень на повзунках…");\n      recomputeExactNow();\n',
     '      sayInWindow("↻ Перераховую точний кадр для значень на повзунках…");\n'),
    ("panel: a change while the bar is running starts a light refresh", panel("while the bar is running"), MAINJS,
     "  if (overtakes && !sessState.previewBusy) quick = false;  // the bar is running: it goes on, from the start\n",
     ""),
    ("panel: the picture of an overtaken run is put on screen", panel("with a server before 4.12.0", "the old run is finished first"), MAINJS,
     "    if (!newest()) return false;  // a newer call is on its way: this answer is for values that are gone\n",
     ""),
    ("panel: the progress card goes away with the answer of an overtaken run", panel("the old run is finished first", "with a server before 4.12.0"), MAINJS,
     "    if (timeoutId) clearTimeout(timeoutId);\n    if (newest()) {\n",
     "    if (timeoutId) clearTimeout(timeoutId);\n    if (true) {\n"),
    ("panel: '[' and ']' are told by their character only", panel("makes the brush smaller"), MAINJS,
     '  if (code === "BracketLeft" || k === "[" || k === "{" || k === "х" || n === 219) return "down";\n',
     '  if (k === "[" || k === "{" || k === "х" || n === 219) return "down";\n'),
    ("panel: the Ukrainian letter of '[' is not known", panel("makes the brush smaller"), MAINJS,
     '  if (code === "BracketLeft" || k === "[" || k === "{" || k === "х" || n === 219) return "down";\n',
     '  if (code === "BracketLeft" || k === "[" || k === "{" || n === 219) return "down";\n'),
    ("panel: the Ukrainian letter of ']' is not known", panel("makes the brush smaller"), MAINJS,
     '  if (code === "BracketRight" || k === "]" || k === "}" || k === "ї" || k === "ъ" || n === 221) return "up";\n',
     '  if (code === "BracketRight" || k === "]" || k === "}" || k === "ъ" || n === 221) return "up";\n'),
    ("panel: the number of the key is not asked", panel("makes the brush smaller"), MAINJS,
     '  if (code === "BracketRight" || k === "]" || k === "}" || k === "ї" || k === "ъ" || n === 221) return "up";\n',
     '  if (code === "BracketRight" || k === "]" || k === "}" || k === "ї" || k === "ъ") return "up";\n'),
    ("panel: a check box that has the focus swallows the keys of the brush", panel("makes the brush smaller"), MAINJS,
     "    if (typing) return;  // (a check box that was clicked last does not swallow the keys of the tools)\n",
     '    if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA")) return;\n'),
    ("panel: with Ctrl the key still changes the brush", panel("makes the brush smaller"), MAINJS,
     '    const brushKey = (e.ctrlKey || e.metaKey || e.altKey) ? "" : brushKeyOf(e);\n',
     "    const brushKey = brushKeyOf(e);\n"),
    ("panel: one step for every size of the brush", panel("makes the brush smaller"), MAINJS,
     "  return s < 20 ? 2 : s < 60 ? 5 : s < 120 ? 10 : 20;\n",
     "  return 6;\n"),
    ("panel: the mixer brush is not sent with the values of the controls", panel("Мікс-пензель"), MAINJS,
     '    mixOn: mixEnabled,\n    mix: getSliderVal("gSlMix"),\n    cycCurve: getSliderVal("gSlCyc"),\n',
     '    mixOn: false,\n    mix: getSliderVal("gSlMix"),\n    cycCurve: getSliderVal("gSlCyc"),\n'),
    ("panel: the sets of the automatic preset do not carry the mixer brush", panel("the mixer brush kept"), MAINJS,
     '    mixOn: mixEnabled,\n    mix: getSliderVal("gSlMix"),\n    cycCurve: clampSliderVal("gSlCyc", c.cycCurve ?? 0),\n',
     '    mixOn: false,\n    mix: getSliderVal("gSlMix"),\n    cycCurve: clampSliderVal("gSlCyc", c.cycCurve ?? 0),\n'),
    ("panel: the tick of the mixer brush does not make the preview out of date", panel("Мікс-пензель"), MAINJS,
     "    c.strayHair, !!c.mixOn, c.mixOn ? c.mix : 0\n",
     "    c.strayHair\n"),
    ("panel: the mixer brush is not kept with the settings", panel("Мікс-пензель"), MAINJS,
     '    mixOn: mixEnabled,\n    mixStrength: getSliderVal("gSlMix"),\n',
     ""),
    ("panel: the mixer brush is not read from the settings", panel("the mixer brush kept"), MAINJS,
     '  if (typeof s.mixOn === "boolean") mixEnabled = s.mixOn;\n',
     ""),
    ("panel: the mixer brush is written into a preset", panel("Мікс-пензель"), MAINJS,
     "  delete cfg.mixOn;  // (the mixer brush is the user's own switch, not a part of any preset - see mixEnabled)\n",
     ""),
    ("panel: the tick at the top does not follow the switch of the settings", panel("Мікс-пензель"), MAINJS,
     '  if (el("dlgChkMix")) el("dlgChkMix").checked = mixEnabled;\n',
     ""),
    ("panel: a click on the caption of a check box does not tick it", panel("a check box is ticked"), MAINJS,
     "      input.checked = !input.checked;\n      if (checkHandlers[id]) checkHandlers[id]();\n",
     "      if (checkHandlers[id]) checkHandlers[id]();\n"),
    ("panel: a click on the caption ticks the box but does not do its work", panel("a check box is ticked"), MAINJS,
     "      input.checked = !input.checked;\n      if (checkHandlers[id]) checkHandlers[id]();\n",
     "      input.checked = !input.checked;\n"),
    ("panel: a click on the check box itself counts twice", panel("a check box is ticked"), MAINJS,
     "      if (!input || e.target === input || input.disabled) return;  // (the check box itself ticks by itself)\n",
     "      if (!input || input.disabled) return;\n"),
    ("panel: a check box without its box (the caption does not tick it)", panel("a check box is ticked"), PLUGIN + "/index.html",
     '<div class="ps-check" data-check="gChkShadow" data-tip="Зберігати тіні під моделлю',
     '<div class="ps-check" data-tip="Зберігати тіні під моделлю'),
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
