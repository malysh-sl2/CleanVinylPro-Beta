// Runs the REAL plugin (uxp-plugin/index.html + main.js) in a simulated browser against a scripted server and
// checks WHEN the plugin asks the server for WHAT while the controls of the big window are used:
//   - nothing is computed while a slider is being dragged;
//   - after the release the preview is refreshed once, the light way (quick: true), without the progress card;
//   - several controls changed in a row give one refresh;
//   - the full-size computation is asked for once: "Застосувати" carries the settings that are on the sliders;
//   - the window opens with the cleaned photo, "До / Після" and "Маска" switch the three views;
//   - a preset click gives one light refresh with that preset's values and says what it changed;
//   - the automatic preset: the presets travel with the photo, the server's choice lands on the controls;
//   - a button pressed while the server is still starting is remembered and runs when the server answers;
//   - smoke: the protection is off until it is asked for; every request asks for "protect smoke only where there
//     is smoke", and the smoke controls say in words what the server saw (on a frame without smoke they change
//     nothing - the note explains why); a frame that seems to have smoke says so when the window opens;
//   - mask edits: Ctrl + Z / Ctrl + Shift + Z / Ctrl + Y and the two buttons step back and forward, edits reach
//     the server one after another;
//   - "Скинути пресет" gives one built-in preset the values it ships with, after a second press;
//   - the backup of the settings: saved through the server, listed, restored after a second click, with a copy of
//     what was there before;
//   - a dark backdrop takes the dark preset of its framing;
//   - one mode: there is no speed button, and every request asks for the full AI fill, whatever settings and
//     presets of an older version say;
//   - the edge of the brush and the eraser: soft unless the user chose the hard one; the choice travels with every
//     stroke and is kept with the settings.
//
//   node tests/plugin_preview.test.js
//   node tests/plugin_preview.test.js "preset click" remembered     (only the scenarios whose name has one of the texts)
//
// Needs the "jsdom" package once (it is not part of the plugin):   npm install --prefix tests jsdom
const fs = require("fs");
const path = require("path");
const vm = require("vm");

function loadJsdom() {
  const tries = ["jsdom", path.join(__dirname, "node_modules", "jsdom")];
  if (process.env.CV_JSDOM) tries.unshift(process.env.CV_JSDOM);
  for (const t of tries) {
    try { return require(t); } catch (_) {}
  }
  return null;
}

const jsdom = loadJsdom();
if (!jsdom) {
  console.log("plugin preview: SKIPPED - the jsdom package is not installed (npm install --prefix tests jsdom)");
  process.exit(0);
}

// (CV_PLUGIN_DIR points the test at another copy of the plugin - used to prove that the test notices a broken one)
const PLUGIN_DIR = process.env.CV_PLUGIN_DIR || path.join(__dirname, "..", "CleanVinylPro2", "uxp-plugin");
const HTML = fs.readFileSync(path.join(PLUGIN_DIR, "index.html"), "utf8");
const MAIN_JS = fs.readFileSync(path.join(PLUGIN_DIR, "main.js"), "utf8");
const PLUGIN_VERSION = JSON.parse(fs.readFileSync(path.join(PLUGIN_DIR, "manifest.json"), "utf8")).version;
const SLIDER_PX = 200; // every slider is 200 px wide in this simulation -> value = clientX / 2 (Turbo: clientX)
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ------------------------------------------------------------------ the simulated Photoshop + server
function makeEnv(serverOpts = {}) {
  const dom = new jsdom.JSDOM(HTML, { runScripts: "outside-only", pretendToBeVisual: true, url: "http://localhost/" });
  const w = dom.window;
  const doc = w.document;
  const t0 = Date.now();
  const requests = [];
  const server = Object.assign({
    startDelay: 40,        // ms the first scan takes
    recomputeDelay: 120,   // ms one /session/recompute takes
    applyDelay: 120,
    quickAware: true,      // false = an older server build: ignores "quick" and does not report it
    failRecompute: 0,      // how many next recomputes answer with an error
    autoFractions: { fracFine: true, fracMed: true, fracLarge: true },
    version: PLUGIN_VERSION, // the version the server reports (another one = a server left running after an update)
    online: true,          // false = nothing answers on the port (the server is not running yet)
    bootMs: null,          // ms after the launch request (cleanvinyl2://start) until the server answers; null = never
    launches: 0,           // how many times the plugin asked Windows to start the server
    scene: null,           // what the server sees in the frame, e.g. { kind: "wide", framing: "wide", dark: false }
    startMaskShare: null,  // share of the frame that is green after the first scan
    maskShares: [],        // ...and after each following recompute
    frameSmoke: null,      // what the frame has of smoke, e.g. { share: 0.05, largest: 0.04, found: true }
    disk: null,            // files in the plugin's data folder, e.g. { "presets_local.json": [...] }; null = no disk
    oldSceneRule: false,   // true = a server before 4.5.0: a dark frame is offered the "dark" set only
    historyAware: true,    // false = a server before 4.5.0: no steps back / forward for the mask edits
    edits: { undo: 0, redo: 0 },  // the history of mask edits the server holds
    editDelays: [],        // ms the next mask edits take, one by one (then no delay)
    editSeq: 0,            // how many mask edits were answered (each answer carries its number in the picture)
    backupAware: true,     // false = a server before 4.5.0: no /backup/... addresses
    backupSaveFails: false,
    backupFolder: "D:\\Plugin Photoshop\\CleanVinylPro2\\backup",
    backups: [],           // the files of the backup folder, oldest first
    folderOpened: 0
  }, serverOpts);
  const W = 4, H = 6;

  const reply = (obj, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => obj, arrayBuffer: async () => new ArrayBuffer(0) });
  // What the engine says of smoke for the parameters `p` (the rule of engine.py: _smoke_auto, SMOKE_ALWAYS_FROM)
  function smokeAnswer(p) {
    if (!server.frameSmoke) return null;
    const on = !!p.smokeOn;
    const auto = on && !!p.smokeAuto && Number(p.smoke) < 95;
    const kept = on && (server.frameSmoke.found || !auto);
    return Object.assign({}, server.frameSmoke, { on, auto, protected: kept ? Math.round(server.frameSmoke.share * 12000) / 10000 : 0 });
  }
  function waitOrAbort(ms, signal) {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(resolve, ms);
      if (signal) {
        signal.addEventListener("abort", () => {
          clearTimeout(timer);
          const err = new Error("aborted");
          err.name = "AbortError";
          reject(err);
        });
      }
    });
  }

  w.fetch = async (url, init = {}) => {
    const u = new URL(url);
    const method = (init.method || "GET").toUpperCase();
    let body = null;
    if (typeof init.body === "string") {
      try { body = JSON.parse(init.body); } catch (_) { body = init.body; }
    } else if (init.body && u.pathname === "/session/start") {
      const bytes = new Uint8Array(init.body);
      const metaLen = new DataView(bytes.buffer, bytes.byteOffset, 4).getUint32(0, true);
      body = JSON.parse(Buffer.from(bytes.subarray(4, 4 + metaLen)).toString("utf8"));
    }
    const rec = { t: Date.now() - t0, method, path: u.pathname, body, done: false };
    if (u.pathname !== "/progress") requests.push(rec);
    try {
      switch (u.pathname) {
        case "/health":
          if (!server.online) throw new TypeError("Failed to fetch");
          return reply({ ok: true, status: "ready", app: "cleanvinylpro2", version: server.version, install_dir: "C:\\CleanVinylPro2", gpu: "Test GPU", provider: "CUDAExecutionProvider", models_loaded: true });
        case "/presets":
          return reply(method === "GET" ? { presets: [], source: "defaults" } : { ok: true });
        case "/settings":
          return reply(method === "GET" ? { exists: false } : { ok: true });
        case "/progress":
          return reply({ ok: true, pct: 50, stage: "…" });
        case "/session/start": {
          await waitOrAbort(server.startDelay, init.signal);
          // the automatic preset the way the engine does it: the set for this kind of frame replaces `params`
          let used = body.params;
          let scene = null;
          if (server.scene) {
            scene = Object.assign({ applied: null }, server.scene);
            // the rule of engine.py (start_session): a dark backdrop has its own sets by framing
            const keys = server.oldSceneRule
              ? [scene.kind, scene.framing, "default"]
              : (scene.dark ? ["dark_" + scene.framing, "dark"] : []).concat([scene.framing, "default"]);
            for (const key of keys) {
              if (body.scenePresets && body.scenePresets[key]) { used = body.scenePresets[key]; scene.applied = key; break; }
            }
          }
          rec.used = used;
          const ans = {
            ok: true, session_id: "sess-1", width: W, height: H, preview_w: W, preview_h: H,
            auto_fractions: used.autoFractions ? server.autoFractions : { fracFine: used.fracFine, fracMed: used.fracMed, fracLarge: used.fracLarge },
            orig_jpg_b64: "QQ==", comp_jpg_b64: "QQ==", overlay_jpg_b64: "QQ==", stats: {}
          };
          const smoke = smokeAnswer(used);
          if (smoke) {
            ans.smoke = smoke;
            if (scene) scene.smoke = smoke;
          }
          if (scene) ans.scene = scene;
          if (server.startMaskShare !== null) ans.mask_share = server.startMaskShare;
          return reply(ans);
        }
        case "/session/recompute": {
          await waitOrAbort(server.recomputeDelay, init.signal);
          if (server.failRecompute > 0) {
            server.failRecompute--;
            return reply({ ok: false, error: "test failure" }, 500);
          }
          const p = body.params;
          const ans = {
            ok: true, session_id: body.session_id,
            auto_fractions: p.autoFractions ? server.autoFractions : { fracFine: p.fracFine, fracMed: p.fracMed, fracLarge: p.fracLarge },
            comp_jpg_b64: "QQ==", overlay_jpg_b64: "QQ==", stats: {}
          };
          if (server.quickAware) ans.quick = !!body.quick && Number(p.cleanPasses || 1) < 2;
          if (server.maskShares.length) ans.mask_share = server.maskShares.shift();
          if (smokeAnswer(p)) ans.smoke = smokeAnswer(p);
          if (server.historyAware) ans.history = { undo: server.edits.undo, redo: server.edits.redo };
          return reply(ans);
        }
        case "/session/mask-edit": {
          if (server.editDelays.length) await waitOrAbort(server.editDelays.shift(), init.signal);
          // (the picture of every answer carries the number of the edit: the test sees which one is on screen)
          const pic = Buffer.from("edit-" + (++server.editSeq)).toString("base64");
          const ans = { ok: true, inverted: false, comp_jpg_b64: pic, overlay_jpg_b64: pic };
          if (server.historyAware) {
            const hist = server.edits;
            if (body.op === "undo" || body.op === "redo") {
              const from = body.op, to = body.op === "undo" ? "redo" : "undo";
              ans.stepped = hist[from] > 0;
              if (ans.stepped) { hist[from]--; hist[to]++; }
            } else if (["fill", "clear", "invert"].includes(body.op) || (body.op === "stroke" && body.points && body.points.length)) {
              hist.undo = Math.min(40, hist.undo + 1);
              hist.redo = 0;
            }
            ans.history = { undo: hist.undo, redo: hist.redo };
          }
          return reply(ans);
        }
        case "/session/dress-preview":
          return reply({ ok: true, inverted: false, comp_jpg_b64: "QQ==", overlay_jpg_b64: "QQ==" });
        case "/backup/save": {
          if (!server.backupAware) return reply({ detail: "Not Found" }, 404);
          if (server.backupSaveFails) return reply({ ok: false, error: "диск недоступний" }, 500);
          const nth = server.backups.length + 1;
          const label = String(body.label || "");
          const file = `CleanVinylPro2_backup_2026-11-19_08-${String(30 + nth).padStart(2, "0")}-00${label ? "_" + label : ""}.json`;
          server.backups.push({
            file, saved_at: `2026-11-19T08:${String(30 + nth).padStart(2, "0")}:00`, version: server.version, label,
            presets_list: JSON.parse(JSON.stringify(body.presets)), settings: JSON.parse(JSON.stringify(body.settings))
          });
          return reply({ ok: true, file, path: server.backupFolder + "\\" + file, folder: server.backupFolder,
            presets: body.presets.length, user_presets: body.presets.filter((x) => !x.builtin).length });
        }
        case "/backup/list": {
          if (!server.backupAware) return reply({ detail: "Not Found" }, 404);
          const found = server.backups.slice().reverse().map((b) => ({
            file: b.file, saved_at: b.saved_at, version: b.version, label: b.label, size: 1000,
            presets: b.presets_list.length, user_presets: b.presets_list.filter((x) => !x.builtin).length
          }));
          return reply({ ok: true, folder: server.backupFolder, backups: found });
        }
        case "/backup/read": {
          const b = server.backups.find((x) => x.file === (body && body.file));
          if (!b) return reply({ ok: false, error: "Такого бекапа в папці немає." }, 404);
          return reply({ ok: true, file: b.file, saved_at: b.saved_at, version: b.version, label: b.label, folder: server.backupFolder,
            presets: b.presets_list.length, presets_list: JSON.parse(JSON.stringify(b.presets_list)), settings: JSON.parse(JSON.stringify(b.settings)) });
        }
        case "/backup/open-folder":
          server.folderOpened++;
          return reply({ ok: true, folder: server.backupFolder, opened: true });
        case "/session/apply": {
          await waitOrAbort(server.applyDelay, init.signal);
          const meta = Buffer.from(JSON.stringify({ ok: true, width: W, height: H, channels: 4, bitDepth: 8, hasLayerMask: false, stats: {} }), "utf8");
          const out = new Uint8Array(4 + meta.length + W * H * 4);
          new DataView(out.buffer).setUint32(0, meta.length, true);
          out.set(meta, 4);
          return { ok: true, status: 200, json: async () => ({}), arrayBuffer: async () => out.buffer };
        }
        default:
          return reply({ ok: true });
      }
    } finally {
      rec.done = true;
      rec.tDone = Date.now() - t0;
    }
  };

  const layer = { id: 99, opacity: 100, visible: true, move: async () => {} };
  const psDoc = { id: 7, width: W, height: H, mode: "RGBColorMode", layers: [], createPixelLayer: async () => layer, createLayer: async () => layer };
  const stubs = {
    photoshop: {
      app: { documents: [psDoc], activeDocument: psDoc },
      core: { executeAsModal: async (fn) => fn({ hostControl: { suspendHistory: async () => 1, resumeHistory: async () => {} } }) },
      imaging: {
        getPixels: async () => ({ imageData: { width: W, height: H, components: 3, colorProfile: "sRGB", getData: async () => new Uint8Array(W * H * 3), dispose() {} } }),
        createImageDataFromBuffer: async () => ({ dispose() {} }),
        putPixels: async () => {},
        putLayerMask: async () => {}
      },
      action: { batchPlay: async () => [] },
      constants: { ElementPlacement: { PLACEBEFORE: "placeBefore" } }
    },
    uxp: {
      storage: {
        localFileSystem: {
          // the plugin's data folder: a plain object of file name -> content (what the plugin writes lands there too)
          getDataFolder: async () => {
            if (!server.disk) throw new Error("no disk in the test");
            return {
              getEntry: async (name) => {
                if (!(name in server.disk)) throw new Error("no such file: " + name);
                return { read: async () => JSON.stringify(server.disk[name]) };
              },
              createFile: async (name) => ({ write: async (text) => { server.disk[name] = JSON.parse(text); } })
            };
          }
        }
      },
      shell: {
        openExternal: async () => {
          server.launches++;
          if (server.bootMs !== null) setTimeout(() => { server.online = true; }, server.bootMs);
        }
      }
    }
  };
  w.require = (name) => stubs[name];

  // The big window: UXP's modal dialog is replaced by a promise that ends on close()
  const dlg = doc.getElementById("retouchModal");
  let closeModal = null;
  dlg.uxpShowModal = () => new Promise((resolve) => { closeModal = resolve; });
  dlg.close = (v) => { const r = closeModal; closeModal = null; if (r) r(v); };

  doc.querySelectorAll(".cv-slider").forEach((n) => {
    n.getBoundingClientRect = () => ({ left: 0, top: 0, right: SLIDER_PX, bottom: 10, width: SLIDER_PX, height: 10 });
  });
  // the photo fills this rectangle of the window (a press inside it is a brush / eraser stroke)
  doc.getElementById("dlgStage").getBoundingClientRect = () => ({ left: 0, top: 0, right: 400, bottom: 600, width: 400, height: 600 });

  const errors = [];
  w.addEventListener("error", (e) => errors.push(String(e.error || e.message)));
  w.addEventListener("unhandledrejection", (e) => errors.push("unhandled: " + String(e.reason)));
  // Run main.js the way a <script> tag does (its top-level let / const stay visible to the test afterwards)
  const ctx = dom.getInternalVMContext();
  const run = (code, filename) => new vm.Script(code, { filename }).runInContext(ctx);
  // The plugin's clock can be moved forward by a test (cvClockSkewMs) - to live through the 2.5 minutes the
  // plugin waits for a server that never starts.
  run("var cvClockSkewMs = 0; (function () { const real = Date.now.bind(Date); Date.now = () => real() + cvClockSkewMs; })();", "test-clock");
  run(MAIN_JS, "main.js");

  const el = (id) => {
    const n = doc.getElementById(id);
    if (!n) throw new Error("no element #" + id);
    return n;
  };
  const mouse = (target, type, x = 0) => target.dispatchEvent(new w.MouseEvent(type, { bubbles: true, cancelable: true, clientX: x, clientY: 5, button: 0 }));
  const env = {
    w, doc, server, requests, errors, el,
    state: (expr) => run(expr, "test-expression"),
    of: (p) => requests.filter((r) => r.path === p),
    recomputes: () => requests.filter((r) => r.path === "/session/recompute"),
    click: (id) => mouse(el(id), "click"),
    check: (id, on) => { el(id).checked = on; el(id).dispatchEvent(new w.Event("change", { bubbles: true })); },
    press: (id, x) => mouse(el(id), "mousedown", x),
    move: (x) => mouse(doc, "mousemove", x),
    release: () => mouse(doc, "mouseup"),
    // one whole drag of a slider: press, a few moves, release. `value` is in slider units (percent).
    async drag(id, value, stepMs = 15) {
      const max = id === "gSlTurbo" ? 200 : 100;
      const from = run(`getSliderVal(${JSON.stringify(id)})`, "test-expression");
      const px = (v) => (v / max) * SLIDER_PX;
      env.press(id, px(from));
      for (let i = 1; i <= 4; i++) {
        await sleep(stepMs);
        env.move(px(from + ((value - from) * i) / 4));
      }
      env.release();
    },
    progressCardVisible: () => el("dlgProgressOverlay").classList.contains("visible"),
    shown: (id) => el(id).style.display !== "none",
    // which of the three pictures is on screen: "original" | "result" | "mask"
    view() {
      const o = env.shown("dlgOrigImg"), c = env.shown("dlgCompImg"), m = env.shown("dlgOverlayImg");
      if (m && !c && !o) return "mask";
      if (o && !c && !m) return "original";
      if (c && !m) return "result";
      return `mixed(orig=${o}, comp=${c}, mask=${m})`;
    },
    modeBadge: () => (el("dlgModeBadge").classList.contains("visible") ? el("dlgModeBadge").textContent : ""),
    presetButton(name) {
      const btn = Array.from(doc.querySelectorAll("#dlgPresetsList .preset-btn")).find((b) => b.textContent.trim() === name);
      if (!btn) throw new Error("no preset named " + name);
      return btn;
    },
    clickPreset(name) { mouse(env.presetButton(name), "click"); },
    // a key pressed in the big window, e.g. key("KeyZ", "я", { ctrlKey: true }); `target` = the element that has the focus
    key(code, key, mods = {}, target = doc.body) {
      const ev = new w.KeyboardEvent("keydown", Object.assign({ bubbles: true, cancelable: true, code, key }, mods));
      target.dispatchEvent(ev);
      return ev;
    },
    edits: () => requests.filter((r) => r.path === "/session/mask-edit"),
    hint: () => el("dlgHoverHint").textContent,
    footer: () => (el("footerStatus").classList.contains("visible") ? el("footerStatus").textContent : ""),
    // the picture on screen: "edit-N" after the N-th mask edit the server answered, "" before any
    picture() {
      const src = String(el("dlgCompImg").src || "");
      const b64 = src.split("base64,")[1] || "";
      const text = Buffer.from(b64, "base64").toString("utf8");
      return text.startsWith("edit-") ? text : "";
    },
    async waitFor(cond, ms = 4000) {
      for (let waited = 0; waited < ms; waited += 20) {
        if (cond()) return true;
        await sleep(20);
      }
      return !!cond();
    },
    badge: () => (el("dlgPreviewBadge").classList.contains("visible") ? el("dlgPreviewBadge").textContent : ""),
    async open() {
      env.click("btnRun");
      for (let i = 0; i < 200 && !env.state("sessState.id"); i++) await sleep(10);
      if (!env.state("sessState.id")) throw new Error("the window did not open: " + el("footerStatus").textContent);
      await sleep(30);
    },
    async settle(ms = 900) { await sleep(ms); },
    // Close the big window, let the plugin finish what it was doing (requests, the settings-save timer), then
    // throw the simulated browser away.
    async close() {
      try { dlg.close("cancel"); } catch (_) {}
      for (let i = 0; i < 300 && (run("isBusy", "test-expression") || requests.some((r) => !r.done)); i++) await sleep(10);
      await sleep(450);
      w.close();
    }
  };
  return env;
}

