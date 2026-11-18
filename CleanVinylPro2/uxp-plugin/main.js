const { app, core, imaging, action, constants } = require("photoshop");
const uxp = require("uxp");
const uxpFs = uxp.storage.localFileSystem;
const uxpShell = uxp.shell;

const CANDIDATE_URLS = ["http://127.0.0.1:18746", "http://localhost:18746"];
// The same number as in manifest.json and server.py. A server of another version still answers (for example the
// previous one that was left running after an update) - the panel then says how to restart it.
const PLUGIN_VERSION = "4.3.0";
let SERVER_URL = CANDIDATE_URLS[0];

const DEFAULT_PRESETS = [
  {
    id: "std",
    name: "Студія (Стандарт)",
    color: "#4da3ff",
    builtin: true,
    cfg: { spots: 75, scuffs: 65, blur: 0, cycCurve: 0, feather: 60, seamOn: true, seam: 85, edge: 70, smokeOn: true, smoke: 80, grain: 90, shadow: true, removeStands: false, master: 100, fracFine: true, fracMed: true, fracLarge: true, dressSmooth: false, dressStrength: 45, cleanPasses: 1 }
  },
  {
    id: "medium_shot",
    name: "Середній план",
    color: "#59b5ff",
    builtin: true,
    cfg: { spots: 75, scuffs: 65, blur: 10, cycCurve: 0, feather: 65, seamOn: true, seam: 78, edge: 74, smokeOn: true, smoke: 80, grain: 92, shadow: true, removeStands: false, master: 100, fracFine: true, fracMed: true, fracLarge: true, dressSmooth: false, dressStrength: 45, cleanPasses: 1 }
  },
  {
    id: "closeup",
    name: "Ближній план",
    color: "#3bc9db",
    builtin: true,
    cfg: { spots: 62, scuffs: 48, blur: 18, cycCurve: 0, feather: 78, seamOn: false, seam: 0, edge: 84, smokeOn: true, smoke: 80, grain: 94, shadow: true, removeStands: false, master: 100, fracFine: true, fracMed: true, fracLarge: false, dressSmooth: false, dressStrength: 35, cleanPasses: 1 }
  },
  {
    id: "wide_shot",
    name: "Дальній план",
    color: "#7c8cff",
    builtin: true,
    cfg: { spots: 85, scuffs: 78, blur: 0, cycCurve: 0, feather: 55, seamOn: true, seam: 90, edge: 66, smokeOn: true, smoke: 80, grain: 90, shadow: true, removeStands: false, master: 100, fracFine: true, fracMed: true, fracLarge: true, dressSmooth: false, dressStrength: 45, cleanPasses: 1 }
  },
  {
    id: "lowkey",
    name: "Темний ключ",
    color: "#9d7cff",
    builtin: true,
    cfg: { spots: 92, scuffs: 55, blur: 0, cycCurve: 0, feather: 65, seamOn: true, seam: 90, edge: 78, smokeOn: true, smoke: 70, grain: 95, shadow: true, removeStands: false, master: 100, fracFine: true, fracMed: true, fracLarge: true, dressSmooth: false, dressStrength: 40, cleanPasses: 1 }
  },
  {
    id: "smoke",
    name: "Зйомка з димом",
    color: "#56d8c9",
    builtin: true,
    cfg: { spots: 72, scuffs: 65, blur: 0, cycCurve: 0, feather: 60, seamOn: true, seam: 80, edge: 75, smokeOn: true, smoke: 95, grain: 90, shadow: true, removeStands: false, master: 100, fracFine: true, fracMed: true, fracLarge: true, dressSmooth: false, dressStrength: 40, cleanPasses: 1 }
  },
  {
    id: "clean_stands",
    name: "Без стійок (AI)",
    color: "#f2a649",
    builtin: true,
    cfg: { spots: 78, scuffs: 70, blur: 0, cycCurve: 0, feather: 60, seamOn: true, seam: 85, edge: 72, smokeOn: true, smoke: 80, grain: 90, shadow: true, removeStands: true, master: 100, fracFine: true, fracMed: true, fracLarge: true, dressSmooth: false, dressStrength: 45, cleanPasses: 1 }
  },
  {
    id: "gentle",
    name: "Делікатний (точки)",
    color: "#e57399",
    builtin: true,
    cfg: { spots: 60, scuffs: 25, blur: 0, cycCurve: 0, feather: 65, seamOn: false, seam: 0, edge: 85, smokeOn: true, smoke: 85, grain: 95, shadow: true, removeStands: false, master: 90, fracFine: true, fracMed: false, fracLarge: false, dressSmooth: false, dressStrength: 35, cleanPasses: 1 }
  }
];

let presetsList = JSON.parse(JSON.stringify(DEFAULT_PRESETS));
let activePresetId = presetsList[0].id;
let presetsEditMode = false;
let seamEnabled = true;
let smokeEnabled = true;
let fracFine = true;
let fracMed = true;
let fracLarge = true;
let fracAuto = true;      // the AUTO button of the fractions as it is right now
let fracAutoUser = true;  // ...and as the user left it (a preset that names its fractions switches AUTO off for a while)
let autoPreset = true;    // pick the preset that suits the frame every time the big window opens
let dressSmoothEnabled = false;
let cleanPasses = 1;
let speedMode = "fast";
// How long the AI models stay in GPU memory after the last job. 2 minutes: long enough to retouch the
// result and come back for the next frame without paying for the model reload again.
const DEFAULT_IDLE_UNLOAD_SEC = 120;
const LEGACY_IDLE_UNLOAD_SEC = 30; // default of settings schema <= 4
const SETTINGS_SCHEMA_VERSION = 5;
let idleUnloadSec = DEFAULT_IDLE_UNLOAD_SEC;
let settingsMigrated = false;
let makeMaskDefault = false;
let deletedDefaultIds = [];
let knownDefaultIds = [];
let hasLocalPresets = false;
let hasLocalSettings = false;
let serverSyncedOnce = false;
let settingsSaveTimer = null;
let lastKnownInstallDir = "";

let serverOnline = false;
let serverLaunchPromise = null;
let isBusy = false;
let lastCreatedLayerId = null;
let lastDocId = null;
let compareShowingOriginal = false;

function setBtnDisabled(node, dis) {
  if (!node) return;
  const flag = !!dis;
  node.disabled = flag;
  node.setAttribute("aria-disabled", flag ? "true" : "false");
  if (node.classList) node.classList.toggle("is-disabled", flag);
}

// Active Interactive Dialog Session State
let sessState = {
  open: false,
  id: null,
  docId: null,
  bitDepth: 8,
  colorProfile: "",
  docW: 0,
  docH: 0,
  pw: 0,
  ph: 0,
  tool: "eraser", // default to Eraser on start so user can erase extra green immediately!
  brushSize: 28,
  // What the photo area shows: "result" - the cleaned photo (the window opens with it), "original" - the photo as
  // it was, "mask" - the cleaned photo under the red/green mask (green = will be cleaned). See setView().
  view: "result",
  blend: 100,
  peekingClean: false,
  peekingBlend: false,
  zoom: 1.0,
  fitZoom: 1.0,
  panX: 0,
  panY: 0,
  spaceDown: false,
  isPanning: false,
  isDrawing: false,
  dragStartX: 0,
  dragStartY: 0,
  panStartX: 0,
  panStartY: 0,
  lastDotX: -1,
  lastDotY: -1,
  strokePoints: [],
  scanAborted: false,
  isApplying: false,
  recomputing: false,
  pendingRecompute: false,
  pendingRecomputePreserve: true,
  pendingRecomputeQuick: false,
  previewTimer: null,      // the light refresh of the preview that waits for its moment
  previewBusy: false,      // a light refresh is running right now
  previewSyncedSig: "",    // the settings the preview on screen was made for
  previewForce: false,     // refresh even if the settings look the same (AUTO fractions were asked for again)
  quickUnsupported: false, // the running server is an older build that only knows the full recompute
  lastStats: null,
  maskShare: null,         // share of the frame that is green now (0..1), as the server last reported it
  presetNote: null,        // a preset was just clicked: say what it changed when the refresh comes back
  note: "",                // short message in the corner of the photo (which preset was picked and why)
  noteTimer: null
};
let pendingApplyPayload = null;

// The preview follows the sliders by itself: once, shortly after the last change, and never while a slider is
// still being dragged. That refresh is light (the server redraws only the preview). The full-size frame is
// computed one time - when "Застосувати" is pressed.
const PREVIEW_DELAY_SLIDER_MS = 450;
const PREVIEW_DELAY_CLICK_MS = 150;

// Custom Drag-Only Sliders
const ALL_SLIDER_IDS = [
  "dlgSlBlend",
  "gSlSpots", "gSlScuffs", "gSlBlur", "gSlCyc", "gSlFeather",
  "gSlSeam", "gSlEdge", "gSlSmoke", "gSlGrain",
  "gSlDress", "gSlTurbo"
];
const SLIDER_VAL_MAP = {
  dlgSlBlend: "dlgValBlend",
  gSlSpots: "gValSpots",
  gSlScuffs: "gValScuffs",
  gSlBlur: "gValBlur",
  gSlCyc: "gValCyc",
  gSlFeather: "gValFeather",
  gSlSeam: "gValSeam",
  gSlEdge: "gValEdge",
  gSlSmoke: "gValSmoke",
  gSlGrain: "gValGrain",
  gSlDress: "gValDress",
  gSlTurbo: "gValTurbo"
};
const SLIDER_MAX_MAP = { gSlTurbo: 200 };
const sliderState = {
  dlgSlBlend: 100,
  gSlSpots: 75,
  gSlScuffs: 65,
  gSlBlur: 0,
  gSlCyc: 0,
  gSlFeather: 60,
  gSlSeam: 85,
  gSlEdge: 70,
  gSlSmoke: 80,
  gSlGrain: 90,
  gSlDress: 45,
  gSlTurbo: 100
};
const sliderDisabled = {};
let activeDragSliderId = null;
let recomputeAbortCtrl = null;

const el = (id) => document.getElementById(id);

function delayMs(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function getSliderMax(id) {
  if (SLIDER_MAX_MAP[id]) return SLIDER_MAX_MAP[id];
  const n = el(id);
  if (n && n.dataset && n.dataset.max) {
    const v = Number(n.dataset.max);
    if (Number.isFinite(v) && v > 0) return v;
  }
  return 100;
}

function getSliderVal(id) {
  return sliderState[id] !== undefined ? sliderState[id] : 0;
}

function clampSliderVal(id, rawVal) {
  return Math.max(0, Math.min(getSliderMax(id), Math.round(Number(rawVal) || 0)));
}

function setSliderVal(id, rawVal) {
  const maxV = getSliderMax(id);
  const v = clampSliderVal(id, rawVal);
  sliderState[id] = v;
  const pct = (v / maxV) * 100;
  const node = el(id);
  if (node) {
    node.dataset.value = String(v);
    const fill = node.querySelector(".cv-slider-fill");
    const thumb = node.querySelector(".cv-slider-thumb");
    if (fill) fill.style.width = pct + "%";
    if (thumb) thumb.style.left = pct + "%";
  }
  return v;
}

function setSliderDisabled(id, disabled) {
  sliderDisabled[id] = !!disabled;
  const node = el(id);
  if (node) node.classList.toggle("disabled", !!disabled);
}

// ------------------------------------------------------------------
// Panel Status & Error UI
// ------------------------------------------------------------------
function setFooterStatus(msg, kind = "info") {
  const f = el("footerStatus");
  if (!f) return;
  if (!msg) {
    f.className = "footer-status";
    f.textContent = "";
    return;
  }
  f.textContent = msg;
  f.className = "footer-status visible " + kind;
}

function showBanner(msg, kind = "info") {
  const b = el("statusBanner");
  if (!b) return;
  el("statusBannerText").textContent = msg;
  b.className = "status-banner visible " + kind;
}

function hideBanner() {
  const b = el("statusBanner");
  if (b) b.className = "status-banner";
}

function showServerErrorCard(reasonText) {
  const card = el("serverErrorCard");
  if (!card) return;
  const pathStr = lastKnownInstallDir || "CleanVinylPro2 (папка програми)";
  const pathEl = el("errInstallPath");
  if (pathEl) pathEl.textContent = pathStr;
  if (reasonText) {
    const body = el("serverErrorBody");
    if (body) {
      body.innerHTML =
        `${reasonText}<br/>` +
        `<b>Що зробити:</b><br/>` +
        `1. Відкрийте папку: <span class="err-path">${escapeHtml(pathStr)}</span><br/>` +
        `2. Клацніть правою кнопкою по <b>start_gpu_server.bat</b> → <b>«Запуск від імені адміністратора»</b>.<br/>` +
        `<span class="err-note">(Якщо запускаєте вперше — спершу запустіть <b>install_windows.bat</b>, а потім <b>setup_ps_launch.bat</b> від імені адміністратора.)</span>`;
    }
  }
  card.classList.add("visible");
}

function hideServerErrorCard() {
  const card = el("serverErrorCard");
  if (card) card.classList.remove("visible");
}

function escapeHtml(s) {
  return String(s || "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" }[c]));
}

// ------------------------------------------------------------------
// Progress Tracking, Live Timer & Rotating Ukrainian Tips
// ------------------------------------------------------------------
const USER_GUIDE_TIPS = [
  "💡 Вікно відкривається одразу з чистим фото. Кнопка «До / Після» показує оригінал, ще раз — знову результат.",
  "💡 Кнопка «Маска» показує зеленим, що буде очищено. Гумка (E) стирає зайве зелене з одягу, взуття або тіней.",
  "💡 Пресет підбирається сам під кадр: темний фон, ближній, середній план чи повний зріст. Іншої думки — виберіть свій у списку.",
  "💡 Ctrl + Клік по іконці Пензля (B) заливає всю маску; Ctrl + Клік по Гумці (E) — повністю очищає маску.",
  "💡 Увімкніть іконку сукні зверху, щоб AI делікатно розгладив різкі складки на одязі без впливу на шкіру й волосся.",
  "💡 Натисніть квадратики фракцій знизу (Дрібна / Середня / Велика), щоб швидко вмикати або вимикати типи чистки.",
  "💡 Колесо миші масштабує фото, а Пробіл + мишка дає змогу плавно рухати кадр у наближенні.",
  "💡 Гарячі клавіші [ і ] миттєво зменшують або збільшують розмір пензля й гумки.",
  "💡 Поставте галочку «Make Mask» зверху, якщо хочете отримати у Photoshop редаговану маску шару.",
  "💡 Якщо на фоні є стійки, кабелі чи прилади — увімкніть їх видалення в налаштуваннях (шестигранник) або пресеті «Без стійок (AI)».",
  "💡 Режим «⚡ Швидкий» очищає кадр за кілька секунд; «✦ Якісний» використовує повний прохід LaMa для складних сцен.",
  "💡 Перегляд оновлюється сам, щойно відпустите повзунок. Повний розрахунок робиться один раз — коли натиснете «Застосувати»."
];

let tipCycleIndex = Math.floor(Math.random() * USER_GUIDE_TIPS.length);
let progressPollTimer = null;
let progressPollInFlight = false;
let progressPollToken = 0;
let modalClockTimer = null;
let modalClockStartMs = 0;
let opStartMs = 0;

function makeJobId() {
  return "cv_" + Date.now() + "_" + Math.floor(Math.random() * 100000);
}

function startModalTimerAndTip() {
  modalClockStartMs = Date.now();
  tipCycleIndex = (tipCycleIndex + 1) % USER_GUIDE_TIPS.length;
  const tipNode = el("dlgProgTip");
  if (tipNode) tipNode.textContent = USER_GUIDE_TIPS[tipCycleIndex];
  const timerNode = el("dlgProgTimer");
  if (timerNode) timerNode.textContent = "⏱ Час: 0.0 с";
  if (modalClockTimer) clearInterval(modalClockTimer);
  modalClockTimer = setInterval(() => {
    const tn = el("dlgProgTimer");
    if (tn && modalClockStartMs > 0) {
      tn.textContent = "⏱ Час: " + ((Date.now() - modalClockStartMs) / 1000).toFixed(1) + " с";
    }
  }, 100);
}

function stopModalTimer() {
  if (modalClockTimer) {
    clearInterval(modalClockTimer);
    modalClockTimer = null;
  }
}

