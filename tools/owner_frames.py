#!/usr/bin/env python3
"""
A look at the owner's own frames and results - a tool for the agent, not a part of the program.

The owner sends a frame as shot and what the program made of it on his PC (the real AI models, which are not
here). This tool answers the questions that come up every time, so that they need not be programmed again
after the sandbox was replaced:

    python tools/owner_frames.py dates FILE [FILE ...]
        The date, the size and the program in the EXIF of each file: which one is the frame, which the
        result, and when each was saved (he names his files alike: "... копия.jpg", "... копия 2.jpg").

    python tools/owner_frames.py zones FRAME RESULT OUT.jpg
        Where his result differs from the frame: [the frame | grain left | tone moved]. "Grain left" is dark
        where the fine grain was taken down (the mixer brush, a repaint) and light where it is untouched;
        "tone moved" is grey where nothing changed, lighter / darker where the result is. Prints the share of
        pixels that are exactly the frame - a layer that does not cover the backdrop shows there.

    python tools/owner_frames.py silhouette FRAME POLYGON.json OUT.npy [CHECK.jpg]
        A stand-in for the silhouette model: GrabCut started from a polygon. POLYGON.json is a list of
        [x, y] corners around the people, in shares of the frame (0..1), drawn by eye - a rough outline is
        enough, the cut follows the real edges. CHECK.jpg shows the outline on the frame.

    python tools/owner_frames.py protected FRAME RESULT OUT.npy [CHECK.jpg] [+ADD.json ...] [-DROP.json ...]
        HIS silhouette, read from his own result: what his run left exactly as it was. He saves the frame and
        the result from one document, one after the other, so the 8 x 8 blocks of the two JPEGs that are equal
        to the last bit are what the program protected - the people and what stands with them (a stool). Far
        closer to his silhouette than GrabCut, also on a dark frame; up to a block (8 px) too small at the
        outline. What his clothing tool changed is missing from it: give a polygon drawn loosely INSIDE each
        such garment as +ADD.json (CHECK.jpg shows the outline: a hole or a bay in a garment is where a polygon
        is still missing). A lamp or a prop that was protected too is taken away with -DROP.json.
        (Polygons as for "silhouette": [x, y] corners in shares of the frame.) With this silhouette, `run`
        gives his picture back wherever the stand-in networks play no part - so the preset and the ticks he
        used can be found by trying (0Q5A3522: his result and the one made here differ by more than 2 levels
        on 1.2% of the frame).

    python tools/owner_frames.py run FRAME SILHOUETTE.npy "PRESET NAME" OUT.jpg [key=value ...] [RESULT]
        The engine of this checkout on the frame, with what the panel sends for that built-in preset and the
        given changes (for example smokeOn=True removeStands=True mixOn=True mix=50), with the stand-in
        networks of the checks. Writes [the frame | this result | tone moved here] and, with RESULT, the
        owner's own result and its tone map next to them. Prints the numbers of the run ("stats").

    python tools/owner_frames.py clothes FRAME SILHOUETTE.npy|auto OUT.jpg [STRENGTH ...] [box=x0,y0,x1,y1]
        The clothing tool («Рівняти одяг») of this checkout on the frame, at each strength of the slider
        (default 45 and 100). Writes [the frame | the clothing mask | per strength: the result, and what it
        changed x8] cut to the box (shares of the frame; default: around the clothing) and prints, per strength,
        how much of the frame moved and how far the hue of the cloth moved. With "auto" the silhouette is a
        rough stand-in made without a polygon (GrabCut started from the backdrop along the left, right and top
        edges): good enough on a light backdrop, wrong on dark frames - draw a polygon for those.

What this can and cannot tell. The maps of the engine (what is smoke, gear, shadow; what is marked for removal;
where the corner is) come from the frame and the silhouette alone, so they are close to his - not equal: his
silhouette is another, and he opens the document, not its JPEG. The AI fill here is a simple stand-in: what
the real one paints into a large area cannot be seen. Never commit his photos or anything made from them.

Needs NumPy, OpenCV and Pillow (the environment of the checks, see AGENTS.md, section 4).
"""
import contextlib
import io
import json
import os
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(path):
    """The picture as RGB uint8 (the path may hold Cyrillic letters)."""
    bgr = cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_COLOR)
    if bgr is None:
        sys.exit(f"cannot read {path}")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def save(path, rgb, quality=88):
    ok, buf = cv2.imencode(os.path.splitext(path)[1] or ".jpg", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        sys.exit(f"cannot write {path}")
    buf.tofile(path)


def small(img, high=900):
    s = high / img.shape[0]
    return cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)


