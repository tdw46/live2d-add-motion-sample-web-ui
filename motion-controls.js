(function exposeMotionControls(root, factory) {
  const api = factory();
  if (typeof module === "object" && module && module.exports) module.exports = api;
  if (root) root.Live2DMotionControls = api;
})(typeof window === "object" ? window : null, () => {
  const AUTO_OFF_MS = 2000;
  const DEFAULT_FADE_MS = 500;
  const HOLD_EPSILON = 0.15;
  const STATE_GROUPS = new Set([
    "idle",
    "smile",
    "surprise",
    "surprised",
    "sad",
    "angry",
    "shy",
    "smirk",
    "cheek",
    "expression",
    "emotion",
  ]);

  function normalizedGroup(group) {
    return String(group || "").replace(/[^a-z0-9]+/gi, "").toLowerCase();
  }

  function curveValues(curve) {
    const segments = curve?.Segments;
    if (!Array.isArray(segments) || segments.length < 2) return null;
    const first = Number(segments[1]);
    let last = first;
    let cursor = 2;
    const segmentWidths = { 0: 2, 1: 6, 2: 2, 3: 2 };
    while (cursor < segments.length) {
      const width = segmentWidths[segments[cursor]];
      if (!width || cursor + width >= segments.length) break;
      last = Number(segments[cursor + width]);
      cursor += width + 1;
    }
    return Number.isFinite(first) && Number.isFinite(last) ? { first, last } : null;
  }

  function motionHoldsFinalPose(motion) {
    return (motion?.Curves || []).some((curve) => {
      if (curve?.Target !== "Parameter") return false;
      const values = curveValues(curve);
      return values && Math.abs(values.last - values.first) > HOLD_EPSILON;
    });
  }

  function motionParameterIds(motion) {
    return [...new Set(
      (motion?.Curves || [])
        .filter((curve) => curve?.Target === "Parameter" && curve.Id)
        .map((curve) => curve.Id),
    )];
  }

  function positiveSeconds(value) {
    const seconds = Number(value);
    return Number.isFinite(seconds) && seconds > 0 ? seconds : null;
  }

  function releaseDurationMs(motion, definition) {
    const seconds = positiveSeconds(motion?.Meta?.FadeOutTime)
      ?? positiveSeconds(definition?.FadeOutTime)
      ?? positiveSeconds(motion?.Meta?.FadeInTime)
      ?? positiveSeconds(definition?.FadeInTime);
    return seconds === null ? DEFAULT_FADE_MS : seconds * 1000;
  }

  function sineEase(value) {
    const clamped = Math.min(1, Math.max(0, Number(value) || 0));
    return 0.5 - 0.5 * Math.cos(clamped * Math.PI);
  }

  function describeMotion(group, motion, definition) {
    const loops = Boolean(motion?.Meta?.Loop);
    const holdsFinalPose = motionHoldsFinalPose(motion);
    const toggleable = loops || holdsFinalPose || STATE_GROUPS.has(normalizedGroup(group));
    return {
      toggleable,
      loops,
      holdsFinalPose,
      replayWhilePersistent: toggleable && !loops && !holdsFinalPose,
      parameterIds: motionParameterIds(motion),
      releaseDurationMs: releaseDurationMs(motion, definition),
    };
  }

  return {
    AUTO_OFF_MS,
    DEFAULT_FADE_MS,
    HOLD_EPSILON,
    curveValues,
    motionHoldsFinalPose,
    motionParameterIds,
    releaseDurationMs,
    sineEase,
    describeMotion,
  };
});
