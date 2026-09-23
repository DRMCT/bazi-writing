#!/usr/bin/env python3
"""開發期工具：校對本質量抽檢。

    python scripts/audit_text.py 甲
讀 source/text/甲.md（apply_fixes 生成的校對本），輸出：
  1. 標籤統計與剩餘 [?]；
  2. [正文] 段與網上通行本語料的相似度，低於閾值的列出（可能是徐注誤標正文，或正文誤標徐注的反面：
     順帶列出 [徐注] 段中相似度很高的，可能是正文誤標徐注）；
  3. 常見 OCR 形近錯字的殘留計數，按上下文粗篩：
     「王」非「王水」外的出現（本書幾乎只有壬）、「已」後接土/卯/酉等干支字、「成」在干支上下文、「末」、
     「葵」、「卵」。
只做提示，不改文件。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_cards as cc  # noqa: E402
import tag_ocr  # noqa: E402

LOW_ZW, HIGH_XZ = 0.55, 0.80
SUSPECTS = [
    ("王(?!水)", "王 疑为壬"),
    ("[甲乙丙丁戊己庚辛壬癸]已|已[子丑寅卯辰巳午未申酉戌亥土]", "已 疑为己/巳"),
    ("[寅午申子辰巳酉丑亥卯未]成|成[子丑寅卯辰巳午未申酉戌亥]", "成 疑为戌"),
    ("末", "末 疑为未"),
    ("葵", "葵 疑为癸"),
    ("卵", "卵 疑为卯"),
    ("康金", "康 疑为庚"),
    ("□", "□ 未识别"),
]


def main(argv: list[str]) -> int:
    dm = argv[0]
    path = Path("source/text") / f"{dm}.md"
    text = path.read_text(encoding="utf-8")
    paras = [(m.group(1), m.group(2)) for m in re.finditer(r"^\[([^\]]+)\]\s*(.*)$", text, flags=re.M)]
    corpus = tag_ocr.load_corpus(dm)
    stats: dict[str, int] = {}
    for tag, _ in paras:
        stats[tag] = stats.get(tag, 0) + 1
    print(f"{path.name}: {len(paras)} 段 {stats}")
    print("\n== [正文] 中与语料相似度低的段（可能误标或异文，请看图） ==")
    for tag, body in paras:
        if tag == "正文" and len(cc.normalize(body)) >= 8:
            s = tag_ocr.best_sim(body, corpus)
            if s < LOW_ZW:
                print(f"  {s:.2f}  {body[:40]}")
    print("\n== [徐注] 中与语料相似度高的段（可能是正文误标徐注） ==")
    for tag, body in paras:
        if tag == "徐注" and len(cc.normalize(body)) >= 8:
            s = tag_ocr.best_sim(body, corpus)
            if s > HIGH_XZ:
                print(f"  {s:.2f}  {body[:40]}")
    print("\n== 形近错字残留（只看正文、徐注、校记） ==")
    joined = "\n".join(b for t, b in paras if t in ("正文", "徐注", "校记"))
    for pat, label in SUSPECTS:
        hits = [m for m in re.finditer(pat, joined)]
        if hits:
            ctx = "；".join(joined[max(0, h.start() - 4): h.end() + 4].replace("\n", " ") for h in hits[:6])
            print(f"  {label}: {len(hits)} 处  例：{ctx}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
