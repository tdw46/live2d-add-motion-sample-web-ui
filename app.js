const statusElement = document.getElementById("status");
const avatarSelect = document.getElementById("avatarSelect");
const generateDialog = document.getElementById("generateDialog");
const generateForm = document.getElementById("generateForm");
const descriptionInput = document.getElementById("avatarDescription");
const generationProgress = document.getElementById("generationProgress");
const generationStatus = document.getElementById("generationStatus");
const progressBar = document.getElementById("progressBar");
const generatedPreview = document.getElementById("generatedPreview");
const submitGenerate = document.getElementById("submitGenerate");
const cancelGenerate = document.getElementById("cancelGenerate");
const closeDialog = document.getElementById("closeDialog");
const params = new URLSearchParams(location.search);

const localeOverride = params.get("lang");
const browserLocale = navigator.languages?.[0] || navigator.language || "en";
const locale = localeOverride === "ja" ||
  (localeOverride !== "en" && /^ja(?:-|$)/i.test(browserLocale)) ? "ja" : "en";

const messages = {
  en: {
    title: (name) => `Live2D Motion Sample - ${name}`,
    heading: (name) => `${name} Motion Player`,
    loading: "Loading…",
    subtitle: "Use the buttons to play motions manually",
    avatarLabel: "Avatar",
    avatarHint: "Hiyori stays the default; generated avatars appear here.",
    generateOption: "＋ Generate new…",
    generateTitle: "Generate a new avatar",
    generateSubtitle: "Gemini creates the artwork, See-through separates it, and the local rigging bridge builds a Live2D model.",
    descriptionLabel: "Character description",
    descriptionPlaceholder: "A cheerful space courier with short blue hair, a white flight jacket, and orange accents…",
    promptHint: "Describe identity, outfit, hair, and colors. The pipeline adds front-facing full-body staging automatically.",
    cancel: "Cancel",
    generateButton: "Generate avatar",
    submitting: "Starting the local generation pipeline…",
    jobQueued: "Queued behind any avatar currently being generated…",
    newActions: "Newly added motions",
    drag: "Drag",
    dragHint: "move the avatar",
    zoom: "Wheel or pinch",
    zoomHint: "zoom around the cursor",
    resetView: "Reset view (position and size)",
    missingConfig: "No default model configuration was found.",
    playing: (label) => `Playing: ${label}`,
    playFailed: (group, index) => `Playback failed: ${group}[${index}]`,
    existing: (group) => `Existing: ${group}`,
    idle: "Idle (the Idle group plays automatically)",
    ready: "Ready — choose a motion",
    autoplay: (play, started) => `Auto-play: ${play} started=${started}`,
    error: (message) => `Error: ${message}`,
    generationFailed: (message) => `Generation failed: ${message}`,
  },
  ja: {
    title: (name) => `Live2D モーション追加サンプル - ${name}`,
    heading: (name) => `${name} モーション再生`,
    loading: "読み込み中…",
    subtitle: "ボタンでモーションを手動再生できます",
    avatarLabel: "アバター",
    avatarHint: "ひよりが初期設定です。生成したアバターもここに追加されます。",
    generateOption: "＋ 新しいアバターを生成…",
    generateTitle: "新しいアバターを生成",
    generateSubtitle: "Geminiで全身画像を作成し、See-throughでレイヤー分けして、ローカルのリグ処理でLive2Dモデルを生成します。",
    descriptionLabel: "キャラクターの説明",
    descriptionPlaceholder: "青いショートヘア、白いフライトジャケット、オレンジの差し色が特徴の明るい宇宙配達員…",
    promptHint: "人物、衣装、髪型、色を説明してください。正面向きの全身構図は自動で追加されます。",
    cancel: "キャンセル",
    generateButton: "アバターを生成",
    submitting: "ローカル生成パイプラインを開始しています…",
    jobQueued: "先に実行中のアバター生成が終わるまで待機しています…",
    newActions: "今回追加したモーション",
    drag: "ドラッグ",
    dragHint: "アバターを移動",
    zoom: "ホイール・ピンチ",
    zoomHint: "カーソル位置を中心に拡大縮小",
    resetView: "表示リセット (位置・サイズ)",
    missingConfig: "初期モデル設定が見つかりません。",
    playing: (label) => `再生中: ${label}`,
    playFailed: (group, index) => `再生失敗: ${group}[${index}]`,
    existing: (group) => `既存: ${group}`,
    idle: "アイドル中 (Idleグループ自動再生)",
    ready: "準備完了 — ボタンを押してください",
    autoplay: (play, started) => `自動再生: ${play} started=${started}`,
    error: (message) => `エラー: ${message}`,
    generationFailed: (message) => `生成に失敗しました: ${message}`,
  },
};
const t = messages[locale];

