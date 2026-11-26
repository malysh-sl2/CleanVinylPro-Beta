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
//   - smoke: the protection is off until it is asked for; every request says that the switch is the user's word
//     ("smokeFaint"), and the smoke controls say in words how much of the frame is kept for smoke - never "no smoke
//     found" (a server before 4.11.0 still gets its own words); a frame that seems to have smoke says so when
//     the window opens;
//   - mask edits: Ctrl + Z / Ctrl + Shift + Z / Ctrl + Y and the two buttons step back and forward, edits reach
//     the server one after another;
//   - "Скинути пресет" gives one built-in preset the values it ships with, after a second press;
//   - the backup of the settings: saved through the server, listed, restored after a second click, with a copy of
//     what was there before;
//   - a dark backdrop takes the dark preset of its framing;
//   - the fast window (4.10.0, the default): pictures of the working size are asked for, nothing is computed by
//     itself after a quick preview or a stroke, the button and Apply compute the real frame; "Детальний перегляд"
//     brings the exact picture by itself back and is kept with the settings; the trace of a stroke is one line
//     however far the pointer jumps; the window says when the AI fill ran on the processor;
//   - one mode: there is no speed button, and every request asks for the full AI fill, whatever settings and
//     presets of an older version say;
//   - the edge of the brush and the eraser: soft unless the user chose the hard one; the choice travels with every
//     stroke and is kept with the settings;
//   - the exact picture comes by itself (4.8.0): a moment after a light refresh the real frame is asked for in the
//     background, without the progress card and without any button; a newer picture is never replaced by an older
//     one; a change of the settings goes first; Apply waits for a run that computes the very frame it needs;
//   - the brush and the eraser are used on the cleaned photo: the mask never switches on by itself;
//   - Ctrl + "+" / Ctrl + "-" / Ctrl + 0 zoom as in Photoshop; the right mouse button drags the photo;
//   - the name without the 2 (4.8.0): what Photoshop is told - the window, the history step, the layer; layers
//     made by an older version are still found by the "До / Після" button of the panel;
//   - a new result leaves "До" (4.16.0): when the bar of a recompute reaches its end - or the light refresh of a
//     slider or a preset is back, or the clothing tick is answered - a window that shows the original goes to the
//     cleaned photo by itself; "Маска" stays; a run that was cancelled, failed or gave way switches nothing, nor
//     does the exact picture that comes by itself.
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
    frameSmoke: null,      // what the frame has of smoke, e.g. { share: 0.05, largest: 0.04, found: true }; with
                           // kept / keptFull: the share that is protected on the user's word below 100 % / at 100 %
    smokeOld: false,       // true = a server before 4.11.0: it knows nothing of "smokeFaint"
    disk: null,            // files in the plugin's data folder, e.g. { "presets_local.json": [...] }; null = no disk
    serverPresets: null,   // the presets the server holds for this user (its presets.json); null = it has none
    oldSceneRule: false,   // true = a server before 4.5.0: a dark frame is offered the "dark" set only
    historyAware: true,    // false = a server before 4.5.0: no steps back / forward for the mask edits
    edits: { undo: 0, redo: 0 },  // the history of mask edits the server holds
    editDelays: [],        // ms the next mask edits take, one by one (then no delay)
    applyStats: null,      // the "stats" of the answer to Apply
    editSeq: 0,            // how many mask edits were answered (each answer carries its number in the picture)
    backupAware: true,     // false = a server before 4.5.0: no /backup/... addresses
    backupSaveFails: false,
    backupFolder: "D:\\Plugin Photoshop\\CleanVinylPro2\\backup",
    backups: [],           // the files of the backup folder, oldest first
    folderOpened: 0,
    // The exact picture by itself (4.8.0) - the rules of engine.py: recompute_session(background=True)
    bgAware: true,         // false = a server before 4.8.0: "background" is ignored, no "rev" / "exact" in the answers
    bgDelay: 250,          // ms one background recompute takes
    bgAnswerDelay: 0,      // ms its answer then spends on the way (a brush stroke made meanwhile is answered first)
    previewSize: null,     // [w, h] of the preview pictures; null = as small as the test photo
    failBackground: 0,     // how many next background recomputes answer with an error
    ownMask: false,        // true = the mask is the user's own drawing ("invert + brush"): never replaced by itself
    progressPct: 50,       // what /progress answers
    rev: 0,                // the number of the pictures last sent
    exact: true,           // the real frame is behind them
    shown: "",             // the settings those pictures belong to
    bgSeen: { started: 0, finished: 0, superseded: 0, skipped: 0 },
    // The newest values win (4.12.0) - the rule of engine.py: a recompute the window waits for stops as soon as
    // another one is asked for and answers {superseded: true}. false = a server before 4.12.0: it finishes the
    // older one first and only then starts the newer one.
    newestWins: true,
    fgSeen: { superseded: 0 }
  }, serverOpts);
  const fgRuns = new Set();          // recomputes the window waits for that have not answered yet
  let fgQueue = Promise.resolve();   // (a server before 4.12.0: one after another)
  if (!server.quickAware) server.bgAware = false;   // (a build that old knows neither)
  const W = 4, H = 6;

  // The picture of every answer says what it is ("light-3": a light refresh, the third picture of this window),
  // so a test sees which one is on screen.
  const pic = (text) => Buffer.from(text).toString("base64");
  // Everything the cleaned frame depends on. Two requests with the same signature ask for the same frame.
  const frameSig = (p) => JSON.stringify([
    p.spots, p.scuffs, p.blur, p.cycCurve, p.feather, !!p.seamOn, p.seam, p.edge, !!p.smokeOn, p.smoke, p.grain,
    !!p.shadow, !!p.removeStands, Math.max(100, Number(p.master) || 0), !!p.fracFine, !!p.fracMed, !!p.fracLarge,
    Number(p.cleanPasses) >= 2 ? 2 : 1
  ]);
  const fractionsOf = (p) => (p.autoFractions ? server.autoFractions : { fracFine: p.fracFine, fracMed: p.fracMed, fracLarge: p.fracLarge });
  const sigOf = (p) => frameSig(Object.assign({}, p, fractionsOf(p)));
  const pictureState = () => (server.bgAware ? { rev: server.rev, exact: server.exact } : {});
  // Background runs in flight. Such a run gives way to every other request that needs the frame.
  const bgRuns = new Set();
  const stopBackground = () => { for (const run of Array.from(bgRuns)) run.giveWay(); };

  const reply = (obj, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => obj, arrayBuffer: async () => new ArrayBuffer(0) });
  // What the engine says of smoke for the parameters `p` (the rules of engine.py: _smoke_faint, _smoke_auto,
  // SMOKE_ALWAYS_FROM)
  function smokeAnswer(p) {
    const fs = server.frameSmoke;
    if (!fs) return null;
    const on = !!p.smokeOn;
    const faint = on && !!p.smokeFaint && !server.smokeOld;
    const auto = on && !!p.smokeAuto && !faint && Number(p.smoke) < 95;
    const usual = fs.share * 1.2;
    let kept = 0;
    if (faint) kept = Number(p.smoke) >= 100 ? (fs.keptFull ?? fs.kept ?? usual) : (fs.kept ?? usual);
    else if (on && (fs.found || !auto)) kept = usual;
    const ans = { share: fs.share, largest: fs.largest, found: fs.found, on, auto, protected: Math.round(kept * 10000) / 10000 };
    if (!server.smokeOld) ans.faint = faint;
    return ans;
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
          return reply(Object.assign({ ok: true, status: "ready", app: "cleanvinylpro2", version: server.version, install_dir: "C:\\CleanVinylPro2", gpu: "Test GPU", provider: "CUDAExecutionProvider", models_loaded: true }, server.healthExtra || {}));
        case "/presets":
          // (server.serverPresets: the copy of the user's presets that the server holds; none = the defaults)
          return reply(method === "GET" ? (server.serverPresets ? { presets: server.serverPresets, source: "user" } : { presets: [], source: "defaults" }) : { ok: true });
        case "/settings":
          return reply(method === "GET" ? { exists: false } : { ok: true });
        case "/progress":
          return reply({ ok: true, pct: server.progressPct, stage: "…" });
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
          stopBackground();
          server.rev = 1;
          server.exact = true;
          server.shown = sigOf(used);
          const ans = Object.assign({
            ok: true, session_id: "sess-1", width: W, height: H,
            preview_w: server.previewSize ? server.previewSize[0] : W, preview_h: server.previewSize ? server.previewSize[1] : H,
            auto_fractions: fractionsOf(used),
            orig_jpg_b64: "QQ==", comp_jpg_b64: pic("start-1"), overlay_jpg_b64: pic("start-1"), stats: server.stats || {}
          }, pictureState());
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
          const p = body.params;
          const background = server.bgAware && body.background === true;
          stopBackground();   // one frame at a time: a background run gives way, also to a newer background run
          if (background) {
            // Nobody waits for this one. Same settings as on screen and the user's own mask: nothing is done.
            const refineOnly = sigOf(p) === server.shown;
            const skipped = () => {
              server.bgSeen.skipped++;
              rec.outcome = "skipped";
              return reply(Object.assign({ ok: true, session_id: body.session_id, skipped: true }, pictureState()));
            };
            if (refineOnly && server.ownMask) return skipped();
            server.bgSeen.started++;
            const run = {};
            const outcome = await new Promise((resolve) => {
              const timer = setTimeout(() => resolve("done"), server.bgDelay);
              run.giveWay = () => { clearTimeout(timer); resolve("superseded"); };
              run.finished = new Promise((r2) => { run.finish = r2; });
              bgRuns.add(run);
            });
            bgRuns.delete(run);
            run.finish();
            if (outcome === "superseded") {
              server.bgSeen.superseded++;
              rec.outcome = "superseded";
              return reply({ ok: true, session_id: body.session_id, superseded: true });
            }
            if (server.failBackground > 0) {
              server.failBackground--;
              rec.outcome = "failed";
              return reply({ ok: false, error: "test failure" }, 500);
            }
            if (refineOnly && server.ownMask) return skipped();   // (drawn while the frame was being computed)
            server.bgSeen.finished++;
            rec.outcome = "done";
          } else if (server.newestWins) {
            fgRuns.forEach((older) => older.giveWay());
            const mine = {};
            const outcome = await new Promise((resolve, reject) => {
              mine.giveWay = () => resolve("superseded");
              fgRuns.add(mine);
              waitOrAbort(server.recomputeDelay, init.signal).then(() => resolve("done"), reject);
            }).finally(() => fgRuns.delete(mine));
            if (outcome === "superseded") {
              server.fgSeen.superseded++;
              rec.outcome = "superseded";
              return reply({ ok: true, session_id: body.session_id, superseded: true });
            }
            if (server.failRecompute > 0) {
              server.failRecompute--;
              return reply({ ok: false, error: "test failure" }, 500);
            }
          } else {
            const before = fgQueue;
            let release;
            fgQueue = new Promise((r2) => { release = r2; });
            try {
              await before;
              await waitOrAbort(server.recomputeDelay, init.signal);
            } finally {
              release();
            }
            if (server.failRecompute > 0) {
              server.failRecompute--;
              return reply({ ok: false, error: "test failure" }, 500);
            }
          }
          rec.outcome = rec.outcome || "done";
          const quick = !background && server.quickAware && !!body.quick && Number(p.cleanPasses || 1) < 2;
          server.rev++;
          server.exact = !quick;
          server.shown = sigOf(p);
          server.ownMask = false;   // any recompute puts the automatic mask back
          const name = (background ? "exact-" : quick ? "light-" : "full-") + server.rev;
          rec.picture = name;
          const ans = Object.assign({
            ok: true, session_id: body.session_id,
            auto_fractions: fractionsOf(p),
            comp_jpg_b64: pic(name), overlay_jpg_b64: pic(name), stats: server.stats || {}
          }, pictureState());
          if (server.quickAware) ans.quick = quick;
          if (server.maskShares.length) ans.mask_share = server.maskShares.shift();
          if (smokeAnswer(p)) ans.smoke = smokeAnswer(p);
          if (server.historyAware) ans.history = { undo: server.edits.undo, redo: server.edits.redo };
          if (background && server.bgAnswerDelay) await sleep(server.bgAnswerDelay);
          return reply(ans);
        }
        case "/session/mask-edit": {
          if (server.editDelays.length) await waitOrAbort(server.editDelays.shift(), init.signal);
          // (the picture of every answer carries the number of the edit: the test sees which one is on screen)
          // A mask edit never waits for a background run and does not stop it.
          const name = "edit-" + (++server.editSeq);
          server.rev++;
          rec.picture = name;
          const ans = Object.assign({ ok: true, inverted: false, comp_jpg_b64: pic(name), overlay_jpg_b64: pic(name) }, pictureState());
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
        case "/session/close":
          stopBackground();   // closing the window stops a background run
          return reply({ ok: true });
        case "/session/stop-background": {
          // the user took hold of a slider: a background run that is on its way stops
          if (!server.bgAware) return reply({ detail: "Not Found" }, 404);
          const stopped = bgRuns.size > 0;
          stopBackground();
          return reply({ ok: true, stopped });
        }
        case "/session/dress-preview":
          return reply(Object.assign({ ok: true, inverted: false, comp_jpg_b64: pic("dress-" + server.rev), overlay_jpg_b64: pic("dress-" + server.rev) }, pictureState()));
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
          // followBackground: the background run computes the very frame Apply needs - Apply waits for it. Otherwise
          // the run gives way and Apply computes the frame itself.
          if (server.bgAware && body.followBackground === true && bgRuns.size) {
            rec.followed = true;
            await Promise.all(Array.from(bgRuns).map((run) => run.finished));
          } else {
            stopBackground();
          }
          await waitOrAbort(server.applyDelay, init.signal);
          const meta = Buffer.from(JSON.stringify({ ok: true, width: W, height: H, channels: 4, bitDepth: 8, hasLayerMask: false, stats: server.applyStats || {} }), "utf8");
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
  // what Photoshop is told by name: the layers that are made, the steps of the History panel, the commands
  const ps = { layersMade: [], history: [], commands: [], modal: null };
  const makeLayer = async (opts) => { ps.layersMade.push(opts && opts.name); return layer; };
  const psDoc = { id: 7, width: W, height: H, mode: "RGBColorMode", layers: [], createPixelLayer: makeLayer, createLayer: makeLayer };
  const hostControl = { suspendHistory: async (opts) => { ps.history.push(opts && opts.name); return 1; }, resumeHistory: async () => {} };
  const stubs = {
    photoshop: {
      app: { documents: [psDoc], activeDocument: psDoc },
      core: { executeAsModal: async (fn, opts) => { ps.commands.push(opts && opts.commandName); return fn({ hostControl }); } },
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
  dlg.uxpShowModal = (opts) => { ps.modal = opts || null; return new Promise((resolve) => { closeModal = resolve; }); };
  dlg.close = (v) => { const r = closeModal; closeModal = null; if (r) r(v); };

  doc.querySelectorAll(".cv-slider").forEach((n) => {
    n.getBoundingClientRect = () => ({ left: 0, top: 0, right: SLIDER_PX, bottom: 10, width: SLIDER_PX, height: 10 });
  });
  // the photo fills this rectangle of the window (a press inside it is a brush / eraser stroke)
  doc.getElementById("dlgStage").getBoundingClientRect = () => ({ left: 0, top: 0, right: 400, bottom: 600, width: 400, height: 600 });
  // ...and this is the part of the window the photo is shown in (zoom and drag are counted from its middle)
  doc.getElementById("dlgViewport").getBoundingClientRect = () => ({ left: 0, top: 0, right: 1000, bottom: 800, width: 1000, height: 800 });

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
  // `more`: other fields of the event, e.g. { button: 2 } for the right mouse button, { clientY: 300 }, { ctrlKey: true }
  let pointerAt = { clientX: 0, clientY: 5 };   // where the pointer was at the last press or move
  const mouse = (target, type, x = 0, more = {}) => {
    const ev = new w.MouseEvent(type, Object.assign({ bubbles: true, cancelable: true, clientX: x, clientY: 5, button: 0 }, more));
    if (type === "mousedown" || type === "mousemove") pointerAt = { clientX: ev.clientX, clientY: ev.clientY };
    target.dispatchEvent(ev);
    return ev;
  };
  const isBackground = (r) => !!(r.body && r.body.background === true);
  const env = {
    w, doc, server, requests, errors, el, ps, psDoc,
    state: (expr) => run(expr, "test-expression"),
    of: (p) => requests.filter((r) => r.path === p),
    // what a control asked for (a light refresh, or a full recompute with the progress card)...
    recomputes: () => requests.filter((r) => r.path === "/session/recompute" && !isBackground(r)),
    // ...and what the window asked for by itself: the exact picture, in the background
    exacts: () => requests.filter((r) => r.path === "/session/recompute" && isBackground(r)),
    click: (id, more) => mouse(el(id), "click", 0, more),
    // a key pressed with the focus on `target` (the document unless said otherwise); what = { key, code, keyCode, ... }
    // (jsdom does not take "keyCode" from the description of the event: it is put on the event afterwards)
    keyDown(what, target) {
      const ev = new w.KeyboardEvent("keydown", Object.assign({ bubbles: true, cancelable: true }, what));
      if (what.keyCode !== undefined) Object.defineProperty(ev, "keyCode", { get: () => what.keyCode });
      (target || doc).dispatchEvent(ev);
      return ev;
    },
    check: (id, on) => { el(id).checked = on; el(id).dispatchEvent(new w.Event("change", { bubbles: true })); },
    press: (id, x, more) => mouse(el(id), "mousedown", x, more),
    move: (x, more) => mouse(doc, "mousemove", x, more),
    // (a mouse button is released where the pointer is - unless the scenario says another place: the moves in
    //  between did not arrive)
    release: (more) => mouse(doc, "mouseup", pointerAt.clientX, Object.assign({ clientY: pointerAt.clientY }, more)),
    mouse,
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
      const text = env.pictureName();
      return text.startsWith("edit-") ? text : "";
    },
    // ...and whatever it is: "start-1", "light-2", "exact-3", "full-4", "edit-1", "dress-2" (see `pic` above)
    pictureName() {
      const src = String(el("dlgCompImg").src || "");
      const b64 = src.split("base64,")[1] || "";
      return Buffer.from(b64, "base64").toString("utf8");
    },
    // where the photo is in the window and how big: what Ctrl + "+" and a drag with the right button change
    zoom: () => run("sessState.zoom", "test-expression"),
    pan: () => run("[sessState.panX, sessState.panY]", "test-expression"),
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
    // The scenarios written for 4.8.0 expect the exact picture by itself and the larger window pictures. Since
    // 4.10.0 that is the "detailed preview", a checkbox that is off unless the user ticks it: those scenarios run
    // with it ticked. A scenario of the fast window (the default) says { detail: false } and gets the panel just
    // as it starts.
    if (!serverOpts || serverOpts.detail !== false) env.state("setDetailPreview(true, false)");
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
    expect(env.exacts().length === 0, "...and no background recompute: the first picture is exact");
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
      // (the last of the four was a switch: since 4.13.0 a switch asks for the exact frame, and it takes the
      //  refresh that the sliders were waiting for with it)
      expect(rs[0].body.quick === undefined && typeof rs[0].body.jobId === "string", "a switch came last: one full recompute for all four");
    }
  });

  await scenario("three sliders one after another give one light refresh", {}, async (env, expect) => {
    await env.open();
    await env.drag("gSlSpots", 90);
    await sleep(200);
    await env.drag("gSlScuffs", 40);
    await sleep(200);
    await env.drag("gSlBlur", 30);
    await env.settle(1000);
    const rs = env.recomputes();
    expect(rs.length === 1 && rs[0].body.quick === true, `one light refresh expected for 3 sliders in a row, got ${rs.length}`);
    if (rs[0]) expect(rs[0].body.params.spots === 90 && rs[0].body.params.scuffs === 40 && rs[0].body.params.blur === 30, "...with all three values");
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

  await scenario("a slider moved while a refresh is running: the refresh starts over at once with both values", { recomputeDelay: 900 }, async (env, expect) => {
    await env.open();
    await env.drag("gSlSpots", 90);
    await sleep(700);                       // the first refresh is on its way now
    expect(env.recomputes().length === 1, "first refresh expected");
    await env.drag("gSlCyc", 60);           // changed while the server is busy
    await sleep(500);                       // (the first one would still be running: it takes 900 ms)
    let rs = env.recomputes();
    expect(rs.length === 2 && rs[1].body.quick === true, `the second refresh must be on its way without waiting for the first: ${rs.length}`);
    expect(rs[0].done && rs[0].outcome === "superseded", "the server must have stopped the first one: " + rs[0].outcome);
    await env.settle(3200);
    rs = env.recomputes();
    expect(rs.length === 2, `two recomputes expected, got ${rs.length}`);
    if (rs[1]) {
      expect(rs[1].body.params.spots === 90 && rs[1].body.params.cycCurve === 60, "the second refresh must carry both values");
    }
    expect(env.state("previewMatchesSettings()") === true && env.state("sessState.recomputing") === false, "the preview must end up to date, nothing left running");
  });

  await scenario("...with a server before 4.12.0: the older refresh is finished first, its picture is not shown, the newer one is", { recomputeDelay: 900, newestWins: false }, async (env, expect) => {
    await env.open();
    await env.drag("gSlSpots", 90);
    await sleep(700);                       // the first refresh is on its way now
    await env.drag("gSlCyc", 60);
    await sleep(900);                       // the first one has answered by now, with a whole picture for the old values
    const rs = env.recomputes();
    expect(rs.length === 2 && rs[0].done && rs[0].outcome === "done" && !rs[1].done,
      `the first answered in full, the second is still running: ${rs.length} requests, ${rs.map((r) => r.outcome + "/" + r.done).join(" ")}`);
    expect(env.state("previewMatchesSettings()") === false, "the picture of the first one is for values that are gone: it must not count as up to date");
    expect(rs[0].picture && env.pictureName() !== rs[0].picture, `...and must not be put on screen: ${env.pictureName()} (the first run made ${rs[0].picture})`);
    expect(env.state("sessState.recomputing") === true && env.badge().includes("Оновлюю"), "the window is still waiting for the newer one: " + env.badge());
    await env.settle(3500);
    expect(env.recomputes().length === 2 && env.state("previewMatchesSettings()") === true,
      `the newer one ends up on screen, nothing more is asked: ${env.recomputes().length} requests, up to date ${env.state("previewMatchesSettings()")}`);
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

  await scenario("ticks recompute the exact frame at once, fraction buttons refresh the light way", {}, async (env, expect) => {
    await env.open();
    env.check("dlgChkStands", true);
    await env.settle(600);
    env.click("dlgFracFine");
    await env.settle(600);
    env.check("gChkShadow", false);
    await env.settle(600);
    const rs = env.recomputes();
    expect(rs.length === 3, `three recomputes expected, got ${rs.length}`);
    expect(rs.length === 3 && rs[0].body.quick === undefined && rs[0].body.jobId && rs[1].body.quick === true && rs[2].body.quick === undefined && rs[2].body.jobId,
      "the two ticks ask for the exact frame (with a progress job), the fraction button for a light refresh: " + rs.map((r) => r.body.quick).join());
    if (rs.length === 3) {
      expect(rs[0].body.params.removeStands === true, "stands removal must be on in the first");
      expect(rs[1].body.params.fracFine === false && rs[1].body.params.autoFractions === false, "fine fraction off, auto off in the second");
      expect(rs.every((r) => r.body.params.smokeOn === false), "smoke protection is off until it is asked for");
      expect(rs[2].body.params.shadow === false, "the shadows switch in the third");
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

  await scenario("2 passes: there is no light way, so the exact picture is computed in the background - by itself", { bgDelay: 600 }, async (env, expect) => {
    await env.open();
    env.click("gPass2");
    await sleep(80);
    expect(env.exacts().length === 0, "the request waits a moment after the click");
    expect(env.badge().includes("Перераховую"), "the badge must say that the preview is being recomputed: " + env.badge());
    await env.waitFor(() => env.exacts().length === 1, 1500);
    expect(env.exacts().length === 1 && env.recomputes().length === 0, `one background recompute and nothing else; got ${env.exacts().length} / ${env.recomputes().length}`);
    const first = env.exacts()[0];
    if (first) {
      expect(first.body.params.cleanPasses === 2 && first.body.quick === undefined && first.body.preserve_edits === true, "2 passes, in full, the strokes kept");
    }
    expect(!env.progressCardVisible(), "no progress card: the window stays usable");
    expect(env.pictureName() === "start-1", "the former picture stays until the new one is ready, got " + env.pictureName());
    await env.waitFor(() => env.pictureName().startsWith("exact-"), 2000);
    expect(env.pictureName().startsWith("exact-"), "the exact picture must appear by itself, got " + env.pictureName());
    expect(env.badge() === "" && env.modeBadge() === "ПІСЛЯ · чисте фото", `nothing left to say: '${env.badge()}' / '${env.modeBadge()}'`);

    await env.drag("gSlSpots", 95);          // a slider: the same - once, after the release
    await sleep(200);
    expect(env.exacts().length === 1, "nothing is sent right at the release");
    await env.waitFor(() => env.exacts().length === 2, 1500);
    await env.waitFor(() => env.exacts().length === 2 && env.exacts()[1].done, 2000);
    await sleep(30);
    expect(env.exacts().length === 2 && env.exacts()[1].body.params.spots === 95, "one more background recompute with the new value");
    expect(env.recomputes().length === 0, "never a recompute that blocks the window");
    expect(env.state("previewMatchesSettings()") === true && env.badge() === "", "the preview is up to date: " + env.badge());

    env.click("dlgFracMed");                 // a fraction button: the same way
    await env.waitFor(() => env.exacts().length === 3 && env.exacts()[2].done, 2500);
    expect(env.exacts().length === 3 && env.recomputes().length === 0, "a fraction button with 2 passes: one background recompute");
    env.click("gPass1");
    await env.waitFor(() => env.recomputes().length === 1, 1500);
    expect(env.recomputes().length === 1 && env.recomputes()[0].body.quick === true, "back to 1 pass: the light refresh is there again");
    await env.waitFor(() => env.exacts().length === 4 && env.exacts()[3].done, 2500);
    expect(env.exacts().length === 4, "...and its exact picture follows");
  });

  await scenario("2 passes with a server before 4.8.0: nothing starts by itself, the badge names the button", { bgAware: false }, async (env, expect) => {
    await env.open();
    env.click("gPass2");
    await env.settle(900);
    expect(env.of("/session/recompute").length === 0, "an older server must not be asked for a recompute that blocks the window");
    expect(env.badge().includes("Перерахувати зараз") && env.badge().includes("restart_gpu_server.bat"), "the badge must name the button and the restart: " + env.badge());
    env.click("dlgFracMed");                 // these buttons recomputed in full at once with such a server - they still do
    await env.settle(500);
    expect(env.of("/session/recompute").length === 1 && env.of("/session/recompute")[0].body.quick === undefined, "a fraction button recomputes in full");
    expect(env.of("/session/recompute").every((r) => r.body.background === undefined), "'background' is never sent to a server that does not know it");
    expect(env.badge() === "", "badge hidden after the full recompute: " + env.badge());
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

  // ---------------------------------------------------------------- the exact picture comes by itself (4.8.0)
  // What a slider does, from the release on:  light refresh (quick picture)  ->  0.7 s of quiet  ->  the real frame
  // is computed in the background  ->  the exact picture replaces the quick one. No button, no progress card.
  const lightDone = (env, n = 1) => env.waitFor(() => env.recomputes().length >= n && env.recomputes()[n - 1].done, 3000);
  const exactDone = (env, n = 1) => env.waitFor(() => env.exacts().length >= n && env.exacts()[n - 1].done, 4000);

  await scenario("the exact picture comes by itself a moment after a light refresh: no button, no progress card", { bgDelay: 900 }, async (env, expect) => {
    await env.open();
    expect(env.modeBadge() === "ПІСЛЯ · чисте фото", "the first picture is exact: " + env.modeBadge());
    env.click("dlgBtnGear");
    await env.drag("gSlSpots", 90);
    await lightDone(env);
    await sleep(30);
    expect(env.pictureName().startsWith("light-"), "the quick picture first, got " + env.pictureName());
    expect(env.modeBadge().includes("швидкий перегляд") && env.modeBadge().includes("уточнюється"), "the corner label must say that the exact picture is coming: " + env.modeBadge());
    expect(env.el("dlgModeBadge").classList.contains("refining") && !env.el("dlgModeBadge").classList.contains("clean"), "...in the colour of 'not final yet'");
    expect(env.badge() === "", "nothing else to say: " + env.badge());
    await sleep(350);
    expect(env.exacts().length === 0, "the exact picture waits for a quiet moment (0.7 s)");
    await env.waitFor(() => env.exacts().length === 1, 1500);
    const x = env.exacts()[0];
    expect(!!x, "the background recompute must be asked for by itself");
    if (x) {
      const waited = x.t - env.recomputes()[0].tDone;
      expect(waited >= 600 && waited <= 1300, `it must start about 0.7 s after the quick picture, started after ${waited} ms`);
      expect(x.body.background === true && x.body.quick === undefined, "it must be a background recompute of the real frame");
      expect(typeof x.body.jobId === "string", "it carries a job id (for the percent)");
      expect(x.body.preserve_edits === true, "the strokes are kept");
      expect(x.body.params.spots === 90 && x.body.params.speedMode === "quality", "the values on the sliders, the full AI fill");
    }
    await sleep(500);                                        // the percent is asked a few times a second
    expect(env.modeBadge().includes("уточнюється… 50 %"), "the corner label must show the percent: " + env.modeBadge());
    expect(!env.progressCardVisible(), "no progress card: the window stays usable");
    expect(env.el("dlgGearPopover").classList.contains("visible"), "the settings popover stays open");
    await exactDone(env);
    await sleep(30);
    expect(env.pictureName().startsWith("exact-"), "the exact picture must be on screen, got " + env.pictureName());
    expect(env.modeBadge() === "ПІСЛЯ · чисте фото", "the corner label: " + env.modeBadge());
    expect(env.el("dlgModeBadge").classList.contains("clean") && !env.el("dlgModeBadge").classList.contains("refining"), "...in the colour of the final picture");
    expect(env.badge() === "" && env.state("previewMatchesSettings()") === true, "up to date, nothing to say: " + env.badge());
    await env.settle(1500);
    expect(env.exacts().length === 1 && env.recomputes().length === 1, `nothing more is asked for: ${env.recomputes().length} light, ${env.exacts().length} exact`);
    expect(env.server.bgSeen.finished === 1 && env.server.bgSeen.superseded === 0, "the one run finished");
  });

  await scenario("a slider held, or moved again, puts the exact picture off: the light refresh always goes first", { bgDelay: 1500 }, async (env, expect) => {
    await env.open();
    await env.drag("gSlSpots", 90);
    await lightDone(env);
    await sleep(300);
    env.press("gSlScuffs", 130);                             // a slider is taken before the exact request went
    await sleep(900);
    expect(env.exacts().length === 0, "nothing is computed while a slider is held");
    env.release();                                           // released where it was: nothing changed
    await env.waitFor(() => env.exacts().length === 1, 2000);
    expect(env.exacts().length === 1 && env.recomputes().length === 1, "the exact picture is asked for after the release");
    expect(env.of("/session/stop-background").length === 0, "nothing was running when the slider was taken: the server is not bothered");
    await sleep(300);                                        // the background run is on its way...
    expect(!env.exacts()[0].done, "the background run must still be running");
    env.press("dlgSlBlend", 60);                             // Blend changes nothing of the frame: the run goes on
    await sleep(60);
    env.release();
    env.press("gSlDress", 60);                               // ...and so does Clothing
    await sleep(60);
    env.release();
    expect(env.of("/session/stop-background").length === 0 && !env.exacts()[0].done, "Blend and Clothing must not stop the background run");
    env.press("gSlSpots", 180);                              // a slider that changes the frame is taken...
    await sleep(80);
    expect(env.of("/session/stop-background").length === 1, "the server must be told at once that the frame will not be wanted");
    expect(env.exacts()[0].done && env.exacts()[0].outcome === "superseded", "the background run stops while the slider is still held");
    expect(env.recomputes().length === 1, "nothing else is asked while the slider is held");
    for (const x of [176, 170, 164, 160]) { await sleep(15); env.move(x); }
    env.release();                                           // ...moved and released
    await lightDone(env, 2);
    await sleep(30);
    expect(env.server.bgSeen.superseded === 1, "one background run was stopped");
    expect(env.of("/session/stop-background").length === 1, "one stop request, not more");
    expect(env.pictureName().startsWith("light-") && env.recomputes()[1].body.params.spots === 80, "the quick picture for the new value, got " + env.pictureName());
    expect(env.modeBadge().includes("уточнюється"), "still a quick picture: " + env.modeBadge());
    expect(env.exacts().length === 1, "no second exact request before the quiet moment");
    await exactDone(env, 2);
    await sleep(30);
    expect(env.exacts().length === 2 && env.exacts()[1].body.params.spots === 80, "one more background run, with the new value");
    expect(env.pictureName().startsWith("exact-") && env.modeBadge() === "ПІСЛЯ · чисте фото", `the exact picture at the end: ${env.pictureName()} / ${env.modeBadge()}`);
    await env.settle(1200);
    expect(env.exacts().length === 2 && env.recomputes().length === 2, "and nothing after it");
  });

  await scenario("Blend or Clothing taken while a refresh was waiting: what was put off goes on after the release", { bgDelay: 300 }, async (env, expect) => {
    await env.open();
    await env.drag("gSlSpots", 90);
    await lightDone(env);
    await sleep(300);
    env.press("dlgSlBlend", 120);                            // Blend is taken before the exact request went...
    await sleep(900);
    expect(env.exacts().length === 0, "nothing starts while a slider is held");
    env.release();                                           // ...and released: the exact picture is still due
    await exactDone(env);
    await sleep(30);
    expect(env.exacts().length === 1 && env.modeBadge() === "ПІСЛЯ · чисте фото", `the exact picture must come after the release: ${env.exacts().length} / ${env.modeBadge()}`);
    env.click("dlgBtnGear");
    env.click("gBtnDress");                                  // (the Clothing slider works only with the switch on)
    await env.waitFor(() => env.of("/session/dress-preview").length === 1 && env.of("/session/dress-preview")[0].done, 1000);
    env.click("dlgFracMed");                                 // a light refresh is due in a moment...
    await sleep(40);
    env.press("gSlDress", 100);                              // ...and Clothing is taken before it went
    expect(env.state("activeDragSliderId") === "gSlDress", "the Clothing slider is held");
    await sleep(600);
    expect(env.recomputes().length === 1, "nothing is computed while a slider is held");
    env.release();
    await lightDone(env, 2);
    expect(env.recomputes().length === 2 && env.recomputes()[1].body.quick === true, "the light refresh that was put off must go on after the release");
    await exactDone(env, 2);
    await sleep(30);
    expect(env.exacts().length === 2 && env.badge() === "" && env.modeBadge() === "ПІСЛЯ · чисте фото", `...and its exact picture follows: '${env.badge()}' / '${env.modeBadge()}'`);
    expect(env.of("/session/stop-background").length === 0, "Blend and Clothing never ask the server to stop anything");
  });

  await scenario("the brush works while the exact picture is on its way; an older picture never replaces a newer one", { bgDelay: 600, bgAnswerDelay: 600 }, async (env, expect) => {
    await env.open();
    await env.drag("gSlSpots", 90);
    await lightDone(env);
    await env.waitFor(() => env.exacts().length === 1, 2000);
    await sleep(150);
    env.press("dlgViewport", 100);                           // a stroke while the frame is being computed
    env.move(120);
    env.release();
    await env.waitFor(() => env.picture() === "edit-1", 400);
    expect(env.picture() === "edit-1", "the stroke must be answered at once, not after the background run; on screen: " + env.pictureName());
    expect(!env.exacts()[0].done, "(the background run is still on its way)");
    expect(env.server.bgSeen.superseded === 0, "a stroke does not stop the background run");
    await env.waitFor(() => env.server.bgSeen.finished === 1, 1500);   // the frame is ready, its answer is on the way
    env.press("dlgViewport", 200);                           // one more stroke: it is answered before that answer arrives
    env.move(220);
    env.release();
    await env.waitFor(() => env.picture() === "edit-2", 400);
    expect(env.picture() === "edit-2" && !env.exacts()[0].done, "the second stroke is on screen before the answer of the background run");
    await exactDone(env);
    await sleep(40);
    expect(env.picture() === "edit-2", "the older picture of the background run must not replace the stroke; on screen: " + env.pictureName());
    expect(env.state("sessState.history.undo") === 2, "...nor its count of steps; got " + env.state("sessState.history.undo"));
    expect(env.modeBadge() === "ПІСЛЯ · чисте фото", "the picture on screen is exact (the stroke was made on the real frame): " + env.modeBadge());
    expect(env.state("previewMatchesSettings()") === true && env.badge() === "", "up to date: " + env.badge());
    await env.settle(1500);
    expect(env.exacts().length === 1 && env.recomputes().length === 1, "nothing more is asked for");
  });

  await scenario("a stroke on a quick picture: the exact one waits until the brush rests, then comes", { bgDelay: 300 }, async (env, expect) => {
    await env.open();
    await env.drag("gSlSpots", 90);
    await lightDone(env);
    await sleep(350);
    env.press("dlgViewport", 100);                           // the mouse button goes down before the exact request went
    env.move(120);
    await sleep(800);
    expect(env.exacts().length === 0, "nothing starts while a stroke is being drawn");
    env.release();
    await env.waitFor(() => env.picture() === "edit-1", 500);
    expect(env.modeBadge().includes("уточнюється"), "the stroke is on a quick picture, its exact version is still due: " + env.modeBadge());
    await sleep(350);
    expect(env.exacts().length === 0, "a quiet moment after the stroke first");
    await exactDone(env);
    await sleep(30);
    expect(env.exacts().length === 1 && env.pictureName().startsWith("exact-"), "then the exact picture comes, got " + env.pictureName());
    expect(env.modeBadge() === "ПІСЛЯ · чисте фото", "the corner label: " + env.modeBadge());
  });

  await scenario("the mask is the user's own drawing: the server declines once, nothing is asked in a loop", {}, async (env, expect) => {
    await env.open();
    await env.drag("gSlSpots", 90);
    await lightDone(env);
    env.server.ownMask = true;                               // as after "inversion + brush"
    await exactDone(env);
    await sleep(40);
    expect(env.exacts().length === 1 && env.exacts()[0].outcome === "skipped", "one request, declined");
    expect(env.pictureName().startsWith("light-"), "the picture stays, got " + env.pictureName());
    expect(env.modeBadge() === "ПІСЛЯ · швидкий перегляд", "a quick picture that stays for now: " + env.modeBadge());
    await env.settle(2000);
    expect(env.exacts().length === 1, `nothing is asked again by itself, got ${env.exacts().length} requests`);
    env.press("dlgViewport", 100);                           // a stroke: one more try (the mask may be the automatic one again)
    env.move(120);
    env.release();
    await exactDone(env, 2);
    await env.settle(1500);
    expect(env.exacts().length === 2 && env.exacts()[1].outcome === "skipped", `one more request after the stroke, not more; got ${env.exacts().length}`);
    env.click("dlgBtnApply");                                // Apply computes the real frame in that case, as always
    await env.waitFor(() => env.state("sessState.open") === false, 3000);
    const a = env.of("/session/apply")[0];
    expect(!!a && a.body.followBackground === false && a.body.params.spots === 90, "Apply carries the values and follows nothing");
  });

  await scenario("a failed exact recompute is said once and not retried in a loop; the next change tries again", { failBackground: 1 }, async (env, expect) => {
    await env.open();
    await env.drag("gSlSpots", 90);
    await exactDone(env);
    await sleep(40);
    expect(env.exacts()[0].outcome === "failed", "the background recompute failed");
    expect(env.badge().includes("Точний перегляд не вдалося") && env.badge().includes("test failure"), "the badge must say so: " + env.badge());
    expect(env.badge().includes("Застосувати"), "...and that Apply still computes the frame: " + env.badge());
    expect(env.modeBadge() === "ПІСЛЯ · швидкий перегляд", "the corner label does not promise what is not coming: " + env.modeBadge());
    expect(env.el("footerStatus").className.includes("error") === false, "the panel footer is not turned red for it");
    await env.settle(2200);
    expect(env.exacts().length === 1, `no retry by itself, got ${env.exacts().length} requests`);
    await env.drag("gSlSpots", 85);
    await exactDone(env, 2);
    await sleep(40);
    expect(env.exacts().length === 2 && env.pictureName().startsWith("exact-"), "the next change tries again and gets the exact picture, got " + env.pictureName());
    expect(env.badge() === "" && env.modeBadge() === "ПІСЛЯ · чисте фото", `nothing left to say: '${env.badge()}' / '${env.modeBadge()}'`);
  });

  await scenario("'Застосувати' while the exact picture for the same values is on its way waits for that run", { bgDelay: 1200, applyDelay: 100 }, async (env, expect) => {
    await env.open();
    await env.drag("gSlSpots", 90);
    await env.waitFor(() => env.exacts().length === 1, 3000);
    await sleep(200);
    env.click("dlgBtnApply");
    await sleep(150);
    expect(env.progressCardVisible(), "Apply shows its progress card");
    await env.waitFor(() => env.state("sessState.open") === false, 4000);
    const a = env.of("/session/apply");
    expect(a.length === 1 && a[0].body.followBackground === true, "Apply must ask to wait for the running background recompute");
    expect(a[0] && a[0].followed === true, "...and the server waited for it");
    expect(env.server.bgSeen.superseded === 0 && env.server.bgSeen.finished === 1, "the frame was computed once, not stopped and started again");
    expect(a[0] && a[0].body.params.spots === 90, "Apply carries the values");
    expect(env.exacts().length === 1 && env.recomputes().length === 1, "no other request");
    expect(env.el("footerStatus").className.includes("error") === false, "no error expected: " + env.el("footerStatus").textContent);
  });

  await scenario("'Застосувати' follows nothing when the values changed since, or when nothing is on its way", { bgDelay: 1500, applyDelay: 100 }, async (env, expect) => {
    await env.open();
    await env.drag("gSlSpots", 90);
    await env.waitFor(() => env.exacts().length === 1, 3000);
    await sleep(100);
    // New values by a button: unlike a slider that is taken, a click does not stop the background run at once -
    // the run in flight goes on computing the former values until the refresh, or Apply, arrives.
    const medBefore = env.state("fracMed");
    env.click("dlgBtnGear");
    env.click("dlgFracMed");
    await sleep(20);
    expect(env.state("fracMed") === !medBefore && !env.exacts()[0].done, "the values changed and the run for the former ones is still on its way");
    env.click("dlgBtnApply");
    await env.waitFor(() => env.state("sessState.open") === false, 4000);
    let a = env.of("/session/apply");
    expect(a.length === 1 && a[0].body.followBackground === false, "Apply must not wait for a run that computes other values");
    expect(a[0] && a[0].followed !== true, "...and the server did not wait for it");
    expect(a[0] && a[0].body.params.fracMed === !medBefore && a[0].body.params.spots === 90, "Apply carries the current values");
    expect(env.server.bgSeen.superseded === 1 && env.of("/session/stop-background").length === 0, "the background run gave way to Apply");
    await env.waitFor(() => env.state("isBusy") === false);
    await env.open();                                        // a new window: the picture is exact, nothing is running
    await env.settle(900);
    expect(env.exacts().length === 1, "a new window asks for nothing by itself");
    env.click("dlgBtnApply");
    await env.waitFor(() => env.state("sessState.open") === false, 4000);
    a = env.of("/session/apply");
    expect(a.length === 2 && a[1].body.followBackground === false, "nothing to follow");
  });

  await scenario("closing the window while the exact picture is on its way: nothing breaks, the next window starts clean", { bgDelay: 1500 }, async (env, expect) => {
    await env.open();
    await env.drag("gSlSpots", 90);
    await env.waitFor(() => env.exacts().length === 1, 3000);
    await sleep(200);
    env.click("dlgBtnCancel");
    await env.waitFor(() => env.state("isBusy") === false);
    await env.waitFor(() => env.exacts()[0].done, 3000);
    expect(env.exacts()[0].outcome === "superseded", "closing the window stops the background run");
    expect(env.state("sessState.exactTimer") === null && env.state("sessState.exactPollTimer") === null, "no timer of the closed window is left");
    await env.open();
    expect(env.pictureName() === "start-1" && env.modeBadge() === "ПІСЛЯ · чисте фото", `a new window: its own first picture, exact: ${env.pictureName()} / ${env.modeBadge()}`);
    env.press("dlgViewport", 100);                           // (the count of pictures starts again with the new window)
    env.move(120);
    env.release();
    await env.waitFor(() => env.picture().startsWith("edit-"), 1000);
    expect(env.picture().startsWith("edit-"), "a stroke in the new window is shown, got " + env.pictureName());
    await env.settle(1200);
    expect(env.exacts().length === 1 && env.recomputes().length === 1, "the new window asked for no recompute");
  });

  await scenario("a server before 4.8.0: no background requests at all, the window works as it did", { bgAware: false, recomputeDelay: 200 }, async (env, expect) => {
    await env.open();
    await env.drag("gSlSpots", 90);
    await lightDone(env);
    await env.settle(1800);
    expect(env.of("/session/recompute").length === 1 && env.recomputes()[0].body.quick === true, "the light refresh, as before");
    expect(env.of("/session/recompute").every((r) => r.body.background === undefined), "'background' must never be sent to a server that does not know it (it would recompute in full and make the window wait)");
    expect(env.modeBadge() === "ПІСЛЯ · чисте фото" && env.badge() === "", `the labels of 4.7.0: '${env.modeBadge()}' / '${env.badge()}'`);
    env.press("dlgViewport", 100);                           // strokes: their pictures carry no number, each one is shown
    env.move(120);
    env.release();
    await env.waitFor(() => env.picture() === "edit-1", 1000);
    expect(env.picture() === "edit-1" && env.view() === "result", "a stroke is shown on the photo");
    env.click("dlgBtnGear");
    env.click("gBtnRecompute");                              // the button gives the exact picture, with the progress card
    await sleep(100);
    expect(env.progressCardVisible(), "the progress card of the full recompute");
    await env.settle(700);
    expect(env.of("/session/recompute").length === 2 && env.of("/session/recompute")[1].body.quick === undefined, "one full recompute");
    env.click("dlgBtnApply");
    await env.waitFor(() => env.state("sessState.open") === false, 3000);
    expect(env.of("/session/apply")[0].body.followBackground === false, "nothing to follow");
  });

  await scenario("'↻ Перерахувати зараз' still works: the full recompute goes first and leaves nothing to refine", { bgDelay: 1500, recomputeDelay: 300 }, async (env, expect) => {
    await env.open();
    await env.drag("gSlSpots", 90);
    await env.waitFor(() => env.exacts().length === 1, 3000);
    await sleep(150);
    env.click("dlgBtnGear");
    expect(env.el("gBtnRecompute").textContent.includes("Перерахувати зараз"), "the button says what it does: " + env.el("gBtnRecompute").textContent);
    env.click("gBtnRecompute");
    await sleep(120);
    expect(env.progressCardVisible(), "the button shows the progress card");
    await env.waitFor(() => env.recomputes().length === 2 && env.recomputes()[1].done, 3000);
    await sleep(40);
    expect(env.recomputes()[1].body.quick === undefined && env.recomputes()[1].body.background === undefined, "a full recompute that is waited for");
    expect(env.server.bgSeen.superseded === 1, "the background run gave way to it");
    expect(env.pictureName().startsWith("full-") && env.modeBadge() === "ПІСЛЯ · чисте фото", `the exact picture of the button: ${env.pictureName()} / ${env.modeBadge()}`);
    expect(!env.progressCardVisible(), "the progress card is gone");
    await env.settle(1500);
    expect(env.exacts().length === 1, "no exact request after a full recompute: the picture is exact already");
  });

  await scenario("the clothing switch on a quick picture does not get in the way of the exact one", { bgDelay: 400 }, async (env, expect) => {
    await env.open();
    env.click("dlgBtnGear");
    await env.drag("gSlSpots", 90);
    await lightDone(env);
    env.click("gBtnDress");                                  // answered at once, the frame is not recomputed for it
    await env.waitFor(() => env.of("/session/dress-preview").length === 1 && env.of("/session/dress-preview")[0].done, 1000);
    await sleep(30);
    expect(env.pictureName().startsWith("dress-"), "the clothing picture is shown, got " + env.pictureName());
    expect(env.modeBadge().includes("уточнюється"), "still a quick picture: " + env.modeBadge());
    await exactDone(env);
    await sleep(30);
    expect(env.exacts().length === 1 && env.pictureName().startsWith("exact-") && env.modeBadge() === "ПІСЛЯ · чисте фото", `then the exact picture: ${env.pictureName()} / ${env.modeBadge()}`);
    expect(env.recomputes().length === 1, "the clothing switch asked for no recompute");
  });

  // ---------------------------------------------------------------- zoom keys, dragging with the right button
  await scenario("Ctrl + '+' and Ctrl + '−' zoom as in Photoshop, Ctrl + 0 fits the photo", { previewSize: [800, 1200] }, async (env, expect) => {
    await env.open();
    const fit = env.state("sessState.fitZoom");
    const near = (a, b) => Math.abs(a - b) < 1e-6;
    expect(near(env.zoom(), fit) && fit > 0.5 && fit < 0.7, "the photo is fitted into the window at the start: " + env.zoom());
    let ev = env.key("Equal", "=", { ctrlKey: true });
    expect(near(env.zoom(), fit * 1.4), "Ctrl + '=' (the '+' key) zooms in, got " + env.zoom() / fit);
    expect(ev.defaultPrevented, "the key is taken by the window");
    env.key("Equal", "+", { ctrlKey: true, shiftKey: true });
    expect(near(env.zoom(), fit * 1.96), "Ctrl + Shift + '=' is the same key, got " + env.zoom() / fit);
    env.key("NumpadAdd", "+", { ctrlKey: true });
    expect(near(env.zoom(), fit * 2.744), "the '+' of the numeric pad zooms in, got " + env.zoom() / fit);
    expect(env.el("dlgZoomLabel").textContent === "274%", "the label shows the zoom: " + env.el("dlgZoomLabel").textContent);
    ev = env.key("Minus", "-", { ctrlKey: true });
    expect(near(env.zoom(), fit * 1.96) && ev.defaultPrevented, "Ctrl + '−' zooms out, got " + env.zoom() / fit);
    env.key("NumpadSubtract", "-", { ctrlKey: true });
    expect(near(env.zoom(), fit * 1.4), "the '−' of the numeric pad zooms out, got " + env.zoom() / fit);
    env.key("", "=", { metaKey: true });                     // a host that names the key only by its character; Cmd on a Mac
    expect(near(env.zoom(), fit * 1.96), "the key is known by its character too, got " + env.zoom() / fit);
    env.key("", "", { ctrlKey: true, keyCode: 189 });        // ...or only by its number
    expect(near(env.zoom(), fit * 1.4), "the key is known by its number too, got " + env.zoom() / fit);

    // the middle of the view stays where it is: what was dragged aside moves away from the middle in proportion
    env.press("dlgViewport", 500, { button: 2, clientY: 400 });
    env.move(540, { clientY: 370 });
    env.release({ button: 2 });
    expect(env.pan()[0] === 40 && env.pan()[1] === -30, "dragged by (40, -30): " + env.pan());
    env.key("Equal", "=", { ctrlKey: true });
    expect(near(env.pan()[0], 56) && near(env.pan()[1], -42), "zooming keeps the middle of the view: " + env.pan());
    env.key("Digit0", "0", { ctrlKey: true });
    expect(near(env.zoom(), fit) && env.pan()[0] === 0 && env.pan()[1] === 0, "Ctrl + 0 fits the photo into the window: " + env.zoom() + " / " + env.pan());
    expect(env.el("dlgZoomLabel").textContent === "100%", "the label: " + env.el("dlgZoomLabel").textContent);

    for (let i = 0; i < 30; i++) env.key("Equal", "=", { ctrlKey: true });
    expect(near(env.zoom(), 6.0), "zooming in stops at the limit, got " + env.zoom());
    for (let i = 0; i < 40; i++) env.key("Minus", "-", { ctrlKey: true });
    expect(near(env.zoom(), 0.15), "zooming out stops at the limit, got " + env.zoom());
    env.key("Numpad0", "0", { ctrlKey: true });

    // not a zoom: the same keys without Ctrl, with Alt, or typed into a text field (each tried by itself: a
    // zoom in followed by a zoom out would look like nothing)
    ev = env.key("Equal", "=");
    expect(near(env.zoom(), fit) && !ev.defaultPrevented, "'=' without Ctrl must not zoom: " + env.zoom() / fit);
    ev = env.key("Minus", "-");
    expect(near(env.zoom(), fit) && !ev.defaultPrevented, "'-' without Ctrl must not zoom: " + env.zoom() / fit);
    env.key("NumpadAdd", "+");
    env.key("Digit0", "0");
    expect(near(env.zoom(), fit), "the numeric pad without Ctrl must not zoom: " + env.zoom() / fit);
    env.key("Equal", "=", { ctrlKey: true, altKey: true });
    expect(near(env.zoom(), fit), "Ctrl + Alt + '=' must not zoom: " + env.zoom() / fit);
    const field = env.doc.createElement("input");
    field.type = "text";
    env.el("retouchModal").appendChild(field);
    ev = env.key("Equal", "=", { ctrlKey: true }, field);
    expect(near(env.zoom(), fit), "the keys typed into a text field must not zoom: " + env.zoom() / fit);
    expect(!ev.defaultPrevented, "a text field keeps its own keys");
    field.remove();

    // the two buttons and the wheel go on working
    env.click("dlgZoomIn");
    expect(near(env.zoom(), fit * 1.25), "the '+' button, got " + env.zoom() / fit);
    env.click("dlgZoomOut");
    expect(near(env.zoom(), fit), "the '−' button, got " + env.zoom() / fit);
    env.el("dlgViewport").dispatchEvent(new env.w.WheelEvent("wheel", { bubbles: true, cancelable: true, deltaY: -100, clientX: 500, clientY: 400 }));
    expect(near(env.zoom(), fit * 1.14), "the wheel, got " + env.zoom() / fit);
    env.click("dlgZoomLabel");
    expect(near(env.zoom(), fit), "a click on the label fits the photo");
    expect(env.of("/session/recompute").length === 0 && env.edits().length === 0, "zooming and dragging ask the server for nothing");

    env.click("dlgBtnCancel");                               // the window is closed: the keys are not ours any more
    await env.waitFor(() => env.state("isBusy") === false);
    ev = env.key("Equal", "=", { ctrlKey: true });
    expect(!ev.defaultPrevented, "with the window closed the keys are left alone");
  });

  await scenario("the right mouse button drags the photo with any tool; no stroke, no menu", { previewSize: [800, 1200] }, async (env, expect) => {
    await env.open();
    const vp = env.el("dlgViewport");
    for (const tool of ["eraser", "brush", "pan"]) {
      env.state(`setActiveTool(${JSON.stringify(tool)})`);
      env.key("Digit0", "0", { ctrlKey: true });
      const down = env.press("dlgViewport", 300, { button: 2, clientY: 200 });
      expect(env.state("sessState.isPanning") === true && env.state("sessState.isDrawing") === false, `${tool}: the right button starts a drag, not a stroke`);
      expect(down.defaultPrevented, `${tool}: the press is taken by the window`);
      expect(vp.style.cursor === "grabbing", `${tool}: the pointer shows a grabbing hand, got '${vp.style.cursor}'`);
      env.move(340, { clientY: 260 });
      expect(env.pan()[0] === 40 && env.pan()[1] === 60, `${tool}: the photo follows the pointer: ${env.pan()}`);
      env.move(250, { clientY: 180 });
      expect(env.pan()[0] === -50 && env.pan()[1] === -20, `${tool}: ...in every direction: ${env.pan()}`);
      env.release({ button: 2 });
      expect(env.state("sessState.isPanning") === false, `${tool}: the drag ends with the release`);
      env.move(400, { clientY: 400 });
      expect(env.pan()[0] === -50 && env.pan()[1] === -20, `${tool}: nothing moves after the release: ${env.pan()}`);
      expect(env.state("sessState.tool") === tool, `${tool}: the tool is the one that was chosen, got ${env.state("sessState.tool")}`);
    }
    expect(env.view() === "result" && env.edits().length === 0, "no stroke was made and the view did not change");

    // the menu of the right button must not open over the photo
    const menu = env.mouse(vp, "contextmenu", 300, { button: 2 });
    expect(menu.defaultPrevented, "the context menu is suppressed over the photo");

    // a host that reports the menu at the press (before any move) must not end the drag...
    env.state("setActiveTool('brush')");
    env.key("Digit0", "0", { ctrlKey: true });
    env.press("dlgViewport", 300, { button: 2, clientY: 200 });
    env.mouse(vp, "contextmenu", 300, { button: 2 });
    env.move(330, { clientY: 200 });
    expect(env.state("sessState.isPanning") === true && env.pan()[0] === 30, "a menu event at the press does not end the drag: " + env.pan());
    // ...and one that reports the release only this way ends it there
    env.mouse(vp, "contextmenu", 330, { button: 2 });
    expect(env.state("sessState.isPanning") === false, "a menu event after the move ends the drag");
    env.move(400, { clientY: 200 });
    expect(env.pan()[0] === 30, "nothing moves afterwards: " + env.pan());

    // a host that reports the right button through pointer events only
    env.key("Digit0", "0", { ctrlKey: true });
    env.mouse(vp, "pointerdown", 300, { button: 2, clientY: 200 });
    expect(env.state("sessState.isPanning") === true, "pointerdown with the right button starts the drag");
    env.mouse(env.doc, "pointermove", 320, { clientY: 250 });
    expect(env.pan()[0] === 20 && env.pan()[1] === 50, "the photo follows: " + env.pan());
    env.mouse(env.doc, "pointerup", 320, { button: 2 });
    expect(env.state("sessState.isPanning") === false, "pointerup ends it");

    // the left button still draws, the middle button and Space + mouse still drag
    env.key("Digit0", "0", { ctrlKey: true });
    env.press("dlgViewport", 100);
    expect(env.state("sessState.isDrawing") === true && env.state("sessState.isPanning") === false, "the left button draws");
    env.move(120);
    env.release();
    await env.waitFor(() => env.edits().length === 1, 1000);
    expect(env.edits().length === 1 && env.pan()[0] === 0, "one stroke, the photo did not move");
    env.press("dlgViewport", 300, { button: 1 });
    env.move(310);
    env.release({ button: 1 });
    expect(env.pan()[0] === 10, "the middle button drags: " + env.pan());
    env.key("Space", " ");
    env.press("dlgViewport", 300);
    env.move(325);
    env.release();
    env.doc.body.dispatchEvent(new env.w.KeyboardEvent("keyup", { bubbles: true, code: "Space", key: " " }));
    expect(env.pan()[0] === 35 && env.edits().length === 1, "Space + mouse drags and does not draw: " + env.pan());
  });

  // ---------------------------------------------------------------- the name (4.8.0: without the 2)
  await scenario("the name has no 2: the panel, the window, the history step, the new layer; a layer made by 4.7.0 is still found", {}, async (env, expect) => {
    const name = "Чистий Вініл Pro";
    expect(env.doc.title === name, "the title of the panel: " + env.doc.title);
    expect(env.doc.querySelector(".brand-title").textContent === name, "the name on the panel: " + env.doc.querySelector(".brand-title").textContent);
    await env.open();
    expect(env.ps.modal && env.ps.modal.title === name, "the title of the big window: " + (env.ps.modal && env.ps.modal.title));
    env.click("dlgBtnApply");
    await env.waitFor(() => env.ps.layersMade.length === 1, 3000);
    await env.waitFor(() => env.state("isBusy") === false);
    expect(env.ps.layersMade.join() === "Чистий вініл (AI)", "the layer must be made under the name without the 2: " + env.ps.layersMade.join());
    expect(env.ps.history.join() === name, "the step of the History panel: " + env.ps.history.join());
    const with2 = env.ps.commands.concat(env.ps.history, env.ps.layersMade).filter((text) => /ініл (Pro )?2/.test(String(text)));
    expect(with2.length === 0 && env.ps.commands.length >= 2, "nothing Photoshop is told may carry the 2: " + with2.join(" | "));

    // "До / Після" of the panel finds the layer of this plugin by its name - the new one and the one of 4.7.0
    const tryLayers = async (layers) => {
      env.psDoc.layers = layers;
      env.state("lastCreatedLayerId = null");
      env.click("btnCompare");
      await sleep(40);
    };
    const made47 = { id: 5, name: "Чистий вініл 2 (AI)", visible: true };
    await tryLayers([{ id: 1, name: "Фон", visible: true }, made47]);
    expect(made47.visible === false, "a layer made by 4.7.0 must still be found and hidden by 'До / Після'; " + env.footer());
    env.click("btnCompare");
    await sleep(40);
    expect(made47.visible === true, "...and shown again");
    const made48 = { id: 6, name: "Чистий вініл (AI)", visible: true };
    await tryLayers([made48]);
    expect(made48.visible === false, "a layer with the new name is found; " + env.footer());
    const inGroup = { id: 9, name: "Чистий вініл 2 (Виділення)", visible: true };
    await tryLayers([{ id: 8, name: "Група 1", visible: true, layers: [inGroup] }]);
    expect(inGroup.visible === false, "a 'selection' layer of 4.7.0 inside a group is found; " + env.footer());
    const selection48 = { id: 10, name: "Чистий вініл (Виділення)", visible: true };
    await tryLayers([selection48]);
    expect(selection48.visible === false, "a 'selection' layer with the new name is found; " + env.footer());
    const foreign = { id: 11, name: "Чистий вініл 3 (AI)", visible: true };
    await tryLayers([foreign, { id: 12, name: "Фон", visible: true }]);
    expect(foreign.visible === true, "a layer of another name is left alone");
    expect(env.footer().includes("«Чистий вініл (AI)» ще не створено"), "...and the panel names the layer it looks for: " + env.footer());
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

  await scenario("the brush and the eraser work on the cleaned photo: the mask never switches on by itself", { editDelays: [300] }, async (env, expect) => {
    await env.open();
    const dots = () => env.el("dlgStrokeDots");
    expect(env.view() === "result", "cleaned photo first");
    env.press("dlgViewport", 100);                           // inside the photo, the eraser is the tool on start
    expect(env.view() === "result", "a stroke must not switch the mask on; got " + env.view());
    env.move(120);
    env.move(140);
    expect(env.shown("dlgStrokeDots") && dots().children.length >= 2, "the trace of the stroke must be seen over the photo while drawing");
    env.release();
    await sleep(120);                                        // the server is still busy with the stroke
    expect(env.view() === "result" && dots().children.length >= 2, "the trace stays until the answer comes");
    expect(env.pictureName() === "start-1", "nothing new on screen yet: " + env.pictureName());
    await env.waitFor(() => env.picture() === "edit-1", 1500);
    const edits = env.of("/session/mask-edit");
    expect(edits.length === 1 && edits[0].body.op === "stroke" && edits[0].body.erase === true, "the eraser stroke must reach the server");
    expect(env.picture() === "edit-1" && env.view() === "result", `the result of the stroke must be on screen, on the cleaned photo: ${env.pictureName()} / ${env.view()}`);
    expect(dots().children.length === 0, "the trace goes away once the picture is there");
    expect(env.modeBadge() === "ПІСЛЯ · чисте фото", "the corner label: " + env.modeBadge());
    expect(env.recomputes().length === 0 && env.exacts().length === 0, "a stroke on an exact picture needs no recompute of any kind");

    // picking a tool - by the button or by the key - does not switch the mask on either
    env.click("dlgToolBrush");
    expect(env.view() === "result" && env.state("sessState.tool") === "brush", "picking the brush keeps the photo, got " + env.view());
    env.key("KeyE", "у");
    expect(env.view() === "result" && env.state("sessState.tool") === "eraser", "the key E keeps the photo, got " + env.view());
    env.key("KeyB", "b");
    expect(env.view() === "result" && env.state("sessState.tool") === "brush", "the key B keeps the photo, got " + env.view());
    env.press("dlgViewport", 200);
    env.move(220);
    env.release();
    await env.waitFor(() => env.picture() === "edit-2", 1500);
    expect(env.view() === "result" && env.picture() === "edit-2", "a brush stroke: the same, got " + env.view());
    expect(env.edits()[1] && env.edits()[1].body.erase === false, "the brush stroke must reach the server as a brush stroke");

    // the three actions on the whole mask keep the photo and say in words what they did
    env.click("dlgToolInvert");
    await env.waitFor(() => env.picture() === "edit-3", 1500);
    expect(env.view() === "result", "the inversion keeps the photo, got " + env.view());
    expect(env.hint().includes("інвертовано") && env.hint().includes("Маска"), "the inversion must be said in words: " + env.hint());
    env.click("dlgToolBrush", { ctrlKey: true });
    await env.waitFor(() => env.picture() === "edit-4", 1500);
    expect(env.view() === "result" && env.edits()[3].body.op === "fill", "Ctrl + click on the brush: the whole layer, the photo stays");
    expect(env.hint().includes("на всьому кадрі"), "...said in words: " + env.hint());
    env.click("dlgToolEraser", { ctrlKey: true });
    await env.waitFor(() => env.picture() === "edit-5", 1500);
    expect(env.view() === "result" && env.edits()[4].body.op === "clear", "Ctrl + click on the eraser: the mask is cleared, the photo stays");
    expect(env.hint().includes("стерто"), "...said in words: " + env.hint());

    // the mask is shown when the user asks for it - and then it stays through the strokes
    env.click("dlgBtnMask");
    expect(env.view() === "mask", "'Маска' shows the mask");
    env.press("dlgViewport", 100);
    expect(env.view() === "mask" && env.shown("dlgStrokeDots"), "a stroke with the mask on stays on the mask");
    env.move(120);
    env.release();
    await env.waitFor(() => env.picture() === "edit-6", 1500);
    expect(env.view() === "mask", "...and after it too, got " + env.view());
    env.press("dlgViewport", 900);                           // outside the photo: a look at the clean result
    expect(env.view() === "result", "holding outside the photo must lift the mask, got " + env.view());
    env.release();
    expect(env.view() === "mask", "...and the mask is back after the release, got " + env.view());
    env.click("dlgBtnMask");
    expect(env.view() === "result", "'Маска' switches it off");

    // on the original nothing a stroke does can be seen: the stroke brings the cleaned photo back
    env.click("dlgBtnBeforeAfter");
    expect(env.view() === "original", "'До / Після' shows the original");
    expect(!env.shown("dlgStrokeDots"), "no trace over the original");
    env.press("dlgViewport", 100);
    expect(env.view() === "result", "a stroke over the original shows the cleaned photo, got " + env.view());
    env.release();
    await env.waitFor(() => env.picture() === "edit-7", 1500);
    expect(env.view() === "result" && env.edits().length === 7, "seven edits, the photo on screen");
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
    env.state("applyPreset(presetsList.find((p) => p.id === 'gentle')); renderPresets();");
    await env.open();
    await env.settle(600);
    const start = env.of("/session/start")[0];
    expect(start.body.scenePresets === undefined, "no presets may be sent when the automatic choice is off");
    expect(start.body.params.smoke === 85 && start.body.params.scuffs === 25, "the chosen preset's values are sent");
    expect(env.state("activePresetId") === "gentle", "the chosen preset stays");
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
  // ("Зйомка з димом" as it was shipped up to 4.12.0; it is no built-in preset any more - see RETIRED_PRESET_IDS)
  const SMOKE_PRESET_412 = {
    id: "smoke", name: "Зйомка з димом", color: "#56d8c9", builtin: true,
    cfg: { spots: 72, scuffs: 65, blur: 0, cycCurve: 0, feather: 60, seamOn: true, seam: 80, edge: 75, smokeOn: true, smoke: 95, grain: 90, shadow: true, removeStands: false, master: 100, fracFine: true, fracMed: true, fracLarge: true, dressSmooth: false, dressStrength: 40, cleanPasses: 1 }
  };
  const presets430 = () => {
    const now = JSON.parse(fs.readFileSync(path.join(PLUGIN_DIR, "..", "server", "presets_defaults.json"), "utf8"));
    const list = IDS_OLD.map((id) => (id === "smoke" ? JSON.parse(JSON.stringify(SMOKE_PRESET_412)) : now.find((p) => p.id === id)));
    // (no word of "Глибина" either: that came with 4.14.0)
    list.forEach((p) => { p.cfg.cycCurve = 0; p.cfg.smokeOn = true; delete p.cfg.cycDepth; if (p.id === "lowkey") p.cfg.spots = 92; });
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
      expect(cyc("closeup") === 0 && cyc("user_1") === 0, "the other presets and the user's own one must stay: " + [cyc("closeup"), cyc("user_1")].join());
      const cfgOf = (id) => env.state(`JSON.stringify((presetsList.find((p) => p.id === ${JSON.stringify(id)}) || { cfg: {} }).cfg)`);
      expect(IDS_OLD.filter((id) => id !== "smoke").every((id) => JSON.parse(cfgOf(id)).smokeOn === false), "smoke protection must go off in every built-in preset");
      expect(env.state("presetsList.some((p) => p.id === 'smoke')") === false, "the smoke preset of that PC is gone (4.13.0)");
      expect(JSON.parse(cfgOf("user_1")).smokeOn === true && JSON.parse(cfgOf("user_1")).spots === 33, "...and stay as saved in the user's own preset");
      expect(JSON.parse(cfgOf("lowkey")).spots === 80, "'Темний ключ' must get dust 80: " + JSON.parse(cfgOf("lowkey")).spots);
      expect(env.state("smokeEnabled") === false && !env.el("dlgChkSmoke").checked && env.el("gBtnSmoke").textContent === "Вимк.",
        "the smoke controls of the active preset must go off: " + env.el("gBtnSmoke").textContent);
      const ids = env.state("presetsList.map((p) => p.id).join()");
      expect(ids === "std,medium_shot,closeup,wide_shot,lowkey,lowkey_medium,lowkey_close,lowkey_wide,clean_stands,gentle,user_1",
        "the three dark presets must land under 'Темний ключ': " + ids);
      expect(env.state("activePresetId") === "wide_shot" && env.state("getSliderVal('gSlCyc')") === 65, "the slider of the active preset must follow, got " + env.state("getSliderVal('gSlCyc')"));
      expect(env.el("gValCyc").textContent === "65%", "...and show it: " + env.el("gValCyc").textContent);
      const onDisk = env.server.disk;
      expect(onDisk["presets_local.json"].find((p) => p.id === "wide_shot").cfg.cycCurve === 65, "the moved presets must be saved on the PC");
      expect(["cyc65", "smokeOff", "lowkeySpots80", "lowkeyCyc65"].every((id) => (onDisk["user_settings.json"].presetMoves || []).includes(id)),
        "the settings must remember that the moves were made: " + JSON.stringify(onDisk["user_settings.json"].presetMoves));
      expect(onDisk["presets_local.json"].length === 11 && onDisk["presets_local.json"].find((p) => p.id === "std").cfg.smokeOn === false, "...and the presets on the PC must hold all of it");
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
    expect(env.state("presetsList.length") === 10 && env.state("presetsList[5].id") === "lowkey_medium", "ten built-in presets, the dark ones together");
    expect(env.state("presetsList.some((p) => p.id === 'smoke' || p.name === 'Зйомка з димом')") === false, "no smoke preset among them (taken out in 4.13.0)");
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
  await scenario("smoke: every request says that the smoke switch is the user's word; the corner presets go with the floor",
    { scene: { kind: "wide", framing: "wide", dark: false } }, async (env, expect) => {
      await env.open();
      const start = env.of("/session/start")[0];
      const sp = start.body.scenePresets || {};
      expect(start.body.params.smokeFaint === true && start.body.params.smokeAuto === true,
        "the first scan must say it (and keep the older key for a server before 4.11.0): " + JSON.stringify(start.body.params));
      expect(Object.keys(sp).length === 8 && Object.keys(sp).every((k) => sp[k].smokeFaint === true && sp[k].smokeAuto === true),
        "...and so must every set of the automatic preset");
      expect(sp.wide.cycCurve === 65 && sp.medium.cycCurve === 65 && sp.default.cycCurve === 65 && sp.dark.cycCurve === 65 && sp.dark_wide.cycCurve === 65 &&
        sp.dark_medium.cycCurve === 65 && sp.close.cycCurve === 0 && sp.dark_close.cycCurve === 0,
        "the corner line goes by default wherever a floor is usually in the frame and stays in the two close-up presets: "
        + JSON.stringify(Object.keys(sp).map((k) => [k, sp[k].cycCurve])));
      expect(env.state("getSliderVal('gSlCyc')") === 65, "the slider must show the value of the applied preset");
      await env.drag("gSlSpots", 90);
      await env.settle(900);
      const rc = env.recomputes();
      expect(rc.length === 1 && rc[0].body.params.smokeFaint === true && rc[0].body.params.smokeAuto === true && rc[0].body.params.cycCurve === 65,
        "a refresh must carry it too");
      env.click("dlgBtnApply");
      await env.settle(900);
      const ap = env.of("/session/apply");
      expect(ap.length === 1 && ap[0].body.params.smokeFaint === true && ap[0].body.params.smokeAuto === true, "...and Apply as well");
    });

  // His report on 4.10.0: "I press that there is smoke and it says no, there is none".
  await scenario("the smoke switch is the user's word: it is never answered with 'no smoke found'",
    { frameSmoke: { share: 0.004, largest: 0.002, found: false, kept: 0, keptFull: 0.21 } }, async (env, expect) => {
      env.check("dlgChkAutoPreset", false);
      await env.open();
      await env.settle(300);
      expect(env.badge() === "", "a frame without smoke opens without a word about smoke: " + env.badge());
      env.check("dlgChkSmoke", true);                        // "I shot with smoke"
      expect(env.hint().includes("увімкнено") && env.hint().includes("перераховую"), "ticking the box must say at once that the frame is being recomputed: " + env.hint());
      await env.settle(900);
      let rc = env.recomputes();
      expect(rc.length === 1 && rc[0].body.params.smokeOn === true && rc[0].body.params.smokeFaint === true && rc[0].body.quick === undefined,
        "one recompute with the protection on, taken on the user's word");
      const denies = (t) => t.includes("не знайдено") || t.includes("нічого не змінює") || t.includes("той самий") || t.includes("немає");
      expect(env.badge().includes("Захист диму увімкнено") && env.badge().includes("не розпізнала") && env.badge().includes("до 100 %"),
        "nothing is kept yet: the note must say so and say what to do: " + env.badge());
      expect(!denies(env.badge()), "the note must not say that the frame has no smoke - the user has just said it has: " + env.badge());
      expect(env.hint() === env.badge(), "the same words must stay in the hint strip after the note is gone: " + env.hint());
      env.check("dlgChkSmoke", false);
      await env.settle(900);
      rc = env.recomputes();
      expect(rc.length === 2 && rc[1].body.params.smokeOn === false, "one more refresh with the protection off");
      expect(env.badge().includes("вимкнено") && env.badge().includes("чиститься") && !denies(env.badge()),
        "switched off: the note must say that everything is cleaned, without a word on whether smoke is there: " + env.badge());
      env.check("dlgChkSmoke", true);
      await env.settle(900);
      await env.drag("gSlSmoke", 100);                       // "protect it anyway"
      await env.settle(1100);
      rc = env.recomputes();
      expect(rc.length === 4 && rc[3].body.params.smoke === 100 && rc[3].body.params.smokeOn === true, "the slider gives one more refresh");
      expect(env.badge().includes("Захист диму увімкнено") && env.badge().includes("21 %") && env.badge().includes("бере за дим") && !denies(env.badge()),
        "the note must say how much of the frame is kept now: " + env.badge());
      await env.drag("gSlSpots", 90);                        // another control: no words about smoke
      await env.settle(1100);
      expect(env.recomputes().length === 5, "the other slider refreshes as usual");
      expect(!env.badge().includes("бере за дим"), "the smoke note must not come back after another control: " + env.badge());
    });

  await scenario("thin smoke that the search by wisps does not call smoke: the tick protects it and says how much",
    { frameSmoke: { share: 0.02, largest: 0.005, found: false, kept: 0.24 } }, async (env, expect) => {
      env.check("dlgChkAutoPreset", false);
      await env.open();
      await env.settle(300);
      expect(env.badge() === "", "too little of it to speak of smoke at the opening: " + env.badge());
      env.click("gBtnSmoke");                                // the switch in the fine settings
      await env.settle(900);
      const rc = env.recomputes();
      expect(rc.length === 1 && rc[0].body.params.smokeOn === true && rc[0].body.params.smokeFaint === true, "one refresh with the protection on");
      expect(env.badge().includes("Захист диму увімкнено") && env.badge().includes("24 %") && env.badge().includes("бере за дим") && env.badge().includes("вище"),
        "the note must say how much is kept and which way the slider goes: " + env.badge());
      expect(!env.badge().includes("не знайдено") && !env.badge().includes("нічого не змінює"), "...and must not deny the smoke: " + env.badge());
      expect(env.el("dlgChkSmoke").checked, "the checkbox on top must follow the switch");
    });

  await scenario("a server before 4.11.0, smoke controls on a frame without smoke: its own words, as before",
    { frameSmoke: { share: 0.004, largest: 0.002, found: false }, smokeOld: true }, async (env, expect) => {
      env.check("dlgChkAutoPreset", false);
      await env.open();
      await env.settle(300);
      expect(env.badge() === "", "a frame without smoke opens without a word about smoke: " + env.badge());
      expect(env.of("/session/start")[0].body.params.smokeOn === false && !env.el("dlgChkSmoke").checked, "the window opens with the protection off");
      env.check("dlgChkSmoke", true);                        // "I shot with smoke"
      expect(env.hint().includes("увімкнено") && env.hint().includes("перераховую"), "ticking the box must say at once that the frame is being recomputed: " + env.hint());
      await env.settle(900);
      let rc = env.recomputes();
      expect(rc.length === 1 && rc[0].body.params.smokeOn === true && rc[0].body.quick === undefined, "one recompute with the protection on");
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
      expect(rc.length === 1 && rc[0].body.params.smokeOn === true && rc[0].body.params.smokeFaint === true, "one refresh with the protection on");
      expect(env.badge().includes("Захист диму увімкнено") && env.badge().includes("6,0 %") && env.badge().includes("бере за дим"),
        "the note must say that the smoke is protected now: " + env.badge());
      expect(env.el("gBtnSmoke").textContent === "Увімк.", "the switch in the fine settings must follow the checkbox");
      env.click("gBtnSmoke");                                // ...and the switch works the other way round
      await env.settle(900);
      rc = env.recomputes();
      expect(rc.length === 2 && rc[1].body.params.smokeOn === false, "one refresh with the protection off");
      expect(env.badge().includes("вимкнено") && env.badge().includes("5,0 %") && env.badge().includes("чиститься"),
        "the note must warn that the smoke is cleaned now: " + env.badge());
      expect(!env.el("dlgChkSmoke").checked, "the checkbox on top must follow the switch");
    });

  // (up to 4.12.0 these three had the preset 'Зйомка з димом' on the controls; it is gone, the smoke tick is the way)
  const smokeLeftOn = (env) => {
    env.check("dlgChkAutoPreset", false);
    env.state("setSliderVal('gSlSmoke', 95); updateSliderVisuals();");
    env.check("dlgChkSmoke", true);                          // (no window is open yet: nothing is computed)
  };
  await scenario("the smoke tick left on: the next window opens with the protection, said when it opens",
    { frameSmoke: { share: 0.05, largest: 0.04, found: true } }, async (env, expect) => {
      smokeLeftOn(env);
      expect(env.el("dlgChkSmoke").checked && env.el("gBtnSmoke").textContent === "Увімк." && env.recomputes().length === 0, "the tick switches the smoke controls on and asks for nothing yet");
      await env.open();
      await env.settle(300);
      const p = env.of("/session/start")[0].body.params;
      expect(p.smokeOn === true && p.smoke === 95 && p.smokeFaint === true, "the first scan must protect smoke: " + JSON.stringify([p.smokeOn, p.smoke, p.smokeFaint]));
      expect(env.badge().includes("Захист диму увімкнено") && env.badge().includes("6,0 %"), "the opening note must say that smoke is kept: " + env.badge());
      env.click("dlgBtnPresets");
      env.clickPreset("Студія (Стандарт)");
      expect(!env.el("dlgChkSmoke").checked, "a preset switches the protection off again (no built-in preset has it on)");
    });

  await scenario("the window opens with the protection on and nothing is recognised as smoke: said at once",
    { frameSmoke: { share: 0.004, largest: 0.002, found: false, kept: 0 } }, async (env, expect) => {
      smokeLeftOn(env);
      await env.open();
      await env.settle(300);
      expect(env.badge().includes("Захист диму увімкнено") && env.badge().includes("не розпізнала") && env.badge().includes("до 100 %"),
        "the opening note must say that nothing is kept and what to do: " + env.badge());
    });

  await scenario("a server before 4.11.0 with the smoke tick left on: its own words at the opening",
    { frameSmoke: { share: 0.05, largest: 0.04, found: true }, smokeOld: true }, async (env, expect) => {
      smokeLeftOn(env);
      await env.open();
      await env.settle(300);
      expect(env.badge().includes("95–100") && env.badge().includes("збережено"), "the opening note must say that smoke is kept: " + env.badge());
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
    expect(env.footer().includes("Бекап збережено") && env.footer().includes("пресетів 10") && env.footer().includes("ваших: 1"), "the panel must say what was saved: " + env.footer());
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
    expect(line.includes("19.11.2026 08:31") && line.includes("пресетів: 10") && line.includes("ваших: 1"), "a line must show the date and what the backup holds: " + line);
    backupRows(env)[0].click();                              // the first click only asks
    await env.settle(200);
    expect(env.of("/backup/read").length === 0 && env.state("presetsList.length") === 10 && !env.state("presetsList.some((p) => p.id === 'usr_7')"), "one click must change nothing");
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
    expect(copy && copy.body.label === "before-restore" && copy.body.presets.length === 10 && !copy.body.presets.some((x) => x.id === "usr_7"),
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
    expect(ids === "std,medium_shot,closeup,wide_shot,lowkey,lowkey_medium,lowkey_close,lowkey_wide,clean_stands,gentle,user_1",
      "the dark presets by framing must be added, the smoke preset of the old backup must be left out: " + ids);
    const lk = cfgOf(env, "lowkey"), mine = cfgOf(env, "user_1");
    expect(lk.spots === 80 && lk.cycCurve === 65 && lk.smokeOn === false, "the changed defaults must reach the restored presets: " + JSON.stringify([lk.spots, lk.cycCurve, lk.smokeOn]));
    expect(mine.spots === 33 && mine.smokeOn === true && mine.cycCurve === 0, "the user's own preset must be as it was saved");
    expect(env.state("activePresetId") === "lowkey" && env.state("getSliderVal('gSlSpots')") === 80 && env.state("getSliderVal('gSlCyc')") === 65 && !env.el("dlgChkSmoke").checked,
      "the controls of the active preset must follow");
    expect(env.server.disk["user_settings.json"].presetMoves.length === 5, "the moves must be remembered: " + JSON.stringify(env.server.disk["user_settings.json"].presetMoves));
    // (4.14.0: "Глибина" is 60 in the light presets with a floor; the dark presets and the user's own know nothing of it)
    const depths = ["std", "medium_shot", "wide_shot", "clean_stands", "lowkey", "user_1"].map((id) => cfgOf(env, id).cycDepth);
    expect(JSON.stringify(depths) === JSON.stringify([60, 60, 60, 60, undefined, undefined]) && env.state("getSliderVal('gSlDepth')") === 0,
      "depth must reach the restored light presets only, and the slider of the active dark preset stays at 0: " + JSON.stringify(depths));
  });

  // ---------------------------------------------------------------- one mode; the edge of the brush and the eraser
  await scenario("one mode: no speed button; settings and presets of an older version that say 'fast' change nothing",
    { disk: { "user_settings.json": { schemaVersion: 5, speedMode: "fast", presetMoves: ["cyc65", "smokeOff", "lowkeySpots80", "lowkeyCyc65"] } },
      scene: { kind: "wide", framing: "wide", dark: false } }, async (env, expect) => {
      await sleep(500);
      expect(env.doc.getElementById("dlgSpeedPill") === null && !/Швидкий|Якісний/.test(env.doc.body.textContent),
        "the speed button and its two names must be gone from the window");
      expect(env.state("speedMode") === "quality" && env.state("buildSettingsSnapshot().speedMode") === "quality", "one mode: " + env.state("speedMode"));
      // presets saved by an older version while the fast mode was on: the built-in ones that the user saved again
      // (the automatic preset offers them to the server) and one of the user's own
      env.state(`(function () {
        presetsList.forEach((p) => { p.cfg.speedMode = "fast"; });
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

  // ------------------------------------------------------------------ 4.10.0: speed first
  await scenario("the fast window (as the panel starts): small pictures are asked for, a slider gives one light refresh and nothing computes by itself", { detail: false, bgDelay: 300 }, async (env, expect) => {
    expect(env.state("detailPreview") === false && env.el("gChkDetail").checked === false, "a fresh installation: 'Детальний перегляд' is off");
    expect(env.el("gBtnRecompute").textContent.includes("Перерахувати зараз") && env.el("gBtnRecompute").textContent.includes("точний перегляд"),
      "the button says what it is for: " + env.el("gBtnRecompute").textContent);
    expect(env.el("gLiveNote").textContent.includes("швидкий перегляд") && env.el("gLiveNote").textContent.includes("Застосувати") && !env.el("gLiveNote").textContent.includes("сам"),
      "the note of the settings must not promise an exact picture by itself: " + env.el("gLiveNote").textContent);
    await env.open();
    const start = env.of("/session/start")[0];
    expect(start && start.body.params.previewLong === 1080, "the window must ask for pictures of the working size (previewLong 1080), got " + (start && start.body.params.previewLong));
    expect(env.modeBadge() === "ПІСЛЯ · чисте фото", "the window opens with the real frame: " + env.modeBadge());
    await env.drag("gSlSpots", 95);
    await env.waitFor(() => env.recomputes().length === 1 && env.recomputes()[0].done, 2500);
    await sleep(1300);                                    // (the exact picture by itself would be asked for after 0.7 s)
    expect(env.recomputes().length === 1 && env.recomputes()[0].body.quick === true, "one light refresh after the release, got " + env.recomputes().length);
    expect(env.exacts().length === 0, "nothing may be computed in the background, got " + env.exacts().length);
    expect(env.modeBadge() === "ПІСЛЯ · швидкий перегляд", "the corner says 'quick preview' and nothing about refining: " + env.modeBadge());
    expect(env.badge() === "", "nothing to complain about: " + env.badge());
    // a stroke: answered, and still nothing in the background
    env.press("dlgViewport", 100); env.move(120); env.release();
    await env.waitFor(() => env.edits().length === 1 && env.edits()[0].done, 1500);
    await sleep(1100);
    expect(env.exacts().length === 0, "a stroke must not start a background run either, got " + env.exacts().length);
    // the button: the real frame, with the progress card
    env.click("gBtnRecompute");
    await env.waitFor(() => env.recomputes().length === 2 && env.recomputes()[1].done, 2500);
    await sleep(60);
    const full = env.recomputes()[1];
    expect(full && full.body.quick === undefined && full.body.params.spots === 95, "the button asks for the real frame with the values on the controls");
    expect(env.modeBadge() === "ПІСЛЯ · чисте фото" && env.exacts().length === 0, "after the button the picture is the real frame: " + env.modeBadge());
    // Apply after a quick preview carries the values, so the server computes the real frame itself
    await env.drag("gSlSpots", 60);
    await env.waitFor(() => env.recomputes().length === 3 && env.recomputes()[2].done, 2500);
    env.click("dlgBtnApply");
    await env.waitFor(() => env.of("/session/apply").length === 1, 2000);
    const ap = env.of("/session/apply")[0];
    expect(ap && ap.body.params && ap.body.params.spots === 60, "Apply must carry the values of the controls: " + JSON.stringify(ap && ap.body.params && ap.body.params.spots));
    expect(env.exacts().length === 0, "and still no background run");
  });

  await scenario("the fast window with 2 passes: nothing starts by itself, the badge names the button", { detail: false, bgDelay: 300 }, async (env, expect) => {
    await env.open();
    env.click("gPass2");
    await sleep(1400);
    expect(env.exacts().length === 0 && env.recomputes().length === 0, `2 passes have no light way and nothing may start by itself: ${env.exacts().length} / ${env.recomputes().length}`);
    expect(env.badge().includes("«↻ Перерахувати» внизу вікна"), "the badge must name the button: " + env.badge());
  });

  await scenario("'Детальний перегляд': ticked - the exact picture comes by itself and larger pictures are asked for; unticked - a background run stops; kept with the settings", { detail: false, bgDelay: 1500 }, async (env, expect) => {
    await env.open();
    await env.drag("gSlSpots", 95);
    await env.waitFor(() => env.recomputes().length === 1 && env.recomputes()[0].done, 2500);
    await sleep(900);
    expect(env.exacts().length === 0, "unticked: nothing in the background");
    env.check("gChkDetail", true);
    expect(env.state("detailPreview") === true && env.hint().includes("Детальний перегляд увімкнено"), "the window says what the tick does: " + env.hint());
    expect(env.el("gBtnRecompute").textContent.includes("не обов’язково"), "the button is optional now: " + env.el("gBtnRecompute").textContent);
    expect(env.el("gLiveNote").textContent.includes("перераховується сам"), "the note of the settings says so too: " + env.el("gLiveNote").textContent);
    await env.waitFor(() => env.exacts().length === 1, 1500);
    expect(env.exacts().length === 1, "ticked while a quick preview is on screen: its exact picture is asked for by itself");
    expect(env.modeBadge().includes("уточнюється"), "the corner says that it is being refined: " + env.modeBadge());
    env.check("gChkDetail", false);                        // while that run is on its way
    await sleep(120);
    expect(env.of("/session/stop-background").length === 1, "unticking stops the background run, got " + env.of("/session/stop-background").length);
    expect(env.modeBadge() === "ПІСЛЯ · швидкий перегляд" && env.hint().includes("вимкнено"), `quick preview again: '${env.modeBadge()}' / '${env.hint()}'`);
    expect(!env.el("gLiveNote").textContent.includes("сам"), "the note of the settings is that of the fast window again: " + env.el("gLiveNote").textContent);
    await sleep(1700);
    expect(env.exacts().length === 1, "and no new one starts, got " + env.exacts().length);
    env.check("gChkDetail", true);
    const saved = () => env.of("/settings").filter((r) => r.method === "POST" && r.body && r.body.detailPreview === true).length > 0;
    await env.waitFor(saved, 2500);
    expect(saved(), "the tick must be written into the settings");
  });

  await scenario("'Детальний перегляд' from the settings: the window asks for the larger pictures", {
    detail: false, disk: { "user_settings.json": { schemaVersion: 5, detailPreview: true, presetMoves: ["cyc65", "smokeOff", "lowkeySpots80", "lowkeyCyc65"] } }
  }, async (env, expect) => {
    expect(env.state("detailPreview") === true && env.el("gChkDetail").checked === true, "the settings must bring the tick back");
    await env.open();
    const start = env.of("/session/start")[0];
    expect(start && start.body.params.previewLong === 2160, "the larger pictures (previewLong 2160), got " + (start && start.body.params.previewLong));
  });

  await scenario("the trace of a stroke is one line however far the pointer jumps between two events", { detail: false, editDelays: [400], previewSize: [400, 600] }, async (env, expect) => {
    await env.open();
    const dots = () => Array.from(env.el("dlgStrokeDots").children).map((d) => [parseFloat(d.style.left), parseFloat(d.style.top), parseFloat(d.style.width)]);
    // (the simulated browser lays nothing out: the photo is given the size its rectangle has, 400 x 600)
    Object.defineProperty(env.el("dlgStage"), "offsetWidth", { value: 400, configurable: true });
    Object.defineProperty(env.el("dlgStage"), "offsetHeight", { value: 600, configurable: true });
    env.press("dlgViewport", 40, { clientY: 300 });
    env.move(360, { clientY: 330 });                       // one event, 320 px away
    const d = dots();
    const diam = d.length ? d[0][2] : 0;
    let widest = 0;
    for (let i = 1; i < d.length; i++) widest = Math.max(widest, Math.hypot(d[i][0] - d[i - 1][0], d[i][1] - d[i - 1][1]));
    expect(d.length >= 8, `the gap of 320 px must be filled with dots, got ${d.length}`);
    expect(diam > 0 && widest <= Math.max(3, 0.3 * diam) + 1.5, `no two neighbouring dots further apart than 0.3 of the brush (${(0.3 * diam).toFixed(1)} px): widest gap ${widest.toFixed(1)} px`);
    expect(d.length > 0 && Math.abs(d[d.length - 1][0] + diam / 2 - 360) <= 1.5 && Math.abs(d[0][0] + diam / 2 - 40) <= 1.5, "the trace runs from the press to the pointer");
    const n1 = d.length;
    env.move(361, { clientY: 330 });                       // a move of one pixel adds nothing
    expect(dots().length === n1, "a move of one pixel must not add dots");
    env.release();
    await env.waitFor(() => env.edits().length === 1 && env.edits()[0].done, 2000);
    await sleep(30);
    const pts = env.edits()[0].body.points;
    expect(pts.length === 3 || pts.length === 2, "the server gets the points of the events themselves, not the filled-in ones: " + pts.length);
    expect(dots().length === 0, "the trace goes when the server has answered");
  });

  await scenario("a stroke begun before the answer to the last one keeps its trace", { detail: false, editDelays: [400, 300, 500], previewSize: [400, 600] }, async (env, expect) => {
    await env.open();
    const dots = () => Array.from(env.el("dlgStrokeDots").children).map((d) => [parseFloat(d.style.left), parseFloat(d.style.top), parseFloat(d.style.width)]);
    Object.defineProperty(env.el("dlgStage"), "offsetWidth", { value: 400, configurable: true });
    Object.defineProperty(env.el("dlgStage"), "offsetHeight", { value: 600, configurable: true });
    // stroke 1, in the upper part of the photo
    env.press("dlgViewport", 60, { clientY: 100 });
    env.move(200, { clientY: 100 });
    env.release();
    const n1 = dots().length;
    expect(n1 >= 4, "the trace of the first stroke: " + n1 + " dots");
    // stroke 2 is begun at once, lower down: the answer to stroke 1 is still on its way
    env.press("dlgViewport", 60, { clientY: 400 });
    env.move(160, { clientY: 400 });
    const n2 = dots().length - n1;
    expect(n2 >= 3, "the trace of the second stroke: " + n2 + " dots");
    await env.waitFor(() => env.edits().length === 1 && env.edits()[0].done, 2000);
    await sleep(40);
    let d = dots();
    expect(d.length === n2, `the answer to stroke 1 takes away its own trace only: ${d.length} dots left, stroke 2 had ${n2}`);
    expect(d.every((p) => Math.abs(p[1] + p[2] / 2 - 400) <= 1.5), "what is left is the trace of stroke 2 (the lower one)");
    // ...and stroke 2 goes on as one line: no restart after the answer
    env.move(340, { clientY: 400 });
    d = dots();
    const diam = d.length ? d[0][2] : 0;
    let widest = 0;
    for (let i = 1; i < d.length; i++) widest = Math.max(widest, Math.hypot(d[i][0] - d[i - 1][0], d[i][1] - d[i - 1][1]));
    expect(d.length > n2 && widest <= Math.max(3, 0.3 * diam) + 1.5, `stroke 2 stays one line after the answer to stroke 1: widest gap ${widest.toFixed(1)} px of ${d.length} dots`);
    env.release();
    const n2all = dots().length;
    // stroke 3 is made while stroke 2 waits for its answer: the answer to stroke 2 leaves the trace of stroke 3
    env.press("dlgViewport", 60, { clientY: 500 });
    env.move(200, { clientY: 500 });
    env.release();
    const n3 = dots().length - n2all;
    await env.waitFor(() => env.edits().length >= 2 && env.edits()[1].done, 2000);
    await sleep(60);                                       // (the answer to stroke 3 takes 500 ms from here)
    d = dots();
    expect(n3 >= 4 && d.length === n3 && d.every((p) => Math.abs(p[1] + p[2] / 2 - 500) <= 1.5), `a stroke that waits for the server keeps its trace: ${d.length} dots left, stroke 3 had ${n3}`);
    await env.waitFor(() => env.edits().length === 3 && env.edits()[2].done, 2000);
    await sleep(40);
    expect(dots().length === 0, "all answers are in: no trace is left, got " + dots().length);
    expect(env.edits().map((r) => r.body.points.length).join() === "2,3,2", "three strokes reached the server, in order: " + env.edits().map((r) => r.body.points.length).join());
  });

  await scenario("a stroke ends where the mouse button was released, also when no move arrived", { detail: false, editDelays: [200], previewSize: [400, 600] }, async (env, expect) => {
    await env.open();
    const dots = () => Array.from(env.el("dlgStrokeDots").children).map((d) => [parseFloat(d.style.left), parseFloat(d.style.top), parseFloat(d.style.width)]);
    Object.defineProperty(env.el("dlgStage"), "offsetWidth", { value: 400, configurable: true });
    Object.defineProperty(env.el("dlgStage"), "offsetHeight", { value: 600, configurable: true });
    // a quick stroke while the window was busy: the press, then the release 320 px away - no move in between
    env.press("dlgViewport", 40, { clientY: 300 });
    env.release({ clientX: 360, clientY: 330 });
    const d = dots();
    expect(d.length >= 8, `the trace runs to the place of the release: ${d.length} dots`);
    await env.waitFor(() => env.edits().length === 1 && env.edits()[0].done, 2000);
    let pts = env.edits()[0].body.points;
    expect(pts.length === 2 && Math.abs(pts[0].x - 0.1) < 0.01 && Math.abs(pts[1].x - 0.9) < 0.01 && Math.abs(pts[1].y - 0.55) < 0.01,
      "the stroke is a line from the press to the release, not a dot: " + JSON.stringify(pts));
    // a plain click stays one point
    env.press("dlgViewport", 200, { clientY: 300 });
    env.release();
    await env.waitFor(() => env.edits().length === 2 && env.edits()[1].done, 2000);
    pts = env.edits()[1].body.points;
    expect(pts.length === 1, "a click is one point: " + JSON.stringify(pts));
    // the release is where the last move was: no point twice
    env.press("dlgViewport", 100, { clientY: 300 });
    env.move(180, { clientY: 300 });
    env.release();
    await env.waitFor(() => env.edits().length === 3 && env.edits()[2].done, 2000);
    pts = env.edits()[2].body.points;
    expect(pts.length === 2, "press, one move, release at the same place: two points, got " + pts.length);
    // a release that brings no place (0, 0) adds nothing: never a line to the corner of the photo
    env.press("dlgViewport", 300, { clientY: 400 });
    env.release({ clientX: 0, clientY: 0 });
    await env.waitFor(() => env.edits().length === 4 && env.edits()[3].done, 2000);
    pts = env.edits()[3].body.points;
    expect(pts.length === 1 && Math.abs(pts[0].x - 0.75) < 0.01, "a release without a place adds no point: " + JSON.stringify(pts));
  });

  await scenario("the AI fill ran on the processor although a video card is there: the window and the panel say so", {
    detail: false,
    stats: { elapsed_ms: 84200, timing: { fill_tiles: 132, fill_s: 71.4, fill_ep: "CPUExecutionProvider", fallback: { lama: "CUDA out of memory" } } },
    healthExtra: { cpu_fallback: { lama: "CUDA out of memory" } }
  }, async (env, expect) => {
    const banner = env.el("statusBannerText").textContent;
    expect(banner.includes("на процесорі") && banner.includes("CUDA out of memory") && banner.includes("restart_gpu_server.bat"), "the panel must warn: " + banner);
    await env.open();
    expect(env.badge().includes("на процесорі") && env.badge().includes("CUDA out of memory"), "the corner of the photo must warn: " + env.badge());
    const line = env.el("gTimeLine");
    expect(line.textContent.includes("84 с") && line.textContent.includes("132") && line.textContent.includes("71 с") && line.textContent.includes("процесор") && line.classList.contains("warn"),
      "the settings must say what the computation took and where the fill ran: " + line.textContent);
  });

  await scenario("the AI fill ran on the video card: the time is shown, nothing warns", {
    detail: false, stats: { elapsed_ms: 9300, timing: { fill_tiles: 90, fill_s: 6.25, fill_ep: "CUDAExecutionProvider", fallback: {} } }
  }, async (env, expect) => {
    await env.open();
    const line = env.el("gTimeLine");
    expect(line.textContent.includes("9,3 с") && line.textContent.includes("90") && line.textContent.includes("6,3 с") && line.textContent.includes("відеокарта") && !line.classList.contains("warn"),
      "the line of the settings: " + line.textContent);
    expect(!env.badge().includes("процесор"), "no warning: " + env.badge());
  });

  await scenario("after Apply the panel says what the layer took and where the AI fill ran", {
    detail: false,
    applyStats: { elapsed_ms: 12400, changed_px: 1234, gpu: "NVIDIA GeForce RTX 5060 Ti", recomputed: true,
                  timing: { fill_tiles: 90, fill_s: 6.25, fill_ep: "CUDAExecutionProvider", fallback: {} } }
  }, async (env, expect) => {
    await env.open();
    env.click("dlgBtnApply");
    await env.waitFor(() => env.ps.layersMade.length === 1 && env.footer().includes("Шар створено"), 3000);
    const f = env.footer();
    expect(f.includes("«Застосувати»: 12 с") && f.includes("AI-заливка: 90 пл. за 6,3 с (відеокарта)"), "the footer of the panel: " + f);
    expect(!f.includes("процесор") && env.el("footerStatus").className.includes("success"), "nothing warns: " + f);
  });

  await scenario("after Apply the panel warns when the AI fill of the layer ran on the processor", {
    detail: false,
    applyStats: { elapsed_ms: 251000, changed_px: 1234, gpu: "NVIDIA GeForce RTX 5060 Ti", recomputed: true,
                  timing: { fill_tiles: 132, fill_s: 240.2, fill_ep: "CPUExecutionProvider", fallback: { lama: "CUDA out of memory" } } }
  }, async (env, expect) => {
    await env.open();
    env.click("dlgBtnApply");
    await env.waitFor(() => env.ps.layersMade.length === 1 && env.footer().includes("Шар створено"), 3000);
    const f = env.footer();
    expect(f.includes("«Застосувати»: 251 с") && f.includes("132 пл. за 240 с (процесор)"), "the footer of the panel: " + f);
    expect(f.includes("на процесорі") && f.includes("CUDA out of memory"), "the footer must say why it was slow: " + f);
  });

  await scenario("after Apply with the frame ready (or an older server) the footer says the time only", {
    detail: false, applyStats: { elapsed_ms: 1800, changed_px: 10, gpu: "NVIDIA GeForce RTX 5060 Ti", recomputed: false }
  }, async (env, expect) => {
    await env.open();
    env.click("dlgBtnApply");
    await env.waitFor(() => env.ps.layersMade.length === 1 && env.footer().includes("Шар створено"), 3000);
    const f = env.footer();
    expect(f.includes("«Застосувати»: 1,8 с.") && !f.includes("AI-заливка"), "the footer of the panel: " + f);
  });

  await scenario("the hair slider: 'Вимк.' until it is moved; one light refresh carries its value, a preset puts it back to 0, Apply carries it", {}, async (env, expect) => {
    await env.open();
    const start = env.of("/session/start")[0];
    expect(start && start.body.params.strayHair === 0, "the window opens with the hair tool off: " + (start && start.body.params.strayHair));
    expect(env.el("gValHair").textContent === "Вимк.", "at 0 the value of the hair slider reads 'Вимк.': " + env.el("gValHair").textContent);
    await env.drag("gSlHair", 60);
    await env.settle(1000);
    const rs = env.recomputes().filter((r) => r.body.quick === true);
    expect(rs.length === 1, `one light refresh expected for the hair slider, got ${rs.length}`);
    if (rs[0]) expect(rs[0].body.params.strayHair === 60, "the refresh must carry strayHair 60, got " + rs[0].body.params.strayHair);
    expect(env.el("gValHair").textContent === "60%", "the value follows the slider: " + env.el("gValHair").textContent);
    env.clickPreset("Дальній план");
    await env.settle(1000);
    expect(env.state('getSliderVal("gSlHair")') === 0 && env.el("gValHair").textContent === "Вимк.",
      "a built-in preset leaves the hair tool off: " + env.state('getSliderVal("gSlHair")') + " / " + env.el("gValHair").textContent);
    const last = env.recomputes().filter((r) => r.body.quick === true).pop();
    expect(last && last.body.params.strayHair === 0, "the refresh after the preset click carries strayHair 0");
    await env.drag("gSlHair", 35);
    await sleep(100);                        // sooner than the refresh would start
    env.click("dlgBtnApply");
    await env.settle(900);
    const a = env.of("/session/apply");
    expect(a.length === 1 && a[0].body.params && a[0].body.params.strayHair === 35,
      "Apply must carry the hair slider: " + (a[0] && a[0].body.params && a[0].body.params.strayHair));
  });

  // ------------------------------------------------------------------ 4.12.0: the owner's list of 2026-11-23
  // "if I press the smoke tick it does not recompute", "pull the recompute button out", "while the bar is running
  // and I press something, the recompute must start from the beginning", "[ smaller, ] larger", "a tick at the
  // top: mixer brush" - and what his screenshot showed: the captions of the check boxes ran over the rows below.
  await scenario("the smoke tick recomputes the frame at once, with the progress card; so does the switch in the settings", { recomputeDelay: 500, detail: false }, async (env, expect) => {
    env.check("dlgChkAutoPreset", false);
    await env.open();
    env.check("dlgChkSmoke", true);
    await sleep(120);
    let rc = env.recomputes();
    expect(rc.length === 1 && rc[0].body.quick === undefined && rc[0].body.jobId, "the tick asks for the real frame at once, with a progress job: " + JSON.stringify(rc.map((r) => r.body.quick)));
    expect(env.progressCardVisible(), "the progress card must be up while the frame is computed");
    await env.settle(1200);
    expect(!env.progressCardVisible() && env.state("previewMatchesSettings()") === true && env.recomputes().length === 1, "one recompute, the card goes, the picture is up to date");
    env.click("dlgBtnGear");
    env.click("gBtnSmoke");                                  // the same switch, in the settings
    await sleep(120);
    rc = env.recomputes();
    expect(rc.length === 2 && rc[1].body.quick === undefined && rc[1].body.params.smokeOn === false && env.progressCardVisible(), "the switch of the settings recomputes the same way");
    await env.settle(1200);
    expect(env.recomputes().length === 2 && env.exacts().length === 0, "nothing follows by itself");
  });

  await scenario("'↻ Перерахувати' on the bottom bar: the real frame with the progress card, the settings stay open", { recomputeDelay: 400, detail: false }, async (env, expect) => {
    await env.open();
    env.click("dlgBtnGear");
    await env.drag("gSlSpots", 90);
    await env.settle(900);
    expect(env.recomputes().length === 1 && env.recomputes()[0].body.quick === true, "the slider gave its light refresh");
    env.click("dlgBtnRecompute");
    await sleep(100);
    const rc = env.recomputes();
    expect(rc.length === 2 && rc[1].body.quick === undefined && rc[1].body.params.spots === 90, "the button asks for the real frame with the values on the sliders");
    expect(env.progressCardVisible(), "with the progress card");
    expect(env.el("dlgGearPopover").classList.contains("visible"), "the settings must stay open: the values can be changed meanwhile");
    await env.settle(900);
    expect(!env.progressCardVisible() && env.state("sessState.exactShown") === true, "the exact picture is on screen, the card is gone");
    expect(env.el("dlgBtnRecompute").textContent.includes("Перерахувати") && (env.el("dlgBtnRecompute").getAttribute("data-tip") || "").includes("спочатку"),
      "the button says what it does, and that a change starts the run over");
  });

  await scenario("a change while the bar is running: the recompute starts over at once with the new values, the bar stays", { recomputeDelay: 900, detail: false }, async (env, expect) => {
    env.check("dlgChkAutoPreset", false);
    await env.open();
    env.click("dlgBtnRecompute");
    await sleep(300);
    expect(env.recomputes().length === 1 && env.progressCardVisible(), "the first run is on its way");
    env.click("dlgFracFine");                                // "I press something while the bar is running" (a button that
    await sleep(400);                                        //  gives a light refresh otherwise, 150 ms after the click)
    let rc = env.recomputes();
    expect(rc.length === 2, `the new values must be asked for at once, not after the first run: ${rc.length} request(s)`);
    expect(rc[1].body.quick === undefined && rc[1].body.jobId && rc[1].body.params.fracFine === false,
      "the bar is running, so the new run is a full one too, with the new value");
    expect(rc[0].done && rc[0].outcome === "superseded", "the server stopped the first run: " + rc[0].outcome);
    expect(env.progressCardVisible() && env.state("sessState.recomputing") === true, "the progress card must stay up for the new run");
    expect(env.el("dlgProgStage").textContent.length > 0, "the card says something");
    env.check("dlgChkSmoke", true);                          // and once more, with the smoke tick
    await sleep(100);
    rc = env.recomputes();
    expect(rc.length === 3 && rc[2].body.params.smokeOn === true && rc[2].body.params.fracFine === false && rc[1].outcome === "superseded",
      "the smoke tick starts the run over as well, with everything that was changed");
    await env.settle(2000);
    expect(env.recomputes().length === 3 && !env.progressCardVisible() && env.state("previewMatchesSettings()") === true && env.state("sessState.recomputing") === false,
      `three requests, the last one on screen: ${env.recomputes().length}, card ${env.progressCardVisible()}`);
    expect(env.pictureName() === env.recomputes()[2].picture, "the picture on screen is the one of the last run: " + env.pictureName());
    expect(env.server.fgSeen.superseded === 2, "two runs gave way: " + env.server.fgSeen.superseded);
  });

  await scenario("...with a server before 4.12.0: the old run is finished first, its picture is dropped, the bar stays for the new one", { recomputeDelay: 700, newestWins: false, detail: false }, async (env, expect) => {
    env.check("dlgChkAutoPreset", false);
    await env.open();
    env.click("dlgBtnRecompute");
    await sleep(300);
    env.click("dlgFracFine");
    await sleep(650);                                        // the first run has answered in full by now
    const rc = env.recomputes();
    expect(rc.length === 2 && rc[0].done && rc[0].outcome === "done" && !rc[1].done, "the old server finished the first run and is on the second");
    expect(env.progressCardVisible() && env.state("sessState.recomputing") === true, "the card must not go away with the answer of the old run");
    expect(env.state("previewMatchesSettings()") === false, "the picture of the old run must not count as the one for the new values");
    expect(rc[0].picture && env.pictureName() !== rc[0].picture, `...and must not be put on screen: ${env.pictureName()} (the old run made ${rc[0].picture})`);
    await env.settle(2000);
    expect(env.recomputes().length === 2 && !env.progressCardVisible() && env.state("previewMatchesSettings()") === true, "the second run ends on screen");
    expect(env.pictureName() === rc[1].picture, `the picture on screen is the one of the second run: ${env.pictureName()} / ${rc[1].picture}`);
  });

  await scenario("'[' makes the brush smaller and ']' larger - also with the Ukrainian layout, and after a check box was clicked", { detail: false }, async (env, expect) => {
    await env.open();
    const size = () => env.state("sessState.brushSize");
    expect(size() === 28, "the brush starts at 28: " + size());
    env.keyDown({ key: "]", code: "BracketRight" });
    expect(size() === 33 && env.el("dlgBrushSizeVal").textContent === "33", `']' must make the brush larger by a step: 28 -> ${size()}`);
    env.keyDown({ key: "[", code: "BracketLeft" });
    expect(size() === 28, "'[' must make it smaller again: " + size());
    env.keyDown({ key: "х", code: "BracketLeft" });          // the Ukrainian layout: the same key types "х"
    env.keyDown({ key: "х", code: "BracketLeft" });
    expect(size() === 18, "the key is told by its place on the keyboard: " + size());
    env.keyDown({ key: "ї" });                               // ...and by its letter, when the host does not say the place
    expect(size() === 20, "'ї' is the key of ']' in the Ukrainian layout (a small brush: a small step): " + size());
    env.keyDown({ key: "Х" });
    expect(size() === 15, "'х' is the key of '[' (also as a capital letter): " + size());
    env.keyDown({ key: "Ї" });
    expect(size() === 17, "...and back: " + size());
    env.keyDown({ key: "ї" });
    expect(size() === 19, "...once more: " + size());
    env.keyDown({ key: "ї" });
    expect(size() === 21, "the brush is at 21 now: " + size());
    env.keyDown({ key: "х" });
    expect(size() === 16, "a step of 5 from 21: " + size());
    env.keyDown({ key: "ї" }); env.keyDown({ key: "ї" });
    expect(size() === 20, "back at 20: " + size());
    env.keyDown({ key: "ъ" });                               // the Russian layout
    expect(size() === 25, "'ъ' is the key of ']' in the Russian layout: " + size());
    env.keyDown({ keyCode: 219 });                           // a host that gives the number only
    expect(size() === 20, "the number of the key works too: " + size());
    env.keyDown({ keyCode: 221 });
    expect(size() === 25, "...both ways: " + size());
    env.el("dlgChkSmoke").focus();
    env.keyDown({ key: "]", code: "BracketRight" }, env.el("dlgChkSmoke"));   // a check box was clicked last
    expect(size() === 30, "a check box that has the focus must not swallow the key: " + size());
    env.keyDown({ key: "]", code: "BracketRight", ctrlKey: true });
    expect(size() === 30, "with Ctrl the key is not ours: " + size());
    env.click("dlgBtnPresets");
    env.keyDown({ key: "]", code: "BracketRight" }, env.el("dlgNewPresetName"));
    expect(size() === 30, "inside a text field the key types its character: " + size());
    for (let i = 0; i < 40; i++) env.keyDown({ code: "BracketLeft" });
    expect(size() === 4, "the brush stops at its smallest size: " + size());
    env.keyDown({ code: "BracketRight" });
    expect(size() === 6, "a small brush changes by a small step: " + size());
    for (let i = 0; i < 40; i++) env.keyDown({ code: "BracketRight" });
    expect(size() === 180, "...and stops at its largest: " + size());
    expect(env.hint().includes("180"), "the hint strip says the size: " + env.hint());
    await env.settle(300);
    expect(env.of("/session/mask-edit").length === 0 && env.recomputes().length === 0, "the keys ask the server for nothing");
    expect(env.state("buildSettingsSnapshot().brushSize") === 180, "the size is kept with the settings");
  });

  await scenario("'Мікс-пензель': the tick at the top goes with every request, one full recompute; the strength is a slider of the settings", { detail: false }, async (env, expect) => {
    env.check("dlgChkAutoPreset", false);
    await env.open();
    expect(env.of("/session/start")[0].body.params.mixOn === false, "the mixer brush is off until it is ticked");
    expect(env.el("gValMix").textContent === "Вимк." && !env.el("dlgChkMix").checked, "both controls show 'off'");
    env.check("dlgChkMix", true);
    expect(env.hint().includes("Мікс-пензель увімкнено"), "the hint strip says what was switched on: " + env.hint());
    await env.settle(900);
    let rc = env.recomputes();
    expect(rc.length === 1 && rc[0].body.quick === undefined && rc[0].body.jobId && rc[0].body.params.mixOn === true && rc[0].body.params.mix === 50,
      "one full recompute with the mixer brush at 50: " + JSON.stringify(rc.map((r) => [r.body.quick, r.body.params.mixOn, r.body.params.mix])));
    expect(env.el("dlgWrapMix").classList.contains("active") && env.el("gBtnMix").textContent === "Увімк." && env.el("gValMix").textContent === "50%",
      "the pill, the switch and the value of the settings follow the tick");
    env.click("dlgBtnGear");
    await env.drag("gSlMix", 80);
    await env.settle(1100);
    rc = env.recomputes();
    expect(rc.length === 2 && rc[1].body.quick === true && rc[1].body.params.mix === 80, "the slider gives one light refresh with its value");
    env.clickPreset("Дальній план");
    await env.settle(1000);
    rc = env.recomputes();
    expect(env.el("dlgChkMix").checked && env.state('getSliderVal("gSlMix")') === 80 && rc[rc.length - 1].body.params.mixOn === true && rc[rc.length - 1].body.params.mix === 80,
      "a preset does not touch the mixer brush: it is the user's own switch");
    env.click("gBtnMix");                                    // the switch of the settings
    await env.settle(900);
    rc = env.recomputes();
    expect(!env.el("dlgChkMix").checked && rc[rc.length - 1].body.params.mixOn === false, "switched off in the settings: the tick at the top follows, the refresh says so");
    expect(env.el("gValMix").textContent === "Вимк.", "the value shows 'off' again");
    env.check("dlgChkMix", true);
    await sleep(60);
    env.click("dlgBtnApply");
    await env.settle(900);
    const a = env.of("/session/apply");
    expect(a.length === 1 && a[0].body.params.mixOn === true && a[0].body.params.mix === 80, "Apply carries the mixer brush");
    const kept = env.state("buildSettingsSnapshot()");
    expect(kept.mixOn === true && kept.mixStrength === 80 && kept.cfg.mixOn === true, "the tick and the strength are kept with the settings");
    expect(env.state("presetConfigToSave()").mixOn === undefined && env.state("presetConfigToSave()").mix === undefined, "...and are not written into a preset");
  });

  await scenario("the mixer brush kept in the settings: the next window opens with it, the automatic preset carries it in every set",
    { scene: { kind: "wide", framing: "wide", dark: false }, disk: { "user_settings.json": { schemaVersion: 5, activePresetId: "std", autoPreset: true, mixOn: true, mixStrength: 65 } } },
    async (env, expect) => {
      await env.open();
      await env.settle(600);
      const start = env.of("/session/start")[0];
      expect(start.body.params.mixOn === true && start.body.params.mix === 65, "the first scan must carry the mixer brush: " + JSON.stringify([start.body.params.mixOn, start.body.params.mix]));
      const sp = start.body.scenePresets || {};
      expect(Object.keys(sp).length === 8 && Object.keys(sp).every((k) => sp[k].mixOn === true && sp[k].mix === 65), "...and so must every set of the automatic preset");
      expect(env.el("dlgChkMix").checked && env.el("gValMix").textContent === "65%", "the controls show what the settings brought");
      expect(env.state("previewMatchesSettings()") === true && env.recomputes().length === 0, "the picture of the first scan is for these values: nothing is asked again");
    });

  await scenario("settings of an older version say nothing of the mixer brush: it is off, at 50", { disk: { "user_settings.json": { schemaVersion: 5, activePresetId: "std", autoPreset: false } } }, async (env, expect) => {
    await env.open();
    expect(env.of("/session/start")[0].body.params.mixOn === false && env.of("/session/start")[0].body.params.mix === 50, "off, and 50 when it is switched on");
  });

  await scenario("a check box is ticked by a click anywhere in its box - the caption, the icon - and does its work once", { recomputeDelay: 150, detail: false }, async (env, expect) => {
    env.check("dlgChkAutoPreset", false);
    await env.open();
    expect(env.doc.querySelectorAll("label").length === 0, "no <label> in the panel: Photoshop draws its text in its own size and colour");
    const boxes = Array.from(env.doc.querySelectorAll("[data-check]")).map((b) => b.getAttribute("data-check")).sort().join();
    expect(boxes === "dlgChkAutoPreset,dlgChkDress,dlgChkMakeMask,dlgChkMix,dlgChkSmoke,dlgChkStands,gChkDetail,gChkShadow", "every check box has its box: " + boxes);
    env.click("dlgBtnGear");
    const caption = env.el("gChkShadow").parentNode.querySelector("span");
    env.mouse(caption, "click", 0);                          // a click on the words
    expect(env.el("gChkShadow").checked === false, "a click on the caption must tick the check box (this one was ticked: it is not now)");
    await env.settle(700);
    let rc = env.recomputes();
    expect(rc.length === 1 && rc[0].body.params.shadow === false, `...and do its work once: ${rc.length} request(s)`);
    env.el("gChkShadow").click();                            // a click on the check box itself
    await env.settle(700);
    rc = env.recomputes();
    expect(env.el("gChkShadow").checked === true && rc.length === 2 && rc[1].body.params.shadow === true, `the check box itself: once as well, not twice: ${rc.length}`);
    env.mouse(env.el("dlgWrapSmoke").querySelector("img"), "click", 0);   // the icon of the smoke pill
    await env.settle(700);
    rc = env.recomputes();
    expect(env.el("dlgChkSmoke").checked === true && env.state("smokeEnabled") === true && rc.length === 3 && rc[2].body.params.smokeOn === true, "a click on the icon ticks the smoke box and recomputes");
    env.mouse(env.el("dlgWrapMix").querySelector("span"), "click", 0);    // the word of the mixer pill
    await env.settle(700);
    rc = env.recomputes();
    expect(env.el("dlgChkMix").checked === true && rc.length === 4 && rc[3].body.params.mixOn === true, "...and the mixer brush");
    env.mouse(env.el("dlgChkMakeMask").parentNode, "click", 0);
    expect(env.el("dlgChkMakeMask").checked === true && env.state("makeMaskDefault") === true, "'Make Mask' by a click on its box");
    env.mouse(env.el("gChkDetail").parentNode.querySelector("span"), "click", 0);
    expect(env.el("gChkDetail").checked === true && env.state("detailPreview") === true,
      `'Детальний перегляд' by a click on its caption: ${env.el("gChkDetail").checked} / ${env.state("detailPreview")}`);
    env.mouse(env.el("dlgChkAutoPreset").parentNode.querySelector("span"), "click", 0);
    expect(env.el("dlgChkAutoPreset").checked === true && env.state("autoPreset") === true, "'Авто' of the presets by a click on its caption");
  });

  // ---------------------------------------------------------------- 4.13.0: what the owner asked for on 2026-11-24
  await scenario("the ring of the brush follows '[' and ']' at once, without a mouse move; so do the tool keys", { detail: false, previewSize: [400, 600] }, async (env, expect) => {
    await env.open();
    // (the simulated browser lays nothing out: the photo is given the size its rectangle has, 400 x 600)
    Object.defineProperty(env.el("dlgStage"), "offsetWidth", { value: 400, configurable: true });
    Object.defineProperty(env.el("dlgStage"), "offsetHeight", { value: 600, configurable: true });
    env.state("setActiveTool('brush')");
    const ring = () => {
      const c = env.el("dlgBrushCursor");
      return c.style.display === "none" || !c.style.width ? null : { size: parseFloat(c.style.width), cx: parseFloat(c.style.left) + parseFloat(c.style.width) / 2, cy: parseFloat(c.style.top) + parseFloat(c.style.height) / 2, colour: c.style.borderColor };
    };
    env.keyDown({ key: "]", code: "BracketRight" });         // the pointer was never seen over the photo
    expect(ring() === null && env.state("sessState.brushSize") === 33, "a key draws no ring where no pointer is; the size changes all the same");
    env.move(200, { clientY: 300 });
    const r0 = ring();
    expect(r0 && r0.size === 66 && Math.abs(r0.cx - 200) <= 1 && Math.abs(r0.cy - 300) <= 1, "the ring is under the pointer, as large as the brush: " + JSON.stringify(r0));
    env.keyDown({ key: "]", code: "BracketRight" });
    const r1 = ring();
    expect(r1 && r1.size === 76 && Math.abs(r1.cx - 200) <= 1 && Math.abs(r1.cy - 300) <= 1,
      "']' makes the ring larger at once, where it is - no mouse move: " + JSON.stringify(r1));
    env.keyDown({ key: "х", code: "BracketLeft" });
    env.keyDown({ key: "х", code: "BracketLeft" });
    expect(ring() && ring().size === 56, "'[' twice: smaller at once: " + JSON.stringify(ring()));
    env.click("dlgBrushBigger");
    expect(ring() && ring().size > 56, "the '+' button next to the size: the ring follows as well: " + JSON.stringify(ring()));
    const green = ring().colour;
    env.keyDown({ key: "e", code: "KeyE" });
    expect(ring() && ring().colour !== green, "E: the ring takes the colour of the eraser at once: " + JSON.stringify(ring()));
    env.keyDown({ key: "h", code: "KeyH" });
    expect(ring() === null, "H: the hand has no ring - it goes at once");
    env.keyDown({ key: "b", code: "KeyB" });
    expect(ring() && ring().colour === green, "B: the ring of the brush is back, without a mouse move");
    env.move(900, { clientY: 700 });                         // the pointer leaves the photo
    expect(ring() === null, "no ring off the photo");
    env.keyDown({ key: "]", code: "BracketRight" });
    expect(ring() === null, "...and a key does not bring it back there");
    expect(env.recomputes().length === 0 && env.edits().length === 0, "none of this asks the server for anything");
  });

  await scenario("'Стійки': a tick on the top bar next to the others, one full recompute; a preset sets it; no row of the settings", { recomputeDelay: 150, detail: false }, async (env, expect) => {
    env.check("dlgChkAutoPreset", false);
    await env.open();
    expect(env.doc.getElementById("gChkRemoveStands") === null, "the row of the settings is gone");
    expect(env.el("dlgWrapStands").parentNode === env.el("dlgWrapMix").parentNode && env.el("dlgWrapStands").parentNode === env.el("dlgWrapSmoke").parentNode,
      "the tick stands on the top bar, in the row of the other ticks");
    expect(env.el("dlgWrapStands").textContent.trim() === "Стійки" && (env.el("dlgWrapStands").getAttribute("data-tip") || "").includes("Прибирати стійки"), "it has a word and a hint");
    expect(env.of("/session/start")[0].body.params.removeStands === false && !env.el("dlgChkStands").checked, "off until it is ticked");
    env.server.stats = { elapsed_ms: 9200, reused_stages: ["fg", "maps"], timing: { fill_tiles: 125, fill_s: 6.0, fill_ep: "CUDAExecutionProvider", fallback: {} } };
    env.mouse(env.el("dlgWrapStands").querySelector("span"), "click", 0);   // a click on the word
    expect(env.el("dlgChkStands").checked && env.el("dlgWrapStands").classList.contains("active") && env.hint().includes("Прибирати стійки"), "ticked, lit, said: " + env.hint());
    await sleep(60);
    expect(env.progressCardVisible(), "the progress card comes at once");
    await env.settle(600);
    let rc = env.recomputes();
    expect(rc.length === 1 && rc[0].body.quick === undefined && typeof rc[0].body.jobId === "string" && rc[0].body.params.removeStands === true,
      "one full recompute with the stands to be removed: " + JSON.stringify(rc.map((r) => [r.body.quick, r.body.params.removeStands])));
    expect(env.hint().includes("Перераховано за 9,2 с") && env.hint().includes("людину взято готовою"), "the hint line says what the run took and what was taken ready: " + env.hint());
    expect(env.state("presetConfigToSave().removeStands") === true, "it is a value of the preset, as before");
    env.click("dlgBtnPresets");
    env.clickPreset("Студія (Стандарт)");
    expect(!env.el("dlgChkStands").checked && !env.el("dlgWrapStands").classList.contains("active"), "a preset without it unticks the box and its pill");
    env.clickPreset("Без стійок (AI)");
    await env.settle(900);
    rc = env.recomputes();
    expect(env.el("dlgChkStands").checked && env.el("dlgWrapStands").classList.contains("active") && rc[rc.length - 1].body.params.removeStands === true,
      "the preset 'Без стійок (AI)' ticks it, and the refresh carries it");
    env.click("dlgBtnApply");
    await env.settle(900);
    expect(env.of("/session/apply").length === 1 && env.of("/session/apply")[0].body.params.removeStands === true, "Apply carries it");
  });

  await scenario("every tick and switch that changes the frame asks for the exact frame at once; a slider for the quick preview; the clothing tick for neither", { recomputeDelay: 100, detail: false }, async (env, expect) => {
    env.check("dlgChkAutoPreset", false);
    await env.open();
    env.click("dlgBtnGear");
    const steps = [
      ["the mixer tick", () => env.check("dlgChkMix", true), (p) => p.mixOn === true],
      ["the mixer switch of the settings", () => env.click("gBtnMix"), (p) => p.mixOn === false],
      ["the seam switch", () => env.click("gBtnSeam"), (p) => p.seamOn === false],
      ["the shadows tick", () => env.check("gChkShadow", false), (p) => p.shadow === false],
      ["the stands tick", () => env.check("dlgChkStands", true), (p) => p.removeStands === true],
      ["the smoke switch of the settings", () => env.click("gBtnSmoke"), (p) => p.smokeOn === true],
      ["the smoke tick", () => env.check("dlgChkSmoke", false), (p) => p.smokeOn === false]
    ];
    for (const [name, act, carries] of steps) {
      const before = env.recomputes().length;
      act();
      await sleep(40);
      const shown = env.progressCardVisible();
      await env.settle(500);
      const rc = env.recomputes();
      const last = rc[rc.length - 1];
      expect(rc.length === before + 1 && last.body.quick === undefined && typeof last.body.jobId === "string" && carries(last.body.params) && shown,
        `${name}: one full recompute with the progress card and the new value (${rc.length - before} request(s), quick ${last && last.body.quick}, card ${shown})`);
    }
    expect(env.state("previewMatchesSettings()") === true && env.state("sessState.exactShown") === true, "the picture on screen is the exact one for these values");
    let before = env.recomputes().length;
    await env.drag("gSlScuffs", 40);
    await env.settle(900);
    let rc = env.recomputes();
    expect(rc.length === before + 1 && rc[rc.length - 1].body.quick === true, "a slider gives a light refresh, as before");
    before = rc.length;
    env.check("dlgChkDress", true);
    await env.settle(600);
    expect(env.recomputes().length === before && env.of("/session/dress-preview").length >= 1, "the clothing tick keeps its own instant preview");
    expect((env.el("gLiveNote").textContent || "").includes("Галочка") && env.el("gLiveNote").textContent.includes("лише те, що змінилося"), "the note of the settings says so: " + env.el("gLiveNote").textContent);
  });

  await scenario("an exact recompute says what was taken ready: the hint line, and the time line when the AI fill was not run again", { recomputeDelay: 100, detail: false }, async (env, expect) => {
    env.check("dlgChkAutoPreset", false);
    env.server.stats = { elapsed_ms: 28000, reused_stages: [], timing: { fill_tiles: 125, fill_s: 15.2, fill_ep: "CUDAExecutionProvider", fallback: {} } };
    await env.open();
    const line = () => env.el("gTimeLine").textContent;
    expect(line().includes("28 с") && line().includes("125"), "the line of the settings after the first computation: " + line());
    env.server.stats = { elapsed_ms: 1900, reused_stages: ["heal", "fg", "maps", "corner", "detect", "scuffs"] };   // (no "timing": the AI fill did not run)
    env.click("dlgBtnRecompute");
    await env.settle(500);
    expect(env.hint().includes("Перераховано за 1,9 с") && env.hint().includes("AI-заливку взято готовими") && env.hint().includes("лише те, що змінилося"),
      "the button: the hint says that only what changed was computed: " + env.hint());
    expect(line().includes("1,9 с") && line().includes("AI-заливку взято готову") && !line().includes("125") && !env.el("gTimeLine").classList.contains("warn"),
      "...and the line of the settings no longer shows the time of the run before: " + line());
    env.server.stats = { elapsed_ms: 14000, reused_stages: ["fg", "maps", "corner", "detect"], timing: { fill_tiles: 60, fill_s: 7.0, fill_ep: "CUDAExecutionProvider", fallback: {} } };
    env.check("dlgChkMix", true);
    await env.settle(500);
    expect(env.hint().includes("за 14 с") && env.hint().includes("пошук дефектів взято готовими") && env.hint().includes("заново"), "the search taken ready, the fill made anew: " + env.hint());
    expect(line().includes("14 с") && line().includes("60 пл"), "the time line shows the fill of this run again: " + line());
    env.server.stats = { elapsed_ms: 26000, reused_stages: ["fg"], timing: { fill_tiles: 120, fill_s: 14.0, fill_ep: "CUDAExecutionProvider", fallback: {} } };
    env.check("gChkShadow", false);
    await env.settle(500);
    expect(env.hint().includes("людину взято готовою") && env.hint().includes("26 с"), "only the person taken ready: " + env.hint());
    env.server.stats = {};                                   // an older server says nothing of this
    env.check("gChkShadow", true);
    await env.settle(500);
    expect(env.hint().startsWith("✓ Перераховано") && !env.hint().includes("undefined") && !env.hint().includes("NaN"), "an answer without these numbers: a plain sentence: " + env.hint());
    await env.drag("gSlScuffs", 40);
    await env.settle(900);
    expect(!env.hint().includes("Перераховано"), "a light refresh says none of this: " + env.hint());
  });

  // ("Зйомка з димом" as 4.12.0 shipped it - see SMOKE_PRESET_412 above - on a PC that had it as the active preset)
  const pc412 = () => {
    const now = JSON.parse(fs.readFileSync(path.join(PLUGIN_DIR, "..", "server", "presets_defaults.json"), "utf8"));
    now.forEach((p) => { delete p.cfg.cycDepth; });           // ("Глибина" came with 4.14.0)
    now.splice(now.findIndex((p) => p.id === "clean_stands"), 0, JSON.parse(JSON.stringify(SMOKE_PRESET_412)));
    now.push({ id: "usr_1700000000000", name: "Зйомка з димом", color: "#54d182", builtin: false, cfg: Object.assign({}, SMOKE_PRESET_412.cfg, { spots: 44 }) });
    return now;
  };
  await scenario("a PC of 4.12.0: the built-in preset 'Зйомка з димом' is gone after the update, the user's own preset of that name stays",
    { disk: { "presets_local.json": pc412(), "user_settings.json": { schemaVersion: 5, activePresetId: "smoke", autoPreset: false, cfg: Object.assign({}, SMOKE_PRESET_412.cfg),
        presetMoves: ["cyc65", "smokeOff", "lowkeySpots80", "lowkeyCyc65"], knownDefaultIds: pc412().filter((p) => p.builtin).map((p) => p.id) } },
      serverPresets: pc412() }, async (env, expect) => {
      await sleep(500);                                      // bootstrap + the first sync with the server
      const ids = env.state("presetsList.map((p) => p.id).join()");
      expect(ids === "std,medium_shot,closeup,wide_shot,lowkey,lowkey_medium,lowkey_close,lowkey_wide,clean_stands,gentle,usr_1700000000000",
        "the built-in smoke preset must leave the list, everything else stay in place: " + ids);
      expect(env.state("activePresetId") === "std" && env.el("dlgActivePresetName").textContent === "Студія (Стандарт)", "it was the active one: the first preset takes its place: " + env.state("activePresetId"));
      expect(env.state("getSliderVal('gSlCyc')") === 65 && env.state("getSliderVal('gSlSmoke')") === 80 && env.state("smokeEnabled") === false && !env.el("dlgChkSmoke").checked,
        "...with its values on the controls (the corner tool at 65, smoke off): " + [env.state("getSliderVal('gSlCyc')"), env.state("getSliderVal('gSlSmoke')"), env.state("smokeEnabled")].join());
      const names = Array.from(env.doc.querySelectorAll("#dlgPresetsList .preset-btn")).map((b) => b.textContent.trim());
      expect(names.filter((n) => n === "Зйомка з димом").length === 1 && names.length === 11, "the list of the window shows the user's own preset of that name, once: " + names.join(" | "));
      const onDisk = env.server.disk;
      expect(!onDisk["presets_local.json"].some((p) => p.id === "smoke") && onDisk["presets_local.json"].length === 11 && onDisk["user_settings.json"].activePresetId === "std",
        "the files on the PC must hold it that way");
      const sent = env.of("/presets").filter((r) => r.method === "POST");
      expect(sent.length >= 1 && !sent[sent.length - 1].body.some((p) => p.id === "smoke") && sent[sent.length - 1].body.some((p) => p.id === "usr_1700000000000"),
        "...and so must the copy on the server");
      expect(env.state("dropRetiredPresets()") === false, "nothing is left to take out");
      await env.open();
      const p = env.of("/session/start")[0].body.params;
      expect(p.smokeOn === false && p.cycCurve === 65 && p.smoke === 80, "the window opens with the values of the preset that took its place: " + JSON.stringify([p.smokeOn, p.cycCurve, p.smoke]));
      env.click("dlgBtnPresets");
      env.clickPreset("Зйомка з димом");                       // the user's own one still works
      expect(env.state("activePresetId") === "usr_1700000000000" && env.el("dlgChkSmoke").checked && env.state("getSliderVal('gSlSpots')") === 44, "the user's own preset is as it was saved");
    });

  await scenario("...also while the server is not running: the smoke preset leaves the list when the panel starts",
    { online: false, disk: { "presets_local.json": pc412(), "user_settings.json": { schemaVersion: 5, activePresetId: "wide_shot", autoPreset: false,
        presetMoves: ["cyc65", "smokeOff", "lowkeySpots80", "lowkeyCyc65"], knownDefaultIds: pc412().filter((p) => p.builtin).map((p) => p.id) } } },
    async (env, expect) => {
      await sleep(400);
      expect(env.state("presetsList.some((p) => p.id === 'smoke')") === false && env.state("presetsList.length") === 11 && env.state("activePresetId") === "wide_shot",
        "the list is without it before the server has said a word; the active preset stays: " + env.state("presetsList.map((p) => p.id).join()"));
      expect(!env.server.disk["presets_local.json"].some((p) => p.id === "smoke"), "...and so is the file on the PC");
    });

  await scenario("a reinstalled Photoshop: the presets come from the copy on the server - without the smoke preset", { disk: {}, serverPresets: pc412() }, async (env, expect) => {
    await sleep(500);
    const ids = env.state("presetsList.map((p) => p.id).join()");
    expect(ids === "std,medium_shot,closeup,wide_shot,lowkey,lowkey_medium,lowkey_close,lowkey_wide,clean_stands,gentle,usr_1700000000000",
      "the list of the server is taken over, the built-in smoke preset is left out: " + ids);
    const sent = env.of("/presets").filter((r) => r.method === "POST");
    expect(sent.length >= 1 && !sent[sent.length - 1].body.some((p) => p.id === "smoke"), "the server gets its copy back without it");
  });

  await scenario("the list of the settings takes the height the window has; its rows do not shrink", { detail: false }, async (env, expect) => {
    await env.open();
    const list = env.doc.querySelector("#dlgGearPopover .gear-scroll");
    const open = (high) => {
      if (env.el("dlgGearPopover").classList.contains("visible")) env.click("dlgBtnGear");
      if (high === null) delete env.el("r4mShell").offsetHeight;
      else Object.defineProperty(env.el("r4mShell"), "offsetHeight", { value: high, configurable: true });
      env.click("dlgBtnGear");
      return list.style.maxHeight;
    };
    expect(open(null) === "", "where the size of the window cannot be read the style sheet decides: '" + list.style.maxHeight + "'");
    expect(open(740) === "380px", "a window of the default height: " + list.style.maxHeight);
    expect(open(960) === "600px", "the owner's window, about 960 px high: " + list.style.maxHeight);
    expect(open(2400) === "760px" && open(420) === "300px", "never more than 760 px, never less than 300: " + list.style.maxHeight);
    const css = fs.readFileSync(path.join(PLUGIN_DIR, "styles.css"), "utf8");
    const rule = (sel) => { const m = css.match(new RegExp(sel.replace(/[.*>]/g, "\\$&") + "\\s*\\{([^}]*)\\}")); return m ? m[1] : ""; };
    expect(/flex-shrink:\s*0/.test(rule(".gear-scroll > *")), "styles.css: the rows of the list must not shrink ('.gear-scroll > *')");
    const named = css.match(/\.gear-scroll \.g-row,[\s\S]*?\{([^}]*)\}/);
    expect(named && /flex-shrink:\s*0/.test(named[1]) && /\.gear-scroll \.ps-check/.test(named[0]) && /\.gear-scroll \.g-passes-row/.test(named[0]),
      "...and the same said for the kinds of rows by name");
    const kinds = new Set(Array.from(list.children).map((n) => (n.className || "").split(" ")[0]));
    const covered = ["g-row", "ps-check", "g-passes-row", "btn-primary", "btn-sec", "g-time-line", "g-vram-box"];
    expect(Array.from(kinds).every((k) => covered.includes(k)), "every kind of row in the list is named in that rule: " + Array.from(kinds).join());
  });

  // ------------------------------------------------------------------ 4.14.0: the owner's list of the evening of 2026-11-24
  const holder = (env) => { const a = env.doc.activeElement; return a ? (a.id || a.tagName) : "nothing"; };

  await scenario("the photo holds the keyboard of the window: at opening, under the mouse, after a press on it; a name being typed keeps it", { detail: false }, async (env, expect) => {
    await env.open();
    await env.settle(500);
    const vp = env.el("dlgViewport");
    const size = () => env.state("sessState.brushSize");
    const hover = () => { env.state("sessState.keysAskedMs = 0"); env.move(200, { clientY: 300 }); };
    expect(env.doc.activeElement === vp, "after opening the photo must hold the keyboard: " + holder(env));
    const s0 = size();
    env.keyDown({ key: "]", code: "BracketRight" }, vp);      // heard at the window, at the document and at the host's window
    expect(size() === s0 + 5, `one press of ']' with the keyboard on the photo counts once: ${s0} -> ${size()}`);
    env.keyDown({ key: "х", code: "BracketLeft" }, vp);
    expect(size() === s0, "...and '[' takes it back: " + size());
    env.keyDown({ key: " ", code: "Space" }, vp);
    expect(env.state("sessState.spaceDown") === true, "Space is the hand while it is held");
    vp.dispatchEvent(new env.w.KeyboardEvent("keyup", { bubbles: true, key: " ", code: "Space" }));
    expect(env.state("sessState.spaceDown") === false && env.state("sessState.tool") === "eraser", "...and the tool is back when it is released");
    // a tick of the settings was clicked last; the mouse comes back to the photo
    env.click("dlgBtnGear");
    env.el("gChkShadow").focus();
    expect(holder(env) === "gChkShadow", "(the tick holds the keyboard now: " + holder(env) + ")");
    hover();
    expect(env.doc.activeElement === vp, "the mouse over the photo gives the keyboard back to it: " + holder(env));
    // a name is being typed: the keyboard stays in the field, whatever the mouse passes over
    env.click("dlgBtnPresets");
    env.click("dlgBtnAddPreset");
    expect(holder(env) === "dlgNewPresetName", "(the field of the new preset holds the keyboard: " + holder(env) + ")");
    hover();
    expect(holder(env) === "dlgNewPresetName", "while a name is typed the mouse over the photo must take nothing: " + holder(env));
    env.keyDown({ key: "]", code: "BracketRight" }, env.el("dlgNewPresetName"));
    expect(size() === s0, "...and ']' types its character there: " + size());
    // a press on the photo area ends the typing (beside the photo: no stroke is made)
    env.press("dlgViewport", 900, { clientY: 700 });
    env.release();
    expect(env.doc.activeElement === vp, "a press on the photo area takes the keyboard, from a text field too: " + holder(env));
    // the form was closed while its field held the keyboard: that is no typing
    env.click("dlgBtnPresets");
    if (!env.el("dlgAddPresetForm").classList.contains("visible")) env.click("dlgBtnAddPreset");
    env.el("dlgNewPresetName").focus();
    env.click("dlgBtnCancelNewPreset");
    hover();
    expect(env.doc.activeElement === vp, "the field of a closed form is not being typed in: " + holder(env));
    env.keyDown({ key: "]", code: "BracketRight" }, env.doc.activeElement);
    expect(size() === s0 + 5, "...and the keys work again: " + size());
    await env.settle(300);
    expect(env.recomputes().length === 0 && env.edits().length === 0, "none of this asks the server for anything");
  });

  await scenario("the second window: 'Застосувати' was clicked last and holds nothing while the next photo is scanned - the keys arrive all the same", { detail: false }, async (env, expect) => {
    await env.open();
    await env.settle(500);
    const size = () => env.state("sessState.brushSize");
    env.el("dlgBtnApply").focus();
    env.click("dlgBtnApply");
    await env.waitFor(() => env.state("sessState.open") === false, 4000);
    await env.settle(500);
    // Photoshop: the control that held the keyboard is switched off for the scan of the next photo - nothing holds it
    if (env.doc.activeElement && env.doc.activeElement.blur) env.doc.activeElement.blur();
    expect(env.doc.activeElement === env.doc.body, "(nothing holds the keyboard between the two windows: " + holder(env) + ")");
    env.click("btnRun");
    await env.waitFor(() => env.of("/session/start").length === 2 && !!env.state("sessState.id"), 4000);
    await env.settle(500);
    expect(env.state("sessState.open") === true && env.doc.activeElement === env.el("dlgViewport"), "in the second window the photo must hold the keyboard: " + holder(env));
    const s0 = size();
    env.keyDown({ key: "ї", code: "BracketRight" }, env.doc.activeElement);
    env.keyDown({ key: "ї", code: "BracketRight" }, env.doc.activeElement);
    expect(size() === s0 + 10, `']' twice in the second window: ${s0} -> ${size()}`);
    env.keyDown({ key: "х", code: "BracketLeft" }, env.doc.activeElement);
    expect(size() === s0 + 5, "'[' once: " + size());
  });

  await scenario("a host that gives the keyboard to no plain element: the button of the tool in hand takes it", { detail: false }, async (env, expect) => {
    env.el("dlgViewport").focus = () => {};
    await env.open();
    await env.settle(500);
    const size = () => env.state("sessState.brushSize");
    expect(holder(env) === "dlgToolEraser", "the eraser is the tool of a new window, and its button holds the keyboard: " + holder(env));
    const s0 = size();
    env.keyDown({ key: "]", code: "BracketRight" }, env.doc.activeElement);
    expect(size() === s0 + 5, `']' arrives, once: ${s0} -> ${size()}`);
    env.keyDown({ key: "b", code: "KeyB" }, env.doc.activeElement);
    env.click("dlgBtnGear");
    env.el("gChkShadow").focus();
    env.state("sessState.keysAskedMs = 0");
    env.move(200, { clientY: 300 });
    expect(holder(env) === "dlgToolBrush", "after B the brush is in hand, and the mouse over the photo gives its button the keyboard: " + holder(env));
  });

  await scenario("'Глибина': a slider under 'Циклорама' - 60 in the light presets, 0 in the dark ones; one light refresh, Apply carries it; nothing without the corner tool", { detail: false },
    async (env, expect) => {
      env.check("dlgChkAutoPreset", false);
      await env.open();
      env.click("dlgBtnGear");
      env.click("dlgBtnPresets");
      const depth = () => env.state('getSliderVal("gSlDepth")');
      const badge = () => env.el("gValDepth").textContent;
      const quick = () => env.recomputes().filter((r) => r.body.quick === true);
      const rows = Array.from(env.doc.querySelectorAll("#dlgGearPopover .gear-scroll > .g-row"));
      const at = (id) => rows.findIndex((n) => !!n.querySelector("#" + id));
      expect(at("gSlDepth") === at("gSlCyc") + 1 && at("gSlCyc") >= 0, "the row stands right under 'Циклорама': " + at("gSlCyc") + " / " + at("gSlDepth"));
      const want = { "Студія (Стандарт)": 60, "Середній план": 60, "Дальній план": 60, "Без стійок (AI)": 60, "Темний ключ": 0, "Темний середній план": 0, "Темний дальній план": 0 };
      for (const [name, value] of Object.entries(want)) {
        env.clickPreset(name);
        expect(depth() === value && badge() === (value ? value + "%" : "Вимк.") && !env.el("gSlDepth").classList.contains("disabled"),
          `the preset '${name}': depth ${value} expected, the slider says ${depth()} / '${badge()}'`);
      }
      env.clickPreset("Дальній план");
      await env.settle(1000);
      let last = quick().pop();
      expect(last && last.body.params.cycDepth === 60 && last.body.params.cycCurve === 65, "the refresh after a preset click carries its depth: " + (last && last.body.params.cycDepth));
      const before = quick().length;
      await env.drag("gSlDepth", 90);
      await env.settle(1000);
      last = quick().pop();
      expect(quick().length === before + 1 && last.body.params.cycDepth === 90 && badge() === "90%", `one light refresh with depth 90: ${quick().length - before} refreshes, '${badge()}'`);
      expect(env.exacts().length === 0, "a slider asks for the quick preview, not for the exact frame");
      expect(env.state("presetConfigToSave().cycDepth") === 90, "depth is a value of the preset");
      // without the corner tool depth is nothing: the row says so, cannot be moved, and asks for no new picture
      env.clickPreset("Ближній план");
      await env.settle(1000);
      expect(badge() === "—" && env.el("gSlDepth").classList.contains("disabled") && depth() === 0,
        `a preset without the corner tool: the row must say '—', be greyed and stand at 0 - it says '${badge()}', greyed: ${env.el("gSlDepth").classList.contains("disabled")}, depth ${depth()}`);
      const n0 = env.recomputes().length;
      const sig0 = env.state("previewSettingsSignature()");
      await env.drag("gSlDepth", 70);
      await env.settle(900);
      expect(depth() === 0 && env.recomputes().length === n0, "the greyed slider does not move and sends nothing");
      env.state('setSliderVal("gSlDepth", 70)');
      expect(env.state("previewSettingsSignature()") === sig0, "...and a depth without the corner tool is no new setting for the picture");
      env.state('setSliderVal("gSlDepth", 0)');
      await env.drag("gSlCyc", 50);
      expect(badge() === "Вимк." && !env.el("gSlDepth").classList.contains("disabled"), "with the corner tool moved up the row comes alive: '" + badge() + "'");
      await env.drag("gSlDepth", 35);
      await sleep(100);                      // sooner than the refresh would start
      env.click("dlgBtnApply");
      await env.settle(900);
      const a = env.of("/session/apply");
      expect(a.length === 1 && a[0].body.params.cycDepth === 35 && a[0].body.params.cycCurve === 50, "Apply carries depth: " + (a[0] && a[0].body.params.cycDepth));
    });

  // ---------------------------------------------------------------- a new result leaves "До" (4.16.0)
  // The owner, 2026-11-26: «ще коли полоска доходе показує фото після бо зари до не зручно» - when the bar reaches
  // its end, show the photo "after"; now "before" stays on screen, which is inconvenient.
  const beforeLit = (env) => env.el("dlgBtnBeforeAfter").classList.contains("active");
  const barGone = (env) => env.waitFor(() => !env.progressCardVisible() && env.state("sessState.recomputing") === false, 4000);

  await scenario("a new result leaves 'До': a tick or '↻ Перерахувати' pressed while the original is shown - the bar ends on the cleaned photo; 'Маска' stays", { recomputeDelay: 400, detail: false },
    async (env, expect) => {
      env.check("dlgChkAutoPreset", false);
      await env.open();
      const full = () => env.recomputes().filter((r) => r.body.quick === undefined);
      env.click("dlgBtnBeforeAfter");
      expect(env.view() === "original" && beforeLit(env), "'До / Після' shows the original, got " + env.view());
      expect((env.el("dlgBtnBeforeAfter").getAttribute("data-tip") || "").includes("само повертається до чистого фото"),
        "the hint of 'До / Після' says that a new result brings the cleaned photo back by itself");
      env.check("dlgChkSmoke", true);                          // a tick: the exact frame, with the bar
      await sleep(150);
      expect(env.progressCardVisible() && full().length === 1, "the tick asks for the exact frame, with the bar");
      expect(env.view() === "original" && beforeLit(env) && env.modeBadge() === "ДО · оригінал", "while the bar is running nothing new is there to show: 'До' stays, got " + env.view());
      await barGone(env);
      expect(env.view() === "result", "the bar reached its end: the cleaned photo must be on screen, got " + env.view());
      expect(!beforeLit(env) && env.modeBadge() === "ПІСЛЯ · чисте фото", `...the button is not lit, the corner label says so: '${env.modeBadge()}'`);
      expect(env.pictureName() === full()[0].picture, "...and it is the picture of that run: " + env.pictureName());

      env.click("dlgBtnBeforeAfter");                          // the button of the bottom bar
      env.click("dlgBtnRecompute");
      await sleep(150);
      expect(env.view() === "original" && env.progressCardVisible(), "'↻ Перерахувати' on 'До': the bar runs over the original");
      await barGone(env);
      expect(env.view() === "result" && full().length === 2 && env.pictureName() === full()[1].picture, "'↻ Перерахувати': the bar ends on the cleaned photo, got " + env.view());

      env.click("dlgBtnRecompute");                            // "До / Після" pressed WHILE the bar is running
      await sleep(150);
      env.click("dlgBtnBeforeAfter");
      expect(env.view() === "original" && env.progressCardVisible(), "the button works while the bar is running");
      await barGone(env);
      expect(env.view() === "result" && !beforeLit(env), "...and the bar still ends on the cleaned photo, got " + env.view());

      env.click("dlgBtnBeforeAfter");                          // the button of the settings
      env.click("dlgBtnGear");
      env.click("gBtnRecompute");
      await sleep(100);
      await barGone(env);
      expect(env.view() === "result" && full().length === 4, "'↻ Перерахувати зараз' of the settings: the same, got " + env.view());

      env.click("dlgBtnMask");                                 // the mask shows the new zones: it stays
      env.check("dlgChkSmoke", false);
      await sleep(150);
      expect(env.view() === "mask" && env.progressCardVisible(), "the mask is on, the bar is running");
      await barGone(env);
      expect(env.view() === "mask" && env.el("dlgBtnMask").classList.contains("active") && env.modeBadge().includes("МАСКА"), "'Маска' must stay after the bar, got " + env.view());
      expect(env.pictureName() === full()[4].picture, "(the new picture is under it: " + env.pictureName() + ")");
      env.click("dlgBtnMask");
      expect(env.view() === "result", "'Маска' again: the cleaned photo");
      env.click("dlgBtnRecompute");                            // on the cleaned photo there is nothing to switch
      await sleep(100);
      await barGone(env);
      expect(env.view() === "result" && full().length === 6 && env.recomputes().length === 6, `six runs with the bar, nothing else was asked: ${full().length} / ${env.recomputes().length}`);
    });

  await scenario("a new result leaves 'До': not when the run was cancelled, failed or gave way - then nothing new is there", { recomputeDelay: 600, detail: false },
    async (env, expect) => {
      env.check("dlgChkAutoPreset", false);
      await env.open();
      env.click("dlgBtnBeforeAfter");
      env.click("dlgBtnRecompute");
      await sleep(200);
      env.click("dlgBtnCancelScan");                           // "Скасувати" on the progress card
      await env.settle(900);
      expect(!env.progressCardVisible() && env.state("sessState.recomputing") === false, "the run was stopped");
      expect(env.view() === "original" && beforeLit(env), "a cancelled run brought nothing: 'До' must stay, got " + env.view());
      expect(env.pictureName() === "start-1", "(the first picture is still the one behind it: " + env.pictureName() + ")");

      env.server.failRecompute = 1;                            // the server answers with an error
      env.click("dlgBtnRecompute");
      await sleep(100);
      await barGone(env);
      expect(env.hint().includes("Помилка перерахунку"), "the error is said: " + env.hint());
      expect(env.view() === "original" && beforeLit(env), "a failed run brought nothing: 'До' must stay, got " + env.view());

      env.server.failRecompute = 1;                            // a light refresh that fails
      await env.drag("gSlSpots", 95);
      await env.settle(1500);
      expect(env.recomputes().length === 3 && env.recomputes()[2].body.quick === true && env.recomputes()[2].done, "the slider asked for its light refresh");
      expect(env.view() === "original", "a failed light refresh: 'До' must stay, got " + env.view());

      env.click("dlgBtnRecompute");                            // a run that gives way to a newer one
      await sleep(200);
      env.check("dlgChkSmoke", true);                          // ...the tick starts the run over
      await sleep(250);
      const rc = env.recomputes();
      expect(rc.length === 5 && rc[3].done && rc[3].outcome === "superseded" && !rc[4].done, "the older run gave way, the newer one is on its way: " + rc.map((r) => r.outcome).join(", "));
      expect(env.view() === "original" && env.progressCardVisible(), "the run that gave way shows nothing: the bar is still running, 'До' stays; got " + env.view());
      await barGone(env);
      expect(env.view() === "result" && env.pictureName() === rc[4].picture, `the newer run ends on the cleaned photo, with its picture: ${env.view()} / ${env.pictureName()}`);
    });

  await scenario("a new result leaves 'До': a server before 4.12.0 - the picture of the older run is dropped, the view waits for the newer one", { recomputeDelay: 700, newestWins: false, detail: false },
    async (env, expect) => {
      env.check("dlgChkAutoPreset", false);
      await env.open();
      env.click("dlgBtnBeforeAfter");
      env.click("dlgBtnRecompute");
      await sleep(300);
      env.click("dlgFracFine");
      await sleep(650);                                        // the first run has answered in full by now
      const rc = env.recomputes();
      expect(rc.length === 2 && rc[0].done && rc[0].outcome === "done" && !rc[1].done, "the old server finished the first run and is on the second");
      expect(env.view() === "original" && env.progressCardVisible(), "the answer of the older run is dropped: the bar is still running and 'До' stays, got " + env.view());
      await barGone(env);
      expect(env.view() === "result" && env.pictureName() === rc[1].picture, `the second run ends on the cleaned photo: ${env.view()} / ${env.pictureName()}`);
    });

  await scenario("a new result leaves 'До': a slider, a preset, a fraction button and the clothing tick - when their picture comes; Blend and a mask step bring none", { detail: false },
    async (env, expect) => {
      env.check("dlgChkAutoPreset", false);
      await env.open();
      env.click("dlgBtnGear");
      env.click("dlgBtnPresets");
      env.click("dlgBtnBeforeAfter");
      await env.drag("gSlSpots", 90);
      await sleep(250);
      expect(env.recomputes().length === 0 && env.view() === "original", "the refresh has not been asked for yet: 'До' stays, got " + env.view());
      await lightDone(env, 1);
      await sleep(30);
      expect(env.view() === "result" && !beforeLit(env), "the light refresh of a slider is back: the cleaned photo, got " + env.view());
      expect(env.pictureName() === env.recomputes()[0].picture && env.modeBadge() === "ПІСЛЯ · швидкий перегляд", `...its picture, named as a quick one: ${env.pictureName()} / '${env.modeBadge()}'`);

      env.click("dlgBtnBeforeAfter");
      env.clickPreset("Дальній план");
      await lightDone(env, 2);
      await sleep(30);
      expect(env.view() === "result" && env.pictureName() === env.recomputes()[1].picture, "a preset click on 'До': the cleaned photo when its refresh is back, got " + env.view());

      env.click("dlgBtnBeforeAfter");
      env.click("dlgFracFine");
      await lightDone(env, 3);
      await sleep(30);
      expect(env.view() === "result" && env.pictureName() === env.recomputes()[2].picture, "a fraction button on 'До': the same, got " + env.view());

      env.click("dlgBtnBeforeAfter");                          // the clothing tick: no recompute, a picture of its own
      env.check("dlgChkDress", !env.el("dlgChkDress").checked);
      await env.waitFor(() => env.pictureName().startsWith("dress-"), 1500);
      await sleep(30);
      expect(env.of("/session/dress-preview").length === 1 && env.pictureName().startsWith("dress-"), "the clothing tick brought its picture: " + env.pictureName());
      expect(env.view() === "result" && !beforeLit(env), "the clothing tick on 'До': the cleaned photo, got " + env.view());

      // what brings no new result leaves "До" alone
      env.click("dlgBtnBeforeAfter");
      env.press("dlgSlBlend", 200);                            // Blend only mixes the two pictures
      env.move(120);
      expect(env.view() === "original", "Blend held on 'До': the original stays, got " + env.view());
      env.release();
      await env.settle(700);
      expect(env.view() === "original" && env.recomputes().length === 3, "Blend asks for nothing and switches nothing, got " + env.view());
      const spots = env.state('getSliderVal("gSlSpots")');     // a slider moved and put back: nothing to ask for
      await env.drag("gSlSpots", spots - 5);
      await sleep(100);
      await env.drag("gSlSpots", spots);
      await env.settle(900);
      expect(env.view() === "original" && env.recomputes().length === 3, `a slider put back to its value asks for nothing: 'До' stays (${env.view()}, ${env.recomputes().length} refreshes)`);
      env.click("dlgToolInvert");                              // a step on the whole mask says in words what it did
      await env.waitFor(() => env.picture() === "edit-1", 1500);
      await sleep(30);
      expect(env.view() === "original" && env.hint().includes("інвертовано"), "an inversion on 'До' is said in words, the view stays; got " + env.view());
      env.key("KeyZ", "z", { ctrlKey: true });                 // ...and so does the step back
      await env.waitFor(() => env.picture() === "edit-2", 1500);
      await sleep(30);
      expect(env.view() === "original" && env.hint().includes("скасовано"), "Ctrl + Z on 'До': the same, got " + env.view());

      env.click("dlgBtnBeforeAfter");                          // with the mask on, a slider leaves the mask on
      env.click("dlgBtnMask");
      await env.drag("gSlSpots", spots - 10);
      await lightDone(env, 4);
      await sleep(30);
      expect(env.recomputes().length === 4 && env.pictureName() === env.recomputes()[3].picture, "(the slider brought its picture: " + env.pictureName() + ")");
      expect(env.view() === "mask" && env.el("dlgBtnMask").classList.contains("active"), "a slider with the mask on: the mask stays, got " + env.view());
    });

  await scenario("a new result leaves 'До': the exact picture that comes by itself does not; with 2 passes the background picture of a change does", { bgDelay: 500 },
    async (env, expect) => {
      env.check("dlgChkAutoPreset", false);
      await env.open();
      env.click("dlgBtnGear");
      await env.drag("gSlSpots", 90);
      await lightDone(env, 1);
      await sleep(30);
      expect(env.view() === "result" && env.pictureName().startsWith("light-"), "the quick picture of the slider is on screen: " + env.pictureName());
      env.click("dlgBtnBeforeAfter");                          // a look at the original while the exact picture is on its way
      await exactDone(env, 1);
      await sleep(60);
      expect(env.exacts()[0].outcome === "done" && env.pictureName().startsWith("exact-"), "the exact picture came by itself: " + env.pictureName());
      expect(env.view() === "original" && beforeLit(env), "...nobody asked for it just now: whoever looks at 'До' goes on looking; got " + env.view());
      env.click("dlgBtnBeforeAfter");
      expect(env.view() === "result" && env.modeBadge() === "ПІСЛЯ · чисте фото", "'До / Після' shows it: " + env.modeBadge());

      env.click("dlgBtnBeforeAfter");                          // 2 passes: no light way, the picture of a change comes
      env.click("gPass2");                                     // in the background - and it IS what was asked for
      await exactDone(env, 2);
      await sleep(60);
      expect(env.exacts()[1].outcome === "done" && env.recomputes().length === 1, "2 passes: one background recompute, no light one");
      expect(env.view() === "result" && !beforeLit(env) && env.pictureName() === env.exacts()[1].picture, `the picture of the change is shown: ${env.view()} / ${env.pictureName()}`);
      env.click("dlgBtnBeforeAfter");
      await env.drag("gSlSpots", 95);                          // a slider with 2 passes: the same
      await exactDone(env, 3);
      await sleep(60);
      expect(env.view() === "result" && env.pictureName() === env.exacts()[2].picture, "a slider with 2 passes on 'До': the cleaned photo when its picture comes, got " + env.view());
      env.click("dlgBtnMask");
      await env.drag("gSlSpots", 85);
      await exactDone(env, 4);
      await sleep(60);
      expect(env.view() === "mask" && env.pictureName() === env.exacts()[3].picture, "...and with the mask on the mask stays, got " + env.view());
    });

  await scenario("a new result leaves 'До': 'До / Після' pressed while the first bar is running - the window still opens on the cleaned photo; 'Маска' pressed there stays", { startDelay: 500, detail: false },
    async (env, expect) => {
      env.click("btnRun");
      await sleep(150);
      expect(env.state("sessState.open") === true && !env.state("sessState.id"), "the first scan is running");
      env.click("dlgBtnBeforeAfter");
      expect(env.state("sessState.view") === "original", "(the button is taken while the scan runs)");
      await env.waitFor(() => !!env.state("sessState.id"), 3000);
      await sleep(60);
      expect(env.view() === "result" && !beforeLit(env) && env.modeBadge() === "ПІСЛЯ · чисте фото", `the first bar ends on the cleaned photo: ${env.view()} / '${env.modeBadge()}'`);
      env.click("dlgBtnCancel");
      await env.waitFor(() => env.state("isBusy") === false, 3000);
      await sleep(100);
      env.click("btnRun");                                     // the next photo: "Маска" pressed during its scan
      await sleep(150);
      env.click("dlgBtnMask");
      await env.waitFor(() => env.of("/session/start").length === 2 && !!env.state("sessState.id"), 3000);
      await sleep(60);
      expect(env.view() === "mask" && env.modeBadge().includes("МАСКА"), "the mask that was asked for during the scan is shown, got " + env.view());
    });

  const failed = results.filter((r) => r.problems.length);
  if (!results.length) {
    console.log("plugin preview: no scenario has that text in its name");
    process.exit(1);
  }
  console.log(failed.length
    ? `plugin preview: ${failed.length} of ${results.length} scenarios FAILED`
    : `plugin preview: ${results.length} scenarios pass (the fast window; drag -> nothing; release -> one light refresh; Apply carries the settings; views, presets, automatic preset, remembered press, smoke notes, steps back and forward, preset reset, backup, one mode, soft and hard brush edge, the exact picture by itself, strokes on the cleaned photo, zoom keys, right-button drag, the hair slider, the keyboard of the window, depth, a new result leaves 'До')`);
  process.exit(failed.length ? 1 : 0);
}

main().catch((err) => {
  console.log("plugin preview: crashed: " + (err && err.stack ? err.stack : err));
  process.exit(1);
});
