#!/usr/bin/env python3
"""
Puts deliberate defects into the program, one at a time, and tells whether the self-checks notice.

    python tests/try_defects.py             # every defect of the list below
    python tests/try_defects.py seam cyc    # only the defects whose check group or name contains one of the words
    python tests/try_defects.py --list      # show the list, change nothing

A check that lets a defect through is a hole in the checks, not a proof that the code is right. For every defect
the script replaces one exact piece of text in a program file, runs the check groups the defect belongs to
(tests/run_checks.py <groups>), puts the file back and reports "caught" or "NOT CAUGHT".

A defect of the PANEL (the word "panel" instead of a check group) is put into a copy of the plugin folder, and the
two tests of the panel are pointed at that copy (CV_PLUGIN_DIR): the settings test, and the scenarios of the
window test whose names contain the text given with the defect. The program files are not touched by these.
They need Node.js and the jsdom package (tests/README.md).

Do NOT edit the program files, build the package or run the checks yourself while this is going: the script
changes the files in place. It restores them when it ends, also after Ctrl+C. If it is killed outright, the
last defect stays in the file: `git diff` shows it, `git checkout -- <file>` removes it (mind your own
uncommitted work in that file - the script refuses to start when the list no longer fits the files).

The list holds the defects for what was new in the last version. Replace it when the next version adds rules:
old entries stop fitting as the code moves on, and the script says so ("out of date") instead of guessing.
A defect that changes nothing the program does (a second line of defence, a dead branch) cannot be caught and
does not belong in the list.
"""
import os
import shutil
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


def panel(text):
    """A defect of the panel: checked by the settings test and by the window scenarios whose names contain `text`."""
    return ("panel", text)


