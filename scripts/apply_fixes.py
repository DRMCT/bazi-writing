#!/usr/bin/env python3
"""開發期工具：把校對員寫的修正清單套用到 OCR 自動打標文本，生成校對本。

    python scripts/apply_fixes.py 乙
讀 source/text/乙.tagged.md 與 source/text/乙.fixes.md，寫 source/text/乙.md。

修正清單每行一條，四種形式（豎線分隔，前後空格隨意）：
    p040 | 故庚王为最要用神 => 故庚壬为最要用神        改字：片段在該頁必須恰好出現一次
    p039 | [徐注] 茂才而止 => [例盘]                    改標籤：以段首幾個字定位該頁的段
    p038 | 删 | 四库存目子平汇刊                        刪段：以段首幾個字定位
    p040 | 合并 | 贵艰难，得壬癸                        併段：把該段併入上一段（換行誤切）
    p068 | 增首 | [标题] 命理秘本穷通宝鉴卷二            增段：插在該頁最前
    p070 | 增 | 二月乙木，阳气 | [校记] ②此节抄本无      增段：插在以該幾個字起頭的段之後
行首 # 為註釋。片段匹配不含行末的特徵括號。套用失敗的條目逐條列出，退出碼 1。
輸出去掉行末特徵括號，保留頁碼標記與標籤。

注意：輸出會整份覆蓋校對本。直接改在校對本上的回改（如「王水」→「壬水」）重跑就丟，
回改一律寫進 fixes 清單再套用。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# 行末特徵括號：穷通宝鉴三個數（筆畫比, 相似度, 置信度），三命通会一個數（置信度）
FEAT = re.compile(r"\s*（[\d.]+(?:, [\d.]+){0,2}）\s*$")
TAG = re.compile(r"^\[([^\]]+)\]\s*")
HALF_COMMA = re.compile(r"(?<=[\u4e00-\u9fff）」》])\,(?=[\u4e00-\u9fff（「《])")
# 頁碼標記：穷通宝鉴 p040（PDF 頁），三命通会 上146 / 中376（印刷頁）
PAGE_ID = r"[p上中下]\d{3}"


def load_pages(tagged: str) -> list[tuple[str, list[str]]]:
    pages: list[tuple[str, list[str]]] = []
    cur = None
    for line in tagged.splitlines():
        m = re.match(rf"<!-- ({PAGE_ID})( 缺 OCR)? -->", line)
        if m:
            cur = (m.group(1), [])
            pages.append(cur)
            continue
        if cur is None or not line.strip():
            continue
        cur[1].append(FEAT.sub("", line))
    return pages


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__); return 2
    dm = argv[0]
    base = Path("source/text")
    tagged = (base / f"{dm}.tagged.md").read_text(encoding="utf-8")
    # 清單：{dm}.fixes.md 加分批的 {dm}.fixes.{批次}.md，按文件名順序合併
    fixes: list[str] = []
    for fp in sorted([base / f"{dm}.fixes.md"] + list(base.glob(f"{dm}.fixes.*.md"))):
        if fp.exists():
            fixes.extend(fp.read_text(encoding="utf-8").splitlines())
    pages = load_pages(tagged)
    index = {p: paras for p, paras in pages}
    failed: list[str] = []
    applied = 0

    def find_para(paras: list[str], head: str) -> int:
        hits = [i for i, x in enumerate(paras) if TAG.sub("", x).startswith(head)]
        if len(hits) != 1:
            return -1
        return hits[0]

    for raw in fixes:
        line = raw.strip()
        if not re.match(rf"^{PAGE_ID}\s*\|", line):
            continue  # 註釋、報告節等非條目行一律忽略
        parts = [x.strip() for x in line.split("|")]
        if len(parts) < 2 or parts[0] not in index:
            failed.append(f"页码错或不在范围内：{raw}"); continue
        paras = index[parts[0]]
        body = "|".join(parts[1:])
        if parts[1] == "删" and len(parts) == 3:
            i = find_para(paras, parts[2])
            if i < 0: failed.append(f"删：找不到或不唯一：{raw}"); continue
            del paras[i]; applied += 1; continue
        if parts[1] == "增首" and len(parts) == 3:
            paras.insert(0, parts[2]); applied += 1; continue
        if parts[1] == "增" and len(parts) == 4:
            i = find_para(paras, parts[2])
            if i < 0: failed.append(f"增：找不到或不唯一：{raw}"); continue
            paras.insert(i + 1, parts[3]); applied += 1; continue
        if parts[1] == "合并" and len(parts) == 3:
            i = find_para(paras, parts[2])
            if i <= 0: failed.append(f"合并：找不到或已是首段：{raw}"); continue
            paras[i - 1] = paras[i - 1] + TAG.sub("", paras[i]); del paras[i]; applied += 1; continue
        if "=>" not in body:
            failed.append(f"缺 =>：{raw}"); continue
        old, new = [x.strip() for x in body.split("=>", 1)]
        mt = re.match(r"^\[([^\]]+)\]\s*(.*)$", old)
        if mt and re.fullmatch(r"\[[^\]]+\]", new):
            i = find_para(paras, mt.group(2))
            if i < 0 or not paras[i].startswith(f"[{mt.group(1)}]"):
                failed.append(f"改标签：找不到或旧标签不符：{raw}"); continue
            paras[i] = new + " " + TAG.sub("", paras[i]); applied += 1; continue
        joined = "\n".join(paras)
        n = joined.count(old)
        if n != 1:
            failed.append(f"改字：片段出现 {n} 次，需恰好一次：{raw}"); continue
        joined = joined.replace(old, new)
        paras[:] = joined.split("\n"); applied += 1

    title = f"《穷通宝鉴评注》{dm} 日主校对本" if len(dm) == 1 else f"{dm} 校对本"
    out = [f"# {title}\n"]
    for p, paras in pages:
        out.append(f"\n<!-- {p} -->\n")
        # OCR 留下的半角逗号夹在汉字之间的统一转全角（通用规则，不进清单）
        out.extend(HALF_COMMA.sub("，", x) + "\n" for x in paras)
    (base / f"{dm}.md").write_text("".join(out), encoding="utf-8")
    remaining = sum(1 for _, paras in pages for x in paras if x.startswith("[?]"))
    print(f"{dm}: 套用 {applied} 条，失败 {len(failed)} 条，剩余 [?] {remaining} 段 → {base / (dm + '.md')}")
    for f in failed:
        print("  ", f)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
