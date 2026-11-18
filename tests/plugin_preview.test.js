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
//   - smoke: every request asks for "protect smoke only where there is smoke", and the smoke controls say in
//     words what the server saw (on a frame without smoke they change nothing - the note explains why).
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
    disk: null             // files in the plugin's data folder, e.g. { "presets_local.json": [...] }; null = no disk
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
            for (const key of [scene.kind, scene.framing, "default"]) {
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
          return reply(ans);
        }
        case "/session/mask-edit":
        case "/session/dress-preview":
          return reply({ ok: true, inverted: false, comp_jpg_b64: "QQ==", overlay_jpg_b64: "QQ==" });
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
    env.check("dlgChkSmoke", false);
    await env.settle(600);
    const rs = env.recomputes();
    expect(rs.length === 3, `three recomputes expected, got ${rs.length}`);
    expect(rs.every((r) => r.body.quick === true), "all three must be light");
    if (rs.length === 3) {
      expect(rs[0].body.params.removeStands === true, "stands removal must be on in the first");
      expect(rs[1].body.params.fracFine === false && rs[1].body.params.autoFractions === false, "fine fraction off, auto off in the second");
      expect(rs[2].body.params.smokeOn === false, "smoke protection off in the third");
    }
    env.click("dlgFracAuto");               // AUTO again: the settings look the same, the server must still be asked
    await env.settle(600);
    expect(env.recomputes().length === 4 && env.recomputes()[3].body.params.autoFractions === true, "AUTO must ask the server once more");
    expect(env.state("fracFine") === true, "the fractions chosen by the server must be shown");
    await env.settle(800);
    expect(env.recomputes().length === 4, "no further recompute after AUTO was answered");
  });

  await scenario("speed mode and the 'exact preview' button recompute in full, with the progress card", { recomputeDelay: 300 }, async (env, expect) => {
    await env.open();
    env.click("dlgSpeedPill");
    await sleep(150);
    expect(env.progressCardVisible(), "the progress card must be shown for a full recompute");
    await env.settle(600);
    env.click("dlgBtnGear");
    env.click("gBtnRecompute");
    await env.settle(700);
    const rs = env.recomputes();
    expect(rs.length === 2, `two recomputes expected, got ${rs.length}`);
    expect(rs.every((r) => r.body.quick === undefined && typeof r.body.jobId === "string"), "both must be full recomputes with a progress job");
    if (rs[0]) expect(rs[0].body.params.speedMode === "quality", "the first must switch to the quality mode");
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
    env.click("dlgSpeedPill");
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
        expect(p.spots === 92 && p.scuffs === 55 && p.seam === 90 && p.edge === 78 && p.smoke === 70 && p.grain === 95,
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
      expect(Object.keys(sp).sort().join() === "close,dark,default,medium,wide", "five sets must be sent, got " + Object.keys(sp).sort().join());
      expect(sp.wide && sp.wide.spots === 85 && sp.wide.scuffs === 78 && sp.wide.edge === 66 && sp.wide.speedMode === "fast" && sp.wide.autoFractions === true,
        "the 'wide' set must be the preset 'Дальній план': " + JSON.stringify(sp.wide));
      expect(sp.dark && sp.dark.spots === 92 && sp.close && sp.close.fracLarge === false && sp.close.autoFractions === false && sp.default && sp.default.spots === 75,
        "the other sets must be 'Темний ключ', 'Ближній план', 'Студія'");
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

  await scenario("automatic preset: a dark frame takes 'Темний ключ'; a deleted preset falls back to 'Студія'",
    { scene: { kind: "dark", framing: "wide", dark: true } }, async (env, expect) => {
      env.state("presetsList = presetsList.filter((p) => p.id !== 'lowkey' && p.id !== 'wide_shot'); renderPresets();");
      await env.open();
      await env.settle(600);
      const sp = env.of("/session/start")[0].body.scenePresets || {};
      expect(!sp.dark && !sp.wide && sp.default, "deleted presets must not be offered: " + Object.keys(sp).join());
      expect(env.state("activePresetId") === "std", "the fallback preset must be used, got " + env.state("activePresetId"));
      expect(env.badge().includes("Студія") && env.badge().includes("темний фон"), "the note: " + env.badge());
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
  const presets430 = () => {
    const list = JSON.parse(fs.readFileSync(path.join(PLUGIN_DIR, "..", "server", "presets_defaults.json"), "utf8"));
    list.forEach((p) => { p.cfg.cycCurve = 0; });
    list.push({ id: "user_1", name: "Мій пресет", color: "#ffffff", builtin: false, cfg: Object.assign({}, list[0].cfg, { cycCurve: 0, spots: 33 }) });
    return list;
  };
  await scenario("a PC with the presets of 4.3.0: the new corner default reaches it once, the user's own values stay",
    { disk: { "presets_local.json": presets430(), "user_settings.json": { schemaVersion: 5, activePresetId: "wide_shot", autoPreset: false, cfg: Object.assign({}, presets430()[3].cfg) } },
      scene: { kind: "wide", framing: "wide", dark: false } }, async (env, expect) => {
      await sleep(500);                                      // bootstrap + the first sync with the server
      const cyc = (id) => env.state(`(presetsList.find((p) => p.id === ${JSON.stringify(id)}) || { cfg: {} }).cfg.cycCurve`);
      expect(cyc("wide_shot") === 65 && cyc("std") === 65 && cyc("medium_shot") === 65 && cyc("clean_stands") === 65,
        "the four presets with a floor must get 65: " + ["wide_shot", "std", "medium_shot", "clean_stands"].map(cyc).join());
      expect(cyc("lowkey") === 0 && cyc("closeup") === 0 && cyc("user_1") === 0, "the other presets and the user's own one must stay: " + [cyc("lowkey"), cyc("closeup"), cyc("user_1")].join());
      expect(env.state("activePresetId") === "wide_shot" && env.state("getSliderVal('gSlCyc')") === 65, "the slider of the active preset must follow, got " + env.state("getSliderVal('gSlCyc')"));
      expect(env.el("gValCyc").textContent === "65%", "...and show it: " + env.el("gValCyc").textContent);
      const onDisk = env.server.disk;
      expect(onDisk["presets_local.json"].find((p) => p.id === "wide_shot").cfg.cycCurve === 65, "the moved presets must be saved on the PC");
      expect((onDisk["user_settings.json"].presetMoves || []).includes("cyc65"), "the settings must remember that the move was made: " + JSON.stringify(onDisk["user_settings.json"].presetMoves));
      const sent = env.of("/presets").filter((r) => r.method === "POST");
      expect(sent.length >= 1 && sent[sent.length - 1].body.find((p) => p.id === "wide_shot").cfg.cycCurve === 65, "the server copy must get the moved presets too");
      await env.open();
      expect(env.of("/session/start")[0].body.params.cycCurve === 65, "the first scan must go with the new value");
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
    expect(env.state("appliedPresetMoves.includes('cyc65')") === true, "the move counts as made");
    expect(env.state("presetsList.find((p) => p.id === 'lowkey').cfg.cycCurve") === 0, "'Темний ключ' keeps the corner");
  });

  // ---------------------------------------------------------------- smoke
  await scenario("smoke: every request asks to protect smoke only where there is smoke; the corner presets go with the floor",
    { scene: { kind: "wide", framing: "wide", dark: false } }, async (env, expect) => {
      await env.open();
      const start = env.of("/session/start")[0];
      const sp = start.body.scenePresets || {};
      expect(start.body.params.smokeAuto === true, "the first scan must ask for it: " + JSON.stringify(start.body.params));
      expect(Object.keys(sp).length === 5 && Object.keys(sp).every((k) => sp[k].smokeAuto === true), "...and so must every set of the automatic preset");
      expect(sp.wide.cycCurve === 65 && sp.medium.cycCurve === 65 && sp.default.cycCurve === 65 && sp.dark.cycCurve === 0 && sp.close.cycCurve === 0,
        "the corner line goes by default in 'Дальній план', 'Середній план', 'Студія' and stays in 'Темний ключ', 'Ближній план': "
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
      env.check("dlgChkSmoke", false);
      await env.settle(900);
      let rc = env.recomputes();
      expect(rc.length === 1 && rc[0].body.params.smokeOn === false && rc[0].body.quick === true, "one light refresh with the protection off");
      expect(env.badge().includes("вимкнено") && env.badge().includes("не знайдено") && env.badge().includes("той самий"),
        "the note must say the result is the same: " + env.badge());
      env.check("dlgChkSmoke", true);
      await env.settle(900);
      rc = env.recomputes();
      expect(rc.length === 2 && rc[1].body.params.smokeOn === true, "one more refresh with the protection on");
      expect(env.badge().includes("не знайдено") && env.badge().includes("нічого не змінює") && env.badge().includes("95–100"),
        "the note must say that nothing changes and how to force the protection: " + env.badge());
      await env.drag("gSlSmoke", 96);                        // "there is smoke, protect it anyway"
      await env.settle(1100);
      rc = env.recomputes();
      expect(rc.length === 3 && rc[2].body.params.smoke === 96, "the slider gives one more refresh");
      expect(env.badge().includes("95–100") && env.badge().includes("збережено") && env.badge().includes("0,48 %"),
        "the note must say that everything smoke-like is kept now: " + env.badge());
      await env.drag("gSlSpots", 90);                        // another control: no words about smoke
      await env.settle(1100);
      expect(env.recomputes().length === 4, "the other slider refreshes as usual");
      expect(!env.badge().includes("95–100"), "the smoke note must not come back after another control: " + env.badge());
    });

  await scenario("a frame with smoke: said when the window opens, and when the protection is switched off",
    { frameSmoke: { share: 0.05, largest: 0.04, found: true }, scene: { kind: "wide", framing: "wide", dark: false } }, async (env, expect) => {
      await env.open();
      await env.settle(300);
      expect(env.badge().includes("Авто-пресет") && env.badge().includes("Дим знайдено") && env.badge().includes("6,0 %"),
        "the opening note must name the preset and the protected smoke: " + env.badge());
      env.click("gBtnSmoke");                                // the switch in the fine settings
      await env.settle(900);
      const rc = env.recomputes();
      expect(rc.length === 1 && rc[0].body.params.smokeOn === false, "one refresh with the protection off");
      expect(env.badge().includes("вимкнено") && env.badge().includes("5,0 %") && env.badge().includes("чиститься"),
        "the note must warn that the smoke is cleaned now: " + env.badge());
      expect(!env.el("dlgChkSmoke").checked, "the checkbox on top must follow the switch");
    });

  await scenario("an older server that says nothing of smoke: no smoke notes, nothing breaks", {}, async (env, expect) => {
    env.check("dlgChkAutoPreset", false);
    await env.open();
    env.check("dlgChkSmoke", false);
    await env.settle(900);
    expect(env.recomputes().length === 1, "the refresh is still asked for");
    expect(env.badge() === "", "no note without an answer about smoke: " + env.badge());
    expect(env.state("sessState.smokeNote") === false, "the request for a note must be closed");
  });

  const failed = results.filter((r) => r.problems.length);
  if (!results.length) {
    console.log("plugin preview: no scenario has that text in its name");
    process.exit(1);
  }
  console.log(failed.length
    ? `plugin preview: ${failed.length} of ${results.length} scenarios FAILED`
    : `plugin preview: ${results.length} scenarios pass (drag -> nothing; release -> one light refresh; Apply carries the settings; views, presets, automatic preset, remembered press, smoke notes)`);
  process.exit(failed.length ? 1 : 0);
}

main().catch((err) => {
  console.log("plugin preview: crashed: " + (err && err.stack ? err.stack : err));
  process.exit(1);
});
