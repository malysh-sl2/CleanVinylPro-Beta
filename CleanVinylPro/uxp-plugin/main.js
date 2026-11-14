const { app, core, imaging, action, constants } = require("photoshop");
const uxp = require("uxp");
const uxpFs = uxp.storage.localFileSystem;
const uxpShell = uxp.shell;

const CANDIDATE_URLS = ["http://127.0.0.1:18745", "http://localhost:18745"];
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
let fracAuto = true;
let dressSmoothEnabled = false;
let cleanPasses = 1;
let speedMode = "fast";
let idleUnloadSec = 30;
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
  autoMask: true,
  blend: 100,
  showingOriginal: false,
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
  lastStats: null
};
let pendingApplyPayload = null;

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

function setSliderVal(id, rawVal) {
  const maxV = getSliderMax(id);
  const v = Math.max(0, Math.min(maxV, Math.round(Number(rawVal) || 0)));
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
  const pathStr = lastKnownInstallDir || "CleanVinylPro (папка плагіна)";
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
  "💡 Після сканування одразу активна Гумка (E) — просто зітріть зайве зелене з одягу, взуття або тіней.",
  "💡 Затисніть мишку за межами фото — миттєво сховається зелена/червона маска, щоб оцінити чистий результат.",
  "💡 Ctrl + Клік по іконці Пензля (B) заливає всю маску; Ctrl + Клік по Гумці (E) — повністю очищає маску.",
  "💡 Увімкніть іконку сукні зверху, щоб AI делікатно розгладив різкі складки на одязі без впливу на шкіру й волосся.",
  "💡 Натисніть квадратики фракцій знизу (Дрібна / Середня / Велика), щоб швидко вмикати або вимикати типи чистки.",
  "💡 Колесо миші масштабує фото, а Пробіл + мишка дає змогу плавно рухати кадр у наближенні.",
  "💡 Гарячі клавіші [ і ] миттєво зменшують або збільшують розмір пензля й гумки.",
  "💡 Поставте галочку «Make Mask» зверху, якщо хочете отримати у Photoshop редаговану маску шару.",
  "💡 Якщо на фоні є стійки, кабелі чи прилади — увімкніть їх видалення в налаштуваннях (шестигранник) або пресеті «Без стійок (AI)».",
  "💡 Режим «⚡ Швидкий» очищає кадр за кілька секунд; «✦ Якісний» використовує повний прохід LaMa для складних сцен."
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

function applyConfig(cfg) {
  setSliderVal("gSlSpots", cfg.spots ?? 75);
  setSliderVal("gSlScuffs", cfg.scuffs ?? 65);
  setSliderVal("gSlBlur", cfg.blur ?? 0);
  setSliderVal("gSlCyc", cfg.cycCurve ?? 0);
  setSliderVal("gSlFeather", cfg.feather ?? 60);
  seamEnabled = cfg.seamOn !== undefined ? !!cfg.seamOn : true;
  setSliderVal("gSlSeam", cfg.seam ?? 85);
  setSliderVal("gSlEdge", cfg.edge ?? 70);
  smokeEnabled = cfg.smokeOn !== undefined ? !!cfg.smokeOn : true;
  setSliderVal("gSlSmoke", cfg.smoke ?? 80);
  setSliderVal("gSlGrain", cfg.grain ?? 90);
  if (el("gChkShadow")) el("gChkShadow").checked = cfg.shadow !== undefined ? !!cfg.shadow : true;
  if (el("gChkRemoveStands")) el("gChkRemoveStands").checked = !!cfg.removeStands;
  setSliderVal("gSlTurbo", Math.max(100, cfg.master ?? 100));

  fracFine = cfg.fracFine !== undefined ? !!cfg.fracFine : true;
  fracMed = cfg.fracMed !== undefined ? !!cfg.fracMed : true;
  fracLarge = cfg.fracLarge !== undefined ? !!cfg.fracLarge : true;
  dressSmoothEnabled = cfg.dressSmooth !== undefined ? !!cfg.dressSmooth : false;
  setSliderVal("gSlDress", cfg.dressStrength ?? 45);
  setCleanPassesUI(cfg.cleanPasses ?? 1);
  updateSliderVisuals();
  updateFractionButtonsUI();
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
  idleUnloadSec = Number.isFinite(n) && n >= 0 ? n : 30;
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
    schemaVersion: 4,
    activePresetId,
    cfg: readCurrentConfig(),
    speedMode,
    idleUnloadSec,
    makeMaskDefault,
    fracAuto,
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
  if (s.idleUnloadSec !== undefined) setIdleUnloadSec(s.idleUnloadSec, false);
  if (typeof s.makeMaskDefault === "boolean") {
    makeMaskDefault = s.makeMaskDefault;
    if (el("dlgChkMakeMask")) el("dlgChkMakeMask").checked = makeMaskDefault;
  }
  if (typeof s.fracAuto === "boolean") fracAuto = s.fracAuto;
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

    if (changed || srvSource === "defaults") {
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
      activePresetId = p.id;
      applyConfig(p.cfg);
      renderPresets();
      scheduleSaveSettings();
      if (el("dlgPresetsPopover")) el("dlgPresetsPopover").classList.remove("visible");
      if (sessState.open && sessState.id) {
        await recomputeInteractiveSession(true);
      }
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
          if (isCpu && info.gpu_error) {
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

async function launchServerViaProtocol(isAutoAttempt = false) {
  if (serverLaunchPromise) {
    const okExisting = await serverLaunchPromise;
    if (!okExisting && !isAutoAttempt) {
      showServerErrorCard(
        "ERROR: Не вдалося запустити сервер через кнопку ▶ (порт 18745 не відповідає)."
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

    // Check once first in case server just finished booting before firing cleanvinyl://
    const preCheck = await probeHealthSilent();
    if (preCheck.ok) {
      setBtnDisabled(playBtn, false);
      return true;
    }

    let launchBlocked = false;
    try {
      if (!uxpShell || !uxpShell.openExternal) {
        throw new Error("Неможливо викликати cleanvinyl:// з цієї версії Photoshop");
      }
      await uxpShell.openExternal("cleanvinyl://start");
    } catch (_) {
      launchBlocked = true;
    }

    if (!launchBlocked) {
      const maxTries = isAutoAttempt ? 12 : 16;
      for (let i = 0; i < maxTries; i++) {
        await delayMs(750);
        const res = await probeHealthSilent();
        if (res.ok) {
          setBtnDisabled(playBtn, false);
          setFooterStatus("✓ GPU-сервер запущено: " + (res.info.gpu || "готово"), "success");
          return true;
        }
        if (res.modelError) {
          setBtnDisabled(playBtn, false);
          showServerErrorCard("Сервер відкрито, але не завантажено моделі: " + escapeHtml(res.modelError));
          return false;
        }
      }
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
        "ERROR: Не вдалося запустити сервер через кнопку ▶ (порт 18745 не відповідає)."
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

async function ensureServerReadyOrPrompt() {
  const ok = await probeHealthSilent();
  if (ok.ok) return true;
  const started = await launchServerViaProtocol(false);
  return started;
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
    if (l.name === "Чистий вініл (AI)" || l.name === "Чистий вініл (Виділення)") return l;
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
function updateStageVisibility() {
  const orig = el("dlgOrigImg");
  const comp = el("dlgCompImg");
  const over = el("dlgOverlayImg");
  const dots = el("dlgStrokeDots");

  const showOrig = sessState.showingOriginal;
  const showMask = sessState.autoMask && !sessState.showingOriginal && !sessState.peekingClean && !sessState.peekingBlend;
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
    dots.style.display = (!sessState.showingOriginal && !sessState.peekingClean && showMask) ? "block" : "none";
  }

  const badge = el("dlgModeBadge");
  if (badge) {
    if (showOrig) {
      badge.textContent = "👁 ОРИГІНАЛ (ДО)";
      badge.className = "r4m-mode-badge visible";
    } else if (sessState.peekingClean || sessState.peekingBlend) {
      badge.textContent = "✨ ЧИСТЕ ФОТО (ПІСЛЯ)";
      badge.className = "r4m-mode-badge visible clean";
    } else {
      badge.className = "r4m-mode-badge";
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
  active.cfg = readCurrentConfig();
  renderPresets();
  await persistPresets();
  await persistSettingsNow();
  if (announce && el("dlgHoverHint")) {
    el("dlgHoverHint").textContent = `✓ Збережено зміни у пресет «${active.name}»`;
  }
  return true;
}

async function recomputeInteractiveSession(preserveEdits = true) {
  if (!sessState.id) return;
  if (sessState.recomputing) {
    sessState.pendingRecompute = true;
    sessState.pendingRecomputePreserve = preserveEdits;
    return;
  }
  sessState.recomputing = true;
  const jobId = makeJobId();
  updateProgressUI(18, "Перерахунок маски та фону...", "modal");
  startProgressPolling(jobId, "modal");

  let aborted = false;
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
    const fetchOpts = {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessState.id,
        params,
        preserve_edits: preserveEdits,
        jobId
      })
    };
    if (recomputeAbortCtrl) fetchOpts.signal = recomputeAbortCtrl.signal;

    const r = await fetch(`${SERVER_URL}/session/recompute`, fetchOpts);
    if (!r.ok) {
      let msg = `Помилка (${r.status})`;
      try { const j = await r.json(); if (j.error) msg = j.error; } catch (_) {}
      throw new Error(msg);
    }
    const d = await r.json();
    if (d.auto_fractions) {
      fracFine = !!d.auto_fractions.fracFine;
      fracMed = !!d.auto_fractions.fracMed;
      fracLarge = !!d.auto_fractions.fracLarge;
      updateFractionButtonsUI();
    }
    if (d.comp_jpg_b64 && el("dlgCompImg")) el("dlgCompImg").src = "data:image/jpeg;base64," + d.comp_jpg_b64;
    if (d.overlay_jpg_b64 && el("dlgOverlayImg")) el("dlgOverlayImg").src = "data:image/jpeg;base64," + d.overlay_jpg_b64;
    sessState.lastStats = d.stats || null;
    updateStageVisibility();
  } catch (err) {
    if (err && err.name === "AbortError") {
      aborted = true;
      if (el("dlgHoverHint")) el("dlgHoverHint").textContent = "Перерахунок скасовано.";
    } else {
      const msg = "Помилка перерахунку: " + (err && err.message ? err.message : String(err));
      setFooterStatus(msg, "error");
      if (el("dlgHoverHint")) el("dlgHoverHint").textContent = msg;
    }
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
    recomputeAbortCtrl = null;
    stopProgressPolling();
    hideProgressUI("modal");
    sessState.recomputing = false;
  }

  if (!aborted && sessState.pendingRecompute && sessState.open && sessState.id) {
    const nextPreserve = sessState.pendingRecomputePreserve;
    sessState.pendingRecompute = false;
    await recomputeInteractiveSession(nextPreserve);
  } else {
    sessState.pendingRecompute = false;
  }
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
  const ready = await ensureServerReadyOrPrompt();
  if (!ready) return;

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
      const jobId = makeJobId();
      const packet = encodeProcessPacket(
        { width, height, channels: components, bitDepth, hasSelection: false, jobId, params },
        rawBuf,
        null
      );
      px.imageData.dispose();
      captured = { packet, width, height, bitDepth, colorProfile, jobId };
    }, { commandName: "Читання фото Чистий Вініл Pro" });
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
  sessState.autoMask = true;
  sessState.blend = 100;
  sessState.showingOriginal = false;
  sessState.peekingClean = false;
  sessState.peekingBlend = false;
  sessState.scanAborted = false;
  sessState.isApplying = false;
  pendingApplyPayload = null;

  if (el("dlgChkAutoMask")) el("dlgChkAutoMask").checked = true;
  setSliderVal("dlgSlBlend", 100);
  updateSliderVisuals();
  if (el("dlgBtnBeforeAfter")) el("dlgBtnBeforeAfter").classList.remove("active");
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

  // Default tool = Eraser so user starts erasing extra green right away!
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

      if (res.auto_fractions) {
        fracFine = !!res.auto_fractions.fracFine;
        fracMed = !!res.auto_fractions.fracMed;
        fracLarge = !!res.auto_fractions.fracLarge;
        updateFractionButtonsUI();
      }

      if (el("dlgOrigImg")) el("dlgOrigImg").src = "data:image/jpeg;base64," + res.orig_jpg_b64;
      if (el("dlgCompImg")) el("dlgCompImg").src = "data:image/jpeg;base64," + res.comp_jpg_b64;
      if (el("dlgOverlayImg")) el("dlgOverlayImg").src = "data:image/jpeg;base64," + (res.overlay_jpg_b64 || res.comp_jpg_b64);

      resetZoomFit();
      updateStageVisibility();
      setBtnDisabled(el("dlgBtnApply"), false);
      updateProgressUI(100, "Готово!", "modal");
      setTimeout(() => hideProgressUI("modal"), 180);
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
      title: "Чистий Вініл Pro",
      resize: "both",
      size: { width: 1020, height: 740 }
    });
  } finally {
    sessState.scanAborted = true;
    stopProgressPolling();
    stopModalTimer();
    hideProgressUI("all");
    await closeServerSession();
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
        name: "Чистий Вініл Pro"
      });
      try {
        const topBefore = doc.layers && doc.layers.length > 0 ? doc.layers[0] : null;
        const newLayer = doc.createPixelLayer
          ? await doc.createPixelLayer({ name: "Чистий вініл (AI)", opacity: Math.round(blend) })
          : await doc.createLayer({ name: "Чистий вініл (AI)" });

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
    }, { commandName: "Чистий Вініл Pro" });

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

  const ready = await ensureServerReadyOrPrompt();
  if (!ready) return;

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
      const suspensionID = await executionContext.hostControl.suspendHistory({ documentID: doc.id, name: "Чистий Вініл (Виділення)" });
      try {
        await action.batchPlay([{ _obj: "set", _target: [{ _ref: "channel", _property: "selection" }], to: { _enum: "ordinal", _value: "none" } }], {});
        const topBefore = doc.layers && doc.layers.length > 0 ? doc.layers[0] : null;
        const newLayer = doc.createPixelLayer
          ? await doc.createPixelLayer({ name: "Чистий вініл (Виділення)", opacity: 100 })
          : await doc.createLayer({ name: "Чистий вініл (Виділення)" });
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
    }, { commandName: "Чистий Вініл (Виділення)" });

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
        setFooterStatus("Шар «Чистий вініл (AI)» ще не створено.", "info");
        return;
      }
      compareShowingOriginal = layer.visible;
      layer.visible = !compareShowingOriginal;
      el("btnCompare").classList.toggle("active", compareShowingOriginal);
      el("btnCompare").textContent = compareShowingOriginal ? "До / Після (Оригінал)" : "До / Після";
    }, { commandName: "До / Після (Чистий Вініл)" });
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
  el("btnRun").addEventListener("click", openInteractiveWorkspace);
  el("btnSelection").addEventListener("click", runQuickSelectionClean);
  el("btnCompare").addEventListener("click", toggleBeforeAfterInPhotoshop);
  el("btnQuickUnload").addEventListener("click", unloadVramManual);
  el("btnPanelHelp").addEventListener("click", () => {
    el("panelHelpBox").classList.toggle("visible");
  });

  // Modal Topbar Controls
  el("dlgBtnBeforeAfter").addEventListener("click", () => {
    sessState.showingOriginal = !sessState.showingOriginal;
    el("dlgBtnBeforeAfter").classList.toggle("active", sessState.showingOriginal);
    updateStageVisibility();
  });

  el("dlgChkAutoMask").addEventListener("change", () => {
    sessState.autoMask = !!el("dlgChkAutoMask").checked;
    updateStageVisibility();
  });

  el("dlgChkDress").addEventListener("change", async () => {
    dressSmoothEnabled = !!el("dlgChkDress").checked;
    updateSliderVisuals();
    scheduleSaveSettings();
    await sendDressPreviewUpdate();
    if (el("dlgHoverHint")) {
      el("dlgHoverHint").textContent = dressSmoothEnabled
        ? "✓ Рівняння одягу увімкнено (затисніть поза фото для перегляду без маски)"
        : "Рівняння одягу вимкнено (повзунок у налаштуваннях неактивний)";
    }
  });

  el("dlgChkSmoke").addEventListener("change", async () => {
    smokeEnabled = !!el("dlgChkSmoke").checked;
    updateSliderVisuals();
    scheduleSaveSettings();
    if (sessState.open && sessState.id) {
      await recomputeInteractiveSession(true);
    }
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
      cfg: readCurrentConfig()
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
  });
  el("gBtnSmoke").addEventListener("click", () => {
    smokeEnabled = !smokeEnabled;
    updateSliderVisuals();
    scheduleSaveSettings();
  });
  el("gBtnDress").addEventListener("click", async () => {
    dressSmoothEnabled = !dressSmoothEnabled;
    updateSliderVisuals();
    scheduleSaveSettings();
    if (sessState.open && sessState.id) await sendDressPreviewUpdate();
  });
  el("gChkShadow").addEventListener("change", scheduleSaveSettings);
  el("gChkRemoveStands").addEventListener("change", scheduleSaveSettings);
  el("gBtnRecompute").addEventListener("click", async () => {
    el("dlgGearPopover").classList.remove("visible");
    const active = presetsList.find((p) => p.id === activePresetId);
    if (active && !active.builtin) {
      await saveCurrentConfigToActivePreset(false);
    }
    await recomputeInteractiveSession(true);
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

  el("dlgToolBrush").addEventListener("click", async (e) => {
    setActiveTool("brush");
    if (e.ctrlKey || e.metaKey) {
      await sendMaskEditOp("fill");
    }
  });

  el("dlgToolEraser").addEventListener("click", async (e) => {
    setActiveTool("eraser");
    if (e.ctrlKey || e.metaKey) {
      await sendMaskEditOp("clear");
    }
  });

  el("dlgToolInvert").addEventListener("click", async () => {
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
    } else if (e.key === "e" || e.key === "E" || e.key === "у" || e.key === "У") {
      setActiveTool("eraser");
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
  el("dlgFracFine").addEventListener("click", async () => {
    fracAuto = false;
    fracFine = !fracFine;
    updateFractionButtonsUI();
    scheduleSaveSettings();
    await recomputeInteractiveSession(true);
  });
  el("dlgFracMed").addEventListener("click", async () => {
    fracAuto = false;
    fracMed = !fracMed;
    updateFractionButtonsUI();
    scheduleSaveSettings();
    await recomputeInteractiveSession(true);
  });
  el("dlgFracLarge").addEventListener("click", async () => {
    fracAuto = false;
    fracLarge = !fracLarge;
    updateFractionButtonsUI();
    scheduleSaveSettings();
    await recomputeInteractiveSession(true);
  });
  el("dlgFracAuto").addEventListener("click", async () => {
    fracAuto = !fracAuto;
    updateFractionButtonsUI();
    scheduleSaveSettings();
    if (fracAuto) await recomputeInteractiveSession(true);
  });

  el("dlgSpeedPill").addEventListener("click", async () => {
    speedMode = speedMode === "fast" ? "quality" : "fast";
    updateFractionButtonsUI();
    scheduleSaveSettings();
    await recomputeInteractiveSession(true);
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
    if (sessState.recomputing && sessState.id) {
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