def grey3(a):
    return np.repeat(np.clip(a, 0, 255).astype(np.uint8)[..., None], 3, axis=2)


def tone_moved(frame, result, sigma=8.0):
    """How far the tone moved (levels, smoothed): positive where the result is lighter."""
    return cv2.GaussianBlur((result.astype(np.float32) - frame.astype(np.float32)).mean(axis=2), (0, 0), sigma)


def grain_left(frame, result, sigma=24.0):
    """The fine grain of the result as a share of the frame's, zone by zone (1 = untouched)."""
    def energy(x):
        g = x.astype(np.float32).mean(axis=2)
        return cv2.GaussianBlur((g - cv2.GaussianBlur(g, (0, 0), 2.0)) ** 2, (0, 0), sigma)
    return np.sqrt(energy(result) / np.maximum(energy(frame), 1e-6))


def cmd_dates(paths):
    from PIL import Image
    for p in paths:
        with Image.open(p) as im:
            ex = im.getexif()
            print(f"{os.path.basename(p)}: {im.size[0]} x {im.size[1]}, saved {ex.get(306)}, by {ex.get(305)}")


def cmd_zones(frame_path, result_path, out_path):
    frame, result = load(frame_path), load(result_path)
    if frame.shape != result.shape:
        sys.exit(f"the two pictures differ in size: {frame.shape[1]} x {frame.shape[0]} and {result.shape[1]} x {result.shape[0]}")
    same = np.abs(frame.astype(np.int16) - result.astype(np.int16)).max(axis=2) == 0
    left, moved = grain_left(frame, result), tone_moved(frame, result)
    print(f"exactly the frame: {same.mean() * 100:.1f}% of the pixels; grain taken down (under 0.7 of the frame's) on "
          f"{(left < 0.7).mean() * 100:.0f}% of the frame; tone moved by more than 1 level on {(np.abs(moved) > 1).mean() * 100:.0f}%, "
          f"largest {moved.min():+.1f} / {moved.max():+.1f}")
    save(out_path, np.hstack([small(frame), small(grey3(left * 200.0)), small(grey3(128.0 + moved * 16.0))]))
    print(f"written {out_path}: the frame | grain left (light = untouched) | tone moved (x16 around grey)")