function updateProgressUI(pct, stage, target = "auto") {
  const p = Math.max(0, Math.min(100, Math.round(Number(pct) || 0)));
  const useModal = target === "modal" || (target === "auto" && sessState.open);
  if (useModal) {
    const ov = el("dlgProgressOverlay");
    const wasHidden = ov && !ov.classList.contains("visible");
    if (ov) ov.classList.add("visible");
    if (wasHidden || !modalClockTimer) startModalTimerAndTip();
    if (el("dlgProgFill")) el("dlgProgFill").style.width = p + "%";
    if (el("dlgProgPct")) el("dlgProgPct").textContent = p + "%";
    if (el("dlgProgStage") && stage) el("dlgProgStage").textContent = stage;
  } else {
    const box = el("panelProgressBox");
    if (box) box.classList.add("visible");
    if (el("panelProgressFill")) el("panelProgressFill").style.width = p + "%";
    if (el("panelProgressPct")) {
      const sec = opStartMs > 0 ? ((Date.now() - opStartMs) / 1000).toFixed(1) + " с • " : "";
      el("panelProgressPct").textContent = `${sec}${p}%`;
    }
    if (el("panelProgressStage") && stage) el("panelProgressStage").textContent = stage;
  }
}

function hideProgressUI(target = "all") {
  if (target === "modal" || target === "all") {
    stopModalTimer();
    const ov = el("dlgProgressOverlay");
    if (ov) ov.classList.remove("visible");
  }
  if (target === "panel" || target === "all") {
    const box = el("panelProgressBox");
    if (box) box.classList.remove("visible");
  }
}

function stopProgressPolling() {
  progressPollToken++;
  if (progressPollTimer) {
    clearInterval(progressPollTimer);
    progressPollTimer = null;
  }
  progressPollInFlight = false;
}

function startProgressPolling(jobId, target = "auto") {
  stopProgressPolling();
  if (!jobId) return;
  const myToken = progressPollToken;
  const poll = async () => {
    if (progressPollInFlight || myToken !== progressPollToken) return;
    progressPollInFlight = true;
    try {
      const r = await fetch(`${SERVER_URL}/progress?job_id=${encodeURIComponent(jobId)}`);
      if (myToken !== progressPollToken) return;
      if (r.ok) {
        const d = await r.json();
        if (myToken !== progressPollToken) return;
        if (d && d.ok && typeof d.pct === "number") {
          updateProgressUI(d.pct, d.stage, target);
        }
      }
    } catch (_) {
    } finally {
      progressPollInFlight = false;
    }
  };
  progressPollTimer = setInterval(poll, 180);
  poll();
}

// ------------------------------------------------------------------
// Local + Server Presets, Settings & Install Path Persistence
// ------------------------------------------------------------------
function readCurrentConfig() {
  return {
    spots: getSliderVal("gSlSpots"),
    scuffs: getSliderVal("gSlScuffs"),
    blur: getSliderVal("gSlBlur"),
    cycCurve: getSliderVal("gSlCyc"),
    feather: getSliderVal("gSlFeather"),
    seamOn: seamEnabled,
    seam: getSliderVal("gSlSeam"),
    edge: getSliderVal("gSlEdge"),
    smokeOn: smokeEnabled,
    smoke: getSliderVal("gSlSmoke"),
    grain: getSliderVal("gSlGrain"),
    shadow: el("gChkShadow") ? el("gChkShadow").checked : true,
    removeStands: el("gChkRemoveStands") ? el("gChkRemoveStands").checked : false,
    master: getSliderVal("gSlTurbo"),
    fracFine,
    fracMed,
    fracLarge,
    dressSmooth: dressSmoothEnabled,
    dressStrength: getSliderVal("gSlDress"),
    cleanPasses,
    speedMode
  };
}

function setCleanPassesUI(n) {
  cleanPasses = Number(n) >= 2 ? 2 : 1;
  if (el("gPass1")) el("gPass1").classList.toggle("active", cleanPasses === 1);
  if (el("gPass2")) el("gPass2").classList.toggle("active", cleanPasses === 2);
}

// The values of a preset exactly as applyConfig() puts them on the controls: defaults for missing keys, the limits
// of the sliders. readCurrentConfig() right after applyConfig(cfg) gives these same values (plus speedMode) -
// the automatic preset relies on it: the server is sent these values before the controls show them.
function normalizedPresetConfig(cfg) {
  const c = cfg || {};
  const flag = (v, dflt) => (v !== undefined ? !!v : dflt);
  return {
    spots: clampSliderVal("gSlSpots", c.spots ?? 75),
    scuffs: clampSliderVal("gSlScuffs", c.scuffs ?? 65),
    blur: clampSliderVal("gSlBlur", c.blur ?? 0),
    cycCurve: clampSliderVal("gSlCyc", c.cycCurve ?? 0),
    feather: clampSliderVal("gSlFeather", c.feather ?? 60),
    seamOn: flag(c.seamOn, true),
    seam: clampSliderVal("gSlSeam", c.seam ?? 85),
    edge: clampSliderVal("gSlEdge", c.edge ?? 70),
    smokeOn: flag(c.smokeOn, true),
    smoke: clampSliderVal("gSlSmoke", c.smoke ?? 80),
    grain: clampSliderVal("gSlGrain", c.grain ?? 90),
    shadow: flag(c.shadow, true),
    removeStands: !!c.removeStands,
    master: clampSliderVal("gSlTurbo", Math.max(100, c.master ?? 100)),
    fracFine: flag(c.fracFine, true),
    fracMed: flag(c.fracMed, true),
    fracLarge: flag(c.fracLarge, true),
    dressSmooth: flag(c.dressSmooth, false),
    dressStrength: clampSliderVal("gSlDress", c.dressStrength ?? 45),
    cleanPasses: Number(c.cleanPasses ?? 1) >= 2 ? 2 : 1
  };
}

function applyConfig(cfg) {
  const c = normalizedPresetConfig(cfg);
  setSliderVal("gSlSpots", c.spots);
  setSliderVal("gSlScuffs", c.scuffs);
  setSliderVal("gSlBlur", c.blur);
  setSliderVal("gSlCyc", c.cycCurve);
  setSliderVal("gSlFeather", c.feather);
  seamEnabled = c.seamOn;
  setSliderVal("gSlSeam", c.seam);
  setSliderVal("gSlEdge", c.edge);
  smokeEnabled = c.smokeOn;
  setSliderVal("gSlSmoke", c.smoke);
  setSliderVal("gSlGrain", c.grain);
  if (el("gChkShadow")) el("gChkShadow").checked = c.shadow;
  if (el("gChkRemoveStands")) el("gChkRemoveStands").checked = c.removeStands;
  setSliderVal("gSlTurbo", c.master);

  fracFine = c.fracFine;
  fracMed = c.fracMed;
  fracLarge = c.fracLarge;
  dressSmoothEnabled = c.dressSmooth;
  setSliderVal("gSlDress", c.dressStrength);
  setCleanPassesUI(c.cleanPasses);
  updateSliderVisuals();
  updateFractionButtonsUI();
}

// ------------------------------------------------------------------
// Presets: fractions, the automatic choice by the kind of frame
// ------------------------------------------------------------------
// What a preset says about the AUTO button of the fractions:
//   true / false - it was saved with AUTO on / off (presets saved by this version carry "fracAuto");
//   null         - it says nothing: AUTO stays the way the user left it.
// A built-in preset that switches a fraction off ("Ближній план": no large one, "Делікатний": only the fine one)
// means exactly that choice. AUTO used to overrule it, so these presets cleaned all three fractions anyway.
function presetFracAuto(p) {
  const c = (p && p.cfg) || {};
  if (typeof c.fracAuto === "boolean") return c.fracAuto;
  if (p && p.builtin && (c.fracFine === false || c.fracMed === false || c.fracLarge === false)) return false;
  return null;
}

function applyPreset(p) {
  activePresetId = p.id;
  applyConfig(p.cfg);
  const auto = presetFracAuto(p);
  fracAuto = auto === null ? fracAutoUser : auto;
  updateFractionButtonsUI();
}

// The current values as a preset stores them (the AUTO button of the fractions is part of the recipe)
function presetConfigToSave() {
  return Object.assign(readCurrentConfig(), { fracAuto });
}

// What the server would be sent if this preset were on the controls
function presetRequestParams(p) {
  const params = normalizedPresetConfig(p.cfg);
  params.speedMode = speedMode;
  const auto = presetFracAuto(p);
  params.autoFractions = auto === null ? fracAutoUser : auto;
  return params;
}

// Which preset suits which kind of frame. The server looks at the frame (dark backdrop / close-up / cut at the
// waist or knees / whole figure) and uses the matching set of values before it cleans anything. Presets are found
// by id: a renamed or edited one keeps working, a deleted one is simply not offered ("default" is used instead).
const AUTO_PRESET_BY_SCENE = { dark: "lowkey", close: "closeup", medium: "medium_shot", wide: "wide_shot", default: "std" };
const SCENE_WORDS = {
  dark: "темний фон",
  close: "ближній план",
  medium: "середній план",
  wide: "людина на повний зріст",
  none: "людини в кадрі не знайдено"
};

function buildScenePresets() {
  const params = {};
  const ids = {};
  Object.keys(AUTO_PRESET_BY_SCENE).forEach((kind) => {
    const p = presetsList.find((x) => x.id === AUTO_PRESET_BY_SCENE[kind]);
    if (p) {
      params[kind] = presetRequestParams(p);
      ids[kind] = p.id;
    }
  });
  return Object.keys(ids).length > 0 ? { params, ids } : null;
}

function autoPresetNote(scene, preset) {
  const kind = scene && scene.dark ? "dark" : ((scene && scene.framing) || "none");
  return `Авто-пресет: «${preset.name}» — ${SCENE_WORDS[kind] || SCENE_WORDS.none}. Інший можна вибрати у списку пресетів.`;
}

function setAutoPreset(on) {
  autoPreset = !!on;
  if (el("dlgChkAutoPreset")) el("dlgChkAutoPreset").checked = autoPreset;
}

function updateSliderVisuals() {
  ALL_SLIDER_IDS.forEach((id) => {
    const v = setSliderVal(id, getSliderVal(id));
    const badge = el(SLIDER_VAL_MAP[id]);
    if (!badge) return;
    if (id === "dlgSlBlend") {
      badge.textContent = String(v);
    } else if (id === "gSlSeam") {
      badge.textContent = seamEnabled ? v + "%" : "Вимк.";
    } else if (id === "gSlSmoke") {
      badge.textContent = smokeEnabled ? v + "%" : "Вимк.";
    } else if (id === "gSlDress") {
      badge.textContent = dressSmoothEnabled ? v + "%" : "Вимк.";
    } else {
      badge.textContent = v + "%";
    }
  });

  if (el("gBtnSeam")) {
    el("gBtnSeam").textContent = seamEnabled ? "Увімк." : "Вимк.";
    el("gBtnSeam").className = "toggle-pill" + (seamEnabled ? " on" : "");
  }
  setSliderDisabled("gSlSeam", !seamEnabled);

  if (el("gBtnSmoke")) {
    el("gBtnSmoke").textContent = smokeEnabled ? "Увімк." : "Вимк.";
    el("gBtnSmoke").className = "toggle-pill" + (smokeEnabled ? " on" : "");
  }
  if (el("dlgChkSmoke")) el("dlgChkSmoke").checked = smokeEnabled;
  if (el("dlgWrapSmoke")) el("dlgWrapSmoke").classList.toggle("active", smokeEnabled);
  setSliderDisabled("gSlSmoke", !smokeEnabled);

  if (el("gBtnDress")) {
    el("gBtnDress").textContent = dressSmoothEnabled ? "Увімк." : "Вимк.";
    el("gBtnDress").className = "toggle-pill" + (dressSmoothEnabled ? " on" : "");
  }
  if (el("dlgChkDress")) el("dlgChkDress").checked = dressSmoothEnabled;
  if (el("dlgWrapDress")) el("dlgWrapDress").classList.toggle("active", dressSmoothEnabled);
  setSliderDisabled("gSlDress", !dressSmoothEnabled);
}

function updateFractionButtonsUI() {
  if (el("dlgFracFine")) el("dlgFracFine").classList.toggle("active", fracFine);
  if (el("dlgFracMed")) el("dlgFracMed").classList.toggle("active", fracMed);
  if (el("dlgFracLarge")) el("dlgFracLarge").classList.toggle("active", fracLarge);
  if (el("dlgFracAuto")) el("dlgFracAuto").classList.toggle("active", fracAuto);
  if (el("dlgSpeedPill")) {
    el("dlgSpeedPill").textContent = speedMode === "quality" ? "✦ Якісний" : "⚡ Швидкий";
  }
}

function setIdleUnloadSec(sec, persist = true) {
  const n = Number(sec);
  idleUnloadSec = Number.isFinite(n) && n >= 0 ? n : DEFAULT_IDLE_UNLOAD_SEC;
  const row = el("gIdlePills");
  if (row) {
    row.querySelectorAll(".idle-pill").forEach((b) => {
      b.classList.toggle("active", Number(b.dataset.sec) === idleUnloadSec);
    });
  }
  if (persist) scheduleSaveSettings();
}

function buildSettingsSnapshot() {
  return {
    schemaVersion: SETTINGS_SCHEMA_VERSION,
    activePresetId,
    cfg: readCurrentConfig(),
    speedMode,
    idleUnloadSec,
    makeMaskDefault,
    fracAuto: fracAutoUser,   // the user's own choice...
    fracAutoNow: fracAuto,    // ...and what the active preset made of it
    autoPreset,
    brushSize: sessState.brushSize,
    deletedDefaultIds: Array.from(new Set(deletedDefaultIds)),
    knownDefaultIds: Array.from(new Set(knownDefaultIds))
  };
}

function applySettingsSnapshot(s) {
  if (!s || typeof s !== "object") return;
  if (Array.isArray(s.deletedDefaultIds)) deletedDefaultIds = Array.from(new Set(s.deletedDefaultIds));
  if (Array.isArray(s.knownDefaultIds)) knownDefaultIds = Array.from(new Set(s.knownDefaultIds));
  if (s.speedMode) speedMode = s.speedMode === "quality" ? "quality" : "fast";
  if (s.idleUnloadSec !== undefined) {
    // Settings saved before schema 5 always carry the former default (30 s), whether or not the option was
    // ever touched -> move that one value to the new default. Any other choice is kept as it was.
    const schema = Number(s.schemaVersion) || 0;
    if (schema < SETTINGS_SCHEMA_VERSION && Number(s.idleUnloadSec) === LEGACY_IDLE_UNLOAD_SEC) {
      setIdleUnloadSec(DEFAULT_IDLE_UNLOAD_SEC, false);
      settingsMigrated = true;
    } else {
      setIdleUnloadSec(s.idleUnloadSec, false);
    }
  }
  if (typeof s.makeMaskDefault === "boolean") {
    makeMaskDefault = s.makeMaskDefault;
    if (el("dlgChkMakeMask")) el("dlgChkMakeMask").checked = makeMaskDefault;
  }
  if (typeof s.fracAuto === "boolean") {
    fracAutoUser = s.fracAuto;
    fracAuto = typeof s.fracAutoNow === "boolean" ? s.fracAutoNow : s.fracAuto;
  }
  if (typeof s.autoPreset === "boolean") setAutoPreset(s.autoPreset);
  if (typeof s.brushSize === "number" && s.brushSize >= 4) sessState.brushSize = Math.round(s.brushSize);
  if (s.activePresetId && presetsList.some((p) => p.id === s.activePresetId)) activePresetId = s.activePresetId;
  if (s.cfg && typeof s.cfg === "object") applyConfig(s.cfg);
}

function appendNewDefaultPresets() {
  if (knownDefaultIds.length === 0 && hasLocalPresets) {
    knownDefaultIds = ["std", "lowkey", "smoke", "clean_stands", "gentle"];
  }
  let added = false;
  DEFAULT_PRESETS.forEach((dp) => {
    const already = presetsList.some((p) => p.id === dp.id);
    const del = deletedDefaultIds.includes(dp.id);
    const known = knownDefaultIds.includes(dp.id);
    if (!already && !del && !known) {
      presetsList.push(JSON.parse(JSON.stringify(dp)));
      added = true;
    }
    if (!known) knownDefaultIds.push(dp.id);
  });
  return added;
}

async function writeLocalJson(filename, obj) {
  try {
    const folder = await uxpFs.getDataFolder();
    const file = await folder.createFile(filename, { overwrite: true });
    await file.write(JSON.stringify(obj, null, 2));
  } catch (_) {}
}

async function readLocalJson(filename) {
  try {
    const folder = await uxpFs.getDataFolder();
    const entry = await folder.getEntry(filename);
    const txt = await entry.read();
    return JSON.parse(txt);
  } catch (_) {
    return null;
  }
}

