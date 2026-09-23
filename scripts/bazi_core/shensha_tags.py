"""神煞叙事标签：查表层。

表在 tables/shensha_tags.json：每个白名单神煞一条核心用法，加若干位置变体，每个变体带 when 条件、叙事标签 tag、
古籍判词 classic（逐字取自校核卡的"位置变体"栏）与出处 source。tag 是自起草的叙事翻译（DESIGN 7.1：叙事映射部分自起草）。
for_chart 按 shensha.compute 的落柱结果逐条求值 when，命中的变体带 id 返回，供人物档案"特色标签"取材并作溯源编号。

when 条件（见表内 conditionVocabulary）：pillar 落柱；stage 日干在该支的十二宫（生旺 / 死绝）；with 同柱另见的神煞；
empty 该柱旬空；clash 该柱地支与他支六冲；god 该柱天干或支本气的十神；gender 命主性别；count 落柱数下限。
一个变体可能在多柱命中，每柱各出一条。
"""

from __future__ import annotations

import json
from pathlib import Path

from . import changsheng as _cs
from . import relations as _R
from . import shensha as _ss
from .shishen import BRANCHES, HIDDEN_STEMS, STEMS, ten_god

_TABLE_PATH = Path(__file__).resolve().parent / "tables" / "shensha_tags.json"
_T = json.loads(_TABLE_PATH.read_text(encoding="utf-8"))
_BY_NAME = {e["shensha"]: e for e in _T["entries"]}
_PILLARS = ("year", "month", "day", "hour")
_CN = {"year": "年", "month": "月", "day": "日", "hour": "时"}
_SHENG_WANG = frozenset({"长生", "冠带", "临官", "帝旺"})
_SI_JUE = frozenset({"死", "墓", "绝"})


def entries() -> list[dict]:
    return _T["entries"]


def core(shensha_name: str) -> str | None:
    e = _BY_NAME.get(shensha_name)
    return e["core"] if e else None


def _facts(pillars: dict, hits: list[dict]) -> dict:
    """求值用事实：每柱落了哪些神煞、旬空、六冲、十神、十二宫。"""
    keys = [k for k in _PILLARS if pillars.get(k)]
    ds = STEMS.index(pillars["day"][0])
    at: dict[str, set[str]] = {k: set() for k in keys}
    for h in hits:
        for p in h["positions"]:
            if p in at:
                at[p].add(h["name"])
    empty = {k: ("空亡" in at[k]) for k in keys}
    nat = _R.natal_relations(pillars)
    clash = {k: False for k in keys}
    for p in nat["pairs"]:
        if "六冲" in p["branches"]:
            for k in p["between"]:
                clash[k] = True
    gods = {}
    for k in keys:
        s = STEMS.index(pillars[k][0])
        b = BRANCHES.index(pillars[k][1])
        g = set()
        if k != "day":
            g.add(ten_god(ds, s))
        g.add(ten_god(ds, HIDDEN_STEMS[b][0]))
        gods[k] = g
    stage = {k: _cs.stage(pillars["day"][0], pillars[k][1]) for k in keys}
    return {"at": at, "empty": empty, "clash": clash, "gods": gods, "stage": stage, "keys": keys}


def _match(when: dict, name: str, pillar: str, f: dict, gender: str | None, count: int) -> bool:
    if when.get("unlisted"):
        return False
    if "pillar" in when and pillar not in when["pillar"]:
        return False
    if "stage" in when:
        st = f["stage"][pillar]
        want = _SHENG_WANG if when["stage"] == "生旺" else _SI_JUE if when["stage"] == "死绝" else None
        if want is None or st not in want:
            return False
    if "with" in when and not all(w in f["at"][pillar] for w in when["with"]):
        return False
    if when.get("empty") and not f["empty"][pillar]:
        return False
    if when.get("clash") and not f["clash"][pillar]:
        return False
    if "god" in when and not (set(when["god"]) & f["gods"][pillar]):
        return False
    if "gender" in when and gender != when["gender"]:
        return False
    if "count" in when and count < when["count"]:
        return False
    return True


def for_chart(pillars: dict, gender: str | None = None) -> dict:
    """返回 {"tags": [...], "cores": {神煞: 核心用法}, "status", "source"}。
    tags 每条：id、shensha、pillar（柱名）、tag、classic、source、origin（古籍译 / 自起草）。"""
    gender = {"male": "男", "female": "女", "男": "男", "女": "女"}.get(gender or "", None)
    hits = _ss.compute(pillars)
    f = _facts(pillars, hits)
    present = sorted({h["name"] for h in hits})
    tags: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for name in present:
        e = _BY_NAME.get(name)
        if not e:
            continue
        pillars_hit = sorted({p for h in hits if h["name"] == name for p in h["positions"]}, key=_PILLARS.index)
        count = len(pillars_hit)
        for v in e["variants"]:
            for p in pillars_hit:
                if (v["id"], p) in seen:
                    continue
                if _match(v["when"], name, p, f, gender, count):
                    seen.add((v["id"], p))
                    tags.append({"id": v["id"], "shensha": name, "pillar": _CN[p], "tag": v["tag"],
                                 "classic": v["classic"], "source": v["source"],
                                 "origin": "古籍判词的叙事译法（自起草）" if v["classic"] else "自起草（DESIGN 附录 B）"})
    return {"tags": tags, "cores": {n: _BY_NAME[n]["core"] for n in present if n in _BY_NAME},
            "status": "叙事映射自起草；古籍判词部分取自校核定稿的神煞卡", "source": str(_TABLE_PATH.name)}