document.documentElement.lang = locale;
document.querySelectorAll("[data-i18n]").forEach((element) => {
  const value = t[element.dataset.i18n];
  if (typeof value === "string") element.textContent = value;
});
document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
  const value = t[element.dataset.i18nPlaceholder];
  if (typeof value === "string") element.placeholder = value;
});
statusElement.textContent = t.loading;

let avatarCatalog = [];
let currentAvatar = null;
let activeJobId = null;

function updateAvatarIdentity(avatar) {
  const name = avatar?.name || "Live2D";
  document.title = t.title(name);
  document.querySelector("#panel h1").textContent = t.heading(name);
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || payload.message || `${response.status} ${response.statusText}`);
  return payload;
}

async function loadAvatarCatalog() {
  const requested = params.get("avatar");
  try {
    const payload = await fetchJson("/api/avatars");
    avatarCatalog = payload.avatars || [];
  } catch {
    const response = await fetch("model.config.json");
    if (!response.ok) throw new Error(t.missingConfig);
    const cfg = await response.json();
    avatarCatalog = [{ id: "hiyori", name: cfg.name || "Hiyori", model3: cfg.model3, default: true }];
  }

  currentAvatar = avatarCatalog.find((avatar) => avatar.id === requested)
    || avatarCatalog.find((avatar) => avatar.default)
    || avatarCatalog[0];
  if (!currentAvatar) throw new Error(t.missingConfig);

  avatarSelect.innerHTML = "";
  const defaultAvatar = avatarCatalog.find((avatar) => avatar.default) || avatarCatalog[0];
  const ordered = [defaultAvatar, ...avatarCatalog.filter((avatar) => avatar !== defaultAvatar)];
  ordered.forEach((avatar) => {
    const option = document.createElement("option");
    option.value = avatar.id;
    option.textContent = avatar.name;
    avatarSelect.appendChild(option);
  });
  const generateOption = document.createElement("option");
  generateOption.value = "__generate__";
  generateOption.textContent = t.generateOption;
  avatarSelect.insertBefore(generateOption, avatarSelect.options[1] || null);
  avatarSelect.value = currentAvatar.id;
  avatarSelect.disabled = false;
  updateAvatarIdentity(currentAvatar);
  return currentAvatar.model3;
}

function openGenerator() {
  avatarSelect.value = currentAvatar.id;
  generationProgress.hidden = true;
  generationStatus.classList.remove("error");
  progressBar.style.width = "4%";
  generatedPreview.hidden = true;
  submitGenerate.disabled = false;
  cancelGenerate.disabled = false;
  closeDialog.disabled = false;
  generateDialog.showModal();
  setTimeout(() => descriptionInput.focus(), 0);
}

avatarSelect.addEventListener("change", () => {
  if (avatarSelect.value === "__generate__") {
    openGenerator();
    return;
  }
  const next = new URL(location.href);
  if (avatarSelect.value === (avatarCatalog.find((avatar) => avatar.default)?.id || "hiyori")) {
    next.searchParams.delete("avatar");
  } else {
    next.searchParams.set("avatar", avatarSelect.value);
  }
  location.assign(next);
});

function closeGenerator() {
  if (activeJobId) return;
  generateDialog.close();
  avatarSelect.value = currentAvatar.id;
}
cancelGenerate.addEventListener("click", closeGenerator);
closeDialog.addEventListener("click", closeGenerator);
generateDialog.addEventListener("cancel", (event) => {
  if (activeJobId) event.preventDefault();
});

