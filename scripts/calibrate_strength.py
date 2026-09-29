#!/usr/bin/env python3
"""旺衰公式校准（DESIGN-命盘层 2.4）。分三步走，本脚本管第一步与第三步。

    python scripts/calibrate_strength.py sample   → 生成样本盘与公式判定，写 calibration/samples.json
    python scripts/calibrate_strength.py sheet     → 把样本摊成子代理可读的判定单（不含公式结论，防止锚定）
    python scripts/calibrate_strength.py score     → 读子代理的裁定，统计一致率并分层列出分歧
    python scripts/calibrate_strength.py classics  → 古籍例盘里徐评（或余春台按语）明说身强弱的盘作标准，统计公式一致率，写 calibration/classics.json

古籍标准（2026-09-23 加）：《穷通宝鉴评注》《子平真诠评注》两套例盘夹具里，判词或按语明说"身旺/身强/日元太旺/身弱/身轻/日元太弱/中和"
的盘，取其说法为标准；说运的句子（"身旺之地""行帮身运"）排除，一盘两说相反的排除。这是徐乐吾亲判，比子代理判定更硬，
两路标准并用：随机样本走子代理，例盘走徐评。

第二步是人的事：把判定单交给 Fable 子代理，每盘只给四柱与查表事实，不给公式结果，
要求按得令、得地、得势、合局逐项说理后给「身旺 / 身弱 / 中和」之一，写回 calibration/verdicts.json（分批则 verdicts.1.json……，score 合并）：
    {"S001": {"verdict": "身弱", "reason": "..."}, ...}

样本覆盖十日主乘十二月支共 120 格，每格一盘，年柱日支时柱由固定种子随机生成，可复现。
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bazi_core import relations, strength  # noqa: E402
from bazi_core.dayun import pillar_name, sexagenary_index  # noqa: E402
from bazi_core.shishen import BRANCHES, HIDDEN_STEMS, STEMS, stem_label, ten_god  # noqa: E402

OUT = Path("calibration")
SEED = 20260922
VERDICTS = ("身旺", "身弱", "中和")


def _legal_pillars_with(stem: str | None = None, branch: str | None = None) -> list[str]:
    out = []
    for i in range(60):
        name = pillar_name(i)
        if stem and name[0] != stem:
            continue
        if branch and name[1] != branch:
            continue
        out.append(name)
    return out


def build_samples() -> list[dict]:
    rng = random.Random(SEED)
    samples = []
    n = 0
    for dm in STEMS:
        for mb in BRANCHES:
            n += 1
            month = rng.choice(_legal_pillars_with(branch=mb))
            day = rng.choice(_legal_pillars_with(stem=dm))
            year = pillar_name(rng.randrange(60))
            hour = pillar_name(rng.randrange(60))
            pillars = {"year": year, "month": month, "day": day, "hour": hour}
            r = strength.assess(pillars)
            samples.append({
                "id": f"S{n:03d}",
                "pillars": pillars,
                "dayMaster": stem_label(STEMS.index(dm)),
                "monthBranch": mb,
                "formula": {"verdict": r["verdict"], "ratio": r["ratio"], "note": r["note"],
                            "flags": r["flags"]},
            })
    return samples


def facts(pillars: dict) -> dict:
    """查表事实：天干十神、地支藏干附十神、地支关系（三合三会、六合、六冲、刑害等）。不含任何强弱结论。"""
    ds = STEMS.index(pillars["day"][0])
    stems, hidden = {}, {}
    for k in ("year", "month", "day", "hour"):
        p = pillars[k]
        s = STEMS.index(p[0])
        stems[k] = f"{stem_label(s)}{'（日主）' if k == 'day' else ten_god(ds, s)}"
        hidden[k] = "、".join(f"{stem_label(h)}{ten_god(ds, h)}"
                             for h in HIDDEN_STEMS[BRANCHES.index(p[1])])
    nat = relations.natal_relations(pillars)
    combos = [f"{t['kind']}{t['branches']}成{t['element']}局" for t in nat["trios"]]
    combos += [f"{p['label']}{'、'.join(p['branches'])}" for p in nat["pairs"] if p["branches"]]
    return {"天干十神": stems, "地支藏干": hidden, "地支关系": combos or ["无"]}


# ---- 古籍例盘标准

import re

FIXTURES = Path(__file__).resolve().parent / "bazi_core" / "tests" / "fixtures"
_STRONG = r"身旺|身强|日元本旺|日元太旺|日元甚旺|日元极旺|日元旺|日主旺|日主甚旺|旺极|极旺|身重|身太旺"
_WEAK = r"身弱|日元太弱|日元甚弱|日元极弱|日元弱|日主弱|日主太弱|弱极|极弱|身太弱|身轻|衰弱"
_NEUTRAL = r"中和"
_PAT = re.compile(f"(?P<strong>{_STRONG})|(?P<weak>{_WEAK})|(?P<neutral>{_NEUTRAL})")
# 说运不说局：后接"之地/之乡/之方/运/地/乡"，或前有"运/行/入/至/转"，或"帮身"
_AFTER = re.compile(r"^(之地|之乡|之方|运|地|乡)")
_BEFORE = re.compile(r"(运|行|入|至|转|帮|补)$")


def _label_from_text(text: str) -> tuple[str | None, list[str]]:
    """从判词抽标签。返回 (标签或 None, 证据句)。两说相反或"弱而不弱"归 None/中和。"""
    votes: dict[str, list[str]] = {"身旺": [], "身弱": [], "中和": []}
    for m in _PAT.finditer(text):
        after = text[m.end():m.end() + 2]
        before = text[max(0, m.start() - 2):m.start()]
        if _AFTER.match(after) or _BEFORE.search(before):
            continue
        ctx = text[max(0, m.start() - 8):m.end() + 8]
        if m.group("weak") and text[m.end():m.end() + 3].startswith("而不弱"):
            votes["中和"].append(ctx); continue
        if m.group("strong"):
            votes["身旺"].append(ctx)
        elif m.group("weak"):
            votes["身弱"].append(ctx)
        else:
            votes["中和"].append(ctx)
    hit = [k for k, v in votes.items() if v]
    if not hit:
        return None, []
    if "身旺" in hit and "身弱" in hit:
        return None, votes["身旺"] + votes["身弱"]
    label = "身旺" if "身旺" in hit else "身弱" if "身弱" in hit else "中和"
    return label, votes[label]


def classics_cases() -> list[dict]:
    out = []
    zp = json.loads((FIXTURES / "ziping_lipan.json").read_text(encoding="utf-8"))["cases"]
    for c in zp:
        if c["flags"]:
            continue
        label, ev = _label_from_text(c["comment"])
        if label:
            y, m, d, h = c["pillars"]
            out.append({"id": f"子平-{c['id']}", "source": f"子平真诠评注 {c['page']} {c['chapter']}",
                        "pillars": {"year": y, "month": m, "day": d, "hour": h}, "label": label, "evidence": ev})
    qt = json.loads((FIXTURES / "qiongtong_lipan.json").read_text(encoding="utf-8"))
    qt = qt["cases"] if isinstance(qt, dict) else qt
    for c in qt:
        if c["flags"]:
            continue
        label, ev = _label_from_text(" ".join(c["judgment"] + c["note"]))
        if label:
            out.append({"id": f"穷通-{c['id']}", "source": f"穷通宝鉴评注 p{c['page']} {c['dayMaster']}{c['sectionTitle']}",
                        "pillars": c["pillars"], "label": label, "evidence": ev})
    rj = FIXTURES / "ziping_renjian.json"   # 2026-09-25：附录《人鉴·命理存验》67 例，林庚白判词明说身强弱的盘
    if rj.exists():
        for c in json.loads(rj.read_text(encoding="utf-8"))["cases"]:
            if c["flags"] or len(c["pillars"]) != 4:
                continue
            label, ev = _label_from_text(c["comment"])
            if label:
                y, m, d, h = c["pillars"]
                out.append({"id": c["id"], "source": f"子平真诠评注附录人鉴 p{c['page']} {c['name']}",
                            "pillars": {"year": y, "month": m, "day": d, "hour": h}, "label": label, "evidence": ev})
    return out


def _score(cases: list[dict], assess) -> dict:
    agree = 0
    matrix: dict[str, int] = {}
    by_label: dict[str, list[int]] = {}
    by_combo: dict[str, list[int]] = {}
    dis = []
    for c in cases:
        r = assess(c["pillars"])
        mine, theirs = r["verdict"], c["label"]
        hit = int(mine == theirs)
        agree += hit
        matrix[f"{theirs}→{mine}"] = matrix.get(f"{theirs}→{mine}", 0) + 1
        by_label.setdefault(theirs, []).append(hit)
        kinds = sorted({k["kind"] for k in r.get("combos", [])}) or ["无合"]
        for k in kinds:
            by_combo.setdefault(k, []).append(hit)
        if not hit:
            dis.append({"id": c["id"], "pillars": c["pillars"], "classic": theirs, "formula": mine,
                        "ratio": r["ratio"], "combos": [k["detail"] for k in r.get("combos", [])],
                        "evidence": c["evidence"][:2]})
    return {"n": len(cases), "agree": agree, "matrix": matrix,
            "byLabel": {k: f"{sum(v)}/{len(v)}" for k, v in by_label.items()},
            "byCombo": {k: f"{sum(v)}/{len(v)}" for k, v in sorted(by_combo.items())},
            "disagreements": dis}


def _assess_without_combos(pillars: dict) -> dict:
    saved = {k: getattr(strength, k) for k in ("SANHUI_FACTOR", "SANHE_FACTOR", "BANHE_FACTOR", "LIUHE_HUA_FACTOR",
                                                "LIUHE_DAMP", "STEMHE_HUA_FACTOR", "STEMHE_DAMP", "MINOR_DAMP")}
    try:
        for k in saved:
            setattr(strength, k, 1.0)
        orig = strength.combo_effects

        def no_override(p):
            b, s_, notes = orig(p)
            for e in list(b.values()) + list(s_.values()):
                e["override"] = None
            return b, s_, notes
        strength.combo_effects = no_override
        return strength.assess(pillars)
    finally:
        for k, v in saved.items():
            setattr(strength, k, v)
        strength.combo_effects = orig


def cmd_classics() -> int:
    OUT.mkdir(exist_ok=True)
    cases = classics_cases()
    dist: dict[str, int] = {}
    for c in cases:
        dist[c["label"]] = dist.get(c["label"], 0) + 1
    print(f"古籍例盘有明说身强弱的 {len(cases)} 盘：{dist}")
    v2 = _score(cases, strength.assess)
    v1 = _score(cases, _assess_without_combos)
    for name, r in (("v2（含合局项）", v2), ("无合局项", v1)):
        print(f"\n== {name}：一致率 {r['agree']}/{r['n']} = {r['agree'] / r['n']:.1%}")
        print("  混淆（古籍→公式）：", json.dumps(r["matrix"], ensure_ascii=False))
        print("  按标签：", r["byLabel"])
        print("  按合局种类：", r["byCombo"])
    near = [d for d in v2["disagreements"] if strength.WEAK_AT <= d["ratio"] <= strength.STRONG_AT]
    print(f"\nv2 分歧 {len(v2['disagreements'])} 盘：中和带内 {len(near)}，带外 {len(v2['disagreements']) - len(near)}")
    (OUT / "classics.json").write_text(json.dumps({"cases": cases, "v2": v2, "noCombo": v1}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"→ {OUT / 'classics.json'}")
    return 0


def cmd_sample() -> int:
    OUT.mkdir(exist_ok=True)
    samples = build_samples()
    (OUT / "samples.json").write_text(json.dumps(samples, ensure_ascii=False, indent=2), encoding="utf-8")
    dist: dict[str, int] = {}
    for s in samples:
        dist[s["formula"]["verdict"]] = dist.get(s["formula"]["verdict"], 0) + 1
    print(f"{len(samples)} 盘 → {OUT / 'samples.json'}；公式分布 {dist}")
    return 0


def cmd_sheet() -> int:
    samples = json.loads((OUT / "samples.json").read_text(encoding="utf-8"))
    lines = ["# 旺衰判定单",
             "",
             "每盘只给四柱与查表事实，不给任何强弱结论。请逐盘按得令、得地、得势、合局四项说理，",
             "再给出「身旺 / 身弱 / 中和」之一。中和只用于确实难分的盘，不要当作回避。合局一项按地支关系栏自行判断三合三会是否成局、六合是否合化。",
             f"把结论写成 JSON：{{\"S001\": {{\"verdict\": \"身弱\", \"reason\": \"一两句\"}}, ...}}，存 {OUT / 'verdicts.json'}。",
             ""]
    for s in samples:
        p = s["pillars"]
        f = facts(p)
        lines.append(f"## {s['id']}  {p['year']} {p['month']} {p['day']} {p['hour']}")
        lines.append(f"- 日主：{s['dayMaster']}，生于{s['monthBranch']}月")
        cn = {"year": "年", "month": "月", "day": "日", "hour": "时"}
        lines.append(f"- 天干十神：{'，'.join(f'{cn[k]}干{v}' for k, v in f['天干十神'].items())}")
        lines.append(f"- 地支藏干：{'；'.join(f'{cn[k]}支藏{v}' for k, v in f['地支藏干'].items())}")
        lines.append(f"- 地支关系：{'，'.join(f['地支关系'])}")
        lines.append("")
    (OUT / "sheet.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(samples)} 盘 → {OUT / 'sheet.md'}")
    return 0


def cmd_score() -> int:
    samples = {s["id"]: s for s in json.loads((OUT / "samples.json").read_text(encoding="utf-8"))}
    parts = sorted(OUT.glob("verdicts*.json"))
    if not parts:
        print(f"缺 {OUT / 'verdicts*.json'}，先让子代理判定"); return 2
    verdicts: dict = {}
    for part in parts:  # 分批交卷：verdicts.1.json、verdicts.2.json……合并
        verdicts.update(json.loads(part.read_text(encoding="utf-8")))
    agree = 0
    by_dm: dict[str, list[int]] = {}
    by_mb: dict[str, list[int]] = {}
    matrix: dict[str, int] = {}
    disagreements = []
    for sid, v in verdicts.items():
        s = samples.get(sid)
        if not s:
            continue
        r = strength.assess(s["pillars"])  # 按当前公式重算，samples.json 里存的是取样时的结论，权重改过就过时
        s["formula"] = {"verdict": r["verdict"], "ratio": r["ratio"], "note": r["note"], "flags": r["flags"]}
        mine, theirs = r["verdict"], v["verdict"]
        hit = int(mine == theirs)
        agree += hit
        by_dm.setdefault(s["dayMaster"], []).append(hit)
        by_mb.setdefault(s["monthBranch"], []).append(hit)
        matrix[f"{mine}→{theirs}"] = matrix.get(f"{mine}→{theirs}", 0) + 1
        if not hit:
            disagreements.append({"id": sid, "pillars": s["pillars"], "formula": mine,
                                  "ratio": s["formula"]["ratio"], "agent": theirs,
                                  "reason": v.get("reason", "")})
    n = len(verdicts)
    print(f"一致率 {agree}/{n} = {agree / n:.1%}\n")
    print("混淆（公式→子代理）：", json.dumps(matrix, ensure_ascii=False))
    print("\n按日主：", ", ".join(f"{k} {sum(v)}/{len(v)}" for k, v in sorted(by_dm.items())))
    print("按月支：", ", ".join(f"{k} {sum(v)}/{len(v)}" for k, v in sorted(by_mb.items())))
    near = [d for d in disagreements if strength.WEAK_AT <= d["ratio"] <= strength.STRONG_AT]
    print(f"\n分歧 {len(disagreements)} 盘，其中落在中和带内 {len(near)} 盘（阈值问题），带外 {len(disagreements) - len(near)} 盘（权重问题）")
    (OUT / "disagreements.json").write_text(json.dumps(disagreements, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"分歧清单 → {OUT / 'disagreements.json'}")
    return 0


def _agent_cases() -> list[dict]:
    """子代理标准：120 盘样本配合并后的裁定，摊成与 classics_cases 同形的列表。"""
    samples = {s["id"]: s for s in json.loads((OUT / "samples.json").read_text(encoding="utf-8"))}
    verdicts: dict = {}
    for part in sorted(OUT.glob("verdicts*.json")):
        verdicts.update(json.loads(part.read_text(encoding="utf-8")))
    return [{"id": sid, "pillars": samples[sid]["pillars"], "label": v["verdict"], "evidence": [v.get("reason", "")]}
            for sid, v in verdicts.items() if sid in samples]


V3_CONFIGS = [
    ("v2 现行", {}),
    ("冲破合局", {"V3_CHONG_BREAKS_COMBO": True}),
    ("墓库长生作根 0.3", {"V3_KU_SHENG_ROOT": True, "KU_SHENG_ROOT_FACTOR": 0.3}),
    ("墓库长生作根 0.5", {"V3_KU_SHENG_ROOT": True, "KU_SHENG_ROOT_FACTOR": 0.5}),
    ("墓库长生作根 0.8", {"V3_KU_SHENG_ROOT": True, "KU_SHENG_ROOT_FACTOR": 0.8}),
    ("两项 0.5", {"V3_CHONG_BREAKS_COMBO": True, "V3_KU_SHENG_ROOT": True, "KU_SHENG_ROOT_FACTOR": 0.5}),
    # 印重盘徐多论身弱（2026-09-23-6 校准遗留）：试印的生扶折扣
    ("印折扣 0.8", {"YIN_SCALE": 0.8}),
    ("印折扣 0.7", {"YIN_SCALE": 0.7}),
    ("印折扣 0.6", {"YIN_SCALE": 0.6}),
]
V3_REPORT = Path(__file__).resolve().parent.parent / "references" / "校核" / "旺衰_v3报告.md"


def cmd_v3() -> int:
    """v3 两个实验项（冲破合局、墓库长生作根）对两路标准的一致率格子；不改默认值，只出报告。"""
    from datetime import date
    agent, classics = _agent_cases(), classics_cases()
    keys = ("V3_CHONG_BREAKS_COMBO", "V3_KU_SHENG_ROOT", "KU_SHENG_ROOT_FACTOR", "YIN_SCALE")
    saved = {k: getattr(strength, k) for k in keys}
    rows, detail = [], {}
    base_dis: dict[str, set] = {}
    try:
        for name, cfg in V3_CONFIGS:
            for k in keys:
                setattr(strength, k, cfg.get(k, saved[k]))
            a, c = _score(agent, strength.assess), _score(classics, strength.assess)
            hit_a = sum(1 for x in agent if _v3_touched(x["pillars"]))
            hit_c = sum(1 for x in classics if _v3_touched(x["pillars"]))
            rows.append((name, a["agree"], a["n"], c["agree"], c["n"], hit_a, hit_c))
            detail[name] = {"agent": a, "classics": c}
            if not cfg:
                base_dis = {"agent": {d["id"] for d in a["disagreements"]}, "classics": {d["id"] for d in c["disagreements"]}}
    finally:
        for k, v in saved.items():
            setattr(strength, k, v)
    lines = ["# 旺衰 v3 实验报告", "",
             f"生成：{date.today().isoformat()}。scripts/calibrate_strength.py v3。两项实验开关默认关，本表只看开了之后两路标准的一致率怎么动；"
             "子代理标准是 120 盘 Fable 独立判定（阈值 0.48–0.52 由它定），古籍标准是徐评或按语明说身强弱的例盘（徐用\"身旺\"较宽，只作偏差记录）。"
             "\"触及\"是该配置下合局被冲破或加了作根分的盘数。", "",
             "| 配置 | 子代理一致 | 古籍一致 | 触及（子代理/古籍） |", "|---|---|---|---|"]
    for name, aa, an, ca, cn, ha, hc in rows:
        lines.append(f"| {name} | {aa}/{an}（{aa / an:.1%}） | {ca}/{cn}（{ca / cn:.1%}） | {ha}/{hc} |")
    lines += ["", "## 各配置相对 v2 翻转的盘", ""]
    for name, _cfg in V3_CONFIGS[1:]:
        for side in ("agent", "classics"):
            now = {d["id"]: d for d in detail[name][side]["disagreements"]}
            fixed = sorted(base_dis[side] - set(now))
            broke = sorted(set(now) - base_dis[side])
            lines.append(f"- {name}·{'子代理' if side == 'agent' else '古籍'}：改对 {len(fixed)} {fixed}；改错 {len(broke)} {broke}")
    V3_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "v3.json").write_text(json.dumps({"rows": rows, "detail": detail}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(lines[:4 + len(rows) + 2]))
    print(f"→ {V3_REPORT}")
    return 0


def _v3_touched(pillars: dict) -> bool:
    r = strength.assess(pillars)
    return any(n.get("broken") for n in r["combos"]) or any("作根" in c["where"] for c in r["contributions"])


def main(argv: list[str]) -> int:
    cmds = {"sample": cmd_sample, "sheet": cmd_sheet, "score": cmd_score, "classics": cmd_classics, "v3": cmd_v3}
    if len(argv) != 1 or argv[0] not in cmds:
        print(__doc__); return 2
    return cmds[argv[0]]()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
