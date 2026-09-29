"""用神与五神（用、喜、忌、仇、闲）——本项目自起草，按徐评例盘校准。

为什么要有：人物档案"真正需要的东西"取用神（DESIGN-人物层 1），多人矩阵要看"A 的用神是不是 B 的日主五行"（DESIGN-命盘层 6），
弧光要给每步大运按用喜闲忌打分（11.2）。旺衰模块只给身强弱与粗喜忌，不分用与喜，也不认病药与调候。

口径：子平为主，调候为辅（DESIGN-命盘层 0）。确定性，每一步写进 reason。
1. 从格（从严）：旺衰比值 ≥ 0.85 且无官杀、财无力才作从强，用生扶中重者；≤ 0.15 且无印、比劫无本气之根才作从弱，
   用克泄耗中最重者。只作候选，解读时复核；够不上的照身强弱论。
2. 扶抑兼病药（徐评"财旺身弱用印""煞重用印""财多用劫""印多用财""身强以制为用"）：
   身弱：克泄耗中最重者为病。官杀、食伤为病用印（化杀、制伤），但印无力（未透干、不坐本气）而杀为病、食伤有力时
   食神制杀（徐评"取食神制煞为用"）；财为病用比劫（敌财）。所取之神盘中无气则取另一个。
   身旺：生扶中重者为病。印为病用财（损印），财无力用食伤（印旺用食伤）；比劫为病按"比劫重用官杀，无官杀用食伤"，官杀亦重时食神制杀，群劫争财故财最后取。
   身弱财多而官杀有力、盘中有印：用印，财杀同为病（"财官两旺而身弱，故用印"）。
   中和（临界带）：按比值落在 0.5 哪一侧走上两条之一，标临界。
3. 调候：亥子丑月调候首选为丙丁、巳午未月调候首选为壬癸时为"调候急"。调候之神不在扶抑的忌一侧、也不是病神，
   则取调候为用（"金寒水冷，取午火为用，乃调和气候之意"），盘中全无也取（寒极燥极，待运引出）；在忌一侧则仍用扶抑，
   调候记在 notes 里作喜神候选。
4. 五神由用神推：喜神生用，忌神克用，仇神生忌，闲神为用所生。病神若落在喜、仇、闲位，一律改作忌；
   扶抑忌一侧的不作喜（降为闲），喜一侧的闲神升为喜。闲神按扶抑一侧标偏喜、偏忌（从强以食伤泄秀为偏喜，从弱顺势皆偏喜）。
   数值 preference：用 1、喜 0.5、闲 ±0.25 或 0、仇 -0.5、忌 -1，供弧光与矩阵打分。
   中和临界盘（旺衰结论"中和"）按比值偏侧论后 preference 减半（damping 0.5），弧光与矩阵不被一枚硬币决定。

校准：scripts/calibrate_yongshen.py 以徐乐吾在《子平真诠评注》《穷通宝鉴评注》例盘里明说的用神为标准，
报告在 references/校核/用神_例盘报告.md。权重与分支都是初值。
"""

from __future__ import annotations

from datetime import datetime

from . import strength as strength_mod
from . import tiaohou as tiaohou_mod
from .shishen import BRANCHES, HIDDEN_STEMS, STEMS, WUXING, element_of

FAMILIES = ("比劫", "食伤", "财", "官杀", "印")  # 与日主五行之差 0..4
SUPPORT_F = ("比劫", "印")
DRAIN_F = ("食伤", "财", "官杀")
_GOD_FAMILY = {"比肩": "比劫", "劫财": "比劫", "食神": "食伤", "伤官": "食伤", "正财": "财", "偏财": "财",
               "正官": "官杀", "七杀": "官杀", "正印": "印", "偏印": "印"}

PREFERENCE = {"用": 1.0, "喜": 0.5, "闲": 0.0, "仇": -0.5, "忌": -1.0}
LEAN = 0.25
WINTER, SUMMER = "亥子丑", "巳午未"
STATUS = "自起草，按徐评例盘校准（references/校核/用神_例盘报告.md）"


def family_element(day_el: int, family: str) -> int:
    return (day_el + FAMILIES.index(family)) % 5


def element_family(day_el: int, el: int) -> str:
    return FAMILIES[(el - day_el) % 5]


def family_weights(strength: dict) -> dict[str, float]:
    w = {f: 0.0 for f in FAMILIES}
    for c in strength["contributions"]:
        w[_GOD_FAMILY[c["tenGod"]]] += c["weight"]
    return {k: round(v, 2) for k, v in w.items()}


