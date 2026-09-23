"""十神、地支藏干與取格（格局）——客戶端 lib/core/shishen.dart 的同構 Python 版。

客戶端算好格局隨請求上送，服務端以同一套規則復算校驗（不一致即拒絕請求），
並據此把十神、藏干與取格依據寫進 prompt——格局是查表就能定的東西，
不再交給模型現場推，杜絕同一命盤兩次報告一次正財格一次偏財格。

取格宗《子平真詮》月令取格法，2026-09-23 按徐評例盤改為「月令本格 + 變格」兩層，口徑見 determine_structure 文檔串。
透干只看年、月、時干；藏干為比劫者不作候選。

刻意不做人元司令分野（各書日數不一），只帶「節後第幾日」作事實。
兩邊金樣例：test_shishen.py ↔ test/shishen_test.dart，改規則須同改。
"""

from __future__ import annotations

from dataclasses import dataclass

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
WUXING = "木火土金水"

TEN_GODS_SAME = ("比肩", "食神", "偏财", "七杀", "偏印")
TEN_GODS_DIFF = ("劫财", "伤官", "正财", "正官", "正印")
TEN_GOD_NAMES = frozenset(TEN_GODS_SAME + TEN_GODS_DIFF)
STRUCTURE_NAMES = frozenset(
    {"建禄格", "月刃格", "月劫格"} | {f"{g}格" for g in TEN_GOD_NAMES if g not in ("比肩", "劫财")}
)

# 地支藏干（天干序）：本氣、中氣、餘氣
HIDDEN_STEMS: tuple[tuple[int, ...], ...] = (
    (9,),  # 子 癸
    (5, 9, 7),  # 丑 己癸辛
    (0, 2, 4),  # 寅 甲丙戊
    (1,),  # 卯 乙
    (4, 1, 9),  # 辰 戊乙癸
    (2, 6, 4),  # 巳 丙庚戊
    (3, 5),  # 午 丁己
    (5, 3, 1),  # 未 己丁乙
    (6, 8, 4),  # 申 庚壬戊
    (7,),  # 酉 辛
    (4, 7, 3),  # 戌 戊辛丁
    (8, 0),  # 亥 壬甲
)
LAYER_NAMES = ("本气", "中气", "余气")
ZAQI_LAYER_NAMES = ("本气", "余气", "墓库")  # 辰戌丑未：本气土、前一行之余气、所墓之五行（徐评论杂气）

# 十干祿位 / 陽干刃位（地支序；-1 為無）
LU_BRANCH = (2, 3, 5, 6, 5, 6, 8, 9, 11, 0)
REN_BRANCH = (3, -1, 6, -1, 6, -1, 9, -1, 0, -1)

# 三合局 [生, 中神, 墓] 與三會方 [孟, 仲, 季]，附五行序
COMBINATIONS: tuple[tuple[tuple[int, int, int], int, str], ...] = (
    ((8, 0, 4), 4, "三合"),
    ((11, 3, 7), 0, "三合"),
    ((2, 6, 10), 1, "三合"),
    ((5, 9, 1), 3, "三合"),
    ((2, 3, 4), 0, "三会"),
    ((5, 6, 7), 1, "三会"),
    ((8, 9, 10), 3, "三会"),
    ((11, 0, 1), 4, "三会"),
)

PILLAR_NAMES = {"year": "年", "month": "月", "day": "日", "hour": "时"}


def stem_index(ch: str) -> int:
    return STEMS.index(ch)


def branch_index(ch: str) -> int:
    return BRANCHES.index(ch)


def element_of(stem: int) -> int:
    return (stem % 10) // 2


def stem_label(stem: int) -> str:
    """「乙木」。"""
    return f"{STEMS[stem]}{WUXING[element_of(stem)]}"


def ten_god(day_stem: int, other: int) -> str:
    rel = (element_of(other) - element_of(day_stem)) % 5
    same = (day_stem % 2) == (other % 2)
    return (TEN_GODS_SAME if same else TEN_GODS_DIFF)[rel]


@dataclass(frozen=True)
class Structure:
    """取格结果。name 是变格后的格（会局、生地藏透变化之后），base 是月令本格（当旺之神所成之格，徐评归章所用）；
    两者多数相同，不同时 variation 说明变化路径（"会局"或"藏透"）；also 是杂气月兼透的兼用格。"""

    name: str
    basis: str
    base: str = ""
    variation: str | None = None
    also: list[str] | None = None  # 杂气兼透时的兼用格（"一透则一用，兼透则兼用"）


