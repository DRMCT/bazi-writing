"""文档自检：几条靠记记不住的规矩交给测试。

- 公开的文件（export_public 导出的全部，含设计稿、examples、测试）里不出现测试书与样例书的人名书名，文件名也查；名单在私有文件，公开版没有就跳过。
- 任务书与模板不写日期（改进 skill 的文字不带日期、人名、书名）。
- 任务书标题里的"流程第 N 步"与 SKILL 流程节对得上。
- 任务书引的 命盘/、人物/ 产物都在 SKILL 的目录图里。
- 模板、检查器、任务书说的字段与项数同源：读法卡、文风卡、戏用页。
- 运行时文件（SKILL、任务书、模板、问法、用法、术语表）不指着设计稿与决策记录；SKILL 与用法不写日期；SKILL 只留路由（不超过两百二十行），它点到的文件都在。
- 设计稿只写现在（DESIGN.md 0c）：不写日期，经过进 决策/；有字数上限。
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
SKILL = ROOT / "SKILL.md"
REFS = ROOT / "references"
DENY = Path(__file__).resolve().parent / "fixtures" / "样例书词表.私有.txt"
TASK_BOOKS = sorted((REFS / "任务书").glob("*.md")) + sorted((REFS / "写作层" / "任务书").glob("*.md"))

CN = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def cn_num(s: str) -> int:
    if "十" not in s:
        return CN[s]
    a, b = s.split("十")
    return (CN[a] if a else 1) * 10 + (CN[b] if b else 0)


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def public_files() -> list[str]:
    """export_public 会导出的文件：git 里的（含没提交的新文件），去掉它排除的。"""
    from export_public import excluded  # 这份脚本只在私有库；公开版没有词表，测试先跳过，走不到这里
    out = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                         cwd=ROOT, capture_output=True, check=True).stdout.decode("utf-8").split("\0")
    return [n for n in out if n and not excluded(n) and (ROOT / n).is_file()]


@pytest.mark.skipif(not DENY.exists(), reason="样例书词表只在私有库")
def test_no_test_book_words_in_public_files() -> None:
    words = [w.strip() for w in read(DENY).splitlines() if w.strip() and not w.startswith("#")]
    bad = []
    for name in public_files():
        try:
            text = name + "\n" + read(ROOT / name)
        except UnicodeDecodeError:
            text = name
        bad += [f"{name}：{w}" for w in words if w in text]
    assert not bad, "公开的文件里有测试书的词（设计稿写实测用角色称：女一、男配、靶子那本）：\n" + "\n".join(bad)


def test_no_dates_in_task_books_and_templates() -> None:
    files = TASK_BOOKS + [REFS / "戏剧层" / "问法.md"]
    for d in (REFS / "写作层" / "模板", REFS / "戏剧层" / "模板"):
        files += [p for p in sorted(d.rglob("*")) if p.is_file()]
    bad = [f"{p.relative_to(ROOT)}:{i}" for p in files for i, line in enumerate(read(p).splitlines(), 1)
           if re.search(r"20\d\d-\d\d-\d\d", line)]
    assert not bad, "任务书与模板里有日期：\n" + "\n".join(bad)


STEP_OF = {"构思.md": (0, "构思"), "写档案_命局段.md": (2, "命局段"), "编配.md": (3, "编配"), "写档案_戏用页.md": (4, "戏用页"),
           "事件链.md": (6, "事件链"), "梗概.md": (7, "梗概"), "写档案_年份段.md": (8, "年份段")}


def test_task_book_steps_match_skill_flow() -> None:
    section = read(SKILL).split("## 流程（正推）", 1)[1].split("\n## ", 1)[0]
    flow = {int(m.group(1)): m.group(2) for m in re.finditer(r"^(\d)\. (.+)$", section, re.M)}
    assert sorted(flow) == list(range(10)), flow
    for name, (n, key) in STEP_OF.items():
        title = read(REFS / "任务书" / name).splitlines()[0]
        assert f"（流程第 {n} 步）" in title, (name, title)
        assert key in flow[n], (n, flow[n])
    stale = [p.name for p in [SKILL, *TASK_BOOKS] if re.search(r"流程(节的)?五步", read(p))]
    assert not stale, stale


def norm(path: str) -> str:
    return re.sub(r"\{[^}]*\}", "{}", path).replace("*", "{}")


def skill_tree() -> set[str]:
    block = read(SKILL).split("## 目录", 1)[1].split("```", 2)[1]
    out: set[str] = set()
    top = ""
    for line in block.splitlines():
        if not line.strip():
            continue
        if not line.startswith(" "):
            top = line.split()[0]
        else:
            out.add(norm(top + line.split()[0]))
    return out


def test_task_book_paths_listed_in_skill_tree() -> None:
    tree = skill_tree()
    missing = []
    for p in TASK_BOOKS:
        for m in re.finditer(r"`((?:命盘|人物)/[^`\s]+)`", read(p)):
            raw = m.group(1)
            if raw.endswith("/") or re.search(r"\.[甲乙丙]\.", raw):  # 目录本身；编配会三版草稿
                continue
            q = norm(raw)
            if q in tree or (q.endswith(".md") and q[:-3] + ".json" in tree):  # .md 是 .json 的渲染
                continue
            missing.append(f"{p.name}：{raw}")
    assert not missing, "任务书引的产物不在 SKILL 目录图里：\n" + "\n".join(missing)


def js_array(src: str, name: str) -> list[str]:
    m = re.search(rf"const {name} = \[(.*?)\];", src, re.S)
    assert m, name
    return re.findall(r'"([^"]+)"', m.group(1))


def test_reading_card_fields_in_sync() -> None:
    body = re.sub(r"<!--.*?-->", "", read(REFS / "写作层" / "模板" / "读法卡.md"), flags=re.S)
    fields = re.findall(r"^- ([^：\n]+)：", body, re.M)
    src = read(ROOT / "scripts" / "check-plan.js")
    fn = src.split("function checkReadingCard", 1)[1].split("\n  }\n", 1)[0]
    checked = js_array(src, "READING_CARD_FIELDS") + re.findall(r'need\(file, t, doc, "([^"]+)"', fn)
    assert sorted(fields) == sorted(checked), (fields, checked)
    m = re.search(r"读法卡\.md`：([一二三四五六七八九十两]+)项", read(REFS / "写作层" / "任务书" / "师承读法卡.md"))
    assert m and cn_num(m.group(1)) == len(fields), m and m.group(0)


def test_style_sections_in_sync() -> None:
    tpl = read(REFS / "写作层" / "模板" / "文风.md")
    heads = re.findall(r"^## (.+)$", tpl, re.M)
    assert heads == js_array(read(ROOT / "scripts" / "check-plan.js"), "STYLE_SECTIONS"), heads
    for text, pat in ((tpl, r"([一二三四五六七八九十两]+)个小节"), (read(REFS / "写作层" / "模板" / "README.md"), r"查([一二三四五六七八九十两]+)节在场")):
        m = re.search(pat, text)
        assert m and cn_num(m.group(1)) == len(heads), m and m.group(0)


USAGE = sorted((REFS / "用法").glob("*.md")) + [REFS / "术语表.md"]


def runtime_docs() -> list[Path]:
    """跑 skill 的会话与子代理照着做的文字：SKILL、任务书、模板、问法、用法、术语表（规则表与校核卡的出处栏不算）。"""
    files = [SKILL, *TASK_BOOKS, REFS / "戏剧层" / "问法.md", *USAGE]
    for d in (REFS / "写作层" / "模板", REFS / "戏剧层" / "模板"):
        files += [p for p in sorted(d.rglob("*")) if p.is_file()]
    return files


def test_runtime_docs_do_not_point_to_design_docs() -> None:
    bad = [f"{p.relative_to(ROOT)}:{i}" for p in runtime_docs() for i, line in enumerate(read(p).splitlines(), 1) if "DESIGN" in line or "决策/" in line or re.search(r"决-\d{3}", line)]
    assert not bad, "运行时文件里提到设计稿或决策记录（要用的规矩写进运行时文件本身）：\n" + "\n".join(bad)


def test_skill_and_usage_have_no_dates() -> None:
    bad = [f"{p.relative_to(ROOT)}:{i}" for p in [SKILL, *USAGE] for i, line in enumerate(read(p).splitlines(), 1)
           if re.search(r"20\d\d-\d\d-\d\d", line)]
    assert not bad, "SKILL 与用法里有日期（经过进设计稿与工作进度）：\n" + "\n".join(bad)


def test_skill_is_short_router() -> None:
    n = len(read(SKILL).splitlines())
    assert n <= 220, f"SKILL.md {n} 行：只留路由，命令与写法进 references/用法/"


def test_skill_referenced_files_exist() -> None:
    missing = []
    for m in re.finditer(r"`(references/[^`*\s]+)`", read(SKILL)):
        rel = m.group(1).rstrip("/")
        if not (ROOT / rel).exists():
            missing.append(rel)
    for m in re.finditer(r"任务书 `([^`/\s]+\.md)`", read(SKILL)):  # 流程节里简写的任务书名
        name = m.group(1)
        if not ((REFS / "任务书" / name).exists() or (REFS / "写作层" / "任务书" / name).exists()):
            missing.append(name)
    assert not missing, missing


def test_drama_page_asks_and_beats_in_sync() -> None:
    tpl = json.loads(read(REFS / "戏剧层" / "模板" / "戏用页.json"))
    src = read(ROOT / "scripts" / "check-drama.js")
    assert [a["ask"] for a in tpl["asks"]] == js_array(src, "ASKS") + js_array(src, "EXTRAS")
    used = {line["beat"] for a in tpl["asks"] for line in a["lines"] if "beat" in line}
    assert used == set(js_array(src, "BEATS")), used
    assert tpl["belief"] in js_array(src, "BELIEFS")
    assert {line["by"] for a in tpl["asks"] for line in a["lines"] if "by" in line} <= set(js_array(src, "BREAK_BY"))
    import drama_render  # 渲染与检查器认同一串附问
    assert list(drama_render.EXTRAS) == js_array(src, "EXTRAS")


DESIGNS = {"DESIGN.md", "DESIGN-命盘层.md", "DESIGN-人物层.md", "DESIGN-戏剧层.md", "DESIGN-写作层.md"}
# 设计稿的字数上限（五份都照 0c 瘦过）
DESIGN_MAX_CHARS = {"DESIGN.md": 8000, "DESIGN-命盘层.md": 15000, "DESIGN-人物层.md": 10000, "DESIGN-戏剧层.md": 12000, "DESIGN-写作层.md": 11000}


def test_only_five_design_docs() -> None:
    extra = {p.name for p in ROOT.glob("DESIGN*.md")} ^ DESIGNS
    assert not extra, f"设计稿只有总纲加四层五份（DESIGN.md 0c），多了或少了：{extra}。拿不准归哪层的先放总纲待定"


def test_layer_docs_follow_skeleton() -> None:
    for name in DESIGN_MAX_CHARS:
        if name == "DESIGN.md":
            continue
        heads = re.findall(r"^## ([0-9]+)\. (.+)$", read(ROOT / name), re.M)
        assert heads and heads[0][0] == "0", f"{name}：第 0 节是定位"
        assert "检查与验收" in heads[-2][1] and "待定" in heads[-1][1], f"{name}：倒数第二节检查与验收、末节待定，现在是 {heads[-2:]}"


def design_anchors(name: str) -> set[str]:
    return {m.group(1) for m in re.finditer(r"^#{2,3} (附录 [A-Z]|[0-9]+[a-z]?(?:\.[0-9]+)?)", read(ROOT / name), re.M)}


def test_design_citations_resolve() -> None:
    """全仓引瘦过的设计稿的节号（"DESIGN-人物层 4""DESIGN.md 0c""DESIGN 附录 A"）都落得到；瘦过的稿内"第 N 节"也落得到。
    决策/ 与工作进度是历史，指的是当时的稿子，不查。"""
    num = r"(?:附录 ?[A-Z]|[0-9]+[a-z]?(?:\.[0-9]+)?)"
    cite = re.compile(r"(DESIGN(?:-(?:命盘层|人物层|戏剧层|写作层))?)(?:\.md)?`?\s*(?:第\s*)?(" + num + r"(?:\s*、\s*" + num + r")*)(?![0-9.])")
    inner = re.compile(r"(?<![-\w])第 ?(" + num + r"(?:、" + num + r")*) ?节")
    anchors = {n.removesuffix(".md"): design_anchors(n) for n in DESIGN_MAX_CHARS}
    out = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                         cwd=ROOT, capture_output=True, check=True).stdout.decode("utf-8").split("\0")
    bad = []
    for name in out:
        if not name or name.startswith(("决策/", "工作进度", "source/")) or not name.endswith((".md", ".py", ".js", ".json")):
            continue
        try:
            text = read(ROOT / name)
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for m in cite.finditer(line):
                if m.group(1) not in anchors:
                    continue
                for n in re.split(r"\s*、\s*", m.group(2)):
                    n = re.sub(r"附录 ?", "附录 ", n)
                    if n not in anchors[m.group(1)]:
                        bad.append(f"{name}:{i}: {m.group(1)} {n}")
            if name in DESIGN_MAX_CHARS:
                for m in inner.finditer(line):
                    bad += [f"{name}:{i}: 本稿第 {n} 节" for n in m.group(1).split("、") if n not in anchors[name.removesuffix(".md")]]
    assert not bad, "引设计稿的节号落不到（改节号时用脚本把引用一起改）：\n" + "\n".join(bad)


def test_design_docs_have_no_dates() -> None:
    bad = [f"{name}:{i}" for name in DESIGN_MAX_CHARS for i, line in enumerate(read(ROOT / name).splitlines(), 1)
           if re.search(r"20\d\d-\d\d-\d\d", line)]
    assert not bad, "设计稿里有日期（设计稿只写现在，经过与日期进 决策/）：\n" + "\n".join(bad)


def test_design_docs_are_bounded() -> None:
    over = {name: len(read(ROOT / name)) for name, cap in DESIGN_MAX_CHARS.items() if len(read(ROOT / name)) > cap}
    assert not over, f"设计稿超过字数上限 {DESIGN_MAX_CHARS}：{over}。被取代的删掉、来由挪进 决策/，别抬上限"
