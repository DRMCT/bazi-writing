#!/usr/bin/env python3
"""开发期工具：从《四库版足本三命通会》（华龄出版社，上中下三册扫描 PDF，自备放 source/ 下）渲染指定印刷页并 OCR。

    python scripts/ocr_sanming.py 上 125 200
    python scripts/ocr_sanming.py 中 346 351 374 378      # 多段：起 止 起 止……

页图存 source/sanming/pages/{册}{印刷页:03d}.png（三倍渲染，供子代理对图校对），
OCR 存 source/sanming/ocr/{册}{印刷页:03d}.json：{"volume","page","pdfPage","lines":[{"box","text","conf"}]}，
行序按版面自上而下、自左而右。已存在的页跳过，可断点续跑。全书排版一种字体，不算笔画比。

印刷页与 PDF 页的偏移（2026-09-22 量得）：上册 pdf = 页 + 8；中册 pdf = 页 − 272；下册 pdf = 页 − 589。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
PDF_GLOBS = {"上": "*三命通会*上*.pdf", "中": "*三命通会*中*.pdf", "下": "*三命通会*下*.pdf"}   # 按书名与册名找
OFFSET = {"上": 8, "中": -272, "下": -589}
PAGES = ROOT / "source" / "sanming" / "pages"
OCR = ROOT / "source" / "sanming" / "ocr"
SCALE = 3


def pdf_page(volume: str, printed: int) -> int:
    return printed + OFFSET[volume]


def find_pdf(pattern: str) -> Path:
    hits = sorted((ROOT / "source").glob(pattern))
    if len(hits) != 1:
        sys.exit(f"source/ 下应恰有一个 {pattern}，找到 {len(hits)} 个")
    return hits[0]


def main(argv: list[str]) -> int:
    import numpy as np
    import pypdfium2 as pdfium
    from rapidocr_onnxruntime import RapidOCR

    if len(argv) < 3 or len(argv) % 2 == 0 or argv[0] not in PDF_GLOBS:
        print(__doc__); return 2
    volume = argv[0]
    ranges = [(int(argv[i]), int(argv[i + 1])) for i in range(1, len(argv), 2)]
    PAGES.mkdir(parents=True, exist_ok=True); OCR.mkdir(parents=True, exist_ok=True)
    pdf = pdfium.PdfDocument(str(find_pdf(PDF_GLOBS[volume])))
    ocr = RapidOCR()
    t0 = time.time(); done = 0
    for lo, hi in ranges:
        for printed in range(lo, hi + 1):
            dst = OCR / f"{volume}{printed:03d}.json"
            if dst.exists():
                continue
            pp = pdf_page(volume, printed)
            img = pdf[pp - 1].render(scale=SCALE).to_pil().convert("RGB")
            png = PAGES / f"{volume}{printed:03d}.png"
            if not png.exists():
                img.save(png)
            res, _ = ocr(np.array(img))
            rows = sorted(res or [], key=lambda r: (round(r[0][0][1] / 30), r[0][0][0]))
            lines = [{"box": [[int(p[0]), int(p[1])] for p in box], "text": text, "conf": round(float(conf), 4)}
                     for box, text, conf in rows]
            dst.write_text(json.dumps({"volume": volume, "page": printed, "pdfPage": pp, "width": img.size[0],
                                       "height": img.size[1], "lines": lines}, ensure_ascii=False), encoding="utf-8")
            done += 1
            if done % 10 == 0:
                print(f"{done} pages, {time.time() - t0:.0f}s", flush=True)
    print(f"done: {done} new pages, total {len(list(OCR.glob('*.json')))}, {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
