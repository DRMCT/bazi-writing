"""默认下场与前史（DESIGN-戏剧层 6）：盘在书里出的主要是书外的时间。

- 默认下场：每个主要人物一条没人插手时的年表。从故事窗起点到窗后 horizon 年，年表的候选年份（timeline._is_candidate）各给一句人话候选：
  主机制与它的形态、主领域的赌注（两难改写 dilemma.rewrite_year 与岁运事件类型表），这一年对这个人偏顺还是偏逆；events 是这个领域常落成的几样事。
  带可选的透法（记得、梦、传闻、卦、旁人判断），按主领域排先后，先后是写作上的建议，不是命理。
  保质期：原本是按他当时那步大运写的，换运那年人变了，原本从那里不准；每人给 coversTo 与换运的来由。
  书一级的保质期（透给读者的原本覆盖到哪一年、过期以后谁接班）要看编配挑了透哪几条，由推演（ensemble_run）按编配算。
- 前史：窗前的候选年份单列（出生到窗起前一年）。六到十二岁的标 nails：谎言候选表的钉法年龄，钉下假话的候选。
  追上来的时候只看盘上的两种机制（pastYears）：窗里冲年支（岁运事件类型表：过去追上来，家里的旧事、身份来历被翻出）、伏吟（旧事重演）。
  哪一条旧账追上来按领域对：那一年动的领域里有这条前史的主领域，就记进它的 catchesUp。对不上领域的年份仍在 pastYears，哪条旧账由事件链挑。
- 上一代（elders）：只出前史，从他出生到窗起前一年；同一家族（families）的晚辈冲年支的年份（年柱是祖上宫）记进他每条前史的 catchesUp，
  不对领域。没给家族就对所有人看。

编号：DF-{名}-{年}（默认下场）、PH-{名}-{年}（前史）；每条另带年表的 L- 编号。推演 idPool 收这两种。
命令行（在作者项目根下）：
    python -m bazi_core.fate 命盘/甲.json 命盘/乙.json --window 2003 2023 [--horizon 10] [--elders 命盘/甲父.json] > 命盘/群像/默认下场.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import dilemma as _dl
from . import lies as _lies
from . import matrix as _mx
from . import timeline as _tl
from . import yongshen as yongshen_mod

SCHEMA = "bazi-fate/v1"
REVEALS = ("记得", "梦", "传闻", "卦", "旁人判断")
# 主领域 → 先挑的两种透法（写作建议：感情与是非靠嘴传，身心与迁徙靠卦，真相靠梦与记得，家事与前程靠旁人的判断）
_REVEAL_FIRST = {
    "感情": ("传闻", "旁人判断"), "六亲": ("旁人判断", "记得"), "财富": ("旁人判断", "传闻"),
    "事业与权力": ("旁人判断", "卦"), "身心": ("卦", "梦"), "名誉与是非": ("传闻", "记得"),
    "学识与真相": ("梦", "记得"), "迁徙与归属": ("卦", "传闻"), "创造与传承": ("旁人判断", "记得"),
}
CATCH_MECH = ("冲年支", "伏吟")  # 过去追上来（冲年支）、旧事重演（伏吟）
DEFAULT_HORIZON = 10


def reveals_for(domain: str | None) -> list[str]:
    first = _REVEAL_FIRST.get(domain or "", ())
    return list(first) + [r for r in REVEALS if r not in first]


def _ys(chart: dict) -> dict:
    return chart.get("yongshen") or yongshen_mod.determine(chart["fourPillars"])


def _year(chart: dict, age: int, year: int) -> dict:
    y = _tl.year_facts(chart, age, _ys(chart), chart["dayun"]["steps"])
    y["year"] = year
    return y


def _item(chart: dict, age: int, year: int) -> tuple[dict, dict] | None:
    """候选年份 → (两难草稿, 年表事实)；不是候选年份或没有领域在动的返回 None。"""
    y = _year(chart, age, year)
    if not _tl._is_candidate(y):
        return None
    item = _dl.rewrite_year(y, f"L-{age}-{y['pillar']}")
    if item is None:
        return None
    return item, y


def _text(item: dict, y: dict, name: str, year: int, age: int, lead: str) -> str:
    shape = _dl.MECH[item["mechanism"]]["form"].split("。")[0]
    tone = "偏顺" if y["score"] > 0 else "偏逆" if y["score"] < 0 else "不顺不逆"
    sec = f"，连带{item['secondary']['domain']}" if item.get("secondary") else ""
    return f"{year}年{age}岁，{lead}{item['mechanismRaw']}，{shape}；押的是{item['primary']['stake']}{sec}；这一年对{name}{tone}"


def _step_of(chart: dict, age: int) -> dict | None:
    return next((s for s in chart["dayun"]["steps"] if s["startAge"] <= age < s["endAge"]), None)


def course(chart: dict, window: tuple[int, int], horizon: int = DEFAULT_HORIZON) -> dict:
    """一个人的默认下场：窗起到窗后 horizon 年的候选年份，加保质期。"""
    name = chart["name"]
    by = _mx._anchor(chart)
    a, b = window
    end = b + horizon
    entries = []
    for year in range(max(a, by), end + 1):
        age = year - by
        got = _item(chart, age, year)
        if got is None:
            continue
        item, y = got
        dom = item["primary"]["domain"]
        entries.append({"id": f"DF-{name}-{year}", "who": name, "year": year, "age": age, "pillar": y["pillar"], "inWindow": year <= b,
                        "mechanism": item["mechanismRaw"], "domain": dom,
                        "secondary": (item.get("secondary") or {}).get("domain"), "score": y["score"],
                        "text": _text(item, y, name, year, age, "没人插手的话："), "events": item["primary"]["events"],
                        "reveal": reveals_for(dom), "ids": item["ids"]})
    start_age = max(a, by) - by
    step = _step_of(chart, start_age)
    turns = [by + s["startAge"] for s in chart["dayun"]["steps"] if s["sequence"] > 1 and max(a, by) < by + s["startAge"] <= end]
    if step and by + step["endAge"] - 1 < end:
        nxt = next((s for s in chart["dayun"]["steps"] if s["sequence"] == step["sequence"] + 1), None)
        covers = by + step["endAge"] - 1
        why = f"{covers + 1}年换运入{nxt['pillar'] if nxt else '下一步'}，人变了，原本从这一年起不准"
    else:
        covers = end
        why = "这一步大运一直走到默认下场的末年"
    return {"who": name, "entries": entries,
            "shelfLife": {"coversTo": covers, "why": why, "turns": turns,
                          "ids": [f"D-{step['sequence']}-{step['pillar']}-基调"] if step else []}}


def past_years(chart: dict, window: tuple[int, int]) -> list[dict]:
    """窗里这个人哪几年旧账容易追上来：冲年支（过去追上来）、伏吟（旧事重演）。domains 是那一年动的领域，拿来对哪一条前史。"""
    by = _mx._anchor(chart)
    a, b = window
    out = []
    for year in range(max(a, by), b + 1):
        age = year - by
        y = _year(chart, age, year)
        hits = [m for m in y["mechanisms"] if m.startswith(CATCH_MECH)]
        if hits:
            out.append({"year": year, "who": chart["name"], "mechanisms": hits, "domains": [d["domain"] for d in y["domains"]],
                        "ids": [f"L-{age}-{y['pillar']}-{m}" for m in hits]})
    return out


def prehistory(chart: dict, window: tuple[int, int], elder: bool = False, heirs: list[dict] | None = None) -> list[dict]:
    """窗前的候选年份。heirs：上一代的同族晚辈（elder 为真时用）。"""
    name = chart["name"]
    by = _mx._anchor(chart)
    a = window[0]
    if elder:
        pys = [py for h in heirs or [] for py in past_years(h, window) if any(m.startswith("冲年支") for m in py["mechanisms"])]
    else:
        pys = past_years(chart, window)
    out = []
    for year in range(by, a):
        age = year - by
        got = _item(chart, age, year)
        if got is None:
            continue
        item, y = got
        dom = item["primary"]["domain"]
        lead = "上一代的旧账：" if elder else ""
        entry = {"id": f"PH-{name}-{year}", "who": name, "year": year, "age": age, "pillar": y["pillar"], "elder": elder,
                 "mechanism": item["mechanismRaw"], "domain": dom, "text": _text(item, y, name, year, age, lead),
                 "nails": (not elder) and age in _lies.CHILD_AGES, "ids": item["ids"]}
        catches = [py for py in pys if elder or dom in py["domains"]]
        entry["catchesUp"] = [{"year": py["year"], "who": py["who"], "mechanisms": py["mechanisms"], "ids": py["ids"]}
                              for py in sorted(catches, key=lambda c: (c["year"], c["who"]))]
        out.append(entry)
    return out


def build(charts: list[dict], window: tuple[int, int], horizon: int = DEFAULT_HORIZON, elders: list[dict] | None = None,
          families: list[list[str]] | None = None, skip: set[str] | None = None) -> dict:
    """skip：不出默认下场与前史的人（编配里背景的人）。"""
    skip = skip or set()
    elders = elders or []
    for c in charts + elders:
        if _mx._anchor(c) is None:
            raise ValueError(f"{c.get('name')} 没有纪年锚（现实历出生年或架空历 --epoch），不能按年对齐")
    people = []
    feats = []
    for c in charts:
        if c["name"] in skip:
            continue
        co = course(c, window, horizon)
        co["prehistory"] = prehistory(c, window)
        co["pastYears"] = past_years(c, window)
        people.append(co)
    by_name = {c["name"]: c for c in charts}
    old = []
    for e in elders:
        fam = next((f for f in families or [] if e["name"] in f), None)
        heirs = [by_name[n] for n in (fam if fam is not None else by_name) if n in by_name and n != e["name"]]
        old.append({"who": e["name"], "heirs": [h["name"] for h in heirs], "prehistory": prehistory(e, window, elder=True, heirs=heirs)})
    for p in people:
        for x in p["entries"]:
            feats.append({"id": x["id"], "text": f"默认下场 {x['who']}：{x['text']}"})
        for x in p["prehistory"]:
            feats.append({"id": x["id"], "text": f"前史 {x['who']}：{x['text']}" + ("（六到十二岁，钉下假话的候选）" if x["nails"] else "")})
    for p in old:
        for x in p["prehistory"]:
            feats.append({"id": x["id"], "text": f"前史 {x['who']}：{x['text']}"})
    return {"schema": SCHEMA, "window": list(window), "horizon": horizon, "people": people, "elders": old, "features": feats,
            "reveals": list(REVEALS),
            "note": "候选，不是结论。编配的默认下场一节挑透哪几条、第几段透、哪几条照样应验、哪几条改；前史一节挑钉下心结的那一年与追上来的旧账。"}


def _main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="几张命盘 → 默认下场年表与前史")
    ap.add_argument("charts", nargs="+")
    ap.add_argument("--window", type=int, nargs=2, required=True, metavar=("起", "止"), help="故事纪年段")
    ap.add_argument("--horizon", type=int, default=DEFAULT_HORIZON, help="默认下场延到窗后几年，默认 10")
    ap.add_argument("--elders", nargs="*", default=[], help="上一代的命盘，只出前史")
    a = ap.parse_args(argv)
    charts = [json.loads(Path(p).read_text(encoding="utf-8")) for p in a.charts]
    elders = [json.loads(Path(p).read_text(encoding="utf-8")) for p in a.elders]
    out = build(charts, (a.window[0], a.window[1]), a.horizon, elders)
    sys.stdout.buffer.write((json.dumps(out, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
