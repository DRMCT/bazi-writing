"""旺衰打分 v2——本项目自起草，无开源依据。

为什么自起草：截至 2026-09-21 没有找到带干净许可证的确定性旺衰算法
（zhexue-shushu 的系数表来自商业 App 反编译；taibu core 不算旺衰；yueyuan
只给得令/得地/得生/得助四个布尔标志；tyme4py 与 lunar_python 皆无）。
反推搜索需要可打分、可复现的旺衰，故在 yueyuan 四标志之上加一套显式权重。

原则：确定性、可解释。每项贡献都列出来，临界盘打「中和」并标记交模型补判。
权重是初值，按 DESIGN 6.4 校准后再定。

依据（非算法来源，只是分类口径）：《滴天髓》论旺衰以月令为纲，兼看通根与生扶；
《子平真诠》以月令定体。此处：
- 得令：月支本气对日主为比劫或印。
- 得地：地支藏干见比劫（通根）；印在支只计入生扶分，不算得地。
- 得势：年月时天干为比劫或印。

v2 合局项（DESIGN 6.4，2026-09-23 由 Fable 重写；9-22 那版出自 Opus 5 已撤回）：单看干支各自加权不够，成局之气另计。
- 三合局、三会方三支齐全：参与之支本气改按局之五行论，整支加权，中气余气减半（气已从局）。
  古籍依据：《三命通会》论支元三合"三字缺其一，则化不成局"（上126，卡 刑冲合害-三合）。三会方无专篇，力度略大于三合。
- 半合：三合缺一而有中神（子午卯酉）：局之五行小幅加权，本气不改；无中神的拱合不计。四库本不认半合成局，此项纯属校准参数。
- 六合：所化五行当令（月支本气同五行）作合化，两支本气改按化气论并加权；否则作合绊，两支减力。
  四库本论支元六合通篇不言所化，所化五行按两库一致收录、午未两存（卡 刑冲合害-六合），午未一律只作合绊。合化条件是自起草。
- 天干五合（只认相邻：年月、月日、日时）：月令在化气之局或次月且无妒合之干，作合化，两干改按化气论并加权；
  否则合绊，两干减力。日主参与的合只把对方合住（减力），日主自身不改，化气成格属变格另判。
  古籍依据：《三命通会》论十干化气"甲己化土，非辰戌丑未月不化，其次午月亦化，有戊字间之则不化，名曰妒合"等五条（上120，卡 刑冲合害-天干五合）。
  "间之"本指位置相隔，此处简化为柱中见该干即妒合。
- 合局所成之五行与日主同气为生扶，异气为耗泄，走十神归类即得；所成之气若正是调候所需，在解读层另记，不进旺衰分。
- 未做：争合妒合的强弱分档。系数皆初值，校准流程见 scripts/calibrate_strength.py。
- v3 实验（2026-09-25，`calibrate_strength.py v3`，报告 references/校核/旺衰_v3报告.md）：冲破合局、墓库长生作根、印折扣三项
  做成模块开关与系数，对子代理 120 盘与徐评例盘 110 盘各跑一遍，没有一项在子代理标准上净增：冲破合局零变化（古籍还倒错一张，
  徐评"寅午会局身旺"的盘被年支子遥冲破了局）；墓库长生作根 0.3/0.5/0.8 子代理 -2/-4/-4、古籍 +2/+3/+4，是拿标准换偏差记录；
  印折扣 0.8/0.7/0.6 子代理 -1/0/0、古籍 -3/-2/-1。默认值全部保持 v2，开关留着给后来的标准用。
"""

from __future__ import annotations

from . import changsheng as CS
from . import relations as R
from .shishen import BRANCHES, HIDDEN_STEMS, STEMS, WUXING, element_of, ten_god

SUPPORT = frozenset({"比肩", "劫财", "正印", "偏印"})
DRAIN = frozenset({"食神", "伤官", "正财", "偏财", "正官", "七杀"})