def family_strong(strength: dict) -> dict[str, bool]:
    """有力：透干，或坐某支本气。只在中气余气里的算无力（"藏而不露，气又休囚，本可不论"）。"""
    out = {f: False for f in FAMILIES}
    for c in strength["contributions"]:
        if "干" in c["where"] or "本气" in c["where"]:
            out[_GOD_FAMILY[c["tenGod"]]] = True
    return out


def _argmax(w: dict[str, float], keys: tuple[str, ...]) -> str:
    # 同分按 keys 顺序取前者
    best = keys[0]
    for k in keys[1:]:
        if w[k] > w[best]:
            best = k
    return best


# 规则开关（校准时比较用；定值见 references/校核/用神_例盘报告.md）
RULES = {
    "caisha_yin": True,       # 身弱财多而官杀有力、盘中有印：取印化杀（"财官两旺而身弱，故用印"）
    "tiaohou_absent": True,   # 调候急而调候之神盘中全无（寒极燥极），且在扶抑的喜一侧：仍取调候为用，待运引出
    "tiaohou_yield": False,    # 调候之神在盘中、扶抑所取又透干有力：扶抑为用，调候退作喜神
    "side_cap": True,         # 扶抑的忌一侧不作喜神（身弱时官杀生印也不算喜），喜一侧的闲神升为喜神
    "cong_strict": True,      # 从格从严：从弱须盘中无印、比劫无本气之根；从强须无官杀、财无力；否则按身强弱论
    "shayin_strong": False,   # 身旺在印而官杀有力：取印化杀（杀印相生）。关：照印多用财；徐评印绶章"用神虽在印"而取运"以财运制印为美"，子代理亦取财
    "yin_weak": True,         # 身弱官杀为病而印无力（未透干、不坐本气）、食伤有力：食神制杀（徐评子平八-06"取食神制煞为用"）。关：盘中有印即取印
}
DAMPING_ZHONGHE = 0.5  # 中和临界盘的 preference 折扣

SHA_HEAVY = 0.6  # 身旺而官杀重（官杀分 ≥ 比劫分 × 0.6）且食伤有力：食神制煞
YIN_OVER = 3.0   # 印分 ≥ 比劫分 × 3 为印太旺（"土重埋金"），印即病，不取印化煞


def _fuyi(side: str, w: dict[str, float], strong: dict[str, bool]) -> tuple[str, str, str]:
    """扶抑兼病药。返回 (用神类, 病神类, 说明)。side 为身旺或身弱。"""
    if side == "身弱":
        bing = _argmax(w, ("官杀", "食伤", "财"))
        if bing in ("官杀", "食伤"):
            fu = '化杀' if bing == '官杀' else '制伤'
            if w["印"] > 0 and (not RULES["yin_weak"] or strong["印"]):
                return "印", bing, f"身弱，{bing}为病，取印{fu}扶身"
            if RULES["yin_weak"] and bing == "官杀" and strong["食伤"]:
                return "食伤", bing, "身弱，杀重而印无力（未透干、不坐本气），食伤有力，取食神制杀"
            if w["印"] > 0:
                return "印", bing, f"身弱，{bing}为病，印虽无力仍取印{fu}扶身"
            return "比劫", bing, f"身弱，{bing}为病，盘中无印，取比劫帮身"
        if RULES["caisha_yin"] and strong["官杀"] and w["印"] > 0:
            return "印", bing + "+官杀", "身弱，财多生杀，官杀有力，取印化杀扶身（财官两旺用印），财杀同为病"
        if w["比劫"] > 0:
            return "比劫", bing, "身弱，财多为病，取比劫敌财"
        return "印", bing, "身弱，财多为病，盘中无比劫，取印扶身"
    bing = "印" if w["印"] >= w["比劫"] else "比劫"
    if bing == "印":
        if RULES["shayin_strong"] and strong["官杀"] and w["印"] < w["比劫"] * YIN_OVER:
            return "印", "财", "身旺在印，官杀透出或坐本气，取印化杀（杀印相生），财来坏印为病"
        if strong["财"]:
            return "财", bing, "身旺，印多为病，取财损印"
        if w["食伤"] > 0:
            return "食伤", bing, "身旺，印旺而财无力，取食伤泄秀"
        if w["财"] > 0:
            return "财", bing, "身旺，印多为病，财虽无力仍取财损印"
        return "官杀", bing, "身旺，印旺而无财无食伤，取官杀"
    # 比劫为病："比劫重用官杀，无官杀用食伤"，群劫争财，财不先取
    if strong["官杀"] and w["官杀"] >= w["比劫"] * SHA_HEAVY and w["食伤"] > 0:
        return "食伤", bing, "身旺，官杀亦重，取食伤制杀（身强以制为用）"
    if strong["官杀"]:
        return "官杀", bing, "身旺，比劫为病，官杀有力，取官杀制劫"
    if w["食伤"] > 0:
        return "食伤", bing, "身旺，比劫为病，官杀无力，取食伤泄秀"
    if w["财"] > 0:
        return "财", bing, "身旺，比劫为病，无官杀食伤，取财"
    if w["官杀"] > 0:
        return "官杀", bing, "身旺，比劫为病，官杀藏而无力，仍取官杀"
    return "食伤", bing, "身旺，比劫为病，克泄耗皆无，取食伤泄秀（盘中无气，待运引出）"


