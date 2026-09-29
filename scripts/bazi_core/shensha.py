"""神煞白名单十五种（DESIGN-命盘层.md 附录 A），查表层。

表来自 tables/shensha.json，由 scripts/build_shensha.py 从校核卡 references/校核/神煞_{组}.md 的「采用规则」生成；
每条带 source 指向卡号。校核依据：《四库版足本三命通会》（华龄出版社，万民英撰、闵兆才编校）校对本，
网络本与《神峰通考》作核对参考。裁决记在卡上，另说进 alternates 字段，运行时不用。

六种查法：
- 日干查地支（天乙贵人、文昌、羊刃、红艳）
- 三合局查地支（桃花、驿马、华盖、将星、亡神、劫煞）：原文以年支为本，日支起查另算并标明
- 月支查干支（天德、月德）：目标是天干或地支，查四柱干支
- 日柱（魁罡、阴差阳错）
- 日柱旬空（空亡）：查年月时三支
- 年支三会查地支（孤辰、寡宿）

歧义登记（已裁，理由在卡上）：天乙贵人只用每干两贵主表，不分阳贵阴贵与昼夜；羊刃只取阳干；
红艳从三命通会（乙午、戊子、壬巳），神峰通考三格作另说；文昌从三命通会「文昌贵」歌诀，通行本文昌作另说；
桃花的「纳音同类」附加条件不入表。
"""

from __future__ import annotations

import json
from pathlib import Path

from .dayun import sexagenary_index
from .shishen import BRANCHES, STEMS

STATUS = "校核定稿"
_TABLE_PATH = Path(__file__).resolve().parent / "tables" / "shensha.json"
_PILLAR_KEYS = ("year", "month", "day", "hour")
_CN = {"year": "年", "month": "月", "day": "日", "hour": "时"}
_TRIOS = ("申子辰", "寅午戌", "巳酉丑", "亥卯未")
_GROUPS = ("亥子丑", "寅卯辰", "巳午未", "申酉戌")


def _load() -> dict[str, dict]:
    data = json.loads(_TABLE_PATH.read_text(encoding="utf-8"))
    return {e["name"]: e for e in data["entries"]}


_ENTRIES = _load()


def entry(name: str) -> dict:
    return _ENTRIES[name]


def table_names() -> list[str]:
    return list(_ENTRIES)


def _values(entry_: dict, key: str) -> list[str]:
    return [v["value"] if isinstance(v, dict) else v for v in entry_["table"].get(key, [])]


def xun_kong(day_pillar: str) -> tuple[str, str]:
    """日柱所在旬的空亡二支：旬首甲子空戌亥，余类推（论空亡「甲子旬中无戌亥」）。"""
    idx = sexagenary_index(day_pillar)
    xun_start = idx - idx % 10
    return BRANCHES[(xun_start + 10) % 12], BRANCHES[(xun_start + 11) % 12]


def _xun_head(day_pillar: str) -> str:
    idx = sexagenary_index(day_pillar)
    xun_start = idx - idx % 10
    return STEMS[0] + BRANCHES[xun_start % 12]


def _positions(pillars: dict, targets: list[str], exclude: str | None = None) -> list[str]:
    return [k for k in _PILLAR_KEYS if pillars.get(k) and k != exclude and pillars[k][1] in targets]


def compute(pillars: dict) -> list[dict]:
    """返回命中的神煞列表：{name, basis, positions, source, status}。同名神煞按年支、日支各查一遍时分两条，basis 注明。"""
    out: list[dict] = []
    day = pillars["day"]
    day_stem, day_branch, year_branch, month_branch = day[0], day[1], pillars["year"][1], pillars["month"][1]

    def add(e: dict, basis: str, positions: list[str]) -> None:
        if positions:
            out.append({"name": e["name"], "basis": basis, "positions": positions,
                        "source": e["source"], "status": STATUS, "cardStatus": e["status"]})

    for e in _ENTRIES.values():
        m = e["method"]
        if m == "日干查地支":
            add(e, f"日干{day_stem}", _positions(pillars, _values(e, day_stem)))
        elif m == "三合局查地支":
            for ref_key, ref in (("year", year_branch), ("day", day_branch)):
                trio = next((t for t in _TRIOS if ref in t), None)
                if trio:
                    note = "" if ref_key == "year" else "（日支起）"
                    add(e, f"{_CN[ref_key]}支{ref}{note}", _positions(pillars, _values(e, trio)))
        elif m == "月支查干支":
            targets = _values(e, month_branch)
            pos = [k for k in _PILLAR_KEYS if pillars.get(k) and (pillars[k][0] in targets or pillars[k][1] in targets)]
            add(e, f"月支{month_branch}", pos)
        elif m == "日柱":
            scope = e.get("scope") or ["day"]
            hits = [k for k in scope if pillars.get(k) and pillars[k] in e["list"]]
            if hits:
                basis = f"日柱{day}" if "day" in hits else f"{_CN[hits[0]]}柱{pillars[hits[0]]}"
                add(e, basis + (f"，{len(hits)}重" if len(hits) > 1 else ""), hits)
        elif m == "日柱旬空":
            head = _xun_head(day)
            k1, k2 = xun_kong(day)
            listed = _values(e, head)
            if listed and set(listed) != {k1, k2}:
                raise ValueError(f"空亡表 {head} 旬与旬空公式不合：{listed} vs {k1}{k2}")
            add(e, f"日柱{day}旬空{k1}{k2}", _positions(pillars, [k1, k2], exclude="day"))
        elif m == "年支三会查地支":
            group = next((g for g in _GROUPS if year_branch in g), None)
            if group:
                add(e, f"年支{year_branch}", _positions(pillars, _values(e, group)))
    return out
