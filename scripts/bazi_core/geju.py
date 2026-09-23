"""格局成败救应与取运：查表层。

表来自 tables/geju.json，由 scripts/build_geju.py 从校核卡 references/校核/格局_*.md 的「采用规则」生成；
每条带 source 指向卡号与卡状态。取格仍由 shishen.determine_structure 做，这里按格名带出《子平真诠》的成格、败格、救应
与取运条件。条件目前是原子短语（十神词、身强弱词、关系词），机器可读但未做逐盘判定，判定属规则层下一步；
解读层拿这些条件与命盘的十神事实对照着读。
"""

from __future__ import annotations

import json
from pathlib import Path

_TABLE_PATH = Path(__file__).resolve().parent / "tables" / "geju.json"
_T = json.loads(_TABLE_PATH.read_text(encoding="utf-8"))
_BY_STRUCTURE = {s: e for e in _T["entries"] for s in e["structures"]}
_FINAL = ("已核", "已裁", "已审")


def entry(structure: str) -> dict | None:
    """按 determine_structure 的格名（如 '七杀格'）取表项；没有的（如杂格）返回 None。"""
    return _BY_STRUCTURE.get(structure)


def names() -> list[str]:
    return [e["name"] for e in _T["entries"]]


def _conditions(structure_name: str) -> dict:
    e = entry(structure_name)
    if e is None:
        return {"structure": structure_name, "status": "无卡", "source": None}
    return {
        "structure": structure_name,
        "name": e["name"],
        "cheng": [i["text"] for i in e["cheng"]],
        "bai": [i["text"] for i in e["bai"]],
        "jiu": [j["text"] for j in e["jiu"]],
        "yun": [{"scope": y["scope"], "favor": [i["text"] for i in y["favor"]], "avoid": [i["text"] for i in y["avoid"]],
                 "neutral": [i["text"] for i in y["neutral"] + y["other"]]} for y in e["yun"]],
        "status": "校核定稿" if e["status"] in _FINAL else e["status"],
        "source": e["source"],
    }


def for_chart(structure) -> dict:
    """按取格结果带出条件。structure 可以是 shishen.Structure 或格名字符串。
    变格（会局、生地藏透）时 name 与 base 不同，两套条件都带出，base 的放在 monthBase；杂气兼透的兼用格放在 also。"""
    if isinstance(structure, str):
        return _conditions(structure)
    out = _conditions(structure.name)
    if structure.base and structure.base != structure.name:
        out["variation"] = structure.variation
        out["monthBase"] = _conditions(structure.base)
    if structure.also:
        out["also"] = [_conditions(a) for a in structure.also]
    return out


# ---------------------------------------------------------------- 逐盘判定（规则层第一步，2026-09-23）
#
# 把卡上的原子短语对命盘的十神事实逐条求值：True 成立、False 不成立、None 词表认不出（解读层按原句读）。
# 一条成败救应条件 = 其原子的合取；有 None 且其余皆真则整条为 None（待模型补判）。
# 事实口径：透 = 年月时干；藏 = 四支藏干（本气 1、中气 0.5、余气 0.25 计数）；逢/见/带/无 = 透或支本气（中气余气不算）；
# 重/多/旺/强 = 计数 ≥ 2；轻/弱 = 0 < 计数 < 2；当令 = 月支本气；有根 = 该五行见于任一支藏干；
# 身强弱 = strength.assess 的结论；相碍 = 两神透干且位置相邻（年月、月时以日主隔开不算）；
# 合 = 天干五合（含与日主合）；刑冲 = 月支与他支六冲或三刑。"化""会"类原子不判。

import re as _re

from . import relations as _R
from . import strength as _S
from .shishen import BRANCHES as _B, HIDDEN_STEMS as _H, STEMS as _ST, element_of as _el, ten_god as _tg