function phaseProgress(phase) {
  return ({ queued: 5, gemini: 18, seethrough: 46, rigging: 82, complete: 100, failed: 100 })[phase] || 8;
}

async function pollGeneration(jobId) {
  while (activeJobId === jobId) {
    const job = await fetchJson(`/api/avatar-jobs/${encodeURIComponent(jobId)}`);
    generationStatus.textContent = job.message || t.jobQueued;
    progressBar.style.width = `${phaseProgress(job.phase)}%`;
    if (job.source_url) {
      generatedPreview.src = `${job.source_url}?v=${Date.now()}`;
      generatedPreview.hidden = false;
    }
    if (job.phase === "complete") {
      activeJobId = null;
      const next = new URL(location.href);
      next.searchParams.set("avatar", job.avatar.id);
      location.assign(next);
      return;
    }
    if (job.phase === "failed") {
      activeJobId = null;
      generationStatus.textContent = t.generationFailed(job.error || "Unknown error");
      generationStatus.classList.add("error");
      submitGenerate.disabled = false;
      cancelGenerate.disabled = false;
      closeDialog.disabled = false;
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
}

generateForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const description = descriptionInput.value.trim();
  if (!description) return;
  generationProgress.hidden = false;
  generationStatus.classList.remove("error");
  generationStatus.textContent = t.submitting;
  submitGenerate.disabled = true;
  cancelGenerate.disabled = true;
  closeDialog.disabled = true;
  try {
    const payload = await fetchJson("/api/avatars/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ description, locale }),
    });
    activeJobId = payload.job_id;
    await pollGeneration(activeJobId);
  } catch (error) {
    activeJobId = null;
    generationStatus.textContent = t.generationFailed(error.message);
    generationStatus.classList.add("error");
    submitGenerate.disabled = false;
    cancelGenerate.disabled = false;
    closeDialog.disabled = false;
  }
});