STEM_WEIGHT = {"year": 12, "month": 15, "hour": 12}  # 9-23 由 8/10/8 抬高：徐评例盘显示天干透出之比劫与官煞比支中中余气分量重
# 本气 / 中气 / 余气
BRANCH_WEIGHT = {
    "month": (30, 10, 4),
    "day": (15, 5, 2),
    "year": (10, 4, 2),
    "hour": (10, 4, 2),
}
YIN_SCALE = 1.0  # 印的生扶力相对比劫的折扣（校准参数）
# 比值归一：五行里生扶（比劫、印）占两种，克泄耗（官煞、财、食伤）占三种，按原分累加时中性盘比值落在 0.4 附近，
# 故克泄分乘 2/3 再算比值，使五行均匀的盘得 0.5。
DRAIN_SCALE = 2 / 3
# 分档阈值（2026-09-23 校准定稿，见 DESIGN 6.4 与 scripts/calibrate_strength.py）：
# 以 120 盘 Fable 子代理独立判定为标准，归一比值的旺弱分界落在 0.50 附近，中和带取 0.48–0.52，一致率 107/120；
# 徐评例盘 107 盘（徐用"身旺"较宽，分界约 0.38）在此阈值下一致 60/107，作偏差记录不作标准。
STRONG_AT = 0.52
WEAK_AT = 0.48
FOLLOW_STRONG_AT = 0.85
FOLLOW_WEAK_AT = 0.15

# ---- 合局系数（v2，初值，待 DESIGN 6.4 校准）
SANHUI_FACTOR = 1.6    # 三会方三支齐全：同方一气
SANHE_FACTOR = 1.5     # 三合局三支齐全
BANHE_FACTOR = 1.2     # 半合：三合缺一而有中神；只加权不改本气
LIUHE_HUA_FACTOR = 1.2 # 六合合化成立：改按化气论并加权
LIUHE_DAMP = 0.8       # 六合合绊：两支减力
STEMHE_HUA_FACTOR = 1.2  # 天干合化成立
STEMHE_DAMP = 0.7      # 天干合绊：两干减力；日主参与时只减对方
MINOR_DAMP = 0.5       # 成局改本气之支，其中气余气减半
FACTOR_FLOOR, FACTOR_CEIL = 0.5, 2.0

# ---- v3 实验项（2026-09-25，默认关；开关与系数由 scripts/calibrate_strength.py v3 对两路标准跑格子后定）
# 冲破合局：合局（三合三会、半合、六合）里任一支被局外之支六冲，则合不成，不加权不改本气也不合绊。
#   依据：《子平真诠评注》论偏官 徐评"刘造寅亥虽合，而得申遥冲解其合"（p？见校对本），论相神"会合解冲"反之亦然，
#   论用神成败救应 原文"刑冲而会合以解之"。是否冲破按六冲表（tables/relations.json，卡 刑冲合害-六冲）。
V3_CHONG_BREAKS_COMBO = False
# 墓库长生作根：日主在某支为长生或墓（十二长生表，卡 十二长生纳音-十干长生位）且该支藏干见比劫，
#   另加该柱本气权重乘 KU_SHENG_ROOT_FACTOR 的生扶分并算得地。阴干长生之支不藏比劫（乙长生午、癸长生卯一类）不加，
#   与任注"阴火长生俗传之谬"相合。依据：徐评例盘"丙火坐戌，通根火库"（穷通 p110 印刷页）、《滴天髓阐微》岁运"必先要旺运通根"。
V3_KU_SHENG_ROOT = False
KU_SHENG_ROOT_FACTOR = 0.5