_GOD_SETS = {
    "官": {"正官"}, "煞": {"七杀"}, "杀": {"七杀"}, "官煞": {"正官", "七杀"}, "官杀": {"正官", "七杀"}, "七煞": {"七杀"}, "七杀": {"七杀"},
    "正官": {"正官"}, "财": {"正财", "偏财"}, "正财": {"正财"}, "偏财": {"偏财"}, "印": {"正印", "偏印"}, "印绶": {"正印", "偏印"},
    "正印": {"正印"}, "偏印": {"偏印"}, "枭": {"偏印"}, "食": {"食神"}, "食神": {"食神"}, "伤": {"伤官"}, "伤官": {"伤官"},
    "食伤": {"食神", "伤官"}, "伤食": {"食神", "伤官"}, "劫": {"劫财"}, "刃": {"劫财"}, "比": {"比肩"}, "比劫": {"比肩", "劫财"},
    "禄劫": {"比肩", "劫财"}, "财官": {"正财", "偏财", "正官"}, "财印": {"正财", "偏财", "正印", "偏印"},
    "煞印": {"七杀", "正印", "偏印"}, "官印": {"正官", "正印", "偏印"},
}
_GOD_RE = "|".join(sorted(_GOD_SETS, key=len, reverse=True))
_LAYER_W = (1.0, 0.5, 0.25)
_ADJ = {("year", "month"), ("month", "year"), ("month", "day"), ("day", "month"), ("day", "hour"), ("hour", "day")}


def chart_facts(pillars: dict) -> dict:
    """判定用的十神事实。"""
    ds = _ST.index(pillars["day"][0])
    keys = [k for k in ("year", "month", "day", "hour") if pillars.get(k)]
    exposed = {k: _tg(ds, _ST.index(pillars[k][0])) for k in keys if k != "day"}
    hidden = {k: [(_tg(ds, h), _LAYER_W[i]) for i, h in enumerate(_H[_B.index(pillars[k][1])])] for k in keys}
    count: dict[str, float] = {}
    presence: dict[str, float] = {}  # 逢/见/带/无 只认透干与支本气；中气余气不算"逢"（建禄格例：癸日亥中甲木不算"官逢伤"）
    for g in exposed.values():
        count[g] = count.get(g, 0) + 1.0
        presence[g] = presence.get(g, 0) + 1.0
    for items in hidden.values():
        for g, w in items:
            count[g] = count.get(g, 0) + w
            if w >= 1.0:
                presence[g] = presence.get(g, 0) + w
    month_main = _tg(ds, _H[_B.index(pillars["month"][1])][0])
    nat = _R.natal_relations(pillars)
    month_clash = any("month" in p["between"] and any(x in ("六冲", "三刑", "自刑", "六害", "破") for x in p["branches"]) for p in nat["pairs"])
    stem_he_pairs = [tuple(p["between"]) for p in nat["pairs"] if p["stemHe"] and tuple(p["between"]) in _ADJ]
    roots = {_el(h) for items in [_H[_B.index(pillars[k][1])] for k in keys] for h in items}
    day_el, month_el = _el(ds), _el(_H[_B.index(pillars["month"][1])][0])
    return {"exposed": exposed, "hidden": hidden, "count": count, "presence": presence, "monthMain": month_main, "monthClash": month_clash,
            "stemHe": stem_he_pairs, "roots": roots, "dayEl": day_el, "monthEl": month_el, "dayStem": ds,
            "verdict": _S.assess(pillars)["verdict"]}


def _present(f: dict, gods: set) -> bool:
    return any(f["presence"].get(g, 0) > 0 for g in gods)


def _exposed(f: dict, gods: set) -> bool:
    return any(g in gods for g in f["exposed"].values())


def _hidden_only(f: dict, gods: set) -> bool:
    return _present(f, gods) and not _exposed(f, gods)


def _n(f: dict, gods: set) -> float:
    return sum(f["count"].get(g, 0) for g in gods)


def _stems_with(f: dict, gods: set) -> list[str]:
    return [k for k, g in f["exposed"].items() if g in gods]


def _he_with(f: dict, gods_a: set, gods_b: set | None) -> bool:
    """gods_a 所在之干与他干相合；gods_b 给出时须与承载 gods_b 之干（或日主）合。"""
    for a, b in f["stemHe"]:
        ga, gb = f["exposed"].get(a, "日主"), f["exposed"].get(b, "日主")
        for x, y in ((ga, gb), (gb, ga)):
            if x in gods_a and (gods_b is None or y in gods_b or (y == "日主" and gods_b == {"日主"})):
                return True
    return False


def _rooted(f: dict, gods: set) -> bool:
    ds = f["dayStem"]
    els = {e for e in range(5) if _tg(ds, e * 2) in gods or _tg(ds, e * 2 + 1) in gods}
    return bool(els & f["roots"])


def _season(f: dict, word: str) -> bool | None:
    pair = {"金水": (3, 4), "木火": (0, 1)}.get(word)
    if not pair:
        return None
    return f["dayEl"] == pair[0] and f["monthEl"] == pair[1]


