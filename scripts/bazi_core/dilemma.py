"""两难改写 v1（DESIGN 10 第 3 条、8.2"压力下的选择"）：年表的候选年份 → 两难草稿。

年表只给事实（机制怎么发生、领域赌注是什么）；岁运事件类型表（tables/suiyun_events.json）给机制的形态、领域的赌注、
精选格的两难模板与合成规则。本模块把两者对起来：
- 主机制：候选年份的机制按烈度排（天克地冲、冲日支、冲提纲、岁运并临、伏吟、岁运相冲、冲年支、冲时支、换运、合绊用神、忌神透干、
  刑、害、合日支、合化为用、用神到位），取最烈的一个；"天克地冲年柱""巳刑申（日支）"一类按前缀归到表里的机制名。
- 主领域：按年表每个领域的 weight（强信号 2、弱信号 1）取最大，主机制冲到的宫位天然指向的领域加 2（冲日支先动感情、身心，
  冲提纲先动六亲、事业，冲年支先动六亲、迁徙，冲时支先动创造与传承），同分按第 10 节九领域的顺序；副领域取次大者，
  精选格里配的副领域若当年也动了则优先它。领域互斥是最好的两难（保名誉就失感情）。
- 两难：表里有 (机制, 主领域) 的精选格就用它；没有就按 compose 规则合成：机制的形态加主副领域的赌注。
- 影响谁（第 3 条"标注影响哪些其他角色"）：给了别人的命盘时，按群像快照（ensemble）取那一年从本人出发或指向本人的被引动边。
输出是草稿，由作者挑、模型改写成这个人的话；不产生编号，sources 引年表的 L- 编号（ids 栏已列出）与 D- 基调编号。

命令行（在作者项目根下）：
    python -m bazi_core.dilemma 命盘/沈砚.年表.json [--chart 命盘/沈砚.json --with 命盘/林昭.json ...] [--ages 6 30] > 命盘/沈砚.两难.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import timeline as _tl

SCHEMA = "bazi-dilemma/v1"
_TABLE_PATH = Path(__file__).resolve().parent / "tables" / "suiyun_events.json"
_T = json.loads(_TABLE_PATH.read_text(encoding="utf-8"))
MECH = {m["name"]: m for m in _T["mechanisms"]}
DOMAIN = {d["name"]: d for d in _T["domains"]}
CELLS = {(c["mechanism"], c["domain"]): c for c in _T["cells"]}
PRIORITY = ("天克地冲", "冲日支", "冲提纲", "岁运并临", "伏吟", "岁运相冲", "冲年支", "冲时支", "换运", "合绊用神", "忌神透干",
            "刑", "害", "合日支", "合化为用", "用神到位")


def normalize(mech: str) -> str | None:
    """年表机制名 → 表里的机制名。刑的写法是"巳刑申（日支）"或"辰辰自刑（日支）"；合只认合日支。"""
    for name in PRIORITY:
        if mech.startswith(name):
            return name
    if "刑" in mech:
        return "刑"
    return None


def primary_mechanism(mechs: list[str]) -> tuple[str, str] | None:
    """(表里的机制名, 年表原机制名)，按烈度取最前者。"""
    best = None
    for m in mechs:
        n = normalize(m)
        if n is None:
            continue
        rank = PRIORITY.index(n)
        if best is None or rank < best[0]:
            best = (rank, n, m)
    return None if best is None else (best[1], best[2])


_PALACE_DOMAIN = {"年": ("六亲", "迁徙与归属"), "月": ("六亲", "事业与权力"), "日": ("感情", "身心"), "时": ("创造与传承", "六亲")}
AFFINITY_BONUS = 2  # 等于一条强信号


def affinity(raw_mech: str) -> tuple[str, ...]:
    """主机制天然指向的领域：冲哪个宫位就先动那个宫位的赌注（第 10 节领域表的触发来源）。"""
    if raw_mech.startswith("冲提纲"):
        return _PALACE_DOMAIN["月"]
    if raw_mech.startswith("冲日支") or raw_mech.startswith("合日支"):
        return _PALACE_DOMAIN["日"]
    if raw_mech.startswith("冲年支"):
        return _PALACE_DOMAIN["年"]
    if raw_mech.startswith("冲时支"):
        return _PALACE_DOMAIN["时"]
    for k, doms in _PALACE_DOMAIN.items():
        if (raw_mech.startswith("天克地冲") or raw_mech.startswith("伏吟")) and raw_mech.endswith(f"{k}柱"):
            return doms
        if "刑" in raw_mech or raw_mech.startswith("害"):
            if raw_mech.endswith(f"{k}支）") or raw_mech.endswith(f"{k}支"):
                return doms
    return ()


def rank_domains(domains: list[dict], raw_mech: str | None = None, weights: dict | None = None) -> list[dict]:
    """weights：书的领域配权（编配表，DESIGN-戏剧层 5.3），领域名 → 倍数，没写的算 1。只改挑哪个领域当主领域，不动年表的事实。"""
    order = {d: i for i, d in enumerate(_tl.DOMAINS)}
    aff = affinity(raw_mech) if raw_mech else ()
    weights = weights or {}

    def score(d: dict) -> float:
        w = d.get("weight", 2 if d.get("strong", True) else 1)
        return (w + (AFFINITY_BONUS if d["domain"] in aff else 0)) * weights.get(d["domain"], 1)

    return sorted(domains, key=lambda d: (-score(d), order[d["domain"]]))


def compose(mech: str, primary: str, secondary: str | None) -> tuple[str, list[str]]:
    """没有精选格时按合成规则拼：形态加两头押的赌注类型；两头只写方向，具体押什么由写档案的模型按处境落。"""
    form = MECH[mech]["form"].split("。")[0]
    if secondary:
        sides = [f"保{primary}，把{DOMAIN[secondary]['stake']}押出去", f"保{secondary}，把{DOMAIN[primary]['stake']}押出去"]
    else:
        sides = [f"为{DOMAIN[primary]['stake']}付全部代价", "退一步，保住别的"]
    return f"{form}：{sides[0]}，还是{sides[1]}", sides


FILL = "落词按此人此年手里有的东西（阶段卡第八面），模板只给形态"


def rewrite_year(y: dict, head: str, weights: dict | None = None, avoid: str | None = None) -> dict | None:
    """avoid：这个领域连着做了两个热年的主领域，这一年若还有别的领域在动就让它退到后面（DESIGN-戏剧层 5.3）。"""
    pm = primary_mechanism(y["mechanisms"])
    if pm is None or not y["domains"]:
        return None
    mech, raw = pm
    ranked = rank_domains(y["domains"], raw, weights)
    if avoid and len(ranked) > 1 and ranked[0]["domain"] == avoid:
        ranked = ranked[1:] + ranked[:1]
    primary = ranked[0]["domain"]
    cell = CELLS.get((mech, primary))
    rest = [d["domain"] for d in ranked[1:]]
    secondary = None
    if cell:
        secondary = next((s for s in cell["sub"] if s in rest), None)
    if secondary is None and rest:
        secondary = rest[0]
    ids = [f"{head}-{raw}"] + [f"{head}-域-{primary}"] + ([f"{head}-域-{secondary}"] if secondary else [])
    return {
        "age": y["age"], "year": y.get("year"), "pillar": y["pillar"], "dayun": y.get("dayun"),
        "mechanism": mech, "mechanismRaw": raw, "form": MECH[mech]["form"], "tempo": MECH[mech]["tempo"],
        "otherMechanisms": [m for m in y["mechanisms"] if m != raw],
        "primary": {"domain": primary, "stake": DOMAIN[primary]["stake"], "via": ranked[0]["via"], "events": DOMAIN[primary]["events"]},
        "secondary": None if secondary is None else {"domain": secondary, "stake": DOMAIN[secondary]["stake"],
                                                     "via": next((d["via"] for d in ranked if d["domain"] == secondary), [])},
        "dilemma": f"{cell['shape']}：{cell['sides'][0]}，还是{cell['sides'][1]}" if cell else compose(mech, primary, secondary)[0],
        "shape": cell["shape"] if cell else MECH[mech]["form"].split("。")[0],
        "sides": cell["sides"] if cell else compose(mech, primary, secondary)[1],
        "fill": FILL,
        "template": "精选格" if cell else "按合成规则合成",
        "suggestedSub": cell["sub"] if cell else [],
        "ids": ids,
        "anchors": sorted(set(MECH[mech]["anchors"]) | set(DOMAIN[primary]["anchors"])),
    }


def _affects(chart: dict, others: list[dict], year: int) -> list[dict]:
    from . import ensemble as _en
    snap = _en.snapshot([chart] + others, year)
    me = chart["name"]
    out: dict[str, dict] = {}
    for e in snap["edges"]:
        if me not in (e["from"], e["to"]):
            continue
        who = e["to"] if e["from"] == me else e["from"]
        item = out.setdefault(who, {"who": who, "seenByMe": None, "seesMe": None, "reasons": [], "ids": []})
        if e["from"] == me:
            item["seenByMe"] = e["tenGod"]
        else:
            item["seesMe"] = e["tenGod"]
        for r in e["reasons"]:
            t = f"{e['from']}→{e['to']}：{r['text']}"
            if t not in item["reasons"]:
                item["reasons"].append(t)
        item["ids"] += [i for i in e["ids"] if i not in item["ids"]]
    return list(out.values())


def build(tl: dict, chart: dict | None = None, others: list[dict] | None = None, ages: list[int] | None = None) -> dict:
    by_age = {y["age"]: y for y in tl["years"]}
    picks = ages if ages else tl["candidates"]
    items = []
    for age in picks:
        y = by_age.get(age)
        if y is None:
            continue
        head = f"L-{y['age']}-{y['pillar']}"
        item = rewrite_year(y, head)
        if item is None:
            continue
        stage = next((s for s in tl.get("stages", []) if s["ages"][0] <= age < s["ages"][1]), None)
        if stage:
            item["stageTone"] = stage["tone"]
            item["ids"].append(f"D-{stage['sequence']}-{stage['pillar']}-基调")
        if chart is not None and others and y.get("year") is not None:
            item["affects"] = _affects(chart, others, y["year"])
        items.append(item)
    return {"schema": SCHEMA, "algorithm": "bazi-writing dilemma v1（DESIGN 10 第 3 条；表 suiyun_events.json）",
            "name": tl.get("name"), "compose": _T["compose"], "items": items,
            "note": "草稿。作者挑年份与主副领域，模型改写成这个人的话；sources 引 ids 里的年表编号，本文件不产生编号。"}


def _main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="年表 → 两难草稿（主机制、主副领域、两难模板、影响谁）")
    ap.add_argument("timeline", help="timeline 输出的年表 JSON")
    ap.add_argument("--chart", default=None, help="本人命盘档案（给 --with 时必填）")
    ap.add_argument("--with", dest="others", nargs="*", default=[], help="其他角色的命盘档案，算这一年谁被牵动")
    ap.add_argument("--ages", type=int, nargs="*", default=None, help="只改写这几岁；默认年表的候选年份")
    a = ap.parse_args(argv)
    tl = json.loads(Path(a.timeline).read_text(encoding="utf-8"))
    chart = json.loads(Path(a.chart).read_text(encoding="utf-8")) if a.chart else None
    if a.others and chart is None:
        ap.error("--with 需要同时给 --chart")
    others = [json.loads(Path(p).read_text(encoding="utf-8")) for p in a.others]
    out = build(tl, chart, others, a.ages)
    sys.stdout.buffer.write((json.dumps(out, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
