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
const layerEditor = document.getElementById("layerEditor");
const layerCount = document.getElementById("layerCount");
const layerList = document.getElementById("layerList");
const layerSaveStatus = document.getElementById("layerSaveStatus");
const resetLayerOrder = document.getElementById("resetLayerOrder");
const saveLayerOrder = document.getElementById("saveLayerOrder");
const regenerateLayers = document.getElementById("regenerateLayers");
const regenerateLayersStatus = document.getElementById("regenerateLayersStatus");
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
    layerOrder: "Layer order",
    layerHint: "Frontmost is at the top. Drag layers or use the arrow buttons.",
    restoreLayerOrder: "Restore model order",
    saveLayerOrder: "Save order",
    moveLayerUp: (name) => `Move ${name} toward the front`,
    moveLayerDown: (name) => `Move ${name} toward the back`,
    hideLayer: (name) => `Hide ${name}`,
    showLayer: (name) => `Show ${name}`,
    soloLayer: (name) => `Show only ${name}`,
    unsoloLayer: (name) => `Stop showing only ${name}`,
    layerUnsaved: "Unsaved layer changes",
    layerSaved: "Layer order saved to this avatar",
    layerLoaded: "Saved layer order applied",
    layerRestored: "Model order restored — save to keep it",
    layerSaveFailed: (message) => `Could not save layer order: ${message}`,
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
    regenerateLayers: "Regenerate layers",
    regeneratingLayers: "Rebuilding from the current semantic PSD…",
    regenerateLayersQueued: "Layer regeneration queued…",
    regenerateLayersDone: "Layers regenerated — reloading the avatar…",
    regenerateLayersFailed: (message) => `Could not regenerate layers: ${message}`,
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
    layerOrder: "レイヤー順序",
    layerHint: "一番上が最前面です。ドラッグまたは矢印ボタンで並べ替えます。",
    restoreLayerOrder: "モデルの順序に戻す",
    saveLayerOrder: "順序を保存",
    moveLayerUp: (name) => `${name}を前面へ移動`,
    moveLayerDown: (name) => `${name}を背面へ移動`,
    hideLayer: (name) => `${name}を非表示`,
    showLayer: (name) => `${name}を表示`,
    soloLayer: (name) => `${name}だけを表示`,
    unsoloLayer: (name) => `${name}だけの表示を解除`,
    layerUnsaved: "レイヤー順序は未保存です",
    layerSaved: "このアバターにレイヤー順序を保存しました",
    layerLoaded: "保存済みのレイヤー順序を適用しました",
    layerRestored: "モデル順序に戻しました。保存すると維持されます。",
    layerSaveFailed: (message) => `レイヤー順序を保存できませんでした: ${message}`,
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
    regenerateLayers: "レイヤーを再生成",
    regeneratingLayers: "現在のセマンティックPSDから再構築しています…",
    regenerateLayersQueued: "レイヤー再生成を待機しています…",
    regenerateLayersDone: "レイヤーを再生成しました。アバターを再読み込みします…",
    regenerateLayersFailed: (message) => `レイヤーを再生成できませんでした: ${message}`,
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
let activeLayerJobId = null;

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
  regenerateLayers.hidden = !currentAvatar.can_regenerate_layers;
  updateAvatarIdentity(currentAvatar);
  if (!currentAvatar.generated) return currentAvatar.model3;
  // PIXI/live2d caches the entire model by its model3 URL. Generated bundles are rebuilt in place,
  // so a fresh page must use a fresh settings cache key before the versioned MOC/texture URLs inside
  // the newly emitted model3 can take effect.
  const modelUrl = new URL(currentAvatar.model3, document.baseURI);
  modelUrl.searchParams.set("build", Date.now().toString());
  return modelUrl.href;
}