def eval_atom(atom: str, f: dict, structure: str | None = None) -> bool | None:
    """一个原子短语对事实求值。认不出返回 None。"""
    a = atom.replace("杀", "煞").replace("枭神", "枭").replace("伤食", "食伤").replace("印绶", "印")
    G = _GOD_RE
    if a in ("身强", "身旺", "身重"):
        return f["verdict"] == "身旺"
    if a in ("身弱", "身轻", "身危"):
        return f["verdict"] == "身弱"
    if a == "无刑冲破害":
        return not f["monthClash"]
    if a in ("有根", "通根"):
        return f["dayEl"] in f["roots"]
    if a == "无根":
        return f["dayEl"] not in f["roots"]
    if a in ("金水", "木火"):
        return _season(f, a)
    if a in ("无制", "煞无食", "煞无制"):
        return not _present(f, {"食神", "伤官"})
    if a in ("制煞", "煞逢制", "煞逢食制", "食制煞", "煞逢食", "透食制煞"):
        return _present(f, {"七杀"}) and (_exposed(f, {"食神", "伤官"}) if a.startswith("透") else _present(f, {"食神", "伤官"}))
    if a == "煞逢制太过":
        return _present(f, {"七杀"}) and _n(f, {"食神", "伤官"}) >= 2 and _n(f, {"七杀"}) < 2
    m = _re.fullmatch(f"({G})逢刑冲", a)
    if m:
        return f["monthMain"] in _GOD_SETS[m.group(1)] and f["monthClash"]
    m = _re.fullmatch(f"(财印|食印)(两清)?不相(碍|伤)", a)
    if m:
        x, y = ({"正财", "偏财"}, {"正印", "偏印"}) if m.group(1) == "财印" else ({"食神"}, {"正印", "偏印"})
        sx, sy = _stems_with(f, x), _stems_with(f, y)
        if not sx or not sy:
            return False
        return not any((p, q) in _ADJ for p in sx for q in sy)
    m = _re.fullmatch("财印相碍", a)
    if m:
        sx, sy = _stems_with(f, {"正财", "偏财"}), _stems_with(f, {"正印", "偏印"})
        return any((p, q) in _ADJ for p in sx for q in sy)
    m = _re.fullmatch(f"({G})当令", a)
    if m:
        return f["monthMain"] in _GOD_SETS[m.group(1)] if m.group(1) not in ("刃", "禄劫") else structure in ("月刃格", "建禄格", "月劫格")
    m = _re.fullmatch(f"({G})(有根|无根)", a)
    if m:
        r = _rooted(f, _GOD_SETS[m.group(1)])
        return r if m.group(2) == "有根" else not r
    m = _re.fullmatch(f"(无)({G})(无({G}))?", a)
    if m:
        gods = set(_GOD_SETS[m.group(2)]) | (set(_GOD_SETS[m.group(4)]) if m.group(4) else set())
        return not _present(f, gods)
    m = _re.fullmatch(f"(透|露)({G})", a) or _re.fullmatch(f"({G})(透|露)", a)
    if m:
        g = m.group(2) if m.group(1) in ("透", "露") else m.group(1)
        return _exposed(f, _GOD_SETS[g])
    m = _re.fullmatch(f"({G})藏", a)
    if m:
        return _hidden_only(f, _GOD_SETS[m.group(1)])
    m = _re.fullmatch(f"(两)({G})透", a)
    if m:
        return len(_stems_with(f, _GOD_SETS[m.group(2)])) >= 2
    m = _re.fullmatch(f"({G})(并透|偏正叠出)", a)
    if m:
        return len(_stems_with(f, _GOD_SETS[m.group(1)])) >= 2
    m = _re.fullmatch(f"(逢|见|带|用)({G})", a)
    if m:
        return _present(f, _GOD_SETS[m.group(2)])
    m = _re.fullmatch(f"({G})(重|多|旺|强)", a)
    if m:
        return _n(f, _GOD_SETS[m.group(1)]) >= 2
    m = _re.fullmatch(f"({G})(轻|弱)", a)
    if m:
        n = _n(f, _GOD_SETS[m.group(1)])
        return 0 < n < 2
    m = _re.fullmatch(f"({G})混", a)
    if m:  # 官煞混：官与煞并见
        gods = _GOD_SETS[m.group(1)]
        return all(_present(f, {g}) for g in gods) if len(gods) > 1 else _n(f, gods) >= 2
    m = _re.fullmatch(f"(合)({G})", a) or _re.fullmatch(f"({G})逢合", a) or _re.fullmatch(f"({G})被合", a)
    if m:
        g = m.group(2) if m.group(1) == "合" else m.group(1)
        return _he_with(f, _GOD_SETS[g], None)
    m = _re.fullmatch(f"透刃合煞", a)
    if m:
        return _he_with(f, {"劫财"}, {"七杀"})
    m = _re.fullmatch(f"({G})(逢|带|见|用|生|佩)({G})(混|制)?", a)
    if m:
        x, y = _GOD_SETS[m.group(1)], _GOD_SETS[m.group(3)]
        if m.group(4) == "混":
            return _present(f, x) and _present(f, y)
        if m.group(4) == "制":
            return _present(f, x) and _present(f, y)
        return _present(f, x) and _present(f, y)
    m = _re.fullmatch(f"(用)({G})(无|逢)({G})", a)
    if m:
        x, y = _GOD_SETS[m.group(2)], _GOD_SETS[m.group(4)]
        return _present(f, x) and (_present(f, y) if m.group(3) == "逢" else not _present(f, y))
    m = _re.fullmatch(f"({G})无({G})(辅)?", a)
    if m:
        return _present(f, _GOD_SETS[m.group(1)]) and not _present(f, _GOD_SETS[m.group(2)])
    m = _re.fullmatch(f"({G})制({G})", a)
    if m:
        return _present(f, _GOD_SETS[m.group(1)]) and _present(f, _GOD_SETS[m.group(2)])
    return None