def _parse(pillar: str) -> tuple[int, int]:
    return stem_index(pillar[0]), branch_index(pillar[1])


# 月支三类：专气（子午卯酉）、生地（寅申巳亥）、杂气（辰戌丑未）。取格口径按类而异，见 determine_structure。
ZAQI_BRANCHES = frozenset({1, 4, 7, 10})
SHENGDI_BRANCHES = frozenset({2, 5, 8, 11})


def _month_structure(ds: int, mb: int, exposed: list[tuple[str, int]]) -> tuple[str, str, list[str]]:
    """月令本格：禄刃先；杂气月透干取之（本气先），不透以本气论；生地与专气月依本气当旺之神，不问透否。
    本气为比劫而无可取者归月劫格。返回 (格名, 依据, 兼用格列表)。"""
    hidden = HIDDEN_STEMS[mb]
    principal = hidden[0]
    mb_name = BRANCHES[mb]
    dm = stem_label(ds)
    if LU_BRANCH[ds] == mb:
        return "建禄格", f"月支{mb_name}为日主{dm}禄位，取建禄格", []
    if REN_BRANCH[ds] == mb:
        return "月刃格", f"月支{mb_name}为日主{dm}刃位，取月刃格", []
    hidden_desc = "、".join(stem_label(s) for s in hidden)
    if mb in ZAQI_BRANCHES:
        # 杂气按五行认透干（"甲生辰月，透壬为印"，辰为水库，壬癸皆算）；兼透则兼用，格名本气先、次官煞、次按藏干序
        found: list[tuple[int, int, str, str]] = []  # (layer, exposed_stem, god, pillar)
        for layer, stem in enumerate(hidden):
            for pillar, exposed_stem in exposed:
                if element_of(exposed_stem) != element_of(stem):
                    continue
                god = ten_god(ds, exposed_stem)
                if god in ("比肩", "劫财") or any(f[1] == exposed_stem for f in found):
                    continue
                found.append((layer, exposed_stem, god, pillar))
        if found:
            # 本气当旺者先（张参政造丙寅戊戌辛酉戊子，丙戊并透，徐评以印论）；余者官煞先（论正官首例壬戌丁未戊申乙卯，丁乙并透，徐评作杂气正官）
            found.sort(key=lambda f: (0 if f[0] == 0 else 1, 0 if f[2] in ("正官", "七杀") else 1, f[0]))
            layer, stem, god, pillar = found[0]
            desc = "、".join(f"{ZAQI_LAYER_NAMES[l]}{stem_label(st)}为{g}透于{PILLAR_NAMES[pl]}干" for l, st, g, pl in found)
            tail = f"，兼透兼用，取{god}格" if len(found) > 1 else f"，取{god}格"
            return f"{god}格", f"月令{mb_name}杂气，{desc}{tail}", [f"{g}格" for _, _, g, _ in found[1:]]
        god = ten_god(ds, principal)
        if god in ("比肩", "劫财"):
            return "月劫格", f"月令{mb_name}杂气，本气{stem_label(principal)}为{god}，余气不透，比劫不立格，取月劫格", []
        return f"{god}格", f"月令{mb_name}藏{hidden_desc}未透干，依本气{stem_label(principal)}取{god}格", []
    god = ten_god(ds, principal)
    if god in ("比肩", "劫财"):
        return "月劫格", f"月支{mb_name}本气{stem_label(principal)}为{god}当令，比劫不立格，取月劫格", []
    for pillar, exposed_stem in exposed:
        if exposed_stem == principal:
            return f"{god}格", f"月令{mb_name}本气{stem_label(principal)}为{god}，透于{PILLAR_NAMES[pillar]}干，取{god}格", []
    if len(hidden) == 1:
        return f"{god}格", f"月令{mb_name}藏{hidden_desc}未透干，依本气{stem_label(principal)}取{god}格", []
    return f"{god}格", f"月令{mb_name}本气{stem_label(principal)}为{god}当旺，未透干仍以当旺之神取{god}格", []


