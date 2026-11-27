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


# The scenarios of the tick «Стійки» (six, their names begin with 'Стійки'), and with them the two of the backup.
STANDS = ("'Стійки'",)
STANDS_BACKUP = ("'Стійки'", "backup: everything is saved", "restoring a backup made by an older version")
# The scenario of the name ("the name has no 2 and carries the version: ...").
NAME = ("the name has no 2",)
MANIFEST = PLUGIN + "/manifest.json"
INDEX = PLUGIN + "/index.html"
_BY_HAND = "  if (byHand && STANDS_PRESET_IDS.includes(p.id)) standsEnabled = true;\n"
_READ_NEW = '  if (typeof s.standsOn === "boolean") standsEnabled = s.standsOn;\n'
_READ_OLD = '  else if (s.cfg && typeof s.cfg === "object" && typeof s.cfg.removeStands === "boolean") standsEnabled = s.cfg.removeStands;\n'
_NOTE = '      const standsNote = untouched && standsEnabled ? "Стійки прибираються: галочка «Стійки» стоїть, як ви її лишили." : "";\n'
_TICK = '    standsEnabled = !!el("dlgChkStands").checked;\n    updateSliderVisuals();\n    scheduleSaveSettings();\n'
_SAID_ON = "Тіні людини лишаються. Галочка стоятиме й на наступних фото, доки ви її не знімете."
_SAID_OFF = "Галочка лишиться знятою й на наступних фото, доки ви її не поставите."
_TIP = (" Галочка не належить пресету: як поставили, так і лишається — для наступних фото, для будь-якого пресета й після перезапуску "
        "Photoshop. Ставить її ще тільки пресет «Без стійок (AI)», коли ви клацаєте його самі; знімаєте її лише ви.")


