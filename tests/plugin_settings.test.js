// Runs the real setIdleUnloadSec / buildSettingsSnapshot / applySettingsSnapshot / applyPresetDefaultMoves of the
// plugin (main.js) in a stub environment and checks:
//   - the move of the idle-unload default from 30 s to 2 minutes;
//   - that the settings added in 4.3.0 (automatic preset; the AUTO button of the fractions as the user left it and
//     as the active preset made it) are read from old and new files and written back;
//   - the one-time moves of changed preset defaults (4.4.0: "Циклорама" 0 -> 65 in four built-in presets; 4.5.0:
//     smoke protection off except in "Зйомка з димом", "Темний ключ" with dust 92 -> 80 and "Циклорама" 0 -> 65):
//     made once, only where the stored value is still the former default, never in the user's own presets;
//   - the built-in presets added by a new version (4.5.0: three dark presets by framing) land under the preset
//     they follow, once, and never come back after the user deleted them;
//   - the automatic preset knows the dark framings;
//   - 4.7.0: the edge of the brush and the eraser (soft unless a file says otherwise) is read and written back; the
//     speed mode of an older file is not read - the file written back names the one mode that is left;
//   - 4.9.0: the slider of the single hairs ("strayHair") is read, applied and part of what makes the preview out
//     of date; a preset that does not name it - every built-in one - leaves the tool off.
//   node tests/plugin_settings.test.js
const fs = require("fs");
const path = require("path");
// (CV_PLUGIN_DIR points the test at another copy of the plugin - tests/try_defects.py proves with it that the
// test notices a broken one)
const PLUGIN_DIR = process.env.CV_PLUGIN_DIR || path.join(__dirname, "..", "CleanVinylPro2", "uxp-plugin");
const src = fs.readFileSync(path.join(PLUGIN_DIR, "main.js"), "utf8");

function grab(name) {
  const start = src.indexOf("function " + name + "(");
  if (start < 0) throw new Error("function not found in main.js: " + name);
  let depth = 0;
  for (let k = src.indexOf("{", start); k < src.length; k++) {
    if (src[k] === "{") depth++;
    else if (src[k] === "}" && --depth === 0) return src.slice(start, k + 1);
  }
  throw new Error("unbalanced braces in " + name);
}

const consts = src.match(
  /const DEFAULT_IDLE_UNLOAD_SEC = .*;\nconst LEGACY_IDLE_UNLOAD_SEC = .*;.*\nconst SETTINGS_SCHEMA_VERSION = .*;\nlet idleUnloadSec = .*;\nlet settingsMigrated = .*;/
);
if (!consts) throw new Error("idle-unload constants block not found in main.js");

const code = `
${consts[0]}
const speedMode = "quality";
let activePresetId = "std", makeMaskDefault = false, fracAuto = true, fracAutoUser = true, autoPreset = true;
let deletedDefaultIds = [], knownDefaultIds = [], presetsList = [], appliedPresetMoves = [];
const sessState = { brushSize: 24, brushSoft: true };
let detailPreview = false;
let mixEnabled = false;
const sliders = { gSlMix: 50 };
function getSliderVal(id) { return sliders[id]; }
function setSliderVal(id, v) { sliders[id] = Math.max(0, Math.min(100, Math.round(Number(v) || 0))); return sliders[id]; }
function updateSliderVisuals() {}
function sayInWindow() {}
function updateRecomputeButton() {}
function scheduleExactPreview() {}
function cancelExactTimer() {}
function stopBackgroundRun() {}
function updatePreviewBadge() {}
function updateModeBadge() {}
const pills = [30, 120, 300, 0].map((sec) => ({ dataset: { sec: String(sec) }, active: sec === 120 }));
pills.forEach((p) => (p.classList = { toggle: (cls, on) => (p.active = on) }));
function el(id) { return id === "gIdlePills" ? { querySelectorAll: () => pills } : null; }
function scheduleSaveSettings() {}
function readCurrentConfig() { return {}; }
function applyConfig() {}
${grab("setIdleUnloadSec")}
${grab("setAutoPreset")}
${grab("setDetailPreview")}
${grab("updateBrushEdgeUI")}
${grab("setBrushSoft")}
${grab("buildSettingsSnapshot")}
${grab("applySettingsSnapshot")}
module.exports = function run(snapshot) {
  idleUnloadSec = DEFAULT_IDLE_UNLOAD_SEC;
  settingsMigrated = false;
  fracAuto = fracAutoUser = autoPreset = true;
  detailPreview = false;
  mixEnabled = false;
  sliders.gSlMix = 50;
  sessState.brushSoft = true;
  pills.forEach((p) => (p.active = Number(p.dataset.sec) === 120));
  applySettingsSnapshot(snapshot);
  return {
    sec: idleUnloadSec,
    migrated: settingsMigrated,
    activePill: pills.filter((p) => p.active).map((p) => Number(p.dataset.sec)),
    saved: buildSettingsSnapshot()
  };
};
`;
const mod = { exports: null };
new Function("module", code)(mod);
const run = mod.exports;

