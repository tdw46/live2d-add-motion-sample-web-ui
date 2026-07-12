#!/usr/bin/env python3
"""Independent validator for the generated motions (implemented separately
from the generator so it can cross-check it).

Checks:
 1. Meta.CurveCount / TotalSegmentCount / TotalPointCount match the actual data
 2. keyframe times are monotonically increasing, start at t=0, end at Duration
 3. bezier control-point times stay inside their segment
 4. every value stays within the range observed in the pre-existing motions
    (also flags parameters the existing motions never use)
 5. first and last frames equal the base pose (actions start from and return
    to the base pose)
 6. motions are registered in model3.json and the referenced files exist

For models that ship without any motions, checks 4 and 5 are skipped with a
warning. Visual verification in the browser is then the only quality gate,
so perform it extra carefully.

Usage: python3 tools/validate_motions.py [runtime dir]
(without an argument, the model registered in model.config.json is used)
Exit code: 0 = pass / 1 = violations found
"""
import collections
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GROUP = "Action"
EPS = 1e-6


def resolve_runtime():
    if len(sys.argv) > 1:
        return sys.argv[1]
    cfg_path = os.path.join(ROOT, "model.config.json")
    if not os.path.exists(cfg_path):
        sys.exit("ERROR: model.config.json がありません。先に python3 tools/setup_model.py を実行してください。")
    cfg = json.load(open(cfg_path))
    return os.path.join(ROOT, os.path.dirname(cfg["model3"]))


RUNTIME = resolve_runtime()


def points(curve):
    """Return (time, value) keyframes plus (segment count, point count,
    control-point violations)."""
    seg = curve["Segments"]
    pts = [(seg[0], seg[1])]
    nseg, npt, ctrl_errors = 0, 1, []
    i = 2
    prev_t = seg[0]
    while i < len(seg):
        nseg += 1
        if seg[i] == 1:  # bezier
            c1t, _, c2t, _, t, v = seg[i + 1:i + 7]
            if not (prev_t - EPS <= c1t <= c2t <= t + EPS):
                ctrl_errors.append(t)
            npt += 3
            pts.append((t, v))
            prev_t = t
            i += 7
        else:
            t, v = seg[i + 1], seg[i + 2]
            npt += 1
            pts.append((t, v))
            prev_t = t
            i += 3
    return pts, nseg, npt, ctrl_errors


def main():
    model3_path = glob.glob(os.path.join(RUNTIME, "*.model3.json"))[0]
    model3 = json.load(open(model3_path))
    entries = model3["FileReferences"]["Motions"].get(GROUP, [])
    if not entries:
        print(f"NG: model3.json に {GROUP} グループがありません")
        return 1

    new_files = [os.path.join(RUNTIME, e["File"]) for e in entries]
    # Motion folder names vary between models (motion/, motions/, ...),
    # so search recursively instead of assuming a directory name
    all_files = set(os.path.normpath(f) for f in
                    glob.glob(os.path.join(RUNTIME, "**", "*.motion3.json"), recursive=True))
    existing = sorted(all_files - set(os.path.normpath(f) for f in new_files))

    # Observe safe value ranges and the base pose (majority first-frame value)
    # from the pre-existing motions
    safe = {}
    first_vals = collections.defaultdict(collections.Counter)
    for f in existing:
        for c in json.load(open(f))["Curves"]:
            if c["Target"] != "Parameter":
                continue
            pts, *_ = points(c)
            vals = [v for _, v in pts]
            lo, hi = safe.get(c["Id"], (float("inf"), float("-inf")))
            safe[c["Id"]] = (min(lo, min(vals)), max(hi, max(vals)))
            first_vals[c["Id"]][round(pts[0][1], 3)] += 1
    base_pose = {pid: cnt.most_common(1)[0][0] for pid, cnt in first_vals.items()}

    has_reference = bool(existing)
    if not has_reference:
        print("WARN: 既存モーションがないモデルのため、値域と基本姿勢のチェックをスキップします。")
        print("WARN: ブラウザでの目視確認を必ず行ってください。")

    errors = []
    for f in new_files:
        name = os.path.basename(f)
        if not os.path.exists(f):
            errors.append(f"{name}: model3.jsonから参照されているがファイルがない")
            continue
        d = json.load(open(f))
        meta = d["Meta"]
        nseg_total = npt_total = 0
        for c in d["Curves"]:
            pid = c["Id"]
            pts, nseg, npt, ctrl_errors = points(c)
            nseg_total += nseg
            npt_total += npt
            for t in ctrl_errors:
                errors.append(f"{name}:{pid}: ベジェ制御点が区間外 (t={t})")
            times = [t for t, _ in pts]
            if times != sorted(times):
                errors.append(f"{name}:{pid}: 時刻が単調増加でない")
            if abs(times[0]) > EPS:
                errors.append(f"{name}:{pid}: t=0 から始まっていない")
            if abs(times[-1] - meta["Duration"]) > EPS:
                errors.append(f"{name}:{pid}: 最終キー({times[-1]})がDuration({meta['Duration']})と不一致")
            if c["Target"] != "Parameter" or not has_reference:
                continue
            if pid not in safe:
                errors.append(f"{name}:{pid}: 既存モーションで未使用のパラメータ(値域を確認して意図的なら除外設定を)")
            else:
                lo, hi = safe[pid]
                for t, v in pts:
                    if not (lo - EPS <= v <= hi + EPS):
                        errors.append(f"{name}:{pid}: 値 {v} (t={t}) が観測値域 [{lo},{hi}] の外")
            base = base_pose.get(pid, 0)
            if abs(pts[0][1] - base) > EPS:
                errors.append(f"{name}:{pid}: 開始値 {pts[0][1]} が基本姿勢 {base} でない")
            if abs(pts[-1][1] - base) > EPS:
                errors.append(f"{name}:{pid}: 最終値 {pts[-1][1]} が基本姿勢 {base} でない")
        for key, actual in [("CurveCount", len(d["Curves"])),
                            ("TotalSegmentCount", nseg_total),
                            ("TotalPointCount", npt_total)]:
            if meta[key] != actual:
                errors.append(f"{name}: Meta.{key}={meta[key]} だが実データは {actual}")
        print(f"checked {name}: curves={len(d['Curves'])} segs={nseg_total} pts={npt_total}")

    print("---")
    if errors:
        print("\n".join(errors))
        print(f"NG: {len(errors)} 件の違反")
        return 1
    print(f"OK: {GROUP}グループ {len(new_files)} モーション全チェック合格")
    return 0


if __name__ == "__main__":
    sys.exit(main())