def _roles(day_el: int, use_el: int, bing_el: int | None, lean: dict[int, int]) -> dict[int, str]:
    xi, ji = (use_el - 1) % 5, (use_el - 2) % 5  # 生用者、克用者
    chou, xian = (use_el + 2) % 5, (use_el + 1) % 5  # 生忌者、用所生者
    roles = {use_el: "用", xi: "喜", ji: "忌", chou: "仇", xian: "闲"}
    if bing_el is not None and bing_el != use_el and roles[bing_el] != "忌":
        was = roles[bing_el]
        roles[bing_el] = "忌"
        if was == "喜" and lean.get(xian, 0) > 0:
            roles[xian] = "喜"
    return roles


def element_in_chart(pillars: dict, el: int) -> bool:
    """某五行是否透干或藏支（日干不算）。"""
    for k, p in pillars.items():
        if not p:
            continue
        if k != "day" and element_of(STEMS.index(p[0])) == el:
            return True
        if any(element_of(h) == el for h in HIDDEN_STEMS[BRANCHES.index(p[1])]):
            return True
    return False


def _exposed(pillars: dict, el: int) -> bool:
    """某五行是否透干（日干不算）。"""
    return any(k != "day" and p and element_of(STEMS.index(p[0])) == el for k, p in pillars.items())