const cases = [
  ["nothing saved yet", {}, 120, false],
  ["old settings, untouched default 30 s", { schemaVersion: 4, idleUnloadSec: 30 }, 120, true],
  ["very old settings without a schema, 30 s", { idleUnloadSec: 30 }, 120, true],
  ["old settings, user chose 5 min", { schemaVersion: 4, idleUnloadSec: 300 }, 300, false],
  ["old settings, user chose Keep", { schemaVersion: 4, idleUnloadSec: 0 }, 0, false],
  ["old settings, user chose 2 min", { schemaVersion: 4, idleUnloadSec: 120 }, 120, false],
  ["new settings, user chose 30 s again", { schemaVersion: 5, idleUnloadSec: 30 }, 30, false],
  ["new settings, 2 min", { schemaVersion: 5, idleUnloadSec: 120 }, 120, false],
  ["broken value", { schemaVersion: 5, idleUnloadSec: "abc" }, 120, false]
];

let failed = 0;
for (const [name, snapshot, expSec, expMigrated] of cases) {
  const r = run(snapshot);
  const ok =
    r.sec === expSec &&
    r.migrated === expMigrated &&
    r.saved.schemaVersion === 5 &&
    r.saved.idleUnloadSec === expSec &&
    JSON.stringify(r.activePill) === JSON.stringify([expSec]);
  if (!ok) {
    failed++;
    console.log("FAIL " + name + " -> " + JSON.stringify(r));
  }
}
// [name, saved file, expected in the file written back: autoPreset, fracAuto (the user's choice), fracAutoNow]
const newKeys = [
  ["a file of 4.2.0: the automatic preset is on, AUTO as saved", { schemaVersion: 5, fracAuto: true }, true, true, true],
  ["a file of 4.2.0 with AUTO switched off", { schemaVersion: 5, fracAuto: false }, true, false, false],
  ["automatic preset switched off", { schemaVersion: 5, autoPreset: false, fracAuto: true }, false, true, true],
  ["a preset that names its fractions was active", { schemaVersion: 5, fracAuto: true, fracAutoNow: false }, true, true, false],
  ["nothing saved yet", {}, true, true, true],
  ["broken values are ignored", { autoPreset: "no", fracAuto: 0, fracAutoNow: "x" }, true, true, true]
];
for (const [name, snapshot, expAutoPreset, expUser, expNow] of newKeys) {
  const r = run(snapshot);
  if (r.saved.autoPreset !== expAutoPreset || r.saved.fracAuto !== expUser || r.saved.fracAutoNow !== expNow) {
    failed++;
    console.log("FAIL " + name + " -> " + JSON.stringify(r.saved));
  }
}
// 4.10.0: "Детальний перегляд" is off unless the settings say that the user ticked it
// [name, saved file, expected in the file written back: detailPreview]
const detailKeys = [
  ["nothing saved yet: the fast window", {}, false],
  ["a file of 4.9.0 (no word of it): the fast window", { schemaVersion: 5, brushSoft: true, autoPreset: true }, false],
  ["the detailed preview was ticked", { schemaVersion: 5, detailPreview: true }, true],
  ["the detailed preview was unticked", { schemaVersion: 5, detailPreview: false }, false],
  ["a broken value is ignored", { schemaVersion: 5, detailPreview: "yes" }, false]
];
for (const [name, snapshot, expDetail] of detailKeys) {
  const r = run(snapshot);
  if (r.saved.detailPreview !== expDetail) {
    failed++;
    console.log("FAIL " + name + " -> " + JSON.stringify(r.saved));
  }
}
// 4.12.0: the mixer brush is the user's own switch, kept with the settings - off, at 50, unless they say otherwise
// [name, saved file, expected in the file written back: mixOn, mixStrength]
const mixKeys = [
  ["nothing saved yet: the mixer brush is off, at 50", {}, false, 50],
  ["a file of 4.11.0 (no word of it): off, at 50", { schemaVersion: 5, detailPreview: false, brushSoft: true }, false, 50],
  ["the mixer brush was ticked, at 70", { schemaVersion: 5, mixOn: true, mixStrength: 70 }, true, 70],
  ["it was unticked, the strength stays", { schemaVersion: 5, mixOn: false, mixStrength: 35 }, false, 35],
  ["a strength out of range is brought into it", { schemaVersion: 5, mixOn: true, mixStrength: 250 }, true, 100],
  ["broken values are ignored", { schemaVersion: 5, mixOn: "yes", mixStrength: "strong" }, false, 50]
];
for (const [name, snapshot, expOn, expStrength] of mixKeys) {
  const r = run(snapshot);
  if (r.saved.mixOn !== expOn || r.saved.mixStrength !== expStrength) {
    failed++;
    console.log("FAIL " + name + " -> " + JSON.stringify(r.saved));
  }
}
// [name, saved file, expected in the file written back: brushSoft, speedMode]
const brushKeys = [
  ["nothing saved yet: the soft edge", {}, true],
  ["a file of 4.6.0 (no word of the edge, fast mode): soft edge, the one mode", { schemaVersion: 5, speedMode: "fast", brushSize: 40 }, true],
  ["the hard edge was chosen", { schemaVersion: 5, speedMode: "quality", brushSoft: false }, false],
  ["the soft edge was chosen", { schemaVersion: 5, brushSoft: true }, true],
  ["a broken value is ignored", { schemaVersion: 5, brushSoft: "hard", speedMode: 7 }, true]
];
for (const [name, snapshot, expSoft] of brushKeys) {
  const r = run(snapshot);
  if (r.saved.brushSoft !== expSoft || r.saved.speedMode !== "quality") {
    failed++;
    console.log("FAIL " + name + " -> " + JSON.stringify(r.saved));
  }
}
// ------------------------------------------------------------------ one-time moves of changed preset defaults
const movesConst = src.match(/const PRESET_DEFAULT_MOVES = \[[\s\S]*?\n\];\n/);
if (!movesConst) throw new Error("PRESET_DEFAULT_MOVES not found in main.js");
const switchesConst = src.match(/const PRESET_SWITCHES = \{[\s\S]*?\n\};\n/);
if (!switchesConst) throw new Error("PRESET_SWITCHES not found in main.js");
const movesCode = `
${movesConst[0]}
${switchesConst[0]}
const speedMode = "quality";
let activePresetId = "std", makeMaskDefault = false, fracAuto = true, fracAutoUser = true, autoPreset = true;
let idleUnloadSec = 120, settingsMigrated = false, smokeEnabled = true;
const DEFAULT_IDLE_UNLOAD_SEC = 120, LEGACY_IDLE_UNLOAD_SEC = 30, SETTINGS_SCHEMA_VERSION = 5;
let deletedDefaultIds = [], knownDefaultIds = [], presetsList = [], appliedPresetMoves = [];
const sessState = { brushSize: 24 };
let detailPreview = false;
let mixEnabled = false;
function setDetailPreview(on) { detailPreview = !!on; }
function updateSliderVisuals() {}
const sliders = {};
function el() { return null; }
function getSliderVal(id) { return sliders[id] ?? 0; }
function setSliderVal(id, v) { sliders[id] = v; return v; }
function setIdleUnloadSec() {}
function readCurrentConfig() {
  return { cycCurve: getSliderVal("gSlCyc"), cycDepth: getSliderVal("gSlDepth"), spots: getSliderVal("gSlSpots"), smokeOn: smokeEnabled };
}
function applyConfig(cfg) {
  const c = cfg || {};
  setSliderVal("gSlCyc", c.cycCurve ?? 0);
  setSliderVal("gSlDepth", c.cycDepth ?? 0);
  setSliderVal("gSlSpots", c.spots ?? 75);
  smokeEnabled = c.smokeOn !== undefined ? !!c.smokeOn : false;
}
${grab("setAutoPreset")}
${grab("buildSettingsSnapshot")}
${grab("applySettingsSnapshot")}
${grab("applyPresetDefaultMoves")}
module.exports = function runMoves(presets, snapshot, times) {
  presetsList = JSON.parse(JSON.stringify(presets));
  appliedPresetMoves = [];
  activePresetId = "std";
  setSliderVal("gSlCyc", 0);
  setSliderVal("gSlDepth", 0);
  setSliderVal("gSlSpots", 75);
  smokeEnabled = true;
  if (snapshot) applySettingsSnapshot(snapshot);
  const changed = [];
  for (let i = 0; i < (times || 1); i++) changed.push(applyPresetDefaultMoves());
  const cyc = {}, spots = {}, smoke = {}, depth = {};
  presetsList.forEach((p) => { cyc[p.id] = p.cfg.cycCurve; spots[p.id] = p.cfg.spots; smoke[p.id] = p.cfg.smokeOn; depth[p.id] = p.cfg.cycDepth; });
  return { changed, cyc, spots, smoke, depth, slider: getSliderVal("gSlCyc"), depthSlider: getSliderVal("gSlDepth"), spotsSlider: getSliderVal("gSlSpots"),
           smokeNow: smokeEnabled, saved: buildSettingsSnapshot() };
};
`;
const modMoves = { exports: null };
new Function("module", movesCode)(modMoves);
const runMoves = modMoves.exports;

