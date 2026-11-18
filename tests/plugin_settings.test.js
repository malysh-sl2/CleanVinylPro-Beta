// Runs the real setIdleUnloadSec / buildSettingsSnapshot / applySettingsSnapshot / applyPresetDefaultMoves of the
// plugin (main.js) in a stub environment and checks:
//   - the move of the idle-unload default from 30 s to 2 minutes;
//   - that the settings added in 4.3.0 (automatic preset; the AUTO button of the fractions as the user left it and
//     as the active preset made it) are read from old and new files and written back;
//   - the one-time moves of changed preset defaults (4.4.0: "Циклорама" 0 -> 65 in four built-in presets): made
//     once, only where the stored value is still the former default, never in the user's own presets.
//   node tests/plugin_settings.test.js
const fs = require("fs");
const path = require("path");
const src = fs.readFileSync(path.join(__dirname, "..", "CleanVinylPro2", "uxp-plugin", "main.js"), "utf8");

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
let activePresetId = "std", speedMode = "fast", makeMaskDefault = false, fracAuto = true, fracAutoUser = true, autoPreset = true;
let deletedDefaultIds = [], knownDefaultIds = [], presetsList = [], appliedPresetMoves = [];
const sessState = { brushSize: 24 };
const pills = [30, 120, 300, 0].map((sec) => ({ dataset: { sec: String(sec) }, active: sec === 120 }));
pills.forEach((p) => (p.classList = { toggle: (cls, on) => (p.active = on) }));
function el(id) { return id === "gIdlePills" ? { querySelectorAll: () => pills } : null; }
function scheduleSaveSettings() {}
function readCurrentConfig() { return {}; }
function applyConfig() {}
${grab("setIdleUnloadSec")}
${grab("setAutoPreset")}
${grab("buildSettingsSnapshot")}
${grab("applySettingsSnapshot")}
module.exports = function run(snapshot) {
  idleUnloadSec = DEFAULT_IDLE_UNLOAD_SEC;
  settingsMigrated = false;
  fracAuto = fracAutoUser = autoPreset = true;
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
// ------------------------------------------------------------------ one-time moves of changed preset defaults
const movesConst = src.match(/const PRESET_DEFAULT_MOVES = \[[\s\S]*?\n\];\n/);
if (!movesConst) throw new Error("PRESET_DEFAULT_MOVES not found in main.js");
const movesCode = `
${movesConst[0]}
let activePresetId = "std", speedMode = "fast", makeMaskDefault = false, fracAuto = true, fracAutoUser = true, autoPreset = true;
let idleUnloadSec = 120, settingsMigrated = false;
const DEFAULT_IDLE_UNLOAD_SEC = 120, LEGACY_IDLE_UNLOAD_SEC = 30, SETTINGS_SCHEMA_VERSION = 5;
let deletedDefaultIds = [], knownDefaultIds = [], presetsList = [], appliedPresetMoves = [];
const sessState = { brushSize: 24 };
const sliders = {};
function el() { return null; }
function getSliderVal(id) { return sliders[id] ?? 0; }
function setSliderVal(id, v) { sliders[id] = v; return v; }
function setIdleUnloadSec() {}
function readCurrentConfig() { return { cycCurve: getSliderVal("gSlCyc") }; }
function applyConfig(cfg) { setSliderVal("gSlCyc", (cfg && cfg.cycCurve) ?? 0); }
${grab("setAutoPreset")}
${grab("buildSettingsSnapshot")}
${grab("applySettingsSnapshot")}
${grab("applyPresetDefaultMoves")}
module.exports = function runMoves(presets, snapshot, times) {
  presetsList = JSON.parse(JSON.stringify(presets));
  appliedPresetMoves = [];
  activePresetId = "std";
  setSliderVal("gSlCyc", 0);
  if (snapshot) applySettingsSnapshot(snapshot);
  const changed = [];
  for (let i = 0; i < (times || 1); i++) changed.push(applyPresetDefaultMoves());
  const cyc = {};
  presetsList.forEach((p) => (cyc[p.id] = p.cfg.cycCurve));
  return { changed, cyc, slider: getSliderVal("gSlCyc"), saved: buildSettingsSnapshot() };
};
`;
const modMoves = { exports: null };
new Function("module", movesCode)(modMoves);
const runMoves = modMoves.exports;

const defaultsNow = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "CleanVinylPro2", "server", "presets_defaults.json"), "utf8"));
const MOVED = ["std", "medium_shot", "wide_shot", "clean_stands"];
const as430 = () => defaultsNow.map((p) => Object.assign({}, p, { cfg: Object.assign({}, p.cfg, { cycCurve: 0 }) })); // the presets a 4.3.0 PC holds
const mine = { id: "my_1", name: "Мій", builtin: false, cfg: { cycCurve: 0 } };
const expectCyc = (r, want) => Object.keys(want).every((id) => r.cyc[id] === want[id]);
const allMoved = Object.fromEntries(defaultsNow.map((p) => [p.id, MOVED.includes(p.id) ? 65 : 0]));
let moveCases = 0;
function moveCase(name, ok, r) {
  moveCases++;
  if (!ok) {
    failed++;
    console.log("FAIL " + name + " -> " + JSON.stringify(r));
  }
}
let r = runMoves(as430(), { schemaVersion: 5, activePresetId: "wide_shot", cfg: { cycCurve: 0 } });
moveCase("presets of 4.3.0: the four presets with a floor get 65, the others stay, the slider of the active preset follows",
  r.changed[0] === true && expectCyc(r, allMoved) && r.slider === 65 && r.saved.presetMoves.includes("cyc65"), r);