// ------------------------------------------------------------------ the scenarios
const results = [];
let running = null; // the scenario whose simulated browser is alive: an error thrown by the plugin belongs to it
for (const kind of ["unhandledRejection", "uncaughtException"]) {
  process.on(kind, (err) => {
    if (running) running.problems.push(`${kind} in the plugin: ` + (err && err.stack ? err.stack : err));
  });
}

const ONLY = process.argv.slice(2);

async function scenario(name, serverOpts, fn) {
  if (ONLY.length && !ONLY.some((text) => name.includes(text))) return;
  const env = makeEnv(serverOpts);
  const rec = { name, problems: [] };
  const expect = (cond, text) => { if (!cond) rec.problems.push(text); };
  running = rec;
  try {
    await sleep(60); // bootstrap of the panel (health check, presets)
    await fn(env, expect);
    if (env.errors.length) rec.problems.push("script errors: " + env.errors.join(" | "));
  } catch (err) {
    rec.problems.push("crashed: " + (err && err.stack ? err.stack : err));
  }
  try {
    await env.close();
  } catch (err) {
    rec.problems.push("closing crashed: " + (err && err.stack ? err.stack : err));
  }
  running = null;
  results.push(rec);
  if (rec.problems.length) console.log("FAIL " + name + "\n   - " + rec.problems.join("\n   - "));
}

