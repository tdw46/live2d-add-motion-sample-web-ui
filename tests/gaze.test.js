const test = require("node:test");
const assert = require("node:assert/strict");
const {
  buildGeometry,
  distanceOutside,
  targetForPoint,
  focusTarget,
  FOCUS_SCALE,
} = require("../gaze.js");

const geometry = buildGeometry([
  { id: "eye_white_r", bounds: { x: 10, y: 20, width: 20, height: 10 } },
  { id: "eye_white_l", bounds: { x: 50, y: 20, width: 20, height: 10 } },
  { id: "pupil_r", bounds: { x: 17, y: 21, width: 8, height: 8 } },
  { id: "iris_l", bounds: { x: 55, y: 23, width: 8, height: 8 } },
]);

test("uses the gap between eye layers and the iris-pixel vertical midpoint", () => {
  assert.equal(geometry.centerX, 40);
  assert.equal(geometry.irisMidY, 26);
  assert.deepEqual(geometry.eyeLayerIds, ["eye_white_r", "eye_white_l"]);
});

test("keeps the authored neutral gaze while the pointer is between the eyes", () => {
  assert.deepEqual(targetForPoint(geometry, { x: 40, y: 25 }), { x: 0, y: 0, amplitude: 0 });
});

test("measures amplitude from the eye rectangle instead of the model center", () => {
  assert.equal(distanceOutside(geometry.eyeBounds, { x: 70, y: 25 }), 0);
  const near = targetForPoint(geometry, { x: 80, y: 25 });
  const far = targetForPoint(geometry, { x: 200, y: 25 });
  assert.ok(near.amplitude > 0 && near.amplitude < far.amplitude);
  assert.equal(far.amplitude, 1);
  assert.ok(near.x > 0);
});

test("uses the iris midpoint for up and down direction", () => {
  const up = targetForPoint(geometry, { x: 40, y: -80 });
  const down = targetForPoint(geometry, { x: 40, y: 130 });
  assert.ok(up.y > 0);
  assert.ok(down.y < 0);
  assert.equal(up.x, 0);
  assert.equal(down.x, 0);
});

test("keeps Cubism focus full-strength so head mesh deformation remains intact", () => {
  assert.deepEqual(FOCUS_SCALE, { x: 1, y: 1 });
  assert.deepEqual(focusTarget({ x: 0.8, y: -0.6 }), { x: 0.8, y: -0.6 });
  assert.deepEqual(focusTarget({ x: 0, y: 0 }), { x: 0, y: 0 });
});
