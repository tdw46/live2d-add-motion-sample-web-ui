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
const layerRegenerateDialog = document.getElementById("layerRegenerateDialog");
const layerRegenerateForm = document.getElementById("layerRegenerateForm");
const layerRegenerateName = document.getElementById("layerRegenerateName");
const layerInstruction = document.getElementById("layerInstruction");
const includeRelatedLayers = document.getElementById("includeRelatedLayers");
const relatedLayersHint = document.getElementById("relatedLayersHint");
const preserveLayerColors = document.getElementById("preserveLayerColors");
const useGeneratedLayerMask = document.getElementById("useGeneratedLayerMask");
const layerChangeAmount = document.getElementById("layerChangeAmount");
const attachmentLock = document.getElementById("attachmentLock");
const layerRegenerateProgress = document.getElementById("layerRegenerateProgress");
const layerRegenerateBar = document.getElementById("layerRegenerateBar");
const layerRegenerateProgressText = document.getElementById("layerRegenerateProgressText");
const submitLayerRegenerate = document.getElementById("submitLayerRegenerate");
const cancelLayerRegenerate = document.getElementById("cancelLayerRegenerate");
const closeLayerRegenerate = document.getElementById("closeLayerRegenerate");
const params = new URLSearchParams(location.search);
let applyGeneratedLayerTextures = null;

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
    layerHint: "Frontmost is at the top. Drag rows or use the arrows to reorder; drag a control strip sideways if needed.",
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
    layerControls: "controls",
    newActions: "Newly added motions",
    drag: "Drag",
    dragHint: "move the avatar",
    zoom: "Wheel or pinch",
    zoomHint: "zoom around the cursor",
    resetView: "Reset view (position and size)",
    missingConfig: "No default model configuration was found.",
    playing: (label) => `Playing: ${label}`,
    dontToggleOff: "Don't toggle off",
    toggleOffHint: "Keep this state active until its button is clicked again",
    returningToIdle: "Returning smoothly to idle…",
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
    layerGenerateTitle: "Regenerate selected layer",
    regenerateLayer: (name) => `Regenerate ${name}`,
    layerInstructionLabel: "What should change?",
    layerInstructionPlaceholder: "Refine the armor into a cleaner segmented sci-fi design while keeping its current silhouette…",
    layerInstructionHint: "The finalized layer, cropped local character context, and matching layers are supplied as visual references.",
    includeRelatedLayers: "Also regenerate matching left/right, front/back, or connected layers",
    relatedLayers: (names) => `Included by default: ${names}`,
    noRelatedLayers: "No matching layer was detected for this selection.",
    preserveLayerColors: "Preserve the existing color palette",
    useGeneratedLayerMask: "Use a new layer mask from the chroma-keyed result",
    generatedLayerMaskHint: "The keyed foreground becomes the new alpha mask. Turn this off only to reuse the finalized mask exactly.",
    undoLayerGeneration: (name) => `Undo the last generation for ${name}`,
    undoGenerationStarting: "Undoing the last generation…",
    redoLayerGeneration: (name) => `Redo the last undone generation for ${name}`,
    redoGenerationStarting: "Redoing the last undone generation…",
    showLayerVariants: (name) => `Show generated variants for ${name}`,
    originalVariant: "Original",
    generatedVariant: (index) => `Generated ${index}`,
    activeVariant: "Selected",
    selectLayerVariant: (variant, name) => `Use ${variant} for ${name}`,
    includeRelatedVariants: (names) => `Also switch matching layers: ${names}`,
    variantSelecting: "Switching layer variant…",
    variantSwitchedInstantly: "Layer textures switched instantly — no rig rebuild needed",
    generatedTextureApplied: "Generated layer textures applied instantly — no rig rebuild needed",
    changeAmountLabel: "Change amount",
    changeSubtle: "Subtle",
    changeBalanced: "Balanced",
    changeStrong: "Strong",
    attachmentLockLabel: "Attachment lock",
    attachmentStrict: "Strict",
    attachmentBalanced: "Balanced",
    attachmentHint: "Attachment lock preserves the original seam while retaining the regenerated silhouette.",
    adjustLayerPlacement: (name) => `Adjust ${name} placement`,
    layerOffsetX: "X",
    layerOffsetY: "Y",
    resetLayerOffset: "Center",
    revertLayerEdit: "Reset regenerated art",
    layerPlacementSaving: "Saving…",
    layerPlacementSaved: "Saved",
    layerRevertStarting: "Restoring the finalized layer art…",
    layerActionFailed: (message) => `Could not update the selected layer: ${message}`,
    regenerateSelected: "Regenerate layer",
    targetedLayerStarting: "Preparing finalized layers for Gemini…",
    targetedLayerFailed: (message) => `Could not regenerate the selected layer: ${message}`,
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
    layerHint: "一番上が最前面です。行のドラッグまたは矢印で並べ替え、必要なら操作欄を横にドラッグできます。",
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
    layerControls: "操作",
    newActions: "今回追加したモーション",
    drag: "ドラッグ",
    dragHint: "アバターを移動",
    zoom: "ホイール・ピンチ",
    zoomHint: "カーソル位置を中心に拡大縮小",
    resetView: "表示リセット (位置・サイズ)",
    missingConfig: "初期モデル設定が見つかりません。",
    playing: (label) => `再生中: ${label}`,
    dontToggleOff: "自動でオフにしない",
    toggleOffHint: "もう一度ボタンを押すまでこの状態を維持します",
    returningToIdle: "滑らかにアイドルへ戻しています…",
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
    layerGenerateTitle: "選択したレイヤーを再生成",
    regenerateLayer: (name) => `${name}を再生成`,
    layerInstructionLabel: "どのように変更しますか？",
    layerInstructionPlaceholder: "現在のシルエットを保ちながら、装甲をすっきりした分割型SFデザインに整える…",
    layerInstructionHint: "完成済みレイヤー、キャラクター周辺の切り抜き、対応レイヤーを参照画像として使用します。",
    includeRelatedLayers: "左右・前後・接続された対応レイヤーも一緒に再生成",
    relatedLayers: (names) => `初期設定で含む: ${names}`,
    noRelatedLayers: "このレイヤーに対応するレイヤーは見つかりませんでした。",
    preserveLayerColors: "現在のカラーパレットを維持",
    useGeneratedLayerMask: "クロマキー結果から新しいレイヤーマスクを作成",
    generatedLayerMaskHint: "キー色以外の領域を新しいアルファマスクにします。完成時のマスクをそのまま使う場合だけオフにしてください。",
    undoLayerGeneration: (name) => `${name}の最後の生成を取り消す`,
    undoGenerationStarting: "最後の生成を取り消しています…",
    redoLayerGeneration: (name) => `${name}の取り消した生成をやり直す`,
    redoGenerationStarting: "取り消した生成をやり直しています…",
    showLayerVariants: (name) => `${name}の生成バリエーションを表示`,
    originalVariant: "オリジナル",
    generatedVariant: (index) => `生成 ${index}`,
    activeVariant: "選択中",
    selectLayerVariant: (variant, name) => `${name}に${variant}を使用`,
    includeRelatedVariants: (names) => `対応レイヤーも一緒に切り替える: ${names}`,
    variantSelecting: "レイヤーバリエーションを切り替えています…",
    variantSwitchedInstantly: "テクスチャを即時切り替えました — リグの再構築は不要でした",
    generatedTextureApplied: "生成したレイヤーテクスチャを即時反映しました — リグの再構築は不要でした",
    changeAmountLabel: "変更量",
    changeSubtle: "控えめ",
    changeBalanced: "標準",
    changeStrong: "大きく",
    attachmentLockLabel: "接続点ロック",
    attachmentStrict: "厳密",
    attachmentBalanced: "標準",
    attachmentHint: "再生成したシルエットを保ちながら、元の接続境界を固定します。",
    adjustLayerPlacement: (name) => `${name}の配置を調整`,
    layerOffsetX: "X",
    layerOffsetY: "Y",
    resetLayerOffset: "中央に戻す",
    revertLayerEdit: "再生成前の画像に戻す",
    layerPlacementSaving: "保存中…",
    layerPlacementSaved: "保存済み",
    layerRevertStarting: "完成済みの元レイヤーに戻しています…",
    layerActionFailed: (message) => `選択したレイヤーを更新できませんでした: ${message}`,
    regenerateSelected: "レイヤーを再生成",
    targetedLayerStarting: "完成済みレイヤーをGemini用に準備しています…",
    targetedLayerFailed: (message) => `選択したレイヤーを再生成できませんでした: ${message}`,
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
let activeLayerEditJobId = null;
let selectedLayerEdit = null;

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