async function persistSettingsNow() {
  const snap = buildSettingsSnapshot();
  hasLocalSettings = true;
  await writeLocalJson("user_settings.json", snap);
  if (serverOnline) {
    try {
      await fetch(`${SERVER_URL}/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(snap)
      });
    } catch (_) {}
  }
}

function scheduleSaveSettings() {
  if (settingsSaveTimer) clearTimeout(settingsSaveTimer);
  settingsSaveTimer = setTimeout(() => {
    settingsSaveTimer = null;
    persistSettingsNow();
  }, 350);
}

async function persistPresets() {
  hasLocalPresets = true;
  await writeLocalJson("presets_local.json", presetsList);
  if (serverOnline) {
    try {
      await fetch(`${SERVER_URL}/presets`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(presetsList)
      });
    } catch (_) {}
  }
}

async function syncPresetsFromServer() {
  if (!serverOnline) return;
  try {
    const [pResp, sResp] = await Promise.all([
      fetch(`${SERVER_URL}/presets`),
      fetch(`${SERVER_URL}/settings`).catch(() => null)
    ]);

    let srvPresets = null;
    let srvSource = "defaults";
    if (pResp && pResp.ok) {
      const pData = await pResp.json();
      if (Array.isArray(pData)) {
        srvPresets = pData;
        srvSource = "user";
      } else if (pData && Array.isArray(pData.presets)) {
        srvPresets = pData.presets;
        srvSource = pData.source || "defaults";
      }
    }

    let srvSettings = null;
    if (sResp && sResp.ok) {
      const sData = await sResp.json();
      if (sData && sData.exists && sData.settings) srvSettings = sData.settings;
    }

    let changed = false;
    if (!hasLocalSettings && srvSettings) {
      applySettingsSnapshot(srvSettings);
      hasLocalSettings = true;
      changed = true;
    } else if (srvSettings && Array.isArray(srvSettings.deletedDefaultIds)) {
      srvSettings.deletedDefaultIds.forEach((id) => {
        if (!deletedDefaultIds.includes(id)) deletedDefaultIds.push(id);
      });
    }

    if (srvPresets && srvPresets.length > 0) {
      if (!hasLocalPresets && (srvSource === "user" || srvPresets.some((p) => !p.builtin))) {
        presetsList = srvPresets;
        hasLocalPresets = true;
        changed = true;
      } else if (hasLocalPresets) {
        srvPresets.forEach((sp) => {
          if (sp && sp.id && !sp.builtin && !presetsList.some((lp) => lp.id === sp.id)) {
            presetsList.push(sp);
            changed = true;
          }
        });
      }
    }

    if (appendNewDefaultPresets()) changed = true;
    if (!presetsList.some((p) => p.id === activePresetId) && presetsList.length > 0) activePresetId = presetsList[0].id;

    await writeLocalJson("presets_local.json", presetsList);
    await writeLocalJson("user_settings.json", buildSettingsSnapshot());

    if (changed || settingsMigrated || srvSource === "defaults") {
      settingsMigrated = false;
      await persistPresets();
      await persistSettingsNow();
    }

    renderPresets();
    serverSyncedOnce = true;
  } catch (_) {}
}

function renderPresets() {
  const active = presetsList.find((p) => p.id === activePresetId) || presetsList[0];
  if (active) {
    if (el("dlgActivePresetName")) el("dlgActivePresetName").textContent = active.name;
    if (el("dlgActivePresetDot")) el("dlgActivePresetDot").style.background = active.color || "#4da3ff";
    if (el("gBtnSavePreset")) {
      const shortName = active.name.length > 20 ? active.name.slice(0, 19) + "…" : active.name;
      el("gBtnSavePreset").textContent = `💾 Зберегти у «${shortName}»`;
    }
  }

  const listEl = el("dlgPresetsList");
  if (!listEl) return;
  listEl.innerHTML = "";

  presetsList.forEach((p, idx) => {
    const row = document.createElement("div");
    row.className = "preset-item";

    const btn = document.createElement("div");
    btn.setAttribute("role", "button");
    btn.tabIndex = 0;
    btn.className = "preset-btn" + (p.id === activePresetId ? " active" : "");

    const dot = document.createElement("span");
    dot.className = "preset-dot";
    dot.style.background = p.color || "#4da3ff";

    const lbl = document.createElement("span");
    lbl.textContent = p.name;

    btn.appendChild(dot);
    btn.appendChild(lbl);
    btn.addEventListener("click", async () => {
      applyPreset(p);
      renderPresets();
      scheduleSaveSettings();
      if (el("dlgPresetsPopover")) el("dlgPresetsPopover").classList.remove("visible");
      announcePresetClick(p);
      refreshPreviewAfterClick(false);
    });
    row.appendChild(btn);

    if (presetsEditMode) {
      const acts = document.createElement("div");
      acts.className = "edit-actions";

      const btnTop = document.createElement("div");
      btnTop.setAttribute("role", "button");
      btnTop.tabIndex = 0;
      btnTop.className = "ord-btn";
      btnTop.textContent = "⤒";
      setBtnDisabled(btnTop, idx === 0);
      btnTop.addEventListener("click", async () => {
        if (btnTop.disabled) return;
        const [item] = presetsList.splice(idx, 1);
        presetsList.unshift(item);
        renderPresets();
        await persistPresets();
      });

      const btnUp = document.createElement("div");
      btnUp.setAttribute("role", "button");
      btnUp.tabIndex = 0;
      btnUp.className = "ord-btn";
      btnUp.textContent = "↑";
      setBtnDisabled(btnUp, idx === 0);
      btnUp.addEventListener("click", async () => {
        if (btnUp.disabled) return;
        [presetsList[idx - 1], presetsList[idx]] = [presetsList[idx], presetsList[idx - 1]];
        renderPresets();
        await persistPresets();
      });

      const btnDn = document.createElement("div");
      btnDn.setAttribute("role", "button");
      btnDn.tabIndex = 0;
      btnDn.className = "ord-btn";
      btnDn.textContent = "↓";
      setBtnDisabled(btnDn, idx === presetsList.length - 1);
      btnDn.addEventListener("click", async () => {
        if (btnDn.disabled) return;
        [presetsList[idx + 1], presetsList[idx]] = [presetsList[idx], presetsList[idx + 1]];
        renderPresets();
        await persistPresets();
      });

      const btnDel = document.createElement("div");
      btnDel.setAttribute("role", "button");
      btnDel.tabIndex = 0;
      btnDel.className = "ord-btn del-btn";
      btnDel.textContent = "×";
      setBtnDisabled(btnDel, presetsList.length <= 1);
      btnDel.addEventListener("click", async () => {
        if (btnDel.disabled || presetsList.length <= 1) return;
        presetsList.splice(idx, 1);
        if (DEFAULT_PRESETS.some((dp) => dp.id === p.id) && !deletedDefaultIds.includes(p.id)) {
          deletedDefaultIds.push(p.id);
        }
        if (activePresetId === p.id && presetsList.length > 0) activePresetId = presetsList[0].id;
        renderPresets();
        await persistPresets();
        await persistSettingsNow();
      });

      acts.appendChild(btnTop);
      acts.appendChild(btnUp);
      acts.appendChild(btnDn);
      acts.appendChild(btnDel);
      row.appendChild(acts);
    }

    listEl.appendChild(row);
  });

  if (el("dlgBtnRestorePresets")) {
    const hasMissing = DEFAULT_PRESETS.some((dp) => !presetsList.some((p) => p.id === dp.id));
    el("dlgBtnRestorePresets").style.display = presetsEditMode && hasMissing ? "block" : "none";
  }
}

// ------------------------------------------------------------------
// GPU Server Health Check, Auto-Start on Open, Green Play Button & Red Error
// ------------------------------------------------------------------
async function probeHealthSilent() {
  const pill = el("gpuStatusBtn");
  const txt = el("gpuStatusText");
  const playBtn = el("btnPlayServer");

  for (const base of CANDIDATE_URLS) {
    try {
      const resp = await fetch(`${base}/health`, { method: "GET" });
      if (resp.ok) {
        const info = await resp.json();
        if (info.app !== "cleanvinylpro2") continue;  // some other program answers on this port
        SERVER_URL = base;
        if (info.install_dir && info.install_dir !== lastKnownInstallDir) {
          lastKnownInstallDir = info.install_dir;
          writeLocalJson("server_meta.json", { install_dir: lastKnownInstallDir });
        }
        if (info.ok) {
          serverOnline = true;
          hideServerErrorCard();
          if (playBtn) playBtn.style.display = "none";
          const isCpu = String(info.provider || "").includes("CPU");
          pill.className = isCpu ? "gpu-pill loading" : "gpu-pill";
          const shortGpu = (info.gpu || "GPU").replace("NVIDIA GeForce ", "").split(",")[0].trim();
          const sleepTag = info.models_loaded === false ? " • сон" : "";
          txt.textContent = (isCpu ? "CPU" : (shortGpu || "GPU")) + sleepTag;
          if (info.version && info.version !== PLUGIN_VERSION) {
            showBanner(
              `Працює сервер версії ${info.version}, а панель — версії ${PLUGIN_VERSION}. Запустіть ` +
              "restart_gpu_server.bat у папці програми: без цього нові функції панелі не працюватимуть.",
              "info"
            );
          } else if (isCpu && info.gpu_error) {
            showBanner("Сервер працює на CPU: " + info.gpu_error, "info");
          } else {
            hideBanner();
          }
          if (!serverSyncedOnce) await syncPresetsFromServer();
          return { ok: true, info };
        }
        return { ok: false, modelError: info.error || "AI-моделі не завантажені" };
      }
    } catch (_) {}
  }
  return { ok: false };
}

async function checkServerHealth() {
  const pill = el("gpuStatusBtn");
  const txt = el("gpuStatusText");
  const playBtn = el("btnPlayServer");
  pill.className = "gpu-pill loading";
  txt.textContent = "Перевірка...";

  const res = await probeHealthSilent();
  if (res.ok) return true;
  if (serverLaunchPromise && !res.modelError) return false;  // it is being started right now: that wait reports

  serverOnline = false;
  pill.className = "gpu-pill offline";
  if (res.modelError) {
    txt.textContent = "Моделі!";
    if (playBtn) playBtn.style.display = "none";
    showServerErrorCard("Сервер працює, але AI-моделі не знайдено: " + escapeHtml(res.modelError));
    return false;
  }

  txt.textContent = "Вимк.";
  if (playBtn) playBtn.style.display = "inline-flex";
  return false;
}

// A cold start is slow: Python, the libraries and both AI models load before the server answers at all (half a
// minute and more after the PC was switched on). So the start is asked for once and then waited for patiently;
// the status turns green by itself the moment the server answers.
const SERVER_START_WAIT_MS = 150000;
const SERVER_START_POLL_MS = 750;
const SERVER_START_HINT_AFTER_MS = 25000;

async function launchServerViaProtocol(isAutoAttempt = false) {
  if (serverLaunchPromise) {
    const okExisting = await serverLaunchPromise;
    if (!okExisting && !isAutoAttempt) {
      showServerErrorCard(
        "ERROR: Не вдалося запустити сервер через кнопку ▶ (порт 18746 не відповідає)."
      );
    }
    return okExisting;
  }

  serverLaunchPromise = (async () => {
    const pill = el("gpuStatusBtn");
    const txt = el("gpuStatusText");
    const playBtn = el("btnPlayServer");
    setBtnDisabled(playBtn, true);
    pill.className = "gpu-pill loading";
    txt.textContent = isAutoAttempt ? "Автозапуск..." : "Старт...";

    // Check once first in case server just finished booting before firing cleanvinyl2://
    const preCheck = await probeHealthSilent();
    if (preCheck.ok) {
      setBtnDisabled(playBtn, false);
      return true;
    }

    let launchBlocked = false;
    try {
      if (!uxpShell || !uxpShell.openExternal) {
        throw new Error("Неможливо викликати cleanvinyl2:// з цієї версії Photoshop");
      }
      await uxpShell.openExternal("cleanvinyl2://start");
    } catch (_) {
      launchBlocked = true;
    }

    if (!launchBlocked) {
      const startedAt = Date.now();
      let hinted = false;
      while (Date.now() - startedAt < SERVER_START_WAIT_MS) {
        await delayMs(SERVER_START_POLL_MS);
        const res = await probeHealthSilent();
        if (res.ok) {
          setBtnDisabled(playBtn, false);
          setFooterStatus("✓ GPU-сервер запущено: " + (res.info.gpu || "готово"), "success");
          return true;
        }
        if (res.modelError) {
          setBtnDisabled(playBtn, false);
          hideBanner();
          showServerErrorCard("Сервер відкрито, але не завантажено моделі: " + escapeHtml(res.modelError));
          return false;
        }
        const waited = Date.now() - startedAt;
        pill.className = "gpu-pill loading";
        txt.textContent = `Запуск… ${Math.round(waited / 1000)} с`;
        if (playBtn) playBtn.style.display = "none";
        if (!hinted && waited >= SERVER_START_HINT_AFTER_MS) {
          hinted = true;
          showBanner(
            "Сервер ще завантажує AI-моделі — перший запуск після ввімкнення ПК може тривати до хвилини. " +
            "Якщо вікно сервера так і не з’явилося, запустіть start_gpu_server.bat вручну.",
            "info"
          );
        }
      }
      hideBanner();
    }

    serverOnline = false;
    pill.className = "gpu-pill offline";
    txt.textContent = "Вимк.";
    if (playBtn) {
      playBtn.style.display = "inline-flex";
      setBtnDisabled(playBtn, false);
    }

    if (!isAutoAttempt) {
      showServerErrorCard(
        "ERROR: Не вдалося запустити сервер через кнопку ▶ (порт 18746 не відповідає)."
      );
    }
    return false;
  })();

  try {
    return await serverLaunchPromise;
  } finally {
    serverLaunchPromise = null;
  }
}

// ------------------------------------------------------------------
// A button pressed while the server is not ready is remembered
// ------------------------------------------------------------------
// "Очистити фон" (and the two other actions) pressed before the server answers: the server is started, the press
// is kept and the action goes on by itself the moment the status turns green - no second press. Pressing the
// same button again while it waits takes the press back.
let pendingPress = null; // { btnId, cancelled, cancel() }

function showPendingPress(btnId, on) {
  const btn = el(btnId);
  if (!btn) return;
  if (on) {
    if (btn.dataset.idleText === undefined) btn.dataset.idleText = btn.textContent;
    btn.textContent = "Чекаю на сервер…";
    btn.classList.add("waiting");
  } else {
    if (btn.dataset.idleText !== undefined) btn.textContent = btn.dataset.idleText;
    btn.classList.remove("waiting");
  }
}

async function ensureServerForAction(btnId, actionName) {
  const first = await probeHealthSilent();
  if (first.ok) return true;
  if (first.modelError) {
    await checkServerHealth();
    return false;
  }

  if (pendingPress) pendingPress.cancel("replaced");
  const ticket = { btnId, cancelled: false, cancel: null };
  const takenBack = new Promise((resolve) => {
    ticket.cancel = (why) => {
      if (ticket.cancelled) return;
      ticket.cancelled = why || "user";
      resolve(false);
    };
  });
  pendingPress = ticket;
  showPendingPress(btnId, true);
  setFooterStatus(
    `Сервер запускається. ${actionName} почнеться само, щойно він буде готовий, — вдруге натискати не треба. ` +
    "Щоб скасувати, натисніть цю кнопку ще раз.",
    "info"
  );

  let ok = false;
  try {
    ok = await Promise.race([launchServerViaProtocol(false), takenBack]);
  } finally {
    showPendingPress(btnId, false);
    if (pendingPress === ticket) pendingPress = null;
  }
  if (ticket.cancelled) {
    if (ticket.cancelled === "user") setFooterStatus("Скасовано. Сервер продовжує запускатися.", "info");
    return false;
  }
  if (ok) setFooterStatus("");
  return !!ok;
}

// A click on an action button: a press that is already waiting for the server is taken back, otherwise the action runs.
function pressOrTakeBack(btnId, action) {
  return () => {
    if (pendingPress && pendingPress.btnId === btnId) {
      pendingPress.cancel("user");
      return;
    }
    action();
  };
}

// Starting the server took a while: the action goes on only if the same document is still the active one.
function sameDocumentStillActive(doc) {
  if (app.documents && app.documents.length > 0 && app.activeDocument && app.activeDocument.id === doc.id) return true;
  setFooterStatus("Сервер готовий. Поки він запускався, документ у Photoshop змінився — натисніть кнопку ще раз.", "info");
  return false;
}

async function unloadVramManual() {
  if (!serverOnline) {
    setFooterStatus("GPU-сервер зараз не запущено.", "info");
    return;
  }
  try {
    const r = await fetch(`${SERVER_URL}/unload`, { method: "POST" });
    if (r.ok) {
      await probeHealthSilent();
      setFooterStatus("✓ Пам'ять GPU (VRAM) та ОЗУ звільнено.", "success");
    }
  } catch (_) {}
}

// ------------------------------------------------------------------
// Pure JS UTF-8 & Binary Helpers
// ------------------------------------------------------------------
function utf8Encode(str) {
  const bytes = [];
  for (let i = 0; i < str.length; i++) {
    let code = str.charCodeAt(i);
    if (code >= 0xd800 && code <= 0xdbff && i + 1 < str.length) {
      const next = str.charCodeAt(i + 1);
      if (next >= 0xdc00 && next <= 0xdfff) {
        code = ((code - 0xd800) << 10) + (next - 0xdc00) + 0x10000;
        i++;
      }
    }
    if (code < 0x80) bytes.push(code);
    else if (code < 0x800) bytes.push(0xc0 | (code >> 6), 0x80 | (code & 0x3f));
    else if (code < 0x10000) bytes.push(0xe0 | (code >> 12), 0x80 | ((code >> 6) & 0x3f), 0x80 | (code & 0x3f));
    else bytes.push(0xf0 | (code >> 18), 0x80 | ((code >> 12) & 0x3f), 0x80 | ((code >> 6) & 0x3f), 0x80 | (code & 0x3f));
  }
  return new Uint8Array(bytes);
}

function utf8Decode(bytes) {
  let out = "";
  let i = 0;
  while (i < bytes.length) {
    const b1 = bytes[i++];
    if (b1 < 0x80) out += String.fromCharCode(b1);
    else if ((b1 & 0xe0) === 0xc0) out += String.fromCharCode(((b1 & 0x1f) << 6) | (bytes[i++] & 0x3f));
    else if ((b1 & 0xf0) === 0xe0) {
      const b2 = bytes[i++] & 0x3f;
      const b3 = bytes[i++] & 0x3f;
      out += String.fromCharCode(((b1 & 0x0f) << 12) | (b2 << 6) | b3);
    } else {
      const b2 = bytes[i++] & 0x3f;
      const b3 = bytes[i++] & 0x3f;
      const b4 = bytes[i++] & 0x3f;
      const cp = (((b1 & 0x07) << 18) | (b2 << 12) | (b3 << 6) | b4) - 0x10000;
      out += String.fromCharCode(0xd800 + (cp >> 10), 0xdc00 + (cp & 0x3ff));
    }
  }
  return out;
}

function encodeProcessPacket(metaObj, pixelTypedArray, selectionTypedArray) {
  const metaBytes = utf8Encode(JSON.stringify(metaObj));
  const pxBytes = new Uint8Array(pixelTypedArray.buffer, pixelTypedArray.byteOffset, pixelTypedArray.byteLength);
  const selBytes = selectionTypedArray
    ? new Uint8Array(selectionTypedArray.buffer, selectionTypedArray.byteOffset, selectionTypedArray.byteLength)
    : null;

  const packet = new Uint8Array(4 + metaBytes.length + pxBytes.length + (selBytes ? selBytes.length : 0));
  const view = new DataView(packet.buffer);
  view.setUint32(0, metaBytes.length, true);
  let pos = 4;
  packet.set(metaBytes, pos);
  pos += metaBytes.length;
  packet.set(pxBytes, pos);
  pos += pxBytes.length;
  if (selBytes) packet.set(selBytes, pos);
  return packet;
}

function decodeApplyResponse(arrayBuf, bitDepth) {
  const view = new DataView(arrayBuf);
  const metaLen = view.getUint32(0, true);
  const meta = JSON.parse(utf8Decode(new Uint8Array(arrayBuf, 4, metaLen)));
  const pixOffset = 4 + metaLen;
  const bps = bitDepth === 16 ? 2 : 1;
  const rgbaLen = meta.width * meta.height * 4 * bps;
  const pixelBuffer = arrayBuf.slice(pixOffset, pixOffset + rgbaLen);
  let layerMaskBytes = null;
  if (meta.hasLayerMask && arrayBuf.byteLength >= pixOffset + rgbaLen + meta.width * meta.height) {
    layerMaskBytes = new Uint8Array(arrayBuf, pixOffset + rgbaLen, meta.width * meta.height).slice();
  }
  return { meta, pixelBuffer, layerMaskBytes };
}

function findLayerById(layers, targetId) {
  if (!layers) return null;
  for (let i = 0; i < layers.length; i++) {
    const l = layers[i];
    if (l.id === targetId) return l;
    if (l.layers && l.layers.length > 0) {
      const nested = findLayerById(l.layers, targetId);
      if (nested) return nested;
    }
  }
  return null;
}

function findLatestPluginLayer(layers) {
  if (!layers) return null;
  for (let i = 0; i < layers.length; i++) {
    const l = layers[i];
    if (l.name === "Чистий вініл 2 (AI)" || l.name === "Чистий вініл 2 (Виділення)") return l;
    if (l.layers && l.layers.length > 0) {
      const nested = findLatestPluginLayer(l.layers);
      if (nested) return nested;
    }
  }
  return null;
}

function clampBounds(b, maxW, maxH) {
  return {
    left: Math.max(0, Math.floor(b.left)),
    top: Math.max(0, Math.floor(b.top)),
    right: Math.min(maxW, Math.ceil(b.right)),
    bottom: Math.min(maxH, Math.ceil(b.bottom))
  };
}

// ------------------------------------------------------------------
// Stage Geometry, Zoom / Pan & Reliable Opaque JPEG Previews (No Canvas!)
// ------------------------------------------------------------------
// One of three views at any moment: "До / Після" switches original <-> cleaned photo (never the red/green one),
// "Маска" switches mask <-> cleaned photo. The brush and the eraser work on the mask, so using them shows it.
function setView(view) {
  sessState.view = view === "original" || view === "mask" ? view : "result";
  updateStageVisibility();
}

function updateStageVisibility() {
  const orig = el("dlgOrigImg");
  const comp = el("dlgCompImg");
  const over = el("dlgOverlayImg");
  const dots = el("dlgStrokeDots");

  const showOrig = sessState.view === "original";
  // (holding the mouse outside the photo, or dragging Blend, lifts the mask for that moment)
  const showMask = sessState.view === "mask" && !sessState.peekingClean && !sessState.peekingBlend;
  const showClean = !showOrig && !showMask;

  if (orig) {
    orig.style.display = (showOrig || (showClean && sessState.blend < 99)) ? "block" : "none";
    orig.style.opacity = "1";
  }
  if (comp) {
    comp.style.display = showClean ? "block" : "none";
    comp.style.opacity = showClean ? String(Math.max(0, Math.min(1, sessState.blend / 100))) : "1";
  }
  if (over) {
    over.style.display = showMask ? "block" : "none";
    over.style.opacity = "1";
  }
  if (dots) {
    dots.style.display = showMask ? "block" : "none";
  }

  if (el("dlgBtnBeforeAfter")) el("dlgBtnBeforeAfter").classList.toggle("active", showOrig);
  if (el("dlgBtnMask")) el("dlgBtnMask").classList.toggle("active", sessState.view === "mask");

  // The corner label always names what is on screen (hidden until the first scan has something to show)
  const badge = el("dlgModeBadge");
  if (badge) {
    if (!sessState.id) {
      badge.className = "r4m-mode-badge";
    } else if (showOrig) {
      badge.textContent = "ДО · оригінал";
      badge.className = "r4m-mode-badge visible";
    } else if (showMask) {
      badge.textContent = "МАСКА · зелене буде очищено";
      badge.className = "r4m-mode-badge visible mask";
    } else {
      badge.textContent = "ПІСЛЯ · чисте фото";
      badge.className = "r4m-mode-badge visible clean";
    }
  }
}

function computeFitZoom() {
  const vp = el("dlgViewport");
  if (!vp || !sessState.pw || !sessState.ph) return 1.0;
  const r = vp.getBoundingClientRect();
  const pad = 28;
  const availW = Math.max(120, r.width - pad);
  const availH = Math.max(120, r.height - pad);
  return Math.min(availW / sessState.pw, availH / sessState.ph);
}

function applyStageLayout() {
  const vp = el("dlgViewport");
  const st = el("dlgStage");
  if (!vp || !st || !sessState.pw || !sessState.ph) return;
  const r = vp.getBoundingClientRect();
  if (r.width <= 0 || r.height <= 0) return;

  const dispW = Math.max(20, Math.round(sessState.pw * sessState.zoom));
  const dispH = Math.max(20, Math.round(sessState.ph * sessState.zoom));
  const left = Math.round((r.width - dispW) * 0.5 + sessState.panX);
  const top = Math.round((r.height - dispH) * 0.5 + sessState.panY);

  st.style.width = dispW + "px";
  st.style.height = dispH + "px";
  st.style.left = left + "px";
  st.style.top = top + "px";

  if (el("dlgZoomLabel")) {
    const relPct = Math.round((sessState.zoom / Math.max(0.05, sessState.fitZoom)) * 100);
    el("dlgZoomLabel").textContent = relPct + "%";
  }
}

function resetZoomFit() {
  sessState.fitZoom = computeFitZoom();
  sessState.zoom = sessState.fitZoom;
  sessState.panX = 0;
  sessState.panY = 0;
  applyStageLayout();
}

function setActiveTool(toolName) {
  sessState.tool = toolName;
  if (el("dlgToolPan")) el("dlgToolPan").className = "r4m-tool-btn" + (toolName === "pan" ? " pan-active" : "");
  if (el("dlgToolBrush")) el("dlgToolBrush").className = "r4m-tool-btn" + (toolName === "brush" ? " active" : "");
  if (el("dlgToolEraser")) el("dlgToolEraser").className = "r4m-tool-btn" + (toolName === "eraser" ? " eraser-active" : "");
  const vp = el("dlgViewport");
  if (vp) {
    vp.style.cursor = toolName === "pan" ? "grab" : "crosshair";
  }
}

function adjustBrushSize(delta) {
  sessState.brushSize = Math.max(4, Math.min(180, sessState.brushSize + delta));
  if (el("dlgBrushSizeVal")) el("dlgBrushSizeVal").textContent = String(sessState.brushSize);
  scheduleSaveSettings();
}

function clearStrokeDots() {
  const d = el("dlgStrokeDots");
  if (d) d.innerHTML = "";
  sessState.lastDotX = -1;
  sessState.lastDotY = -1;
  const cur = el("dlgBrushCursor");
  if (cur && !sessState.isDrawing) cur.style.display = "none";
}

function renderBrushCursorAndDot(hoverPt, addDot = false) {
  const st = el("dlgStage");
  const cur = el("dlgBrushCursor");
  if (!st) return;
  const dispW = st.offsetWidth || (sessState.pw * sessState.zoom);
  const dispH = st.offsetHeight || (sessState.ph * sessState.zoom);
  const scale = dispW / Math.max(1, sessState.pw);
  const diam = Math.max(6, Math.round(sessState.brushSize * 2 * scale));
  const half = diam * 0.5;

  if (cur && hoverPt && (sessState.tool === "brush" || sessState.tool === "eraser") && !sessState.spaceDown) {
    cur.style.display = "block";
    cur.style.width = diam + "px";
    cur.style.height = diam + "px";
    cur.style.left = Math.round(hoverPt.x * dispW - half) + "px";
    cur.style.top = Math.round(hoverPt.y * dispH - half) + "px";
    cur.style.borderColor = sessState.tool === "eraser" ? "#ff707b" : "#54ff95";
  } else if (cur) {
    cur.style.display = "none";
  }

  if (addDot && hoverPt && el("dlgStrokeDots")) {
    const dx = hoverPt.x - sessState.lastDotX;
    const dy = hoverPt.y - sessState.lastDotY;
    if (sessState.lastDotX < 0 || (dx * dx + dy * dy) >= 0.00004) {
      sessState.lastDotX = hoverPt.x;
      sessState.lastDotY = hoverPt.y;
      const dot = document.createElement("div");
      dot.className = "stroke-dot";
      dot.style.width = diam + "px";
      dot.style.height = diam + "px";
      dot.style.left = Math.round(hoverPt.x * dispW - half) + "px";
      dot.style.top = Math.round(hoverPt.y * dispH - half) + "px";
      dot.style.background = sessState.tool === "eraser" ? "#b41822" : "#22ee58";
      el("dlgStrokeDots").appendChild(dot);
    }
  }
}

function getNormalizedStagePoint(clientX, clientY) {
  const st = el("dlgStage");
  if (!st) return null;
  const r = st.getBoundingClientRect();
  if (!r || r.width <= 0 || r.height <= 0) return null;
  const inside = clientX >= r.left && clientX <= r.right && clientY >= r.top && clientY <= r.bottom;
  return {
    inside,
    x: Math.max(0, Math.min(1, (clientX - r.left) / r.width)),
    y: Math.max(0, Math.min(1, (clientY - r.top) / r.height))
  };
}

// ------------------------------------------------------------------
// Interactive Session Server Calls
// ------------------------------------------------------------------
async function sendMaskEditOp(op, points = null) {
  if (!sessState.id) return;
  try {
    const r = await fetch(`${SERVER_URL}/session/mask-edit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessState.id,
        op,
        points,
        radius_px: sessState.brushSize,
        erase: sessState.tool === "eraser",
        dressSmooth: dressSmoothEnabled,
        dressStrength: getSliderVal("gSlDress")
      })
    });
    if (r.ok) {
      const d = await r.json();
      if (d.comp_jpg_b64 && el("dlgCompImg")) el("dlgCompImg").src = "data:image/jpeg;base64," + d.comp_jpg_b64;
      if (d.overlay_jpg_b64 && el("dlgOverlayImg")) el("dlgOverlayImg").src = "data:image/jpeg;base64," + d.overlay_jpg_b64;
      if (typeof d.mask_share === "number") sessState.maskShare = d.mask_share;
    }
  } catch (_) {}
  clearStrokeDots();
}