const defaultsNow = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "CleanVinylPro2", "server", "presets_defaults.json"), "utf8"));
// "Зйомка з димом" was a built-in preset up to 4.12.0 (taken out in 4.13.0: the owner asked for it). The PCs of
// earlier versions hold it, so the lists of those versions are built with it, the way 4.12.0 shipped it.
const SMOKE_PRESET_412 = {
  id: "smoke", name: "Зйомка з димом", color: "#56d8c9", builtin: true,
  cfg: { spots: 72, scuffs: 65, blur: 0, cycCurve: 0, feather: 60, seamOn: true, seam: 80, edge: 75, smokeOn: true, smoke: 95, grain: 90, shadow: true, removeStands: false, master: 100, fracFine: true, fracMed: true, fracLarge: true, dressSmooth: false, dressStrength: 40, cleanPasses: 1 }
};
const defaultsThen = (() => {
  const list = JSON.parse(JSON.stringify(defaultsNow));
  list.splice(list.findIndex((p) => p.id === "clean_stands"), 0, JSON.parse(JSON.stringify(SMOKE_PRESET_412)));
  return list;
})();
// The built-in presets as the PCs of earlier versions hold them
const IDS_440 = ["std", "medium_shot", "closeup", "wide_shot", "lowkey", "smoke", "clean_stands", "gentle"];
const FLOOR_440 = ["std", "medium_shot", "wide_shot", "clean_stands"];      // "Циклорама" 65 since 4.4.0
const SMOKE_OFF = IDS_440.filter((id) => id !== "smoke");                     // smoke protection off since 4.5.0
// (a preset saved before 4.14.0 has no word of "Глибина")
const noDepth = (cfg) => { const c = Object.assign({}, cfg); delete c.cycDepth; return c; };
const older = (cycOf) => defaultsThen.filter((p) => IDS_440.includes(p.id)).map((p) => Object.assign({}, p, {
  cfg: Object.assign(noDepth(p.cfg), { cycCurve: cycOf(p.id), smokeOn: true }, p.id === "lowkey" ? { spots: 92 } : {})
}));
const as430 = () => older(() => 0);
const as440 = () => older((id) => (FLOOR_440.includes(id) ? 65 : 0));
const mine = { id: "my_1", name: "Мій", builtin: false, cfg: { cycCurve: 0, spots: 92, smokeOn: true } };
const MOVES_4130 = ["cyc65", "smokeOff", "lowkeySpots80", "lowkeyCyc65"];
const ALL_MOVES = MOVES_4130.concat(["depth60"]);
const cycNow = Object.fromEntries(IDS_440.map((id) => [id, FLOOR_440.includes(id) || id === "lowkey" ? 65 : 0]));
const smokeNow = Object.fromEntries(IDS_440.map((id) => [id, id === "smoke"]));
const same = (got, want) => Object.keys(want).every((id) => got[id] === want[id]);
let moveCases = 0;
function moveCase(name, ok, r) {
  moveCases++;
  if (!ok) {
    failed++;
    console.log("FAIL " + name + " -> " + JSON.stringify(r));
  }
}
let r = runMoves(as430(), { schemaVersion: 5, activePresetId: "wide_shot", cfg: { cycCurve: 0, spots: 85, smokeOn: true } });
moveCase("presets of 4.3.0: every move is made, the controls of the active preset follow",
  r.changed[0] === true && same(r.cyc, cycNow) && same(r.smoke, smokeNow) && r.spots.lowkey === 80 && r.spots.wide_shot === 85 &&
  r.slider === 65 && r.smokeNow === false && ALL_MOVES.every((id) => r.saved.presetMoves.includes(id)), r);
