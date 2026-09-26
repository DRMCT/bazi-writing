#!/usr/bin/env python3
"""从《滴天髓阐微》校核卡生成机器表 tables/ditiansui.json，并投影成 references/滴天髓_规则.md。

读 references/校核/滴天髓_*.md 的每张卡：
  - 采用规则：按"；"切成条目；"条件：X→结论：Y"或"X→Y"形式的拆成 cond / result，"键：值"形式的拆成 key / value；
    切不动的原样进 raw。
  - 叙事译法：按行切，去掉行首序号，条末括注的依据（"（依据 …）"）拆进 basis。
  - 引文只记页码与句数，不复制全文（全文在卡上，卡引用校对本，校对本不公开）。
每条带 card（卡号）、chapter（章）、status（卡状态）。没有卡号的条目不会出现，机器表因此天然带出处。

用法：python scripts/build_ditiansui.py            （写表与投影）
      python scripts/build_ditiansui.py --check    （只解析并报告切不动的条目）
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from check_cards import parse_cards  # noqa: E402

CARDS = sorted((ROOT / "references" / "校核").glob("滴天髓_*.md"))
TABLE = ROOT / "scripts" / "bazi_core" / "tables" / "ditiansui.json"
DOC = ROOT / "references" / "滴天髓_规则.md"
PAGE = re.compile(r"[（(]\s*p\d{3}[^）)]*[）)]")
ARROW = re.compile(r"\s*(?:→|->|—>)\s*")


def split_items(text: str) -> list[str]:
    items = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        depth, buf = 0, ""
        for ch in line:                          # 括号（含〔〕）里的分号不切
            if ch in "（(〔[": depth += 1
            elif ch in "）)〕]": depth = max(0, depth - 1)
            if ch in "；;" and depth == 0:
                if buf.strip(): items.append(buf.strip().rstrip("。"))
                buf = ""
            else:
                buf += ch
        if buf.strip():
            items.append(buf.strip().rstrip("。"))
    return items


def parse_rule(item: str) -> dict:
    """"条件：X→性：Y" / "X→Y" / "键：值" 三种；其余进 raw。"""
    if ARROW.search(item):
        left, right = ARROW.split(item, 1)
        lk, lsep, lv = left.partition("：")
        rk, rsep, rv = right.partition("：")
        cond = (lv if lsep and lk.strip() in ("条件", "变", "分支") else left).strip()
        key = lk.strip() if lk in ("变", "分支") else "条件"
        return {"kind": "rule", "key": key, "cond": cond,
                "resultKey": (rk.strip() if rv else ""), "result": (rv or right).strip()}
    if "：" in item:
        k, _, v = item.partition("：")
        return {"kind": "kv", "key": k.strip(), "value": v.strip()}
    return {"kind": "raw", "text": item}


def merge_rules(rules: list[dict]) -> list[dict]:
    """卡上常见两种列表写法：键值后用分号并列多个值（"忌：土燥；火烈"），箭头前用分号并列多个条件
    （"条件：官太弱；官旺用印而见财→异路"）。前者并回上一个键值，后者并成"或"条件。"""
    out: list[dict] = []
    pending: list[str] = []
    for r in rules:
        if r["kind"] == "raw":
            if out and out[-1]["kind"] == "kv" and not pending:
                out[-1]["value"] += "、" + r["text"]
            else:
                pending.append(r["text"])
            continue
        if pending and r["kind"] == "rule":
            r["cond"] = "或".join(pending + [r["cond"]])
            pending = []
        elif pending:
            out.extend({"kind": "raw", "text": t} for t in pending)
            pending = []
        out.append(r)
    out.extend({"kind": "raw", "text": t} for t in pending)
    return out


def parse_narrative(text: str) -> list[dict]:
    out = []
    for line in text.splitlines():
        line = re.sub(r"^\s*(?:[0-9０-９]+[.．、)]|[-*•]|[一二三四五六七八九十]+[、.])\s*", "", line.strip())
        if not line:
            continue
        m = re.search(r"[（(]([^）)]*(?:依据|对应|据)[^）)]*)[）)]\s*$", line)
        basis = m.group(1) if m else ""
        sentence = line[:m.start()].strip() if m else line
        out.append({"text": sentence, "basis": basis})
    return out


def chapter_of(path: Path) -> str:
    return path.stem.split("_", 1)[1]


def build(check_only: bool) -> int:
    entries = []
    unparsed = []
    for f in CARDS:
        text = f.read_text(encoding="utf-8")
        for c in parse_cards(text):
            fields = c["fields"]
            if "采用规则" not in fields:
                continue
            rules = merge_rules([parse_rule(it) for it in split_items(fields["采用规则"])])
            for r in rules:
                if r["kind"] == "raw":
                    unparsed.append((c["id"], r["text"]))
            quotes = {}
            for k in ("原文引文", "原注引文", "任注要点"):
                v = fields.get(k, "")
                quotes[k] = {"sentences": len([s for s in re.split(r"[。；]", PAGE.sub("", v)) if len(s.strip()) >= 4]),
                             "pages": sorted(set(re.findall(r"p\d{3}", v)))}
            lipan = [ln.strip() for ln in fields.get("例盘", "").splitlines() if ln.strip() and ln.strip() not in ("无", "無")]
            entries.append({
                "card": c["id"], "chapter": chapter_of(f), "file": f.name,
                "title": next((ln for ln in text.splitlines() if ln.startswith(f"### {c['id']}")), "")[4 + len(c["id"]):].strip(),
                "rules": rules, "narrative": parse_narrative(fields.get("叙事译法", "")),
                "quotes": quotes, "lipanCount": len(lipan),
                "source": fields.get("出处", "").strip(), "ruling": fields.get("裁决", "").strip(),
                "status": fields.get("状态", "").strip(),
            })
    print(f"{len(CARDS)} 个卡文件，{len(entries)} 张卡，规则 {sum(len(e['rules']) for e in entries)} 条，"
          f"叙事译法 {sum(len(e['narrative']) for e in entries)} 条，切不动 {len(unparsed)} 条")
    for cid, t in unparsed:
        print("  raw ", cid, t[:60])
    if check_only:
        return 0
    TABLE.write_text(json.dumps({"format": "ditiansui/v1", "entries": entries}, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = ["# 《滴天髓阐微》规则投影", "",
             "由 `scripts/build_ditiansui.py` 从 `references/校核/滴天髓_*.md` 的校核卡生成，机器表 `scripts/bazi_core/tables/ditiansui.json`。"
             "每条带卡号；引文原文在卡上，卡引用校对本，校对本不公开。叙事译法是自起草，括注它依据的采用规则项。", ""]
    cur = None
    for e in entries:
        if e["chapter"] != cur:
            cur = e["chapter"]
            lines += [f"## {cur}", ""]
        lines += [f"### {e['card']}  {e['title']}", "", f"- 出处：{e['source']}", f"- 状态：{e['status']}；裁决：{e['ruling']}"]
        for r in e["rules"]:
            if r["kind"] == "rule":
                lines.append(f"- {r['key']}：{r['cond']} → {r['resultKey'] + '：' if r['resultKey'] else ''}{r['result']}")
            elif r["kind"] == "kv":
                lines.append(f"- {r['key']}：{r['value']}")
            else:
                lines.append(f"- （未结构化）{r['text']}")
        if e["narrative"]:
            lines.append("- 叙事译法（自起草）：")
            for nrt in e["narrative"]:
                lines.append(f"    - {nrt['text']}" + (f"（{nrt['basis']}）" if nrt["basis"] else ""))
        lines.append("")
    DOC.write_text("\n".join(lines), encoding="utf-8")
    print("wrote", TABLE, DOC)
    return 0


if __name__ == "__main__":
    raise SystemExit(build("--check" in sys.argv[1:]))
