#!/usr/bin/env python3
"""校核卡「忌句」与公式比对（校核 README：忌句由脚本与公式比对，一致的不进机器表，不一致的作例外保留）。

    python scripts/compare_avoid.py            → 写报告 references/校核/调候_忌句比对.md
    python scripts/compare_avoid.py --check    → 只打印摘要

公式：以卡的主序用神 U（各节气段首选天干之并集，「比劫」换算成日主同五行二干）为准，
    克用神 K = 五行克 U 者；合去用神 H = 与 U 天干相合者（甲己、乙庚、丙辛、丁壬、戊癸）；
    缺用神 = 「无/乏/不见 U」。
忌句每句抽出提到的干（含「一派」「多」「透」「见」「支成某局」与十神名换算）：
    - 提到 K 或 H 的：公式可推（克用神 / 合用神），不进表；
    - 只说缺 U 的：公式可推（缺用神），不进表；
    - 提到的只是 U 本身（用神过多、争合）：例外，进表 kind=用神过多；
    - 提到别的干（泄用神、比劫夺财、印星、局等）：例外，进表 kind=其他；
    - 一个干都抽不出的（「运入西南」「不得寅时」）：无法解析，只进报告，人读。
例外写进 tiaohou.json 的 avoidExceptions（build_tiaohou.py 调本模块），每项带原句。
例外 51 句由主会话逐句过了一遍（2026-09-23，作者授权），裁定写在 RULINGS：剔除的不进表（判定改「人工剔除」），
改依据的保留原句只换依据。剔除三类：合去用神（公式已推）、从化判词、正面判词。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_cards import parse_cards  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "references" / "校核"
TABLE = ROOT / "scripts" / "bazi_core" / "tables" / "tiaohou.json"
REPORT = CARDS / "调候_忌句比对.md"

STEMS = "甲乙丙丁戊己庚辛壬癸"
ELEM = "木木火火土土金金水水"
ELEMENTS = "木火土金水"
KE = {"木": "土", "火": "金", "土": "水", "金": "木", "水": "火"}          # 我克
COMBINE = {"甲": "己", "己": "甲", "乙": "庚", "庚": "乙", "丙": "辛", "辛": "丙", "丁": "壬", "壬": "丁", "戊": "癸", "癸": "戊"}
STEMS_OF = {e: [s for s in STEMS if ELEM[STEMS.index(s)] == e] for e in ELEMENTS}
TRIO = {"申子辰": "水", "寅午戌": "火", "巳酉丑": "金", "亥卯未": "木", "亥子丑": "水", "巳午未": "火", "申酉戌": "金", "寅卯辰": "木"}
# 十神 → 与日主的五行关系（0 同 1 我生 2 我克 3 克我 4 生我）
TEN_GOD_REL = {"比肩": 0, "劫财": 0, "比劫": 0, "劫": 0, "食神": 1, "伤官": 1, "食伤": 1, "食": 1, "伤": 1,
               "财": 2, "正财": 2, "偏财": 2, "财星": 2, "官": 3, "煞": 3, "杀": 3, "七煞": 3, "七杀": 3, "官煞": 3, "官杀": 3, "官星": 3,
               "印": 4, "枭": 4, "印绶": 4, "正印": 4, "偏印": 4, "枭印": 4}
SEQ = "木火土金水"

X = "[甲乙丙丁戊己庚辛壬癸]"
XS = f"{X}+"
E = "[金木水火土]"
EE = f"{E}{E}?"
SUFFIX = r"(?:多|重重|叠叠|太多|太旺|太重|出干|透干|透出|一透|透|出|旺|司权|司令|当权|得地|贪合|两困|离乱|合|克|伤|制|困|破|夺|混|杂|晦|泄|争|之烁|俱|忌)"
# (正则, 类别)；类别 absent 表示「无」，其余都算「出现」。「癸水」「戊土」这类干后带五行字的，五行字可有可无。
PATTERNS = [
    (rf"(?:无|乏|不见|缺|少|不得|不透|无有)(?:一点|滴|一)?({XS})", "absent"),
    (rf"(?:时月出|月时出|干出|出)({XS})", "present"),
    (rf"({XS}{E}?(?:[，、]{XS}{E}?)*)[，、]?不宜(?:取用|用)", "present"),
    (rf"({XS}){E}?(?:不透|不出|不见|不显|无|俱无)", "absent"),
    (rf"(?:无|乏|不见|缺)({EE})(?!局)", "element_absent"),
    (rf"(?:一派|一片|满局|多见|重见|重重|叠叠|太多|太旺|太重|多|二|两|三|四柱|干透|透出|出干|见|有|逢|遇|用|取|忌)({XS})", "present"),
    (rf"({XS}){E}?{SUFFIX}", "present"),
    (rf"支(?:成|会|全|见|中|逢)?({E})局|({E})局", "trio"),
    (rf"(?:一派|多|重|旺|盛|多见|重见|满局|见|逢|忌|有)({EE})(?!局)", "element"),
    (rf"({EE})(?:多|重|旺|盛|太过|太多|为病|司权|当权|重重|叠叠|出干|出|透|厚|埋|乡)", "element"),
]
# 句首的标签与引书残片
LABEL = re.compile(r"^[（(][^）)]*[）)]|^[”\"]+")
TEN_GOD_PAT = re.compile("|".join(sorted(TEN_GOD_REL, key=len, reverse=True)))


def element_of(stem: str) -> str:
    return ELEM[STEMS.index(stem)]


def rel_stems(dm: str, rel: int) -> list[str]:
    e = SEQ[(SEQ.index(element_of(dm)) + rel) % 5]
    return STEMS_OF[e]


def expand_useful(dm: str, primary: list[dict]) -> list[str]:
    out: list[str] = []
    for p in primary:
        for slot in p["stems"]:
            for s in slot:
                if s in STEMS:
                    out.append(s)
                elif s in TEN_GOD_REL:
                    out.extend(rel_stems(dm, TEN_GOD_REL[s]))
    return sorted(set(out), key=STEMS.index)


def mentions(dm: str, sent: str) -> tuple[set[str], set[str]]:
    """句里提到的干：(出现者, 缺者)。五行、局、十神都换算成干。"""
    present, absent = set(), set()
    for pat, kind in PATTERNS:
        for m in re.finditer(pat, sent):
            tok = re.sub(rf"[^{STEMS}{ELEMENTS}]", "", next(g for g in m.groups() if g))
            if kind == "absent":
                absent.update(c for c in tok if c in STEMS)
            elif kind == "present":
                present.update(c for c in tok if c in STEMS)
            elif kind == "element_absent":
                for e in tok:
                    absent.update(STEMS_OF[e])
            else:
                for e in tok:
                    present.update(STEMS_OF[e])
    for m in re.finditer(r"(申子辰|寅午戌|巳酉丑|亥卯未|亥子丑|巳午未|申酉戌|寅卯辰)", sent):
        present.update(STEMS_OF[TRIO[m.group(1)]])
    for m in TEN_GOD_PAT.finditer(sent):
        stems = rel_stems(dm, TEN_GOD_REL[m.group(0)])
        before = sent[max(0, m.start() - 2):m.start()]
        (absent if re.search(r"无|乏|缺", before) else present).update(stems)
    return present, absent


def classify(dm: str, useful: list[str], sent: str) -> dict:
    present, absent = mentions(dm, sent)
    U = set(useful)
    K = {s for u in U for s in STEMS_OF[KE_BY[element_of(u)]]}
    H = {COMBINE[u] for u in U}
    hit_k = sorted(present & K, key=STEMS.index)
    hit_h = sorted(present & H, key=STEMS.index)
    hit_absent = sorted(absent & U, key=STEMS.index)
    # 五行、十神换算出的干成对出现（壬癸、丙丁），同五行里有一个是用神就按用神本身算
    u_elems = {element_of(u) for u in U}
    same_as_u = {s for s in present if element_of(s) in u_elems}
    others = sorted(present - K - H - same_as_u, key=STEMS.index)
    if hit_k or hit_h:
        kind, why = "公式可推", ("克用神" + "".join(hit_k) if hit_k else "") + ("；" if hit_k and hit_h else "") + ("合用神" + "".join(hit_h) if hit_h else "")
    elif hit_absent:
        kind, why = "公式可推", "缺用神" + "".join(hit_absent)
    elif others:
        kind, why = "例外", "其他" + "".join(others) + ("，缺" + "".join(sorted(absent, key=STEMS.index)) if absent else "")
    elif same_as_u:
        kind, why = "例外", "用神过多" + "".join(sorted(same_as_u, key=STEMS.index))
    elif absent:
        kind, why = "例外", "缺" + "".join(sorted(absent, key=STEMS.index)) + "（非用神）"
    else:
        kind, why = "无法解析", ""
    return {"text": sent, "kind": kind, "why": why, "present": sorted(present, key=STEMS.index), "absent": sorted(absent, key=STEMS.index)}


KE_BY = {v: k for k, v in KE.items()}   # 被克 → 克我者：木被金克

# 主会话逐句裁定（卡号, 句首几个字）→ ("剔除", 理由) 或 ("依据", 新依据)
RULINGS: dict[tuple[str, str], tuple[str, str]] = {
    ("调候-乙未", "或丙合而癸亦合"): ("剔除", "合去用神，公式已推"),
    ("调候-乙未", "丙合癸不合"): ("剔除", "合去用神，公式已推"),
    ("调候-乙申", "凡从化格"): ("剔除", "从化判词，不是取用忌句"),
    ("调候-丁戌", "但此格幼年困厄"): ("剔除", "正面判词，忌的是缺水而非见水"),
    ("调候-戊戌", "癸甲全无"): ("剔除", "缺用神癸甲，公式已推"),
    ("调候-庚午", "见壬癸出干制火"): ("剔除", "正面判词，壬癸即用神"),
    ("调候-癸戌", "或有甲癸"): ("剔除", "正面判词"),
    ("调候-丙午", "阳刃合杀"): ("依据", "比劫太旺（羊刃倒戈）"),
    ("调候-壬卯", "二月寒气悉除"): ("依据", "忌火（丙丁非用神）"),
}


def apply_ruling(cid: str, r: dict) -> dict:
    for (c, head), (act, why) in RULINGS.items():
        if c == cid and r["text"].startswith(head):
            if act == "剔除":
                r["kind"], r["why"] = "人工剔除", why
            else:
                r["why"] = why
    return r


def split_sentences(field: str) -> list[str]:
    out = []
    for s in re.split(r"[。；]", field):
        s = LABEL.sub("", s.strip().strip("…").strip()).strip()
        if len(s) >= 4 and s not in ("无", "無"):
            out.append(s)
    return out


def load_cards() -> dict[str, dict]:
    cards: dict[str, dict] = {}
    for dm in STEMS:
        for c in parse_cards((CARDS / f"调候_{dm}.md").read_text(encoding="utf-8")):
            cards[c["id"]] = c
    return cards


def compare(entries: list[dict]) -> dict[str, list[dict]]:
    """卡号 → 每句判定。entries 为 tiaohou.json 的 entries（含 primary）。"""
    cards = load_cards()
    out: dict[str, list[dict]] = {}
    for e in entries:
        cid = e["source"]
        useful = expand_useful(e["dayMaster"], e["primary"])
        field = cards[cid]["fields"].get("忌句", "")
        out[cid] = [apply_ruling(cid, classify(e["dayMaster"], useful, s)) for s in split_sentences(field)]
    return out


def exceptions_of(results: list[dict]) -> list[dict]:
    return [{"text": r["text"], "kind": r["why"][:4] if r["why"].startswith("用神过多") else "其他",
             "stems": r["present"], "absent": r["absent"]} for r in results if r["kind"] == "例外"]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    entries = json.loads(TABLE.read_text(encoding="utf-8"))["entries"]
    res = compare(entries)
    total = sum(len(v) for v in res.values())
    by = {k: sum(1 for v in res.values() for r in v if r["kind"] == k) for k in ("公式可推", "例外", "无法解析", "人工剔除")}
    lines = ["# 调候忌句与公式比对", "",
             f"生成：{date.today().isoformat()}。120 张卡忌句共 {total} 句：公式可推（克用神、合用神、缺用神）{by['公式可推']} 句，不进机器表；"
             f"例外 {by['例外']} 句，进 tiaohou.json 的 avoidExceptions；无法解析 {by['无法解析']} 句，只在此报告，人读；"
             f"人工剔除 {by['人工剔除']} 句（主会话逐句裁定，见脚本 RULINGS）。",
             "", "用神 U 取卡的主序各段首选之并集（十神名换算）。「提到」列是脚本从句里抽出的干，五行、局、十神已换算。", ""]
    for e in entries:
        cid = e["source"]
        useful = "".join(expand_useful(e["dayMaster"], e["primary"]))
        lines += [f"## {cid}  用神 {useful}", "", "| 判定 | 依据 | 提到 | 缺 | 忌句 |", "|---|---|---|---|---|"]
        for r in res[cid]:
            lines.append(f"| {r['kind']} | {r['why']} | {''.join(r['present'])} | {''.join(r['absent'])} | {r['text']} |")
        lines.append("")
    print("\n".join(lines[:4]))
    if not a.check:
        REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"→ {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