def _eval_condition(cond: dict, f: dict, structure: str | None) -> dict:
    atoms = {at: eval_atom(at, f, structure) for at in cond["atoms"]}
    vals = list(atoms.values())
    if not vals:
        holds = None
    elif any(v is False for v in vals):
        holds = False
    elif any(v is None for v in vals):
        holds = None
    else:
        holds = True
    return {"text": cond["text"], "holds": holds, "atoms": atoms}


def judge(pillars: dict, structure) -> dict:
    """按取格结果对命盘逐条判成败救应与取运局。structure 是 shishen.Structure 或格名。
    返回 {structure, base?, verdict, cheng, bai, jiu, yun, coverage}；verdict：成格 / 败格 / 败而有救 / 不成格 / 待判。"""
    name = structure if isinstance(structure, str) else structure.name
    e = entry(name)
    f = chart_facts(pillars)
    if e is None:
        return {"structure": name, "verdict": "无卡", "coverage": None}
    cheng = [_eval_condition(c, f, name) for c in e["cheng"]]
    bai = [_eval_condition(c, f, name) for c in e["bai"]]
    jiu = []
    for j in e["jiu"]:
        cause = _eval_condition(j["cause"], f, name)
        fix = _eval_condition(j["fix"], f, name)
        jiu.append({"text": j["text"], "cause": cause, "fix": fix,
                    "applies": True if (cause["holds"] and fix["holds"]) else (None if (cause["holds"] is not False and fix["holds"] is not False and (cause["holds"] is None or fix["holds"] is None)) else False)})
    yun = []
    for y in e["yun"]:
        scope = {at: eval_atom(at, f, name) for at in y["scopeAtoms"]}
        sv = list(scope.values())
        holds = None if not sv else (False if any(v is False for v in sv) else (None if any(v is None for v in sv) else True))
        yun.append({"scope": y["scope"], "holds": holds, "atoms": scope,
                    "favor": [i["text"] for i in y["favor"]], "avoid": [i["text"] for i in y["avoid"]],
                    "neutral": [i["text"] for i in y["neutral"] + y["other"]]})
    all_atoms = [v for c in cheng + bai for v in c["atoms"].values()] + [v for j in jiu for v in list(j["cause"]["atoms"].values()) + list(j["fix"]["atoms"].values())]
    known = sum(1 for v in all_atoms if v is not None)
    any_cheng = any(c["holds"] for c in cheng)
    any_bai = any(c["holds"] for c in bai)
    saved = any(j["applies"] for j in jiu)
    if any_bai and not saved:
        verdict = "败格"
    elif any_bai and saved:
        verdict = "败而有救"
    elif any_cheng:
        verdict = "成格"
    elif any(c["holds"] is None for c in cheng + bai):
        verdict = "待判"
    else:
        verdict = "不成格"
    out = {"structure": name, "verdict": verdict, "cheng": cheng, "bai": bai, "jiu": jiu, "yun": yun,
           "coverage": f"{known}/{len(all_atoms)}", "facts": {"exposed": f["exposed"], "monthMain": f["monthMain"], "strength": f["verdict"]}}
    if not isinstance(structure, str) and structure.base and structure.base != name and entry(structure.base):
        out["monthBase"] = judge(pillars, structure.base)
    return out
