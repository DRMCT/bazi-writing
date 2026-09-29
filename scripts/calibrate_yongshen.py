#!/usr/bin/env python3
"""用神判定校准：以徐乐吾在两套例盘里明说的用神为标准。

    python scripts/calibrate_yongshen.py gold    → 从两套例盘夹具抽徐评明说的用神，写 calibration/yongshen_gold.json
    python scripts/calibrate_yongshen.py score   → 读金标准，跑 yongshen.determine，统计一致率，写 references/校核/用神_例盘报告.md
    python scripts/calibrate_yongshen.py sheet   → 旺衰校准的 120 盘样本摊成三份用神判定单（含调候表，不含任何强弱与用神结论），交 Fable 子代理
    python scripts/calibrate_yongshen.py fable   → 读 calibration/yongshen_verdicts.{1,2,3}.json，统计用神与五行喜忌方向的一致率
    python scripts/calibrate_yongshen.py rules   → 规则开关逐组合比较两路一致率
    python scripts/calibrate_yongshen.py report  → 写 references/校核/用神_例盘报告.md（calibration/ 不入库，报告自成一体）

两路标准（与旺衰校准同法，DESIGN-命盘层 2.4）：徐评例盘是古籍标准，但徐在八格章里说的"用神"常指格局用神（月令之神），
与本模块要的扶抑用神不全是一回事，穷通例盘则多是调候表本身；随机样本走 Fable 子代理独立判定，作现代标准。

金标准的抽法：夹具的徐评（子平）与按语、判词（穷通）里，找"用神在X""以X为用""取X为用""用X"一类句子，
X 是十神（印、劫、食伤、财、官煞……）、天干、五行或"某支中某干"，按日主换成五行类（比劫、食伤、财、官杀、印）。
假设句（本当、本可、若）与否定句（不用、不可为用、岂可为用）剔除；"用神在/为X"优先于"以X为用"，后者优先于"用X"。
X 带动作的（"取财损印""用印化煞""取食神制煞"），用神取施动的一方。兼用（"兼用财印""印劫"）记成集合，判定落在集合里即算中。
正则抽不准的盘在 OVERRIDES 里逐盘改写或剔除，理由写在旁边。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bazi_core.shishen import STEMS, WUXING, element_of  # noqa: E402

FIX = Path(__file__).resolve().parent / "bazi_core" / "tests" / "fixtures"
OUT = Path("calibration")

FAMILIES = ("比劫", "食伤", "财", "官杀", "印")  # 与日主五行之差 0..4

_GOD_WORDS = [
    ("印绶", "印"), ("正印", "印"), ("偏印", "印"), ("枭神", "印"), ("枭", "印"), ("印", "印"),
    ("劫财", "比劫"), ("比劫", "比劫"), ("比肩", "比劫"), ("阳刃", "比劫"), ("羊刃", "比劫"), ("劫", "比劫"), ("禄", "比劫"), ("刃", "比劫"),
    ("食神", "食伤"), ("伤官", "食伤"), ("食伤", "食伤"), ("伤食", "食伤"), ("泄秀", "食伤"), ("食", "食伤"), ("伤", "食伤"),
    ("财星", "财"), ("正财", "财"), ("偏财", "财"), ("财", "财"),
    ("正官", "官杀"), ("官星", "官杀"), ("官煞", "官杀"), ("官杀", "官杀"), ("七煞", "官杀"), ("七杀", "官杀"), ("偏官", "官杀"),
    ("煞", "官杀"), ("杀", "官杀"), ("官", "官杀"),
]
_GOD_RE = "|".join(re.escape(w) for w, _ in _GOD_WORDS)
_GOD_MAP = dict(_GOD_WORDS)
_POS = r"(?:[年月日时]上|[年月日时]干|[子丑寅卯辰巳午未申酉戌亥](?:中|宫|内)|月令|支中|透出之?)?"
_ATOM = rf"(?:[甲乙丙丁戊己庚辛壬癸][木火土金水]?|[子丑寅卯辰巳午未申酉戌亥][木火土金水]|[木火土金水](?![气局])|{_GOD_RE})"
# 目标：一个或两个原子并列（"财印""印劫""庚金之财"取首个原子）
_TARGET = rf"{_POS}(?P<t>{_ATOM})(?P<t2>{_ATOM})?"

_NEG_BEFORE = re.compile(r"(不|非|无|岂|弃|难|未|莫|勿|忌|恶|怕|畏|破|坏|伤|去|本当|本可|若|如|虽|可以|亦可)$")
_NEG_CLAUSE = re.compile(r"不能为用|不可为用|非可为用|岂可为用|不作.*用|无用|置之不用|不用|破用|害用|伤用|用神太|用神被|用神受|用神不|失其用")

_VERB = "制化损泄生扶帮抑破去合护滋克伤夺冲助培"
_AGENT = rf"(?<![{_VERB}])"
_FORMULA = r"(?:财旺|财多|身弱|身旺|身强|身轻|煞重|杀重|印旺|印多|印重|伤官|食神|日元旺|劫重|比劫重|伤重)"

_PATTERNS = [
    # 优先级 1：用神在/为/专取 X；X 用神
    (1, re.compile(rf"用神(?:专取|仍在|虽在|即在|在|为|是|取|乃)(?:[^，。；：]{{0,2}}?){_TARGET}")),
    (1, re.compile(rf"{_AGENT}{_TARGET}用神(?![太被受不伤])")),
    # 优先级 2：以/取 X ……为用神；X 为用神
    (2, re.compile(rf"(?:以|取|专取|当以|固当以|仍当以|乃以|是以|完全以|故以)(?:[^，。；：]{{0,2}}?){_TARGET}[^，。；：]{{0,10}}?为用神")),
    (2, re.compile(rf"{_AGENT}{_TARGET}[^，。；：]{{0,6}}?为用神")),
    # 优先级 3：以/取/专用 X ……为用；财旺用印一类套语；弃 X 用 Y
    (3, re.compile(rf"(?:以|取|专取|当以|固当以|仍当以|乃以|是以|完全以|故以)(?:[^，。；：]{{0,2}}?){_TARGET}[^，。；：]{{0,10}}?(?:取用|为用)")),
    (3, re.compile(rf"(?:专用|兼用|重用|只能用|须用|宜用|当用|即用|仍用|故用|乃用|而用|亦用|是用)(?:[^，。；：]{{0,2}}?){_TARGET}")),
    (3, re.compile(rf"{_FORMULA}用{_TARGET}")),
    (3, re.compile(rf"(?:弃|舍)[^，。；：]{{1,3}}用{_TARGET}")),
    (3, re.compile(rf"{_AGENT}{_TARGET}[^，。；：]{{0,6}}?为用(?!神)")),
    # 优先级 4：用 X（句首或虚词后）
    (4, re.compile(rf"(?:^|故|乃|则|而|亦|是|须|宜|当|只|谓)用(?P<pre>[^，。；：]{{0,2}}?){_TARGET}")),
]


def _family(atom: str, dm_el: int) -> str | None:
    if atom in _GOD_MAP:
        return _GOD_MAP[atom]
    ch = atom[0]
    if ch in STEMS:
        el = element_of(STEMS.index(ch))
    elif ch in WUXING:
        el = WUXING.index(ch)
    elif len(atom) >= 2 and atom[1] in WUXING:
        el = WUXING.index(atom[1])
    else:
        return None
    return FAMILIES[(el - dm_el) % 5]


def extract(text: str, dm_stem: str) -> dict | None:
    """一段徐评或按语 → {"families": [...], "phrase": ..., "priority": n}；找不到返回 None。"""
    dm_el = element_of(STEMS.index(dm_stem))
    best = None
    for clause in re.split(r"[，。；：？！]", text):
        if not clause or _NEG_CLAUSE.search(clause) and not re.search(r"用神(?:专取|在|为)", clause):
            continue
        for prio, pat in _PATTERNS:
            for m in pat.finditer(clause):
                head = clause[: m.start()]
                if _NEG_BEFORE.search(head[-3:] if len(head) >= 3 else head):
                    continue
                fams = []
                for key in ("t", "t2"):
                    a = m.group(key)
                    if a:
                        f = _family(a, dm_el)
                        if f and f not in fams:
                            fams.append(f)
                if not fams:
                    continue
                cand = {"families": fams, "phrase": m.group(0).strip("，。；： "), "priority": prio}
                if best is None or prio < best["priority"]:
                    best = cand
    return best


# 正则抽不准的盘逐盘改写（families 为 None 即剔除），理由写在旁边。键为夹具 id。
OVERRIDES: dict[str, dict] = {
    "子平八-04": {"families": ["食伤"], "phrase": "辰中乙木余气透干，用以泄日元之秀", "why": "用以泄秀，所用为乙木伤官"},
    "子平八-08": {"families": ["官杀"], "phrase": "年上乙木微弱，乃用神太弱而扶之也", "why": "用神即年上乙木七杀"},
    "子平八-14": {"families": ["官杀"], "phrase": "气偏于木，从其旺势为用……为从煞格也", "why": "从煞格，从木"},
    "子平八-18": {"families": ["食伤"], "phrase": "火金相战，取土通关为富格", "why": "通关之土为丁火之食伤"},
    "子平九-08": {"families": ["官杀"], "phrase": "时透七煞，制刃为用", "why": "制刃者为时上丙火七煞，刃是被制者"},
    "子平二十一-03": {"families": ["食伤"], "phrase": "徐为文臣，用食生财", "why": "用煞为权说的是袁造，本造用食"},
    "子平二十一-04": {"families": None, "why": "评语言年戊日甲，与所附四柱不合，判词错配"},
    "子平三十四-02": {"families": ["食伤"], "phrase": "丁火官星，合壬用神", "why": "用神为壬水食神"},
    "子平三十六-01": {"families": ["食伤"], "phrase": "当以金水伤官取用", "why": "金水伤官是格名，所用为伤官"},
    "子平三十六-13": {"families": ["食伤"], "phrase": "使癸水用神不伤", "why": "用神为癸水食神"},
    "子平四十二-04": {"families": ["印"], "phrase": "兼制伤扶身与调和气候二者之用", "why": "制伤扶身又调候者为壬水偏印"},
    "子平四十二-08": {"families": ["官杀"], "phrase": "夏月火土，非用水润土，调和气候不可", "why": "用壬水七煞调候"},
    "子平四十六-09": {"families": ["食伤"], "phrase": "子水者，取以调候，非以为用也", "why": "木火通明，用丙火食神"},
    "子平四十六-12": {"families": ["食伤"], "phrase": "取食神制煞耳……身强以制为用耳", "why": "用丙火食神制煞"},
    "子平四十八-11": {"families": ["比劫", "印"], "phrase": "势象偏于土金，宜土金水运", "why": "从旺，土金为用"},
}


def gold_cases() -> list[dict]:
    out = []
    zp = json.loads((FIX / "ziping_lipan.json").read_text(encoding="utf-8"))
    for c in zp["cases"]:
        p = c["pillars"]
        if len(p) < 4 or any(len(x) != 2 for x in p):
            continue
        pillars = {"year": p[0], "month": p[1], "day": p[2], "hour": p[3]}
        g = extract(c.get("comment") or "", p[2][0])
        out.append({"id": "子平" + c["id"], "book": "子平", "pillars": pillars, "text": c.get("comment") or "", "gold": g})
    qt = json.loads((FIX / "qiongtong_lipan.json").read_text(encoding="utf-8"))
    for c in qt["cases"]:
        p = c["pillars"]
        if not all(p.get(k) and len(p[k]) == 2 for k in ("year", "month", "day", "hour")):
            continue
        text = "。".join((c.get("note") or []) + (c.get("judgment") or []))
        g = extract(text, p["day"][0])
        out.append({"id": "穷通" + c["id"], "book": "穷通", "pillars": dict(p), "text": text, "gold": g})
    for x in out:
        if x["id"] in OVERRIDES:
            ov = OVERRIDES[x["id"]]
            x["gold"] = None if ov.get("families") is None else {"families": ov["families"], "phrase": ov.get("phrase", ""), "priority": 0}
            x["override"] = ov.get("why", "")
    return [x for x in out if x["gold"]]


def cmd_gold() -> int:
    cases = gold_cases()
    OUT.mkdir(exist_ok=True)
    (OUT / "yongshen_gold.json").write_text(json.dumps(cases, ensure_ascii=False, indent=1), encoding="utf-8")
    by_book: dict[str, int] = {}
    for c in cases:
        by_book[c["book"]] = by_book.get(c["book"], 0) + 1
    print(f"金标准 {len(cases)} 盘：{by_book}")
    return 0


def _run(cases: list[dict], mode: str) -> list[dict]:
    from bazi_core import yongshen
    out = []
    for c in cases:
        r = yongshen.determine(c["pillars"], tiaohou_mode=mode)
        out.append({"id": c["id"], "book": c["book"], "hit": r["yong"]["family"] in c["gold"]["families"],
                    "got": r["yong"]["family"], "gold": c["gold"]["families"], "method": r["method"], "side": r["side"],
                    "urgent": r["tiaohou"]["urgent"], "r": r, "c": c})
    return out


def _rate(rows: list[dict]) -> str:
    n = len(rows)
    k = sum(r["hit"] for r in rows)
    return f"{k}/{n}（{k / n:.0%}）" if n else "0/0"


def cmd_score(write: bool = True) -> int:
    cases = gold_cases()
    lines = []
    for mode in ("side", "off", "always"):
        rows = _run(cases, mode)
        zp = [r for r in rows if r["book"] == "子平"]
        qt = [r for r in rows if r["book"] == "穷通"]
        lines.append(f"{mode:6s} 子平 {_rate(zp)}  穷通 {_rate(qt)}  调候急盘 子平 {_rate([r for r in zp if r['urgent']])} 穷通 {_rate([r for r in qt if r['urgent']])}")
    print(chr(10).join(lines))
    rows = _run(cases, "side")
    for book in ("子平", "穷通"):
        br = [r for r in rows if r["book"] == book]
        for key in ("side", "method"):
            groups: dict[str, list] = {}
            for r in br:
                groups.setdefault(r[key], []).append(r)
            print(book, key, "  ".join(f"{g} {_rate(v)}" for g, v in sorted(groups.items())))
        conf: dict[tuple, int] = {}
        for r in br:
            if not r["hit"]:
                conf[("/".join(r["gold"]), r["got"])] = conf.get(("/".join(r["gold"]), r["got"]), 0) + 1
        print(book, "错配（徐→判）", sorted(conf.items(), key=lambda x: -x[1])[:12])
    return 0


SHEET_HEAD = [
    "# 用神判定单（第 {part} 份，共 3 份）",
    "",
    "每盘只给四柱、查表事实与调候表，不给任何强弱或用神结论。请逐盘先判身强弱，再定用神（一个五行），",
    "并把五行各标「用 / 喜 / 闲 / 忌」之一（用只有一个；喜是用神之外对命局有利的，忌是不利的，闲是可有可无的）。",
    "口径：子平为主（扶抑、病药、通关、格局相神），调候为辅；寒暖燥湿失衡到急的盘可以取调候为用。",
    "从格、专旺只在确实成立时判，判了在 method 里写明。调候表一栏是《穷通宝鉴》按日主与月令查得的调候用神（本项目校核定稿），只是事实，不是结论。",
    "把结论写成 JSON，存 {path}：",
    '{{"S001": {{"strength": "身弱", "yong": "水", "roles": {{"木": "喜", "火": "忌", "土": "忌", "金": "闲", "水": "用"}}, "method": "扶抑", "reason": "一两句"}}, ...}}',
    "method 取 扶抑、病药、通关、调候、从格、专旺 之一。",
    "",
]


def cmd_sheet() -> int:
    from calibrate_strength import facts
    from bazi_core import tiaohou
    samples = json.loads((OUT / "samples.json").read_text(encoding="utf-8"))
    cn = {"year": "年", "month": "月", "day": "日", "hour": "时"}
    for part in range(3):
        path = OUT / f"yongshen_verdicts.{part + 1}.json"
        lines = [x.format(part=part + 1, path=path) for x in SHEET_HEAD]
        for s in samples[part * 40:(part + 1) * 40]:
            p = s["pillars"]
            f = facts(p)
            th = tiaohou.lookup(p["day"][0], p["month"][1])
            slots = "；".join("或".join(x) for x in th["slots"])
            lines.append(f"## {s['id']}  {p['year']} {p['month']} {p['day']} {p['hour']}")
            lines.append(f"- 日主：{s['dayMaster']}，生于{s['monthBranch']}月")
            lines.append(f"- 天干十神：{'，'.join(f'{cn[k]}干{v}' for k, v in f['天干十神'].items())}")
            lines.append(f"- 地支藏干：{'；'.join(f'{cn[k]}支藏{v}' for k, v in f['地支藏干'].items())}")
            lines.append(f"- 地支关系：{'，'.join(f['地支关系'])}")
            lines.append(f"- 调候表：{slots}" + (f"（按节气分段：{'、'.join(th['periods'])}，此处取中气后一段）" if th["periods"] else ""))
            lines.append("")
        (OUT / f"yongshen_sheet.{part + 1}.md").write_text(chr(10).join(lines), encoding="utf-8")
    print(f"{len(samples)} 盘 → {OUT}/yongshen_sheet.{{1,2,3}}.md")
    return 0


def _sign(label: str) -> int:
    return 1 if label.startswith(("用", "喜")) else -1 if label.startswith(("忌", "仇")) else 0


def cmd_fable() -> int:
    from bazi_core import yongshen
    samples = {s["id"]: s for s in json.loads((OUT / "samples.json").read_text(encoding="utf-8"))}
    verdicts: dict[str, dict] = {}
    for part in (1, 2, 3):
        f = OUT / f"yongshen_verdicts.{part}.json"
        if f.exists():
            verdicts.update(json.loads(f.read_text(encoding="utf-8")))
    n = hit = sign_ok = sign_n = strict = 0
    rows = []
    for sid, v in sorted(verdicts.items()):
        r = yongshen.determine(samples[sid]["pillars"])
        n += 1
        ok = r["yong"]["element"] == v["yong"]
        hit += ok
        agree = sum(_sign(r["roles"][e]) == _sign(v["roles"].get(e, "闲")) for e in "木火土金水")
        sign_ok += agree
        sign_n += 5
        strict += agree == 5
        rows.append((sid, ok, agree, r, v))
    print(f"Fable 标准 {n} 盘：用神五行一致 {hit}/{n}（{hit / max(n, 1):.0%}）；五行喜忌方向逐项一致 {sign_ok}/{sign_n}（{sign_ok / max(sign_n, 1):.0%}），五项全同 {strict}/{n}")
    for sid, ok, agree, r, v in rows:
        if not ok:
            print(sid, "".join(samples[sid]["pillars"].values()), "子代理", v["strength"], v["yong"], v["method"], "| 判", r["side"], r["yong"]["element"], r["method"], "|", v["reason"][:60], "|", r["reason"][:50])
    return 0


def cmd_rules() -> int:
    """规则开关逐组合比较：徐评子平例盘与 Fable 判定两路一致率。"""
    import itertools
    from bazi_core import yongshen
    gold = [c for c in gold_cases() if c["book"] == "子平"]
    samples = {s["id"]: s for s in json.loads((OUT / "samples.json").read_text(encoding="utf-8"))}
    verdicts: dict[str, dict] = {}
    for part in (1, 2, 3):
        f = OUT / f"yongshen_verdicts.{part}.json"
        if f.exists():
            verdicts.update(json.loads(f.read_text(encoding="utf-8")))
    keys = list(yongshen.RULES)
    saved = dict(yongshen.RULES)
    for combo in itertools.product((False, True), repeat=len(keys)):
        yongshen.RULES.update(dict(zip(keys, combo)))
        zp = sum(yongshen.determine(c["pillars"])["yong"]["family"] in c["gold"]["families"] for c in gold)
        fb = sum(yongshen.determine(samples[k]["pillars"])["yong"]["element"] == v["yong"] for k, v in verdicts.items())
        sg = 0
        for k, v in verdicts.items():
            r = yongshen.determine(samples[k]["pillars"])
            sg += sum(_sign(r["roles"][e]) == _sign(v["roles"].get(e, "闲")) for e in "木火土金水")
        flag = " ".join(f"{k}={'开' if on else '关'}" for k, on in zip(keys, combo))
        print(f"{flag}  子平 {zp}/{len(gold)}  Fable 用神 {fb}/{len(verdicts)}  喜忌方向 {sg}/{5 * len(verdicts)}")
    yongshen.RULES.update(saved)
    return 0


REPORT = Path("references/校核/用神_例盘报告.md")


def _load_verdicts() -> dict[str, dict]:
    verdicts: dict[str, dict] = {}
    for part in (1, 2, 3):
        f = OUT / f"yongshen_verdicts.{part}.json"
        if f.exists():
            verdicts.update(json.loads(f.read_text(encoding="utf-8")))
    return verdicts


def cmd_report() -> int:
    import itertools
    from bazi_core import yongshen
    cases = gold_cases()
    zp_rows = [r for r in _run(cases, "side") if r["book"] == "子平"]
    qt_rows = [r for r in _run(cases, "side") if r["book"] == "穷通"]
    samples = {x["id"]: x for x in json.loads((OUT / "samples.json").read_text(encoding="utf-8"))}
    verdicts = _load_verdicts()
    L = ["# 用神判定校准报告", "",
         "由 `scripts/calibrate_yongshen.py report` 生成。模块 scripts/bazi_core/yongshen.py，口径见 DESIGN-命盘层 2.5。", ""]
    L += ["## 规则开关", "", "| 开关 | 现值 |", "|---|---|"]
    for k, v in yongshen.RULES.items():
        L.append(f"| {k} | {'开' if v else '关'} |")
    L += ["", "逐组合比较（子平金标准用神类一致 / Fable 用神五行一致 / Fable 五行喜忌方向逐项一致）：", "",
          "| " + " | ".join(yongshen.RULES) + " | 子平 | Fable 用神 | 喜忌方向 |", "|" + "---|" * (len(yongshen.RULES) + 3)]
    keys = list(yongshen.RULES)
    saved = dict(yongshen.RULES)
    for combo in itertools.product((False, True), repeat=len(keys)):
        yongshen.RULES.update(dict(zip(keys, combo)))
        zp = sum(yongshen.determine(c["pillars"])["yong"]["family"] in c["gold"]["families"] for c in cases if c["book"] == "子平")
        fb = sg = 0
        for k, v in verdicts.items():
            r = yongshen.determine(samples[k]["pillars"])
            fb += r["yong"]["element"] == v["yong"]
            sg += sum(_sign(r["roles"][e]) == _sign(v["roles"].get(e, "闲")) for e in "木火土金水")
        mark = "（现值）" if dict(zip(keys, combo)) == saved else ""
        L.append("| " + " | ".join("开" if x else "关" for x in combo) + f" | {zp}/{len(zp_rows)} | {fb}/{len(verdicts)} | {sg}/{5 * len(verdicts)}{mark} |")
    yongshen.RULES.update(saved)
    zp_hit = sum(r["hit"] for r in zp_rows)
    qt_hit = sum(r["hit"] for r in qt_rows)
    L += ["", "## 古籍标准：徐评明说的用神", "",
          f"- 子平例盘（《子平真诠评注》徐评，人工核过）：{zp_hit}/{len(zp_rows)}（{zp_hit / len(zp_rows):.0%}）。",
          f"- 穷通例盘（《穷通宝鉴评注》按语，正则抽取）：{qt_hit}/{len(qt_rows)}（{qt_hit / len(qt_rows):.0%}）。穷通例盘的用神多是调候表本身，只作参考。",
          "- 徐在八格章里说的用神常指格局用神（月令之神），与扶抑用神不全同，这是子平一路的天花板。", "",
          "子平例盘未中的盘（徐评原话 → 本模块所取与理由）：", "",
          "| 编号 | 四柱 | 徐评 | 徐取 | 本模块 | 理由 |", "|---|---|---|---|---|---|"]
    for r in zp_rows:
        if not r["hit"]:
            y = r["r"]
            L.append(f"| {r['id']} | {' '.join(r['c']['pillars'].values())} | {r['c']['gold']['phrase']} | {'/'.join(r['gold'])} | {r['got']} | {y['reason']} |")
    if verdicts:
        n = len(verdicts)
        rows = []
        fb = sg = 0
        for k, v in sorted(verdicts.items()):
            r = yongshen.determine(samples[k]["pillars"])
            ok = r["yong"]["element"] == v["yong"]
            agree = sum(_sign(r["roles"][e]) == _sign(v["roles"].get(e, "闲")) for e in "木火土金水")
            fb += ok
            sg += agree
            rows.append((k, ok, agree, r, v))
        by_method: dict[str, list[bool]] = {}
        for k, ok, agree, r, v in rows:
            by_method.setdefault(v.get("method", "?"), []).append(ok)
        L += ["", "## 子代理标准：Fable 独立判定", "",
              f"旺衰校准的 120 盘（十日主乘十二月支）分三份交 Fable 子代理，判定单只给四柱、查表事实与调候表，不给任何强弱与用神结论。",
              f"- 用神五行一致 {fb}/{n}（{fb / n:.0%}）；五行喜忌方向逐项一致 {sg}/{5 * n}（{sg / (5 * n):.0%}）。",
              "- 按子代理所用方法：" + "；".join(f"{m} {sum(x)}/{len(x)}" for m, x in sorted(by_method.items())) + "。", "",
              "未中的盘：", "", "| 盘 | 四柱 | 子代理 | 本模块 | 子代理理由 | 本模块理由 |", "|---|---|---|---|---|---|"]
        for k, ok, agree, r, v in rows:
            if not ok:
                p = samples[k]["pillars"]
                L.append(f"| {k} | {' '.join(p.values())} | {v['strength']}，{v['yong']}（{v.get('method', '')}） | {r['side']}，{r['yong']['element']}（{r['method']}） | {v.get('reason', '')} | {r['reason']} |")
    REPORT.write_text(chr(10).join(L) + chr(10), encoding="utf-8")
    print(f"→ {REPORT}")
    return 0


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = argv[0] if argv else "gold"
    if cmd == "gold":
        return cmd_gold()
    if cmd == "score":
        return cmd_score()
    if cmd == "sheet":
        return cmd_sheet()
    if cmd == "fable":
        return cmd_fable()
    if cmd == "rules":
        return cmd_rules()
    if cmd == "report":
        return cmd_report()
    if cmd == "miss":
        book = argv[1] if len(argv) > 1 else "子平"
        for r in _run(gold_cases(), "side"):
            if r["book"] == book and not r["hit"]:
                y = r["r"]
                print(r["id"], "".join(r["c"]["pillars"].values()), "徐", "/".join(r["gold"]), "判", r["got"], "|", y["side"], y["familyWeights"], "|", y["reason"], "|", r["c"]["gold"]["phrase"])
        return 0
    if cmd == "dump":
        for c in gold_cases():
            g = c["gold"]
            print(c["id"], "".join(c["pillars"].values()), "/".join(g["families"]), g["priority"], "|", g["phrase"])
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
