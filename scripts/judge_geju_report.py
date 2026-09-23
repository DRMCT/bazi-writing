#!/usr/bin/env python3
"""开发期工具：把 geju.judge 跑过《子平真诠评注》八格章的 83 张徐评命例，写成报告 references/校核/格局_判定报告.md。

    python scripts/judge_geju_report.py

报告三节：判定分布与原子覆盖率；词表认不出的原子（按出现次数）；逐盘一行（格、判定、成立的败条与救应、徐评判词前四十字），
供人看判定器与徐评是否合拍。判定器口径见 geju.py 逐盘判定一节。
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bazi_core import geju  # noqa: E402
from bazi_core.shishen import determine_structure  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "scripts" / "bazi_core" / "tests" / "fixtures" / "ziping_lipan.json"
REPORT = ROOT / "references" / "校核" / "格局_判定报告.md"


def main() -> int:
    cases = [c for c in json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"] if "expectedStructures" in c]
    verdicts: Counter = Counter()
    unknown: Counter = Counter()
    known = total = 0
    rows = []
    for c in cases:
        pillars = dict(zip(("year", "month", "day", "hour"), c["pillars"]))
        s = determine_structure(*c["pillars"])
        j = geju.judge(pillars, s)
        verdicts[j["verdict"]] += 1
        k, n = j["coverage"].split("/")
        known += int(k); total += int(n)
        blocks = j["cheng"] + j["bai"] + [x["cause"] for x in j["jiu"]] + [x["fix"] for x in j["jiu"]]
        for b in blocks:
            for a, v in b["atoms"].items():
                if v is None:
                    unknown[a] += 1
        bai = "、".join(b["text"] for b in j["bai"] if b["holds"])
        jiu = "、".join(x["text"] for x in j["jiu"] if x["applies"])
        cheng = "、".join(b["text"] for b in j["cheng"] if b["holds"])
        rows.append(f"| {c['id']} | {' '.join(c['pillars'])} | {s.name}{'（本格' + s.base + '）' if s.base != s.name else ''} | {j['verdict']} | {cheng} | {bai} | {jiu} | {c['comment'][:40]} |")
    lines = ["# 格局逐盘判定报告", "",
             f"生成：{date.today().isoformat()}。geju.judge 对八格章 {len(cases)} 张徐评命例逐条求值。判定分布：{dict(verdicts)}；"
             f"原子覆盖率 {known}/{total}（{known / total:.0%}）。", "",
             "判定口径：一条条件 = 原子的合取；逢/见/带/无只认透干与支本气；重/多 = 计数 ≥ 2（透 1、本气 1、中气 0.5、余气 0.25）；"
             "身强弱取 strength.assess；相碍看财印透干是否相邻；合看天干五合（含与日主合）；刑冲看月支。"
             "化、会、留、去、先后一类原子不判（None），整条为待判。成败判定：有败条成立且无救应为败格，有救应为败而有救，否则有成条成立为成格。", "",
             "徐评举例多为讨论变格、相神与取运，不都是成格之造，判定分布偏败不奇怪；要看的是逐盘的败条与救应与判词是否说的同一件事。", "",
             "## 词表认不出的原子", ""]
    lines += [f"- {a}：{n} 次" for a, n in unknown.most_common()]
    lines += ["", "## 逐盘", "", "| 例盘 | 四柱 | 格 | 判定 | 成立的成条 | 成立的败条 | 救应 | 判词 |", "|---|---|---|---|---|---|---|---|"] + rows
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:3]))
    print("→", REPORT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