# (name, check groups - or panel(<text>), file, exact text, replacement)
DEFECTS = [
    # ---- the edge of the brush and the eraser (4.7.0)
    ("brush: the soft edge is as narrow as the hard one", "brush", ENGINE,
     "    BRUSH_SOFT_BAND = 1.0 ", "    BRUSH_SOFT_BAND = 0.2 "),
    ("brush: the hard edge is as wide as the soft one", "brush", ENGINE,
     "    BRUSH_HARD_BAND = 0.2 ", "    BRUSH_HARD_BAND = 1.0 "),
    ("brush: a stroke that names no edge is a hard one", "brush", ENGINE,
     "                        soft = 1.0 if softness is None else float(np.clip(softness, 0.0, 1.0))",
     "                        soft = 0.0 if softness is None else float(np.clip(softness, 0.0, 1.0))"),
    ("brush: the server drops the edge that the panel asked for", "brush", SERVER,
     "            None if softness is None else float(softness),\n", "            None,\n"),
    # ---- the person (4.7.0)
    ("brush: the soft brush paints over the person", "brush", ENGINE,
     "        return alpha * (1.0 - keep_out * float(np.clip(softness, 0.0, 1.0)))", "        return alpha"),
    ("brush: the hard brush keeps off the person too", "brush", ENGINE,
     "        return alpha * (1.0 - keep_out * float(np.clip(softness, 0.0, 1.0)))", "        return alpha * (1.0 - keep_out)"),
    # ---- what a painted zone is made of (4.7.0)
    ("brush: the layer is not repainted where the brush went", "brush", ENGINE,
     "                if brush_soft:\n                    strength_s = self._brush_strength_small(sess)\n",
     "                if False:\n                    strength_s = self._brush_strength_small(sess)\n"),
    ("brush: the window does not show what the brush painted", "brush", ENGINE,
     "            strength = self._brush_strength_small(sess)\n            if np.any(strength):\n",
     "            strength = self._brush_strength_small(sess)\n            if False:\n"),
    ("brush: a painted zone gets no grain", "brush", ENGINE,
     "                    + np.sin(ang)[..., None] * g_b)", "                    + 0.0 * g_b)"),
    ("brush: the two grains are mixed plainly in the soft edge", "brush", ENGINE,
     "            dst += (a[..., None] * (fill_b - lp_b) + (np.cos(ang) - 1.0)[..., None] * detail\n                    + np.sin(ang)[..., None] * g_b)",
     "            dst += (a[..., None] * (fill_b - lp_b) - a[..., None] * detail\n                    + a[..., None] * g_b)"),
    # ---- the tone near a shadow, and with nothing around (4.7.0)
    ("brush: a shadow that a stroke touches goes into the tone", "brush", ENGINE,
     "    BRUSH_ODD_K = 3.0\n", "    BRUSH_ODD_K = 1e9\n"),
    ("brush: no part of the surroundings is ever 'most'", "brush", ENGINE,
     "    BRUSH_MOST = (0.45, 0.65)\n", "    BRUSH_MOST = (2.0, 3.0)\n"),
    ("brush: surroundings of two kinds are taken for uneven ones", "brush", ENGINE,
     "    BRUSH_SECOND = (0.10, 0.25)\n", "    BRUSH_SECOND = (2.0, 3.0)\n"),
    ("brush: the tone stays as soon as a stroke touches anything", "brush", ENGINE,
     "    BRUSH_SECOND = (0.10, 0.25)\n", "    BRUSH_SECOND = (0.0, 0.01)\n"),
    ("brush: the even part is looked for with the wide band", "brush", ENGINE,
     "    BRUSH_FIT_TOL = 0.015\n", "    BRUSH_FIT_TOL = 0.04\n"),
    ("brush: a backdrop painted all over is repainted from the strip that is left", "brush", ENGINE,
     "    BRUSH_RING_MIN = (0.10, 0.20)\n", "    BRUSH_RING_MIN = (0.0, 0.0)\n"),
    # ---- "fill" (4.7.0)
    ("fill: the whole frame counts as painted, as before 4.7.0", "mask", ENGINE,
     "                if op == \"fill\" and soft_mode:\n", "                if op == \"fill\" and False:\n"),
    ("fill: a step back leaves the layer on the whole frame", "brush", ENGINE,
     "        sess[\"fill_all\"] = bool(snap.get(\"fill\", False))\n", ""),
    # ---- the panel: the two edge buttons (4.7.0)
    ("panel: every stroke is sent as a soft one, whatever button is on", panel("edge"), MAINJS,
     "    softness: sessState.brushSoft ? 1 : 0,", "    softness: 1,"),
    ("panel: a stroke does not say which edge it has", panel("edge"), MAINJS,
     "    softness: sessState.brushSoft ? 1 : 0,   // the edge of the stroke: 1 soft, 0 hard (a server before 4.7.0 ignores it)\n", ""),
    ("panel: the window starts with the hard edge", panel("edge"), MAINJS,
     "  brushSoft: true,\n", "  brushSoft: false,\n"),
    ("panel: the lower button chooses the soft edge too", panel("edge"), MAINJS,
     "  el(\"dlgBrushHard\").addEventListener(\"click\", () => setBrushSoft(false));", "  el(\"dlgBrushHard\").addEventListener(\"click\", () => setBrushSoft(true));"),
    ("panel: the buttons do not show that the hard edge is on", panel("edge"), MAINJS,
     "classList.toggle(\"active\", !sessState.brushSoft);", "classList.toggle(\"active\", false);"),
    ("panel: the chosen edge is not written into the settings", panel("edge"), MAINJS,
     "    brushSoft: sessState.brushSoft,\n", ""),
    ("panel: a click on an edge button does not save the settings", panel("edge"), MAINJS,
     "  if (!byUser) return;\n  scheduleSaveSettings();\n  sayInWindow(sessState.brushSoft\n", "  if (!byUser) return;\n  sayInWindow(sessState.brushSoft\n"),
    ("panel: the edge kept in the settings is not put back", panel("edge"), MAINJS,
     "  if (typeof s.brushSoft === \"boolean\") setBrushSoft(s.brushSoft, false);\n", ""),
    ("panel: the trace of a soft stroke is as solid as that of a hard one", panel("edge"), MAINJS,
     "      dot.style.opacity = sessState.brushSoft ? \"0.2\" : \"0.65\";", "      dot.style.opacity = \"0.65\";"),
    # ---- the panel: one mode (4.7.0)
    ("panel: the one mode is the fast one", panel("one mode"), MAINJS,
     "const speedMode = \"quality\";", "const speedMode = \"fast\";"),
    ("panel: a preset that an older version saved with 'fast' asks for the fast fill", panel("one mode"), MAINJS,
     "  const params = normalizedPresetConfig(p.cfg);\n  params.speedMode = speedMode;\n",
     "  const params = normalizedPresetConfig(p.cfg);\n  params.speedMode = (p.cfg && p.cfg.speedMode) || speedMode;\n"),
]


