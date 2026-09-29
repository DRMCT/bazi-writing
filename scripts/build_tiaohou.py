#!/usr/bin/env python3
"""从十卷调候校核卡的「采用规则」字段生成机器表 bazi_core/tables/tiaohou.json。

    python scripts/build_tiaohou.py            → 写 tables/tiaohou.json 与 references/校核/调候_抽取报告.md
    python scripts/build_tiaohou.py --check    → 只打印报告，不写表

半自动：能解析的进结构字段，解析不了的碎片原样落在 notes 与报告里，由人核。
每条带 source 指向卡号，没有卡的条目不允许进表（DESIGN-命盘层 3.2）。

条目形态（2026-09-22 定）：
    primary      主序。列表，每项 {stems:[...], period:{label,boundary,side}|null}。
                 stems 里一个位次可有多个候选（如「壬癸」），写成 [["壬","癸"]]。
    conditional  条件用神。{stems, kind, when(原文条件), tags(粗标签)}。
    indispensable 不可缺。{stems, note}
    downgrade    降格。{absent, note}
    avoid        忌。原文短语列表。
    notes        解析剩下的碎片，人读。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "references" / "校核"
OUT = ROOT / "scripts" / "bazi_core" / "tables" / "tiaohou.json"
REPORT = CARDS / "调候_抽取报告.md"

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
MONTH_NAMES = {"寅": "正月", "卯": "二月", "辰": "三月", "巳": "四月", "午": "五月", "未": "六月",
               "申": "七月", "酉": "八月", "戌": "九月", "亥": "十月", "子": "十一月", "丑": "十二月"}
TEN_GOD = ["比肩", "比劫", "劫财", "劫", "食伤", "食神", "伤官", "财", "官煞", "官杀", "官", "煞", "印比", "枭印", "印", "金水"]
ELEMENTS = "金木水火土"

# 节气段标签 → (boundary, side)。boundary 为中气/节名或「半月」「清明后十日」。
PERIODS = {
    "雨水前": ("雨水", "before"), "雨水后": ("雨水", "after"),
    "清明后谷雨前": ("谷雨", "before"), "谷雨后": ("谷雨", "after"), "清明后": ("谷雨", "before"),
    "清明后（上半月）": ("谷雨", "before"), "谷雨后（下半月）": ("谷雨", "after"),
    "清明后十日内": ("清明后十日", "before"), "十日之后": ("清明后十日", "after"),
    "夏至前": ("夏至", "before"), "夏至后": ("夏至", "after"),
    "夏至前/上半月": ("夏至", "before"), "夏至后/下半月": ("夏至", "after"),
    "大暑前": ("大暑", "before"), "大暑后": ("大暑", "after"),
    "秋分前": ("秋分", "before"), "秋分后": ("秋分", "after"),
    "秋分前/上半月": ("秋分", "before"), "秋分后/下半月": ("秋分", "after"),
    "霜降前": ("霜降", "before"), "霜降后": ("霜降", "after"),
    "冬至前": ("冬至", "before"), "冬至后": ("冬至", "after"),
    "上半月": ("半月", "before"), "下半月": ("半月", "after"),
    "上半月（大暑前，徐注\"看法与五月略同\"）": ("大暑", "before"), "下半月（大暑后）": ("大暑", "after"),
}

# 少数条目的写法解析器吃不动，手工给主序；条件用神仍走解析。
OVERRIDES: dict[str, dict] = {
    "辛未": {"primary": [
        {"stems": [["壬"], ["己"], ["癸"]], "period": {"label": "大暑前", "boundary": "大暑", "side": "before"},
         "note": "同五月，徐注「上下半月不同，与庚金同论」，主会话定 period 大暑"},
        {"stems": [["壬"], ["庚"]], "period": {"label": "大暑后", "boundary": "大暑", "side": "after"}},
    ]},
    "壬未": {"primary": [
        {"stems": [["癸"], ["庚"]], "period": {"label": "大暑前", "boundary": "大暑", "side": "before"}, "note": "同五月"},
        {"stems": [["辛"], ["甲"], ["庚"]], "period": {"label": "大暑后", "boundary": "大暑", "side": "after"}},
    ]},
    "癸未": {"primary": [
        {"stems": [["庚"], ["辛"], ["比劫"]], "period": {"label": "上半月", "boundary": "大暑", "side": "before"}, "note": "须有比劫助金"},
        {"stems": [["庚"], ["辛"]], "period": {"label": "下半月", "boundary": "大暑", "side": "after"}},
    ]},
    "乙午": {"primary": [
        {"stems": [["癸"], ["丙"]], "period": {"label": "夏至前/上半月", "boundary": "夏至", "side": "before"}},
        {"stems": [["丙"], ["癸"]], "period": {"label": "夏至后/下半月", "boundary": "夏至", "side": "after"}, "note": "丙癸并尊"},
    ]},
    "乙酉": {"primary": [
        {"stems": [["癸"]], "period": {"label": "秋分前/上半月", "boundary": "秋分", "side": "before"}, "note": "无癸姑用壬"},
        {"stems": [["丙"], ["癸"]], "period": {"label": "秋分后/下半月", "boundary": "秋分", "side": "after"}},
    ]},
    "戊卯": {"primary": [{"stems": [["丙"], ["癸"], ["甲"]], "period": None, "note": "二月从徐注；正月见戊寅卡"}]},
    "壬丑": {"primary": [
        {"stems": [["丙"]], "period": {"label": "上半月", "boundary": "半月", "side": "before"}},
        {"stems": [["丙"], ["甲"]], "period": {"label": "下半月", "boundary": "半月", "side": "after"}},
    ]},
    "癸辰": {"primary": [
        {"stems": [["丙"]], "period": {"label": "清明后（上半月）", "boundary": "谷雨", "side": "before"}},
        {"stems": [["丙"], ["辛"]], "period": {"label": "谷雨后（下半月）", "boundary": "谷雨", "side": "after"}},
    ]},
    "甲戌": {"primary": [
        {"stems": [["丁"], ["丙"], ["庚"]], "period": {"label": "上半月", "boundary": "半月", "side": "before"}, "note": "同八月，徐注"},
        {"stems": [["庚"], ["丁"], ["壬", "癸"]], "period": {"label": "下半月", "boundary": "半月", "side": "after"}},
    ]},
    "辛丑": {"primary": [{"stems": [["丙"], ["壬"], ["戊", "己"]], "period": None}]},
    "壬申": {"primary": [{"stems": [["戊"], ["丁"]], "period": None, "note": "戊取辰戌之戊，不用申中之戊；丁须与壬相隔"}]},
    "辛巳": {"primary": [{"stems": [["壬"], ["癸"], ["甲"]], "period": None, "note": "甲为破戊之药，须有壬癸"}]},
    "癸亥": {"primary": [{"stems": [["丙"]], "period": None, "note": "从徐注；庚辛限木局，见 conditional"}]},
}


# ---------------------------------------------------------------- 解析

def read_rules() -> list[tuple[str, str, str, str]]:
    out = []
    for dm in STEMS:
        text = (CARDS / f"调候_{dm}.md").read_text(encoding="utf-8")
        for m in re.finditer(r"### 调候-(\S+)[^\n]*\n(.*?)(?=\n### |\n## )", text, re.S):
            cid, body = m.group(1), m.group(2)
            rule = re.search(r"^- 采用规则：(.*)$", body, re.M).group(1).strip()
            status = re.search(r"^- 状态：(.*)$", body, re.M).group(1).strip()
            out.append((cid, cid[0], cid[1], rule, status))
    return out


def split_parens(s: str) -> tuple[str, list[str]]:
    """摘出顶层（…）组，返回（去括号后的正文，括号内容列表）。"""
    body, groups, depth, buf = [], [], 0, []
    for ch in s:
        if ch == "（":
            depth += 1
            if depth == 1:
                continue
        elif ch == "）":
            depth -= 1
            if depth == 0:
                groups.append("".join(buf)); buf = []
                continue
        (buf if depth > 0 else body).append(ch)
    return "".join(body), groups


def parse_token(tok: str) -> dict | None:
    """「丙」「壬癸」「庚辛」「二丁」「己土/印」「比劫」「金」→ {stems, kind}。不认得返回 None。"""
    tok = tok.strip().strip("\"“”")
    tok = re.sub(r"^(兼用|专用|必用|宜用|即|用)", "", tok)
    if len(tok) == 2 and tok[0] in STEMS and tok[1] in ELEMENTS:
        tok = tok[0]
    count = None
    if tok[:1] in "二两三" and len(tok) == 2 and tok[1] in STEMS:
        count, tok = {"二": 2, "两": 2, "三": 3}[tok[0]], tok[1]
    alts = [t for t in re.split(r"[/／]", tok) if t]
    stems, kinds = [], set()
    for a in alts:
        a = a.strip()
        if a and all(c in STEMS for c in a):
            stems.extend(list(a)); kinds.add("stem")
        elif a in TEN_GOD:
            stems.append(a); kinds.add("tenGod")
        elif a in ELEMENTS:
            stems.append(a); kinds.add("element")
        else:
            return None
    if not stems:
        return None
    d = {"stems": stems, "kind": "stem" if kinds == {"stem"} else "/".join(sorted(kinds))}
    if count:
        d["count"] = count
    return d


def parse_sequence(s: str) -> tuple[list[list[str]], list[str]]:
    """「庚、丁」「癸、丁、庚」「庚、丁、壬癸」→ 位次列表；不认得的碎片另返回。"""
    s = s.strip().split("。")[0]
    s = re.sub(r"^(同[一二三四五六七八九十]+月[，,]?|即)", "", s)
    slots, junk = [], []
    for part in re.split(r"[、，,]", s):
        part = part.strip()
        if not part:
            continue
        t = parse_token(part)
        if t and t["kind"] in ("stem", "tenGod"):
            slots.append(t["stems"] if t["kind"] == "stem" else [t["stems"][0]])
        else:
            junk.append(part)
    return slots, junk


TAGS = [
    (r"无(?P<x>[甲乙丙丁戊己庚辛壬癸])", "absent"),
    (r"支成(?P<x>[金木水火土])局|(?P<y>[金木水火土])局", "trio"),
    (r"(?:一派|一片|多见|重重|太多|太旺|多)(?P<x>[甲乙丙丁戊己庚辛壬癸金木水火土])", "many"),
    (r"(?P<x>[甲乙丙丁戊己庚辛壬癸])(?:多|重重|太多|太旺)", "many"),
    (r"(?P<x>[甲乙丙丁戊己庚辛壬癸])透|(?P<y>[甲乙丙丁戊己庚辛壬癸])出干", "exposed"),
]


def tags_of(when: str) -> dict:
    tags: dict[str, list[str]] = {}
    for pat, name in TAGS:
        for m in re.finditer(pat, when):
            v = m.group("x") if "x" in m.groupdict() and m.group("x") else m.groupdict().get("y")
            if v and v not in tags.setdefault(name, []):
                tags[name].append(v)
    return tags


def parse_rule(cid: str, rule: str) -> dict:
    entry: dict = {"primary": [], "conditional": [], "indispensable": [], "downgrade": [], "avoid": [], "notes": []}
    text = rule

    # 另记忌 / 另记 / 不可缺 / 降格 尾巴
    for m in re.finditer(r"另记忌：([^；。]+)", text):
        entry["avoid"].extend(x.strip() for x in re.split(r"[、]", m.group(1)) if x.strip())
    text = re.sub(r"[；。]?另记忌：[^；。]+", "", text)
    for m in re.finditer(r"不可缺：([^；。）]+)", text):
        entry["indispensable"].append({"stems": re.findall(r"[甲乙丙丁戊己庚辛壬癸金木水火土]", m.group(1)), "note": m.group(1).strip()})
    text = re.sub(r"[；。]?不可缺：[^；。）]+", "", text)
    for m in re.finditer(r"另记[\"“]([^\"”]+?)(不可缺|不可少)[\"”]", text):
        entry["indispensable"].append({"stems": re.findall(r"[甲乙丙丁戊己庚辛壬癸金木水火土]", m.group(1)), "note": m.group(1) + m.group(2)})
    text = re.sub(r"[，；。]?另记[\"“][^\"”]+?(不可缺|不可少)[\"”]", "", text)
    for m in re.finditer(r"无([甲乙丙丁戊己庚辛壬癸])：降格[，,]?([^；。（]*)", text):
        entry["downgrade"].append({"absent": m.group(1), "note": m.group(2).strip()})
    text = re.sub(r"[；。]?无[甲乙丙丁戊己庚辛壬癸]：降格[^；。]*(（[^）]*）)?", "", text)
    for m in re.finditer(r"另记(?!忌)[：:]?([^；。]+)", text):
        entry["notes"].append("另记：" + m.group(1).strip())
    text = re.sub(r"[；。]?另记(?!忌)[：:]?[^；。]+", "", text)

    body, groups = split_parens(text)

    # 括号组：「X：条件」为条件用神；「节气/条件」+ 后随主序在 body 里；其余为注
    entry["alternates"] = []
    for g in groups:
        m = re.match(r"^\s*([^：:]{1,8})[：:](.*)$", g, re.S)
        tok = parse_token(m.group(1)) if m else None
        if m and tok:
            when = m.group(2).strip()
            entry["conditional"].append({**tok, "when": when, "tags": tags_of(when)})
            continue
        handled = False
        for part in re.split(r"[；;]", g):
            pm = re.match(r"^\s*([^：:]{2,14})[：:]?(.*)$", part.strip())
            if not pm:
                continue
            label, val = pm.group(1), pm.group(2).strip()
            ref = re.search(r"(?:同|与)([一二三四五六七八九十]+月)", part)
            plabel = label if label in PERIODS else next((k for k in PERIODS if part.strip().startswith(k)), None)
            if plabel:
                b, side = PERIODS[plabel]
                period = {"label": plabel, "boundary": b, "side": side}
                slots, _ = parse_sequence(val)
                if ref:
                    entry["primary"].append({"stems": [], "period": period, "sameAs": ref.group(1), "note": val})
                elif slots:
                    entry["primary"].append({"stems": slots, "period": period, "note": val})
                else:
                    continue
                handled = True
            elif val and "：" not in val:
                slots, junk = parse_sequence(val)
                if slots and not junk and label not in MONTH_NAMES.values():
                    entry["alternates"].append({"when": label, "stems": slots})
                    handled = True
        if not handled:
            entry["notes"].append(g.strip())

    # 正文：按；分段，段首若为节气标签则带 period
    for seg in re.split(r"[；;]", body):
        seg = seg.strip(" 。，")
        if not seg:
            continue
        period = None
        m = re.match(r"^([^：:]{2,14})[：:](.*)$", seg)
        if m and m.group(1) in PERIODS:
            b, side = PERIODS[m.group(1)]
            period = {"label": m.group(1), "boundary": b, "side": side}
            seg = m.group(2)
        elif m and m.group(1) in MONTH_NAMES.values():
            if m.group(1) != MONTH_NAMES[cid[1]]:
                entry["notes"].append(seg); continue
            seg = m.group(2)
        elif m:
            slots, junk = parse_sequence(m.group(2))
            if slots and not junk:
                entry["alternates"].append({"when": m.group(1), "stems": slots})
            else:
                entry["notes"].append(seg)
            continue
        seg = re.sub(r"^同[一二三四五六七八九十]+月[，,]?", "", seg)
        slots, junk = parse_sequence(seg)
        if slots:
            entry["primary"].append({"stems": slots, "period": period})
        entry["notes"].extend(junk)

    if cid in OVERRIDES:
        entry["primary"] = OVERRIDES[cid]["primary"]
        entry["notes"].append("主序手工给定（OVERRIDES）")
    return entry


def build() -> tuple[dict, list[str]]:
    rules = read_rules()
    assert len(rules) == 120, len(rules)
    entries, report = [], []
    parsed = {cid: parse_rule(cid, rule) for cid, dm, mb, rule, status in rules}
    name_to_branch = {v: k for k, v in MONTH_NAMES.items()}
    for cid, e in parsed.items():
        for p in e["primary"]:
            if p.get("sameAs"):
                ref = parsed[cid[0] + name_to_branch[p["sameAs"]]]
                default = next((q for q in ref["primary"] if not q.get("period")), None) or                           next((q for q in ref["primary"] if q.get("period", {}) and q["period"]["side"] == "after"), None) or ref["primary"][0]
                p["stems"] = default["stems"]
    for cid, dm, mb, rule, status in rules:
        e = parsed[cid]
        if not e["primary"]:
            report.append(f"- **{cid}** 无主序！ 原文：{rule}")
        e_out = {"dayMaster": dm, "monthBranch": mb, "source": f"调候-{cid}", "status": status, **e, "rule": rule}
        entries.append(e_out)
    # 忌句与公式比对：公式推不出的忌句作例外进表（compare_avoid.py，报告另写）
    from compare_avoid import compare, exceptions_of
    verdicts = compare(entries)
    for e_out in entries:
        e_out["avoidExceptions"] = exceptions_of(verdicts[e_out["source"]])
        junk = [n for n in e["notes"] if not n.startswith(("正文", "徐注", "另记", "主序手工", "总论", "总之", "\"", "“"))]
        if junk:
            report.append(f"- {cid}：主序 {fmt(e['primary'])}；未入结构的碎片：" + " ｜ ".join(junk))
    table = {"schema": "tiaohou/1", "generated": date.today().isoformat(),
             "source": "references/校核/调候_{日主}.md 采用规则字段；《穷通宝鉴评注》徐乐吾评注本校核卡",
             "entries": entries}
    return table, report


def fmt(primary: list[dict]) -> str:
    return "；".join(((p["period"]["label"] + "：") if p.get("period") else "") + "、".join("/".join(s) for s in p["stems"]) for p in primary)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    table, report = build()
    n = len(table["entries"])
    n_period = sum(1 for e in table["entries"] if any(p.get("period") for p in e["primary"]))
    n_cond = sum(len(e["conditional"]) for e in table["entries"])
    n_alt = sum(len(e.get("alternates", [])) for e in table["entries"])
    head = [f"# 调候机器表抽取报告", "", f"生成：{table['generated']}，{n} 条；带节气段 {n_period} 条；条件用神 {n_cond} 项；条件改序 {n_alt} 项；不可缺 {sum(len(e['indispensable']) for e in table['entries'])} 项；降格 {sum(len(e['downgrade']) for e in table['entries'])} 项。",
            "", "下面是解析器没放进结构字段的碎片，人核。主序已列出便于对照卡。", ""]
    print("\n".join(head + report))
    if not a.check:
        OUT.parent.mkdir(exist_ok=True)
        OUT.write_text(json.dumps(table, ensure_ascii=False, indent=1), encoding="utf-8")
        REPORT.write_text("\n".join(head + report) + "\n", encoding="utf-8")
        print(f"\n→ {OUT}\n→ {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