r = runMoves(as430(), { schemaVersion: 5, activePresetId: "wide_shot", cfg: { cycCurve: 0 } }, 2);
moveCase("the moves are made once", r.changed[0] === true && r.changed[1] === false && same(r.cyc, cycNow) && same(r.smoke, smokeNow), r);
const edited = as430();
edited.find((p) => p.id === "std").cfg.cycCurve = 40;
r = runMoves(edited.concat([mine]), { schemaVersion: 5, activePresetId: "std", cfg: { cycCurve: 40, smokeOn: true } });
moveCase("a value the user chose stays; the user's own preset is never touched",
  r.cyc.std === 40 && r.cyc.wide_shot === 65 && r.slider === 40 &&
  r.cyc.my_1 === 0 && r.spots.my_1 === 92 && r.smoke.my_1 === true, r);
r = runMoves(as430(), { schemaVersion: 5, activePresetId: "smoke", cfg: { cycCurve: 0, spots: 72, smokeOn: true } });
moveCase("the controls are left alone when the active preset is not one a move names",
  r.slider === 0 && r.spotsSlider === 72 && r.smokeNow === true && r.cyc.smoke === 0 && r.smoke.smoke === true && r.cyc.std === 65, r);
r = runMoves(as430().concat([mine]), { schemaVersion: 5, activePresetId: "my_1", cfg: { cycCurve: 0, spots: 92, smokeOn: true } });
moveCase("...or is the user's own", r.slider === 0 && r.spotsSlider === 92 && r.smokeNow === true && r.cyc.my_1 === 0, r);
r = runMoves(as430(), { schemaVersion: 5, activePresetId: "std", cfg: { cycCurve: 0, smokeOn: true }, presetMoves: ALL_MOVES });
moveCase("settings that remember the moves: what the user set afterwards stays",
  r.changed[0] === false && r.cyc.std === 0 && r.cyc.wide_shot === 0 && r.slider === 0 && r.smoke.std === true && r.smokeNow === true && r.spots.lowkey === 92, r);
r = runMoves(defaultsNow, null);
moveCase("a fresh install: nothing to move, the moves are remembered",
  r.cyc.std === 65 && r.cyc.lowkey === 65 && r.cyc.closeup === 0 && r.smoke.std === false && r.smoke.smoke === undefined && r.spots.lowkey === 80 &&
  ALL_MOVES.every((id) => r.saved.presetMoves.includes(id)), r);
r = runMoves(as430(), { schemaVersion: 5, presetMoves: "broken", activePresetId: "std", cfg: { cycCurve: 0 } });
moveCase("a broken list in the file counts as no list", r.changed[0] === true && r.cyc.std === 65, r);

