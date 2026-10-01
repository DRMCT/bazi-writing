"""师承文本导入（import_shicheng.py）：epub 按页切、页里多章再切、--split 全书按标题切；txt 按整行标题切；
简介、番外、杂行、断号与正文里像章标题的行都进报告。"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import import_shicheng as im  # noqa: E402

BODY = "她推开门，屋里的灯还亮着，桌上一碗汤已经凉了。" * 20  # 约四百六十个汉字，过 min-chars


def make_epub(path: Path, pages: list[str]) -> None:
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("META-INF/container.xml", '<container><rootfiles><rootfile full-path="OEBPS/content.opf"/></rootfiles></container>')
        items = "".join(f'<item id="p{i}" href="p{i}.xhtml"/>' for i in range(len(pages)))
        refs = "".join(f'<itemref idref="p{i}"/>' for i in range(len(pages)))
        z.writestr("OEBPS/content.opf", f"<package><manifest>{items}</manifest><spine>{refs}</spine></package>")
        for i, p in enumerate(pages):
            z.writestr(f"OEBPS/p{i}.xhtml", f"<html><head><title>x</title></head><body>{p}</body></html>")


def page(title: str, *lines: str) -> str:
    return f"<h2>{title}</h2>" + "".join(f"<p>{l}</p>" for l in lines)


def run(args: list[str], capsys) -> dict:
    code = im.main(args)
    out = capsys.readouterr().out.strip().splitlines()[-1]
    rep = json.loads(out)
    rep["_code"] = code
    return rep


def headings(p: Path) -> list[str]:
    out = []  # 按顺序认第1章、第2章……，正文里混进的像标题的行不算
    for l in p.read_text(encoding="utf-8").split("\n"):
        if l.startswith(f"第{len(out) + 1}章 "):
            out.append(l)
    return out


def test_epub_pages_intro_extras_noise_and_gaps(tmp_path: Path, capsys) -> None:
    pages = [
        page("内容简介", "一个关于灶台的故事。" * 50),  # 标题是简介：进简介，不算章
        page("第一章 开张", BODY, "求月票！求推荐票！", "原本站在门口的人走了进来。"),  # 求票删；"原本站在"不是水印
        page("第2章 来客", "第002章", BODY, "第3章 混进正文的一行", BODY),  # 开头的标题残行删；正文中间一行像标题：不切，括起来，报 strayHeadings
        page("第4章 算账", BODY, "作者有话要说：", "谢谢大家的支持。"),  # 第 3 章缺：报断号；作者有话说到章末删
        page("第5章 收尾", BODY, "（正文完）"),
        page("番外一 灶神", BODY),
    ]
    src = tmp_path / "书.epub"
    make_epub(src, pages)
    rep = run([str(src), "--name", "某书", "--out", str(tmp_path / "师承")], capsys)
    assert rep["_code"] == 0 and rep["mode"] == "epub" and rep["chapters"] == 4 and rep["extras"] == 1
    assert rep["introChars"] > 0 and rep["gaps"] == [{"after": 2, "missing": "3"}]
    assert rep["strayHeadings"] == [{"chapter": 2, "line": "第3章 混进正文的一行"}]
    assert rep["noise"] == {"求票": 1, "作者有话说": 2, "标题残行": 1}
    out = tmp_path / "师承"
    assert headings(out / "某书.txt") == ["第1章 开张", "第2章 来客", "第3章 算账", "第4章 收尾"]
    text = (out / "某书.txt").read_text(encoding="utf-8")
    assert "原本站在门口" in text and "求月票" not in text and "谢谢大家" not in text
    assert "〔第3章 混进正文的一行〕" in text and "\n第002章\n" not in text
    assert (out / "某书.番外.txt").exists() and "灶台" in (out / "某书.简介.txt").read_text(encoding="utf-8")


def test_epub_page_holding_several_chapters_and_split_override(tmp_path: Path, capsys) -> None:
    src = tmp_path / "合页.epub"
    make_epub(src, [page("卷一", "第1章 甲", BODY, "第2章 乙", BODY, "第3章 丙", BODY)])
    rep = run([str(src), "--name", "合页", "--out", str(tmp_path), "--dry-run"], capsys)
    assert rep["chapters"] == 3 and rep["gaps"] == [] and not (tmp_path / "合页.txt").exists()
    # 章号藏在正文里的书：给 --split，不看页，全书按标题行切
    src2 = tmp_path / "藏号.epub"
    make_epub(src2, [page("——", "这是第一章", BODY), page("杂", BODY, "这是第二章", BODY)])
    rep = run([str(src2), "--name", "藏号", "--out", str(tmp_path), "--split", r"^这是第[一二三四五六七八九十]+章$"], capsys)
    assert rep["mode"] == "epub+split" and rep["chapters"] == 2


def test_txt_numbered_titles_and_gb18030(tmp_path: Path, capsys) -> None:
    text = "\n".join(["书名", "作者：某人", "001：初见（1）", BODY, "002：初见（2）", BODY, "002：初见（2）", BODY, "后记", BODY])
    src = tmp_path / "书.txt"
    src.write_bytes(text.encode("gb18030"))
    rep = run([str(src), "--name", "编号", "--out", str(tmp_path)], capsys)
    assert rep["mode"] == "txt" and rep["chapters"] == 3 and rep["extras"] == 1
    assert rep["dups"] == [{"chapter": 3, "original": 2}] and rep["numbered"] == 3
    assert headings(tmp_path / "编号.txt") == ["第1章 初见（1）", "第2章 初见（2）", "第3章 初见（2）"]
    assert "作者：某人" in (tmp_path / "编号.简介.txt").read_text(encoding="utf-8")


def test_chinese_numerals() -> None:
    assert [im.cn2int(x) for x in ("十", "十二", "二十", "一百零五", "两百三十四", "１２", "〇")] == [10, 12, 20, 105, 234, 12, 0]
    assert im.original_number("第二百六十七章（一章但两章的字数）") == 267 and im.original_number("258：一岁") == 258
    assert im.bare_title("第001章 觉醒") == "觉醒" and im.bare_title("001：萧四小姐（1）") == "萧四小姐（1）"
