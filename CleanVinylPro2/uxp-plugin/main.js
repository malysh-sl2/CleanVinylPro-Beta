const { app, core, imaging, action, constants } = require("photoshop");
const uxp = require("uxp");
const uxpFs = uxp.storage.localFileSystem;
const uxpShell = uxp.shell;

const CANDIDATE_URLS = ["http://127.0.0.1:18746", "http://localhost:18746"];
// The same number as in manifest.json and server.py. A server of another version still answers (for example the
// previous one that was left running after an update) - the panel then says how to restart it.
const PLUGIN_VERSION = "4.12.0";
let SERVER_URL = CANDIDATE_URLS[0];

const DEFAULT_PRESETS = [
  {
    id: "std",
    name: "Студія (Стандарт)",
    color: "#4da3ff",
    builtin: true,
    cfg: { spots: 75, scuffs: 65, blur: 0, cycCurve: 65, feather: 60, seamOn: true, seam: 85, edge: 70, smokeOn: false, smoke: 80, grain: 90, shadow: true, removeStands: false, master: 100, fracFine: true, fracMed: true, fracLarge: true, dressSmooth: false, dressStrength: 45, cleanPasses: 1 }
  },
  {
    id: "medium_shot",
    name: "Середній план",
    color: "#59b5ff",
    builtin: true,
    cfg: { spots: 75, scuffs: 65, blur: 10, cycCurve: 65, feather: 65, seamOn: true, seam: 78, edge: 74, smokeOn: false, smoke: 80, grain: 92, shadow: true, removeStands: false, master: 100, fracFine: true, fracMed: true, fracLarge: true, dressSmooth: false, dressStrength: 45, cleanPasses: 1 }
  },
  {
    id: "closeup",
    name: "Ближній план",
    color: "#3bc9db",
    builtin: true,
    cfg: { spots: 62, scuffs: 48, blur: 18, cycCurve: 0, feather: 78, seamOn: false, seam: 0, edge: 84, smokeOn: false, smoke: 80, grain: 94, shadow: true, removeStands: false, master: 100, fracFine: true, fracMed: true, fracLarge: false, dressSmooth: false, dressStrength: 35, cleanPasses: 1 }
  },
  {
    id: "wide_shot",
    name: "Дальній план",
    color: "#7c8cff",
    builtin: true,
    cfg: { spots: 85, scuffs: 78, blur: 0, cycCurve: 65, feather: 55, seamOn: true, seam: 90, edge: 66, smokeOn: false, smoke: 80, grain: 90, shadow: true, removeStands: false, master: 100, fracFine: true, fracMed: true, fracLarge: true, dressSmooth: false, dressStrength: 45, cleanPasses: 1 }
  },
  {
    id: "lowkey",
    name: "Темний ключ",
    color: "#9d7cff",
    builtin: true,
    cfg: { spots: 80, scuffs: 55, blur: 0, cycCurve: 65, feather: 65, seamOn: true, seam: 90, edge: 78, smokeOn: false, smoke: 70, grain: 95, shadow: true, removeStands: false, master: 100, fracFine: true, fracMed: true, fracLarge: true, dressSmooth: false, dressStrength: 40, cleanPasses: 1 }
  },
  {
    id: "lowkey_medium",
    name: "Темний середній план",
    color: "#b190ff",
    builtin: true,
    cfg: { spots: 72, scuffs: 50, blur: 0, cycCurve: 65, feather: 68, seamOn: true, seam: 80, edge: 82, smokeOn: false, smoke: 70, grain: 95, shadow: true, removeStands: false, master: 100, fracFine: true, fracMed: true, fracLarge: true, dressSmooth: false, dressStrength: 40, cleanPasses: 1 }
  },
  {
    id: "lowkey_close",
    name: "Темний ближній план",
    color: "#c7a6ff",
    builtin: true,
    cfg: { spots: 62, scuffs: 45, blur: 0, cycCurve: 0, feather: 78, seamOn: false, seam: 0, edge: 86, smokeOn: false, smoke: 70, grain: 95, shadow: true, removeStands: false, master: 100, fracFine: true, fracMed: true, fracLarge: false, dressSmooth: false, dressStrength: 35, cleanPasses: 1 }
  },
  {
    id: "lowkey_wide",
    name: "Темний дальній план",
    color: "#8468e8",
    builtin: true,
    cfg: { spots: 80, scuffs: 55, blur: 0, cycCurve: 65, feather: 65, seamOn: true, seam: 90, edge: 78, smokeOn: false, smoke: 70, grain: 95, shadow: true, removeStands: false, master: 100, fracFine: true, fracMed: true, fracLarge: true, dressSmooth: false, dressStrength: 40, cleanPasses: 1 }
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
    cfg: { spots: 78, scuffs: 70, blur: 0, cycCurve: 65, feather: 60, seamOn: true, seam: 85, edge: 72, smokeOn: false, smoke: 80, grain: 90, shadow: true, removeStands: true, master: 100, fracFine: true, fracMed: true, fracLarge: true, dressSmooth: false, dressStrength: 45, cleanPasses: 1 }
  },
  {
    id: "gentle",
    name: "Делікатний (точки)",
    color: "#e57399",
    builtin: true,
    cfg: { spots: 60, scuffs: 25, blur: 0, cycCurve: 0, feather: 65, seamOn: false, seam: 0, edge: 85, smokeOn: false, smoke: 85, grain: 95, shadow: true, removeStands: false, master: 90, fracFine: true, fracMed: false, fracLarge: false, dressSmooth: false, dressStrength: 35, cleanPasses: 1 }
  }
];

let presetsList = JSON.parse(JSON.stringify(DEFAULT_PRESETS));
let activePresetId = presetsList[0].id;
let presetsEditMode = false;
let seamEnabled = true;
let smokeEnabled = false; // smoke is looked for and protected only when asked: the checkbox, or the preset "Зйомка з димом"
let fracFine = true;
let fracMed = true;
let fracLarge = true;
let fracAuto = true;      // the AUTO button of the fractions as it is right now
let fracAutoUser = true;  // ...and as the user left it (a preset that names its fractions switches AUTO off for a while)
let autoPreset = true;    // pick the preset that suits the frame every time the big window opens
// "Detailed preview" (a checkbox in the settings of the big window). Off - the way the window worked up to 4.7.0
// and the default again since 4.10.0: the window gets pictures of the working size (in a large window the person
// looks a little soft; the layer is not affected) and after a change it shows the quick preview; the real frame is
// computed by "Застосувати" or by the button "↻ Перерахувати зараз". On - what 4.8.0 brought: pictures twice as
// detailed and the exact picture by itself, in the background. On the owner's PC the brush was slow with it (every
// answer to a stroke is 1.7 MB instead of 0.5) and a preview took one to seven minutes. Which part cost the time
// there is not known - it cannot be measured without his Photoshop; he asked for the former way back.
let detailPreview = false;
const PREVIEW_LONG_FAST = 1080;     // "previewLong" of the start request: the working pictures themselves
const PREVIEW_LONG_DETAIL = 2160;
// The trace of a stroke (renderBrushCursorAndDot): the gap between two mouse events is filled with dots this far
// apart (a share of the brush diameter, at least so many pixels); so many per event and per stroke at most.
const STROKE_DOT_STEP = 0.3;
const STROKE_DOT_MIN_PX = 3;
const STROKE_DOTS_PER_MOVE = 120;
const STROKE_DOTS_MAX = 1500;
let dressSmoothEnabled = false;
// "Мікс-пензель" (since 4.12.0): after the cleaning the server goes over the backdrop the way a retoucher does with
// a wide soft mixer brush. The switch and its strength (slider gSlMix) are the user's own, like "Make Mask": no
// preset changes them, so the tick stays as it was put for every frame and every preset.
let mixEnabled = false;
let cleanPasses = 1;
// How the found defects are closed. One way is left: the full AI fill (what used to be the mode "✦ Якісний").
// The fast mode and its button were removed in 4.7.0 at the owner's request; a "fast" kept in settings or presets
// that an older version saved is ignored. (The light preview after a slider move is still drawn the fast way by
// the server - that is the server's own business and does not depend on this value.)
const speedMode = "quality";
// How long the AI models stay in GPU memory after the last job. 2 minutes: long enough to retouch the
// result and come back for the next frame without paying for the model reload again.
const DEFAULT_IDLE_UNLOAD_SEC = 120;
const LEGACY_IDLE_UNLOAD_SEC = 30; // default of settings schema <= 4
const SETTINGS_SCHEMA_VERSION = 5;
let idleUnloadSec = DEFAULT_IDLE_UNLOAD_SEC;
let settingsMigrated = false;
// Built-in presets are kept on the PC the way they were first seen, so a default that changes in a new version
// would never reach an installed copy. Each entry moves one value, once: in the listed built-in presets, and on
// the slider itself when one of those presets is the active one - and only where the stored value is still the
// former default (a value the user chose stays). The moves already made are remembered in the settings.
// (a move of a switch has no slider: the switch is found by the key in PRESET_SWITCHES)
const PRESET_DEFAULT_MOVES = [
  // 4.4.0: the wall-floor line is removed by default wherever a floor is usually in the frame
  { id: "cyc65", presets: ["std", "medium_shot", "wide_shot", "clean_stands"], key: "cycCurve", slider: "gSlCyc", from: 0, to: 65 },
  // 4.5.0: smoke protection is off until it is asked for ("Зйомка з димом" keeps it)
  { id: "smokeOff", presets: ["std", "medium_shot", "closeup", "wide_shot", "lowkey", "clean_stands", "gentle"], key: "smokeOn", from: true, to: false },
  // 4.5.0: dust is judged against the noise of each part of the frame; on a dark backdrop 92 marks plain noise
  { id: "lowkeySpots80", presets: ["lowkey"], key: "spots", slider: "gSlSpots", from: 92, to: 80 },
  // 4.5.0: ...and the wall-floor line goes on a dark backdrop as well
  { id: "lowkeyCyc65", presets: ["lowkey"], key: "cycCurve", slider: "gSlCyc", from: 0, to: 65 }
];
const PRESET_SWITCHES = {
  smokeOn: { get: () => smokeEnabled, set: (v) => { smokeEnabled = !!v; } }
};
let appliedPresetMoves = [];
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
  // The edge of the brush and the eraser: soft (a stroke fades out, no stripe and no sharp step) or hard (it ends
  // about where the cursor circle is). Soft unless the user chose otherwise; kept with the settings.
  brushSoft: true,
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
  strokeNo: 0,      // counts the strokes of this window: every dot of the trace knows the stroke it belongs to
  strokeDots: [],   // the dots on screen: { node, stroke }
  scanAborted: false,
  isApplying: false,
  recomputing: false,
  // Steps of the mask edits (brush, eraser, fill, clear, invert) that can be taken back / made again. The server
  // keeps the history and says the two numbers with every answer about the mask.
  history: { undo: 0, redo: 0 },
  previewTimer: null,      // the light refresh of the preview that waits for its moment
  previewBusy: false,      // a light refresh is running right now
  previewSyncedSig: "",    // the settings the preview on screen was made for
  previewForce: false,     // refresh even if the settings look the same (AUTO fractions were asked for again)
  quickUnsupported: false, // the running server is an older build that only knows the full recompute
  // The exact picture comes by itself (see scheduleExactPreview): after a light refresh the server computes the
  // real frame in the background, and the window puts the exact picture in place of the quick one.
  picRev: 0,               // number of the pictures on screen, as the server counts them (see takeSessionPictures)
  syncRev: 0,              // ...and of the last recompute whose settings the window took over
  exactShown: true,        // the picture on screen is the exact one: the real frame was computed for it
  exactTimer: null,        // the background recompute that waits for a quiet moment
  exactSig: "",            // the settings the latest background recompute was asked for
  exactJob: null,          // its progress job
  exactPct: null,          // ...and its progress, percent
  exactPollTimer: null,
  exactPollBusy: false,
  exactError: "",          // why the last one failed (it is not tried again until something changes)
  exactHold: false,        // the server declined: the mask is the user's own drawing (asked again after the next answer)
  bgUnsupported: false,    // the running server is an older build that has no background recompute
  lastStats: null,
  maskShare: null,         // share of the frame where defects were found (bright green), as the server last reported it
  presetNote: null,        // a preset was just clicked: say what it changed when the refresh comes back
  smokeNote: false,        // a smoke control was just used: say what the server saw of smoke when the refresh comes back
  note: "",                // short message in the corner of the photo (which preset was picked and why)
  cpuWarn: "",             // ...and the warning that the AI fill ran on the processor (it goes before the note)
  cpuWarnTimer: null,
  noteTimer: null
};
let pendingApplyPayload = null;