# (name, check groups - or panel(<text>, ...), file, exact text, replacement)
DEFECTS = [
    # ---- The tick «Стійки» is the user's own (4.18.0). The owner, 2026-11-27: «дивися я ставлю галочку щзі стойками
    #      а вона відключається зроби як я посллідніраз ш так би вона і другий раз була».
    # What took the tick away up to 4.17.0: a preset put on the controls, and the sets offered to the server.
    ("stands: a preset put on the controls sets the tick from its own values, as up to 4.17.0 - the next photo takes it off", panel(*STANDS), MAINJS,
     '  if (el("gChkShadow")) el("gChkShadow").checked = c.shadow;\n  setSliderVal("gSlTurbo", c.master);\n',
     '  if (el("gChkShadow")) el("gChkShadow").checked = c.shadow;\n  standsEnabled = !!(cfg && cfg.removeStands);\n  setSliderVal("gSlTurbo", c.master);\n'),
    ("stands: the sets offered to the server carry the preset's own value - with the automatic preset the next photo is cleaned with the stands", panel(*STANDS), MAINJS,
     "    // (the stands are not a matter of the preset either: every set carries the tick as the user left it)\n    removeStands: standsEnabled,\n",
     "    // (the stands are not a matter of the preset either: every set carries the tick as the user left it)\n    removeStands: !!c.removeStands,\n"),
    ("stands: the first scan of a photo does not carry the tick (the values of the controls say 'keep the stands')", panel(*STANDS), MAINJS,
     '    shadow: el("gChkShadow") ? el("gChkShadow").checked : true,\n    removeStands: standsEnabled,\n',
     '    shadow: el("gChkShadow") ? el("gChkShadow").checked : true,\n    removeStands: false,\n'),
    # The tick itself.
    ("stands: the tick is not taken from the box - it jumps back, the stands stay", panel(*STANDS), MAINJS,
     _TICK, "    updateSliderVisuals();\n    scheduleSaveSettings();\n"),
    ("stands: the tick is not written to the settings when it is put (closing Photoshop right away loses it)", panel(*STANDS), MAINJS,
     _TICK, '    standsEnabled = !!el("dlgChkStands").checked;\n    updateSliderVisuals();\n'),
    ("stands: the box does not follow the switch - after a restart the stands go, the box is empty", panel(*STANDS), MAINJS,
     '  if (el("dlgChkStands")) el("dlgChkStands").checked = standsEnabled;\n', ""),
    ("stands: the pill of the tick is never lit", panel(*STANDS), MAINJS,
     '  if (el("dlgWrapStands")) el("dlgWrapStands").classList.toggle("active", standsEnabled);\n',
     '  if (el("dlgWrapStands")) el("dlgWrapStands").classList.toggle("active", false);\n'),
    # Kept with the settings; a file of 4.17.0; a backup.
    ("stands: the settings are read without the tick - Photoshop started again opens with the stands in the frame", panel(*STANDS_BACKUP), MAINJS,
     _READ_NEW + _READ_OLD, ""),
    ("stands: only the new word of the settings is read - on a PC of 4.17.0 the tick that stood there is lost", panel(*STANDS_BACKUP), MAINJS,
     _READ_OLD, ""),
    ("stands: the settings can only put the tick, never take it off - a backup made with the tick off leaves it on", panel(*STANDS_BACKUP), MAINJS,
     _READ_NEW + _READ_OLD, '  if (s.cfg && typeof s.cfg === "object" && s.cfg.removeStands === true) standsEnabled = true;\n'),
    ("stands: a preset that is saved holds the tick again", panel(*STANDS), MAINJS,
     "  delete cfg.removeStands;  // (...and so are the stands - see standsEnabled)\n", ""),
    # Which preset puts the tick, and when.
    ("stands: a click by hand on 'Без стійок (AI)' no longer puts the tick", panel(*STANDS), MAINJS,
     _BY_HAND, ""),
    ("stands: 'Без стійок (AI)' puts the tick whoever applies it - the program too (a restart, the automatic choice off)", panel(*STANDS), MAINJS,
     _BY_HAND, "  if (STANDS_PRESET_IDS.includes(p.id)) standsEnabled = true;\n"),
    ("stands: every preset clicked by hand puts the tick", panel(*STANDS), MAINJS,
     _BY_HAND, "  if (byHand) standsEnabled = true;\n"),
    ("stands: a preset clicked by hand sets the tick from its own values - any preset takes it off, as up to 4.17.0", panel(*STANDS), MAINJS,
     _BY_HAND, "  if (byHand) standsEnabled = !!(p.cfg && p.cfg.removeStands);\n"),
    ("stands: any preset saved with 'removeStands: true' puts the tick when clicked - also the user's own of 4.17.0", panel(*STANDS), MAINJS,
     _BY_HAND, "  if (byHand && p.cfg && p.cfg.removeStands === true) standsEnabled = true;\n"),
    ("stands: the click on a preset is not passed on as the user's act - no preset puts the tick in the window", panel(*STANDS), MAINJS,
     "      applyPreset(p, true);\n", "      applyPreset(p);\n"),
    ("stands: 'Скинути пресет' is not the user's act - resetting 'Без стійок (AI)' puts nothing", panel(*STANDS), MAINJS,
     "  applyPreset(active, true);\n", "  applyPreset(active);\n"),
    # What the window says.
    ("stands: a window that opens with the tick left on does not say so", panel(*STANDS), MAINJS,
     _NOTE, '      const standsNote = "";\n'),
    ("stands: every opening speaks of the stands, also with the tick off", panel(*STANDS), MAINJS,
     _NOTE, _NOTE.replace("untouched && standsEnabled ?", "untouched ?")),
    ("stands: the hint line does not say that the tick will stay", panel(*STANDS), MAINJS,
     _SAID_ON, "Тіні людини лишаються."),
    ("stands: ...nor that a tick taken off stays off", panel(*STANDS), MAINJS,
     " " + _SAID_OFF, ""),
    ("stands: the hint of the tick does not say whose it is", panel(*STANDS), INDEX,
     _TIP, ""),
    # ---- The version next to the name (4.18.0). The owner: «і ще у назві плагіна пиши версію бо деколи не розумію чи
    #      установ нову чи то стара». manifest.json is written by hand with every version: the likely mistake there
    #      is a number that was not moved on - asked of the window test and of the group `server`.
    ("name: the manifest names the plugin without the version (the Plugins menu)", panel(*NAME), MANIFEST,
     '  "name": "Чистий Вініл Pro 4.18.0",\n', '  "name": "Чистий Вініл Pro",\n'),
    ("name: the tab of the panel carries no version (the label in the manifest)", panel(*NAME), MANIFEST,
     '        "default": "Чистий Вініл Pro 4.18.0"\n', '        "default": "Чистий Вініл Pro"\n'),
    ("name: the manifest name still carries the version before - the number was moved on, the name was not", panel(*NAME), MANIFEST,
     '  "name": "Чистий Вініл Pro 4.18.0",\n', '  "name": "Чистий Вініл Pro 4.17.0",\n'),
    ("name: the manifest name still carries the version before, asked of the group server", "server", MANIFEST,
     '  "name": "Чистий Вініл Pro 4.18.0",\n', '  "name": "Чистий Вініл Pro 4.17.0",\n'),
    ("name: the label of the panel still carries the version before, asked of the group server", "server", MANIFEST,
     '        "default": "Чистий Вініл Pro 4.18.0"\n', '        "default": "Чистий Вініл Pro 4.17.0"\n'),
    ("name: the title of the big window has no version", panel(*NAME), MAINJS,
     "      title: PLUGIN_TITLE,\n", "      title: PLUGIN_NAME,\n"),
    ("name: the title of the big window has no version, asked of the group server", "server", MAINJS,
     "      title: PLUGIN_TITLE,\n", "      title: PLUGIN_NAME,\n"),
    ("name: no version under the name on the panel (main.js does not write it)", panel(*NAME), MAINJS,
     '  if (el("brandVersion")) el("brandVersion").textContent = "версія " + PLUGIN_VERSION;\n', ""),
    ("name: the version on the panel is a number written by hand - the one of the version before", panel(*NAME), MAINJS,
     '"версія " + PLUGIN_VERSION;\n', '"версія 4.17.0";\n'),
    ("name: the panel has no place for the version (index.html)", panel(*NAME), INDEX,
     '          <div class="brand-version" id="brandVersion"></div>\n', ""),
    ("name: the step of the History panel carries the version - it goes into the document", panel(*NAME), MAINJS,
     '        documentID: doc.id,\n        name: "Чистий Вініл Pro"\n', "        documentID: doc.id,\n        name: PLUGIN_TITLE\n"),
    # (Not in the list, because the checks cannot tell: how Photoshop shows the name of the manifest - in the Plugins
    #  menu, on the tab, in the list of Creative Cloud - and whether a panel whose label changes with every version
    #  keeps its place in his workspace. And which of two words of a settings file wins when they disagree: a file
    #  written by the program never holds such a pair.)
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
