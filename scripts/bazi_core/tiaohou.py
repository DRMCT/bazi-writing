"""调候用神：日主 × 月支（× 出生时刻所在节气段）→ 用神。

表来自 tables/tiaohou.json，由 scripts/build_tiaohou.py 从十卷校核卡的「采用规则」生成；
每条带 source 指向卡号（references/校核/调候_{日主}.md）。校核依据：《穷通宝鉴评注》徐乐吾评注本。

主序可按节气分段（雨水、谷雨、清明后十日、夏至、大暑、秋分、霜降、冬至、半月）。
给出生时刻（UTC）时按段取；架空历无时刻时取中气之后的一段（占月份大半），并标 periodUnresolved。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .almanac import term_time
from .shishen import BRANCHES, HIDDEN_STEMS, STEMS, WUXING, element_of

STATUS = "校核定稿"
_TABLE_PATH = Path(__file__).resolve().parent / "tables" / "tiaohou.json"
_BOUNDARY_LON = {"雨水": 330.0, "清明": 15.0, "谷雨": 30.0, "夏至": 90.0, "大暑": 120.0,
                 "秋分": 180.0, "霜降": 210.0, "冬至": 270.0}


def _load() -> dict[tuple[str, str], dict]:
    data = json.loads(_TABLE_PATH.read_text(encoding="utf-8"))
    return {(e["dayMaster"], e["monthBranch"]): e for e in data["entries"]}


_ENTRIES = _load()


def entry(day_stem: str, month_branch: str) -> dict:
    return _ENTRIES[(day_stem, month_branch)]


def table_size() -> int:
    return len(_ENTRIES)


# ---------------------------------------------------------------- 节气段

def _month_jie(instant_utc: datetime, month_branch: str) -> datetime | None:
    """出生所在月的节（立春、惊蛰……）的时刻。"""
    order = (BRANCHES.index(month_branch) - 2) % 12
    lon = (315.0 + 30.0 * order) % 360.0
    best = None
    for y in (instant_utc.year - 1, instant_utc.year):
        t = term_time(y, lon)
        if t is not None and t <= instant_utc and (best is None or t > best):
            best = t
    return best


def boundary_time(instant_utc: datetime, month_branch: str, boundary: str) -> datetime | None:
    """本月内某分界的时刻：中气/清明按黄经求，半月与清明后十日按节起算。"""
    jie = _month_jie(instant_utc, month_branch)
    if jie is None:
        return None
    if boundary == "半月":
        return jie + timedelta(days=15)
    if boundary == "清明后十日":
        return jie + timedelta(days=10)
    lon = _BOUNDARY_LON[boundary]
    for y in (instant_utc.year - 1, instant_utc.year, instant_utc.year + 1):
        t = term_time(y, lon)
        if t is not None and jie <= t < jie + timedelta(days=32):
            return t
    return None


def _pick_primary(e: dict, instant_utc: datetime | None) -> tuple[dict, bool]:
    segs = e["primary"]
    plain = [p for p in segs if not p.get("period")]
    dated = [p for p in segs if p.get("period")]
    if not dated:
        return plain[0], False
    if instant_utc is not None:
        if instant_utc.tzinfo is None:
            instant_utc = instant_utc.replace(tzinfo=timezone.utc)
        for p in dated:
            b = boundary_time(instant_utc, e["monthBranch"], p["period"]["boundary"])
            if b is None:
                continue
            if (instant_utc < b) == (p["period"]["side"] == "before"):
                return p, False
    # 无时刻或定不出：取中气之后一段；没有就取无段的默认；再没有取第一段
    after = [p for p in dated if p["period"]["side"] == "after"]
    return (after or plain or segs)[0], True


# ---------------------------------------------------------------- 查表

def lookup(day_stem: str, month_branch: str, instant_utc: datetime | None = None) -> dict:
    e = entry(day_stem, month_branch)
    seg, unresolved = _pick_primary(e, instant_utc)
    stems = [s[0] for s in seg["stems"]]           # 每位次取首选
    stem_only = [s for s in stems if s in STEMS]
    return {
        "dayMaster": day_stem,
        "monthBranch": month_branch,
        "stems": stems,
        "slots": seg["stems"],
        "elements": [WUXING[element_of(STEMS.index(s))] for s in stem_only],
        "period": seg.get("period"),
        "periodUnresolved": unresolved,
        "periods": [p["period"]["label"] for p in e["primary"] if p.get("period")],
        "conditional": e["conditional"],
        "alternates": e.get("alternates", []),
        "indispensable": e["indispensable"],
        "downgrade": e["downgrade"],
        "avoid": e["avoid"],
        "avoidExceptions": e.get("avoidExceptions", []),   # 忌句里公式（克用神、合用神、缺用神）推不出的，见 compare_avoid.py
        "status": STATUS,
        "cardStatus": e["status"],
        "source": e["source"],
    }


def present_in_chart(pillars: dict, day_stem: str, month_branch: str,
                     instant_utc: datetime | None = None) -> dict:
    """调候用神是否透干或藏支。只对天干位次判断，十神位次（如「比劫」）不判。"""
    info = lookup(day_stem, month_branch, instant_utc)
    exposed = {p[0] for k, p in pillars.items() if p and k != "day"}
    hidden = set()
    for k, p in pillars.items():
        if p:
            hidden.update(STEMS[h] for h in HIDDEN_STEMS[BRANCHES.index(p[1])])
    stems = [s for s in info["stems"] if s in STEMS]
    info["exposed"] = [s for s in stems if s in exposed]
    info["hidden"] = [s for s in stems if s in hidden and s not in exposed]
    info["missing"] = [s for s in stems if s not in exposed and s not in hidden]
    ind = [s for i in info["indispensable"] for s in i["stems"] if s in STEMS]
    info["indispensableMissing"] = [s for s in ind if s not in exposed and s not in hidden]
    return info