async function sendDressPreviewUpdate() {
  if (!sessState.id) return;
  try {
    const r = await fetch(`${SERVER_URL}/session/dress-preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessState.id,
        dressSmooth: dressSmoothEnabled,
        dressStrength: getSliderVal("gSlDress")
      })
    });
    if (r.ok) {
      const d = await r.json();
      if (d.comp_jpg_b64 && el("dlgCompImg")) el("dlgCompImg").src = "data:image/jpeg;base64," + d.comp_jpg_b64;
      if (d.overlay_jpg_b64 && el("dlgOverlayImg")) el("dlgOverlayImg").src = "data:image/jpeg;base64," + d.overlay_jpg_b64;
    }
  } catch (_) {}
}

async function saveCurrentConfigToActivePreset(announce = true) {
  const active = presetsList.find((p) => p.id === activePresetId);
  if (!active) return false;
  active.cfg = presetConfigToSave();
  renderPresets();
  await persistPresets();
  await persistSettingsNow();
  if (announce && el("dlgHoverHint")) {
    el("dlgHoverHint").textContent = `✓ Збережено зміни у пресет «${active.name}»`;
  }
  return true;
}

// ------------------------------------------------------------------
// Preview that follows the sliders (light refresh) + the full recompute on request
// ------------------------------------------------------------------
// Everything that changes the cleaned background. Clothing and Blend are not here: they have their own instant paths.
function previewSettingsSignature() {
  const c = readCurrentConfig();
  return JSON.stringify([
    c.spots, c.scuffs, c.blur, c.cycCurve, c.feather, !!c.seamOn, c.seam, c.edge, !!c.smokeOn, c.smoke, c.grain,
    !!c.shadow, !!c.removeStands, c.master, !!c.fracFine, !!c.fracMed, !!c.fracLarge, c.cleanPasses, c.speedMode
  ]);
}

function previewMatchesSettings() {
  return !sessState.previewForce && previewSettingsSignature() === sessState.previewSyncedSig;
}

// With 2 passes the second pass searches the already cleaned full-size frame, so there is no light way to show it.
function lightPreviewAvailable() {
  return cleanPasses < 2 && !sessState.quickUnsupported;
}

function progressCardInUse() {
  return sessState.isApplying || (sessState.recomputing && !sessState.previewBusy);
}

function cancelPreviewTimer() {
  if (sessState.previewTimer) {
    clearTimeout(sessState.previewTimer);
    sessState.previewTimer = null;
  }
}

// A short message in the corner of the photo: which preset was picked and why, what a clicked preset changed.
// It gives way to the "refreshing" / "stale" messages and goes away by itself.
function showPreviewNote(text, ms = 8000) {
  if (sessState.noteTimer) clearTimeout(sessState.noteTimer);
  sessState.note = text || "";
  sessState.noteTimer = sessState.note
    ? setTimeout(() => {
      sessState.noteTimer = null;
      sessState.note = "";
      updatePreviewBadge();
    }, ms)
    : null;
  updatePreviewBadge();
}

function percentOfFrame(share) {
  const pct = Math.max(0, Number(share) || 0) * 100;
  return pct.toFixed(pct >= 10 ? 0 : pct >= 1 ? 1 : 2).replace(".", ",") + " %";
}

// A preset was clicked. Between presets the cleaned photo often changes very little (they differ in how sensitive
// the search is), so what happened is also said in words once the refreshed preview is back.
function announcePresetClick(p) {
  if (!sessState.open || !sessState.id) return;
  if (previewMatchesSettings()) {
    sessState.presetNote = null;
    showPreviewNote(`Пресет «${p.name}»: значення ті самі, що вже на екрані, — перегляд не змінився.`);
    return;
  }
  sessState.presetNote = { name: p.name, before: sessState.maskShare };
}

function presetNoteText(note, shareNow) {
  if (typeof shareNow !== "number") return `✓ Пресет «${note.name}» застосовано.`;
  const now = percentOfFrame(shareNow);
  if (typeof note.before !== "number") return `✓ Пресет «${note.name}»: буде очищено ${now} кадру.`;
  const was = percentOfFrame(note.before);
  return now === was
    ? `✓ Пресет «${note.name}»: зона очищення та сама (${now} кадру) — відмінність лише в м’якості та краях.`
    : `✓ Пресет «${note.name}»: буде очищено ${now} кадру (було ${was}).`;
}

function updatePreviewBadge() {
  const badge = el("dlgPreviewBadge");
  if (!badge) return;
  let text = "";
  let cls = "r4m-preview-badge";
  if (sessState.open && sessState.id && !sessState.isApplying) {
    if (sessState.previewBusy || sessState.previewTimer) {
      text = "↻ Оновлюю перегляд…";
      cls += " visible";
    } else if (!activeDragSliderId && !sessState.recomputing && !previewMatchesSettings()) {
      if (sessState.quickUnsupported) {
        text = "Перегляд ще зі старими значеннями. Запущено стару версію сервера — перезапустіть його (restart_gpu_server.bat). Оновити зараз: кнопка «↻ Точний перегляд» у налаштуваннях.";
      } else if (cleanPasses >= 2) {
        text = "Перегляд ще зі старими значеннями. З 2× проходом він оновлюється кнопкою «↻ Точний перегляд» у налаштуваннях. «Застосувати» врахує нові значення й без цього.";
      } else {
        text = "Перегляд не оновився. Натисніть «↻ Точний перегляд» у налаштуваннях. «Застосувати» врахує нові значення й без цього.";
      }
      cls += " visible stale";
    } else if (sessState.note) {
      text = sessState.note;
      cls += " visible note";
    }
  }
  badge.textContent = text;
  badge.className = cls;
}

// A setting of the cleaned background was changed: refresh the preview once, a moment after the last change.
function requestPreviewRefresh(waitMs, force) {
  if (!sessState.open || !sessState.id) return;
  if (force) sessState.previewForce = true;
  cancelPreviewTimer();
  if (!sessState.isApplying && lightPreviewAvailable() && !previewMatchesSettings()) {
    sessState.previewTimer = setTimeout(firePreviewRefresh, Math.max(0, Number(waitMs) || 0));
  }
  updatePreviewBadge();
}

function firePreviewRefresh() {
  sessState.previewTimer = null;
  const idle = !sessState.open || !sessState.id || sessState.isApplying;
  // A slider is being dragged again: nothing is computed during a drag, its release asks once more.
  if (idle || activeDragSliderId || !lightPreviewAvailable() || previewMatchesSettings()) {
    updatePreviewBadge();
    return;
  }
  recomputeInteractiveSession(true, true);
}

// Buttons that always recomputed at once (fractions, smoke checkbox, presets): now they refresh the preview the
// light way; where there is no light way (2 passes, older server) they recompute in full at once, as before.
function refreshPreviewAfterClick(force) {
  if (!sessState.open || !sessState.id) return;
  if (lightPreviewAvailable()) requestPreviewRefresh(PREVIEW_DELAY_CLICK_MS, force);
  else recomputeInteractiveSession(true, false);
}

// quick = true: light refresh, only the preview is redrawn, nothing blocks the window.
// quick = false: full recompute of the real frame with the progress card (exact preview).
async function recomputeInteractiveSession(preserveEdits = true, quick = false) {
  if (!sessState.id) return false;
  if (sessState.recomputing) {
    // One more run right after the current one. A full request outranks a light one.
    sessState.pendingRecomputeQuick = sessState.pendingRecompute ? (sessState.pendingRecomputeQuick && !!quick) : !!quick;
    sessState.pendingRecompute = true;
    sessState.pendingRecomputePreserve = preserveEdits;
    return false;
  }
  cancelPreviewTimer();
  quick = !!quick;
  sessState.recomputing = true;
  sessState.previewBusy = quick;
  sessState.previewForce = false;
  const sid = sessState.id;
  const sigAtSend = previewSettingsSignature();
  const jobId = quick ? null : makeJobId();
  if (quick) {
    updatePreviewBadge();
  } else {
    updateProgressUI(18, "Перерахунок маски та фону...", "modal");
    startProgressPolling(jobId, "modal");
  }

  let aborted = false;
  let done = false;
  let timeoutId = null;
  try {
    if (typeof AbortController !== "undefined") {
      recomputeAbortCtrl = new AbortController();
      timeoutId = setTimeout(() => {
        try { if (recomputeAbortCtrl) recomputeAbortCtrl.abort(); } catch (_) {}
      }, 90000);
    } else {
      recomputeAbortCtrl = null;
    }

    const params = readCurrentConfig();
    params.autoFractions = fracAuto;
    const payload = { session_id: sid, params, preserve_edits: preserveEdits };
    if (quick) payload.quick = true;
    else payload.jobId = jobId;
    const fetchOpts = {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    };
    if (recomputeAbortCtrl) fetchOpts.signal = recomputeAbortCtrl.signal;

    const r = await fetch(`${SERVER_URL}/session/recompute`, fetchOpts);
    if (!r.ok) {
      let msg = `Помилка (${r.status})`;
      try { const j = await r.json(); if (j.error) msg = j.error; } catch (_) {}
      throw new Error(msg);
    }
    const d = await r.json();
    if (sessState.id === sid) {
      if (quick && typeof d.quick !== "boolean" && !sessState.quickUnsupported) {
        // An older server build: it ignored "quick" and recomputed in full. Stop asking it after every slider.
        sessState.quickUnsupported = true;
        if (el("dlgHoverHint")) {
          el("dlgHoverHint").textContent = "Запущено стару версію сервера: перезапустіть його (restart_gpu_server.bat), щоб перегляд оновлювався сам.";
        }
      }
      // Nothing was touched while the server was busy -> the picture that came back is for the current settings.
      const untouched = previewSettingsSignature() === sigAtSend;
      if (d.auto_fractions && (untouched || (params.autoFractions && fracAuto))) {
        fracFine = !!d.auto_fractions.fracFine;
        fracMed = !!d.auto_fractions.fracMed;
        fracLarge = !!d.auto_fractions.fracLarge;
        updateFractionButtonsUI();
      }
      if (d.comp_jpg_b64 && el("dlgCompImg")) el("dlgCompImg").src = "data:image/jpeg;base64," + d.comp_jpg_b64;
      if (d.overlay_jpg_b64 && el("dlgOverlayImg")) el("dlgOverlayImg").src = "data:image/jpeg;base64," + d.overlay_jpg_b64;
      sessState.lastStats = d.stats || null;
      sessState.previewSyncedSig = untouched ? previewSettingsSignature() : sigAtSend;
      if (sessState.presetNote && untouched) {
        const note = sessState.presetNote;
        sessState.presetNote = null;
        showPreviewNote(presetNoteText(note, d.mask_share));
      }
      if (typeof d.mask_share === "number") sessState.maskShare = d.mask_share;
      done = true;
      updateStageVisibility();
    }
  } catch (err) {
    sessState.presetNote = null;
    if (err && err.name === "AbortError") {
      aborted = true;
      if (el("dlgHoverHint")) el("dlgHoverHint").textContent = quick ? "Оновлення перегляду перервано." : "Перерахунок скасовано.";
    } else {
      const msg = (quick ? "Помилка оновлення перегляду: " : "Помилка перерахунку: ") + (err && err.message ? err.message : String(err));
      setFooterStatus(msg, "error");
      if (el("dlgHoverHint")) el("dlgHoverHint").textContent = msg;
    }
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
    recomputeAbortCtrl = null;
    if (!quick && !sessState.isApplying) {
      // (while "Застосувати" is running the progress card belongs to it)
      stopProgressPolling();
      hideProgressUI("modal");
    }
    sessState.recomputing = false;
    sessState.previewBusy = false;
  }

  const again = sessState.pendingRecompute;
  const nextPreserve = sessState.pendingRecomputePreserve;
  const nextQuick = sessState.pendingRecomputeQuick;
  sessState.pendingRecompute = false;
  sessState.pendingRecomputeQuick = false;
  const alive = sessState.open && sessState.id === sid && !sessState.isApplying;
  if (again && !aborted && alive) {
    if (!nextQuick) {
      await recomputeInteractiveSession(nextPreserve, false);
    } else if (done && lightPreviewAvailable() && !previewMatchesSettings()) {
      await recomputeInteractiveSession(nextPreserve, true);
    }
  }
  updatePreviewBadge();
  return done;
}

async function closeServerSession() {
  const sid = sessState.id;
  sessState.id = null;
  sessState.open = false;
  if (sid && serverOnline) {
    try {
      await fetch(`${SERVER_URL}/session/close`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sid })
      });
    } catch (_) {}
  }
}

// ------------------------------------------------------------------
// Open Retouch4me-Style Interactive Workspace ("Очистити фон")
// ------------------------------------------------------------------
async function openInteractiveWorkspace() {
  if (isBusy) return;
  if (!app.documents || app.documents.length === 0) {
    setFooterStatus("Спочатку відкрийте фотографію у Photoshop.", "error");
    return;
  }

  const doc = app.activeDocument;
  const docModeStr = String(doc.mode || "").toLowerCase();
  if (docModeStr && !docModeStr.includes("rgb")) {
    setFooterStatus("Переведіть документ у режим RGB (Зображення → Режим → RGB).", "error");
    return;
  }

  setFooterStatus("");
  const ready = await ensureServerForAction("btnRun", "«Очистити фон»");
  if (!ready || isBusy || !sameDocumentStillActive(doc)) return;

  isBusy = true;
  setBtnDisabled(el("btnRun"), true);
  setBtnDisabled(el("btnSelection"), true);
  opStartMs = Date.now();
  updateProgressUI(4, "Читання фото з Photoshop...", "panel");

  let captured = null;
  try {
    await core.executeAsModal(async () => {
      const px = await imaging.getPixels({ documentID: doc.id, colorSpace: "RGB" });
      const rawBuf = await px.imageData.getData({ chunky: true });
      if (rawBuf instanceof Float32Array) {
        px.imageData.dispose();
        throw new Error("32-бітні HDR-документи не підтримуються. Переведіть у 16 біт/канал.");
      }
      const bitDepth = rawBuf instanceof Uint16Array ? 16 : 8;
      const width = px.imageData.width;
      const height = px.imageData.height;
      const components = px.imageData.components;
      const colorProfile = px.imageData.colorProfile || "";

      const params = readCurrentConfig();
      params.autoFractions = fracAuto;
      const settingsSig = previewSettingsSignature();
      const jobId = makeJobId();
      const meta = { width, height, channels: components, bitDepth, hasSelection: false, jobId, params };
      // Automatic preset: the presets travel with the photo, the server uses the one that suits the frame
      const scenePresets = autoPreset ? buildScenePresets() : null;
      if (scenePresets) meta.scenePresets = scenePresets.params;
      const packet = encodeProcessPacket(meta, rawBuf, null);
      px.imageData.dispose();
      captured = {
        packet, width, height, bitDepth, colorProfile, jobId, settingsSig,
        autoFractions: !!params.autoFractions,
        scenePresetIds: scenePresets ? scenePresets.ids : null
      };
    }, { commandName: "Читання фото Чистий Вініл Pro 2" });
  } catch (err) {
    hideProgressUI("panel");
    isBusy = false;
    setBtnDisabled(el("btnRun"), false);
    setBtnDisabled(el("btnSelection"), false);
    setFooterStatus("Помилка читання: " + (err && err.message ? err.message : String(err)), "error");
    return;
  }

  hideProgressUI("panel");

  // Reset dialog visual state and show modal immediately with centered Progress overlay!
  sessState.open = true;
  sessState.id = null;
  sessState.docId = doc.id;
  sessState.docW = captured.width;
  sessState.docH = captured.height;
  sessState.bitDepth = captured.bitDepth;
  sessState.colorProfile = captured.colorProfile;
  sessState.pw = captured.width;
  sessState.ph = captured.height;
  sessState.view = "result";   // the window opens with the cleaned photo; "Маска" shows the green zones
  sessState.maskShare = null;
  sessState.presetNote = null;
  showPreviewNote("");
  sessState.blend = 100;
  sessState.peekingClean = false;
  sessState.peekingBlend = false;
  sessState.scanAborted = false;
  sessState.isApplying = false;
  cancelPreviewTimer();
  sessState.pendingRecompute = false;
  sessState.pendingRecomputeQuick = false;
  sessState.previewBusy = false;
  sessState.previewSyncedSig = "";
  sessState.previewForce = false;
  sessState.quickUnsupported = false;
  pendingApplyPayload = null;
  updatePreviewBadge();

  setSliderVal("dlgSlBlend", 100);
  updateSliderVisuals();
  if (el("dlgChkAutoPreset")) el("dlgChkAutoPreset").checked = autoPreset;
  if (el("dlgChkMakeMask")) el("dlgChkMakeMask").checked = makeMaskDefault;
  if (el("dlgBrushSizeVal")) el("dlgBrushSizeVal").textContent = String(sessState.brushSize);
  if (el("dlgOrigImg")) el("dlgOrigImg").src = "";
  if (el("dlgCompImg")) el("dlgCompImg").src = "";
  if (el("dlgOverlayImg")) el("dlgOverlayImg").src = "";
  clearStrokeDots();
  setBtnDisabled(el("dlgBtnApply"), true);
  if (el("dlgPresetsPopover")) el("dlgPresetsPopover").classList.remove("visible");
  if (el("dlgGearPopover")) el("dlgGearPopover").classList.remove("visible");
  if (el("dlgInfoPopover")) el("dlgInfoPopover").classList.remove("visible");

  // Default tool = Eraser: the first stroke over the photo shows the mask and erases the extra green there
  setActiveTool("eraser");
  updateStageVisibility();
  updateFractionButtonsUI();
  renderPresets();

  const dlg = el("retouchModal");
  updateProgressUI(10, "Сканування моделі та пошук дефектів...", "modal");

  // Run initial AI scan asynchronously while dialog is open
  (async () => {
    startProgressPolling(captured.jobId, "modal");
    try {
      const resp = await fetch(`${SERVER_URL}/session/start`, {
        method: "POST",
        headers: { "Content-Type": "application/octet-stream" },
        body: captured.packet.buffer
      });
      if (sessState.scanAborted || !sessState.open) return;
      if (!resp.ok) {
        let errMsg = `Помилка сервера (${resp.status})`;
        try { const j = await resp.json(); if (j.error) errMsg = j.error; } catch (_) {}
        throw new Error(errMsg);
      }
      const res = await resp.json();
      if (sessState.scanAborted || !sessState.open) return;

      sessState.id = res.session_id;
      sessState.pw = res.preview_w;
      sessState.ph = res.preview_h;
      sessState.lastStats = res.stats || null;

      // Sliders may have been moved while the first scan was running: then the picture is for the values sent.
      const untouched = previewSettingsSignature() === captured.settingsSig;

      // Automatic preset: the server has already cleaned the frame with the preset that suits it; put that
      // preset on the controls. (Controls touched during the scan win: the preview is refreshed for them.)
      const sceneKey = res.scene && res.scene.applied;
      const scenePresetId = sceneKey && captured.scenePresetIds ? captured.scenePresetIds[sceneKey] : null;
      const scenePreset = scenePresetId ? presetsList.find((p) => p.id === scenePresetId) : null;
      let autoNote = "";
      if (scenePreset && untouched) {
        applyPreset(scenePreset);
        renderPresets();
        scheduleSaveSettings();
        autoNote = autoPresetNote(res.scene, scenePreset);
      }

      if (res.auto_fractions && (untouched || (captured.autoFractions && fracAuto))) {
        fracFine = !!res.auto_fractions.fracFine;
        fracMed = !!res.auto_fractions.fracMed;
        fracLarge = !!res.auto_fractions.fracLarge;
        updateFractionButtonsUI();
      }
      if (untouched) sessState.previewSyncedSig = previewSettingsSignature();
      else sessState.previewSyncedSig = scenePreset ? "" : captured.settingsSig;
      if (typeof res.mask_share === "number") sessState.maskShare = res.mask_share;
      if (autoNote) showPreviewNote(autoNote);

      if (el("dlgOrigImg")) el("dlgOrigImg").src = "data:image/jpeg;base64," + res.orig_jpg_b64;
      if (el("dlgCompImg")) el("dlgCompImg").src = "data:image/jpeg;base64," + res.comp_jpg_b64;
      if (el("dlgOverlayImg")) el("dlgOverlayImg").src = "data:image/jpeg;base64," + (res.overlay_jpg_b64 || res.comp_jpg_b64);

      resetZoomFit();
      updateStageVisibility();
      setBtnDisabled(el("dlgBtnApply"), false);
      updateProgressUI(100, "Готово!", "modal");
      setTimeout(() => { if (!progressCardInUse()) hideProgressUI("modal"); }, 180);
      if (!untouched) requestPreviewRefresh(PREVIEW_DELAY_CLICK_MS, false);
    } catch (err) {
      if (!sessState.scanAborted && sessState.open) {
        hideProgressUI("modal");
        setFooterStatus("Помилка сканування: " + (err && err.message ? err.message : String(err)), "error");
        try { dlg.close("error"); } catch (_) {}
      }
    } finally {
      stopProgressPolling();
      captured.packet = null;
    }
  })();

  // Delay layout fit slightly until modal finishes opening
  setTimeout(() => { if (sessState.open) resetZoomFit(); }, 60);

  try {
    await dlg.uxpShowModal({
      title: "Чистий Вініл Pro 2",
      resize: "both",
      size: { width: 1020, height: 740 }
    });
  } finally {
    sessState.scanAborted = true;
    cancelPreviewTimer();
    sessState.pendingRecompute = false;
    sessState.presetNote = null;
    showPreviewNote("");
    stopProgressPolling();
    stopModalTimer();
    hideProgressUI("all");
    await closeServerSession();
    updatePreviewBadge();
  }

  // Run Photoshop executeAsModal ONLY AFTER uxpShowModal has completely closed
  // so Photoshop exits modal lock and imaging.putPixels writes non-transparent pixels!
  if (pendingApplyPayload) {
    const payload = pendingApplyPayload;
    pendingApplyPayload = null;
    await delayMs(40);
    await commitApplyPayloadToPhotoshop(payload);
  }

  isBusy = false;
  setBtnDisabled(el("btnRun"), false);
  setBtnDisabled(el("btnSelection"), false);
}

async function applyInteractiveResultToPhotoshop() {
  if (!sessState.id || sessState.isApplying) return;
  sessState.isApplying = true;
  setBtnDisabled(el("dlgBtnApply"), true);
  // The layer is always made for the values that are on the sliders right now: they travel with the request and
  // the server computes the full-size frame for them - once, here. A light refresh still waiting is not needed.
  cancelPreviewTimer();
  sessState.pendingRecompute = false;
  updatePreviewBadge();
  const applyParams = readCurrentConfig();
  applyParams.autoFractions = fracAuto;

  const doc = app.activeDocument;
  const makeMask = el("dlgChkMakeMask") ? !!el("dlgChkMakeMask").checked : false;
  makeMaskDefault = makeMask;
  scheduleSaveSettings();

  const jobId = makeJobId();
  updateProgressUI(35, "Підготовка фінального шару...", "modal");
  startProgressPolling(jobId, "modal");

  try {
    const resp = await fetch(`${SERVER_URL}/session/apply`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessState.id,
        blend: sessState.blend,
        makeMask,
        dressSmooth: dressSmoothEnabled,
        dressStrength: getSliderVal("gSlDress"),
        params: applyParams,
        jobId
      })
    });
    if (!resp.ok) {
      let msg = `Помилка (${resp.status})`;
      try { const j = await resp.json(); if (j.error) msg = j.error; } catch (_) {}
      throw new Error(msg);
    }

    const buf = await resp.arrayBuffer();
    const { meta, pixelBuffer, layerMaskBytes } = decodeApplyResponse(buf, sessState.bitDepth);
    pendingApplyPayload = {
      docId: doc.id,
      bitDepth: sessState.bitDepth,
      colorProfile: sessState.colorProfile,
      blend: sessState.blend,
      makeMask,
      meta,
      pixelBuffer,
      layerMaskBytes
    };
    el("retouchModal").close("applied");
  } catch (err) {
    const errMsg = "Помилка підготовки шару: " + (err && err.message ? err.message : String(err));
    setFooterStatus(errMsg, "error");
    if (el("dlgHoverHint")) el("dlgHoverHint").textContent = errMsg;
    setBtnDisabled(el("dlgBtnApply"), false);
  } finally {
    stopProgressPolling();
    hideProgressUI("modal");
    sessState.isApplying = false;
    updatePreviewBadge();
  }
}

async function commitApplyPayloadToPhotoshop(payload) {
  const doc = app.activeDocument;
  if (!doc) {
    setFooterStatus("Документ у Photoshop було закрито.", "error");
    return;
  }
  const { meta, pixelBuffer, layerMaskBytes, bitDepth, colorProfile, blend, makeMask } = payload;
  const outTyped = bitDepth === 16 ? new Uint16Array(pixelBuffer) : new Uint8Array(pixelBuffer);
  updateProgressUI(93, "Створення шару у Photoshop...", "panel");

  try {
    let maskNote = "";
    await core.executeAsModal(async (executionContext) => {
      const suspensionID = await executionContext.hostControl.suspendHistory({
        documentID: doc.id,
        name: "Чистий Вініл Pro 2"
      });
      try {
        const topBefore = doc.layers && doc.layers.length > 0 ? doc.layers[0] : null;
        const newLayer = doc.createPixelLayer
          ? await doc.createPixelLayer({ name: "Чистий вініл 2 (AI)", opacity: Math.round(blend) })
          : await doc.createLayer({ name: "Чистий вініл 2 (AI)" });

        if (!newLayer) throw new Error("Photoshop не зміг створити новий шар.");

        if (topBefore && newLayer.id !== topBefore.id && constants && constants.ElementPlacement) {
          try { await newLayer.move(topBefore, constants.ElementPlacement.PLACEBEFORE); } catch (_) {}
        }

        await action.batchPlay([{ _obj: "select", _target: [{ _ref: "layer", _id: newLayer.id }], makeVisible: true }], {});

        let outImageData = null;
        try {
          const imgOpts = {
            width: meta.width,
            height: meta.height,
            components: 4,
            chunky: true,
            colorSpace: "RGB"
          };
          if (colorProfile) imgOpts.colorProfile = colorProfile;
          outImageData = await imaging.createImageDataFromBuffer(outTyped, imgOpts);
        } catch (_) {
          outImageData = await imaging.createImageDataFromBuffer(outTyped, {
            width: meta.width,
            height: meta.height,
            components: 4,
            chunky: true,
            colorSpace: "RGB"
          });
        }
        await imaging.putPixels({
          documentID: doc.id,
          layerID: newLayer.id,
          imageData: outImageData,
          replace: true
        });
        outImageData.dispose();

        newLayer.opacity = Math.round(blend);
        newLayer.visible = true;
        lastCreatedLayerId = newLayer.id;
        lastDocId = doc.id;
        compareShowingOriginal = false;
        if (el("btnCompare")) {
          el("btnCompare").classList.remove("active");
          el("btnCompare").textContent = "До / Після";
        }

        if (makeMask && layerMaskBytes) {
          let allZero = true;
          let allFull = true;
          for (let i = 0; i < layerMaskBytes.length; i++) {
            const v = layerMaskBytes[i];
            if (v > 0) allZero = false;
            if (v < 255) allFull = false;
            if (!allZero && !allFull) break;
          }

          await action.batchPlay(
            [
              { _obj: "select", _target: [{ _ref: "layer", _id: newLayer.id }], makeVisible: true },
              {
                _obj: "make",
                new: { _class: "channel" },
                at: { _ref: "channel", _enum: "channel", _value: "mask" },
                using: { _enum: "userMaskEnabled", _value: allZero ? "hideAll" : "revealAll" }
              }
            ],
            {}
          );

          if (!allZero && !allFull) {
            try {
              const maskArr = bitDepth === 16
                ? (() => {
                    const u16 = new Uint16Array(layerMaskBytes.length);
                    for (let i = 0; i < layerMaskBytes.length; i++) {
                      u16[i] = Math.round((layerMaskBytes[i] / 255) * 32768);
                    }
                    return u16;
                  })()
                : layerMaskBytes;

              try {
                const maskImg = await imaging.createImageDataFromBuffer(maskArr, {
                  width: meta.width,
                  height: meta.height,
                  components: 1,
                  chunky: true,
                  colorSpace: "Grayscale",
                  colorProfile: "Gray Gamma 2.2"
                });
                await imaging.putLayerMask({
                  documentID: doc.id,
                  layerID: newLayer.id,
                  imageData: maskImg,
                  replace: true
                });
                maskImg.dispose();
              } catch (_) {
                const maskImg8 = await imaging.createImageDataFromBuffer(layerMaskBytes, {
                  width: meta.width,
                  height: meta.height,
                  components: 1,
                  chunky: true,
                  colorSpace: "Grayscale",
                  colorProfile: "Gray Gamma 2.2"
                });
                await imaging.putLayerMask({
                  documentID: doc.id,
                  layerID: newLayer.id,
                  imageData: maskImg8,
                  replace: true
                });
                maskImg8.dispose();
              }
            } catch (_) {}
          }
          maskNote = " • з маскою шару";
        }
      } finally {
        await executionContext.hostControl.resumeHistory(suspensionID);
      }
    }, { commandName: "Чистий Вініл Pro 2" });

    const totalSec = opStartMs > 0 ? ((Date.now() - opStartMs) / 1000).toFixed(2) : "—";
    const chPx = (meta.stats && meta.stats.changed_px) || 0;
    const gpuLabel = ((meta.stats && meta.stats.gpu) || "GPU").replace("NVIDIA GeForce ", "").split(",")[0].trim();
    setFooterStatus(`✓ Шар створено (${gpuLabel}, ${bitDepth}-bit${maskNote}, змінено ${chPx.toLocaleString("uk-UA")} пкс, сесія ${totalSec} с).`, "success");
    probeHealthSilent();
  } catch (err) {
    setFooterStatus("Помилка запису шару у Photoshop: " + (err && err.message ? err.message : String(err)), "error");
  } finally {
    hideProgressUI("panel");
  }
}

// ------------------------------------------------------------------
// Quick Selection Mode ("У виділенні")
// ------------------------------------------------------------------
async function runQuickSelectionClean() {
  if (isBusy) return;
  if (!app.documents || app.documents.length === 0) {
    setFooterStatus("Спочатку відкрийте фотографію у Photoshop.", "error");
    return;
  }

  const doc = app.activeDocument;
  const docModeStr = String(doc.mode || "").toLowerCase();
  if (docModeStr && !docModeStr.includes("rgb")) {
    setFooterStatus("Переведіть документ у режим RGB (Зображення → Режим → RGB).", "error");
    return;
  }

  const ready = await ensureServerForAction("btnSelection", "Очищення у виділенні");
  if (!ready || isBusy || !sameDocumentStillActive(doc)) return;

  isBusy = true;
  setBtnDisabled(el("btnRun"), true);
  setBtnDisabled(el("btnSelection"), true);
  opStartMs = Date.now();
  const jobId = makeJobId();
  updateProgressUI(8, "Читання виділеної ділянки...", "panel");

  try {
    let captured = null;
    await core.executeAsModal(async () => {
      let selBounds = null;
      try { selBounds = await Promise.resolve(doc.selection.bounds); } catch (_) { selBounds = null; }
      if (!selBounds || selBounds.right <= selBounds.left || selBounds.bottom <= selBounds.top) {
        throw new Error("Немає активного виділення. Обведіть місце Ласо (L) і натисніть «У виділенні».");
      }
      const PAD = 220;
      const queryBounds = clampBounds(
        { left: selBounds.left - PAD, top: selBounds.top - PAD, right: selBounds.right + PAD, bottom: selBounds.bottom + PAD },
        doc.width,
        doc.height
      );

      const px = await imaging.getPixels({ documentID: doc.id, colorSpace: "RGB", sourceBounds: queryBounds });
      const rawBuf = await px.imageData.getData({ chunky: true });
      if (rawBuf instanceof Float32Array) {
        px.imageData.dispose();
        throw new Error("32-бітні HDR-документи не підтримуються.");
      }

      const bitDepth = rawBuf instanceof Uint16Array ? 16 : 8;
      const width = px.imageData.width;
      const height = px.imageData.height;
      const components = px.imageData.components;
      const colorProfile = px.imageData.colorProfile || "";
      const actualBounds = px.sourceBounds || queryBounds;
      const boundLeft = Number.isFinite(actualBounds.left) ? actualBounds.left : 0;
      const boundTop = Number.isFinite(actualBounds.top) ? actualBounds.top : 0;

      const selRes = await imaging.getSelection({ documentID: doc.id, sourceBounds: actualBounds });
      const selBuf = await selRes.imageData.getData({ chunky: true });
      const selIs16 = selBuf instanceof Uint16Array;
      const sb = selRes.sourceBounds || actualBounds;
      const sw = selRes.imageData.width;
      const sh = selRes.imageData.height;
      const selFull = new Uint8Array(width * height);
      const offX = Math.max(0, (Number.isFinite(sb.left) ? sb.left : boundLeft) - boundLeft);
      const offY = Math.max(0, (Number.isFinite(sb.top) ? sb.top : boundTop) - boundTop);
      for (let y = 0; y < sh; y++) {
        const dstY = offY + y;
        if (dstY >= height) break;
        const copyW = Math.min(sw, width - offX);
        if (copyW > 0) {
          if (selIs16) {
            for (let x = 0; x < copyW; x++) selFull[dstY * width + offX + x] = Math.min(255, Math.round((selBuf[y * sw + x] / 32768) * 255));
          } else {
            selFull.set(selBuf.subarray(y * sw, y * sw + copyW), dstY * width + offX);
          }
        }
      }
      selRes.imageData.dispose();

      const params = readCurrentConfig();
      const packet = encodeProcessPacket(
        { width, height, channels: components, bitDepth, hasSelection: true, selectionBitDepth: 8, jobId, params },
        rawBuf,
        selFull
      );
      px.imageData.dispose();
      captured = { packet, bitDepth, colorProfile, left: boundLeft, top: boundTop };
    }, { commandName: "Читання виділення" });

    startProgressPolling(jobId, "panel");
    const resp = await fetch(`${SERVER_URL}/process`, {
      method: "POST",
      headers: { "Content-Type": "application/octet-stream" },
      body: captured.packet.buffer
    });
    stopProgressPolling();
    if (!resp.ok) {
      let errMsg = `Помилка (${resp.status})`;
      try { const j = await resp.json(); if (j.error) errMsg = j.error; } catch (_) {}
      throw new Error(errMsg);
    }

    const buf = await resp.arrayBuffer();
    const { meta, pixelBuffer } = decodeApplyResponse(buf, captured.bitDepth);
    const outTyped = captured.bitDepth === 16 ? new Uint16Array(pixelBuffer) : new Uint8Array(pixelBuffer);

    await core.executeAsModal(async (executionContext) => {
      const suspensionID = await executionContext.hostControl.suspendHistory({ documentID: doc.id, name: "Чистий Вініл 2 (Виділення)" });
      try {
        await action.batchPlay([{ _obj: "set", _target: [{ _ref: "channel", _property: "selection" }], to: { _enum: "ordinal", _value: "none" } }], {});
        const topBefore = doc.layers && doc.layers.length > 0 ? doc.layers[0] : null;
        const newLayer = doc.createPixelLayer
          ? await doc.createPixelLayer({ name: "Чистий вініл 2 (Виділення)", opacity: 100 })
          : await doc.createLayer({ name: "Чистий вініл 2 (Виділення)" });
        if (topBefore && newLayer.id !== topBefore.id && constants && constants.ElementPlacement) {
          try { await newLayer.move(topBefore, constants.ElementPlacement.PLACEBEFORE); } catch (_) {}
        }
        await action.batchPlay([{ _obj: "select", _target: [{ _ref: "layer", _id: newLayer.id }], makeVisible: true }], {});
        const imgOpts = { width: meta.width, height: meta.height, components: 4, chunky: true, colorSpace: "RGB" };
        if (captured.colorProfile) imgOpts.colorProfile = captured.colorProfile;
        const imgData = await imaging.createImageDataFromBuffer(outTyped, imgOpts);
        await imaging.putPixels({
          documentID: doc.id,
          layerID: newLayer.id,
          imageData: imgData,
          targetBounds: { left: captured.left, top: captured.top },
          replace: true
        });
        imgData.dispose();
        lastCreatedLayerId = newLayer.id;
        lastDocId = doc.id;
      } finally {
        await executionContext.hostControl.resumeHistory(suspensionID);
      }
    }, { commandName: "Чистий Вініл 2 (Виділення)" });

    const sec = ((Date.now() - opStartMs) / 1000).toFixed(2);
    setFooterStatus(`✓ Виділену ділянку очищено за ${sec} с.`, "success");
    probeHealthSilent();
  } catch (err) {
    setFooterStatus("Помилка: " + (err && err.message ? err.message : String(err)), "error");
  } finally {
    stopProgressPolling();
    hideProgressUI("panel");
    isBusy = false;
    setBtnDisabled(el("btnRun"), false);
    setBtnDisabled(el("btnSelection"), false);
  }
}

// ------------------------------------------------------------------
// Print format 5:7: the canvas grows on two opposite sides and the server continues the backdrop there
// ------------------------------------------------------------------
const FORMAT_LAYER_NAME = "Фон 5:7 (AI)";

function setMainButtonsDisabled(dis) {
  setBtnDisabled(el("btnRun"), dis);
  setBtnDisabled(el("btnSelection"), dis);
  setBtnDisabled(el("btnFormat57"), dis);
}

async function runExtendCanvasToFormat() {
  if (isBusy) return;
  if (!app.documents || app.documents.length === 0) {
    setFooterStatus("Спочатку відкрийте фотографію у Photoshop.", "error");
    return;
  }

  const doc = app.activeDocument;
  const docModeStr = String(doc.mode || "").toLowerCase();
  if (docModeStr && !docModeStr.includes("rgb")) {
    setFooterStatus("Переведіть документ у режим RGB (Зображення → Режим → RGB).", "error");
    return;
  }

  const ready = await ensureServerForAction("btnFormat57", "«Формат 5:7»");
  if (!ready || isBusy || !sameDocumentStillActive(doc)) return;

  isBusy = true;
  setMainButtonsDisabled(true);
  opStartMs = Date.now();
  const jobId = makeJobId();
  updateProgressUI(8, "Читання фото...", "panel");

  try {
    let captured = null;
    await core.executeAsModal(async () => {
      const px = await imaging.getPixels({ documentID: doc.id, colorSpace: "RGB" });
      const rawBuf = await px.imageData.getData({ chunky: true });
      if (rawBuf instanceof Float32Array) {
        px.imageData.dispose();
        throw new Error("32-бітні HDR-документи не підтримуються.");
      }
      const bitDepth = rawBuf instanceof Uint16Array ? 16 : 8;
      const width = px.imageData.width;
      const height = px.imageData.height;
      const components = px.imageData.components;
      const colorProfile = px.imageData.colorProfile || "";
      const packet = encodeProcessPacket(
        { width, height, channels: components, bitDepth, jobId, params: { ratioShort: 5, ratioLong: 7, edge: getSliderVal("gSlEdge") } },
        rawBuf,
        null
      );
      px.imageData.dispose();
      captured = { packet, bitDepth, colorProfile, width, height };
    }, { commandName: "Читання фото (Формат 5:7)" });

    if (captured.width !== doc.width || captured.height !== doc.height) {
      throw new Error("Не вдалося прочитати весь документ. Зніміть виділення і спробуйте ще раз.");
    }

    startProgressPolling(jobId, "panel");
    const resp = await fetch(`${SERVER_URL}/extend-canvas`, {
      method: "POST",
      headers: { "Content-Type": "application/octet-stream" },
      body: captured.packet.buffer
    });
    stopProgressPolling();
    captured.packet = null;
    if (!resp.ok) {
      let errMsg = `Помилка (${resp.status})`;
      try { const j = await resp.json(); if (j.error) errMsg = j.error; } catch (_) {}
      throw new Error(errMsg);
    }

    const contentType = String((resp.headers && resp.headers.get && resp.headers.get("content-type")) || "");
    if (contentType.includes("application/json")) {
      const j = await resp.json();
      if (j && j.unchanged) {
        setFooterStatus(
          j.reason === "too_far"
            ? "Цей кадр надто далекий від формату 5:7 — фон довелося б добудовувати більш ніж на половину кадру."
            : "Кадр уже має формат 5:7 — добудовувати нічого не треба.",
          "info"
        );
        return;
      }
      throw new Error((j && j.error) || "Сервер не повернув зображення.");
    }

    const buf = await resp.arrayBuffer();
    const { meta, pixelBuffer } = decodeApplyResponse(buf, captured.bitDepth);
    const outTyped = captured.bitDepth === 16 ? new Uint16Array(pixelBuffer) : new Uint8Array(pixelBuffer);
    updateProgressUI(92, "Розширення полотна у Photoshop...", "panel");

    await core.executeAsModal(async (executionContext) => {
      const suspensionID = await executionContext.hostControl.suspendHistory({ documentID: doc.id, name: "Формат 5:7 (Чистий Вініл 2)" });
      try {
        await action.batchPlay([{ _obj: "set", _target: [{ _ref: "channel", _property: "selection" }], to: { _enum: "ordinal", _value: "none" } }], {});

        // 1. bigger canvas, the photo stays in the middle (both added strips are equal)
        let resized = false;
        if (typeof doc.resizeCanvas === "function" && constants && constants.AnchorPosition) {
          try {
            await doc.resizeCanvas(meta.width, meta.height, constants.AnchorPosition.MIDDLECENTER);
            resized = true;
          } catch (_) { resized = false; }
        }
        if (!resized) {
          await action.batchPlay([{
            _obj: "canvasSize",
            width: { _unit: "pixelsUnit", _value: meta.width },
            height: { _unit: "pixelsUnit", _value: meta.height },
            horizontal: { _enum: "horizontalLocation", _value: "center" },
            vertical: { _enum: "verticalLocation", _value: "center" }
          }], {});
        }
        if (doc.width !== meta.width || doc.height !== meta.height) {
          throw new Error(`Photoshop не змінив розмір полотна (${doc.width}×${doc.height} замість ${meta.width}×${meta.height}).`);
        }

        // 2. the continued backdrop goes to its own layer on top
        const topBefore = doc.layers && doc.layers.length > 0 ? doc.layers[0] : null;
        const newLayer = doc.createPixelLayer
          ? await doc.createPixelLayer({ name: FORMAT_LAYER_NAME, opacity: 100 })
          : await doc.createLayer({ name: FORMAT_LAYER_NAME });
        if (topBefore && newLayer.id !== topBefore.id && constants && constants.ElementPlacement) {
          try { await newLayer.move(topBefore, constants.ElementPlacement.PLACEBEFORE); } catch (_) {}
        }
        await action.batchPlay([{ _obj: "select", _target: [{ _ref: "layer", _id: newLayer.id }], makeVisible: true }], {});
        const imgOpts = { width: meta.width, height: meta.height, components: 4, chunky: true, colorSpace: "RGB" };
        if (captured.colorProfile) imgOpts.colorProfile = captured.colorProfile;
        const imgData = await imaging.createImageDataFromBuffer(outTyped, imgOpts);
        await imaging.putPixels({
          documentID: doc.id,
          layerID: newLayer.id,
          imageData: imgData,
          targetBounds: { left: 0, top: 0 },
          replace: true
        });
        imgData.dispose();
      } finally {
        await executionContext.hostControl.resumeHistory(suspensionID);
      }
    }, { commandName: "Формат 5:7 (Чистий Вініл 2)" });

    const sec = ((Date.now() - opStartMs) / 1000).toFixed(1);
    const added = meta.left > 0 ? `по ${meta.left} px зліва і справа` : `по ${meta.top} px зверху і знизу`;
    if (meta.subjectAtEdge) {
      setFooterStatus(`✓ Формат 5:7 готовий (${added}) за ${sec} с. Увага: людина або сукня торкається краю кадру — це місце на новій смузі перевірте і за потреби доробіть вручну.`, "info");
    } else {
      setFooterStatus(`✓ Формат 5:7 готовий: добудовано ${added}, шар «${FORMAT_LAYER_NAME}», ${sec} с.`, "success");
    }
    probeHealthSilent();
  } catch (err) {
    setFooterStatus("Помилка: " + (err && err.message ? err.message : String(err)), "error");
  } finally {
    stopProgressPolling();
    hideProgressUI("panel");
    isBusy = false;
    setMainButtonsDisabled(false);
  }
}

async function toggleBeforeAfterInPhotoshop() {
  if (!app.activeDocument) {
    setFooterStatus("Немає відкритого документа у Photoshop.", "error");
    return;
  }
  try {
    await core.executeAsModal(async () => {
      let layer = (lastCreatedLayerId && app.activeDocument.id === lastDocId)
        ? findLayerById(app.activeDocument.layers, lastCreatedLayerId)
        : null;
      if (!layer) {
        layer = findLatestPluginLayer(app.activeDocument.layers);
        if (layer) {
          lastCreatedLayerId = layer.id;
          lastDocId = app.activeDocument.id;
        }
      }
      if (!layer) {
        setFooterStatus("Шар «Чистий вініл 2 (AI)» ще не створено.", "info");
        return;
      }
      compareShowingOriginal = layer.visible;
      layer.visible = !compareShowingOriginal;
      el("btnCompare").classList.toggle("active", compareShowingOriginal);
      el("btnCompare").textContent = compareShowingOriginal ? "До / Після (Оригінал)" : "До / Після";
    }, { commandName: "До / Після (Чистий Вініл 2)" });
  } catch (err) {
    setFooterStatus("Помилка До/Після: " + (err && err.message ? err.message : String(err)), "error");
  }
}

// ------------------------------------------------------------------
// Ukrainian Hover Tooltip Manager
// ------------------------------------------------------------------
let hoverTimer = null;
function showTipForElement(target) {
  const hintStrip = el("dlgHoverHint");
  const gearTip = el("gTipBox");
  if (!target) {
    if (hintStrip) hintStrip.textContent = "Наведіть курсор на кнопку для підказки";
    return;
  }
  const msg = target.getAttribute ? target.getAttribute("data-tip") : "";
  if (!msg) return;
  if (hintStrip) hintStrip.textContent = msg;
  const gearPop = el("dlgGearPopover");
  if (gearTip && gearPop && gearPop.contains && gearPop.contains(target)) {
    gearTip.textContent = msg;
  }
}

function initTooltips() {
  const dlg = el("retouchModal");
  const tipBox = el("dlgTooltip");
  if (!dlg || !tipBox) return;

  dlg.addEventListener("mouseover", (e) => {
    if (activeDragSliderId) return;
    const target = e.target && e.target.closest ? e.target.closest("[data-tip]") : null;
    if (hoverTimer) { clearTimeout(hoverTimer); hoverTimer = null; }
    tipBox.classList.remove("visible");
    showTipForElement(target);
    if (!target) return;
    const msg = target.getAttribute("data-tip");
    if (!msg) return;
    const insideGear = el("dlgGearPopover") && el("dlgGearPopover").contains && el("dlgGearPopover").contains(target);
    if (!insideGear) {
      hoverTimer = setTimeout(() => {
        tipBox.textContent = msg;
        tipBox.classList.add("visible");
      }, 360);
    }
  });

  dlg.addEventListener("mouseout", (e) => {
    if (activeDragSliderId) return;
    const related = e.relatedTarget && e.relatedTarget.closest ? e.relatedTarget.closest("[data-tip]") : null;
    if (!related) {
      if (hoverTimer) { clearTimeout(hoverTimer); hoverTimer = null; }
      tipBox.classList.remove("visible");
    }
  });
}

// ------------------------------------------------------------------
// Event Wiring
// ------------------------------------------------------------------
function updateSliderFromClientX(sliderId, clientX) {
  if (sliderDisabled[sliderId]) return;
  const node = el(sliderId);
  if (!node) return;
  const rect = node.getBoundingClientRect();
  if (!rect || rect.width <= 0) return;
  const maxV = getSliderMax(sliderId);
  const next = Math.max(0, Math.min(maxV, Math.round(((clientX - rect.left) / rect.width) * maxV)));
  if (next !== getSliderVal(sliderId)) {
    setSliderVal(sliderId, next);
    updateSliderVisuals();
    if (sliderId === "dlgSlBlend") {
      sessState.blend = next;
      updateStageVisibility();
    } else {
      scheduleSaveSettings();
    }
  }
}

function initEvents() {
  // Custom drag-only sliders
  ALL_SLIDER_IDS.forEach((id) => {
    const node = el(id);
    if (!node) return;
    node.addEventListener("mousedown", (e) => {
      if (e.button !== 0 || sliderDisabled[id]) return;
      e.preventDefault();
      e.stopPropagation();
      activeDragSliderId = id;
      // Nothing is recomputed while a slider is being dragged; a refresh that was waiting is put off as well.
      cancelPreviewTimer();
      updatePreviewBadge();
      const tipOwner = node.closest ? node.closest("[data-tip]") : null;
      if (tipOwner) showTipForElement(tipOwner);
      if (id === "dlgSlBlend" && sessState.open) {
        sessState.peekingBlend = true;
        updateStageVisibility();
      }
      updateSliderFromClientX(id, e.clientX);
    });
  });

  document.addEventListener("mousemove", (e) => {
    if (activeDragSliderId) {
      updateSliderFromClientX(activeDragSliderId, e.clientX);
      return;
    }
    if (!sessState.open || !sessState.pw) return;

    if (sessState.isPanning) {
      sessState.panX = sessState.panStartX + (e.clientX - sessState.dragStartX);
      sessState.panY = sessState.panStartY + (e.clientY - sessState.dragStartY);
      applyStageLayout();
      return;
    }

    const pt = getNormalizedStagePoint(e.clientX, e.clientY);
    if (sessState.isDrawing && pt) {
      sessState.strokePoints.push({ x: pt.x, y: pt.y, norm: true });
      renderBrushCursorAndDot(pt, true);
    } else if (pt && pt.inside) {
      renderBrushCursorAndDot(pt, false);
    } else {
      const cur = el("dlgBrushCursor");
      if (cur) cur.style.display = "none";
    }
  });

  document.addEventListener("mouseup", async () => {
    const finishedSliderId = activeDragSliderId;
    activeDragSliderId = null;

    if (finishedSliderId === "dlgSlBlend" && sessState.open) {
      sessState.peekingBlend = false;
      updateStageVisibility();
    }

    // The slider was released: one light refresh of the preview, a moment later (Blend and Clothing are instant).
    if (finishedSliderId && finishedSliderId !== "dlgSlBlend" && finishedSliderId !== "gSlDress") {
      requestPreviewRefresh(PREVIEW_DELAY_SLIDER_MS, false);
    }

    if (finishedSliderId === "gSlDress" && sessState.open && sessState.id && dressSmoothEnabled) {
      await sendDressPreviewUpdate();
    }

    if (sessState.peekingClean) {
      sessState.peekingClean = false;
      updateStageVisibility();
    }
    if (sessState.isPanning) {
      sessState.isPanning = false;
      setActiveTool(sessState.tool);
    }
    if (sessState.isDrawing) {
      sessState.isDrawing = false;
      const pts = sessState.strokePoints.slice();
      sessState.strokePoints = [];
      if (pts.length > 0 && sessState.id) {
        await sendMaskEditOp("stroke", pts);
      } else {
        clearStrokeDots();
      }
    }
  });

  // Main Panel Buttons
  el("gpuStatusBtn").addEventListener("click", checkServerHealth);
  el("btnPlayServer").addEventListener("click", () => launchServerViaProtocol(false));
  el("btnRetryPlay").addEventListener("click", () => launchServerViaProtocol(false));
  el("btnRecheckServer").addEventListener("click", checkServerHealth);
  el("btnRun").addEventListener("click", pressOrTakeBack("btnRun", openInteractiveWorkspace));
  el("btnSelection").addEventListener("click", pressOrTakeBack("btnSelection", runQuickSelectionClean));
  el("btnFormat57").addEventListener("click", pressOrTakeBack("btnFormat57", runExtendCanvasToFormat));
  el("btnCompare").addEventListener("click", toggleBeforeAfterInPhotoshop);
  el("btnQuickUnload").addEventListener("click", unloadVramManual);
  el("btnPanelHelp").addEventListener("click", () => {
    el("panelHelpBox").classList.toggle("visible");
  });

  // Modal Topbar Controls
  // "До / Після": the photo as it was <-> the cleaned photo. "Маска": the red/green mask <-> the cleaned photo.
  el("dlgBtnBeforeAfter").addEventListener("click", () => {
    setView(sessState.view === "original" ? "result" : "original");
  });

  el("dlgBtnMask").addEventListener("click", () => {
    setView(sessState.view === "mask" ? "result" : "mask");
  });

  el("dlgChkAutoPreset").addEventListener("change", () => {
    setAutoPreset(el("dlgChkAutoPreset").checked);
    scheduleSaveSettings();
    if (el("dlgHoverHint")) {
      el("dlgHoverHint").textContent = autoPreset
        ? "✓ Авто-пресет увімкнено: з наступного фото пресет підбиратиметься під кадр"
        : "Авто-пресет вимкнено: лишається пресет, який вибрали ви";
    }
  });

  el("dlgChkDress").addEventListener("change", async () => {
    dressSmoothEnabled = !!el("dlgChkDress").checked;
    updateSliderVisuals();
    scheduleSaveSettings();
    await sendDressPreviewUpdate();
    if (el("dlgHoverHint")) {
      el("dlgHoverHint").textContent = dressSmoothEnabled
        ? "✓ Рівняння одягу увімкнено"
        : "Рівняння одягу вимкнено (повзунок у налаштуваннях неактивний)";
    }
  });

  el("dlgChkSmoke").addEventListener("change", async () => {
    smokeEnabled = !!el("dlgChkSmoke").checked;
    updateSliderVisuals();
    scheduleSaveSettings();
    refreshPreviewAfterClick(false);
    if (el("dlgHoverHint")) {
      el("dlgHoverHint").textContent = smokeEnabled
        ? "✓ Захист диму увімкнено"
        : "Захист диму вимкнено (повзунок у налаштуваннях неактивний)";
    }
  });

  el("dlgChkMakeMask").addEventListener("change", () => {
    makeMaskDefault = !!el("dlgChkMakeMask").checked;
    scheduleSaveSettings();
  });

  // Popovers (Presets / Gear / Info)
  function togglePopover(popId) {
    ["dlgPresetsPopover", "dlgGearPopover", "dlgInfoPopover"].forEach((id) => {
      const n = el(id);
      if (!n) return;
      if (id === popId) n.classList.toggle("visible");
      else n.classList.remove("visible");
    });
  }

  el("dlgBtnPresets").addEventListener("click", (e) => {
    e.stopPropagation();
    togglePopover("dlgPresetsPopover");
  });
  el("dlgBtnGear").addEventListener("click", (e) => {
    e.stopPropagation();
    togglePopover("dlgGearPopover");
  });
  el("dlgBtnCloseGear").addEventListener("click", () => el("dlgGearPopover").classList.remove("visible"));
  el("dlgBtnInfo").addEventListener("click", (e) => {
    e.stopPropagation();
    togglePopover("dlgInfoPopover");
  });
  el("dlgBtnCloseInfo").addEventListener("click", () => el("dlgInfoPopover").classList.remove("visible"));

  // Presets Edit/Add/Restore inside Popover
  el("dlgBtnAddPreset").addEventListener("click", () => {
    const f = el("dlgAddPresetForm");
    f.classList.toggle("visible");
    if (f.classList.contains("visible")) {
      el("dlgNewPresetName").value = "";
      el("dlgNewPresetName").focus();
    }
  });
  el("dlgBtnCancelNewPreset").addEventListener("click", () => el("dlgAddPresetForm").classList.remove("visible"));

  async function commitModalPreset() {
    const name = el("dlgNewPresetName").value.trim() || `Пресет ${presetsList.length + 1}`;
    const palette = ["#54d182", "#59b5ff", "#e884d5", "#f5b849", "#ff7d7d"];
    const newP = {
      id: "usr_" + Date.now(),
      name,
      color: palette[presetsList.length % palette.length],
      builtin: false,
      cfg: presetConfigToSave()
    };
    presetsList.unshift(newP);
    activePresetId = newP.id;
    el("dlgAddPresetForm").classList.remove("visible");
    renderPresets();
    await persistPresets();
    await persistSettingsNow();
  }
  el("dlgBtnSaveNewPreset").addEventListener("click", commitModalPreset);
  el("dlgNewPresetName").addEventListener("keydown", (e) => { if (e.key === "Enter") commitModalPreset(); });

  el("dlgBtnEditPresets").addEventListener("click", () => {
    presetsEditMode = !presetsEditMode;
    el("dlgBtnEditPresets").classList.toggle("active", presetsEditMode);
    renderPresets();
  });

  el("dlgBtnRestorePresets").addEventListener("click", async () => {
    deletedDefaultIds = [];
    DEFAULT_PRESETS.forEach((dp) => {
      if (!presetsList.some((p) => p.id === dp.id)) presetsList.push(JSON.parse(JSON.stringify(dp)));
      if (!knownDefaultIds.includes(dp.id)) knownDefaultIds.push(dp.id);
    });
    renderPresets();
    await persistPresets();
    await persistSettingsNow();
  });

  // Gear Fine Controls inside Popover
  el("gBtnSeam").addEventListener("click", () => {
    seamEnabled = !seamEnabled;
    updateSliderVisuals();
    scheduleSaveSettings();
    requestPreviewRefresh(PREVIEW_DELAY_CLICK_MS, false);
  });
  el("gBtnSmoke").addEventListener("click", () => {
    smokeEnabled = !smokeEnabled;
    updateSliderVisuals();
    scheduleSaveSettings();
    requestPreviewRefresh(PREVIEW_DELAY_CLICK_MS, false);
  });
  el("gBtnDress").addEventListener("click", async () => {
    dressSmoothEnabled = !dressSmoothEnabled;
    updateSliderVisuals();
    scheduleSaveSettings();
    if (sessState.open && sessState.id) await sendDressPreviewUpdate();
  });
  el("gChkShadow").addEventListener("change", () => {
    scheduleSaveSettings();
    requestPreviewRefresh(PREVIEW_DELAY_CLICK_MS, false);
  });
  el("gChkRemoveStands").addEventListener("change", () => {
    scheduleSaveSettings();
    requestPreviewRefresh(PREVIEW_DELAY_CLICK_MS, false);
  });
  // Exact preview on request: the real frame is recomputed in full (the same work "Застосувати" would do).
  el("gBtnRecompute").addEventListener("click", async () => {
    el("dlgGearPopover").classList.remove("visible");
    const active = presetsList.find((p) => p.id === activePresetId);
    if (active && !active.builtin) {
      await saveCurrentConfigToActivePreset(false);
    }
    await recomputeInteractiveSession(true, false);
    if (active && !active.builtin && el("dlgHoverHint")) {
      el("dlgHoverHint").textContent = `✓ Зміни збережено у «${active.name}» та оновлено прев’ю`;
    }
  });
  el("gBtnSavePreset").addEventListener("click", async () => {
    await saveCurrentConfigToActivePreset(true);
  });

  const gPasses = el("gPassPills");
  if (gPasses) {
    gPasses.querySelectorAll(".idle-pill").forEach((b) => {
      b.addEventListener("click", () => {
        setCleanPassesUI(Number(b.dataset.pass));
        scheduleSaveSettings();
        requestPreviewRefresh(PREVIEW_DELAY_CLICK_MS, false);
      });
    });
  }

  const gIdle = el("gIdlePills");
  if (gIdle) {
    gIdle.querySelectorAll(".idle-pill").forEach((b) => {
      b.addEventListener("click", async () => {
        setIdleUnloadSec(Number(b.dataset.sec), false);
        await persistSettingsNow();
      });
    });
  }

  // Left Toolbar (Pan / Brush + Ctrl-Click Fill / Eraser + Ctrl-Click Clear / Invert / Size)
  el("dlgToolPan").addEventListener("click", () => setActiveTool("pan"));

  // The brush, the eraser and the inversion work on the mask: picking one of them shows it
  el("dlgToolBrush").addEventListener("click", async (e) => {
    setActiveTool("brush");
    setView("mask");
    if (e.ctrlKey || e.metaKey) {
      await sendMaskEditOp("fill");
    }
  });

  el("dlgToolEraser").addEventListener("click", async (e) => {
    setActiveTool("eraser");
    setView("mask");
    if (e.ctrlKey || e.metaKey) {
      await sendMaskEditOp("clear");
    }
  });

  el("dlgToolInvert").addEventListener("click", async () => {
    setView("mask");
    await sendMaskEditOp("invert");
  });

  el("dlgBrushSmaller").addEventListener("click", () => adjustBrushSize(-6));
  el("dlgBrushBigger").addEventListener("click", () => adjustBrushSize(6));

  // Viewport Mouse Interactions: Draw / Pan / Peek Clean Photo Outside Image!
  const vp = el("dlgViewport");
  vp.addEventListener("mousedown", (e) => {
    if (!sessState.open) return;
    // Close open popovers when clicking viewport
    ["dlgPresetsPopover", "dlgGearPopover", "dlgInfoPopover"].forEach((id) => {
      if (el(id)) el(id).classList.remove("visible");
    });

    if (e.button === 1 || sessState.spaceDown || sessState.tool === "pan") {
      e.preventDefault();
      sessState.isPanning = true;
      sessState.dragStartX = e.clientX;
      sessState.dragStartY = e.clientY;
      sessState.panStartX = sessState.panX;
      sessState.panStartY = sessState.panY;
      vp.style.cursor = "grabbing";
      return;
    }

    const pt = getNormalizedStagePoint(e.clientX, e.clientY);
    if (!pt || !pt.inside) {
      // Clicking & holding outside photo hides red/green mask to peek at clean photo!
      sessState.peekingClean = true;
      updateStageVisibility();
      return;
    }

    if (e.button === 0 && (sessState.tool === "brush" || sessState.tool === "eraser")) {
      e.preventDefault();
      if (!sessState.id) return;                         // nothing to draw on while the first scan is running
      if (sessState.view !== "mask") setView("mask");    // a stroke edits the mask: show it
      sessState.isDrawing = true;
      sessState.lastDotX = -1;
      sessState.lastDotY = -1;
      sessState.strokePoints = [{ x: pt.x, y: pt.y, norm: true }];
      renderBrushCursorAndDot(pt, true);
    }
  });

  vp.addEventListener("wheel", (e) => {
    if (!sessState.open || !sessState.pw) return;
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.14 : 1 / 1.14;
    const oldZoom = sessState.zoom;
    const nextZoom = Math.max(0.15, Math.min(6.0, oldZoom * factor));
    const r = vp.getBoundingClientRect();
    const cx = e.clientX - r.left - r.width * 0.5;
    const cy = e.clientY - r.top - r.height * 0.5;
    const scaleRatio = nextZoom / Math.max(0.01, oldZoom);
    sessState.panX = cx - (cx - sessState.panX) * scaleRatio;
    sessState.panY = cy - (cy - sessState.panY) * scaleRatio;
    sessState.zoom = nextZoom;
    applyStageLayout();
  });

  // Keyboard shortcuts inside modal
  document.addEventListener("keydown", (e) => {
    if (!sessState.open) return;
    if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA")) return;
    if (e.code === "Space") {
      sessState.spaceDown = true;
      vp.style.cursor = "grab";
    } else if (e.key === "[") {
      adjustBrushSize(-6);
    } else if (e.key === "]") {
      adjustBrushSize(6);
    } else if (e.key === "b" || e.key === "B" || e.key === "и" || e.key === "И") {
      setActiveTool("brush");
      if (sessState.id) setView("mask");
    } else if (e.key === "e" || e.key === "E" || e.key === "у" || e.key === "У") {
      setActiveTool("eraser");
      if (sessState.id) setView("mask");
    } else if (e.key === "h" || e.key === "H" || e.key === "р" || e.key === "Р") {
      setActiveTool("pan");
    }
  });

  document.addEventListener("keyup", (e) => {
    if (!sessState.open) return;
    if (e.code === "Space") {
      sessState.spaceDown = false;
      setActiveTool(sessState.tool);
    }
  });

  // Bottom Bar: Fractions + Auto + Speed + Zoom + Apply/Cancel
  el("dlgFracFine").addEventListener("click", () => {
    fracAuto = fracAutoUser = false;
    fracFine = !fracFine;
    updateFractionButtonsUI();
    scheduleSaveSettings();
    refreshPreviewAfterClick(false);
  });
  el("dlgFracMed").addEventListener("click", () => {
    fracAuto = fracAutoUser = false;
    fracMed = !fracMed;
    updateFractionButtonsUI();
    scheduleSaveSettings();
    refreshPreviewAfterClick(false);
  });
  el("dlgFracLarge").addEventListener("click", () => {
    fracAuto = fracAutoUser = false;
    fracLarge = !fracLarge;
    updateFractionButtonsUI();
    scheduleSaveSettings();
    refreshPreviewAfterClick(false);
  });
  el("dlgFracAuto").addEventListener("click", () => {
    fracAuto = fracAutoUser = !fracAuto;
    updateFractionButtonsUI();
    scheduleSaveSettings();
    if (fracAuto) refreshPreviewAfterClick(true);  // the server picks the fractions again
  });

  // The speed mode only changes HOW the found defects are closed, and the light preview always draws the fast
  // way - so this switch is shown by a full recompute, the only way to see what the quality mode gives.
  el("dlgSpeedPill").addEventListener("click", async () => {
    speedMode = speedMode === "fast" ? "quality" : "fast";
    updateFractionButtonsUI();
    scheduleSaveSettings();
    await recomputeInteractiveSession(true, false);
  });

  el("dlgZoomOut").addEventListener("click", () => {
    sessState.zoom = Math.max(0.15, sessState.zoom / 1.25);
    applyStageLayout();
  });
  el("dlgZoomIn").addEventListener("click", () => {
    sessState.zoom = Math.min(6.0, sessState.zoom * 1.25);
    applyStageLayout();
  });
  el("dlgZoomLabel").addEventListener("click", resetZoomFit);

  el("dlgBtnApply").addEventListener("click", applyInteractiveResultToPhotoshop);
  el("dlgBtnCancel").addEventListener("click", () => el("retouchModal").close("cancel"));
  el("dlgBtnCloseX").addEventListener("click", () => el("retouchModal").close("cancel"));
  el("dlgBtnCancelScan").addEventListener("click", () => {
    if (sessState.recomputing && !sessState.previewBusy && !sessState.isApplying && sessState.id) {
      // a full recompute is running: stop waiting for it, the window stays open
      sessState.pendingRecompute = false;
      try { if (recomputeAbortCtrl) recomputeAbortCtrl.abort(); } catch (_) {}
      stopProgressPolling();
      hideProgressUI("modal");
      sessState.recomputing = false;
      return;
    }
    sessState.scanAborted = true;
    el("retouchModal").close("cancel");
  });

  // Keyboard activation (Enter/Space) for <div role="button"> controls
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    const t = e.target;
    if (!t || t.tagName === "INPUT" || t.tagName === "TEXTAREA") return;
    const rb = t.getAttribute && t.getAttribute("role") === "button" ? t : null;
    if (!rb || rb.disabled || (rb.classList && rb.classList.contains("is-disabled"))) return;
    if (e.key === " " && sessState.open) return; // Space inside modal is reserved for Pan!
    e.preventDefault();
    rb.click();
  });

  window.addEventListener("resize", () => {
    if (sessState.open && sessState.pw) {
      const oldFit = Math.max(0.05, sessState.fitZoom);
      const rel = sessState.zoom / oldFit;
      sessState.fitZoom = computeFitZoom();
      sessState.zoom = sessState.fitZoom * rel;
      applyStageLayout();
    }
  });

  initTooltips();
}

(async function bootstrap() {
  initEvents();

  const [localPresets, localSettings, serverMeta] = await Promise.all([
    readLocalJson("presets_local.json"),
    readLocalJson("user_settings.json"),
    readLocalJson("server_meta.json")
  ]);

  if (serverMeta && serverMeta.install_dir) {
    lastKnownInstallDir = serverMeta.install_dir;
  }
  if (Array.isArray(localPresets) && localPresets.length > 0) {
    presetsList = localPresets;
    hasLocalPresets = true;
  }
  if (localSettings && typeof localSettings === "object") {
    hasLocalSettings = true;
    applySettingsSnapshot(localSettings);
  }
  if (appendNewDefaultPresets()) {
    await writeLocalJson("presets_local.json", presetsList);
    await writeLocalJson("user_settings.json", buildSettingsSnapshot());
  }
  if (!hasLocalSettings && presetsList.length > 0) {
    activePresetId = presetsList[0].id;
    applyConfig(presetsList[0].cfg);
  }

  renderPresets();
  updateSliderVisuals();
  updateFractionButtonsUI();

  // Check health on panel open; if offline, silently try auto-starting once!
  const firstCheck = await probeHealthSilent();
  if (!firstCheck.ok) {
    if (firstCheck.modelError) {
      await checkServerHealth();
    } else {
      await launchServerViaProtocol(true);
    }
  }
})();