async function main() {
  await scenario("opening the window computes once and nothing afterwards", {}, async (env, expect) => {
    await env.open();
    await env.settle(1200);
    expect(env.of("/session/start").length === 1, "one /session/start expected");
    expect(env.recomputes().length === 0, `no recompute expected after opening, got ${env.recomputes().length}`);
    expect(env.badge() === "", "the preview badge must be hidden: " + env.badge());
    expect(!env.progressCardVisible(), "the progress card must be hidden after the scan");
  });

  await scenario("dragging a slider: nothing during the drag, one light refresh after the release", { recomputeDelay: 400 }, async (env, expect) => {
    await env.open();
    env.click("dlgBtnGear");
    env.press("gSlSpots", 150);
    for (let x = 152; x <= 170; x += 2) { await sleep(40); env.move(x); }   // 400 ms of dragging
    await sleep(500);                                                        // holding the mouse button, not moving
    expect(env.recomputes().length === 0, "a recompute was sent while the slider was still held");
    expect(env.badge() === "", "no 'refreshing' badge while the slider is held: " + env.badge());
    const tRelease = Date.now();
    env.release();
    await sleep(250);
    expect(env.recomputes().length === 0, "the refresh must wait a moment after the release");
    expect(env.badge().includes("Оновлюю"), "the badge must announce the coming refresh");
    await sleep(450);
    expect(env.recomputes().length === 1, `one recompute expected ~0.45 s after the release, got ${env.recomputes().length}`);
    const r = env.recomputes()[0];
    if (r) {
      expect(r.body.quick === true, "the refresh must be the light one (quick: true)");
      expect(r.body.jobId === undefined, "a light refresh has no progress job");
      expect(r.body.params.spots === 85, "spots must be 85, got " + r.body.params.spots);
      expect(r.body.preserve_edits === true, "brush edits must be kept");
    }
    expect(!env.progressCardVisible(), "the progress card must not appear for a light refresh");
    expect(env.el("dlgGearPopover").classList.contains("visible"), "the settings popover must stay open");
    await env.settle(700);
    expect(env.recomputes().length === 1, "exactly one recompute for one slider");
    expect(env.badge() === "", "the badge must disappear when the preview is up to date: " + env.badge());
    expect(env.state("previewMatchesSettings()") === true, "the preview must be marked as up to date");
    void tRelease;
  });

  await scenario("several sliders one after another give one refresh", {}, async (env, expect) => {
    await env.open();
    await env.drag("gSlSpots", 90);
    await sleep(200);
    await env.drag("gSlScuffs", 40);
    await sleep(200);
    await env.drag("gSlBlur", 30);
    await sleep(200);
    env.click("gBtnSeam");
    await env.settle(1000);
    const rs = env.recomputes();
    expect(rs.length === 1, `one recompute expected for 4 changes in a row, got ${rs.length}`);
    if (rs[0]) {
      const p = rs[0].body.params;
      expect(p.spots === 90 && p.scuffs === 40 && p.blur === 30 && p.seamOn === false, "the refresh must carry all four changes: " + JSON.stringify(p));
      expect(rs[0].body.quick === true, "light refresh expected");
    }
  });

  await scenario("a new drag puts off the refresh that was waiting", {}, async (env, expect) => {
    await env.open();
    await env.drag("gSlSpots", 90);
    await sleep(200);                       // the refresh for the first slider would start in 250 ms...
    env.press("gSlScuffs", 130);            // ...but the next slider is already being dragged
    for (let i = 1; i <= 8; i++) { await sleep(100); env.move(130 - i * 5); }
    expect(env.recomputes().length === 0, `nothing may be computed while the second slider is held, got ${env.recomputes().length}`);
    env.release();
    await env.settle(900);
    const rs = env.recomputes();
    expect(rs.length === 1, `one recompute expected after the second release, got ${rs.length}`);
    if (rs[0]) expect(rs[0].body.params.spots === 90 && rs[0].body.params.scuffs === 45, "both values in one refresh: " + JSON.stringify(rs[0].body.params));
  });

  await scenario("a slider moved while a refresh is running gives exactly one more refresh", { recomputeDelay: 900 }, async (env, expect) => {
    await env.open();
    await env.drag("gSlSpots", 90);
    await sleep(700);                       // the first refresh is on its way now
    expect(env.recomputes().length === 1, "first refresh expected");
    await env.drag("gSlCyc", 60);           // changed while the server is busy
    await env.settle(3200);
    const rs = env.recomputes();
    expect(rs.length === 2, `two recomputes expected, got ${rs.length}`);
    if (rs[1]) {
      expect(rs[1].body.params.spots === 90 && rs[1].body.params.cycCurve === 60, "the second refresh must carry both values");
      expect(rs[1].t >= rs[0].tDone, "the second refresh must start after the first one has answered");
    }
    expect(env.state("previewMatchesSettings()") === true, "the preview must end up to date");
  });

  await scenario("a slider returned to its value, Blend and Clothing sliders do not recompute", {}, async (env, expect) => {
    await env.open();
    env.press("gSlSpots", 150); await sleep(20); env.move(180); await sleep(20); env.move(150); env.release();
    await env.drag("dlgSlBlend", 50);
    env.click("gBtnDress");
    await env.drag("gSlDress", 80);
    await env.settle(900);
    expect(env.recomputes().length === 0, `no recompute expected, got ${env.recomputes().length}`);
    expect(env.of("/session/dress-preview").length >= 1, "the clothing slider must still use its own instant preview");
  });

  await scenario("switches and fraction buttons refresh the light way", {}, async (env, expect) => {
    await env.open();
    env.check("gChkRemoveStands", true);
    await env.settle(600);
    env.click("dlgFracFine");
    await env.settle(600);
    env.check("dlgChkSmoke", true);
    await env.settle(600);
    const rs = env.recomputes();
    expect(rs.length === 3, `three recomputes expected, got ${rs.length}`);
    expect(rs.every((r) => r.body.quick === true), "all three must be light");
    if (rs.length === 3) {
      expect(rs[0].body.params.removeStands === true, "stands removal must be on in the first");
      expect(rs[1].body.params.fracFine === false && rs[1].body.params.autoFractions === false, "fine fraction off, auto off in the second");
      expect(rs[0].body.params.smokeOn === false && rs[1].body.params.smokeOn === false, "smoke protection is off until it is asked for");
      expect(rs[2].body.params.smokeOn === true, "smoke protection on in the third");
    }
    env.click("dlgFracAuto");               // AUTO again: the settings look the same, the server must still be asked
    await env.settle(600);
    expect(env.recomputes().length === 4 && env.recomputes()[3].body.params.autoFractions === true, "AUTO must ask the server once more");
    expect(env.state("fracFine") === true, "the fractions chosen by the server must be shown");
    await env.settle(800);
    expect(env.recomputes().length === 4, "no further recompute after AUTO was answered");
  });

  await scenario("the 'exact preview' button recomputes in full, with the progress card", { recomputeDelay: 300 }, async (env, expect) => {
    await env.open();
    env.click("dlgBtnGear");
    env.click("gBtnRecompute");
    await sleep(150);
    expect(env.progressCardVisible(), "the progress card must be shown for a full recompute");
    await env.settle(700);
    const rs = env.recomputes();
    expect(rs.length === 1, `one recompute expected, got ${rs.length}`);
    expect(rs.every((r) => r.body.quick === undefined && typeof r.body.jobId === "string"), "it must be a full recompute with a progress job");
    if (rs[0]) expect(rs[0].body.params.speedMode === "quality", "the full AI fill must be asked for");
    expect(!env.progressCardVisible(), "the progress card must be hidden afterwards");
    expect(!env.el("dlgGearPopover").classList.contains("visible"), "the exact preview closes the settings popover");
    expect(env.badge() === "", "badge hidden: " + env.badge());
  });

  await scenario("2 passes: sliders do not start anything by themselves", {}, async (env, expect) => {
    await env.open();
    env.click("gPass2");
    await env.settle(700);
    expect(env.recomputes().length === 0, "choosing 2 passes must not start a full recompute by itself");
    expect(env.badge().includes("2×"), "the badge must explain the 2-pass case: " + env.badge());
    await env.drag("gSlSpots", 95);
    await env.settle(900);
    expect(env.recomputes().length === 0, "a slider must not start a full recompute with 2 passes");
    env.click("dlgFracMed");                // these buttons always recomputed at once - they still do, in full
    await env.settle(500);
    expect(env.recomputes().length === 1 && env.recomputes()[0].body.quick === undefined, "a fraction button recomputes in full with 2 passes");
    expect(env.badge() === "", "badge hidden after the full recompute: " + env.badge());
    env.click("gPass1");
    await env.settle(700);
    expect(env.recomputes().length === 2 && env.recomputes()[1].body.quick === true, "back to 1 pass: light refresh");
  });

  await scenario("an older server build: asked once, then never again after every slider", { quickAware: false }, async (env, expect) => {
    await env.open();
    await env.drag("gSlSpots", 90);
    await env.settle(900);
    expect(env.recomputes().length === 1, "first refresh expected");
    expect(env.state("sessState.quickUnsupported") === true, "the plugin must notice the older server");
    expect(env.el("dlgHoverHint").textContent.includes("restart_gpu_server.bat"), "the hint must tell to restart the server");
    await env.drag("gSlSpots", 60);
    await env.settle(900);
    expect(env.recomputes().length === 1, "no automatic recompute against an older server");
    expect(env.badge().includes("restart_gpu_server.bat"), "the badge must tell to restart the server: " + env.badge());
  });

  await scenario("'Застосувати' right after a slider: no refresh, the settings travel with Apply", {}, async (env, expect) => {
    await env.open();
    await env.drag("gSlSpots", 95);
    await sleep(100);                        // sooner than the refresh would start
    env.click("dlgBtnApply");
    await env.settle(900);
    expect(env.recomputes().length === 0, `no recompute expected, got ${env.recomputes().length}`);
    const a = env.of("/session/apply");
    expect(a.length === 1, "one /session/apply expected");
    if (a[0]) {
      expect(a[0].body.params && a[0].body.params.spots === 95, "Apply must carry the current slider values");
      expect(a[0].body.params && a[0].body.params.autoFractions === true, "Apply must say whether fractions are automatic");
      expect(typeof a[0].body.jobId === "string", "Apply keeps its progress job");
    }
    expect(env.state("sessState.open") === false, "the window must close after Apply");
    expect(env.of("/session/close").length === 1, "the session must be closed on the server");
    expect(env.el("footerStatus").className.includes("error") === false, "no error expected: " + env.el("footerStatus").textContent);
  });

  await scenario("'Застосувати' while a light refresh is running keeps its progress card", { recomputeDelay: 600, applyDelay: 1400 }, async (env, expect) => {
    await env.open();
    await env.drag("gSlSpots", 95);
    await sleep(720);                        // the refresh is on its way
    expect(env.recomputes().length === 1 && !env.recomputes()[0].done, "the light refresh must be running");
    env.click("dlgBtnApply");
    await sleep(800);                        // the refresh has answered, Apply is still running
    expect(env.recomputes()[0].done, "the refresh must have answered by now");
    expect(env.progressCardVisible(), "the progress card of Apply must stay visible");
    await env.settle(1200);
    expect(env.recomputes().length === 1, "no extra recompute");
    expect(env.of("/session/apply").length === 1 && env.of("/session/apply")[0].body.params.spots === 95, "Apply carries the values");
    expect(env.state("sessState.open") === false, "the window must close after Apply");
  });

  await scenario("a failed light refresh is not retried in a loop", { failRecompute: 1 }, async (env, expect) => {
    await env.open();
    await env.drag("gSlSpots", 95);
    await env.settle(1800);
    expect(env.recomputes().length === 1, `one attempt expected, got ${env.recomputes().length}`);
    expect(env.badge().includes("не оновився"), "the badge must say the preview was not refreshed: " + env.badge());
    await env.drag("gSlSpots", 90);
    await env.settle(900);
    expect(env.recomputes().length === 2, "the next change tries again");
    expect(env.badge() === "", "badge hidden after a good refresh: " + env.badge());
  });

  await scenario("sliders moved during the first scan are picked up after it", { startDelay: 500 }, async (env, expect) => {
    env.click("btnRun");
    await sleep(150);
    await env.drag("gSlBlur", 40);          // the scan is still running
    for (let i = 0; i < 200 && !env.state("sessState.id"); i++) await sleep(10);
    await env.settle(900);
    const rs = env.recomputes();
    expect(env.of("/session/start")[0].body.params.blur === 0, "the scan was started with the old value");
    expect(rs.length === 1 && rs[0].body.quick === true && rs[0].body.params.blur === 40, "one light refresh with the new value expected");
    expect(!env.progressCardVisible(), "the progress card of the scan must be hidden");
  });

  await scenario("closing the window drops a refresh that was waiting", {}, async (env, expect) => {
    await env.open();
    await env.drag("gSlSpots", 95);
    await sleep(100);
    env.click("dlgBtnCancel");
    await env.settle(900);
    expect(env.recomputes().length === 0, "no recompute after the window was closed");
    expect(env.of("/session/apply").length === 0, "nothing was applied");
    expect(env.of("/session/close").length === 1, "the session must be closed on the server");
  });

  await scenario("'Скасувати' on the progress card stops a full recompute and keeps the window", { recomputeDelay: 800 }, async (env, expect) => {
    await env.open();
    env.click("dlgBtnGear");
    env.click("gBtnRecompute");
    await sleep(200);
    env.click("dlgBtnCancelScan");
    await env.settle(1000);
    expect(env.state("sessState.open") === true && env.state("sessState.recomputing") === false, "the window stays open, nothing is running");
    expect(!env.progressCardVisible(), "the progress card must be hidden");
    await env.drag("gSlSpots", 95);          // the window keeps working
    await env.settle(1600);
    expect(env.recomputes().length === 2 && env.recomputes()[1].body.quick === true, "the next slider refreshes the light way");
    expect(env.badge() === "", "badge hidden: " + env.badge());
  });

  await scenario("brush stroke while a light refresh is running", { recomputeDelay: 500 }, async (env, expect) => {
    await env.open();
    await env.drag("gSlSpots", 95);
    await sleep(600);
    env.click("dlgToolInvert");              // any mask edit: allowed while the refresh is on its way
    await env.settle(900);
    expect(env.recomputes().length === 1, "one refresh");
    expect(env.of("/session/mask-edit").length === 1, "the mask edit was sent");
    expect(!env.progressCardVisible(), "no progress card");
  });

  // ---------------------------------------------------------------- the three views of the photo
  await scenario("the window opens with the cleaned photo; 'До / Після' and 'Маска' switch the views", {}, async (env, expect) => {
    await env.open();
    expect(env.view() === "result", "the window must open with the cleaned photo, got " + env.view());
    expect(env.modeBadge().includes("ПІСЛЯ"), "the corner label must say ПІСЛЯ: " + env.modeBadge());
    env.click("dlgBtnBeforeAfter");
    expect(env.view() === "original", "'До / Після' must show the original, got " + env.view());
    expect(env.el("dlgBtnBeforeAfter").classList.contains("active"), "'До / Після' must be lit while the original is shown");
    expect(env.modeBadge().includes("ДО"), "the corner label must say ДО: " + env.modeBadge());
    env.click("dlgBtnBeforeAfter");
    expect(env.view() === "result", "'До / Після' again must show the cleaned photo, got " + env.view());
    expect(!env.el("dlgBtnBeforeAfter").classList.contains("active"), "'До / Після' must not stay lit");
    env.click("dlgBtnMask");
    expect(env.view() === "mask" && env.el("dlgBtnMask").classList.contains("active"), "'Маска' must show the red/green mask, got " + env.view());
    expect(env.modeBadge().includes("МАСКА"), "the corner label must say МАСКА: " + env.modeBadge());
    env.click("dlgBtnBeforeAfter");
    expect(env.view() === "original" && !env.el("dlgBtnMask").classList.contains("active"), "'До / Після' from the mask must show the original, got " + env.view());
    env.click("dlgBtnBeforeAfter");
    expect(env.view() === "result", "...and then the cleaned photo, never the mask; got " + env.view());
    env.click("dlgBtnMask");
    env.click("dlgBtnMask");
    expect(env.view() === "result" && !env.el("dlgBtnMask").classList.contains("active"), "'Маска' again must return to the cleaned photo");
    expect(env.recomputes().length === 0, "switching views must not ask the server for anything");
    await env.close();                                       // the next opening starts with the cleaned photo again
  });

  await scenario("a brush stroke shows the mask by itself; holding outside the photo lifts it", {}, async (env, expect) => {
    await env.open();
    expect(env.view() === "result", "cleaned photo first");
    env.press("dlgViewport", 100);                           // inside the photo, the eraser is the tool on start
    expect(env.view() === "mask", "a stroke edits the mask, so the mask must appear; got " + env.view());
    env.move(120);
    env.release();
    await env.settle(200);
    const edits = env.of("/session/mask-edit");
    expect(edits.length === 1 && edits[0].body.op === "stroke" && edits[0].body.erase === true, "the eraser stroke must reach the server");
    env.press("dlgViewport", 900);                           // outside the photo: a look at the clean result
    expect(env.view() === "result", "holding outside the photo must lift the mask, got " + env.view());
    env.release();
    expect(env.view() === "mask", "...and the mask is back after the release, got " + env.view());
    env.click("dlgBtnMask");
    expect(env.view() === "result", "'Маска' switches it off");
    env.click("dlgToolBrush");
    expect(env.view() === "mask" && env.state("sessState.tool") === "brush", "picking the brush shows the mask");
  });

  // ---------------------------------------------------------------- presets
  await scenario("a preset click: one light refresh with that preset's values, and a note about what changed",
    { startMaskShare: 0.005, maskShares: [0.023] }, async (env, expect) => {
      env.check("dlgChkAutoPreset", false);
      await env.open();
      env.click("dlgBtnPresets");
      env.clickPreset("Темний ключ");
      expect(env.el("dlgActivePresetName").textContent === "Темний ключ", "the button must show the clicked preset");
      expect(!env.el("dlgPresetsPopover").classList.contains("visible"), "the list must close");
      await env.settle(900);
      const rc = env.recomputes();
      expect(rc.length === 1, `one recompute expected, got ${rc.length}`);
      if (rc[0]) {
        const p = rc[0].body.params;
        expect(rc[0].body.quick === true, "the refresh must be the light one");
        expect(p.spots === 80 && p.scuffs === 55 && p.seam === 90 && p.edge === 78 && p.smoke === 70 && p.grain === 95 && p.cycCurve === 65,
          "the values of 'Темний ключ' must be sent, got " + JSON.stringify(p));
        expect(p.autoFractions === true, "AUTO stays on for a preset with all three fractions");
      }
      expect(env.badge().includes("Темний ключ") && env.badge().includes("2,3 %") && env.badge().includes("0,50 %"),
        "the note must name the preset and both shares: " + env.badge());
      expect(!env.progressCardVisible(), "no progress card for a preset");
      env.click("dlgBtnPresets");
      env.clickPreset("Темний ключ");                        // the same preset once more: nothing to compute
      await env.settle(700);
      expect(env.recomputes().length === 1, "the preset that is already on screen must not recompute");
      expect(env.badge().includes("ті самі"), "...and the note must say so: " + env.badge());
    });

  await scenario("a preset that names its fractions switches AUTO off; the next preset gives AUTO back", {}, async (env, expect) => {
    env.check("dlgChkAutoPreset", false);
    await env.open();
    expect(env.el("dlgFracAuto").classList.contains("active"), "AUTO is on at the start");
    env.clickPreset("Ближній план");
    await env.settle(800);
    let p = env.recomputes()[0] && env.recomputes()[0].body.params;
    expect(p && p.autoFractions === false && p.fracLarge === false && p.fracFine === true && p.fracMed === true,
      "'Ближній план' must be sent with its own fractions (no large one) and AUTO off: " + JSON.stringify(p));
    expect(!env.el("dlgFracAuto").classList.contains("active") && !env.el("dlgFracLarge").classList.contains("active"),
      "the AUTO and the large-fraction buttons must be off");
    env.clickPreset("Делікатний (точки)");
    await env.settle(800);
    p = env.recomputes()[1] && env.recomputes()[1].body.params;
    expect(p && p.autoFractions === false && p.fracFine === true && p.fracMed === false && p.fracLarge === false,
      "'Делікатний' must clean the fine fraction only: " + JSON.stringify(p));
    env.clickPreset("Студія (Стандарт)");
    await env.settle(800);
    p = env.recomputes()[2] && env.recomputes()[2].body.params;
    expect(p && p.autoFractions === true, "AUTO must be back with a preset that does not name fractions: " + JSON.stringify(p));
    expect(env.el("dlgFracAuto").classList.contains("active"), "the AUTO button must be lit again");
    expect(env.recomputes().length === 3, "three presets, three refreshes; got " + env.recomputes().length);
    env.click("dlgFracAuto");                                // the user switches AUTO off himself...
    env.clickPreset("Дальній план");
    await env.settle(800);
    p = env.recomputes()[3] && env.recomputes()[3].body.params;
    expect(p && p.autoFractions === false, "...then presets leave it off: " + JSON.stringify(p));
  });

  await scenario("what a preset would send equals what the controls send once it is applied (all presets)", {}, async (env, expect) => {
    const bad = env.state(`(function () {
      const out = [];
      const sorted = (o) => JSON.stringify(Object.keys(o).sort().map((k) => [k, o[k]]));
      presetsList.forEach((p) => {
        const before = presetRequestParams(p);
        applyPreset(p);
        const after = Object.assign(readCurrentConfig(), { autoFractions: fracAuto });
        if (sorted(before) !== sorted(after)) out.push(p.id + ": " + sorted(before) + " vs " + sorted(after));
      });
      const odd = { id: "odd", builtin: false, cfg: { spots: 500, master: 20, blur: -4, cleanPasses: 7, fracAuto: false } };
      const b2 = presetRequestParams(odd);
      applyPreset(odd);
      const a2 = Object.assign(readCurrentConfig(), { autoFractions: fracAuto });
      if (sorted(b2) !== sorted(a2)) out.push("odd: " + sorted(b2) + " vs " + sorted(a2));
      if (a2.spots !== 100 || a2.master !== 100 || a2.blur !== 0 || a2.cleanPasses !== 2 || a2.autoFractions !== false) out.push("limits: " + sorted(a2));
      return out.join(" || ");
    })()`);
    expect(bad === "", "differences: " + bad);
    expect(env.state("presetsList.length") >= 8, "the built-in presets must be loaded");
  });

  // ---------------------------------------------------------------- the automatic preset
  await scenario("automatic preset: the presets travel with the photo, the server's choice lands on the controls",
    { scene: { kind: "wide", framing: "wide", dark: false }, startMaskShare: 0.01 }, async (env, expect) => {
      await env.open();
      await env.settle(900);
      const start = env.of("/session/start")[0];
      const sp = start.body.scenePresets || {};
      expect(Object.keys(sp).sort().join() === "close,dark,dark_close,dark_medium,dark_wide,default,medium,wide", "eight sets must be sent, got " + Object.keys(sp).sort().join());
      expect(sp.wide && sp.wide.spots === 85 && sp.wide.scuffs === 78 && sp.wide.edge === 66 && sp.wide.speedMode === "quality" && sp.wide.autoFractions === true,
        "the 'wide' set must be the preset 'Дальній план': " + JSON.stringify(sp.wide));
      expect(sp.dark && sp.dark.spots === 80 && sp.close && sp.close.fracLarge === false && sp.close.autoFractions === false && sp.default && sp.default.spots === 75,
        "the other sets must be 'Темний ключ', 'Ближній план', 'Студія'");
      expect(sp.dark_wide && sp.dark_wide.cycCurve === 65 && sp.dark_medium && sp.dark_medium.spots === 72 && sp.dark_medium.edge === 82 &&
        sp.dark_close && sp.dark_close.fracLarge === false && sp.dark_close.autoFractions === false && sp.dark_close.seamOn === false,
        "...and the three dark presets by framing: " + JSON.stringify([sp.dark_wide, sp.dark_medium, sp.dark_close]));
      expect(Object.keys(sp).every((k) => sp[k].smokeOn === false), "no set asks for smoke protection");
      expect(env.state("activePresetId") === "wide_shot", "the active preset must be 'Дальній план', got " + env.state("activePresetId"));
      expect(env.el("dlgActivePresetName").textContent === "Дальній план", "the button must show it");
      expect(env.state("getSliderVal('gSlSpots')") === 85 && env.state("getSliderVal('gSlScuffs')") === 78, "the sliders must show its values");
      expect(env.recomputes().length === 0, `the frame was already cleaned with this preset: no recompute, got ${env.recomputes().length}`);
      expect(env.state("previewMatchesSettings()") === true, "the preview must count as up to date");
      expect(env.badge().includes("Авто-пресет") && env.badge().includes("Дальній план") && env.badge().includes("повний зріст"),
        "the note must say what was picked and why: " + env.badge());
      expect(env.view() === "result", "cleaned photo on screen");
      env.click("dlgBtnPresets");
      env.clickPreset("Студія (Стандарт)");                  // a manual choice still works afterwards
      await env.settle(800);
      expect(env.recomputes().length === 1 && env.recomputes()[0].body.params.spots === 75, "a manual choice must refresh with its values");
      expect(env.state("activePresetId") === "std", "...and become the active preset");
    });

  await scenario("automatic preset for a close-up: the preset's own fractions are used, AUTO steps aside",
    { scene: { kind: "close", framing: "close", dark: false }, autoFractions: { fracFine: true, fracMed: true, fracLarge: true } }, async (env, expect) => {
      await env.open();
      await env.settle(600);
      expect(env.state("activePresetId") === "closeup", "active preset: " + env.state("activePresetId"));
      expect(!env.el("dlgFracAuto").classList.contains("active"), "AUTO must be off for this preset");
      expect(env.el("dlgFracFine").classList.contains("active") && env.el("dlgFracMed").classList.contains("active") && !env.el("dlgFracLarge").classList.contains("active"),
        "fine + medium on, large off");
      expect(env.recomputes().length === 0, "no recompute after the opening");
      expect(env.state("previewMatchesSettings()") === true, "the preview must count as up to date");
      await env.close();
    });

  await scenario("automatic preset: a dark frame takes the dark preset of its framing",
    { scene: { kind: "dark", framing: "wide", dark: true } }, async (env, expect) => {
      await env.open();
      await env.settle(600);
      const start = env.of("/session/start")[0];
      expect(env.state("activePresetId") === "lowkey_wide", "a dark full-length frame must take 'Темний дальній план', got " + env.state("activePresetId"));
      expect(start.used && start.used.spots === 80 && start.used.cycCurve === 65 && start.used.smokeOn === false, "...and be cleaned with its values: " + JSON.stringify(start.used));
      expect(env.el("dlgActivePresetName").textContent === "Темний дальній план", "the button must show it: " + env.el("dlgActivePresetName").textContent);
      expect(env.badge().includes("Темний дальній план") && env.badge().includes("темний фон") && env.badge().includes("повний зріст"),
        "the note must name the preset, the dark backdrop and the framing: " + env.badge());
      expect(env.recomputes().length === 0 && env.state("previewMatchesSettings()") === true, "the frame is already cleaned with this preset");
    });

  for (const [framing, id, name] of [["close", "lowkey_close", "Темний ближній план"], ["medium", "lowkey_medium", "Темний середній план"], ["none", "lowkey", "Темний ключ"]]) {
    await scenario(`automatic preset: a dark frame, framing '${framing}' -> '${name}'`, { scene: { kind: "dark", framing, dark: true } }, async (env, expect) => {
      await env.open();
      await env.settle(500);
      expect(env.state("activePresetId") === id, `expected ${id}, got ` + env.state("activePresetId"));
      expect(env.badge().includes(name) && env.badge().includes("темний фон"), "the note: " + env.badge());
      if (framing === "close") expect(!env.el("dlgFracAuto").classList.contains("active") && !env.el("dlgFracLarge").classList.contains("active"), "the dark close-up names its fractions: no large one, AUTO off");
    });
  }

  await scenario("automatic preset: deleted dark presets fall back - the general dark one, then the framing, then 'Студія'",
    { scene: { kind: "dark", framing: "wide", dark: true } }, async (env, expect) => {
      env.state("presetsList = presetsList.filter((p) => p.id !== 'lowkey_wide'); renderPresets();");
      await env.open();
      await env.settle(500);
      let sp = env.of("/session/start")[0].body.scenePresets || {};
      expect(!sp.dark_wide && sp.dark, "a deleted preset must not be offered: " + Object.keys(sp).join());
      expect(env.state("activePresetId") === "lowkey", "without 'Темний дальній план' the general dark preset is used, got " + env.state("activePresetId"));
      env.el("retouchModal").close("cancel");
      await env.waitFor(() => env.state("isBusy") === false);
      env.state("presetsList = presetsList.filter((p) => !p.id.startsWith('lowkey') && p.id !== 'wide_shot'); renderPresets();");
      await env.open();
      await env.settle(500);
      sp = env.of("/session/start")[1].body.scenePresets || {};
      expect(Object.keys(sp).sort().join() === "close,default,medium", "only the presets that are left are offered: " + Object.keys(sp).sort().join());
      expect(env.state("activePresetId") === "std", "the last fallback is 'Студія', got " + env.state("activePresetId"));
      expect(env.badge().includes("Студія") && env.badge().includes("темний фон"), "the note: " + env.badge());
    });

  await scenario("automatic preset with a server of an older version: a dark frame gets the general dark preset, nothing breaks",
    { scene: { kind: "dark", framing: "wide", dark: true }, oldSceneRule: true }, async (env, expect) => {
      await env.open();
      await env.settle(500);
      expect(env.state("activePresetId") === "lowkey", "expected 'Темний ключ', got " + env.state("activePresetId"));
      expect(env.recomputes().length === 0 && env.state("previewMatchesSettings()") === true, "the frame counts as cleaned with it");
    });

  await scenario("automatic preset switched off: nothing is offered, the chosen preset stays", { scene: { kind: "wide", framing: "wide", dark: false } }, async (env, expect) => {
    env.check("dlgChkAutoPreset", false);
    env.state("applyPreset(presetsList.find((p) => p.id === 'smoke')); renderPresets();");
    await env.open();
    await env.settle(600);
    const start = env.of("/session/start")[0];
    expect(start.body.scenePresets === undefined, "no presets may be sent when the automatic choice is off");
    expect(start.body.params.smoke === 95, "the chosen preset's values are sent");
    expect(env.state("activePresetId") === "smoke", "the chosen preset stays");
    expect(env.badge() === "", "no note: " + env.badge());
    expect(env.recomputes().length === 0, "no recompute");
  });

  await scenario("sliders touched during the first scan win over the automatic preset", { startDelay: 500, scene: { kind: "wide", framing: "wide", dark: false } }, async (env, expect) => {
    env.click("btnRun");
    await sleep(150);
    await env.drag("gSlSpots", 40);
    await env.waitFor(() => env.state("sessState.id"));
    await env.settle(1200);
    expect(env.state("activePresetId") === "std", "the preset must not be swapped under the user's hand, got " + env.state("activePresetId"));
    expect(env.state("getSliderVal('gSlSpots')") === 40, "the user's value stays");
    expect(env.recomputes().length === 1 && env.recomputes()[0].body.params.spots === 40, "one refresh for the user's values");
    expect(env.state("previewMatchesSettings()") === true, "the preview is up to date afterwards");
  });

  await scenario("a server of another version left running: the panel says how to restart it", { version: "4.2.0" }, async (env, expect) => {
    const text = env.el("statusBanner").classList.contains("visible") ? env.el("statusBannerText").textContent : "";
    expect(text.includes("4.2.0") && text.includes(PLUGIN_VERSION) && text.includes("restart_gpu_server.bat"), "the banner must name both versions and the file to run: " + text);
    expect(env.state("serverOnline") === true, "the older server is still used");
    await env.open();                                        // ...and the window still works with it
    expect(env.view() === "result", "the window opens");
  });

  await scenario("a server of the same version: no banner", {}, async (env, expect) => {
    expect(!env.el("statusBanner").classList.contains("visible"), "no banner expected: " + env.el("statusBannerText").textContent);
    expect(env.state("PLUGIN_VERSION") === PLUGIN_VERSION, `main.js says ${env.state("PLUGIN_VERSION")}, manifest.json says ${PLUGIN_VERSION}`);
  });

  // ---------------------------------------------------------------- a press made before the server is ready
  await scenario("'Очистити фон' pressed while the server is starting is remembered and runs by itself",
    { online: false, bootMs: 1700 }, async (env, expect) => {
      expect(env.server.launches === 1, "the panel must ask for the server once on opening, got " + env.server.launches);
      env.click("btnRun");
      await sleep(300);
      expect(env.el("btnRun").textContent.includes("Чекаю на сервер"), "the button must say it is waiting: " + env.el("btnRun").textContent.trim());
      expect(env.el("footerStatus").textContent.includes("почнеться само"), "the panel must explain: " + env.el("footerStatus").textContent);
      expect(env.of("/session/start").length === 0, "nothing can start before the server answers");
      expect(!env.el("serverErrorCard").classList.contains("visible"), "no error while the server is still starting");
      const opened = await env.waitFor(() => env.state("sessState.id"), 6000);
      expect(opened, "the window must open by itself once the server answers: " + env.el("footerStatus").textContent);
      expect(env.of("/session/start").length === 1, "exactly one scan, got " + env.of("/session/start").length);
      expect(env.server.launches === 1, "the server must not be launched a second time, got " + env.server.launches);
      expect(env.el("btnRun").textContent.trim() === "Очистити фон", "the button text must be back: " + env.el("btnRun").textContent.trim());
      expect(!env.el("btnRun").classList.contains("waiting"), "the waiting look must be gone");
      expect(!env.el("serverErrorCard").classList.contains("visible"), "no error card");
      expect(env.el("gpuStatusText").textContent.includes("Test GPU"), "the status must show the GPU: " + env.el("gpuStatusText").textContent);
    });

  await scenario("the status turns green by itself after a slow start, without any press", { online: false, bootMs: 2300 }, async (env, expect) => {
    await sleep(1200);
    expect(env.state("serverOnline") === false && env.el("gpuStatusText").textContent.includes("Запуск"), "still starting: " + env.el("gpuStatusText").textContent);
    expect(env.el("btnPlayServer").style.display === "none", "no ▶ button while the start is in progress");
    const up = await env.waitFor(() => env.state("serverOnline") === true, 5000);
    expect(up, "the plugin must notice the server by itself");
    expect(env.el("gpuStatusBtn").className === "gpu-pill", "the status must be green: " + env.el("gpuStatusBtn").className);
    expect(env.of("/session/start").length === 0, "nothing opens by itself when no button was pressed");
    expect(env.server.launches === 1, "one launch");
  });

  await scenario("pressing the waiting button again takes the press back", { online: false, bootMs: 1500 }, async (env, expect) => {
    env.click("btnRun");
    await sleep(250);
    expect(env.el("btnRun").classList.contains("waiting"), "waiting");
    env.click("btnRun");
    await sleep(100);
    expect(!env.el("btnRun").classList.contains("waiting") && env.el("btnRun").textContent.trim() === "Очистити фон", "the button must be back to normal");
    expect(env.el("footerStatus").textContent.includes("Скасовано"), "the panel must confirm: " + env.el("footerStatus").textContent);
    await env.waitFor(() => env.state("serverOnline") === true, 5000);
    await sleep(400);
    expect(env.of("/session/start").length === 0, "a press that was taken back must not run");
    expect(env.state("sessState.open") === false && env.state("isBusy") === false, "nothing is open");
    env.click("btnRun");                                     // and the button works as usual afterwards
    expect(await env.waitFor(() => env.state("sessState.id"), 3000), "a new press opens the window");
  });

  await scenario("another button pressed while waiting replaces the remembered press", { online: false, bootMs: 1500 }, async (env, expect) => {
    env.click("btnRun");
    await sleep(200);
    env.click("btnFormat57");
    await sleep(200);
    expect(!env.el("btnRun").classList.contains("waiting") && env.el("btnFormat57").classList.contains("waiting"), "only the last pressed button waits");
    await env.waitFor(() => env.of("/extend-canvas").length > 0, 5000);
    await sleep(300);
    expect(env.of("/extend-canvas").length === 1 && env.of("/session/start").length === 0, "the last press runs, the first one does not");
  });

  await scenario("the document changed while the server was starting: the remembered press is dropped", { online: false, bootMs: 1200 }, async (env, expect) => {
    env.click("btnRun");
    await sleep(200);
    env.state("require('photoshop').app.activeDocument = { id: 8, mode: 'RGBColorMode', layers: [] }");
    await env.waitFor(() => env.state("serverOnline") === true, 5000);
    await sleep(400);
    expect(env.of("/session/start").length === 0, "another document must not be scanned by a press made for the first one");
    expect(env.el("footerStatus").textContent.includes("документ"), "the panel must say why: " + env.el("footerStatus").textContent);
    expect(env.state("isBusy") === false, "not busy");
  });

  await scenario("the server never starts: the wait ends with the error card, the press is dropped", { online: false }, async (env, expect) => {
    env.click("btnRun");
    await sleep(1000);
    expect(env.el("btnRun").classList.contains("waiting"), "waiting");
    expect(!env.el("serverErrorCard").classList.contains("visible"), "no error card during the wait");
    env.state("cvClockSkewMs = 26000");                      // 26 s later: a hint, still waiting
    await sleep(1000);
    expect(env.el("statusBanner").classList.contains("visible") && env.el("statusBannerText").textContent.includes("start_gpu_server.bat"),
      "after a while the panel must say what to do if no server window appeared");
    expect(env.el("btnRun").classList.contains("waiting"), "still waiting");
    env.state("cvClockSkewMs = 151000");                     // 2.5 minutes later
    await sleep(1100);
    expect(env.el("serverErrorCard").classList.contains("visible"), "the error card must appear when the wait is over");
    expect(!env.el("btnRun").classList.contains("waiting") && env.el("btnRun").textContent.trim() === "Очистити фон", "the button must be back to normal");
    expect(env.el("gpuStatusText").textContent === "Вимк." && env.el("btnPlayServer").style.display !== "none", "status 'Вимк.' with the ▶ button");
    expect(env.of("/session/start").length === 0 && env.state("isBusy") === false, "nothing started");
    expect(env.server.launches === 1, "one launch request, got " + env.server.launches);
  });

  // ---------------------------------------------------------------- defaults that changed since the PC saved its presets
  // (what a PC of 4.3.0 holds: the eight built-in presets of that time - no corner tool anywhere, smoke protection on
  //  everywhere, "Темний ключ" with dust 92 - and a preset of the user's own)
  const IDS_OLD = ["std", "medium_shot", "closeup", "wide_shot", "lowkey", "smoke", "clean_stands", "gentle"];
  const presets430 = () => {
    const now = JSON.parse(fs.readFileSync(path.join(PLUGIN_DIR, "..", "server", "presets_defaults.json"), "utf8"));
    const list = IDS_OLD.map((id) => now.find((p) => p.id === id));
    list.forEach((p) => { p.cfg.cycCurve = 0; p.cfg.smokeOn = true; if (p.id === "lowkey") p.cfg.spots = 92; });
    list.push({ id: "user_1", name: "Мій пресет", color: "#ffffff", builtin: false, cfg: Object.assign({}, list[0].cfg, { cycCurve: 0, spots: 33, smokeOn: true }) });
    return list;
  };
  await scenario("a PC with the presets of 4.3.0: the new corner default reaches it once, the user's own values stay",
    { disk: { "presets_local.json": presets430(), "user_settings.json": { schemaVersion: 5, activePresetId: "wide_shot", autoPreset: false, cfg: Object.assign({}, presets430()[3].cfg) } },
      scene: { kind: "wide", framing: "wide", dark: false } }, async (env, expect) => {
      await sleep(500);                                      // bootstrap + the first sync with the server
      const cyc = (id) => env.state(`(presetsList.find((p) => p.id === ${JSON.stringify(id)}) || { cfg: {} }).cfg.cycCurve`);
      expect(cyc("wide_shot") === 65 && cyc("std") === 65 && cyc("medium_shot") === 65 && cyc("clean_stands") === 65,
        "the four presets with a floor must get 65: " + ["wide_shot", "std", "medium_shot", "clean_stands"].map(cyc).join());
      expect(cyc("lowkey") === 65, "since 4.5.0 the dark preset gets 65 as well: " + cyc("lowkey"));
      expect(cyc("closeup") === 0 && cyc("smoke") === 0 && cyc("user_1") === 0, "the other presets and the user's own one must stay: " + [cyc("closeup"), cyc("smoke"), cyc("user_1")].join());
      const cfgOf = (id) => env.state(`JSON.stringify((presetsList.find((p) => p.id === ${JSON.stringify(id)}) || { cfg: {} }).cfg)`);
      expect(IDS_OLD.every((id) => JSON.parse(cfgOf(id)).smokeOn === (id === "smoke")), "smoke protection must go off in every built-in preset but the smoke one");
      expect(JSON.parse(cfgOf("user_1")).smokeOn === true && JSON.parse(cfgOf("user_1")).spots === 33, "...and stay as saved in the user's own preset");
      expect(JSON.parse(cfgOf("lowkey")).spots === 80, "'Темний ключ' must get dust 80: " + JSON.parse(cfgOf("lowkey")).spots);
      expect(env.state("smokeEnabled") === false && !env.el("dlgChkSmoke").checked && env.el("gBtnSmoke").textContent === "Вимк.",
        "the smoke controls of the active preset must go off: " + env.el("gBtnSmoke").textContent);
      const ids = env.state("presetsList.map((p) => p.id).join()");
      expect(ids === "std,medium_shot,closeup,wide_shot,lowkey,lowkey_medium,lowkey_close,lowkey_wide,smoke,clean_stands,gentle,user_1",
        "the three dark presets must land under 'Темний ключ': " + ids);
      expect(env.state("activePresetId") === "wide_shot" && env.state("getSliderVal('gSlCyc')") === 65, "the slider of the active preset must follow, got " + env.state("getSliderVal('gSlCyc')"));
      expect(env.el("gValCyc").textContent === "65%", "...and show it: " + env.el("gValCyc").textContent);
      const onDisk = env.server.disk;
      expect(onDisk["presets_local.json"].find((p) => p.id === "wide_shot").cfg.cycCurve === 65, "the moved presets must be saved on the PC");
      expect(["cyc65", "smokeOff", "lowkeySpots80", "lowkeyCyc65"].every((id) => (onDisk["user_settings.json"].presetMoves || []).includes(id)),
        "the settings must remember that the moves were made: " + JSON.stringify(onDisk["user_settings.json"].presetMoves));
      expect(onDisk["presets_local.json"].length === 12 && onDisk["presets_local.json"].find((p) => p.id === "std").cfg.smokeOn === false, "...and the presets on the PC must hold all of it");
      const sent = env.of("/presets").filter((r) => r.method === "POST");
      expect(sent.length >= 1 && sent[sent.length - 1].body.find((p) => p.id === "wide_shot").cfg.cycCurve === 65, "the server copy must get the moved presets too");
      await env.open();
      expect(env.of("/session/start")[0].body.params.cycCurve === 65 && env.of("/session/start")[0].body.params.smokeOn === false, "the first scan must go with the new values");
      // the user decides otherwise: 0 stays 0 from now on (the next start of Photoshop reads the files written here)
      env.state("setSliderVal('gSlCyc', 0); presetsList.find((p) => p.id === 'wide_shot').cfg.cycCurve = 0; persistPresets(); persistSettingsNow();");
      await sleep(200);
      expect(onDisk["presets_local.json"].find((p) => p.id === "wide_shot").cfg.cycCurve === 0 && onDisk["user_settings.json"].presetMoves.includes("cyc65"),
        "a value set by the user afterwards must be saved as it is");
      expect(env.state("applyPresetDefaultMoves()") === false && cyc("wide_shot") === 0, "...and must not be moved again");
    });

  await scenario("...also while the server is not running yet (the move is made when the panel starts, not when the server answers)",
    { online: false, disk: { "presets_local.json": presets430(), "user_settings.json": { schemaVersion: 5, activePresetId: "std", autoPreset: true, cfg: Object.assign({}, presets430()[0].cfg) } } },
    async (env, expect) => {
      await sleep(400);
      expect(env.state("presetsList.find((p) => p.id === 'std').cfg.cycCurve") === 65 && env.state("getSliderVal('gSlCyc')") === 65, "moved at start-up");
      const onDisk = env.server.disk;
      expect(onDisk["presets_local.json"].find((p) => p.id === "medium_shot").cfg.cycCurve === 65 && (onDisk["user_settings.json"].presetMoves || []).includes("cyc65"),
        "...and saved on the PC at once");
      expect(env.state("settingsMigrated") === true, "the server copy is to follow at the first sync");
    });

  await scenario("a PC whose plugin folder is empty but whose server still holds the presets of 4.3.0: moved when they arrive", {}, async (env, expect) => {
    // (the scripted server answers GET /presets with nothing; the arrival is played by hand, the way syncPresetsFromServer does it)
    await sleep(300);
    const moved = env.state(`(function () {
      presetsList = ${JSON.stringify(presets430())};
      applySettingsSnapshot({ schemaVersion: 5, activePresetId: "wide_shot", cfg: { cycCurve: 0 } });
      const changed = applyPresetDefaultMoves();
      return [changed, presetsList.find((p) => p.id === "wide_shot").cfg.cycCurve, getSliderVal("gSlCyc"), presetsList.find((p) => p.id === "user_1").cfg.cycCurve].join();
    })()`);
    expect(moved === "true,65,65,0", "settings that carry no list of moves reset it, so the move is made: " + moved);
  });

  await scenario("a fresh installation: the built-in presets come with the corner default, nothing is 'moved'", { disk: {} }, async (env, expect) => {
    await sleep(500);
    expect(env.state("getSliderVal('gSlCyc')") === 65 && env.state("activePresetId") === "std", "the first preset is on the controls with its 65");
    expect(env.state("appliedPresetMoves.includes('cyc65') && appliedPresetMoves.includes('smokeOff') && appliedPresetMoves.includes('lowkeySpots80')") === true, "the moves count as made");
    expect(env.state("presetsList.find((p) => p.id === 'closeup').cfg.cycCurve") === 0, "'Ближній план' keeps the corner");
    expect(env.state("presetsList.length") === 11 && env.state("presetsList[5].id") === "lowkey_medium", "eleven built-in presets, the dark ones together");
    expect(env.state("smokeEnabled") === false && !env.el("dlgChkSmoke").checked && !env.el("dlgWrapSmoke").classList.contains("active") &&
      env.el("gBtnSmoke").textContent === "Вимк." && env.el("gValSmoke").textContent === "Вимк.", "smoke protection is off on a fresh installation");
  });

  // The only start at which no preset and no saved value is put on the controls: what they show is what the panel
  // is drawn with. Smoke protection must not be on there either.
  await scenario("settings saved without the values of the controls (a file cut by hand): smoke protection is not switched on by itself",
    { disk: { "user_settings.json": { schemaVersion: 5, presetMoves: ["cyc65", "smokeOff", "lowkeySpots80", "lowkeyCyc65"] } } }, async (env, expect) => {
      await sleep(500);
      expect(env.state("smokeEnabled") === false && !env.el("dlgChkSmoke").checked && !env.el("dlgWrapSmoke").classList.contains("active") &&
        env.el("gBtnSmoke").textContent === "Вимк." && env.el("gValSmoke").textContent === "Вимк.", "smoke protection must stay off until it is asked for");
    });

  // ---------------------------------------------------------------- smoke
  await scenario("smoke: every request asks to protect smoke only where there is smoke; the corner presets go with the floor",
    { scene: { kind: "wide", framing: "wide", dark: false } }, async (env, expect) => {
      await env.open();
      const start = env.of("/session/start")[0];
      const sp = start.body.scenePresets || {};
      expect(start.body.params.smokeAuto === true, "the first scan must ask for it: " + JSON.stringify(start.body.params));
      expect(Object.keys(sp).length === 8 && Object.keys(sp).every((k) => sp[k].smokeAuto === true), "...and so must every set of the automatic preset");
      expect(sp.wide.cycCurve === 65 && sp.medium.cycCurve === 65 && sp.default.cycCurve === 65 && sp.dark.cycCurve === 65 && sp.dark_wide.cycCurve === 65 &&
        sp.dark_medium.cycCurve === 65 && sp.close.cycCurve === 0 && sp.dark_close.cycCurve === 0,
        "the corner line goes by default wherever a floor is usually in the frame and stays in the two close-up presets: "
        + JSON.stringify(Object.keys(sp).map((k) => [k, sp[k].cycCurve])));
      expect(env.state("getSliderVal('gSlCyc')") === 65, "the slider must show the value of the applied preset");
      await env.drag("gSlSpots", 90);
      await env.settle(900);
      const rc = env.recomputes();
      expect(rc.length === 1 && rc[0].body.params.smokeAuto === true && rc[0].body.params.cycCurve === 65, "a refresh must carry it too");
      env.click("dlgBtnApply");
      await env.settle(900);
      const ap = env.of("/session/apply");
      expect(ap.length === 1 && ap[0].body.params.smokeAuto === true, "...and Apply as well");
    });

  await scenario("smoke controls on a frame without smoke: the note says why nothing changes",
    { frameSmoke: { share: 0.004, largest: 0.002, found: false } }, async (env, expect) => {
      env.check("dlgChkAutoPreset", false);
      await env.open();
      await env.settle(300);
      expect(env.badge() === "", "a frame without smoke opens without a word about smoke: " + env.badge());
      expect(env.of("/session/start")[0].body.params.smokeOn === false && !env.el("dlgChkSmoke").checked, "the window opens with the protection off");
      env.check("dlgChkSmoke", true);                        // "I shot with smoke"
      expect(env.hint().includes("увімкнено") && env.hint().includes("оновлюю перегляд"), "ticking the box must say at once that the preview is being refreshed: " + env.hint());
      await env.settle(900);
      let rc = env.recomputes();
      expect(rc.length === 1 && rc[0].body.params.smokeOn === true && rc[0].body.quick === true, "one light refresh with the protection on");
      expect(env.badge().includes("Перегляд оновлено") && env.badge().includes("не знайдено") && env.badge().includes("нічого не змінює") && env.badge().includes("95–100"),
        "the note must say that the preview was refreshed, that nothing changes and how to force the protection: " + env.badge());
      expect(env.hint() === env.badge(), "the same words must stay in the hint strip after the note is gone: " + env.hint());
      expect(env.el("dlgWrapSmoke").classList.contains("active") && env.el("gBtnSmoke").textContent === "Увімк.", "both smoke controls must show 'on'");
      env.check("dlgChkSmoke", false);
      await env.settle(900);
      rc = env.recomputes();
      expect(rc.length === 2 && rc[1].body.params.smokeOn === false, "one more refresh with the protection off");
      expect(env.badge().includes("вимкнено") && env.badge().includes("не знайдено") && env.badge().includes("той самий"),
        "the note must say the result is the same: " + env.badge());
      env.check("dlgChkSmoke", true);
      await env.settle(900);
      await env.drag("gSlSmoke", 96);                        // "there is smoke, protect it anyway"
      await env.settle(1100);
      rc = env.recomputes();
      expect(rc.length === 4 && rc[3].body.params.smoke === 96 && rc[3].body.params.smokeOn === true, "the slider gives one more refresh");
      expect(env.badge().includes("95–100") && env.badge().includes("збережено") && env.badge().includes("0,48 %"),
        "the note must say that everything smoke-like is kept now: " + env.badge());
      await env.drag("gSlSpots", 90);                        // another control: no words about smoke
      await env.settle(1100);
      expect(env.recomputes().length === 5, "the other slider refreshes as usual");
      expect(!env.badge().includes("95–100"), "the smoke note must not come back after another control: " + env.badge());
    });

  await scenario("a frame with smoke, protection off (the usual state): the window says so at once; the tick protects the smoke",
    { frameSmoke: { share: 0.05, largest: 0.04, found: true }, scene: { kind: "wide", framing: "wide", dark: false } }, async (env, expect) => {
      await env.open();
      await env.settle(300);
      expect(env.badge().includes("Авто-пресет") && env.badge().includes("Схоже, у кадрі є дим") && env.badge().includes("5,0 %") && env.badge().includes("поставте галочку"),
        "the opening note must name the preset and warn that the smoke is being cleaned: " + env.badge());
      env.check("dlgChkSmoke", true);
      await env.settle(900);
      let rc = env.recomputes();
      expect(rc.length === 1 && rc[0].body.params.smokeOn === true && rc[0].body.params.smokeAuto === true, "one refresh with the protection on");
      expect(env.badge().includes("Дим знайдено") && env.badge().includes("6,0 %"), "the note must say that the smoke is protected now: " + env.badge());
      expect(env.el("gBtnSmoke").textContent === "Увімк.", "the switch in the fine settings must follow the checkbox");
      env.click("gBtnSmoke");                                // ...and the switch works the other way round
      await env.settle(900);
      rc = env.recomputes();
      expect(rc.length === 2 && rc[1].body.params.smokeOn === false, "one refresh with the protection off");
      expect(env.badge().includes("вимкнено") && env.badge().includes("5,0 %") && env.badge().includes("чиститься"),
        "the note must warn that the smoke is cleaned now: " + env.badge());
      expect(!env.el("dlgChkSmoke").checked, "the checkbox on top must follow the switch");
    });

  await scenario("the preset 'Зйомка з димом' keeps the protection on: said when the window opens",
    { frameSmoke: { share: 0.05, largest: 0.04, found: true } }, async (env, expect) => {
      env.check("dlgChkAutoPreset", false);
      env.state("applyPreset(presetsList.find((p) => p.id === 'smoke')); renderPresets(); updateSliderVisuals();");
      expect(env.el("dlgChkSmoke").checked && env.el("gBtnSmoke").textContent === "Увімк.", "the preset must switch the smoke controls on");
      await env.open();
      await env.settle(300);
      const p = env.of("/session/start")[0].body.params;
      expect(p.smokeOn === true && p.smoke === 95, "the first scan must protect smoke: " + JSON.stringify([p.smokeOn, p.smoke]));
      expect(env.badge().includes("95–100") && env.badge().includes("збережено"), "the opening note must say that smoke is kept: " + env.badge());
      env.click("dlgBtnPresets");
      env.clickPreset("Студія (Стандарт)");
      expect(!env.el("dlgChkSmoke").checked, "another preset switches the protection off again");
    });

  await scenario("an older server that says nothing of smoke: no smoke notes, nothing breaks", {}, async (env, expect) => {
    env.check("dlgChkAutoPreset", false);
    await env.open();
    env.check("dlgChkSmoke", true);
    await env.settle(900);
    expect(env.recomputes().length === 1, "the refresh is still asked for");
    expect(env.badge() === "", "no note without an answer about smoke: " + env.badge());
    expect(env.state("sessState.smokeNote") === false, "the request for a note must be closed");
  });

  // ---------------------------------------------------------------- one step back / forward for the mask edits
  const dim = (env, id) => env.el(id).classList.contains("is-dim");
  const stroke = (env) => { env.press("dlgViewport", 100); env.move(120); env.release(); };

  await scenario("Ctrl + Z and the two buttons: a mask edit is taken back and made again", {}, async (env, expect) => {
    await env.open();
    const ops = () => env.edits().map((r) => r.body.op).join();
    expect(dim(env, "dlgBtnUndo") && dim(env, "dlgBtnRedo"), "a fresh window: nothing to step to, both buttons are dim");
    stroke(env);                                             // an eraser stroke - a click on the photo by accident, say
    await env.settle(200);
    expect(ops() === "stroke", "the stroke must reach the server: " + ops());
    expect(!dim(env, "dlgBtnUndo") && dim(env, "dlgBtnRedo"), "after an edit 'back' is bright and 'forward' dim");
    expect(env.state("JSON.stringify(sessState.history)") === '{"undo":1,"redo":0}', "the counts: " + env.state("JSON.stringify(sessState.history)"));
    const ev = env.key("KeyZ", "я", { ctrlKey: true });      // the Ukrainian layout: the key is told by its place
    await env.settle(200);
    expect(ev.defaultPrevented, "the key must not go on to Photoshop");
    expect(ops() === "stroke,undo", "Ctrl + Z must ask for one step back: " + ops());
    expect(env.picture() === "edit-2", "the picture of the step back must be on screen: " + env.picture());
    expect(dim(env, "dlgBtnUndo") && !dim(env, "dlgBtnRedo"), "after the step back 'forward' is bright");
    expect(env.hint().includes("скасовано") && env.hint().includes("Ctrl + Shift + Z"), "the hint must say what happened and how to get it back: " + env.hint());
    env.key("KeyZ", "Z", { ctrlKey: true, shiftKey: true });
    await env.settle(200);
    expect(ops() === "stroke,undo,redo" && !dim(env, "dlgBtnUndo") && dim(env, "dlgBtnRedo"), "Ctrl + Shift + Z must make the edit again: " + ops());
    expect(env.hint().includes("повернуто"), "the hint: " + env.hint());
    env.click("dlgBtnUndo");
    await env.settle(200);
    expect(ops() === "stroke,undo,redo,undo", "the ↺ button does what Ctrl + Z does: " + ops());
    env.key("KeyY", "н", { ctrlKey: true });
    await env.settle(200);
    expect(ops() === "stroke,undo,redo,undo,redo", "Ctrl + Y makes the edit again as well: " + ops());
    env.click("dlgBtnRedo");                                 // nothing left to make again
    await env.settle(200);
    expect(env.edits().length === 6 && env.hint().includes("Повертати нічого"), "a press with nothing to step to must say so: " + env.hint());
    // the keys keep their own meaning in a text field; a checkbox that was clicked last does not swallow them
    env.click("dlgBtnPresets");
    env.click("dlgBtnAddPreset");
    env.key("KeyZ", "z", { ctrlKey: true }, env.el("dlgNewPresetName"));
    await env.settle(150);
    expect(env.edits().length === 6, "Ctrl + Z in the preset name field belongs to the field");
    env.key("KeyZ", "z", { ctrlKey: true }, env.el("dlgChkMakeMask"));
    await env.settle(150);
    expect(env.edits().length === 7 && env.edits()[6].body.op === "undo", "Ctrl + Z with a checkbox in focus must still step back");
    env.key("", "z", { metaKey: true });                     // a key event that carries no code: told by the letter
    await env.settle(150);
    expect(env.edits().length === 8 && env.hint().includes("Скасовувати нічого"), "Cmd / Ctrl + z without a key code works too; with nothing left it says so: " + env.hint());
    env.key("KeyZ", "z", {});
    env.key("KeyZ", "z", { ctrlKey: true, altKey: true });
    await env.settle(150);
    expect(env.edits().length === 8, "Z alone and Ctrl + Alt + Z are not steps");
    env.click("dlgToolInvert");                              // every kind of edit can be taken back
    await env.settle(150);
    expect(env.state("sessState.history.undo") === 1 && !dim(env, "dlgBtnUndo"), "the inversion must count as a step");
    await env.drag("gSlSpots", 90);                          // a refresh of the preview keeps the steps
    await env.settle(900);
    expect(env.recomputes().length === 1 && !dim(env, "dlgBtnUndo") && env.state("sessState.history.undo") === 1, "a refresh must keep the steps");
    // the window is closed: the keys do nothing; the next window starts clean
    env.el("retouchModal").close("cancel");
    await env.waitFor(() => env.state("isBusy") === false);
    const sent = env.edits().length;
    env.key("KeyZ", "z", { ctrlKey: true });
    await env.settle(150);
    expect(env.edits().length === sent, "Ctrl + Z with the window closed must ask nothing");
    env.server.edits = { undo: 0, redo: 0 };
    await env.open();
    expect(dim(env, "dlgBtnUndo") && dim(env, "dlgBtnRedo") && env.state("sessState.history.undo") === 0, "a new window: both buttons are dim again");
  });

  await scenario("mask edits reach the server one after another: a slow answer never covers a newer picture", { editDelays: [500, 20] }, async (env, expect) => {
    await env.open();
    stroke(env);                                             // answered after half a second
    await sleep(40);
    env.key("KeyZ", "z", { ctrlKey: true });                 // pressed while the stroke is still on its way
    await env.settle(900);
    const e = env.edits();
    expect(e.length === 2 && e[0].body.op === "stroke" && e[1].body.op === "undo", "both edits must be sent, in the order they were made");
    if (e.length === 2) expect(e[1].t >= e[0].tDone, `the step back must wait for the stroke: sent at ${e[1].t} ms, the stroke was answered at ${e[0].tDone} ms`);
    expect(env.picture() === "edit-2", "the picture of the last edit must stay on screen: " + env.picture());
    expect(env.state("JSON.stringify(sessState.history)") === '{"undo":0,"redo":1}', "the counts: " + env.state("JSON.stringify(sessState.history)"));
    expect(env.hint().includes("скасовано"), "the stroke was there by then, so it was taken back: " + env.hint());
  });

  await scenario("a server before 4.5.0: a step back says that the server must be restarted", { historyAware: false }, async (env, expect) => {
    await env.open();
    stroke(env);
    await env.settle(200);
    expect(dim(env, "dlgBtnUndo"), "without an answer about the history the buttons stay dim");
    env.key("KeyZ", "z", { ctrlKey: true });
    await env.settle(200);
    expect(env.edits().length === 2, "the request is still made");
    expect(env.hint().includes("стару версію сервера") && env.hint().includes("restart_gpu_server.bat"), "the hint must say what to do: " + env.hint());
  });

  // ---------------------------------------------------------------- "Скинути пресет"
  const shippedCfg = (id) => JSON.parse(fs.readFileSync(path.join(PLUGIN_DIR, "..", "server", "presets_defaults.json"), "utf8")).find((x) => x.id === id).cfg;
  const cfgOf = (env, id) => JSON.parse(env.state(`JSON.stringify(presetsList.find((p) => p.id === ${JSON.stringify(id)}).cfg)`));

  await scenario("'Скинути пресет': the second press gives the active built-in preset the values it ships with, and only that one",
    { disk: {} }, async (env, expect) => {
      env.check("dlgChkAutoPreset", false);
      await sleep(300);
      await env.open();
      // the user tunes two presets and saves them
      env.click("dlgBtnPresets");
      env.clickPreset("Дальній план");
      await env.settle(600);
      await env.drag("gSlSpots", 40);
      await env.settle(700);
      env.click("gBtnSavePreset");
      await env.settle(300);
      env.click("dlgBtnPresets");
      env.clickPreset("Студія (Стандарт)");
      await env.settle(600);
      await env.drag("gSlSpots", 30);
      env.check("dlgChkSmoke", true);
      await env.settle(900);
      env.click("gBtnSavePreset");
      await env.settle(300);
      expect(cfgOf(env, "std").spots === 30 && cfgOf(env, "std").smokeOn === true && cfgOf(env, "wide_shot").spots === 40,
        "the tuned values must be saved first: " + JSON.stringify([cfgOf(env, "std").spots, cfgOf(env, "std").smokeOn, cfgOf(env, "wide_shot").spots]));
      const n0 = env.recomputes().length;
      const reset = env.el("gBtnResetPreset");
      expect(reset.textContent.includes("Скинути") && reset.textContent.includes("Студія") && !reset.classList.contains("is-dim"), "the button must name the active preset: " + reset.textContent);
      env.click("gBtnResetPreset");                          // the first press only asks
      await env.settle(300);
      expect(cfgOf(env, "std").spots === 30 && reset.textContent.includes("ще раз") && reset.classList.contains("armed"), "one press must change nothing and ask for one more: " + reset.textContent);
      expect(env.recomputes().length === n0 && env.hint().includes("ще раз"), "...and compute nothing: " + env.hint());
      env.click("gBtnResetPreset");                          // the second one resets
      await env.settle(900);
      const shipped = shippedCfg("std");
      const now = cfgOf(env, "std");
      expect(Object.keys(shipped).length === Object.keys(now).length && Object.keys(shipped).every((k) => now[k] === shipped[k]), "the preset must hold exactly the values it ships with: " + JSON.stringify(now));
      expect(env.state("getSliderVal('gSlSpots')") === 75 && !env.el("dlgChkSmoke").checked, "...and the controls must show them");
      expect(cfgOf(env, "wide_shot").spots === 40, "another preset must keep what the user saved into it");
      const rc = env.recomputes();
      expect(rc.length === n0 + 1 && rc[n0].body.quick === true && rc[n0].body.params.spots === 75 && rc[n0].body.params.smokeOn === false, "one light refresh with the shipped values");
      expect(!reset.classList.contains("armed") && reset.textContent.includes("Скинути"), "the button must be back to its usual words: " + reset.textContent);
      expect(env.hint().includes("скинуто"), "the hint: " + env.hint());
      expect(env.badge().includes("Студія"), "the note of a preset change must appear: " + env.badge());
      const onDisk = env.server.disk["presets_local.json"];
      expect(onDisk.find((x) => x.id === "std").cfg.spots === 75 && onDisk.find((x) => x.id === "wide_shot").cfg.spots === 40, "the presets on the PC must hold it");
      const posted = env.of("/presets").filter((r) => r.method === "POST");
      expect(posted.length >= 1 && posted[posted.length - 1].body.find((x) => x.id === "std").cfg.spots === 75, "...and the server copy too");
      // a built-in preset the user renamed is still reset (it is found by its id); the name stays
      env.state("presetsList.find((p) => p.id === 'wide_shot').name = 'Мій дальній'; applyPreset(presetsList.find((p) => p.id === 'wide_shot')); renderPresets();");
      env.click("gBtnResetPreset");
      env.click("gBtnResetPreset");
      await env.settle(900);
      expect(cfgOf(env, "wide_shot").spots === 85 && env.state("presetsList.find((p) => p.id === 'wide_shot').name") === "Мій дальній", "a renamed built-in preset must be reset, its name kept");
      // a preset of the user's own has nothing to be reset to
      env.state("presetsList.unshift({ id: 'usr_9', name: 'Мій', color: '#ffffff', builtin: false, cfg: Object.assign({}, presetsList[0].cfg, { spots: 11 }) }); applyPreset(presetsList[0]); renderPresets();");
      expect(reset.classList.contains("is-dim"), "for the user's own preset the button is dim: " + reset.className);
      env.click("gBtnResetPreset");
      env.click("gBtnResetPreset");
      await env.settle(300);
      expect(cfgOf(env, "usr_9").spots === 11 && env.hint().includes("власний пресет"), "nothing must change, the hint explains why: " + env.hint());
    });

  await scenario("'Скинути пресет': a single press is forgotten after a few seconds, and does not pass on to another preset", {}, async (env, expect) => {
    env.check("dlgChkAutoPreset", false);
    await env.open();
    await env.drag("gSlSpots", 40);
    await env.settle(700);
    env.click("gBtnSavePreset");
    await env.settle(200);
    const reset = env.el("gBtnResetPreset");
    env.click("gBtnResetPreset");
    expect(reset.classList.contains("armed"), "armed after one press");
    env.click("gBtnSavePreset");                             // saving in between takes the press back
    await env.settle(200);
    expect(!reset.classList.contains("armed"), "'Зберегти' must take the press back");
    env.click("gBtnResetPreset");
    await sleep(6400);
    expect(!reset.classList.contains("armed") && reset.textContent.includes("Скинути"), "the press must be forgotten after a few seconds: " + reset.textContent);
    env.click("gBtnResetPreset");                            // counts as a first press again
    await env.settle(200);
    expect(cfgOf(env, "std").spots === 40 && reset.classList.contains("armed"), "a press after the pause must be a first one again");
    env.click("dlgBtnPresets");
    env.clickPreset("Дальній план");                         // another preset picked while the button waits
    expect(!reset.classList.contains("armed") && reset.textContent.includes("Дальній"), "the press must not pass on to another preset: " + reset.textContent);
    env.click("gBtnResetPreset");
    await env.settle(300);
    expect(cfgOf(env, "std").spots === 40 && reset.classList.contains("armed"), "...there it is a first press again; 'Студія' keeps the saved value");
  });

  // ---------------------------------------------------------------- backup of the settings
  const backupRows = (env) => Array.from(env.doc.querySelectorAll("#backupList .backup-row"));

  await scenario("backup: everything is saved into a file through the server and restored from it after a second click", { disk: {} }, async (env, expect) => {
    await sleep(400);
    // what is worth keeping: a preset of the user's own, a tuned built-in one, a deleted one, the switches
    env.state(`(function () {
      presetsList.unshift({ id: "usr_7", name: "Мій сірий фон", color: "#54d182", builtin: false, cfg: Object.assign({}, presetsList[0].cfg, { spots: 44, smokeOn: true }) });
      presetsList.find((p) => p.id === "wide_shot").cfg.scuffs = 12;
      presetsList = presetsList.filter((p) => p.id !== "gentle");
      deletedDefaultIds.push("gentle");
      applyPreset(presetsList[0]);
      setAutoPreset(false);
      makeMaskDefault = true;
      setBrushSoft(false, false);
      sessState.brushSize = 61;
      renderPresets();
      updateSliderVisuals();
    })()`);
    const kept = env.state("JSON.stringify([presetsList, buildSettingsSnapshot()])");
    const box = env.el("panelBackupBox");
    env.click("btnBackupSave");
    await env.settle(300);
    const saves = env.of("/backup/save");
    expect(saves.length === 1 && saves[0].body.label === "" && JSON.stringify([saves[0].body.presets, saves[0].body.settings]) === kept,
      "the backup must carry every preset and the whole settings snapshot");
    expect(env.footer().includes("Бекап збережено") && env.footer().includes("пресетів 11") && env.footer().includes("ваших: 1"), "the panel must say what was saved: " + env.footer());
    expect(box.classList.contains("visible") && box.textContent.includes(env.server.backupFolder) && box.textContent.includes(env.server.backups[0].file),
      "...and where the file is: " + box.textContent);
    env.click("btnBackupOpenFolder");
    await env.settle(150);
    expect(env.server.folderOpened === 1 && env.footer().includes("відкрито"), "the folder must be opened through the server: " + env.footer());
    env.click("btnBackupClose");
    expect(!box.classList.contains("visible"), "'Закрити' must hide the box");

    // everything is lost (a reinstalled Photoshop: only the built-in presets, the settings as shipped)
    env.state(`(function () {
      presetsList = JSON.parse(JSON.stringify(DEFAULT_PRESETS));
      deletedDefaultIds = [];
      applyPreset(presetsList[0]);
      setAutoPreset(true);
      makeMaskDefault = false;
      setBrushSoft(true, false);
      sessState.brushSize = 28;
      renderPresets();
      updateSliderVisuals();
    })()`);
    env.click("btnBackupRestore");
    await env.settle(300);
    expect(box.classList.contains("visible") && backupRows(env).length === 1, "the list of backups must appear: " + box.textContent);
    const line = backupRows(env)[0] ? backupRows(env)[0].textContent : "";
    expect(line.includes("19.11.2026 08:31") && line.includes("пресетів: 11") && line.includes("ваших: 1"), "a line must show the date and what the backup holds: " + line);
    backupRows(env)[0].click();                              // the first click only asks
    await env.settle(200);
    expect(env.of("/backup/read").length === 0 && env.state("presetsList.length") === 11 && !env.state("presetsList.some((p) => p.id === 'usr_7')"), "one click must change nothing");
    expect(backupRows(env)[0].classList.contains("armed") && backupRows(env)[0].textContent.includes("ще раз"), "...and ask for one more: " + backupRows(env)[0].textContent);
    backupRows(env)[0].click();                              // the second one restores
    await env.settle(600);
    const reads = env.of("/backup/read");
    expect(reads.length === 1 && reads[0].body.file === env.server.backups[0].file, "the second click must read that backup");
    expect(env.state("JSON.stringify([presetsList, buildSettingsSnapshot()])") === kept, "the presets and the settings must be exactly as they were saved");
    expect(env.state("autoPreset") === false && env.state("makeMaskDefault") === true && env.state("sessState.brushSoft") === false && env.state("sessState.brushSize") === 61 &&
      env.state("activePresetId") === "usr_7" && env.state("deletedDefaultIds.join()") === "gentle", "the switches, the active preset and the deleted preset must be back");
    expect(env.state("getSliderVal('gSlSpots')") === 44 && env.el("dlgChkSmoke").checked && !env.el("dlgChkAutoPreset").checked && env.el("dlgChkMakeMask").checked &&
      env.el("dlgActivePresetName").textContent === "Мій сірий фон", "the controls must show it: " + env.el("dlgActivePresetName").textContent);
    const copy = env.of("/backup/save")[1];
    expect(copy && copy.body.label === "before-restore" && copy.body.presets.length === 11 && !copy.body.presets.some((x) => x.id === "usr_7"),
      "what was there before the restore must be kept as one more backup");
    const posted = env.of("/presets").filter((r) => r.method === "POST");
    const settingsPosted = env.of("/settings").filter((r) => r.method === "POST");
    expect(posted.length >= 1 && posted[posted.length - 1].body.some((x) => x.id === "usr_7") && copy && posted[posted.length - 1].t >= copy.tDone,
      "the server copy must get the restored presets, after the safety copy was written");
    expect(settingsPosted.length >= 1 && settingsPosted[settingsPosted.length - 1].body.autoPreset === false && settingsPosted[settingsPosted.length - 1].body.activePresetId === "usr_7",
      "...and the restored settings");
    expect(env.server.disk["presets_local.json"].some((x) => x.id === "usr_7") && env.server.disk["user_settings.json"].makeMaskDefault === true, "the files on the PC must hold them too");
    expect(env.footer().includes("Відновлено") && env.footer().includes("19.11.2026 08:31") && env.footer().includes("копія перед відновленням"), "the panel must say what was done: " + env.footer());
    expect(!box.classList.contains("visible"), "the list must close after the restore");
    env.click("btnBackupRestore");                           // the list now holds the automatic copy too, marked as such
    await env.settle(300);
    expect(backupRows(env).length === 2 && backupRows(env)[0].textContent.includes("копія перед відновленням") && !backupRows(env)[1].textContent.includes("копія"),
      "the automatic copy must be listed and marked: " + backupRows(env).map((n) => n.textContent).join(" | "));
    env.click("btnBackupRestore");
    await env.settle(150);
    expect(!box.classList.contains("visible"), "a second press on the button must hide the list");
    // the restored state opens the window as usual
    await env.open();
    const p0 = env.of("/session/start")[0].body.params;
    expect(p0.spots === 44 && p0.smokeOn === true && p0.speedMode === "quality", "the first scan must go with the restored values: " + JSON.stringify([p0.spots, p0.smokeOn, p0.speedMode]));
  });

  await scenario("backup: a server before 4.5.0, a file that cannot be written, an empty folder, a broken file - the panel says what to do",
    { backupAware: false }, async (env, expect) => {
      await sleep(300);
      const box = env.el("panelBackupBox");
      env.click("btnBackupSave");
      await env.settle(300);
      expect(env.footer().includes("Бекап не збережено") && env.footer().includes("стару версію сервера") && env.footer().includes("restart_gpu_server.bat"),
        "an older server: the panel must say that it has to be restarted: " + env.footer());
      expect(!box.classList.contains("visible"), "no box without a backup");
      env.click("btnBackupRestore");
      await env.settle(300);
      expect(env.footer().includes("стару версію сервера") && !box.classList.contains("visible"), "the same for the list: " + env.footer());
      env.server.backupAware = true;
      env.server.backupSaveFails = true;
      env.click("btnBackupSave");
      await env.settle(300);
      expect(env.footer().includes("Бекап не збережено") && env.footer().includes("диск недоступний"), "the reason the server gives must be shown: " + env.footer());
      env.server.backupSaveFails = false;
      env.click("btnBackupRestore");
      await env.settle(300);
      expect(box.classList.contains("visible") && backupRows(env).length === 0 && box.textContent.includes("Бекапів ще немає") && box.textContent.includes(env.server.backupFolder),
        "an empty folder: the box must say so and name the folder: " + box.textContent);
      env.click("btnBackupRestore");
      // a file that holds nothing usable: nothing is replaced
      env.server.backups.push({ file: "broken.json", saved_at: "2026-11-10T09:00:00", version: "4.5.0", label: "", presets_list: [{ id: "x" }], settings: {} });
      const before = env.state("JSON.stringify(presetsList)");
      env.click("btnBackupRestore");
      await env.settle(300);
      backupRows(env)[0].click();
      await env.settle(150);
      backupRows(env)[0].click();
      await env.settle(400);
      expect(env.footer().includes("Бекап не відновлено") && env.state("JSON.stringify(presetsList)") === before, "a broken backup must change nothing: " + env.footer());
    });

  await scenario("restoring a backup made by an older version: the defaults that changed since and the new built-in presets are added", { disk: {} }, async (env, expect) => {
    await sleep(400);
    env.server.backups.push({
      file: "CleanVinylPro2_backup_old.json", saved_at: "2026-11-01T10:00:00", version: "4.4.0", label: "", presets_list: presets430(),
      settings: { schemaVersion: 5, activePresetId: "lowkey", autoPreset: true, presetMoves: [], knownDefaultIds: IDS_OLD.slice(), deletedDefaultIds: [], cfg: Object.assign({}, presets430()[4].cfg) }
    });
    env.click("btnBackupRestore");
    await env.settle(300);
    backupRows(env)[0].click();
    await env.settle(150);
    backupRows(env)[0].click();
    await env.settle(600);
    const ids = env.state("presetsList.map((p) => p.id).join()");
    expect(ids === "std,medium_shot,closeup,wide_shot,lowkey,lowkey_medium,lowkey_close,lowkey_wide,smoke,clean_stands,gentle,user_1", "the dark presets by framing must be added: " + ids);
    const lk = cfgOf(env, "lowkey"), mine = cfgOf(env, "user_1");
    expect(lk.spots === 80 && lk.cycCurve === 65 && lk.smokeOn === false && cfgOf(env, "smoke").smokeOn === true, "the changed defaults must reach the restored presets: " + JSON.stringify([lk.spots, lk.cycCurve, lk.smokeOn]));
    expect(mine.spots === 33 && mine.smokeOn === true && mine.cycCurve === 0, "the user's own preset must be as it was saved");
    expect(env.state("activePresetId") === "lowkey" && env.state("getSliderVal('gSlSpots')") === 80 && env.state("getSliderVal('gSlCyc')") === 65 && !env.el("dlgChkSmoke").checked,
      "the controls of the active preset must follow");
    expect(env.server.disk["user_settings.json"].presetMoves.length === 4, "the moves must be remembered: " + JSON.stringify(env.server.disk["user_settings.json"].presetMoves));
  });

  // ---------------------------------------------------------------- one mode; the edge of the brush and the eraser
  await scenario("one mode: no speed button; settings and presets of an older version that say 'fast' change nothing",
    { disk: { "user_settings.json": { schemaVersion: 5, speedMode: "fast", presetMoves: ["cyc65", "smokeOff", "lowkeySpots80", "lowkeyCyc65"] } },
      scene: { kind: "wide", framing: "wide", dark: false } }, async (env, expect) => {
      await sleep(500);
      expect(env.doc.getElementById("dlgSpeedPill") === null && !/Швидкий|Якісний/.test(env.doc.body.textContent),
        "the speed button and its two names must be gone from the window");
      expect(env.state("speedMode") === "quality" && env.state("buildSettingsSnapshot().speedMode") === "quality", "one mode: " + env.state("speedMode"));
      // a preset of the user's own, saved by an older version while the fast mode was on
      env.state(`(function () {
        presetsList.push({ id: "usr_fast", name: "Мій швидкий", color: "#54d182", builtin: false, cfg: Object.assign({}, presetsList[0].cfg, { spots: 41, speedMode: "fast" }) });
        renderPresets();
      })()`);
      await env.open();
      const start = env.of("/session/start")[0].body;
      const sets = Object.keys(start.scenePresets || {});
      expect(start.params.speedMode === "quality", "the first scan must ask for the full AI fill: " + start.params.speedMode);
      expect(sets.length === 8 && sets.every((k) => start.scenePresets[k].speedMode === "quality"),
        "every set offered to the automatic preset must ask for it too: " + sets.map((k) => k + "=" + start.scenePresets[k].speedMode).join());
      env.click("dlgBtnPresets");
      env.clickPreset("Мій швидкий");
      await env.settle(800);
      const rs = env.recomputes();
      expect(rs.length === 1 && rs[0].body.params.spots === 41 && rs[0].body.params.speedMode === "quality",
        "a preset saved with the fast mode must be sent with the full AI fill: " + JSON.stringify(rs.map((r) => [r.body.params.spots, r.body.params.speedMode])));
      env.click("dlgBtnApply");
      await env.settle(700);
      const a = env.of("/session/apply");
      expect(a.length === 1 && a[0].body.params && a[0].body.params.speedMode === "quality", "Apply must ask for the full AI fill");
      expect(env.server.disk["user_settings.json"].speedMode === "quality", "the settings file must say it from now on: " + env.server.disk["user_settings.json"].speedMode);
    });

  await scenario("the edge of the brush and the eraser: soft unless the hard one is chosen; the choice goes with every stroke and is kept",
    { disk: {} }, async (env, expect) => {
      const lit = (id) => env.el(id).classList.contains("active");
      const dots = () => Array.from(env.doc.querySelectorAll("#dlgStrokeDots .stroke-dot"));
      const last = () => { const e = env.edits(); return e[e.length - 1].body; };
      await env.open();
      expect(env.state("sessState.brushSoft") === true && lit("dlgBrushSoft") && !lit("dlgBrushHard"), "a fresh installation: the soft edge is chosen");
      env.press("dlgViewport", 100);                         // the eraser is the tool on start
      expect(dots().length === 1 && dots()[0].style.opacity === "0.2", "the trace of a soft stroke is pale: " + dots().map((d) => d.style.opacity).join());
      env.move(120);
      env.release();
      await env.settle(200);
      expect(env.edits().length === 1 && last().op === "stroke" && last().erase === true && last().softness === 1,
        "a soft eraser stroke must say so to the server: " + JSON.stringify([last().erase, last().softness]));
      env.click("dlgBrushHard");
      expect(env.state("sessState.brushSoft") === false && !lit("dlgBrushSoft") && lit("dlgBrushHard"), "the lower button chooses the hard edge");
      expect(env.hint().includes("жорсткий"), "the window must say what was chosen: " + env.hint());
      expect(env.edits().length === 1 && env.recomputes().length === 0, "choosing the edge asks the server for nothing");
      env.press("dlgViewport", 100);
      expect(dots().length === 1 && dots()[0].style.opacity === "0.65", "the trace of a hard stroke is solid: " + dots().map((d) => d.style.opacity).join());
      env.move(120);
      env.release();
      await env.settle(200);
      expect(env.edits().length === 2 && last().erase === true && last().softness === 0, "a hard eraser stroke: " + JSON.stringify([last().erase, last().softness]));
      env.click("dlgToolBrush");
      env.press("dlgViewport", 100);
      env.move(120);
      env.release();
      await env.settle(200);
      expect(env.edits().length === 3 && last().erase === false && last().softness === 0, "the brush has the same edge as the eraser: " + JSON.stringify([last().erase, last().softness]));
      await env.settle(500);                                 // the settings are saved a moment after the click
      expect(env.server.disk["user_settings.json"] && env.server.disk["user_settings.json"].brushSoft === false,
        "the choice must be written into the settings: " + JSON.stringify(env.server.disk["user_settings.json"] && env.server.disk["user_settings.json"].brushSoft));
      env.click("dlgBrushSoft");
      expect(env.state("sessState.brushSoft") === true && lit("dlgBrushSoft") && !lit("dlgBrushHard") && env.hint().includes("м’який"), "the upper button brings the soft edge back: " + env.hint());
      env.press("dlgViewport", 100);
      env.move(120);
      env.release();
      await env.settle(200);
      expect(env.edits().length === 4 && last().softness === 1, "the next stroke is soft again");
      env.el("retouchModal").close("cancel");               // a window opened again shows the choice that was made
      await env.waitFor(() => env.state("isBusy") === false);
      env.click("dlgBrushHard");
      await env.open();
      expect(lit("dlgBrushHard") && !lit("dlgBrushSoft"), "a new window must show the edge that is chosen");
    });

  await scenario("the hard edge kept in the settings is there after Photoshop is started again",
    { disk: { "user_settings.json": { schemaVersion: 5, brushSoft: false, brushSize: 40, presetMoves: ["cyc65", "smokeOff", "lowkeySpots80", "lowkeyCyc65"] } } }, async (env, expect) => {
      await sleep(500);
      expect(env.state("sessState.brushSoft") === false && env.state("sessState.brushSize") === 40, "the settings must bring the hard edge back");
      await env.open();
      expect(env.el("dlgBrushHard").classList.contains("active") && !env.el("dlgBrushSoft").classList.contains("active"), "the window must show it");
      env.press("dlgViewport", 100);
      env.move(120);
      env.release();
      await env.settle(200);
      expect(env.edits().length === 1 && env.edits()[0].body.softness === 0 && env.edits()[0].body.radius_px === 40, "...and the strokes must have it");
    });

  await scenario("settings of an older version say nothing of the edge: it is soft",
    { disk: { "user_settings.json": { schemaVersion: 5, brushSize: 52, presetMoves: ["cyc65", "smokeOff", "lowkeySpots80", "lowkeyCyc65"] } } }, async (env, expect) => {
      await sleep(500);
      expect(env.state("sessState.brushSoft") === true && env.state("sessState.brushSize") === 52, "soft, with the brush size that was saved");
    });

  const failed = results.filter((r) => r.problems.length);
  if (!results.length) {
    console.log("plugin preview: no scenario has that text in its name");
    process.exit(1);
  }
  console.log(failed.length
    ? `plugin preview: ${failed.length} of ${results.length} scenarios FAILED`
    : `plugin preview: ${results.length} scenarios pass (drag -> nothing; release -> one light refresh; Apply carries the settings; views, presets, automatic preset, remembered press, smoke notes, steps back and forward, preset reset, backup)`);
  process.exit(failed.length ? 1 : 0);
}

main().catch((err) => {
  console.log("plugin preview: crashed: " + (err && err.stack ? err.stack : err));
  process.exit(1);
});
