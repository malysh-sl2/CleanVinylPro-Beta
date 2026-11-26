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
    # ---- a new result leaves "До" (4.16.0; the owner: "when the bar reaches its end, show the photo after - now it
    #      is before, inconvenient"). All of it is the panel: the scenarios named "a new result leaves 'До'".
    ("view: the bar ends and 'До' stays on screen, as up to 4.15.0 (a recompute never shows its result)", panel("a new result leaves"), MAINJS,
     "      done = true;\n      showNewResult();  // the bar reached its end (or the light refresh is back): \"До\" gives way to the result\n",
     "      done = true;\n"),
    ("view: only the bar leaves 'До' - the light refresh of a slider or a preset comes back unseen", panel("a new result leaves"), MAINJS,
     "      showNewResult();  // the bar reached its end (or the light refresh is back): \"До\" gives way to the result\n",
     "      if (!quick) showNewResult();\n"),
    ("view: only the light refresh leaves 'До' - a run with the bar ends on the original", panel("a new result leaves"), MAINJS,
     "      showNewResult();  // the bar reached its end (or the light refresh is back): \"До\" gives way to the result\n",
     "      if (quick) showNewResult();\n"),
    ("view: 'До' is left when the run STARTS, not when its picture comes (a cancelled run has switched the view by then)", panel("a new result leaves"), MAINJS,
     "  const run = ++recomputeRun;\n  const newest = () => run === recomputeRun;\n",
     "  const run = ++recomputeRun;\n  const newest = () => run === recomputeRun;\n  showNewResult();\n"),
    ("view: a run that was cancelled or failed leaves 'До' too, though it brought nothing", panel("a new result leaves"), MAINJS,
     "      sessState.recomputing = false;\n      sessState.previewBusy = false;\n    }\n  }\n",
     "      sessState.recomputing = false;\n      sessState.previewBusy = false;\n      showNewResult();\n    }\n  }\n"),
    ("view: the answer of a run that gave way to a newer one leaves 'До' while the bar is still running", panel("a new result leaves"), MAINJS,
     "    if (!newest()) return false;  // a newer call is on its way: this answer is for values that are gone\n",
     "    if (!newest()) { showNewResult(); return false; }\n"),
    ("view: 'Маска' is left as well when a new result comes", panel("a new result leaves"), MAINJS,
     "function showNewResult() {\n  if (sessState.view === \"original\") setView(\"result\");\n",
     "function showNewResult() {\n  if (sessState.view !== \"result\") setView(\"result\");\n"),
    ("view: the exact picture that comes by itself takes the original away from whoever looks at it", panel("a new result leaves"), MAINJS,
     "    if (!refine) showNewResult();\n",
     "    showNewResult();\n"),
    ("view: with 2 passes the picture of a change comes in the background and 'До' stays on screen", panel("a new result leaves"), MAINJS,
     "    if (!refine) showNewResult();\n",
     ""),
    ("view: 'До / Після' pressed while the first bar is running - the window opens on the original", panel("a new result leaves"), MAINJS,
     "      showNewResult();  // (\"До / Після\" pressed while the first bar was running: the bar ends on the result too)\n",
     ""),
    ("view: the first bar ends on the cleaned photo whatever was asked for - also when 'Маска' was pressed", panel("a new result leaves"), MAINJS,
     "      showNewResult();  // (\"До / Після\" pressed while the first bar was running: the bar ends on the result too)\n",
     "      setView(\"result\");\n"),
    ("view: the clothing tick on 'До' brings its picture unseen", panel("a new result leaves"), MAINJS,
     "      if (takeSessionPictures(d)) showNewResult();\n",
     "      takeSessionPictures(d);\n"),
    ("view: a step on the mask (inversion, Ctrl + Z) leaves 'До' - it says in words what it did, the view is the user's", panel("a new result leaves"), MAINJS,
     "      if (typeof d.mask_share === \"number\") sessState.maskShare = d.mask_share;\n      if (d.history) setEditHistory(d.history);\n",
     "      if (typeof d.mask_share === \"number\") sessState.maskShare = d.mask_share;\n      if (d.history) setEditHistory(d.history);\n      showNewResult();\n"),
    # (Not in the list, because the checks cannot tell:
    #   - "a run that the SERVER stopped for a request of another window leaves 'До'" (the branch `d.superseded` of
    #     the newest call): the scripted server of the test stops a run only for a newer request of the same window,
    #     and that older call is not the newest any more.)
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
