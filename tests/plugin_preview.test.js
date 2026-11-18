// Runs the REAL plugin (uxp-plugin/index.html + main.js) in a simulated browser against a scripted server and
// checks WHEN the plugin asks the server for WHAT while the controls of the big window are used:
//   - nothing is computed while a slider is being dragged;
//   - after the release the preview is refreshed once, the light way (quick: true), without the progress card;
//   - several controls changed in a row give one refresh;
//   - the full-size computation is asked for once: "Застосувати" carries the settings that are on the sliders.
//
//   node tests/plugin_preview.test.js
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
    autoFractions: { fracFine: true, fracMed: true, fracLarge: true }
  }, serverOpts);
  const W = 4, H = 6;

  const reply = (obj, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => obj, arrayBuffer: async () => new ArrayBuffer(0) });
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
          return reply({ ok: true, status: "ready", app: "cleanvinylpro2", version: "test", install_dir: "C:\\CleanVinylPro2", gpu: "Test GPU", provider: "CUDAExecutionProvider", models_loaded: true });
        case "/presets":
          return reply(method === "GET" ? { presets: [], source: "defaults" } : { ok: true });
        case "/settings":
          return reply(method === "GET" ? { exists: false } : { ok: true });
        case "/progress":
          return reply({ ok: true, pct: 50, stage: "…" });
        case "/session/start":
          await waitOrAbort(server.startDelay, init.signal);
          return reply({
            ok: true, session_id: "sess-1", width: W, height: H, preview_w: W, preview_h: H,
            auto_fractions: body.params.autoFractions ? server.autoFractions : { fracFine: body.params.fracFine, fracMed: body.params.fracMed, fracLarge: body.params.fracLarge },
            orig_jpg_b64: "QQ==", comp_jpg_b64: "QQ==", overlay_jpg_b64: "QQ==", stats: {}
          });
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
  const psDoc = { id: 7, mode: "RGBColorMode", layers: [], createPixelLayer: async () => layer, createLayer: async () => layer };
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
    uxp: { storage: { localFileSystem: { getDataFolder: async () => { throw new Error("no disk in the test"); } } }, shell: { openExternal: async () => {} } }
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

  const errors = [];
  w.addEventListener("error", (e) => errors.push(String(e.error || e.message)));
  w.addEventListener("unhandledrejection", (e) => errors.push("unhandled: " + String(e.reason)));
  // Run main.js the way a <script> tag does (its top-level let / const stay visible to the test afterwards)
  const ctx = dom.getInternalVMContext();
  const run = (code, filename) => new vm.Script(code, { filename }).runInContext(ctx);
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

async function scenario(name, serverOpts, fn) {
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

  const failed = results.filter((r) => r.problems.length);
  console.log(failed.length
    ? `plugin preview: ${failed.length} of ${results.length} scenarios FAILED`
    : `plugin preview: ${results.length} scenarios pass (drag -> nothing; release -> one light refresh; Apply carries the settings)`);
  process.exit(failed.length ? 1 : 0);
}

main().catch((err) => {
  console.log("plugin preview: crashed: " + (err && err.stack ? err.stack : err));
  process.exit(1);
});