def determine(pillars: dict, instant_utc: datetime | None = None, strength: dict | None = None,
              tiaohou: dict | None = None, tiaohou_mode: str = "side") -> dict:
    """tiaohou_mode：side 调候不在忌一侧才取（默认）；off 不看调候；always 调候急且在盘即取。后两者只供校准比较。"""
    st = strength or strength_mod.assess(pillars)
    ds = STEMS.index(pillars["day"][0])
    day_el = element_of(ds)
    w = family_weights(st)
    strong = family_strong(st)
    ratio = st["ratio"]
    th = tiaohou or tiaohou_mod.present_in_chart(pillars, pillars["day"][0], pillars["month"][1], instant_utc)
    mb = pillars["month"][1]

    notes: list[str] = []
    bing: str | None = None
    damping = 1.0
    cong_ok_strong = not RULES["cong_strict"] or (w["官杀"] == 0 and not strong["财"])
    cong_ok_weak = not RULES["cong_strict"] or (w["印"] == 0 and not strong["比劫"])
    if ratio >= strength_mod.FOLLOW_STRONG_AT and cong_ok_strong:
        method, side = "从强", "从强"
        use = _argmax(w, ("比劫", "印"))
        reason = f"比值 {ratio}，生扶独旺，从强候选，用{use}顺其旺势（解读时复核）"
    elif ratio <= strength_mod.FOLLOW_WEAK_AT and cong_ok_weak:
        method, side = "从弱", "从弱"
        use = _argmax(w, ("官杀", "财", "食伤"))
        reason = f"比值 {ratio}，日主无力，从弱候选，从{use}（解读时复核）"
    else:
        method = "扶抑"
        if st["verdict"] == "中和":
            side = "身旺" if ratio >= 0.5 else "身弱"
            damping = DAMPING_ZHONGHE
            notes.append(f"中和临界盘，按比值 {ratio} 偏{side[-1]}论，解读时补判；preference 减半（damping {damping}）")
        else:
            side = st["verdict"]
            if st.get("note") in ("从强候选", "从弱候选"):
                notes.append(f"比值 {ratio} 已到{st['note'][:2]}一带，但{'官杀或财有力' if side == '身旺' else '印或比劫有根'}，不作从格，按{side}论")
        use, bing, reason = _fuyi(side, w, strong)

    # 扶抑一侧：lean[el] = +1 偏喜 / -1 偏忌
    lean: dict[int, int] = {}
    for f in FAMILIES:
        el = family_element(day_el, f)
        if side in ("身弱", "从强"):
            lean[el] = 1 if f in SUPPORT_F else -1
        else:
            lean[el] = 1 if f in DRAIN_F else -1
    if side == "从强":
        lean[family_element(day_el, "食伤")] = 1  # 专旺喜泄秀

    # 调候
    th_stems = [s for s in th.get("stems", []) if s in STEMS]
    th_el = element_of(STEMS.index(th_stems[0])) if th_stems else None
    urgent = th_el is not None and ((mb in WINTER and th_el == 1) or (mb in SUMMER and th_el == 4))
    present = th_el is not None and element_in_chart(pillars, th_el)
    adopted = False
    xi_extra: int | None = None
    use_el = family_element(day_el, use)
    bings = bing.split("+") if bing else []
    bing = bings[0] if bings else None
    bing_el = family_element(day_el, bing) if bing else None
    if method == "扶抑" and urgent and tiaohou_mode != "off":
        if th_el == use_el:
            reason += "，所取亦合调候"
            adopted = True
        elif th_el == bing_el:
            notes.append(f"调候之{WUXING[th_el]}正是病神，不取")
        elif (RULES["tiaohou_yield"] and present and tiaohou_mode != "always" and _exposed(pillars, use_el)
              and lean[th_el] > 0):
            notes.append(f"调候之{WUXING[th_el]}在盘中，扶抑所取{use}透干有力，扶抑为用，调候作喜神")
            xi_extra = th_el
        elif (present or (RULES["tiaohou_absent"] and lean[th_el] > 0)) and (lean[th_el] > 0 or tiaohou_mode == "always"):
            prev = use
            use = element_family(day_el, th_el)
            use_el = th_el
            adopted = True
            reason = (f"{'冬月寒' if mb in WINTER else '夏月燥'}，调候为急，{WUXING[th_el]}{'在盘中' if present else '盘中全无（待运引出）'}，"
                      f"取{WUXING[th_el]}（{use}）调候为用；扶抑原取{prev}")
        elif present:
            notes.append(f"调候之{WUXING[th_el]}在盘中，但在扶抑的忌一侧，仍用扶抑，调候作喜神候选")
        else:
            notes.append(f"调候急而{WUXING[th_el]}不在盘中，待运引出")

    roles = _roles(day_el, use_el, bing_el, lean)
    for extra in bings[1:]:
        el = family_element(day_el, extra)
        if el != use_el:
            roles[el] = "忌"
    if xi_extra is not None and roles[xi_extra] in ("闲", "仇"):
        roles[xi_extra] = "喜"
    if RULES["side_cap"] and side in ("身弱", "身旺"):
        for el in range(5):
            if el == use_el:
                continue
            if roles[el] == "喜" and lean[el] < 0 and el != xi_extra:
                roles[el] = "闲"
            elif roles[el] == "闲" and lean[el] > 0:
                roles[el] = "喜"
    pref: dict[str, float] = {}
    role_out: dict[str, str] = {}
    for el in range(5):
        r = roles[el]
        v = PREFERENCE[r]
        label = r
        if r == "闲":
            v = LEAN * lean[el]
            label = "闲（偏喜）" if lean[el] > 0 else "闲（偏忌）"
        pref[WUXING[el]] = round(v * damping, 3)
        role_out[WUXING[el]] = label
    return {
        "algorithm": "bazi-writing yongshen v1（自起草；子平扶抑病药为主，调候为辅，见模块文档）",
        "method": "调候" if adopted and method == "扶抑" and use_el == th_el and "调候为用" in reason else method,
        "side": side,
        "yong": {"element": WUXING[use_el], "family": element_family(day_el, use_el)},
        "bing": None if bing is None else {"element": WUXING[bing_el], "family": bing,
                                           "also": [{"element": WUXING[family_element(day_el, b)], "family": b} for b in bings[1:]]},
        "roles": role_out,
        "preference": pref,
        "damping": damping,
        "familyWeights": w,
        "tiaohou": {"stem": th_stems[0] if th_stems else None, "element": None if th_el is None else WUXING[th_el],
                    "urgent": urgent, "present": present, "adopted": adopted},
        "reason": reason,
        "notes": notes,
        "status": STATUS,
    }
