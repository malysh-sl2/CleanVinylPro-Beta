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
    # ---- an error of the GPU costs one run, not the session (4.10.0)
    ("fallback: after one GPU error the processor keeps the fill for good", "fallback", ENGINE,
     "                sess_now, in_names = self._lama_on_cpu(exc)\n",
     "                sess_now, in_names = self._lama_on_cpu(exc)\n                self.lama_sess = sess_now\n"),
    ("fallback: the tile the GPU refused is left as it was", "fallback", ENGINE,
     "                sess_now, in_names = self._lama_on_cpu(exc)\n"
     "                pred = sess_now.run(None, {in_names[0]: inp_img, in_names[1]: inp_msk})[0][0]\n",
     "                sess_now, in_names = self._lama_on_cpu(exc)\n"
     "                pred = inp_img[0] * self.lama_out_scale\n"),
    ("fallback: the processor fails on a later tile: the tile is left out and the GPU is asked again", "fallback", ENGINE,
     "                if sess_now is not self.lama_sess:\n                    raise                  # the processor's session failed as well: nothing is left to try\n",
     "                if sess_now is not self.lama_sess:\n                    sess_now = self.lama_sess\n                    continue\n"),
    ("fallback: the answer does not say why the processor did the fill", "fallback", ENGINE,
     "\"fill_ep\": self._fill_log[\"ep\"], \"fallback\": dict(self.cpu_fallback)}\n",
     "\"fill_ep\": self._fill_log[\"ep\"], \"fallback\": {}}\n"),
    ("fallback: a fill the processor did is said to have run on the GPU", "fallback", ENGINE,
     "            log[\"ep\"] = \"CPUExecutionProvider\" if on_cpu else ep_now\n",
     "            log[\"ep\"] = ep_now\n"),
    ("fallback: the note of a fallback stays after a run the GPU did alone", "fallback", ENGINE,
     "                self.cpu_fallback.pop(\"lama\", None)   # the GPU did the whole run: an earlier fallback is over\n",
     "                pass\n"),
    ("fallback: a run without trouble says nothing of its fill", "fallback fastwin", ENGINE,
     "            if self._fill_log[\"tiles\"] > 0:\n                # the AI fill of this call",
     "            if False:\n                # the AI fill of this call"),
    ("fallback: the processor's session for the fill gets one thread, as before", "fallback", ENGINE,
     "            self._lama_cpu_sess, _ = self._create_cpu_session(self.lama_path, threads=self._fallback_threads())\n",
     "            self._lama_cpu_sess, _ = self._create_cpu_session(self.lama_path)\n"),
    ("fallback: the processor's session takes every processor (none left for Photoshop)", "fallback", ENGINE,
     "        return max(1, (os.cpu_count() or 2) - 1)\n",
     "        return max(1, (os.cpu_count() or 2))\n"),
    ("fallback: _create_cpu_session ignores the number of threads", "fallback", ENGINE,
     "        so_cpu.intra_op_num_threads = max(1, int(threads))\n",
     "        so_cpu.intra_op_num_threads = 1\n"),
    ("fallback: the silhouette: after one GPU error the processor keeps the job for good", "fallback", ENGINE,
     "            cpu_sess = self._matting_cpu_sess\n",
     "            cpu_sess = self.matting_sess = self._matting_cpu_sess\n"),
    ("fallback: the silhouette: the note of a fallback stays after a good frame", "fallback", ENGINE,
     "        else:\n            self.cpu_fallback.pop(\"matting\", None)\n",
     "        else:\n            pass\n"),
    ("fallback: the silhouette: the fallback is not noted", "fallback", ENGINE,
     "            self.cpu_fallback[\"matting\"] = str(exc)[:300]\n", ""),
    ("fallback: the silhouette: the processor's session gets one thread", "fallback", ENGINE,
     "                self._matting_cpu_sess, _ = self._create_cpu_session(self.mat_path, threads=self._fallback_threads())\n",
     "                self._matting_cpu_sess, _ = self._create_cpu_session(self.mat_path)\n"),
    ("http: /health says nothing of a fallback", "http", SERVER,
     "        \"cpu_fallback\": dict(getattr(eng, \"cpu_fallback\", {}) or {}),\n",
     "        \"cpu_fallback\": {},\n"),
    # ---- the fast window (4.10.0)
    ("fastwin: with the automatic preset the size the panel asked for is lost (large pictures all the same)", "fastwin", ENGINE,
     "(params or {}).get(\"previewLong\", p.get(\"previewLong\"))", "p.get(\"previewLong\")"),
    ("fastwin: Apply does not pass on what its computation took", "fastwin", ENGINE,
     "                if recomputed and sess.get(\"last_timing\"):\n", "                if False:\n"),
    ("fastwin: an Apply that found the frame ready repeats the numbers of an older computation", "fastwin", ENGINE,
     "                if recomputed and sess.get(\"last_timing\"):\n", "                if sess.get(\"last_timing\"):\n"),
    ("fastwin: the computation Apply makes is not remembered", "fastwin", ENGINE,
     "        sess[\"last_timing\"] = (st or {}).get(\"timing\")", "        sess[\"last_timing\"] = None"),
    ("panel: the exact picture is computed by itself although the box is off", panel("the fast window"), MAINJS,
     "  if (!detailPreview) return false;  // the fast window: the real frame is computed by Apply or by the button\n", ""),
    ("panel: the fast window asks for the large pictures", panel("the fast window"), MAINJS,
     "      params.previewLong = detailPreview ? PREVIEW_LONG_DETAIL : PREVIEW_LONG_FAST;\n",
     "      params.previewLong = PREVIEW_LONG_DETAIL;\n"),
    ("panel: the detailed preview asks for the small pictures", panel("'Детальний перегляд'"), MAINJS,
     "      params.previewLong = detailPreview ? PREVIEW_LONG_DETAIL : PREVIEW_LONG_FAST;\n",
     "      params.previewLong = PREVIEW_LONG_FAST;\n"),
    ("panel: the window sends no picture size at all", panel("the fast window", "'Детальний перегляд'"), MAINJS,
     "      params.previewLong = detailPreview ? PREVIEW_LONG_DETAIL : PREVIEW_LONG_FAST;\n", ""),
    ("panel: the corner says 'being refined' in the fast window", panel("the fast window", "'Детальний перегляд'"), MAINJS,
     "  return (sessState.exactHold || sessState.exactError || !detailPreview) ? \"quick\" : \"refining\";\n",
     "  return (sessState.exactHold || sessState.exactError) ? \"quick\" : \"refining\";\n"),
    ("panel: unticking the box leaves the background run going", panel("'Детальний перегляд'"), MAINJS,
     "      stopBackgroundRun();  // a run that is on its way is of no use any more: the computer is free at once\n", ""),
    ("panel: ticking the box does not bring the exact picture", panel("'Детальний перегляд'"), MAINJS,
     "    if (detailPreview) {\n      scheduleExactPreview();\n    } else {\n",
     "    if (detailPreview) {\n    } else {\n"),
    ("panel: the box is not written into the settings", panel("'Детальний перегляд'"), MAINJS,
     "    detailPreview,\n", ""),
    ("panel: the box is not read from the settings", panel("'Детальний перегляд' from the settings"), MAINJS,
     "  if (typeof s.detailPreview === \"boolean\") setDetailPreview(s.detailPreview, false);\n", ""),
    ("panel: a broken value in the settings switches the detailed preview on", panel("'Детальний перегляд' from the settings"), MAINJS,
     "  if (typeof s.detailPreview === \"boolean\") setDetailPreview(s.detailPreview, false);\n",
     "  if (s.detailPreview !== undefined) setDetailPreview(s.detailPreview, false);\n"),
    ("panel: the note of the settings promises an exact picture by itself in the fast window", panel("the fast window", "'Детальний перегляд'"), MAINJS,
     "    note.textContent = detailPreview\n", "    note.textContent = true\n"),
    ("panel: the button of the exact picture reads 'not needed' in the fast window", panel("the fast window"), MAINJS,
     "  btn.textContent = detailPreview ? \"↻ Перерахувати зараз (не обов’язково)\" : \"↻ Перерахувати зараз (точний перегляд)\";\n",
     "  btn.textContent = \"↻ Перерахувати зараз (не обов’язково)\";\n"),
    # ---- the brush: the trace and the end of a stroke (4.10.0)
    ("panel: the trace is one dot per mouse event again", panel("the trace of a stroke is one line"), MAINJS,
     "      const n = first ? 1 : Math.max(1, Math.min(STROKE_DOTS_PER_MOVE, Math.ceil(gap / stepPx)));\n",
     "      const n = 1;\n"),
    ("panel: the dots of the trace are too far apart (one brush width)", panel("the trace of a stroke is one line"), MAINJS,
     "const STROKE_DOT_STEP = 0.3;", "const STROKE_DOT_STEP = 1.0;"),
    ("panel: the answer to a stroke wipes every trace, also that of the stroke being drawn", panel("keeps its trace"), MAINJS,
     "  clearStrokeDots(allDone ? null : tracesUpTo);\n", "  clearStrokeDots();\n"),
    ("panel: every dot goes although a stroke is being drawn", panel("keeps its trace"), MAINJS,
     "  const allDone = maskEditsWaiting === 0 && !sessState.isDrawing;\n", "  const allDone = maskEditsWaiting === 0;\n"),
    ("panel: every dot goes although another stroke waits for the server", panel("keeps its trace"), MAINJS,
     "  const allDone = maskEditsWaiting === 0 && !sessState.isDrawing;\n", "  const allDone = !sessState.isDrawing;\n"),
    ("panel: the requests on their way are not counted", panel("keeps its trace"), MAINJS,
     "  maskEditsWaiting += 1;\n", ""),
    ("panel: the strokes are not told apart (every dot belongs to stroke 0)", panel("keeps its trace"), MAINJS,
     "      sessState.strokeNo += 1;\n", ""),
    ("panel: a stroke being drawn starts its trace anew when an answer comes (a gap in the line)", panel("keeps its trace"), MAINJS,
     "  if (!sessState.isDrawing) {\n    sessState.lastDotX = -1;\n", "  if (true) {\n    sessState.lastDotX = -1;\n"),
    ("panel: the trace of a stroke that waits for the server is never taken away", panel("keeps its trace"), MAINJS,
     "      if (it.stroke > upTo) keep.push(it);\n", "      if (true) keep.push(it);\n"),
    ("panel: the place of the release is not part of the stroke (a quick stroke is a dot)", panel("button was released"), MAINJS,
     "        sessState.strokePoints.push({ x: end.x, y: end.y, norm: true });\n        renderBrushCursorAndDot(end, true);\n", ""),
    ("panel: the stroke gets its last point but the trace does not show it", panel("button was released"), MAINJS,
     "        sessState.strokePoints.push({ x: end.x, y: end.y, norm: true });\n        renderBrushCursorAndDot(end, true);\n",
     "        sessState.strokePoints.push({ x: end.x, y: end.y, norm: true });\n"),
    ("panel: a release that brings no place draws a line to the corner of the photo", panel("button was released"), MAINJS,
     " && !(e.clientX === 0 && e.clientY === 0);\n", ";\n"),
    ("panel: the place of the release is added also when the last move was there (a point twice)", panel("button was released"), MAINJS,
     "      if (end && last && (Math.abs(end.x - last.x) > 1e-4 || Math.abs(end.y - last.y) > 1e-4)) {\n",
     "      if (end && last) {\n"),
    # ---- what a computation took, and the warning of the processor (4.10.0)
    ("panel: the corner of the photo does not warn that the processor did the fill", panel("ran on the processor"), MAINJS,
     "    } else if (sessState.cpuWarn) {\n      text = sessState.cpuWarn;\n", ""),
    ("panel: the banner of the panel does not warn of a fallback", panel("ran on the processor"), MAINJS,
     "            showBanner(cpuFallbackText(info.cpu_fallback.lama || info.cpu_fallback.matting), \"info\");\n", ""),
    ("panel: the line of the settings is not written", panel("ran on the"), MAINJS,
     "    line.textContent = whole + fillTimeText(t);\n", ""),
    ("panel: the fill is always said to have run on the video card", panel("ran on the", "after Apply"), MAINJS,
     "  const onCpu = String(t.fill_ep || \"\").includes(\"CPU\");\n  return `AI-заливка",
     "  const onCpu = false;\n  return `AI-заливка"),
    ("panel: the line of the settings is not marked when the processor did the fill", panel("ran on the"), MAINJS,
     "    line.classList.toggle(\"warn\", onCpu);\n", ""),
    ("panel: the warning is shown without the reason", panel("ran on the processor", "after Apply"), MAINJS,
     "    String(why).slice(0, 160) + ", "    \"\" + "),
    ("panel: after Apply the footer says nothing of the AI fill", panel("after Apply"), MAINJS,
     "    if (tm) timeNote += `${timeNote ? \" · \" : \" \"}${fillTimeText(tm)}`;\n", ""),
    ("panel: after Apply the footer does not say what Apply took", panel("after Apply"), MAINJS,
     "    let timeNote = typeof st.elapsed_ms === \"number\" ? ` «Застосувати»: ${secondsText(st.elapsed_ms / 1000)}` : \"\";\n",
     "    let timeNote = \"\";\n"),
    ("panel: after Apply the footer does not warn that the processor did the fill", panel("after Apply"), MAINJS,
     "      timeNote + (why ? \" \" + cpuFallbackText(why) : \"\"), \"success\");\n",
     "      timeNote, \"success\");\n"),
    ("panel: seconds are written with a point and too many digits", panel("ran on the", "after Apply"), MAINJS,
     "  return (v < 10 ? v.toFixed(1).replace(\".\", \",\") : String(Math.round(v))) + \" с\";\n",
     "  return v.toFixed(2) + \" с\";\n"),
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
