// Runs the real setIdleUnloadSec / buildSettingsSnapshot / applySettingsSnapshot of the plugin (main.js)
// in a stub environment and checks the move of the idle-unload default from 30 s to 2 minutes, and that the
// settings added in 4.3.0 (automatic preset; the AUTO button of the fractions as the user left it and as the
// active preset made it) are read from old and new files and written back:
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
let deletedDefaultIds = [], knownDefaultIds = [], presetsList = [];
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
const total = cases.length + newKeys.length;
console.log(failed ? `plugin settings migration: ${failed} of ${total} cases FAILED` : `plugin settings migration: ${total} cases pass`);
process.exit(failed ? 1 : 0);