async function pollLayerRegeneration(jobId) {
  while (activeLayerJobId === jobId) {
    const job = await fetchJson(`/api/avatar-jobs/${encodeURIComponent(jobId)}`);
    regenerateLayersStatus.textContent = job.message || t.regenerateLayersQueued;
    if (job.phase === "complete") {
      activeLayerJobId = null;
      regenerateLayersStatus.textContent = t.regenerateLayersDone;
      regenerateLayersStatus.className = "avatar-job-status success";
      const next = new URL(location.href);
      next.searchParams.set("layers", Date.now().toString());
      location.assign(next);
      return;
    }
    if (job.phase === "failed") {
      throw new Error(job.error || "Unknown error");
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
}

regenerateLayers.addEventListener("click", async () => {
  if (!currentAvatar?.can_regenerate_layers || activeLayerJobId) return;
  regenerateLayers.disabled = true;
  regenerateLayersStatus.className = "avatar-job-status";
  regenerateLayersStatus.textContent = t.regeneratingLayers;
  try {
    const payload = await fetchJson(
      `/api/avatars/${encodeURIComponent(currentAvatar.id)}/regenerate-layers`,
      { method: "POST" },
    );
    activeLayerJobId = payload.job_id;
    await pollLayerRegeneration(activeLayerJobId);
  } catch (error) {
    activeLayerJobId = null;
    regenerateLayers.disabled = false;
    regenerateLayersStatus.textContent = t.regenerateLayersFailed(error.message);
    regenerateLayersStatus.className = "avatar-job-status error";
  }
});

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

async function loadDrawableLabels(modelJson) {
  try {
    const modelUrl = new URL(modelJson, document.baseURI);
    const definition = await fetchJson(modelUrl, { cache: "no-store" });
    const displayInfo = definition.FileReferences?.DisplayInfo;
    if (!displayInfo) return new Map();
    const cdi = await fetchJson(new URL(displayInfo, modelUrl), { cache: "no-store" });
    return new Map((cdi.Parts || []).map((part) => [part.Id, part.Name || part.Id]));
  } catch {
    return new Map();
  }
}

function normalizedLayerOrder(savedOrder, modelOrder) {
  const available = new Set(modelOrder);
  const seen = new Set();
  const normalized = [];
  if (Array.isArray(savedOrder)) {
    savedOrder.forEach((id) => {
      if (available.has(id) && !seen.has(id)) {
        normalized.push(id);
        seen.add(id);
      }
    });
  }
  modelOrder.forEach((id) => {
    if (!seen.has(id)) normalized.push(id);
  });
  return normalized;
}

function drawableThumbnail(model, coreModel, drawableId, size = 80) {
  try {
    const drawableIndex = coreModel.getDrawableIndex(drawableId);
    if (drawableIndex < 0) return "";
    const textureIndex = coreModel.getDrawableTextureIndices(drawableIndex);
    const texture = model.textures?.[textureIndex];
    const source = texture?.baseTexture?.resource?.source;
    const sourceWidth = source?.naturalWidth || source?.videoWidth || source?.width || 0;
    const sourceHeight = source?.naturalHeight || source?.videoHeight || source?.height || 0;
    const uvs = coreModel.getDrawableVertexUvs(drawableIndex);
    const indices = coreModel.getDrawableVertexIndices(drawableIndex);
    if (!source || !sourceWidth || !sourceHeight || !uvs?.length || !indices?.length) return "";

    // Cubism's fragment shader flips the V coordinate before sampling the
    // texture. Mirror that conversion for previews drawn by the HTML canvas.
    const canvasUvs = new Float32Array(uvs.length);
    const us = [];
    const vs = [];
    for (let i = 0; i < uvs.length; i += 2) {
      const u = uvs[i];
      const v = 1 - uvs[i + 1];
      canvasUvs[i] = u;
      canvasUvs[i + 1] = v;
      us.push(u);
      vs.push(v);
    }
    const uMin = Math.max(0, Math.min(...us));
    const uMax = Math.min(1, Math.max(...us));
    const vMin = Math.max(0, Math.min(...vs));
    const vMax = Math.min(1, Math.max(...vs));
    const cropWidth = Math.max(1, (uMax - uMin) * sourceWidth);
    const cropHeight = Math.max(1, (vMax - vMin) * sourceHeight);
    const padding = 6;
    const scale = Math.min((size - padding * 2) / cropWidth, (size - padding * 2) / cropHeight);
    const drawWidth = cropWidth * scale;
    const drawHeight = cropHeight * scale;
    const offsetX = (size - drawWidth) / 2;
    const offsetY = (size - drawHeight) / 2;

    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    const context = canvas.getContext("2d");
    context.imageSmoothingEnabled = true;
    context.imageSmoothingQuality = "high";

    const point = (vertexIndex) => ({
      x: offsetX + ((canvasUvs[vertexIndex * 2] - uMin) * sourceWidth * scale),
      y: offsetY + ((canvasUvs[vertexIndex * 2 + 1] - vMin) * sourceHeight * scale),
    });
    for (let i = 0; i < indices.length; i += 3) {
      const first = point(indices[i]);
      const second = point(indices[i + 1]);
      const third = point(indices[i + 2]);
      context.save();
      context.beginPath();
      context.moveTo(first.x, first.y);
      context.lineTo(second.x, second.y);
      context.lineTo(third.x, third.y);
      context.closePath();
      context.clip();
      context.drawImage(
        source,
        uMin * sourceWidth,
        vMin * sourceHeight,
        cropWidth,
        cropHeight,
        offsetX,
        offsetY,
        drawWidth,
        drawHeight,
      );
      context.restore();
    }
    return canvas.toDataURL("image/png");
  } catch {
    return "";
  }
}

async function setupLayerEditor(model, modelJson) {
  if (!currentAvatar) return;
  const internalModel = model.internalModel;
  const coreModel = internalModel?.coreModel;
  const renderer = internalModel?.renderer;
  if (
    !coreModel?.getDrawableIds ||
    !coreModel?.getDrawableRenderOrders ||
    !coreModel?.getDrawableOpacity ||
    !renderer?.doDrawModel
  ) {
    return;
  }

  const drawableIds = Array.from(coreModel.getDrawableIds());
  const initialRenderOrders = Array.from(coreModel.getDrawableRenderOrders());
  const modelOrder = drawableIds
    .map((id, index) => ({ id, order: initialRenderOrders[index] }))
    .sort((left, right) => right.order - left.order)
    .map((entry) => entry.id);
  let currentOrder = normalizedLayerOrder(currentAvatar.viewer?.layer_order, modelOrder);
  let savedOrder = [...currentOrder];
  const hiddenIds = new Set();
  let soloId = null;
  let draggedId = null;

  function applyLayerOrder() {
    const renderOrders = coreModel.getDrawableRenderOrders();
    currentOrder.forEach((id, frontIndex) => {
      const drawableIndex = coreModel.getDrawableIndex(id);
      if (drawableIndex >= 0) renderOrders[drawableIndex] = currentOrder.length - 1 - frontIndex;
    });
  }

  // Cubism 4 exposes opacity as a per-drawable getter rather than a mutable opacity array. Wrap the
  // getter so hidden/solo state composes with native animated opacity (blink, expressions, etc.).
  const originalGetDrawableOpacity = coreModel.getDrawableOpacity.bind(coreModel);
  coreModel.getDrawableOpacity = (drawableIndex) => {
    const id = drawableIds[drawableIndex];
    const shouldShow = soloId ? id === soloId : !hiddenIds.has(id);
    return shouldShow ? originalGetDrawableOpacity(drawableIndex) : 0;
  };

  const originalDrawModel = renderer.doDrawModel.bind(renderer);
  renderer.doDrawModel = () => {
    applyLayerOrder();
    originalDrawModel();
  };
  applyLayerOrder();

  const labels = await loadDrawableLabels(modelJson);
  const thumbnails = new Map(drawableIds.map((id) => [id, drawableThumbnail(model, coreModel, id)]));
  layerCount.textContent = drawableIds.length;
  layerEditor.hidden = false;

  function setSaveState(message, className = "") {
    layerSaveStatus.textContent = message;
    layerSaveStatus.className = `layer-save-status ${className}`.trim();
    saveLayerOrder.disabled = JSON.stringify(currentOrder) === JSON.stringify(savedOrder);
  }

  function moveLayer(fromIndex, toIndex) {
    if (fromIndex < 0 || fromIndex >= currentOrder.length) return;
    const boundedTarget = Math.max(0, Math.min(currentOrder.length - 1, toIndex));
    if (fromIndex === boundedTarget) return;
    const [id] = currentOrder.splice(fromIndex, 1);
    currentOrder.splice(boundedTarget, 0, id);
    applyLayerOrder();
    renderLayerList();
    setSaveState(t.layerUnsaved);
  }

  function renderLayerList() {
    const previousScrollTop = layerList.scrollTop;
    layerList.replaceChildren();
    layerList.dataset.order = currentOrder.join("|");
    currentOrder.forEach((id, index) => {
      const name = labels.get(id) || id.replace(/_/g, " ");
      const row = document.createElement("li");
      row.className = "layer-row";
      row.dataset.drawableId = id;
      row.title = id;
      row.draggable = true;
      row.classList.toggle("layer-hidden", hiddenIds.has(id));
      row.classList.toggle("layer-solo", soloId === id);
      row.classList.toggle("layer-solo-muted", Boolean(soloId && soloId !== id));

      const handle = document.createElement("span");
      handle.className = "layer-handle";
      handle.textContent = "⠿";
      handle.setAttribute("aria-hidden", "true");

      const thumbnail = document.createElement(thumbnails.get(id) ? "img" : "span");
      thumbnail.className = `layer-thumbnail${thumbnails.get(id) ? "" : " empty"}`;
      thumbnail.setAttribute("aria-hidden", "true");
      if (thumbnails.get(id)) {
        thumbnail.src = thumbnails.get(id);
        thumbnail.alt = "";
      } else {
        thumbnail.textContent = "·";
      }

      const label = document.createElement("span");
      label.className = "layer-name";
      label.append(name);

      const visibility = document.createElement("button");
      const isVisible = !hiddenIds.has(id);
      visibility.type = "button";
      visibility.className = `layer-tool layer-visibility${isVisible ? "" : " is-off"}`;
      visibility.innerHTML = [
        '<svg viewBox="0 0 24 24" aria-hidden="true">',
        '<path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z"></path>',
        '<circle cx="12" cy="12" r="3"></circle>',
        '</svg>',
      ].join("");
      visibility.setAttribute("aria-pressed", String(isVisible));
      visibility.setAttribute("aria-label", isVisible ? t.hideLayer(name) : t.showLayer(name));
      visibility.addEventListener("click", () => {
        if (hiddenIds.has(id)) hiddenIds.delete(id);
        else hiddenIds.add(id);
        renderLayerList();
      });

      const solo = document.createElement("button");
      const isSolo = soloId === id;
      solo.type = "button";
      solo.className = `layer-tool layer-solo-toggle${isSolo ? " is-active" : ""}`;
      solo.textContent = isSolo ? "★" : "☆";
      solo.setAttribute("aria-pressed", String(isSolo));
      solo.setAttribute("aria-label", isSolo ? t.unsoloLayer(name) : t.soloLayer(name));
      solo.addEventListener("click", () => {
        soloId = isSolo ? null : id;
        renderLayerList();
      });

      const up = document.createElement("button");
      up.type = "button";
      up.className = "layer-move";
      up.textContent = "↑";
      up.disabled = index === 0;
      up.setAttribute("aria-label", t.moveLayerUp(name));
      up.addEventListener("click", () => moveLayer(index, index - 1));

      const down = document.createElement("button");
      down.type = "button";
      down.className = "layer-move";
      down.textContent = "↓";
      down.disabled = index === currentOrder.length - 1;
      down.setAttribute("aria-label", t.moveLayerDown(name));
      down.addEventListener("click", () => moveLayer(index, index + 1));

      row.addEventListener("dragstart", (event) => {
        draggedId = id;
        row.classList.add("dragging");
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", id);
      });
      row.addEventListener("dragover", (event) => {
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
        row.classList.add("drag-over");
      });
      row.addEventListener("dragleave", () => row.classList.remove("drag-over"));
      row.addEventListener("drop", (event) => {
        event.preventDefault();
        row.classList.remove("drag-over");
        const fromIndex = currentOrder.indexOf(draggedId);
        let toIndex = currentOrder.indexOf(id);
        if (fromIndex < toIndex) toIndex -= 1;
        moveLayer(fromIndex, toIndex);
      });
      row.addEventListener("dragend", () => {
        draggedId = null;
        layerList.querySelectorAll(".layer-row").forEach((item) => {
          item.classList.remove("dragging", "drag-over");
        });
      });

      row.append(handle, thumbnail, label, visibility, solo, up, down);
      layerList.appendChild(row);
    });
    const restoreScroll = () => {
      const maximumScrollTop = Math.max(0, layerList.scrollHeight - layerList.clientHeight);
      layerList.scrollTop = Math.min(previousScrollTop, maximumScrollTop);
    };
    restoreScroll();
    requestAnimationFrame(restoreScroll);
  }

  resetLayerOrder.addEventListener("click", () => {
    currentOrder = [...modelOrder];
    applyLayerOrder();
    renderLayerList();
    setSaveState(t.layerRestored);
  });

  saveLayerOrder.addEventListener("click", async () => {
    saveLayerOrder.disabled = true;
    try {
      const payload = await fetchJson(
        `/api/avatars/${encodeURIComponent(currentAvatar.id)}/viewer-metadata`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ layer_order: currentOrder }),
        },
      );
      savedOrder = [...payload.viewer.layer_order];
      currentAvatar.viewer = payload.viewer;
      setSaveState(t.layerSaved, "saved");
    } catch (error) {
      setSaveState(t.layerSaveFailed(error.message), "error");
      saveLayerOrder.disabled = false;
    }
  });

  renderLayerList();
  const hasSavedOrder = Array.isArray(currentAvatar.viewer?.layer_order);
  setSaveState(hasSavedOrder ? t.layerLoaded : "", hasSavedOrder ? "saved" : "");
}

