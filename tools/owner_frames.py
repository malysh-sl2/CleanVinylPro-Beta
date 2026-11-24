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

    python tools/owner_frames.py run FRAME SILHOUETTE.npy "PRESET NAME" OUT.jpg [key=value ...] [RESULT]
        The engine of this checkout on the frame, with what the panel sends for that built-in preset and the
        given changes (for example smokeOn=True removeStands=True mixOn=True mix=50), with the stand-in
        networks of the checks. Writes [the frame | this result | tone moved here] and, with RESULT, the
        owner's own result and its tone map next to them. Prints the numbers of the run ("stats").

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
    elif len(argv) >= 5 and argv[0] == "run":
        cmd_run(argv[1], argv[2], argv[3], argv[4], argv[5:])
    else:
        print(__doc__.strip())
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
