#!/usr/bin/env python3
"""
Self-checks of the Clean Vinyl Pro server (folder CleanVinylPro2; the program was shown as "Pro 2" up to 4.7.0).
No AI models, no GPU and no Photoshop needed.

    python tests/run_checks.py            # quick run (about 35 minutes)
    python tests/run_checks.py --full     # more random cases
    python tests/run_checks.py stage http # only the groups whose name contains one of the words

Part 1 - what was NOT meant to change still gives the pixels of the original program (folder CleanVinylPro,
v3.2.1). These comparisons run in the "legacy regime": quality mode, smoke protection off, cyclorama 0, clothing
off, stains 0, floor-joint pieces judged one by one - the places where this program works differently on
purpose - and "toneEdge" off: the repair is blended under the protected band and hidden there by the layer, as
it always was. (In the interactive window also: background blur 0. With the backdrop blurred the layer covers the
whole backdrop; the window now shows that in two greens and repairs a brush stroke there - see `mask`.)
  convert   fast pixel conversions give the same numbers as the plain NumPy formulas (all 8/16-bit values)
  process   one-shot clean: current engine == v3.2.1 engine, pixel for pixel
  session   interactive window (open / sliders / brush / apply): current engine == v3.2.1
  http      every HTTP endpoint: current server == v3.2.1 server (needs the `httpx` package)
  stage     interactive stage cache: a recompute that re-uses stored stages == a full recompute
  quick     light preview after the sliders: the layer made by "light refreshes + one full computation at Apply"
            == the layer of the old way (a full recompute after every change); the preview itself stays close
  white     the "white patch after Apply" bug stays fixed
  gpu       the cuDNN option can never push the models from the GPU onto the CPU

Part 2 - what this program does differently from v3.2.1, each with its own measurable promise:
  cyc       cyclorama: the wall-floor line goes away, people are not touched, a frame without a corner is not touched
  dress     clothing: wrinkles get weaker; volume, colour, fine texture, denim and everything outside stay
  speed     the two ways of closing defects - the full AI fill (the only mode of the panel since 4.7.0) and the fast
            way (the light preview) - find exactly the same defects
  smoke     smoke protection: no "protected ring" around the person; real smoke is still protected
  empty     a frame without people: nobody is invented
  format    format 5:7: size, seamless join, nothing drawn over the photo, 8/16 bit, both orientations
  scene     automatic preset: the frame is recognised (whole figure / cut at the waist or knees / close-up / dark
            backdrop) and the window opens exactly as if the suitable preset had been chosen by hand
  stains    stains and shoe marks: evened next to the person as well as away from it; shadows, props, the light,
            the person and a clean frame stay as they are
  seam      the joint of two backdrop sheets: removed on both sides of the person, short pieces and dark lines
            included; two different lines are not joined; works together with the wall-floor corner
  mask      the whole backdrop is evened: the mask view tells "found and repaired" from "evened", the brush
            repairs what it paints, the eraser leaves alone what it erases
  brush     the brush and the eraser of the big window: a soft edge without a step (a hard one when asked), a
            painted zone made of the tone and the grain of the backdrop around it, the same in the window and
            in the layer; the soft brush never touches the person; a shadow that a stroke crosses or touches is
            neither smeared nor spread; "fill" repaints nothing
  dark      a dark backdrop with a pool of light: the noise of the lit part is not taken for dust (it is judged
            against the noise found there), real dust is still found, an evenly lit frame is searched exactly as
            before; the pictures of the big window keep the fine noise of a dark frame (JPEG 100 instead of 90)
  gear      studio gear is told by its body: dust at the hard edge of a cast shadow and a scratch on the floor
            are repaired (both used to be kept untouched as "gear"); a stand, a cable and a reflector at the frame
            border are still left alone; a shadow edge is not taken for smoke
  shadow    a dirty spot inside a cast shadow is repaired; the rim of the shadow, its denser parts, a contact shadow
            and a light gap in it are not (the rule is also tried on drawn spots with the owner's numbers)
  undo      the big window: every mask edit (brush, eraser, fill, clear, invert) can be taken back and made again,
            also after the sliders were moved; Apply after a step back == Apply without that edit
  exact     the exact picture of the big window comes by itself: a background recompute gives the frame of a full
            recompute; the brush and the eraser are answered while it computes and stay in the result; new slider
            values, Apply, closing the window or another photo make it stop at its next safe place with the
            session untouched (tried at every such place), and so does the window when a slider is taken; Apply
            waits for it when it computes the very frame Apply needs; a mask that is the user's own drawing is
            never replaced by itself; the clothing switch used meanwhile shows in the exact pictures
  sharp     the pictures the big window is sent are twice the working size (up to 2160 px, never larger than the
            frame): what the layer leaves alone - the person - is the photo of that size, pixel for pixel, several
            times sharper than the working picture enlarged; the layer shows what it showed (also after a stroke,
            the eraser, a light refresh, the exact picture); ironed clothing keeps the weave of the cloth; the
            working size, by which the window places everything, is unchanged
  edge      the corner and the stains change the tone of the backdrop right up to the person: no strip of the old
            tone is left around it (the rim along a hem and around the shoes); the person is not touched; the
            repair away from the person is what it was
  line      a joint of the vinyl that the corner tool takes for the corner: its thin dark line goes with the step,
            with the seam tool on and off - also when the line runs beside the middle of the step (one line, one
            tool: the seam tool marks nothing of it); a joint or a corner without such a line: nothing is taken out
  hair      the slider of the single hairs: hairs that stick out of the hairdo are repaired (also a dead straight
            one), from the wall as the photo has it; what stays: the fuzz of the outline, a hair that
            runs along it, an eyelash, a dark line that grows out of the lit face, a line that touches nobody, a
            wisp of crossing hairs, a thread at the clothes, a cable (also one crossed by hairs), a pole that goes
            on beyond the searched zone or to the top of the frame, and the person;
            the lower the slider, the longer a hair must be, and a higher position never takes less; dark and
            light hairs, a close-up; at 0 nothing is looked for; in the big window a light refresh and a full
            recompute give the frame of that slider value
  fallback  an error of the GPU costs one run, not the session (since 4.10.0): the processor finishes the fill the
            GPU refused, with the same pixels and with all processors but one; the answer says where the fill ran
            and why; the next run asks the GPU again; when the processor fails too, the error comes out; the
            silhouette network follows the same rule
  fastwin   the fast window (since 4.10.0): a start request that asks for pictures of the working size gets them,
            also with the automatic preset and after a stroke; without the request the pictures are the large
            ones; an Apply that computes the real frame says what its AI fill took and where it ran

Part 3 - the program around the engine:
  server    settings migration, binary packets, one version everywhere; the name a person reads has no 2 (since
            4.8.0), layers of older versions are still recognised, the plugin icon is opaque; no id / port /
            url scheme / task / data folder shared with the original program (both can run side by side)
  plugin    plugin settings migration and the behaviour of the big window (needs Node.js; the window test
            also needs the jsdom package), the .ccx package and the download archive CleanVinylPro2.zip being
            up to date, CRLF line endings of the .bat files

Part 4 - installing (tests/install_checks.py; needs nothing but Python):
  folders   folders.ini (shared folders for the AI models, Python and its libraries): read alike by Python and by
            install_windows.bat; the models are found in the shared folder, copied before they are downloaded
  install   server/setup_env.py really run in an imitated PC: libraries once in the shared folder, a second copy
            of the program needs no pip, a moved Python is re-linked, libraries of the old program are re-used
  bat       the .bat files read the way cmd.exe reads them (they cannot be run without Windows)

The comparisons with v3.2.1 use the files of the original program kept in tests/baseline_v321 (engine.py, server.py
and a few more, exactly as they were; the program itself is no longer in the repository).
"""
import base64
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import types
import warnings

sys.dont_write_bytecode = True  # keep the repository free of __pycache__ folders

import cv2  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H  # noqa: E402
import install_checks as IC  # noqa: E402

# The seam detector (unchanged since v3.2.1) averages an empty selection on some frames; NumPy reports that
# as a RuntimeWarning in both versions. It is not what these checks are about.
warnings.filterwarnings("ignore", category=RuntimeWarning)

FULL = "--full" in sys.argv
ONLY = [a for a in sys.argv[1:] if not a.startswith("-")]
E = H.load_engine()
E_OLD, SRV_OLD = H.load_baseline()
ENG = E.CleanVinylEngine

_results = []


def report(group: str, ok: bool, text: str) -> None:
    _results.append((group, ok))
    print(f"[{'ok' if ok else 'FAIL'}] {group:8s} {text}", flush=True)


def _quiet(fn, *a, **k):
    """Runs fn with the engine's console chatter hidden."""
    real = sys.stdout
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
    try:
        return fn(*a, **k)
    finally:
        sys.stdout.close()
        sys.stdout = real


def _legacy(p: dict) -> dict:
    """The parameters under which the engine must still give the pixels of v3.2.1 (see the header)."""
    return dict(p, speedMode="quality", smokeOn=False, cycCurve=0, dressSmooth=False, scuffs=0, seamJoin=False,
                grainLocal=False, previewQuality=90, gearBody=False, shadowSpots=False, brushSoft=False, previewLong=1080,
                toneEdge=False, cornerHair=False, strayHair=0)


def _legacy_window(p: dict) -> dict:
    """
    The legacy regime for the interactive window: also without the background blur. With any stage that works on
    the whole backdrop the layer covers the whole backdrop; the window then shows what was found and repaired apart
    from what is only evened, and repairs a brush stroke there - on purpose, see check_mask. (The blur itself is
    still compared with v3.2.1 by the one-shot checks.)
    """
    return dict(_legacy(p), blur=0)


def _same_stats(a: dict, b: dict) -> bool:
    skip = ("elapsed_ms", "reused_stages", "timing")
    return all(a[k] == b.get(k) for k in a if k not in skip)


# ----------------------------------------------------------------------------------------------------------------------
def check_convert():
    bad = []
    u8 = np.arange(256, dtype=np.uint8).reshape(16, 16)
    u16 = np.arange(65536, dtype=np.uint16).reshape(256, 256)
    for arr, ps in ((u8, 255.0), (u16, 32768.0)):
        unit_ref = np.clip(arr.astype(np.float32) * (1.0 / ps), 0.0, 1.0)
        if not np.array_equal(ENG._to_unit_f32(arr, ps), unit_ref):
            bad.append(f"_to_unit_f32 {arr.dtype}")
        if not np.array_equal(ENG._to_analysis_u8(arr, ps), np.clip(unit_ref * 255.0 + 0.5, 0, 255).astype(np.uint8)):
            bad.append(f"_to_analysis_u8 {arr.dtype}")
        # the formula the session code used before: (x / ps) * 255 + 0.5
        if not np.array_equal(ENG._to_analysis_u8(arr, ps), np.clip((arr.astype(np.float32) / ps) * 255.0 + 0.5, 0, 255).astype(np.uint8)):
            bad.append(f"_to_analysis_u8 (session formula) {arr.dtype}")

    rng = np.random.default_rng(0)
    for dt, ps in ((np.uint8, 255.0), (np.uint16, 32768.0)):
        ties = (np.arange(int(ps)) + 0.5) / ps
        vals = np.concatenate([rng.random(400_000), ties, [-0.5, -1e-9, 0.0, 1.0, 1.0000001, 1.7, 3.0]])
        for ftype in (np.float32, np.float64):
            x = vals.astype(ftype).reshape(-1, 1)
            ref = np.clip(np.round(x * ps), 0, ps).astype(dt)
            if not np.array_equal(ENG._quantize_unit(x.copy(), ps, dt), ref):
                bad.append(f"_quantize_unit {np.dtype(ftype).name}->{np.dtype(dt).name}")
    x = rng.random((300, 7)).astype(np.float64)  # layer mask of a 16-bit document: float64 alpha -> uint8
    if not np.array_equal(ENG._quantize_unit(x.copy(), 255.0, np.uint8), np.clip(np.round(x * 255.0), 0, 255).astype(np.uint8)):
        bad.append("_quantize_unit float64->uint8 mask")

    for dt in (np.uint8, np.uint16):
        rgba = rng.integers(0, 256, (37, 53, 4)).astype(dt)
        if not np.array_equal(ENG._rgb_planes(rgba), rgba[:, :, :3]):
            bad.append(f"_rgb_planes {np.dtype(dt).name}")
        ro = rgba.copy()
        ro.setflags(write=False)
        ENG._rgb_planes(ro)

    for trial in range(40):  # 128px cell detection of the heal blend
        h, w = int(rng.integers(1, 700)), int(rng.integers(1, 900))
        a = np.zeros((h, w), np.float32)
        for _ in range(int(rng.integers(0, 6))):
            a[int(rng.integers(0, h)), int(rng.integers(0, w))] = float(rng.choice([1.0, 0.5, 0.0015, 0.0025]))
        cells, bbox = ENG._heal_cells(a)
        ref_cells = [(y, min(h, y + 128), x, min(w, x + 128)) for y in range(0, h, 128) for x in range(0, w, 128)
                     if (a[y:y + 128, x:x + 128] > 0).any()]
        ys, xs = np.where(a > 0.002)
        ref_bbox = (int(ys.min()), int(ys.max()) + 1, int(xs.min()), int(xs.max()) + 1) if ys.size else None
        if cells != ref_cells or bbox != ref_bbox:
            bad.append(f"_heal_cells trial {trial}")
            break
    report("convert", not bad, "pixel conversions and cell detection match the NumPy formulas" if not bad else f"differences: {bad}")


# ----------------------------------------------------------------------------------------------------------------------
SIZES = [(2000, 1500), (1500, 2000), (1777, 1333), (640, 480), (300, 200), (2600, 1731), (1024, 1024), (129, 257), (3000, 2000)]


def _rand_params(rng):
    p = dict(H.STD)
    p["speedMode"] = str(rng.choice(["fast", "quality"]))
    for k, lo, hi in (("spots", 0, 100), ("scuffs", 0, 100), ("blur", 0, 60), ("cycCurve", 0, 80), ("feather", 0, 100),
                      ("seam", 0, 100), ("edge", 0, 100), ("smoke", 0, 100), ("grain", 0, 100), ("master", 60, 200),
                      ("dressStrength", 0, 100)):
        r = rng.random()
        if k in ("blur", "cycCurve") and r < 0.5:
            p[k] = 0
        elif k in ("spots", "scuffs", "grain") and r < 0.12:
            p[k] = 0
        elif r < 0.75 or k in ("blur", "cycCurve"):
            p[k] = int(rng.integers(lo, hi + 1))
    for k, pr in (("seamOn", 0.8), ("smokeOn", 0.8), ("shadow", 0.8), ("removeStands", 0.3), ("fracFine", 0.85),
                  ("fracMed", 0.85), ("fracLarge", 0.85), ("dressSmooth", 0.25)):
        p[k] = bool(rng.random() < pr)
    p["cleanPasses"] = 2 if rng.random() < 0.25 else 1
    return p


def _mutate(p, rng):
    p = dict(p)
    for _ in range(int(rng.integers(1, 4))):
        k = str(rng.choice(["spots", "scuffs", "blur", "cycCurve", "feather", "seam", "edge", "smoke", "grain", "master",
                            "seamOn", "smokeOn", "shadow", "removeStands", "fracFine", "fracMed", "fracLarge",
                            "cleanPasses", "speedMode", "autoFractions", "same", "blur", "cycCurve", "scuffs", "blur",
                            "feather", "spots", "smokeAuto", "seamJoin", "cycCurve", "scuffs", "smokeFaint"]))
        if k == "same":
            continue
        if k in ("seamOn", "smokeOn", "shadow", "removeStands", "fracFine", "fracMed", "fracLarge", "autoFractions",
                 "smokeAuto", "seamJoin", "smokeFaint"):
            p[k] = not bool(p.get(k, False))
        elif k == "cleanPasses":
            p[k] = 3 - int(p.get(k, 1))
        elif k == "speedMode":
            p[k] = "quality" if p.get(k) == "fast" else "fast"
        elif k == "master":
            p[k] = int(rng.choice([60, 100, 100, 130, 200]))
        elif k in ("blur", "cycCurve"):
            p[k] = int(rng.choice([0, 0, 10, 25, 40, 70]))
        else:
            p[k] = int(rng.integers(0, 101))
    return p


def _rand_selection(rng, w, h, bit16):
    kind = str(rng.choice(["none", "none", "small", "large", "soft", "empty"]))
    if kind == "none":
        return None
    sel = np.zeros((h, w), np.uint8)
    if kind == "small":
        x0, y0 = int(rng.integers(0, int(w * 0.7))), int(rng.integers(int(h * 0.5), int(h * 0.85)))
        sel[y0:y0 + max(4, h // 8), x0:x0 + max(4, w // 6)] = 255
    elif kind == "large":
        sel[h // 10:, : int(w * 0.9)] = 255
    elif kind == "soft":
        cv2.circle(sel, (w // 3, int(h * 0.75)), max(6, min(w, h) // 5), 255, -1)
        sel = cv2.GaussianBlur(sel, (0, 0), max(1.0, min(w, h) / 60))
    if bit16 and rng.random() < 0.5:
        sel = sel.astype(np.uint16) * 128
    return sel


def check_process():
    if E_OLD is None:
        report("process", True, "SKIPPED - v3.2.1 is not available (tests/baseline_v321 is missing)")
        return
    rng = np.random.default_rng(1000)
    n_cases = 60 if FULL else 14
    bad = []
    t_old = t_new = 0.0
    for ci in range(n_cases):
        w, h = SIZES[int(rng.integers(0, len(SIZES)))]
        bit16, rgba, lowkey = bool(rng.random() < 0.4), bool(rng.random() < 0.5), bool(rng.random() < 0.3)
        img, sil = H.make_studio_image(w, h, n_dust=int(rng.integers(0, 160)), n_hair=int(rng.integers(0, 14)),
                                       seed=int(rng.integers(0, 10 ** 6)), bit16=bit16, rgba=rgba, lowkey=lowkey)
        if rng.random() < 0.15:
            sil = np.zeros_like(sil)  # nobody in the frame
        params = _legacy(_rand_params(rng))
        sel = _rand_selection(rng, w, h, bit16)
        kw = {}
        custom = str(rng.choice(["none", "none", "none", "fg", "heal", "both"]))
        if custom in ("fg", "both"):
            kw["custom_fg_mask"] = (cv2.resize(sil, (w, h)) * 255).astype(np.uint8)
        if custom in ("heal", "both"):
            hm = np.zeros((h, w), np.uint8)
            for _ in range(int(rng.integers(0, 9))):
                cv2.circle(hm, (int(rng.integers(0, w)), int(rng.integers(0, h))), int(rng.integers(2, max(3, min(w, h) // 10))), 255, -1)
            kw["custom_heal_mask"] = hm
        outs = []
        for mod in (E_OLD, E):
            eng = H.make_engine(mod, sil)
            src = img.copy()
            src.setflags(write=False)  # the server hands over a read-only view of the request body
            oc = {}
            t0 = time.perf_counter()
            res, st = _quiet(eng.process, src, 16 if bit16 else 8, dict(params),
                             selection_alpha=None if sel is None else sel.copy(), out_cache=oc,
                             **{k: v.copy() for k, v in kw.items()})
            dt = time.perf_counter() - t0
            if mod is E:
                t_new += dt
            else:
                t_old += dt
            outs.append((res, st, oc, eng.lama_sess.calls))
        (r0, s0, c0, l0), (r1, s1, c1, l1) = outs
        # (the current engine may hand over more than v3.2.1 did; what v3.2.1 handed over must be the same)
        same_oc = set(c0) <= set(c1) and all(
            np.array_equal(c0[k], c1[k]) if isinstance(c0[k], np.ndarray) else c0[k] == c1[k] for k in c0)
        if not (np.array_equal(r0, r1) and _same_stats(s0, s1) and same_oc and l0 == l1):
            bad.append(f"case {ci}: {w}x{h} {'16' if bit16 else '8'}-bit {'RGBA' if rgba else 'RGB'} {params}")
    report("process", not bad, f"{n_cases} random one-shot cleans (legacy regime) identical to v3.2.1 "
                               f"(time {t_old:.1f}s -> {t_new:.1f}s)" if not bad else "DIFFERENT:\n  " + "\n  ".join(bad))


def check_stage():
    rng = np.random.default_rng(2000)
    bad = []
    steps = reused = 0
    for (w, h, bit16, rgba) in ([(2000, 1500, False, False), (1500, 2000, True, True)] + ([(2600, 1731, False, True)] if FULL else [])):
        img, sil = H.make_studio_image(w, h, seed=w, bit16=bit16, rgba=rgba)
        fg_raw = np.clip(sil * 255.0, 0, 255).astype(np.uint8)
        sel = None
        if rgba:
            sel = np.zeros((h, w), np.uint8)
            sel[h // 3:, : int(w * 0.8)] = 255
        eng = H.make_engine(E, sil)
        cache: dict = {}
        p = dict(H.STD, speedMode="fast")
        for step in range(24 if FULL else 12):
            if step:
                p = _mutate(p, rng)
            p["dressSmooth"] = False
            a, sa = _quiet(eng.process, img, 16 if bit16 else 8, dict(p), selection_alpha=sel, cached_fg_raw_1024=fg_raw, stage_cache=cache)
            b, sb = _quiet(eng.process, img, 16 if bit16 else 8, dict(p), selection_alpha=sel, cached_fg_raw_1024=fg_raw)
            steps += 1
            reused += len(sa["reused_stages"])
            if not (np.array_equal(a, b) and _same_stats(sa, sb)):
                bad.append(f"{w}x{h} step {step} reused={sa['reused_stages']} params={p}")
        # same parameters again -> everything cached, still identical
        a, sa = _quiet(eng.process, img, 16 if bit16 else 8, dict(p), selection_alpha=sel, cached_fg_raw_1024=fg_raw, stage_cache=cache)
        if not np.array_equal(a, b) or "heal" not in sa["reused_stages"]:
            bad.append(f"{w}x{h} repeat call reused={sa['reused_stages']}")
    report("stage", not bad, f"{steps} recomputes with the stage cache identical to full recomputes "
                             f"({reused} stages re-used)" if not bad else "DIFFERENT:\n  " + "\n  ".join(bad))


def _count_full_frames(eng):
    """Counts how many times the engine computes the real, full-size cleaned frame."""
    counter = {"n": 0}
    real = eng.process

    def counted(*a, **k):
        if k.get("analysis") is None and not k.get("analysis_only", False):
            counter["n"] += 1
        return real(*a, **k)

    eng.process = counted
    return counter


def check_quick():
    """
    The big window after the "light preview" change. Two engines get the same frame and the same actions:
      A (new way): every slider change only refreshes the preview (quick=True); the real frame is computed at Apply;
      B (old way): every slider change recomputes the real frame at once.
    Both must hand Photoshop exactly the same layer.
    """
    rng = np.random.default_rng(7100)
    bad = []
    n_steps = n_apply = n_quick = 0
    worst_col = worst_mask = 0.0
    worst_person = -1.0
    frames = [(2600, 1800, False, False, False), (1800, 2600, True, True, True)] + ([(3000, 2000, False, True, False)] if FULL else [])
    for (w, h, bit16, rgba, with_sel) in frames:
        img, sil = H.make_studio_image(w, h, seed=w + 7, bit16=bit16, rgba=rgba)
        bd = 16 if bit16 else 8
        sel = None
        if with_sel:
            sel = np.zeros((h, w), np.uint16 if bit16 else np.uint8)
            sel[h // 3:, : int(w * 0.85)] = 32768 if bit16 else 255
        A, B = H.make_engine(E, sil), H.make_engine(E, sil)
        full_a, full_b = _count_full_frames(A), _count_full_frames(B)
        p = dict(H.STD, speedMode="fast", cycCurve=40, dressSmooth=True, dressStrength=50, autoFractions=True)
        ra = _quiet(A.start_session, img, bd, dict(p), sel)
        rb = _quiet(B.start_session, img, bd, dict(p), sel)
        sa_id, sb_id = ra["session_id"], rb["session_id"]
        if A._active_session.get("proxy") is None:
            bad.append(f"{w}x{h}: no reduced copy was prepared for the light preview")
            continue
        tag = f"{w}x{h}/{bd}bit"

        def apply_both(label, params_for_a=None):
            nonlocal n_apply
            n_apply += 1
            oa, ma, sta = _quiet(A.apply_session, sa_id, 90.0, True, True, 50.0, None, params_for_a)
            ob, mb, stb = _quiet(B.apply_session, sb_id, 90.0, True, True, 50.0)
            if not (np.array_equal(oa, ob) and np.array_equal(ma, mb)):
                bad.append(f"{tag} {label}: the applied layer differs from the old way")
            if not np.array_equal(A._active_session["cleaned_base_rgba"], B._active_session["cleaned_base_rgba"]):
                bad.append(f"{tag} {label}: the real frame after Apply differs from the old way")
            return sta, stb

        # ---- 1. sliders, brush, eraser, then Apply: same layer as the old way
        for step in range(14 if FULL else 9):
            p = _mutate(p, rng)
            p["dressSmooth"], p["dressStrength"] = True, 50
            base_before = full_a["n"]
            qa = _quiet(A.recompute_session, sa_id, dict(p), True, None, True)
            qb = _quiet(B.recompute_session, sb_id, dict(p), True, None, False)
            n_steps += 1
            light = int(p.get("cleanPasses", 1)) < 2
            if qa["quick"] is not light or qb["quick"] is not False:
                bad.append(f"{tag} step {step}: answer quick={qa['quick']}/{qb['quick']}, expected {light}/False")
            if light:
                n_quick += 1
                if full_a["n"] != base_before:
                    bad.append(f"{tag} step {step}: a light refresh computed the real frame")
                sa, sb = A._active_session, B._active_session
                col = np.abs(sa["clean_base_small_bgr"].astype(np.int16) - sb["clean_base_small_bgr"].astype(np.int16))
                msk = np.abs(sa["auto_mask_small_u8"].astype(np.int16) - sb["auto_mask_small_u8"].astype(np.int16))
                worst_col, worst_mask = max(worst_col, float(col.mean())), max(worst_mask, float(msk.mean()))
                if col.mean() > 0.6 or np.percentile(col, 99) > 2 or msk.mean() > 3.0:
                    bad.append(f"{tag} step {step}: light preview is far from the exact one (colour mean {col.mean():.2f}, "
                               f"p99 {np.percentile(col, 99):.0f}; mask mean {msk.mean():.2f}) params={p}")
                # The person is not cleaned, so in the preview it must stay as sharp as in the original picture
                # (the clothing preview shows exactly these pixels). The exact preview is the yardstick.
                core = cv2.resize(sb["core_mask_u8"], (sa["preview_w"], sa["preview_h"]), interpolation=cv2.INTER_AREA) > 128
                if np.any(core):
                    orig_core = sa["orig_small_bgr"].astype(np.int16)[core]
                    off_a = float(np.abs(sa["clean_base_small_bgr"].astype(np.int16)[core] - orig_core).mean())
                    off_b = float(np.abs(sb["clean_base_small_bgr"].astype(np.int16)[core] - orig_core).mean())
                    worst_person = max(worst_person, off_a - off_b)
                    if off_a > off_b + 0.1:
                        bad.append(f"{tag} step {step}: the person in the light preview is off by {off_a:.2f} levels (exact preview: {off_b:.2f})")
            if qa["auto_fractions"] != qb["auto_fractions"]:
                bad.append(f"{tag} step {step}: automatic fractions differ")
            if step % 3 == 1:
                pts = [{"x": float(rng.uniform(0.1, 0.9)), "y": float(rng.uniform(0.1, 0.9)), "norm": 1} for _ in range(int(rng.integers(1, 4)))]
                erase = bool(rng.random() < 0.5)
                radius = float(rng.integers(12, 40))
                for eng_, sid_ in ((A, sa_id), (B, sb_id)):
                    eng_.edit_session_mask(sid_, "stroke", pts, radius, erase=erase, dress_smooth=True, dress_strength=50.0)
            if step % 4 == 3:
                before = full_a["n"]
                sta, _ = apply_both(f"apply after step {step}")
                if light and not (sta["recomputed"] is True and full_a["n"] == before + 1):
                    bad.append(f"{tag} step {step}: Apply after light refreshes must compute the real frame exactly once")
                before = full_a["n"]
                sta, _ = apply_both(f"second apply after step {step}")
                if sta["recomputed"] is not False or full_a["n"] != before:
                    bad.append(f"{tag} step {step}: a second Apply computed the real frame again")

        # ---- 2. sliders moved with no refresh at all: Apply carries the values
        for k in range(3):
            p = _mutate(_mutate(p, rng), rng)
            p["dressSmooth"], p["dressStrength"] = True, 50
            _quiet(B.recompute_session, sb_id, dict(p), True, None, False)
            before = full_a["n"]
            sta, _ = apply_both(f"apply with new settings #{k}", dict(p))
            if full_a["n"] - before > 1:
                bad.append(f"{tag} apply with new settings #{k}: more than one full computation")
            same = dict(p, dressStrength=77, dressSmooth=False, someUnknownKey=5)
            before = full_a["n"]
            sta, _ = apply_both(f"apply with the same settings #{k}", same)
            if sta["recomputed"] is not False or full_a["n"] != before:
                bad.append(f"{tag} apply with the same settings #{k}: the real frame was computed again")

        # ---- 3. the cost promise, counted
        if full_b["n"] <= full_a["n"]:
            bad.append(f"{tag}: the new way computed the real frame {full_a['n']} times, the old way {full_b['n']} times")

        # ---- 4. "invert + brush" makes the mask the user's own drawing: Apply must use exactly the one on screen
        p = dict(H.STD, speedMode="fast", spots=88, cycCurve=30)
        _quiet(A.recompute_session, sa_id, dict(p), False, None, True)
        A.edit_session_mask(sa_id, "invert")
        A.edit_session_mask(sa_id, "stroke", [{"x": 0.3, "y": 0.5, "norm": 1}, {"x": 0.5, "y": 0.55, "norm": 1}], 30.0, erase=False)
        shown = A._compute_effective_mask_small(A._active_session).copy()
        _, mask_a, sta = _quiet(A.apply_session, sa_id, 100.0, True, False, 0.0)
        n_apply += 1
        after = A._compute_effective_mask_small(A._active_session)
        ref = cv2.resize(shown, (w, h), interpolation=cv2.INTER_LINEAR)
        if sta["recomputed"] is not True or not np.array_equal(shown, after) or np.abs(mask_a.astype(np.int16) - ref.astype(np.int16)).max() > 1:
            bad.append(f"{tag}: after invert + brush the applied mask is not the one shown")
        A.close_session(sa_id)
        B.close_session(sb_id)

    # ---- 5. where there is no light way, the server says so and does the full recompute
    img, sil = H.make_studio_image(1500, 1000, seed=5)
    S = H.make_engine(E, sil)
    r = _quiet(S.start_session, img, 8, dict(H.STD, speedMode="fast"))
    q = _quiet(S.recompute_session, r["session_id"], dict(H.STD, speedMode="fast", blur=30), True, None, True)
    if S._active_session.get("proxy") is not None or q["quick"] is not False or S._active_session.get("base_stale"):
        bad.append("small frame: must be recomputed in full and say quick=False")

    # ---- 6. Apply notices every setting of the clean, and only those
    sig = ENG._clean_signature
    ref = sig(dict(H.STD, speedMode="fast"))
    for key, val in (("spots", 76), ("scuffs", 64), ("blur", 1), ("cycCurve", 1), ("feather", 61), ("seamOn", False), ("seam", 84),
                     ("edge", 71), ("smokeOn", False), ("smoke", 81), ("grain", 89), ("shadow", False), ("removeStands", True),
                     ("master", 101), ("speedMode", "quality"), ("fracFine", False), ("fracMed", False), ("fracLarge", False),
                     ("cleanPasses", 2), ("strayHair", 1), ("toneEdge", False), ("cornerHair", False)):
        changed = dict(H.STD, speedMode="fast")
        changed[key] = val
        if sig(changed) == ref:
            bad.append(f"Apply would not notice a change of '{key}'")
    for key, val in (("dressSmooth", True), ("dressStrength", 99), ("autoFractions", True), ("unknown", 1), ("master", 60), ("spots", 75.0)):
        changed = dict(H.STD, speedMode="fast")
        changed[key] = val
        if sig(changed) != ref:
            bad.append(f"Apply would recompute for '{key}', which does not change the clean")
    import inspect
    read_by_process = set(re.findall(r'params\.get\("(\w+)"', inspect.getsource(ENG.process)))
    in_signature = set(re.findall(r'(?:p\.get|fl)\("(\w+)"', inspect.getsource(sig)))
    missing = read_by_process - in_signature - {"dressSmooth", "dressStrength"}
    if missing or not read_by_process:
        bad.append(f"settings read by process() but unknown to Apply: {sorted(missing)}")

    report("quick", not bad,
           f"{n_steps} slider steps ({n_quick} light refreshes) + {n_apply} applies: same layer as full recomputes after every step; "
           f"a light refresh never computes the real frame, Apply computes it once; light preview differs from the exact one by "
           f"<= {worst_col:.2f} levels (mask <= {worst_mask:.2f})" if not bad else "DIFFERENT:\n  " + "\n  ".join(bad))


# ("dress_s", the clothing mask, is built differently on purpose - see check_dress)
SESSION_ARRAYS = ["cleaned_base_rgba", "auto_mask_small_u8", "clean_paint_small_bgr", "clean_base_small_bgr", "user_paint_u8",
                  "user_erase_u8", "core_mask_u8", "orig_small_bgr", "fg_raw_1024", "img_rgba_orig"]


def _session_state_diff(eo, en):
    so, sn = eo._active_session, en._active_session
    bad = [k for k in SESSION_ARRAYS if (so.get(k) is None) != (sn.get(k) is None) or (so.get(k) is not None and not np.array_equal(so[k], sn[k]))]
    if bool(so.get("inverted")) != bool(sn.get("inverted")):
        bad.append("inverted")
    if so["params"] != sn["params"]:
        bad.append("params")
    return bad


def _response_diff(ro, rn):
    bad = []
    for k in ro:
        if k in ("mask_png_b64", "session_id"):  # the unused mask PNG is no longer sent
            continue
        if k == "stats":
            if not _same_stats(ro[k], rn[k]):
                bad.append("stats")
        elif ro[k] != rn.get(k):
            bad.append(k)
    return bad


def check_session():
    if E_OLD is None:
        report("session", True, "SKIPPED - v3.2.1 is not available (tests/baseline_v321 is missing)")
        return
    rng = np.random.default_rng(5000)
    bad = []
    n_steps = n_apply = 0
    t_old = t_new = 0.0
    for qi in range(8 if FULL else 3):
        w, h = [(2000, 1500), (1500, 2000), (1777, 1333), (2600, 1731), (900, 700)][int(rng.integers(0, 5))]
        bit16, rgba, lowkey = bool(rng.random() < 0.4), bool(rng.random() < 0.6), bool(rng.random() < 0.3)
        img, sil = H.make_studio_image(w, h, n_dust=int(rng.integers(20, 150)), n_hair=int(rng.integers(0, 12)),
                                       seed=int(rng.integers(0, 10 ** 6)), bit16=bit16, rgba=rgba, lowkey=lowkey)
        sel = None
        if rng.random() < 0.3:
            sel = np.zeros((h, w), np.uint8)
            sel[h // 3:, : int(w * 0.8)] = 255
        p = _legacy_window(dict(H.STD, autoFractions=bool(rng.random() < 0.6)))
        eo, en = H.make_engine(E_OLD, sil), H.make_engine(E, sil)
        src = img.copy()
        src.setflags(write=False)
        bd = 16 if bit16 else 8
        t0 = time.perf_counter()
        ro = _quiet(eo.start_session, src, bd, dict(p), selection_alpha=None if sel is None else sel.copy())
        t1 = time.perf_counter()
        rn = _quiet(en.start_session, src, bd, dict(p), selection_alpha=None if sel is None else sel.copy())
        t_old, t_new = t_old + t1 - t0, t_new + time.perf_counter() - t1
        d = _response_diff(ro, rn) + _session_state_diff(eo, en)
        n_steps += 1
        if d:
            bad.append(f"sequence {qi} start: {d}")
        so, sn = ro["session_id"], rn["session_id"]
        sent = dict(p)
        for oi in range(18 if FULL else 12):
            op = str(rng.choice(["recompute", "recompute", "recompute", "paint", "paint", "erase", "fill", "clear",
                                 "invert", "reset_auto", "dress", "apply", "apply"]))
            d = []
            if op == "recompute":
                sent = _legacy_window(_mutate(sent, rng))
                keep = bool(rng.random() < 0.8)
                t0 = time.perf_counter()
                ro = _quiet(eo.recompute_session, so, dict(sent), keep)
                t1 = time.perf_counter()
                rn = _quiet(en.recompute_session, sn, dict(sent), keep)
                t_old, t_new = t_old + t1 - t0, t_new + time.perf_counter() - t1
                d = _response_diff(ro, rn) + _session_state_diff(eo, en)
            elif op in ("paint", "erase"):
                pts = [{"x": float(rng.random()), "y": float(rng.random()), "norm": 1} for _ in range(int(rng.integers(1, 6)))]
                rad, ds = float(rng.integers(4, 60)), False
                ro = eo.edit_session_mask(so, "stroke", pts, rad, erase=(op == "erase"), dress_smooth=ds, dress_strength=50.0)
                rn = en.edit_session_mask(sn, "stroke", pts, rad, erase=(op == "erase"), dress_smooth=ds, dress_strength=50.0)
                d = _response_diff(ro, rn) + _session_state_diff(eo, en)
            elif op in ("fill", "clear", "invert", "reset_auto"):
                d = _response_diff(eo.edit_session_mask(so, op), en.edit_session_mask(sn, op)) + _session_state_diff(eo, en)
            elif op == "dress":
                val = float(rng.integers(0, 100))
                d = _response_diff(eo.dress_preview_session(so, False, val), en.dress_preview_session(sn, False, val))
            else:
                mk, ds = bool(rng.random() < 0.5), False
                val, blend = float(rng.integers(10, 100)), float(rng.integers(0, 101))
                with H.fixed_fast_inpaint(eo):  # v3.2.1 with only the white-patch line corrected
                    oo, mo, sto = _quiet(eo.apply_session, so, blend, mk, ds, val)
                on_, mn, stn = _quiet(en.apply_session, sn, blend, mk, ds, val)
                n_apply += 1
                if not np.array_equal(oo, on_):
                    d.append("layer pixels")
                if (mo is None) != (mn is None) or (mo is not None and not np.array_equal(mo, mn)):
                    d.append("layer mask")
                d += [k for k in ("changed_px", "make_mask", "dress_smooth", "blend") if sto[k] != stn[k]]
                d += _session_state_diff(eo, en)
            n_steps += 1
            if d:
                bad.append(f"sequence {qi} step {oi} ({op}): {d}")
    report("session", not bad, f"{n_steps} interactive steps ({n_apply} applies, legacy regime) identical to v3.2.1 "
                               f"(open + recompute time {t_old:.1f}s -> {t_new:.1f}s)" if not bad else "DIFFERENT:\n  " + "\n  ".join(bad))


def check_white():
    """Brush a zone the automatic mask did not cover, press Apply in fast mode: the zone must not turn white."""
    img, sil = H.make_studio_image(1500, 1000, n_dust=40, n_hair=3, seed=9)
    counts = {}
    for name, mod in (("v3.2.1", E_OLD), ("current", E)):
        if mod is None:
            continue
        eng = H.make_engine(mod, sil)
        p = dict(H.STD, speedMode="fast", spots=0, scuffs=0, seamOn=False)  # empty automatic mask
        sid = _quiet(eng.start_session, img, 8, dict(p))["session_id"]
        eng.edit_session_mask(sid, "stroke", [{"x": 0.15, "y": 0.3, "norm": 1}, {"x": 0.3, "y": 0.35, "norm": 1}], 25.0, erase=False)
        out, _, _ = _quiet(eng.apply_session, sid, 100.0, False, False, 45.0)
        zone = out[:, :, 3] > 128
        counts[name] = (int((out[:, :, :3][zone].min(axis=1) >= 250).sum()), int(zone.sum()),
                        float(out[:, :, :3][zone].mean()), float(img[zone].mean()))
    white, total, mean_out, mean_src = counts["current"]
    ok = white == 0 and total > 1000 and abs(mean_out - mean_src) < 12
    extra = f"; v3.2.1 produced {counts['v3.2.1'][0]} white pixels there" if "v3.2.1" in counts else ""
    report("white", ok, f"brushed zone after Apply: {white} white pixels of {total}, brightness {mean_src:.0f} -> {mean_out:.0f}{extra}")


# ----------------------------------------------------------------------------------------------------------------------
# Part 2: what this program does differently from v3.2.1
# ----------------------------------------------------------------------------------------------------------------------
def _comp(src, out):
    """What Photoshop shows after the result layer is put over the photo (8-bit frames), as float levels."""
    a = out[:, :, 3:4].astype(np.float32) / 255.0
    return src[:, :, :3].astype(np.float32) * (1.0 - a) + out[:, :, :3].astype(np.float32) * a


def _step(img, rows, cols, span=12):
    """Largest change of the mean brightness between rows `span` apart inside a column band: a line across it."""
    g = img[rows, cols].astype(np.float32).mean(axis=(1, 2))
    return float(np.abs(g[span:] - g[:-span]).max())


def _plain_frame(w, h, seed=0, person=True):
    """A backdrop without a wall-floor corner (soft lighting only), with the usual 'person' in the middle or empty."""
    rng = np.random.default_rng(seed)
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    xx = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    lum = 150.0 * (1.0 - 0.22 * ((xx - 0.5) * 2) ** 2 - 0.15 * ((yy - 0.45) * 2) ** 2) + 25.0 * yy
    img = np.clip(lum[..., None] * np.float32([1.02, 1.0, 0.97]) + rng.standard_normal((h, w, 3)).astype(np.float32) * 1.8, 0, 255).astype(np.uint8)
    _, sil = H.make_studio_image(w, h, n_dust=0, n_hair=0, seed=1)
    if not person:
        return img, np.zeros_like(sil)
    img[cv2.resize(sil, (w, h)) > 0.5] = (40, 40, 46)
    return img, sil


def _two_line_frame(w, h, level=18.6, upper=0.59, lower=0.77, drop=3.3, lit=14.0, seed=11, noise=1.1, person=(70, 62, 58)):
    """
    A backdrop of brightness `level` with two lines across it:
      at `upper` of the height a faint step - the backdrop right below it is `drop` levels darker and slowly climbs
      back (nine tenths of the step within one percent of the height);
      at `lower` a sharp strong one, `lit` levels up, a little tilted.
    level 18.6, drop 3.3, lit 14: the owner's black backdrop - the upper line is the wall-floor corner (3.4 levels on
    his frame), the lower one the rim of a pool of light, four times as strong.
    A light `level`: the lower line is the corner, the upper one a faint line across the wall.
    Returns (frame, silhouette 1024).
    """
    rng = np.random.default_rng(seed)
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    xx = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    fall = 1.0 - 0.10 * ((xx - 0.5) * 2) ** 2
    t = 1.0 / (1.0 + np.exp(-np.clip((yy - upper) * 400.0, -50, 50)))
    below = level - drop + 1.35 * drop * np.clip((yy - upper) / (lower - upper), 0.0, 1.0)
    lum = (level * (1 - t) + below * t) * fall
    edge_y = lower + 0.010 * (xx - 0.5)
    lum = lum + lit * (1.0 / (1.0 + np.exp(-np.clip((yy - edge_y) * 500.0, -50, 50)))) * (1.0 + 0.6 * np.clip((yy - lower) / (1.0 - lower), 0.0, 1.0))
    lum = np.broadcast_to(lum, (h, w)).astype(np.float32)
    img = lum[..., None] * np.float32([1.02, 1.0, 0.97])
    img = img + (rng.standard_normal((h, w, 1)).astype(np.float32) + 0.25 * rng.standard_normal((h, w, 3)).astype(np.float32)) * noise
    _, sil = H.make_studio_image(w, h, n_dust=0, n_hair=0, seed=1)
    img = np.clip(img, 0, 255)
    img[cv2.resize(sil, (w, h)) > 0.5] = person
    return img.astype(np.uint8), sil


def _across(img, y, cols, gap=0.012, tall=0.02):
    """Mean brightness just below the height `y` minus just above it, in a column band (levels)."""
    h = img.shape[0]
    g = img[:, cols].astype(np.float32).mean(axis=(1, 2))
    return float(g[int(h * (y + gap)):int(h * (y + gap + tall))].mean() - g[int(h * (y - gap - tall)):int(h * (y - gap))].mean())


def check_cyc():
    bad = []
    off = dict(H.STD, spots=0, scuffs=0, seamOn=False, blur=0)
    notes = []
    for (w, h, mode) in ((1500, 2000, "quality"), (2000, 1500, "fast")):
        img, sil = H.make_studio_image(w, h, n_dust=0, n_hair=0, seed=3)
        eng = H.make_engine(E, sil)
        base = _comp(img, _quiet(eng.process, img, 8, dict(off, speedMode=mode, cycCurve=0))[0])
        rows = slice(int(h * 0.50), int(h * 0.74))  # the corner of this frame is at 0.62 of the height
        bands = [slice(int(w * 0.04), int(w * 0.24)), slice(int(w * 0.76), int(w * 0.96))]
        before = [_step(base, rows, b) for b in bands]
        person = cv2.resize(sil, (w, h)) > 0.9
        for strength, limit in ((30, 0.75), (60, 0.35), (100, 0.30)):
            comp = _comp(img, _quiet(eng.process, img, 8, dict(off, speedMode=mode, cycCurve=strength))[0])
            after = [_step(comp, rows, b) for b in bands]
            if strength == 60:
                notes.append(f"{mode}: step {max(before):.1f} -> {max(after):.1f} levels")
            if max(a / b for a, b in zip(after, before)) > limit:
                bad.append(f"{w}x{h} {mode} strength {strength}: line step {before} -> {after}")
            if float(np.abs(comp - base)[person].max()) > 0.0:
                bad.append(f"{w}x{h} {mode} strength {strength}: the person was changed")
            far = np.r_[0:int(h * 0.12), int(h * 0.985):h]
            if float(np.abs(comp - base)[far].max()) > 0.51:
                bad.append(f"{w}x{h} {mode} strength {strength}: changed far from the corner")
            if float(np.abs(comp - base).max()) > 40.0:
                bad.append(f"{w}x{h} {mode} strength {strength}: a pixel moved by {np.abs(comp - base).max():.0f} levels")
        # the same frame in 16 bit
        img16 = (img.astype(np.uint16) * 128)
        out16 = _quiet(eng.process, img16, 16, dict(off, speedMode=mode, cycCurve=60))[0]
        if out16.dtype != np.uint16 or int(out16[:, :, 3].max()) == 0:
            bad.append(f"{w}x{h} {mode}: 16-bit frame not processed")
        # a backdrop without a corner must stay exactly as it is
        flat, sil2 = _plain_frame(w, h, seed=w)
        eng2 = H.make_engine(E, sil2)
        a0 = _comp(flat, _quiet(eng2.process, flat, 8, dict(off, speedMode=mode, cycCurve=0))[0])
        a1 = _comp(flat, _quiet(eng2.process, flat, 8, dict(off, speedMode=mode, cycCurve=100))[0])
        if float(np.abs(a1 - a0).max()) > 0.0:
            bad.append(f"{w}x{h} {mode}: a frame without a corner was changed by {np.abs(a1 - a0).max():.1f} levels")
    # "Clean inside the selection": the corner goes only when the selection holds the whole line. A selection that
    # holds a part of it must leave the corner alone - a line bent on one side of the selection border only is worse.
    w, h = 1500, 2000
    img, sil = H.make_studio_image(w, h, n_dust=0, n_hair=0, seed=3)
    rows = slice(int(h * 0.50), int(h * 0.74))
    left, right = slice(int(w * 0.04), int(w * 0.24)), slice(int(w * 0.76), int(w * 0.96))
    whole = np.zeros((h, w), np.uint8)
    whole[int(h * 0.30):int(h * 0.95)] = 255             # all of the line, most of the frame
    part = np.zeros((h, w), np.uint8)
    part[int(h * 0.30):int(h * 0.95), : int(w * 0.40)] = 255  # only its left end
    eng = H.make_engine(E, sil)
    p60 = dict(off, speedMode="fast", cycCurve=60)
    c_whole = _comp(img, _quiet(eng.process, img, 8, dict(p60), selection_alpha=whole)[0])
    out_part, st_part = _quiet(eng.process, img, 8, dict(p60), selection_alpha=part)
    c_part = _comp(img, out_part)
    before = [_step(img, rows, b) for b in (left, right)]
    after_whole = [_step(c_whole, rows, b) for b in (left, right)]
    after_part = [_step(c_part, rows, b) for b in (left, right)]
    if max(a / b for a, b in zip(after_whole, before)) > 0.40:
        bad.append(f"a selection that holds the whole corner: line step {before} -> {after_whole}")
    if min(a / b for a, b in zip(after_part, before)) < 0.95 or st_part.get("corner_row") is not None or int(out_part[:, :, 3].max()) != 0:
        bad.append(f"a selection that holds a part of the corner must leave it alone: line step {before} -> {after_part}, corner_row {st_part.get('corner_row')}")

    # A black backdrop: the corner is a faint step, and lower on the floor runs something four times as strong and
    # as sharp - the rim of a pool of light, the shadow of a stool. Version 4.5.0 took that for the corner and bent
    # the light there; the corner itself stayed. The corner is the upper line, however faint next to the other.
    # (drop 1.9: as faint to the finder as the corner of the owner's frame, score 0.26)
    sides = (slice(int(w * 0.04), int(w * 0.24)), slice(int(w * 0.76), int(w * 0.96)))
    for drop in (3.3, 1.9):
        dark, sil_d = _two_line_frame(w, h, drop=drop)
        for mode in ("fast", "quality"):
            out, st = _quiet(H.make_engine(E, sil_d).process, dark, 8, dict(off, smokeOn=False, speedMode=mode, cycCurve=65))
            comp = _comp(dark, out)
            row = st.get("corner_row")
            corner = [(_across(dark, 0.59, c), _across(comp, 0.59, c)) for c in sides]
            rim = [(_across(dark, 0.77, c), _across(comp, 0.77, c)) for c in sides]
            if row is None or abs(row - 0.59) > 0.012:
                bad.append(f"black backdrop, corner of {drop} levels at 0.59, rim of a pool of light at 0.77 ({mode}): the corner was looked for at {row}")
            elif max(abs(a) / abs(b) for b, a in corner) > 0.55:
                bad.append(f"black backdrop ({drop} levels, {mode}): the corner step went {corner} (before, after) - not removed")
            if max(abs(a - b) for b, a in rim) > 0.08 * abs(rim[0][0]):
                bad.append(f"black backdrop ({drop} levels, {mode}): the rim of the pool of light was changed: {rim} (before, after)")
            if drop == 3.3 and mode == "fast" and row is not None:
                notes.append(f"black backdrop: faint corner found at {row:.3f} above a rim of light 4x as strong, step {corner[0][0]:.1f} -> {corner[0][1]:.1f}")
    # ...but only where such a faint line can be seen at all. On a light backdrop a line of 5 levels across the wall
    # is nothing next to the corner, and the corner stays the corner (exactly as before).
    light, sil_l = _two_line_frame(w, h, level=150.0, upper=0.45, lower=0.62, drop=5.0, lit=22.0, noise=1.8, person=(40, 40, 46))
    out, st = _quiet(H.make_engine(E, sil_l).process, light, 8, dict(off, smokeOn=False, speedMode="fast", cycCurve=65))
    comp = _comp(light, out)
    row = st.get("corner_row")
    if row is None or abs(row - 0.62) > 0.012 or max(abs(_across(comp, 0.45, c) - _across(light, 0.45, c)) for c in sides) > 0.3:
        bad.append(f"light backdrop with a faint line across the wall at 0.45: the corner (at 0.62) was looked for at {row}")
    report("cyc", not bad, "cyclorama removes the wall-floor line (" + "; ".join(notes) + "), person untouched, no corner -> no change; "
                           "inside a selection only when it holds the whole line" if not bad else "wrong:\n  " + "\n  ".join(bad))


def _garment_frame(w=1400, h=2000, seed=5):
    """
    A 'person' in a smooth blue dress with a pair of jeans-like trousers under it. Returns the frame and the
    separate ingredients, so that every promise of the ironing can be measured on its own.
    """
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    img = np.full((h, w, 3), 118.0, np.float32)
    core = np.zeros((h, w), np.uint8)
    cx = w // 2
    cv2.ellipse(core, (cx, int(h * 0.15)), (int(w * 0.07), int(h * 0.055)), 0, 0, 360, 255, -1)   # head
    cv2.rectangle(core, (cx - int(w * 0.22), int(h * 0.20)), (cx + int(w * 0.22), int(h * 0.93)), 255, -1)
    dress = np.zeros((h, w), bool)
    dress[int(h * 0.20):int(h * 0.66), cx - int(w * 0.22):cx + int(w * 0.22)] = True
    denim = np.zeros((h, w), bool)
    denim[int(h * 0.66):int(h * 0.93), cx - int(w * 0.22):cx + int(w * 0.22)] = True
    volume = 0.55 + 0.45 * np.cos((xx - cx) / (w * 0.22) * 1.35)            # the roundness of the body
    wrinkles = np.zeros((h, w), np.float32)
    for _ in range(70):                                                         # many shallow creases
        x0, y0 = rng.integers(cx - int(w * 0.20), cx + int(w * 0.20)), rng.integers(int(h * 0.24), int(h * 0.63))
        ang, length = rng.uniform(0, np.pi), rng.uniform(60, 220)
        x1, y1 = int(x0 + np.cos(ang) * length), int(y0 + np.sin(ang) * length)
        layer = np.zeros((h, w), np.float32)
        cv2.line(layer, (int(x0), int(y0)), (x1, y1), 1.0, int(rng.integers(3, 8)), cv2.LINE_AA)
        wrinkles += cv2.GaussianBlur(layer, (0, 0), float(rng.uniform(2.0, 4.0))) * float(rng.choice([-1, 1]) * rng.uniform(0.04, 0.08))
    fold = np.zeros((h, w), np.float32)                                         # one deep fold: part of the shape
    cv2.line(fold, (cx - int(w * 0.18), int(h * 0.50)), (cx + int(w * 0.12), int(h * 0.30)), 1.0, 9, cv2.LINE_AA)
    fold = cv2.GaussianBlur(fold, (0, 0), 4.0) * -0.45
    weave = rng.standard_normal((h, w)).astype(np.float32) * 0.012               # fine texture of the cloth
    clean_dress = np.float32([70, 125, 190])[None, None, :] * volume[..., None]
    dress_px = clean_dress * (1.0 + wrinkles + fold + weave)[..., None]
    img[dress] = dress_px[dress]
    jeans = np.float32([52, 70, 105])[None, None, :] * (volume * (1.0 + rng.standard_normal((h, w)).astype(np.float32) * 0.14))[..., None]
    img[denim] = jeans[denim]
    head = core.astype(bool) & (yy < h * 0.20)
    img[head] = (205, 160, 135)
    img += rng.standard_normal((h, w, 3)).astype(np.float32) * 1.5
    img_u8 = np.clip(img, 0, 255).astype(np.uint8)
    return img_u8, core, dict(dress=dress, denim=denim, head=head, wrinkles=wrinkles, fold=fold, clean=clean_dress)


def check_dress():
    bad = []
    img, core, g = _garment_frame()
    h, w = img.shape[:2]
    sc = 1024.0 / max(h, w)
    small = cv2.resize(img, (int(round(w * sc)), int(round(h * sc))), interpolation=cv2.INTER_AREA)
    mask = ENG._build_dress_mask_small(small, core, max_dim=1024, tex_rms=ENG._fabric_texture_small(img))
    m_full = cv2.resize(mask, (w, h), interpolation=cv2.INTER_LINEAR)
    inner = cv2.erode(g["dress"].astype(np.uint8), np.ones((61, 61), np.uint8)) > 0
    inner_denim = cv2.erode(g["denim"].astype(np.uint8), np.ones((61, 61), np.uint8)) > 0
    if float(m_full[inner].mean()) < 0.9:
        bad.append(f"smooth cloth is not in the clothing mask ({m_full[inner].mean():.2f})")
    if float(m_full[inner_denim].mean()) > 0.15:
        bad.append(f"denim is in the clothing mask ({m_full[inner_denim].mean():.2f})")
    outside = cv2.dilate(core, np.ones((9, 9), np.uint8)) == 0       # the backdrop
    head_in = cv2.erode(g["head"].astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
    if float(m_full[head_in].max()) > 0.05 or float(m_full[outside].max()) > 0.0:
        bad.append("head or backdrop is in the clothing mask")

    f0 = img.astype(np.float32) / 255.0
    same, alpha0 = ENG._smooth_dress_fabric(f0.copy(), mask, 0.0)
    if not np.array_equal(same, f0) or float(alpha0.max()) != 0.0:
        bad.append("strength 0 changed the picture")

    def amount(image, field, where):
        """How much of a known streak pattern is present in the picture (1 = as drawn, 0 = gone)."""
        resid = np.log(image[:, :, 1] + 0.02) - np.log(g["clean"][:, :, 1] / 255.0 + 0.02)
        f = np.log1p(field)
        resid = resid - cv2.GaussianBlur(resid, (0, 0), 25)
        f = f - cv2.GaussianBlur(f, (0, 0), 25)
        return float((resid[where] * f[where]).sum() / (f[where] * f[where]).sum())

    near_fold = cv2.dilate((np.abs(g["fold"]) > 0.02).astype(np.uint8), np.ones((41, 41), np.uint8)) > 0
    crease_zone = inner & ~near_fold
    fold_zone = inner & (np.abs(g["fold"]) > 0.05)
    notes = []
    prev = amount(f0, g["wrinkles"], crease_zone)
    for strength, max_left in ((40, 0.80), (80, 0.55), (120, 0.45)):
        out, alpha = ENG._smooth_dress_fabric(f0.copy(), mask, float(strength))
        left = amount(out, g["wrinkles"], crease_zone) / amount(f0, g["wrinkles"], crease_zone)
        fold_left = amount(out, g["fold"], fold_zone) / amount(f0, g["fold"], fold_zone)
        notes.append(f"{strength}: creases x{left:.2f}, deep fold x{fold_left:.2f}")
        if left > max_left:
            bad.append(f"strength {strength}: {left:.2f} of the creases left (limit {max_left})")
        if left > prev + 0.02:
            bad.append(f"strength {strength} irons less than a weaker setting")
        prev = left
        if fold_left < 0.70:
            bad.append(f"strength {strength}: the deep fold was flattened to {fold_left:.2f}")
        diff = (out - f0) * 255.0
        # volume and light: the broad picture of the garment stays
        broad = np.abs(cv2.GaussianBlur(diff, (0, 0), 45))[inner].max()
        if broad > 1.5:
            bad.append(f"strength {strength}: broad brightness of the garment moved by {broad:.1f} levels")
        # colour: all three channels get the same factor
        ratio = (out[inner] + 0.02) / (f0[inner] + 0.02)
        if float(np.abs(ratio - ratio[:, 1:2]).max()) > 1e-4:
            bad.append(f"strength {strength}: the colour changed")
        # fine texture and grain stay
        hp = lambda x: x[:, :, 1] - cv2.GaussianBlur(x[:, :, 1], (0, 0), 1.2)
        tex = float(hp(out)[crease_zone].std() / hp(f0)[crease_zone].std())
        if not 0.95 < tex < 1.05:
            bad.append(f"strength {strength}: fine texture x{tex:.2f}")
        # everything that is not smooth cloth stays exactly
        if float(np.abs(diff)[core == 0].max()) > 0.0 or float(np.abs(diff)[g["head"]].max()) > 0.0:
            bad.append(f"strength {strength}: backdrop or head changed "
                       f"({np.abs(diff)[core == 0].max():.2f} / {np.abs(diff)[g['head']].max():.2f} levels)")
        if float(np.abs(diff)[inner_denim].mean()) > 0.15:
            bad.append(f"strength {strength}: denim changed by {np.abs(diff)[inner_denim].mean():.2f} levels on average")
        if float(alpha[np.abs(diff).max(axis=2) > 1.0].min(initial=1.0)) < 0.15:
            bad.append(f"strength {strength}: a changed pixel is not covered by the layer alpha")
    # the live preview (small copy) and the full-size result must look alike
    prev_small = cv2.resize(img, (w * 1080 // h, 1080), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    out_small, _ = ENG._smooth_dress_fabric(prev_small.copy(), mask, 80.0, fast_mode=True)
    out_full, _ = ENG._smooth_dress_fabric(f0.copy(), mask, 80.0)
    d_small = (out_small - prev_small)[:, :, 1]
    d_full = cv2.resize((out_full - f0)[:, :, 1], (d_small.shape[1], d_small.shape[0]), interpolation=cv2.INTER_AREA)
    sel = cv2.resize(crease_zone.astype(np.uint8), (d_small.shape[1], d_small.shape[0])) > 0
    corr = float(np.corrcoef(d_small[sel], d_full[sel])[0, 1])
    if corr < 0.75:
        bad.append(f"preview and full-size ironing disagree (correlation {corr:.2f})")
    report("dress", not bad, "clothing: " + "; ".join(notes) + f"; volume, colour, texture, denim, head, backdrop kept; preview~final {corr:.2f}"
           if not bad else "wrong:\n  " + "\n  ".join(bad))


def check_speed():
    bad = []
    n = 0
    for (w, h, seed) in ((1500, 2000, 11), (2000, 1500, 12)) + (((2600, 1731, 13),) if FULL else ()):
        img, sil = H.make_studio_image(w, h, n_dust=140, n_hair=10, seed=seed, lowkey=(seed == 12))
        marks = {}
        for mode in ("fast", "quality"):
            eng = H.make_engine(E, sil)
            oc = {}
            _, st = _quiet(eng.process, img, 8, dict(H.STD, speedMode=mode), out_cache=oc)
            marks[mode] = (oc["heal_mask_full"] > 0, st["seam_px"], st["spot_px"])
        n += 1
        if not np.array_equal(marks["fast"][0], marks["quality"][0]) or marks["fast"][1:] != marks["quality"][1:]:
            bad.append(f"{w}x{h}: fast marks {int(marks['fast'][0].sum())} px, quality {int(marks['quality'][0].sum())} px")
        if int(marks["fast"][0].sum()) < 500:
            bad.append(f"{w}x{h}: almost nothing was found on a dusty frame")
        # the green preview shows the very same marks
        eng = H.make_engine(E, sil)
        green, _ = _quiet(eng.preview_action_mask, img, 8, dict(H.STD, speedMode="fast"))
        heal = marks["quality"][0]
        missed = int((heal & (green == 0)).sum())
        extra = int(((green > 0) & (cv2.dilate(heal.astype(np.uint8), np.ones((3, 3), np.uint8)) == 0)).sum())
        if missed or extra:
            bad.append(f"{w}x{h}: green preview differs from the cleaning ({missed} px not shown, {extra} px shown but not cleaned)")
    report("speed", not bad, f"{n} frames: the full fill (the only mode of the panel since 4.7.0), the fast fill (the light preview draws with it) and the green preview mark the same defects" if not bad else "wrong:\n  " + "\n  ".join(bad))


def check_smoke():
    bad = []
    w, h = 1500, 2000
    rng = np.random.default_rng(21)
    img, sil = H.make_studio_image(w, h, n_dust=0, n_hair=0, seed=21)
    # soft wisps, like real smoke (hard-edged noise would be taken for cables and stands by both versions)
    wisps = cv2.GaussianBlur(rng.standard_normal((h, w)).astype(np.float32), (0, 0), 10.0)
    wisps *= 6.0 / float(wisps.std())
    cloud = np.zeros((h, w), np.float32)
    cv2.ellipse(cloud, (int(w * 0.17), int(h * 0.30)), (int(w * 0.13), int(h * 0.16)), 0, 0, 360, 1.0, -1)
    cloud = cv2.GaussianBlur(cloud, (0, 0), 25)
    smoky = np.clip(img.astype(np.float32) + (wisps * cloud)[..., None], 0, 255).astype(np.uint8)

    def smoke_map(mod, image, silhouette):
        eng = H.make_engine(mod, silhouette)
        fg, corem = eng._clean_fg_mask(np.clip(silhouette * 255, 0, 255).astype(np.uint8), w, h, 70.0)
        sm = eng._compute_protection_maps_small(image, fg, corem, 80.0, True, True)[2]
        return cv2.resize(sm, (w, h), interpolation=cv2.INTER_LINEAR) > 100, fg

    new_plain, fg = smoke_map(E, img, sil)
    # the strip of backdrop right next to the person, above the floor shadow (a shadow is structure of its own)
    near = (cv2.dilate((fg > 22).astype(np.uint8), np.ones((121, 121), np.uint8)) > 0) & (fg < 8)
    near[int(h * 0.60):] = False
    ring_new = float(new_plain[near].mean())
    if ring_new > 0.03:
        bad.append(f"no smoke in the frame, yet {ring_new * 100:.0f}% of the backdrop next to the person is 'smoke'")
    new_smoky, _ = smoke_map(E, smoky, sil)
    in_cloud = cloud > 0.6
    got = float(new_smoky[in_cloud].mean())
    if got < 0.8:
        bad.append(f"only {got * 100:.0f}% of a real smoke cloud is protected")
    note = f"ring around the person {ring_new * 100:.1f}%, smoke cloud protected {got * 100:.0f}%"
    if E_OLD is not None:
        old_plain, _ = smoke_map(E_OLD, img, sil)
        old_smoky, _ = smoke_map(E_OLD, smoky, sil)
        note += f" (v3.2.1: ring {old_plain[near].mean() * 100:.0f}%, cloud {old_smoky[in_cloud].mean() * 100:.0f}%)"
        if got < 0.9 * float(old_smoky[in_cloud].mean()):
            bad.append("smoke is protected worse than in v3.2.1")
        # a frame with smoke and nobody in it: nothing may differ from v3.2.1
        bare, nobody = _plain_frame(w, h, seed=22, person=False)
        bare = np.clip(bare.astype(np.float32) + (wisps * cloud)[..., None], 0, 255).astype(np.uint8)
        a, _ = smoke_map(E, bare, nobody)
        b, _ = smoke_map(E_OLD, bare, nobody)
        if float(a[in_cloud].mean()) < 0.8 or float((a != b).mean()) > 0.0005:
            bad.append(f"frame without people: smoke map differs from v3.2.1 on {(a != b).mean() * 100:.2f}% of the pixels")

    # The automatic mode ("smokeAuto", asked for by the plugin): smoke is protected only when the frame has smoke.
    # A dirty floor gives small mottled patches that look like thin smoke; protecting them keeps exactly the dirt.
    dirt = np.zeros((h, w), np.float32)
    cv2.ellipse(dirt, (int(w * 0.30), int(h * 0.93)), (int(w * 0.06), int(h * 0.022)), 0, 0, 360, 1.0, -1)
    cv2.ellipse(dirt, (int(w * 0.72), int(h * 0.95)), (int(w * 0.055), int(h * 0.020)), 0, 0, 360, 1.0, -1)
    dirt = cv2.GaussianBlur(dirt, (0, 0), 12)
    dirty = np.clip(img.astype(np.float32) + (wisps * dirt)[..., None], 0, 255).astype(np.uint8)

    def texture(a, zone, band=(4.0, 20.0)):
        g = a.astype(np.float32).mean(axis=2)
        mid = cv2.GaussianBlur(g, (0, 0), band[0]) - cv2.GaussianBlur(g, (0, 0), band[1])
        return float(np.sqrt((mid[zone > 0.6] ** 2).mean()))

    def cleaned(frame, zone, band=(4.0, 20.0), **over):
        eng = H.make_engine(E, sil)
        out, stats = _quiet(eng.process, frame, 8, dict(H.STD, spots=0, seamOn=False, speedMode="fast", **over))
        return stats.get("smoke") or {}, texture(_comp(frame, out), zone, band) / texture(frame, zone, band)

    sm, kept = cleaned(dirty, dirt, smokeAuto=True)
    if sm.get("found") is not False or sm.get("protected") != 0.0 or sm.get("on") is not True or sm.get("auto") is not True or kept > 0.7:
        bad.append(f"dirty floor, automatic mode: {sm}, {kept * 100:.0f}% of the dirt left")
    note += f"; automatic mode: dirty patches are cleaned ({kept * 100:.0f}% left"
    sm, kept = cleaned(dirty, dirt)
    if not (sm.get("protected", 0) > 0.01) or sm.get("auto") is not False or kept < 0.95:
        bad.append(f"dirty floor without the automatic mode must behave as before (everything smoke-like kept): {sm}, {kept * 100:.0f}% left")
    note += f", without it {kept * 100:.0f}%)"
    sm, kept = cleaned(dirty, dirt, smokeAuto=True, smoke=ENG.SMOKE_ALWAYS_FROM)
    if not (sm.get("protected", 0) > 0.01) or sm.get("auto") is not False or kept < 0.95:
        bad.append(f"slider at {ENG.SMOKE_ALWAYS_FROM:.0f}: smoke must be protected without asking for evidence: {sm}, {kept * 100:.0f}% left")
    sm, kept = cleaned(smoky, cloud, smokeAuto=True)
    if sm.get("found") is not True or not (sm.get("protected", 0) > 0.05) or kept < 0.95:
        bad.append(f"a real cloud, automatic mode: {sm}, {kept * 100:.0f}% of its texture left")
    note += f", a real cloud is kept ({kept * 100:.0f}%)"
    sm, kept = cleaned(smoky, cloud, smokeAuto=True, smokeOn=False)
    if sm.get("on") is not False or sm.get("found") is not True or sm.get("protected") != 0.0 or kept > 0.8:
        bad.append(f"a real cloud, protection off: {sm}, {kept * 100:.0f}% of its texture left")
    # the window says what it saw: with the first scan and with every refresh
    eng = H.make_engine(E, sil)
    win = dict(H.STD, speedMode="fast", smokeAuto=True)
    r1 = _quiet(eng.start_session, smoky, 8, dict(win))
    r2 = _quiet(eng.recompute_session, r1["session_id"], dict(win, smokeOn=False), True, None, True)
    r3 = _quiet(eng.recompute_session, r1["session_id"], dict(win, smokeOn=False), True, None, False)
    s1, s2, s3 = r1.get("smoke") or {}, r2.get("smoke") or {}, r3.get("smoke") or {}
    if s1.get("found") is not True or not (s1.get("protected", 0) > 0.05) or r1["scene"].get("smoke") != s1 or r1["stats"].get("smoke") != s1:
        bad.append(f"the window must say that smoke was found and protected: {s1}")
    if s2.get("on") is not False or s2.get("protected") != 0.0 or s2.get("found") is not True or s3 != s2:
        bad.append(f"after the protection is switched off the window must say so (light and full refresh alike): {s2} / {s3}")

    # ---- The smoke switch as the user's word ("smokeFaint", sent by the plugin since 4.11.0) ----
    # His report on 4.10.0: on a light backdrop the program knows the smoke where there is much of it and not where
    # there is little, and "I press that there is smoke and it says no, there is none".
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)

    def billows(seed_b, sigma=22.0, std=2.0):   # thin smoke: soft billows of two levels, no fine wisps
        b = cv2.GaussianBlur(np.random.default_rng(seed_b).standard_normal((h, w)).astype(np.float32), (0, 0), sigma)
        return b * (std / float(b.std()))

    def oval(cx, cy, rx, ry, soft):
        m = np.zeros((h, w), np.float32)
        cv2.ellipse(m, (int(w * cx), int(h * cy)), (int(w * rx), int(h * ry)), 0, 0, 360, 1.0, -1)
        return cv2.GaussianBlur(m, (0, 0), soft)

    def with_smoke(pattern, zone):
        return np.clip(img.astype(np.float32) + (pattern * zone)[..., None], 0, 255).astype(np.uint8)

    def word_map(image, strength=80.0):
        """The smoke map with the switch taken on trust, at the size of the frame."""
        eng_w = H.make_engine(E, sil)
        fg_w, core_w = eng_w._clean_fg_mask(np.clip(sil * 255, 0, 255).astype(np.uint8), w, h, 70.0)
        sm_w = eng_w._compute_protection_maps_small(image, fg_w, core_w, float(strength), True, True, smoke_faint=True)[2]
        return cv2.resize(sm_w, (w, h), interpolation=cv2.INTER_LINEAR) > 100

    thin_band = (11.0, 44.0)
    in_thin = cloud > 0.6
    thin = with_smoke(billows(5), cloud)
    sm, old_left = cleaned(thin, cloud, band=thin_band, smokeAuto=True)   # the way of 4.10.0: this is his report
    if sm.get("found") is not False or sm.get("protected") != 0.0 or old_left > 0.6:
        bad.append(f"the thin cloud of this check must be one that the search by wisps does not see: {sm}, {old_left * 100:.0f}% left")
    sm, kept = cleaned(thin, cloud, band=thin_band, smokeAuto=True, smokeFaint=True)
    if sm.get("faint") is not True or sm.get("auto") is not False or not (sm.get("protected", 0) > 0.04) or kept < 0.9:
        bad.append(f"thin smoke with the switch on must be protected on the user's word: {sm}, {kept * 100:.0f}% of its texture left")
    note += f"; the switch as the user's word: thin smoke kept {kept * 100:.0f}% (the way of 4.10.0: {old_left * 100:.0f}%)"
    sm, kept = cleaned(smoky, cloud, smokeAuto=True, smokeFaint=True)
    if sm.get("found") is not True or not (sm.get("protected", 0) > 0.05) or kept < 0.95:
        bad.append(f"a real cloud with the switch on: {sm}, {kept * 100:.0f}% of its texture left")
    # nothing on a clean wall, nothing next to the person
    plain_w = word_map(img)
    wall_w, ring_w = float(plain_w[: int(h * 0.45)].mean()), float(plain_w[near].mean())
    if wall_w > 0.01 or ring_w > 0.03:
        bad.append(f"no smoke in the frame, the switch on: {wall_w * 100:.1f}% of the wall and {ring_w * 100:.1f}% of the ring around the person are 'smoke'")
    # the slider: under SMOKE_SOFT_FROM only wisps count, higher up it reaches thinner smoke
    got_lo = float(word_map(thin, ENG.SMOKE_SOFT_FROM - 1.0)[in_thin].mean())
    got_60 = float(word_map(thin, 60.0)[in_thin].mean())
    got_80, got_95 = float(word_map(thin)[in_thin].mean()), float(word_map(thin, 95.0)[in_thin].mean())
    if got_lo > 0.02 or got_80 < 0.75 or got_60 > got_80 - 0.1 or got_95 < got_80 + 0.03:
        bad.append(f"thin smoke by the slider: {got_lo * 100:.0f}% of the cloud under {ENG.SMOKE_SOFT_FROM:.0f}, {got_60 * 100:.0f}% at 60, "
                   f"{got_80 * 100:.0f}% at 80, {got_95 * 100:.0f}% at 95 (every step up must reach thinner smoke)")
    note += f", {got_80 * 100:.0f}% of its cloud at 80 and {got_95 * 100:.0f}% at 95"
    # one direction is not smoke: the soft rim of a pool of light on the wall
    r_pool = np.sqrt((xx - 0.30 * w) ** 2 + (yy - 0.30 * h) ** 2)
    pool = 1.0 / (1.0 + np.exp((r_pool - 0.20 * w) / 18.0))
    lit = np.clip(img.astype(np.float32) * (1.0 + 0.30 * pool[..., None]), 0, 255).astype(np.uint8)
    rim = float(word_map(lit)[np.abs(r_pool - 0.20 * w) < 60].mean())
    if rim > 0.3:
        bad.append(f"the rim of a pool of light is taken for smoke on {rim * 100:.0f}% of its length")
    note += f"; rim of a pool of light {rim * 100:.0f}%"
    # the floor next to the feet: dirt stays dirt until the slider says "everything" (100 %)
    line = ENG.SMOKE_FLOOR_FROM
    for value, limit in ((80.0, None), (95.0, None), (100.0, 0.95)):
        sm, kept = cleaned(dirty, dirt, smokeAuto=True, smokeFaint=True, smoke=value)
        in_dirt = float(word_map(dirty, value)[dirt > 0.6].mean())
        if limit is None and (kept > 0.7 or in_dirt > 0.02):
            bad.append(f"dirty floor, the switch on, slider {value:.0f}: {kept * 100:.0f}% of the dirt left, {in_dirt * 100:.0f}% of it protected")
        if limit is not None and (kept < limit or in_dirt < 0.9):
            bad.append(f"slider {value:.0f} means everything soft, the floor too: {kept * 100:.0f}% of the dirt left, {in_dirt * 100:.0f}% of it protected")
    # thin smoke that comes down to the floor is kept there too; thin smoke on the floor alone only at 100 %
    low = oval(0.22, line + 0.02, 0.16, 0.15, 25)
    under = (low > 0.6) & (yy > (line + 0.04) * h)
    down = float(word_map(with_smoke(billows(6), low))[under].mean())
    alone = oval(0.22, line + 0.175, 0.16, 0.05, 20)
    alone_img = with_smoke(billows(6), alone)
    alone_80, alone_100 = float(word_map(alone_img)[alone > 0.6].mean()), float(word_map(alone_img, 100.0)[alone > 0.6].mean())
    if down < 0.9 or alone_80 > 0.05 or alone_100 < 0.9:
        bad.append(f"thin smoke at the floor: {down * 100:.0f}% of the part under the line of a cloud that comes from above; "
                   f"a cloud on the floor alone {alone_80 * 100:.0f}% at 80 and {alone_100 * 100:.0f}% at 100")
    note += f"; floor: dirt cleaned, smoke from above kept {down * 100:.0f}%, alone {alone_80 * 100:.0f}% / {alone_100 * 100:.0f}% at 100"
    # A line is not smoke. (1) A soft straight line across the wall, crossed by the fall-off of the light: two
    # straight things that cross have two directions too - the light is taken out first, up to the very border.
    row_l = int(0.35 * h)
    step_l = 1.0 / (1.0 + np.exp(-np.clip((yy - row_l) / 4.0, -50, 50)))
    lined = np.clip(img.astype(np.float32) - 9.0 * step_l[..., None], 0, 255).astype(np.uint8)
    on_line = np.abs(yy - row_l) < 10
    ends = on_line & ((xx < 0.08 * w) | (xx > 0.92 * w))
    for value in (80.0, 95.0, 100.0):
        got_l = word_map(lined, value)
        if float(got_l[on_line].mean()) > 0.03 or float(got_l[ends].mean()) > 0.03:
            bad.append(f"a straight line on the wall, slider {value:.0f}: {got_l[on_line].mean() * 100:.0f}% of it is 'smoke' "
                       f"({got_l[ends].mean() * 100:.0f}% of its two ends at the frame border)")
    slope = np.add.outer(np.arange(6, dtype=np.float32) * 2, np.arange(5, dtype=np.float32) * 3)
    known = np.ones_like(slope)
    known[0, 1] = 0.0
    past, past_w = ENG._continued_past_border(slope, known, 3)
    want = np.add.outer((np.arange(12, dtype=np.float32) - 3) * 2, (np.arange(11, dtype=np.float32) - 3) * 3)
    if past.shape != (12, 11) or not np.allclose(past, want) or float(past_w[:3, 4].max()) != 0.0 or float(past_w[:3, 5].min()) != 1.0:
        bad.append("_continued_past_border: a slope must go on as the same slope past every border, and what leans on an "
                   "unknown border value must not count")
    # (2) a band of wisps is a line, whichever way it lies; a cloud, a thick band, a short piece, a bent one are not
    shapes = np.zeros((400, 600), np.uint8)
    cv2.line(shapes, (40, 60), (340, 90), 1, 14)              # 1: a thin straight band, a little tilted
    cv2.ellipse(shapes, (470, 80), (70, 45), 0, 0, 360, 1, -1)  # 2: a cloud
    cv2.line(shapes, (40, 200), (340, 200), 1, 60)            # 3: a thick band
    cv2.line(shapes, (420, 200), (455, 200), 1, 14)           # 4: a short piece
    cv2.line(shapes, (60, 300), (260, 300), 1, 14)            # 5: a bent one
    cv2.line(shapes, (260, 300), (260, 390), 1, 14)
    cv2.ellipse(shapes, (450, 911), (611, 611), 0, 257.7, 282.3, 1, 10)   # 6: a thin arc - a tendril, not a line
    left = H.make_engine(E, sil)._smoke_without_lines(shapes > 0)
    probes = {"thin straight band": (190, 75, False), "cloud": (470, 80, True), "thick band": (190, 200, True),
              "short piece": (437, 200, True), "bent band": (160, 300, True), "thin arc": (450, 300, True)}
    wrong = [name for name, (px, py, stays) in probes.items() if bool(left[py, px]) != stays]
    if wrong:
        bad.append(f"_smoke_without_lines: only a thin straight band of wisps is a line; wrong for: {', '.join(wrong)}")

    def after(frame, **over):
        eng_l = H.make_engine(E, sil)
        out, stats = _quiet(eng_l.process, frame, 8, dict(H.STD, speedMode="fast", smokeAuto=True, smokeFaint=True, **over))
        return _comp(frame, out), stats

    def corner_left(res):   # the steepest change across the wall-floor corner, left of the person (levels per pixel)
        g = res[:, int(0.05 * w):int(0.30 * w)].astype(np.float32).mean(axis=(1, 2))
        g = cv2.GaussianBlur(g.reshape(-1, 1), (0, 0), 3).ravel()
        return float(np.abs(np.gradient(g))[int(0.62 * h) - 40:int(0.62 * h) + 40].max())

    # (3) the vinyl seam gives a band of wisps: at 100 % - "everything" - it is still a seam and is repaired
    seam_off, seam_full = after(img, smokeOn=False)[1].get("seam_px", 0), after(img, smoke=100)[1].get("seam_px", 0)
    if seam_off < 5000 or seam_full < 0.9 * seam_off:
        bad.append(f"the seam with the smoke switch at 100 %: {seam_full} px found for repair, {seam_off} with the switch off")
    # (4) the tools for lines stop under thick smoke only: the corner goes under thin smoke as well, and a frame
    # without smoke loses its corner at any value of the slider
    corner_in = corner_left(img)
    corner_off = corner_left(after(img, smokeOn=False, cycCurve=65)[0])
    corner_on = max(corner_left(after(img, smoke=value, cycCurve=65)[0]) for value in (95, 100))
    if corner_in < 0.3 or corner_off > 0.15 or corner_on > corner_off + 0.05:
        bad.append(f"the corner of a frame without smoke: {corner_in:.2f} levels/px in the frame, {corner_off:.2f} after the corner "
                   f"tool, {corner_on:.2f} with the smoke switch at 95-100 %")
    over_corner = oval(0.17, 0.62, 0.14, 0.13, 25)
    thin_c = with_smoke(billows(7), over_corner)
    taken = float(word_map(thin_c)[over_corner > 0.6].mean())
    corner_thin = corner_left(after(thin_c, smoke=80, cycCurve=65)[0])
    if taken < 0.75 or corner_thin > 0.2:
        bad.append(f"thin smoke over the corner: {taken * 100:.0f}% of it is taken for smoke; the corner under it is left at "
                   f"{corner_thin:.2f} levels/px ({corner_left(thin_c):.2f} in the frame)")
    note += (f"; lines: a wall line 0%, the seam at 100 % {seam_full} px (off: {seam_off}), the corner {corner_in:.2f} -> "
             f"{corner_on:.2f} at 95-100 % and {corner_thin:.2f} under thin smoke")

    # the window: the answer says that the switch was taken on trust, and the maps follow the key
    eng = H.make_engine(E, sil)
    win = dict(H.STD, speedMode="fast", smokeAuto=True, smokeFaint=True, smokeOn=False)
    r1 = _quiet(eng.start_session, thin, 8, dict(win))
    r2 = _quiet(eng.recompute_session, r1["session_id"], dict(win, smokeOn=True), True, None, True)
    r3 = _quiet(eng.recompute_session, r1["session_id"], dict(win, smokeOn=True), True, None, False)
    r4 = _quiet(eng.recompute_session, r1["session_id"], dict(win, smokeOn=True, smokeAuto=False, smokeFaint=False), True, None, True)
    s1, s2, s3, s4 = (r.get("smoke") or {} for r in (r1, r2, r3, r4))
    if s1.get("on") is not False or s1.get("faint") is not False or s1.get("protected") != 0.0:
        bad.append(f"the window opens with the switch off: {s1}")
    if s2.get("on") is not True or s2.get("faint") is not True or s2.get("auto") is not False or not (s2.get("protected", 0) > 0.04) or s3 != s2:
        bad.append(f"the switch on in the window: the answer must say 'faint' and what is protected (light and full refresh alike): {s2} / {s3}")
    if s4.get("faint") is not False or s4.get("auto") is not False or s4.get("protected") == s2.get("protected"):
        bad.append(f"the same values without 'smokeFaint' are another request (only the wisps count) - the maps must be made anew: {s4}")
    report("smoke", not bad, note if not bad else "wrong:\n  " + "\n  ".join(bad))


def check_empty():
    bad = []
    w, h = 1500, 2000
    img, sil = H.make_studio_image(w, h, n_dust=30, n_hair=2, seed=31)
    blob = np.zeros((1024, 1024), np.float32)   # what a matting network answers on an empty backdrop: a faint blob
    cv2.circle(blob, (500, 620), 110, 0.03, -1)
    blob = cv2.GaussianBlur(blob, (0, 0), 20)
    eng = H.make_engine(E, blob)
    fg, corem = eng._clean_fg_mask(eng._predict_fg_raw(img), w, h, 70.0)
    if int(fg.max()) != 0 or int(corem.max()) != 0:
        bad.append(f"a faint blob became a person (mask up to {int(fg.max())})")
    note = "empty backdrop -> no person"
    if E_OLD is not None:
        eo = H.make_engine(E_OLD, blob)
        fo, _ = eo._clean_fg_mask(eo._predict_fg_raw(img), w, h, 70.0)
        note += f" (v3.2.1 invented one covering {(fo > 128).mean() * 100:.1f}% of the frame)"
        # a real person is found exactly as before, logits included
        for name, m in (("0..1 mask", sil), ("logits", (sil - 0.5) * 16.0), ("weak but real 0..0.8", sil * 0.8)):
            a = H.make_engine(E, m)._predict_fg_raw(img)
            b = H.make_engine(E_OLD, m)._predict_fg_raw(img)
            if not np.array_equal(a, b):
                bad.append(f"a real person ({name}) is outlined differently from v3.2.1")
    report("empty", not bad, note if not bad else "wrong:\n  " + "\n  ".join(bad))


def _people_matte(w, h, visible, share, people=1, skirt=0.0, stand=False):
    """
    Matte (1024x1024, 0..1) of standing people. Only the upper `visible` part of the body is inside the frame and
    takes `share` of the frame height (visible=1: whole figure with floor under the feet). skirt: half-width of a
    dress hem in body heights (0 = trousers). stand: a softbox on a stand next to the people - a wide box above
    their heads, a pole and wide feet that reach the bottom edge of the frame.
    """
    m = np.zeros((h, w), np.uint8)
    hp = share * h / visible                      # body height in pixels
    y0 = (1.0 - share) * h * (0.45 if visible >= 1.0 else 1.0)
    centres = [w * 0.5] if people == 1 else [w * 0.5 - 0.14 * hp, w * 0.5 + 0.14 * hp]
    for cx in centres:
        pt = lambda fx, fy: (int(round(cx + fx * hp)), int(round(y0 + fy * hp)))  # noqa: E731
        cv2.ellipse(m, pt(0, 0.065), (int(0.048 * hp), int(0.065 * hp)), 0, 0, 360, 255, -1)
        cv2.rectangle(m, pt(-0.025, 0.12), pt(0.025, 0.17), 255, -1)
        cv2.fillPoly(m, [np.array([pt(-0.13, 0.17), pt(0.13, 0.17), pt(0.10, 0.36), pt(0.105, 0.52), pt(-0.105, 0.52), pt(-0.10, 0.36)], np.int32)], 255)
        for s in (-1, 1):
            cv2.fillPoly(m, [np.array([pt(s * 0.13, 0.175), pt(s * 0.165, 0.19), pt(s * 0.16, 0.50), pt(s * 0.125, 0.50)], np.int32)], 255)
        if skirt > 0:
            cv2.fillPoly(m, [np.array([pt(-0.105, 0.45), pt(0.105, 0.45), pt(skirt, 0.99), pt(-skirt, 0.99)], np.int32)], 255)
        else:
            for s in (-1, 1):
                cv2.fillPoly(m, [np.array([pt(s * 0.012, 0.52), pt(s * 0.105, 0.52), pt(s * 0.075, 0.95), pt(s * 0.02, 0.95)], np.int32)], 255)
                cv2.ellipse(m, pt(s * 0.055, 0.975), (int(0.045 * hp), int(0.025 * hp)), 0, 0, 360, 255, -1)
    if stand:
        cv2.rectangle(m, (int(w * 0.58), int(h * 0.02)), (int(w * 0.98), int(h * 0.14)), 255, -1)
        cv2.rectangle(m, (int(w * 0.93), int(h * 0.14)), (int(w * 0.945), h - 1), 255, -1)
        cv2.rectangle(m, (int(w * 0.76), int(h * 0.97)), (int(w * 0.99), h - 1), 255, -1)
    return cv2.resize(m, (1024, 1024), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0


def check_scene():
    """The automatic preset: what kind of frame it is, and that the suitable set of values is used from the start."""
    bad = []
    eng0 = ENG("/nonexistent-models", load_models=False)

    def kind_of(matte, w, h, backdrop=150, person=90):
        img = np.full((h, w, 3), backdrop, np.uint8)
        img[cv2.resize(matte, (w, h)) > 0.5] = person
        return eng0._scene_info((matte * 255).astype(np.uint8), img, w, h)

    # 1. the framing is read from the silhouette: every body crop, both orientations, one or two people, dress or trousers
    n_frames = 0
    want = {"full": (1.0, 0.76, "wide"), "full, tight": (1.0, 0.92, "wide"), "waist": (0.50, 0.86, "medium"),
            "bust": (0.27, 0.85, "close"), "head": (0.19, 0.88, "close")}
    for (w, h) in ((2000, 3000), (3000, 2000), (2400, 2400), (2000, 2800), (2800, 2000)):
        for name, (visible, share, kind) in want.items():
            for skirt in (0.0, 0.22):
                for people in (1, 2):
                    if people == 2 and 0.19 * (share * h / visible) > 0.5 * w:
                        continue  # two heads this large do not fit into the frame side by side
                    got = kind_of(_people_matte(w, h, visible, share, people, skirt), w, h)
                    n_frames += 1
                    # two people side by side, cut by the frame: "medium" and "close" are both fine (no floor either way)
                    ok = got["framing"] == kind or (people == 2 and kind != "wide" and got["framing"] in ("medium", "close"))
                    if not ok or got["kind"] != got["framing"] or got["dark"]:
                        bad.append(f"{w}x{h} {name}, people={people}, skirt={skirt}: {got['framing']} (kind {got['kind']}), expected {kind}")
    # a whole figure whose wide hem is cut by the bottom edge is still a whole figure; knees cut -> not a close-up
    for (w, h) in ((2000, 3000), (3000, 2000)):
        got = kind_of(_people_matte(w, h, 0.97, 0.97, 1, 0.30), w, h)
        n_frames += 1
        if got["framing"] != "wide" or not got["cut"]:
            bad.append(f"{w}x{h} whole figure with the hem at the frame edge: {got}")
        got = kind_of(_people_matte(w, h, 0.72, 0.90, 1, 0.0), w, h)
        n_frames += 1
        if got["framing"] == "close":
            bad.append(f"{w}x{h} knees-up frame taken for a close-up: {got}")
    # a softbox on a stand whose feet reach the bottom edge must not turn a whole figure into a cut one
    for skirt in (0.0, 0.22):
        got = kind_of(_people_matte(2000, 3000, 1.0, 0.76, 1, skirt, stand=True), 2000, 3000)
        n_frames += 1
        if got["framing"] != "wide" or got["cut"]:
            bad.append(f"a softbox on a stand next to the person changed the framing: {got}")
    # nobody in the frame
    blob = np.zeros((1024, 1024), np.float32)
    cv2.circle(blob, (500, 620), 110, 0.03, -1)
    for m in (np.zeros((1024, 1024), np.float32), cv2.GaussianBlur(blob, (0, 0), 20)):
        got = kind_of(m, 2000, 3000)
        if got["framing"] != "none" or got["kind"] != "none":
            bad.append(f"an empty frame got a framing: {got}")

    # 2. dark key: decided by the backdrop alone, whatever the person wears
    full = _people_matte(2000, 3000, 1.0, 0.76)
    bust = _people_matte(2000, 3000, 0.27, 0.85)
    limit = ENG.SCENE_DARK_LUMA
    for backdrop, person, dark in ((12, 230, True), (int(limit) - 4, 20, True), (int(limit) + 5, 20, False), (60, 230, False), (150, 10, False), (240, 30, False)):
        for matte, framing in ((full, "wide"), (bust, "close")):
            got = kind_of(matte, 2000, 3000, backdrop, person)
            if got["dark"] != dark or got["framing"] != framing or got["kind"] != ("dark" if dark else framing):
                bad.append(f"backdrop {backdrop}, person {person}: {got}")
            if abs((got["backdrop_luma"] or 0) - backdrop) > 1.5:
                bad.append(f"backdrop {backdrop} measured as {got['backdrop_luma']}")
    # the owner's own backdrops: black (13-20) and dark grey (31) are a dark key to him, his grey one (52) is not
    for backdrop, dark in ((13, True), (20, True), (31, True), (52, False), (78, False)):
        got = kind_of(full, 2000, 3000, backdrop, 120)
        if got["dark"] != dark:
            bad.append(f"the owner's backdrop of brightness {backdrop} must {'be' if dark else 'not be'} a dark key (limit {limit})")
    # ...also when the person takes most of the frame: a bright face on black is dark key, a dark coat on grey is not
    big = np.zeros((1024, 1024), np.float32)
    cv2.ellipse(big, (512, 640), (430, 560), 0, 0, 360, 1.0, -1)
    for backdrop, person, dark in ((12, 230, True), (150, 10, False)):
        got = kind_of(big, 2000, 3000, backdrop, person)
        if got["person_share"] < 0.6 or got["dark"] != dark or abs((got["backdrop_luma"] or 0) - backdrop) > 1.5:
            bad.append(f"person over most of the frame, backdrop {backdrop}, person {person}: {got}")

    # 3. the engine: start_session with the sets by kind of frame == start_session with the suitable set given by hand
    w, h = 1500, 2100
    img, _ = H.make_studio_image(w, h, n_dust=50, n_hair=4, seed=41)
    sil = _people_matte(w, h, 1.0, 0.76)
    sets = {
        "dark": dict(H.STD, speedMode="fast", autoFractions=True, spots=92, scuffs=55, edge=78),
        "close": dict(H.STD, speedMode="fast", autoFractions=False, spots=62, scuffs=48, blur=18, edge=84, seamOn=False, fracLarge=False),
        "medium": dict(H.STD, speedMode="fast", autoFractions=True, blur=10, seam=78, edge=74),
        "wide": dict(H.STD, speedMode="fast", autoFractions=True, spots=85, scuffs=78, edge=66, seam=90),
        "default": dict(H.STD, speedMode="fast", autoFractions=True),
    }
    asked = dict(H.STD, speedMode="fast", autoFractions=True, spots=40, edge=50)  # what the controls showed before
    same = ("auto_fractions", "comp_jpg_b64", "overlay_jpg_b64", "orig_jpg_b64", "mask_share")

    def opened(image, matte, presets, params=asked):
        e = H.make_engine(E, matte)
        return e, _quiet(e.start_session, image, 8, dict(params), None, None, presets)

    cases = [("whole figure", img, sil, "wide", "wide"),
             ("close-up", img, _people_matte(w, h, 0.27, 0.85), "close", "close"),
             ("cut at the waist", img, _people_matte(w, h, 0.50, 0.86), "medium", "medium"),
             ("dark backdrop", (img * 0.12).astype(np.uint8), sil, "dark", "dark"),
             ("nobody", img, np.zeros((1024, 1024), np.float32), "none", "default")]
    for name, image, matte, kind, used in cases:
        e1, r1 = opened(image, matte, sets)
        e2, r2 = opened(image, matte, None, sets[used])
        sc = r1.get("scene") or {}
        if sc.get("kind") != kind or sc.get("applied") != used:
            bad.append(f"{name}: seen as {sc.get('kind')}, used the set '{sc.get('applied')}' (expected {kind} / {used})")
        if any(r1[k] != r2[k] for k in same) or not _same_stats(r1["stats"], r2["stats"]) or e1._active_session["params"] != e2._active_session["params"]:
            bad.append(f"{name}: the window differs from the one opened with that set by hand")
        if (r2.get("scene") or {}).get("applied") is not None or (r2.get("scene") or {}).get("kind") != kind:
            bad.append(f"{name}: without sets nothing may be replaced, yet the frame must still be described: {r2.get('scene')}")
        if name in ("whole figure", "close-up"):
            a1 = _quiet(e1.apply_session, r1["session_id"], 100.0, False, False, 45.0)
            a2 = _quiet(e2.apply_session, r2["session_id"], 100.0, False, False, 45.0)
            if not np.array_equal(a1[0], a2[0]):
                bad.append(f"{name}: the layer after Apply differs from the one made with that set by hand")
    # a deleted preset: its kind falls back to the framing, then to "default"; nothing offered -> `params` as sent
    for presets, used in (({k: v for k, v in sets.items() if k != "dark"}, "wide"),
                          ({"default": sets["default"]}, "default"), ({}, None), ({"close": sets["close"]}, None)):
        e1, r1 = opened((img * 0.12).astype(np.uint8), sil, presets)
        e2, r2 = opened((img * 0.12).astype(np.uint8), sil, None, sets[used] if used else asked)
        if r1["scene"]["applied"] != used or r1["comp_jpg_b64"] != r2["comp_jpg_b64"] or e1._active_session["params"] != e2._active_session["params"]:
            bad.append(f"sets {sorted(presets)}: used '{r1['scene']['applied']}', expected '{used}'")

    # 3b. a dark backdrop has its own sets by framing: "dark_<framing>" first, then the general "dark", then the set
    #     of the framing, then "default". A light frame never takes a dark set.
    dark_img = (img * 0.12).astype(np.uint8)
    dsets = dict(sets,
                 dark_wide=dict(sets["dark"], spots=80, cycCurve=65),
                 dark_medium=dict(sets["dark"], spots=72, edge=82),
                 dark_close=dict(sets["dark"], spots=62, edge=86, seamOn=False, fracLarge=False, autoFractions=False))
    for name, matte, want in (("whole figure", sil, "dark_wide"), ("cut at the waist", _people_matte(w, h, 0.50, 0.86), "dark_medium"),
                              ("close-up", _people_matte(w, h, 0.27, 0.85), "dark_close"), ("nobody", np.zeros((1024, 1024), np.float32), "dark")):
        e1, r1 = opened(dark_img, matte, dsets)
        e2, r2 = opened(dark_img, matte, None, dsets[want])
        if r1["scene"]["applied"] != want or r1["scene"]["kind"] != "dark":
            bad.append(f"dark backdrop, {name}: used the set '{r1['scene']['applied']}' (expected '{want}')")
        elif any(r1[k] != r2[k] for k in same) or e1._active_session["params"] != e2._active_session["params"]:
            bad.append(f"dark backdrop, {name}: the window differs from the one opened with the set '{want}' by hand")
    for dropped, want in ((("dark_wide",), "dark"), (("dark_wide", "dark"), "wide"), (("dark_wide", "dark", "wide"), "default")):
        e1, r1 = opened(dark_img, sil, {k: v for k, v in dsets.items() if k not in dropped})
        if r1["scene"]["applied"] != want:
            bad.append(f"dark backdrop without the sets {dropped}: used '{r1['scene']['applied']}', expected '{want}'")
    e1, r1 = opened(img, sil, dsets)
    if r1["scene"]["applied"] != "wide":
        bad.append(f"a light frame took the set '{r1['scene']['applied']}' although only a dark backdrop has dark sets")

    # 4. "how much of the frame was found and repaired" (the bright green of the mask; the plugin's notes are built
    #    on it): reported after every step and equal to the mask on screen. More about the two greens: check_mask.
    e1, r1 = opened(img, sil, None)
    sid = r1["session_id"]

    def share():
        s = e1._active_session
        return float(np.count_nonzero(e1._compute_marked_mask_small(s, e1._compute_effective_mask_small(s)) > 127)) / (r1["preview_w"] * r1["preview_h"])

    if not (0.0 < r1["mask_share"] < 0.5) or abs(r1["mask_share"] - share()) > 1e-4:
        bad.append(f"mask_share after the scan: {r1.get('mask_share')} vs {share():.5f}")
    r2 = _quiet(e1.recompute_session, sid, dict(asked, spots=95), True, None, True)
    if abs(r2["mask_share"] - share()) > 1e-4 or r2["mask_share"] <= r1["mask_share"]:
        bad.append(f"mask_share after a more sensitive search: {r1['mask_share']} -> {r2.get('mask_share')}")
    # ("fill" shows the layer on the whole frame and repaints nothing: what counts as found stays as it was)
    r3 = _quiet(e1.edit_session_mask, sid, "fill", None, 20, False, False, 45.0)
    shown3 = share()
    r4 = _quiet(e1.edit_session_mask, sid, "clear", None, 20, False, False, 45.0)
    if (r3.get("layer_share") != 1.0 or abs(r3["mask_share"] - shown3) > 1e-4 or abs(r3["mask_share"] - r2["mask_share"]) > 1e-4
            or r4.get("mask_share") != 0.0 or r4.get("layer_share") != 0.0):
        bad.append(f"after fill / clear: mask_share {r3.get('mask_share')} (on screen {shown3:.5f}, before {r2['mask_share']}) / {r4.get('mask_share')}, "
                   f"layer_share {r3.get('layer_share')} / {r4.get('layer_share')}")

    # 5. over HTTP, the way the plugin sends it
    note = ""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from fastapi.testclient import TestClient
    except Exception:
        TestClient = None
        note = "; HTTP part SKIPPED (pip install httpx)"
    if TestClient is not None:
        srv = H.load_server()
        keep = srv.ENGINE, srv.ENGINE_ERROR
        real_out = sys.stdout
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
        try:
            srv.ENGINE, srv.ENGINE_ERROR = H.make_engine(E, sil), None
            with TestClient(srv.app) as client:
                def start(extra):
                    meta = dict({"width": w, "height": h, "channels": 3, "bitDepth": 8, "hasSelection": False, "jobId": "s", "params": asked}, **extra)
                    mb = json.dumps(meta).encode("utf-8")
                    return client.post("/session/start", content=struct.pack("<I", len(mb)) + mb + np.ascontiguousarray(img).tobytes())
                ra, rb, rc = start({"scenePresets": sets}), start({}), start({"scenePresets": "nonsense"})
                ja, jb = ra.json(), rb.json()
                if ra.status_code != 200 or ja["scene"]["applied"] != "wide" or ja["scene"]["kind"] != "wide" or srv.ENGINE._active_session is None:
                    bad.append(f"HTTP /session/start with scenePresets: {ra.status_code} {ja.get('scene')}")
                if rb.status_code != 200 or jb["scene"]["applied"] is not None or jb["comp_jpg_b64"] == ja["comp_jpg_b64"]:
                    bad.append("HTTP /session/start without scenePresets must use `params` as sent")
                if rc.status_code != 200 or rc.json()["scene"]["applied"] is not None or rc.json()["comp_jpg_b64"] != jb["comp_jpg_b64"]:
                    bad.append("HTTP /session/start with a broken scenePresets must behave as without it")
                if not isinstance(ja.get("mask_share"), float):
                    bad.append("HTTP /session/start must report mask_share")
        finally:
            sys.stdout.close()
            sys.stdout = real_out
            srv.ENGINE, srv.ENGINE_ERROR = keep
    report("scene", not bad, f"{n_frames} silhouettes framed right (whole figure / waist / close-up, both orientations, 1-2 people); dark key by the "
                             f"backdrop (limit {limit:.0f}), with its own set for every framing; opening with the automatic preset == opening with "
                             f"that preset by hand, layer included{note}"
           if not bad else "wrong:\n  " + "\n  ".join(bad))


# ----------------------------------------------------------------------------------------------------------------------
# Stains, smears and shoe marks ("Сліди взуття та розводи")
# ----------------------------------------------------------------------------------------------------------------------
def _stained_frame(w, h, seed=4, dark=False):
    """
    A lit backdrop with the usual 'person', a contact shadow under the feet, a soft cast shadow, a red ball and a
    strip of yellow tape - and stains over the floor (soft spots of 0.8-2.4% of the frame height, a third of them
    right next to the legs). dark=True: a low-key backdrop with the pool of a lamp on the floor.
    Returns (frame with the stains, the same frame without them, silhouette, what was drawn where).
    """
    rng = np.random.default_rng(seed)
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    xx = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    if dark:
        lum = 26.0 * (1.0 - 0.25 * ((xx - 0.5) * 2) ** 2) + 6.0 * yy
        pool = np.exp(-(((xx - 0.27) / 0.20) ** 2 + ((yy - 0.84) / 0.06) ** 2) * 1.2)
        lum = lum + 70.0 * pool
    else:
        lum = 150.0 * (1.0 - 0.22 * ((xx - 0.5) * 2) ** 2 - 0.15 * ((yy - 0.45) * 2) ** 2) + 25.0 * yy
        pool = np.zeros((h, w), np.float32)
    lum = np.broadcast_to(lum, (h, w)).astype(np.float32).copy()
    pool = np.broadcast_to(pool, (h, w)).astype(np.float32)
    _, sil = H.make_studio_image(w, h, n_dust=0, n_hair=0, seed=1)
    person = cv2.resize(sil, (w, h)) > 0.5
    cx = w // 2
    small = (max(8, h // 8), max(8, w // 8))
    sh = np.zeros(small, np.float32)
    cv2.ellipse(sh, (cx // 8 + 30, int(h * 0.905) // 8), (max(1, int(w * 0.11) // 8), max(1, int(h * 0.022) // 8)), 0, 0, 360, 1.0, -1)
    contact = cv2.resize(cv2.GaussianBlur(sh, (0, 0), 6), (w, h))
    cs = np.zeros(small, np.float32)
    cv2.ellipse(cs, (int(w * 0.76) // 8, int(h * 0.76) // 8), (max(1, int(w * 0.11) // 8), max(1, int(h * 0.04) // 8)), -18, 0, 360, 1.0, -1)
    cast = cv2.resize(cv2.GaussianBlur(cs, (0, 0), 5), (w, h))
    lit = lum * (1.0 - 0.38 * contact) * (1.0 - 0.14 * cast)

    st = np.zeros((h, w), np.float32)
    for i in range(170):
        r = int(rng.uniform(0.004, 0.012) * h)
        if i % 3 == 0:    # next to the legs and the feet
            px = int(cx + rng.choice([-1, 1]) * rng.uniform(0.055, 0.15) * w)
            py = int(rng.uniform(0.74, 0.97) * h)
        else:
            px, py = int(rng.uniform(0.03, 0.97) * w), int(rng.uniform(0.66, 0.98) * h)
        y0, y1, x0, x1 = max(0, py - 4 * r), min(h, py + 4 * r), max(0, px - 4 * r), min(w, px + 4 * r)
        blob = np.zeros((y1 - y0, x1 - x0), np.float32)
        cv2.ellipse(blob, (px - x0, py - y0), (int(r * rng.uniform(1.0, 2.2)), r), float(rng.uniform(0, 180)), 0, 360, 1.0, -1)
        st[y0:y1, x0:x1] += cv2.GaussianBlur(blob, (0, 0), max(1.0, r * 0.35)) * float(rng.choice([-1, -1, -1, 1]) * rng.uniform(3.5, 6.5))
    st *= 0.40 if dark else 1.0
    noise = rng.standard_normal((h, w, 3)).astype(np.float32) * (1.2 if dark else 1.8)
    ball = (np.arange(w)[None, :] - int(w * 0.16)) ** 2 + (np.arange(h)[:, None] - int(h * 0.74)) ** 2 <= (0.035 * w) ** 2
    tape = np.zeros((h, w), bool)
    tape[int(h * 0.940):int(h * 0.940) + max(4, h // 200), int(w * 0.62):int(w * 0.92)] = True
    st[cv2.dilate((ball | tape).astype(np.uint8), np.ones((int(0.03 * h) | 1,) * 2, np.uint8)) > 0] = 0.0  # (measured on their own)

    def paint(l):
        img = l[..., None] * np.float32([1.02, 1.0, 0.97]) + noise
        img[ball] = np.float32([190, 40, 40]) + noise[ball]
        img[tape] = l[tape][:, None] * np.float32([1.16, 1.02, 0.52]) + noise[tape]
        img[person] = np.float32([40, 40, 46]) + noise[person] * 0.5
        return np.clip(img, 0, 255).astype(np.uint8)

    return paint(lit + st), paint(lit), sil, dict(person=person, stains=st, contact=contact, cast=cast, ball=ball, tape=tape, pool=pool)


def _stain_numbers(c, stained, clean, g, dark=False):
    """
    `c`: the cleaned frame (float levels). Returns what is left of the stains (all of them / those within 4% of the
    frame height from the person / those farther than 10%), how deep the two shadows still are, and what happened to
    the person, the ball, the tape and the light.
    """
    h, w = stained.shape[:2]
    gray = lambda im: im.astype(np.float32).mean(axis=2)  # noqa: E731
    S = cv2.GaussianBlur(g["stains"], (0, 0), 2.0)
    R = cv2.GaussianBlur(gray(c) - gray(clean), (0, 0), 2.0)
    person = g["person"]
    bg = ~(cv2.dilate(person.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0)
    sel = bg & (np.abs(S) > (0.5 if dark else 1.2))
    dist = cv2.distanceTransform((~person).astype(np.uint8), cv2.DIST_L2, 5)
    left = lambda m: float((R[m] * S[m]).sum() / max(1e-6, float((S[m] ** 2).sum())))  # noqa: E731
    d0, d1 = gray(clean), gray(c)
    quiet_bg = bg & (np.abs(S) < 0.2)
    rows, cols = np.arange(h)[:, None], np.arange(w)[None, :]
    con = quiet_bg & (g["contact"] > 0.5)
    con_ref = quiet_bg & (g["contact"] < 0.02) & (g["cast"] < 0.02) & (np.abs(rows - int(h * 0.905)) < 0.03 * h) & (np.abs(cols - w // 2) < 0.30 * w)
    cst = quiet_bg & (g["cast"] > 0.6)
    cst_ref = quiet_bg & (g["cast"] < 0.03) & (g["contact"] < 0.02) & (cv2.dilate((g["cast"] > 0.2).astype(np.uint8), np.ones((int(0.12 * w) | 1,) * 2, np.uint8)) > 0)
    depth = lambda a, inside, ref: float(np.median(a[ref]) - np.median(a[inside]))  # noqa: E731
    ball_core = cv2.erode(g["ball"].astype(np.uint8), np.ones((15, 15), np.uint8)) > 0
    lab_b = lambda im: cv2.cvtColor(np.clip(im, 0, 255).astype(np.uint8), cv2.COLOR_RGB2LAB)[..., 2].astype(np.float32)  # noqa: E731
    beside = np.roll(g["tape"], -4 * max(4, h // 200), axis=0)
    tape_colour = lambda im: float(lab_b(im)[g["tape"]].mean() - lab_b(im)[beside].mean())  # noqa: E731
    changed = np.abs(c - stained.astype(np.float32))
    inside = cv2.erode(person.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0  # (the outline itself is a soft edge)
    return dict(
        left=left(sel), near=left(sel & (dist < 0.04 * h)), far=left(sel & (dist > 0.10 * h)),
        contact=depth(d1, con, con_ref) / depth(d0, con, con_ref), cast=depth(d1, cst, cst_ref) / depth(d0, cst, cst_ref),
        person=float(changed[inside].max()), ball=float(changed[ball_core].mean()),
        tape=tape_colour(c) / tape_colour(stained),
        light=float(np.abs(cv2.GaussianBlur(d1 - gray(stained), (0, 0), 0.05 * h))[bg].max()),
    )


def check_stains():
    """
    "Сліди взуття та розводи": stains of the floor are evened - next to the person as well as away from it - while
    shadows, props, the light and the person stay.
    """
    bad, notes = [], []
    only = dict(H.STD, spots=0, seamOn=False, blur=0, cycCurve=0, smokeAuto=True)  # nothing but the stain stage works

    def cleaned(frame, sil, engine=E, bit16=False, **over):
        eng = H.make_engine(engine, sil)
        if not bit16:
            return _comp(frame, _quiet(eng.process, frame, 8, dict(only, **over))[0])
        out = _quiet(eng.process, frame.astype(np.uint16) * 128, 16, dict(only, **over))[0]
        if out.dtype != np.uint16:
            bad.append("16-bit frame: the answer is not 16-bit")
        out = out.astype(np.float32) / 128.0
        a = out[:, :, 3:4] / 255.0
        return frame.astype(np.float32) * (1.0 - a) + out[:, :, :3] * a

    grad = lambda a: np.hypot(cv2.Sobel(a, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(a, cv2.CV_32F, 0, 1, ksize=3)) / 8.0  # noqa: E731
    by_strength = {}
    for (w, h, mode) in ((1500, 2000, "quality"), (1500, 2000, "fast"), (2000, 1500, "fast")):
        stained, clean, sil, g = _stained_frame(w, h)
        r = _stain_numbers(cleaned(stained, sil, speedMode=mode, scuffs=65), stained, clean, g)
        tag = f"{w}x{h} {mode}"
        if mode == "fast" and w < h:
            by_strength[65] = r["left"]
            notes.append(f"stains left {r['left'] * 100:.0f}% (next to the person {r['near'] * 100:.0f}%), contact shadow {r['contact'] * 100:.0f}%, "
                         f"soft cast shadow {r['cast'] * 100:.0f}%")
        if r["left"] > 0.55 or r["far"] > 0.55:
            bad.append(f"{tag}: {r['left'] * 100:.0f}% of the stains are left (away from the person {r['far'] * 100:.0f}%)")
        if r["near"] > 0.60 or r["near"] > r["far"] + 0.15:
            bad.append(f"{tag}: next to the person {r['near'] * 100:.0f}% of the stains are left, away from it {r['far'] * 100:.0f}%")
        if r["contact"] < 0.85:
            bad.append(f"{tag}: the contact shadow under the feet kept {r['contact'] * 100:.0f}% of its depth")
        if r["cast"] < 0.62:
            bad.append(f"{tag}: the soft cast shadow kept {r['cast'] * 100:.0f}% of its depth")
        if r["person"] > 0.01:
            bad.append(f"{tag}: the person was changed by {r['person']:.3f} levels")
        if r["ball"] > 1.0 or r["tape"] < 0.75:
            bad.append(f"{tag}: the red ball moved by {r['ball']:.2f} levels, the yellow tape kept {r['tape'] * 100:.0f}% of its colour")
        if r["light"] > 2.0:
            bad.append(f"{tag}: the light itself moved by {r['light']:.2f} levels")
        # a frame with no stains on it stays as it is: nothing is drawn where there is nothing to even
        # (the two shadows are measured above, on their own)
        c0 = cleaned(clean, sil, speedMode=mode, scuffs=65)
        bg = (~(cv2.dilate(g["person"].astype(np.uint8), np.ones((31, 31), np.uint8)) > 0) & (g["contact"] < 0.02) & (g["cast"] < 0.02)
              & ~(cv2.dilate((g["ball"] | g["tape"]).astype(np.uint8), np.ones((61, 61), np.uint8)) > 0))
        a0, a1 = cv2.GaussianBlur(clean.astype(np.float32).mean(axis=2), (0, 0), 3.0), cv2.GaussianBlur(c0.mean(axis=2), (0, 0), 3.0)
        drawn = float(np.percentile((grad(a1) - grad(a0))[bg], 99.9))
        moved = float(np.abs(cv2.GaussianBlur(a1 - a0, (0, 0), 6.0))[bg].max())
        if drawn > 0.10 or moved > 2.5:
            bad.append(f"{tag}: a frame without stains got new edges ({drawn:.3f} levels/px) or moved by {moved:.2f} levels")

    w, h = 1500, 2000
    stained, clean, sil, g = _stained_frame(w, h)
    for strength in (30, 100):
        by_strength[strength] = _stain_numbers(cleaned(stained, sil, speedMode="fast", scuffs=strength), stained, clean, g)["left"]
    if not (by_strength[30] > by_strength[65] + 0.05 > by_strength[100] + 0.10):
        bad.append(f"the slider does not grade the effect: stains left at 30 / 65 / 100 = " + " / ".join(f"{by_strength[k] * 100:.0f}%" for k in (30, 65, 100)))
    if float(np.abs(cleaned(stained, sil, speedMode="fast", scuffs=0) - stained.astype(np.float32)).max()) > 0.0:
        bad.append("slider at 0: the frame was changed")
    r16 = _stain_numbers(cleaned(stained, sil, bit16=True, speedMode="fast", scuffs=65), stained, clean, g)
    if abs(r16["left"] - by_strength[65]) > 0.03 or r16["person"] > 0.51:
        bad.append(f"16-bit frame: stains left {r16['left'] * 100:.0f}% (8-bit: {by_strength[65] * 100:.0f}%), person moved by {r16['person']:.2f}")

    # a low-key backdrop with a lamp's pool on the floor: stains go, the pool keeps its shape and its rim
    dstained, dclean, dsil, dg = _stained_frame(w, h, dark=True)
    cd = cleaned(dstained, dsil, speedMode="fast", scuffs=55)
    rd = _stain_numbers(cd, dstained, dclean, dg, dark=True)
    notes.append(f"dark backdrop: stains left {rd['left'] * 100:.0f}%")
    if rd["left"] > 0.82 or rd["near"] > 0.85 or rd["person"] > 0.01 or rd["contact"] < 0.85:
        bad.append(f"dark backdrop: stains left {rd['left'] * 100:.0f}% (next to the person {rd['near'] * 100:.0f}%), "
                   f"contact shadow {rd['contact'] * 100:.0f}%, person moved by {rd['person']:.3f}")
    bgd = ~(cv2.dilate(dg["person"].astype(np.uint8), np.ones((31, 31), np.uint8)) > 0)
    rim = bgd & (dg["pool"] > 0.2) & (dg["pool"] < 0.8) & (np.abs(dg["stains"]) < 0.1)
    b0, b1 = cv2.GaussianBlur(dclean.astype(np.float32).mean(axis=2), (0, 0), 4.0), cv2.GaussianBlur(cd.mean(axis=2), (0, 0), 4.0)
    rim_sharper = float(np.median(grad(b1)[rim]) / max(1e-6, float(np.median(grad(b0)[rim]))))
    core = bgd & (dg["pool"] > 0.9)
    pool_kept = float((np.median(b1[core]) - np.median(b1[bgd & (dg["pool"] < 0.02) & (np.arange(h)[:, None] > 0.70 * h)]))
                      / (np.median(b0[core]) - np.median(b0[bgd & (dg["pool"] < 0.02) & (np.arange(h)[:, None] > 0.70 * h)])))
    if not (0.93 <= rim_sharper <= 1.07) or not (0.97 <= pool_kept <= 1.03):
        bad.append(f"dark backdrop: the rim of the lamp's pool became x{rim_sharper:.2f} as steep, the pool kept {pool_kept * 100:.0f}% of its light")

    # the rim of a lamp's pool with one slightly steeper spot in it (a repaired seam leaves such a spot): an
    # edge-keeping average flattens both shoulders of the spot and so draws a line there; it must be left alone
    rng = np.random.default_rng(5)
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    t = np.clip((yy - 0.69) / 0.11, 0.0, 1.0)
    lum = 11.0 + 50.0 * (t * t * (3 - 2 * t)) + 2.5 / (1.0 + np.exp(-(yy - 0.745) * h / 5.0))
    rim_img = np.clip(np.broadcast_to(lum, (h, w))[..., None] * np.float32([0.9, 0.95, 1.15]) + rng.standard_normal((h, w, 3)).astype(np.float32) * 1.2, 0, 255).astype(np.uint8)
    rim_img[cv2.resize(sil, (w, h)) > 0.5] = (20, 20, 24)
    rim_out = cleaned(rim_img, sil, speedMode="fast", scuffs=55)
    prof = lambda a: a[:, int(w * 0.04):int(w * 0.30)].astype(np.float32).mean(axis=(1, 2))  # noqa: E731
    p0, p1 = prof(rim_img), prof(rim_out)
    k, rows = int(0.004 * h), np.arange(int(0.70 * h), int(0.79 * h))
    climb = lambda q: float(max(q[r + k] - q[r - k] for r in rows))  # noqa: E731
    if climb(p1) > 1.04 * climb(p0):
        bad.append(f"the steepest spot of a lamp's rim became steeper: {climb(p0):.2f} -> {climb(p1):.2f} levels over {2 * k} rows")

    # the darkest corner of the backdrop (a small soft shadow, under half a percent of the frame) is a backdrop like
    # any other: stains in it are evened too. (Left out of the tone range, it stayed as an untouched ragged patch.)
    rng = np.random.default_rng(11)
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    xx = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    lum = np.broadcast_to(150.0 * (1.0 - 0.22 * ((xx - 0.5) * 2) ** 2 - 0.15 * ((yy - 0.45) * 2) ** 2) + 25.0 * yy, (h, w)).astype(np.float32).copy()
    patch = np.zeros((h, w), np.float32)
    cv2.ellipse(patch, (int(w * 0.24), int(h * 0.80)), (int(w * 0.05), int(h * 0.02)), 0, 0, 360, 1.0, -1)
    patch = cv2.GaussianBlur(patch, (0, 0), 10)
    spots = np.zeros((h, w), np.float32)
    for i in range(60):
        if i < 3:    # three small spots inside the patch, apart from one another: dark, light, dark
            sx, sy, sign = int(w * (0.24 + 0.03 * (i - 1))), int(h * 0.80), (-1.0, 1.0, -1.0)[i]
        else:
            sx, sy, sign = int(rng.uniform(0.04, 0.96) * w), int(rng.uniform(0.66, 0.97) * h), float(rng.choice([-1, 1]))
            if abs(sx - 0.24 * w) < 0.09 * w and abs(sy - 0.80 * h) < 0.05 * h:
                continue
        blob = np.zeros((h, w), np.float32)
        cv2.circle(blob, (sx, sy), 9, 1.0, -1)
        spots += cv2.GaussianBlur(blob, (0, 0), 3.5) * sign * float(rng.uniform(4.0, 5.5))
    noise = rng.standard_normal((h, w, 3)).astype(np.float32) * 1.8
    person = cv2.resize(sil, (w, h)) > 0.5
    frames = []
    for with_spots in (True, False):
        f = (lum - 14.0 * patch + (spots if with_spots else 0.0))[..., None] * np.float32([1.02, 1.0, 0.97]) + noise
        f[person] = np.float32([40, 40, 46])
        frames.append(np.clip(f, 0, 255).astype(np.uint8))
    out = cleaned(frames[0], sil, speedMode="fast", scuffs=65)
    S = cv2.GaussianBlur(spots, (0, 0), 2.0)
    R = cv2.GaussianBlur(out.mean(axis=2) - frames[1].astype(np.float32).mean(axis=2), (0, 0), 2.0)
    Rp = cv2.GaussianBlur(cleaned(frames[1], sil, speedMode="fast", scuffs=65).mean(axis=2) - frames[1].astype(np.float32).mean(axis=2), (0, 0), 2.0)
    in_patch = (patch > 0.6) & (np.abs(S) > 1.2) & ~person
    elsewhere = (patch < 0.02) & (np.abs(S) > 1.2) & ~(cv2.dilate(person.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0)
    # (what the stage does to the shadow itself is taken out: only the stains are asked about)
    left_in = float(((R - Rp)[in_patch] * S[in_patch]).sum() / (S[in_patch] ** 2).sum())
    left_out = float(((R - Rp)[elsewhere] * S[elsewhere]).sum() / (S[elsewhere] ** 2).sum())
    # (inside such a patch a stain has less of its own tone around it, so more of it is left than on the open floor;
    #  what must not happen is that it is left as it was)
    if left_in > 0.60:
        bad.append(f"stains inside the darkest small patch of the backdrop: {left_in * 100:.0f}% left (elsewhere {left_out * 100:.0f}%)")
    notes.append(f"inside a small dark patch {left_in * 100:.0f}% (around it {left_out * 100:.0f}%)")

    if E_OLD is not None:
        ro = _stain_numbers(cleaned(stained, sil, engine=E_OLD, speedMode="fast", scuffs=65), stained, clean, g)
        notes.append(f"v3.2.1 left {ro['left'] * 100:.0f}% (next to the person {ro['near'] * 100:.0f}%)")
    report("stains", not bad, "; ".join(notes) + "; person, ball, tape and light kept, a clean frame stays clean, 8/16 bit" if not bad else "wrong:\n  " + "\n  ".join(bad))


# ----------------------------------------------------------------------------------------------------------------------
# The joint of two backdrop sheets ("Шов з’єднання вінілу"), alone and together with the wall-floor corner
# ----------------------------------------------------------------------------------------------------------------------
def _joint_frame(w, h, left=(0.0, 0.18), right=(0.83, 1.0), y_left=0.80, y_right=0.80, corner=False, seed=7, dark=10.0, weak_left=1.0,
                 narrow=False, step=0.0):
    """
    A floor with the joint of two backdrop sheets (a hair-thin dark line with a faint rim), seen only as two pieces:
    a wide silhouette - a long dress with a train that leaves the frame - hides the middle. `left` / `right`: the
    visible part of the line on each side (shares of the width); `y_left` / `y_right`: its height on each side
    (different values = two different lines); `dark`: how dark the line is (levels). corner=True adds the
    wall-floor corner at 0.62 of the height.
    narrow=True: the usual narrow 'person' instead of the dress - the floor between the two pieces is in plain view.
    step: the line runs along the edge of a lit area - the floor below `y_left` is this many levels lighter.
    Returns (frame, silhouette 1024, mask of the drawn joint).
    """
    rng = np.random.default_rng(seed)
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    xx = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    if corner:
        t = 1.0 / (1.0 + np.exp(-np.clip((yy - 0.62) * 220.0, -50, 50)))
        lum = (150.0 * (1 - t) + 172.0 * t) * (1.0 - 0.22 * (((xx - 0.5) * 2) ** 2) - 0.10 * (((yy - 0.45) * 2) ** 2))
    else:
        lum = 150.0 * (1.0 - 0.22 * ((xx - 0.5) * 2) ** 2 - 0.15 * ((yy - 0.45) * 2) ** 2) + 25.0 * yy
    lum = np.broadcast_to(lum, (h, w)).astype(np.float32).copy()
    if step:
        lit = np.zeros((h, w), np.float32)
        lit[int(h * y_left):] = 1.0
        lum += step * cv2.GaussianBlur(lit, (0, 0), 1.5)
    joint = np.zeros((h, w), bool)
    for (x0, x1), yj, k in ((left, y_left, weak_left), (right, y_right, 1.0)):
        ys, xa, xb = int(h * yj), int(w * x0), int(w * x1)
        if xb > xa:
            lum[max(0, ys - 3):ys + 4, xa:xb] -= 0.2 * dark * k
            lum[ys:ys + 2, xa:xb] -= dark * k
            joint[ys:ys + 2, xa:xb] = True
    img = np.clip(lum[..., None] * np.float32([1.02, 1.0, 0.97]) + rng.standard_normal((h, w, 3)).astype(np.float32) * 1.8, 0, 255).astype(np.uint8)
    sil = np.zeros((h, w), np.uint8)
    cx = w // 2
    if narrow:
        _, sil_std = H.make_studio_image(w, h, n_dust=0, n_hair=0, seed=1)
        sil[cv2.resize(sil_std, (w, h)) > 0.5] = 255
    else:
        cv2.ellipse(sil, (cx, int(h * 0.20)), (int(w * 0.035), int(h * 0.07)), 0, 0, 360, 255, -1)
        xl, xr = int(w * (left[1] + 0.02)) if left[1] > left[0] else int(w * 0.20), int(w * (right[0] - 0.02)) if right[1] > right[0] else int(w * 0.81)
        dress = np.array([[cx - int(w * 0.05), int(h * 0.26)], [cx + int(w * 0.05), int(h * 0.26)], [xr, int(h * 0.74)], [xr, h], [xl, h], [xl, int(h * 0.74)]], np.int32)
        cv2.fillPoly(sil, [dress], 255)
    img[sil > 0] = (40, 40, 46)
    joint &= sil == 0
    return img, cv2.resize(sil, (1024, 1024), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0, joint


def _joint_sides(img, joint, heal):
    """Per side (left, right half of the frame): how dark the joint is against the floor above and below it (levels),
    and which share of it the repair mask covers."""
    g = img.astype(np.float32).mean(axis=2)
    w = img.shape[1]
    out = []
    for cols in (slice(0, w // 2), slice(w // 2, w)):
        m = joint[:, cols]
        if not m.any():
            out.append((0.0, 0.0))
            continue
        ys, xs = np.nonzero(m)
        yc, x0, x1 = int(ys.min()), int(xs.min()) + 20, int(xs.max()) - 20
        band = g[:, cols][:, x0:x1]
        dark = float((band[yc - 14:yc - 10].mean() + band[yc + 11:yc + 15].mean()) / 2 - band[yc:yc + 1].mean())
        out.append((dark, float((heal[:, cols][m] > 0).mean()) if heal is not None else 0.0))
    return out


def check_seam():
    """
    The joint of two sheets is removed on BOTH sides of the person, however short the visible pieces are and however
    dark the line is; two different lines are not taken for one; the wall-floor corner and the joint do not get in
    each other's way.
    """
    bad, notes = [], []
    base = dict(H.STD, spots=0, scuffs=0, blur=0, cycCurve=0, smokeAuto=True)

    def run(w=1500, h=2000, mode="fast", engine=E, frame=None, **over):
        img, sil, joint = _joint_frame(w, h, **(frame or {}))
        oc = {}
        eng = H.make_engine(engine, sil)
        out, stats = _quiet(eng.process, img, 8, dict(base, speedMode=mode, **over), out_cache=oc)
        comp = _comp(img, out)
        before, after = _joint_sides(img, joint, oc.get("heal_mask_full")), _joint_sides(comp, joint, oc.get("heal_mask_full"))
        return dict(stats=stats, before=[b[0] for b in before], after=[a[0] for a in after], cover=[a[1] for a in after], img=img, comp=comp, sil=sil)

    def both_gone(r):
        return min(r["cover"]) >= 0.9 and max(a / b for a, b in zip(r["after"], r["before"])) <= 0.25

    def untouched(r, sides=(0, 1)):
        return all(r["cover"][s] == 0.0 and abs(r["after"][s] - r["before"][s]) < 0.3 for s in sides)

    # 1. two short pieces of one line (18% and 17% of the width): judged one by one neither is long enough
    for (w, h, mode) in ((1500, 2000, "fast"), (1500, 2000, "quality"), (2000, 1500, "fast")):
        r = run(w, h, mode)
        if not both_gone(r):
            bad.append(f"{w}x{h} {mode}: two short pieces of one joint: covered {r['cover']}, line {r['before']} -> {r['after']} levels")
        if mode == "fast" and w < h:
            notes.append(f"pieces of 18% + 17% of the width: line {r['before'][0]:.0f}/{r['before'][1]:.0f} -> {r['after'][0]:.1f}/{r['after'][1]:.1f} levels")
        if not untouched(run(w, h, mode, seamJoin=False)):
            bad.append(f"{w}x{h} {mode}: with seamJoin off the pieces must be judged one by one, as the original program did")
    # 2. what must NOT be joined or taken
    r = run(frame=dict(y_right=0.87))
    if not untouched(r):
        bad.append(f"two short lines at different heights were taken for one joint: covered {r['cover']}")
    r = run(frame=dict(left=(0.0, 0.15), right=(1.0, 1.0)))
    if not untouched(r, sides=(0,)):
        bad.append(f"one short piece alone (15% of the width) was taken for a joint: covered {r['cover']}")
    if run(seamOn=False)["stats"]["seam_px"] != 0:
        bad.append("the tool is switched off, yet a seam was marked")
    # 3. a long piece on one side and a short one on the other: the short side is not forgotten
    r = run(frame=dict(left=(0.0, 0.40), right=(0.90, 1.0)))
    if not both_gone(r):
        bad.append(f"a long piece and a short one: covered {r['cover']}, line {r['before']} -> {r['after']} levels")
    r = run(frame=dict(weak_left=0.5))
    if not both_gone(r):
        bad.append(f"one side twice fainter than the other: covered {r['cover']}, line {r['before']} -> {r['after']} levels")
    # 4. however visible the joint is: a faint one and a really dark one (the dark one used to be left in the photo).
    #    With the corner tool on as well: on a floor that darkens towards the camera a faint joint used to pass for
    #    the wall-floor corner, and was then smeared instead of repaired.
    for dark in (2.5, 30.0):
        for cyc in (0, 65):
            r = run(frame=dict(left=(0.0, 0.30), right=(0.72, 1.0), dark=dark), cycCurve=cyc)
            if min(r["cover"]) < 0.9 or r["stats"].get("corner_row") is not None:
                bad.append(f"a joint {dark:.1f} levels dark, cyclorama {cyc}: covered {r['cover']}, 'corner' at {r['stats'].get('corner_row')}")
    # ...and the corner finder itself: no frame with nothing but a joint may give it a line
    worst = 0.0
    for seed in (7, 8, 9):
        for dark in (1.5, 2.5, 4.0):
            img_j, sil_j, _ = _joint_frame(1500, 2000, left=(0.0, 0.30), right=(0.72, 1.0), dark=dark, seed=seed)
            eng_j = H.make_engine(E, sil_j)
            fg_j, core_j = eng_j._clean_fg_mask(_quiet(eng_j._predict_fg_raw, img_j), 1500, 2000, 70.0)
            st_j, _, sk_j, _ = eng_j._compute_protection_maps_small(img_j, fg_j, core_j, 80.0, False, True)
            if eng_j._corner_line_of_frame(img_j, fg_j, st_j, sk_j) is not None:
                worst = max(worst, dark)
    if worst:
        bad.append(f"a faint floor joint (up to {worst} levels dark) was taken for the wall-floor corner")
    # 5. together with the wall-floor corner: the corner is found where it is, the joint is repaired on both sides
    for cyc in (0, 65):
        r = run(frame=dict(corner=True), cycCurve=cyc)
        row = r["stats"].get("corner_row")
        if not both_gone(r):
            bad.append(f"corner + joint, cyclorama {cyc}: joint covered {r['cover']}, line {r['before']} -> {r['after']} levels")
        if cyc and (row is None or abs(row - 0.62) > 0.012):
            bad.append(f"corner + joint: the corner was looked for at {row} of the height, it is at 0.62")
        if cyc:
            h, w = r["img"].shape[:2]
            rows = slice(int(h * 0.50), int(h * 0.74))
            for name, cols in (("left", slice(int(w * 0.02), int(w * 0.16))), ("right", slice(int(w * 0.86), int(w * 0.98)))):
                s0, s1 = _step(r["img"], rows, cols), _step(r["comp"], rows, cols)
                if s1 > 0.40 * s0:
                    bad.append(f"corner + joint: the corner line on the {name} went from {s0:.1f} to {s1:.1f} levels only")
            notes.append(f"with the corner: found at {row:.3f} of the height (drawn at 0.620), joint and corner both removed")
    # A corner with a hair-thin dark crease in it. With the corner tool on, the seam search leaves that strip alone:
    # a strip repaired there blurs the corner and gets in the way of the tool. With the tool off the crease is a
    # line like any other and is repaired.
    w, h = 1500, 2000
    rng = np.random.default_rng(9)
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    xx = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    floor = (yy >= 0.62).astype(np.float32)
    lum = (150.0 * (1 - floor) + 172.0 * floor) * (1.0 - 0.22 * (((xx - 0.5) * 2) ** 2) - 0.10 * (((yy - 0.45) * 2) ** 2))
    lum = np.broadcast_to(lum, (h, w)).astype(np.float32).copy()
    lum[int(h * 0.62) - 1:int(h * 0.62) + 1] -= 8.0
    creased = np.clip(cv2.GaussianBlur(lum, (0, 0), 0.8)[..., None] * np.float32([1.02, 1.0, 0.97]) + rng.standard_normal((h, w, 3)).astype(np.float32) * 1.8, 0, 255).astype(np.uint8)
    _, sil_std = H.make_studio_image(w, h, n_dust=0, n_hair=0, seed=1)
    creased[cv2.resize(sil_std, (w, h)) > 0.5] = (40, 40, 46)
    strip = slice(int(h * (0.62 - 0.012)), int(h * (0.62 + 0.012)))
    rows_c = slice(int(h * 0.50), int(h * 0.74))
    for cyc in (0, 65):
        oc = {}
        out, stats = _quiet(H.make_engine(E, sil_std).process, creased, 8, dict(base, speedMode="fast", cycCurve=cyc), out_cache=oc)
        marked = int((oc["heal_mask_full"][strip] > 0).sum())
        comp = _comp(creased, out)
        kept = max(_step(comp, rows_c, b) / _step(creased, rows_c, b) for b in (slice(int(w * 0.04), int(w * 0.24)), slice(int(w * 0.76), int(w * 0.96))))
        if cyc and (marked != 0 or kept > 0.35 or stats.get("corner_row") is None):
            bad.append(f"corner with a crease, cyclorama {cyc}: {marked} px marked for repair inside the corner strip, line kept {kept * 100:.0f}%, corner at {stats.get('corner_row')}")
        if not cyc and marked < 0.5 * w * 4:
            bad.append(f"corner with a crease, cyclorama off: the crease must be repaired as a line, {marked} px marked")

    # A soft corner (a step the seam search does not take for a line) with a crease along its right third only. A
    # dark backdrop gives that: the corner is a thin line here and nothing there. With the corner tool off nobody
    # takes the line, and a line repaired in pieces is a dashed, hard-edged remainder - so nothing inside the corner
    # strip may be repaired at all.
    soft = 1.0 / (1.0 + np.exp(-np.clip((yy - 0.62) * 220.0, -50, 50)))
    lum_p = np.broadcast_to((150.0 * (1 - soft) + 172.0 * soft) * (1.0 - 0.22 * (((xx - 0.5) * 2) ** 2) - 0.10 * (((yy - 0.45) * 2) ** 2)), (h, w)).astype(np.float32).copy()
    lum_p[int(h * 0.62) - 1:int(h * 0.62) + 1, int(w * 0.66):] -= 8.0
    part = np.clip(cv2.GaussianBlur(lum_p, (0, 0), 0.8)[..., None] * np.float32([1.02, 1.0, 0.97]) + rng.standard_normal((h, w, 3)).astype(np.float32) * 1.8, 0, 255).astype(np.uint8)
    person_p = cv2.resize(sil_std, (w, h)) > 0.5
    part[person_p] = (40, 40, 46)
    seen_p = ~person_p[int(h * 0.62)]

    def strip_marked(rule_on, **over):
        """(pixels marked for repair inside the corner strip, share of the visible corner they cover)"""
        eng_p = H.make_engine(E, sil_std)
        if not rule_on:  # the search as it is without the "whole line or nothing" rule
            eng_p._whole_line_repair_only = lambda mask, line, fg, need=0.85: mask
        oc_p = {}
        _quiet(eng_p.process, part, 8, dict(base, speedMode="fast", **over), out_cache=oc_p)
        m = oc_p["heal_mask_full"][strip] > 0
        return int(m.sum()), float(m.any(axis=0)[seen_p].mean())

    (pieces, cover_p), (kept_p, _) = strip_marked(False), strip_marked(True)
    if pieces < 2000 or not 0.25 < cover_p < 0.75:
        bad.append(f"the test frame is not what it should be: without the rule the seam search marks {pieces} px, {cover_p * 100:.0f}% of the corner")
    if kept_p != 0:
        bad.append(f"corner creased on one side, cyclorama off: {kept_p} px of it are repaired (a dashed remainder); it must be the whole line or nothing")
    if strip_marked(True, cycCurve=65)[0] != 0:
        bad.append("corner creased on one side, cyclorama 65: the corner strip belongs to the corner tool, nothing may be marked in it")
    # the rule itself: a line repaired along (nearly) all of its visible length stays, a part of it goes
    for cover, slope, expect_kept in ((1.0, 0.0, True), (0.9, 0.02, True), (0.6, 0.0, False), (0.3, -0.03, False)):
        mh, mw = 600, 900
        m = np.zeros((mh, mw), np.uint8)
        fgm = np.zeros((mh, mw), np.uint8)
        fgm[:, 380:520] = 255                                   # the person hides the middle of the line
        line = {"row": 300.0, "slope": slope, "half": 14.0}
        xs = np.arange(mw)
        seen = np.flatnonzero(fgm[300, :] < 40)
        for x in seen[: int(round(cover * seen.size))]:
            yc = int(round(300.0 + slope * (x - (mw - 1) / 2.0)))
            m[yc - 2:yc + 3, x] = 1
        m[80:90, 100:300] = 1                                    # a joint elsewhere on the floor: never touched
        before = m.copy()
        got = ENG._whole_line_repair_only(m, line, fgm)
        strip_px = int(np.count_nonzero(got[250:350]))
        if not np.array_equal(got[:200], before[:200]) or (strip_px > 0) != expect_kept or (expect_kept and not np.array_equal(got, before)):
            bad.append(f"whole-line rule: a repair over {cover * 100:.0f}% of the visible corner (slope {slope}) -> {'kept' if strip_px else 'dropped'}")

    # a floor joint without any corner in the frame is not a corner (it used to be taken for one and smeared)
    r = run(cycCurve=65)
    if r["stats"].get("corner_row") is not None or not both_gone(r):
        bad.append(f"a joint in a frame without a corner: 'corner' at {r['stats'].get('corner_row')}, joint covered {r['cover']}")

    # 6. What only looks like the pieces of a joint (version 4.5.0 repaired both as one; found on the owner's frames).
    # a) Two short lines that stand at one height by chance - a scratch at each border of the frame. Next to a narrow
    #    person the floor between them is in plain view and shows no line; a joint would be seen there. Behind a wide
    #    dress the very same two pieces are one joint.
    ends = dict(left=(0.0, 0.16), right=(0.84, 1.0))
    for mode in ("fast", "quality"):
        r = run(mode=mode, frame=dict(ends, narrow=True))
        if not untouched(r):
            bad.append(f"{mode}: two short lines with the floor in plain view between them were repaired as one joint: covered {r['cover']}")
        r = run(mode=mode, frame=dict(ends))
        if not both_gone(r):
            bad.append(f"{mode}: the same two pieces behind a wide dress are one joint: covered {r['cover']}, line {r['before']} -> {r['after']} levels")
    # b) A thin line along the edge of a lit area: the floor is lighter on one of its sides. A strip repaired there
    #    smears the light. (The line is drawn low on the floor: higher up a straight edge from border to border is
    #    the wall-floor corner and belongs to the corner check.)
    low = dict(y_left=0.88, y_right=0.88)
    for edge in (14.0, -14.0, 10.0):
        r = run(frame=dict(low, step=edge))
        if not untouched(r):
            bad.append(f"a thin line along the edge of a lit area ({edge:+.0f} levels) was repaired as a joint: covered {r['cover']}")
    for edge in (0.0, 5.5):  # ...but a floor that is a little lighter on one side of a joint is still a floor with a joint
        r = run(frame=dict(low, step=edge))
        if not both_gone(r):
            bad.append(f"a joint with the floor {edge} levels lighter on one side: covered {r['cover']}, line {r['before']} -> {r['after']} levels")
    # c) The rules themselves, on drawn arrays.
    #    The floor in plain view between two pieces: 1000 columns, the pieces take 160 at each border, the person 100.
    seen = np.ones((400, 1000), np.float32)
    seen[:, 450:550] = 0.0
    spans, level = [(0, 160), (840, 160)], {"slope": 0.0, "offs": 200.0, "xc": 80.0}

    def in_view(cand, lead=level):
        return ENG._seam_floor_in_view(spans, lead, np.cumsum(cand, axis=0, dtype=np.int32), seen, 7.0)

    nothing = np.zeros((400, 1000), np.uint8)
    on_line, off_line, slanted = nothing.copy(), nothing.copy(), nothing.copy()
    on_line[198:203, 300:420] = 1          # something thin the search saw on the course of the line (not a piece)
    off_line[150:153, 600:700] = 1         # ...and away from it
    for x in range(600, 720):
        slanted[int(round(199.2 + 0.03 * x)), x] = 1
    got = (in_view(nothing), in_view(on_line), in_view(off_line), in_view(slanted), in_view(slanted, {"slope": 0.03, "offs": 199.2, "xc": 80.0}))
    if got != (580, 460, 580, 580, 460):
        bad.append(f"floor in plain view between two pieces: {got}, expected (580, 460, 580, 580, 460)")
    #    A piece is looked at along its own course. A bent joint: across a straight line laid through it the line
    #    smears out (on the owner's black frame it kept a fifth of its strength and the joint was dropped).
    ph, pw = 400, 900
    xs_p = np.arange(150, 750)
    course = 200.0 + 24.0 * ((xs_p - 150) / 600.0) ** 2
    floor = (120.0 + 0.05 * np.arange(ph, dtype=np.float32)[:, None]) * np.ones((1, pw), np.float32)
    away = np.abs(np.arange(ph, dtype=np.float32)[:, None] - np.interp(np.arange(pw), xs_p, course)[None, :])
    inside = (np.arange(pw)[None, :] >= 150) & (np.arange(pw)[None, :] < 750)
    bent = floor.copy()
    bent[(away <= 1.0) & inside] -= 8.0
    bent[(away <= 3.5) & inside] -= 1.6
    y0, bh = 198, 30
    comp = ((away <= 1.0) & inside)[y0:y0 + bh, 150:750]
    path = ENG._seam_piece_path(comp, comp.astype(np.float32), y0)
    slope, offs = (float(v) for v in np.polyfit(xs_p, course, 1))
    piece = {"box": (150, y0, 600, bh), "path": path, "slope": slope, "offs": offs}
    everything = np.ones((ph, pw), np.float32)
    along = ENG._seam_piece_check(bent, everything, piece)
    across = ENG._seam_piece_check(bent, everything, dict(piece, path=None))
    level_piece = {"box": (150, 190, 600, 20), "path": np.full(600, 200.0, np.float32), "slope": 0.0, "offs": 200.0}
    line = floor.copy()
    line[199:202] -= 8.0
    plain = ENG._seam_piece_check(line, everything, level_piece)
    if float(np.abs(path - course).max()) > 1.5:
        bad.append(f"the course of a bent piece is off by {np.abs(path - course).max():.1f} rows")
    if along is None or across is None or along[0] < 0.9 * plain[0] or across[0] > 0.5 * along[0] or abs(along[1]) > 1.0:
        bad.append(f"a bent joint: along its own course {along}, across a straight line {across}, a straight joint {plain}")
    #    ...what the profile says: a joint on a floor that gets lighter towards the camera has no step, a slow slope of
    #    the light is no line, the edge of a lit area gives its height, and too little backdrop gives no answer.
    slow = ENG._seam_piece_check(floor + 0.5 * np.clip(np.arange(ph, dtype=np.float32)[:, None] - 180.0, 0.0, 40.0), everything, level_piece)
    if abs(plain[1]) > 0.5 or slow[0] > 0.1 * plain[0] or abs(slow[1]) > 0.5:
        bad.append(f"profile of a joint {plain} (no step expected), of a slow slope {slow} (no line, no step expected)")
    for height in (12.0, -12.0, 5.0):
        edge_img = floor.copy()
        edge_img[200:] += height
        got_step = ENG._seam_piece_check(cv2.GaussianBlur(edge_img, (0, 0), 1.2), everything, level_piece)[1]
        if abs(got_step - height) > 0.5:
            bad.append(f"the edge of a lit area, {height:+.0f} levels: the profile says {got_step:+.1f}")
    hidden = everything.copy()
    hidden[:, 150:650] = 0.0
    if ENG._seam_piece_check(line, hidden, level_piece) is not None:
        bad.append("a piece with five sixths of the backdrop around it hidden must give no answer")
    notes.append("two scratches at one height are not a joint, a line along the edge of a lit area is not a joint")
    report("seam", not bad, "; ".join(notes) + "; two different lines and a lone short piece are left alone; faint and dark joints alike, "
           "with the corner tool on or off; a corner is repaired as a whole line or not at all"
           if not bad else "wrong:\n  " + "\n  ".join(bad))


# ----------------------------------------------------------------------------------------------------------------------
# The "Маска" view and the brush when the whole backdrop is evened
# ----------------------------------------------------------------------------------------------------------------------
def check_mask():
    """
    With the stain / blur / corner stages on, the layer covers the whole backdrop. The mask view must still tell
    what was found and repaired (bright green) from what is only evened (pale green), "mask_share" must count the
    former, and the brush and the eraser must keep working.
    """
    bad = []
    w, h = 1500, 2000
    pw, ph = int(round(w * 1080.0 / max(w, h))), int(round(h * 1080.0 / max(w, h)))  # the working size of the window
    img, sil = H.make_studio_image(w, h, n_dust=60, n_hair=4, seed=77)
    speck = (int(w * 0.25), int(h * 0.35))          # a mark on the wall that the search is not allowed to take (see `quiet`)
    cv2.circle(img, speck, 7, tuple(int(v) - 45 for v in img[speck[1], speck[0]]), -1, lineType=cv2.LINE_AA)
    on = dict(H.STD, speedMode="fast", smokeAuto=True)   # "Сліди взуття та розводи" 65: the whole backdrop is evened
    off = dict(on, scuffs=0, blur=0, cycCurve=0)          # only what the search finds is repaired

    def opened(params, image=img):
        eng = H.make_engine(E, sil)
        return eng, _quiet(eng.start_session, image, 8, dict(params))

    def jpg(b64):
        """A picture of the window, brought to the working size the masks have (it is sent larger: check_sharp)."""
        import base64
        pic = cv2.imdecode(np.frombuffer(base64.b64decode(b64), np.uint8), cv2.IMREAD_COLOR)
        if pic.shape[0] > ph:
            pic = cv2.resize(pic, (pw, ph), interpolation=cv2.INTER_AREA)
        return pic.astype(np.float32)

    def counted(eng):
        s = eng._active_session
        eff = eng._compute_effective_mask_small(s)
        return (float(np.count_nonzero(eng._compute_marked_mask_small(s, eff) > 127)) / eff.size, float(np.count_nonzero(eff > 127)) / eff.size)

    def agrees(eng, r):
        mk, ly = counted(eng)
        return abs(r["mask_share"] - mk) <= 1e-4 and abs(r["layer_share"] - ly) <= 1e-4

    # 1. the two numbers
    e_on, r_on = opened(on)
    e_off, r_off = opened(off)
    if not agrees(e_on, r_on) or not agrees(e_off, r_off):
        bad.append("mask_share / layer_share differ from the masks on screen")
    if abs(r_off["mask_share"] - r_off["layer_share"]) > 1e-9:
        bad.append(f"nothing but repairs: the two shares must be the same, got {r_off['mask_share']} / {r_off['layer_share']}")
    if not (r_on["layer_share"] > 0.6 and 0.0 < r_on["mask_share"] < 0.25):
        bad.append(f"backdrop evened: layer_share {r_on['layer_share']}, mask_share {r_on['mask_share']}")
    if abs(r_on["mask_share"] - r_off["mask_share"]) > 0.35 * r_off["mask_share"] + 0.002:
        bad.append(f"the repaired share must not depend on the evening of the backdrop: {r_off['mask_share']} without it, {r_on['mask_share']} with it")

    # 2. the picture: bright green = repaired, pale green = evened, red = left alone
    s = e_on._active_session
    layer, marked = s["auto_mask_small_u8"], s["repair_mask_small_u8"]
    ov, cp = jpg(r_on["overlay_jpg_b64"]), jpg(r_on["comp_jpg_b64"])
    green = lambda a: a[..., 1] - 0.5 * (a[..., 0] + a[..., 2])  # noqa: E731  (BGR)
    red = lambda a: a[..., 2] - 0.5 * (a[..., 0] + a[..., 1])    # noqa: E731
    k = np.ones((5, 5), np.uint8)
    z_marked = cv2.erode((marked > 200).astype(np.uint8), k) > 0
    z_evened = (cv2.erode((layer > 200).astype(np.uint8), k) > 0) & ~(cv2.dilate((marked > 20).astype(np.uint8), k) > 0)
    z_alone = cv2.erode((layer < 20).astype(np.uint8), k) > 0
    if min(int(z_marked.sum()), int(z_evened.sum()), int(z_alone.sum())) < 200:
        bad.append(f"the test frame has too little of one zone: repaired {z_marked.sum()}, evened {z_evened.sum()}, untouched {z_alone.sum()} px")
    else:
        g_m, g_e, g_a = (float(np.median((green(ov) - green(cp))[z])) for z in (z_marked, z_evened, z_alone))
        r_a, r_e = float(np.median((red(ov) - red(cp))[z_alone])), float(np.median((red(ov) - red(cp))[z_evened]))
        if not (g_m > 60.0 and 8.0 < g_e < 0.6 * g_m and g_a < 6.0 and r_a > 12.0 and r_e < 4.0):
            bad.append(f"mask colours: repaired +{g_m:.0f} green, evened +{g_e:.0f} green ({r_e:+.0f} red), untouched +{g_a:.0f} green {r_a:+.0f} red")
    # (without the evening the picture is the old one: everything in the layer is bright green)
    s0 = e_off._active_session
    if s0["repair_mask_small_u8"] is not s0["auto_mask_small_u8"]:
        bad.append("nothing but repairs: the layer and the repaired zones must be one and the same mask")

    # 3. the brush: a mark that the search left in the evened backdrop is repaired when it is painted over
    quiet = dict(on, spots=0, seamOn=False)                 # the search takes nothing; the backdrop is still evened
    px, py = speck[0] / w, speck[1] / h
    contrast = lambda a: float(np.median(a[speck[1] - 20:speck[1] + 21, speck[0] - 20:speck[0] + 21].mean(axis=2))  # noqa: E731
                               - a[speck[1] - 3:speck[1] + 4, speck[0] - 3:speck[0] + 4].mean())
    layers = {}
    for name, stroke in (("left", False), ("painted", True)):
        eng, r = opened(quiet)
        if stroke:
            rs = eng.edit_session_mask(r["session_id"], "stroke", [{"x": px, "y": py, "norm": 1}], 14.0, erase=False, dress_smooth=False, dress_strength=45.0)
            if not agrees(eng, rs) or rs["mask_share"] <= r["mask_share"]:
                bad.append(f"a brush stroke must add to the repaired share: {r['mask_share']} -> {rs.get('mask_share')}")
        out = _quiet(eng.apply_session, r["session_id"], 100.0, False, False, 45.0)[0]
        layers[name] = _comp(img, out)
    c_src, c_left, c_painted = contrast(img.astype(np.float32)), contrast(layers["left"]), contrast(layers["painted"])
    if c_left < 0.7 * c_src:
        bad.append(f"the test mark was removed without the brush ({c_src:.0f} -> {c_left:.0f} levels): nothing to prove")
    if c_painted > 0.3 * c_src:
        bad.append(f"a mark painted over with the brush is still there after Apply: {c_src:.0f} -> {c_painted:.0f} levels")
    far = np.ones((h, w), bool)
    far[speck[1] - 150:speck[1] + 151, speck[0] - 150:speck[0] + 151] = False
    if float(np.abs(layers["painted"] - layers["left"])[far].max()) > 0.0:
        bad.append("the brush stroke changed the layer away from the stroke")

    # 4. the eraser: what is erased is not touched at all, and both shares say so; fill / clear / invert / reset
    eng, r = opened(on)
    sid = r["session_id"]
    ex, ey = 0.82, 0.30                                      # plain wall
    re_ = eng.edit_session_mask(sid, "stroke", [{"x": ex, "y": ey, "norm": 1}], 40.0, erase=True, dress_smooth=False, dress_strength=45.0)
    if not agrees(eng, re_) or re_["layer_share"] >= r["layer_share"]:
        bad.append(f"an eraser stroke must take from the layer: layer_share {r['layer_share']} -> {re_.get('layer_share')}")
    out = _quiet(eng.apply_session, sid, 100.0, False, False, 45.0)[0]
    # (the eraser has a soft edge: it is at full strength within half of its circle - a square that fits in there;
    #  the edge itself is measured in check_brush)
    cy_, cx_, rad = int(ey * h), int(ex * w), int(0.3 * 40.0 * w / r["preview_w"])
    if int(out[cy_ - rad:cy_ + rad, cx_ - rad:cx_ + rad, 3].max()) != 0:
        bad.append("an erased zone is still part of the layer after Apply")
    # "fill" shows the layer on the whole frame and repaints nothing: what counts as found and repaired is what the
    # search found (the eraser stroke is forgotten); "clear" leaves nothing
    rf = eng.edit_session_mask(sid, "fill")
    fill_ok = agrees(eng, rf) and rf["layer_share"] == 1.0 and abs(rf["mask_share"] - r["mask_share"]) <= 1e-9
    rc = eng.edit_session_mask(sid, "clear")
    ra = eng.edit_session_mask(sid, "reset_auto")
    if not fill_ok or (rc["mask_share"], rc["layer_share"]) != (0.0, 0.0):
        bad.append(f"fill / clear: {rf['mask_share']}, {rf['layer_share']} (found before: {r['mask_share']}) / {rc['mask_share']}, {rc['layer_share']}")
    if abs(ra["mask_share"] - r["mask_share"]) > 1e-9 or abs(ra["layer_share"] - r["layer_share"]) > 1e-9 or not agrees(eng, ra):
        bad.append(f"'reset' must bring the automatic mask back: {r['mask_share']}, {r['layer_share']} -> {ra['mask_share']}, {ra['layer_share']}")
    ri = eng.edit_session_mask(sid, "invert")
    if not agrees(eng, ri) or abs(ri["mask_share"] - ri["layer_share"]) > 1e-9 or abs(ri["layer_share"] - (1.0 - r["layer_share"])) > 0.02:
        bad.append(f"inverted mask: {ri['mask_share']}, {ri['layer_share']} (the layer was {r['layer_share']})")
    eng.edit_session_mask(sid, "invert")

    # 5. after the sliders: the light refresh and the full recompute report the same, and more is found at a higher
    #    setting (a frame large enough for the light way: its long side is above PREVIEW_PROXY_MIN_DIM)
    big, _ = H.make_studio_image(1950, 2600, n_dust=80, n_hair=4, seed=78)
    more = dict(on, spots=95)
    e1, r1 = opened(on, big)
    rq = _quiet(e1.recompute_session, r1["session_id"], dict(more), True, None, True)
    e2, r2 = opened(on, big)
    rfull = _quiet(e2.recompute_session, r2["session_id"], dict(more), True, None, False)
    if rq.get("quick") is not True or rfull.get("quick") is not False:
        bad.append(f"recompute: the light way was {rq.get('quick')}, the full way {rfull.get('quick')}")
    if not agrees(e1, rq) or not agrees(e2, rfull):
        bad.append("recompute: the shares differ from the masks on screen")
    if abs(rq["mask_share"] - rfull["mask_share"]) > 0.004 or abs(rq["layer_share"] - rfull["layer_share"]) > 0.004:
        bad.append(f"light refresh vs full recompute: mask_share {rq['mask_share']} / {rfull['mask_share']}, layer_share {rq['layer_share']} / {rfull['layer_share']}")
    if rq["mask_share"] <= r1["mask_share"]:
        bad.append(f"a more sensitive search must find more: {r1['mask_share']} -> {rq['mask_share']}")
    # Apply after a light refresh computes the real frame; the masks must stay the ones that were on screen
    before = counted(e1)
    _quiet(e1.apply_session, r1["session_id"], 100.0, False, False, 45.0)
    after = counted(e1)
    if abs(before[0] - after[0]) > 0.004 or abs(before[1] - after[1]) > 0.004:
        bad.append(f"Apply after a light refresh changed the masks: {before} -> {after}")
    # 6. two passes: what the second pass repaired is marked too (big dark marks: the stand-in repair leaves a smudge
    #    of them for the second pass to find)
    marks = img.copy()
    rng = np.random.default_rng(3)
    for i in range(10):
        mx, my = int(rng.uniform(0.08, 0.92) * w), int(rng.uniform(0.66, 0.95) * h)
        if abs(mx - w // 2) < 0.2 * w:
            mx = int(0.15 * w) + i * 20
        cv2.circle(marks, (mx, my), 12, tuple(int(max(0, int(v) - 70)) for v in marks[my, mx]), -1, lineType=cv2.LINE_AA)
    oc = {}
    _quiet(H.make_engine(E, sil).process, marks, 8, dict(on, cleanPasses=2), out_cache=oc)
    second = 0 if oc.get("heal_mask_pass2") is None else int((oc["heal_mask_pass2"] > 0).sum())
    e3, r3 = opened(dict(on, cleanPasses=2), marks)
    e4, r4 = opened(on, marks)
    if second < 100:
        bad.append(f"two passes: the test frame gave the second pass nothing to repair ({second} px)")
    elif not agrees(e3, r3) or r3["mask_share"] <= r4["mask_share"]:
        bad.append(f"two passes: the second pass repaired {second} px, yet mask_share is {r3['mask_share']} (one pass: {r4['mask_share']})")
    report("mask", not bad, f"backdrop evened: the layer covers {r_on['layer_share'] * 100:.0f}% of the frame, {r_on['mask_share'] * 100:.1f}% of the frame is marked as "
                            f"found and repaired (bright green), the rest of the layer is pale green; a brushed mark is repaired at Apply ({c_src:.0f} -> {c_painted:.0f} levels), "
                            f"an erased zone is left alone; light refresh == full recompute" if not bad else "wrong:\n  " + "\n  ".join(bad))


def check_brush():
    """
    The brush and the eraser of the big window since 4.7.0 (engine.py: "the brush and the eraser of the big window").
    A drawn frame with nothing to find, and nothing searched for or evened (`off`): whatever differs from the photo
    was made by the brush. The engine constants named in the messages are the rules that each part pins down.
    """
    import base64
    bad = []
    w, h = 1500, 2000
    clean, sil = H.make_studio_image(w, h, n_dust=0, n_hair=0, seed=501)
    off = dict(H.STD, speedMode="fast", smokeOn=False, spots=0, scuffs=0, blur=0, cycCurve=0, seamOn=False)
    on = dict(H.STD, speedMode="fast", smokeAuto=True)   # the backdrop is evened: the layer covers it
    lum = lambda a: a.astype(np.float32).mean(axis=2)                               # noqa: E731
    tone = lambda a, s=8.0: cv2.GaussianBlur(lum(a), (0, 0), s)                     # noqa: E731
    grain = lambda a: lum(a) - cv2.GaussianBlur(lum(a), (0, 0), 3.0)                # noqa: E731
    person = cv2.resize(sil, (w, h), interpolation=cv2.INTER_LINEAR)
    inner = cv2.erode((person > 0.9).astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
    backdrop = person < 0.02
    far = np.zeros((h, w), bool)
    far[int(0.05 * h):int(0.15 * h), int(0.05 * w):int(0.30 * w)] = True

    def opened(image, params=off, bits=8):
        eng = H.make_engine(E, sil)
        return eng, _quiet(eng.start_session, image, bits, dict(params))

    def edit(eng, r, op):
        return eng.edit_session_mask(r["session_id"], op)

    def stroke(eng, r, pts, radius, erase=False, softness=None):
        return eng.edit_session_mask(r["session_id"], "stroke", [{"x": x, "y": y, "norm": 1} for x, y in pts], float(radius), erase, False, 45.0, softness)

    def layer(eng, r):
        return _quiet(eng.apply_session, r["session_id"], 100.0, False, False, 45.0)[0]

    def edge(line):
        """(pixels between 10 % and 90 % of the layer, the largest step from one pixel to the next) along a line across the edge"""
        return int(((line > 0.1) & (line < 0.9)).sum()), float(np.abs(np.diff(line)).max())

    # ---- 1. a lamp spot with three specks in it: painted over, it is gone; the edge of the stroke; window == layer
    spot = (int(0.22 * w), int(0.30 * h))
    m = np.zeros((h, w), np.float32)
    cv2.circle(m, spot, 70, 1.0, -1)
    lamp = 14.0 * cv2.GaussianBlur(m, (0, 0), 18)[..., None]
    spotted = np.clip(clean.astype(np.float32) + lamp, 0, 255).astype(np.uint8)
    for dx, dy in ((-25, 6), (12, -18), (30, 22)):
        cv2.circle(spotted, (spot[0] + dx, spot[1] + dy), 3, (70, 70, 70), -1, lineType=cv2.LINE_AA)
    eng, r = opened(spotted)
    rad = 60.0 * w / r["preview_w"]                       # the brush circle in pixels of the frame
    seen = {}
    t_stroke = 0.0
    for name, softness in (("soft", 1.0), ("hard", 0.0), ("unsaid", None)):
        edit(eng, r, "reset_auto")
        t1 = time.perf_counter()
        rs = stroke(eng, r, [(0.19, 0.30), (0.25, 0.302)], 60, softness=softness)
        t_stroke = max(t_stroke, time.perf_counter() - t1)
        out = layer(eng, r)
        res = _comp(spotted, out)
        a = out[..., 3].astype(np.float32) / 255.0
        core, band = a >= 0.98, (a > 0.02) & (a < 0.98)
        err = tone(res) - tone(clean)
        seen[name] = dict(out=out, rs=rs, res=res, a=a, core_err=float(np.abs(err[core]).max()), band_err=float(np.abs(err[band]).max()),
                          g=[float(grain(res)[z].std()) for z in (far, core, band)], darkest=float(res[core].min()),
                          edge=edge(a[spot[1]:spot[1] + int(2.0 * rad), spot[0]]), core=core)
    soft, hard = seen["soft"], seen["hard"]
    was = float((tone(spotted) - tone(clean))[soft["core"]].max())
    if was < 8.0:
        bad.append(f"the test spot is too faint ({was:.1f} levels): nothing to prove")
    for name in ("soft", "hard"):
        v = seen[name]
        if v["core_err"] > 1.0 or v["band_err"] > 1.5:
            bad.append(f"{name} brush over a lamp spot of {was:.0f} levels: the tone is off by {v['core_err']:.2f} levels in the middle of the stroke, "
                       f"{v['band_err']:.2f} in its edge (the tone must go on from the backdrop around)")
        g_far, g_core, g_band = v["g"]
        if not (0.9 * g_far <= g_core <= 1.12 * g_far and 0.9 * g_far <= g_band <= 1.12 * g_far):
            bad.append(f"{name} brush: the grain of the painted zone is {g_core:.2f} in the middle and {g_band:.2f} in the edge, {g_far:.2f} on the untouched backdrop")
        if v["darkest"] < float(clean[v["core"]].min()) - 8.0:
            bad.append(f"{name} brush: a speck is still there (darkest pixel {v['darkest']:.0f}, the clean backdrop has {int(clean[v['core']].min())})")
    (ws, ss), (wh, sh_) = soft["edge"], hard["edge"]
    if ws < 0.45 * rad or ss > 0.03:
        bad.append(f"soft brush (BRUSH_SOFT_BAND): the edge of a stroke goes from 10 % to 90 % over {ws} px, largest step {ss:.3f} (circle {rad:.0f} px: at least {0.45 * rad:.0f} px, at most 0.030)")
    if wh > 0.25 * rad or sh_ < 2.5 * ss:
        bad.append(f"hard brush (BRUSH_HARD_BAND): the edge of a stroke goes from 10 % to 90 % over {wh} px, largest step {sh_:.3f} (soft: {ws} px, {ss:.3f})")
    if not np.array_equal(seen["unsaid"]["out"], soft["out"]):
        bad.append("a stroke that does not name its edge must be a soft one")
    # (the window shows what the layer gets)
    win = cv2.imdecode(np.frombuffer(base64.b64decode(soft["rs"]["comp_jpg_b64"]), np.uint8), cv2.IMREAD_COLOR)
    small = cv2.resize(np.clip(soft["res"], 0, 255).astype(np.uint8), (win.shape[1], win.shape[0]), interpolation=cv2.INTER_AREA)
    zone = cv2.resize(soft["a"], (win.shape[1], win.shape[0]), interpolation=cv2.INTER_AREA) > 0.02
    dw = np.abs(cv2.GaussianBlur(lum(small) - lum(win), (0, 0), 3.0))
    if float(dw[zone].max()) > float(dw[~zone].max()) + 0.6:
        bad.append(f"the window shows a painted zone {dw[zone].max():.2f} levels away from what the layer gets (elsewhere the two pictures differ by {dw[~zone].max():.2f})")

    # ---- 2. the person: the soft brush never touches it, the hard brush repaints what it passes over
    eng, r = opened(clean)
    box = np.zeros((h, w), bool)
    box[int(0.74 * h):int(0.78 * h), int(0.40 * w):int(0.60 * w)] = True
    for name, softness in (("soft", 1.0), ("hard", 0.0)):
        edit(eng, r, "reset_auto")
        stroke(eng, r, [(0.40, 0.76), (0.60, 0.76)], 22, softness=softness)   # across both legs
        out = layer(eng, r)
        d = np.abs(_comp(clean, out) - clean.astype(np.float32)).max(axis=2)
        a = out[..., 3]
        if name == "soft":
            if int(a[inner].max()) != 0 or float(d[inner].max()) != 0.0:
                bad.append(f"the soft brush touched the person (layer {int(a[inner].max())} of 255 there, changed by {d[inner].max():.0f} levels)")
            if int(a[box & backdrop].max()) != 255 or float(a[box & backdrop].mean()) < 120.0:
                bad.append(f"the soft brush must still paint the floor between and beside the legs (layer there: at most {int(a[box & backdrop].max())}, mean {a[box & backdrop].mean():.0f} of 255)")
        elif float((d[box & inner] > 8.0).mean()) < 0.9:
            bad.append(f"the hard brush must repaint what it passes over (a prop taken for a person): changed {100 * (d[box & inner] > 8.0).mean():.0f} % of the legs it crossed")

    # ---- 3. determinism: Apply twice gives the same layer; a stroke elsewhere leaves a painted zone as it was
    edit(eng, r, "reset_auto")
    stroke(eng, r, [(0.19, 0.30), (0.25, 0.302)], 40)
    one = layer(eng, r)
    again = layer(eng, r)
    stroke(eng, r, [(0.80, 0.20), (0.85, 0.21)], 40)
    two = layer(eng, r)
    z1 = one[..., 3] > 0
    if not np.array_equal(one, again):
        bad.append("Apply twice in a row gave two different layers")
    if not np.array_equal(one[z1], two[z1]) or int((two[..., 3] > 0).sum()) <= int(z1.sum()):
        bad.append("a second stroke elsewhere changed the zone painted first")

    # ---- 4. "fill": the whole layer is visible, nothing is repainted, and a step back takes it away
    e_on, r_on = opened(clean, on)
    for (eng_, r_, name) in ((eng, r, "nothing searched"), (e_on, r_on, "backdrop evened")):
        edit(eng_, r_, "reset_auto")
        plain = layer(eng_, r_)
        rf = edit(eng_, r_, "fill")
        filled = layer(eng_, r_)
        edit(eng_, r_, "undo")
        back = layer(eng_, r_)
        if int(filled[..., 3].min()) != 255 or rf["layer_share"] != 1.0:
            bad.append(f"fill ({name}): the layer must cover the whole frame (least {int(filled[..., 3].min())} of 255, layer_share {rf['layer_share']})")
        if not np.array_equal(filled[..., :3], plain[..., :3]) or not np.array_equal(filled[..., :3][inner], clean[inner]):
            n_px = int(np.any(filled[..., :3] != plain[..., :3], axis=2).sum())
            bad.append(f"fill ({name}) must repaint nothing: {n_px} px of the layer differ from the layer without it, "
                       f"{int(np.any(filled[..., :3][inner] != clean[inner], axis=1).sum())} px of the person differ from the photo")
        if not np.array_equal(back, plain):
            bad.append(f"fill ({name}): a step back must bring the layer back as it was")

    # ---- 5. the eraser: what it erases is gone from the layer, softly or with a hard edge
    cx, cy = int(0.83 * w), int(0.305 * h)
    rad_e = 40.0 * w / r_on["preview_w"]
    edit(e_on, r_on, "reset_auto")
    if int(layer(e_on, r_on)[cy, cx, 3]) != 255:
        bad.append("the test place of the eraser is not in the layer: nothing to prove")
    erased = {}
    for name, softness in (("soft", 1.0), ("hard", 0.0)):
        edit(e_on, r_on, "reset_auto")
        stroke(e_on, r_on, [(0.80, 0.30), (0.86, 0.31)], 40, erase=True, softness=softness)
        a = layer(e_on, r_on)[..., 3].astype(np.float32) / 255.0
        erased[name] = edge(a[cy:cy + int(2.0 * rad_e), cx])
        if float(a[cy, cx]) != 0.0:
            bad.append(f"{name} eraser: the middle of the stroke is still in the layer ({a[cy, cx]:.2f})")
    (ws_e, ss_e), (wh_e, sh_e) = erased["soft"], erased["hard"]
    if ws_e < 0.45 * rad_e or ss_e > 0.04:
        bad.append(f"soft eraser: the edge of the erased zone goes from 10 % to 90 % over {ws_e} px, largest step {ss_e:.3f} (circle {rad_e:.0f} px)")
    if wh_e > 0.25 * rad_e or sh_e < 2.5 * ss_e:
        bad.append(f"hard eraser: the edge of the erased zone goes from 10 % to 90 % over {wh_e} px, largest step {sh_e:.3f} (soft: {ws_e} px, {ss_e:.3f})")

    # ---- 6. a hard-edged shadow on the wall (30 % darker)
    sh = np.zeros((h, w), np.float32)
    sh[int(0.38 * h):int(0.56 * h), int(0.04 * w):int(0.20 * w)] = 1.0
    sh = cv2.GaussianBlur(sh, (0, 0), 3.0)
    shaded_f = clean.astype(np.float32) * (1.0 - 0.30 * sh)[..., None]
    shaded = np.clip(shaded_f, 0, 255).astype(np.uint8)
    dark, lit = sh > 0.98, sh < 0.02
    # (a) a stroke along its edge: half of the surroundings is shadow, half is lit wall - the tone stays (BRUSH_SECOND;
    #     the two halves are told apart with BRUSH_FIT_TOL)
    eng, r = opened(shaded)
    stroke(eng, r, [(0.20, 0.42), (0.20, 0.52)], 14)
    out = layer(eng, r)
    err = cv2.GaussianBlur(lum(_comp(shaded, out)) - lum(shaded), (0, 0), 4.0)
    z = out[..., 3] > 128
    e_dark, e_lit, e_max = float(err[z & dark].mean()), float(err[z & lit].mean()), float(np.abs(err[out[..., 3] > 0]).max())
    if abs(e_dark) > 4.0 or abs(e_lit) > 4.0 or e_max > 8.0:
        bad.append(f"a stroke along the edge of a shadow (BRUSH_SECOND, BRUSH_FIT_TOL): the shadow side changed by {e_dark:+.1f} levels, the lit side by {e_lit:+.1f}, "
                   f"at most {e_max:.1f} - the edge was smeared")
    # (b) a stroke on the lit wall whose end only touches the shadow, over a light stain: the wall keeps its tone
    #     (BRUSH_MOST, BRUSH_ODD_K: the shadow is left out) and the stain is evened (the tone does not simply stay)
    sc = (int(0.27 * w), int(0.47 * h))
    m = np.zeros((h, w), np.float32)
    cv2.circle(m, sc, 16, 1.0, -1)
    stained = np.clip(shaded_f + 12.0 * cv2.GaussianBlur(m, (0, 0), 6)[..., None], 0, 255).astype(np.uint8)
    mid = (slice(sc[1] - 10, sc[1] + 11), slice(sc[0] - 10, sc[0] + 11))
    eng, r = opened(stained)
    stroke(eng, r, [(0.225, 0.47), (0.31, 0.47)], 14)
    out = layer(eng, r)
    err = cv2.GaussianBlur(lum(_comp(stained, out)) - lum(shaded), (0, 0), 4.0)   # against the frame without the stain
    stain = float(cv2.GaussianBlur(lum(stained) - lum(shaded), (0, 0), 4.0)[mid].mean())
    left, wall = float(err[mid].mean()), float(np.abs(err[(out[..., 3] > 0) & lit]).max())
    if abs(left) > 0.3 * stain:
        bad.append(f"a stain next to a shadow, painted over: {stain:.1f} -> {left:+.1f} levels (the stroke only touches the shadow: the tone must not simply stay, BRUSH_SECOND)")
    if wall > 3.0:
        bad.append(f"a stroke that touches a shadow changed the lit wall by {wall:.1f} levels (BRUSH_MOST, BRUSH_ODD_K: the shadow must be left out of the tone)")

    # ---- 7. nearly the whole backdrop painted over, a strip is left: the tone stays, the grain is still the frame's own
    rows = [0.03 + 0.055 * i for i in range(18)]
    path = []
    for i, y in enumerate(rows):
        path += [(0.0, y), (0.84, y)] if i % 2 == 0 else [(0.84, y), (0.0, y)]
    eng, r = opened(clean)
    stroke(eng, r, path, 60)
    painted = float((eng._brush_strength_small(eng._active_session) > 0).mean())
    t1 = time.perf_counter()
    out = layer(eng, r)
    t_big = time.perf_counter() - t1
    res = _comp(clean, out)
    d = np.abs(tone(res, 4.0) - tone(clean, 4.0))[backdrop]
    if painted < 0.75:
        bad.append(f"the test strokes cover only {100 * painted:.0f} % of the window: nothing to prove")
    if float(d.mean()) > 0.5 or float(np.percentile(d, 99)) > 2.0:
        bad.append(f"the whole backdrop painted over (BRUSH_RING_MIN): its tone changed by {d.mean():.1f} levels on average, {np.percentile(d, 99):.1f} at the 99th percentile")
    if float(np.abs(res - clean.astype(np.float32))[inner].max()) != 0.0:
        bad.append("the whole backdrop painted over: the person changed")
    if not 0.9 <= float(grain(res)[far].std()) / float(grain(clean)[far].std()) <= 1.12:
        bad.append(f"the whole backdrop painted over: grain {grain(clean)[far].std():.2f} -> {grain(res)[far].std():.2f}")

    # ---- 8. a 16-bit frame
    clean16, _ = H.make_studio_image(w, h, n_dust=0, n_hair=0, seed=501, bit16=True)
    spotted16 = np.clip(clean16.astype(np.float32) + 128.0 * lamp, 0, 32768).astype(np.uint16)
    eng, r = opened(spotted16, bits=16)
    stroke(eng, r, [(0.19, 0.30), (0.25, 0.302)], 60)
    out = layer(eng, r)
    a = out[..., 3:4].astype(np.float32) / 32768.0
    res16 = (spotted16.astype(np.float32) * (1.0 - a) + out[..., :3].astype(np.float32) * a) / 128.0
    err16 = float(np.abs((tone(res16) - tone(clean16.astype(np.float32) / 128.0))[a[..., 0] >= 0.98]).max())
    if out.dtype != np.uint16 or int(out[..., 3].max()) != 32768 or err16 > 1.0:
        bad.append(f"16-bit frame: layer {out.dtype}, alpha up to {int(out[..., 3].max())}, the tone of the painted spot is off by {err16:.2f} levels")

    # ---- 9. over HTTP: the edge named in the request is the edge of the stroke; a request without it is soft
    note = ""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from fastapi.testclient import TestClient
    except Exception:
        TestClient = None
        note = " (the HTTP part was SKIPPED: the httpx package is missing)"
    if TestClient is not None:
        srv = H.load_server()
        e_direct, r_direct = opened(clean)
        e_http, r_http = opened(clean)
        srv.ENGINE, srv.ENGINE_ERROR = e_http, None
        pts = [{"x": 0.80, "y": 0.30, "norm": 1}, {"x": 0.86, "y": 0.31, "norm": 1}]
        masks = {}
        real_out, real_err = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = open(os.devnull, "w", encoding="utf-8")
        try:
            with TestClient(srv.app) as client:
                for softness in (0, 1, None):
                    body = dict(session_id=r_http["session_id"], op="stroke", points=pts, radius_px=40, erase=True)
                    if softness is not None:
                        body["softness"] = softness
                    client.post("/session/mask-edit", json=dict(session_id=r_http["session_id"], op="reset_auto"))
                    ans = client.post("/session/mask-edit", json=body)
                    edit(e_direct, r_direct, "reset_auto")
                    stroke(e_direct, r_direct, [(0.80, 0.30), (0.86, 0.31)], 40, erase=True, softness=None if softness is None else float(softness))
                    masks[softness] = e_http._active_session["user_erase_u8"].copy()
                    if ans.status_code != 200 or not np.array_equal(masks[softness], e_direct._active_session["user_erase_u8"]):
                        bad.append(f"/session/mask-edit with softness {softness}: the stroke differs from the one the engine makes for that edge")
        finally:
            sys.stdout.close()
            sys.stdout, sys.stderr = real_out, real_err
        if len(masks) == 3 and (np.array_equal(masks[0], masks[1]) or not np.array_equal(masks[1], masks[None])):
            bad.append("/session/mask-edit: a hard and a soft stroke must differ, and a request that names no edge must be soft")

    report("brush", not bad,
           f"soft edge: a stroke fades over {ws} px (hard: {wh} px), largest step {ss:.3f} of the layer (hard: {sh_:.3f}); eraser {ws_e} px / {ss_e:.3f} (hard: {wh_e} px / {sh_e:.3f}); "
           f"a lamp spot of {was:.0f} levels painted over is off by {soft['core_err']:.2f} levels, grain {soft['g'][0]:.2f} around / {soft['g'][1]:.2f} inside; "
           f"the soft brush leaves the person alone, the hard one repaints it; fill repaints nothing; a shadow edge is not smeared ({e_dark:+.1f} / {e_lit:+.1f}), "
           f"a touched shadow does not darken the wall ({wall:.1f}), a stain there is evened ({stain:.1f} -> {left:+.1f}); "
           f"{100 * painted:.0f} % of the window painted keeps its tone ({d.mean():.2f}), Apply {t_big:.1f} s; a stroke takes up to {1000 * t_stroke:.0f} ms{note}"
           if not bad else "wrong:\n  " + "\n  ".join(bad))


def check_format():
    bad = []
    notes = []

    def run(name, image, sil, bit=8, expect=None):
        hh, ww = image.shape[:2]
        eng = H.make_engine(E, sil)
        full = np.dstack([image, np.full((hh, ww), 255 if bit == 8 else 32768, image.dtype)])
        full.setflags(write=False)
        out, info = _quiet(eng.extend_canvas, full, bit, {})
        if expect is not None:
            if out is not None or info.get("reason") != expect:
                bad.append(f"{name}: expected '{expect}', got {info}")
            return None, info
        if out is None:
            bad.append(f"{name}: nothing was added ({info})")
            return None, info
        nw, nh, L, T = info["new_w"], info["new_h"], info["left"], info["top"]
        ratio = min(nw, nh) / max(nw, nh)
        if abs(ratio - 5 / 7) > 2.5 / max(nw, nh) or out.shape != (nh, nw, 4) or out.dtype != image.dtype:
            bad.append(f"{name}: size {nw}x{nh}, ratio {ratio:.4f}")
        if (L > 0) == (T > 0) or info["right"] != L or info["bottom"] != T or (nw - ww, nh - hh) != (2 * L, 2 * T):
            bad.append(f"{name}: strips {info}")
        opaque = np.full((nh, nw), 255 if bit == 8 else 32768, image.dtype)
        opaque[T:T + hh, L:L + ww] = 0
        if not np.array_equal(out[:, :, 3], opaque):
            bad.append(f"{name}: the layer is not 'opaque strips, transparent over the photo'")
        return out, info

    w, h = 1000, 1500
    img, sil = H.make_studio_image(w, h, n_dust=0, n_hair=0, seed=41)
    out, info = run("portrait 2:3", img, sil)
    if out is not None:
        L = info["left"]
        k = 255.0
        for side, strip, edge in (("left", out[:, :L, :3][:, ::-1], img[:, :L]), ("right", out[:, L + w:, :3], img[:, ::-1][:, :L])):
            strip, edge = strip.astype(np.float32), edge.astype(np.float32)
            seam = float(np.abs(strip[:, :4].mean(axis=(1, 2)) - edge[:, :4].mean(axis=(1, 2))).mean())
            if seam > 1.2:
                bad.append(f"portrait {side}: brightness jumps by {seam:.1f} levels at the old edge")
            hp = lambda x: x[:, :, 1] - cv2.GaussianBlur(x[:, :, 1], (0, 0), 1.5)
            grain = float(hp(strip).std() / hp(edge).std())
            if not 0.85 < grain < 1.2:
                bad.append(f"portrait {side}: grain of the new strip x{grain:.2f}")
            # the wall-floor line and the lighting carry on: each row of the strip resembles the row next to it
            rows_new, rows_old = strip.mean(axis=(1, 2)), edge[:, :24].mean(axis=(1, 2))
            drift = float(np.abs(cv2.blur(rows_new[:, None], (1, 31)) - cv2.blur(rows_old[:, None], (1, 31))).max())
            if drift > 6.0:
                bad.append(f"portrait {side}: rows of the strip drift from the photo by {drift:.1f} levels")
            notes.append(f"{side} seam {seam:.1f} lv, grain x{grain:.2f}")
        if info["subject_at_edge"]:
            bad.append("portrait: person reported at the edge, but stands in the middle")
        out16, info16 = run("portrait 2:3, 16 bit", (img.astype(np.uint16) * 128), sil, bit=16)
        if out16 is not None:
            d16 = float(np.abs(out16[:, :L, :3].astype(np.float32) / 128.0 - out[:, :L, :3]).mean())
            if d16 > 1.0:
                bad.append(f"16-bit strips differ from the 8-bit ones by {d16:.2f} levels")
    land = np.ascontiguousarray(np.rot90(img))
    out_l, info_l = run("landscape 3:2", land, np.ascontiguousarray(np.rot90(sil)))
    if out_l is not None and (info_l["top"] == 0 or info_l["new_w"] != land.shape[1]):
        bad.append(f"landscape: {info_l}")
    run("portrait 4:5 (grows up and down)", np.ascontiguousarray(img[150:1400]), np.zeros_like(sil))
    run("already 5:7", cv2.resize(img, (1000, 1400)), sil, expect="already")
    run("panorama", np.ascontiguousarray(img[:300]), sil, expect="too_far")
    # a person cut by the frame edge cannot be continued: the caller is told, and no half-person is mirrored
    cut = np.ascontiguousarray(img[:, int(w * 0.42):])
    sil_cut = cv2.resize(cv2.resize(sil, (w, h))[:, int(w * 0.42):], (1024, 1024))
    out_c, info_c = run("person at the edge", cut, sil_cut)
    if out_c is not None:
        if not info_c["subject_at_edge"]:
            bad.append("person at the edge was not reported")
        strip = out_c[:, :info_c["left"], :3].astype(np.float32)
        dark = float((strip.mean(axis=2) < 60).mean())
        if dark > 0.02:
            bad.append(f"the cut person was mirrored into the new strip ({dark * 100:.0f}% dark pixels)")
    report("format", not bad, "format 5:7: " + "; ".join(notes) + "; 8/16 bit, portrait/landscape, 'already 5:7' and 'person at the edge' handled"
           if not bad else "wrong:\n  " + "\n  ".join(bad))


def check_gpu():
    CUDA, DML, CPU = "CUDAExecutionProvider", "DmlExecutionProvider", "CPUExecutionProvider"

    def run(avail, behaviour, algo="HEURISTIC", allow_dml=True, n=2):
        calls, cpu_calls = [], []

        def session(path, sess_options=None, providers=None):
            opt = None
            for prov in providers:
                if isinstance(prov, tuple) and prov[0] == CUDA:
                    opt = prov[1].get("cudnn_conv_algo_search", "")
            calls.append(opt)
            active = behaviour(opt)
            return types.SimpleNamespace(get_providers=lambda: list(active))

        fake = types.SimpleNamespace(
            SessionOptions=lambda: types.SimpleNamespace(),
            GraphOptimizationLevel=types.SimpleNamespace(ORT_ENABLE_ALL=99),
            get_available_providers=lambda: list(avail),
            InferenceSession=session,
        )
        eng = H.make_engine(E, np.zeros((1024, 1024), np.float32))
        eng._cudnn_algo = algo
        eng.gpu_error = ""
        eng._preload_ort_cuda = lambda: None
        eng._create_cpu_session = lambda path: (cpu_calls.append(path) or ("CPU_SESSION", CPU))
        real, E.ort = E.ort, fake
        try:
            outs = [_quiet(eng._create_session, "m.onnx", allow_dml=allow_dml) for _ in range(n)]
        finally:
            E.ort = real
        return [o[1] for o in outs], calls, cpu_calls, eng

    def boom():
        raise RuntimeError("unknown option")

    bad = []
    act, calls, cpu, eng = run([CUDA, CPU], lambda a: [CUDA, CPU])
    if calls != ["HEURISTIC", "HEURISTIC"] or act != [CUDA, CUDA]:
        bad.append("option accepted")
    act, calls, cpu, eng = run([CUDA, CPU], lambda a: boom() if a else [CUDA, CPU])
    if calls != ["HEURISTIC", "", ""] or act != [CUDA, CUDA] or eng.gpu_error:
        bad.append("option rejected with an error")
    act, calls, cpu, eng = run([CUDA, CPU], lambda a: [CPU] if a else [CUDA, CPU])
    if calls != ["HEURISTIC", "", ""] or act != [CUDA, CUDA] or eng.gpu_error:
        bad.append("option rejected silently (CPU fallback inside ONNX Runtime)")
    act, calls, cpu, eng = run([CUDA, CPU], lambda a: [CPU])
    if act != [CPU, CPU] or "CUDAExecutionProvider" not in eng.gpu_error:
        bad.append("CUDA broken")
    act, calls, cpu, eng = run([CUDA, DML, CPU], lambda a: [DML, CPU])
    if act != [DML, DML]:
        bad.append("CUDA broken, DirectML available")
    act, calls, cpu, eng = run([CUDA, CPU], lambda a: boom(), n=1)
    if act != [CPU] or cpu != ["m.onnx"]:
        bad.append("everything fails")
    act, calls, cpu, eng = run([DML, CPU], lambda a: [DML, CPU])
    if calls != [None, None]:
        bad.append("DirectML only")
    act, calls, cpu, eng = run([CUDA, CPU], lambda a: [CUDA, CPU], algo="", n=1)
    if calls != [""]:
        bad.append("EXHAUSTIVE override")
    report("gpu", not bad, "cuDNN option: accepted -> used; rejected / broken CUDA -> previous behaviour" if not bad else f"wrong: {bad}")


def check_fallback():
    """
    An error of the GPU costs one run, not the session (4.10.0). The processor finishes the fill that the GPU refused,
    with the same result; the answer says where the fill ran and why; the next run asks the GPU again. Up to 4.9.0
    the processor kept the job until the models were loaded anew - on one thread, and nothing said so.
    """
    bad = []
    CUDA, CPU = "CUDAExecutionProvider", "CPUExecutionProvider"

    class Refusing(H.FakeLama):                      # the GPU's fill: refuses the requests whose numbers are given
        def __init__(self, refuse):
            super().__init__()
            self.refuse, self.asked = set(refuse), 0

        def run(self, outputs, feed):
            self.asked += 1
            if self.asked in self.refuse:
                raise RuntimeError("CUDA out of memory (simulated)")
            return super().run(outputs, feed)        # (.calls counts the tiles it filled)

    class OnCpu(H.FakeLama):
        def get_providers(self):
            return [CPU]

    class Broken(OnCpu):
        def run(self, outputs, feed):
            raise RuntimeError("the processor fails too (simulated)")

    class BrokenLater(OnCpu):                        # the processor's session gives up after its first tile
        def run(self, outputs, feed):
            if self.calls >= 1:
                raise RuntimeError("the processor fails too (simulated)")
            return super().run(outputs, feed)

    img, sil = H.make_studio_image(1500, 1000, seed=5)
    p = dict(H.STD, speedMode="quality")
    ref, ref_st = _quiet(H.make_engine(E, sil).process, img, 8, p)
    tiles = int(ref_st["tiles_run"])
    t_ref = ref_st.get("timing") or {}
    if tiles < 6:
        bad.append(f"the frame of this check asks for {tiles} tiles only")
    if t_ref.get("fill_tiles") != tiles or t_ref.get("fill_ep") != CUDA or t_ref.get("fallback") != {} or not isinstance(t_ref.get("fill_s"), float):
        bad.append(f"a run without trouble must say: {tiles} tiles, on the GPU, no fallback - it says {t_ref}")

    def engine_with(gpu, cpu_cls=OnCpu):
        eng = H.make_engine(E, sil)
        eng.lama_sess, made = gpu, []

        def cpu_session(path, threads=1):
            made.append((threads, cpu_cls()))
            return made[-1][1], CPU

        eng._create_cpu_session = cpu_session
        return eng, made

    # (the machine of this run may have two processors, where "all but one" is the single thread of before: the
    #  engine is told of eight)
    real_count = os.cpu_count
    for name, refuse in (("the 3rd tile", {3}), ("every tile", set(range(1, 500)))):
        gpu = Refusing(refuse)
        eng, made = engine_with(gpu)
        os.cpu_count = lambda: 8
        try:
            out, st = _quiet(eng.process, img, 8, p)
            if made and (made[0][0] != 7 or eng._fallback_threads() != 7):
                bad.append(f"the GPU refuses {name}: of 8 processors the session for this run must get 7 threads, it got {made[0][0]} "
                           f"(_fallback_threads says {eng._fallback_threads()})")
        finally:
            os.cpu_count = real_count
        first_bad = min(refuse)
        t = st.get("timing") or {}
        if not np.array_equal(out, ref):
            bad.append(f"the GPU refuses {name}: the result differs from a run without trouble")
        if eng.lama_sess is not gpu:
            bad.append(f"the GPU refuses {name}: the GPU session was thrown away (the next run cannot ask it again)")
        if len(made) != 1 or made[0][1].calls != tiles - (first_bad - 1) or gpu.calls != first_bad - 1 or gpu.asked != first_bad:
            bad.append(f"the GPU refuses {name}: the processor must finish this run alone - sessions made {len(made)}, tiles filled by the processor "
                       f"{made[0][1].calls if made else None} of {tiles}, by the GPU {gpu.calls}, GPU asked {gpu.asked} times")
        if t.get("fill_ep") != CPU or "simulated" not in str((t.get("fallback") or {}).get("lama")) or t.get("fill_tiles") != tiles \
                or "simulated" not in str(eng.cpu_fallback.get("lama")) or "LaMa" not in eng.gpu_error:
            bad.append(f"the GPU refuses {name}: the answer must say 'processor' and why - it says {t}; engine: {eng.cpu_fallback}")
        if name == "the 3rd tile":
            # the next run: the GPU is asked again and does it all; the note of the fallback is gone
            out2, st2 = _quiet(eng.process, img, 8, p)
            t2 = st2.get("timing") or {}
            if not np.array_equal(out2, ref) or gpu.calls != (first_bad - 1) + tiles or len(made) != 1 or made[0][1].calls != tiles - (first_bad - 1):
                bad.append(f"the run after a fallback must go to the GPU again: GPU filled {gpu.calls - (first_bad - 1)} of {tiles} tiles, "
                           f"processor sessions {len(made)}")
            if t2.get("fill_ep") != CUDA or t2.get("fallback") != {} or eng.cpu_fallback != {}:
                bad.append(f"the run after a fallback: the answer still says {t2}; engine: {eng.cpu_fallback}")
    # the processor fails as well: the error comes out (no going back to the GPU, no tile left out, no silent picture)
    for cpu_cls, when in ((Broken, "at once"), (BrokenLater, "after its first tile")):
        gpu = Refusing({1})
        eng, made = engine_with(gpu, cpu_cls)
        try:
            _quiet(eng.process, img, 8, p)
            bad.append(f"the GPU and the processor both fail ({when}): process() must raise")
        except RuntimeError as exc:
            if "processor fails too" not in str(exc) or len(made) != 1 or gpu.asked != 1:
                bad.append(f"the GPU and the processor both fail ({when}): {exc!r}, processor sessions {len(made)}, GPU asked {gpu.asked} time(s)")

    # the session of the processor really gets the threads it is given
    class Options:
        pass

    seen, ort = [], E.ort
    kept = {k: getattr(ort, k, None) for k in ("SessionOptions", "InferenceSession")}
    ort.SessionOptions = Options
    ort.InferenceSession = lambda path, sess_options=None, providers=None: seen.append((path, sess_options, providers)) or "session"
    try:
        made_s = H.make_engine(E, sil)._create_cpu_session("model.onnx", threads=7)
    finally:
        for k, v in kept.items():
            if v is None:
                delattr(ort, k)
            else:
                setattr(ort, k, v)
    if made_s != ("session", CPU) or len(seen) != 1 or seen[0][2] != [CPU] or getattr(seen[0][1], "intra_op_num_threads", None) != 7:
        bad.append(f"_create_cpu_session(threads=7): the session must be made for the processor with 7 threads - "
                   f"{getattr(seen[0][1], 'intra_op_num_threads', None) if seen else None} thread(s), providers {seen[0][2] if seen else None}")

    # the silhouette network: the same rule
    class RefusingMatting(H.FakeMatting):
        asked, refuse = 0, {1}

        def run(self, outputs, feed):
            self.asked += 1
            if self.asked in self.refuse:
                raise RuntimeError("CUDA out of memory (simulated)")
            return super().run(outputs, feed)

    eng = H.make_engine(E, sil)
    gpu_m, made_m = RefusingMatting(sil), []

    def cpu_matting(path, threads=1):
        made_m.append((threads, H.FakeMatting(sil)))
        return made_m[-1][1], CPU

    eng.matting_sess, eng._create_cpu_session = gpu_m, cpu_matting
    os.cpu_count = lambda: 8
    try:
        out, st = _quiet(eng.process, img, 8, p)
    finally:
        os.cpu_count = real_count
    if not np.array_equal(out, ref) or eng.matting_sess is not gpu_m or len(made_m) != 1 or "simulated" not in str(eng.cpu_fallback.get("matting")) \
            or made_m[0][0] != 7 or "simulated" not in str((st.get("timing") or {}).get("fallback", {}).get("matting")):
        bad.append(f"the GPU refuses the silhouette: same result {np.array_equal(out, ref)}, GPU session kept {eng.matting_sess is gpu_m}, "
                   f"processor sessions {len(made_m)} with {made_m[0][0] if made_m else None} thread(s) (7 expected), engine says {eng.cpu_fallback}, "
                   f"the answer says {st.get('timing')}")
    out, st = _quiet(eng.process, img, 8, p)
    if not np.array_equal(out, ref) or gpu_m.asked < 2 or len(made_m) != 1 or eng.cpu_fallback != {}:
        bad.append(f"the frame after a silhouette fallback must go to the GPU again: asked {gpu_m.asked}, engine says {eng.cpu_fallback}")
    report("fallback", not bad, f"a GPU error costs one run: the processor finishes it ({tiles} tiles, same pixels, all processors but one - 7 threads "
           f"of 8), the answer says where the fill ran and why, the next run is on the GPU again; fill and silhouette" if not bad
           else "wrong:\n  " + "\n  ".join(bad))


def check_fastwin():
    """
    The fast window (4.10.0): the panel asks for pictures of the working size ("previewLong" 1080) and gets them -
    also when the automatic preset is on, where the values of the chosen preset replace those of the request.
    (With 4.8.0 the request's word was lost there: the window would have got the large pictures all the same.)
    """
    bad, notes = [], []
    img, sil = H.make_studio_image(3000, 2000, seed=3)
    p = dict(H.STD, speedMode="quality")

    def opened(params, presets=None):
        eng = H.make_engine(E, sil)
        r = _quiet(eng.start_session, img, 8, params, None, None, presets)
        pic = cv2.imdecode(np.frombuffer(base64.b64decode(r["comp_jpg_b64"]), np.uint8), cv2.IMREAD_COLOR)
        a = _quiet(eng.edit_session_mask, r["session_id"], "stroke", [{"x": 0.2, "y": 0.8, "norm": True}, {"x": 0.3, "y": 0.8, "norm": True}], 20.0, False, False, 45.0, 1.0)
        pic2 = cv2.imdecode(np.frombuffer(base64.b64decode(a["comp_jpg_b64"]), np.uint8), cv2.IMREAD_COLOR)
        return (r["preview_w"], r["preview_h"]), pic.shape[1::-1], pic2.shape[1::-1], len(r["comp_jpg_b64"]) + len(r["overlay_jpg_b64"]), r

    presets = {"default": dict(p)}                       # what the panel sends with the automatic preset: no "previewLong" in it
    work, fast, fast_stroke, bytes_fast, r_fast = opened(dict(p, previewLong=1080), presets)
    if not r_fast.get("scene", {}).get("applied"):
        bad.append("the frame of this check did not take a preset of the automatic choice")
    if fast != work or fast_stroke != work:
        bad.append(f"previewLong 1080 with the automatic preset: pictures {fast} / after a stroke {fast_stroke}, the working size is {work}")
    _, plain, _, _, _ = opened(dict(p, previewLong=1080))
    if plain != work:
        bad.append(f"previewLong 1080 without presets: pictures {plain}, the working size is {work}")
    _, big, big_stroke, bytes_big, _ = opened(dict(p, previewLong=2160), presets)
    _, dflt, _, _, _ = opened(dict(p), presets)
    if max(big) != 2160 or big_stroke != big or dflt != big:
        bad.append(f"previewLong 2160 with the automatic preset: pictures {big} / after a stroke {big_stroke}; not asked at all: {dflt}")
    notes.append(f"asked for 1080: pictures {fast[0]}x{fast[1]} (the working size), also with the automatic preset and after a stroke; "
                 f"asked for 2160: {big[0]}x{big[1]}, {bytes_big / max(1, bytes_fast):.1f} times the bytes")

    # With the fast window the real frame is computed by Apply: its answer says what the AI fill took and where it
    # ran - the panel shows that after the window has closed. An Apply that finds the frame ready says nothing of it.
    eng = H.make_engine(E, sil)
    r = _quiet(eng.start_session, img, 8, dict(p, previewLong=1080))
    q = _quiet(eng.recompute_session, r["session_id"], dict(p, previewLong=1080, spots=35), True, None, True)
    _, _, st = _quiet(eng.apply_session, r["session_id"], 100.0, False, False, 45.0)
    t = st.get("timing") or {}
    if q.get("quick") is not True or st.get("recomputed") is not True:
        bad.append(f"the frame of this check: a light refresh (quick={q.get('quick')}), then an Apply that computes (recomputed={st.get('recomputed')})")
    elif not t.get("fill_tiles") or t.get("fill_ep") != "CUDAExecutionProvider" or not isinstance(t.get("fill_s"), float) or t.get("fallback") != {}:
        bad.append(f"Apply computed the real frame: its answer must say the tiles, the seconds and where the fill ran - it says {t}")
    _, _, st2 = _quiet(eng.apply_session, r["session_id"], 100.0, False, False, 45.0)
    if st2.get("recomputed") is not False or "timing" in st2:
        bad.append(f"a second Apply finds the frame ready: recomputed={st2.get('recomputed')}, timing {st2.get('timing')}")
    notes.append(f"Apply after a light refresh computes the frame and says so ({t.get('fill_tiles')} tiles, {t.get('fill_ep')})")
    report("fastwin", not bad, "; ".join(notes) if not bad else "wrong:\n  " + "\n  ".join(bad))


def check_server():
    srv = H.load_server()
    bad = []
    f = srv._idle_unload_from_settings
    for data, exp in (({}, 120.0), ({"schemaVersion": 4, "idleUnloadSec": 30}, 120.0), ({"idleUnloadSec": 30}, 120.0),
                      ({"schemaVersion": 4, "idleUnloadSec": 300}, 300.0), ({"schemaVersion": 4, "idleUnloadSec": 0}, 0.0),
                      ({"schemaVersion": 5, "idleUnloadSec": 30}, 30.0), ({"schemaVersion": 5, "idleUnloadSec": 120}, 120.0),
                      ({"schemaVersion": "x", "idleUnloadSec": 30}, 120.0), ({"schemaVersion": 4, "idleUnloadSec": -5}, 0.0)):
        if f(data) != exp:
            bad.append(f"idle unload {data} -> {f(data)} (expected {exp})")
    if E.DEFAULT_IDLE_UNLOAD_SEC != 120.0:
        bad.append("default idle unload is not 120 s")

    rng = np.random.default_rng(4)
    for dt in (np.uint8, np.uint16):
        for pad in (0, 1, 2, 3):
            arr = rng.integers(0, 255, (5, 7, 3)).astype(dt)
            raw = b"x" * pad + arr.tobytes() + b"tail"
            got = srv._packet_array(raw, pad, arr.shape, dt)
            if got is None or not np.array_equal(got, arr):
                bad.append(f"_packet_array {np.dtype(dt).name} offset {pad}")
            if srv._packet_array(raw, pad, (5, 7, 4), dt) is not None and len(raw) - pad < 5 * 7 * 4 * np.dtype(dt).itemsize:
                bad.append("_packet_array accepted a short body")
    # One version number in three places: a mismatch makes start_gpu_server.bat restart the server on every launch
    root = H.APP_DIR
    old_dir = H.BASELINE_FILES_DIR  # manifest.json and setup_launcher.py of the original program
    if E_OLD is None or SRV_OLD is None:
        bad.append("tests/baseline_v321 is missing or broken: the comparisons with v3.2.1 were skipped")

    def text(*parts):
        with open(os.path.join(*parts), encoding="utf-8") as fh:
            return fh.read()

    bat_versions = set(re.findall(r"get\('version'\)=='([^']+)'", text(root, "start_gpu_server.bat")))
    manifest = json.loads(text(root, "uxp-plugin", "manifest.json"))
    js_versions = re.findall(r'const PLUGIN_VERSION = "([^"]+)";', text(root, "uxp-plugin", "main.js"))
    if bat_versions != {srv.APP_VERSION} or manifest["version"] != srv.APP_VERSION or js_versions != [srv.APP_VERSION]:
        bad.append(f"version mismatch: server {srv.APP_VERSION}, start_gpu_server.bat {sorted(bat_versions)}, manifest {manifest['version']}, "
                   f"main.js {js_versions}")
    # ...and the same number wherever the user reads it: window titles of the .bat files, the first lines of the instruction
    shown = {bat: set(re.findall(r"\bv(\d+\.\d+\.\d+)", text(root, bat))) for bat in sorted(os.listdir(root)) if bat.endswith(".bat")}
    wrong = {bat: sorted(v) for bat, v in shown.items() if v - {srv.APP_VERSION}}
    manual = next(f for f in os.listdir(root) if f.endswith(".txt"))
    if wrong or f"(v{srv.APP_VERSION})" not in "".join(text(root, manual).splitlines(True)[:3]) \
            or f"v{srv.APP_VERSION}" not in text(root, "install_windows.bat"):
        bad.append(f"version shown to the user differs from {srv.APP_VERSION}: {wrong or manual}")
    # the AI models are taken from the folder named in folders.ini, never from a fixed place
    import cvpaths
    if srv.MODELS_DIR != cvpaths.resolve_models_dir() or "MODELS_DIR = cvpaths.resolve_models_dir()" not in text(root, "server", "server.py"):
        bad.append("server.py does not take the models folder from folders.ini")

    # The name. Up to 4.7.0 the program was shown as "Чистий Вініл Pro 2", to tell it from the original program
    # next to which it was installed. The owner removed the original and asked for the name without the 2
    # (4.8.0). Only what a person reads was renamed; everything the two programs register stays apart (below).
    shown_name = "Чистий Вініл Pro"
    html = text(root, "uxp-plugin", "index.html")
    main_js = text(root, "uxp-plugin", "main.js")
    name_problems = [where for where, ok in (
        ("manifest name", manifest["name"] == shown_name),
        ("panel label", manifest["entrypoints"][0]["label"]["default"] == shown_name),
        ("index.html", "Pro 2" not in html and f"<title>{shown_name}</title>" in html),
        ("main.js strings", not re.search(r'["`][^"`\n]*Вініл (Pro )?2[^"`\n]*["`]', main_js)),
        (".bat files", not any("Pro 2" in text(root, bat) for bat in os.listdir(root) if bat.endswith(".bat"))),
        ("the manual", "Pro 2" not in "".join(text(root, manual).splitlines(True)[:3])),
        ("server banner", "Clean Vinyl Pro 2" not in text(root, "server", "server.py")),
    ) if not ok]
    if name_problems:
        bad.append(f"the name still carries the 2: {name_problems}")
    # The layers: made under the new names; a document that holds a layer of 4.7.0 or older is still recognised
    for want in ('const LAYER_NAME_AI = "Чистий вініл (AI)";', 'const LAYER_NAME_SELECTION = "Чистий вініл (Виділення)";',
                 '"Чистий вініл 2 (AI)", "Чистий вініл 2 (Виділення)"];', "PLUGIN_LAYER_NAMES.includes(l.name)"):
        if want not in main_js:
            bad.append(f"layer names: main.js lacks {want!r}")
    if re.search(r'create(Pixel)?Layer\(\{ name: "', main_js):
        bad.append("layer names: a layer is created under a name written in place (use LAYER_NAME_AI / LAYER_NAME_SELECTION)")
    # The pictures of the big window are larger than its working size (check_sharp). The window places the photo,
    # the brush and the strokes by "preview_w" / "preview_h" of the answer and must never ask a picture for its size.
    if re.search(r"natural(Width|Height)", main_js) or "sessState.pw = res.preview_w;" not in main_js \
            or "sessState.ph = res.preview_h;" not in main_js:
        bad.append("the big window must take its working size from preview_w / preview_h, never from the pictures (naturalWidth)")

    # The icon of the plugin (Photoshop: the list of plugins). Adobe asks for a picture without transparency, in
    # the size the manifest names and twice that, for every theme of the interface.
    for icon in manifest.get("icons", []):
        if "all" not in icon.get("theme", []) or icon.get("species") != ["pluginList"] or sorted(icon.get("scale", [])) != [1, 2]:
            bad.append(f"plugin icon: theme / species / scale of {icon.get('path')}")
        stem, ext = os.path.splitext(icon["path"])
        for scale, names in ((1, (icon["path"], f"{stem}@1x{ext}")), (2, (f"{stem}@2x{ext}",))):
            for name in names:
                pic = cv2.imread(os.path.join(root, "uxp-plugin", name), cv2.IMREAD_UNCHANGED)
                if pic is None:
                    bad.append(f"plugin icon: {name} is missing")
                elif pic.shape[:2] != (icon["height"] * scale, icon["width"] * scale):
                    bad.append(f"plugin icon: {name} is {pic.shape[1]}x{pic.shape[0]}, the manifest says {icon['width'] * scale}x{icon['height'] * scale}")
                elif pic.ndim == 3 and pic.shape[2] == 4 and int(pic[..., 3].min()) < 255:
                    bad.append(f"plugin icon: {name} has transparent pixels")
                elif len({tuple(int(v) for v in pic[y, x][:3]) for y in (0, -1) for x in (0, -1)}) != 1:
                    bad.append(f"plugin icon: the corners of {name} differ (a picture cut out of a rounded square?)")
    if not manifest.get("icons"):
        bad.append("plugin icon: the manifest names none")

    # Clean Vinyl Pro (folder CleanVinylPro2) must be able to run next to the original program: nothing they
    # register may coincide
    port = str(srv.APP_PORT)
    plugin_js = text(root, "uxp-plugin", "main.js")
    launcher = text(root, "server", "setup_launcher.py")
    scheme = manifest["requiredPermissions"]["launchProcess"]["schemes"][0]
    for where, ok in (
        ("manifest network port", all(d.endswith(":" + port) for d in manifest["requiredPermissions"]["network"]["domains"])),
        ("main.js server address", f'"http://127.0.0.1:{port}"' in plugin_js and f"{scheme}://start" in plugin_js),
        ("main.js checks who answers", f'info.app !== "{srv.APP_ID}"' in plugin_js),
        ("start_gpu_server.bat port", f"127.0.0.1:{port}/health" in text(root, "start_gpu_server.bat")),
        ("launcher url scheme", f"Software\\Classes\\{scheme}\"" in launcher),
        ("data folder", srv._resolve_user_data_dir.__code__.co_consts.count("CleanVinylPro2") == 1),
    ):
        if not ok:
            bad.append(f"identity: {where}")
    if not os.path.isfile(os.path.join(old_dir, "manifest.json")) or not os.path.isfile(os.path.join(old_dir, "setup_launcher.py")):
        bad.append("tests/baseline_v321: manifest.json / setup_launcher.py of the original program are missing")
    else:
        old_manifest = json.loads(text(old_dir, "manifest.json"))
        old_launcher = text(old_dir, "setup_launcher.py")
        old_port = old_manifest["requiredPermissions"]["network"]["domains"][0].rsplit(":", 1)[1]
        task = re.search(r'"/TN", "([^"]+)"', launcher).group(1)
        clashes = [name for name, same in (
            ("plugin id", manifest["id"] == old_manifest["id"]),
            ("panel id", manifest["entrypoints"][0]["id"] == old_manifest["entrypoints"][0]["id"]),
            ("port", port == old_port),
            ("url scheme", scheme in old_manifest["requiredPermissions"]["launchProcess"]["schemes"]),
            ("scheduled task", f'"{task}"' in old_launcher),
            ("registry key", f"Software\\Classes\\{scheme}\"" in old_launcher),
            ("data folder", 'os.path.join(appdata, "CleanVinylPro2")' not in launcher),
        ) if same]
        for bat in sorted(f for f in os.listdir(root) if f.endswith(".bat")):
            if old_port in text(root, bat).replace("на " + old_port, ""):
                clashes.append(f"{bat} mentions port {old_port}")
        if clashes:
            bad.append(f"shared with the original program: {clashes}")

    resp = srv._binary_response({"ok": True, "текст": "ї"}, np.arange(6, dtype=np.uint16).reshape(2, 3), None, np.array([7, 8], np.uint8))
    n = struct.unpack_from("<I", resp.body, 0)[0]
    if json.loads(resp.body[4:4 + n].decode("utf-8")) != {"ok": True, "текст": "ї"} or resp.body[4 + n:] != np.arange(6, dtype=np.uint16).tobytes() + b"\x07\x08":
        bad.append("_binary_response layout")
    report("server", not bad, f"settings migration, packet parsing, version {srv.APP_VERSION} everywhere, the name without the 2, an opaque plugin icon, "
           f"nothing registered in common with the original program (port {srv.APP_PORT})"
           if not bad else f"wrong: {bad}")


def _http_quick_round_trip(client, srv, packet, split, bad) -> int:
    """The requests exactly as the plugin sends them after the 'light preview' change. Returns how many were made."""
    w, h = 1800, 2600
    img, sil = H.make_studio_image(w, h, n_dust=60, n_hair=6, seed=77)
    keep = srv.ENGINE
    n = 0
    try:
        srv.ENGINE = H.make_engine(E, sil)
        p = dict(H.STD, speedMode="fast", cycCurve=40, autoFractions=False)
        meta = {"width": w, "height": h, "channels": 3, "bitDepth": 8, "hasSelection": False, "jobId": "s", "params": p}
        r = client.post("/session/start", content=packet(meta, img)); n += 1
        sid = r.json()["session_id"]
        p1 = dict(p, spots=90)
        r = client.post("/session/recompute", json=dict(session_id=sid, params=p1, preserve_edits=True, quick=True)); n += 1
        if r.status_code != 200 or r.json().get("quick") is not True or not r.json().get("comp_jpg_b64"):
            bad.append("/session/recompute with quick=true must refresh only the preview and say quick=true")
        r = client.post("/session/recompute", json=dict(session_id=sid, params=p1, preserve_edits=True, jobId="j")); n += 1
        if r.status_code != 200 or r.json().get("quick") is not False:
            bad.append("/session/recompute without quick must stay a full recompute and say quick=false")
        p2 = dict(p, spots=90, blur=25, cycCurve=70)
        body = dict(session_id=sid, blend=100, makeMask=False, dressSmooth=False, dressStrength=45, jobId="a")
        r_new = client.post("/session/apply", json=dict(body, params=p2)); n += 1
        client.post("/session/recompute", json=dict(session_id=sid, params=p2, preserve_edits=True, jobId="j")); n += 1
        r_ref = client.post("/session/apply", json=body); n += 1
        if r_new.status_code != 200 or r_ref.status_code != 200:
            bad.append(f"/session/apply with settings: status {r_new.status_code}/{r_ref.status_code}")
        else:
            (m_new, px_new), (m_ref, px_ref) = split(r_new.content), split(r_ref.content)
            if px_new != px_ref or len(px_new) != w * h * 4:
                bad.append("/session/apply with settings: the layer differs from 'full recompute, then apply'")
            if m_new["stats"].get("dress_smooth") is not False or m_new != m_ref:
                bad.append("/session/apply with settings: the answer header differs from 'full recompute, then apply'")
        # The exact picture by itself: "background" in /session/recompute, "followBackground" in /session/apply
        # (what a background run does when other requests come in is checked on the engine - see check_exact)
        p3 = dict(p2, spots=70)
        r = client.post("/session/recompute", json=dict(session_id=sid, params=p3, preserve_edits=True, quick=True)); n += 1
        light = r.json()
        r = client.post("/session/recompute", json=dict(session_id=sid, params=p3, preserve_edits=True, background=True, jobId="b")); n += 1
        exact = r.json()
        if r.status_code != 200 or light.get("exact") is not False or exact.get("exact") is not True or exact.get("quick") is not False \
                or exact.get("rev") != light.get("rev", -9) + 1 or not exact.get("comp_jpg_b64") or exact.get("superseded") or exact.get("skipped"):
            bad.append("/session/recompute with background=true must compute the real frame and say exact=true with the next rev")
        prog = client.get("/progress", params={"job_id": "b"}).json(); n += 1
        if prog.get("pct") != 100 or prog.get("done") is not True:
            bad.append(f"/progress of a finished background recompute must be 100 %, done: {prog}")
        r = client.post("/session/mask-edit", json=dict(session_id=sid, op="invert")); n += 1
        edit1 = r.json()
        r = client.post("/session/mask-edit", json=dict(session_id=sid, op="stroke", radius_px=20, erase=False,
                                                        points=[{"x": 0.3, "y": 0.8, "norm": 1}, {"x": 0.4, "y": 0.8, "norm": 1}])); n += 1
        edit2 = r.json()
        if not (exact.get("rev", 0) < edit1.get("rev", 0) < edit2.get("rev", 0)) or edit2.get("exact") is not True:
            bad.append("/session/mask-edit must carry a growing rev and say whether the real frame is behind the pictures")
        r = client.post("/session/dress-preview", json=dict(session_id=sid, dressSmooth=False, dressStrength=45)); n += 1
        if r.json().get("rev") != edit2.get("rev") or r.json().get("exact") is not True:
            bad.append("/session/dress-preview must carry the rev of the pictures as they are (it changes nothing)")
        client.post("/session/recompute", json=dict(session_id=sid, params=p3, preserve_edits=True, quick=True)); n += 1
        client.post("/session/mask-edit", json=dict(session_id=sid, op="invert")); n += 1
        client.post("/session/mask-edit", json=dict(session_id=sid, op="stroke", radius_px=20, erase=False,
                                                    points=[{"x": 0.6, "y": 0.8, "norm": 1}])); n += 1
        r = client.post("/session/recompute", json=dict(session_id=sid, params=p3, preserve_edits=True, background=True, jobId="c")); n += 1
        if r.status_code != 200 or r.json().get("skipped") is not True or r.json().get("exact") is not False or "comp_jpg_b64" in r.json():
            bad.append("/session/recompute with background=true and the user's own mask on screen must answer skipped=true")
        # "a slider was taken": the request reaches the engine with the session it names
        told = []
        plain_stop = srv.ENGINE.stop_background

        def watched_stop(session_id):
            told.append(session_id)
            return plain_stop(session_id)

        srv.ENGINE.stop_background = watched_stop
        r = client.post("/session/stop-background", json=dict(session_id=sid)); n += 1
        r2 = client.post("/session/stop-background", json=dict(session_id="another-window")); n += 1
        srv.ENGINE.stop_background = plain_stop
        if r.status_code != 200 or r.json() != {"ok": True, "stopped": False} or r2.json() != {"ok": True, "stopped": False} \
                or told != [sid, "another-window"]:
            bad.append(f"/session/stop-background must hand the session to the engine and answer stopped=false when nothing runs: {told}")
        asked_to_follow = []
        plain_apply = srv.ENGINE.apply_session

        def watched_apply(*a, **k):  # (what the engine does with it is checked in check_exact)
            asked_to_follow.append(a[7] if len(a) > 7 else k.get("follow_background", False))
            return plain_apply(*a, **k)

        srv.ENGINE.apply_session = watched_apply
        r_follow = client.post("/session/apply", json=dict(body, params=p3, followBackground=True)); n += 1
        r_plain = client.post("/session/apply", json=dict(body, params=p3)); n += 1
        srv.ENGINE.apply_session = plain_apply
        if r_follow.status_code != 200 or r_plain.status_code != 200 or split(r_follow.content)[1] != split(r_plain.content)[1]:
            bad.append("/session/apply with followBackground=true and nothing running must give the layer of a plain Apply")
        if asked_to_follow != [True, False]:
            bad.append(f"/session/apply must hand followBackground to the engine, and only when the panel asked for it: {asked_to_follow}")
        client.post("/session/close", json=dict(session_id=sid))
    finally:
        srv.ENGINE = keep
    return n


def _http_backup_round_trip(client, srv, bad) -> int:
    """
    Backups of the settings: what the plugin sends is written as one file into the backup folder, listed and given
    back unchanged; only files of that folder can be read; files that are not backups are skipped; of the copies
    the program makes by itself before a restore only the newest are kept. Returns the number of requests made.
    """
    import tempfile
    n = 0
    tmp = tempfile.mkdtemp(prefix="cv_backup_")
    folder = os.path.join(tmp, "backup")
    keep_env = os.environ.get("CLEANVINYL_BACKUP_DIR")
    os.environ["CLEANVINYL_BACKUP_DIR"] = folder
    try:
        with open(os.path.join(H.SERVER_DIR, "presets_defaults.json"), "r", encoding="utf-8") as f:
            presets = json.load(f)
        presets.insert(0, {"id": "usr_1", "name": "Мій пресет", "color": "#54d182", "builtin": False, "cfg": {"spots": 50, "smokeOn": True}})
        settings = {"schemaVersion": 5, "activePresetId": "usr_1", "autoPreset": False, "cfg": {"spots": 50}, "presetMoves": ["cyc65"]}

        def get(path):
            nonlocal n
            n += 1
            return client.get(path)

        def post(path, **kw):
            nonlocal n
            n += 1
            return client.post(path, **kw)

        if get("/health").json().get("backup_dir") != folder:
            bad.append("backup: /health must name the backup folder")
        r = get("/backup/list")
        if r.status_code != 200 or r.json() != {"ok": True, "folder": folder, "backups": []} or os.path.exists(folder):
            bad.append(f"backup: an empty list for a folder that does not exist yet (and no folder made by looking): {r.status_code} {r.text[:120]}")
        r1 = post("/backup/save", json={"presets": presets, "settings": settings})
        j1 = r1.json()
        on_disk = {}
        path1 = os.path.join(folder, j1.get("file", "?"))
        if r1.status_code != 200 or not j1.get("ok") or j1.get("path") != path1 or j1.get("folder") != folder or not os.path.isfile(path1) \
                or j1.get("presets") != len(presets) or j1.get("user_presets") != 1 or not re.fullmatch(r"CleanVinylPro2_backup_\d{4}-\d\d-\d\d_\d\d-\d\d-\d\d\.json", j1.get("file", "")):
            bad.append(f"backup: /backup/save answer {r1.status_code} {r1.text[:200]}")
        else:
            with open(path1, "r", encoding="utf-8") as f:
                on_disk = json.load(f)
            if on_disk.get("presets") != presets or on_disk.get("settings") != settings or on_disk.get("version") != srv.APP_VERSION or on_disk.get("kind") != srv.BACKUP_KIND:
                bad.append("backup: the file does not hold what was sent")
        j2 = post("/backup/save", json={"presets": presets, "settings": settings}).json()     # within the same second: another name
        j3 = post("/backup/save", json={"presets": presets[1:], "settings": settings, "label": "before-restore/../x y"}).json()
        names = {j1.get("file"), j2.get("file"), j3.get("file")}
        if len(names) != 3 or not str(j3.get("file", "")).endswith("_before-restorexy.json") or os.sep in str(j3.get("file")) or len(os.listdir(folder)) != 3:
            bad.append(f"backup: three saves must give three plain file names inside the folder: {sorted(map(str, names))}")
        # what is not a backup of this program is skipped; a file the owner renamed is still a backup
        with open(os.path.join(folder, "notes.json"), "w", encoding="utf-8") as f:
            f.write('{"a": 1}')
        with open(os.path.join(folder, "broken.json"), "w", encoding="utf-8") as f:
            f.write("{not json")
        with open(os.path.join(folder, "other program.json"), "w", encoding="utf-8") as f:   # the same shape, made by something else
            json.dump({"kind": "settings-of-another-program", "presets": presets, "settings": settings}, f)
        with open(os.path.join(tmp, "outside.json"), "w", encoding="utf-8") as f:
            json.dump(on_disk, f)
        os.replace(path1, os.path.join(folder, "мій бекап (копія).json"))
        listed = get("/backup/list").json().get("backups", [])
        if sorted(b["file"] for b in listed) != sorted(["мій бекап (копія).json", j2.get("file"), j3.get("file")]):
            bad.append(f"backup: the list must hold the three backups and nothing else: {[b['file'] for b in listed]}")
        elif not all(re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d", b["saved_at"]) and b["version"] == srv.APP_VERSION for b in listed) \
                or sorted((b["presets"], b["user_presets"], b["label"]) for b in listed) != sorted([(len(presets), 1, ""), (len(presets), 1, ""), (len(presets) - 1, 0, "before-restorexy")]):
            bad.append(f"backup: the list must say when each backup was made and what it holds: {listed}")
        r = post("/backup/read", json={"file": "мій бекап (копія).json"})
        jr = r.json()
        if r.status_code != 200 or jr.get("presets_list") != presets or jr.get("settings") != settings or jr.get("presets") != len(presets):
            bad.append(f"backup: /backup/read must give back exactly what was saved: {r.status_code}")
        for name, want in (("../outside.json", 404), (os.path.join(tmp, "outside.json"), 404), ("nope.json", 404), ("", 404), (None, 404),
                           ("notes.json", 400), ("broken.json", 400), ("other program.json", 400)):
            r = post("/backup/read", json={"file": name})
            if r.status_code != want or r.json().get("ok") is not False or "presets_list" in r.json():
                bad.append(f"backup: /backup/read of {name!r} answered {r.status_code}, expected {want}")
        for body, want in (({"presets": [], "settings": {}}, 400), ({"presets": [{"id": "a"}], "settings": {}}, 400), ({"presets": presets}, 400), ([1, 2], 400)):
            r = post("/backup/save", json=body)
            if r.status_code != want or r.json().get("ok") is not False:
                bad.append(f"backup: /backup/save of a broken request answered {r.status_code}")
        if post("/backup/save", content=b"{not json").status_code != 400 or len(os.listdir(folder)) != 6:
            bad.append("backup: a broken request must write nothing")
        # copies made before a restore: the newest few stay, the owner's backups are never removed
        for _ in range(srv.BACKUP_AUTO_KEEP + 3):
            post("/backup/save", json={"presets": presets, "settings": settings, "label": "before-restore"})
        left = os.listdir(folder)
        if sum(x.endswith("_before-restore.json") for x in left) != srv.BACKUP_AUTO_KEEP or not {"мій бекап (копія).json", j2.get("file"), j3.get("file")} <= set(left):
            bad.append(f"backup: {srv.BACKUP_AUTO_KEEP} automatic copies must stay and every other backup: {sorted(left)}")
        r = post("/backup/open-folder")
        if r.status_code != 200 or r.json().get("folder") != folder or r.json().get("opened") is not (sys.platform == "win32"):
            bad.append(f"backup: /backup/open-folder {r.status_code} {r.text[:120]}")
        # the folder cannot be written: the answer says so instead of a crash
        blocked = os.path.join(tmp, "a file, not a folder")
        with open(blocked, "w", encoding="utf-8") as f:
            f.write("x")
        os.environ["CLEANVINYL_BACKUP_DIR"] = os.path.join(blocked, "backup")
        r = post("/backup/save", json={"presets": presets, "settings": settings})
        if r.status_code != 500 or r.json().get("ok") is not False or not r.json().get("error"):
            bad.append(f"backup: a folder that cannot be made must give an error with a reason: {r.status_code} {r.text[:120]}")
        if get("/backup/list").json().get("backups") != []:
            bad.append("backup: a folder that cannot be read lists nothing")
    finally:
        if keep_env is None:
            os.environ.pop("CLEANVINYL_BACKUP_DIR", None)
        else:
            os.environ["CLEANVINYL_BACKUP_DIR"] = keep_env
        shutil.rmtree(tmp, ignore_errors=True)
    return n


def check_http():
    if SRV_OLD is None:
        report("http", True, "SKIPPED - v3.2.1 is not available (tests/baseline_v321 is missing)")
        return
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from fastapi.testclient import TestClient
    except Exception as exc:
        report("http", True, f"SKIPPED - FastAPI test client is not available ({exc}); install it with: pip install httpx")
        return
    srv = H.load_server()

    def packet(meta, *arrays):
        mb = json.dumps(meta).encode("utf-8")
        return struct.pack("<I", len(mb)) + mb + b"".join(np.ascontiguousarray(a).tobytes() for a in arrays)

    def split(body):
        n = struct.unpack_from("<I", body, 0)[0]
        meta = json.loads(body[4:4 + n].decode("utf-8"))
        # ("recomputed" is new: Apply says whether it had to compute the real frame itself; "smoke" is new: what
        #  was seen of smoke in the frame)
        meta["stats"] = {k: v for k, v in meta.get("stats", {}).items() if k not in ("elapsed_ms", "reused_stages", "recomputed", "smoke", "timing")}
        return meta, body[4 + n:]

    def norm(d):
        # ("quick" is new: a recompute says whether it only refreshed the preview; "scene", "smoke", "mask_share" and
        #  "layer_share" are new: the answer describes the frame, what was seen of smoke, and how much of the frame
        #  was found and repaired / is covered by the layer; "history" is new: how many mask edits can be taken
        #  back and made again; "rev" and "exact" are new: the number of the pictures in order, and whether the
        #  real frame is behind them - see check_exact)
        d = {k: v for k, v in d.items() if k not in ("session_id", "mask_png_b64", "quick", "scene", "smoke", "mask_share", "layer_share", "history", "rev", "exact")}
        if "stats" in d:
            d["stats"] = {k: v for k, v in d["stats"].items() if k not in ("elapsed_ms", "reused_stages", "smoke", "timing")}
        return d

    bad = []
    n = 0
    cases = [(1203, 901, True, False, 1), (901, 1203, False, True, 2)] + ([(1400, 1000, False, False, 0), (1000, 1400, True, True, 0)] if FULL else [])
    real_out = sys.stdout
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
    real_err, sys.stderr = sys.stderr, sys.stdout  # the "session expired" case prints a traceback on purpose
    try:
        for (w, h, bit16, rgba, pad) in cases:
            img, sil = H.make_studio_image(w, h, n_dust=60, n_hair=6, seed=w + h, bit16=bit16, rgba=rgba)
            SRV_OLD.ENGINE, SRV_OLD.ENGINE_ERROR = H.make_engine(E_OLD, sil), None
            srv.ENGINE, srv.ENGINE_ERROR = H.make_engine(E, sil), None
            bd = 16 if bit16 else 8
            sel = np.zeros((h, w), np.uint16 if bit16 else np.uint8)
            sel[h // 2:, : w // 2] = 32768 if bit16 else 255
            heal = np.zeros((h // 2, w // 2), np.uint8)
            heal[h // 3:h // 3 + 20, w // 5:w // 5 + 40] = 255
            prot = (np.clip(cv2.resize(sil, (w, h)), 0, 1) * 255).astype(np.uint8)
            with TestClient(SRV_OLD.app) as co, TestClient(srv.app) as cn:
                def both(path, **kw):
                    return co.post(path, **kw), cn.post(path, **kw)

                def binary_same(name, ro, rn):
                    nonlocal n
                    n += 1
                    if not (ro.status_code == rn.status_code == 200 and split(ro.content) == split(rn.content)):
                        bad.append(f"{w}x{h} {name}")

                for mode in ("quality",):
                    meta = {"width": w, "height": h, "channels": img.shape[2], "bitDepth": bd,
                            "params": _legacy(H.STD), "jobId": "j", "note": "x" * pad}
                    binary_same(f"/process {mode}", *both("/process", content=packet(meta, img)))
                    binary_same(f"/process {mode} selection", *both("/process", content=packet(dict(meta, hasSelection=True, selectionBitDepth=bd), img, sel)))
                    binary_same(f"/process {mode} custom masks", *both("/process", content=packet(
                        dict(meta, hasCustomProtect=True, hasCustomHeal=True, healMaskWidth=w // 2, healMaskHeight=h // 2), img, prot, heal)))
                    binary_same(f"/process {mode} selection missing", *both("/process", content=packet(dict(meta, hasSelection=True), img)))
                # (the green "action" preview now shows the thorough search in both speed modes - see check_speed)
                binary_same("/preview-mask protection", *both("/preview-mask", content=packet(dict(meta, maskType="protection"), img)))
                rn = cn.post("/preview-mask", content=packet(dict(meta, maskType="action"), img))
                n += 1
                if rn.status_code != 200 or len(split(rn.content)[1]) != w * h:
                    bad.append(f"{w}x{h} /preview-mask action")
                ro, rn = both("/process", content=packet(meta, img)[:-1000])
                n += 1
                if not (ro.status_code == rn.status_code == 400 and ro.json() == rn.json()):
                    bad.append(f"{w}x{h} truncated body")

                for mode in ("quality",):
                    p = _legacy(dict(H.STD, autoFractions=True))
                    meta = {"width": w, "height": h, "channels": img.shape[2], "bitDepth": bd, "params": p, "note": "x" * pad}
                    ro, rn = both("/session/start", content=packet(meta, img))
                    n += 1
                    if not (ro.status_code == rn.status_code == 200 and norm(ro.json()) == norm(rn.json())):
                        bad.append(f"{w}x{h} /session/start {mode}")
                        continue
                    so, sn = ro.json()["session_id"], rn.json()["session_id"]
                    # (the window is compared in its legacy regime: no stage that works on the whole backdrop - see
                    #  _legacy_window; "Сліди взуття та розводи" and the blur used to be among these steps)
                    steps = [
                        ("recompute", dict(params=dict(p, spots=85), preserve_edits=True)),
                        ("mask-edit", dict(op="stroke", points=[{"x": 0.2, "y": 0.8, "norm": 1}, {"x": 0.4, "y": 0.7, "norm": 1}], radius_px=20, erase=False)),
                        ("mask-edit", dict(op="stroke", points=[{"x": 0.6, "y": 0.6, "norm": 1}], radius_px=30, erase=True, dressSmooth=False, dressStrength=60)),
                        ("recompute", dict(params=dict(p, spots=85, grain=60, edge=80), preserve_edits=True)),
                        ("dress-preview", dict(dressSmooth=False, dressStrength=70)),
                        ("mask-edit", dict(op="invert")),
                        ("recompute", dict(params=dict(p, spots=50, autoFractions=False, fracMed=False), preserve_edits=False)),
                        ("mask-edit", dict(op="stroke", points=[{"x": 0.3, "y": 0.85, "norm": 1}], radius_px=40, erase=False)),
                    ]
                    for i, (ep, payload) in enumerate(steps):
                        ro = co.post(f"/session/{ep}", json=dict(payload, session_id=so))
                        rn = cn.post(f"/session/{ep}", json=dict(payload, session_id=sn))
                        n += 1
                        if not (ro.status_code == rn.status_code == 200 and norm(ro.json()) == norm(rn.json())):
                            bad.append(f"{w}x{h} /session/{ep} #{i} {mode}")
                    for mk, ds in ((False, False), (True, False)):
                        payload = dict(blend=80, makeMask=mk, dressSmooth=ds, dressStrength=55)
                        with H.fixed_fast_inpaint(SRV_OLD.ENGINE):
                            ro = co.post("/session/apply", json=dict(payload, session_id=so))
                        rn = cn.post("/session/apply", json=dict(payload, session_id=sn))
                        binary_same(f"/session/apply {mode} mask={mk}", ro, rn)
                    ro = co.post("/session/recompute", json=dict(session_id="nope", params=p))
                    rn = cn.post("/session/recompute", json=dict(session_id="nope", params=p))
                    n += 1
                    if not (ro.status_code == rn.status_code == 500 and ro.json() == rn.json()):
                        bad.append(f"{w}x{h} expired session answer")
                    co.post("/session/close", json=dict(session_id=so))
                    cn.post("/session/close", json=dict(session_id=sn))

                # ---- what v3.2.1 does not have ----
                n += 1
                hl = cn.get("/health").json()
                if hl.get("app") != srv.APP_ID or hl.get("version") != srv.APP_VERSION or hl.get("models_dir") != srv.MODELS_DIR:
                    bad.append("/health does not name this program and its models folder")
                # /health tells the panel what the processor had to compute although a GPU is there (4.10.0)
                if hl.get("cpu_fallback") != {}:
                    bad.append(f"/health: cpu_fallback must be empty without trouble, it is {hl.get('cpu_fallback')!r}")
                srv.ENGINE.cpu_fallback["lama"] = "CUDA out of memory"
                if cn.get("/health").json().get("cpu_fallback") != {"lama": "CUDA out of memory"}:
                    bad.append("/health does not pass on what the processor had to compute")
                srv.ENGINE.cpu_fallback.clear()
                # clothing + cyclorama through the whole interactive round trip
                p2 = dict(H.STD, speedMode="fast", cycCurve=60, dressSmooth=True, dressStrength=60)
                r = cn.post("/session/start", content=packet({"width": w, "height": h, "channels": img.shape[2], "bitDepth": bd, "params": p2}, img))
                n += 1
                if r.status_code != 200:
                    bad.append(f"{w}x{h} /session/start with clothing + cyclorama")
                else:
                    sid = r.json()["session_id"]
                    for ep, payload in (("recompute", dict(params=dict(p2, cycCurve=100), preserve_edits=True)),
                                        ("dress-preview", dict(dressSmooth=True, dressStrength=90))):
                        n += 1
                        if cn.post(f"/session/{ep}", json=dict(payload, session_id=sid)).status_code != 200:
                            bad.append(f"{w}x{h} /session/{ep} (new features)")
                    r = cn.post("/session/apply", json=dict(session_id=sid, blend=100, makeMask=False, dressSmooth=True, dressStrength=60))
                    n += 1
                    if r.status_code != 200 or len(split(r.content)[1]) != w * h * 4 * (2 if bit16 else 1):
                        bad.append(f"{w}x{h} /session/apply (new features)")
                    cn.post("/session/close", json=dict(session_id=sid))
                # light preview: "quick" in /session/recompute, the current settings inside /session/apply
                if (w, h) == cases[0][:2]:
                    n += _http_quick_round_trip(cn, srv, packet, split, bad)
                    n += _http_backup_round_trip(cn, srv, bad)
                # format 5:7
                r = cn.post("/extend-canvas", content=packet({"width": w, "height": h, "channels": img.shape[2], "bitDepth": bd,
                                                              "params": {"ratioShort": 5, "ratioLong": 7}, "jobId": "f"}, img))
                n += 1
                plan = ENG._extension_plan(w, h)
                if r.status_code != 200:
                    bad.append(f"{w}x{h} /extend-canvas status {r.status_code}")
                elif (plan["new_w"], plan["new_h"]) == (w, h):
                    # this test frame already is 5:7: nothing to add, the answer is plain JSON
                    if r.json().get("unchanged") is not True:
                        bad.append(f"{w}x{h} /extend-canvas on a frame that already is 5:7 (first request)")
                else:
                    m5, body = split(r.content)
                    if (m5["width"], m5["height"], m5["left"], m5["top"]) != (plan["new_w"], plan["new_h"], plan["left"], plan["top"]) \
                            or len(body) != plan["new_w"] * plan["new_h"] * 4 * (2 if bit16 else 1):
                        bad.append(f"{w}x{h} /extend-canvas answer")
                    ext = np.frombuffer(body, np.uint16 if bit16 else np.uint8).reshape(plan["new_h"], plan["new_w"], 4)
                    again = cn.post("/extend-canvas", content=packet({"width": plan["new_w"], "height": plan["new_h"], "channels": 4, "bitDepth": bd,
                                                                      "params": {}}, ext))
                    n += 1
                    if again.status_code != 200 or again.json().get("unchanged") is not True:
                        bad.append(f"{w}x{h} /extend-canvas on a frame that already is 5:7")
    finally:
        sys.stdout.close()
        sys.stdout, sys.stderr = real_out, real_err
    report("http", not bad, f"{n} HTTP requests: legacy regime answered identically to the v3.2.1 server, new endpoints answer correctly" if not bad else f"DIFFERENT: {bad}")


# ----------------------------------------------------------------------------------------------------------------------
# A dark backdrop: dust against the noise of the place, the pictures of the big window
# ----------------------------------------------------------------------------------------------------------------------
def _low_key_frame(w, h, kind="floor", seed=3, dust=24):
    """
    A frame whose noise grows with the light, as the noise of a camera does (white, the same in the three channels,
    plus a little colour noise): about 1.2 levels where the backdrop is nearly black, 2.6 where it is lit.
      "floor"  a dark wall over a lit floor, the left part of the floor darker - a low-key shot. Most of the frame is
               dark, so the noise of the frame as a whole is the noise of the dark part;
      "even"   the same light everywhere (the brightness of the lit floor);
      "vignette" a light backdrop that gets a quarter darker towards the corners - an ordinary studio frame.
    `dust`: real specks (30-45 levels darker or lighter, 4-10 px across) drawn where the frame is lit.
    The frame is big on purpose: the two passes of the dust search work at different scales, and only on a frame of
    about this size do they see what they see on a real 20-megapixel photo.
    Returns (frame, silhouette 1024, how lit every pixel is 0..1, person (bool), centres of the specks).
    """
    rng = np.random.default_rng(seed)
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    xx = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    if kind == "floor":
        light = 1.0 / (1.0 + np.exp(-(yy - 0.58) * 9.0)) * (0.55 + 0.45 * xx)
    elif kind == "even":
        light = np.ones((h, w), np.float32)
    else:
        light = 1.0 - 0.25 * (((xx - 0.5) * 2) ** 2 + ((yy - 0.5) * 2) ** 2) / 2.0
    light = np.broadcast_to(light, (h, w)).astype(np.float32)
    lum = 16.0 + 105.0 * light
    sigma = 0.4 + 0.2 * np.sqrt(lum)
    img = lum[..., None] * np.float32([1.02, 1.0, 0.97])
    img = img + (rng.standard_normal((h, w, 1)).astype(np.float32) + 0.25 * rng.standard_normal((h, w, 3)).astype(np.float32)) * sigma[..., None]
    _, sil = H.make_studio_image(w, h, n_dust=0, n_hair=0, seed=1)
    person = cv2.resize(sil, (w, h)) > 0.5
    centres, tries = [], 0
    while len(centres) < dust and tries < 5000:
        tries += 1
        cx, cy = int(rng.integers(60, w - 60)), int(rng.integers(int(h * 0.70), h - 60))
        if light[cy, cx] < 0.6 or person[cy - 40:cy + 40, cx - 40:cx + 40].any() or any((cx - a) ** 2 + (cy - b) ** 2 < 90 ** 2 for a, b in centres):
            continue
        spot = np.zeros((h, w), np.float32)
        cv2.circle(spot, (cx, cy), int(rng.choice([2, 3, 3, 4, 5])) * max(1, w // 1500), 1.0, -1, lineType=cv2.LINE_AA)
        img -= float(rng.integers(30, 46)) * (1 if rng.random() < 0.7 else -1) * spot[..., None]
        centres.append((cx, cy))
    img = np.clip(img, 0, 255)
    img[person] = (70, 62, 58)
    return img.astype(np.uint8), sil, light, person, centres


def check_dark():
    bad, notes = [], []
    w, h = 2800, 4200
    base = dict(H.STD, spots=80, scuffs=0, blur=0, cycCurve=0, seamOn=False, smokeOn=False, speedMode="fast")

    # 1. a dark wall over a lit floor: plain noise of the lit part is not dust
    img, sil, light, person, centres = _low_key_frame(w, h, "floor")
    away = ~(cv2.dilate(person.astype(np.uint8), np.ones((41, 41), np.uint8)) > 0)
    near = np.zeros((h, w), np.uint8)
    for cx, cy in centres:
        cv2.circle(near, (cx, cy), 40, 1, -1)
    lit = (light > 0.6) & away & (near == 0)       # the lit floor without the drawn dust and the person
    got = {}
    for local in (False, True):
        oc = {}
        _quiet(H.make_engine(E, sil).process, img, 8, dict(base, grainLocal=local), out_cache=oc)
        heal = oc["heal_mask_full"] > 0
        got[local] = (float(heal[lit].mean()), sum(bool(heal[cy, cx]) for cx, cy in centres), heal)
    oc = {}
    _quiet(H.make_engine(E, sil).process, img, 8, dict(base), out_cache=oc)
    if not np.array_equal(oc["heal_mask_full"] > 0, got[True][2]):
        bad.append("judging dust against the local noise must be the default (no 'grainLocal' in the request)")
    was, now = got[False][0], got[True][0]
    if was < 0.30:
        bad.append(f"the test frame is not what it should be: judged against the noise of the frame only {was * 100:.1f}% of the lit floor is 'dust'")
    if now > 0.02 or now > was / 20.0:
        bad.append(f"lit floor of a dark frame: {now * 100:.1f}% of it is marked as dust (it was {was * 100:.0f}% with the noise of the whole frame)")
    if got[True][1] < len(centres) - 1:
        bad.append(f"real dust in the lit floor: only {got[True][1]} of {len(centres)} specks found")
    dark_part = (light < 0.05) & away
    if not np.array_equal(got[False][2][dark_part], got[True][2][dark_part]):
        bad.append("the dark part of the frame must be searched exactly as before")
    notes.append(f"lit floor of a dark frame: {was * 100:.0f}% -> {now * 100:.2f}% of it taken for dust, {got[True][1]} of {len(centres)} real specks found")

    # 2. where the light is even nothing changes: the search gives the very same mask as before
    for kind in ("even", "vignette"):
        img_e, sil_e, _, _, cen_e = _low_key_frame(w, h, kind, seed=5)
        eng = H.make_engine(E, sil_e)
        fg, core = eng._clean_fg_mask(_quiet(eng._predict_fg_raw, img_e), w, h, 70.0)
        st, _, sk, shd = eng._compute_protection_maps_small(img_e, fg, core, 80.0, False, True)
        a, _ = eng._detect_spots_mask(img_e, fg, st, sk, shd, 80.0, fast_mode=False, local_grain=False)
        b, _ = eng._detect_spots_mask(img_e, fg, st, sk, shd, 80.0, fast_mode=False, local_grain=True)
        if not np.array_equal(a, b):
            bad.append(f"evenly lit frame ('{kind}'): the dust mask differs on {int((a != b).sum())} px from the search of before")
        if sum(bool(b[cy, cx]) for cx, cy in cen_e) < len(cen_e) - 1:
            bad.append(f"evenly lit frame ('{kind}'): real dust is not found")
    notes.append("evenly lit frames: the same mask as before")

    # 2b. the rule itself, on drawn noise maps: 45 x 30 cells of known noise, the noise of the frame as a whole is 1
    def gain_of(cells):
        hp = np.abs(np.random.default_rng(11).standard_normal((600, 900)).astype(np.float32)) * np.kron(cells, np.ones((20, 20), np.float32))
        return ENG._local_grain_gain(hp, np.ones((600, 900), bool), 1.0)

    plain = np.ones((30, 45), np.float32)
    # an ordinary frame, a tenth of it noticeably noisier than the rest (his light-grey sample is like that)
    cells = plain.copy()
    cells[10:20, 5:19] = 1.15
    if gain_of(cells) is not None:
        bad.append("an ordinary frame with a part 15% noisier than the rest must be searched exactly as before")
    # an evenly lit frame with one small patch far noisier: only that patch is judged more strictly, and only partly
    cells = plain.copy()
    cells[12:18, 20:26] = 1.42
    g = gain_of(cells)
    if g is None or g.shape != (30, 45) or not 1.05 < float(g[14:16, 22:24].mean()) < 1.30 or float(g[:8].max()) != 1.0 or float(g[:, :14].max()) != 1.0:
        bad.append(f"a small noisier patch on an evenly lit frame: gain {None if g is None else (round(float(g[14:16, 22:24].mean()), 2), float(g[:8].max()))}"
                   ", expected about 1.17 in the patch and exactly 1 elsewhere")
    # a low-key frame, the lit two fifths twice as noisy as the dark majority: the lit part is judged by its own noise
    cells = plain.copy()
    cells[18:] = 1.9
    g = gain_of(cells)
    if g is None or not 1.75 < float(g[22:].mean()) < 2.05 or float(g[:14].max()) > 1.15 or float(g.min()) < 1.0:
        bad.append(f"a low-key frame: gain {None if g is None else (round(float(g[22:].mean()), 2), round(float(g[:14].max()), 2))}, expected about 1.9 in the lit part and 1 in the dark one")

    # 3. the pictures of the big window: a dark frame keeps its fine noise (JPEG 100), a light one stays at 90
    import base64

    def opened(frame, matte, **over):
        eng = H.make_engine(E, matte)
        r = _quiet(eng.start_session, frame, 8, dict(base, **over))
        return eng, r

    def fine_kept(eng, r, key="orig_jpg_b64"):
        """
        How much of the pixel-to-pixel noise of the dark wall is left in the picture the window gets. Measured
        against what the picture is made of: the photo at the size of the picture - and, for the cleaned photo of a
        picture larger than the working size, the working-size photo enlarged like the layer is (check_sharp).
        """
        s = eng._active_session
        pic = cv2.imdecode(np.frombuffer(base64.b64decode(r[key]), np.uint8), cv2.IMREAD_GRAYSCALE).astype(np.float32)
        made_of = s["orig_small_bgr"]
        if pic.shape != made_of.shape[:2]:
            made_of = (s["orig_disp_bgr"] if key == "orig_jpg_b64" else
                       cv2.resize(made_of, (pic.shape[1], pic.shape[0]), interpolation=cv2.INTER_CUBIC))
        src = cv2.cvtColor(made_of, cv2.COLOR_BGR2GRAY).astype(np.float32)
        ph, pw = src.shape
        wall = (slice(int(ph * 0.05), int(ph * 0.45)), slice(int(pw * 0.05), int(pw * 0.30)))
        return float(np.abs(np.diff(pic[wall], axis=1)).mean() / max(1e-6, np.abs(np.diff(src[wall], axis=1)).mean()))

    small, sil_s, _, _, _ = _low_key_frame(1500, 2000, "floor", seed=4, dust=6)
    light_frame, sil_l = H.make_studio_image(1500, 2000, n_dust=40, n_hair=3, seed=5)
    e_dark, r_dark = opened(small, sil_s)
    e_90, r_90 = opened(small, sil_s, previewQuality=90)
    e_light, r_light = opened(light_frame, sil_l)
    q = lambda e: e._active_session.get("preview_q")  # noqa: E731
    if q(e_dark) != ENG.PREVIEW_JPEG_QUALITY_DARK or q(e_light) != ENG.PREVIEW_JPEG_QUALITY or q(e_90) != 90:
        bad.append(f"preview quality: dark frame {q(e_dark)}, light frame {q(e_light)}, dark frame with 'previewQuality' 90 -> {q(e_90)}")
    k100, k90 = fine_kept(e_dark, r_dark), fine_kept(e_90, r_90)
    if k100 < 0.85 or k90 > 0.6:
        bad.append(f"dark frame: the picture keeps {k100 * 100:.0f}% of the fine noise (must keep it), at quality 90 {k90 * 100:.0f}% (the test expects a visible loss there)")
    if fine_kept(e_dark, r_dark, "comp_jpg_b64") < 0.6:
        bad.append("dark frame: the picture of the cleaned photo lost its fine noise")
    sid = r_dark["session_id"]
    r_re = _quiet(e_dark.recompute_session, sid, dict(base, spots=60), True, None, True)
    r_ed = _quiet(e_dark.edit_session_mask, sid, "stroke", [{"x": 0.2, "y": 0.2, "norm": 1}], 20, True, False, 45.0)
    if min(fine_kept(e_dark, r_re, "comp_jpg_b64"), fine_kept(e_dark, r_ed, "comp_jpg_b64")) < 0.6 or q(e_dark) != ENG.PREVIEW_JPEG_QUALITY_DARK:
        bad.append("dark frame: a refresh or a brush stroke brought the coarse picture back")
    for asked, want in ((70, 70), (5, 50), (300, 100), ("abc", ENG.PREVIEW_JPEG_QUALITY_DARK), (None, ENG.PREVIEW_JPEG_QUALITY_DARK)):
        e_x, _ = opened(small, sil_s, previewQuality=asked)
        if q(e_x) != want:
            bad.append(f"'previewQuality' {asked!r} -> {q(e_x)}, expected {want}")
    notes.append(f"window pictures of a dark frame keep {k100 * 100:.0f}% of the fine noise (at JPEG 90: {k90 * 100:.0f}%), a light frame stays at JPEG 90")
    report("dark", not bad, "; ".join(notes) if not bad else "wrong:\n  " + "\n  ".join(bad))


# ----------------------------------------------------------------------------------------------------------------------
# What is studio gear, and a dirty spot inside a cast shadow
# ----------------------------------------------------------------------------------------------------------------------
def _gear_frame(w=1500, h=2000, seed=6):
    """
    A light floor with real studio gear and with two things that only have long strong edges:
      shadow   a hard-edged cast shadow on the floor (light on one side, shadow on the other - nothing stands there);
      scratch  a thin faint scratch (an eighth of the light is missing in it);
      specks   dust right next to the shadow edge and around the scratch;
      pole     a light stand inside the frame: a thin dark pole with two legs;
      cable    a thin dark cable on the floor;
      panel    a reflector that comes in over the right border: a broad light panel - a one-sided edge without a
               body, like the shadow, but at the border of the frame.
    Returns (frame, silhouette 1024, dict: every item as a float map 0..1, 'shadow_edge', 'panel_edge', 'person',
    'specks': centres of the specks near the shadow edge / the scratch).
    """
    rng = np.random.default_rng(seed)
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    xx = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    lum = 150.0 * (1.0 - 0.22 * ((xx - 0.5) * 2) ** 2 - 0.15 * ((yy - 0.45) * 2) ** 2) + 25.0 * yy
    lum = np.broadcast_to(lum, (h, w)).astype(np.float32).copy()
    pts = lambda coords: np.array([[int(x * w), int(y * h)] for x, y in coords], np.int32)  # noqa: E731

    def drawn(fn, blur=1.2):
        m = np.zeros((h, w), np.float32)
        fn(m)
        return cv2.GaussianBlur(m, (0, 0), blur)

    shadow = drawn(lambda m: cv2.fillPoly(m, [pts([(0.07, 0.82), (0.33, 0.79), (0.38, 0.90), (0.10, 0.94)])], 1.0), 1.5)
    scratch = drawn(lambda m: cv2.polylines(m, [pts([(0.66, 0.875), (0.74, 0.915), (0.83, 0.940), (0.88, 0.972)])], False, 1.0, 3, cv2.LINE_AA), 0.8)

    def stand(m):
        for (xa, ya), (xb, yb), thick in (((0.82, 0.30), (0.82, 0.74), 12), ((0.82, 0.70), (0.76, 0.78), 9), ((0.82, 0.70), (0.88, 0.78), 9)):
            cv2.line(m, (int(xa * w), int(ya * h)), (int(xb * w), int(yb * h)), 1.0, thick, cv2.LINE_AA)

    pole = drawn(stand)
    cable = drawn(lambda m: cv2.polylines(m, [pts([(0.06, 0.665), (0.13, 0.700), (0.22, 0.705), (0.30, 0.760)])], False, 1.0, 4, cv2.LINE_AA), 0.8)
    panel = drawn(lambda m: cv2.fillPoly(m, [pts([(0.90, 0.10), (1.01, 0.09), (1.01, 0.43), (0.915, 0.42)])], 1.0))
    lum = lum * (1.0 - 0.40 * shadow) * (1.0 - 0.125 * scratch)
    lum = lum * (1.0 - panel) + 222.0 * panel
    lum = lum * (1.0 - pole) + 32.0 * pole
    lum = lum * (1.0 - cable) + 34.0 * cable
    grown = lambda m, k: cv2.dilate(m.astype(np.uint8), np.ones((k, k), np.uint8)) > 0  # noqa: E731
    edge = cv2.Canny((shadow > 0.5).astype(np.uint8) * 255, 50, 150) > 0
    specks = {"edge": [], "scratch": []}
    for key, zone, n in (("edge", grown(edge, 61) & ~grown(edge, 25), 14), ("scratch", grown(scratch > 0.3, 91) & ~grown(scratch > 0.05, 31), 8)):
        ys, xs = np.nonzero(zone)
        tries = 0
        while len(specks[key]) < n and tries < 4000:
            tries += 1
            i = int(rng.integers(0, ys.size))
            cx, cy = int(xs[i]), int(ys[i])
            if any((cx - a) ** 2 + (cy - b) ** 2 < 70 ** 2 for a, b in specks["edge"] + specks["scratch"]) or not (20 < cx < w - 20 and 20 < cy < h - 20):
                continue
            spot = np.zeros((h, w), np.float32)
            cv2.circle(spot, (cx, cy), 3, 1.0, -1, lineType=cv2.LINE_AA)
            lum -= 38.0 * spot
            specks[key].append((cx, cy))
    img = np.clip(lum[..., None] * np.float32([1.02, 1.0, 0.97]) + rng.standard_normal((h, w, 3)).astype(np.float32) * 1.8, 0, 255)
    _, sil = H.make_studio_image(w, h, n_dust=0, n_hair=0, seed=1)
    person = cv2.resize(sil, (w, h)) > 0.5
    img[person] = (40, 40, 46)
    return img.astype(np.uint8), sil, dict(shadow=shadow, scratch=scratch, pole=pole, cable=cable, panel=panel, person=person, specks=specks,
                                           shadow_edge=grown(edge, 5), panel_edge=cv2.Canny((panel > 0.5).astype(np.uint8) * 255, 50, 150) > 0)


def check_gear():
    """
    Studio gear is left untouched by every stage, so whatever is taken for gear keeps its dirt. Until 4.5.0 every
    long strong edge was gear - the hard edge of a cast shadow and a scratch on the floor included (the owner's grey
    frame: dust and a scratch left inside untouched rectangles). Gear is now told by its body.
    """
    bad, notes = [], []
    w, h = 1500, 2000
    img, sil, g = _gear_frame(w, h)
    gray = lambda im: im.astype(np.float32).mean(axis=2)  # noqa: E731
    grown = lambda m, k: cv2.dilate(m.astype(np.uint8), np.ones((k, k), np.uint8)) > 0  # noqa: E731
    zones = {"shadow edge": g["shadow_edge"], "scratch": g["scratch"] > 0.5, "stand": g["pole"] > 0.5, "cable": g["cable"] > 0.5,
             "reflector at the border": g["panel_edge"]}
    # 1. the map of what is kept as gear
    eng = H.make_engine(E, sil)
    fg, core = eng._clean_fg_mask(_quiet(eng._predict_fg_raw, img), w, h, 70.0)
    kept, smoke = {}, {}
    for body in (True, False):
        smoke[body] = {}
        st, _, _, _ = eng._compute_protection_maps_small(img, fg, core, 80.0, True, True, smoke_auto=True, info=smoke[body], gear_body=body)
        st_full = cv2.resize(st, (w, h), interpolation=cv2.INTER_LINEAR) > 75
        kept[body] = {k: float(st_full[m].mean()) for k, m in zones.items()}
    for k in ("shadow edge", "scratch"):
        if kept[False][k] < 0.9:
            bad.append(f"the test frame is not what it should be: by the old rule the {k} is kept as gear on {kept[False][k] * 100:.0f}% of its length only")
        if kept[True][k] > 0.05:
            bad.append(f"the {k} is still kept as studio gear ({kept[True][k] * 100:.0f}% of it)")
    for k in ("stand", "cable", "reflector at the border"):
        if kept[True][k] < 0.9:
            bad.append(f"the {k} is not kept as studio gear any more ({kept[True][k] * 100:.0f}% of it)")
    # an edge that is not gear is not smoke either (its outline read as wisps and "smoke" was found in the frame)
    if smoke[True].get("found") or smoke[True].get("share", 1.0) > 0.01:
        bad.append(f"a hard shadow edge that is no gear any more was taken for smoke: {smoke[True]}")
    # 2. the result: dust at the shadow edge and the scratch are repaired, the shadow and the gear stay
    scr = g["scratch"] > 0.5
    beside = grown(scr, 25) & ~grown(scr, 13)
    inside = cv2.erode((g["shadow"] > 0.98).astype(np.uint8), np.ones((41, 41), np.uint8)) > 0
    around = grown(g["shadow"] > 0.02, 121) & ~grown(g["shadow"] > 0.02, 41) & ~g["person"]
    thin_gear = (g["pole"] > 0.02) | (g["cable"] > 0.02)
    base = dict(H.STD, scuffs=0, blur=0, cycCurve=0, seamOn=False, smokeAuto=True)
    o = gray(img)

    def cleaned(mode, **over):
        oc = {}
        out, stats = _quiet(H.make_engine(E, sil).process, img, 8, dict(base, speedMode=mode, **over), out_cache=oc)
        heal = oc["heal_mask_full"] > 0
        c = gray(_comp(img, out))
        return dict(heal=heal, stats=stats, c=c, found={k: sum(bool(heal[cy, cx]) for cx, cy in v) for k, v in g["specks"].items()},
                    line=float(c[beside].mean() - c[scr].mean()), shadow=float(np.median(c[around]) - np.median(c[inside])))

    line0, shadow0 = float(o[beside].mean() - o[scr].mean()), float(np.median(o[around]) - np.median(o[inside]))
    n_edge, n_scr = len(g["specks"]["edge"]), len(g["specks"]["scratch"])
    for mode in ("quality", "fast"):
        now, old = cleaned(mode), cleaned(mode, gearBody=False)
        if not np.array_equal(now["heal"], cleaned(mode, gearBody=True)["heal"]):
            bad.append(f"{mode}: telling gear by its body must be the default (no 'gearBody' in the request)")
        if old["found"]["edge"] > n_edge // 2 or float(old["heal"][scr].mean()) > 0.1:
            bad.append(f"{mode}: the test frame is not what it should be: by the old rule {old['found']['edge']} of {n_edge} specks at the shadow edge are found, "
                       f"{old['heal'][scr].mean() * 100:.0f}% of the scratch")
        if now["found"]["edge"] < n_edge - 1 or now["found"]["scratch"] < n_scr - 1:
            bad.append(f"{mode}: dust next to a shadow edge: {now['found']['edge']} of {n_edge} specks found; around a scratch: {now['found']['scratch']} of {n_scr}")
        if float(now["heal"][scr].mean()) < 0.9 or now["line"] > 0.4 * line0:
            bad.append(f"{mode}: the scratch: {now['heal'][scr].mean() * 100:.0f}% of it marked, {line0:.1f} -> {now['line']:.1f} levels")
        if abs(now["shadow"] - shadow0) > 0.03 * shadow0:
            bad.append(f"{mode}: the cast shadow itself changed: {shadow0:.1f} -> {now['shadow']:.1f} levels deep")
        if bool(now["heal"][thin_gear].any()) or float(np.abs(now["c"] - o)[thin_gear].max()) > 0.0:
            bad.append(f"{mode}: the stand or the cable was touched ({int(now['heal'][thin_gear].sum())} px marked for repair)")
        if now["stats"].get("smoke", {}).get("found"):
            bad.append(f"{mode}: smoke was 'found' in a frame without any: {now['stats'].get('smoke')}")
        if mode == "fast":
            notes.append(f"dust at a hard shadow edge: {old['found']['edge']} -> {now['found']['edge']} of {n_edge} specks found; "
                         f"a scratch {line0:.0f} -> {now['line']:.1f} levels (was left as 'gear')")
            # the green preview (before the big window is opened) shows the very same marks
            green, _ = _quiet(H.make_engine(E, sil).preview_action_mask, img, 8, dict(base, speedMode=mode))
            missed, extra = int((now["heal"] & (green == 0)).sum()), int(((green > 0) & ~grown(now["heal"], 3)).sum())
            if missed or extra:
                bad.append(f"the green preview differs from the cleaning ({missed} px not shown, {extra} px shown but not cleaned)")
    report("gear", not bad, "; ".join(notes) + "; the shadow, a stand, a cable and a reflector at the frame border stay as they are; "
           "a shadow edge is not taken for smoke" if not bad else "wrong:\n  " + "\n  ".join(bad))


def _shadow_frame(w=2800, h=4200, seed=8, stain=12.3, faint=9.8):
    """
    A light floor with a broad cast shadow next to the person (denser towards one side, as real shadows are), and:
      stain    a dirty spot wholly inside the shadow - what the rule is for. Sized and shaded like the owner's scuff
               under a hand's shadow: 1.4 x the threshold of the place, the shadow around it varying by a good half
               of its depth; too big and too faint for the fine pass of the dust search;
      faint    a patch only a little darker than the shadow (the shadow's own unevenness);
      gap      a light patch (a gap in the shadow);
      rim      a dark patch on the soft rim of the shadow;
      tip      a short narrow tongue of the shadow sticking out into the lit floor (the shadow of a finger);
      contact  the dark core of the contact shadow, right at a shoe.
    The frame is big for the reason given at _low_key_frame.
    Returns (frame, silhouette 1024, dict: every item as a float map 0..1, 'shadow', 'person').
    """
    rng = np.random.default_rng(seed)
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    xx = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    lum = 150.0 * (1.0 - 0.22 * ((xx - 0.5) * 2) ** 2 - 0.15 * ((yy - 0.45) * 2) ** 2) + 25.0 * yy
    lum = np.broadcast_to(lum, (h, w)).astype(np.float32).copy()
    _, sil = H.make_studio_image(w, h, n_dust=0, n_hair=0, seed=1)
    person = cv2.resize(sil, (w, h)) > 0.5
    cx = w // 2
    u = w / 1500.0

    def ell(x, y, ax, ay, blur):
        m = np.zeros((h, w), np.float32)
        cv2.ellipse(m, (int(x * w), int(y * h)), (int(ax * u), int(ay * u)), 0, 0, 360, 1.0, -1, lineType=cv2.LINE_AA)
        return cv2.GaussianBlur(m, (0, 0), blur * u)

    shadow = ell(0.755, 0.80, 0.16 * 1500, 0.065 * 2000, 12.0)
    dense = 1.0 + 0.36 * np.clip((xx - 0.755) / 0.10, -1.0, 1.0)
    tip = np.zeros((h, w), np.float32)
    cv2.line(tip, (int(0.60 * w), int(0.745 * h)), (int(0.645 * w), int(0.765 * h)), 1.0, int(16 * u), cv2.LINE_AA)
    tip = cv2.GaussianBlur(tip, (0, 0), 2.0 * u)
    small = np.zeros((max(8, h // 8), max(8, w // 8)), np.float32)
    cv2.ellipse(small, (cx // 8 + int(30 * u), int(h * 0.905) // 8), (max(1, int(w * 0.11) // 8), max(1, int(h * 0.022) // 8)), 0, 0, 360, 1.0, -1)
    contact_soft = cv2.resize(cv2.GaussianBlur(small, (0, 0), 6 * u), (w, h))
    items = dict(
        stain=ell(0.735, 0.805, 15, 8, 2.2),
        faint=ell(0.800, 0.775, 15, 8, 0.8),
        gap=ell(0.700, 0.770, 15, 8, 2.2),
        rim=ell(0.915, 0.800, 15, 8, 2.2),
        contact=ell(0.5 + 0.030, 0.9095, 15, 8, 2.2),
    )
    lum = lum * (1.0 - 0.28 * np.maximum(shadow * dense, tip)) * (1.0 - 0.38 * contact_soft)
    lum = lum - stain * items["stain"] - faint * items["faint"] + 18.0 * items["gap"] - 18.0 * items["rim"] - 18.0 * items["contact"]
    img = lum[..., None] * np.float32([1.02, 1.0, 0.97])
    img = img + (rng.standard_normal((h, w, 1)).astype(np.float32) + 0.25 * rng.standard_normal((h, w, 3)).astype(np.float32)) * 1.8
    img = np.clip(img, 0, 255)
    img[person] = (40, 40, 46)
    items.update(shadow=shadow, tip=tip, person=person)
    return img.astype(np.uint8), sil, items


def _shadow_rule_cases():
    """
    The shadow-spot rule on drawn inputs, at the working size of a 20-megapixel frame: one blob per case.
    A case: (name, how dark the blob is against the shadow in units of the threshold, by how much the shadow around
    it varies as a share of the blob's depth, size (w, h) in px, what else is there, taken or not).
    Returns (cases, centre of every blob, the mask the rule gives, the map of the blobs).
    """
    thr = 8.46  # the threshold inside a full shadow at the usual settings
    cases = [
        # the owner's frames (the numbers are in the engine, at SHADOW_SPOT_*)
        ("the scuff in a hand's shadow, quality mode", 1.36, 0.61, (18, 9), None, True),
        ("the scuff in a hand's shadow, fast mode", 1.41, 0.50, (14, 9), None, True),
        ("a faint patch along the rim of a pool of light", 1.13, 0.30, (25, 8), None, False),
        ("another such patch", 1.07, 0.30, (11, 8), None, False),
        ("a piece of a hard shadow edge", 4.64, 0.98, (8, 20), None, False),
        # every limit from its other side
        ("a clear spot in an even shadow", 3.0, 0.20, (16, 12), None, True),
        ("a spot whose surroundings vary by 0.9 of its depth", 1.36, 0.90, (18, 9), None, False),
        ("a deep spot, the shadow around it varies by 14 levels", 3.5, 14.0 / (3.5 * thr), (16, 12), None, False),
        ("a deep spot, the shadow around it varies by 10 levels", 3.5, 10.0 / (3.5 * thr), (16, 12), None, True),
        ("a spot right next to the person", 1.6, 0.2, (18, 9), "person", False),
        ("a spot at the border of the frame", 1.6, 0.2, (18, 9), "border", False),
        ("a spot with other finds all around it", 1.6, 0.2, (18, 9), "busy", False),
        ("a long streak", 1.6, 0.2, (48, 8), None, False),
        ("a big patch", 1.6, 0.2, (90, 60), None, False),
        ("a light patch", 1.6, 0.2, (18, 9), "light", False),
    ]
    sw, sh = 1365, 2048
    l_med = np.full((sh, sw), 100.0, np.float32)
    dd = np.zeros((sh, sw), np.float32)
    lighter = np.zeros((sh, sw), np.float32)
    safe = np.ones((sh, sw), bool)
    extra = np.zeros((sh, sw), np.uint8)
    centres = []
    for i, (_, peak, vary, (bw, bh), what, _) in enumerate(cases):
        cx, cy = (12 if what == "border" else 200 + 320 * (i % 4)), 200 + 320 * (i // 4)
        depth = peak * thr
        l_med[cy - 150:cy + 150, cx:min(sw, cx + 150)] += vary * depth      # the shadow: two tones that meet at the blob
        blob = np.zeros((sh, sw), np.float32)
        cv2.ellipse(blob, (cx, cy), (bw // 2, bh // 2), 0, 0, 360, 1.0, -1, lineType=cv2.LINE_AA)
        blob = cv2.GaussianBlur(blob, (0, 0), 0.8)
        if what == "light":
            lighter += depth * blob
        else:
            dd += depth * blob
        if what == "person":
            safe[cy - 4:cy + 4, cx + bw // 2 + 3:cx + bw // 2 + 9] = False
        if what == "busy":
            extra[cy - bh:cy + bh:2, cx - bw:cx + bw:2] = 1
        centres.append((cx, cy))
    cand = ((dd > thr) | (lighter > thr)).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(cand, connectivity=8)
    out = ENG._shadow_spots(np.arange(1, n), stats, labels, np.maximum(cand, extra), dd, np.full((sh, sw), thr, np.float32),
                            l_med - dd + lighter, l_med, safe, 1.8)
    return cases, centres, out, dd


def check_shadow():
    """
    A dirty spot inside a cast shadow is repaired (the owner's grey frame: a scuff under the shadow of a hand was
    the one mark the dust search kept, because inside a shadow it used to drop everything bigger than a speck);
    the shadow itself - its rim, its denser parts, the shadow under a shoe - is not.
    """
    bad, notes = [], []
    # 1. the rule itself, with the numbers measured on the owner's frames
    cases, centres, out, dd = _shadow_rule_cases()
    rows, cols = np.arange(out.shape[0])[:, None], np.arange(out.shape[1])[None, :]
    for (name, _, _, _, _, want), (cx, cy) in zip(cases, centres):
        got = bool(out[cy, cx])
        if got != want:
            bad.append(f"{name}: {'taken' if got else 'left'}, must be {'taken' if want else 'left'}")
        elif got and not bool(out[(dd > 1.8) & (np.abs(rows - cy) < 80) & (np.abs(cols - cx) < 80)].all()):
            bad.append(f"{name}: taken, but not whole (its faint rim would stay as a ring)")
    # 2. a whole frame, both speed modes
    w, h = 2800, 4200
    img, sil, g = _shadow_frame(w, h)
    gray = lambda im: im.astype(np.float32).mean(axis=2)  # noqa: E731
    grown = lambda m, k: cv2.dilate(m.astype(np.uint8), np.ones((k, k), np.uint8)) > 0  # noqa: E731
    names = ("stain", "faint", "gap", "rim", "contact")
    core = {n: g[n] > 0.5 for n in names}
    ring = {n: grown(core[n], 121) & ~grown(g[n] > 0.02, 31) & ~g["person"] for n in names}
    near_stain = grown(g["stain"] > 0.05, 61)
    marks = np.maximum.reduce([g[n] for n in names])
    in_shadow = (g["shadow"] > 0.98) & ~grown(marks > 0.02, 61)
    lit_floor = grown(g["shadow"] > 0.02, 241) & ~grown(g["shadow"] > 0.02, 81) & ~g["person"] & (g["tip"] < 0.01)
    depth = lambda a, n: float(np.median(a[ring[n]]) - a[core[n]].mean())  # noqa: E731
    base = dict(H.STD, scuffs=0, blur=0, cycCurve=0, seamOn=False, smokeOn=False, smokeAuto=True)
    o = gray(img)
    shadow0 = float(np.median(o[lit_floor]) - np.median(o[in_shadow]))

    def cleaned(mode, **over):
        oc = {}
        out_l, _ = _quiet(H.make_engine(E, sil).process, img, 8, dict(base, speedMode=mode, **over), out_cache=oc)
        return oc["heal_mask_full"] > 0, gray(_comp(img, out_l))

    for mode, left_max in (("quality", 0.80), ("fast", 0.40)):  # (the stand-in for the repair network only blurs: a big spot stays half visible)
        (h_on, c_on), (h_off, c_off) = cleaned(mode), cleaned(mode, shadowSpots=False)
        if not np.array_equal(h_on, cleaned(mode, shadowSpots=True)[0]):
            bad.append(f"{mode}: looking for dirt inside shadows must be the default (no 'shadowSpots' in the request)")
        if float(h_off[core["stain"]].mean()) > 0.0:
            bad.append(f"{mode}: the test frame is not what it should be: the spot inside the shadow is found without the rule")
        d0, d1 = depth(o, "stain"), depth(c_on, "stain")
        if float(h_on[core["stain"]].mean()) < 0.9 or d1 > left_max * d0:
            bad.append(f"{mode}: the dirty spot inside the shadow: {h_on[core['stain']].mean() * 100:.0f}% of it marked, {d0:.1f} -> {d1:.1f} levels")
        added = h_on & ~h_off
        if bool((added & ~near_stain).any()):
            bad.append(f"{mode}: the rule marked {int((added & ~near_stain).sum())} px of the shadow that are not the dirty spot")
        for n in names[1:]:
            if abs(depth(c_on, n) - depth(c_off, n)) > 0.05:
                bad.append(f"{mode}: '{n}' was changed by the rule: {depth(c_off, n):.1f} -> {depth(c_on, n):.1f} levels")
        shadow1 = float(np.median(c_on[lit_floor]) - np.median(c_on[in_shadow]))
        if abs(shadow1 - shadow0) > 0.03 * shadow0:
            bad.append(f"{mode}: the cast shadow itself changed: {shadow0:.1f} -> {shadow1:.1f} levels deep")
        if mode == "fast":
            notes.append(f"a dirty spot inside a cast shadow: {d0:.1f} -> {d1:.1f} levels (was left alone)")
            green, _ = _quiet(H.make_engine(E, sil).preview_action_mask, img, 8, dict(base, speedMode=mode))
            missed, extra = int((h_on & (green == 0)).sum()), int(((green > 0) & ~grown(h_on, 3)).sum())
            if missed or extra:
                bad.append(f"the green preview differs from the cleaning ({missed} px not shown, {extra} px shown but not cleaned)")
    report("shadow", not bad, "; ".join(notes) + f"; the rule on drawn spots: {len(cases)} cases, the owner's scuff taken, the rim of a shadow, a faint "
           "patch, a contact shadow, a streak and a light gap left; nothing else in the shadow is touched" if not bad else "wrong:\n  " + "\n  ".join(bad))


# ----------------------------------------------------------------------------------------------------------------------
# The pictures the window is sent (4.8.0)
# ----------------------------------------------------------------------------------------------------------------------
def check_sharp():
    """
    "The person looks blurred in the window, and is fine after Apply." The session works at <= 1080 px (masks,
    strokes, the cleaned proxy), and up to 4.7.0 the window was sent pictures of that size: in a large window or
    zoomed in, the whole photo was soft. Now the pictures are drawn at up to DISPLAY_LONG px: the photo at that
    size, and over it the layer of the working size, enlarged.
      * the size: twice the working size on a large frame, never larger than the frame, not at all where little
        would be gained; "previewLong" of the request overrules it (the checks against v3.2.1 ask for 1080);
        the working size ("preview_w" / "preview_h"), by which the window places everything, stays;
      * what the layer leaves alone IS the photo of that size, pixel for pixel - the person is as sharp in the
        cleaned picture as in the picture of the original, and several times sharper than the working picture
        enlarged;
      * the layer shows what it showed: reduced to the working size, the pictures are the working pictures (the
        cleaned photo and the mask view), also after the eraser, a light refresh and the exact picture;
      * the eraser brings the photo back (the specks it erased along are as dark as in the picture of the
        original), and what the brush paints away is gone in the larger picture too;
      * ironed clothing keeps the weave of the cloth: the photo takes only the change the ironing makes;
      * a small frame gets the working pictures, as before.
    """
    import base64
    bad, notes = [], []

    def dec(b64):
        return cv2.imdecode(np.frombuffer(base64.b64decode(b64), np.uint8), cv2.IMREAD_COLOR)

    def fine(pic, zone):
        """Fine detail: the mean step between neighbouring pixels inside the zone (levels of 255)."""
        g = cv2.cvtColor(pic, cv2.COLOR_BGR2GRAY).astype(np.float32)
        d = np.abs(np.diff(g, axis=1))
        return float(d[zone[:, 1:] & zone[:, :-1]].mean())

    def gap(a, b, zone=None):
        """How far two pictures are apart (mean of the absolute difference, levels of 255)."""
        d = np.abs(a.astype(np.float32) - b.astype(np.float32)).mean(axis=2)
        return float(d.mean() if zone is None else d[zone].mean())

    # ---- 1. the size, by the rule alone
    for (fw, fh, asked), want in (
        ((5760, 3840, None), (2160, 1440)),      # his camera: twice the working size
        ((3840, 5760, None), (1440, 2160)),
        ((3000, 2000, None), (2160, 1440)),
        ((2000, 1500, None), (2000, 1500)),      # never larger than the frame itself
        ((1300, 900, None), None),               # less than a quarter larger than the working picture: not worth it
        ((1000, 700, None), None),               # a small frame: the working picture is the frame
        ((5760, 3840, 1080), None),              # the working size was asked for (the checks against v3.2.1)
        ((5760, 3840, 0), None),
        ((5760, 3840, 2880), (2880, 1920)),
        ((5760, 3840, 99999), (4320, 2880)),     # the request has a limit
        ((5760, 3840, "abc"), (2160, 1440)),     # nonsense: the usual size
    ):
        sc = min(1.0, 1080.0 / max(fw, fh))
        got = ENG._display_size(fw, fh, max(16, int(round(fw * sc))), max(16, int(round(fh * sc))), asked)
        if got != want:
            bad.append(f"size of the window pictures for a {fw}x{fh} frame, 'previewLong' {asked!r}: {got}, expected {want}")

    # ---- 2. a frame whose person has detail down to one pixel, as skin, hair and cloth have
    w, h = 3000, 2000
    img, sil = H.make_studio_image(w, h, n_dust=60, n_hair=4, seed=77)
    person = cv2.resize(sil, (w, h), interpolation=cv2.INTER_NEAREST) > 0.5
    f = img.astype(np.float32)
    f[person] += np.random.default_rng(11).normal(0.0, 12.0, (h, w)).astype(np.float32)[person][:, None]
    img = np.clip(f, 0, 255).astype(np.uint8)
    dust = [(int((0.66 + 0.02 * i) * w), int(0.70 * h)) for i in range(7)]   # a row of specks on the floor (see 3.)
    for x, y in dust:
        cv2.circle(img, (x, y), 3, tuple(int(v) - 40 for v in img[y, x]), -1, lineType=cv2.LINE_AA)
    # (smoke protection off, as in the owner's presets: with it the stand-in frame keeps parts of the floor
    #  uncleaned, and the row of specks must be something the search removes)
    params = dict(H.STD, speedMode="fast", smokeOn=False)

    def opened(image, matte, **over):
        eng = H.make_engine(E, matte)
        return eng, _quiet(eng.start_session, image, 8, dict(params, **over))

    def stroke(eng, r, pts, radius, erase=False, dress=False):
        return _quiet(eng.edit_session_mask, r["session_id"], "stroke", [{"x": x, "y": y, "norm": 1} for x, y in pts],
                      radius, erase, dress, 80.0, 1.0)

    e_d, r_d = opened(img, sil)                      # as the panel asks: the display pictures
    e_w, r_w = opened(img, sil, previewLong=1080)    # the working pictures, as up to 4.7.0
    pw, ph = r_d["preview_w"], r_d["preview_h"]
    dw, dh = 2160, 1440
    o_d, c_d, v_d = (dec(r_d[key]) for key in ("orig_jpg_b64", "comp_jpg_b64", "overlay_jpg_b64"))
    o_w, c_w, v_w = (dec(r_w[key]) for key in ("orig_jpg_b64", "comp_jpg_b64", "overlay_jpg_b64"))
    if (pw, ph) != (1080, 720) or (r_w["preview_w"], r_w["preview_h"]) != (pw, ph):
        bad.append(f"the working size of the window must stay 1080x720 for a 3000x2000 frame: {pw}x{ph} / {r_w['preview_w']}x{r_w['preview_h']}")
    if not (o_d.shape == c_d.shape == v_d.shape == (dh, dw, 3)):
        bad.append(f"the three pictures of a 3000x2000 frame must be 2160x1440: {o_d.shape}, {c_d.shape}, {v_d.shape}")
    if not (o_w.shape == c_w.shape == v_w.shape == (ph, pw, 3)):
        bad.append(f"with 'previewLong' 1080 the three pictures must be the working ones: {o_w.shape}, {c_w.shape}, {v_w.shape}")
    if bad:
        report("sharp", False, "wrong:\n  " + "\n  ".join(bad))
        return

    def reduced(pic):
        return cv2.resize(pic, (pw, ph), interpolation=cv2.INTER_AREA)

    def zones(eng):
        """(untouched, layer): where the layer shows nothing / everything, with room to spare, at the display size."""
        eff = eng._compute_effective_mask_small(eng._active_session)
        k = np.ones((25, 25), np.uint8)
        big = lambda m: cv2.resize(cv2.erode(m.astype(np.uint8), k), (dw, dh), interpolation=cv2.INTER_NEAREST) > 0  # noqa: E731
        return big(eff == 0), big(eff == 255)

    alone, layer = zones(e_d)
    inside = alone & (cv2.resize(person.astype(np.uint8), (dw, dh), interpolation=cv2.INTER_NEAREST) > 0)
    photo = cv2.cvtColor(cv2.resize(img, (dw, dh), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2BGR)
    if not (inside.mean() >= 0.03 and layer.mean() >= 0.3):
        bad.append(f"test frame: {inside.mean():.1%} of it is the inside of the person, {layer.mean():.1%} is backdrop inside the layer")
    # (a) the picture of the original is the photo at that size
    if not (gap(o_d, photo) <= 2.5 and fine(o_d, inside) >= 0.8 * fine(photo, inside)):
        bad.append(f"the picture of the original is not the photo at 2160x1440: {gap(o_d, photo):.2f} levels apart, "
                   f"fine detail {fine(o_d, inside):.2f} of {fine(photo, inside):.2f}")
    # (b) what the layer leaves alone is that photo, pixel for pixel (the two JPEGs hold the same blocks there)
    if not np.array_equal(c_d[inside], o_d[inside]):
        bad.append(f"inside the person the cleaned picture must BE the picture of the original: "
                   f"{int(np.count_nonzero((c_d != o_d).any(axis=2) & inside))} pixels differ")
    # (c) ...and that is several times sharper than the working picture, enlarged as the window enlarges it
    f_disp, f_photo = fine(c_d, inside), fine(photo, inside)
    f_work = fine(cv2.resize(c_w, (dw, dh), interpolation=cv2.INTER_LINEAR), inside)
    if not (f_disp >= 0.8 * f_photo and f_disp >= 2.0 * f_work):
        bad.append(f"fine detail of the person: {f_disp:.2f} in the window picture, {f_photo:.2f} in the photo of that size, "
                   f"{f_work:.2f} in the working picture enlarged (must keep 80 % and be twice the latter)")

    # (d) the layer shows what it showed
    def same_layer(what, r_disp, r_work, zone_s=None, limit=1.0):
        cd, cw = dec(r_disp["comp_jpg_b64"]), dec(r_work["comp_jpg_b64"])
        vd, vw = dec(r_disp["overlay_jpg_b64"]), dec(r_work["overlay_jpg_b64"])
        if cd.shape != (dh, dw, 3) or vd.shape != (dh, dw, 3) or cw.shape != (ph, pw, 3):
            bad.append(f"{what}: the pictures changed their size ({cd.shape}, {vd.shape} / {cw.shape})")
            return cd
        back = cv2.erode((e_w._compute_effective_mask_small(e_w._active_session) == 255).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
        zone = back if zone_s is None else (back & zone_s)
        g_c, g_v = gap(reduced(cd), cw, zone), gap(reduced(vd), vw)
        worst = float(cv2.GaussianBlur(np.abs(reduced(cd).astype(np.float32) - cw.astype(np.float32)).mean(axis=2), (0, 0), 2.0)[zone].max())
        if not (g_c <= limit and worst <= 4.0 and g_v <= 2.0):
            bad.append(f"{what}: reduced to the working size, the cleaned picture is {g_c:.2f} levels from the working one inside "
                       f"the layer (largest patch {worst:.2f}), the mask view {g_v:.2f} (at most {limit}, 4.0 and 2.0)")
        return cd

    same_layer("on opening", r_d, r_w)
    # (e) the mask view of that size carries the same tints as the working one (the two ways of drawing it)
    s_w = e_w._active_session
    eff_w = e_w._compute_effective_mask_small(s_w)
    marked_w = e_w._compute_marked_mask_small(s_w, eff_w)
    for mk in (marked_w, None):
        m = eff_w.astype(np.float32)[:, :, None] / 255.0
        red_a = 0.36 * (1.0 - m)
        grn_a = ENG.OVERLAY_GREEN * m if mk is None else (
            ENG.OVERLAY_GREEN * (mk.astype(np.float32)[:, :, None] / 255.0)
            + ENG.OVERLAY_GREEN_PALE * np.maximum(m - mk.astype(np.float32)[:, :, None] / 255.0, 0.0))
        tints = c_w.astype(np.float32) * (1.0 - red_a) + np.float32([18.0, 18.0, 178.0]) * red_a
        tints = tints * (1.0 - grn_a) + np.float32([52.0, 255.0, 16.0]) * grn_a
        new_way = ENG._overlay_display(c_w, eff_w, mk).astype(np.float32)
        old_way = dec(ENG._encode_overlay_jpg(c_w, eff_w, quality=100, marked_u8=mk)).astype(np.float32)
        d_new, d_old = float(np.abs(new_way - tints).max()), float(np.abs(old_way - tints).mean())
        if d_new > 1.01 or d_old > 2.0:
            bad.append(f"the mask view: the tints of _overlay_display are {d_new:.2f} levels from the rule at most (allowed 1), "
                       f"the JPEG of _encode_overlay_jpg {d_old:.2f} on average (allowed 2)")

    # ---- 3. the eraser, the brush, a light refresh, the exact picture: the same on both, and the size stays
    def dark(pic, at, core=1.5):
        """How dark a mark at `at` (frame pixels) is against the backdrop around it (levels of 255), at the size of the picture."""
        sc = pic.shape[0] / float(h)
        cx_, cy_ = int(round(at[0] * sc)), int(round(at[1] * sc))
        far, near = max(6, int(round(24 * sc))), max(0, int(round(core * sc)))
        around = pic[cy_ - far:cy_ + far + 1, cx_ - far:cx_ + far + 1].astype(np.float32).mean(axis=2)
        return float(np.median(around) - around[far - near:far + near + 1, far - near:far + near + 1].min())

    specks = lambda pic: float(np.mean([dark(pic, at) for at in dust]))  # noqa: E731

    # The eraser is drawn along the row of specks, which the search removes. Where it erased, the specks must be
    # back - in the larger picture as dark as in the picture of the original.
    d_photo, d_clean = specks(o_d), specks(c_d)
    if not (d_photo >= 15.0 and d_clean <= 0.3 * d_photo):
        bad.append(f"test frame: the specks are {d_photo:.1f} levels dark in the picture of the original and {d_clean:.1f} in the cleaned one")
    line_e = [(0.66 + 0.01 * i, 0.70) for i in range(13)]
    rd, rw = stroke(e_d, r_d, line_e, 26, erase=True), stroke(e_w, r_w, line_e, 26, erase=True)
    c_e = same_layer("after the eraser", rd, rw)
    d_erased, d_work, d_work_photo = specks(c_e), specks(dec(rw["comp_jpg_b64"])), specks(o_w)
    if not (d_erased >= 0.75 * d_photo and d_work >= 0.5 * d_work_photo):
        bad.append(f"the eraser must bring the photo back at the full size of the picture: where it erased, the specks are {d_erased:.1f} "
                   f"levels dark ({d_photo:.1f} in the picture of the original; the working pictures: {d_work:.1f} of {d_work_photo:.1f})")

    # The brush: a mark that the search leaves alone is painted away - in the larger picture too.
    mark = (int(0.20 * w), int(0.30 * h))
    marked_img = img.copy()
    cv2.circle(marked_img, mark, 9, tuple(int(v) - 45 for v in marked_img[mark[1], mark[0]]), -1, lineType=cv2.LINE_AA)
    spot = lambda pic: dark(pic, mark, core=4.0)  # noqa: E731

    e_m, r_m = opened(marked_img, sil, spots=0, seamOn=False)       # (the search takes nothing; the backdrop is still evened)
    s_photo, s_before = spot(dec(r_m["orig_jpg_b64"])), spot(dec(r_m["comp_jpg_b64"]))
    r_p = stroke(e_m, r_m, [(mark[0] / float(w), mark[1] / float(h))], 14)
    s_after = spot(dec(r_p["comp_jpg_b64"]))
    if not (s_photo >= 25.0 and s_before >= 0.7 * s_photo):
        bad.append(f"test frame: the mark is {s_photo:.0f} levels dark in the picture of the original and {s_before:.0f} in the cleaned one before the brush")
    if not s_after <= 0.3 * s_photo:
        bad.append(f"a mark painted over with the brush is still in the larger picture: {s_photo:.0f} -> {s_after:.0f} levels")
    _quiet(e_m.close_session, r_m["session_id"])

    moved = dict(params, spots=40, seam=30)
    recompute = lambda eng, r, **k: _quiet(eng.recompute_session, r["session_id"], dict(moved), True, None, **k)  # noqa: E731
    same_layer("after a light refresh", recompute(e_d, r_d, quick=True), recompute(e_w, r_w, quick=True))
    rd, rw = recompute(e_d, r_d, background=True), recompute(e_w, r_w, background=True)
    if rd.get("exact") is not True or rw.get("exact") is not True:
        bad.append("the exact picture did not come")
    else:
        c_x = same_layer("the exact picture", rd, rw)
        alone_x, _ = zones(e_d)
        inside_x = alone_x & inside
        if not np.array_equal(c_x[inside_x], o_d[inside_x]) or not inside_x.mean() >= 0.03:
            bad.append("after the edits and the recomputes the inside of the person must still BE the picture of the original")

    # ---- 4. ironed clothing keeps the weave of the cloth
    gimg, core, g = _garment_frame()
    gh, gw = gimg.shape[:2]
    matte = cv2.resize(core, (1024, 1024), interpolation=cv2.INTER_AREA)
    e_g, r_g = opened(gimg, matte, dressSmooth=True, dressStrength=80)
    e_gw, r_gw = opened(gimg, matte, dressSmooth=True, dressStrength=80, previewLong=1080)
    o_g, c_g, c_gw = dec(r_g["orig_jpg_b64"]), dec(r_g["comp_jpg_b64"]), dec(r_gw["comp_jpg_b64"])
    if c_g.shape != (gh, gw, 3) or o_g.shape != (gh, gw, 3):
        bad.append(f"a {gw}x{gh} frame: the pictures must have the size of the frame itself, they have {c_g.shape}")
    else:
        cloth = cv2.erode(g["dress"].astype(np.uint8), np.ones((61, 61), np.uint8)) > 0
        cloth_s = cv2.resize(cloth.astype(np.uint8), (c_gw.shape[1], c_gw.shape[0]), interpolation=cv2.INTER_NEAREST) > 0
        o_gw = dec(r_gw["orig_jpg_b64"])
        near_fold = cv2.dilate((np.abs(g["fold"]) > 0.02).astype(np.uint8), np.ones((41, 41), np.uint8)) > 0

        def creases(pic):
            """How much of the drawn creases is in a picture (about 1 = as drawn, 0 = gone), measured at its own size."""
            size = (pic.shape[1], pic.shape[0])
            field = np.log1p(cv2.resize(g["wrinkles"], size, interpolation=cv2.INTER_AREA))
            zone = cv2.resize((cloth & ~near_fold).astype(np.uint8), size, interpolation=cv2.INTER_NEAREST) > 0
            clean = cv2.resize(np.ascontiguousarray(g["clean"][:, :, 1]), size, interpolation=cv2.INTER_AREA)
            resid = np.log(pic[:, :, 1].astype(np.float32) / 255.0 + 0.02) - np.log(clean / 255.0 + 0.02)
            sigma = 25.0 * size[0] / gw
            resid = resid - cv2.GaussianBlur(resid, (0, 0), sigma)
            field = field - cv2.GaussianBlur(field, (0, 0), sigma)
            return float((resid[zone] * field[zone]).sum() / (field[zone] * field[zone]).sum())

        left_d, left_w = creases(c_g) / creases(o_g), creases(c_gw) / creases(o_gw)   # what the ironing leaves of them
        kept = fine(c_g, cloth) / max(1e-6, fine(o_g, cloth))
        weave = lambda pic: (pic[:, :, 1].astype(np.float32) - cv2.GaussianBlur(pic[:, :, 1].astype(np.float32), (0, 0), 1.5))[cloth]  # noqa: E731
        # Is it the weave of the photo, thread for thread? (The two pictures are JPEGs of a weave two levels deep:
        # about 0.8 is what they can agree. An enlarged layer gives next to nothing, a wrong sign a negative number.)
        own = float(np.corrcoef(weave(c_g), weave(o_g))[0, 1])
        if not own >= 0.6:
            bad.append(f"ironed clothing: the fine detail of the cloth is not that of the photo (correlation {own:.2f}, at least 0.60)")
        if not left_w <= 0.85:
            bad.append(f"test frame: the ironing leaves {left_w:.0%} of the creases in the working picture")
        if not abs(left_d - left_w) <= 0.12:
            bad.append(f"ironed clothing: the window picture keeps {left_d:.0%} of the creases, the working picture {left_w:.0%} - the same ironing must show")
        if not kept >= 0.8:
            bad.append(f"ironed clothing lost the weave of the cloth: {kept:.0%} of the fine detail of the photo is left (at least 80 %)")
        r_off = _quiet(e_g.dress_preview_session, r_g["session_id"], False, 80.0)
        c_off = dec(r_off["comp_jpg_b64"])
        deep = cv2.erode(cloth.astype(np.uint8), np.ones((65, 65), np.uint8)) > 0
        if c_off.shape != c_g.shape or not np.array_equal(c_off[deep], o_g[deep]):
            bad.append("clothing switched off: the cloth must be the photo again, at the size of the other pictures")
        notes.append(f"ironed clothing keeps {kept:.0%} of the weave (the photo's own: correlation {own:.2f}) and shows the same ironing "
                     f"({left_d:.0%} of the creases left; working picture: {left_w:.0%})")

    # ---- 5. a small frame: the working pictures are the frame
    simg, ssil = H.make_studio_image(900, 600, n_dust=20, n_hair=2, seed=3)
    e_s, r_s = opened(simg, ssil)
    if dec(r_s["comp_jpg_b64"]).shape != (600, 900, 3) or dec(r_s["orig_jpg_b64"]).shape != (600, 900, 3) \
            or e_s._active_session.get("orig_disp_bgr") is not None:
        bad.append("a 900x600 frame must get pictures of 900x600")

    report("sharp", not bad,
           (f"a 3000x2000 frame: the window gets pictures of 2160x1440 and still works at 1080x720; inside the person the cleaned "
            f"picture is the photo of that size, pixel for pixel: fine detail {f_disp:.1f} levels (the photo: {f_photo:.1f}; the "
            f"working picture enlarged: {f_work:.1f}); the layer shows what it showed, also after the eraser, a light refresh and "
            f"the exact picture; the eraser brings the specks of the photo back ({d_clean:.1f} -> {d_erased:.1f} levels, the photo: "
            f"{d_photo:.1f}), the brush paints a mark away ({s_photo:.0f} -> {s_after:.0f} levels); "
            + "; ".join(notes) + "; a small frame gets its own size")
           if not bad else "wrong:\n  " + "\n  ".join(bad))


# ----------------------------------------------------------------------------------------------------------------------
# Steps back and forward for the mask edits of the big window
# ----------------------------------------------------------------------------------------------------------------------
def check_undo():
    bad = []
    w, h = 1500, 2000
    img, sil = H.make_studio_image(w, h, n_dust=60, n_hair=4, seed=77)
    params = dict(H.STD, speedMode="fast", smokeAuto=True)

    def opened():
        eng = H.make_engine(E, sil)
        return eng, _quiet(eng.start_session, img, 8, dict(params))

    def state(eng):
        s = eng._active_session
        return (s["user_paint_u8"].copy(), s["user_erase_u8"].copy(), bool(s.get("inverted", False)), s["clean_paint_small_bgr"].copy(),
                s["auto_mask_small_u8"].copy(), s["repair_mask_small_u8"].copy(), bool(s.get("mask_detached", False)))

    def same(a, b):
        return all(np.array_equal(x, y) if isinstance(x, np.ndarray) else x == y for x, y in zip(a, b))

    def edit(eng, sid, op, pts=None, erase=True, radius=24):
        return _quiet(eng.edit_session_mask, sid, op, pts, radius, erase, False, 45.0)

    def line(x0, y0, x1, y1):
        return [{"x": x0, "y": y0, "norm": 1}, {"x": x1, "y": y1, "norm": 1}]

    pics = ("comp_jpg_b64", "overlay_jpg_b64")
    eng, r0 = opened()
    sid = r0["session_id"]
    s0 = state(eng)

    # 1. nothing to take back on a fresh window
    r = edit(eng, sid, "undo")
    if r.get("stepped") is not False or r.get("history") != {"undo": 0, "redo": 0} or not same(state(eng), s0) or any(r[k] != r0[k] for k in pics):
        bad.append(f"a step back on a fresh window must change nothing: {r.get('stepped')}, {r.get('history')}")

    # 2. every kind of edit goes back to exactly what was there, and forward again to exactly what it made
    edits = [("eraser stroke", "stroke", line(0.15, 0.80, 0.35, 0.86), True),
             ("brush stroke", "stroke", line(0.70, 0.30, 0.85, 0.36), False),
             ("fill", "fill", None, True), ("clear", "clear", None, True), ("invert", "invert", None, True),
             ("stroke on an inverted mask", "stroke", line(0.20, 0.20, 0.30, 0.25), True)]
    trail = [(s0, r0)]
    for name, op, pts, erase in edits:
        r = edit(eng, sid, op, pts, erase)
        if r.get("history") != {"undo": len(trail), "redo": 0} or "stepped" in r:
            bad.append(f"{name}: history {r.get('history')} after {len(trail)} edits")
        if same(state(eng), trail[-1][0]):
            bad.append(f"the test is not what it should be: the {name} changed nothing")
        trail.append((state(eng), r))
    for i in range(len(edits) - 1, -1, -1):          # all the way back
        r = edit(eng, sid, "undo")
        if r.get("stepped") is not True or r.get("history") != {"undo": i, "redo": len(edits) - i}:
            bad.append(f"step back over the {edits[i][0]}: {r.get('stepped')}, {r.get('history')}")
        if not same(state(eng), trail[i][0]):
            bad.append(f"step back over the {edits[i][0]}: the mask or the preview is not what it was before that edit")
        elif any(r[k] != trail[i][1][k] for k in pics):
            bad.append(f"step back over the {edits[i][0]}: the pictures are not the ones shown before that edit")
    for i in range(1, len(edits) + 1):                # and forward again
        r = edit(eng, sid, "redo")
        if r.get("stepped") is not True or not same(state(eng), trail[i][0]) or any(r[k] != trail[i][1][k] for k in pics):
            bad.append(f"step forward over the {edits[i - 1][0]}: not what that edit had made")
    if edit(eng, sid, "redo").get("stepped") is not False:
        bad.append("a step forward with nothing taken back must say so")

    # 3. a new edit after a step back: what was taken back can no longer be made again
    eng, r0 = opened()
    sid = r0["session_id"]
    edit(eng, sid, "stroke", line(0.15, 0.80, 0.35, 0.86), True)
    edit(eng, sid, "undo")
    r = edit(eng, sid, "stroke", line(0.60, 0.80, 0.80, 0.86), True)
    if r.get("history") != {"undo": 1, "redo": 0} or edit(eng, sid, "redo").get("stepped") is not False:
        bad.append(f"a new edit after a step back must drop the steps forward: {r.get('history')}")
    # ...and the history is not endless
    for i in range(ENG.EDIT_HISTORY_MAX + 8):
        r = edit(eng, sid, "stroke", [{"x": 0.1 + 0.015 * i, "y": 0.5, "norm": 1}], True, 10)
    if r.get("history") != {"undo": ENG.EDIT_HISTORY_MAX, "redo": 0}:
        bad.append(f"{ENG.EDIT_HISTORY_MAX + 9} edits must leave {ENG.EDIT_HISTORY_MAX} steps: {r.get('history')}")

    # 4. the sliders were moved in between (light and full recompute): the edit is still taken back, and the window
    #    is then exactly the window of a session that never had that edit; Apply gives the same layer as well
    moved = dict(params, spots=92, edge=80)
    for quick in (True, False):
        eng, r0 = opened()
        sid = r0["session_id"]
        twin, t0 = opened()
        edit(eng, sid, "stroke", line(0.15, 0.80, 0.35, 0.86), True)       # erased by accident
        edit(eng, sid, "stroke", line(0.70, 0.30, 0.85, 0.36), False)      # painted by accident
        r_re = _quiet(eng.recompute_session, sid, dict(moved), True, None, quick)
        t_re = _quiet(twin.recompute_session, t0["session_id"], dict(moved), True, None, quick)
        if r_re.get("history") != {"undo": 2, "redo": 0} or t_re.get("history") != {"undo": 0, "redo": 0}:
            bad.append(f"{'light' if quick else 'full'} recompute: the steps must survive it: {r_re.get('history')}")
        if any(r_re[k] == t_re[k] for k in pics):
            bad.append("the test is not what it should be: the two strokes do not show after the recompute")
        edit(eng, sid, "undo")
        r = edit(eng, sid, "undo")
        if r.get("history") != {"undo": 0, "redo": 2} or not same(state(eng), state(twin)) or any(r[k] != t_re[k] for k in pics):
            bad.append(f"{'light' if quick else 'full'} recompute, then two steps back: the window differs from one that never had the strokes")
        a = _quiet(eng.apply_session, sid, 100.0, False, False, 45.0, None, dict(moved))
        b = _quiet(twin.apply_session, t0["session_id"], 100.0, False, False, 45.0, None, dict(moved))
        if not np.array_equal(a[0], b[0]):
            bad.append(f"{'light' if quick else 'full'} recompute, two steps back, Apply: the layer differs from the layer without the strokes")
    # a recompute that drops the edits on purpose drops their history too
    eng, r0 = opened()
    sid = r0["session_id"]
    edit(eng, sid, "stroke", line(0.15, 0.80, 0.35, 0.86), True)
    r = _quiet(eng.recompute_session, sid, dict(moved), False, None, True)
    if r.get("history") != {"undo": 0, "redo": 0} or edit(eng, sid, "undo").get("stepped") is not False:
        bad.append(f"a recompute without the edits must clear the steps: {r.get('history')}")

    # 5. a step forward, then Apply: the layer of the edit (the eraser leaves the zone alone)
    eng, r0 = opened()
    sid = r0["session_id"]
    twin, t0 = opened()
    for e, s in ((eng, sid), (twin, t0["session_id"])):
        edit(e, s, "stroke", line(0.15, 0.80, 0.35, 0.86), True)
    edit(eng, sid, "undo")
    edit(eng, sid, "redo")
    a = _quiet(eng.apply_session, sid, 100.0, False, False, 45.0)
    b = _quiet(twin.apply_session, t0["session_id"], 100.0, False, False, 45.0)
    if not np.array_equal(a[0], b[0]):
        bad.append("back and forward again, Apply: the layer differs from the layer of the edit itself")

    # 6. over HTTP, the way the plugin asks
    note = ""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from fastapi.testclient import TestClient
    except Exception:
        TestClient = None
        note = "; HTTP part SKIPPED (pip install httpx)"
    if TestClient is not None:
        srv = H.load_server()
        keep = srv.ENGINE, srv.ENGINE_ERROR
        real_out = sys.stdout
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
        try:
            srv.ENGINE, srv.ENGINE_ERROR = H.make_engine(E, sil), None
            with TestClient(srv.app) as client:
                meta = json.dumps({"width": w, "height": h, "channels": 3, "bitDepth": 8, "hasSelection": False, "jobId": "u", "params": params}).encode("utf-8")
                j0 = client.post("/session/start", content=struct.pack("<I", len(meta)) + meta + np.ascontiguousarray(img).tobytes()).json()
                post = lambda **body: client.post("/session/mask-edit", json=dict(body, session_id=j0["session_id"])).json()  # noqa: E731
                j1 = post(op="stroke", points=line(0.15, 0.80, 0.35, 0.86), radius_px=24, erase=True)
                j2 = post(op="undo")
                j3 = post(op="redo")
                j4 = post(op="undo")
                j5 = post(op="undo")
                if j1.get("history") != {"undo": 1, "redo": 0} or j2.get("stepped") is not True or j2.get("history") != {"undo": 0, "redo": 1} or j2["comp_jpg_b64"] != j0["comp_jpg_b64"]:
                    bad.append(f"HTTP: a stroke, then a step back: {j1.get('history')}, {j2.get('stepped')}, {j2.get('history')}")
                if j3.get("stepped") is not True or j3["comp_jpg_b64"] != j1["comp_jpg_b64"] or j4.get("stepped") is not True or j5.get("stepped") is not False:
                    bad.append(f"HTTP: forward, back, back: {j3.get('stepped')}, {j4.get('stepped')}, {j5.get('stepped')}")
                jr = client.post("/session/recompute", json=dict(session_id=j0["session_id"], params=dict(params, spots=85), preserve_edits=True, quick=True)).json()
                if jr.get("history") != {"undo": 0, "redo": 1}:
                    bad.append(f"HTTP: /session/recompute must report the steps: {jr.get('history')}")
        finally:
            sys.stdout.close()
            sys.stdout = real_out
            srv.ENGINE, srv.ENGINE_ERROR = keep
    report("undo", not bad, f"{len(edits)} kinds of mask edits go back and forward exactly; also after the sliders were moved (light and full recompute); "
                            f"Apply after a step back == Apply without the edit; {ENG.EDIT_HISTORY_MAX} steps are kept{note}"
           if not bad else "wrong:\n  " + "\n  ".join(bad))


def check_exact():
    """
    The exact picture comes by itself: recompute_session(background=True) - see engine.py.
    Nothing here depends on timing: a background run is either held at one of its progress points by the check
    (Gate) while the other requests are made, or told to give way at its k-th safe place.
    """
    # (the console of the engine is silenced once for the whole group: _quiet() swaps sys.stdout, and that cannot
    #  be done from two threads at a time)
    bad, n_places, tried = _quiet(_exact_cases)
    report("exact", not bad,
           f"a background recompute gives the frame of a full one ({n_places} safe places); it gave way at {tried} of them with the "
           "session untouched and the next run correct; strokes are answered and kept meanwhile, the clothing switch too; new "
           "values, a slider taken, Apply, closing and another photo stop it; Apply waits for the frame it needs (computed "
           "once); the user's own mask is never replaced"
           if not bad else "wrong:\n   " + "\n   ".join(bad))


def _exact_cases():
    import hashlib
    import threading

    bad = []
    w, h = 2600, 1740  # (the long side must reach PREVIEW_PROXY_MIN_DIM, or there is no quick preview to replace)
    img, sil = H.make_studio_image(w, h, n_dust=70, n_hair=6, seed=5, rgba=True)
    base = dict(H.STD, speedMode="quality", smokeAuto=True, autoFractions=False)
    moved = dict(base, spots=88, scuffs=80, blur=25)   # the sliders after the user moved them
    moved_again = dict(moved, scuffs=40)
    stroke_a = [{"x": 0.30, "y": 0.80, "norm": 1}, {"x": 0.36, "y": 0.83, "norm": 1}, {"x": 0.40, "y": 0.80, "norm": 1}]
    stroke_b = [{"x": 0.70, "y": 0.85, "norm": 1}, {"x": 0.76, "y": 0.86, "norm": 1}]

    def state(eng):
        """Everything of the session that a recompute or a mask edit can change, as one short text."""
        s = eng._active_session
        hsh = hashlib.sha1()
        for key in ("cleaned_base_rgba", "core_mask_u8", "clean_base_small_bgr", "clean_paint_small_bgr",
                    "auto_mask_small_u8", "repair_mask_small_u8", "user_paint_u8", "user_erase_u8"):
            hsh.update(np.ascontiguousarray(s[key]).tobytes())
        hsh.update(repr((bool(s["base_stale"]), bool(s["mask_detached"]), bool(s["inverted"]), bool(s["fill_all"]),
                         sorted(s["params"].items()), len(s["history"]["undo"]), len(s["history"]["redo"]))).encode())
        return hsh.hexdigest()

    def pictures(ans):
        return ans.get("comp_jpg_b64"), ans.get("overlay_jpg_b64")

    def opened():
        """A window with the quick preview for `moved` on screen: the real frame is still the one for `base`."""
        eng = H.make_engine(E, sil)
        first = eng.start_session(img, 8, dict(base))
        sid = first["session_id"]
        ans = eng.recompute_session(sid, dict(moved), True, None, True)
        if first.get("exact") is not True or not isinstance(first.get("rev"), int) or ans.get("quick") is not True \
                or ans.get("exact") is not False or ans.get("rev") != first.get("rev", 0) + 1:
            bad.append(f"opening must answer exact=True with a rev, a light refresh quick=True, exact=False and the next rev: "
                       f"{first.get('exact')}, {first.get('rev')} / {ans.get('quick')}, {ans.get('exact')}, {ans.get('rev')}")
        return eng, sid

    def recompute(eng, sid, params, quick=False, background=False, cb=None):
        return eng.recompute_session(sid, dict(params), True, cb, quick, background)

    def stroke(eng, sid, pts, erase, radius=24.0):
        return eng.edit_session_mask(sid, "stroke", pts, radius, erase, False, 45.0)

    def apply(eng, sid, params, cb=None, follow=False):
        return eng.apply_session(sid, 100.0, False, False, 45.0, cb, dict(params), follow)

    class Gate:
        """A progress callback that holds the run at its first progress point from `pct` on, until open()."""
        def __init__(self, pct=79):
            self.pct, self.reached, self.go, self.used = pct, threading.Event(), threading.Event(), False
            self.gave_up = False

        def __call__(self, pct, txt):
            if not self.used and pct >= self.pct:
                self.used = True
                self.reached.set()
                # (the check opens the gate within seconds. The limit matters only when the engine is broken and
                #  the request that should have been answered meanwhile waits for this very run.)
                if not self.go.wait(45):
                    self.gave_up = True

        def holding(self):
            """True while the run stands at the gate: what was answered before this turned False was answered
            'meanwhile'. (A request that had to wait until the gate gave up was not.)"""
            return self.reached.is_set() and not self.go.is_set() and not self.gave_up

        def open(self):
            self.go.set()

    def in_thread(fn):
        box = {}

        def run():
            try:
                box["ans"] = fn()
            except BaseException as exc:  # noqa: B036  (the check must see whatever came out)
                box["err"] = exc

        th = threading.Thread(target=run, daemon=True)
        th.start()
        return th, box

    def held_run(eng, sid, params=moved):
        """A background recompute, held in its middle: (gate, thread, box of its answer)."""
        gate = Gate()
        th, box = in_thread(lambda: recompute(eng, sid, params, background=True, cb=gate))
        if not gate.reached.wait(120):
            gate.open()
            th.join(120)
            raise RuntimeError(f"the background run did not reach its middle: {box}")
        return gate, th, box

    def wait_for_waiter(eng):
        for _ in range(1200):
            if eng._compute_waiters > 0:
                return True
            time.sleep(0.01)
        return False

    def idle(eng):
        return (not eng._compute_lock.locked() and not eng.lock.locked() and eng._active_jobs == 0 and eng._bg_runs == 0
                and eng._compute_waiters == 0 and getattr(eng._bg_local, "check", None) is None and eng._bg_follower is None)

    def gave_way(ans):
        return isinstance(ans, dict) and ans.get("superseded") is True and "comp_jpg_b64" not in ans

    # ---- 1. a background recompute gives exactly what a recompute the user waits for gives
    eng, sid = opened()
    light_state = state(eng)
    ref = recompute(eng, sid, moved)
    ref_state = state(eng)
    eng, sid = opened()
    if state(eng) != light_state:
        bad.append("two windows opened the same way differ (the check itself is not repeatable)")
    cold_cache = dict(eng._active_session["stage_cache"])
    plain_checkpoint = eng._checkpoint
    places = [0]

    def counting():
        if getattr(eng._bg_local, "check", None) is not None:
            places[0] += 1
        plain_checkpoint()

    eng._checkpoint = counting
    ans = recompute(eng, sid, moved, background=True)
    eng._checkpoint = plain_checkpoint
    n_places = places[0]
    if pictures(ans) != pictures(ref) or state(eng) != ref_state or ans.get("exact") is not True or ans.get("quick") is not False \
            or ans.get("rev") != ref.get("rev") or ans.get("superseded") or ans.get("skipped") or not idle(eng):
        bad.append("a background recompute must give the pictures, the session and the answer of a full recompute")
    if n_places < 20:
        bad.append(f"a background recompute passed only {n_places} safe places")

    # ---- 2. it gives way at every safe place and leaves nothing behind; the next run ends with the same frame
    eng, sid = opened()
    sess = eng._active_session
    plain_checkpoint = eng._checkpoint  # (of this engine: the one above belongs to the window before)
    tried, wrong_at, warm = 0, [], {}
    resume_at = {max(1, n_places // 4), max(1, n_places // 2), max(1, (3 * n_places) // 4)}
    for k in range(1, n_places + 1):
        if not FULL and 3 < k < n_places - 2 and k % 3 and k not in resume_at:
            continue
        tried += 1
        sess["stage_cache"] = dict(cold_cache)  # (as if no run had been here before: every place is met again)
        seen = [0]

        def waiter_at_k():
            if getattr(eng._bg_local, "check", None) is not None:
                seen[0] += 1
                if seen[0] == k:
                    eng._compute_waiters += 1  # from here on somebody is waiting for the frame
            plain_checkpoint()

        eng._checkpoint = waiter_at_k
        try:
            ans = recompute(eng, sid, moved, background=True)
        finally:
            eng._checkpoint = plain_checkpoint
            if seen[0] >= k:
                eng._compute_waiters -= 1
        if seen[0] < k or not gave_way(ans) or state(eng) != light_state or not idle(eng):
            wrong_at.append(k)
        if k in resume_at:
            warm[k] = dict(sess["stage_cache"])
    if wrong_at:
        bad.append(f"giving way at safe place(s) {wrong_at} of {n_places}: the answer must be 'superseded', the session untouched, the locks free")
    # (the cache now holds whatever the last run finished - nearly everything)
    ans = recompute(eng, sid, moved, background=True)
    if pictures(ans) != pictures(ref) or state(eng) != ref_state:
        bad.append("after giving way at the last safe place, the next background run must end with the frame of an undisturbed one")
    for k in sorted(warm):
        eng, sid = opened()
        eng._active_session["stage_cache"] = warm[k]  # what a run that gave way at place k left behind
        ans = recompute(eng, sid, moved, background=True)
        if pictures(ans) != pictures(ref) or state(eng) != ref_state:
            bad.append(f"after giving way at safe place {k}, the next background run must end with the frame of an undisturbed one")

    # ---- 3. the brush and the eraser are answered while the run computes, and stay in the result
    eng, sid = opened()
    stroke(eng, sid, stroke_a, False)
    stroke(eng, sid, stroke_b, True, 30.0)
    ref_drawn = recompute(eng, sid, moved)
    ref_drawn_state = state(eng)
    eng, sid = opened()
    gate, th, box = held_run(eng, sid)
    s1 = stroke(eng, sid, stroke_a, False)
    s2 = stroke(eng, sid, stroke_b, True, 30.0)
    answered_meanwhile = th.is_alive() and gate.holding()
    gate.open()
    th.join(120)
    ans = box.get("ans") or {}
    if not answered_meanwhile:
        bad.append("brush strokes must be answered while a background recompute is still computing")
    if s1.get("exact") is not False or s2.get("exact") is not False or not (s1.get("rev", 0) < s2.get("rev", 0) < ans.get("rev", 0)):
        bad.append(f"strokes during a background run: exact must stay False and the rev must grow: {s1.get('rev')}, {s2.get('rev')}, {ans.get('rev')}")
    if pictures(ans) != pictures(ref_drawn) or state(eng) != ref_drawn_state or ans.get("exact") is not True \
            or ans.get("history") != {"undo": 2, "redo": 0} or not idle(eng):
        bad.append("strokes made during a background run: the result must be that of 'the strokes, then a full recompute'")

    # ---- 3b. the clothing switch used while the run computes: the exact pictures are drawn with the clothing as
    #          the window asked for it last, not as it was when the run started
    eng, sid = opened()
    ref_dressed = recompute(eng, sid, dict(moved, dressSmooth=True, dressStrength=90))
    eng, sid = opened()
    gate, th, box = held_run(eng, sid)  # (it starts with the clothing switch off)
    worn = eng.dress_preview_session(sid, True, 90.0)
    worn_meanwhile = th.is_alive() and gate.holding()
    gate.open()
    th.join(120)
    ans = box.get("ans") or {}
    if not worn_meanwhile:
        bad.append("the clothing switch must be answered while a background recompute is still computing")
    if pictures(ref_dressed) == pictures(ref):
        bad.append("the clothing switch changes nothing on the frame of this check: the check is blind")
    elif pictures(ans) != pictures(ref_dressed) or not worn.get("comp_jpg_b64") or worn.get("exact") is not False or not idle(eng):
        bad.append("the clothing switch used during a background run: the exact pictures must show the clothing as the window asked last")
    # ...and a run that starts after the switch was used draws with what its own request says
    ans = recompute(eng, sid, dict(moved_again, dressSmooth=False), background=True)
    off_again = recompute(eng, sid, dict(moved_again, dressSmooth=False))
    if pictures(ans) != pictures(off_again):
        bad.append("a background run must draw the clothing as its own request says when nothing was said after it")

    # ---- 4. new slider values go first: the run gives way, the session is as if it had never started
    eng, sid = opened()
    ref_light2 = recompute(eng, sid, moved_again, quick=True)
    ref_light2_state = state(eng)
    eng, sid = opened()
    gate, th, box = held_run(eng, sid)
    th2, box2 = in_thread(lambda: recompute(eng, sid, moved_again, quick=True))
    waited = wait_for_waiter(eng)
    gate.open()
    th.join(120)
    th2.join(120)
    ans2 = box2.get("ans") or {}
    if not waited or not gave_way(box.get("ans")) or pictures(ans2) != pictures(ref_light2) or state(eng) != ref_light2_state \
            or ans2.get("exact") is not False or not idle(eng):
        bad.append("new slider values during a background run: the run must give way and the light refresh must come out as without it")
    # ...and so does an older background run for a newer one
    gate, th, box = held_run(eng, sid, moved_again)
    th2, box2 = in_thread(lambda: recompute(eng, sid, moved, background=True))
    waited = wait_for_waiter(eng)
    gate.open()
    th.join(120)
    th2.join(120)
    ans2 = box2.get("ans") or {}
    if not waited or not gave_way(box.get("ans")) or ans2.get("exact") is not True or pictures(ans2) != pictures(ref) or not idle(eng):
        bad.append("a newer background run must make the older one give way, and come out as an undisturbed one")

    # ---- 4b. the window says that a slider was taken (stop_background): the run stops although nobody waits for
    #          the frame yet; a run asked for afterwards is not affected
    eng, sid = opened()
    gate, th, box = held_run(eng, sid)
    told = eng.stop_background(sid)
    gate.open()
    th.join(120)
    if told != {"ok": True, "stopped": True} or not gave_way(box.get("ans")) or state(eng) != light_state or not idle(eng):
        bad.append(f"stop_background during a background run: the run must stop and leave the session untouched ({told})")
    if eng.stop_background(sid) != {"ok": True, "stopped": False} or eng.stop_background("another-window") != {"ok": True, "stopped": False}:
        bad.append("stop_background with no background run, or for another window, must answer stopped=False")
    ans = recompute(eng, sid, moved, background=True)
    if pictures(ans) != pictures(ref) or state(eng) != ref_state or not idle(eng):
        bad.append("a background run asked for after stop_background must run to its end")
    # ...and a run that still waits for its turn when the window says so does not start at all
    eng, sid = opened()
    runs = []
    plain_process = eng.process

    def counted_process(*a, **k):
        runs.append(1)
        return plain_process(*a, **k)

    eng.process = counted_process
    front = Gate()
    th, box = in_thread(lambda: recompute(eng, sid, moved, cb=front))            # a recompute the user waits for...
    front.reached.wait(120)
    th2, box2 = in_thread(lambda: recompute(eng, sid, moved, background=True))   # ...and a background one behind it
    for _ in range(1200):
        if eng._bg_runs == 1 and eng._compute_waiters == 1:
            break
        time.sleep(0.01)
    told = eng.stop_background(sid)
    front.open()
    th.join(120)
    th2.join(120)
    eng.process = plain_process
    if told != {"ok": True, "stopped": True} or not gave_way(box2.get("ans")) or len(runs) != 1 or state(eng) != ref_state or not idle(eng):
        bad.append(f"stop_background for a run that still waits for its turn: it must not start (frames computed: {len(runs)}, {told})")

    # ---- 5. Apply: waits for a run that computes the very frame it needs; stops it otherwise. The layer is the same.
    eng, sid = opened()
    ref_layer = apply(eng, sid, moved)[0]
    for follow in (True, False):
        eng, sid = opened()
        runs = []
        plain_process = eng.process

        def counted(*a, **k):
            runs.append(1)
            return plain_process(*a, **k)

        eng.process = counted
        shown = []
        gate, th, box = held_run(eng, sid)
        th2, box2 = in_thread(lambda: apply(eng, sid, moved, cb=lambda pct, txt: shown.append(pct), follow=follow))
        if follow:
            for _ in range(1200):
                if eng._bg_follower is not None:
                    break
                time.sleep(0.01)
        else:
            wait_for_waiter(eng)
        gate.open()
        th.join(120)
        th2.join(240)
        eng.process = plain_process
        out = box2.get("ans")
        ans = box.get("ans") or {}
        if out is None or not np.array_equal(out[0], ref_layer) or not idle(eng):
            bad.append(f"Apply during a background run (follow={follow}): the layer must be the one of a plain Apply: {box2.get('err')}")
        elif follow and (ans.get("exact") is not True or len(runs) != 1 or out[2].get("recomputed") is not False
                         or any(b < a for a, b in zip(shown, shown[1:])) or not shown or shown[0] >= 60):
            bad.append(f"Apply that follows a background run: the frame must be computed once (was {len(runs)}), by that run, "
                       f"and the progress must go on from its numbers without going back: {shown[:3]}..{shown[-3:]}")
        elif not follow and (not gave_way(ans) or out[2].get("recomputed") is not True):
            bad.append("Apply without 'follow' must stop the background run and compute the frame itself")

    # ---- 6. a mask that is the user's own drawing is never replaced by itself
    eng, sid = opened()
    eng.edit_session_mask(sid, "invert")
    stroke(eng, sid, stroke_a, False)
    drawn = state(eng)
    computed = []
    plain_process = eng.process
    eng.process = lambda *a, **k: (computed.append(1), plain_process(*a, **k))[1]
    ans = recompute(eng, sid, moved, background=True)
    eng.process = plain_process
    # ("nothing" includes the frame: a run that computes it first and declines afterwards costs seconds each time)
    if ans.get("skipped") is not True or "comp_jpg_b64" in ans or ans.get("exact") is not False or state(eng) != drawn \
            or not idle(eng) or computed:
        bad.append(f"with the user's own mask on screen a background recompute for the same settings must do nothing "
                   f"(frames computed: {len(computed)})")
    layer_drawn = apply(eng, sid, moved)[0]  # (Apply computes the real frame then, and keeps the mask - as before)
    if eng._active_session["mask_detached"] is not True or eng._active_session["base_stale"] is not False:
        bad.append("Apply with the user's own mask must compute the real frame and keep that mask")
    eng, sid = opened()
    gate, th, box = held_run(eng, sid)
    eng.edit_session_mask(sid, "invert")
    stroke(eng, sid, stroke_a, False)
    drawn_meanwhile = th.is_alive() and gate.holding()
    gate.open()
    th.join(120)
    ans = box.get("ans") or {}
    if not drawn_meanwhile:
        bad.append("the inversion and a stroke must be answered while a background recompute is still computing")
    if ans.get("skipped") is not True or state(eng) != drawn or not idle(eng):
        bad.append("a mask drawn by hand while a background recompute was computing must not be replaced by its result")
    elif not np.array_equal(apply(eng, sid, moved)[0], layer_drawn):
        bad.append("Apply after such a skipped run must give the layer of a plain Apply")
    ans = recompute(eng, sid, moved_again, background=True)  # new values are the user's own doing: as any recompute
    if ans.get("skipped") or ans.get("exact") is not True or eng._active_session["mask_detached"] is not False:
        bad.append("a background recompute for NEW slider values must work as any recompute (also with the user's own mask)")

    # ---- 7. closing the window stops the run; opening another photo does too
    eng, sid = opened()
    gate, th, box = held_run(eng, sid)
    eng.close_session(sid)
    gate.open()
    th.join(120)
    if not gave_way(box.get("ans")) or not idle(eng):
        bad.append("closing the window must stop a background recompute")
    eng, sid = opened()
    gate, th, box = held_run(eng, sid)
    th2, box2 = in_thread(lambda: eng.start_session(img, 8, dict(base)))
    waited = wait_for_waiter(eng)
    gate.open()
    th.join(120)
    th2.join(240)
    if not waited or not gave_way(box.get("ans")) or not (box2.get("ans") or {}).get("session_id") or not idle(eng):
        bad.append("opening another photo must stop a background recompute of the former window")

    # ---- 8. no quick way (2 passes): the background run is the only refresh, and it is a full recompute
    eng, sid = opened()
    twice = dict(moved, cleanPasses=2)
    ref2 = recompute(eng, sid, twice)
    ref2_state = state(eng)
    eng, sid = opened()
    ans = recompute(eng, sid, twice, background=True)
    if pictures(ans) != pictures(ref2) or state(eng) != ref2_state or ans.get("exact") is not True or ans.get("quick") is not False:
        bad.append("2 passes: a background recompute must give the pictures and the session of a full recompute")

    return bad, n_places, tried


# ----------------------------------------------------------------------------------------------------------------------
# 4.9.0: the tone stages reach the person, the thin line of the corner, single hairs
# ----------------------------------------------------------------------------------------------------------------------
def _person_core(matte):
    """
    The person of a synthetic frame for "is not touched": every pixel the network is sure of (matte above 0.9).
    Since 4.9.0 the tone of the backdrop is shifted right up to the person, and along the soft edge of the matte
    the photo decides where that is - but never where the network is sure (TONE_GATE_SURE).
    """
    return matte > 0.9


def check_edge():
    """
    "toneEdge". The corner and the stains change the tone of the backdrop - and stopped at the margin of the
    protection, so a strip around the person kept the old tone: a rim along the hem and around the shoes that no
    position of the protection slider removed (it only made the strip wider or narrower). A change of tone is no
    repair: it now goes right up to the person, whose outline is taken from the network and from the photo itself.
    """
    bad, notes = [], []
    off = dict(H.STD, spots=0, scuffs=0, seamOn=False, blur=0, smokeOn=False)
    gray = lambda a: a[..., :3].astype(np.float32).mean(axis=2)  # noqa: E731
    w, h = 1500, 2000
    img, sil = H.make_studio_image(w, h, n_dust=0, n_hair=0, seed=3)
    matte = cv2.resize(sil, (w, h))
    dist = cv2.distanceTransform((matte <= 0.5).astype(np.uint8), cv2.DIST_L2, 5)
    inside = _person_core(matte)
    # the corner of this frame is at 0.62 of the height: the floor right under it gets darker, the wall above lighter
    under = np.zeros((h, w), bool)
    under[int(h * 0.625):int(h * 0.645)] = True
    over = np.zeros((h, w), bool)
    over[int(h * 0.595):int(h * 0.615)] = True
    eng = H.make_engine(E, sil)
    for mode in ("fast", "quality"):
        for edge in (70, 90):
            share = {}
            for on in (True, False):
                comp = _comp(img, _quiet(eng.process, img, 8, dict(off, speedMode=mode, cycCurve=65, edge=edge, toneEdge=on))[0])
                d = gray(comp) - gray(img)
                # how much of the shift of the open backdrop (90..130 px away) arrives 2..4 px from the person
                share[on] = [float(d[rows & (dist >= 2) & (dist < 4)].mean() / d[rows & (dist >= 90) & (dist < 130)].mean()) for rows in (under, over)]
                if float(np.abs(comp - img.astype(np.float32))[inside].max()) > 0.0:
                    bad.append(f"corner, {mode}, protection {edge}, toneEdge {on}: the person was changed by {np.abs(comp - img.astype(np.float32))[inside].max():.2f} levels")
            if min(share[True]) < 0.85 or max(share[True]) > 1.15:
                bad.append(f"corner, {mode}, protection {edge}: next to the person the backdrop moves {share[True]} of what it moves in the open (under, over the corner)")
            if max(share[False]) > 0.50:
                bad.append(f"corner, {mode}, protection {edge}: the measurement does not see the strip the former way leaves ({share[False]})")
            if mode == "fast" and edge == 70:
                notes.append(f"corner: next to the person the floor moves {100 * share[True][0]:.0f}% of what it moves in the open (the former way: {100 * share[False][0]:.0f}%)")

    # Stains: what is left of them right at the person. (The stage itself judges by less backdrop there, so it is
    # weaker than in the open; the strip of the protection no longer adds to that.)
    stained, clean, sil_s, g = _stained_frame(w, h)
    person = g["person"]
    dist_s = cv2.distanceTransform((~person).astype(np.uint8), cv2.DIST_L2, 5)
    S = cv2.GaussianBlur(g["stains"], (0, 0), 2.0)
    strip = (dist_s >= 2) & (dist_s < 5) & (np.abs(S) > 1.2)
    eng_s = H.make_engine(E, sil_s)
    left = {}
    for on in (True, False):
        comp = _comp(stained, _quiet(eng_s.process, stained, 8, dict(off, scuffs=65, speedMode="fast", toneEdge=on))[0])
        R = cv2.GaussianBlur(gray(comp) - gray(clean), (0, 0), 2.0)
        left[on] = float((R[strip] * S[strip]).sum() / float((S[strip] ** 2).sum()))
        core = cv2.erode(person.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
        if float(np.abs(comp - stained.astype(np.float32))[core].max()) > 0.0:
            bad.append(f"stains, toneEdge {on}: the person was changed")
    if left[True] > 0.76 or left[True] > left[False] - 0.06:
        bad.append(f"stains 2..5 px from the person: {left[True]:.2f} of them left (the former way: {left[False]:.2f})")
    notes.append(f"stains right at the person: {100 * left[True]:.0f}% left (the former way: {100 * left[False]:.0f}%)")

    # The repair under the protected band stays what it was: with no tone stage the result is the one of the
    # former way wherever the protection is whole or absent (in between, the repair fades once instead of twice).
    img_d, sil_d = H.make_studio_image(w, h, seed=5)
    eng_d = H.make_engine(E, sil_d)
    p_d = dict(H.STD, scuffs=0, blur=0, cycCurve=0, smokeOn=False, speedMode="fast")
    c_on = _comp(img_d, _quiet(eng_d.process, img_d, 8, dict(p_d, toneEdge=True))[0])
    c_off = _comp(img_d, _quiet(eng_d.process, img_d, 8, dict(p_d, toneEdge=False))[0])
    matte_d = cv2.resize(sil_d, (w, h))
    dist_d = cv2.distanceTransform((matte_d <= 0.5).astype(np.uint8), cv2.DIST_L2, 5)
    apart = dist_d > 0.02 * h
    core_d = _person_core(matte_d)
    if float(np.abs(c_on - c_off)[apart].max()) > 0.0 or float(np.abs(c_on - img_d.astype(np.float32))[core_d].max()) > 0.0:
        bad.append(f"repair without tone stages: away from the person the result differs from the former way by {np.abs(c_on - c_off)[apart].max():.2f} levels, "
                   f"the person by {np.abs(c_on - img_d.astype(np.float32))[core_d].max():.2f}")
    if float(np.abs(c_off - img_d.astype(np.float32)).max()) < 5.0:
        bad.append("repair without tone stages: nothing was repaired in the frame of this check")

    # ...and with a tone stage on, a repair still ends where the protection begins. The seam of this frame runs
    # into the legs: it is repaired up to the protected band and stays inside it, as it always did - although the
    # layer now covers the band (the tone is shifted there), nothing of the repair may show through it.
    seam_row = int(h * 0.80)
    row_dist = dist[seam_row]

    def seam_depth(pic, lo, hi):
        cols = np.flatnonzero((row_dist >= lo) & (row_dist < hi))
        g_ = gray(pic)
        around = np.concatenate([g_[seam_row - 16:seam_row - 11][:, cols], g_[seam_row + 12:seam_row + 17][:, cols]]).mean()
        return float(around - g_[seam_row - 1:seam_row + 2][:, cols].mean())

    d0 = seam_depth(img, 2, 5)
    for mode in ("fast", "quality"):
        kept = {}
        for on in (True, False):
            comp = _comp(img, _quiet(eng.process, img, 8, dict(H.STD, spots=0, blur=0, cycCurve=0, smokeOn=False, scuffs=65, speedMode=mode, toneEdge=on))[0])
            kept[on] = (seam_depth(comp, 2, 5) / d0, seam_depth(comp, 14, 22) / d0, seam_depth(comp, 60, 140) / d0)
        if kept[True][0] < 0.65 or abs(kept[True][0] - kept[False][0]) > 0.08 or max(abs(v) for v in kept[True][1:]) > 0.15:
            bad.append(f"seam next to the legs, {mode}: {kept[True]} of its depth is left at 2-5 / 14-22 / 60-140 px from the person (the former way: {kept[False]})")
        if mode == "fast":
            notes.append(f"a seam that runs into the legs is repaired up to the protection and stays inside it ({100 * kept[True][0]:.0f}% of its depth right at the leg, "
                         f"{100 * abs(kept[True][1]):.0f}% from 14 px on)")
    report("edge", not bad, "the tone stages reach the person: " + "; ".join(notes) + "; the person is not touched; the repair away from the person is as before"
           if not bad else "wrong:\n  " + "\n  ".join(bad))


def _hairline_frame(w=1500, h=2000, at=0.77, slope=0.012, depth=2.2, lit=30.0, level=24.0, seed=21, noise=1.1, line=True, off=0.0):
    """
    A dark floor with the joint of two vinyl sheets across the frame, as on the owner's frame 3417: above the joint
    the floor is lit, below it is not, and along the joint runs a thin dark line - `depth` levels deep, two pixels
    wide, a little tilted. There is no wall-floor corner sharp enough to be found: the joint is what the corner tool
    takes for the corner. line=False: the same frame without the thin line. off: the thin line runs so many pixels
    below the middle of the step of light.
    Returns (frame, silhouette, the row of the thin line for every column).
    """
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    rows = at * h + slope * (xx[0] - w / 2.0)
    t = 1.0 / (1.0 + np.exp(-np.clip((yy - rows[None, :]) / (0.004 * h), -40, 40)))
    lum = level + lit * (1.0 - t) * (0.55 + 0.45 * np.exp(-((xx / w - 0.62) / 0.45) ** 2))
    lum = lum * (1.0 - 0.10 * ((xx / w - 0.5) * 2) ** 2)
    rows = rows + off
    if line:
        lum -= depth * np.exp(-0.5 * ((yy - rows[None, :]) / 0.9) ** 2)
    _, sil = H.make_studio_image(w, h, n_dust=0, n_hair=0, seed=1)
    person = cv2.resize(sil, (w, h)) > 0.5
    img = lum[..., None] * np.float32([1.03, 1.0, 0.95]) + rng.standard_normal((h, w, 3)).astype(np.float32) * noise
    img[person] = np.float32([12, 12, 14]) + rng.standard_normal((int(person.sum()), 3)).astype(np.float32) * 0.5
    return np.clip(img + 0.5, 0, 255).astype(np.uint8), sil, rows


def _line_dip(pic, rows, cols, off=(5, 9)):
    """How much darker the rows of a thin line are than the rows 5..9 px above and below it (levels; columns averaged)."""
    g = pic[..., :3].astype(np.float32).mean(axis=2)
    xs = np.arange(cols.start, cols.stop)
    r0 = np.round(rows[xs]).astype(int)
    at = np.mean([g[r0 + k, xs] for k in (-1, 0, 1)], axis=0)
    around = np.mean([g[r0 + s * k, xs] for k in range(off[0], off[1] + 1) for s in (-1, 1)], axis=0)
    return float((around - at).mean())


def _step_over(pic, rows, cols, gap=30, tall=20):
    """Mean brightness `gap` px above a line minus `gap` px below it (levels; columns averaged)."""
    g = pic[..., :3].astype(np.float32).mean(axis=2)
    xs = np.arange(cols.start, cols.stop)
    r0 = np.round(rows[xs]).astype(int)
    return float((np.mean([g[r0 - gap - k, xs] for k in range(tall)], axis=0) - np.mean([g[r0 + gap + k, xs] for k in range(tall)], axis=0)).mean())


def _pool_frame(w=1500, h=2000, at=0.77, slope=0.012, lit=34.0, level=22.0, reach=0.04, seed=23, noise=1.1):
    """
    The joint of _hairline_frame (no thin line), with two things of the owner's frame 3417 added: the train of the
    dress lies on the floor to the right of the legs and hides the floor below the joint there, and next to the
    person the pool of light reaches below the joint (by `reach` of the height at the hem, fading out to the right).
    Returns (frame, silhouette 1024, row of the joint per column, silhouette of the frame size).
    """
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    rows = at * h + slope * (xx[0] - w / 2.0)
    cx = w // 2
    ext = reach * h * np.exp(-((xx[0] - (cx + 0.055 * w)) / (0.11 * w)) ** 2)        # how far the light goes below the joint
    edge = rows + ext
    soft = 0.004 * h + 0.35 * ext                                                   # the further, the softer its lower edge
    t = 1.0 / (1.0 + np.exp(-np.clip((yy - edge[None, :]) / soft[None, :], -40, 40)))
    lum = level + lit * (1.0 - t) * (0.55 + 0.45 * np.exp(-((xx / w - 0.62) / 0.45) ** 2))
    lum = lum * (1.0 - 0.10 * ((xx / w - 0.5) * 2) ** 2)
    _, sil = H.make_studio_image(w, h, n_dust=0, n_hair=0, seed=1)
    person = (cv2.resize(sil, (w, h)) > 0.5).astype(np.uint8)
    train = np.array([[cx + int(0.03 * w), int((at + 0.045) * h)], [cx + int(0.33 * w), int((at + 0.060) * h)],
                      [cx + int(0.36 * w), int(0.93 * h)], [cx + int(0.03 * w), int(0.93 * h)]], np.int32)
    cv2.fillPoly(person, [train], 1)
    img = lum[..., None] * np.float32([1.03, 1.0, 0.95]) + rng.standard_normal((h, w, 3)).astype(np.float32) * noise
    img[person > 0] = np.float32([12, 12, 14]) + rng.standard_normal((int(person.sum()), 3)).astype(np.float32) * 0.5
    return (np.clip(img + 0.5, 0, 255).astype(np.uint8), cv2.resize(person * 255, (1024, 1024), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0,
            rows, person)


def check_line():
    """
    "cornerHair". A joint of the vinyl that the corner tool takes for the corner: the tool turns the step into a
    slope - and left the thin dark line of the joint lying on that slope (about a third of its depth), while the
    seam tool leaves the corner to the corner tool. The corner tool now takes the thin line as well.
    """
    bad, notes = [], []
    w, h = 1500, 2000
    frame, sil, rows = _hairline_frame(w, h)
    sides = (slice(int(w * 0.05), int(w * 0.30)), slice(int(w * 0.70), int(w * 0.95)))
    dip0 = [_line_dip(frame, rows, c) for c in sides]
    step0 = [_step_over(frame, rows, c) for c in sides]
    if min(dip0) < 1.0 or min(step0) < 15.0:
        bad.append(f"the frame of this check has no line to remove: dip {dip0}, step {step0}")
    eng = H.make_engine(E, sil)
    p = dict(H.STD, spots=0, scuffs=0, blur=0, smokeOn=False, cycCurve=65)
    core = _person_core(cv2.resize(sil, (w, h)))
    for mode in ("fast", "quality"):
        for seam in (False, True):
            got = {}
            for on in (True, False):
                out, st = _quiet(eng.process, frame, 8, dict(p, speedMode=mode, seamOn=seam, seam=90, cornerHair=on))
                comp = _comp(frame, out)
                got[on] = ([_line_dip(comp, rows, c) for c in sides], [_step_over(comp, rows, c) for c in sides], st)
                if float(np.abs(comp - frame.astype(np.float32))[core].max()) > 0.0:
                    bad.append(f"{mode}, seam {seam}, cornerHair {on}: the person was changed")
            dip, step, st = got[True]
            tag = f"{mode}, seam tool {'on' if seam else 'off'}"
            if st.get("corner_row") is None or abs(st["corner_row"] - 0.77) > 0.012 or not st.get("corner_hair"):
                bad.append(f"{tag}: the joint at 0.77 was not taken with its thin line (corner_row {st.get('corner_row')}, corner_hair {st.get('corner_hair')})")
            if st.get("seam_px"):
                bad.append(f"{tag}: the seam tool marked {st.get('seam_px')} px of the line the corner tool takes (one line, one tool)")
            if max(abs(a) / b for a, b in zip(dip, dip0)) > 0.15:
                bad.append(f"{tag}: the thin line went {dip0} -> {dip} levels - still there")
            if max(a / b for a, b in zip(step, step0)) > 0.45:
                bad.append(f"{tag}: the step of the joint went {step0} -> {step} levels - not evened")
            if min(a / b for a, b in zip(got[False][0], dip0)) < 0.22 or got[False][2].get("corner_hair"):
                bad.append(f"{tag}: the measurement does not see the line the former way leaves ({got[False][0]}, corner_hair {got[False][2].get('corner_hair')})")
            if mode == "fast" and not seam:
                notes.append(f"thin line of a joint taken for the corner: {max(dip0):.1f} -> {max(abs(v) for v in dip):.2f} levels (the former way: {max(got[False][0]):.2f}), "
                             f"its step {max(step0):.0f} -> {max(step):.0f}")
    # The thin line need not lie in the middle of the step. Here it runs 38 px below it: outside the strip that the
    # seam search always leaves to the corner tool, inside the zone in which the corner tool looks for its line.
    # One line, one tool: the corner tool takes it, and the seam tool - switched on - marks nothing of it.
    beside, sil_s, rows_s = _hairline_frame(w, h, off=38.0)
    out, st = _quiet(H.make_engine(E, sil_s).process, beside, 8, dict(p, speedMode="fast", seamOn=True, seam=90))
    dip_s0 = [_line_dip(beside, rows_s, c) for c in sides]
    dip_s = [_line_dip(_comp(beside, out), rows_s, c) for c in sides]
    if not min(dip_s0) >= 1.0:
        bad.append(f"the frame with the line beside the step has no line to remove: dip {dip_s0}")
    elif not st.get("corner_hair") or st.get("seam_px") or not max(abs(a) / b for a, b in zip(dip_s, dip_s0)) <= 0.15:
        bad.append(f"a thin line 38 px beside the middle of the step, seam tool on: corner_hair {st.get('corner_hair')}, the seam tool marked {st.get('seam_px')} px "
                   f"(one line, one tool), the line went {dip_s0} -> {dip_s} levels")
    # the same frame without the thin line: nothing is found, nothing is taken out
    plain, sil_p, rows_p = _hairline_frame(w, h, line=False)
    eng_p = H.make_engine(E, sil_p)
    out, st = _quiet(eng_p.process, plain, 8, dict(p, speedMode="fast", seamOn=False))
    comp = _comp(plain, out)
    if st.get("corner_hair") or max(abs(_line_dip(comp, rows_p, c)) for c in sides) > 0.12:
        bad.append(f"a joint without a thin line: corner_hair {st.get('corner_hair')}, dip after {[_line_dip(comp, rows_p, c) for c in sides]}")
    # a real wall-floor corner has no thin line either, and the usual frame is cleaned as before
    img, sil_c = H.make_studio_image(w, h, n_dust=0, n_hair=0, seed=3)
    eng_c = H.make_engine(E, sil_c)
    off = dict(H.STD, spots=0, scuffs=0, seamOn=False, blur=0, smokeOn=False, cycCurve=65, speedMode="fast")
    o1, s1 = _quiet(eng_c.process, img, 8, dict(off))
    o0, s0 = _quiet(eng_c.process, img, 8, dict(off, cornerHair=False))
    far = cv2.distanceTransform((cv2.resize(sil_c, (w, h)) <= 0.5).astype(np.uint8), cv2.DIST_L2, 5) > 0.03 * h
    if s1.get("corner_hair") or float(np.abs(_comp(img, o1) - _comp(img, o0))[far].max()) > 0.0:
        bad.append(f"a plain wall-floor corner: corner_hair {s1.get('corner_hair')}, the result away from the person differs from the former way by "
                   f"{np.abs(_comp(img, o1) - _comp(img, o0))[far].max():.2f} levels")
    # The pool of light that reaches below the joint next to the hem, where the train hides the floor further down.
    # The corner tool lifted that strip as if it were as dark as the floor in the open: a lighter streak along the
    # joint, right at the dress. A piece of backdrop in plain view is no longer left lighter than its own slope.
    pool, sil_o, rows_o, person_o = _pool_frame(w, h)
    eng_o = H.make_engine(E, sil_o)
    g_ = lambda a: a[..., :3].astype(np.float32).mean(axis=2)  # noqa: E731
    cols_o = np.arange(int(w * 0.567), int(w * 0.627))      # next to the hem, over the train
    r_o = np.round(rows_o[cols_o]).astype(int)
    streak = {}
    for on in (True, False):
        out, st = _quiet(eng_o.process, pool, 8, dict(p, speedMode="fast", seamOn=False, cornerHair=on))
        c = g_(_comp(pool, out))
        above = np.mean([c[r_o - k, cols_o] for k in range(20, 50)])
        below = np.mean([c[r_o + k, cols_o] for k in range(15, 60)])
        streak[on] = float(below - above)
        if on and (st.get("corner_row") is None or abs(st["corner_row"] - 0.77) > 0.012):
            bad.append(f"pool of light next to the hem: the joint was looked for at {st.get('corner_row')}")
        if float(np.abs(_comp(pool, out) - pool.astype(np.float32))[cv2.erode(person_o, np.ones((7, 7), np.uint8)) > 0].max()) > 0.0:
            bad.append(f"pool of light next to the hem, cornerHair {on}: the person was changed")
    if streak[True] > 3.0:
        bad.append(f"pool of light next to the hem: below the joint the floor is left {streak[True]:.1f} levels lighter than above it")
    if streak[False] < 8.0:
        bad.append(f"pool of light next to the hem: the measurement does not see the streak the former way leaves ({streak[False]:.1f} levels)")
    notes.append(f"a pool of light that reaches below the joint at the hem: the strip under the joint is {streak[True]:+.1f} levels against the floor above it (the former way: {streak[False]:+.1f})")
    report("line", not bad, "; ".join(notes) + "; with the seam tool on and off, both fills; a line that runs beside the middle of the step is taken by the corner tool "
           "alone; a joint or a corner without such a line: nothing is taken out"
           if not bad else "wrong:\n  " + "\n  ".join(bad))


def _hair_frame(w=1500, h=2000, zoom=1.0, wall=150.0, hair=26.0, skin=188.0, line=62.0, thick=2, seed=9, noise=1.2, spot=0.0, skip=(),
                top="hair"):
    """
    A head in profile against a plain wall, with thin things that stick out of it:
      "out"    three single hairs that grow out of the hairdo and lead away from it (two of them curved);
      "up"     one more on top of the head, dead straight and exactly vertical (next to such a line the line search
               finds faint side lines, which point across it);
      "short"  one more such hair, a tenth of the head long;
      "fringe" short hairs that lie along the outline of the hairdo - its soft edge;
      "along"  a hair that leaves the hairdo and then runs along its outline;
      "lash"   a short dark line on the lit face (an eyelash in profile);
      "face"   a long line of the same kind that grows out of the lit face;
      "apart"  such a line that touches nobody;
      "tuft"   a wisp: six faint hairs that cross each other;
      "low"    a thread that sticks out of the clothes, three head widths below the top of the head;
      "cable"  such a line that starts at the hairdo and goes on to the border of the frame;
      "long"   with top="pole", in the place of "up": a straight line a head width long, two degrees off the
               vertical - it leaves the searched zone, and in a close-up it reaches the top of the frame (a pole,
               a strap behind the head).
    zoom: the size of the head (1 = about 300 px wide in a frame 1500 px wide). spot: a spot of light on the wall
    behind the head, so many levels at its middle. skip: the names that are not drawn (the same frame without them).
    Returns (frame, silhouette for the stand-in matting network, {name: the pixels drawn}, silhouette of the frame size).
    """
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    s = w / 1500.0 * zoom
    rx, ry = int(150 * s), int(190 * s)
    cx, cy = int(w * 0.50), int(max(h * 0.30, ry + 110 * s + 0.03 * h))
    lum = wall * (1.0 - 0.10 * ((xx / w - 0.5) * 2) ** 2 - 0.06 * ((yy / h - 0.4) * 2) ** 2)
    if spot:
        lum = lum + spot * np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (1.25 * ry) ** 2))
    img = np.repeat(lum[..., None], 3, axis=2) * np.float32([1.02, 1.0, 0.97])
    sil = np.zeros((h, w), np.uint8)
    cv2.ellipse(sil, (cx, cy), (rx, ry), 0, 0, 360, 255, -1)
    body = np.array([[cx - int(120 * s), cy + int(150 * s)], [cx + int(120 * s), cy + int(150 * s)],
                     [cx + int(330 * s), h + int(400 * s)], [cx - int(330 * s), h + int(400 * s)]], np.int32)
    cv2.fillPoly(sil, [body], 255)
    person = np.empty((h, w, 3), np.float32)
    person[:] = hair
    face = np.zeros((h, w), np.uint8)   # the lit face: the front part of the head
    cv2.ellipse(face, (cx, cy), (rx, ry), 0, 0, 360, 255, -1)
    face[:, cx - int(60 * s):] = 0
    face[: cy - int(70 * s)] = 0
    person[face > 0] = (skin, skin * 0.84, skin * 0.74)
    person[min(h, cy + int(240 * s)):] = (40, 40, 46)
    marks = {}

    def draw(name, pts, width=None, tone=None):
        if name in skip:
            return
        m = np.zeros((h, w), np.uint8)
        cv2.polylines(m, [np.round(np.array(pts, np.float32)).astype(np.int32)], False, 255,
                      max(1, int(round((thick if width is None else width) * zoom))), lineType=cv2.LINE_AA)
        if not (m > 128).any():
            return   # (the thing lies outside this frame)
        a = (m.astype(np.float32) / 255.0)[..., None]
        img[:] = img * (1 - a) + (line if tone is None else tone) * a
        marks[name] = np.maximum(marks.get(name, 0), (m > 128).astype(np.uint8))

    def ray(angle, r0, r1, bend=0.0, n=14):
        """From the outline of the head outwards; the angle is counted from 'up', clockwise, in degrees."""
        pts = []
        for t in np.linspace(0.0, 1.0, n):
            a = np.deg2rad(angle + bend * t * t)
            pts.append((cx + (rx + r0 + (r1 - r0) * t) * np.sin(a), cy - (ry + r0 + (r1 - r0) * t) * np.cos(a)))
        return pts

    for angle, far, bend in ((-14, 95, 0.0), (10, 75, 9.0), (40, 62, 7.0)):
        draw("out", ray(angle, -4 * s, far * s, bend))
    if top == "pole":
        draw("long", ray(-2, -4 * s, 300 * s, n=2))
    else:
        draw("up", ray(0, -4 * s, 85 * s, n=2))
    draw("short", ray(25, -4 * s, 36 * s))
    draw("along", ray(-60, -4 * s, 28 * s, n=5)
         + [(cx + (rx + 28 * s) * np.sin(a), cy - (ry + 28 * s) * np.cos(a)) for a in np.deg2rad(np.linspace(-58.0, -28.0, 16))])
    for angle in (62, 70, 78, 86):   # along the outline, 5..11 px from it
        d = (5 + (angle % 7)) * s
        draw("fringe", [(cx + (rx + d) * np.sin(a), cy - (ry + d) * np.cos(a)) for a in np.deg2rad(np.linspace(angle - 4.0, angle + 4.0, 8))], width=1)
    ex, ey = cx - rx * np.cos(np.deg2rad(8)), cy - ry * np.sin(np.deg2rad(8))
    draw("lash", [(ex + 3 * s, ey), (ex - 12 * s, ey - 5 * s)])
    fx, fy = cx - rx * np.cos(np.deg2rad(-20)), cy - ry * np.sin(np.deg2rad(-20))
    draw("face", [(fx + 3 * s, fy), (fx - 80 * s, fy + 14 * s)])
    draw("apart", ray(55, 60 * s, 125 * s, n=4))
    # a wisp: six faint hairs that cross each other like a lattice, three leaning one way and three the other
    # (faint: drawn as strongly as the single hairs, such a patch is a thing to the map of the gear)
    for angle, lean in ((99, 1), (104, 1), (109, 1), (107, -1), (112, -1), (117, -1)):
        root = ray(angle, -4 * s, 0, n=2)[0]
        out_dir = np.deg2rad(angle + 32 * lean)
        draw("tuft", [root, (root[0] + 74 * s * np.sin(out_dir), root[1] - 74 * s * np.cos(out_dir))], tone=wall + 0.2 * (line - wall))
    # a thread that sticks out of the clothes, three head widths below the top of the head
    low_y = cy - ry + 6.0 * rx
    low_x = cx + 120 * s + 210 * s * (low_y - cy - 150 * s) / max(1.0, h + 400 * s - cy - 150 * s)
    draw("low", [(low_x - 4 * s, low_y), (low_x + 70 * s, low_y - 24 * s)])
    k0 = (cx + rx * np.sin(np.deg2rad(125)), cy - ry * np.cos(np.deg2rad(125)))
    draw("cable", [(k0[0] - 3 * s, k0[1]), (w - 1, k0[1] + 0.10 * (w - 1 - k0[0]))])

    a = (cv2.GaussianBlur(sil, (0, 0), 0.8).astype(np.float32) / 255.0)[..., None]
    img[:] = img * (1 - a) + person * a
    img += rng.normal(0.0, noise, (h, w, 1)).astype(np.float32)
    return (np.clip(img + 0.5, 0, 255).astype(np.uint8), cv2.resize(sil, (1024, 1024), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0,
            marks, sil)


def _mark_depth(pic, mark, ring=7):
    """How far the pixels of a drawn line are from the tone of the wall around them (levels, darker or lighter)."""
    around = (cv2.dilate(mark, np.ones((2 * ring + 1, 2 * ring + 1), np.uint8)) > 0) & ~(cv2.dilate(mark, np.ones((7, 7), np.uint8)) > 0)
    g = pic[..., :3].astype(np.float32).mean(axis=2)
    return abs(float(np.median(g[around]) - g[mark > 0].mean()))


def check_hair():
    """
    "strayHair": the single hairs that stick out of the hairdo are found where the dust search never looks - from
    the edge of the hairdo outwards - and repaired like dust. Everything else that is thin and near a head stays.
    """
    bad, notes = [], []
    p = dict(H.STD, spots=0, scuffs=0, seamOn=False, blur=0, cycCurve=0, smokeOn=False)

    STAY = ("fringe", "along", "lash", "face", "apart", "tuft", "low", "cable", "long")

    def judged(tag, frame, marks, sil_full, out, st, taken=0.30, stay=STAY):
        comp = _comp(frame, out)
        dist = cv2.distanceTransform((sil_full == 0).astype(np.uint8), cv2.DIST_L2, 5)
        head_w = float((sil_full[: int(np.nonzero(sil_full.any(axis=1))[0][0] + 0.08 * frame.shape[0])] > 0).sum(axis=1).max())
        kept = {}
        for name, m in marks.items():
            if name not in stay:
                # (the first pixels of a hair, in the fuzz of the outline, stay: a hair is judged from there on)
                m = ((m > 0) & (dist > (0.06 if name == "short" else 0.12) * head_w)).astype(np.uint8)
            if int(m.sum()) < 20:
                bad.append(f"{tag}: '{name}' has {int(m.sum())} pixels to judge by")
                kept[name] = float("nan")
                continue
            kept[name] = _mark_depth(comp, m) / _mark_depth(frame, m)
        if not st.get("hair_px"):
            bad.append(f"{tag}: no hair was marked (hair_px {st.get('hair_px')})")
        for name in marks:
            if name in stay:
                if not kept[name] >= 0.90:
                    bad.append(f"{tag}: '{name}' must stay, {100 * kept[name]:.0f}% of it is left")
            elif not kept[name] <= (taken if name == "out" else 0.45):
                bad.append(f"{tag}: the hairs '{name}' kept {100 * kept[name]:.0f}% of their contrast")
        changed = np.abs(comp - frame.astype(np.float32)).max(axis=2)
        if float(changed[sil_full > 0].max()) > 0.0:
            bad.append(f"{tag}: the person was changed by {changed[sil_full > 0].max():.1f} levels")
        # (everything that may be taken in this scene, with room for the soft edge of the repair; 0.01: where the
        #  layer is faintly there and says what the photo says, the composite differs by the rounding of floats)
        may_go = np.zeros_like(marks["out"])
        for name, m in marks.items():
            if name not in stay:
                may_go |= m
        away = cv2.dilate(may_go, np.ones((int(0.32 * head_w) | 1,) * 2, np.uint8)) == 0
        if float(changed[away].max()) > 0.01:
            bad.append(f"{tag}: the frame was changed away from the hairs (by {changed[away].max():.2f} levels)")
        return kept

    def with_fill_source(eng_, frame_, params):
        """process(), and what the inpainting was given: (layer, stats, {"src": the picture, "mask": what to fill})."""
        seen = {}

        def spy(fn):
            def call(img, mask, *a, **k):
                if "src" not in seen and img.shape[:2] == frame_.shape[:2]:
                    seen["src"], seen["mask"] = img.copy(), mask.copy()
                return fn(img, mask, *a, **k)
            return call

        eng_._run_fast_inpaint, eng_._run_lama_tiles = spy(eng_._run_fast_inpaint), spy(eng_._run_lama_tiles)
        try:
            out_, st_ = _quiet(eng_.process, frame_, 8, params)
        finally:
            del eng_.__dict__["_run_fast_inpaint"], eng_.__dict__["_run_lama_tiles"]
        return out_, st_, seen

    frame, sil, marks, sil_full = _hair_frame()
    eng = H.make_engine(E, sil)
    for mode in ("fast", "quality"):
        out0, st0 = _quiet(eng.process, frame, 8, dict(p, speedMode=mode))
        out_z, st_z = _quiet(eng.process, frame, 8, dict(p, speedMode=mode, strayHair=0))
        if st0.get("hair_px") or st_z.get("hair_px") or int(out0[..., 3].max()) != 0 or not np.array_equal(out0, out_z):
            bad.append(f"{mode}: with the slider at 0 nothing may be looked for (hair_px {st0.get('hair_px')}, layer {int(out0[..., 3].max())})")
        out, st, fill = with_fill_source(eng, frame, dict(p, speedMode=mode, strayHair=100))
        kept = judged(f"{mode}, slider 100", frame, marks, sil_full, out, st)
        # The mark of a hair begins inside the protected band, so the network must be shown the wall around it as
        # the photo has it. (Elsewhere the band is painted over with an average of the backdrop further away, to
        # keep the colours of the person out of a repair that ends before the band: next to a head that average
        # is not the tone of the wall right there.) Looked at from 5 px off the person: beyond the guard strip,
        # which is painted over either way, and still inside the band.
        if "src" not in fill:
            bad.append(f"{mode}: no repair was asked for")
        else:
            off_person = cv2.distanceTransform((sil_full == 0).astype(np.uint8), cv2.DIST_L2, 5) > 5
            around = (cv2.dilate((fill["mask"] > 0).astype(np.uint8), np.ones((49, 49), np.uint8)) > 0) & off_person & (fill["mask"] == 0)
            differs = np.abs(fill["src"].astype(np.int16) - frame[..., :3].astype(np.int16)).max(axis=2)[around]
            if differs.size == 0 or int(differs.max()) > 0:
                bad.append(f"{mode}: around the hairs the repair is shown something else than the photo "
                           f"({100.0 * float((differs > 0).mean()) if differs.size else 0:.0f}% of the surroundings, up to {int(differs.max()) if differs.size else 0} levels)")
        if mode == "fast":
            notes.append(f"hairs that stick out of the hairdo: {100 * kept['out']:.0f}% of their contrast left (a dead straight vertical one: {100 * kept['up']:.0f}%); "
                         f"the fuzz of the outline {100 * kept['fringe']:.0f}%, "
                         f"a hair that turns to run along the outline {100 * kept['along']:.0f}%, "
                         f"an eyelash {100 * kept['lash']:.0f}%, a line out of the lit face {100 * kept['face']:.0f}%, a line that touches nobody {100 * kept['apart']:.0f}%, "
                         f"a thread at the clothes {100 * kept['low']:.0f}%, a cable that goes on to the frame border {100 * kept['cable']:.0f}%")
            short100 = kept["short"]
    # a hair of a tenth of the head goes at 100 (above) and stays at 30: the lower the slider, the longer a hair must be
    out, st = _quiet(eng.process, frame, 8, dict(p, speedMode="fast", strayHair=30))
    k30 = judged("slider 30", frame, marks, sil_full, out, st, stay=("short",) + STAY)
    notes.append(f"a hair a tenth of the head long: {100 * short100:.0f}% left at 100, {100 * k30['short']:.0f}% at 30")
    # A wisp - hairs that cross each other - is no single hair. (Judged without the cable: next to it the map of
    # the gear takes the wisp for a part of the same thing, and the search does not look there at all.)
    # In the same frame a pole stands where the vertical hair was: a line that grows out of the hairdo like a hair
    # and is still there where the searched zone ends.
    fw, sw_, mw, fullw = _hair_frame(skip=("cable",), top="pole")
    ow, stw = _quiet(H.make_engine(E, sw_).process, fw, 8, dict(p, speedMode="fast", strayHair=100))
    kw_ = judged("a wisp and a pole", fw, mw, fullw, ow, stw)
    notes.append(f"a wisp of crossing hairs {100 * kw_['tuft']:.0f}%, a pole that leaves the searched zone {100 * kw_['long']:.0f}%")
    # the slider: what a lower position takes, a higher one takes too
    px = [int(_quiet(eng.process, frame, 8, dict(p, speedMode="fast", strayHair=v))[1].get("hair_px") or 0) for v in (25, 50, 75, 100)]
    if sorted(px) != px or px[-1] == 0:
        bad.append(f"marked pixels at 25 / 50 / 75 / 100 of the slider: {px}")
    # Light hairs in front of a dark wall (a light line that grows out of the lit face is a hair there: only a
    # dark hair is asked what it grows out of); a close-up, with thicker hairs - there the wisp reaches the cable,
    # and the piece of the cable between the head and that knot ends in the open like a hair; the pole on top of
    # the head ends at the top of the frame there, before the searched zone does.
    for tag, kw, taken, stay in (("light hairs on a dark wall", dict(wall=34.0, hair=92.0, line=150.0, seed=10), 0.35, tuple(n for n in STAY if n != "face")),
                                 ("close-up", dict(zoom=3.2, seed=11, top="pole"), 0.35, STAY)):
        f2, s2, m2, full2 = _hair_frame(**kw)
        o2, st2 = _quiet(H.make_engine(E, s2).process, f2, 8, dict(p, speedMode="fast", strayHair=100))
        k2 = judged(tag, f2, m2, full2, o2, st2, taken=taken, stay=stay)
        notes.append(f"{tag}: {100 * k2['out']:.0f}% left" + (f", the pole that ends at the top of the frame {100 * k2['long']:.0f}%" if "long" in k2 else ""))
    # the hairs go together with the usual clean, and the person stays untouched there too
    out, st = _quiet(eng.process, frame, 8, dict(H.STD, smokeOn=False, cycCurve=65, speedMode="fast", strayHair=100))
    comp = _comp(frame, out)
    core = cv2.erode(sil_full, np.ones((7, 7), np.uint8)) > 0
    if not st.get("hair_px") or float(np.abs(comp - frame.astype(np.float32))[core].max()) > 0.0:
        bad.append(f"with the usual clean: hair_px {st.get('hair_px')}, the person changed by {np.abs(comp - frame.astype(np.float32))[core].max():.1f}")
    # The tool changes nothing about the other repairs. Around a marked hair the inpainting is shown the photo
    # right up to the person; everywhere else the protected band is painted over with the backdrop as always.
    # So dust next to the legs, far below the hairs, must be repaired pixel for pixel as with the slider at 0.
    dusty, specks = frame.copy(), np.zeros(frame.shape[:2], np.uint8)
    off_p = cv2.distanceTransform((sil_full == 0).astype(np.uint8), cv2.DIST_L2, 5)
    ys_d, xs_d = np.nonzero((off_p > 10) & (off_p < 16) & (np.arange(frame.shape[0])[:, None] > 0.62 * frame.shape[0]))
    for i in np.random.default_rng(5).choice(ys_d.size, 24, replace=False):
        cv2.circle(dusty, (int(xs_d[i]), int(ys_d[i])), 2, (70, 70, 70), -1)
        cv2.circle(specks, (int(xs_d[i]), int(ys_d[i])), 2, 1, -1)
    low = int(0.55 * frame.shape[0])
    for mode in ("fast", "quality"):
        pd = dict(H.STD, smokeOn=False, cycCurve=0, scuffs=0, seamOn=False, speedMode=mode)
        o_off, st_off = _quiet(eng.process, dusty, 8, pd)
        o_on, st_on = _quiet(eng.process, dusty, 8, dict(pd, strayHair=100))
        seen = dusty[..., :3].astype(np.float32).mean(axis=2)
        left = float(np.abs(_comp(dusty, o_off)[..., :3].mean(axis=2) - 150.0)[specks > 0].mean() / max(1e-6, np.abs(seen - 150.0)[specks > 0].mean()))
        if left > 0.5 or not st_on.get("hair_px"):
            bad.append(f"{mode}, dust next to the legs: the scene judges nothing ({100 * left:.0f}% of the dust left with the slider at 0, hair_px {st_on.get('hair_px')} at 100)")
        elif not np.array_equal(o_on[low:], o_off[low:]):
            diff = np.abs(_comp(dusty, o_on) - _comp(dusty, o_off)).max(axis=2)[low:]
            bad.append(f"{mode}, dust next to the legs: with the hair slider at 100 its repair is another one than at 0 "
                       f"({int((diff > 0).sum())} px, up to {float(diff.max()):.1f} levels)")

    # The big window: the slider moved after the window opened gives the frame of a window opened with that value,
    # the quick way and the full way; back at 0 nothing is left of it.
    big, sil_b, marks_b, full_b = _hair_frame(2100, 2800, seed=12)
    win = dict(p, speedMode="quality")

    def applied(eng_, sid):
        return _quiet(eng_.apply_session, sid, 100.0, False, False, 0.0)[0]

    e_ref = H.make_engine(E, sil_b)
    ref100 = applied(e_ref, _quiet(e_ref.start_session, big, 8, dict(win, strayHair=100))["session_id"])
    e_ref0 = H.make_engine(E, sil_b)
    ref0 = applied(e_ref0, _quiet(e_ref0.start_session, big, 8, dict(win))["session_id"])
    if int(ref0[..., 3].max()) != 0 or int(ref100[..., 3].max()) == 0:
        bad.append("window: a session opened with the slider at 0 / at 100 gives a layer / no layer")
    for quick in (True, False):
        e1 = H.make_engine(E, sil_b)
        r = _quiet(e1.start_session, big, 8, dict(win))
        q = _quiet(e1.recompute_session, r["session_id"], dict(win, strayHair=100), True, None, quick)
        if quick and (q.get("quick") is not True or not q["stats"].get("hair_px")):
            bad.append(f"window: the light refresh did not mark the hairs (quick {q.get('quick')}, hair_px {q['stats'].get('hair_px')})")
        if not np.array_equal(applied(e1, r["session_id"]), ref100):
            bad.append(f"window: slider moved to 100 ({'light refresh' if quick else 'full recompute'}), then Apply: not the frame of a window opened at 100")
        e2 = H.make_engine(E, sil_b)
        r = _quiet(e2.start_session, big, 8, dict(win, strayHair=100))
        q = _quiet(e2.recompute_session, r["session_id"], dict(win, strayHair=0), True, None, quick)
        if q["stats"].get("hair_px") or not np.array_equal(applied(e2, r["session_id"]), ref0):
            bad.append(f"window: slider back at 0 ({'light refresh' if quick else 'full recompute'}), then Apply: something of the hair repair is left")
    # ...and between two values that both look for hairs (what one value found is not what the other finds)
    e_ref1 = H.make_engine(E, sil_b)
    r1 = _quiet(e_ref1.start_session, big, 8, dict(win, strayHair=1))
    px1 = r1["stats"].get("hair_px")
    ref1 = applied(e_ref1, r1["session_id"])
    e3 = H.make_engine(E, sil_b)
    r = _quiet(e3.start_session, big, 8, dict(win, strayHair=100))
    q = _quiet(e3.recompute_session, r["session_id"], dict(win, strayHair=1), True, None, True)
    if q["stats"].get("hair_px") != px1 or not np.array_equal(applied(e3, r["session_id"]), ref1):
        bad.append(f"window: slider moved from 100 to 1: hair_px {q['stats'].get('hair_px')} (a window opened at 1: {px1}), or the layer differs")
    if px1 == r["stats"].get("hair_px"):
        bad.append(f"window: the slider at 1 and at 100 marks the same {px1} px in the frame of this check")
    report("hair", not bad, "; ".join(notes) + "; the person untouched; dust far from the hairs repaired as with the slider at 0; slider at 0: nothing looked for; the big window: light refresh and full recompute == opened with that value"
           if not bad else "wrong:\n  " + "\n  ".join(bad))


def check_plugin():
    root = H.REPO_ROOT
    r = subprocess.run([sys.executable, os.path.join(root, "tools", "build_ccx.py"), "--check"], capture_output=True, text=True)
    report("plugin", r.returncode == 0, r.stdout.strip().splitlines()[0] if r.stdout.strip() else "build_ccx.py --check failed")
    # the one file people download: same content as the folder, .bat files with CRLF (cmd.exe needs them)
    r = subprocess.run([sys.executable, os.path.join(root, "tools", "build_zip.py"), "--check"], capture_output=True, text=True)
    report("plugin", r.returncode == 0, r.stdout.strip().splitlines()[0] if r.returncode == 0 and r.stdout.strip()
           else "build_zip.py --check: " + " | ".join((r.stdout + r.stderr).strip().splitlines()[:12]))
    node = shutil.which("node")
    if not node:
        report("plugin", True, "settings migration test SKIPPED - Node.js is not installed")
        return
    r = subprocess.run([node, os.path.join(root, "tests", "plugin_settings.test.js")], capture_output=True, text=True)
    last = (r.stdout.strip().splitlines() or ["no output"])[-1]
    report("plugin", r.returncode == 0, last if r.returncode == 0 else r.stdout + r.stderr)
    # the big window: when the plugin asks the server for what (prints SKIPPED by itself when jsdom is missing)
    r = subprocess.run([node, os.path.join(root, "tests", "plugin_preview.test.js")], capture_output=True, text=True)
    last = (r.stdout.strip().splitlines() or ["no output"])[-1]
    report("plugin", r.returncode == 0, last if r.returncode == 0 else r.stdout + r.stderr)


GROUPS = [("convert", check_convert), ("process", check_process), ("stage", check_stage), ("quick", check_quick),
          ("session", check_session),
          ("white", check_white), ("gpu", check_gpu), ("fallback", check_fallback), ("fastwin", check_fastwin),
          ("cyc", check_cyc), ("dress", check_dress), ("speed", check_speed), ("smoke", check_smoke), ("empty", check_empty),
          ("format", check_format), ("scene", check_scene), ("stains", check_stains), ("seam", check_seam), ("mask", check_mask),
          ("brush", check_brush),
          ("dark", check_dark), ("gear", check_gear), ("shadow", check_shadow), ("undo", check_undo),
          ("exact", check_exact), ("sharp", check_sharp),
          ("edge", check_edge), ("line", check_line), ("hair", check_hair),
          ("server", check_server), ("http", check_http),
          ("folders", lambda: IC.check_folders(report)), ("install", lambda: IC.check_install(report)),
          ("bat", lambda: IC.check_bat(report)), ("plugin", check_plugin)]


def main() -> int:
    t0 = time.perf_counter()
    print(f"Clean Vinyl Pro self-checks ({'full' if FULL else 'quick'} run); NumPy {np.__version__}, OpenCV {cv2.__version__}; "
          f"baseline v3.2.1: {'available' if E_OLD is not None else 'NOT available'}", flush=True)
    for name, fn in GROUPS:
        if ONLY and not any(word in name for word in ONLY):
            continue
        try:
            fn()
        except Exception as exc:  # a crashed check is a failed check
            import traceback
            traceback.print_exc()
            report(name, False, f"crashed: {type(exc).__name__}: {exc}")
    failed = [g for g, ok in _results if not ok]
    print(f"\n{'ALL CHECKS PASSED' if not failed else 'FAILED: ' + ', '.join(sorted(set(failed)))} "
          f"({len(_results)} results, {time.perf_counter() - t0:.0f} s)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