function setLayerEditBusy(busy) {
  submitLayerRegenerate.disabled = busy;
  cancelLayerRegenerate.disabled = busy;
  closeLayerRegenerate.disabled = busy;
}

function openLayerRegenerator(layer) {
  selectedLayerEdit = layer;
  layerRegenerateName.textContent = layer.name;
  layerInstruction.value = "";
  preserveLayerColors.checked = true;
  useGeneratedLayerMask.checked = true;
  layerChangeAmount.value = "balanced";
  attachmentLock.value = "strict";
  includeRelatedLayers.checked = true;
  includeRelatedLayers.disabled = layer.related.length === 0;
  relatedLayersHint.textContent = layer.related.length
    ? t.relatedLayers(layer.related.map((item) => item.name).join(", "))
    : t.noRelatedLayers;
  layerRegenerateProgress.hidden = true;
  layerRegenerateProgressText.classList.remove("error");
  layerRegenerateBar.style.width = "5%";
  setLayerEditBusy(false);
  layerRegenerateDialog.showModal();
  setTimeout(() => layerInstruction.focus(), 0);
}

function closeLayerRegenerator() {
  if (activeLayerEditJobId) return;
  layerRegenerateDialog.close();
  selectedLayerEdit = null;
}

cancelLayerRegenerate.addEventListener("click", closeLayerRegenerator);
closeLayerRegenerate.addEventListener("click", closeLayerRegenerator);
layerRegenerateDialog.addEventListener("cancel", (event) => {
  if (activeLayerEditJobId) event.preventDefault();
});

function layerEditProgress(phase) {
  return ({ queued: 5, gemini: 42, textures: 92, rigging: 86, complete: 100, failed: 100 })[phase] || 10;
}

async function pollLayerEdit(jobId) {
  while (activeLayerEditJobId === jobId) {
    const job = await fetchJson(`/api/avatar-jobs/${encodeURIComponent(jobId)}`);
    layerRegenerateProgressText.textContent = job.message || t.targetedLayerStarting;
    layerRegenerateBar.style.width = `${layerEditProgress(job.phase)}%`;
    if (job.phase === "complete") {
      if (job.texture_only) {
        try {
          if (!applyGeneratedLayerTextures) throw new Error("Layer texture editor is unavailable.");
          await applyGeneratedLayerTextures(job);
          activeLayerEditJobId = null;
          setLayerEditBusy(false);
          layerRegenerateDialog.close();
          selectedLayerEdit = null;
          return;
        } catch {
          // The generated textures are already persisted. Reload only if this browser could not
          // bind them into the current WebGL context.
        }
      }
      activeLayerEditJobId = null;
      const next = new URL(location.href);
      next.searchParams.set("layers", Date.now().toString());
      location.assign(next);
      return;
    }
    if (job.phase === "failed") throw new Error(job.error || "Unknown error");
    await new Promise((resolve) => setTimeout(resolve, 1500));
  }
}

layerRegenerateForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selectedLayerEdit || activeLayerEditJobId) return;
  const instruction = layerInstruction.value.trim();
  if (!instruction) return;
  layerRegenerateProgress.hidden = false;
  layerRegenerateProgressText.classList.remove("error");
  layerRegenerateProgressText.textContent = t.targetedLayerStarting;
  layerRegenerateBar.style.width = "5%";
  setLayerEditBusy(true);
  try {
    const payload = await fetchJson(
      `/api/avatars/${encodeURIComponent(currentAvatar.id)}/regenerate-layer`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          layer_id: selectedLayerEdit.id,
          instruction,
          include_related: includeRelatedLayers.checked,
          preserve_colors: preserveLayerColors.checked,
          use_generated_mask: useGeneratedLayerMask.checked,
          change_amount: layerChangeAmount.value,
          attachment_lock: attachmentLock.value,
        }),
      },
    );
    activeLayerEditJobId = payload.job_id;
    await pollLayerEdit(activeLayerEditJobId);
  } catch (error) {
    activeLayerEditJobId = null;
    layerRegenerateProgressText.textContent = t.targetedLayerFailed(error.message);
    layerRegenerateProgressText.classList.add("error");
    setLayerEditBusy(false);
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
  let regenerationLayers = new Map();
  if (currentAvatar.can_regenerate_layers) {
    try {
      const payload = await fetchJson(
        `/api/avatars/${encodeURIComponent(currentAvatar.id)}/layers`,
      );
      regenerationLayers = new Map((payload.layers || []).map((layer) => [layer.id, layer]));
    } catch {
      regenerationLayers = new Map();
    }
  }
  const expandedPlacementIds = new Set();
  const placementStatus = new Map();
  const initialBakedOffsets = new Map();
  const previewOffsets = new Map();
  const placementTimers = new Map();
  const placementQueue = new Map();
  let placementWorkerActive = false;
  let rowActionActive = false;
  let historyPendingIds = new Set();
  let historyPendingAction = null;
  const expandedVariantIds = new Set();
  const variantTextureCache = new Map();
  let activeVariantMenu = null;
  let activeVariantAnchor = null;
  for (const [id, layer] of regenerationLayers) {
    const offset = {
      x: Number(layer.offset?.x) || 0,
      y: Number(layer.offset?.y) || 0,
    };
    initialBakedOffsets.set(id, { ...offset });
    previewOffsets.set(id, { ...offset });
  }

  function applyLiveLayerOffsets() {
    if (!coreModel.getDrawableVertexPositions) return;
    for (const [id, preview] of previewOffsets) {
      const layer = regenerationLayers.get(id);
      const canvas = layer?.canvas;
      const baked = initialBakedOffsets.get(id) || { x: 0, y: 0 };
      if (!Array.isArray(canvas) || canvas.length !== 2 || !canvas[0] || !canvas[1]) continue;
      const deltaX = (preview.x - baked.x) * 2 / canvas[0];
      const deltaY = -(preview.y - baked.y) * 2 / canvas[1];
      if (!deltaX && !deltaY) continue;
      const drawableIndex = coreModel.getDrawableIndex(id);
      if (drawableIndex < 0) continue;
      const positions = coreModel.getDrawableVertexPositions(drawableIndex);
      for (let vertex = 0; vertex < positions.length; vertex += 2) {
        positions[vertex] += deltaX;
        positions[vertex + 1] += deltaY;
      }
    }
  }

  if (typeof coreModel.update === "function") {
    const originalCoreUpdate = coreModel.update.bind(coreModel);
    coreModel.update = (...args) => {
      const result = originalCoreUpdate(...args);
      applyLiveLayerOffsets();
      return result;
    };
  }

  function setPlacementStatus(id, message, className = "") {
    placementStatus.set(id, { message, className });
    const row = Array.from(layerList.querySelectorAll(".layer-row"))
      .find((candidate) => candidate.dataset.drawableId === id);
    const status = row?.querySelector(".layer-offset-status");
    if (status) {
      status.textContent = message;
      status.className = `layer-offset-status ${className}`.trim();
    }
  }

  async function waitForLayerAction(jobId, onUpdate = null) {
    while (true) {
      const job = await fetchJson(`/api/avatar-jobs/${encodeURIComponent(jobId)}`);
      onUpdate?.(job);
      if (job.phase === "complete") return job;
      if (job.phase === "failed") throw new Error(job.error || "Unknown error");
      await new Promise((resolve) => setTimeout(resolve, 750));
    }
  }

  async function processPlacementQueue() {
    if (placementWorkerActive) return;
    placementWorkerActive = true;
    while (placementQueue.size) {
      const [id, offset] = placementQueue.entries().next().value;
      placementQueue.delete(id);
      setPlacementStatus(id, t.layerPlacementSaving);
      try {
        const payload = await fetchJson(
          `/api/avatars/${encodeURIComponent(currentAvatar.id)}/offset-layer`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              layer_id: id,
              offset_x: offset.x,
              offset_y: offset.y,
              include_related: false,
            }),
          },
        );
        await waitForLayerAction(payload.job_id);
        const layer = regenerationLayers.get(id);
        if (layer) {
          layer.offset = { ...offset };
          layer.can_revert = layer.overridden || offset.x !== 0 || offset.y !== 0;
          const row = Array.from(layerList.querySelectorAll(".layer-row"))
            .find((candidate) => candidate.dataset.drawableId === id);
          const restore = row?.querySelector(".restore-art");
          if (restore) restore.disabled = !layer.can_revert;
        }
        setPlacementStatus(id, t.layerPlacementSaved, "saved");
      } catch (error) {
        setPlacementStatus(id, t.layerActionFailed(error.message), "error");
      }
    }
    placementWorkerActive = false;
  }

  function queuePlacementSave(id, delay = 0) {
    clearTimeout(placementTimers.get(id));
    placementTimers.set(id, setTimeout(() => {
      placementTimers.delete(id);
      placementQueue.set(id, { ...previewOffsets.get(id) });
      processPlacementQueue();
    }, delay));
  }

  async function restoreLayerArt(id) {
    if (rowActionActive || activeLayerEditJobId) return;
    rowActionActive = true;
    setPlacementStatus(id, t.layerRevertStarting);
    try {
      const payload = await fetchJson(
        `/api/avatars/${encodeURIComponent(currentAvatar.id)}/revert-layer`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ layer_id: id, include_related: false }),
        },
      );
      await waitForLayerAction(payload.job_id);
      const next = new URL(location.href);
      next.searchParams.set("layers", Date.now().toString());
      location.assign(next);
    } catch (error) {
      rowActionActive = false;
      setPlacementStatus(id, t.layerActionFailed(error.message), "error");
    }
  }

  async function runLayerHistoryAction(id, action) {
    if (rowActionActive || activeLayerEditJobId || placementWorkerActive) return;
    rowActionActive = true;
    const isRedo = action === "redo";
    const capability = isRedo ? "can_redo_generation" : "can_undo_generation";
    const relatedIds = regenerationLayers.get(id)?.related || [];
    historyPendingIds = new Set([
      id,
      ...relatedIds.filter((relatedId) => regenerationLayers.get(relatedId)?.[capability]),
    ]);
    historyPendingAction = action;
    renderLayerList();
    const startingMessage = isRedo ? t.redoGenerationStarting : t.undoGenerationStarting;
    layerSaveStatus.textContent = startingMessage;
    layerSaveStatus.className = "layer-save-status is-busy";
    try {
      const payload = await fetchJson(
        `/api/avatars/${encodeURIComponent(currentAvatar.id)}/${action}-generation`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ layer_id: id, include_related: true }),
        },
      );
      await waitForLayerAction(payload.job_id, (job) => {
        layerSaveStatus.textContent = job.message || startingMessage;
      });
      const next = new URL(location.href);
      next.searchParams.set("layers", Date.now().toString());
      location.assign(next);
    } catch (error) {
      rowActionActive = false;
      historyPendingIds.clear();
      historyPendingAction = null;
      renderLayerList();
      layerSaveStatus.textContent = t.layerActionFailed(error.message);
      layerSaveStatus.className = "layer-save-status error";
    }
  }

  const undoLayerGeneration = (id) => runLayerHistoryAction(id, "undo");
  const redoLayerGeneration = (id) => runLayerHistoryAction(id, "redo");

  async function loadVariantTexture(url) {
    if (variantTextureCache.has(url)) return variantTextureCache.get(url);
    const texture = PIXI.Texture.from(url);
    const pending = texture.baseTexture.valid
      ? Promise.resolve(texture)
      : new Promise((resolve, reject) => {
        const timeout = setTimeout(() => reject(new Error("Texture loading timed out.")), 10000);
        texture.baseTexture.once("loaded", () => {
          clearTimeout(timeout);
          resolve(texture);
        });
        texture.baseTexture.once("error", (error) => {
          clearTimeout(timeout);
          reject(error instanceof Error ? error : new Error("Texture loading failed."));
        });
      });
    variantTextureCache.set(url, pending);
    try {
      return await pending;
    } catch (error) {
      variantTextureCache.delete(url);
      throw error;
    }
  }

  async function applyRuntimeVariantTextures(layerIds, variantId) {
    const refreshed = await fetchJson(
      `/api/avatars/${encodeURIComponent(currentAvatar.id)}/layers`,
    );
    regenerationLayers = new Map((refreshed.layers || []).map((layer) => [layer.id, layer]));
    const replacements = [];
    for (const layerId of layerIds) {
      const variant = regenerationLayers.get(layerId)?.variants?.find(
        (item) => item.id === variantId,
      );
      if (!variant?.thumbnail_url) throw new Error(`Generated variant missing for ${layerId}.`);
      const drawableIndex = coreModel.getDrawableIndex(layerId);
      if (drawableIndex < 0) throw new Error(`Live2D drawable missing for ${layerId}.`);
      const textureIndex = coreModel.getDrawableTextureIndices(drawableIndex);
      const texture = await loadVariantTexture(variant.thumbnail_url);
      replacements.push({ layerId, textureIndex, texture });
    }
    for (const replacement of replacements) {
      model.textures[replacement.textureIndex] = replacement.texture;
    }
    replacements.forEach(({ layerId }) => {
      thumbnails.set(layerId, drawableThumbnail(model, coreModel, layerId));
    });
  }

  async function selectLayerVariant(id, variant, includeRelated = true) {
    if (rowActionActive || activeLayerEditJobId || placementWorkerActive || variant.active) return;
    rowActionActive = true;
    expandedVariantIds.clear();
    const matchingRelated = includeRelated
      ? (regenerationLayers.get(id)?.related || []).filter((relatedId) =>
        regenerationLayers.get(relatedId)?.variants?.some((item) => item.id === variant.id))
      : [];
    historyPendingIds = new Set([id, ...matchingRelated]);
    historyPendingAction = "variant";
    renderLayerList();
    layerSaveStatus.textContent = t.variantSelecting;
    layerSaveStatus.className = "layer-save-status is-busy";
    try {
      const payload = await fetchJson(
        `/api/avatars/${encodeURIComponent(currentAvatar.id)}/select-variant`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            layer_id: id,
            variant_id: variant.id,
            include_related: includeRelated,
          }),
        },
      );
      const completed = await waitForLayerAction(payload.job_id, (job) => {
        layerSaveStatus.textContent = job.message || t.variantSelecting;
      });
      if (completed.texture_only) {
        try {
          await applyRuntimeVariantTextures(completed.layer_ids || [id], variant.id);
          rowActionActive = false;
          historyPendingIds.clear();
          historyPendingAction = null;
          renderLayerList();
          layerSaveStatus.textContent = t.variantSwitchedInstantly;
          layerSaveStatus.className = "layer-save-status saved";
          return;
        } catch {
          // The server has already persisted the texture. A quick reload is the reliable fallback if
          // this browser could not upload/bind the replacement texture in the current WebGL context.
        }
      }
      const next = new URL(location.href);
      next.searchParams.set("layers", Date.now().toString());
      location.assign(next);
    } catch (error) {
      rowActionActive = false;
      historyPendingIds.clear();
      historyPendingAction = null;
      renderLayerList();
      layerSaveStatus.textContent = t.layerActionFailed(error.message);
      layerSaveStatus.className = "layer-save-status error";
    }
  }

  function enableHorizontalDragScroll(container) {
    let pointerId = null;
    let startX = 0;
    let startScrollLeft = 0;
    let dragged = false;
    let suppressClick = false;

    container.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      pointerId = event.pointerId;
      startX = event.clientX;
      startScrollLeft = container.scrollLeft;
      dragged = false;
      suppressClick = false;
    });
    container.addEventListener("pointermove", (event) => {
      if (event.pointerId !== pointerId) return;
      const distance = event.clientX - startX;
      if (!dragged && Math.abs(distance) < 6) return;
      if (!dragged) {
        dragged = true;
        container.classList.add("drag-scrolling");
        container.setPointerCapture?.(event.pointerId);
      }
      container.scrollLeft = startScrollLeft - distance;
      event.preventDefault();
    });
    const finishDrag = (event) => {
      if (event.pointerId !== pointerId) return;
      if (dragged) {
        suppressClick = true;
        container.releasePointerCapture?.(event.pointerId);
        setTimeout(() => { suppressClick = false; }, 0);
      }
      pointerId = null;
      dragged = false;
      container.classList.remove("drag-scrolling");
    };
    container.addEventListener("pointerup", finishDrag);
    container.addEventListener("pointercancel", finishDrag);
    container.addEventListener("click", (event) => {
      if (!suppressClick) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      suppressClick = false;
    }, true);
  }

  const thumbnails = new Map(drawableIds.map((id) => [id, drawableThumbnail(model, coreModel, id)]));
  applyGeneratedLayerTextures = async (job) => {
    await applyRuntimeVariantTextures(job.layer_ids || [], job.variant_id);
    historyPendingIds.clear();
    historyPendingAction = null;
    renderLayerList();
    layerSaveStatus.textContent = t.generatedTextureApplied;
    layerSaveStatus.className = "layer-save-status saved";
  };
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

  function positionVariantMenu(menu, anchorElement) {
    if (!menu?.matches(":popover-open") || !anchorElement?.isConnected) return;
    const anchor = anchorElement.getBoundingClientRect();
    const list = layerList.getBoundingClientRect();
    const preferredWidth = Math.min(280, Math.max(220, list.width - 18));
    menu.style.width = `${preferredWidth}px`;
    menu.style.maxHeight = `${Math.max(120, Math.min(250, innerHeight - 20))}px`;
    const bounds = menu.getBoundingClientRect();
    const spaceBelow = innerHeight - anchor.bottom - 8;
    const spaceAbove = anchor.top - 8;
    const openUpward = spaceBelow < Math.min(bounds.height, 180) && spaceAbove > spaceBelow;
    const unclampedTop = openUpward
      ? anchor.top - bounds.height - 6
      : anchor.bottom + 6;
    const top = Math.max(8, Math.min(unclampedTop, innerHeight - bounds.height - 8));
    const left = Math.max(8, Math.min(anchor.left, innerWidth - bounds.width - 8));
    menu.style.top = `${top}px`;
    menu.style.left = `${left}px`;
    menu.classList.add("is-positioned");
  }

  function renderLayerList() {
    const previousScrollTop = layerList.scrollTop;
    if (activeVariantMenu) {
      const staleMenu = activeVariantMenu;
      activeVariantMenu = null;
      activeVariantAnchor = null;
      staleMenu.remove();
    }
    layerList.replaceChildren();
    layerList.dataset.order = currentOrder.join("|");
    currentOrder.forEach((id, index) => {
      const layerInfo = regenerationLayers.get(id) || {};
      const variants = Array.isArray(layerInfo.variants) ? layerInfo.variants : [];
      const name = layerInfo.display_name || labels.get(id) || id.replace(/_/g, " ");
      const row = document.createElement("li");
      row.className = "layer-row";
      row.dataset.drawableId = id;
      row.title = id;
      row.draggable = true;
      row.classList.toggle("layer-hidden", hiddenIds.has(id));
      row.classList.toggle("layer-solo", soloId === id);
      row.classList.toggle("layer-solo-muted", Boolean(soloId && soloId !== id));
      row.classList.toggle("placement-open", expandedPlacementIds.has(id));
      const historyPending = historyPendingIds.has(id);
      const undoPending = historyPending && historyPendingAction === "undo";
      const redoPending = historyPending && historyPendingAction === "redo";
      const variantPending = historyPending && historyPendingAction === "variant";
      const variantsExpanded = expandedVariantIds.has(id);
      row.classList.toggle("history-pending", historyPending);
      row.classList.toggle("variant-open", variantsExpanded);

      const handle = document.createElement("span");
      handle.className = "layer-handle";
      handle.textContent = "⠿";
      handle.setAttribute("aria-hidden", "true");

      const thumbnailPicker = document.createElement(variants.length > 1 ? "button" : "span");
      thumbnailPicker.className = `layer-thumbnail-picker${variants.length > 1 ? " has-variants" : ""}`;
      thumbnailPicker.draggable = false;
      const thumbnail = document.createElement(thumbnails.get(id) ? "img" : "span");
      thumbnail.className = `layer-thumbnail-image${thumbnails.get(id) ? "" : " empty"}`;
      if (thumbnails.get(id)) {
        thumbnail.src = thumbnails.get(id);
        thumbnail.alt = "";
      } else {
        thumbnail.textContent = "·";
      }
      thumbnailPicker.append(thumbnail);
      if (variants.length > 1) {
        thumbnailPicker.type = "button";
        thumbnailPicker.setAttribute("aria-expanded", String(variantsExpanded));
        thumbnailPicker.setAttribute("aria-label", t.showLayerVariants(name));
        thumbnailPicker.title = t.showLayerVariants(name);
        const chevron = document.createElement("span");
        chevron.className = "layer-thumbnail-chevron";
        chevron.textContent = "⌄";
        chevron.setAttribute("aria-hidden", "true");
        thumbnailPicker.append(chevron);
        thumbnailPicker.addEventListener("click", (event) => {
          event.stopPropagation();
          const opening = !expandedVariantIds.has(id);
          expandedVariantIds.clear();
          if (opening) {
            expandedVariantIds.add(id);
            expandedPlacementIds.delete(id);
          }
          renderLayerList();
        });
      }
      if (variantPending) {
        const spinner = document.createElement("span");
        spinner.className = "layer-thumbnail-spinner layer-button-spinner";
        spinner.setAttribute("aria-hidden", "true");
        thumbnailPicker.append(spinner);
      }

      const label = document.createElement("span");
      label.className = "layer-name";
      label.append(name);
      const labelWrap = document.createElement("span");
      labelWrap.className = "layer-name-wrap";
      labelWrap.append(label);
      const undoGeneration = document.createElement("button");
      undoGeneration.type = "button";
      undoGeneration.className = "layer-undo-generation";
      undoGeneration.innerHTML = undoPending
        ? '<span class="layer-button-spinner" aria-hidden="true"></span>'
        : [
          '<svg viewBox="0 0 24 24" aria-hidden="true">',
          '<path d="M9 7 4 12l5 5"></path>',
          '<path d="M4 12h9a7 7 0 0 1 7 7"></path>',
          '</svg>',
        ].join("");
      undoGeneration.disabled = !regenerationLayers.get(id)?.can_undo_generation || historyPending;
      undoGeneration.setAttribute("aria-busy", String(undoPending));
      undoGeneration.setAttribute("aria-label", t.undoLayerGeneration(name));
      undoGeneration.title = t.undoLayerGeneration(name);
      undoGeneration.addEventListener("click", () => undoLayerGeneration(id));
      const redoGeneration = document.createElement("button");
      redoGeneration.type = "button";
      redoGeneration.className = "layer-redo-generation";
      redoGeneration.innerHTML = redoPending
        ? '<span class="layer-button-spinner" aria-hidden="true"></span>'
        : [
          '<svg viewBox="0 0 24 24" aria-hidden="true">',
          '<path d="m15 7 5 5-5 5"></path>',
          '<path d="M20 12h-9a7 7 0 0 0-7 7"></path>',
          '</svg>',
        ].join("");
      redoGeneration.disabled = !regenerationLayers.get(id)?.can_redo_generation || historyPending;
      redoGeneration.setAttribute("aria-busy", String(redoPending));
      redoGeneration.setAttribute("aria-label", t.redoLayerGeneration(name));
      redoGeneration.title = t.redoLayerGeneration(name);
      redoGeneration.addEventListener("click", () => redoLayerGeneration(id));
      labelWrap.append(undoGeneration, redoGeneration);

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

      const placement = document.createElement("button");
      const canAdjustPlacement = regenerationLayers.has(id);
      const placementExpanded = expandedPlacementIds.has(id);
      placement.type = "button";
      placement.className = `layer-tool layer-placement-toggle${placementExpanded ? " is-active" : ""}`;
      placement.textContent = "⊹";
      placement.hidden = !canAdjustPlacement;
      placement.setAttribute("aria-expanded", String(placementExpanded));
      placement.setAttribute("aria-label", t.adjustLayerPlacement(name));
      placement.addEventListener("click", () => {
        const opening = !expandedPlacementIds.has(id);
        if (opening) {
          expandedPlacementIds.add(id);
          expandedVariantIds.delete(id);
        }
        else expandedPlacementIds.delete(id);
        renderLayerList();
        if (opening) {
          requestAnimationFrame(() => {
            const expandedRow = Array.from(layerList.querySelectorAll(".layer-row"))
              .find((candidate) => candidate.dataset.drawableId === id);
            expandedRow?.querySelector(".layer-offset-panel")?.scrollIntoView({ block: "nearest" });
          });
        }
      });

      const regenerate = document.createElement("button");
      regenerate.type = "button";
      regenerate.className = "layer-tool layer-regenerate";
      regenerate.textContent = "✦";
      regenerate.hidden = !regenerationLayers.has(id);
      regenerate.setAttribute("aria-label", t.regenerateLayer(name));
      regenerate.addEventListener("click", () => {
        const regenerationLayer = regenerationLayers.get(id) || {};
        const relatedIds = regenerationLayer.related || [];
        const related = relatedIds.map((relatedId) => ({
          id: relatedId,
          name: regenerationLayers.get(relatedId)?.display_name || labels.get(relatedId) || relatedId.replace(/_/g, " "),
        }));
        openLayerRegenerator({
          id,
          name,
          related,
          canRevert: Boolean(regenerationLayer.can_revert),
          offset: regenerationLayer.offset || { x: 0, y: 0 },
        });
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

      const rowActions = document.createElement("div");
      rowActions.className = "layer-row-actions";
      rowActions.setAttribute("role", "group");
      rowActions.setAttribute("aria-label", `${name} ${t.layerControls}`);
      rowActions.draggable = false;
      rowActions.append(visibility, solo, regenerate, placement, up, down);
      enableHorizontalDragScroll(rowActions);

      let variantMenu = null;
      if (variantsExpanded && variants.length > 1) {
        variantMenu = document.createElement("div");
        variantMenu.className = "layer-variant-menu";
        variantMenu.setAttribute("popover", "auto");
        variantMenu.setAttribute("role", "listbox");
        variantMenu.setAttribute("aria-label", t.showLayerVariants(name));
        variantMenu.draggable = false;
        const groupedIds = (layerInfo.related || []).filter((relatedId) =>
          regenerationLayers.get(relatedId)?.variants?.length);
        let includeRelatedVariants = null;
        if (groupedIds.length) {
          const groupedNames = groupedIds.map((relatedId) =>
            regenerationLayers.get(relatedId)?.display_name || labels.get(relatedId) || relatedId.replace(/_/g, " "));
          const groupOption = document.createElement("label");
          groupOption.className = "layer-variant-group-option";
          includeRelatedVariants = document.createElement("input");
          includeRelatedVariants.type = "checkbox";
          includeRelatedVariants.checked = true;
          const groupCopy = document.createElement("span");
          groupCopy.textContent = t.includeRelatedVariants(groupedNames.join(", "));
          groupOption.append(includeRelatedVariants, groupCopy);
          variantMenu.append(groupOption);
        }
        variants.forEach((variant) => {
          const variantLabel = variant.kind === "baseline"
            ? t.originalVariant
            : t.generatedVariant(variant.index);
          const option = document.createElement("button");
          option.type = "button";
          option.className = `layer-variant-option${variant.active ? " is-active" : ""}`;
          option.disabled = Boolean(variant.active) || historyPending;
          option.setAttribute("role", "option");
          option.setAttribute("aria-selected", String(Boolean(variant.active)));
          option.setAttribute("aria-label", t.selectLayerVariant(variantLabel, name));
          const preview = document.createElement("img");
          preview.src = variant.thumbnail_url;
          preview.alt = "";
          preview.loading = "lazy";
          const copy = document.createElement("span");
          copy.className = "layer-variant-copy";
          const title = document.createElement("span");
          title.className = "layer-variant-title";
          title.textContent = variantLabel;
          copy.append(title);
          if (variant.instruction) {
            const instruction = document.createElement("span");
            instruction.className = "layer-variant-instruction";
            instruction.textContent = variant.instruction;
            copy.append(instruction);
          }
          option.append(preview, copy);
          if (variant.active) {
            const active = document.createElement("span");
            active.className = "layer-variant-active";
            active.textContent = t.activeVariant;
            option.append(active);
          }
          option.addEventListener("click", (event) => {
            event.stopPropagation();
            selectLayerVariant(id, variant, includeRelatedVariants?.checked ?? false);
          });
          variantMenu.append(option);
        });
      }

      row.addEventListener("dragstart", (event) => {
        if (event.target.closest("button, input, .layer-row-actions, .layer-offset-panel, .layer-variant-menu, .layer-thumbnail-picker")) {
          event.preventDefault();
          return;
        }
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

      row.append(handle, thumbnailPicker, labelWrap, rowActions);
      if (canAdjustPlacement) {
        const panel = document.createElement("div");
        panel.className = "layer-offset-panel";
        panel.hidden = !placementExpanded;
        panel.draggable = false;

        const preview = previewOffsets.get(id) || { x: 0, y: 0 };
        const makeSlider = (axis, labelText) => {
          const wrapper = document.createElement("div");
          wrapper.className = "layer-offset-row";
          const sliderLabel = document.createElement("label");
          sliderLabel.textContent = labelText;
          const slider = document.createElement("input");
          slider.type = "range";
          slider.min = "-256";
          slider.max = "256";
          slider.step = "1";
          slider.value = String(preview[axis]);
          slider.setAttribute("aria-label", `${name} ${labelText}`);
          const output = document.createElement("output");
          const showValue = () => {
            const value = Number(slider.value);
            output.textContent = `${value > 0 ? "+" : ""}${value}px`;
          };
          showValue();
          slider.addEventListener("input", () => {
            const next = { ...(previewOffsets.get(id) || { x: 0, y: 0 }) };
            next[axis] = Number(slider.value);
            previewOffsets.set(id, next);
            showValue();
            setPlacementStatus(id, "");
            queuePlacementSave(id, 650);
          });
          slider.addEventListener("change", () => queuePlacementSave(id));
          wrapper.append(sliderLabel, slider, output);
          return { wrapper, slider, output };
        };
        const xSlider = makeSlider("x", t.layerOffsetX);
        const ySlider = makeSlider("y", t.layerOffsetY);
        const actions = document.createElement("div");
        actions.className = "layer-offset-actions";
        const center = document.createElement("button");
        center.type = "button";
        center.className = "secondary";
        center.textContent = t.resetLayerOffset;
        center.addEventListener("click", () => {
          previewOffsets.set(id, { x: 0, y: 0 });
          xSlider.slider.value = "0";
          ySlider.slider.value = "0";
          xSlider.output.textContent = "0px";
          ySlider.output.textContent = "0px";
          setPlacementStatus(id, "");
          queuePlacementSave(id);
        });
        const restore = document.createElement("button");
        restore.type = "button";
        restore.className = "secondary restore-art";
        restore.textContent = t.revertLayerEdit;
        restore.disabled = !regenerationLayers.get(id)?.can_revert;
        restore.addEventListener("click", () => restoreLayerArt(id));
        const status = document.createElement("span");
        const savedStatus = placementStatus.get(id) || { message: "", className: "" };
        status.className = `layer-offset-status ${savedStatus.className}`.trim();
        status.textContent = savedStatus.message;
        actions.append(center, restore, status);
        panel.append(xSlider.wrapper, ySlider.wrapper, actions);
        row.appendChild(panel);
      }
      layerList.appendChild(row);
      if (variantMenu) {
        document.body.appendChild(variantMenu);
        activeVariantMenu = variantMenu;
        activeVariantAnchor = thumbnailPicker;
        variantMenu.showPopover();
        variantMenu.addEventListener("toggle", (event) => {
          if (event.newState !== "closed" || activeVariantMenu !== variantMenu) return;
          activeVariantMenu = null;
          activeVariantAnchor = null;
          expandedVariantIds.delete(id);
          renderLayerList();
        });
      }
    });
    const restoreScroll = () => {
      const maximumScrollTop = Math.max(0, layerList.scrollHeight - layerList.clientHeight);
      layerList.scrollTop = Math.min(previousScrollTop, maximumScrollTop);
    };
    restoreScroll();
    requestAnimationFrame(() => {
      restoreScroll();
      positionVariantMenu(activeVariantMenu, activeVariantAnchor);
    });
  }

  document.addEventListener("click", (event) => {
    if (!expandedVariantIds.size || event.target.closest(".layer-thumbnail-picker, .layer-variant-menu")) {
      return;
    }
    expandedVariantIds.clear();
    renderLayerList();
  });

  layerList.addEventListener("scroll", () => {
    if (!expandedVariantIds.size) return;
    expandedVariantIds.clear();
    renderLayerList();
  }, { passive: true });

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
    const focusTarget = window.Live2DGaze.focusTarget(lastTarget);
    internalModel.focusController.focus(focusTarget.x, focusTarget.y);
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
      const samples = {
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
      };
      document.documentElement.dataset.gazeSamples = JSON.stringify(samples);
      document.documentElement.dataset.gazeFocusSamples = JSON.stringify(
        Object.fromEntries(
          Object.entries(samples).map(([name, sample]) => [
            name,
            window.Live2DGaze.focusTarget(sample),
          ]),
        ),
      );
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
  const motionControls = window.Live2DMotionControls;
  const motionDefinitions = new Map();
  const motionKey = (group, index) => `${group}\u0000${index}`;
  const motionModelUrl = new URL(modelJson, document.baseURI);

  await Promise.all(Object.entries(groups).flatMap(([group, entries]) =>
    entries.map(async (entry, index) => {
      let definition = null;
      try {
        definition = await fetchJson(new URL(entry.File, motionModelUrl), { cache: "no-store" });
      } catch (error) {
        console.warn(`Could not inspect motion ${group}[${index}]`, error);
      }
      motionDefinitions.set(motionKey(group, index), motionControls.describeMotion(group, definition, entry));
    }),
  ));

  const motionManager = model.internalModel.motionManager;
  const coreModel = model.internalModel.coreModel;
  const rawCoreModel = coreModel.getModel?.();
  const rawParameterIds = Array.from(rawCoreModel?.parameters?.ids || []);
  const parameterCount = coreModel.getParameterCount?.()
    ?? rawCoreModel?.parameters?.count
    ?? rawParameterIds.length;
  const parameterIndices = new Map();

  function parameterIdText(value) {
    if (typeof value === "string") return value;
    const cubismString = value?.getString?.();
    if (typeof cubismString === "string") return cubismString;
    if (typeof cubismString?.s === "string") return cubismString.s;
    if (typeof value?.s === "string") return value.s;
    return String(value || "");
  }

  for (let index = 0; index < parameterCount; index += 1) {
    const id = rawParameterIds[index] || coreModel.getParameterId?.(index);
    parameterIndices.set(parameterIdText(id), index);
  }

  function parameterDefault(index) {
    return coreModel.getParameterDefaultValue?.(index)
      ?? rawCoreModel?.parameters?.defaultValues?.[index];
  }

  function parameterValue(index) {
    return coreModel.getParameterValueByIndex?.(index)
      ?? rawCoreModel?.parameters?.values?.[index];
  }

  let parameterRelease = null;

  function beginReleaseDebug(durationMs, parameterCount) {
    if (!params.has("motiondebug")) return;
    document.documentElement.dataset.motionReleaseDurationMs = String(durationMs);
    document.documentElement.dataset.motionReleaseParameterCount = String(parameterCount);
    delete document.documentElement.dataset.motionReleaseSummary;
    window.__live2dMotionReleaseDebug = {
      completed: false,
      durationMs,
      parameterCount,
      samples: [],
    };
  }

  function publishReleaseProgress(progress, weight = null) {
    if (!params.has("motiondebug")) return;
    if (progress === null) {
      delete document.documentElement.dataset.motionReleaseProgress;
      const debug = window.__live2dMotionReleaseDebug;
      if (debug) {
        debug.completed = true;
        const middle = debug.samples.reduce((closest, sample) => (
          !closest || Math.abs(sample.progress - 0.5) < Math.abs(closest.progress - 0.5)
            ? sample
            : closest
        ), null);
        document.documentElement.dataset.motionReleaseSummary = JSON.stringify({
          completed: true,
          durationMs: debug.durationMs,
          parameterCount: debug.parameterCount,
          sampleCount: debug.samples.length,
          middle,
        });
      }
      return;
    }
    document.documentElement.dataset.motionReleaseProgress = progress.toFixed(3);
    window.__live2dMotionReleaseDebug?.samples.push({ progress, weight });
  }

  function cancelParameterRelease() {
    if (!parameterRelease) return;
    const release = parameterRelease;
    parameterRelease = null;
    app.ticker.remove(release.tick, null);
    publishReleaseProgress(null);
    release.resolve(false);
  }

  function releaseParameters(parameterIds, durationMs) {
    cancelParameterRelease();
    const parameters = parameterIds.flatMap((id) => {
      const index = parameterIndices.get(id);
      if (index === undefined) return [];
      const from = parameterValue(index);
      const to = parameterDefault(index);
      return Number.isFinite(from) && Number.isFinite(to) ? [{ index, from, to }] : [];
    });

    beginReleaseDebug(durationMs, parameters.length);
    if (!parameters.length) {
      publishReleaseProgress(null);
      return Promise.resolve(true);
    }

    return new Promise((resolve) => {
      const startedAt = performance.now();
      const duration = Math.max(1, durationMs);
      const tick = () => {
        const progress = Math.min(1, (performance.now() - startedAt) / duration);
        const weight = motionControls.sineEase(progress);
        parameters.forEach(({ index, from, to }) => {
          coreModel.setParameterValueByIndex(index, from + (to - from) * weight);
        });
        coreModel.saveParameters?.();
        publishReleaseProgress(progress, weight);
        if (progress < 1) return;
        app.ticker.remove(tick, null);
        if (parameterRelease?.tick === tick) parameterRelease = null;
        publishReleaseProgress(null);
        resolve(true);
      };
      parameterRelease = { tick, resolve };
      const beforeRender = (PIXI.UPDATE_PRIORITY?.LOW ?? -25) + 1;
      app.ticker.add(tick, null, beforeRender);
      tick();
    });
  }

  const avatarMotionKey = currentAvatar?.id || motionModelUrl.pathname;
  function persistentPreferenceKey(group, index) {
    return `live2d.motion-persistent:${avatarMotionKey}:${group}:${index}`;
  }

  function readPersistentPreference(group, index) {
    try {
      return localStorage.getItem(persistentPreferenceKey(group, index)) === "true";
    } catch {
      return false;
    }
  }

  function writePersistentPreference(group, index, enabled) {
    try {
      const key = persistentPreferenceKey(group, index);
      if (enabled) localStorage.setItem(key, "true");
      else localStorage.removeItem(key);
    } catch {
      // Storage can be unavailable in privacy-restricted browser contexts.
    }
  }

  let activeToggle = null;
  let motionSerial = 0;

  function markActive(active, enabled) {
    active.button.classList.toggle("is-active", enabled);
    active.button.setAttribute("aria-pressed", String(enabled));
  }

  function scheduleToggleOff(active) {
    clearTimeout(active.timer);
    if (active.persistCheckbox.checked) return;
    active.timer = setTimeout(() => {
      if (activeToggle === active) void deactivateToggle();
    }, motionControls.AUTO_OFF_MS);
  }

  async function resumeIdle() {
    if (!groups.Idle?.length) return;
    await model.motion("Idle", 0, PIXI.live2d.MotionPriority.FORCE);
  }

  async function deactivateToggle({ resume = true, updateStatus = true } = {}) {
    const active = activeToggle;
    if (!active) return;
    activeToggle = null;
    const releaseSerial = ++motionSerial;
    clearTimeout(active.timer);
    markActive(active, false);
    motionManager.stopAllMotions();
    if (updateStatus) statusElement.textContent = t.returningToIdle;
    const completed = await releaseParameters(active.info.parameterIds, active.info.releaseDurationMs);
    if (!completed || releaseSerial !== motionSerial) return;
    if (resume) await resumeIdle();
    if (updateStatus) statusElement.textContent = t.idle;
  }

  function motionButton(group, entry, index) {
    const info = motionDefinitions.get(motionKey(group, index));
    const wrapper = document.createElement("div");
    wrapper.className = "motion-control";
    wrapper.dataset.motionGroup = group;
    wrapper.dataset.motionIndex = String(index);
    wrapper.dataset.motionParameterCount = String(info.parameterIds.length);
    wrapper.dataset.motionReleaseMs = String(info.releaseDurationMs);
    const button = document.createElement("button");
    button.className = `motion${group === newGroup ? " new" : ""}`;
    button.type = "button";
    button.setAttribute("aria-pressed", "false");
    const file = decodeURIComponent(new URL(entry.File, motionModelUrl).pathname.split("/").pop())
      .replace(/\.motion3\.json$/i, "");
    const groupLabel = group.replace(/[_-]+/g, " ");
    const fallbackLabel = groups[group].length === 1 ? groupLabel : `${groupLabel} ${index + 1}`;
    const label = entry.Names?.[locale] || entry.Name || fallbackLabel;
    button.append(label);
    const small = document.createElement("span");
    small.className = "file";
    small.textContent = file;
    button.appendChild(small);
    wrapper.appendChild(button);

    let persistCheckbox = null;
    if (info.toggleable) {
      const persistLabel = document.createElement("label");
      persistLabel.className = "motion-persist";
      persistLabel.title = t.toggleOffHint;
      persistCheckbox = document.createElement("input");
      persistCheckbox.type = "checkbox";
      persistCheckbox.checked = readPersistentPreference(group, index);
      persistCheckbox.setAttribute("aria-label", `${label}: ${t.dontToggleOff}`);
      persistLabel.append(persistCheckbox, t.dontToggleOff);
      wrapper.appendChild(persistLabel);

      persistCheckbox.addEventListener("change", () => {
        writePersistentPreference(group, index, persistCheckbox.checked);
        const active = activeToggle;
        if (!active || active.group !== group || active.index !== index) return;
        if (!persistCheckbox.checked) {
          scheduleToggleOff(active);
          return;
        }
        clearTimeout(active.timer);
        if (active.info.replayWhilePersistent && !motionManager.playing) {
          void model.motion(group, index, PIXI.live2d.MotionPriority.FORCE);
        }
      });
    }

    button.onclick = async () => {
      cancelParameterRelease();
      if (activeToggle?.group === group && activeToggle.index === index) {
        await deactivateToggle();
        return;
      }
      if (activeToggle) await deactivateToggle({ resume: false, updateStatus: false });
      const requestSerial = ++motionSerial;
      statusElement.textContent = t.playing(label);
      const ok = await model.motion(group, index, PIXI.live2d.MotionPriority.FORCE);
      if (requestSerial !== motionSerial) return;
      if (!ok) {
        statusElement.textContent = t.playFailed(group, index);
        return;
      }
      if (info.toggleable) {
        activeToggle = {
          group,
          index,
          label,
          button,
          persistCheckbox,
          info,
          serial: requestSerial,
          timer: null,
        };
        markActive(activeToggle, true);
        scheduleToggleOff(activeToggle);
      }
    };
    return wrapper;
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

  motionManager.on("motionFinish", () => {
    if (parameterRelease) return;
    const active = activeToggle;
    if (!active) {
      statusElement.textContent = t.idle;
      return;
    }
    if (!active.persistCheckbox.checked || !active.info.replayWhilePersistent) return;
    const serial = active.serial;
    setTimeout(async () => {
      if (activeToggle !== active || active.serial !== serial) return;
      await model.motion(active.group, active.index, PIXI.live2d.MotionPriority.FORCE);
    }, 0);
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
