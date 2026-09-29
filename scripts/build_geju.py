#!/usr/bin/env python3
"""从格局校核卡（references/校核/格局_*.md）的「采用规则」生成机器表 bazi_core/tables/geju.json。

    python scripts/build_geju.py            → 写 tables/geju.json 与 references/校核/格局_抽取报告.md
    python scripts/build_geju.py --check    → 只打印报告

采用规则的写法（子代理任务_格局.md 定，三批子代理各有小异，这里都认）：
    成：{条件}；{条件}……                      条件用"且""或"连接原子短语，括注（……）或〔……〕是附注
    败：……
    救：{败因}→{救法}；……
    运·{局}：喜A运、B运；忌C运；不忌D运        取运按局分行，"运·X：""运（X）：""运〔X〕：""运：" 四种写法都认
附注里带"徐"字（（徐）〔徐〕）的条目标 fromXu=true；带"两存"的标 disputed=true。
条件原子按词表切分：十神词、身强弱词、季节词、关系词；切不动的原子记进报告，不阻断建表。
每条带 source 指向卡号与卡状态；没有卡的条目不允许进表（DESIGN-命盘层 3.2）。格名映射到 shishen.determine_structure 的格名。
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
OUT = ROOT / "scripts" / "bazi_core" / "tables" / "geju.json"
REPORT = CARDS / "格局_抽取报告.md"

STRUCTURES = {
    "正官": ["正官格"], "财": ["正财格", "偏财格"], "印绶": ["正印格", "偏印格"], "食神": ["食神格"],
    "偏官": ["七杀格"], "伤官": ["伤官格"], "阳刃": ["月刃格"], "建禄月劫": ["建禄格", "月劫格"],
}
# 十神词（长的在前，先匹配）
GODS = ["官煞", "官杀", "食伤", "伤食", "财印", "煞印", "印绶", "偏印", "正印", "正官", "七煞", "七杀", "正财", "偏财",
        "食神", "伤官", "比劫", "禄劫", "官", "煞", "杀", "财", "印", "食", "伤", "刃", "禄", "劫", "比", "枭"]
BODY = ["身强", "身弱", "身轻", "身重", "身旺", "身危"]
SEASON = ["金水", "木火", "春木秋金", "冬金夏木"]
REL = ["不相碍", "不相伤", "相碍", "相伤", "两清", "当令", "有根", "无根", "同根月令", "合化", "化为", "透", "藏", "逢", "带", "见", "无",
       "去", "制", "合", "化", "冲", "刑", "破", "害", "伤", "泄", "生", "隔", "敌", "会", "党", "当", "就", "存", "留", "用", "佩",
       "重", "轻", "多", "旺", "强", "弱", "混", "清", "太过", "有情", "有力", "无力", "露", "叠出", "偏正", "间之", "先", "后",
       "不忌", "忌", "喜", "运", "地", "乡", "助身", "助", "护", "通关", "解", "兼", "辅", "取清", "弃", "成格", "之神", "及", "且", "或", "而", "则", "者", "之", "为", "亦", "与", "并"]
STEM_MONTH = re.compile(r"^[甲乙丙丁戊己庚辛壬癸]生[子丑寅卯辰巳午未申酉戌亥]月$")
ANNOT = re.compile(r"[（〔(\[]([^）〕)\]]*)[）〕)\]]")
RUN_HEAD = re.compile(r"^运(?:[·•]\s*(?P<a>[^：]+)|（(?P<b>[^）]+)）|〔(?P<c>[^〕]+)〕)?\s*：\s*(?P<body>.*)$")


def atoms(text: str) -> tuple[list[str], list[str]]:
    """把条件短语切成词表里的原子；切不动的残片另返。"""
    s = ANNOT.sub("", text).strip()
    out, rest = [], []
    for phrase in re.split(r"[且或、，]", s):
        phrase = phrase.strip()
        if not phrase:
            continue
        if STEM_MONTH.match(phrase):
            out.append(phrase); continue
        i, buf = 0, []
        while i < len(phrase):
            hit = next((w for w in GODS + BODY + SEASON + REL if phrase.startswith(w, i)), None)
            if hit:
                buf.append(hit); i += len(hit)
            else:
                buf.append("?" + phrase[i]); i += 1
        out.append("".join(b if not b.startswith("?") else b[1:] for b in buf))
        bad = "".join(b[1:] for b in buf if b.startswith("?"))
        if bad:
            rest.append(bad)
    return out, rest


def item(text: str) -> dict:
    notes = ANNOT.findall(text)
    core = ANNOT.sub("", text).strip()
    a, rest = atoms(core)
    return {"text": text.strip(), "core": core, "atoms": a, "notes": notes,
            "fromXu": any("徐" in n for n in notes), "disputed": any("两存" in n or "存疑" in n for n in notes),
            "unparsed": rest}


def parse_rule(rule: str) -> tuple[dict, list[str]]:
    out = {"cheng": [], "bai": [], "jiu": [], "yun": []}
    problems: list[str] = []
    for raw in rule.strip().splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("成："):
            out["cheng"] += [item(x) for x in line[2:].split("；") if x.strip()]
        elif line.startswith("败："):
            out["bai"] += [item(x) for x in line[2:].split("；") if x.strip()]
        elif line.startswith("救："):
            for x in line[2:].split("；"):
                if not x.strip():
                    continue
                if "→" in x:
                    cause, fix = x.split("→", 1)
                    out["jiu"].append({"cause": item(cause), "fix": item(fix), "text": x.strip()})
                else:
                    problems.append(f"救应无→：{x.strip()}")
        elif line.startswith("运"):
            m = RUN_HEAD.match(line)
            if not m:
                problems.append(f"运行读不出：{line}"); continue
            scope = (m.group("a") or m.group("b") or m.group("c") or "通").strip()
            entry = {"scope": scope, "scopeAtoms": atoms(scope)[0], "favor": [], "avoid": [], "neutral": [], "other": []}
            for seg in m.group("body").split("；"):
                seg = seg.strip()
                if not seg:
                    continue
                if seg.startswith("喜"):
                    entry["favor"] += [item(x) for x in seg[1:].split("、") if x.strip()]
                elif seg.startswith("不忌"):
                    entry["neutral"] += [item(x) for x in seg[2:].split("、") if x.strip()]
                elif seg.startswith("忌"):
                    entry["avoid"] += [item(x) for x in seg[1:].split("、") if x.strip()]
                elif re.search(r"不忌|不为害|未即凶|无伤|非福|无虑|亦亨|不碍", seg):
                    entry["neutral"].append(item(seg))
                else:
                    entry["other"].append(item(seg))
            out["yun"].append(entry)
        else:
            problems.append(f"行读不出：{line}")
    return out, problems


def build() -> tuple[dict, list[str]]:
    entries, report = [], []
    for f in sorted(CARDS.glob("格局_*.md")):
        if "报告" in f.name:
            continue
        for c in parse_cards(f.read_text(encoding="utf-8")):
            if not c["id"].startswith("格局-"):
                continue
            name = c["id"][3:]
            rule, problems = parse_rule(c["fields"]["采用规则"])
            e = {"name": name, "structures": STRUCTURES[name], "source": c["id"], "file": f.name,
                 "status": c["fields"]["状态"].split("（")[0].strip(), "outline": c["fields"]["出处"].strip(), **rule}
            entries.append(e)
            bad = []
            for key in ("cheng", "bai"):
                bad += [f"{key}：{i['core']} → 残片 {i['unparsed']}" for i in e[key] if i["unparsed"]]
            for j in e["jiu"]:
                for part in (j["cause"], j["fix"]):
                    if part["unparsed"]:
                        bad.append(f"救：{part['core']} → 残片 {part['unparsed']}")
            for y in e["yun"]:
                for part in y["favor"] + y["avoid"] + y["neutral"] + y["other"]:
                    if part["unparsed"]:
                        bad.append(f"运〔{y['scope']}〕：{part['core']} → 残片 {part['unparsed']}")
            report.append(f"## {c['id']}  状态 {e['status']}\n\n成 {len(e['cheng'])}、败 {len(e['bai'])}、救 {len(e['jiu'])}、运 {len(e['yun'])} 局，"
                          f"徐评来源 {sum(1 for k in ('cheng', 'bai') for i in e[k] if i['fromXu'])} 条，两存 {sum(1 for k in ('cheng', 'bai') for i in e[k] if i['disputed'])} 条。\n")
            if problems:
                report.append("读不出的行：\n" + "\n".join(f"- {p}" for p in problems) + "\n")
            if bad:
                report.append("词表切不动的残片（不阻断建表，解读层按原句读）：\n" + "\n".join(f"- {b}" for b in bad) + "\n")
    table = {"schema": "geju/1", "generated": date.today().isoformat(),
             "source": "references/校核/格局_{官财印,食煞伤,刃禄}.md 采用规则字段；《子平真诠评注》校核卡",
             "vocabulary": {"gods": GODS, "body": BODY, "season": SEASON, "relations": REL},
             "entries": entries}
    return table, report


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    table, report = build()
    head = [f"# 格局机器表抽取报告", "", f"生成：{date.today().isoformat()}。{len(table['entries'])} 张卡 → tables/geju.json。"
            "条件原子按词表切分，残片列在各卡下；救应与取运按局分列。", ""]
    print("\n".join(head + report)[:3000])
    if not a.check:
        OUT.write_text(json.dumps(table, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        REPORT.write_text("\n".join(head + report) + "\n", encoding="utf-8")
        print("→", OUT, REPORT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