# 天干合化的月令条件与妒合之干：《三命通会》上120（卡 刑冲合害-天干五合）
STEM_HUA_RULES = {
    "土": {"months": "辰戌丑未", "next": "午", "jealous": "戊"},
    "金": {"months": "巳酉丑", "next": "申", "jealous": "甲"},
    "水": {"months": "申子辰", "next": "亥", "jealous": "丁"},
    "木": {"months": "亥卯未", "next": "寅", "jealous": "丙"},
    "火": {"months": "寅午戌", "next": "巳", "jealous": "己"},
}
# 五行名 → 该五行阳干序（木甲 火丙 土戊 金庚 水壬），改论时用
_ELEM_STEM = {"木": 0, "火": 2, "土": 4, "金": 6, "水": 8}
_CENTER = "子午卯酉"
_ADJACENT = (("year", "month"), ("month", "day"), ("day", "hour"))

_PILLAR_KEYS = ("year", "month", "day", "hour")
_CN = {"year": "年", "month": "月", "day": "日", "hour": "时"}


def _clamp(x: float) -> float:
    return round(min(FACTOR_CEIL, max(FACTOR_FLOOR, x)), 3)


def combo_effects(pillars: dict) -> tuple[dict, dict, list[dict]]:
    """合局对力量的修正。

    返回 (branch_effects, stem_effects, notes)。
    branch_effects[柱] = {"factor", "override"}：override 是本气改论的五行名或 None。
    stem_effects[柱] = {"factor", "override"}：天干合化时 override 为化气五行，合绊时只有 factor。
    一支或一干可同时被多个关系牵动：系数相乘后截断；override 取力度最大者。
    """
    keys = [k for k in _PILLAR_KEYS if pillars.get(k)]
    branch_of = {k: pillars[k][1] for k in keys}
    stem_of = {k: pillars[k][0] for k in keys}
    present = set(branch_of.values())
    month_el = WUXING[element_of(HIDDEN_STEMS[BRANCHES.index(branch_of["month"])][0])] if "month" in branch_of else None
    b_eff = {k: {"factor": 1.0, "override": None, "_rank": 0.0} for k in keys}
    s_eff = {k: {"factor": 1.0, "override": None, "_rank": 0.0} for k in keys}
    notes: list[dict] = []

    all_branches = [branch_of[k] for k in keys]

    def broken_by(branches: str) -> str | None:
        """v3：局中任一支被局外之支六冲，返回"申冲寅"一类说明，否则 None。"""
        if not V3_CHONG_BREAKS_COMBO:
            return None
        for z in branches:
            foe = R.LIU_CHONG.get(z)
            if foe and foe not in branches and foe in all_branches:
                return f"{foe}冲{z}"
        return None

    def touch_branches(branches: str, factor: float, element: str | None, kind: str, override: bool, detail: str) -> None:
        hit = [k for k in keys if branch_of[k] in branches]
        if (why := broken_by(branches)):
            notes.append({"kind": kind, "branches": branches, "element": element, "factor": 1.0, "override": False,
                          "pillars": [_CN[k] for k in hit], "detail": f"{detail}；{why}，冲破合局，不计", "broken": why})
            return
        for k in hit:
            e = b_eff[k]
            e["factor"] *= factor
            if override and element and factor > e["_rank"]:
                e["override"], e["_rank"] = element, factor
        notes.append({"kind": kind, "branches": branches, "element": element, "factor": factor,
                      "override": override, "pillars": [_CN[k] for k in hit], "detail": detail})

    # 三会方、三合局（三支齐全）：改本气
    for fang, wx in R.SAN_HUI.items():
        if all(z in present for z in fang):
            touch_branches(fang, SANHUI_FACTOR, wx, "三会", True, f"{fang}三会{wx}方，参与之支本气改按{wx}论")
    for ju, wx in R.SAN_HE.items():
        if all(z in present for z in ju):
            touch_branches(ju, SANHE_FACTOR, wx, "三合", True, f"{ju}三合{wx}局，参与之支本气改按{wx}论")
        elif ju[1] in present:
            partial = "".join(z for z in ju if z in present)
            if len(partial) == 2:
                touch_branches(partial, BANHE_FACTOR, wx, "半合", False, f"{partial}半合{wx}（有中神{ju[1]}），加权不改本气")
    # 六合：所化当令则合化，否则合绊
    seen: set[frozenset] = set()
    for k in keys:
        b = branch_of[k]
        mate = R.LIU_HE.get(b)
        if not mate or mate not in present:
            continue
        pair = frozenset({b, mate})
        if pair in seen:
            continue
        seen.add(pair)
        wx = R.LIU_HE_ELEMENT.get(b + mate)
        if wx and wx == month_el:
            touch_branches(b + mate, LIUHE_HUA_FACTOR, wx, "六合", True, f"{b}{mate}六合化{wx}，{wx}当令，合化成立，两支本气改按{wx}论")
        else:
            why = "所化两存" if wx is None else f"所化{wx}不当令"
            touch_branches(b + mate, LIUHE_DAMP, wx, "六合", False, f"{b}{mate}六合，{why}，作合绊，两支减力")

    # 天干五合：只认相邻
    for ka, kb in _ADJACENT:
        if ka not in stem_of or kb not in stem_of:
            continue
        a, b = stem_of[ka], stem_of[kb]
        if R.STEM_HE.get(a) != b:
            continue
        wx = R.STEM_HE_ELEMENT[a + b]
        rule = STEM_HUA_RULES[wx]
        mb = branch_of["month"]
        others = [stem_of[k] for k in keys if k not in (ka, kb)]
        in_season = mb in rule["months"] or mb == rule["next"]
        jealous = rule["jealous"] in others
        hua = in_season and not jealous
        involves_day = "day" in (ka, kb)
        label = f"{_CN[ka]}干{a}与{_CN[kb]}干{b}合"
        if involves_day:
            other = kb if ka == "day" else ka
            s_eff[other]["factor"] *= STEMHE_DAMP
            detail = f"{label}，日主合{stem_of[other]}，{stem_of[other]}被合住减力" + ("；月令合化条件具，化气成格另判" if hua else "")
            notes.append({"kind": "天干合", "stems": a + b, "element": wx, "factor": STEMHE_DAMP, "override": False,
                          "pillars": [_CN[other]], "detail": detail})
            continue
        if hua:
            for k in (ka, kb):
                e = s_eff[k]
                e["factor"] *= STEMHE_HUA_FACTOR
                if STEMHE_HUA_FACTOR > e["_rank"]:
                    e["override"], e["_rank"] = wx, STEMHE_HUA_FACTOR
            detail = f"{label}化{wx}，月令{mb}合化条件具且无{rule['jealous']}妒合，两干改按{wx}论"
            notes.append({"kind": "天干合", "stems": a + b, "element": wx, "factor": STEMHE_HUA_FACTOR, "override": True,
                          "pillars": [_CN[ka], _CN[kb]], "detail": detail})
        else:
            for k in (ka, kb):
                s_eff[k]["factor"] *= STEMHE_DAMP
            why = f"有{rule['jealous']}妒合" if jealous else f"月令{mb}不化{wx}"
            notes.append({"kind": "天干合", "stems": a + b, "element": wx, "factor": STEMHE_DAMP, "override": False,
                          "pillars": [_CN[ka], _CN[kb]], "detail": f"{label}，{why}，作合绊，两干减力"})

    for eff in (b_eff, s_eff):
        for e in eff.values():
            e["factor"] = _clamp(e["factor"])
            e.pop("_rank")
    return b_eff, s_eff, notes