def determine_structure(
    year: str, month: str, day: str, hour: str | None
) -> Structure:
    """取格；返回格名（简体规范名）、月令本格与一句取格依据（入 prompt）。

    口径（2026-09-23 按《子平真诠评注》徐评例盘裁定，见 references/校核/格局_例盘报告.md）：
    1. 月令本格 base：禄刃先；杂气月（辰戌丑未）透干取之，本气先，皆不透以本气土论；
       生地（寅申巳亥）与专气（子午卯酉）依本气当旺之神，不问透否。本气比劫无可取者归月劫格。
       徐评八格章归章即按此，"先用当旺之神，次及得气之神，乃一定之次序"（论用神变化徐评）。
    2. 变格 name：禄刃劫不变；月支与另两支会成三合局或三会方（三支齐全）且局之五行非日主同气，随局取格，
       局之五行透干者取透干十神，未透以中神论（"寅午戌三合变化在前"）；生地月本气不透而中气余气透干，
       舍本气而用透者（"不透甲而透丙，则同知得以作主"）。杂气与专气的变格即本格。
    成败救应条件按 name 查表，base 不同时一并带出，解读层看徐评"变而不失本格"之意自定。"""
    ys, yb = _parse(year)
    ms, mb = _parse(month)
    ds, db = _parse(day)
    hs_hb = _parse(hour) if hour else None

    hidden = HIDDEN_STEMS[mb]
    principal = hidden[0]
    mb_name = BRANCHES[mb]

    exposed: list[tuple[str, int]] = [("month", ms)]
    if hs_hb is not None:
        exposed.append(("hour", hs_hb[0]))
    exposed.append(("year", ys))

    base, base_basis, also = _month_structure(ds, mb, exposed)
    if base in ("建禄格", "月刃格", "月劫格"):
        # 禄刃劫"皆以透干支，别取财官煞食为用"，格不因透干会支而改（论建禄月劫）
        return Structure(base, base_basis, base, None, also)

    branches = {yb, mb, db}
    if hs_hb is not None:
        branches.add(hs_hb[1])
    for combo, element, kind in COMBINATIONS:
        if mb not in combo or not all(b in branches for b in combo):
            continue
        if element == element_of(ds):
            continue  # 同氣成局歸旺衰論
        others = "".join(BRANCHES[b] for b in combo if b != mb)
        combo_desc = f"月支{mb_name}与{others}{kind}成{WUXING[element]}局"
        for pillar, stem in exposed:
            if element_of(stem) != element:
                continue
            god = ten_god(ds, stem)
            return Structure(
                f"{god}格",
                f"{base_basis}；{combo_desc}，{stem_label(stem)}透于{PILLAR_NAMES[pillar]}干为{god}，随局变格取{god}格",
                base, "会局", also,
            )
        core = HIDDEN_STEMS[combo[1]][0]
        god = ten_god(ds, core)
        return Structure(
            f"{god}格",
            f"{base_basis}；{combo_desc}，{WUXING[element]}未透干，以局中{stem_label(core)}论{god}，随局变格取{god}格",
            base, "会局", also,
        )

    if mb in SHENGDI_BRANCHES and not any(stem == principal for _, stem in exposed):
        for layer, stem in enumerate(hidden[1:], start=1):
            god = ten_god(ds, stem)
            if god in ("比肩", "劫财"):
                continue
            for pillar, exposed_stem in exposed:
                if exposed_stem != stem:
                    continue
                return Structure(
                    f"{god}格",
                    f"{base_basis}；本气不透而{LAYER_NAMES[layer]}{stem_label(stem)}透于{PILLAR_NAMES[pillar]}干为{god}，舍本气而用透者，变格取{god}格",
                    base, "藏透", also,
                )
    return Structure(base, base_basis, base, None, also)


def ten_god_lines(year: str, month: str, day: str, hour: str | None) -> list[str]:
    """prompt 用：天干十神一行、地支藏干一行。"""
    ds = stem_index(day[0])
    pillars = [("year", year), ("month", month), ("day", day)]
    if hour:
        pillars.append(("hour", hour))

    stems = []
    for key, pillar in pillars:
        s = stem_index(pillar[0])
        label = "日主" if key == "day" else ten_god(ds, s)
        stems.append(f"{PILLAR_NAMES[key]}干{stem_label(s)}{label}")

    branches = []
    for key, pillar in pillars:
        b = branch_index(pillar[1])
        parts = "、".join(f"{stem_label(s)}{ten_god(ds, s)}" for s in HIDDEN_STEMS[b])
        branches.append(f"{PILLAR_NAMES[key]}支{BRANCHES[b]}藏{parts}")

    return [
        "天干十神：" + "，".join(stems),
        "地支藏干（附对日主十神）：" + "；".join(branches),
    ]
