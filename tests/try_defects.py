#!/usr/bin/env python3
"""
Puts deliberate defects into the program, one at a time, and tells whether the self-checks notice.

    python tests/try_defects.py             # every defect of the list below
    python tests/try_defects.py seam cyc    # only the defects whose check group or name contains one of the words
    python tests/try_defects.py --list      # show the list, change nothing

A check that lets a defect through is a hole in the checks, not a proof that the code is right. For every defect
the script replaces one exact piece of text in a program file, runs the check groups the defect belongs to
(tests/run_checks.py <groups>), puts the file back and reports "caught" or "NOT CAUGHT".

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
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = "CleanVinylPro2/server/engine.py"
SERVER = "CleanVinylPro2/server/server.py"

# (name, check groups, file, exact text, replacement)
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
]


def main() -> int:
    words = [a for a in sys.argv[1:] if not a.startswith("-")]
    chosen = [d for d in DEFECTS if not words or any(wd in d[1] or wd in d[0] for wd in words)]
    if "--list" in sys.argv:
        for name, groups, rel, _, _ in chosen:
            print(f"{groups:8s} {name}   [{rel}]")
        return 0
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
    try:
        for i, (name, groups, rel, old, new) in enumerate(chosen, 1):
            path = os.path.join(ROOT, rel)
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(texts[rel].replace(old, new))
            try:
                t1 = time.perf_counter()
                r = subprocess.run([sys.executable, os.path.join(ROOT, "tests", "run_checks.py")] + groups.split(),
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
            finally:
                with open(path, "w", encoding="utf-8", newline="") as f:
                    f.write(texts[rel])
            caught = r.returncode != 0
            why = ""
            if caught:
                lines = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
                at = next((k for k, ln in enumerate(lines) if ln.startswith("[FAIL]")), None)
                why = (lines[at + 1] if at is not None and at + 1 < len(lines) and not lines[at + 1].startswith("[") else (lines[at] if at is not None else lines[-1]))[:150]
            else:
                missed.append(name)
            print(f"[{i:2d}/{len(chosen)}] {'caught    ' if caught else 'NOT CAUGHT'} {name}  ({time.perf_counter() - t1:.0f} s){'  <- ' + why if why else ''}", flush=True)
    finally:
        for rel, text in texts.items():  # whatever happened, the files are as they were
            with open(os.path.join(ROOT, rel), "w", encoding="utf-8", newline="") as f:
                f.write(text)
    print(f"\n{len(chosen) - len(missed)} of {len(chosen)} defects caught in {time.perf_counter() - t0:.0f} s"
          + ("" if not missed else "; NOT caught:\n  " + "\n  ".join(missed)))
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