async function main() {
  const modelJson = params.get("model") || await loadAvatarCatalog();
  const stage = document.getElementById("stage");
  const app = new PIXI.Application({
    backgroundAlpha: 0,
    preserveDrawingBuffer: true,
    resizeTo: stage,
    autoDensity: true,
    resolution: window.devicePixelRatio || 1,
  });
  stage.appendChild(app.view);

  const model = await PIXI.live2d.Live2DModel.from(modelJson);
  app.stage.addChild(model);

  let userAdjusted = false;
  function layout() {
    const scale = Math.min(
      app.screen.width / model.internalModel.width,
      app.screen.height / model.internalModel.height,
    ) * 1.1;
    model.scale.set(scale);
    model.anchor.set(0.5, 0.5);
    model.position.set(app.screen.width / 2, app.screen.height / 2 + app.screen.height * 0.05);
  }
  layout();
  app.renderer.on("resize", () => { if (!userAdjusted) layout(); });

  model.interactive = true;
  model.buttonMode = true;
  let drag = null;
  model.on("pointerdown", (event) => {
    drag = { dx: event.data.global.x - model.x, dy: event.data.global.y - model.y };
  });
  model.on("pointermove", (event) => {
    if (!drag) return;
    userAdjusted = true;
    model.position.set(event.data.global.x - drag.dx, event.data.global.y - drag.dy);
  });
  model.on("pointerup", () => { drag = null; });
  model.on("pointerupoutside", () => { drag = null; });

  const MIN_SCALE = 0.05;
  const MAX_SCALE = 5;
  app.view.addEventListener("wheel", (event) => {
    event.preventDefault();
    const rect = app.view.getBoundingClientRect();
    const mx = event.clientX - rect.left;
    const my = event.clientY - rect.top;
    const base = model.scale.x;
    const next = Math.min(MAX_SCALE, Math.max(MIN_SCALE, base * Math.exp(-event.deltaY * 0.002)));
    const factor = next / base;
    if (factor === 1) return;
    userAdjusted = true;
    model.scale.set(next);
    model.position.set(mx + (model.x - mx) * factor, my + (model.y - my) * factor);
  }, { passive: false });

  document.getElementById("resetView").onclick = () => {
    userAdjusted = false;
    layout();
  };

  const settings = model.internalModel.settings;
  const groups = settings.motions || {};
  const newGroup = "Action";

  function motionButton(group, entry, index) {
    const button = document.createElement("button");
    button.className = `motion${group === newGroup ? " new" : ""}`;
    const file = entry.File.split("/").pop().replace(".motion3.json", "");
    const label = entry.Names?.[locale] || entry.Name || file;
    button.append(label);
    const small = document.createElement("span");
    small.className = "file";
    small.textContent = file;
    button.appendChild(small);
    button.onclick = async () => {
      statusElement.textContent = t.playing(label);
      const ok = await model.motion(group, index, PIXI.live2d.MotionPriority.FORCE);
      if (!ok) statusElement.textContent = t.playFailed(group, index);
    };
    return button;
  }

  const newButtons = document.getElementById("newButtons");
  const addedMotions = groups[newGroup] || [];
  document.getElementById("newActions").hidden = addedMotions.length === 0;
  addedMotions.forEach((entry, index) => newButtons.appendChild(motionButton(newGroup, entry, index)));

  const container = document.getElementById("buttons");
  for (const [group, entries] of Object.entries(groups)) {
    if (group === newGroup) continue;
    const details = document.createElement("details");
    details.className = "group";
    const summary = document.createElement("summary");
    summary.append(t.existing(group));
    const count = document.createElement("span");
    count.className = "count";
    count.textContent = entries.length;
    summary.appendChild(count);
    details.appendChild(summary);
    const body = document.createElement("div");
    body.className = "body";
    entries.forEach((entry, index) => body.appendChild(motionButton(group, entry, index)));
    details.appendChild(body);
    container.appendChild(details);
  }

  model.internalModel.motionManager.on("motionFinish", () => {
    statusElement.textContent = t.idle;
  });
  statusElement.textContent = t.ready;

  if (params.get("uitest")) {
    setTimeout(() => {
      const before = { x: model.x, y: model.y, s: model.scale.x };
      const rect = app.view.getBoundingClientRect();
      const cx = rect.left + before.x;
      const cy = rect.top + before.y;
      const pointer = (type, x, y) => new PointerEvent(type, {
        clientX: x, clientY: y, pointerId: 1, pointerType: "mouse",
        isPrimary: true, buttons: 1, bubbles: true,
      });
      app.view.dispatchEvent(pointer("pointerdown", cx, cy));
      document.dispatchEvent(pointer("pointermove", cx + 120, cy + 60));
      document.dispatchEvent(pointer("pointerup", cx + 120, cy + 60));
      const afterDrag = { x: model.x, y: model.y };
      app.view.dispatchEvent(new WheelEvent("wheel", {
        clientX: cx, clientY: cy, deltaY: -300, bubbles: true, cancelable: true,
      }));
      statusElement.textContent =
        `uitest drag:(${before.x.toFixed(0)},${before.y.toFixed(0)})->` +
        `(${afterDrag.x.toFixed(0)},${afterDrag.y.toFixed(0)}) ` +
        `zoom:${before.s.toFixed(3)}->${model.scale.x.toFixed(3)}`;
    }, 300);
  }

  const play = params.get("play");
  if (play) {
    const [group, index] = play.split(":");
    const started = await model.motion(group, Number(index || 0), PIXI.live2d.MotionPriority.FORCE);
    statusElement.textContent = t.autoplay(play, started);
    const freeze = Number(params.get("freeze"));
    if (freeze > 0) setTimeout(() => {
      const manager = model.internalModel.motionManager;
      statusElement.textContent += ` frozen@${freeze}s playing=${manager.playing}`;
      manager.update = () => true;
    }, freeze * 1000);
  }
}

main().catch((error) => {
  statusElement.textContent = t.error(error.message);
  console.error(error);
});
