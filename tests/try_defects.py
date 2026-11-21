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
    # ---- the exact picture by itself, the engine (4.8.0)
    ("exact: a background run does not give way to a request that waits for the frame", "exact", ENGINE,
     "                    if self._compute_waiters > 0 or self._active_session is not sess or self._bg_stop != stop_mark:\n",
     "                    if self._active_session is not sess or self._bg_stop != stop_mark:\n"),
    ("exact: a background run goes on although the window said that a slider was taken", "exact", ENGINE,
     "                    if self._compute_waiters > 0 or self._active_session is not sess or self._bg_stop != stop_mark:\n",
     "                    if self._compute_waiters > 0 or self._active_session is not sess:\n"),
    ("exact: a run that still waited for its turn starts although the window said so", "exact", ENGINE,
     "                    if self._bg_stop != stop_mark:\n                        return {\"ok\": True, \"session_id\": session_id, \"superseded\": True}\n",
     "                    if False:\n                        return {\"ok\": True, \"session_id\": session_id, \"superseded\": True}\n"),
    ("exact: 'a slider was taken' also stops the runs that are asked for later", "exact", ENGINE,
     "                stop_mark = self._bg_stop  # (stop_background() after this moment is meant for this run too)\n",
     "                stop_mark = 0\n"),
    ("exact: a background run holds the session while it computes (the brush has to wait)", "exact", ENGINE,
     "                    computed = self._recompute_full(sess, clean_params, progress)\n",
     "                    with self._session_lock:\n                        computed = self._recompute_full(sess, clean_params, progress)\n"),
    ("exact: strokes are dropped when the background run puts its frame in place", "exact", ENGINE,
     "                    return self._recompute_commit(sess, p, computed, True, t0, dress=sess.get(\"dress_live\"))\n",
     "                    return self._recompute_commit(sess, p, computed, False, t0, dress=sess.get(\"dress_live\"))\n"),
    ("exact: the exact pictures forget the clothing switch that was used meanwhile", "exact", ENGINE,
     "                    return self._recompute_commit(sess, p, computed, True, t0, dress=sess.get(\"dress_live\"))\n",
     "                    return self._recompute_commit(sess, p, computed, True, t0)\n"),
    ("exact: the clothing switch is not remembered for the exact pictures", "exact", ENGINE,
     "                sess = self._session_or_raise(session_id)\n                sess[\"dress_live\"] = (bool(dress_smooth), float(dress_strength))\n                previews = self._render_session_previews(",
     "                sess = self._session_or_raise(session_id)\n                previews = self._render_session_previews("),
    ("exact: with the user's own mask the frame is computed first and declined afterwards", "exact", ENGINE,
     "                    if refine_only and sess.get(\"mask_detached\"):\n                        return {\"ok\": True, \"session_id\": session_id, \"skipped\": True, **self._picture_state(sess)}\n                    # (this request is the newest word",
     "                    if False:\n                        return {\"ok\": True, \"session_id\": session_id, \"skipped\": True, **self._picture_state(sess)}\n                    # (this request is the newest word"),
    ("exact: a mask that became the user's own drawing while the run was computing is replaced by its result", "exact", ENGINE,
     "                    if refine_only and sess.get(\"mask_detached\"):\n                        # the mask became the user's own drawing while the frame was being computed\n",
     "                    if False:\n                        # the mask became the user's own drawing while the frame was being computed\n"),
    ("exact: Apply stops the background run it was told to wait for", "exact", ENGINE,
     "            with self._compute_turn(ask_way=not follow_background, follower=follower), self._session_lock:\n",
     "            with self._compute_turn(ask_way=True, follower=follower), self._session_lock:\n"),
    ("exact: Apply that waited for a background run starts its progress bar again", "exact", ENGINE,
     "                elif followed:\n", "                elif False:\n"),
    ("exact: a quick picture is reported as the exact one", "exact", ENGINE,
     "        return {\"rev\": int(sess.get(\"rev\", 0)), \"exact\": not bool(sess.get(\"base_stale\"))}\n",
     "        return {\"rev\": int(sess.get(\"rev\", 0)), \"exact\": True}\n"),
    ("exact: a mask edit does not get the next number", "exact", ENGINE,
     "\"history\": self._edit_history_counts(sess), **self._picture_state(sess, changed=True)}\n",
     "\"history\": self._edit_history_counts(sess), **self._picture_state(sess)}\n"),
    # ---- ...the server (4.8.0)
    # ---- the pictures the window is sent (4.8.0)
    ("sharp: the picture of the original is the working picture enlarged", "sharp", ENGINE,
     "                    orig_disp_bgr = cv2.cvtColor(cv2.resize(orig_rgb_u8, disp_size, interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2BGR)\n",
     "                    orig_disp_bgr = cv2.resize(orig_small_bgr, disp_size, interpolation=cv2.INTER_LINEAR)\n"),
    ("sharp: the cleaned picture is drawn over the working picture enlarged (the person is soft, as before)", "sharp", ENGINE,
     "                comp_bgr = self._compose_display(disp, orig_s, layer_s, alpha_s, relit_s)\n",
     "                comp_bgr = self._compose_display(cv2.resize(orig_s, (disp.shape[1], disp.shape[0])), orig_s, layer_s, alpha_s, relit_s)\n"),
    ("sharp: the picture of the original stays at the working size", "sharp", ENGINE,
     "                orig_jpg_b64 = self._encode_b64_jpg(orig_small_bgr if orig_disp_bgr is None else orig_disp_bgr,\n",
     "                orig_jpg_b64 = self._encode_b64_jpg(orig_small_bgr,\n"),
    ("sharp: the enlarged layer covers the whole picture, the person too", "sharp", ENGINE,
     "        change = cv2.multiply(cv2.subtract(layer, disp_bgr, dtype=cv2.CV_32F), cv2.merge([a, a, a]))\n",
     "        change = cv2.subtract(layer, disp_bgr, dtype=cv2.CV_32F)\n"),
    ("sharp: the larger pictures do not show the strokes and the eraser", "sharp", ENGINE,
     "                comp_bgr = self._compose_display(disp, orig_s, layer_s, alpha_s, relit_s)\n",
     "                comp_bgr = self._compose_display(disp, orig_s, layer_s, sess[\"auto_mask_small_u8\"].astype(np.float32) / 255.0, relit_s)\n"),
    ("sharp: the larger pictures do not show what the brush painted", "sharp", ENGINE,
     "                comp_bgr = self._compose_display(disp, orig_s, layer_s, alpha_s, relit_s)\n",
     "                comp_bgr = self._compose_display(disp, orig_s, sess[\"clean_base_small_bgr\"], alpha_s, relit_s)\n"),
    ("sharp: ironed clothing is shown from the enlarged layer (the weave is lost)", "sharp", ENGINE,
     "                comp_bgr = self._compose_display(disp, orig_s, layer_s, alpha_s, relit_s)\n",
     "                comp_bgr = self._compose_display(disp, orig_s, layer_s, alpha_s, None)\n"),
    ("sharp: ironed clothing gets the fine detail of the photo upside down", "sharp", ENGINE,
     "            change += cv2.multiply(cv2.subtract(disp_bgr, orig_up, dtype=cv2.CV_32F), cv2.merge([r, r, r]))\n",
     "            change -= cv2.multiply(cv2.subtract(disp_bgr, orig_up, dtype=cv2.CV_32F), cv2.merge([r, r, r]))\n"),
    ("sharp: a picture larger than the frame itself", "sharp", ENGINE,
     "        scale = min(1.0, float(long_side) / max(h, w, 1))\n        dw, dh = int(round(w * scale)), int(round(h * scale))\n        if dw < pw",
     "        scale = float(long_side) / max(h, w, 1)\n        dw, dh = int(round(w * scale)), int(round(h * scale))\n        if dw < pw"),
    ("sharp: 'previewLong' of the request is ignored", "sharp", ENGINE,
     "                disp_size = self._display_size(w, h, pw, ph, p.get(\"previewLong\"))\n",
     "                disp_size = self._display_size(w, h, pw, ph, None)\n"),
    ("sharp: the working size the window places things by follows the larger pictures", "sharp", ENGINE,
     "                    \"preview_w\": pw,\n                    \"preview_h\": ph,\n                    \"auto_fractions\": auto_fracs,\n",
     "                    \"preview_w\": pw if orig_disp_bgr is None else orig_disp_bgr.shape[1],\n                    \"preview_h\": ph if orig_disp_bgr is None else orig_disp_bgr.shape[0],\n                    \"auto_fractions\": auto_fracs,\n"),
    ("sharp: the mask view of the larger size has no tints", "sharp", ENGINE,
     "                out[\"overlay_jpg_b64\"] = self._encode_b64_jpg(self._overlay_display(comp_bgr, eff_mask, marked), quality=quality)\n",
     "                out[\"overlay_jpg_b64\"] = self._encode_b64_jpg(comp_bgr, quality=quality)\n"),
    ("sharp: the mask view of the larger size shows the whole layer bright green", "sharp", ENGINE,
     "                out[\"overlay_jpg_b64\"] = self._encode_b64_jpg(self._overlay_display(comp_bgr, eff_mask, marked), quality=quality)\n",
     "                out[\"overlay_jpg_b64\"] = self._encode_b64_jpg(self._overlay_display(comp_bgr, eff_mask, None), quality=quality)\n"),
    ("sharp: the mask view of the larger size has no red over what is left alone", "sharp", ENGINE,
     "        red = cv2.resize(red_a * (1.0 - grn_a), size, interpolation=cv2.INTER_LINEAR)\n",
     "        red = cv2.resize(0.0 * red_a, size, interpolation=cv2.INTER_LINEAR)\n"),
    ("sharp: a picture that is hardly larger than the working one is made all the same", "sharp", ENGINE,
     "        if dw < pw * cls.DISPLAY_MIN_GAIN or dh < ph * cls.DISPLAY_MIN_GAIN:\n",
     "        if dw <= pw or dh <= ph:\n"),
    ("sharp: the size a request may ask for has no limit", "sharp", ENGINE,
     "                long_side = int(np.clip(int(asked), 0, 4320))\n",
     "                long_side = int(asked)\n"),
    ("http: the server does not pass 'background' on (every exact request makes the window wait)", "http", SERVER,
     "        background = bool(body.get(\"background\", False))\n", "        background = False\n"),
    ("http: the server does not pass 'followBackground' on", "http", SERVER,
     "        follow_background = bool(body.get(\"followBackground\", False))\n", "        follow_background = False\n"),
    ("http: 'a slider was taken' does not reach the engine", "http", SERVER,
     "    return eng.stop_background(sid)\n", "    return {\"ok\": True, \"stopped\": False}\n"),
    # ---- ...the panel (4.8.0)
    ("panel: no exact picture is asked for after a light refresh", panel("exact"), MAINJS,
     "  if (sessState.open && sessState.id === sid) scheduleExactPreview();\n  else updatePreviewBadge();\n  return done;\n",
     "  updatePreviewBadge();\n  return done;\n"),
    ("panel: the exact picture is asked for at once, without the quiet moment", panel("exact"), MAINJS,
     "const EXACT_DELAY_MS = 700;\n", "const EXACT_DELAY_MS = 0;\n"),
    ("panel: the exact request is an ordinary recompute (the window waits for it)", panel("exact"), MAINJS,
     "      body: JSON.stringify({ session_id: sid, params, preserve_edits: true, background: true, jobId })\n",
     "      body: JSON.stringify({ session_id: sid, params, preserve_edits: true, jobId })\n"),
    ("panel: an older picture replaces a newer one", panel("exact"), MAINJS,
     "    if (d.rev < sessState.picRev) return false;\n", ""),
    ("panel: the exact picture is asked for while a slider is held", panel("exact"), MAINJS,
     "  const busy = activeDragSliderId || sessState.isDrawing || sessState.recomputing || sessState.previewTimer;\n",
     "  const busy = sessState.isDrawing || sessState.recomputing || sessState.previewTimer;\n"),
    ("panel: the exact picture is asked for while a stroke is being drawn", panel("exact"), MAINJS,
     "  const busy = activeDragSliderId || sessState.isDrawing || sessState.recomputing || sessState.previewTimer;\n",
     "  const busy = activeDragSliderId || sessState.recomputing || sessState.previewTimer;\n"),
    ("panel: the server is not told when a slider is taken during a background run", panel("exact"), MAINJS,
     "      if (id !== \"dlgSlBlend\" && id !== \"gSlDress\") stopBackgroundRun();\n", ""),
    ("panel: taking Blend stops the background run", panel("exact"), MAINJS,
     "      if (id !== \"dlgSlBlend\" && id !== \"gSlDress\") stopBackgroundRun();\n", "      stopBackgroundRun();\n"),
    ("panel: what was put off when Blend or Clothing was taken is forgotten", panel("put off"), MAINJS,
     "    } else if (finishedSliderId) {\n", "    } else if (false) {\n"),
    ("panel: the corner label calls a quick picture the clean photo", panel("exact"), MAINJS,
     "    badge.textContent = kind === \"exact\" ? \"ПІСЛЯ · чисте фото\" : \"ПІСЛЯ · швидкий перегляд\" + refining;\n",
     "    badge.textContent = \"ПІСЛЯ · чисте фото\";\n"),
    ("panel: a failed exact request is tried again and again", panel("exact"), MAINJS,
     "    sessState.exactError = failed;\n", ""),
    ("panel: an exact request the server declined is asked again and again", panel("own drawing"), MAINJS,
     "    sessState.exactHold = true;\n", ""),
    ("panel: with 2 passes the sliders start nothing, as before 4.8.0", panel("2 passes"), MAINJS,
     "  return !lightPreviewAvailable();  // new values and no light way (2 passes): the exact picture is the only one\n",
     "  return false;\n"),
    ("panel: a server before 4.8.0 is asked for background recomputes", panel("before 4.8.0"), MAINJS,
     "      sessState.bgUnsupported = typeof res.exact !== \"boolean\";\n", "      sessState.bgUnsupported = false;\n"),
    ("panel: Apply never asks to wait for the running background recompute", panel("Застосувати"), MAINJS,
     "  const followBackground = exactJobs.size > 0 && sessState.exactSig === previewSettingsSignature();\n",
     "  const followBackground = false;\n"),
    ("panel: Apply waits for a background recompute of other values", panel("Застосувати"), MAINJS,
     "  const followBackground = exactJobs.size > 0 && sessState.exactSig === previewSettingsSignature();\n",
     "  const followBackground = exactJobs.size > 0;\n"),
    ("panel: a closed window leaves its exact timer running", panel("closing the window"), MAINJS,
     "    sessState.scanAborted = true;\n    cancelPreviewTimer();\n    cancelExactTimer();\n    stopExactPolling();\n",
     "    sessState.scanAborted = true;\n    cancelPreviewTimer();\n"),
    # ---- strokes on the cleaned photo (4.8.0)
    ("panel: a stroke switches the mask on, as before 4.8.0", panel("cleaned photo"), MAINJS,
     "      if (sessState.view === \"original\") setView(\"result\");\n", "      if (sessState.view !== \"mask\") setView(\"mask\");\n"),
    ("panel: the key B switches the mask on", panel("cleaned photo"), MAINJS,
     "      setActiveTool(\"brush\");\n    } else if (e.key === \"e\"", "      setActiveTool(\"brush\");\n      if (sessState.id) setView(\"mask\");\n    } else if (e.key === \"e\""),
    ("panel: the inversion switches the mask on", panel("cleaned photo"), MAINJS,
     "    const d = await sendMaskEditOp(\"invert\");\n", "    setView(\"mask\");\n    const d = await sendMaskEditOp(\"invert\");\n"),
    ("panel: the trace of a stroke is not shown over the cleaned photo", panel("cleaned photo"), MAINJS,
     "    dots.style.display = showOrig ? \"none\" : \"block\";\n", "    dots.style.display = showMask ? \"block\" : \"none\";\n"),
    ("panel: a stroke over the original leaves the original on screen", panel("cleaned photo"), MAINJS,
     "      if (sessState.view === \"original\") setView(\"result\");\n", ""),
    # ---- zoom keys, the right mouse button (4.8.0)
    ("panel: Ctrl + '+' zooms out and Ctrl + '-' zooms in", panel("Ctrl + '+'"), MAINJS,
     "        else zoomBy(zoomKey === \"in\" ? ZOOM_KEY_STEP : 1 / ZOOM_KEY_STEP);\n", "        else zoomBy(zoomKey === \"in\" ? 1 / ZOOM_KEY_STEP : ZOOM_KEY_STEP);\n"),
    ("panel: Ctrl + 0 does not fit the photo", panel("Ctrl + '+'"), MAINJS,
     "        if (zoomKey === \"fit\") resetZoomFit();\n        else zoomBy(", "        if (zoomKey === \"fit\") return;\n        else zoomBy("),
    ("panel: the zoom keys work without Ctrl", panel("Ctrl + '+'"), MAINJS,
     "    if (!typing && (e.ctrlKey || e.metaKey) && !e.altKey) {\n", "    if (!typing && !e.altKey) {\n"),
    ("panel: the zoom keys are taken from a text field", panel("Ctrl + '+'"), MAINJS,
     "    if (!typing && (e.ctrlKey || e.metaKey) && !e.altKey) {\n", "    if ((e.ctrlKey || e.metaKey) && !e.altKey) {\n"),
    ("panel: a key that says only its number is not a zoom key", panel("Ctrl + '+'"), MAINJS,
     " || k === \"subtract\" || n === 189 || n === 109 || n === 173) return \"out\";\n", " || k === \"subtract\") return \"out\";\n"),
    ("panel: zooming with the keys lets the middle of the view drift", panel("Ctrl + '+'"), MAINJS,
     "  sessState.panX = cx - (cx - sessState.panX) * ratio;\n  sessState.panY = cy - (cy - sessState.panY) * ratio;\n", ""),
    ("panel: the keys zoom past the limits", panel("Ctrl + '+'"), MAINJS,
     "  const nextZoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, oldZoom * factor));\n", "  const nextZoom = oldZoom * factor;\n"),
    ("panel: the right mouse button does not drag the photo", panel("right mouse"), MAINJS,
     "    if (e.button === 1 || e.button === 2 || sessState.spaceDown || sessState.tool === \"pan\") {\n",
     "    if (e.button === 1 || sessState.spaceDown || sessState.tool === \"pan\") {\n"),
    ("panel: the menu of the right button opens over the photo", panel("right mouse"), MAINJS,
     "    if (!sessState.open) return;\n    e.preventDefault();\n    if (sessState.isPanning && sessState.panButton === 2 &&",
     "    if (!sessState.open) return;\n    if (sessState.isPanning && sessState.panButton === 2 &&"),
    ("panel: a menu event at the press ends the drag at once", panel("right mouse"), MAINJS,
     "(sessState.panMoved || Date.now() - sessState.panStartedMs > 250)", "true"),
    ("panel: a menu event never ends the drag (a host without 'mouseup' for the right button)", panel("right mouse"), MAINJS,
     "(sessState.panMoved || Date.now() - sessState.panStartedMs > 250)", "false"),
    ("panel: the right button of a host that sends pointer events only is ignored", panel("right mouse"), MAINJS,
     "    if (!sessState.open || e.button !== 2 || sessState.isPanning) return;\n    startPan(e);\n", "    return;\n"),
    # ---- the name without the 2 (4.8.0)
    ("panel: a new layer keeps the 2 in its name", panel("the name has no 2"), MAINJS,
     "const LAYER_NAME_AI = \"Чистий вініл (AI)\";\n", "const LAYER_NAME_AI = \"Чистий вініл 2 (AI)\";\n"),
    ("panel: a layer made by 4.7.0 is no longer found by 'До / Після'", panel("the name has no 2"), MAINJS,
     "const PLUGIN_LAYER_NAMES = [LAYER_NAME_AI, LAYER_NAME_SELECTION, \"Чистий вініл 2 (AI)\", \"Чистий вініл 2 (Виділення)\"];\n",
     "const PLUGIN_LAYER_NAMES = [LAYER_NAME_AI, LAYER_NAME_SELECTION];\n"),
    ("panel: the step of the History panel keeps the 2", panel("the name has no 2"), MAINJS,
     "        name: \"Чистий Вініл Pro\"\n", "        name: \"Чистий Вініл Pro 2\"\n"),
    ("panel: the big window keeps the 2 in its title", panel("the name has no 2"), MAINJS,
     "      title: \"Чистий Вініл Pro\",\n", "      title: \"Чистий Вініл Pro 2\",\n"),
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