// 4.4.0 -> 4.5.0: the PC remembers the move of 4.4.0 and holds its presets
const back0 = as440();
back0.find((p) => p.id === "std").cfg.cycCurve = 0;   // "Циклорама" put back to 0 by the user after 4.4.0
r = runMoves(back0.concat([mine]), { schemaVersion: 5, activePresetId: "lowkey", cfg: { cycCurve: 0, spots: 92, smokeOn: true }, presetMoves: ["cyc65"] });
moveCase("presets of 4.4.0: smoke off everywhere but in the smoke preset, the dark preset gets dust 80 and the corner tool",
  r.changed[0] === true && same(r.smoke, smokeNow) && r.spots.lowkey === 80 && r.cyc.lowkey === 65 &&
  r.cyc.std === 0 && r.cyc.wide_shot === 65 && r.smoke.my_1 === true && r.spots.my_1 === 92, r);
moveCase("...and the controls of the active dark preset follow all three", r.spotsSlider === 80 && r.slider === 65 && r.smokeNow === false, r);
const tuned = as440();
Object.assign(tuned.find((p) => p.id === "lowkey").cfg, { spots: 85, cycCurve: 30 });
tuned.find((p) => p.id === "closeup").cfg.smokeOn = false;   // already switched off by the user
r = runMoves(tuned, { schemaVersion: 5, activePresetId: "lowkey", cfg: { cycCurve: 30, spots: 70, smokeOn: false }, presetMoves: ["cyc65"] });
moveCase("values the user chose in the dark preset stay, on the controls too",
  r.spots.lowkey === 85 && r.cyc.lowkey === 30 && r.spotsSlider === 70 && r.slider === 30 && r.smokeNow === false && r.smoke.closeup === false && r.smoke.lowkey === false, r);
r = runMoves(as440(), { schemaVersion: 5, activePresetId: "std", cfg: { cycCurve: 65, spots: 75, smokeOn: true }, presetMoves: ["cyc65"] }, 2);
moveCase("the smoke switch of the active preset goes off once; switched on again by the user it stays on",
  r.changed[0] === true && r.changed[1] === false && r.smokeNow === false && r.slider === 65, r);

// 4.13.0 -> 4.14.0: "Глибина" (the wider cove of the corner tool) is 60 in the light presets with a floor
const LIGHT_FLOOR = ["std", "medium_shot", "wide_shot", "clean_stands"];
const as4130 = () => defaultsNow.map((p) => Object.assign({}, p, { cfg: noDepth(p.cfg) }));
const depthNow = Object.fromEntries(defaultsNow.map((p) => [p.id, LIGHT_FLOOR.includes(p.id) ? 60 : undefined]));
r = runMoves(as4130().concat([mine]), { schemaVersion: 5, activePresetId: "wide_shot", cfg: { cycCurve: 65, spots: 85, smokeOn: false }, presetMoves: MOVES_4130 }, 2);
moveCase("presets of 4.13.0: the light presets with a floor get depth 60, the dark and the close ones and the user's own nothing; once",
  r.changed[0] === true && r.changed[1] === false && same(r.depth, depthNow) && r.depth.my_1 === undefined && r.saved.presetMoves.includes("depth60"), r);
moveCase("...and the slider of the active light preset follows; nothing else of it moves", r.depthSlider === 60 && r.slider === 65 && r.spotsSlider === 85 && r.smokeNow === false, r);
r = runMoves(as4130(), { schemaVersion: 5, activePresetId: "lowkey", cfg: { cycCurve: 65, spots: 80, smokeOn: false }, presetMoves: MOVES_4130 });
moveCase("the slider of an active dark preset stays at 0", r.depthSlider === 0 && r.depth.lowkey === undefined && r.depth.std === 60, r);
const deep = as4130();
deep.find((p) => p.id === "std").cfg.cycDepth = 25;
r = runMoves(deep, { schemaVersion: 5, activePresetId: "std", cfg: { cycCurve: 65, cycDepth: 25 }, presetMoves: MOVES_4130 });
moveCase("a depth the user chose stays, in the preset and on the slider", r.depth.std === 25 && r.depthSlider === 25 && r.depth.wide_shot === 60, r);
r = runMoves(defaultsNow, { schemaVersion: 5, activePresetId: "std", cfg: { cycCurve: 65, cycDepth: 0 }, presetMoves: ALL_MOVES });
moveCase("depth put back to 0 by the user after 4.14.0 stays at 0", r.changed[0] === false && r.depthSlider === 0, r);
moveCase("presets_defaults.json: exactly the light presets with a floor carry depth 60, every other preset 0",
  defaultsNow.every((p) => p.cfg.cycDepth === (LIGHT_FLOOR.includes(p.id) ? 60 : 0)), defaultsNow.map((p) => [p.id, p.cfg.cycDepth]));

const FLOOR_NOW = ["std", "medium_shot", "wide_shot", "clean_stands", "lowkey", "lowkey_medium", "lowkey_wide"];
moveCase("presets_defaults.json: exactly the presets with a floor carry \"Циклорама\" 65",
  defaultsNow.every((p) => p.cfg.cycCurve === (FLOOR_NOW.includes(p.id) ? 65 : 0)), defaultsNow.map((p) => [p.id, p.cfg.cycCurve]));
