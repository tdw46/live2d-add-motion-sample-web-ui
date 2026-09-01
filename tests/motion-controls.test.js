const test = require("node:test");
const assert = require("node:assert/strict");
const {
  AUTO_OFF_MS,
  DEFAULT_FADE_MS,
  describeMotion,
  motionHoldsFinalPose,
  motionParameterIds,
  releaseDurationMs,
  sineEase,
} = require("../motion-controls.js");

function curve(id, end, start = 0) {
  return { Target: "Parameter", Id: id, Segments: [0, start, 0, 0.4, end] };
}

test("state motions default to a two-second toggle-off", () => {
  assert.equal(AUTO_OFF_MS, 2000);
  assert.equal(describeMotion("Smile", { Meta: { Loop: false }, Curves: [] }).toggleable, true);
  assert.equal(describeMotion("Shy", { Meta: { Loop: false }, Curves: [] }).toggleable, true);
});

test("held custom expressions are toggleable even outside a known group", () => {
  const motion = { Meta: { Loop: false }, Curves: [curve("ParamCheek", 1)] };
  assert.equal(motionHoldsFinalPose(motion), true);
  assert.deepEqual(describeMotion("Action", motion), {
    toggleable: true,
    loops: false,
    holdsFinalPose: true,
    replayWhilePersistent: false,
    parameterIds: ["ParamCheek"],
    releaseDurationMs: 500,
  });
});

test("one-shot actions play through without toggle controls", () => {
  const headShake = {
    Meta: { Loop: false },
    Curves: [{
      Target: "Parameter",
      Id: "ParamAngleX",
      Segments: [0, 0, 0, 0.8, 20, 0, 1.6, 0],
    }],
  };
  assert.equal(motionHoldsFinalPose(headShake), false);
  assert.equal(describeMotion("Head_shake", headShake).toggleable, false);
  assert.equal(describeMotion("Legs_sway", headShake).toggleable, false);
});

test("persistent state motions replay only when they otherwise return to base", () => {
  const smile = describeMotion("Smile", { Meta: { Loop: false }, Curves: [curve("ParamMouthForm", 0)] });
  const angry = describeMotion("Angry", { Meta: { Loop: false }, Curves: [curve("ParamMouthForm", -0.7)] });
  const idle = describeMotion("Idle", { Meta: { Loop: true }, Curves: [] });
  assert.equal(smile.replayWhilePersistent, true);
  assert.equal(angry.replayWhilePersistent, false);
  assert.equal(idle.replayWhilePersistent, false);
});

test("parameter reset scope is unique and excludes model curves", () => {
  assert.deepEqual(motionParameterIds({ Curves: [
    curve("ParamEyeLOpen", 0),
    curve("ParamEyeLOpen", 1),
    { Target: "Model", Id: "Opacity", Segments: [0, 1] },
  ] }), ["ParamEyeLOpen"]);
});

test("toggle-off matches authored fades and otherwise uses the runtime default", () => {
  assert.equal(DEFAULT_FADE_MS, 500);
  assert.equal(releaseDurationMs({ Meta: {} }, {}), 500);
  assert.equal(releaseDurationMs({ Meta: { FadeInTime: 0.35 } }, {}), 350);
  assert.equal(releaseDurationMs({ Meta: { FadeOutTime: 0.2, FadeInTime: 0.35 } }, {}), 200);
  assert.equal(releaseDurationMs({ Meta: {} }, { FadeOutTime: 0.4 }), 400);
});

test("toggle-off uses the same smooth sine easing shape as motion fades", () => {
  assert.equal(sineEase(0), 0);
  assert.ok(Math.abs(sineEase(0.5) - 0.5) < 1e-12);
  assert.equal(sineEase(1), 1);
  assert.ok(sineEase(0.25) < 0.25);
  assert.ok(sineEase(0.75) > 0.75);
});
