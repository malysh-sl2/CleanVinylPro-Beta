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
    # ---- at the border the whole of a thing goes (4.15.0: the owner's 0Q5A3610 - the lit side of a softbox shone
    #      into the wall that replaced its body, the far edge of its black base stayed as a dark line)
    ("border: nothing goes with a thing at the border (the rule 'to the border' is off)", "border", ENGINE,
     "        wide = min(sw, cap + rim)\n        out = take.copy()\n",
     "        wide = min(sw, cap + rim)\n        return take\n        out = take.copy()\n"),
    ("border: a pole that stands free takes the wall behind it too", "border", ENGINE,
     "            thing = np.isin(lbl, at_border)\n",
     "            thing = lbl > 0\n"),
    ("border: a thing takes everything up to itself however far into the frame it reaches (no GEAR_HULL_MAX)", "border", ENGINE,
     "        cap = max(4, int(round(self.GEAR_HULL_MAX * sw)))\n        rim = max(1, int(round(self.GEAR_HULL_RIM * sw)))\n",
     "        cap = sw\n        rim = max(1, int(round(self.GEAR_HULL_RIM * sw)))\n"),
    ("border: no rim beyond the far side of a thing", "border", ENGINE,
     "                for _ in range(rim):      # one pixel further at a time, and not into the gear\n",
     "                for _ in range(0):        # one pixel further at a time, and not into the gear\n"),
    ("border: the rim eats into gear that stays", "border", ENGINE,
     "                    step[stays & (hull == 0)] = 0\n",
     "                    pass\n"),
    ("border: rows left out between two rows of a thing are not closed", "border", ENGINE,
     "            hull = cv2.morphologyEx(hull, cv2.MORPH_CLOSE, np.ones((gap, 1), np.uint8))\n",
     "            pass\n"),
    ("border: two things at the border are joined however far apart they are", "border", ENGINE,
     "        gap = max(3, int(round(self.GEAR_HULL_GAP * sh))) | 1\n",
     "        gap = max(3, int(round(10.0 * self.GEAR_HULL_GAP * sh))) | 1\n"),
    ("border: the right border is not looked at", "border", ENGINE,
     "        for mirrored in (False, True):\n",
     "        for mirrored in (False,):\n"),
    # ---- black on a dark wall
    ("border: black on a dark wall is not black (the far edge of a black base stays as a dark line)", "border", ENGINE,
     "                  | ((L < self.GEAR_BLACK_DEEP) & (row_mid_l > self.GEAR_BLACK_WALL))    # (on a dark wall)\n",
     "                  | ((L < -1.0) & (row_mid_l > self.GEAR_BLACK_WALL))    # (on a dark wall)\n"),
    ("border: black outright is not black where the middle of the row is dark too", "border", ENGINE,
     "                  | (L < self.GEAR_BLACK_PURE))\n",
     "                  | (L < -1.0))\n"),
    ("border: a dark thing on a darker wall counts as black (GEAR_BLACK_WALL is not asked)", "border", ENGINE,
     "                  | ((L < self.GEAR_BLACK_DEEP) & (row_mid_l > self.GEAR_BLACK_WALL))    # (on a dark wall)\n",
     "                  | ((L < self.GEAR_BLACK_DEEP) & (row_mid_l > -1.0))    # (on a dark wall)\n"),
    ("border: along the border a black thing is followed no further than anywhere else", "border bigfill", ENGINE,
     "        near[:, :2 * reach] = True\n        near[:, -2 * reach:] = True\n",
     "        pass\n"),
    # ---- the black end of a thin thing (0Q5A3411: the foot of a stand stayed as a black dot on a dark floor when its
    #      leg went)
    ("border: the black end of a thin thing at the border is not followed (the foot of a stand stays on a dark floor)", "border", ENGINE,
     "            taken = self._black_end_at_border(stand_remove > 0.5, L, fg_border_excl)\n",
     "            taken = stand_remove > 0.5\n"),
    ("border: the black end of a thing is followed anywhere in the frame, not only near the border", "border", ENGINE,
     "        zone[:, :cap] = True\n        zone[:, sw - cap:] = True\n        held = take & zone\n",
     "        zone[:, :] = True\n        held = take & zone\n"),
    ("border: the black end of a thing at the right border is not followed", "border", ENGINE,
     "        zone[:, :cap] = True\n        zone[:, sw - cap:] = True\n        held = take & zone\n",
     "        zone[:, :cap] = True\n        held = take & zone\n"),
    ("border: the end of a taken thing is followed where it is merely dark (GEAR_BLACK_PURE is not asked)", "border", ENGINE,
     "        black = (L < self.GEAR_BLACK_PURE) & zone & (~person) & (~take)\n",
     "        black = (L < 6.0) & zone & (~person) & (~take)\n"),
    ("border: the black of the person joins what lies beyond it to a taken thing", "border", ENGINE,
     "        black = (L < self.GEAR_BLACK_PURE) & zone & (~person) & (~take)\n",
     "        black = (L < self.GEAR_BLACK_PURE) & zone & (~take)\n"),
    ("border: a black backdrop counts as the end of a taken thing (no limit of the area)", "border", ENGINE,
     "        of_thing &= st[:, cv2.CC_STAT_AREA] <= self.GEAR_BLACK_MAX * L.size      # (a black backdrop is no thing)\n",
     "        pass\n"),
    ("border: the black end of a thing is taken without a rim", "border", ENGINE,
     "        more = cv2.dilate(more.view(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))) > 0\n        return take | (more & ~person)\n",
     "        return take | (more & ~person)\n"),
    # ---- light gear that hangs together with a taken thing (0Q5A3413: the end of a lit strip softbox stayed in the
    #      air when the black flag it crosses went)
    ("border: light gear beside a taken thing is left as it was - eaten in part (the rule is off)", "border", ENGINE,
     "        if self.GEAR_LIGHT_OVER <= 0.0:\n            return out\n",
     "        if True:\n            return out\n"),
    ("border: light gear goes with a thing it does not touch", "border", ENGINE,
     "            near = cv2.dilate(np.isin(lbl_t, at).view(np.uint8), k_rim) > 0\n",
     "            near = cv2.dilate(np.isin(lbl_t, at).view(np.uint8), np.ones((41, 41), np.uint8)) > 0\n"),
    ("border: gear with nothing light in it goes too", "border", ENGINE,
     "                if int(lit.sum()) < self.GEAR_LIGHT_MIN * sh * sw:\n",
     "                if False:\n"),
    ("border: a speck of light makes a dark thing light gear (GEAR_LIGHT_MIN is not asked)", "border", ENGINE,
     "                if int(lit.sum()) < self.GEAR_LIGHT_MIN * sh * sw:\n",
     "                if int(lit.sum()) < 1:\n"),
    ("border: one level over the backdrop is light enough (GEAR_LIGHT_OVER is not asked)", "border", ENGINE,
     "                lit = (body > 0) & (l_here > float(np.median(l_here[ring])) + self.GEAR_LIGHT_OVER)\n",
     "                lit = (body > 0) & (l_here > float(np.median(l_here[ring])) + 1.0)\n"),
    ("border: light gear that reaches into the frame goes too", "border", ENGINE,
     "                if (x0 < sw - reach) if right else (x0 + bw > reach):\n",
     "                if False:\n"),
    ("border: gear that may not be taken - what runs along the person - goes too", "border", ENGINE,
     "                if i <= 0 or gear_lut[i] <= 0:\n",
     "                if i <= 0:\n"),
    ("border: light gear at the right border is not looked at", "border", ENGINE,
     "        for right in (False, True):\n",
     "        for right in (False,):\n"),
    ("border: only the edges of a light thing go, not what they enclose", "border", ENGINE,
     "                cv2.drawContours(body, outline, -1, 1, thickness=cv2.FILLED)\n",
     "                pass\n"),
    ("border: the black end of a light thing stays", "border", ENGINE,
     "            grown = self._whole_black_thing(L, row_mid_l, out.view(np.uint8), fg_s, core_s, person)\n",
     "            grown = out.view(np.uint8)\n"),
    ("border: a light thing is taken without a rim", "border", ENGINE,
     "            out = (cv2.dilate(grown, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))) > 0) & ~person\n",
     "            out = (grown > 0) & ~person\n"),
    # ---- the floor beyond the sheet ("ще паркет треба приберати")
    ("border: the floor beyond the sheet is not looked for (the parquet stays)", "border", ENGINE,
     "            floor = self._foreign_floor(L, A, B, fg_s, fg_border_excl)\n",
     "            floor = np.zeros(L.shape, dtype=bool)\n"),
    ("border: any colour far from the backdrop's counts as wood (the hue is not asked)", "border", ENGINE,
     "        wood = (far > self.GEAR_FLOOR_CHROMA) & (hue > lo) & (hue < hi) & (L > 20.0) & (fg_s < 0.2) & (~fg_border_excl)\n",
     "        wood = (far > self.GEAR_FLOOR_CHROMA) & (L > 20.0) & (fg_s < 0.2) & (~fg_border_excl)\n"),
    ("border: a faintly warm patch counts as wood (half of GEAR_FLOOR_CHROMA is enough)", "border", ENGINE,
     "        wood = (far > self.GEAR_FLOOR_CHROMA) & (hue > lo) & (hue < hi) & (L > 20.0) & (fg_s < 0.2) & (~fg_border_excl)\n",
     "        wood = (far > 0.5 * self.GEAR_FLOOR_CHROMA) & (hue > lo) & (hue < hi) & (L > 20.0) & (fg_s < 0.2) & (~fg_border_excl)\n"),
    ("border: wood need not differ from the backdrop (the parquet runs together with the warm floor beside it and stays)", "border", ENGINE,
     "        wood = (far > self.GEAR_FLOOR_CHROMA) & (hue > lo) & (hue < hi) & (L > 20.0) & (fg_s < 0.2) & (~fg_border_excl)\n",
     "        wood = (far > 1.0) & (hue > lo) & (hue < hi) & (L > 20.0) & (fg_s < 0.2) & (~fg_border_excl)\n"),
    ("border: a pool of warm light counts as floor (no sharp edge is asked)", "border", ENGINE,
     "            if int(outline.sum()) < 8 or float(np.median(step[ya:yb, xa:xb][outline])) < self.GEAR_FLOOR_EDGE:\n",
     "            if int(outline.sum()) < 8:\n"),
    ("border: wood anywhere in the frame counts, not only at its border", "border", ENGINE,
     "            if not (x0 <= 1 or y0 <= 1 or x0 + bw >= sw - 1 or y0 + bh >= sh - 1):\n",
     "            if False:\n"),
    ("border: wood that touches the person counts (a bench, a stool)", "border", ENGINE,
     "            if bool(person[ya:yb, xa:xb][around].any()):\n",
     "            if False:\n"),
    ("border: a wooden backdrop counts as the floor beyond the sheet (no limit of the area)", "border", ENGINE,
     "            if not (self.GEAR_FLOOR_MIN * sh * sw <= area <= self.GEAR_FLOOR_MAX * sh * sw):\n",
     "            if not (self.GEAR_FLOOR_MIN * sh * sw <= area):\n"),
    ("border: a speck of wood colour at the border counts as floor (no GEAR_FLOOR_MIN)", "border", ENGINE,
     "            if not (self.GEAR_FLOOR_MIN * sh * sw <= area <= self.GEAR_FLOOR_MAX * sh * sw):\n",
     "            if not (area <= self.GEAR_FLOOR_MAX * sh * sw):\n"),
    ("border: what has the colour of wood in deep shade counts as floor", "border", ENGINE,
     "        wood = (far > self.GEAR_FLOOR_CHROMA) & (hue > lo) & (hue < hi) & (L > 20.0) & (fg_s < 0.2) & (~fg_border_excl)\n",
     "        wood = (far > self.GEAR_FLOOR_CHROMA) & (hue > lo) & (hue < hi) & (fg_s < 0.2) & (~fg_border_excl)\n"),
    ("border: the edge of the parquet stays as a warm line (no rim)", "border", ENGINE,
     "                k_f = 2 * max(1, int(round(self.GEAR_FLOOR_RIM * sw))) + 1\n",
     "                k_f = 1\n"),
    # ---- the wall is continued from backdrop only
    ("border: the fill for large places is not told which gear stays", "border", ENGINE,
     "                                            gear_s=(eff_stand_protect if gear_body else None)) if big_fill else None)\n",
     "                                            gear_s=None) if big_fill else None)\n"),
    ("border: gear that stays counts as wall to continue from", "border", ENGINE,
     "            wall &= cv2.resize(gear_s, (sw, sh), interpolation=cv2.INTER_LINEAR) < 75\n",
     "            pass\n"),
    # ---- what lies along the person is the person's (the dashes under the hem of 0Q5A3610)
    ("border: the cleaning repaints what lies along the person", "border", ENGINE,
     "                                heal_mask, gone_j, gone_s = self._found_beside_person(seam_mask, spot_mask, eff_fg_for_spots,\n"
     "                                                                                      img_rgb_u8)\n"
     "                                edge_gone = (gone_j, gone_s)\n",
     "                                heal_mask = np.maximum(seam_mask, spot_mask)\n"),
    ("border: the green preview shows what lies along the person as if it were cleaned", "border", ENGINE,
     "                    action_bin = self._found_beside_person(seam_mask, spot_mask, eff_fg_for_spots, img_rgb_u8)[0]   # as process() does\n",
     "                    action_bin = np.maximum(seam_mask, spot_mask)   # as process() does\n"),
    ("border: the second pass of the cleaning finds the strip along the person again", "border", ENGINE,
     "                    if gone_2 is not None:\n                        spot2_mask[gone_2] = 0\n",
     "                    if False:\n                        spot2_mask[gone_2] = 0\n"),
    ("border: a piece that only starts at the person counts as lying along it (the share is not asked)", "border", ENGINE,
     "        gone = (nearest <= 0.5 * (reach + rim)) & (along >= self.PERSON_EDGE_SHARE * area)\n",
     "        gone = (nearest <= 0.5 * (reach + rim))\n"),
    ("border: a piece a little way off the person counts as lying along it (the nearest point is not asked)", "border", ENGINE,
     "        gone = (nearest <= 0.5 * (reach + rim)) & (along >= self.PERSON_EDGE_SHARE * area)\n",
     "        gone = (along >= self.PERSON_EDGE_SHARE * area)\n"),
    ("border: the rim the searches put around what they find is not allowed for", "border", ENGINE,
     "        rim = float(self.PERSON_EDGE_RIM)\n",
     "        rim = 0.0\n"),
    ("border: 'along the person' reaches ten times as far", "border", ENGINE,
     "        reach = max(3.0, self.PERSON_EDGE_REACH * max(h, w))\n",
     "        reach = max(3.0, 10.0 * self.PERSON_EDGE_REACH * max(h, w))\n"),
    ("border: a short piece of the joint next to the person is dropped too (the joint between the legs stays)", "border", ENGINE,
     "            gone &= np.maximum(st[:, cv2.CC_STAT_WIDTH], st[:, cv2.CC_STAT_HEIGHT]) >= self.PERSON_EDGE_JOINT * reach\n",
     "            pass\n"),
    ("border: a long line of the joint search along the person is repainted", "border", ENGINE,
     "        gone_j = self._along_person(seam_mask, fg_u8, long_only=True)\n",
     "        gone_j = None\n"),
    ("border: a strip of the dust search along the person is repainted (only the joints are looked at)", "border", ENGINE,
     "        gone_s = self._along_person(spot_mask, fg_u8, rgb=rgb)\n",
     "        gone_s = None\n"),
    ("border: what was dropped along the person is still counted as found", "border", ENGINE,
     "                        seam_px, spot_px = int(seam_mask.sum()) - edge_gone[0], int(spot_mask.sum()) - edge_gone[1]\n",
     "                        seam_px, spot_px = int(seam_mask.sum()), int(spot_mask.sum())\n"),
    ("border: the mask of the dust search is changed in place (the stage cache gets it without the strip)", "border", ENGINE,
     "        keep_s = spot_mask if gone_s is None else np.where(gone_s, np.uint8(0), spot_mask)\n",
     "        keep_s = spot_mask\n        if gone_s is not None:\n            spot_mask[gone_s] = 0\n"),
    # ---- ...but only when the THING in the piece is joined to the person: dust beside a shoe is dust (the frame is asked)
    ("border: the cleaning does not ask the frame - a speck of dust right beside a leg stays in the photo", "border", ENGINE,
     "                                heal_mask, gone_j, gone_s = self._found_beside_person(seam_mask, spot_mask, eff_fg_for_spots,\n"
     "                                                                                      img_rgb_u8)\n",
     "                                heal_mask, gone_j, gone_s = self._found_beside_person(seam_mask, spot_mask, eff_fg_for_spots)\n"),
    ("border: the green preview does not ask the frame - the speck beside the leg is not shown, though it is cleaned", "border", ENGINE,
     "                    action_bin = self._found_beside_person(seam_mask, spot_mask, eff_fg_for_spots, img_rgb_u8)[0]   # as process() does\n",
     "                    action_bin = self._found_beside_person(seam_mask, spot_mask, eff_fg_for_spots)[0]   # as process() does\n"),
    ("border: the frame is never asked - the mask alone decides what is the person's", "border", ENGINE,
     "        if rgb is not None and self.PERSON_EDGE_TOUCH >= 0.0:\n",
     "        if False:\n"),
    ("border: once the frame is asked nothing is the person's (the rim of a skirt is repainted as dust)", "border", ENGINE,
     "        return bool(at_band[parts[thing & piece]].any())\n",
     "        return False\n"),
    ("border: anything that stands out at the band counts, joined to the thing or not (a speck beside the end of a lace stays)", "border", ENGINE,
     "        return bool(at_band[parts[thing & piece]].any())\n",
     "        return bool(at_band.any())\n"),
    ("border: 'right beside the band' reaches four pixels (a speck 3 px from a leg counts as joined to it)", "border", ENGINE,
     "        at_band[parts[thing & (far <= self.PERSON_EDGE_GUARD)]] = True\n",
     "        at_band[parts[thing & (far <= self.PERSON_EDGE_GUARD + 3.0)]] = True\n"),
    ("border: the faintest shade counts as the thing (a speck in the shade of a leg is joined to it by that shade)", "border", ENGINE,
     "        thing = np.ascontiguousarray((off >= max(self.PERSON_EDGE_SEEN, self.PERSON_EDGE_TOUCH * peak)) & (far > 0.0))\n",
     "        thing = np.ascontiguousarray((off >= self.PERSON_EDGE_SEEN) & (far > 0.0))\n"),
    ("border: a mark with nothing to see in it, right beside the person, is repaired", "border", ENGINE,
     "        if peak < self.PERSON_EDGE_SEEN:\n            return True                                  # nothing in it stands out\n",
     "        if peak < self.PERSON_EDGE_SEEN:\n            return False                                 # nothing in it stands out\n"),
    # (Not in the list, because the checks cannot tell:
    #   - the second pass of the cleaning is not given the frame: it only sees what the first pass left;
    #   - "no backdrop beside the piece to compare with" (fewer than 12 pixels of it): no drawn frame has such a piece;
    #   - the rim of the rule 'to the border' when no gear is named (`gear is None`): the program always names it;
    #   - "the distance is measured from the band, not from the nearest point of the piece": on the drawn frames
    #     both give the same pieces - the difference is a guard of one to three pixels the searches keep.)
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
