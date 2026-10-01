"""师承文本导入：epub 或 txt → 书/师承/{书名}.txt，一章一个整行"第N章 标题"，供量尺与读法卡用。

    python scripts/import_shicheng.py 原书.epub --name 恶女 --out 书/师承
    python scripts/import_shicheng.py 原书.txt --name 恶女 --out 书/师承 [--split <regex>]

切章：epub 按 spine 一页一章（页里又有两个以上"第N章"整行的，再按它切；给了 `--split` 就不看页，全书按标题行切）；txt 按整行的"第N章/第N回"、
"001：标题"一类标题切，`--split` 给整行正则覆盖。汉字少于 `--min-chars`（默认 400）的页不算章：正文之前的进简介（标题是内容简介、文案一类的也进），
其余记进报告的 dropped。"正文完、全文完"所在章之后，与标题以番外、后记、完结感言起头、或正文之后章号为零的章，进 {书名}.番外.txt。
清掉的杂行：求票、作者有话说（到章末）、站点水印与网址一类，按条数报。

产物：{书名}.txt、{书名}.番外.txt（有就写）、{书名}.简介.txt（有就写），UTF-8 无 BOM、LF；
重新编号从 1 起，原标题去掉自带的章号留在后面。stdout 一行 JSON 报告：章数、汉字、章长中位数与十分位，
特别短（不到中位数三成）与特别长（中位数两倍半以上）的章，原章号的断号与重号，正文里像章标题的行（开头两行内的当标题残行删，
更靠后的用〔〕括起来），清掉的杂行，丢掉的短页，头尾几章的标题。主会话看报告，不对就换 --split 或手修文本再跑。
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import zipfile
from pathlib import Path

CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNITS = {"十": 10, "百": 100, "千": 1000}
NUM = r"[0-9０-９零〇一二三四五六七八九十百千两]+"
CHAPTER_RE = re.compile(rf"^\s*第\s*{NUM}\s*[章回节](?:\s|[：:、.．]|$)")
NUMBERED_RE = re.compile(r"^\s*[0-9０-９]{1,4}\s*[：:、．.]\s*\S")
SPECIAL_RE = re.compile(r"^\s*(楔子|序章|序|引子|尾声|番外|后记|完结感言|作者的话)(\s|[：:、.．（(一二三四五六七八九十0-9]|$)")
EXTRA_TITLE_RE = re.compile(r"^\s*(番外|后记|完结感言|作者的话|新书|感言)")
INTRO_TITLE_RE = re.compile(r"^\s*(内容简介|作品简介|简介|文案|内容提要|作品相关)\s*$")
END_RE = re.compile(r"[（(]?(正文完|全文完|正文完结|全书完|大结局完)[）)]?")
NOISE = [
    ("求票", re.compile(r"求(月票|推荐票|票票|收藏|订阅|评论|打赏)|月票.{0,6}(加更|求)|推荐票")),
    ("站点水印", re.compile(r"(请记住本站|本站地址|本站域名|最新章节|手机阅读|无弹窗|笔趣阁|首发于|首发网站|txt下载|全文阅读|天才一秒记住)")),
    ("网址", re.compile(r"(https?://|www\.|\.com|\.net|\.org)", re.I)),
    ("本章完", re.compile(r"^\s*[（(【]?\s*本章完\s*[）)】]?\s*$")),
]
AUTHOR_NOTE_RE = re.compile(r"^\s*(作者有话要说|作者有话说|作者的话)\s*[：:]?")

han = lambda s: len(re.findall(r"[一-鿿]", s))


def cn2int(s: str) -> int | None:
    s = s.translate(str.maketrans("０１２３４５６７８９", "0123456789")).strip()
    if s.isdigit():
        return int(s)
    total, cur = 0, 0
    for ch in s:
        if ch in CN_DIGITS:
            cur = CN_DIGITS[ch]
        elif ch in CN_UNITS:
            total += (cur or 1) * CN_UNITS[ch]
            cur = 0
        else:
            return None
    return total + cur


def original_number(title: str) -> int | None:
    m = re.match(rf"^\s*第\s*({NUM})\s*[章回节]", title) or re.match(r"^\s*([0-9０-９]{1,4})\s*[：:、．.]", title)
    return cn2int(m.group(1)) if m else None


def bare_title(title: str) -> str:
    t = re.sub(rf"^\s*第\s*{NUM}\s*[章回节]\s*[：:、.．]?\s*", "", title)
    t = re.sub(r"^\s*[0-9０-９]{1,4}\s*[：:、．.]\s*", "", t)
    return t.strip() or title.strip()


def clean_html(t: str) -> list[str]:
    t = re.sub(r"(?is)<(script|style|head)\b.*?</\1>", "", t)
    t = re.sub(r"(?i)<br\s*/?>", "\n", t)
    t = re.sub(r"(?i)</(p|div|h\d|li|tr)>", "\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t).replace("　", " ").replace("\xa0", " ")
    return [l.strip() for l in t.split("\n") if l.strip()]


def read_epub(path: Path) -> list[list[str]]:
    z = zipfile.ZipFile(path)
    container = z.read("META-INF/container.xml").decode("utf-8", "ignore") if "META-INF/container.xml" in z.namelist() else ""
    m = re.search(r'full-path="([^"]+)"', container)
    opf = m.group(1) if m else next(n for n in z.namelist() if n.endswith(".opf"))
    o = z.read(opf).decode("utf-8", "ignore")
    base = os.path.dirname(opf)
    manifest = {}
    for item in re.findall(r"<item\b[^>]*>", o):
        i, h = re.search(r'\bid="([^"]+)"', item), re.search(r'\bhref="([^"]+)"', item)
        if i and h:
            manifest[i.group(1)] = h.group(1)
    docs = []
    for sid in re.findall(r'<itemref\b[^>]*idref="([^"]+)"', o):
        href = manifest.get(sid)
        if not href:
            continue
        p = os.path.normpath(os.path.join(base, href)).replace("\\", "/") if base else href
        try:
            lines = clean_html(z.read(p).decode("utf-8", "ignore"))
        except KeyError:
            continue
        if lines:
            docs.append(lines)
    return docs


def read_txt(path: Path) -> list[str]:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "gb18030", "big5"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", "ignore")
    return [l.strip() for l in text.replace("　", " ").splitlines() if l.strip()]


def is_heading(line: str, split_re: re.Pattern | None) -> bool:
    if split_re is not None:
        return bool(split_re.match(line))
    if len(line) > 40:
        return False
    return bool(CHAPTER_RE.match(line) or NUMBERED_RE.match(line) or SPECIAL_RE.match(line))


def split_lines(lines: list[str], split_re: re.Pattern | None) -> tuple[list[str], list[dict]]:
    """整行标题切章；第一个标题之前的行原样返回（简介或前言）。"""
    head, units, cur = [], [], None
    for l in lines:
        if is_heading(l, split_re):
            cur = {"title": l, "body": []}
            units.append(cur)
        elif cur is None:
            head.append(l)
        else:
            cur["body"].append(l)
    return head, units


def units_from_epub(docs: list[list[str]], split_re: re.Pattern | None) -> list[dict]:
    units = []
    for lines in docs:
        k = 1
        while k < min(3, len(lines)) and CHAPTER_RE.match(lines[k]) and len(lines[k]) <= 40:
            k += 1  # 标题下面紧跟的一两行旧章号是标题残行，不算页里另起的章
        strict = [l for l in lines[k:] if (split_re.match(l) if split_re else CHAPTER_RE.match(l) and len(l) <= 40)]
        if len(strict) >= 2:  # 一页装了几章：按页里的章标题再切
            head, sub = split_lines(lines, split_re or CHAPTER_RE)
            if head:
                units.append({"title": head[0], "body": head[1:]})
            units.extend(sub)
            continue
        title, body = lines[0], lines[1:]
        if body and body[0] == title:
            body = body[1:]
        units.append({"title": title, "body": body})
    return units


def strip_noise(body: list[str], counts: dict) -> list[str]:
    out = []
    for l in body:
        if AUTHOR_NOTE_RE.match(l):
            counts["作者有话说"] = counts.get("作者有话说", 0) + 1 + (len(body) - body.index(l) - 1)
            break
        hit = next((k for k, r in NOISE if r.search(l) and han(l) <= 40), None)
        if hit:
            counts[hit] = counts.get(hit, 0) + 1
            continue
        out.append(l)
    return out


def fix_stray(body: list[str], counts: dict, stray: list[str]) -> list[str]:
    """正文里像章标题的行：开头两行内的是标题残行，删；更靠后的用〔〕括起来，下游按整行切章时不会切错。"""
    looks = lambda l: bool(CHAPTER_RE.match(l)) and len(l) <= 40
    k = 0
    while k < min(2, len(body)) and looks(body[k]):
        k += 1
    if k:
        counts["标题残行"] = counts.get("标题残行", 0) + k
    out = []
    for l in body[k:]:
        if looks(l):
            stray.append(l)
            l = f"〔{l}〕"
        out.append(l)
    return out


def build(units: list[dict], intro_head: list[str], min_chars: int) -> dict:
    noise: dict[str, int] = {}
    intro = list(intro_head)
    chapters, extras, dropped = [], [], []
    in_extra = False
    for u in units:
        stray: list[str] = []
        body = fix_stray(strip_noise(u["body"], noise), noise, stray)
        n = han("".join(body))
        title = u["title"].strip()
        if INTRO_TITLE_RE.match(title) and not chapters:
            intro.extend([title] + body)
            continue
        if not in_extra and chapters and (EXTRA_TITLE_RE.match(title) or original_number(title) == 0):
            in_extra = True  # 番外、后记，或正文之后的第000章
        if n < min_chars:
            if not chapters and not in_extra:
                intro.extend([title] + body)
            else:
                dropped.append(title[:30])
            continue
        (extras if in_extra else chapters).append({"title": title, "body": body, "han": n, "stray": stray})
        if not in_extra and any(END_RE.search(l) for l in body[-3:]):
            in_extra = True
    return {"chapters": chapters, "extras": extras, "intro": intro, "dropped": dropped, "noise": noise}


def report(name: str, src: Path, mode: str, r: dict) -> dict:
    ch = r["chapters"]
    lens = sorted(c["han"] for c in ch)
    med = lens[len(lens) // 2] if lens else 0
    nums = [original_number(c["title"]) for c in ch]
    gaps, dups, seen, prev = [], [], set(), None
    for k, n in enumerate(nums, 1):
        if n is None:
            continue
        if n in seen:
            dups.append({"chapter": k, "original": n})
        elif prev is not None and n > prev + 1:
            gaps.append({"after": k - 1, "missing": f"{prev + 1}" if n == prev + 2 else f"{prev + 1}-{n - 1}"})
        seen.add(n)
        prev = n if prev is None or n > prev else prev
    stray = [{"chapter": k, "line": l[:30]} for k, c in enumerate(ch, 1) for l in c["stray"]]
    return {
        "name": name, "source": src.name, "mode": mode,
        "chapters": len(ch), "han": sum(lens), "median": med,
        "p10": lens[len(lens) // 10] if lens else 0, "p90": lens[len(lens) * 9 // 10] if lens else 0,
        "numbered": sum(n is not None for n in nums),
        "short": [k for k, c in enumerate(ch, 1) if c["han"] < med * 0.3],
        "long": [k for k, c in enumerate(ch, 1) if med and c["han"] > med * 2.5],
        "gaps": gaps, "dups": dups, "strayHeadings": stray[:20],
        "noise": r["noise"], "extras": len(r["extras"]), "introChars": han("".join(r["intro"])), "dropped": r["dropped"][:20],
        "head": [c["title"][:30] for c in ch[:3]], "tail": [c["title"][:30] for c in ch[-3:]],
    }


def write(out_dir: Path, name: str, r: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    def dump(path: Path, cs: list[dict]) -> None:
        with open(path, "w", encoding="utf-8", newline="\n") as w:
            for k, c in enumerate(cs, 1):
                w.write(f"第{k}章 {bare_title(c['title'])}\n" + "\n".join(c["body"]) + "\n")

    dump(out_dir / f"{name}.txt", r["chapters"])
    if r["extras"]:
        dump(out_dir / f"{name}.番外.txt", r["extras"])
    if r["intro"]:
        (out_dir / f"{name}.简介.txt").write_text("\n".join(r["intro"]) + "\n", encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="师承文本导入：epub 或 txt 切成一章一个整行第N章")
    ap.add_argument("source")
    ap.add_argument("--name", required=True, help="书名简称，产物文件名用它")
    ap.add_argument("--out", default="书/师承")
    ap.add_argument("--split", help="章标题整行正则，覆盖默认")
    ap.add_argument("--min-chars", type=int, default=400, help="汉字少于它的页不算章")
    ap.add_argument("--dry-run", action="store_true", help="只报不写")
    a = ap.parse_args(argv)
    src = Path(a.source)
    split_re = re.compile(a.split) if a.split else None
    if src.suffix.lower() == ".epub" and split_re is not None:  # 给了标题正则：不按页，全书按标题行切
        head, units = split_lines([l for d in read_epub(src) for l in d], split_re)
        mode = "epub+split"
    elif src.suffix.lower() == ".epub":
        units, head, mode = units_from_epub(read_epub(src), None), [], "epub"
    else:
        head, units = split_lines(read_txt(src), split_re)
        mode = "txt"
    r = build(units, head, a.min_chars)
    rep = report(a.name, src, mode, r)
    if not a.dry_run:
        write(Path(a.out), a.name, r)
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False))
    return 0 if r["chapters"] else 1


if __name__ == "__main__":
    sys.exit(main())
