#!/usr/bin/env python3
"""開發期工具：用 RapidOCR 把 source/pages/pNNN.png 逐頁識別，存 source/ocr/pNNN.json。

每頁 JSON：{"page": N, "lines": [{"box": [[x,y]×4], "text": "...", "conf": 0.98,
"aniso": 0.91}]}，行序按版面自上而下、自左而右。aniso 是該行墨跡的「豎筆寬 / 橫筆厚」，
楷體（余春台正文）約 0.85–1.1，宋體（徐樂吾評注）約 0.4–0.7，用來自動區分正文與徐注。

只在校核階段用，運行期不需要。依賴 rapidocr-onnxruntime、pillow、numpy（pip）。
已存在的頁跳過，可斷點續跑。用法：python scripts/ocr_pages.py [起頁 止頁]
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path


def _runs(mask, axis: int) -> float:
    import numpy as np
    m = mask if axis == 1 else mask.T
    lens = []
    for row in m:
        r = row.astype(np.int8)
        d = np.diff(np.concatenate(([0], r, [0])))
        lens.extend((np.where(d == -1)[0] - np.where(d == 1)[0]).tolist())
    return float(np.mean(lens)) if lens else 0.0


def anisotropy(gray, box) -> float:
    import numpy as np
    xs = [p[0] for p in box]; ys = [p[1] for p in box]
    x0, x1, y0, y1 = int(min(xs)), int(max(xs)), int(min(ys)), int(max(ys))
    crop = gray[y0:y1, x0:x1] < 140
    if crop.size == 0:
        return 0.0
    v, h = _runs(crop, 1), _runs(crop, 0)
    return round(v / h, 3) if h else 0.0


def main(argv: list[str]) -> int:
    import numpy as np
    from PIL import Image, ImageOps
    from rapidocr_onnxruntime import RapidOCR
    pages = Path("source/pages"); out = Path("source/ocr"); out.mkdir(exist_ok=True)
    files = sorted(pages.glob("p*.png"))
    if argv:
        lo, hi = int(argv[0]), int(argv[1])
        files = [f for f in files if lo <= int(f.stem[1:]) <= hi]
    ocr = RapidOCR()
    t0 = time.time(); done = 0
    for f in files:
        dst = out / (f.stem + ".json")
        if dst.exists():
            continue
        gray = np.asarray(ImageOps.grayscale(Image.open(f)))
        res, _ = ocr(str(f))
        rows = sorted(res or [], key=lambda r: (round(r[0][0][1] / 20), r[0][0][0]))
        lines = [{"box": [[int(p[0]), int(p[1])] for p in box], "text": text, "conf": round(float(conf), 4),
                  "aniso": anisotropy(gray, box)} for box, text, conf in rows]
        dst.write_text(json.dumps({"page": int(f.stem[1:]), "lines": lines}, ensure_ascii=False), encoding="utf-8")
        done += 1
        if done % 20 == 0:
            print(f"{done} pages, {time.time()-t0:.0f}s", flush=True)
    print(f"done: {done} new pages, total {len(list(out.glob('p*.json')))}, {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