moveCase("presets_defaults.json: smoke protection is off in every preset, and the smoke preset is gone (4.13.0)",
  defaultsNow.length === 10 && defaultsNow.every((p) => p.cfg.smokeOn === false && p.id !== "smoke" && p.name !== "Зйомка з димом"),
  defaultsNow.map((p) => [p.id, p.cfg.smokeOn]));
moveCase("every move names presets that exist, a key they have, and leads to the value the preset ships with", (() => {
  const moves = new Function(movesConst[0] + "return PRESET_DEFAULT_MOVES;")();
  return moves.length === ALL_MOVES.length && moves.every((m) => ALL_MOVES.includes(m.id) && m.presets.every((id) => {
    const p = defaultsNow.find((x) => x.id === id);
    return p && p.cfg[m.key] === m.to && typeof m.from === typeof m.to && m.from !== m.to;
  }));
})(), null);

// The built-in presets exist twice: in the plugin (DEFAULT_PRESETS, used before the server answers) and on the
// server (presets_defaults.json). They must say the same.
const inPlugin = src.match(/const DEFAULT_PRESETS = \[[\s\S]*?\n\];\n/);
if (!inPlugin) throw new Error("DEFAULT_PRESETS not found in main.js");
const pluginPresets = new Function(inPlugin[0] + "return DEFAULT_PRESETS;")();
const flat = (list) => list.map((p) => [p.id, p.name, p.color, !!p.builtin, Object.keys(p.cfg).sort().map((k) => [k, p.cfg[k]])]);
const differ = [];
flat(pluginPresets).forEach((row, i) => {
  if (JSON.stringify(row) !== JSON.stringify(flat(defaultsNow)[i])) differ.push(row[0]);
});
moveCase("the built-in presets of the plugin and of the server are the same",
  pluginPresets.length === defaultsNow.length && differ.length === 0, { plugin: pluginPresets.length, server: defaultsNow.length, differ });

// ------------------------------------------------------------------ built-in presets added by a new version
const DARK_NEW = ["lowkey_medium", "lowkey_close", "lowkey_wide"];
const addCode = `
${inPlugin[0]}
let presetsList = [], deletedDefaultIds = [], knownDefaultIds = [], hasLocalPresets = true;
${grab("appendNewDefaultPresets")}
module.exports = function runAppend(presets, known, deleted, times) {
  presetsList = JSON.parse(JSON.stringify(presets));
  knownDefaultIds = known.slice();
  deletedDefaultIds = deleted.slice();
  const added = [];
  for (let i = 0; i < (times || 1); i++) added.push(appendNewDefaultPresets());
  return { added, ids: presetsList.map((p) => p.id), known: knownDefaultIds.slice(), list: presetsList };
};
`;
const modAdd = { exports: null };
new Function("module", addCode)(modAdd);
const runAppend = modAdd.exports;
const order = (ids) => ids.map((id) => as440().find((p) => p.id === id) || mine);
// (a PC that came from the first versions: the three framing presets were added at the end of its list in 4.3.0)
const PC_ORDER = ["my_1", "std", "lowkey", "smoke", "clean_stands", "gentle", "medium_shot", "closeup", "wide_shot"];
r = runAppend(order(PC_ORDER), IDS_440, [], 2);
moveCase("the three dark presets by framing land right under \"Темний ключ\", once",
  r.added[0] === true && r.added[1] === false &&
  r.ids.join() === ["my_1", "std", "lowkey"].concat(DARK_NEW, ["smoke", "clean_stands", "gentle", "medium_shot", "closeup", "wide_shot"]).join() &&
  DARK_NEW.every((id) => r.known.includes(id)), r.ids);
moveCase("...with the values they ship with",
  DARK_NEW.every((id) => JSON.stringify(flat([r.list.find((p) => p.id === id)])) === JSON.stringify(flat([defaultsNow.find((p) => p.id === id)]))), null);
r = runAppend(order(IDS_440.filter((id) => id !== "lowkey")), IDS_440, ["lowkey"]);
moveCase("\"Темний ключ\" deleted by the user: the new ones go under the built-in preset before it, the deleted one stays deleted",
  r.ids.join() === ["std", "medium_shot", "closeup", "wide_shot"].concat(DARK_NEW, ["smoke", "clean_stands", "gentle"]).join(), r.ids);
r = runAppend([mine], IDS_440, IDS_440);
moveCase("no built-in preset left in the list: the new ones go to its end", r.ids.join() === ["my_1"].concat(DARK_NEW).join(), r.ids);
r = runAppend(order(IDS_440), IDS_440.concat(DARK_NEW), ["lowkey_close", "lowkey_medium", "lowkey_wide"]);
moveCase("dark presets deleted by the user do not come back", r.added[0] === false && r.ids.join() === IDS_440.join(), r.ids);