// The preview follows the sliders by itself: once, shortly after the last change, and never while a slider is
// still being dragged. That refresh is light (the server redraws only the preview) and shows at once. The exact
// picture - the real frame, computed in full - follows by itself: once the window has been quiet for
// EXACT_DELAY_MS, the server computes it in the background (see scheduleExactPreview). No button has to be pressed.
const PREVIEW_DELAY_SLIDER_MS = 450;
const PREVIEW_DELAY_CLICK_MS = 150;
const EXACT_DELAY_MS = 700;
const EXACT_POLL_MS = 350;
// Background recomputes that are on their way. (A set per window: an answer that comes after its window was
// closed must not be counted for the next one.)
let exactJobs = new Set();

// Custom Drag-Only Sliders
const ALL_SLIDER_IDS = [
  "dlgSlBlend",
  "gSlSpots", "gSlHair", "gSlScuffs", "gSlBlur", "gSlMix", "gSlCyc", "gSlFeather",
  "gSlSeam", "gSlEdge", "gSlSmoke", "gSlGrain",
  "gSlDress", "gSlTurbo"
];
const SLIDER_VAL_MAP = {
  dlgSlBlend: "dlgValBlend",
  gSlSpots: "gValSpots",
  gSlHair: "gValHair",
  gSlScuffs: "gValScuffs",
  gSlBlur: "gValBlur",
  gSlMix: "gValMix",
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
  gSlHair: 0,
  gSlScuffs: 65,
  gSlBlur: 0,
  gSlMix: 50,
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
  "💡 Кнопка «Маска»: яскраво-зелене — знайдені дефекти, блідо-зелене — фон, який вирівнюється. Гумка (E) стирає зайве зелене з одягу, взуття або тіней.",
  "💡 Пензлем і гумкою можна працювати просто по чистому фото: відпустили мишку — результат одразу видно. Зелену маску вмикає кнопка «Маска».",
  "💡 Розводи й сліди на підлозі вирівнюються аж до самих ніг, тіні лишаються. Лінію стіна–підлога прибирає «Циклорама»; щоб лишити її — поставте 0%.",
  "💡 Пресет підбирається сам під кадр: темний фон, ближній, середній план чи повний зріст. Іншої думки — виберіть свій у списку.",
  "💡 Ctrl + Клік по іконці Пензля (B) показує шар на всьому кадрі; Ctrl + Клік по Гумці (E) — повністю очищає маску.",
  "💡 Увімкніть іконку сукні зверху, щоб AI делікатно розгладив різкі складки на одязі без впливу на шкіру й волосся.",
  "💡 Натисніть квадратики фракцій знизу (Дрібна / Середня / Велика), щоб швидко вмикати або вимикати типи чистки.",
  "💡 Зум: колесо миші або Ctrl + «+» / Ctrl + «−», як у Photoshop; Ctrl + 0 — вписати фото у вікно. Рухати наближене фото: затисніть праву кнопку миші й тягніть (або Пробіл + мишка).",
  "💡 Гарячі клавіші [ і ] миттєво зменшують або збільшують розмір пензля й гумки.",
  "💡 Поодинокі волосини, що стирчать із зачіски, прибирає повзунок «Волоски довкола зачіски» у тонких налаштуваннях. Він вимкнений, доки його не зрушити; зайве повертає Гумка (E).",
  "💡 Поставте галочку «Make Mask» зверху, якщо хочете отримати у Photoshop редаговану маску шару.",
  "💡 Якщо на фоні є стійки, кабелі чи прилади — увімкніть їх видалення в налаштуваннях (шестигранник) або пресеті «Без стійок (AI)».",
  "💡 Пензель і гумка мають м’який край — без смуги й різкого переходу. Потрібен чіткий край — нижній кружечок під розміром пензля.",
  "💡 Щойно відпустите повзунок, вікно показує швидкий перегляд; точний кадр рахує «Застосувати». Чіткіше фото у вікні й точний перерахунок сам вмикає галочка «Детальний перегляд» у налаштуваннях — це повільніше."
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
    // Single hairs that stick out of the hairdo; 0 = the tool is off (and it is 0 in every built-in preset)
    strayHair: getSliderVal("gSlHair"),
    scuffs: getSliderVal("gSlScuffs"),
    blur: getSliderVal("gSlBlur"),
    mixOn: mixEnabled,
    mix: getSliderVal("gSlMix"),
    cycCurve: getSliderVal("gSlCyc"),
    feather: getSliderVal("gSlFeather"),
    seamOn: seamEnabled,
    seam: getSliderVal("gSlSeam"),
    edge: getSliderVal("gSlEdge"),
    smokeOn: smokeEnabled,
    smoke: getSliderVal("gSlSmoke"),
    // The smoke switch is the user's word - "this frame has smoke": the server asks for no evidence and looks for
    // thin smoke as well (smokeFaint, since 4.11.0), and says how much of the frame it keeps (see smokeNoteText).
    // smokeAuto is what a server before 4.11.0 understands: smoke protected only when the frame has enough of it.
    smokeAuto: true,
    smokeFaint: true,
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
    strayHair: clampSliderVal("gSlHair", c.strayHair ?? 0),
    scuffs: clampSliderVal("gSlScuffs", c.scuffs ?? 65),
    blur: clampSliderVal("gSlBlur", c.blur ?? 0),
    // (the mixer brush is not a matter of the preset: every set carries what the user has put)
    mixOn: mixEnabled,
    mix: getSliderVal("gSlMix"),
    cycCurve: clampSliderVal("gSlCyc", c.cycCurve ?? 0),
    feather: clampSliderVal("gSlFeather", c.feather ?? 60),
    seamOn: flag(c.seamOn, true),
    seam: clampSliderVal("gSlSeam", c.seam ?? 85),
    edge: clampSliderVal("gSlEdge", c.edge ?? 70),
    smokeOn: flag(c.smokeOn, false),
    smoke: clampSliderVal("gSlSmoke", c.smoke ?? 80),
    smokeAuto: true,
    smokeFaint: true,
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
  setSliderVal("gSlHair", c.strayHair);
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
  const cfg = Object.assign(readCurrentConfig(), { fracAuto });
  delete cfg.mixOn;  // (the mixer brush is the user's own switch, not a part of any preset - see mixEnabled)
  delete cfg.mix;
  return cfg;
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
// by id: a renamed or edited one keeps working, a deleted one is simply not offered. On a dark backdrop the server
// tries "dark_<framing>", then "dark", then the framing, then "default"; on a light one the framing, then "default".
const AUTO_PRESET_BY_SCENE = {
  dark_close: "lowkey_close", dark_medium: "lowkey_medium", dark_wide: "lowkey_wide", dark: "lowkey",
  close: "closeup", medium: "medium_shot", wide: "wide_shot", default: "std"
};
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
  const framing = (scene && scene.framing) || "none";
  let seen = SCENE_WORDS[framing] || SCENE_WORDS.none;
  if (scene && scene.dark) seen = SCENE_WORDS[framing] && framing !== "none" ? `${SCENE_WORDS.dark}, ${SCENE_WORDS[framing]}` : SCENE_WORDS.dark;
  return `Авто-пресет: «${preset.name}» — ${seen}. Інший можна вибрати у списку пресетів.`;
}

function setAutoPreset(on) {
  autoPreset = !!on;
  if (el("dlgChkAutoPreset")) el("dlgChkAutoPreset").checked = autoPreset;
}

// The button of the exact picture says what it is for: with the detailed preview the same picture comes by itself.
// The note at the top of the settings says what happens after a slider is released.
function updateRecomputeButton() {
  const note = el("gLiveNote");
  if (note) {
    note.textContent = detailPreview
      ? "Перегляд перераховується сам: щойно відпустите повзунок — швидко, а потім точно, для всього кадру (поки рахується, у кутку фото написано «уточнюється»). Жодної кнопки натискати не треба."
      : "Щойно відпустите повзунок — вікно показує швидкий перегляд. Точний кадр, для всього фото, рахує «Застосувати» або кнопка «↻ Перерахувати» внизу вікна.";
  }
  const btn = el("gBtnRecompute");
  if (!btn) return;
  btn.textContent = detailPreview ? "↻ Перерахувати зараз (не обов’язково)" : "↻ Перерахувати зараз (точний перегляд)";
  btn.setAttribute("data-tip", detailPreview
    ? "Необов’язкова кнопка: з «Детальним переглядом» перегляд і так перераховується сам після кожної зміни — спершу швидко, а потім точно, для всього кадру. Кнопка робить той самий точний розрахунок негайно, з вікном прогресу."
    : "Точний перегляд — програма рахує справжній кадр для всього фото, з вікном прогресу. Після зміни повзунка вікно показує швидкий перегляд; ця кнопка потрібна, якщо хочете побачити точний результат ще до «Застосувати». «Застосувати» і так рахує точний кадр.");
}

// "Детальний перегляд" on / off (see detailPreview). The exact picture by itself starts or stops at once; the size
// of the window pictures is fixed when the window opens, so that part shows from the next opening.
function setDetailPreview(on, announce = true) {
  detailPreview = !!on;
  if (el("gChkDetail")) el("gChkDetail").checked = detailPreview;
  updateRecomputeButton();
  if (sessState.open && sessState.id) {
    if (detailPreview) {
      scheduleExactPreview();
    } else {
      cancelExactTimer();
      stopBackgroundRun();  // a run that is on its way is of no use any more: the computer is free at once
      updatePreviewBadge();
      updateModeBadge();
    }
  }
  if (announce) {
    sayInWindow(detailPreview
      ? "✓ Детальний перегляд увімкнено: точний кадр рахується сам після кожної зміни — це повільніше. Чіткіше фото у вікні — з наступного відкриття вікна."
      : "Детальний перегляд вимкнено: вікно працює швидко. Точний кадр рахує «Застосувати» або кнопка «↻ Перерахувати зараз». М’якше фото у вікні — з наступного відкриття вікна.");
  }
}

function secondsText(s) {
  const v = Math.max(0, Number(s) || 0);
  return (v < 10 ? v.toFixed(1).replace(".", ",") : String(Math.round(v))) + " с";
}

function cpuFallbackText(why) {
  return "⚠ AI-модель щойно рахувала на процесорі, а не на відеокарті — це в багато разів повільніше. Причина: " +
    String(why).slice(0, 160) + ". Якщо повторюється — закрийте програми, що займають відеопам’ять, або перезапустіть сервер (restart_gpu_server.bat).";
}

function fillTimeText(t) {
  const onCpu = String(t.fill_ep || "").includes("CPU");
  return `AI-заливка: ${t.fill_tiles} пл. за ${secondsText(t.fill_s)} (${onCpu ? "процесор" : "відеокарта"})`;
}

// What the last computation of the frame took: a line in the settings of the big window. When a video card is there
// and the AI fill ran on the processor all the same (the card refused a tile - see _lama_on_cpu of the engine), the
// window says so in the corner of the photo: that is what "a preview takes minutes" usually is.
function noteComputeStats(stats) {
  const t = stats && stats.timing;
  if (!t || !t.fill_tiles) return;
  const onCpu = String(t.fill_ep || "").includes("CPU");
  const why = t.fallback && (t.fallback.lama || t.fallback.matting);
  const line = el("gTimeLine");
  if (line) {
    const whole = typeof stats.elapsed_ms === "number" ? `Останній розрахунок: ${secondsText(stats.elapsed_ms / 1000)} · ` : "";
    line.textContent = whole + fillTimeText(t);
    line.classList.toggle("warn", onCpu);
  }
  if (why) {
    sessState.cpuWarn = cpuFallbackText(why);
    if (sessState.cpuWarnTimer) clearTimeout(sessState.cpuWarnTimer);
    sessState.cpuWarnTimer = setTimeout(() => {
      sessState.cpuWarnTimer = null;
      sessState.cpuWarn = "";
      updatePreviewBadge();
    }, 20000);
    updatePreviewBadge();
  }
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
    } else if (id === "gSlMix") {
      badge.textContent = mixEnabled ? v + "%" : "Вимк.";
    } else if (id === "gSlDress") {
      badge.textContent = dressSmoothEnabled ? v + "%" : "Вимк.";
    } else if (id === "gSlHair") {
      badge.textContent = v > 0 ? v + "%" : "Вимк.";
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

  if (el("gBtnMix")) {
    el("gBtnMix").textContent = mixEnabled ? "Увімк." : "Вимк.";
    el("gBtnMix").className = "toggle-pill" + (mixEnabled ? " on" : "");
  }
  if (el("dlgChkMix")) el("dlgChkMix").checked = mixEnabled;
  if (el("dlgWrapMix")) el("dlgWrapMix").classList.toggle("active", mixEnabled);
  setSliderDisabled("gSlMix", !mixEnabled);

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
    detailPreview,
    mixOn: mixEnabled,
    mixStrength: getSliderVal("gSlMix"),
    brushSize: sessState.brushSize,
    brushSoft: sessState.brushSoft,
    deletedDefaultIds: Array.from(new Set(deletedDefaultIds)),
    knownDefaultIds: Array.from(new Set(knownDefaultIds)),
    presetMoves: Array.from(new Set(appliedPresetMoves))
  };
}

