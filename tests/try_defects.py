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
touched by these. The server's list of built-in presets (presets_defaults.json) is copied next to that folder,
where both tests read it, and can take a defect of the panel as well.
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


# The three scenarios named "'Глибина' ..." (the slider, and the two of a PC of 4.16.0), the automatic preset on a dark
# frame, and the backup of an older version: where the window shows what the dark presets ship.
DEPTH10 = ("'Глибина'", "automatic preset: a dark frame takes", "restoring a backup made by an older version")
PRESETS_JSON = "CleanVinylPro2/server/presets_defaults.json"
# "Темний дальній план" as the server's list writes it, up to the value in question (the line of its colour is the
# only one in the file; "Темний ключ" has the same values)
_WIDE_JSON = '    "color": "#8468e8",\n    "builtin": true,\n    "cfg": {\n' + "".join(f'      "{k}": {v},\n' for k, v in (
    ("spots", 80), ("scuffs", 55), ("blur", 0), ("feather", 65), ("seamOn", "true"), ("seam", 90), ("edge", 78), ("smokeOn", "false"),
    ("smoke", 70), ("grain", 95), ("shadow", "true"), ("removeStands", "false"), ("master", 100), ("fracFine", "true"), ("fracMed", "true"),
    ("fracLarge", "true"), ("dressSmooth", "false"), ("dressStrength", 40), ("cycCurve", 65)))
_MOVE = '  { id: "darkDepth10", presets: ["lowkey", "lowkey_medium", "lowkey_wide"], key: "cycDepth", slider: "gSlDepth", from: 0, to: 10 }\n'
_WIDE = "        wide = 1.0 + self.CORNER_DEPTH_WIDE * float(np.clip(depth / 100.0, 0.0, 1.0))\n"


def _preset_js(preset_id, name, color, head, depth):
    """The first lines of a built-in preset in DEFAULT_PRESETS of main.js, up to its depth."""
    return f'    id: "{preset_id}",\n    name: "{name}",\n    color: "{color}",\n    builtin: true,\n    cfg: {{ {head}, cycCurve: 65, cycDepth: {depth},'


