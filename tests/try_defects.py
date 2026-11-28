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


# (name, check groups - or panel(<text>, ...), file, exact text, replacement)
DEFECTS = [
    # ---- «Рівняти одяг» made anew (4.19.0). The owner, 2026-11-27: «має ріняти не доглажене зморшки і пятна як є а
    #      станом на зари ужаш усе плаття точками заливає і колір міняє». Each defect takes one of the rules away.
    ("layer: opened where the cloth happened to change, as up to 4.18.0 - it lies over the dress in spots", "dress", ENGINE,
     "        alpha_full[fy0:fy1, fx0:fx1] = cv2.resize(cover, size, interpolation=cv2.INTER_LINEAR)\n",
     "        alpha_full[fy0:fy1, fx0:fx1] = cv2.resize(cover * np.clip(np.abs(d).max(axis=2) / 0.006, 0.0, 1.0), size, interpolation=cv2.INTER_LINEAR)\n"),
    ("fold: nothing is taken for a fold - what is deep is ironed like a crease", "dress", ENGINE,
     "                g_lum = (1.0 - deep) * (1.0 - keep)\n", "                g_lum = 1.0 - keep\n"),
    ("fold: a fold is weakened at every width instead of being left alone (the gate keeps 60% of it out)", "dress", ENGINE,
     "            deep = deep * deep * (3.0 - 2.0 * deep)\n            del depth, tinted\n",
     "            deep = 0.6 * deep * deep * (3.0 - 2.0 * deep)\n            del depth, tinted\n"),
    ("size: the widths are a share of the frame, whatever the size of the garment", "dress", ENGINE,
     "        half_all = cls._dress_scale(dress_mask_small) * ref\n", "        half_all = 0.11 * ref\n"),
    ("colour: one gain for red, green and blue again - a tinted stain keeps its tint", "dress", ENGINE,
     "                pull = r_lum[..., None] * g_lum[..., None] + r_col * g_col[..., None]\n",
     "                pull = r_lum[..., None] * g_lum[..., None] + 0.0 * r_col\n"),
    ("garments: two garments of different colour are ironed as one - a plane is laid across their border", "dress", ENGINE,
     "        for m_src in cls._cloth_colours(low, m_all):\n", "        for m_src in [m_all]:\n"),
    ("print: a hue on little cloth is a garment of its own - an emblem is ironed within itself", "dress", ENGINE,
     "        is_garment = share >= 0.04\n", "        is_garment = share >= 0.0\n"),
    ("mask: skin is what the colour rule finds and nothing more - the ruddy half of a hand is cloth", "dress", ENGINE,
     "                skin_all = (np.isin(lbl_g, touching[touching > 0]) & (cand | (skin > 0))).astype(np.uint8)\n",
     "                skin_all = skin\n"),
    ("mask: scraps of cloth are kept - each is a dot of the layer", "dress", ENGINE,
     "            min_area = (0.02 * max(sw, sh)) ** 2\n", "            min_area = 0.0\n"),
    ("weave: the low layer is the picture itself - grain and weave are ironed with the creases", "dress", ENGINE,
     "        sig_fine = max(0.8, 0.0009 * ref)            # everything finer is weave and grain: never touched\n",
     "        sig_fine = 0.3\n"),
    ("form: the surface is a plane fitted once - it does not follow the roundness of the body", "dress", ENGINE,
     "            return 2.0 * s1 - fit(s1)\n", "            return s1\n"),
    ("apply: Apply irons at half the strength the window was given", "quick", ENGINE,
     "                    cleaned_f32, dress_alpha_full = self._smooth_dress_fabric(cleaned_f32, ds, float(dress_strength), fast_mode=fast_mode)\n",
     "                    cleaned_f32, dress_alpha_full = self._smooth_dress_fabric(cleaned_f32, ds, 0.5 * float(dress_strength), fast_mode=fast_mode)\n"),
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