def assess(pillars: dict) -> dict:
    ds = STEMS.index(pillars["day"][0])
    day_el = element_of(ds)
    contributions: list[dict] = []
    support = 0.0
    drain = 0.0

    def add(where: str, stem_idx: int, weight: float) -> None:
        nonlocal support, drain
        god = ten_god(ds, stem_idx)
        side = "support" if god in SUPPORT else "drain"
        if god in ("正印", "偏印"):
            weight = round(weight * YIN_SCALE, 2)
        if side == "support":
            support += weight
        else:
            drain += weight
        contributions.append({"where": where, "stem": STEMS[stem_idx], "tenGod": god,
                              "weight": weight, "side": side})

    b_eff, s_eff, combos = combo_effects(pillars)
    for key in _PILLAR_KEYS:
        p = pillars.get(key)
        if not p:
            continue
        if key != "day":
            se = s_eff[key]
            w = STEM_WEIGHT[key] * se["factor"]
            if se["override"]:
                add(f"{_CN[key]}干（化{se['override']}）", _ELEM_STEM[se["override"]], round(w, 2))
            else:
                add(f"{_CN[key]}干", STEMS.index(p[0]), round(w, 2))
        be = b_eff[key]
        factor, override = be["factor"], be["override"]
        hidden = HIDDEN_STEMS[BRANCHES.index(p[1])]
        for layer, stem_idx in enumerate(hidden):
            layer_name = ("本气", "中气", "余气")[layer]
            w = BRANCH_WEIGHT[key][layer] * factor
            if override and layer == 0:
                add(f"{_CN[key]}支本气（从{override}局）", _ELEM_STEM[override], round(w, 2))
                continue
            if override:
                w *= MINOR_DAMP
            add(f"{_CN[key]}支{layer_name}", stem_idx, round(w, 2))
        if V3_KU_SHENG_ROOT and not override:
            stg = CS.stage(pillars["day"][0], p[1])
            if stg in ("长生", "墓"):
                bijie = [h for h in hidden if ten_god(ds, h) in ("比肩", "劫财")]
                if bijie:
                    add(f"{_CN[key]}支{stg}作根", bijie[0], round(BRANCH_WEIGHT[key][0] * KU_SHENG_ROOT_FACTOR, 2))

    total = support + drain * DRAIN_SCALE
    ratio = support / total if total else 0.5
    month_main = HIDDEN_STEMS[BRANCHES.index(pillars["month"][1])][0]
    de_ling = ten_god(ds, month_main) in SUPPORT
    # 得地取通根之义：地支藏干见比劫；印在支只算生扶，不算根
    de_di = any(c["tenGod"] in ("比肩", "劫财") and "支" in c["where"] for c in contributions)
    de_shi = sum(1 for c in contributions if c["side"] == "support" and c["where"].startswith(("年干", "月干", "时干"))) >= 2

    if ratio >= FOLLOW_STRONG_AT:
        verdict, note = "身旺", "从强候选"
    elif ratio >= STRONG_AT:
        verdict, note = "身旺", None
    elif ratio <= FOLLOW_WEAK_AT:
        verdict, note = "身弱", "从弱候选"
    elif ratio <= WEAK_AT:
        verdict, note = "身弱", None
    else:
        verdict, note = "中和", "临界盘，解读时交模型补判"

    # 喜忌五行：身旺喜泄克耗（我生、我克、克我），身弱喜生扶（生我、同我）；中和先看调候
    me, sheng_wo, wo_sheng, wo_ke, ke_wo = (
        WUXING[day_el], WUXING[(day_el - 1) % 5], WUXING[(day_el + 1) % 5],
        WUXING[(day_el + 2) % 5], WUXING[(day_el + 3) % 5],
    )
    if verdict == "身旺":
        favorable, unfavorable = [wo_sheng, wo_ke, ke_wo], [sheng_wo, me]
    elif verdict == "身弱":
        favorable, unfavorable = [sheng_wo, me], [wo_sheng, wo_ke, ke_wo]
    else:
        favorable, unfavorable = [], []

    return {
        "algorithm": "bazi-writing strength v2（自起草，含合局项；见模块文档与 DESIGN 6.4）",
        "dayMaster": WUXING[day_el],
        "support": round(support, 2),
        "drain": round(drain, 2),
        "ratio": round(ratio, 3),
        "verdict": verdict,
        "note": note,
        "flags": {"得令": de_ling, "得地": de_di, "得势": de_shi},
        "favorable": favorable,
        "unfavorable": unfavorable,
        "combos": combos,
        "contributions": contributions,
    }
