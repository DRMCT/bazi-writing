"""日支亲密关系：查表层（DESIGN-人物层 1 亲密关系模式取日支与亲密关系星）。

表在 tables/rizhi_intimacy.json（narrative-table/v1，三张分表）：日支本气十神一行、日支地支一行、修正项若干。
for_chart 按命盘事实求值：十神行与地支行必中各一，修正项按 cond 码逐条判，命中的进 modifiers。
条件码：day_branch_yong / day_branch_ji（日支本气五行在五神里的位置）、day_branch_clashed / combined / xing / hai（命局内
他支对日支的六冲、六合、刑或自刑、害）、day_branch_empty（日支旬空）、day_branch_taohua（日支坐桃花或红艳）、
lover_star_absent / multi / clean / muddy（亲密关系星：命盘顶层 loverStar，排盘时 --lover-star 指定，默认男取财、女取官杀，
DESIGN-人物层 6）、jie_heavy_cai_light（亲密关系星为财时判，传统男命）、female_guan_sha_mixed（亲密关系星为官杀时判，传统女命）、day_stem_he。
条件按亲密关系星的家族判，不按性别：作者把一个角色的亲密关系星改成别的家族，财清财浊一类条件跟着家族走。
编号前缀 IN：IN-十神-{十神}、IN-支-{地支}、IN-{cond}。叙事各栏自起草，锚点指向校核卡，人物档案引编号时在 note 注明自起草。
"""

from __future__ import annotations

import json
from pathlib import Path

from . import relations as _R
from . import shensha as _ss
from .shishen import BRANCHES, HIDDEN_STEMS, STEMS, WUXING, element_of, ten_god

_TABLE_PATH = Path(__file__).resolve().parent / "tables" / "rizhi_intimacy.json"
_T = json.loads(_TABLE_PATH.read_text(encoding="utf-8"))
_SEC = {s["key"]: s for s in _T["sections"]}
_BY_GOD = {r["tenGod"]: r for r in _SEC["tenGod"]["rows"]}
_BY_BRANCH = {r["branch"]: r for r in _SEC["branch"]["rows"]}
_MODS = {r["cond"]: r for r in _SEC["modifiers"]["rows"]}
_FAM = {"比肩": "比劫", "劫财": "比劫", "食神": "食伤", "伤官": "食伤", "正财": "财", "偏财": "财",
        "正官": "官杀", "七杀": "官杀", "正印": "印", "偏印": "印"}
_KEYS = ("year", "month", "day", "hour")
LOVER_FAMILY = {"male": "财", "female": "官杀"}  # 传统默认（DESIGN-人物层 6）
FAMILY_GODS = {"财": ("正财", "偏财"), "官杀": ("正官", "七杀"), "食伤": ("食神", "伤官"), "印": ("正印", "偏印"), "比劫": ("比肩", "劫财")}
FAMILIES = tuple(FAMILY_GODS)


def table() -> dict:
    return _T


def default_family(gender: str | None) -> str | None:
    return LOVER_FAMILY.get(gender or "")


def lover_spec(gender: str | None, family: str | None = None) -> dict | None:
    """命盘顶层 loverStar：{"family", "gods", "by"}。作者指定的家族优先（排盘 --lover-star），否则按性别取传统默认；没性别也没指定则 None。"""
    if family:
        if family not in FAMILY_GODS:
            raise ValueError(f"亲密关系星须是 {'、'.join(FAMILIES)} 之一，收到 {family!r}")
        return {"family": family, "gods": list(FAMILY_GODS[family]), "by": "作者指定"}
    fam = default_family(gender)
    return {"family": fam, "gods": list(FAMILY_GODS[fam]), "by": "性别默认"} if fam else None


def lover_gods(chart: dict) -> tuple[str, ...]:
    """年表与阶段卡读这个：命盘顶层 loverStar 的十神对；旧命盘没有该字段时按性别取默认。"""
    spec = chart.get("loverStar") or lover_spec(chart.get("gender"))
    return tuple(spec["gods"]) if spec else ()


def lover_star(pillars: dict, family: str | None) -> dict:
    """亲密关系星的分布：透干几处、坐支本气几处、任一层藏干是否可见。family 取 FAMILIES 之一或 None。"""
    fam = family
    if not fam:
        return {"family": None, "exposed": 0, "main": 0, "anywhere": False}
    ds = STEMS.index(pillars["day"][0])
    exposed = main = 0
    anywhere = False
    for k in _KEYS:
        p = pillars.get(k)
        if not p:
            continue
        if k != "day" and _FAM[ten_god(ds, STEMS.index(p[0]))] == fam:
            exposed += 1
            anywhere = True
        hidden = HIDDEN_STEMS[BRANCHES.index(p[1])]
        if _FAM[ten_god(ds, hidden[0])] == fam:
            main += 1
        if any(_FAM[ten_god(ds, h)] == fam for h in hidden):
            anywhere = True
    return {"family": fam, "exposed": exposed, "main": main, "anywhere": anywhere}