# (name, check groups - or panel(<text>, ...), file, exact text, replacement)
DEFECTS = [
    # ---- "Глибина" 10 in the dark presets (4.17.0; the owner had put 10 on a low-key frame by hand and, asked
    #      whether the dark presets should come with it, wrote «я поставив 10 став одразу»).
    # The engine is as it was. What the new value leans on - a small depth is a small step - is asked of it now:
    ("depth: any depth above 0 widens the cove in full - the 10 of the dark presets is as much as 100", "depth", ENGINE,
     _WIDE, "        wide = 1.0 + self.CORNER_DEPTH_WIDE * float(depth > 0)\n"),
    ("depth: the widening is twice what the slider says - 10 does what 20 should", "depth", ENGINE,
     _WIDE, "        wide = 1.0 + self.CORNER_DEPTH_WIDE * float(np.clip(depth / 50.0, 0.0, 1.0))\n"),
    ("depth: a depth under 20 counts as none - what the dark presets ship does nothing", "depth", ENGINE,
     _WIDE, "        wide = 1.0 + self.CORNER_DEPTH_WIDE * float(np.clip((depth if depth >= 20 else 0.0) / 100.0, 0.0, 1.0))\n"),
    # What the presets ship: the plugin's own list and the server's.
    ("presets: 'Темний дальній план' ships depth 0, as up to 4.16.0 (the plugin's list)", panel(*DEPTH10), MAINJS,
     _preset_js("lowkey_wide", "Темний дальній план", "#8468e8", "spots: 80, scuffs: 55, blur: 0", 10),
     _preset_js("lowkey_wide", "Темний дальній план", "#8468e8", "spots: 80, scuffs: 55, blur: 0", 0)),
    ("presets: 'Темний ключ' ships depth 0, as up to 4.16.0 (the plugin's list)", panel(*DEPTH10), MAINJS,
     _preset_js("lowkey", "Темний ключ", "#9d7cff", "spots: 80, scuffs: 55, blur: 0", 10),
     _preset_js("lowkey", "Темний ключ", "#9d7cff", "spots: 80, scuffs: 55, blur: 0", 0)),
    ("presets: 'Темний середній план' ships depth 0, as up to 4.16.0 (the plugin's list)", panel(*DEPTH10), MAINJS,
     _preset_js("lowkey_medium", "Темний середній план", "#b190ff", "spots: 72, scuffs: 50, blur: 0", 10),
     _preset_js("lowkey_medium", "Темний середній план", "#b190ff", "spots: 72, scuffs: 50, blur: 0", 0)),
    ("presets: the server's list keeps depth 0 for 'Темний дальній план' (presets_defaults.json)", panel(*DEPTH10), PRESETS_JSON,
     _WIDE_JSON + '      "cycDepth": 10,\n', _WIDE_JSON + '      "cycDepth": 0,\n'),
    # The one-time move for a PC that holds its presets.
    ("move: there is no move for the dark presets - a PC that holds its presets keeps depth 0 in them", panel(*DEPTH10), MAINJS,
     _MOVE, ""),
    ("move: the dark close-up is moved too ('Темний ближній план' has no corner tool and ships 0)", panel(*DEPTH10), MAINJS,
     _MOVE, _MOVE.replace('"lowkey_medium", "lowkey_wide"]', '"lowkey_medium", "lowkey_close", "lowkey_wide"]')),
    ("move: 'Темний ключ' is left out of the move", panel(*DEPTH10), MAINJS,
     _MOVE, _MOVE.replace('["lowkey", "lowkey_medium", "lowkey_wide"]', '["lowkey_medium", "lowkey_wide"]')),
    ("move: 'Темний середній план' is left out of the move", panel(*DEPTH10), MAINJS,
     _MOVE, _MOVE.replace('["lowkey", "lowkey_medium", "lowkey_wide"]', '["lowkey", "lowkey_wide"]')),
    ("move: 'Темний дальній план' is left out of the move - the preset of a dark full-length frame keeps 0", panel(*DEPTH10), MAINJS,
     _MOVE, _MOVE.replace('["lowkey", "lowkey_medium", "lowkey_wide"]', '["lowkey", "lowkey_medium"]')),
    ("move: the slider of the active dark preset is not moved (the move names no slider)", panel(*DEPTH10), MAINJS,
     _MOVE, _MOVE.replace(' slider: "gSlDepth",', '')),
    ("move: the move leads to 60, the depth of the light presets", panel(*DEPTH10), MAINJS,
     _MOVE, _MOVE.replace("to: 10 }", "to: 60 }")),
    ("move: the move takes 60 for the former value - a dark preset at 0 is never moved", panel(*DEPTH10), MAINJS,
     _MOVE, _MOVE.replace("from: 0,", "from: 60,")),
    ("move: a move does not ask what the preset holds - a depth the user saved into a dark preset is replaced by 10", panel(*DEPTH10), MAINJS,
     "      if (!isFormer(p.cfg[m.key] ?? m.from)) return;\n",
     ""),
    ("move: a move does not ask what stands on the slider - a depth put there by hand is replaced by 10", panel(*DEPTH10), MAINJS,
     "    if (m.slider && getSliderVal(m.slider) === m.from) {\n",
     "    if (m.slider) {\n"),
    # The hint of the row.
    ("hint: the hint of 'Глибина' still says 0% for the dark presets", panel(*DEPTH10), PLUGIN + "/index.html",
     "У світлих пресетах стоїть 60%, у темних — 10%.",
     "У світлих пресетах стоїть 60%, у темних — 0%."),
    # (Not in the list, because it is no rule of the program: which number is right for a dark frame. 10 is the
    #  owner's own choice; what it does on his six dark frames was measured and looked at - see AGENTS.md.)
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
