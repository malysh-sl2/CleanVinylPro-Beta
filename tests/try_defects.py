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
    # ---- the tone stages reach the person (4.9.0)
    ("edge: the corner stops at the margin of the protection again (the rim along the hem)", "edge", ENGINE,
     "                    tone_gate=tone_gate,\n                    level_seen=corner_hair,\n",
     "                    tone_gate=None,\n                    level_seen=corner_hair,\n"),
    ("edge: the stains fade out before the person as they did", "edge", ENGINE,
     "                                                         fg_gate=(tone_gate is None))\n",
     "                                                         fg_gate=True)\n"),
    ("edge: the photo is not asked where the edge of the person is", "edge", ENGINE,
     "            np.maximum(view, q8, out=view)\n        return gate\n",
     "        return gate\n"),
    ("edge: the photo is asked also where the network is sure of the person", "cyc", ENGINE,
     "            q8[t_rows[ya - a0:yb - a0] >= self.TONE_GATE_SURE] = 0\n",
     ""),
    ("edge: the stains are evened across the outline of the person", "edge", ENGINE,
     "                if tone_gate is not None:\n                    # the correction was computed without its fade towards the person: it ends at the outline\n",
     "                if False:\n                    # the correction was computed without its fade towards the person: it ends at the outline\n"),
    ("edge: the repair is blended into the frame under the protected band", "edge", ENGINE,
     "                    heal_gated = bool(tone_edge and custom_heal_mask is None)\n",
     "                    heal_gated = False\n"),
    ("edge: the former way cannot be asked for any more (toneEdge off is ignored)", "process", ENGINE,
     "            tone_edge = bool(params.get(\"toneEdge\", True))\n",
     "            tone_edge = True\n"),
    # ---- the thin line of a joint that is taken for the corner (4.9.0)
    ("line: the thin line along the corner is not looked for", "line", ENGINE,
     "            hair_line = bool(corner_hair and cyc_str > 0)  # the thin line along the corner is looked for\n",
     "            hair_line = False\n"),
    ("line: the thin line is found but not taken out", "line", ENGINE,
     "            hair_alpha = self._remove_corner_hairline(cleaned_f32, line[\"hair\"], who)\n",
     "            hair_alpha = None\n"),
    ("line: next to the person the backdrop is left lighter than its own slope", "line", ENGINE,
     "                    level_seen=corner_hair,\n                )\n",
     "                    level_seen=False,\n                )\n"),
    ("line: the seam tool works inside the zone of the corner's thin line", "line", ENGINE,
     "                                        skip_line = dict(skip_line, half=skip_line.get(\"zone\", skip_line[\"half\"]))\n",
     "                                        pass\n"),
    # ---- single hairs, the search (4.9.0)
    # Not in the list, because they change nothing that can be seen: HAIR_AWAY taken out alone (HAIR_OUTWARD turns
    # the same pieces away), and either half of the strength test of a piece (HAIR_MEAN, the peak) in these scenes.
    ("hair: a line that touches nobody is a hair", "hair", ENGINE,
     "                good = ((d_min <= attach) & (d_max >= stick_out) & (d_max < leaves) & ~at_border\n",
     "                good = ((d_max >= stick_out) & (d_max < leaves) & ~at_border\n"),
    ("hair: the fuzz of the outline is searched too", "hair", ENGINE,
     "        bad |= dist <= fringe                     # (the fuzz of the outline: after `calm`, which lies outside it)\n",
     ""),
    ("hair: a line that goes on beyond the searched zone is a hair", "hair", ENGINE,
     "                good = ((d_min <= attach) & (d_max >= stick_out) & (d_max < leaves) & ~at_border\n",
     "                good = ((d_min <= attach) & (d_max >= stick_out) & ~at_border\n"),
    ("hair: a line that reaches the border of the frame is a hair", "hair", ENGINE,
     "                good = ((d_min <= attach) & (d_max >= stick_out) & (d_max < leaves) & ~at_border\n",
     "                good = ((d_min <= attach) & (d_max >= stick_out) & (d_max < leaves)\n"),
    ("hair: the piece of a cable up to a knot of hairs is a hair", "hair", ENGINE,
     "                    if goes_on(py[of_g], px[of_g], d[of_g], lbl):\n",
     "                    if False:\n"),
    ("hair: the slider does not ask for longer hairs when it is low", "hair", ENGINE,
     "                    (self.HAIR_MIN_LEN[0] + (self.HAIR_MIN_LEN[1] - self.HAIR_MIN_LEN[0]) * level) * head_w)\n",
     "                    self.HAIR_MIN_LEN[1] * head_w)\n"),
    ("hair: a dark line may grow out of a lit face", "hair", ENGINE,
     "                        if inside > tone + 0.5 * depth:\n",
     "                        if False:\n"),
    ("hair: a hair that runs along the outline is taken", "hair", ENGINE,
     "                      & ((c_max - c_min) >= self.HAIR_AWAY * length) & (outw >= self.HAIR_OUTWARD * shown))\n",
     "                      & ((c_max - c_min) >= self.HAIR_AWAY * length))\n"),
    ("hair: the faint side lines of a strong hair count as much as the hair (it then 'runs along the outline')", "hair", ENGINE,
     "                show = np.maximum(cv_.astype(np.float32) - med, 0.0)\n",
     "                show = np.ones(cv_.shape, dtype=np.float32)\n"),
    ("hair: a wisp of crossing hairs is taken", "hair", ENGINE,
     "                      & (length >= piece_min) & (count <= self.HAIR_TUFT * length)\n",
     "                      & (length >= piece_min)\n"),
    ("hair: hairs are looked for along the whole figure", "hair", ENGINE,
     "        near_s[int(np.ceil((top_px + self.HAIR_ZONE_DOWN * head_px) * zs)):] = 0\n",
     ""),
    ("hair: the mark is as thin as the hair (it only fades)", "hair", ENGINE,
     "        grow = max(int(np.ceil(13.0 * ws)) | 1, int(round(0.024 * head_w)) | 1)\n",
     "        grow = 3\n"),
    ("hair: light hairs are not looked for", "hair", ENGINE,
     "        for op, gain in ((cv2.MORPH_BLACKHAT, 1.0), (cv2.MORPH_TOPHAT, self.HAIR_LIGHT)):\n",
     "        for op, gain in ((cv2.MORPH_BLACKHAT, 1.0),):\n"),
    # ---- single hairs, the repair and the window (4.9.0)
    ("hair: around a hair the repair is shown an average of the backdrop, not the photo", "hair", ENGINE,
     "                        solid_full = hair_solid\n",
     "                        solid_full = None\n"),
    ("hair: with a hair marked, every repair of the frame is shown the photo up to the person", "hair", ENGINE,
     "                                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_z, k_z))) > 0\n",
     "                                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_z, k_z))) >= 0\n"),
    ("hair: the slider moved in the window keeps the marks of its former position", "hair", ENGINE,
     "            k_hair = (k_maps, remove_stands, hair_eff)\n",
     "            k_hair = (k_maps, remove_stands)\n"),
    ("hair: the light refresh gets the hair marks at the size of the real frame", "hair", ENGINE,
     "        if found.get(\"near_mask\") is not None:\n            small[\"near_mask\"] = reduced(\"near\", found[\"near_mask\"], binary=True)\n",
     ""),
    ("hair: hair_px is in every answer of the server (the tool is off)", "http", ENGINE,
     "            if hair_eff > 0:\n                stats[\"hair_px\"] = hair_px",
     "            if True:\n                stats[\"hair_px\"] = hair_px"),
    ("hair: Apply does not notice that the hair slider was moved", "quick", ENGINE,
     "            float(np.clip(fl(\"strayHair\", 0), 0.0, 100.0)),\n",
     ""),
    # ---- the hair slider of the panel (4.9.0)
    ("panel: the hair slider is not sent to the server", panel("the hair slider"), MAINJS,
     "    strayHair: getSliderVal(\"gSlHair\"),\n", "    strayHair: 0,\n"),
    ("panel: moving the hair slider does not make the preview out of date", panel("the hair slider"), MAINJS,
     "    c.strayHair\n  ]);\n", "    0\n  ]);\n"),
    ("panel: at 0 the hair slider reads 0% instead of 'Вимк.'", panel("the hair slider"), MAINJS,
     "      badge.textContent = v > 0 ? v + \"%\" : \"Вимк.\";\n", "      badge.textContent = v + \"%\";\n"),
    ("panel: a preset saved before 4.9.0 switches the hair tool on", panel("the hair slider"), MAINJS,
     "    strayHair: clampSliderVal(\"gSlHair\", c.strayHair ?? 0),\n", "    strayHair: clampSliderVal(\"gSlHair\", c.strayHair ?? 50),\n"),
    ("panel: a preset does not move the hair slider", panel("the hair slider"), MAINJS,
     "  setSliderVal(\"gSlHair\", c.strayHair);\n", ""),
    ("panel: the hair slider is not one of the sliders (no drag, no badge)", panel("the hair slider"), MAINJS,
     "  \"gSlSpots\", \"gSlHair\", \"gSlScuffs\", \"gSlBlur\", \"gSlCyc\", \"gSlFeather\",\n",
     "  \"gSlSpots\", \"gSlScuffs\", \"gSlBlur\", \"gSlCyc\", \"gSlFeather\",\n"),
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
