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

# (name, check groups, file, exact text, replacement)
DEFECTS = [
    # ---- studio gear is told by its body (4.6.0)
    ("gear: a one-sided edge counts as gear again", "gear", ENGINE,
     "    GEAR_BODY_STEP = 0.20 ", "    GEAR_BODY_STEP = 0.01 "),
    ("gear: a faint thin line counts as gear again", "gear", ENGINE,
     "    GEAR_BODY_THIN = 0.16 ", "    GEAR_BODY_THIN = 0.02 "),
    ("gear: a stand and a cable are no gear any more", "gear", ENGINE,
     "    GEAR_BODY_THIN = 0.16 ", "    GEAR_BODY_THIN = 0.95 "),
    ("gear: an edge at the frame border is judged like any other", "gear", ENGINE,
     "            if x0 <= 2 or x0 + bw >= sw - 2 or y0 <= 2:\n                gear[i] = True\n                continue\n", ""),
    ("gear: the body rule is off unless asked for", "gear", ENGINE,
     "            grain_local = bool(params.get(\"grainLocal\", True))\n            # \"gearBody\": studio gear is told by its body; a shadow edge or a scratch is not gear (_edge_blobs_with_body)\n            gear_body = bool(params.get(\"gearBody\", True))",
     "            grain_local = bool(params.get(\"grainLocal\", True))\n            # \"gearBody\": studio gear is told by its body; a shadow edge or a scratch is not gear (_edge_blobs_with_body)\n            gear_body = bool(params.get(\"gearBody\", False))"),
    ("gear: the green preview keeps the old rule", "gear", ENGINE,
     "            seam_join = bool(params.get(\"seamJoin\", True))\n            gear_body = bool(params.get(\"gearBody\", True))",
     "            seam_join = bool(params.get(\"seamJoin\", True))\n            gear_body = bool(params.get(\"gearBody\", False))"),
    ("gear: an edge that is no gear reads as smoke", "gear", ENGINE,
     "bg_only = ((fg_s < 0.06) & (stand_mask < 0.4) & (edges_any < 0.4)).astype(np.uint8)",
     "bg_only = ((fg_s < 0.06) & (stand_mask < 0.4)).astype(np.uint8)"),
    # ---- the wall-floor corner on a black backdrop (4.6.0)
    ("corner: no upper line rule", "cyc", ENGINE,
     "            if bool(seen.any()):\n                j = int(np.flatnonzero(seen)[0])", "            if False:\n                j = int(np.flatnonzero(seen)[0])"),
    ("corner: the upper line must be five times as visible", "cyc", ENGINE,
     "    CORNER_UPPER_MIN_REL = 0.04 ", "    CORNER_UPPER_MIN_REL = 0.20 "),
    ("corner: any faint upper line wins, on a light backdrop too", "cyc", ENGINE,
     "    CORNER_UPPER_MIN_REL = 0.04 ", "    CORNER_UPPER_MIN_REL = 0.0 "),
    ("corner: the upper line must score more than the owner's corner does", "cyc", ENGINE,
     "    CORNER_UPPER_MIN_SCORE = 0.15 ", "    CORNER_UPPER_MIN_SCORE = 0.30 "),
    ("corner: the upper line must run along nine tenths of the width", "cyc", ENGINE,
     "(row_score >= CleanVinylEngine.CORNER_UPPER_MIN_SCORE) & (row_cov >= 0.5)", "(row_score >= CleanVinylEngine.CORNER_UPPER_MIN_SCORE) & (row_cov >= 0.9)"),
    # ---- what only looks like a floor joint (4.6.0)
    ("seam: the edge of a lit area passes for a joint", "seam", ENGINE,
     "    SEAM_LIGHT_EDGE = 8.0 ", "    SEAM_LIGHT_EDGE = 20.0 "),
    ("seam: a floor a little lighter on one side is no joint", "seam", ENGINE,
     "    SEAM_LIGHT_EDGE = 8.0 ", "    SEAM_LIGHT_EDGE = 4.0 "),
    ("seam: no piece has a line of its own", "seam", ENGINE,
     "    SEAM_OWN_LINE = 0.30 ", "    SEAM_OWN_LINE = 3.0 "),
    ("seam: pieces are joined whatever lies open between them", "seam", ENGINE,
     "is_line = in_view <= total_w and total_w > 0.24 * sw and thin_g / (wide_g + 0.05) >= 1.05",
     "is_line = total_w > 0.24 * sw and thin_g / (wide_g + 0.05) >= 1.05"),
    ("seam: what the search saw between the pieces counts as open floor", "seam", ENGINE,
     "        lined |= (cand_rows[r_hi, cols] - cand_rows[r_lo, cols]) > 0\n", ""),
    ("seam: a piece is looked at across a straight line", "seam", ENGINE,
     "        line = piece[\"path\"] if piece.get(\"path\") is not None else piece[\"slope\"] * xs + piece[\"offs\"]\n",
     "        line = piece[\"slope\"] * xs + piece[\"offs\"]\n"),
    ("seam: the course of a piece is its top row", "seam", ENGINE,
     "        rows = np.argmax(s, axis=0).astype(np.float32)\n", "        rows = np.zeros(bw, dtype=np.float32)\n"),
    ("seam: the slope of the light is not taken out of the step", "seam", ENGINE,
     "        return line_here, (b1 - a1) - per_row * float(n0 + n1 + 1)\n", "        return line_here, (b1 - a1)\n"),
    # ---- a dirty spot inside a cast shadow (4.6.0)
    ("shadow: the spot must be darker than the owner's scuff is", "shadow", ENGINE,
     "    SHADOW_SPOT_PEAK = 1.25\n", "    SHADOW_SPOT_PEAK = 1.5\n"),
    ("shadow: any patch above the threshold is a spot", "shadow", ENGINE,
     "    SHADOW_SPOT_PEAK = 1.25\n", "    SHADOW_SPOT_PEAK = 1.0\n"),
    ("shadow: the shadow around the spot must be more even than around the owner's scuff", "shadow", ENGINE,
     "    SHADOW_SPOT_RING_DEPTH = 0.75\n", "    SHADOW_SPOT_RING_DEPTH = 0.5\n"),
    ("shadow: an uneven shadow around the spot is fine", "shadow", ENGINE,
     "    SHADOW_SPOT_RING_DEPTH = 0.75\n", "    SHADOW_SPOT_RING_DEPTH = 1.2\n"),
    ("shadow: no limit in levels for the shadow around a deep spot", "shadow", ENGINE,
     "    SHADOW_SPOT_RING_FLAT_MAX = 12.0 ", "    SHADOW_SPOT_RING_FLAT_MAX = 40.0 "),
    ("shadow: a spot may touch the person or the border", "shadow", ENGINE,
     "                if (x1 - x0) < bw + 2 * m or (y1 - y0) < bh + 2 * m or not bool(bg_safe[box].all()):\n", "                if False:\n"),
    ("shadow: other finds around the spot do not matter", "shadow", ENGINE,
     "    SHADOW_SPOT_RING_BUSY = 0.08\n", "    SHADOW_SPOT_RING_BUSY = 1.0\n"),
    ("shadow: a big patch is a spot", "shadow", ENGINE,
     "    SHADOW_SPOT_MAX_DIM = 0.035 ", "    SHADOW_SPOT_MAX_DIM = 0.2 "),
    ("shadow: a long streak is a spot", "shadow", ENGINE,
     "    SHADOW_SPOT_ASPECT = 3.5\n", "    SHADOW_SPOT_ASPECT = 10.0\n"),
    ("shadow: only the dark middle of the spot is taken", "shadow", ENGINE,
     "                soft = ((dark_diff[box] > low_thr) | comp).astype(np.uint8)\n", "                soft = comp.astype(np.uint8)\n"),
    ("shadow: the rule is off unless asked for", "shadow", ENGINE,
     "            shadow_spots = bool(params.get(\"shadowSpots\", True))\n", "            shadow_spots = bool(params.get(\"shadowSpots\", False))\n"),
    ("shadow: the green preview does not know the rule", "shadow", ENGINE,
     "                    shadow_spots=bool(params.get(\"shadowSpots\", True)),\n", "                    shadow_spots=False,\n"),
    # ---- which backdrop is a dark key (4.6.0)
    ("scene: the owner's dark grey is not dark", "scene", ENGINE,
     "    SCENE_DARK_LUMA = 40.0\n", "    SCENE_DARK_LUMA = 26.0\n"),
    ("scene: the owner's grey is dark", "scene", ENGINE,
     "    SCENE_DARK_LUMA = 40.0\n", "    SCENE_DARK_LUMA = 60.0\n"),
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