def _label(groups) -> str:
    return groups if isinstance(groups, str) else groups[0]


def _run_panel_tests(plugin_dir, text):
    """(exit code, output) of the settings test and of the window scenarios named `text`, on the plugin in plugin_dir."""
    env = dict(os.environ)
    if plugin_dir:
        env["CV_PLUGIN_DIR"] = plugin_dir
    code, out = 0, ""
    for test, args in ((PANEL_TESTS[0], []), (PANEL_TESTS[1], [text])):
        try:
            r = subprocess.run(["node", os.path.join(ROOT, "tests", test)] + args, env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        except OSError as exc:
            return None, f"Node.js could not be started: {exc}"
        if "SKIPPED" in r.stdout:
            return None, r.stdout.strip()
        code, out = code or r.returncode, out + r.stdout
    return code, out


def main() -> int:
    words = [a for a in sys.argv[1:] if not a.startswith("-")]
    chosen = [d for d in DEFECTS if not words or any(wd in _label(d[1]) or wd in d[0] for wd in words)]
    if "--list" in sys.argv:
        for name, groups, rel, _, _ in chosen:
            print(f"{_label(groups):8s} {name}   [{rel}]")
        return 0
    for text in sorted({d[1][1] for d in chosen if not isinstance(d[1], str)}):
        # a defect of the panel counts as caught only if the same tests pass without it
        code, out = _run_panel_tests(None, text)
        if code is None:
            print(f"the panel tests cannot run here ({out[:200]}). Nothing was changed.")
            return 2
        if code != 0:
            print(f"the panel tests ('{text}') fail without any defect - nothing can be told. Nothing was changed.\n{out[-600:]}")
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
                    copy = os.path.join(tmp, "uxp-plugin")
                    shutil.copytree(os.path.join(ROOT, PLUGIN), copy)
                    with open(os.path.join(copy, os.path.relpath(rel, PLUGIN)), "w", encoding="utf-8", newline="") as f:
                        f.write(texts[rel].replace(old, new))
                    code, out = _run_panel_tests(copy, groups[1])
                finally:
                    shutil.rmtree(tmp, ignore_errors=True)
            caught = bool(code)
            why = ""
            if caught:
                lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
                at = next((k for k, ln in enumerate(lines) if ln.startswith(("[FAIL]", "FAIL "))), None)
                nxt = lines[at + 1] if at is not None and at + 1 < len(lines) else ""
                why = (nxt if nxt and not nxt.startswith(("[", "FAIL ", "plugin ")) else (lines[at] if at is not None else lines[-1]))[:150]
            else:
                missed.append(name)
            print(f"[{i:2d}/{len(chosen)}] {'caught    ' if caught else 'NOT CAUGHT'} {name}  ({time.perf_counter() - t1:.0f} s){'  <- ' + why if why else ''}", flush=True)
    finally:
        for rel in touched:  # whatever happened, the files are as they were
            with open(os.path.join(ROOT, rel), "w", encoding="utf-8", newline="") as f:
                f.write(texts[rel])
    print(f"\n{len(chosen) - len(missed)} of {len(chosen)} defects caught in {time.perf_counter() - t0:.0f} s"
          + ("" if not missed else "; NOT caught:\n  " + "\n  ".join(missed)))
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
