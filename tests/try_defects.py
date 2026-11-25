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
    # ---- what is too large for the network gets the wall beside it (4.14.0: the owner's 0Q5A3534 and 0Q5A2507, a
    #      column 11..22 levels too light in place of a black curtain)
    ("bigfill: nothing is too large (the network is asked for the curtain as before)", "bigfill", ENGINE,
     "        ids = [i for i in range(1, n) if 2.0 * float(depth[i]) >= need]\n",
     "        ids = []\n"),
    ("bigfill: everything is too large, the thin strip and the stand too", "bigfill", ENGINE,
     "        ids = [i for i in range(1, n) if 2.0 * float(depth[i]) >= need]\n",
     "        ids = list(range(1, n))\n"),
    ("bigfill: a thing at the border counts as deep as it is wide, not twice that", "bigfill", ENGINE,
     "        ids = [i for i in range(1, n) if 2.0 * float(depth[i]) >= need]\n",
     "        ids = [i for i in range(1, n) if float(depth[i]) >= need]\n"),
    ("bigfill: the reduced copy of the window decides by its own pixels", "bigfill", ENGINE,
     "        need = max(3.0, self.BIG_FILL_THICK * self.BIG_FILL_TILE * float(render_scale) * sc)\n",
     "        need = max(3.0, self.BIG_FILL_THICK * self.BIG_FILL_TILE * sc)\n"),
    ("bigfill: the tone is not carried along the rows (a shadow that runs into the curtain ends at its edge)", "bigfill", ENGINE,
     "            along_rows = at_lr and (not at_tb or bw <= bh)\n",
     "            along_rows = False\n"),
    ("bigfill: the network is still asked for the place (its answer is painted over afterwards)", "bigfill", ENGINE,
     "                        heal_net[big[\"full\"] > 0] = 0\n",
     "                        pass\n"),
    ("bigfill: the new wall gets the grain of what stood there - next to none for a black curtain", "bigfill", ENGINE,
     "                                        if bool(n_big.any()):\n",
     "                                        if False:\n"),
    ("bigfill: the new wall gets its grain whatever the grain slider says", "bigfill", ENGINE,
     "                                            as_wall = wall_g * (self.BIG_FILL_GRAIN * g_ratio / (self.BIG_FILL_GRAIN_HP * noise_std))\n",
     "                                            as_wall = wall_g * (self.BIG_FILL_GRAIN / (self.BIG_FILL_GRAIN_HP * noise_std))\n"),
    ("bigfill: the answer does not say what was too large", "bigfill", ENGINE,
     "                stats[\"big_fill\"] = {\"pieces\": int(big_info[0]), \"share\": round(float(big_info[1]), 4)}\n",
     "                pass\n"),
    ("bigfill: an answer taken from the stage cache forgets what was too large", "bigfill", ENGINE,
     "                    big_info = hit_heal.get(\"big_info\")\n",
     "                    big_info = None\n"),
    ("bigfill: the stage cache does not know the switch", "bigfill", ENGINE,
     "            k_heal = (k_detect, fast_mode, grain_keep, tone_edge, big_fill)\n",
     "            k_heal = (k_detect, fast_mode, grain_keep, tone_edge)\n"),
    # ---- a black thing at the border is marked whole
    ("bigfill: the rest of a black thing is not looked for (the wide top of the curtain stays)", "bigfill", ENGINE,
     "        if gear_body and bool(bd_keep.any()):\n            bd_keep = self._whole_black_thing(",
     "        if False:\n            bd_keep = self._whole_black_thing("),
    ("bigfill: the whole black thing takes a person in black as well", "bigfill", ENGINE,
     "                 & (fg_s < 0.2) & (core_s < 0.15) & (~fg_border_excl))\n",
     "                 & (~fg_border_excl))\n"),
    ("bigfill: the whole black thing is followed as far as it goes (no reach)", "bigfill", ENGINE,
     "        black = ((L < self.GEAR_BLACK_L) & ((row_mid_l - L) > self.GEAR_BLACK_UNDER) & near\n",
     "        black = ((L < self.GEAR_BLACK_L) & ((row_mid_l - L) > self.GEAR_BLACK_UNDER)\n"),
    ("bigfill: a black backdrop counts as a thing (no limit of the area)", "bigfill", ENGINE,
     "        held &= st[:, cv2.CC_STAT_AREA] <= self.GEAR_BLACK_MAX * L.size\n",
     ""),
    # ---- "Глибина": the wider cove of the corner tool (the owner: "the wall looks a metre away")
    ("depth: the value is not read (the cove stays as it was)", "depth", ENGINE,
     "            cyc_depth = float(np.clip(float(params.get(\"cycDepth\", 0)), 0.0, 100.0)) if cyc_str > 0 else 0.0\n",
     "            cyc_depth = 0.0\n"),
    ("depth: below the line the wider zone is used for everything (the lit floor loses light)", "depth", ENGINE,
     "            W_s = np.where(yy_s > row_s, z_dark + (z_lift - z_dark) * lifts, zone(d_rel))[..., None]\n",
     "            W_s = np.where(yy_s > row_s, z_lift, zone(d_rel))[..., None]\n"),
    ("depth: below the line nothing is widened (the dark belt of far floor stays)", "depth", ENGINE,
     "            W_s = np.where(yy_s > row_s, z_dark + (z_lift - z_dark) * lifts, zone(d_rel))[..., None]\n",
     "            W_s = np.where(yy_s > row_s, z_dark, zone(d_rel))[..., None]\n"),
    ("depth: above the line nothing is widened (the wall does not take the tone of the floor)", "depth", ENGINE,
     "            W_s = np.where(yy_s > row_s, z_dark + (z_lift - z_dark) * lifts, zone(d_rel))[..., None]\n",
     "            W_s = np.where(yy_s > row_s, z_dark + (z_lift - z_dark) * lifts, z_dark)[..., None]\n"),
    ("depth: the stages after the corner are taken ready from the cache of another depth", "depth", ENGINE,
     "            k_cyc = (k_heal, cyc_str, cyc_depth)\n",
     "            k_cyc = (k_heal, cyc_str)\n"),
    ("depth: without the corner tool it still counts as a new setting", "depth", ENGINE,
     "            (float(np.clip(fl(\"cycDepth\", 0), 0.0, 100.0)) if fl(\"cycCurve\", 0) > 0 else 0.0), fl(\"feather\", 60),\n",
     "            float(np.clip(fl(\"cycDepth\", 0), 0.0, 100.0)), fl(\"feather\", 60),\n"),
    ("depth: the signature of the settings does not know it", "depth", ENGINE,
     "            (float(np.clip(fl(\"cycDepth\", 0), 0.0, 100.0)) if fl(\"cycCurve\", 0) > 0 else 0.0), fl(\"feather\", 60),\n",
     "            fl(\"feather\", 60),\n"),
    # ---- the panel: the keys of the window
    ("panel: the photo never takes the keyboard", panel("the photo holds", "the second window"), MAINJS,
     "  if (evenWhileTyping !== true && typingInWindow()) return;\n  try { vp.focus(); } catch (_) {}\n",
     "  if (evenWhileTyping !== true && typingInWindow()) return;\n"),
    ("panel: the photo cannot hold the keyboard (no tabindex)", panel("the photo holds", "the second window"), PLUGIN + "/index.html",
     "        <div class=\"r4m-viewport\" id=\"dlgViewport\" tabindex=\"0\">\n",
     "        <div class=\"r4m-viewport\" id=\"dlgViewport\">\n"),
    ("panel: the photo gets the keyboard from the mouse only - not when the window opens, not when the scan is over", panel("the second window"), MAINJS,
     "function keepKeysInWindow(evenWhileTyping) {\n  if (!sessState.open) return;\n",
     "function keepKeysInWindow(evenWhileTyping) {\n  if (!sessState.open || !sessState.keysAskedMs) return;\n"),
    ("panel: a host that gives the keyboard to no plain element is left without keys", panel("a host that gives"), MAINJS,
     "    try { if (btn && btn !== a && typeof btn.focus === \"function\") btn.focus(); } catch (_) {}\n",
     ""),
    ("panel: the mouse over the photo does not give it the keyboard back", panel("the photo holds", "a host that gives"), MAINJS,
     "      sessState.keysAskedMs = Date.now();\n      keepKeysInWindow();\n",
     "      sessState.keysAskedMs = Date.now();\n"),
    ("panel: a press on the photo leaves the keyboard in the text field", panel("the photo holds"), MAINJS,
     "    keepKeysInWindow(true);  // (the press itself gives the photo nothing: its default is cancelled below)\n",
     "    keepKeysInWindow();\n"),
    ("panel: a name being typed loses the keyboard to the photo under the mouse", panel("the photo holds"), MAINJS,
     "  if (evenWhileTyping !== true && typingInWindow()) return;\n",
     ""),
    ("panel: the field of a closed form still counts as typing", panel("the photo holds"), MAINJS,
     "  return ![\"dlgAddPresetForm\", \"dlgPresetsPopover\"].some((id) => {\n",
     "  return ![].some((id) => {\n"),
    ("panel: one press of a key counts at every place that hears it", panel("the photo holds", "the second window", "a host that gives"), MAINJS,
     "    if (!sessState.open || e === lastKeyDown) return;\n",
     "    if (!sessState.open) return;\n"),
    # ---- the panel: "Глибина"
    ("panel: depth is not sent to the server", panel("'Глибина'"), MAINJS,
     "    cycDepth: getSliderVal(\"gSlDepth\"),\n",
     ""),
    ("panel: a preset does not put its depth on the slider", panel("'Глибина'"), MAINJS,
     "  setSliderVal(\"gSlDepth\", c.cycDepth);\n",
     ""),
    ("panel: the value of a preset is lost on the way to the controls", panel("'Глибина'"), MAINJS,
     "    cycDepth: clampSliderVal(\"gSlDepth\", c.cycDepth ?? 0),\n",
     "    cycDepth: 0,\n"),
    ("panel: depth can be moved without the corner tool", panel("'Глибина'"), MAINJS,
     "  setSliderDisabled(\"gSlDepth\", getSliderVal(\"gSlCyc\") <= 0);\n",
     ""),
    ("panel: the row of depth does not say that it is nothing without the corner tool", panel("'Глибина'"), MAINJS,
     "      badge.textContent = getSliderVal(\"gSlCyc\") > 0 ? (v > 0 ? v + \"%\" : \"Вимк.\") : \"—\";\n",
     "      badge.textContent = v > 0 ? v + \"%\" : \"Вимк.\";\n"),
    ("panel: a depth without the corner tool asks for a new picture", panel("'Глибина'"), MAINJS,
     "c.cycCurve > 0 ? c.cycDepth : 0, c.feather,",
     "c.cycDepth, c.feather,"),
    ("panel: a new depth is no new setting for the picture", panel("'Глибина'"), MAINJS,
     "c.cycCurve > 0 ? c.cycDepth : 0, c.feather,",
     "0, c.feather,"),
    ("panel: the row of depth is no row of the list (not under the corner tool, not kept from being squeezed)", panel("'Глибина'"), PLUGIN + "/index.html",
     "                <div class=\"g-row\" data-tip=\"Глибина — стіна за людиною здається дальшою",
     "                <div class=\"g-line\" data-tip=\"Глибина — стіна за людиною здається дальшою"),
    # ---- the panel: what a PC of an earlier version gets
    ("panel: the light presets of an installed copy stay without depth (no one-time move)", panel("restoring a backup made by an older version"), MAINJS,
     "  { id: \"depth60\", presets: [\"std\", \"medium_shot\", \"wide_shot\", \"clean_stands\"], key: \"cycDepth\", slider: \"gSlDepth\", from: 0, to: 60 }\n",
     "  { id: \"depth60\", presets: [], key: \"cycDepth\", slider: \"gSlDepth\", from: 0, to: 60 }\n"),
    ("panel: the move gives depth to a dark preset too", panel("restoring a backup made by an older version"), MAINJS,
     "  { id: \"depth60\", presets: [\"std\", \"medium_shot\", \"wide_shot\", \"clean_stands\"], key: \"cycDepth\", slider: \"gSlDepth\", from: 0, to: 60 }\n",
     "  { id: \"depth60\", presets: [\"std\", \"medium_shot\", \"wide_shot\", \"clean_stands\", \"lowkey\"], key: \"cycDepth\", slider: \"gSlDepth\", from: 0, to: 60 }\n"),
    ("panel: the move does not move the slider of the active preset", panel("restoring a backup made by an older version"), MAINJS,
     "key: \"cycDepth\", slider: \"gSlDepth\", from: 0, to: 60 }\n",
     "key: \"cycDepth\", slider: \"gSlNone\", from: 0, to: 60 }\n"),
    # (Not in the list, because the checks cannot tell:
    #   - the second paste of the continued wall, into the result in full depth (_paste_big_tone(lama_f32, big)):
    #     on an 8-bit frame it writes what is there already; it matters for a 16-bit document only;
    #   - "grain is laid although the network was not run" (`or big is not None`): the drawn frame has a stand and a
    #     strip for the network, so the network always runs;
    #   - CORNER_DEPTH_SIGN, the width of the change from one zone to the other: where the two meet the correction
    #     is next to nothing, so a hard change shows as an edge of a fraction of a level;
    #   - the keys heard at the window itself and at the host's window (not only at the document), and the three
    #     timers after the opening: which of them a host needs is seen in Photoshop only.)
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
