#!/usr/bin/env python3
"""
Self-checks of the Clean Vinyl Pro 2 server (folder CleanVinylPro2). No AI models, no GPU and no Photoshop needed.

    python tests/run_checks.py            # quick run (a few minutes)
    python tests/run_checks.py --full     # more random cases
    python tests/run_checks.py stage http # only the groups whose name contains one of the words

Part 1 - what was NOT meant to change still gives the pixels of the original program (folder CleanVinylPro,
v3.2.1). These comparisons run in the "legacy regime": quality mode, smoke protection off, cyclorama 0, clothing
off, stains 0, floor-joint pieces judged one by one - the places where Clean Vinyl Pro 2 works differently on
purpose. (In the interactive window also: background blur 0. With the backdrop blurred the layer covers the whole
backdrop; the window now shows that in two greens and repairs a brush stroke there - see `mask`.)
  convert   fast pixel conversions give the same numbers as the plain NumPy formulas (all 8/16-bit values)
  process   one-shot clean: current engine == v3.2.1 engine, pixel for pixel
  session   interactive window (open / sliders / brush / apply): current engine == v3.2.1
  http      every HTTP endpoint: current server == v3.2.1 server (needs the `httpx` package)
  stage     interactive stage cache: a recompute that re-uses stored stages == a full recompute
  quick     light preview after the sliders: the layer made by "light refreshes + one full computation at Apply"
            == the layer of the old way (a full recompute after every change); the preview itself stays close
  white     the "white patch after Apply" bug stays fixed
  gpu       the cuDNN option can never push the models from the GPU onto the CPU

Part 2 - what Clean Vinyl Pro 2 does differently, each with its own measurable promise:
  cyc       cyclorama: the wall-floor line goes away, people are not touched, a frame without a corner is not touched
  dress     clothing: wrinkles get weaker; volume, colour, fine texture, denim and everything outside stay
  speed     "Швидкий" and "Якісний" find exactly the same defects (they differ only in how defects are repaired)
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

Part 3 - the program around the engine:
  server    settings migration, binary packets, one version everywhere, and no name / port shared with the
            original program (both must be able to run side by side)
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
    """The parameters under which Clean Vinyl Pro 2 must still give the pixels of v3.2.1 (see the header)."""
    return dict(p, speedMode="quality", smokeOn=False, cycCurve=0, dressSmooth=False, scuffs=0, seamJoin=False)


def _legacy_window(p: dict) -> dict:
    """
    The legacy regime for the interactive window: also without the background blur. With any stage that works on
    the whole backdrop the layer covers the whole backdrop; the window then shows what was found and repaired apart
    from what is only evened, and repairs a brush stroke there - on purpose, see check_mask. (The blur itself is
    still compared with v3.2.1 by the one-shot checks.)
    """
    return dict(_legacy(p), blur=0)


def _same_stats(a: dict, b: dict) -> bool:
    skip = ("elapsed_ms", "reused_stages")
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
                            "feather", "spots", "smokeAuto", "seamJoin", "cycCurve", "scuffs"]))
        if k == "same":
            continue
        if k in ("seamOn", "smokeOn", "shadow", "removeStands", "fracFine", "fracMed", "fracLarge", "autoFractions",
                 "smokeAuto", "seamJoin"):
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
                     ("cleanPasses", 2)):
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
# Part 2: what Clean Vinyl Pro 2 does differently
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
    report("speed", not bad, f"{n} frames: both speed modes and the green preview mark the same defects" if not bad else "wrong:\n  " + "\n  ".join(bad))


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

    def texture(a, zone):
        g = a.astype(np.float32).mean(axis=2)
        band = cv2.GaussianBlur(g, (0, 0), 4.0) - cv2.GaussianBlur(g, (0, 0), 20.0)
        return float(np.sqrt((band[zone > 0.6] ** 2).mean()))

    def cleaned(frame, zone, **over):
        eng = H.make_engine(E, sil)
        out, stats = _quiet(eng.process, frame, 8, dict(H.STD, spots=0, seamOn=False, speedMode="fast", **over))
        return stats.get("smoke") or {}, texture(_comp(frame, out), zone) / texture(frame, zone)

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
    r3 = _quiet(e1.edit_session_mask, sid, "fill", None, 20, False, False, 45.0)
    r4 = _quiet(e1.edit_session_mask, sid, "clear", None, 20, False, False, 45.0)
    if r3.get("mask_share") != 1.0 or r4.get("mask_share") != 0.0:
        bad.append(f"mask_share after fill / clear: {r3.get('mask_share')} / {r4.get('mask_share')}")

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
                             f"backdrop (limit {limit:.0f}); opening with the automatic preset == opening with that preset by hand, layer included{note}"
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
def _joint_frame(w, h, left=(0.0, 0.18), right=(0.83, 1.0), y_left=0.80, y_right=0.80, corner=False, seed=7, dark=10.0, weak_left=1.0):
    """
    A floor with the joint of two backdrop sheets (a hair-thin dark line with a faint rim), seen only as two pieces:
    a wide silhouette - a long dress with a train that leaves the frame - hides the middle. `left` / `right`: the
    visible part of the line on each side (shares of the width); `y_left` / `y_right`: its height on each side
    (different values = two different lines); `dark`: how dark the line is (levels). corner=True adds the
    wall-floor corner at 0.62 of the height. Returns (frame, silhouette 1024, mask of the drawn joint).
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
    # 4. however visible the joint is: a faint one and a really dark one (the dark one used to be left in the photo)
    for dark in (2.5, 30.0):
        r = run(frame=dict(left=(0.0, 0.30), right=(0.72, 1.0), dark=dark))
        if min(r["cover"]) < 0.9:
            bad.append(f"a joint {dark:.1f} levels dark: covered {r['cover']}")
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

    # a floor joint without any corner in the frame is not a corner (it used to be taken for one and smeared)
    r = run(cycCurve=65)
    if r["stats"].get("corner_row") is not None or not both_gone(r):
        bad.append(f"a joint in a frame without a corner: 'corner' at {r['stats'].get('corner_row')}, joint covered {r['cover']}")
    report("seam", not bad, "; ".join(notes) + "; two different lines and a lone short piece are left alone; faint and dark joints alike"
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
    img, sil = H.make_studio_image(w, h, n_dust=60, n_hair=4, seed=77)
    speck = (int(w * 0.25), int(h * 0.35))          # a mark on the wall that the search is not allowed to take (see `quiet`)
    cv2.circle(img, speck, 7, tuple(int(v) - 45 for v in img[speck[1], speck[0]]), -1, lineType=cv2.LINE_AA)
    on = dict(H.STD, speedMode="fast", smokeAuto=True)   # "Сліди взуття та розводи" 65: the whole backdrop is evened
    off = dict(on, scuffs=0, blur=0, cycCurve=0)          # only what the search finds is repaired

    def opened(params, image=img):
        eng = H.make_engine(E, sil)
        return eng, _quiet(eng.start_session, image, 8, dict(params))

    def jpg(b64):
        import base64
        return cv2.imdecode(np.frombuffer(base64.b64decode(b64), np.uint8), cv2.IMREAD_COLOR).astype(np.float32)

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
    cy_, cx_, rad = int(ey * h), int(ex * w), int(0.5 * 40.0 * w / r["preview_w"])
    if int(out[cy_ - rad:cy_ + rad, cx_ - rad:cx_ + rad, 3].max()) != 0:
        bad.append("an erased zone is still part of the layer after Apply")
    rf = eng.edit_session_mask(sid, "fill")
    rc = eng.edit_session_mask(sid, "clear")
    ra = eng.edit_session_mask(sid, "reset_auto")
    if (rf["mask_share"], rf["layer_share"]) != (1.0, 1.0) or (rc["mask_share"], rc["layer_share"]) != (0.0, 0.0):
        bad.append(f"fill / clear: {rf['mask_share']}, {rf['layer_share']} / {rc['mask_share']}, {rc['layer_share']}")
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

    # Clean Vinyl Pro 2 must be able to run next to the original program: nothing they register may coincide
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
            ("plugin name", manifest["name"] == old_manifest["name"]),
            ("port", port == old_port),
            ("url scheme", scheme in old_manifest["requiredPermissions"]["launchProcess"]["schemes"]),
            ("scheduled task", f'"{task}"' in old_launcher),
            ("registry key", f"Software\\Classes\\{scheme}\"" in old_launcher),
            ("data folder", 'os.path.join(appdata, "CleanVinylPro2")' not in launcher),
            ("layer name", "Чистий вініл 2 (AI)" not in plugin_js or '"Чистий вініл (AI)"' in plugin_js),
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
    report("server", not bad, f"settings migration, packet parsing, version {srv.APP_VERSION} everywhere, nothing shared with the original program (port {srv.APP_PORT})"
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
        client.post("/session/close", json=dict(session_id=sid))
    finally:
        srv.ENGINE = keep
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
        meta["stats"] = {k: v for k, v in meta.get("stats", {}).items() if k not in ("elapsed_ms", "reused_stages", "recomputed", "smoke")}
        return meta, body[4 + n:]

    def norm(d):
        # ("quick" is new: a recompute says whether it only refreshed the preview; "scene", "smoke", "mask_share" and
        #  "layer_share" are new: the answer describes the frame, what was seen of smoke, and how much of the frame
        #  was found and repaired / is covered by the layer)
        d = {k: v for k, v in d.items() if k not in ("session_id", "mask_png_b64", "quick", "scene", "smoke", "mask_share", "layer_share")}
        if "stats" in d:
            d["stats"] = {k: v for k, v in d["stats"].items() if k not in ("elapsed_ms", "reused_stages", "smoke")}
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

                # ---- what only Clean Vinyl Pro 2 has ----
                n += 1
                hl = cn.get("/health").json()
                if hl.get("app") != srv.APP_ID or hl.get("version") != srv.APP_VERSION or hl.get("models_dir") != srv.MODELS_DIR:
                    bad.append("/health does not name this program and its models folder")
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
          ("white", check_white), ("gpu", check_gpu),
          ("cyc", check_cyc), ("dress", check_dress), ("speed", check_speed), ("smoke", check_smoke), ("empty", check_empty),
          ("format", check_format), ("scene", check_scene), ("stains", check_stains), ("seam", check_seam), ("mask", check_mask),
          ("server", check_server), ("http", check_http),
          ("folders", lambda: IC.check_folders(report)), ("install", lambda: IC.check_install(report)),
          ("bat", lambda: IC.check_bat(report)), ("plugin", check_plugin)]


def main() -> int:
    t0 = time.perf_counter()
    print(f"Clean Vinyl Pro 2 self-checks ({'full' if FULL else 'quick'} run); NumPy {np.__version__}, OpenCV {cv2.__version__}; "
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