function applySettingsSnapshot(s) {
  if (!s || typeof s !== "object") return;
  if (Array.isArray(s.deletedDefaultIds)) deletedDefaultIds = Array.from(new Set(s.deletedDefaultIds));
  if (Array.isArray(s.knownDefaultIds)) knownDefaultIds = Array.from(new Set(s.knownDefaultIds));
  // (settings saved by an older version carry no list: every move is still to be made - applyPresetDefaultMoves)
  appliedPresetMoves = Array.isArray(s.presetMoves) ? Array.from(new Set(s.presetMoves.filter((x) => typeof x === "string"))) : [];
  // (s.speedMode of an older version is not read: there is one mode now)
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
  if (typeof s.detailPreview === "boolean") setDetailPreview(s.detailPreview, false);
  if (typeof s.brushSize === "number" && s.brushSize >= 4) sessState.brushSize = Math.round(s.brushSize);
  if (typeof s.brushSoft === "boolean") setBrushSoft(s.brushSoft, false);
  if (typeof s.mixOn === "boolean") mixEnabled = s.mixOn;
  if (typeof s.mixStrength === "number" && Number.isFinite(s.mixStrength)) setSliderVal("gSlMix", s.mixStrength);
  if (s.activePresetId && presetsList.some((p) => p.id === s.activePresetId)) activePresetId = s.activePresetId;
  if (s.cfg && typeof s.cfg === "object") applyConfig(s.cfg);
  else updateSliderVisuals();
}

function appendNewDefaultPresets() {
  if (knownDefaultIds.length === 0 && hasLocalPresets) {
    knownDefaultIds = ["std", "lowkey", "smoke", "clean_stands", "gentle"];
  }
  let added = false;
  DEFAULT_PRESETS.forEach((dp, i) => {
    const already = presetsList.some((p) => p.id === dp.id);
    const del = deletedDefaultIds.includes(dp.id);
    const known = knownDefaultIds.includes(dp.id);
    if (!already && !del && !known) {
      // A new built-in preset goes right under the built-in one it follows in the default list (the dark presets
      // by framing land under "Темний ключ"); at the end of the list when none of those is there any more.
      let at = -1;
      for (let k = i - 1; k >= 0 && at < 0; k--) at = presetsList.findIndex((p) => p.id === DEFAULT_PRESETS[k].id);
      const copy = JSON.parse(JSON.stringify(dp));
      if (at >= 0) presetsList.splice(at + 1, 0, copy);
      else presetsList.push(copy);
      added = true;
    }
    if (!known) knownDefaultIds.push(dp.id);
  });
  return added;
}

