"""阶段状态卡草稿 v1（DESIGN 10 第 6 条前半、8.3）：年表里每步大运的阶段事实 → 这十年他与画像差在哪。

人物档案的十二段是全生涯的画像（体），阶段状态卡按大运分段写这十年的偏移（用）：性格、价值观与喜好、说话方式、需要的得失、
亲密关系动静、能力与漏洞、关系变化七面（DESIGN 8.3）。事实由 timeline.py 在年表 stages 里算好（D-{步}-{干支}-… 编号），本模块把
阶段状态表（tables/stage_overlay.json）与弧光匹配表的档位行对上编号，出草稿：
- 性格：前半句先给命局透干与月令本气的画像底色（十神性格表旺行，T- 与 H-月支-本气 编号），再给天干十神的性格偏移（示人）加地支十神（底色），
  叠合行说是放大画像还是带来画像里没有的，补调候另加一句；有了底色对照，偏移才不会写成绝对句；
- 价值观与喜好：天干十神这十年把什么当真、喜好偏移，地支十神作底色；
- 说话方式：前半句同样先给透干的画像底色（十神性格表的说话方式），再给天干十神的说话偏移；
- 需要的得失：干支五行各为用喜忌仇闲说用神这十年到位、被牵住还是够不着，合绊用神、合化为用另加，末尾列这一步里的挂钩年份；
  需要什么、以为想要什么是画像的定论，卡里不重抄；
- 亲密关系动静：大运冲合刑害日支，大运十神为亲密关系星（命盘顶层 loverStar，默认男财女官杀，DESIGN 7.3），运柱逢桃花红艳；挑什么样的人是画像的定论；
- 能力与漏洞：档位的外部压力与写作陷阱，日主在运支的十二长生的气力，冲提纲、天克地冲、伏吟；
- 关系变化：给了矩阵时，这十年内与谁同步忌运、一顺一逆（E- 编号），冲年支、冲时支、驿马；都没有时退回这十年最常动的领域与候选年份。
  只写十年一段的底色；某一年谁对谁怎么反应归群像快照（Q-），不在卡里写。
干支一推一压（用喜对忌仇）时需要的得失先给合并的一句（表 roles 的混行）。女命草稿把"他"换成"她"。
另列这十年最常动的领域、窗内候选年份（L- 编号，连该年领域编号一起）、该段全部事实编号 allIds（写卡时不限于各面已用的）、
hooks（各面的挂钩年份：这一步大运里与该面直接相关的流年与 L- 编号，不限候选年份，把偏移落到具体一年用）。草稿不产生编号，人物档案的阶段状态段引 ids 里的 D-、L-、E- 编号。

命令行（在作者项目根下）：
    python -m bazi_core.stagecard 命盘/林昭.年表.json --chart 命盘/林昭.json [--matrix 命盘/矩阵.json] [--window 24 46] > 命盘/林昭.阶段.json
--window 是故事覆盖的岁数段，只出与它相交的大运；不给就出年表里的全部大运。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from . import arc as arc_mod
from . import intimacy as intimacy_mod

SCHEMA = "bazi-stagecard/v1"
ASPECTS = ("性格", "价值观与喜好", "说话方式", "需要的得失", "亲密关系动静", "能力与漏洞", "关系变化")
_TABLES = Path(__file__).resolve().parent / "tables"
_TABLE_PATH = _TABLES / "stage_overlay.json"
_T = json.loads(_TABLE_PATH.read_text(encoding="utf-8"))
_SEC = {s["key"]: {r[next(iter(r))]: r for r in s["rows"]} for s in _T["sections"]}
DECADE, OVERLAY, ROLES, PALACE, CHANGSHENG = (_SEC[k] for k in ("decade", "overlay", "roles", "palace", "changsheng"))
# 十神性格表的旺行：透干即旺，作性格与说话方式两面的画像底色
_SS = {(r["tenGod"], r["state"]): r for r in json.loads((_TABLES / "shishen_traits.json").read_text(encoding="utf-8"))["rows"]}
_ROLE_CN = {"用": "用神", "喜": "喜神", "忌": "忌神", "仇": "仇神", "闲": "闲神"}


def table() -> dict:
    return _T


def _palace_row(mech: str) -> dict | None:
    """年表机制名 → 表里的行：刑日支写作"卯刑酉（日支）"一类，天克地冲与伏吟带柱名。"""
    if mech in PALACE:
        return PALACE[mech]
    if mech.startswith("天克地冲"):
        return PALACE["天克地冲"]
    if mech.startswith("伏吟"):
        return PALACE["伏吟"]
    if "刑" in mech and mech.endswith("日支）"):
        return PALACE["刑日支"]
    return None


_HOOKS = {"亲密关系动静": ("冲日支", "合日支", "害日支", "天克地冲日柱", "伏吟日柱"), "需要的得失": ("用神到位", "合绊用神", "合化为用", "忌神透干"),
          "关系变化": ("冲年支", "冲时支", "天克地冲年柱", "天克地冲时柱", "合年支", "合时支"),
          "能力与漏洞": ("冲提纲", "天克地冲月柱", "伏吟月柱", "岁运并临", "岁运相冲", "换运")}


def _HOOK_ASPECT(mech: str) -> str | None:
    for asp, names in _HOOKS.items():
        if mech in names:
            return asp
    if "刑" in mech and mech.endswith("日支）"):
        return "亲密关系动静"
    return None


def _natal_stems(chart: dict) -> list[tuple[str, str, str]]:
    """命局透干（月干、年干、时干）与月令本气的十神及其编号：表现层与说话方式的画像底色。
    月令本气未透也算（格局多从它取，画像的表现层常写它），排在月干之后；命盘没带 features 索引时现算。"""
    feats = chart.get("features")
    if feats is None:
        from . import chart as chart_mod
        feats = chart_mod.features(chart)
    ids = [f["id"] for f in feats if f["id"].startswith(("T-", "H-月支-本气-"))]
    out = []
    for pos in ("月干", "月令", "年干", "时干"):
        for i in ids:
            parts = i.split("-")
            hit = (pos == "月令" and len(parts) == 4 and parts[1] == "月支") or (pos != "月令" and len(parts) == 3 and parts[1] == pos)
            if hit and (parts[-1], "旺") in _SS and parts[-1] not in [g for _, g, _ in out]:
                out.append((pos, parts[-1], i))
    return out


def _band_row(band: str) -> dict:
    return next(r for r in arc_mod._TONE_ROWS if r["band"] == band)


def _edges_in(matrix: dict | None, name: str, years: tuple[int, int] | None) -> list[dict]:
    """矩阵里与本人相连、且年份段与这步大运相交的同步忌运与顺逆边。"""
    if not matrix or years is None or years[0] is None:
        return []
    a, b = years
    out = []
    for e in matrix.get("edges", []):
        if name not in (e["from"], e["to"]):
            continue
        for f in e.get("features", []):
            parts = f["id"].split("-")
            if len(parts) < 6 or parts[3] not in ("同步忌运", "顺逆"):
                continue
            lo, hi = int(parts[4]), int(parts[5])
            if hi >= a and lo < b:
                out.append({"id": f["id"], "text": f["text"], "from": e["from"], "to": e["to"], "kind": parts[3], "years": [lo, hi]})
    return out


def rewrite_stage(st: dict, chart: dict, tl: dict, matrix: dict | None, step: dict) -> dict:
    head = f"D-{st['sequence']}-{st['pillar']}"
    gz = st["pillar"]
    sg, bg = st["tenGods"]["stem"], st["tenGods"]["branch"]
    rs, rb = st["roles"]["stem"][0], st["roles"]["branch"][0]  # 闲（偏喜）一类只取首字
    aspects: dict[str, dict] = {a: {"draft": [], "ids": []} for a in ASPECTS}

    def put(aspect: str, text: str, *ids: str) -> None:
        d = aspects[aspect]
        if text and text not in d["draft"]:
            d["draft"].append(text)
        d["ids"] += [i for i in ids if i not in d["ids"]]

    # 性格与说话方式先给画像底色（命局透干，十神性格表旺行），偏移接在后面，别写成绝对句
    natal = _natal_stems(chart)
    if natal:
        put("性格", "画像底色（透干与月令）：" + "、".join(f"{pos}{tg}（{'、'.join(_SS[(tg, '旺')]['tendencies'])}）" for pos, tg, _ in natal), *[i for *_, i in natal])
        put("说话方式", "画像底色（透干与月令）：" + "、".join(f"{pos}{tg}（{_SS[(tg, '旺')]['speech']}）" for pos, tg, _ in natal), *[i for *_, i in natal])
    # 性格、价值观与喜好、说话方式：天干示人，地支底色，叠合说放大还是新来
    put("性格", f"示人的偏移（{sg}）：{DECADE[sg]['shift']}", f"{head}-干-{sg}", f"{head}-{st['overlay'][sg]}-{sg}")
    put("性格", f"叠合：{OVERLAY[st['overlay'][sg]]['meaning']}", f"{head}-{st['overlay'][sg]}-{sg}")
    if bg != sg:
        put("性格", f"底色（{bg}）：{DECADE[bg]['shift']}", f"{head}-支-{bg}", f"{head}-{st['overlay'][bg]}-{bg}")
    put("价值观与喜好", f"把什么当真（{sg}）：{DECADE[sg]['values']}；喜好：{DECADE[sg]['likes']}", f"{head}-干-{sg}")
    if bg != sg:
        put("价值观与喜好", f"底色（{bg}）：{DECADE[bg]['values']}", f"{head}-支-{bg}")
    put("说话方式", f"{sg}临运：{DECADE[sg]['speech']}", f"{head}-干-{sg}")
    # 需要的得失：干支各为什么，用神这十年到位、被牵住还是够不着
    sign = {"用": 1, "喜": 1, "忌": -1, "仇": -1, "闲": 0}
    if sign[rs] * sign[rb] < 0:  # 一推一压：先给合并的一句，再给各自的
        put("需要的得失", f"天干{gz[0]}为{_ROLE_CN[rs]}而地支{gz[1]}为{_ROLE_CN[rb]}：{ROLES['混']['need']}", f"{head}-干-{rs}", f"{head}-支-{rb}")
    put("需要的得失", f"天干{gz[0]}为{_ROLE_CN[rs]}：{ROLES[rs]['need']}", f"{head}-干-{rs}")
    if rb != rs:
        put("需要的得失", f"地支{gz[1]}为{_ROLE_CN[rb]}：{ROLES[rb]['need']}", f"{head}-支-{rb}")
    # 冲合宫位按表里的落点分派
    for m in st["mechanisms"]:
        row = _palace_row(m)
        if row is None:
            continue
        put(row["aspect"], f"{m}：{row['shift']}", f"{head}-{m}")
    # 亲密关系星与桃花
    lover = intimacy_mod.lover_gods(chart)
    for g, pos in ((sg, "干"), (bg, "支")):
        if g in lover:
            put("亲密关系动静", f"大运带亲密关系星{g}十年：感情的事在这一段浮上来，{DECADE[g]['values']}", f"{head}-{pos}-{g}")
    for n in st["shensha"]:
        if n in ("桃花", "红艳"):
            put("亲密关系动静", f"运柱逢{n}：这十年有一段不该有的感情，或人缘里带着情", f"{head}-煞-{n}")
        elif n == "华盖":
            put("能力与漏洞", "运柱逢华盖：这十年孤，肯独处，宜学问艺术，不宜热闹", f"{head}-煞-{n}")
        elif n == "驿马":
            put("关系变化", "运柱逢驿马：这十年动，迁徙、远行、换地方", f"{head}-煞-{n}")
        elif n in ("将星", "天乙贵人", "文昌", "羊刃"):
            put("能力与漏洞", f"运柱逢{n}：" + {"将星": "这十年有权可用，人肯听他", "天乙贵人": "这十年有人帮，难处有人替他解",
                                              "文昌": "这十年学得进、写得出", "羊刃": "这十年手狠，能成事也能伤人"}[n], f"{head}-煞-{n}")
    # 能力与漏洞：档位与长生
    band = _band_row(st["band"])
    put("能力与漏洞", f"档位{st['band']}：{band['meaning']}；陷阱：{band['pitfall']}", f"{head}-档-{st['band']}", f"{head}-基调")
    cs = CHANGSHENG[st["changsheng"]]
    put("能力与漏洞", f"气力（{st['changsheng']}）：{cs['energy']}；{cs['pitfall']}", f"{head}-长生-{st['changsheng']}")
    # 关系变化：矩阵边
    years = (step.get("startYear"), step.get("endYear"))
    edges = _edges_in(matrix, chart.get("name") or tl.get("name"), years)
    for e in edges:
        put("关系变化", e["text"], e["id"])
    # 领域与候选年份（候选年份的编号连领域一起列，写卡时可引）
    by_age = {y["age"]: y for y in tl["years"]}
    cands = [{"age": a, "year": by_age[a].get("year"), "mechanisms": by_age[a]["mechanisms"],
              "domains": [d["domain"] for d in by_age[a]["domains"]],
              "ids": [f"L-{a}-{by_age[a]['pillar']}"] + [f"L-{a}-{by_age[a]['pillar']}-{m}" for m in by_age[a]["mechanisms"]]
              + [f"L-{a}-{by_age[a]['pillar']}-域-{d['domain']}" for d in by_age[a]["domains"]]}
             for a in st["candidates"] if a in by_age]
    dom_ids = [f"{head}-域-{d['domain']}" for d in st["domains"]]
    # 关系变化没有冲年支、冲时支、驿马、矩阵边时，退回这十年最常动的领域与候选年份，不留空
    if not aspects["关系变化"]["draft"] and (st["domains"] or cands):
        text = "无宫位冲合与关系边；这十年最常动的领域是" + "、".join(d["domain"] for d in st["domains"])
        if cands:
            text += "，候选年份 " + "、".join(f"{c['age']}岁（{'、'.join(c['mechanisms'][:2])}）" for c in cands) + "，关系的变化从这几年里挑"
        put("关系变化", text, *dom_ids, *[c["ids"][0] for c in cands])
    # 该段全部事实编号，写卡时不限于各面已用的
    all_ids = [f["id"] for f in tl["features"] if f["id"].startswith(head + "-")]
    # 各面的挂钩年份：窗内这一步大运里与该面直接相关的流年（不限候选年份），写卡时把偏移落到具体一年用
    lo, hi = st["ages"]
    in_stage = [y for y in tl["years"] if lo <= y["age"] < hi]
    hooks: dict[str, list[dict]] = {}
    for y in in_stage:
        yh = f"L-{y['age']}-{y['pillar']}"
        for m in y["mechanisms"]:
            asp = _HOOK_ASPECT(m)
            if asp:
                hooks.setdefault(asp, []).append({"age": y["age"], "mechanism": m, "id": f"{yh}-{m}"})
        for n in y["shensha"]:
            if n in ("桃花", "红艳"):
                hooks.setdefault("亲密关系动静", []).append({"age": y["age"], "mechanism": f"逢{n}", "id": f"{yh}-域-感情" if any(d["domain"] == "感情" for d in y["domains"]) else yh})
            elif n == "驿马":
                hooks.setdefault("关系变化", []).append({"age": y["age"], "mechanism": "逢驿马", "id": f"{yh}-域-迁徙与归属" if any(d["domain"] == "迁徙与归属" for d in y["domains"]) else yh})
    # 需要的得失落到年份：这一步里合绊用神、合化为用的流年（用神到位与忌神透干年年都有，只留在 hooks 里），免得每步忌运都抄同一句
    strong = [h for h in hooks.get("需要的得失", []) if h["mechanism"] in ("合绊用神", "合化为用")]
    if strong:
        put("需要的得失", "落到年份：" + "、".join(f"{h['age']}岁{h['mechanism']}" for h in strong), *[h["id"] for h in strong])
    keynote = (f"{st['ages'][0]}至{st['ages'][1]}岁，{gz}运，{st['band']}（顺逆分 {st['score']}）。"
               f"天干{sg}为{_ROLE_CN[rs]}示人，地支{bg}为{_ROLE_CN[rb]}坐底；日主在此{st['changsheng']}"
               + (f"；与命局{'、'.join(st['mechanisms'])}" if st["mechanisms"] else "")
               + (f"；最常动{'、'.join(d['domain'] for d in st['domains'])}" if st["domains"] else "") + "。")
    she = (chart.get("gender") == "female")
    for a in aspects.values():
        a["draft"] = "；".join(a["draft"]) if a["draft"] else None
        if she and a["draft"]:
            a["draft"] = re.sub(r"(?<!其)他", "她", a["draft"])
    return {"stage": head, "sequence": st["sequence"], "pillar": gz, "ages": st["ages"], "years": [years[0], years[1]] if years[0] else None,
            "tone": st["tone"], "band": st["band"], "score": st["score"], "tenGods": st["tenGods"], "roles": st["roles"],
            "changsheng": st["changsheng"], "overlay": st["overlay"], "mechanisms": st["mechanisms"], "shensha": st["shensha"],
            "keynote": keynote, "keynoteIds": [f"{head}-基调", f"{head}-档-{st['band']}", f"{head}-干-{sg}", f"{head}-支-{bg}"],
            "aspects": aspects, "domains": [{**d, "id": i} for d, i in zip(st["domains"], dom_ids)], "candidates": cands,
            "edges": edges, "allIds": all_ids, "hooks": hooks}


def build(tl: dict, chart: dict, matrix: dict | None = None, window: tuple[int, int] | None = None) -> dict:
    steps = {s["sequence"]: s for s in chart["dayun"]["steps"]}
    a, b = window if window else (tl["window"][0], tl["window"][1])
    items = []
    for st in tl["stages"]:
        if "tenGods" not in st:
            raise ValueError("年表没有阶段事实，用当前版本的 timeline 重新生成")
        lo, hi = st["ages"]
        if hi <= a or lo > b:
            continue
        item = rewrite_stage(st, chart, tl, matrix, steps[st["sequence"]])
        item["partial"] = lo < a or hi > b + 1
        items.append(item)
    return {"schema": SCHEMA, "algorithm": "bazi-writing stagecard v1（DESIGN 10 第 6 条前半；表 stage_overlay.json）",
            "name": tl.get("name"), "window": [a, b], "aspects": list(ASPECTS), "stages": items,
            "note": "草稿。每步大运七面各一到两条，写这十年与画像的差，不重抄画像：性格与说话方式先说画像底色再说偏移，"
                    "需要的得失只写用神的到位与牵绊，亲密关系动静只写配偶宫的动静，关系变化只写十年一段的底色；"
                    "模型改写成这个人的话，sources 引各面 ids 里的 D-、L-、E-、T- 编号，本文件不产生编号。"}


def _main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="年表 → 阶段状态卡草稿（每步大运七面的偏移）")
    ap.add_argument("timeline", help="timeline 输出的年表 JSON（含阶段事实）")
    ap.add_argument("--chart", required=True, help="本人命盘档案")
    ap.add_argument("--matrix", default=None, help="多人矩阵，列这十年内的同步忌运与顺逆边")
    ap.add_argument("--window", type=int, nargs=2, default=None, metavar=("起", "止"), help="故事覆盖的岁数段；不给出全部大运")
    a = ap.parse_args(argv)
    tl = json.loads(Path(a.timeline).read_text(encoding="utf-8"))
    chart = json.loads(Path(a.chart).read_text(encoding="utf-8"))
    matrix = json.loads(Path(a.matrix).read_text(encoding="utf-8")) if a.matrix else None
    out = build(tl, chart, matrix, tuple(a.window) if a.window else None)
    sys.stdout.buffer.write((json.dumps(out, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
