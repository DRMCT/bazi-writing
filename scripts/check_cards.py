#!/usr/bin/env python3
"""校核卡引文核对：「取用引文」「忌句」须能在校对本的正文段里找到，「徐注要点」须能在徐注段里找到。

用法：
    python scripts/check_cards.py references/校核/调候_乙.md [--corpus-dir references/校核/语料] [--json]
退出码：0 字段齐全；1 字段缺失；2 参数错误。低相似度句子只提示不阻断。

只做字面核对（去标点、统一异体字），不判断命理。徐评本的正文措辞与网上通行本有出入
（如「一榜堪图」书作「可许一榜」），所以引文核对用相似度而不是逐字：每句给出与语料最相近句子的
相似度，低于 LOW 的句子列为「疑似徐注或抄错」，只作提示；阻断只针对字段缺失。
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

# 卡的种类按文件名前缀认：调候（穷通宝鉴，按日主分文件）、神煞、刑冲合害、十二长生纳音（对三命通会校对本）、格局（对子平真诠校对本）
KINDS = {
    "调候": {
        "required": ["取用引文", "忌句", "徐注要点", "分支判词", "从化判词", "校记", "出处", "采用规则", "初稿写法", "差异", "裁决", "状态"],
        "quotes": {"取用引文": "正文", "忌句": "正文", "徐注要点": "徐注"},   # 引文字段 → 校对本池子
        "pools": {"正文": "正文", "徐注": "徐注"},                              # 校对本标签 → 池子
    },
    "神煞": {
        "required": ["查法引文", "断语引文", "位置变体", "校者注", "出处", "采用规则", "初稿写法", "核对", "差异", "裁决", "状态"],
        "quotes": {"查法引文": "正文", "断语引文": "正文", "校者注": "校者注"},
        "pools": {"正文": "正文", "歌诀": "正文", "校者注": "校者注"},
        "proof": "三命通会_神煞",
    },
    # 刑冲合害与十二长生纳音：三命通会卷一卷二，引文可落在神煞页（三合、六害、三刑、冲击）或基础页（六合、十干合、生死、纳音）
    "刑冲合害": {
        "required": ["引文", "出处", "采用规则", "初稿写法", "核对", "差异", "裁决", "状态"],
        "quotes": {"引文": "正文"},
        "pools": {"正文": "正文", "歌诀": "正文", "表格": "正文", "校者注": "校者注"},
        "proof": ["三命通会_神煞", "三命通会_基础"],
    },
    "格局": {
        "required": ["成格引文", "败格引文", "救应引文", "取运引文", "徐评要点", "例盘", "出处", "采用规则", "初稿写法", "核对", "差异", "裁决", "状态"],
        "quotes": {"成格引文": "原文", "败格引文": "原文", "救应引文": "原文", "取运引文": "原文", "徐评要点": "徐评"},
        "pools": {"原文": "原文", "徐评": "徐评", "标题": "原文"},
        "proof": "子平真诠_格局",
    },
    # 滴天髓阐微：十干体性、性情、疾病、六亲、小儿、何知、出身、地位、岁运、官杀、伤官各章的卡，文件名以 滴天髓_ 起头
    "滴天髓": {
        "required": ["原文引文", "原注引文", "任注要点", "例盘", "出处", "采用规则", "叙事译法", "初稿写法", "核对", "差异", "裁决", "状态"],
        "quotes": {"原文引文": "原文", "原注引文": "原注", "任注要点": "任注"},
        "pools": {"原文": "原文", "标题": "原文", "原注": "原注", "任注": "任注", "小标题": "任注"},
        "proof": ["滴天髓_天干官杀", "滴天髓_六亲岁运", "滴天髓_性情疾病"],
    },
    # 三命通会六亲章（中册卷七 484–493）与岁运章（上册卷二 107–115）的卡，文件名以 三命通会_ 起头（2026-09-25）
    "三命通会": {
        "required": ["引文", "出处", "采用规则", "叙事译法", "初稿写法", "核对", "差异", "裁决", "状态"],
        "quotes": {"引文": "正文"},
        "pools": {"正文": "正文", "歌诀": "正文", "表格": "正文", "标题": "正文", "校者注": "校者注"},
        "proof": "三命通会_六亲岁运",
    },
    "十二长生纳音": {
        "required": ["引文", "出处", "采用规则", "初稿写法", "核对", "差异", "裁决", "状态"],
        "quotes": {"引文": "正文"},
        "pools": {"正文": "正文", "歌诀": "正文", "表格": "正文", "标题": "正文", "校者注": "校者注"},
        "proof": ["三命通会_基础", "三命通会_六十甲子"],
    },
    # 五运六气：《素问》运气七篇，维基文库繁体录入本切篇语料（references/校核/语料/素问_运气.txt），无校对本，
    # 引文直接对语料核；卡文件名以 运气_ 起头。后世推演（平气）的卡引文栏写"无（后世推演……）"，不核
    "运气": {
        "required": ["引文", "出处", "采用规则", "叙事译法", "初稿写法", "核对", "差异", "裁决", "状态"],
        "quotes": {"引文": "正文"},
        "pools": {"正文": "正文"},
        "proof": [],
        "corpus": "素问_运气.txt",
    },
}
REQUIRED_FIELDS = KINDS["调候"]["required"]
QUOTE_FIELDS = KINDS["调候"]["quotes"]
MIN_SENTENCE = 6
LOW = 0.55        # 对网上通行本语料：措辞有异文，阈值放宽
PROOF_LOW = 0.85  # 对校对本：同一本书，应近乎逐字，阈值收紧
PROOF_DIR = Path("source/text")

# 异体与简繁对照：两边都归一到左边
VARIANTS = {
    "後": "后", "於": "于", "隹": "佳", "乾": "干", "祇": "只", "衹": "只", "祗": "只",
    "煞": "杀", "才": "财", "纔": "才", "麤": "粗", "麄": "粗", "斲": "斫", "斵": "斫",
    "□": "",
}
PUNCT = re.compile(r"[\s，。、；：︰！？「」『』“”‘’（）()《》〈〉【】\[\]·…—\-–,.;:!?\"'*]")


def normalize(s: str) -> str:
    s = PUNCT.sub("", s)
    return "".join(VARIANTS.get(ch, ch) for ch in s)


def split_sentences(s: str) -> list[str]:
    parts = re.split(r"[。；！？]", s)
    out = []
    for p in parts:
        p = p.strip().strip("…").strip()
        if p.startswith(("{", "无（", "無（")) or p in ("无", "無", ""):
            continue
        if len(normalize(p)) >= MIN_SENTENCE:
            out.append(p)
    return out


def parse_cards(text: str) -> list[dict]:
    cards = []
    blocks = re.split(r"(?m)^### ", text)[1:]
    for b in blocks:
        head, _, body = b.partition("\n")
        m = re.match(r"((?:调候|神煞|刑冲合害|长生|纳音|格局|十干|性情|疾病|六亲|小儿|何知|出身|地位|岁运|贞元|官杀|伤官|运气)-\S+)", head)
        card = {"id": m.group(1) if m else head.strip(), "fields": {}}
        cur = None
        for line in body.splitlines():
            fm = re.match(r"^- ([^：:]+)[：:]\s*(.*)$", line)
            if fm:
                cur = fm.group(1).strip()
                card["fields"][cur] = fm.group(2)
            elif cur and (line.startswith("    ") or line.startswith("\t")):
                card["fields"][cur] += "\n" + line.strip()
            elif line.startswith("---") or line.startswith("## "):
                break
        cards.append(card)
    return cards


def day_master_of(path: Path, cards: list[dict]) -> str | None:
    m = re.search(r"调候_(.)\.md$", path.name)
    if m:
        return m.group(1)
    for c in cards:
        m = re.match(r"调候-(.)", c["id"])
        if m:
            return m.group(1)
    return None


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("card_file")
    ap.add_argument("--corpus-dir", default="references/校核/语料")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    path = Path(a.card_file)
    if not path.exists():
        print(f"not found: {path}", file=sys.stderr)
        return 2
    text = path.read_text(encoding="utf-8")
    cards = parse_cards(text)
    kind = next((k for k in KINDS if k != "调候" and path.name.startswith(k)), "调候")
    spec = KINDS[kind]
    required, quote_fields = spec["required"], spec["quotes"]
    dm = day_master_of(path, cards) if kind == "调候" else None
    def split_pool(text: str) -> list[str]:
        return [normalize(s) for s in re.split(r"[。；！？\n]", text) if len(normalize(s)) >= MIN_SENTENCE]

    # 优先对校对本：按标签分池，能查出「把注抄成正文」；没有校对本才退回网上通行本
    proof_names = [f"{dm}"] if kind == "调候" else ([spec["proof"]] if isinstance(spec["proof"], str) else spec["proof"])
    proofs = [PROOF_DIR / f"{n}.md" for n in proof_names]
    if kind == "滴天髓":
        proofs = [p for p in proofs if p.exists()]     # 分批校对，有哪份对哪份
    if spec.get("corpus"):
        corpus_path = Path(a.corpus_dir) / spec["corpus"]
        if not corpus_path.exists():
            print(f"corpus not found: {corpus_path}", file=sys.stderr)
            return 2
        pools = {"正文": split_pool(corpus_path.read_text(encoding="utf-8"))}
        source, low = f"通行本语料 {corpus_path}", LOW
    elif proofs and all(p.exists() for p in proofs):
        body = "\n".join(p.read_text(encoding="utf-8") for p in proofs)
        raw = {}
        for m in re.finditer(r"^\[([^\]]+)\]\s*(.*)$", body, flags=re.M):
            pool = spec["pools"].get(m.group(1))
            if pool:
                raw.setdefault(pool, []).append(m.group(2))
        pools = {pool: split_pool("\n".join(raw.get(pool, []))) for pool in set(spec["pools"].values())}
        source, low = "校对本 " + "、".join(str(p) for p in proofs), PROOF_LOW
    else:
        corpus_path = Path(a.corpus_dir) / f"穷通宝鉴_正文_{dm}.txt"
        if dm is None or not corpus_path.exists():
            print(f"neither proof text nor corpus found for day master {dm!r}", file=sys.stderr)
            return 2
        shared = split_pool(corpus_path.read_text(encoding="utf-8"))
        pools = {"正文": shared, "徐注": []}
        source, low = f"通行本语料 {corpus_path}（无校对本，徐注要点不核）", LOW

    def best(sent: str, pool: list[str]) -> float:
        n = normalize(sent)
        return max((difflib.SequenceMatcher(None, n, c).ratio() for c in pool), default=0.0)

    report = {"file": str(path), "kind": kind, "dayMaster": dm, "cards": len(cards), "source": source,
              "missingFields": [], "unmatched": []}
    for c in cards:
        for f in required:
            if f not in c["fields"]:
                report["missingFields"].append({"card": c["id"], "field": f})
        for f, tag in quote_fields.items():
            pool = pools.get(tag, [])
            if not pool:
                continue
            for sent in split_sentences(c["fields"].get(f, "")):
                score = best(sent, pool)
                if score < low:
                    other_tag = next((t for t in pools if t != tag), tag)
                    swapped = pools[other_tag] and best(sent, pools[other_tag]) >= low
                    report["unmatched"].append({"card": c["id"], "field": f, "sentence": sent,
                                                "score": round(score, 2),
                                                "hint": f"在{other_tag}池里能找到，抄错了池" if swapped else ""})

    ok = not report["missingFields"]
    report["ok"] = ok
    if a.json:
        sys.stdout.buffer.write((json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    else:
        lines = [f"{path.name}: {len(cards)} 张{kind}卡" + (f"，日主 {dm}" if dm else "") + f"，核对来源：{source}"]
        for m in report["missingFields"]:
            lines.append(f"  缺字段  {m['card']}  {m['field']}")
        for u in report["unmatched"]:
            lines.append(f"  引文找不到(相似度 {u['score']}){u['hint'] and '，' + u['hint']}  {u['card']}  [{u['field']}]  {u['sentence']}")
        lines.append(("  通过" if ok else f"  未通过：缺字段 {len(report['missingFields'])}") + f"；低相似度提示 {len(report['unmatched'])} 句")
        sys.stdout.buffer.write(("\n".join(lines) + "\n").encode("utf-8"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
