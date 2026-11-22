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
    # ---- the smoke switch is the user's word; thin smoke; a line is not smoke (4.11.0)
    ("smoke: with the word the answer still says 'only when the frame proves smoke'", "smoke", ENGINE,
     '        return (bool(p.get("smokeOn", True)) and bool(p.get("smokeAuto", False)) and not bool(p.get("smokeFaint", False))\n',
     '        return (bool(p.get("smokeOn", True)) and bool(p.get("smokeAuto", False))\n'),
    ("smoke: the soft search is skipped (the tick trusts the wisps only)", "smoke", ENGINE,
     "            if want_smoke and smoke_faint:\n",
     "            if want_smoke and smoke_faint and False:\n"),
    ("smoke: a request without the word gets the new search too", "smoke", ENGINE,
     '        return bool(p.get("smokeOn", True)) and bool(p.get("smokeFaint", False))\n',
     '        return bool(p.get("smokeOn", True))\n'),
    ("smoke: the light is not taken out before the soft measure (a line across the wall is smoke)", "smoke", ENGINE,
     "        if self.SMOKE_SOFT_FLATTEN > 0:\n",
     "        if False:\n"),
    ("smoke: past the frame border the values are mirrored the usual way (the ends of a line are smoke)", "smoke", ENGINE,
     "            head_v, head_g = 2.0 * v[0:1] - v[pad:0:-1], g[pad:0:-1] * g[0:1]\n"
     "            tail_v, tail_g = 2.0 * v[-1:] - v[-2:-pad - 2:-1], g[-2:-pad - 2:-1] * g[-1:]\n",
     "            head_v, head_g = v[pad:0:-1], g[pad:0:-1] * g[0:1]\n"
     "            tail_v, tail_g = v[-2:-pad - 2:-1], g[-2:-pad - 2:-1] * g[-1:]\n"),
    ("smoke: what leans on an unknown border value counts", "smoke", ENGINE,
     "            head_v, head_g = 2.0 * v[0:1] - v[pad:0:-1], g[pad:0:-1] * g[0:1]\n",
     "            head_v, head_g = 2.0 * v[0:1] - v[pad:0:-1], g[pad:0:-1]\n"),
    ("smoke: a curved rim counts (the weaker direction may be as weak as it likes)", "smoke", ENGINE,
     "    SMOKE_SOFT_MIN_RATIO = 0.10\n",
     "    SMOKE_SOFT_MIN_RATIO = 0.0\n"),
    ("smoke: under 40 % the soft search still runs", "smoke", ENGINE,
     "        if smoke_strength >= self.SMOKE_SOFT_FROM:\n",
     "        if True:\n"),
    ("smoke: from 80 % up the slider reaches nothing thinner", "smoke", ENGINE,
     "    SMOKE_SOFT_PER_STEP = 0.003\n",
     "    SMOKE_SOFT_PER_STEP = 0.0\n"),
    ("smoke: below 80 % the slider gives nothing up", "smoke", ENGINE,
     "    SMOKE_SOFT_PER_STEP_LOW = 0.006\n",
     "    SMOKE_SOFT_PER_STEP_LOW = 0.0\n"),
    ("smoke: everything soft counts at any value (the dirt next to the feet too)", "smoke", ENGINE,
     "        if smoke_strength >= 100.0:\n",
     "        if True:\n"),
    ("smoke: 100 % does not mean everything", "smoke", ENGINE,
     "        if smoke_strength >= 100.0:\n",
     "        if False:\n"),
    ("smoke: a piece on the floor counts with nothing of it above the line", "smoke", ENGINE,
     "    SMOKE_SOFT_MIN_AREA = 0.004\n",
     "    SMOKE_SOFT_MIN_AREA = -1.0\n"),
    ("smoke: patches of thin smoke a few pixels apart are separate pieces (what lies on the floor is lost)", "smoke", ENGINE,
     "    SMOKE_PIECE_GAP = 17\n",
     "    SMOKE_PIECE_GAP = 1\n"),
    ("smoke: a band of wisps is smoke (the seam stays at 100 %)", "smoke", ENGINE,
     "        wisp = self._smoke_without_lines(wisp_bin > 0)\n",
     "        wisp = wisp_bin > 0\n"),
    ("smoke: a thick band of wisps is called a line", "smoke", ENGINE,
     "            if (short_side <= self.SMOKE_LINE_WIDTH and long_side >= self.SMOKE_LINE_ASPECT * short_side\n",
     "            if (long_side >= self.SMOKE_LINE_ASPECT * short_side\n"),
    ("smoke: a short piece of wisps is called a line", "smoke", ENGINE,
     "            if (short_side <= self.SMOKE_LINE_WIDTH and long_side >= self.SMOKE_LINE_ASPECT * short_side\n",
     "            if (short_side <= self.SMOKE_LINE_WIDTH\n"),
    ("smoke: a thin arc of wisps is called a line", "smoke", ENGINE,
     "                    and area >= self.SMOKE_LINE_FILL * long_side * short_side):\n",
     "                    ):\n"),
    ("smoke: the tools for lines get the whole smoke map (the corner stays under thin smoke)", "smoke", ENGINE,
     '            lines_out["smoke"] = np.clip(smoke_dense * 255, 0, 255).astype(np.uint8)\n',
     '            lines_out["smoke"] = np.clip(smoke_mask * 255, 0, 255).astype(np.uint8)\n'),
    ("smoke: the cove is gated by the whole smoke map", "smoke", ENGINE,
     "                    smoke_lines_s,\n                    shadow_s,\n                    cyc_str,\n",
     "                    smoke_s,\n                    shadow_s,\n                    cyc_str,\n"),
    ("smoke: the answer does not say that the switch was taken on trust", "smoke", ENGINE,
     '                            smoke_info.update({"on": bool(smoke_on), "auto": bool(smoke_auto), "faint": bool(smoke_faint)})\n',
     '                            smoke_info.update({"on": bool(smoke_on), "auto": bool(smoke_auto)})\n'),
    ("smoke: the maps are kept when the word is taken back", "smoke", ENGINE,
     "            k_maps = (k_fg, smoke_str, smoke_on, smoke_auto, smoke_faint, keep_shadow, gear_body)\n",
     "            k_maps = (k_fg, smoke_str, smoke_on, smoke_auto, keep_shadow, gear_body)\n"),
    ("smoke: the cleaned frame is kept when the word is taken back", "smoke", ENGINE,
     "            CleanVinylEngine._smoke_auto(p), CleanVinylEngine._smoke_faint(p),\n",
     "            CleanVinylEngine._smoke_auto(p),\n"),
    # (Not in the list, because the checks cannot tell: the corner finder and the seam search given the whole map
    # instead of the thick smoke - on the frames of the checks only the map of the cove decides.)
    # ---- the panel
    ("panel: the controls do not send the tick as the user's word", panel("every request says that the smoke switch"), MAINJS,
     '    smokeFaint: true,\n    grain: getSliderVal("gSlGrain"),\n',
     '    smokeFaint: false,\n    grain: getSliderVal("gSlGrain"),\n'),
    ("panel: a preset does not send the tick as the user's word", panel("every request says that the smoke switch"), MAINJS,
     '    smokeFaint: true,\n    grain: clampSliderVal("gSlGrain", c.grain ?? 90),\n',
     '    smokeFaint: false,\n    grain: clampSliderVal("gSlGrain", c.grain ?? 90),\n'),
    ("panel: the tick is answered with the words of the old search", panel("the smoke switch is the user's word", "thin smoke that"), MAINJS,
     "  if (byWord && sm.faint) {\n",
     "  if (false) {\n"),
    ("panel: the share that is kept is not said", panel("the smoke switch is the user's word", "thin smoke that"), MAINJS,
     "`Захист диму увімкнено: ${percentOfFrame(sm.protected)} кадру програма бере за дим",
     "`Захист диму увімкнено: частину кадру програма бере за дим"),
    ("panel: the window opens with the tick on and nothing recognised: nothing is said", panel("nothing is recognised as smoke"), MAINJS,
     "(smokeSeen.protected > 0 || smokeSeen.faint)",
     "(smokeSeen.protected > 0)"),
    ("panel: a server before 4.11.0 gets the new words", panel("a server before 4.11.0"), MAINJS,
     '  const byWord = "faint" in sm;\n',
     "  const byWord = true;\n"),
    ("panel: switched off, the new server is answered 'no smoke was found anyway'", panel("the smoke switch is the user's word", "a server before 4.11.0"), MAINJS,
     "    return byWord\n",
     "    return !byWord\n"),
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
