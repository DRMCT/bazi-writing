#!/usr/bin/env python3
"""开发期工具：从《子平真诠评注》（中医古籍出版社 2012，沈孝瞻原著、徐乐吾评注、苏全有等注译，扫描 PDF，自备放 source/ 下）渲染指定印刷页并 OCR。

    python scripts/ocr_ziping.py 86 158 199 310      # 起 止 起 止……，印刷页码

页图存 source/ziping/pages/p{印刷页:03d}.png（三倍渲染，供子代理对图校对），
OCR 存 source/ziping/ocr/p{印刷页:03d}.json：{"page","pdfPage","width","height","lines":[{"box","text","conf"}]}，
行序按版面自上而下、自左而右。已存在的页跳过，可断点续跑。

印刷页与 PDF 页的偏移（2026-09-23 量得）：正文四十八章与附录 pdf = 页 + 73（第 127 页在 pdf 200）；书前综述另有一套页码，不用。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
PDF_GLOB = "*子平真诠*.pdf"   # 按书名找
OFFSET = 73
PAGES = ROOT / "source" / "ziping" / "pages"
OCR = ROOT / "source" / "ziping" / "ocr"
SCALE = 3


def pdf_page(printed: int) -> int:
    return printed + OFFSET


def find_pdf(pattern: str) -> Path:
    hits = sorted((ROOT / "source").glob(pattern))
    if len(hits) != 1:
        sys.exit(f"source/ 下应恰有一个 {pattern}，找到 {len(hits)} 个")
    return hits[0]


def main(argv: list[str]) -> int:
    import numpy as np
    import pypdfium2 as pdfium
    from rapidocr_onnxruntime import RapidOCR

    if len(argv) < 2 or len(argv) % 2:
        print(__doc__); return 2
    ranges = [(int(argv[i]), int(argv[i + 1])) for i in range(0, len(argv), 2)]
    PAGES.mkdir(parents=True, exist_ok=True); OCR.mkdir(parents=True, exist_ok=True)
    pdf = pdfium.PdfDocument(str(find_pdf(PDF_GLOB)))
    ocr = RapidOCR()
    t0 = time.time(); done = 0
    for lo, hi in ranges:
        for printed in range(lo, hi + 1):
            dst = OCR / f"p{printed:03d}.json"
            if dst.exists():
                continue
            pp = pdf_page(printed)
            img = pdf[pp - 1].render(scale=SCALE).to_pil().convert("RGB")
            png = PAGES / f"p{printed:03d}.png"
            if not png.exists():
                img.save(png)
            res, _ = ocr(np.array(img))
            rows = sorted(res or [], key=lambda r: (round(r[0][0][1] / 30), r[0][0][0]))
            lines = [{"box": [[int(p[0]), int(p[1])] for p in box], "text": text, "conf": round(float(conf), 4)}
                     for box, text, conf in rows]
            dst.write_text(json.dumps({"page": printed, "pdfPage": pp, "width": img.size[0],
                                       "height": img.size[1], "lines": lines}, ensure_ascii=False), encoding="utf-8")
            done += 1
            if done % 10 == 0:
                print(f"{done} pages, {time.time() - t0:.0f}s", flush=True)
    print(f"done: {done} new pages, total {len(list(OCR.glob('*.json')))}, {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