// Makes the moves of PRESET_DEFAULT_MOVES that were not made yet. Call it once the presets and the settings are
// loaded. Returns true when a preset or a slider was changed (the caller saves).
function applyPresetDefaultMoves() {
  let changed = false;
  PRESET_DEFAULT_MOVES.forEach((m) => {
    if (appliedPresetMoves.includes(m.id)) return;
    appliedPresetMoves.push(m.id);
    const isFormer = (v) => (typeof m.from === "boolean" ? !!v === m.from : Number(v) === m.from);
    presetsList.forEach((p) => {
      if (!p || !p.builtin || !p.cfg || !m.presets.includes(p.id)) return;
      if (!isFormer(p.cfg[m.key] ?? m.from)) return;
      p.cfg[m.key] = m.to;
      changed = true;
    });
    if (!m.presets.includes(activePresetId)) return;
    const sw = PRESET_SWITCHES[m.key];
    if (m.slider && getSliderVal(m.slider) === m.from) {
      setSliderVal(m.slider, m.to);
      changed = true;
    } else if (!m.slider && sw && sw.get() === m.from) {
      sw.set(m.to);
      changed = true;
    }
  });
  return changed;
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

    if (applyPresetDefaultMoves()) {
      changed = true;
      updateSliderVisuals();
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
    if (el("gBtnResetPreset")) {
      const shortName = active.name.length > 20 ? active.name.slice(0, 19) + "…" : active.name;
      const canReset = !!defaultPresetOf(active.id);
      const armed = canReset && resetPresetArmedId === active.id;
      el("gBtnResetPreset").textContent = armed
        ? `Натисніть ще раз — скинути «${shortName}»`
        : canReset ? `↺ Скинути «${shortName}» до стандартних` : "↺ Скинути до стандартних (не для власних пресетів)";
      el("gBtnResetPreset").classList.toggle("is-dim", !canReset);
      el("gBtnResetPreset").classList.toggle("armed", armed);
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
          } else if (info.cpu_fallback && (info.cpu_fallback.lama || info.cpu_fallback.matting)) {
            // a video card is there, and the last run went to the processor all the same
            showBanner(cpuFallbackText(info.cpu_fallback.lama || info.cpu_fallback.matting), "info");
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
// Backup of everything the plugin remembers (presets + settings) into a file, and back
// ------------------------------------------------------------------
// The plugin may write only into its own data folder, and a reinstall of Photoshop can wipe that one. So the file
// is written by the server into <program folder>/backup; the panel shows where it is and can open the folder.
// A file put into that folder by hand (from another PC, from a flash drive) is offered for a restore as well.
let backupBusy = false;
let backupArmedFile = null;  // the backup whose line was clicked once (the second click restores it)

// "2026-11-19T08:35:12" -> "19.11.2026 08:35"
function backupStamp(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(String(iso || ""));
  return m ? `${m[3]}.${m[2]}.${m[1]} ${m[4]}:${m[5]}` : String(iso || "");
}

async function backupFetch(path, body) {
  let r;
  try {
    r = await fetch(`${SERVER_URL}${path}`, body === undefined ? undefined : {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
  } catch (_) {
    throw new Error("сервер не відповідає. Перевірте, чи він запущений (індикатор угорі панелі).");
  }
  let d = null;
  try { d = await r.json(); } catch (_) {}
  if (r.status === 404 && !(d && d.error)) {
    throw new Error("запущено стару версію сервера, вона ще не вміє робити бекапи. Перезапустіть сервер (restart_gpu_server.bat) і повторіть.");
  }
  if (!r.ok || !d || d.ok === false) throw new Error((d && d.error) || `помилка сервера (${r.status})`);
  return d;
}

// The box under the two backup buttons: a few lines of text (one <div> per line) and, for a restore, the list
function showBackupBox(mode, lines, backups, folder) {
  const box = el("panelBackupBox");
  if (!box) return;
  const textEl = el("backupBoxText");
  textEl.innerHTML = "";
  (lines || []).forEach((line) => {
    const row = document.createElement("div");
    row.className = line.path ? "backup-path" : "backup-line";
    row.textContent = line.path || line;
    textEl.appendChild(row);
  });
  const listEl = el("backupList");
  listEl.innerHTML = "";
  (backups || []).forEach((b) => {
    const row = document.createElement("div");
    row.setAttribute("role", "button");
    row.tabIndex = 0;
    const armed = backupArmedFile === b.file;
    row.className = "backup-row" + (armed ? " armed" : "");
    const mine = b.user_presets > 0 ? ` (ваших: ${b.user_presets})` : "";
    const auto = b.label === "before-restore" ? " · копія перед відновленням" : "";
    row.textContent = armed
      ? `Натисніть ще раз — відновити бекап від ${backupStamp(b.saved_at)}`
      : `${backupStamp(b.saved_at)} · пресетів: ${b.presets}${mine}${auto}`;
    row.addEventListener("click", () => onBackupRowClick(b, backups, folder));
    listEl.appendChild(row);
  });
  box.dataset.mode = mode;
  box.classList.add("visible");
}

function hideBackupBox() {
  backupArmedFile = null;
  const box = el("panelBackupBox");
  if (!box) return;
  box.dataset.mode = "";
  box.classList.remove("visible");
}

function backupPayload(label) {
  return { presets: presetsList, settings: buildSettingsSnapshot(), label: label || "" };
}

// "💾 Бекап налаштувань"
async function saveSettingsBackup() {
  if (backupBusy) return;
  const ready = await ensureServerForAction("btnBackupSave", "Бекап");
  if (!ready || backupBusy) return;
  backupBusy = true;
  try {
    const d = await backupFetch("/backup/save", backupPayload(""));
    backupArmedFile = null;
    setFooterStatus(`✓ Бекап збережено: пресетів ${d.presets}${d.user_presets > 0 ? ` (ваших: ${d.user_presets})` : ""} і всі налаштування.`, "success");
    showBackupBox("saved", [
      "Файл бекапа:",
      { path: d.path },
      "Тримайте його копію ще й на іншому диску чи флешці — тоді налаштування переживуть і перевстановлення Windows.",
      "Щоб відновити: покладіть файл у цю саму папку й натисніть «📂 Відновити»."
    ], [], d.folder);
  } catch (err) {
    setFooterStatus("Бекап не збережено: " + (err && err.message ? err.message : String(err)), "error");
  } finally {
    backupBusy = false;
  }
}

function showBackupList(backups, folder) {
  const lines = backups.length > 0
    ? ["Виберіть бекап. Поточні пресети й налаштування буде замінено тими, що у файлі; їхня копія збережеться поруч сама."]
    : ["Бекапів ще немає. Папка для них:", { path: folder }, "Натисніть «💾 Бекап налаштувань» — або покладіть сюди файл бекапа й натисніть «📂 Відновити» ще раз."];
  showBackupBox("list", lines, backups, folder);
}

// "📂 Відновити": shows the backups of the folder (a second press hides the list)
async function openBackupList() {
  if (backupBusy) return;
  const box = el("panelBackupBox");
  if (box && box.classList.contains("visible") && box.dataset.mode === "list") {
    hideBackupBox();
    return;
  }
  const ready = await ensureServerForAction("btnBackupRestore", "Список бекапів");
  if (!ready || backupBusy) return;
  backupBusy = true;
  try {
    const d = await backupFetch("/backup/list");
    backupArmedFile = null;
    showBackupList(Array.isArray(d.backups) ? d.backups : [], d.folder || "");
    setFooterStatus("");
  } catch (err) {
    setFooterStatus("Не вдалося прочитати список бекапів: " + (err && err.message ? err.message : String(err)), "error");
  } finally {
    backupBusy = false;
  }
}

// The presets and the settings of a backup in place of the current ones. False: the file holds nothing usable.
async function applySettingsBackup(d) {
  const list = Array.isArray(d && d.presets_list)
    ? d.presets_list.filter((x) => x && typeof x === "object" && x.id && x.name && x.cfg && typeof x.cfg === "object")
    : [];
  if (list.length === 0 || !d.settings || typeof d.settings !== "object") return false;
  presetsList = JSON.parse(JSON.stringify(list));
  hasLocalPresets = true;
  hasLocalSettings = true;
  activePresetId = presetsList[0].id;
  deletedDefaultIds = [];
  knownDefaultIds = [];
  applySettingsSnapshot(d.settings);
  if (!d.settings.cfg || typeof d.settings.cfg !== "object") {
    applyPreset(presetsList.find((x) => x.id === activePresetId) || presetsList[0]);
  }
  // A backup made by an older version: the defaults that changed since then, the built-in presets added since then
  applyPresetDefaultMoves();
  appendNewDefaultPresets();
  settingsMigrated = false;
  renderPresets();
  updateSliderVisuals();
  updateFractionButtonsUI();
  await persistPresets();
  await persistSettingsNow();
  return true;
}

// A line of the list: the first click asks for one more, the second one restores that backup
async function onBackupRowClick(b, backups, folder) {
  if (backupBusy) return;
  if (backupArmedFile !== b.file) {
    backupArmedFile = b.file;
    showBackupList(backups, folder);
    return;
  }
  backupArmedFile = null;
  backupBusy = true;
  try {
    const d = await backupFetch("/backup/read", { file: b.file });
    // What is about to be replaced is kept as one more backup (the newest few of these copies stay in the folder)
    let kept = true;
    try { await backupFetch("/backup/save", backupPayload("before-restore")); } catch (_) { kept = false; }
    if (!(await applySettingsBackup(d))) throw new Error("у файлі немає пресетів або налаштувань.");
    hideBackupBox();
    setFooterStatus(
      `✓ Відновлено бекап від ${backupStamp(d.saved_at)}: пресетів ${presetsList.length} і всі налаштування.` +
      (kept ? " Те, що було до цього, збережено в папці бекапів як «копія перед відновленням»." : ""),
      "success"
    );
  } catch (err) {
    showBackupList(backups, folder);
    setFooterStatus("Бекап не відновлено: " + (err && err.message ? err.message : String(err)), "error");
  } finally {
    backupBusy = false;
  }
}

async function openBackupFolder() {
  try {
    const d = await backupFetch("/backup/open-folder", {});
    setFooterStatus(d.opened ? "Папку з бекапами відкрито у Провіднику Windows." : `Папка з бекапами: ${d.folder}`, "info");
  } catch (err) {
    setFooterStatus("Не вдалося відкрити папку: " + (err && err.message ? err.message : String(err)), "error");
  }
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

// The layers this plugin makes. Up to 4.7.0 the program was called «Чистий Вініл Pro 2» and its layers carried
// the 2 as well: a document that holds such a layer is still served by the «До / Після» button of the panel.
const LAYER_NAME_AI = "Чистий вініл (AI)";
const LAYER_NAME_SELECTION = "Чистий вініл (Виділення)";
const PLUGIN_LAYER_NAMES = [LAYER_NAME_AI, LAYER_NAME_SELECTION, "Чистий вініл 2 (AI)", "Чистий вініл 2 (Виділення)"];

function findLatestPluginLayer(layers) {
  if (!layers) return null;
  for (let i = 0; i < layers.length; i++) {
    const l = layers[i];
    if (PLUGIN_LAYER_NAMES.includes(l.name)) return l;
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
// "Маска" switches mask <-> cleaned photo. The window never switches to the mask by itself: the brush and the
// eraser are used on whatever is on screen - on the cleaned photo their result is seen at once (since 4.8.0; up
// to 4.7.0 every stroke switched the mask on, and the result stayed hidden under the green).
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
    // the trace of a stroke (it exists only from the press until the server's answer) is seen over the cleaned
    // photo and over the mask alike
    dots.style.display = showOrig ? "none" : "block";
  }

  if (el("dlgBtnBeforeAfter")) el("dlgBtnBeforeAfter").classList.toggle("active", showOrig);
  if (el("dlgBtnMask")) el("dlgBtnMask").classList.toggle("active", sessState.view === "mask");
  updateModeBadge();
}

// The corner label always names what is on screen (hidden until the first scan has something to show). For the
// cleaned photo it also says whether the picture is the exact one or a quick preview whose exact version is on
// its way (see scheduleExactPreview).
function updateModeBadge() {
  const badge = el("dlgModeBadge");
  if (!badge) return;
  const showOrig = sessState.view === "original";
  const showMask = sessState.view === "mask" && !sessState.peekingClean && !sessState.peekingBlend;
  const kind = previewKind();
  const refining = kind === "refining" ? " · уточнюється…" + exactProgressText() : "";
  if (!sessState.id) {
    badge.className = "r4m-mode-badge";
  } else if (showOrig) {
    badge.textContent = "ДО · оригінал";
    badge.className = "r4m-mode-badge visible";
  } else if (showMask) {
    badge.textContent = "МАСКА · яскраве — дефекти, бліде — вирівняний фон" + refining;
    badge.className = "r4m-mode-badge visible mask";
  } else {
    badge.textContent = kind === "exact" ? "ПІСЛЯ · чисте фото" : "ПІСЛЯ · швидкий перегляд" + refining;
    // (green: this is what the layer will be; amber: a quick preview)
    badge.className = kind === "exact" ? "r4m-mode-badge visible clean" : "r4m-mode-badge visible refining";
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

const ZOOM_MIN = 0.15;
const ZOOM_MAX = 6.0;
const ZOOM_WHEEL_STEP = 1.14;
const ZOOM_BUTTON_STEP = 1.25;
const ZOOM_KEY_STEP = 1.4;   // Ctrl + "+" / Ctrl + "−"

// Which zoom key of Photoshop is this (pressed with Ctrl)? "in": "+" / "=", "out": "−", "fit": "0"; "" for any
// other key. The key next to Backspace and the numeric pad both count. Hosts differ in what they say about a
// key, so its place on the keyboard (e.code), its character (e.key) and its number (e.keyCode) are all asked.
function zoomKeyOf(e) {
  const code = String(e.code || "");
  const k = String(e.key || "").toLowerCase();
  const n = Number(e.keyCode || e.which || 0);
  if (code === "Equal" || code === "NumpadAdd" || k === "+" || k === "=" || k === "add" || n === 187 || n === 107 || n === 61) return "in";
  if (code === "Minus" || code === "NumpadSubtract" || k === "-" || k === "_" || k === "−" || k === "subtract" || n === 189 || n === 109 || n === 173) return "out";
  if (code === "Digit0" || code === "Numpad0" || k === "0" || n === 48 || n === 96) return "fit";
  return "";
}

// Zoom by `factor`; the point of the photo that is (cx, cy) away from the middle of the viewport stays where it
// is. The mouse wheel passes the pointer; the keys and the two buttons pass nothing - the middle of the view
// stays, as with Ctrl + "+" in Photoshop.
function zoomBy(factor, cx = 0, cy = 0) {
  const oldZoom = sessState.zoom;
  const nextZoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, oldZoom * factor));
  const ratio = nextZoom / Math.max(0.01, oldZoom);
  sessState.panX = cx - (cx - sessState.panX) * ratio;
  sessState.panY = cy - (cy - sessState.panY) * ratio;
  sessState.zoom = nextZoom;
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

// "[" makes the brush smaller, "]" larger - the keys of Photoshop. Which of the two is this key ("down" / "up"; ""
// for any other)? The key is told by its place on the keyboard first (e.code): with the Ukrainian layout the same
// two keys type "х" and "ї" (with the Russian one "х" and "ъ"), and the owner works with that layout. Hosts differ
// in what they say about a key, so its character (e.key) and its number (e.keyCode) are asked as well.
function brushKeyOf(e) {
  const code = String(e.code || "");
  const k = String(e.key || "").toLowerCase();
  const n = Number(e.keyCode || e.which || 0);
  if (code === "BracketLeft" || k === "[" || k === "{" || k === "х" || n === 219) return "down";
  if (code === "BracketRight" || k === "]" || k === "}" || k === "ї" || k === "ъ" || n === 221) return "up";
  return "";
}

// One press of "[" or "]": a small step for a small brush, a larger one for a large brush (as in Photoshop).
function brushKeyStep() {
  const s = sessState.brushSize;
  return s < 20 ? 2 : s < 60 ? 5 : s < 120 ? 10 : 20;
}

// ------------------------------------------------------------------
// Check boxes with a caption or an icon
// ------------------------------------------------------------------
// The box around a check box is a <div data-check="id of the check box">, not a <label>: Photoshop draws the text
// of a <label> in its own size and colour, whatever the style sheet says (the owner's screenshot of 2026-11-23:
// large grey captions that ran over the rows below), and whether a click on a <label> reaches its check box
// there was never seen. A click anywhere in the box ticks the check box and does what a click on the check box
// itself does - without a made-up "change" event, which a host may or may not deliver.
const checkHandlers = {};

function onCheck(id, fn) {
  const node = el(id);
  if (!node) return;
  checkHandlers[id] = fn;
  node.addEventListener("change", fn);
}

function bindCheckBoxes() {
  const boxes = document.querySelectorAll ? document.querySelectorAll("[data-check]") : [];
  Array.prototype.forEach.call(boxes, (box) => {
    const id = box.getAttribute("data-check");
    box.addEventListener("click", (e) => {
      const input = el(id);
      if (!input || e.target === input || input.disabled) return;  // (the check box itself ticks by itself)
      input.checked = !input.checked;
      if (checkHandlers[id]) checkHandlers[id]();
    });
  });
}

// The two buttons under the brush size: the upper one is the soft edge, the lower one the hard edge
function updateBrushEdgeUI() {
  if (el("dlgBrushSoft")) el("dlgBrushSoft").classList.toggle("active", sessState.brushSoft);
  if (el("dlgBrushHard")) el("dlgBrushHard").classList.toggle("active", !sessState.brushSoft);
}

function setBrushSoft(soft, byUser = true) {
  sessState.brushSoft = !!soft;
  updateBrushEdgeUI();
  if (!byUser) return;
  scheduleSaveSettings();
  sayInWindow(sessState.brushSoft
    ? "Край пензля і гумки: м’який — мазок плавно сходить нанівець, людину пензель не чіпає."
    : "Край пензля і гумки: жорсткий — мазок закінчується біля кола курсора; такий пензель перемальовує все, по чому пройде.");
}

function removeNode(node) {
  try {
    if (node && typeof node.remove === "function") node.remove();
    else if (node && node.parentNode) node.parentNode.removeChild(node);
  } catch (_) {}
}

// Takes the trace of the strokes away. `upTo` (optional): only the strokes up to this number - the ones whose
// result is in the picture now. A stroke that is being drawn, or that is still on its way to the server, keeps its
// trace: until 4.9.0 the answer to one stroke wiped the trace of the next, which then looked as if it had not taken.
function clearStrokeDots(upTo = null) {
  const d = el("dlgStrokeDots");
  if (upTo === null) {
    if (d) d.innerHTML = "";
    sessState.strokeDots = [];
  } else {
    const keep = [];
    sessState.strokeDots.forEach((it) => {
      if (it.stroke > upTo) keep.push(it);
      else removeNode(it.node);
    });
    sessState.strokeDots = keep;
  }
  if (!sessState.isDrawing) {
    sessState.lastDotX = -1;
    sessState.lastDotY = -1;
    const cur = el("dlgBrushCursor");
    if (cur) cur.style.display = "none";
  }
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
    // The trace under the pointer until the server answers. Between two mouse events the pointer can be far away -
    // a quick hand, or a window that was busy for a moment - and one dot per event then leaves a row of separate
    // dots where the server draws one line (it joins the points). So the way from the last dot is filled with
    // dots (STROKE_DOT_STEP): the trace is the stroke that will be made.
    const box = el("dlgStrokeDots");
    const first = sessState.lastDotX < 0;
    const dx = hoverPt.x - sessState.lastDotX;
    const dy = hoverPt.y - sessState.lastDotY;
    if (first || (dx * dx + dy * dy) >= 0.00004) {
      const toX = hoverPt.x * dispW;
      const toY = hoverPt.y * dispH;
      const fromX = first ? toX : sessState.lastDotX * dispW;
      const fromY = first ? toY : sessState.lastDotY * dispH;
      const gap = Math.sqrt((toX - fromX) * (toX - fromX) + (toY - fromY) * (toY - fromY));
      const stepPx = Math.max(STROKE_DOT_MIN_PX, diam * STROKE_DOT_STEP);
      const n = first ? 1 : Math.max(1, Math.min(STROKE_DOTS_PER_MOVE, Math.ceil(gap / stepPx)));
      for (let i = 1; i <= n && sessState.strokeDots.length < STROKE_DOTS_MAX; i++) {
        const dot = document.createElement("div");
        dot.className = "stroke-dot";
        dot.style.width = diam + "px";
        dot.style.height = diam + "px";
        dot.style.left = Math.round(fromX + (toX - fromX) * (i / n) - half) + "px";
        dot.style.top = Math.round(fromY + (toY - fromY) * (i / n) - half) + "px";
        dot.style.background = sessState.tool === "eraser" ? "#b41822" : "#22ee58";
        // (pale dots that add up towards the middle of the stroke look like the soft edge the stroke will have;
        // the hard brush leaves the solid trace it always had)
        dot.style.opacity = sessState.brushSoft ? "0.2" : "0.65";
        box.appendChild(dot);
        sessState.strokeDots.push({ node: dot, stroke: sessState.strokeNo });
      }
      sessState.lastDotX = hoverPt.x;
      sessState.lastDotY = hoverPt.y;
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
// Mask edits reach the server one after another, in the order they were made: an answer that comes late must
// never put an older picture over a newer one (several Ctrl + Z in a row, a stroke right after a step back).
// Resolves with the server's answer, or null when there was none.
let maskEditQueue = Promise.resolve(null);
let maskEditsWaiting = 0;  // requests that were made and are not answered yet

function sendMaskEditOp(op, points = null) {
  if (!sessState.id) return Promise.resolve(null);
  const body = {
    session_id: sessState.id,
    op,
    points,
    radius_px: sessState.brushSize,
    softness: sessState.brushSoft ? 1 : 0,   // the edge of the stroke: 1 soft, 0 hard (a server before 4.7.0 ignores it)
    erase: sessState.tool === "eraser",
    dressSmooth: dressSmoothEnabled,
    dressStrength: getSliderVal("gSlDress")
  };
  // The strokes whose trace may go when this answer is shown: all that were finished before this request. (Requests
  // are answered in the order they were made, so every one of those strokes is in the picture by then.)
  const tracesUpTo = sessState.isDrawing ? sessState.strokeNo - 1 : sessState.strokeNo;
  maskEditsWaiting += 1;
  const run = () => postMaskEdit(body, tracesUpTo);
  maskEditQueue = maskEditQueue.then(run, run);
  return maskEditQueue;
}

async function postMaskEdit(body, tracesUpTo = null) {
  let d = null;
  if (sessState.id === body.session_id) {
    try {
      const r = await fetch(`${SERVER_URL}/session/mask-edit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      if (r.ok) d = await r.json();
    } catch (_) {
      d = null;
    }
    if (d && sessState.id === body.session_id && takeSessionPictures(d)) {
      if (typeof d.mask_share === "number") sessState.maskShare = d.mask_share;
      if (d.history) setEditHistory(d.history);
    }
  }
  maskEditsWaiting = Math.max(0, maskEditsWaiting - 1);
  // Nothing else is on its way and nothing is being drawn - the usual case: every dot goes, as it always did.
  // Otherwise only the traces of the strokes that are in the picture now.
  const allDone = maskEditsWaiting === 0 && !sessState.isDrawing;
  clearStrokeDots(allDone ? null : tracesUpTo);
  // (a stroke changes nothing about the frame itself; but if the picture under it is still a quick preview, its
  //  exact version is due - and was put off while the brush was busy)
  if (sessState.id === body.session_id) scheduleExactPreview();
  return d;
}

// How many mask edits can be taken back / made again: the two buttons of the left bar are bright when there is
// something to step to. (They stay clickable when dim - a press then says in words that there is nothing.)
function setEditHistory(h) {
  const count = (v) => Math.max(0, Math.round(Number(v) || 0));
  sessState.history = { undo: count(h && h.undo), redo: count(h && h.redo) };
  [["dlgBtnUndo", sessState.history.undo], ["dlgBtnRedo", sessState.history.redo]].forEach(([id, n]) => {
    const b = el(id);
    if (!b) return;
    b.classList.toggle("is-dim", n === 0);
  });
}

// A line of text for the user of the big window: the hint strip at the bottom and, when the fine settings are
// open, their own hint box (it covers the strip on a small window).
function sayInWindow(text) {
  if (el("dlgHoverHint")) el("dlgHoverHint").textContent = text;
  const gearPop = el("dlgGearPopover");
  if (el("gTipBox") && gearPop && gearPop.classList.contains("visible")) el("gTipBox").textContent = text;
}

// Ctrl + Z / the ↺ button (back = true), Ctrl + Shift + Z, Ctrl + Y / the ↻ button (back = false)
async function stepMaskEdit(back) {
  if (!sessState.open || !sessState.id || sessState.isApplying || sessState.isDrawing) return false;
  const d = await sendMaskEditOp(back ? "undo" : "redo");
  if (!d) return false;
  if (typeof d.stepped !== "boolean") {
    sayInWindow("Крок назад недоступний: запущено стару версію сервера. Перезапустіть його (restart_gpu_server.bat).");
    return false;
  }
  if (!d.stepped) {
    sayInWindow(back
      ? "Скасовувати нічого: правок маски (пензель, гумка, заливка, інверсія) ще не було."
      : "Повертати нічого: скасованих кроків немає.");
    return false;
  }
  const left = back ? sessState.history.undo : sessState.history.redo;
  const more = left > 0 ? ` (можна ще ${left})` : "";
  sayInWindow(back
    ? `↺ Останню правку маски скасовано${more}. Повернути її: Ctrl + Shift + Z або кнопка ↻.`
    : `↻ Скасовану правку повернуто${more}.`);
  return true;
}

// ------------------------------------------------------------------
// "Скинути пресет": the values a built-in preset ships with
// ------------------------------------------------------------------
let resetPresetArmedId = null;  // the preset whose reset button was pressed once (the second press does it)
let resetPresetTimer = null;
const RESET_PRESET_CONFIRM_MS = 6000;

function defaultPresetOf(id) {
  return DEFAULT_PRESETS.find((dp) => dp.id === id) || null;
}

function disarmPresetReset() {
  if (resetPresetTimer) clearTimeout(resetPresetTimer);
  resetPresetTimer = null;
  if (resetPresetArmedId === null) return;
  resetPresetArmedId = null;
  renderPresets();
}

// First press: asks for one more (a reset replaces the values the user saved into this preset). Second press within
// a few seconds: the active preset gets the values it ships with; they go onto the controls and into the preview.
// Only this one preset changes. A preset the user made has no shipped values - the button says so.
async function resetActivePresetToDefault() {
  const active = presetsList.find((p) => p.id === activePresetId);
  if (!active) return false;
  const shipped = defaultPresetOf(active.id);
  if (!shipped) {
    disarmPresetReset();
    sayInWindow(`«${active.name}» — ваш власний пресет: стандартних значень у нього немає. Скинути можна пресети, що постачаються з програмою.`);
    return false;
  }
  if (resetPresetArmedId !== active.id) {
    if (resetPresetTimer) clearTimeout(resetPresetTimer);
    resetPresetArmedId = active.id;
    resetPresetTimer = setTimeout(disarmPresetReset, RESET_PRESET_CONFIRM_MS);
    renderPresets();
    sayInWindow(`Скинути «${active.name}» до стандартних значень? Натисніть кнопку ще раз. Зміниться лише цей пресет.`);
    return false;
  }
  if (resetPresetTimer) clearTimeout(resetPresetTimer);
  resetPresetTimer = null;
  resetPresetArmedId = null;
  active.cfg = JSON.parse(JSON.stringify(shipped.cfg));
  applyPreset(active);
  renderPresets();
  sayInWindow(`✓ Пресет «${active.name}» скинуто до стандартних значень.`);
  announcePresetClick(active);
  refreshPreviewAfterClick(false);
  await persistPresets();
  await persistSettingsNow();
  return true;
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
      takeSessionPictures(d);
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
    !!c.shadow, !!c.removeStands, c.master, !!c.fracFine, !!c.fracMed, !!c.fracLarge, c.cleanPasses, c.speedMode,
    c.strayHair, !!c.mixOn, c.mixOn ? c.mix : 0
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

function cancelExactTimer() {
  if (sessState.exactTimer) {
    clearTimeout(sessState.exactTimer);
    sessState.exactTimer = null;
  }
}

// Every answer of the big window carries the two pictures and their number in order ("rev"). A brush stroke is
// answered while a background recompute is still on its way, so two answers can arrive the other way round: a
// picture older than the one on screen is dropped. Returns false for such an answer.
// "exact" of the answer: the real frame was computed for these pictures (false after a light refresh).
function takeSessionPictures(d) {
  if (!d) return false;
  if (typeof d.rev === "number") {
    if (d.rev < sessState.picRev) return false;
    sessState.picRev = d.rev;
  }
  if (d.comp_jpg_b64 && el("dlgCompImg")) el("dlgCompImg").src = "data:image/jpeg;base64," + d.comp_jpg_b64;
  if (d.overlay_jpg_b64 && el("dlgOverlayImg")) el("dlgOverlayImg").src = "data:image/jpeg;base64," + d.overlay_jpg_b64;
  if (typeof d.exact === "boolean") sessState.exactShown = d.exact;
  if (d.stats) noteComputeStats(d.stats);
  // something new is on screen: whatever kept the exact recompute from being asked for may be over
  sessState.exactHold = false;
  sessState.exactError = "";
  updateModeBadge();
  return true;
}

// What the picture on screen is:
//   "exact"    - the real frame was computed for it: this is what the layer will be;
//   "refining" - a quick preview, and the exact picture is on its way by itself;
//   "quick"    - a quick preview that stays for now (the exact one failed, or the server declined - see exactHold).
function previewKind() {
  if (sessState.exactShown || sessState.bgUnsupported) return "exact";
  return (sessState.exactHold || sessState.exactError || !detailPreview) ? "quick" : "refining";
}

function exactProgressText() {
  return exactJobs.size > 0 && typeof sessState.exactPct === "number" ? ` ${Math.round(sessState.exactPct)} %` : "";
}

// Should the exact picture be computed now, by itself?
function exactPreviewWanted() {
  if (!detailPreview) return false;  // the fast window: the real frame is computed by Apply or by the button
  if (!sessState.open || !sessState.id || sessState.isApplying || sessState.bgUnsupported) return false;
  if (sessState.exactError) return false;
  // a quick preview is on screen (exactHold: the server declined to replace the user's own mask by itself)
  if (previewMatchesSettings()) return !sessState.exactShown && !sessState.exactHold;
  return !lightPreviewAvailable();  // new values and no light way (2 passes): the exact picture is the only one
}

// The exact picture comes by itself. Once the window has been quiet for a moment and the picture on screen is a
// quick preview (or still shows the former values, where there is no light way), the server computes the real
// frame in the background. Nothing waits for it: the brush and the eraser work meanwhile, and a change of the
// settings simply goes first - the server stops the background run and this function is called again afterwards.
function scheduleExactPreview(waitMs) {
  cancelExactTimer();
  if (exactPreviewWanted()) {
    const ms = waitMs === undefined ? EXACT_DELAY_MS : Math.max(0, Number(waitMs) || 0);
    sessState.exactTimer = setTimeout(fireExactPreview, ms);
  }
  updatePreviewBadge();
  updateModeBadge();
}

function fireExactPreview() {
  sessState.exactTimer = null;
  // Not now: a slider is held, a stroke is being drawn, or another request for the frame is on its way or about
  // to go. Each of them calls scheduleExactPreview() when it is done.
  const busy = activeDragSliderId || sessState.isDrawing || sessState.recomputing || sessState.previewTimer;
  const onItsWay = exactJobs.size > 0 && sessState.exactSig === previewSettingsSignature();
  if (!exactPreviewWanted() || busy || onItsWay) {
    updatePreviewBadge();
    updateModeBadge();
    return;
  }
  runExactPreview();
}

// A slider that changes the frame was taken hold of while the exact picture is being computed: that picture will
// not be wanted. The server is told at once, so the run stops while the slider is still being moved - and the
// refresh that follows the release does not have to wait for it to stop. (Without this the run stops all the
// same, but only when that refresh arrives.) A server before 4.8.0 has no background runs.
function stopBackgroundRun() {
  if (!sessState.open || !sessState.id || exactJobs.size === 0 || sessState.bgUnsupported) return;
  fetch(`${SERVER_URL}/session/stop-background`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessState.id })
  }).catch(() => {});
}

function stopExactPolling() {
  if (sessState.exactPollTimer) {
    clearInterval(sessState.exactPollTimer);
    sessState.exactPollTimer = null;
  }
  sessState.exactPct = null;
}

// The percent next to "уточнюється": asked from the server a few times a second while a background run is on.
function startExactPolling() {
  if (sessState.exactPollTimer) return;
  sessState.exactPollTimer = setInterval(async () => {
    const job = sessState.exactJob;
    if (!job || !exactJobs.has(job)) {
      stopExactPolling();
      return;
    }
    if (sessState.exactPollBusy) return;
    sessState.exactPollBusy = true;
    try {
      const r = await fetch(`${SERVER_URL}/progress?job_id=${encodeURIComponent(job)}`);
      if (r.ok) {
        const d = await r.json();
        if (d && d.ok && typeof d.pct === "number" && sessState.exactJob === job && exactJobs.has(job)) {
          sessState.exactPct = d.pct;
          updatePreviewBadge();
          updateModeBadge();
        }
      }
    } catch (_) {
    } finally {
      sessState.exactPollBusy = false;
    }
  }, EXACT_POLL_MS);
}

// One background recompute: the real frame for the values on the sliders, without the progress card.
async function runExactPreview() {
  const sid = sessState.id;
  if (!sid) return false;
  const jobs = exactJobs;
  const jobId = makeJobId();
  const sigAtSend = previewSettingsSignature();
  const refine = previewMatchesSettings();  // the same values as on screen: only the quick picture becomes exact
  const params = readCurrentConfig();
  params.autoFractions = fracAuto;
  jobs.add(jobId);
  sessState.exactJob = jobId;
  sessState.exactSig = sigAtSend;
  sessState.exactPct = null;
  sessState.previewForce = false;
  startExactPolling();
  updatePreviewBadge();
  updateModeBadge();

  let d = null;
  let failed = "";
  try {
    const r = await fetch(`${SERVER_URL}/session/recompute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sid, params, preserve_edits: true, background: true, jobId })
    });
    if (!r.ok) {
      let msg = `Помилка (${r.status})`;
      try { const j = await r.json(); if (j.error) msg = j.error; } catch (_) {}
      throw new Error(msg);
    }
    d = await r.json();
  } catch (err) {
    failed = err && err.message ? err.message : String(err);
  } finally {
    jobs.delete(jobId);
  }
  if (jobs !== exactJobs || sessState.id !== sid || !sessState.open) return false;  // that window is closed
  if (jobs.size === 0) stopExactPolling();

  let done = false;
  if (failed) {
    // Not tried again by itself: the next change of the settings or of the mask clears this (takeSessionPictures)
    sessState.exactError = failed;
  } else if (d.superseded) {
    // another request went first; it asks for the exact picture again when it is done
  } else if (d.skipped) {
    // the mask on screen is the user's own drawing: a recompute would put the automatic one back. "Застосувати"
    // computes the real frame in that case.
    if (typeof d.exact === "boolean") sessState.exactShown = d.exact;
    sessState.exactHold = true;
  } else {
    if (typeof d.exact !== "boolean") sessState.bgUnsupported = true;  // an older server: it made everything wait
    takeRecomputeAnswer(d, sigAtSend, params, refine);
    done = true;
  }
  updateStageVisibility();
  scheduleExactPreview();  // (e.g. the values were changed meanwhile and there is no light way)
  return done;
}

// The answer of a recompute - light, full or background - is taken over: pictures, fractions, notes, and which
// settings the picture on screen now belongs to. `refine`: a background run for the values already on screen.
function takeRecomputeAnswer(d, sigAtSend, params, refine) {
  // (false: a newer picture is on screen already - a brush stroke answered later; it has this recompute in it)
  const fresh = takeSessionPictures(d);
  if (typeof d.rev === "number") {
    if (d.rev < sessState.syncRev) return;  // a later recompute has been taken over already
    sessState.syncRev = d.rev;
  }
  // Nothing was touched while the server was busy -> the picture that came back is for the current settings.
  const untouched = previewSettingsSignature() === sigAtSend;
  if (d.auto_fractions && (untouched || (params.autoFractions && fracAuto))) {
    fracFine = !!d.auto_fractions.fracFine;
    fracMed = !!d.auto_fractions.fracMed;
    fracLarge = !!d.auto_fractions.fracLarge;
    updateFractionButtonsUI();
  }
  if (fresh && d.history) setEditHistory(d.history);  // the brush strokes live on through a refresh, and so do their steps
  sessState.lastStats = d.stats || null;
  sessState.previewSyncedSig = untouched ? previewSettingsSignature() : sigAtSend;
  if (sessState.presetNote && untouched) {
    const note = sessState.presetNote;
    sessState.presetNote = null;
    sessState.smokeNote = false;
    showPreviewNote(presetNoteText(note, d.mask_share));
  } else if (sessState.smokeNote && untouched) {
    // (also in the hint strip: the note in the corner goes away by itself, the strip stays until the next hint)
    sessState.smokeNote = false;
    const smokeText = smokeNoteText(d.smoke);
    showPreviewNote(smokeText, 12000);
    if (smokeText) sayInWindow(smokeText);
  } else if (sessState.note && !refine) {
    showPreviewNote("");  // the note on screen described the picture that has just been replaced
  }
  if (fresh && typeof d.mask_share === "number") sessState.maskShare = d.mask_share;
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

// (the shares are the bright green of the mask: dust, seam and gear that were found and will be redrawn; the rest
// of the backdrop is evened as a whole and is pale green there)
function presetNoteText(note, shareNow) {
  if (typeof shareNow !== "number") return `✓ Пресет «${note.name}» застосовано.`;
  const now = percentOfFrame(shareNow);
  if (typeof note.before !== "number") return `✓ Пресет «${note.name}»: дефекти знайдено на ${now} кадру.`;
  const was = percentOfFrame(note.before);
  return now === was
    ? `✓ Пресет «${note.name}»: дефекти знайдено там само (${now} кадру) — відмінність у вирівнюванні фону та краях.`
    : `✓ Пресет «${note.name}»: дефекти знайдено на ${now} кадру (було ${was}).`;
}

// What the server saw of smoke in this frame, in words. `sm` comes with every answer of the big window:
// { share, largest: smoke-like areas / the biggest of them (share of the frame), found: enough of it to call it
//   smoke, protected: share of the frame that is kept, on: protection asked for, auto: only when smoke is found,
//   faint: the switch was taken as the user's word (a server from 4.11.0 on always sends this key) }.
// With such a server the switch is never answered with "no smoke found": the user says there is smoke, the
// program says how much of the frame it keeps for it and which way to move the slider.
function smokeNoteText(sm) {
  if (!sm || typeof sm !== "object") return "";
  const byWord = "faint" in sm;
  if (!sm.on) {
    if (sm.found) return `Захист диму вимкнено: дим у кадрі (${percentOfFrame(sm.share)}) чиститься як звичайний фон.`;
    return byWord
      ? "Захист диму вимкнено: увесь фон чиститься як звичайний — і дим, якщо він там є."
      : "Захист диму вимкнено. Диму в кадрі й так не знайдено — результат той самий.";
  }
  if (byWord && sm.faint) {
    if (!(sm.protected > 0)) {
      return "Захист диму увімкнено, але програма не розпізнала в кадрі диму, тож поки нічого не береже. Дим є? Потягніть «Захист диму» до 100 % — тоді вона береже все м’яке на фоні, і на підлозі теж.";
    }
    return `Захист диму увімкнено: ${percentOfFrame(sm.protected)} кадру програма бере за дим і не чистить. Частину диму все одно зачищено — потягніть «Захист диму» вище (до 100 %); береже бруд — нижче.`;
  }
  if (!sm.found && sm.auto) {
    return "Перегляд оновлено. Диму в кадрі не знайдено, тому захист диму тут нічого не змінює — картинка та сама. Дим є, але ледь помітний? Поставте «Захист диму» на 95–100 %.";
  }
  if (!(sm.protected > 0)) return "Захист диму увімкнено, але схожих на дим ділянок у кадрі немає.";
  return sm.auto
    ? `Дим знайдено й захищено: ${percentOfFrame(sm.protected)} кадру не чиститься.`
    : `Захист диму на 95–100 %: збережено все, що схоже на дим (${percentOfFrame(sm.protected)} кадру), навіть світлі розводи.`;
}

// The window has just opened with the smoke protection off (the usual state) and the frame seems to have smoke:
// without these words the smoke would be cleaned away silently.
function smokeOffHintText(sm) {
  return `Схоже, у кадрі є дим (${percentOfFrame(sm.share)} кадру), а захист диму вимкнено — дим чиститься як звичайний фон. Щоб його зберегти, поставте галочку з димом угорі.`;
}

// A smoke control was used: once the refreshed preview is back, say what the server saw of smoke. (On most frames
// there is no smoke and the control changes nothing - without these words it looks broken.)
function askSmokeNote() {
  if (sessState.open && sessState.id) sessState.smokeNote = true;
}

function updatePreviewBadge() {
  const badge = el("dlgPreviewBadge");
  if (!badge) return;
  let text = "";
  let cls = "r4m-preview-badge";
  if (sessState.open && sessState.id && !sessState.isApplying) {
    const stale = !previewMatchesSettings();
    if (sessState.previewBusy || sessState.previewTimer) {
      text = "↻ Оновлюю перегляд…";
      cls += " visible";
    } else if (stale && exactPreviewWanted() && (sessState.exactTimer || exactJobs.size > 0)) {
      // no light way for these values (2 passes): the picture still shows the former ones until the exact one comes
      text = "↻ Перераховую перегляд із новими значеннями…" + exactProgressText();
      cls += " visible";
    } else if (!activeDragSliderId && !sessState.recomputing && stale) {
      if (sessState.exactError) {
        text = `Перегляд не вдалося оновити: ${sessState.exactError}. Спробуйте кнопку «↻ Перерахувати» внизу вікна. «Застосувати» врахує нові значення й без цього.`;
      } else if (sessState.quickUnsupported || sessState.bgUnsupported) {
        text = "Перегляд ще зі старими значеннями. Запущено стару версію сервера — перезапустіть його (restart_gpu_server.bat). Оновити зараз: кнопка «↻ Перерахувати зараз» у налаштуваннях.";
      } else {
        text = "Перегляд не оновився. Натисніть «↻ Перерахувати» внизу вікна. «Застосувати» врахує нові значення й без цього.";
      }
      cls += " visible stale";
    } else if (sessState.exactError && !sessState.exactShown) {
      text = `Точний перегляд не вдалося порахувати: ${sessState.exactError}. На екрані швидкий перегляд; «Застосувати» все одно зробить точний розрахунок.`;
      cls += " visible stale";
    } else if (sessState.cpuWarn) {
      text = sessState.cpuWarn;
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
// The light way where there is one; otherwise (2 passes) the exact picture is asked for, in the background.
function requestPreviewRefresh(waitMs, force) {
  if (!sessState.open || !sessState.id) return;
  if (force) sessState.previewForce = true;
  cancelPreviewTimer();
  sessState.exactError = "";  // the values changed: an exact recompute that failed may be tried again
  if (!sessState.isApplying && lightPreviewAvailable() && !previewMatchesSettings()) {
    cancelExactTimer();
    sessState.previewTimer = setTimeout(firePreviewRefresh, Math.max(0, Number(waitMs) || 0));
    updatePreviewBadge();
    updateModeBadge();
    return;
  }
  // (also when the slider came back to the value the preview shows: a quick preview still wants its exact picture)
  scheduleExactPreview(previewMatchesSettings() ? undefined : waitMs);
}

function firePreviewRefresh() {
  sessState.previewTimer = null;
  const idle = !sessState.open || !sessState.id || sessState.isApplying;
  // A slider is being dragged again: nothing is computed during a drag, its release asks once more.
  if (idle || activeDragSliderId || !lightPreviewAvailable() || previewMatchesSettings()) {
    if (!idle && !activeDragSliderId) scheduleExactPreview();
    else updatePreviewBadge();
    return;
  }
  recomputeInteractiveSession(true, true);
}

// Buttons that always recomputed at once (fractions, smoke checkbox, presets): they refresh the preview the light
// way; with 2 passes, where there is no light way, the exact picture comes in the background. Only an older
// server, which knows neither, recomputes in full at once, as before.
function refreshPreviewAfterClick(force) {
  if (!sessState.open || !sessState.id) return;
  if (lightPreviewAvailable() || !sessState.bgUnsupported) requestPreviewRefresh(PREVIEW_DELAY_CLICK_MS, force);
  else recomputeInteractiveSession(true, false);
}

// quick = true: light refresh, only the preview is redrawn, nothing blocks the window.
// quick = false: full recompute of the real frame with the progress card - the buttons "↻ Перерахувати".
// (The exact picture that comes by itself is runExactPreview: the same computation in the background.)
//
// The newest values win (since 4.12.0). A call that comes while another one is on its way does not wait for it:
// the new request goes out at once, the server stops the older run at its next safe place (it answers
// {superseded: true}; a server before 4.12.0 finishes it first) and whatever the older request brings back is
// dropped. While the progress card is up the newer run is a full one as well - the user is waiting for the exact
// picture - and the bar starts from the beginning.
let recomputeRun = 0;  // the number of the newest call; only that call may touch the window

async function recomputeInteractiveSession(preserveEdits = true, quick = false) {
  if (!sessState.id) return false;
  const overtakes = sessState.recomputing;
  quick = !!quick;
  if (overtakes && !sessState.previewBusy) quick = false;  // the bar is running: it goes on, from the start
  const run = ++recomputeRun;
  const newest = () => run === recomputeRun;
  cancelPreviewTimer();
  cancelExactTimer();
  sessState.exactError = "";
  sessState.recomputing = true;
  sessState.previewBusy = quick;
  sessState.previewForce = false;
  const sid = sessState.id;
  const sigAtSend = previewSettingsSignature();
  const jobId = quick ? null : makeJobId();
  if (quick) {
    updatePreviewBadge();
  } else {
    stopProgressPolling();
    updateProgressUI(18, overtakes ? "Значення змінилися — перераховую спочатку..." : "Перерахунок маски та фону...", "modal");
    startProgressPolling(jobId, "modal");
  }

  let done = false;
  let timeoutId = null;
  let ctrl = null;
  try {
    if (typeof AbortController !== "undefined") {
      ctrl = new AbortController();
      recomputeAbortCtrl = ctrl;  // ("Скасувати" on the progress card stops the newest run)
      timeoutId = setTimeout(() => {
        try { ctrl.abort(); } catch (_) {}
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
    if (ctrl) fetchOpts.signal = ctrl.signal;

    const r = await fetch(`${SERVER_URL}/session/recompute`, fetchOpts);
    if (!r.ok) {
      let msg = `Помилка (${r.status})`;
      try { const j = await r.json(); if (j.error) msg = j.error; } catch (_) {}
      throw new Error(msg);
    }
    const d = await r.json();
    if (!newest()) return false;  // a newer call is on its way: this answer is for values that are gone
    if (d.superseded) {
      // (the server gave way to a request this window did not make - nothing to show; the badge says the rest)
    } else if (sessState.id === sid) {
      if (quick && typeof d.quick !== "boolean" && !sessState.quickUnsupported) {
        // An older server build: it ignored "quick" and recomputed in full. Stop asking it after every slider.
        sessState.quickUnsupported = true;
        if (el("dlgHoverHint")) {
          el("dlgHoverHint").textContent = "Запущено стару версію сервера: перезапустіть його (restart_gpu_server.bat), щоб перегляд оновлювався швидко.";
        }
      }
      if (typeof d.exact !== "boolean") sessState.bgUnsupported = true;  // an older server: no background recompute
      takeRecomputeAnswer(d, sigAtSend, params, false);
      done = true;
      updateStageVisibility();
    }
  } catch (err) {
    if (!newest()) return false;
    sessState.presetNote = null;
    sessState.smokeNote = false;
    if (err && err.name === "AbortError") {
      if (el("dlgHoverHint")) el("dlgHoverHint").textContent = quick ? "Оновлення перегляду перервано." : "Перерахунок скасовано.";
    } else {
      const msg = (quick ? "Помилка оновлення перегляду: " : "Помилка перерахунку: ") + (err && err.message ? err.message : String(err));
      setFooterStatus(msg, "error");
      if (el("dlgHoverHint")) el("dlgHoverHint").textContent = msg;
    }
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
    if (newest()) {
      if (recomputeAbortCtrl === ctrl) recomputeAbortCtrl = null;
      if (!quick && !sessState.isApplying) {
        // (while "Застосувати" is running the progress card belongs to it)
        stopProgressPolling();
        hideProgressUI("modal");
      }
      sessState.recomputing = false;
      sessState.previewBusy = false;
    }
  }

  // The light picture is on screen: its exact version follows by itself after a quiet moment.
  if (sessState.open && sessState.id === sid) scheduleExactPreview();
  else updatePreviewBadge();
  return done;
}

// The exact picture at once, with the progress card: the two buttons "↻ Перерахувати" and the smoke switch (what
// smoke is decides what gets cleaned at all, and the owner asked for the recompute to start by itself).
function recomputeExactNow() {
  if (!sessState.open || !sessState.id || sessState.isApplying) return Promise.resolve(false);
  return recomputeInteractiveSession(true, false);
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
      // the size of the pictures this window will be sent (it is fixed for the whole session)
      params.previewLong = detailPreview ? PREVIEW_LONG_DETAIL : PREVIEW_LONG_FAST;
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
  sessState.view = "result";   // the window opens with the cleaned photo; "Маска" shows the green zones
  sessState.maskShare = null;
  sessState.presetNote = null;
  sessState.smokeNote = false;
  showPreviewNote("");
  sessState.blend = 100;
  sessState.peekingClean = false;
  sessState.peekingBlend = false;
  sessState.scanAborted = false;
  sessState.isApplying = false;
  cancelPreviewTimer();
  recomputeRun += 1;  // (a recompute of the window before, still on its way, must not touch this window)
  sessState.recomputing = false;
  sessState.previewBusy = false;
  sessState.previewSyncedSig = "";
  sessState.previewForce = false;
  sessState.quickUnsupported = false;
  cancelExactTimer();
  stopExactPolling();
  exactJobs = new Set();
  sessState.picRev = 0;
  sessState.syncRev = 0;
  sessState.exactShown = true;
  sessState.exactSig = "";
  sessState.exactJob = null;
  sessState.exactError = "";
  sessState.exactHold = false;
  sessState.bgUnsupported = false;
  sessState.isPanning = false;
  setEditHistory(null);
  pendingApplyPayload = null;
  updatePreviewBadge();

  setSliderVal("dlgSlBlend", 100);
  updateSliderVisuals();
  if (el("dlgChkAutoPreset")) el("dlgChkAutoPreset").checked = autoPreset;
  if (el("dlgChkMakeMask")) el("dlgChkMakeMask").checked = makeMaskDefault;
  if (el("dlgBrushSizeVal")) el("dlgBrushSizeVal").textContent = String(sessState.brushSize);
  updateBrushEdgeUI();
  if (el("dlgOrigImg")) el("dlgOrigImg").src = "";
  if (el("dlgCompImg")) el("dlgCompImg").src = "";
  if (el("dlgOverlayImg")) el("dlgOverlayImg").src = "";
  clearStrokeDots();
  setBtnDisabled(el("dlgBtnApply"), true);
  if (el("dlgPresetsPopover")) el("dlgPresetsPopover").classList.remove("visible");
  if (el("dlgGearPopover")) el("dlgGearPopover").classList.remove("visible");
  if (el("dlgInfoPopover")) el("dlgInfoPopover").classList.remove("visible");

  // Default tool = Eraser: a stroke over the photo takes the cleaning back there (the photo shows it at once)
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
      // The working size of the window: the photo, the brush and the strokes are placed by it. The pictures
      // themselves are larger since 4.8.0 (up to twice, so that the person is sharp in a big window) and are
      // simply drawn into the same box - never ask a picture for its size.
      sessState.pw = res.preview_w;
      sessState.ph = res.preview_h;
      sessState.lastStats = res.stats || null;
      // The first pictures are exact (the real frame was computed for them) and carry their number in order.
      // A server that says neither is an older build: no background recompute is asked of it.
      sessState.picRev = typeof res.rev === "number" ? res.rev : 0;
      sessState.syncRev = sessState.picRev;
      sessState.exactShown = true;
      sessState.bgUnsupported = typeof res.exact !== "boolean";

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
      // Smoke in the frame changes what is cleaned, so it is said right away (no smoke - the usual case - no words)
      const smokeSeen = res.smoke || (res.scene && res.scene.smoke) || null;
      let smokeNote = "";
      // (a server from 4.11.0 on takes the switch on trust: then it is also said when it keeps nothing)
      if (untouched && smokeSeen && smokeSeen.on && (smokeSeen.protected > 0 || smokeSeen.faint)) smokeNote = smokeNoteText(smokeSeen);
      else if (untouched && smokeSeen && !smokeSeen.on && smokeSeen.found) smokeNote = smokeOffHintText(smokeSeen);
      if (autoNote || smokeNote) showPreviewNote([autoNote, smokeNote].filter(Boolean).join(" "), smokeNote ? 12000 : 8000);
      // what the first scan took - and a warning when its AI fill ran on the processor (it goes before the note)
      noteComputeStats(res.stats);

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
      title: "Чистий Вініл Pro",
      resize: "both",
      size: { width: 1020, height: 740 }
    });
  } finally {
    sessState.scanAborted = true;
    cancelPreviewTimer();
    cancelExactTimer();
    stopExactPolling();
    recomputeRun += 1;  // (whatever a recompute of this window still brings back is for nobody)
    sessState.recomputing = false;
    sessState.previewBusy = false;
    sessState.presetNote = null;
    sessState.smokeNote = false;
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
  cancelExactTimer();
  updatePreviewBadge();
  const applyParams = readCurrentConfig();
  applyParams.autoFractions = fracAuto;
  // The exact picture for these very values is being computed in the background right now: Apply waits for that
  // run instead of stopping it and computing the same frame from the start.
  const followBackground = exactJobs.size > 0 && sessState.exactSig === previewSettingsSignature();

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
        followBackground,
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
    if (sessState.open && sessState.id) scheduleExactPreview();  // (Apply failed: the window goes on)
    else updatePreviewBadge();
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
          ? await doc.createPixelLayer({ name: LAYER_NAME_AI, opacity: Math.round(blend) })
          : await doc.createLayer({ name: LAYER_NAME_AI });

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
    // What "Застосувати" itself took, and the AI fill inside it (with the fast window the real frame is computed
    // here): the window is closed by now, so the panel is the place where the user can read it - and tell us.
    const st = meta.stats || {};
    const tm = st.timing && st.timing.fill_tiles ? st.timing : null;
    let timeNote = typeof st.elapsed_ms === "number" ? ` «Застосувати»: ${secondsText(st.elapsed_ms / 1000)}` : "";
    if (tm) timeNote += `${timeNote ? " · " : " "}${fillTimeText(tm)}`;
    if (timeNote) timeNote += ".";
    const why = tm && tm.fallback && (tm.fallback.lama || tm.fallback.matting);
    setFooterStatus(`✓ Шар створено (${gpuLabel}, ${bitDepth}-bit${maskNote}, змінено ${chPx.toLocaleString("uk-UA")} пкс, сесія ${totalSec} с).` +
      timeNote + (why ? " " + cpuFallbackText(why) : ""), "success");
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
      const suspensionID = await executionContext.hostControl.suspendHistory({ documentID: doc.id, name: "Чистий Вініл (Виділення)" });
      try {
        await action.batchPlay([{ _obj: "set", _target: [{ _ref: "channel", _property: "selection" }], to: { _enum: "ordinal", _value: "none" } }], {});
        const topBefore = doc.layers && doc.layers.length > 0 ? doc.layers[0] : null;
        const newLayer = doc.createPixelLayer
          ? await doc.createPixelLayer({ name: LAYER_NAME_SELECTION, opacity: 100 })
          : await doc.createLayer({ name: LAYER_NAME_SELECTION });
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
      const suspensionID = await executionContext.hostControl.suspendHistory({ documentID: doc.id, name: "Формат 5:7 (Чистий Вініл)" });
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
    }, { commandName: "Формат 5:7 (Чистий Вініл)" });

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
        setFooterStatus(`Шар «${LAYER_NAME_AI}» ще не створено.`, "info");
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

// The photo follows the pointer while it is being dragged (see startPan in initEvents)
function panTo(clientX, clientY) {
  const dx = clientX - sessState.dragStartX;
  const dy = clientY - sessState.dragStartY;
  if (dx !== 0 || dy !== 0) sessState.panMoved = true;
  sessState.panX = sessState.panStartX + dx;
  sessState.panY = sessState.panStartY + dy;
  applyStageLayout();
}

function initEvents() {
  bindCheckBoxes();
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
      // ...and the exact picture that is being computed right now will not be wanted if this slider moves
      // (Blend and Clothing change nothing of the frame)
      if (id !== "dlgSlBlend" && id !== "gSlDress") stopBackgroundRun();
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
      panTo(e.clientX, e.clientY);
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

  document.addEventListener("mouseup", async (e) => {
    const finishedSliderId = activeDragSliderId;
    activeDragSliderId = null;

    if (finishedSliderId === "dlgSlBlend" && sessState.open) {
      sessState.peekingBlend = false;
      updateStageVisibility();
    }

    // The slider was released: one light refresh of the preview, a moment later (Blend and Clothing are instant).
    if (finishedSliderId && finishedSliderId !== "dlgSlBlend" && finishedSliderId !== "gSlDress") {
      if (finishedSliderId === "gSlSmoke") askSmokeNote();
      requestPreviewRefresh(PREVIEW_DELAY_SLIDER_MS, false);
    } else if (finishedSliderId) {
      // Blend and Clothing change nothing of the frame. But whatever was waiting when the slider was taken - a
      // light refresh, the exact picture - was put off, and goes on now.
      requestPreviewRefresh(PREVIEW_DELAY_CLICK_MS, false);
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
      // The stroke ends where the button was released. Usually the last move was at that very place; but when the
      // window was busy (showing the picture of the stroke before), the moves of a quick stroke may not have come
      // at all - and the stroke was then a dot at the place of the press, or stopped short.
      const hasPlace = e && Number.isFinite(e.clientX) && Number.isFinite(e.clientY) && !(e.clientX === 0 && e.clientY === 0);
      const end = hasPlace ? getNormalizedStagePoint(e.clientX, e.clientY) : null;
      const last = sessState.strokePoints[sessState.strokePoints.length - 1];
      if (end && last && (Math.abs(end.x - last.x) > 1e-4 || Math.abs(end.y - last.y) > 1e-4)) {
        sessState.strokePoints.push({ x: end.x, y: end.y, norm: true });
        renderBrushCursorAndDot(end, true);
      }
      sessState.isDrawing = false;
      const pts = sessState.strokePoints.slice();
      sessState.strokePoints = [];
      if (pts.length > 0 && sessState.id) {
        await sendMaskEditOp("stroke", pts);
      } else {
        clearStrokeDots();
        scheduleExactPreview();  // (it was put off while the mouse button was down)
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
  el("btnBackupSave").addEventListener("click", pressOrTakeBack("btnBackupSave", saveSettingsBackup));
  el("btnBackupRestore").addEventListener("click", pressOrTakeBack("btnBackupRestore", openBackupList));
  el("btnBackupOpenFolder").addEventListener("click", openBackupFolder);
  el("btnBackupClose").addEventListener("click", hideBackupBox);

  // Modal Topbar Controls
  // "До / Після": the photo as it was <-> the cleaned photo. "Маска": the red/green mask <-> the cleaned photo.
  el("dlgBtnBeforeAfter").addEventListener("click", () => {
    setView(sessState.view === "original" ? "result" : "original");
  });

  el("dlgBtnMask").addEventListener("click", () => {
    setView(sessState.view === "mask" ? "result" : "mask");
  });

  if (el("gChkDetail")) {
    onCheck("gChkDetail", () => {
      setDetailPreview(el("gChkDetail").checked);
      scheduleSaveSettings();
    });
    setDetailPreview(detailPreview, false);  // the box and the button show the value the settings brought
  }

  onCheck("dlgChkAutoPreset", () => {
    setAutoPreset(el("dlgChkAutoPreset").checked);
    scheduleSaveSettings();
    if (el("dlgHoverHint")) {
      el("dlgHoverHint").textContent = autoPreset
        ? "✓ Авто-пресет увімкнено: з наступного фото пресет підбиратиметься під кадр"
        : "Авто-пресет вимкнено: лишається пресет, який вибрали ви";
    }
  });

  onCheck("dlgChkDress", async () => {
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

  onCheck("dlgChkSmoke", () => {
    smokeEnabled = !!el("dlgChkSmoke").checked;
    updateSliderVisuals();
    scheduleSaveSettings();
    askSmokeNote();
    // The frame is recomputed at once, with the progress card (until 4.12.0: a light refresh, which the owner did
    // not take for a recompute - "I press the smoke tick and it does not recompute").
    // (what the server finds is said once the picture is back - see smokeNoteText)
    const live = sessState.open && sessState.id;
    sayInWindow(smokeEnabled
      ? "✓ Захист диму увімкнено" + (live ? " — шукаю дим у кадрі й перераховую…" : "")
      : "Захист диму вимкнено (повзунок у налаштуваннях неактивний)" + (live ? " — перераховую…" : ""));
    recomputeExactNow();
  });

  onCheck("dlgChkMix", () => {
    mixEnabled = !!el("dlgChkMix").checked;
    updateSliderVisuals();
    scheduleSaveSettings();
    requestPreviewRefresh(PREVIEW_DELAY_CLICK_MS, false);
    sayInWindow(mixEnabled
      ? `✓ Мікс-пензель увімкнено (${getSliderVal("gSlMix")}%): після чистки фон розгладжується. Силу змінює повзунок у налаштуваннях.`
      : "Мікс-пензель вимкнено: фон лишається таким, яким його залишила чистка.");
  });

  onCheck("dlgChkMakeMask", () => {
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
  if (el("gBtnMix")) {
    el("gBtnMix").addEventListener("click", () => {
      mixEnabled = !mixEnabled;
      updateSliderVisuals();
      scheduleSaveSettings();
      requestPreviewRefresh(PREVIEW_DELAY_CLICK_MS, false);
      sayInWindow(mixEnabled ? `✓ Мікс-пензель увімкнено (${getSliderVal("gSlMix")}%)` : "Мікс-пензель вимкнено");
    });
  }
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
    askSmokeNote();
    const live = sessState.open && sessState.id;
    sayInWindow(smokeEnabled
      ? "✓ Захист диму увімкнено" + (live ? " — шукаю дим у кадрі й перераховую…" : "")
      : "Захист диму вимкнено" + (live ? " — перераховую…" : ""));
    recomputeExactNow();  // (as the tick at the top of the window: the same switch)
  });
  el("gBtnDress").addEventListener("click", async () => {
    dressSmoothEnabled = !dressSmoothEnabled;
    updateSliderVisuals();
    scheduleSaveSettings();
    if (sessState.open && sessState.id) await sendDressPreviewUpdate();
  });
  onCheck("gChkShadow", () => {
    scheduleSaveSettings();
    requestPreviewRefresh(PREVIEW_DELAY_CLICK_MS, false);
  });
  onCheck("gChkRemoveStands", () => {
    scheduleSaveSettings();
    requestPreviewRefresh(PREVIEW_DELAY_CLICK_MS, false);
  });
  // The exact picture on request, at once and with the progress card. Not needed any more: the same picture comes
  // by itself after every change (scheduleExactPreview). The button stays for the case that it does not.
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
  // The same on the bottom bar, always at hand (the owner asked for it: "pull the recompute button out").
  // The settings stay open if they are: the values can be changed while the bar is running, and the run then
  // starts over with them.
  if (el("dlgBtnRecompute")) {
    el("dlgBtnRecompute").addEventListener("click", () => {
      if (sessState.isApplying) return;
      sayInWindow("↻ Перераховую точний кадр для значень на повзунках…");
      recomputeExactNow();
    });
  }
  el("gBtnSavePreset").addEventListener("click", async () => {
    disarmPresetReset();
    await saveCurrentConfigToActivePreset(true);
  });
  el("gBtnResetPreset").addEventListener("click", resetActivePresetToDefault);

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

  // The brush, the eraser and the inversion change the mask. The window keeps showing what it shows: on the
  // cleaned photo the result of every stroke is seen at once; the mask is seen when the user switched it on with
  // "Маска". The three actions on the whole mask say in words what they did (on the photo it is not obvious).
  el("dlgToolBrush").addEventListener("click", async (e) => {
    setActiveTool("brush");
    if (e.ctrlKey || e.metaKey) {
      const d = await sendMaskEditOp("fill");
      if (d) sayInWindow("Шар показано на всьому кадрі. Зони видно кнопкою «Маска»; скасувати — Ctrl + Z.");
    }
  });

  el("dlgToolEraser").addEventListener("click", async (e) => {
    setActiveTool("eraser");
    if (e.ctrlKey || e.metaKey) {
      const d = await sendMaskEditOp("clear");
      if (d) sayInWindow("Маску стерто повністю: шар тепер нічого не змінює. Скасувати — Ctrl + Z.");
    }
  });

  el("dlgToolInvert").addEventListener("click", async () => {
    const d = await sendMaskEditOp("invert");
    if (d) sayInWindow("Маску інвертовано: шар тепер діє там, де не діяв. Зони видно кнопкою «Маска»; скасувати — Ctrl + Z.");
  });

  // One step back / forward for the mask edits (the keys: Ctrl + Z, Ctrl + Shift + Z, Ctrl + Y - see below)
  el("dlgBtnUndo").addEventListener("click", () => stepMaskEdit(true));
  el("dlgBtnRedo").addEventListener("click", () => stepMaskEdit(false));

  el("dlgBrushSmaller").addEventListener("click", () => adjustBrushSize(-6));
  el("dlgBrushBigger").addEventListener("click", () => adjustBrushSize(6));
  el("dlgBrushSoft").addEventListener("click", () => setBrushSoft(true));
  el("dlgBrushHard").addEventListener("click", () => setBrushSoft(false));

  // Viewport Mouse Interactions: Draw / Pan / Peek Clean Photo Outside Image!
  const vp = el("dlgViewport");

  function startPan(e) {
    if (e.preventDefault) e.preventDefault();
    sessState.isPanning = true;
    sessState.panButton = e.button;
    sessState.panStartedMs = Date.now();
    sessState.panMoved = false;
    sessState.dragStartX = e.clientX;
    sessState.dragStartY = e.clientY;
    sessState.panStartX = sessState.panX;
    sessState.panStartY = sessState.panY;
    vp.style.cursor = "grabbing";
    const cur = el("dlgBrushCursor");
    if (cur) cur.style.display = "none";
  }

  function endPan() {
    if (!sessState.isPanning) return;
    sessState.isPanning = false;
    setActiveTool(sessState.tool);
  }

  // The right mouse button drags the photo, so it must not open a menu over it. Where the host reports the
  // release of the right button only this way (no "mouseup"), the drag ends here - but not at the press itself
  // (some systems send this event when the button goes down).
  vp.addEventListener("contextmenu", (e) => {
    if (!sessState.open) return;
    e.preventDefault();
    if (sessState.isPanning && sessState.panButton === 2 && (sessState.panMoved || Date.now() - sessState.panStartedMs > 250)) {
      endPan();
    }
  });

  // (Pointer events: a host that reports the right button only through them is served as well. Where both kinds
  //  of events come, the second one finds the drag already started and changes nothing.)
  vp.addEventListener("pointerdown", (e) => {
    if (!sessState.open || e.button !== 2 || sessState.isPanning) return;
    startPan(e);
  });
  document.addEventListener("pointermove", (e) => {
    if (!sessState.open || !sessState.isPanning || sessState.panButton !== 2) return;
    panTo(e.clientX, e.clientY);
  });
  document.addEventListener("pointerup", (e) => {
    if (sessState.isPanning && sessState.panButton === 2 && e.button === 2) endPan();
  });

  vp.addEventListener("mousedown", (e) => {
    if (!sessState.open) return;
    // Close open popovers when clicking viewport
    ["dlgPresetsPopover", "dlgGearPopover", "dlgInfoPopover"].forEach((id) => {
      if (el(id)) el(id).classList.remove("visible");
    });

    // Drag the photo: the right or the middle mouse button with any tool, Space + mouse, or the hand tool
    if (e.button === 1 || e.button === 2 || sessState.spaceDown || sessState.tool === "pan") {
      startPan(e);
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
      // The stroke is made on what is on screen: the cleaned photo (its result shows there the moment the mouse
      // is released) or the mask. Only "До" is left: nothing a stroke does can be seen on the original.
      if (sessState.view === "original") setView("result");
      sessState.isDrawing = true;
      sessState.strokeNo += 1;
      sessState.lastDotX = -1;
      sessState.lastDotY = -1;
      sessState.strokePoints = [{ x: pt.x, y: pt.y, norm: true }];
      renderBrushCursorAndDot(pt, true);
    }
  });

  vp.addEventListener("wheel", (e) => {
    if (!sessState.open || !sessState.pw) return;
    e.preventDefault();
    const r = vp.getBoundingClientRect();
    zoomBy(e.deltaY < 0 ? ZOOM_WHEEL_STEP : 1 / ZOOM_WHEEL_STEP, e.clientX - r.left - r.width * 0.5, e.clientY - r.top - r.height * 0.5);
  });

  // Keyboard shortcuts inside modal
  document.addEventListener("keydown", (e) => {
    if (!sessState.open) return;
    // Ctrl + Z: the last mask edit back; Ctrl + Shift + Z or Ctrl + Y: forward again. The key is told by its place
    // on the keyboard (e.code), so the Ukrainian layout works too. Inside a text field the keys keep their own
    // meaning; a checkbox that was clicked last does not swallow them.
    const t = e.target;
    const typing = !!t && (t.tagName === "TEXTAREA" || (t.tagName === "INPUT" && String(t.type || "text").toLowerCase() !== "checkbox"));
    if (!typing && (e.ctrlKey || e.metaKey) && !e.altKey) {
      const k = String(e.key || "").toLowerCase();
      const isZ = e.code === "KeyZ" || k === "z" || k === "я";
      const isY = e.code === "KeyY" || k === "y" || k === "н";
      if (isZ || isY) {
        e.preventDefault();
        if (e.stopPropagation) e.stopPropagation();
        stepMaskEdit(isZ && !e.shiftKey);
        return;
      }
      // Ctrl + "+" and Ctrl + "−" zoom in and out around the middle of the view, Ctrl + 0 fits the photo into the
      // window - the keys of Photoshop.
      const zoomKey = zoomKeyOf(e);
      if (zoomKey && sessState.pw) {
        e.preventDefault();
        if (e.stopPropagation) e.stopPropagation();
        if (zoomKey === "fit") resetZoomFit();
        else zoomBy(zoomKey === "in" ? ZOOM_KEY_STEP : 1 / ZOOM_KEY_STEP);
        return;
      }
    }
    if (typing) return;  // (a check box that was clicked last does not swallow the keys of the tools)
    const brushKey = (e.ctrlKey || e.metaKey || e.altKey) ? "" : brushKeyOf(e);
    if (e.code === "Space") {
      sessState.spaceDown = true;
      vp.style.cursor = "grab";
    } else if (brushKey) {
      e.preventDefault();
      adjustBrushSize(brushKey === "down" ? -brushKeyStep() : brushKeyStep());
      sayInWindow(`Розмір пензля: ${sessState.brushSize} (клавіші [ та ] — менше й більше)`);
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

  // Bottom Bar: Fractions + Auto + Zoom + Apply/Cancel
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

  el("dlgZoomOut").addEventListener("click", () => zoomBy(1 / ZOOM_BUTTON_STEP));
  el("dlgZoomIn").addEventListener("click", () => zoomBy(ZOOM_BUTTON_STEP));
  el("dlgZoomLabel").addEventListener("click", resetZoomFit);

  el("dlgBtnApply").addEventListener("click", applyInteractiveResultToPhotoshop);
  el("dlgBtnCancel").addEventListener("click", () => el("retouchModal").close("cancel"));
  el("dlgBtnCloseX").addEventListener("click", () => el("retouchModal").close("cancel"));
  el("dlgBtnCancelScan").addEventListener("click", () => {
    if (sessState.recomputing && !sessState.previewBusy && !sessState.isApplying && sessState.id) {
      // a full recompute is running: stop waiting for it, the window stays open
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
  if (!hasLocalSettings && presetsList.length > 0) {
    activePresetId = presetsList[0].id;
    applyConfig(presetsList[0].cfg);
  }
  // Defaults that changed since the presets on this PC were saved (the server copy follows at the first sync)
  const movedDefaults = applyPresetDefaultMoves();
  if (movedDefaults) settingsMigrated = true;
  if (appendNewDefaultPresets() || movedDefaults) {
    await writeLocalJson("presets_local.json", presetsList);
    await writeLocalJson("user_settings.json", buildSettingsSnapshot());
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