async function setupModelAwareGaze(model, app, modelJson) {
  const canvas = app.view;
  const internalModel = model.internalModel;
  const coreModel = internalModel?.coreModel;
  const labels = await loadDrawableLabels(modelJson);
  const drawableIds = coreModel?.getDrawableIds ? Array.from(coreModel.getDrawableIds()) : [];
  const drawables = drawableIds.map((id) => {
    const index = coreModel.getDrawableIndex(id);
    return {
      id,
      name: labels.get(id) || id,
      bounds: internalModel.getDrawableBounds(index),
    };
  });
  const geometry = window.Live2DGaze?.buildGeometry(drawables);
  const point = new PIXI.Point();
  let lastTarget = { x: 0, y: 0, amplitude: 0 };

  function publishDebug() {
    if (!params.has("gazedebug")) return;
    document.documentElement.dataset.gazeTarget = JSON.stringify(lastTarget);
    document.documentElement.dataset.gazeFocus = JSON.stringify({
      x: internalModel.focusController.x,
      y: internalModel.focusController.y,
      targetX: internalModel.focusController.targetX,
      targetY: internalModel.focusController.targetY,
    });
  }

  function reset() {
    lastTarget = { x: 0, y: 0, amplitude: 0 };
    internalModel.focusController.focus(0, 0);
    publishDebug();
  }

  function onPointerMove(event) {
    const rect = canvas.getBoundingClientRect();
    const screenX = (event.clientX - rect.left) * (app.screen.width / rect.width);
    const screenY = (event.clientY - rect.top) * (app.screen.height / rect.height);

    if (!geometry) {
      model.focus(screenX, screenY);
      return;
    }

    point.set(screenX, screenY);
    model.toModelPosition(point, point);
    lastTarget = window.Live2DGaze.targetForPoint(geometry, point);
    internalModel.focusController.focus(lastTarget.x, lastTarget.y);
    publishDebug();
  }

  canvas.addEventListener("pointermove", onPointerMove);
  canvas.addEventListener("pointerleave", reset);
  reset();
  if (params.has("gazedebug")) {
    const topLeft = model.toGlobal(new PIXI.Point(geometry?.eyeBounds.x || 0, geometry?.eyeBounds.y || 0));
    const bottomRight = model.toGlobal(new PIXI.Point(
      (geometry?.eyeBounds.x || 0) + (geometry?.eyeBounds.width || 0),
      (geometry?.eyeBounds.y || 0) + (geometry?.eyeBounds.height || 0),
    ));
    document.documentElement.dataset.gazeReady = "true";
    document.documentElement.dataset.gazeGeometry = JSON.stringify(geometry);
    document.documentElement.dataset.gazeWorldBounds = JSON.stringify({
      x: topLeft.x,
      y: topLeft.y,
      width: bottomRight.x - topLeft.x,
      height: bottomRight.y - topLeft.y,
    });
    if (geometry) {
      const right = geometry.eyeBounds.x + geometry.eyeBounds.width;
      document.documentElement.dataset.gazeSamples = JSON.stringify({
        betweenEyes: window.Live2DGaze.targetForPoint(geometry, {
          x: geometry.centerX,
          y: geometry.irisMidY,
        }),
        nearRight: window.Live2DGaze.targetForPoint(geometry, {
          x: right + geometry.reach * 0.1,
          y: geometry.irisMidY,
        }),
        farRight: window.Live2DGaze.targetForPoint(geometry, {
          x: right + geometry.reach * 2,
          y: geometry.irisMidY,
        }),
        farAbove: window.Live2DGaze.targetForPoint(geometry, {
          x: geometry.centerX,
          y: geometry.eyeBounds.y - geometry.reach * 2,
        }),
      });
    }
  }
  return {
    geometry,
    get target() { return { ...lastTarget }; },
  };
}

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

  const model = await PIXI.live2d.Live2DModel.from(modelJson, { autoInteract: false });
  app.stage.addChild(model);
  await setupLayerEditor(model, modelJson);

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
  const gaze = await setupModelAwareGaze(model, app, modelJson);
  if (params.has("gazedebug")) window.__live2dGazeDebug = { app, model, gaze };

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