def cmd_silhouette(frame_path, polygon_path, out_path, check_path=None):
    frame = load(frame_path)
    with open(polygon_path, encoding="utf-8") as f:
        poly = json.load(f)
    s = 1100.0 / frame.shape[0]
    work = cv2.cvtColor(cv2.resize(frame, None, fx=s, fy=s, interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2BGR)
    sh, sw = work.shape[:2]
    inside = np.zeros((sh, sw), np.uint8)
    cv2.fillPoly(inside, [np.array([(int(x * sw), int(y * sh)) for x, y in poly], np.int32)], 1)
    mask = np.full((sh, sw), cv2.GC_BGD, np.uint8)
    mask[cv2.dilate(inside, np.ones((25, 25), np.uint8)) > 0] = cv2.GC_PR_BGD
    mask[inside > 0] = cv2.GC_PR_FGD
    mask[cv2.erode(inside, np.ones((25, 25), np.uint8)) > 0] = cv2.GC_FGD
    # (dark clothes on a dark backdrop: the shadows are opened up so that the colour models can tell them apart)
    opened = np.clip(255.0 * (work.astype(np.float32) / 255.0) ** 0.5, 0, 255).astype(np.uint8)
    cv2.grabCut(opened, mask, None, np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64), 5, cv2.GC_INIT_WITH_MASK)
    cut = ((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD)).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(cut, 8)
    keep = np.zeros_like(cut)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] > 0.002 * sh * sw:
            keep[lab == i] = 1
    keep = cv2.morphologyEx(keep, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    sil = cv2.resize(cv2.GaussianBlur(keep.astype(np.float32), (0, 0), 1.2), (1024, 1024), interpolation=cv2.INTER_LINEAR)
    np.save(out_path, sil)
    print(f"written {out_path}: the people cover {(sil > 0.5).mean() * 100:.1f}% of the frame")
    if check_path:
        view = np.clip(small(frame).astype(np.float32) * 1.8 + 20, 0, 255).astype(np.uint8)
        on = cv2.resize(sil, (view.shape[1], view.shape[0])) > 0.5
        view[cv2.morphologyEx(on.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0] = (0, 255, 0)
        save(check_path, view)


def cmd_protected(frame_path, result_path, out_path, rest):
    frame, result = load(frame_path), load(result_path)
    if frame.shape != result.shape:
        sys.exit(f"the two pictures differ in size: {frame.shape[1]} x {frame.shape[0]} and {result.shape[1]} x {result.shape[0]}")
    h, w = frame.shape[:2]
    hb, wb = h // 8, w // 8
    diff = np.abs(frame.astype(np.int16) - result.astype(np.int16)).max(axis=2)
    same = (diff[:hb * 8, :wb * 8].reshape(hb, 8, wb, 8).max(axis=(1, 3)) == 0).astype(np.uint8)
    # single equal blocks of the backdrop go, the body stays
    same = cv2.morphologyEx(same, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(same, 8)
    keep = np.zeros_like(same)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] > 0.004 * hb * wb:
            keep[lab == i] = 1
    keep = cv2.morphologyEx(keep, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    for arg in rest:
        if arg[:1] not in "+-":
            continue
        with open(arg[1:], encoding="utf-8") as f:
            poly = json.load(f)
        area = np.zeros_like(keep)
        cv2.fillPoly(area, [np.array([(int(x * wb), int(y * hb)) for x, y in poly], np.int32)], 1)
        keep[area > 0] = 1 if arg[0] == "+" else 0
    sil = cv2.resize(cv2.GaussianBlur(keep.astype(np.float32), (0, 0), 0.8), (1024, 1024), interpolation=cv2.INTER_LINEAR)
    np.save(out_path, sil)
    print(f"written {out_path}: equal to the last bit on {(diff == 0).mean() * 100:.1f}% of the pixels; what was protected covers "
          f"{(sil > 0.5).mean() * 100:.1f}% of the frame")
    check = next((a for a in rest if a[:1] not in "+-"), None)
    if check:
        view = np.clip(small(frame).astype(np.float32) * 1.8 + 20, 0, 255).astype(np.uint8)
        on = cv2.resize(sil, (view.shape[1], view.shape[0])) > 0.5
        view[cv2.morphologyEx(on.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0] = (0, 255, 0)
        save(check, view)


def auto_silhouette(frame):
    """A rough stand-in for the silhouette model without a polygon: what is not the backdrop of the frame edges."""
    s = 1000.0 / frame.shape[0]
    work = cv2.cvtColor(cv2.resize(frame, None, fx=s, fy=s, interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2BGR)
    sh, sw = work.shape[:2]
    lab = cv2.cvtColor(work, cv2.COLOR_BGR2LAB).astype(np.float32)
    # the backdrop, roughly: the picture with everything smaller than a third of the frame smoothed away
    back = cv2.GaussianBlur(cv2.medianBlur(work, 2 * int(0.04 * sw) + 1), (0, 0), 0.10 * sw)
    far = np.linalg.norm(lab - cv2.cvtColor(back, cv2.COLOR_BGR2LAB).astype(np.float32), axis=2)
    mask = np.full((sh, sw), cv2.GC_PR_BGD, np.uint8)
    mask[far > 16.0] = cv2.GC_PR_FGD
    mask[cv2.erode((far > 30.0).astype(np.uint8), np.ones((9, 9), np.uint8)) > 0] = cv2.GC_FGD
    edge = max(4, int(0.02 * sw))
    mask[:, :edge] = cv2.GC_BGD
    mask[:, -edge:] = cv2.GC_BGD
    mask[:edge, :] = np.where(far[:edge, :] > 30.0, mask[:edge, :], cv2.GC_BGD)   # (a head may reach the top edge)
    opened = np.clip(255.0 * (work.astype(np.float32) / 255.0) ** 0.5, 0, 255).astype(np.uint8)
    cv2.grabCut(opened, mask, None, np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64), 5, cv2.GC_INIT_WITH_MASK)
    cut = ((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD)).astype(np.uint8)
    n, lbl, stats, _ = cv2.connectedComponentsWithStats(cut, 8)
    keep = np.zeros_like(cut)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] > 0.004 * sh * sw:
            keep[lbl == i] = 1
    keep = cv2.morphologyEx(keep, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    return cv2.resize(cv2.GaussianBlur(keep.astype(np.float32), (0, 0), 1.2), (1024, 1024), interpolation=cv2.INTER_LINEAR)


def cmd_clothes(frame_path, sil_arg, out_path, rest):
    strengths = [float(a) for a in rest if "=" not in a] or [45.0, 100.0]
    box = next(([float(v) for v in a.split("=", 1)[1].split(",")] for a in rest if a.startswith("box=")), None)
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import harness as H
    engine = H.load_engine()
    frame = load(frame_path)
    h, w = frame.shape[:2]
    sil = auto_silhouette(frame) if sil_arg == "auto" else np.load(sil_arg)
    eng = H.make_engine(engine, sil)
    params = panel_params("std", [])
    cache = {}

    def run(p):
        oc = {}
        with contextlib.redirect_stdout(io.StringIO()):
            out, _ = eng.process(frame, 8, p, stage_cache=cache, out_cache=oc)
        a = out[:, :, 3:4].astype(np.float32) / 255.0
        return np.clip(frame.astype(np.float32) * (1 - a) + out[:, :, :3].astype(np.float32) * a, 0, 255).astype(np.uint8), oc

    base, _ = run(dict(params, dressSmooth=False))
    results, mask = [], None
    for s in strengths:
        res, oc = run(dict(params, dressSmooth=True, dressStrength=s))
        mask = oc.get("dress_s")
        results.append(res)
    if mask is None:
        sys.exit("the engine made no clothing mask")
    m_full = cv2.resize(mask, (w, h), interpolation=cv2.INTER_LINEAR)
    cloth = m_full > 0.5
    if box is None:
        ys, xs = np.where(m_full > 0.05)
        if ys.size == 0:
            sys.exit("no clothing found (the mask is empty)")
        box = [max(0.0, xs.min() / w - 0.02), max(0.0, ys.min() / h - 0.02), min(1.0, xs.max() / w + 0.02), min(1.0, ys.max() / h + 0.02)]
    x0, y0, x1, y1 = int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)

    def hue(x):
        x = cv2.GaussianBlur(x.astype(np.float32), (0, 0), 3.0) + 5.0
        return np.log(x[..., 0] / x[..., 1]), np.log(x[..., 2] / x[..., 1])

    print(f"the clothing mask covers {cloth.mean() * 100:.1f}% of the frame, in "
          f"{cv2.connectedComponents((mask > 0.02).astype(np.uint8), connectivity=8)[0] - 1} piece(s)")
    tiles = [frame[y0:y1, x0:x1], grey3(m_full[y0:y1, x0:x1] * 255.0)]
    hb = hue(base)
    lit = cloth & (cv2.GaussianBlur(base, (0, 0), 3.0).max(axis=2) > 40)
    for s, res in zip(strengths, results):
        d = res.astype(np.int16) - base.astype(np.int16)
        ad = np.abs(d).max(axis=2)
        hr = hue(res)
        moved = np.maximum(np.abs(hr[0] - hb[0]), np.abs(hr[1] - hb[1]))[lit] if lit.any() else np.zeros(1)
        lab0 = cv2.cvtColor(base, cv2.COLOR_RGB2LAB).astype(np.float32)[cloth].mean(axis=0)
        lab1 = cv2.cvtColor(res, cv2.COLOR_RGB2LAB).astype(np.float32)[cloth].mean(axis=0)
        outside = ad[~cv2.dilate(cloth.astype(np.uint8), np.ones((41, 41), np.uint8)).astype(bool)]
        print(f"strength {s:g}: moved by more than 1 level on {(ad > 1).mean() * 100:.2f}% of the frame, by more than 3 on "
              f"{(ad > 3).mean() * 100:.2f}%, largest {int(ad.max())}; outside the clothing largest {int(outside.max()) if outside.size else 0}; "
              f"hue of the cloth moved by more than 2% on {(moved > 0.02).mean() * 100:.2f}% of it; mean of the cloth (Lab, 0..255): "
              f"L {lab1[0] - lab0[0]:+.2f} a {lab1[1] - lab0[1]:+.2f} b {lab1[2] - lab0[2]:+.2f}")
        tiles += [res[y0:y1, x0:x1], np.clip(128 + 8 * d[y0:y1, x0:x1], 0, 255).astype(np.uint8)]
    k = min(1.0, 2400.0 / (len(tiles) * (x1 - x0)), 1300.0 / (y1 - y0))
    save(out_path, np.hstack([cv2.resize(t_, None, fx=k, fy=k, interpolation=cv2.INTER_AREA) for t_ in tiles]), 90)
    print(f"written {out_path} (scale {k:.2f}): the frame | the clothing mask | " + " | ".join(f"{s:g}, changed x8" for s in strengths))


def panel_params(preset_name, changes):
    """What the panel sends for a built-in preset (readCurrentConfig of main.js), with the given changes."""
    with open(os.path.join(ROOT, "CleanVinylPro2", "server", "presets_defaults.json"), encoding="utf-8") as f:
        presets = json.load(f)
    found = [p for p in presets if preset_name in (p["name"], p["id"])]
    if not found:
        sys.exit(f"no built-in preset '{preset_name}'; there are: " + ", ".join(p["name"] for p in presets))
    params = dict(found[0]["cfg"])
    params.update(strayHair=0, mixOn=False, mix=50, smokeAuto=True, smokeFaint=True, speedMode="quality", autoFractions=True)
    for item in changes:
        key, value = item.split("=", 1)
        params[key] = {"True": True, "False": False}.get(value, None)
        if params[key] is None:
            params[key] = float(value) if "." in value else int(value)
    return params


def cmd_run(frame_path, sil_path, preset_name, out_path, rest):
    changes = [a for a in rest if "=" in a]
    results = [a for a in rest if "=" not in a]
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import harness as H
    engine = H.load_engine()
    frame, sil = load(frame_path), np.load(sil_path)
    params = panel_params(preset_name, changes)
    eng = H.make_engine(engine, sil)
    with contextlib.redirect_stdout(io.StringIO()):
        out, stats = eng.process(frame, 8, params)
    alpha = out[:, :, 3:4].astype(np.float32) / 255.0
    here = np.clip(frame.astype(np.float32) * (1 - alpha) + out[:, :, :3].astype(np.float32) * alpha, 0, 255).astype(np.uint8)
    print("stats: " + json.dumps({k: v for k, v in stats.items() if not isinstance(v, (dict, list))}, ensure_ascii=False))
    print("smoke: " + json.dumps(stats.get("smoke"), ensure_ascii=False) + "; taken ready: " + ",".join(stats.get("reused_stages", [])))
    tiles = [small(frame), small(here), small(grey3(128.0 + tone_moved(frame, here) * 12.0))]
    names = "the frame | the result here | tone moved here (x12)"
    if results:
        his = load(results[0])
        tiles += [small(his), small(grey3(128.0 + tone_moved(frame, his) * 12.0))]
        names += " | his result | tone moved in his"
    save(out_path, np.hstack(tiles))
    print(f"written {out_path}: {names}")


def main(argv):
    if len(argv) >= 2 and argv[0] == "dates":
        cmd_dates(argv[1:])
    elif len(argv) == 4 and argv[0] == "zones":
        cmd_zones(*argv[1:])
    elif len(argv) in (4, 5) and argv[0] == "silhouette":
        cmd_silhouette(*argv[1:])
    elif len(argv) >= 4 and argv[0] == "protected":
        cmd_protected(argv[1], argv[2], argv[3], argv[4:])
    elif len(argv) >= 5 and argv[0] == "run":
        cmd_run(argv[1], argv[2], argv[3], argv[4], argv[5:])
    elif len(argv) >= 4 and argv[0] == "clothes":
        cmd_clothes(argv[1], argv[2], argv[3], argv[4:])
    else:
        print(__doc__.strip())
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
