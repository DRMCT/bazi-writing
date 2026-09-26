#!/usr/bin/env python3
"""换盘测试的对照实验报告：几份人物档案两两算差异度，按"同盘"与"异盘"分组，给阈值建议。

    python scripts/divergence_report.py 人物档案.json ... [--out references/校核/换盘_对照报告.md]

同盘：两份档案的 chart 字段解析后指向同一张盘的四柱（读命盘文件比四柱，不比路径），是"同一个人物写两遍"的措辞噪音；
异盘：不同的盘。换盘测试要求异盘的差异度都过阈值，而阈值又必须高于同盘的差异度，否则测试没有分辨力。
建议阈值取 同盘最大值 与 异盘最小值 的中点；两者若交叉（同盘的比异盘的还高），报告直接写出，阈值不给。
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_divergence as cd  # noqa: E402


def load(path: Path) -> tuple[dict, str]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    chart_path = (path.parent.parent / doc["chart"]).resolve()
    chart = json.loads(chart_path.read_text(encoding="utf-8"))
    fp = chart["fourPillars"]
    key = " ".join(fp[k] or "" for k in ("year", "month", "day", "hour"))
    return doc, key


def run(paths: list[Path]) -> dict:
    docs = [(p, *load(p)) for p in paths]
    rows = []
    for (pa, a, ka), (pb, b, kb) in itertools.combinations(docs, 2):
        r = cd.compare(a, b)
        rows.append({"a": pa.stem, "b": pb.stem, "same": ka == kb, "pillarsA": ka, "pillarsB": kb,
                     "divergence": r["divergence"], "idDistance": r["idDistance"], "textDistance": r["textDistance"],
                     "sequenceDistance": r["sequenceDistance"], "sharedKinds": len(r["sharedKinds"])})
    same = [r["divergence"] for r in rows if r["same"]]
    diff = [r["divergence"] for r in rows if not r["same"]]
    out = {"pairs": rows, "same": {"n": len(same), "max": max(same) if same else None, "min": min(same) if same else None},
           "diff": {"n": len(diff), "min": min(diff) if diff else None, "max": max(diff) if diff else None}}
    if same and diff:
        gap = min(diff) - max(same)
        out["gap"] = round(gap, 4)
        out["suggestedThreshold"] = round((max(same) + min(diff)) / 2, 2) if gap > 0 else None
    return out


def render(res: dict, paths: list[Path]) -> str:
    lines = ["# 换盘测试对照报告", "",
             "由 scripts/divergence_report.py 生成。差异度算法见 scripts/check_divergence.py（编号路：溯源编号折成事实种类后的 Jaccard 距离；"
             "文本路：逐段字二元组 Jaccard 距离取平均；差异度取两路平均）。同盘＝两份档案指向同一张盘（同一人物写两遍，量的是措辞噪音）；"
             "异盘＝不同的盘。换盘测试要异盘全过阈值，阈值又要高于同盘，否则没有分辨力。", "",
             "档案：" + "、".join(p.as_posix() for p in paths), "",
             "| 甲 | 乙 | 同盘 | 差异度 | 编号路 | 文本路 | 序列距离 | 共有事实种类 |", "|---|---|---|---|---|---|---|---|"]
    for r in sorted(res["pairs"], key=lambda x: x["divergence"]):
        lines.append(f"| {r['a']} | {r['b']} | {'是' if r['same'] else '否'} | {r['divergence']} | {r['idDistance']} | {r['textDistance']} | {r['sequenceDistance']} | {r['sharedKinds']} |")
    s, d = res["same"], res["diff"]
    lines += ["", f"同盘对 {s['n']} 个，差异度 {s['min']}–{s['max']}；异盘对 {d['n']} 个，差异度 {d['min']}–{d['max']}。"]
    if "gap" in res:
        if res["suggestedThreshold"] is not None:
            lines.append(f"同盘最大与异盘最小相差 {res['gap']}，建议阈值取中点 {res['suggestedThreshold']}。")
        else:
            lines.append(f"同盘最大 {s['max']} 高于异盘最小 {d['min']}（差 {res['gap']}），两组交叉，现有度量分不开，阈值不给。")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="人物档案两两差异度，分同盘、异盘，给阈值建议")
    ap.add_argument("docs", nargs="+")
    ap.add_argument("--out", default=None, help="写成 markdown 报告的路径；不给只打印 JSON")
    a = ap.parse_args(argv)
    paths = [Path(p) for p in a.docs]
    res = run(paths)
    if a.out:
        Path(a.out).write_text(render(res, paths), encoding="utf-8")
        print(f"→ {a.out}")
    print(json.dumps({k: v for k, v in res.items() if k != "pairs"}, ensure_ascii=False))
    for r in sorted(res["pairs"], key=lambda x: x["divergence"]):
        print(f"{'同' if r['same'] else '异'} {r['a']}×{r['b']}: {r['divergence']} (编号 {r['idDistance']} 文本 {r['textDistance']} 序列 {r['sequenceDistance']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