def _conditions(pillars: dict, family: str | None, ys: dict) -> list[str]:
    ds = STEMS.index(pillars["day"][0])
    db = pillars["day"][1]
    main_el = WUXING[element_of(HIDDEN_STEMS[BRANCHES.index(db)][0])]
    role = ys["roles"][main_el]
    hit: list[str] = []
    if role in ("用", "喜"):
        hit.append("day_branch_yong")
    elif role in ("忌", "仇"):
        hit.append("day_branch_ji")
    rels: set[str] = set()
    stem_he = False
    for pr in _R.natal_relations(pillars)["pairs"]:
        if "day" not in pr["between"]:
            continue
        rels.update(pr["branches"])
        stem_he = stem_he or bool(pr.get("stemHe"))
    if "六冲" in rels:
        hit.append("day_branch_clashed")
    if "六合" in rels:
        hit.append("day_branch_combined")
    if rels & {"刑", "自刑"}:
        hit.append("day_branch_xing")
    if "害" in rels:
        hit.append("day_branch_hai")
    if db in _ss.xun_kong(pillars["day"]):
        hit.append("day_branch_empty")
    hits = _ss.compute(pillars)
    if any(h["name"] in ("桃花", "红艳") and "day" in h["positions"] for h in hits):
        hit.append("day_branch_taohua")
    ls = lover_star(pillars, family)
    exposed_gods = {ten_god(ds, STEMS.index(pillars[k][0])) for k in ("year", "month", "hour") if pillars.get(k)}
    exposed_fams = {_FAM[g] for g in exposed_gods}
    if ls["family"]:
        if not ls["anywhere"]:
            hit.append("lover_star_absent")
        if ls["exposed"] >= 2 or ls["exposed"] + ls["main"] >= 3:
            hit.append("lover_star_multi")
    if family == "财":  # 财清财浊、比劫夺财：亲密关系星为财时判（传统男命）
        cai_el = WUXING[(element_of(ds) + 2) % 5]
        if ys["roles"][cai_el] in ("用", "喜") and "比劫" not in exposed_fams and ls["anywhere"]:
            hit.append("lover_star_clean")
        if "财" in exposed_fams and ("官杀" in exposed_fams or ("印" in exposed_fams and ys.get("side") == "身弱")):
            hit.append("lover_star_muddy")
        w = ys.get("familyWeights") or {}
        if w and w.get("比劫", 0) > 2 * w.get("财", 0) and "财" not in exposed_fams:
            hit.append("jie_heavy_cai_light")
    if family == "官杀" and {"正官", "七杀"} <= exposed_gods:  # 官杀混杂：亲密关系星为官杀时判（传统女命）
        hit.append("female_guan_sha_mixed")
    if stem_he:
        hit.append("day_stem_he")
    return hit


def for_chart(pillars: dict, gender: str | None, ys: dict, family: str | None = None) -> dict:
    """返回 {"tenGod": 行, "branch": 行, "modifiers": [行], "loverStar": {...}, "features": [{id, kind, text}], "status", "source"}。
    family 是亲密关系星的家族（命盘顶层 loverStar.family），不给则按性别取默认。"""
    family = family or default_family(gender)
    ds = STEMS.index(pillars["day"][0])
    db = pillars["day"][1]
    god = ten_god(ds, HIDDEN_STEMS[BRANCHES.index(db)][0])
    god_row = _BY_GOD[god]
    br_row = _BY_BRANCH[db]
    conds = _conditions(pillars, family, ys)
    mods = [{"id": f"IN-{c}", **_MODS[c]} for c in conds]
    feats = [
        {"id": f"IN-十神-{god}", "kind": "亲密关系",
         "text": f"日支{db}本气为{god}：伴侣像{god_row['partner']}；{god_row['pattern']}；摩擦在{god_row['friction']}"},
        {"id": f"IN-支-{db}", "kind": "亲密关系", "text": f"日支{db}（{br_row['kind']}）：关系{br_row['temper']}；{br_row['scene']}"},
    ]
    for m in mods:
        feats.append({"id": m["id"], "kind": "亲密关系修正",
                      "text": f"{m['when']}：{m['effect']}" + (f"｜古籍：{m['classic']}" if m.get("classic") else "")})
    return {"tenGod": {"id": f"IN-十神-{god}", **god_row}, "branch": {"id": f"IN-支-{db}", **br_row}, "modifiers": mods,
            "loverStar": {"family": family, **{k: v for k, v in lover_star(pillars, family).items() if k != "family"}}, "features": feats,
            "status": "叙事映射自起草；修正项里的古籍判词取自六亲夫妻卡与官杀卡", "source": _TABLE_PATH.name}