r = runMoves(as430(), { schemaVersion: 5, activePresetId: "wide_shot", cfg: { cycCurve: 0 } }, 2);
moveCase("the move is made once", r.changed[0] === true && r.changed[1] === false && expectCyc(r, allMoved), r);
const edited = as430();
edited.find((p) => p.id === "std").cfg.cycCurve = 40;
r = runMoves(edited.concat([mine]), { schemaVersion: 5, activePresetId: "std", cfg: { cycCurve: 40 } });
moveCase("a value the user chose stays; the user's own preset is never touched",
  r.cyc.std === 40 && r.cyc.wide_shot === 65 && r.cyc.my_1 === 0 && r.slider === 40, r);
r = runMoves(as430(), { schemaVersion: 5, activePresetId: "lowkey", cfg: { cycCurve: 0 } });
moveCase("the slider is left alone when the active preset is not one of the four", r.slider === 0 && r.cyc.lowkey === 0 && r.cyc.std === 65, r);
r = runMoves(as430().concat([mine]), { schemaVersion: 5, activePresetId: "my_1", cfg: { cycCurve: 0 } });
moveCase("...or is the user's own", r.slider === 0 && r.cyc.my_1 === 0, r);
r = runMoves(as430(), { schemaVersion: 5, activePresetId: "std", cfg: { cycCurve: 0 }, presetMoves: ["cyc65"] });
moveCase("settings that remember the move: 0 set by the user afterwards stays 0",
  r.changed[0] === false && r.cyc.std === 0 && r.cyc.wide_shot === 0 && r.slider === 0, r);
r = runMoves(defaultsNow, null);
moveCase("a fresh install: nothing to move, the move is remembered",
  r.cyc.std === 65 && r.cyc.lowkey === 0 && r.saved.presetMoves.includes("cyc65"), r);
r = runMoves(as430(), { schemaVersion: 5, presetMoves: "broken", activePresetId: "std", cfg: { cycCurve: 0 } });
moveCase("a broken list in the file counts as no list", r.changed[0] === true && r.cyc.std === 65, r);
moveCase("presets_defaults.json: exactly the four presets carry 65", defaultsNow.every((p) => p.cfg.cycCurve === (MOVED.includes(p.id) ? 65 : 0)), defaultsNow.map((p) => [p.id, p.cfg.cycCurve]));

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

const total = cases.length + newKeys.length + moveCases;
console.log(failed ? `plugin settings migration: ${failed} of ${total} cases FAILED` : `plugin settings migration: ${total} cases pass`);
process.exit(failed ? 1 : 0);