// ------------------------------------------------------------------ a built-in preset that no longer exists (4.13.0)
const retiredConst = src.match(/const RETIRED_PRESET_IDS = \[[^\]]*\];\n/);
if (!retiredConst) throw new Error("RETIRED_PRESET_IDS not found in main.js");
const retireCode = `
${inPlugin[0]}
${retiredConst[0]}
let presetsList = [], activePresetId = "std";
const applied = [];
function applyConfig(cfg) { applied.push(cfg); }
${grab("dropRetiredPresets")}
module.exports = function runRetire(presets, active, times) {
  presetsList = JSON.parse(JSON.stringify(presets));
  activePresetId = active;
  applied.length = 0;
  const changed = [];
  for (let i = 0; i < (times || 1); i++) changed.push(dropRetiredPresets());
  return { changed, ids: presetsList.map((p) => p.id), active: activePresetId, applied: applied.slice(), list: presetsList };
};
`;
const modRetire = { exports: null };
new Function("module", retireCode)(modRetire);
const runRetire = modRetire.exports;
const ownSmoke = { id: "usr_1700000000000", name: "Зйомка з димом", builtin: false, cfg: { cycCurve: 0, spots: 70, smokeOn: true, smoke: 95 } };
const pc412 = defaultsThen.concat([mine, ownSmoke]);
r = runRetire(pc412, "wide_shot", 2);
moveCase("a PC of 4.12.0: the built-in smoke preset leaves the list, once; every other preset stays where it was",
  r.changed[0] === true && r.changed[1] === false && !r.ids.includes("smoke") &&
  r.ids.join() === pc412.map((p) => p.id).filter((id) => id !== "smoke").join(), r);
moveCase("...the user's own preset of the same name stays, and so do the active preset and the controls",
  r.ids.includes(ownSmoke.id) && r.ids.includes("my_1") && r.active === "wide_shot" && r.applied.length === 0, r);
r = runRetire(pc412, "smoke");
moveCase("the smoke preset was the active one: the first preset of the list takes its place, with its values on the controls",
  r.changed[0] === true && r.active === "std" && r.applied.length === 1 && JSON.stringify(r.applied[0]) === JSON.stringify(r.list[0].cfg) &&
  r.list[0].cfg.smokeOn === false && r.list[0].cfg.cycCurve === 65, r);
r = runRetire(defaultsNow.concat([mine]), "my_1");
moveCase("a list without it: nothing changes", r.changed[0] === false && r.ids.length === 11 && r.active === "my_1" && r.applied.length === 0, r);
r = runRetire([SMOKE_PRESET_412], "smoke");
moveCase("a list of nothing but the smoke preset: the built-in presets of this version take its place",
  r.changed[0] === true && r.ids.join() === defaultsNow.map((p) => p.id).join() && r.active === "std", r);

// ------------------------------------------------------------------ the automatic preset and the defaults of a preset
const sceneConst = src.match(/const AUTO_PRESET_BY_SCENE = \{[\s\S]*?\n\};\n/);
if (!sceneConst) throw new Error("AUTO_PRESET_BY_SCENE not found in main.js");
const sceneCode = `
${sceneConst[0]}
let presetsList = [];
let mixEnabled = false;
function presetRequestParams(p) { return Object.assign({}, p.cfg); }
function clampSliderVal(id, v) { return v; }
function getSliderVal(id) { return id === "gSlMix" ? 50 : 0; }
${grab("buildScenePresets")}
${grab("normalizedPresetConfig")}
module.exports = { scene: (presets) => { presetsList = presets; return buildScenePresets(); }, norm: normalizedPresetConfig, map: AUTO_PRESET_BY_SCENE };
`;
const modScene = { exports: null };
new Function("module", sceneCode)(modScene);
const sceneApi = modScene.exports;
const DARK_KEYS = { dark_close: "lowkey_close", dark_medium: "lowkey_medium", dark_wide: "lowkey_wide", dark: "lowkey" };
let sp = sceneApi.scene(defaultsNow);
moveCase("the automatic preset: a dark backdrop has its own preset for every framing, a light one as before",
  sp && Object.keys(sp.ids).length === 8 && same(sp.ids, Object.assign({ close: "closeup", medium: "medium_shot", wide: "wide_shot", default: "std" }, DARK_KEYS)) &&
  sp.params.dark_wide.cycCurve === 65 && sp.params.dark_close.seamOn === false, sp && sp.ids);
sp = sceneApi.scene(defaultsNow.filter((p) => p.id !== "lowkey_wide"));
moveCase("...a deleted dark preset is simply not offered (the server then takes the general dark one)",
  sp && !("dark_wide" in sp.ids) && sp.ids.dark === "lowkey" && Object.keys(sp.ids).length === 7, sp && sp.ids);
moveCase("a preset that does not say whether smoke is protected: it is not", sceneApi.norm({}).smokeOn === false &&
  sceneApi.norm({ smokeOn: true }).smokeOn === true && sceneApi.norm({ smokeOn: false }).smokeOn === false, sceneApi.norm({}));

