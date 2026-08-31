(function exposeGazeMath(root, factory) {
  const api = factory();
  if (typeof module === "object" && module && module.exports) module.exports = api;
  if (root) root.Live2DGaze = api;
})(typeof window === "object" ? window : null, () => {
  const IRIS_PATTERN = /(?:^|[^a-z])(iris|irides|pupil)(?:[^a-z]|$)/i;
  const EYE_WHITE_PATTERN = /(?:eye[^a-z]*white|white[^a-z]*eye|sclera)/i;
  const EYE_PATTERN = /(?:^|[^a-z])eye(?:[^a-z]|$)/i;
  const NON_OPEN_EYE_PATTERN = /(?:brow|closed|blink|smile|iris|irides|pupil|white|sclera)/i;

  function combinedName(drawable) {
    return `${drawable.id || ""} ${drawable.name || ""}`.replace(/_/g, " ");
  }

  function unionBounds(drawables) {
    if (!drawables.length) return null;
    const left = Math.min(...drawables.map((drawable) => drawable.bounds.x));
    const top = Math.min(...drawables.map((drawable) => drawable.bounds.y));
    const right = Math.max(...drawables.map((drawable) => drawable.bounds.x + drawable.bounds.width));
    const bottom = Math.max(...drawables.map((drawable) => drawable.bounds.y + drawable.bounds.height));
    return { x: left, y: top, width: right - left, height: bottom - top };
  }

  function buildGeometry(drawables) {
    const valid = drawables.filter((drawable) =>
      drawable.bounds && drawable.bounds.width > 0 && drawable.bounds.height > 0,
    );
    const irises = valid.filter((drawable) => IRIS_PATTERN.test(combinedName(drawable)));
    const whites = valid.filter((drawable) => EYE_WHITE_PATTERN.test(combinedName(drawable)));
    const openEyes = valid.filter((drawable) => {
      const name = combinedName(drawable);
      return EYE_PATTERN.test(name) && !NON_OPEN_EYE_PATTERN.test(name);
    });
    const eyeLayers = whites.length >= 2 ? whites : openEyes.length >= 2 ? openEyes : irises;
    const eyeBounds = unionBounds(eyeLayers);
    const irisBounds = unionBounds(irises);
    if (!eyeBounds || !irisBounds) return null;

    const sortedEyes = [...eyeLayers].sort((left, right) =>
      (left.bounds.x + left.bounds.width / 2) - (right.bounds.x + right.bounds.width / 2),
    );
    const leftEye = sortedEyes[0]?.bounds;
    const rightEye = sortedEyes[sortedEyes.length - 1]?.bounds;
    const leftInnerEdge = leftEye ? leftEye.x + leftEye.width : eyeBounds.x + eyeBounds.width / 2;
    const rightInnerEdge = rightEye ? rightEye.x : eyeBounds.x + eyeBounds.width / 2;
    const centerX = leftInnerEdge <= rightInnerEdge
      ? (leftInnerEdge + rightInnerEdge) / 2
      : eyeBounds.x + eyeBounds.width / 2;

    return {
      eyeBounds,
      irisMidY: irisBounds.y + irisBounds.height / 2,
      centerX,
      reach: Math.max(1, eyeBounds.width * 1.75, eyeBounds.height * 5),
      eyeLayerIds: eyeLayers.map((drawable) => drawable.id),
      irisLayerIds: irises.map((drawable) => drawable.id),
    };
  }

  function distanceOutside(bounds, point) {
    const right = bounds.x + bounds.width;
    const bottom = bounds.y + bounds.height;
    const dx = point.x < bounds.x ? bounds.x - point.x : point.x > right ? point.x - right : 0;
    const dy = point.y < bounds.y ? bounds.y - point.y : point.y > bottom ? point.y - bottom : 0;
    return Math.hypot(dx, dy);
  }

  function smoothstep(value) {
    const clamped = Math.max(0, Math.min(1, value));
    return clamped * clamped * (3 - 2 * clamped);
  }

  function targetForPoint(geometry, point) {
    const amplitude = smoothstep(distanceOutside(geometry.eyeBounds, point) / geometry.reach);
    if (amplitude === 0) return { x: 0, y: 0, amplitude: 0 };

    const dx = point.x - geometry.centerX;
    const dy = point.y - geometry.irisMidY;
    const length = Math.hypot(dx, dy) || 1;
    return {
      x: (dx / length) * amplitude,
      // Cubism's positive EyeBallY points up while model-canvas Y points down.
      y: -(dy / length) * amplitude,
      amplitude,
    };
  }

  return { buildGeometry, distanceOutside, targetForPoint };
});
