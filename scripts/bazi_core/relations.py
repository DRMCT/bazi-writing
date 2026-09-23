"""刑冲合害：命局内部四柱之间，以及命局对岁运的柱对柱关系。

表来自 tables/relations.json，由 scripts/build_relations.py 从校核卡 references/校核/刑冲合害.md 的「采用规则」生成，
每条带 source 指向卡号与卡状态。配对表四库交叉全同；三刑方向、三合土局、六合与天干所化按《三命通会》卷二裁。
vendor/yueyuan_relations.py 不再被引用，留作卡上「初稿写法」的对照。
"""

from __future__ import annotations

import json
from pathlib import Path

from .shishen import STEMS, element_of

_TABLE_PATH = Path(__file__).resolve().parent / "tables" / "relations.json"
_T = json.loads(_TABLE_PATH.read_text(encoding="utf-8"))

_PILLAR_KEYS = ("year", "month", "day", "hour")
_CN = {"year": "年", "month": "月", "day": "日", "hour": "时"}


def _both_ways(entries: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for e in entries:
        a, b = e["pair"]
        out[a], out[b] = b, a
    return out


def _pair_attr(entries: list[dict], attr: str) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for e in entries:
        out[e["pair"]] = e[attr]
        out[e["pair"][::-1]] = e[attr]
    return out


STEM_HE = _both_ways(_T["stemHe"])
STEM_HE_ELEMENT = _pair_attr(_T["stemHe"], "element")
STEM_HE_NAME = _pair_attr(_T["stemHe"], "name")
LIU_HE = _both_ways(_T["liuHe"])
LIU_HE_ELEMENT = _pair_attr(_T["liuHe"], "element")
LIU_CHONG = _both_ways(_T["liuChong"])
HAI = _both_ways(_T["liuHai"])
XING: dict[str, tuple[str, ...]] = {}
XING_KIND: dict[str, str] = {}
for _e in _T["sanXing"]["directed"]:
    XING[_e["from"]] = XING.get(_e["from"], ()) + (_e["to"],)
    XING_KIND[_e["from"] + _e["to"]] = _e["kind"]
ZI_XING = tuple(e["branch"] for e in _T["sanXing"]["self"])
SAN_HE = {e["branches"]: e["element"] for e in _T["sanHe"] if len(e["branches"]) == 3}
SI_KU = next((e for e in _T["sanHe"] if len(e["branches"]) == 4), None)
SAN_HUI = {e["branches"]: e["element"] for e in _T["sanHui"]}


def table_sources() -> dict[str, str]:
    """卡号 → 状态，供测试与档案标注。"""
    out = {}
    for key in ("stemHe", "liuHe", "liuChong", "liuHai", "sanHe", "sanHui"):
        for e in _T[key]:
            out[e["source"]] = e["status"]
    for e in _T["sanXing"]["directed"] + _T["sanXing"]["self"]:
        out[e["source"]] = e["status"]
    return out


def stem_relation(a: str, b: str) -> str | None:
    """a 对 b：合 / 克 / 被克 / 同 / 生 / 被生。"""
    if STEM_HE.get(a) == b:
        return "合"
    ea, eb = element_of(STEMS.index(a)), element_of(STEMS.index(b))
    d = (eb - ea) % 5
    return {0: "同", 1: "生", 2: "克", 3: "被克", 4: "被生"}[d]


def xing_direction(a: str, b: str) -> str | None:
    """两支相刑的方向：'寅刑巳'、'子卯互刑'、'辰辰自刑'；不刑为 None。"""
    if a == b:
        return f"{a}{a}自刑" if a in ZI_XING else None
    ab, ba = b in XING.get(a, ()), a in XING.get(b, ())
    if ab and ba:
        return f"{a}{b}互刑"
    if ab:
        return f"{a}刑{b}"
    if ba:
        return f"{b}刑{a}"
    return None


def branch_pair(a: str, b: str) -> list[str]:
    """两地支之间的关系名列表（可多重，如既刑又害）。"""
    out: list[str] = []
    if LIU_HE.get(a) == b:
        out.append("六合")
    if LIU_CHONG.get(a) == b:
        out.append("六冲")
    if b in XING.get(a, ()) or a in XING.get(b, ()):
        out.append("刑")
    if a == b and a in ZI_XING:
        out.append("自刑")
    if HAI.get(a) == b:
        out.append("害")
    return out


def pillar_pair(p1: str, p2: str) -> dict:
    """柱对柱：伏吟、反吟（天克地冲）、天干关系、地支关系。岁运对命局用。"""
    stem_rel = stem_relation(p1[0], p2[0])
    branches = branch_pair(p1[1], p2[1])
    tags: list[str] = []
    if p1 == p2:
        tags.append("伏吟")
    if stem_rel in ("克", "被克") and "六冲" in branches:
        tags.append("天克地冲")
    return {"stem": stem_rel, "branches": branches, "tags": tags}


def natal_relations(pillars: dict) -> dict:
    """命局内部：两两地支关系（带刑的方向与六合所化）、天干五合（带所化）、三合局与三会方（三支齐全）、四库全。"""
    keys = [k for k in _PILLAR_KEYS if pillars.get(k)]
    pairs: list[dict] = []
    for i, ka in enumerate(keys):
        for kb in keys[i + 1:]:
            a, b = pillars[ka], pillars[kb]
            rel = branch_pair(a[1], b[1])
            stem_he = STEM_HE.get(a[0]) == b[0]
            if rel or stem_he:
                item = {
                    "between": [ka, kb],
                    "label": f"{_CN[ka]}{_CN[kb]}",
                    "branches": rel,
                    "stemHe": stem_he,
                    "tianKeDiChong": "六冲" in rel and stem_relation(a[0], b[0]) in ("克", "被克"),
                }
                if stem_he:
                    item["stemHeElement"] = STEM_HE_ELEMENT[a[0] + b[0]]
                if "六合" in rel:
                    item["liuHeElement"] = LIU_HE_ELEMENT[a[1] + b[1]]
                if "刑" in rel or "自刑" in rel:
                    item["xing"] = xing_direction(a[1], b[1])
                pairs.append(item)
    present = {pillars[k][1] for k in keys}
    trios: list[dict] = []
    for ju, wx in SAN_HE.items():
        if all(z in present for z in ju):
            trios.append({"kind": "三合", "branches": ju, "element": wx})
    for fang, wx in SAN_HUI.items():
        if all(z in present for z in fang):
            trios.append({"kind": "三会", "branches": fang, "element": wx})
    if SI_KU and all(z in present for z in SI_KU["branches"]):
        trios.append({"kind": "四库全", "branches": SI_KU["branches"], "element": SI_KU["element"]})
    return {"pairs": pairs, "trios": trios}


def transit_relations(pillars: dict, transit: str) -> dict:
    """岁运柱对命局四柱：逐柱给 pillar_pair，并标出冲提纲、冲日支。"""
    hits = {}
    for k in _PILLAR_KEYS:
        if pillars.get(k):
            hits[k] = pillar_pair(transit, pillars[k])
    flags = []
    if "六冲" in hits.get("month", {}).get("branches", []):
        flags.append("冲提纲")
    if "六冲" in hits.get("day", {}).get("branches", []):
        flags.append("冲日支")
    for k, h in hits.items():
        if "天克地冲" in h["tags"]:
            flags.append(f"天克地冲{_CN[k]}柱")
        if "伏吟" in h["tags"]:
            flags.append(f"伏吟{_CN[k]}柱")
    return {"transit": transit, "byPillar": hits, "flags": flags}