// ------------------------------------------------------------------ 4.9.0: the slider of the single hairs
const sliderTables = src.match(/const ALL_SLIDER_IDS = \[[\s\S]*?\n\];\nconst SLIDER_VAL_MAP = \{[\s\S]*?\n\};\nconst SLIDER_MAX_MAP = .*;\nconst sliderState = \{[\s\S]*?\n\};\n/);
if (!sliderTables) throw new Error("the slider tables were not found in main.js");
const hairCode = `
${sliderTables[0]}
const sliderDisabled = {};
const badges = {};
let seamEnabled = true, smokeEnabled = false, dressSmoothEnabled = false, fracFine = true, fracMed = true, fracLarge = true, cleanPasses = 1;
let mixEnabled = false;
const speedMode = "quality";
function el(id) { return /^(gVal|dlgVal)/.test(id) ? (badges[id] = badges[id] || { textContent: "" }) : null; }
function updateFractionButtonsUI() {}
${grab("getSliderMax")}
${grab("getSliderVal")}
${grab("clampSliderVal")}
${grab("setSliderVal")}
${grab("setSliderDisabled")}
${grab("readCurrentConfig")}
${grab("setCleanPassesUI")}
${grab("normalizedPresetConfig")}
${grab("applyConfig")}
${grab("updateSliderVisuals")}
${grab("previewSettingsSignature")}
module.exports = {
  ids: ALL_SLIDER_IDS, map: SLIDER_VAL_MAP, state: sliderState, read: readCurrentConfig, norm: normalizedPresetConfig, apply: applyConfig,
  sig: previewSettingsSignature, badge: (id) => (badges[id] ? badges[id].textContent : null),
  set: (id, v) => { setSliderVal(id, v); updateSliderVisuals(); },
  mix: (on) => { mixEnabled = !!on; updateSliderVisuals(); }
};
`;
const modHair = { exports: null };
new Function("module", hairCode)(modHair);
const hair = modHair.exports;
moveCase("the hair slider is one of the sliders: listed, with its own value badge, at 0 until it is moved, sent as 'strayHair'",
  hair.ids.includes("gSlHair") && hair.map.gSlHair === "gValHair" && hair.state.gSlHair === 0 && hair.read().strayHair === 0,
  { ids: hair.ids, read: hair.read().strayHair });
moveCase("a preset that does not name the hair slider leaves the tool off; one that does gives its value, kept within 0..100",
  hair.norm({}).strayHair === 0 && hair.norm({ strayHair: 55 }).strayHair === 55 && hair.norm({ strayHair: 180 }).strayHair === 100 &&
  hair.norm({ strayHair: -3 }).strayHair === 0 && hair.norm({ strayHair: "x" }).strayHair === 0, hair.norm({ strayHair: 180 }));
hair.apply({ strayHair: 40 });
const hairAt40 = { read: hair.read().strayHair, badge: hair.badge("gValHair") };
hair.apply({});
moveCase("a preset puts its value on the hair slider ('40%'); a preset without one puts it back to 0 ('Вимк.')",
  hairAt40.read === 40 && hairAt40.badge === "40%" && hair.read().strayHair === 0 && hair.badge("gValHair") === "Вимк.",
  { at40: hairAt40, after: hair.read().strayHair, badge: hair.badge("gValHair") });
const sigHair0 = hair.sig();
hair.set("gSlHair", 30);
const sigHair30 = hair.sig();
hair.set("gSlHair", 0);
moveCase("moving the hair slider makes the preview out of date; back at its value it is up to date again",
  sigHair0 !== sigHair30 && hair.sig() === sigHair0, { sigHair0, sigHair30 });
moveCase("every built-in preset leaves the hair tool off (in the plugin and on the server)",
  defaultsNow.every((p) => hair.norm(p.cfg).strayHair === 0) && pluginPresets.every((p) => hair.norm(p.cfg).strayHair === 0), null);

// 4.12.0: the mixer brush - a slider with a switch; the strength counts only while the switch is on
const sigMixOff = hair.sig();
hair.set("gSlMix", 80);
moveCase("the mixer brush switched off: 'Вимк.', and its slider does not make the preview out of date",
  hair.badge("gValMix") === "Вимк." && hair.sig() === sigMixOff && hair.read().mixOn === false && hair.read().mix === 80, { badge: hair.badge("gValMix") });
hair.mix(true);
const sigMix80 = hair.sig();
hair.set("gSlMix", 40);
moveCase("switched on: the value is shown, the switch and the strength both make the preview out of date",
  hair.badge("gValMix") === "40%" && sigMix80 !== sigMixOff && hair.sig() !== sigMix80 && hair.read().mixOn === true && hair.read().mix === 40, { badge: hair.badge("gValMix") });
moveCase("a preset says nothing of the mixer brush: what it would send carries the user's own switch, and applying it leaves the switch alone",
  defaultsNow.every((p) => p.cfg.mixOn === undefined && p.cfg.mix === undefined && hair.norm(p.cfg).mixOn === true && hair.norm(p.cfg).mix === 40) &&
  (hair.apply(defaultsNow[0].cfg), hair.read().mixOn === true && hair.read().mix === 40), null);
hair.mix(false);

const total = cases.length + newKeys.length + detailKeys.length + mixKeys.length + brushKeys.length + moveCases;
console.log(failed ? `plugin settings migration: ${failed} of ${total} cases FAILED` : `plugin settings migration: ${total} cases pass`);
process.exit(failed ? 1 : 0);
