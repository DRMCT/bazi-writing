"""写作层：书/ 模板与两个检查器（check-plan、check-prose）。夹具用林昭样例的 命盘/ 与 人物/ 当项目根，书/ 按模板填真编号。"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
EXAMPLE = ROOT / "examples" / "林昭"
TEMPLATES = ROOT / "references" / "写作层" / "模板"
PLAN = ROOT / "scripts" / "check-plan.js"
PROSE = ROOT / "scripts" / "check-prose.js"
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="需要 node")

THEME = """# 主题

- 写法轮廓：webnovel
- 时代：古代
- 主角：林昭
- 目标读者：爱看宅斗的女读者

## 命题

一个靠锋利立身的人，肯不肯把刀口对着自己。

## 两半

- 上半：她以为锋利就是站得住
- 下半：让她站住的是她肯欠别人

## 装置

| 编号 | 装置 | 类型 | 认法 | 全书上限 | 用法 |
|---|---|---|---|---|---|
| F001 | 那枚铜钱 | 物件 | 铜钱 | 2 | 只在无人处摸它 |

## 白名单

- 户主自择入户之夫，田粮契约归户主
"""

STYLE = """# 文风

## 师承

- 书：无
- 学什么：无
- 不学什么：无

## 叙述者

- 是谁、离多远：贴着林昭，借她的口气说话
- 判断与幽默：人物式的判断可以有
- 述与演：述四演六
- 情绪怎么写：可以直说，身体留给一章最要紧的一下
- 信息怎么进：叙述者一段讲完
- 环境与感官：一场至多一处
- 时间：一句话可以跳几天
- 开头与结尾：章尾落在一个念头上

## 叙述

- 视角：第三人称限知，贴着林昭走。
- 进内心写感受不写动机的解释。

## 句与段

- 短句中句为主。

## 口吻与用词

- 古代白话，不用现代词。

## 对白

- 林昭：话短，带刺，先驳后问。
- 裴恪：慢，绕，说定的事再说一遍。

## 标点

- 引号用中文双引号。

## 情绪与节奏

- 情绪写过程不写结论。

## 不写

- 细纲与档案里的原句。

## 阈值

| 项 | 值 |
|---|---|
| 章长 | 300 |
| 句尾否定 | 2 |
| 双否定 | 0 |
| 感叹号 | 1 |
"""

VOLUME = """# 卷一

- 卷：1
- 段：一
- 大运：D-2-庚辰
- 起止年：324–330
- 主角：林昭
- 命题的哪一半：她以为锋利就是站得住

## 骨

- 为哪一人一事：林昭要裴恪先开口
- 起：U-1
- 承：U-1
- 转：U-1
- 合：U-1
- 高潮：U-1
- 响：TH-325-裴恪-林昭-感情
- 清算：无
- 落下风：U-1，裴恪当着沈砚先压她一头
- 破：U-1，林昭漏，自己
- 默认下场：DF-林昭-328 透
- 卷末的问题：她肯不肯欠他

## 单元

| 单元 | 来路 | 两难 | 赌注 | 起止年 | 在场 | 开的线程 | 合的线程 | 前后因果 |
|---|---|---|---|---|---|---|---|---|
| U-1 | 热年出事、对手出招；裴恪先开口 | 林昭 J-325-林昭-裴恪 | 押的是她在裴恪跟前的体面 | 325 | 林昭、裴恪、沈砚 | TH-325-裴恪-林昭-感情 | 无 | 开卷 |

## 卷末偏移

- 林昭：刀口第一次转向自己。
"""

UNIT = """# U-1

- 单元：U-1
- 卷：1
- 年：325
- 来路：热年出事、对手出招；裴恪先开口
- 两难：J-325-林昭-裴恪
- 线程：TH-325-裴恪-林昭-感情
- 在场：林昭、裴恪、沈砚

## 走法甲

- 谁做选择：林昭
- 事件顺序：裴恪先开口，林昭当场顶回去，沈砚在旁看着。
- 输了丢什么：体面
- 赢了欠什么：欠裴恪一句话
- 结束时开着的线程：TH-325-裴恪-林昭-感情

## 走法乙

- 谁做选择：裴恪
- 事件顺序：裴恪把话咽回去，转头找沈砚。
- 输了丢什么：先手
- 赢了欠什么：欠沈砚一个人情
- 结束时开着的线程：无

## 走法丙

- 谁做选择：沈砚
- 事件顺序：沈砚替两人把话说破。
- 输了丢什么：两头都得罪
- 赢了欠什么：欠林昭一次
- 结束时开着的线程：TH-325-裴恪-林昭-感情

## 作者选

- 选：甲
- 为什么：选择要落在主角身上。

## 章

| 章 | 功能：让谁面对什么 | 读者离开时多知道什么 |
|---|---|---|
| 1 | 让林昭面对裴恪开口那一下 | 她的刺是怕 |
| 2 | 让林昭面对沈砚看穿她 | 沈砚站在哪一边 |
"""

OUTLINE = """# 第{n}章

- 章：{n}
- 单元：U-1
- 主视角：林昭
- 年：325
- 时候：入秋一个傍晚
- 地点：后院灶房
- 在场：林昭、裴恪
- 位置：无

## 意图

读者离开时知道林昭的刺底下是怕。

## 赌注

林昭押的是体面，引 J-325-林昭-裴恪 与 TH-325-裴恪-林昭-感情 。

## 决定

她可以把碗递过去，她把碗放下了。

## 弧

- 要什么：要他先开口
- 起：第 1 场，他会不会问
- 承：他绕着说
- 转：她把碗放下
- 合：碗还在灶上

## 在场与知情

| 人 | 这一章做什么 | 知道什么 |
|---|---|---|
| 林昭 | 做饭、放碗 | 铜钱的来处 |
| 裴恪 | 站在门口说慢话 | 不知道那枚铜钱的来处 |
| 读者 | 到章末 | 知道刺底下是怕；不知道铜钱从哪来 |

## 场

| 场 | 视角 | 述/演 | 时候与地点 | 转折 | 读者担心 | 对面要什么 | 怎么去要 | 谁的五拍 | 碰线 | 破 | 感官锚点 | 落点 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 林昭 | 演 | 傍晚灶房 | 进：想递碗（正）；出：碗放下（负） | 她先软下来 | 裴恪要她先认 | 绕着说，等她开口 | 林昭 | 被问起来处 | 漏，自己 | 灶烟 | 她把碗放下 |

## 禁放

- 禁：不揭铜钱的来处
- 放：裴恪的慢可以写足

## 物件

{objects}

## 承接

{prev}

## 钩子

停在她放下碗的那一下。
"""

CH1 = """# 第1章

灶烟从门缝里挤出来，林昭把碗放下。
裴恪站在门口，话说得慢，一句绕过一句。
她的手指在袖子里摸到那枚铜钱，凉的。
她把手抽出来，端起碗。
碗沿有一道缺口，硌着嘴唇。
"""

CH2 = """# 第2章

裴恪又站在门口，话说得慢，一句绕过一句，和昨天一样。
林昭摸了摸铜钱，又摸了摸铜钱。
{copied}
她没抬头，也没出声。
他不动。
她不看他。
风把灶烟压下来。
户主自择入户之夫，田粮契约归户主，这句她记得。
"""


def make_book(tmp_path: Path, chapters: int = 2, outline_objects: str = "F001") -> Path:
    for sub in ("命盘", "人物"):
        shutil.copytree(EXAMPLE / sub, tmp_path / sub)
    book = tmp_path / "书"
    for d in ("卷", "单元", "细纲", "正文", "稿", "会", "追踪"):
        (book / d).mkdir(parents=True)
    (book / "主题.md").write_text(THEME, encoding="utf-8")
    (book / "文风.md").write_text(STYLE, encoding="utf-8")
    (book / "卷" / "卷1.md").write_text(VOLUME, encoding="utf-8")
    (book / "单元" / "U-1.md").write_text(UNIT, encoding="utf-8")
    for n in range(1, chapters + 1):
        prev = "无，首章" if n == 1 else f"第{n - 1}章末她放下碗"
        (book / "细纲" / f"第{n}章.md").write_text(OUTLINE.format(n=n, objects=outline_objects, prev=prev), encoding="utf-8")
    return book


def run(script: Path, *args: str) -> tuple[int, list[dict], dict]:
    r = subprocess.run(["node", str(script), *args], capture_output=True, text=True, encoding="utf-8")
    rows = [json.loads(l) for l in r.stdout.splitlines() if l.strip()]
    assert rows, r.stderr
    summary = rows[-1]
    assert summary.get("summary"), r.stdout
    return r.returncode, rows[:-1], summary


def hits(rows: list[dict], check: str, level: str | None = None) -> list[dict]:
    return [x for x in rows if x.get("check") == check and (level is None or x.get("level") == level)]


def test_templates_and_profile_table() -> None:
    for name in ("主题.md", "文风.md", "卷.md", "单元.md", "细纲.md", "回纲会.md", "README.md"):
        assert (TEMPLATES / name).exists(), name
    outline = (TEMPLATES / "细纲.md").read_text(encoding="utf-8")
    assert not any(q in outline for q in "“”\"「」"), "细纲模板里不许有引号"
    table = json.loads((ROOT / "references" / "写作层" / "轮廓.json").read_text(encoding="utf-8"))
    assert table["schema"] == "bazi-book-profile/v2" and set(table["profiles"]) == {"webnovel"}
    for p in table["profiles"].values():
        assert {"negationTail", "exclaimPerK", "ellipsisPerK", "dashPerK"} <= set(p["thresholds"])
        assert p["copy"]["ngram"] == 8 and p["repeat"]["ngram"] == 6
        assert p["chapterRange"][0] < p["chapterChars"] < p["chapterRange"][1]
    assert set(table["hooklessKinds"]) <= set(table["hookKinds"]) and set(table["roundEndBad"]) <= set(table["hookKinds"])
    assert "推" in table["expectActs"] and "搁置" in table["expectActs"] and "常驻" in table["scales"]
    for sub in ("在场与知情.json", "登记.json", "期待.json"):
        doc = json.loads((TEMPLATES / "追踪" / sub).read_text(encoding="utf-8"))
        assert doc["schema"].startswith("bazi-book-")


@needs_node
def test_plan_fixture_passes(tmp_path: Path) -> None:
    book = make_book(tmp_path)
    code, rows, summary = run(PLAN, str(book))
    assert code == 0, [r for r in rows if r["level"] == "error"]
    assert summary["errors"] == 0
    assert summary["byType"] == {"主题": 1, "文风": 1, "卷": 1, "单元": 1, "细纲": 2}
    assert summary["idPool"] > 100 and summary["names"] >= 2 and summary["objects"] == 1
    assert not hits(rows, "编号")  # 真编号都在池里


@needs_node
def test_plan_catches_quotes_ids_walks_objects_birth(tmp_path: Path) -> None:
    book = make_book(tmp_path, chapters=3)  # 三章细纲都碰 F001，上限 2
    o1 = book / "细纲" / "第1章.md"
    o1.write_text(o1.read_text(encoding="utf-8").replace("她把碗放下", "她说“我不去”").replace("J-325-林昭-裴恪 与", "J-999-甲-乙 与"), encoding="utf-8")
    o2 = book / "细纲" / "第2章.md"
    o2.write_text(o2.read_text(encoding="utf-8").replace("- 年：325", "- 年：300").replace("## 意图\n", "## 意图\n\n这一章的爽点在第三场，对标某书。\n"), encoding="utf-8")
    u = book / "单元" / "U-1.md"
    u.write_text(u.read_text(encoding="utf-8").replace("- 谁做选择：裴恪", "- 谁做选择：林昭"), encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert code == 1
    assert hits(rows, "引号", "error") and all(x["type"] == "细纲" for x in hits(rows, "引号", "error"))
    assert any(x["text"] == "J-999-甲-乙" for x in hits(rows, "编号", "error"))
    assert any("谁做选择上不同" in x["note"] for x in hits(rows, "走法", "error"))
    assert hits(rows, "物件超限", "error"), "三章细纲排了三次 F001，上限 2"
    assert any("还没出生" in x["note"] for x in hits(rows, "在场", "error")), "林昭生于 306，300 年不能在场"
    assert {x["text"] for x in hits(rows, "借鉴字样", "warn")} >= {"爽点", "对标"}


@needs_node
def test_plan_unit_not_chosen_and_loose_mode(tmp_path: Path) -> None:
    book = make_book(tmp_path)
    u = book / "单元" / "U-1.md"
    u.write_text(u.read_text(encoding="utf-8").replace("- 选：甲", "- 选：待定"), encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert code == 0
    assert any(x["text"] == "待定" for x in hits(rows, "作者选", "warn"))
    assert any("没选走法就排了章" in x["note"] for x in hits(rows, "章", "warn"))
    foreign = tmp_path / "别家细纲.md"
    foreign.write_text("# 细纲 第2章\n- 核心事件：她说“我不嫁”\n- 字数目标：2300 字\n- 爽点：当众回绝\n", encoding="utf-8")
    code, rows, summary = run(PLAN, str(foreign), "--loose", "--root", str(tmp_path))
    assert code == 0 and summary["byType"] == {"外来": 1}
    assert hits(rows, "引号", "warn") and hits(rows, "逐点字数", "warn") and hits(rows, "借鉴字样", "warn")


@needs_node
def test_plan_walk_name_sentence_and_subbullets(tmp_path: Path) -> None:
    """任务书让『谁做选择』先名字再接一句解释，得失按人分成缩进子条；检查器拿句号前的名字比在场，子条算字段的值。"""
    book = make_book(tmp_path)
    u = book / "单元" / "U-1.md"
    t = u.read_text(encoding="utf-8")
    t = t.replace("- 谁做选择：林昭", "- 谁做选择：林昭。她在第三步把话顶了回去，本可以咽下去。")
    t = t.replace("- 输了丢什么：体面\n", "- 输了丢什么：\n  - 林昭：体面\n  - 裴恪：先手\n")
    t = t.replace("- 赢了欠什么：欠裴恪一句话\n", "- 赢了欠什么：\n  1. 林昭欠裴恪一句话\n  2. 沈砚欠林昭一次\n")
    u.write_text(t, encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert code == 0, [r for r in rows if r["level"] == "error"]
    assert not hits(rows, "走法"), hits(rows, "走法")
    # 名字不在在场里仍报
    u.write_text(t.replace("- 谁做选择：林昭。", "- 谁做选择：路人。"), encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert any(x["text"] == "路人" and "不在在场里" in x["note"] for x in hits(rows, "走法", "warn"))


@needs_node
def test_prose_clean_chapter_and_summary(tmp_path: Path) -> None:
    book = make_book(tmp_path)
    (book / "正文" / "第1章.md").write_text(CH1, encoding="utf-8")
    code, rows, summary = run(PROSE, str(book / "正文" / "第1章.md"))
    assert code == 0, rows
    assert summary["profile"] == "webnovel" and "章长" in summary["overrides"]
    assert summary["copies"] == 0 and summary["repeats"] == 0
    assert summary["objects"]["F001"] == {"chapter": 1, "total": 1, "limit": 2}
    assert summary["sources"] >= 3  # 细纲、读者本、文风
    assert summary["chars"] > 50


@needs_node
def test_prose_catches_copy_repeat_objects_negation(tmp_path: Path) -> None:
    book = make_book(tmp_path)
    (book / "正文" / "第1章.md").write_text(CH1, encoding="utf-8")
    card = (tmp_path / "人物" / "林昭.读者本.md").read_text(encoding="utf-8").splitlines()
    sentence = next(l for l in card if l.startswith("- ") and len(l) > 40).lstrip("- ").split("：", 1)[-1][:24]
    (book / "正文" / "第2章.md").write_text(CH2.format(copied=sentence), encoding="utf-8")
    code, rows, summary = run(PROSE, str(book / "正文" / "第2章.md"))
    assert code == 1
    copies = hits(rows, "照抄", "error")
    assert copies and any("读者本" in x["source"] for x in copies), copies
    assert not any("户主自择" in x["text"] for x in copies), "白名单里的律文放行"
    repeats = hits(rows, "跨章重复", "warn")
    assert any("话说得慢" in x["text"] for x in repeats), repeats
    assert hits(rows, "装置超限", "error") and summary["objects"]["F001"]["total"] == 3
    assert summary["negationTail"] >= 3 and hits(rows, "句尾否定", "warn")  # 文风阈值 2
    assert hits(rows, "双否定", "warn")
    assert summary["prev"] == 1


@needs_node
def test_prose_foreign_layout_flags(tmp_path: Path) -> None:
    """目录不是 书/ 形状时逐项指定；几章一起给，前面的章当后面的前文。"""
    make_book(tmp_path)
    a, b = tmp_path / "a.md", tmp_path / "b.md"
    a.write_text(CH1, encoding="utf-8")
    b.write_text(CH2.format(copied="她把碗放下，端起来，又放下。"), encoding="utf-8")
    code, rows, summary = run(PROSE, str(a), str(b), "--theme", str(tmp_path / "书" / "主题.md"), "--style", str(tmp_path / "书" / "文风.md"),
                              "--cards", str(tmp_path / "人物"), "--profile", "webnovel", "--summary")
    assert summary["file"] == str(b) and summary["profile"] == "webnovel" and summary["prev"] == 1
    assert summary["objects"]["F001"]["total"] == 3 and code == 1


@needs_node
def test_plan_walk_on_table(tmp_path: Path) -> None:
    """龙套表：登记的称呼在细纲在场里不报；放进场表的五拍报 error（龙套没有戏用页）。"""
    book = make_book(tmp_path)
    (book / "龙套.md").write_text("# 龙套\n\n| 称呼 | 功能 | 一句 | 首次出场 |\n|---|---|---|---|\n| 辅导员 | 查寝的人 | 开口先念规定 | 第1章 |\n", encoding="utf-8")
    o1 = book / "细纲" / "第1章.md"
    o1.write_text(o1.read_text(encoding="utf-8").replace("- 在场：林昭、裴恪", "- 在场：林昭、裴恪、辅导员"), encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert code == 0 and summary["extras"] == 1 and summary["byType"].get("龙套") == 1
    assert not hits(rows, "在场")
    o1.write_text(o1.read_text(encoding="utf-8").replace("| 林昭 | 被问起来处 |", "| 辅导员 | 被问起来处 |"), encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert code == 1 and any("龙套没有五拍" in x["note"] for x in hits(rows, "场", "error"))


@needs_node
def test_plan_outline_pov_decision_knowledge(tmp_path: Path) -> None:
    """细纲新字段（2026-09-26）：主视角不在在场里 error；决定空 error；在场与知情表漏人、缺读者行 warn；别人的线 warn；五拍全写无 error；不是正叙的书缺位置 warn。"""
    book = make_book(tmp_path)
    o1 = book / "细纲" / "第1章.md"
    src = o1.read_text(encoding="utf-8")
    o1.write_text(src.replace("- 主视角：林昭", "- 主视角：顾衡").replace("她可以把碗递过去，她把碗放下了。", "")
                  .replace("| 裴恪 | 站在门口说慢话 | 不知道那枚铜钱的来处 |\n| 读者 | 到章末 | 知道刺底下是怕；不知道铜钱从哪来 |\n", ""), encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert code == 1
    assert any(x["text"] == "顾衡" and "主视角不在在场里" in x["note"] for x in hits(rows, "字段", "error"))
    assert any(x["text"] == "决定" for x in hits(rows, "小节", "error"))
    assert any(x["text"] == "裴恪" for x in hits(rows, "在场与知情", "warn")) and any(x["text"] == "读者" for x in hits(rows, "在场与知情", "warn"))
    o1.write_text(src.replace("| 林昭 | 被问起来处 |", "| 裴恪 | 被问起来处 |"), encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert code == 0 and any(x["text"] == "裴恪" and "只从外面写" in x["note"] for x in hits(rows, "场", "warn"))
    o1.write_text(src.replace("| 林昭 | 被问起来处 |", "| 无 | 被问起来处 |"), encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert code == 0 and any(x["text"] == "五拍" for x in hits(rows, "场", "warn"))  # 一章不走线降成 warn：调剂或松的章可以
    theme = book / "主题.md"
    theme.write_text(theme.read_text(encoding="utf-8").replace("## 装置", "## 叙述结构\n\n- 结构：双线\n\n| 现在时段 | 起止年 | 插在它后面的回忆单元 |\n|---|---|---|\n| 1 | 330 | U-1 |\n\n## 装置"), encoding="utf-8")
    o1.write_text(src.replace("- 位置：无\n", ""), encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert code == 0 and any(x["text"] == "位置" for x in hits(rows, "字段", "warn"))


@needs_node
def test_plan_narrative_structure_and_chapter_uniqueness(tmp_path: Path) -> None:
    """主题没有叙述结构一节报 warn；不是正叙时插入表没填完不查重号只报 warn，填完了两个单元记录排同一个章号报 error。"""
    book = make_book(tmp_path)
    code, rows, summary = run(PLAN, str(book))
    assert code == 0 and any(x["text"] == "叙述结构" for x in hits(rows, "小节", "warn"))
    theme = book / "主题.md"
    theme.write_text(theme.read_text(encoding="utf-8").replace("## 装置", "## 叙述结构\n\n- 结构：双线\n- 现在时：2017 年那条线\n- 回忆怎么进出：一把伞\n\n## 装置"), encoding="utf-8")
    u2 = (book / "单元" / "U-1.md").read_text(encoding="utf-8").replace("# U-1", "# U-2").replace("- 单元：U-1", "- 单元：U-2")
    (book / "单元" / "U-2.md").write_text(u2, encoding="utf-8")  # 章表照抄，第1、2章与 U-1 重号
    code, rows, summary = run(PLAN, str(book))
    assert not any(x["text"] == "叙述结构" for x in hits(rows, "小节", "warn"))
    assert code == 0 and hits(rows, "插入表", "warn") and not [x for x in hits(rows, "章", "error") if "重号" in x["note"]]
    theme.write_text(theme.read_text(encoding="utf-8").replace("- 回忆怎么进出：一把伞\n", "- 回忆怎么进出：一把伞\n\n| 现在时段 | 起止年 | 插在它后面的回忆单元 |\n|---|---|---|\n| 1 | 2017 | U-1、U-2 |\n"), encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert not hits(rows, "插入表")
    dup = [x for x in hits(rows, "章", "error") if "重号" in x["note"]]
    assert code == 1 and len(dup) == 2 and all("U-2.md" in x["file"] for x in dup)


@needs_node
def test_plan_style_ten_sections_and_reading_card(tmp_path: Path) -> None:
    """文风十节：缺师承或叙述者报 error；读法卡按标题认，十八项缺一报 error，引文超十五字 warn。"""
    book = make_book(tmp_path)
    style = book / "文风.md"
    style.write_text(style.read_text(encoding="utf-8").replace("## 叙述者\n", "## 叙述人\n"), encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert code == 1 and any(x["text"] == "叙述者" for x in hits(rows, "小节", "error"))
    style.write_text(style.read_text(encoding="utf-8").replace("## 叙述人\n", "## 叙述者\n"), encoding="utf-8")
    cards = book / "师承" / "读法" / "某书"
    cards.mkdir(parents=True)
    fields = ["章", "字数", "覆盖时间", "演", "述", "述演比", "叙述者的判断与幽默", "情绪写法", "旧事怎么进", "环境与感官", "时间过渡", "开头", "结尾", "埋", "收", "对白", "腔调变化", "最值得学的一个讲法"]
    body = "# 读法卡 · 第1章\n\n" + "\n".join(f"- {k}：有" for k in fields) + "\n"
    (cards / "第1章.md").write_text(body, encoding="utf-8")
    (book / "师承" / "片段.md").write_text("# 师承片段\n\n她说：“这一段引得很长很长很长很长很长很长很长很长。”约 300 字。\n", encoding="utf-8")
    code, rows, summary = run(PLAN, str(book / "师承"))
    assert code == 0 and summary["byType"] == {"读法卡": 1}, rows  # 师承目录下只认读法卡，片段与文本不查
    (cards / "第2章.md").write_text(body.replace("- 收：有\n", "").replace("- 开头：有", "- 开头：“这一句引得太长了超过了十五个字的限度”"), encoding="utf-8")
    code, rows, summary = run(PLAN, str(cards))
    assert code == 1 and any(x["text"] == "收" for x in hits(rows, "字段", "error")) and hits(rows, "引文", "warn")


@needs_node
def test_plan_outline_scene_mode_and_turn(tmp_path: Path) -> None:
    """细纲场表：述/演只认述或演；转折空 warn；述的场走线 warn；全是述报 warn。"""
    book = make_book(tmp_path)
    o1 = book / "细纲" / "第1章.md"
    src = o1.read_text(encoding="utf-8")
    o1.write_text(src.replace("| 1 | 林昭 | 演 | 傍晚灶房 | 进：想递碗（正）；出：碗放下（负） |", "| 1 | 林昭 | 述 | 傍晚灶房 |  |"), encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert code == 0
    notes = [x["note"] for x in hits(rows, "场", "warn")]
    assert any("转折" in x["text"] for x in hits(rows, "场", "warn")) and any("述的场不走线" in n for n in notes) and any("至少一场演" in n for n in notes)
    o1.write_text(src.replace("| 1 | 林昭 | 演 |", "| 1 | 林昭 | 演述 |"), encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert any("述/演" in x["text"] for x in hits(rows, "场", "warn"))


STATS = ROOT / "scripts" / "style-stats.js"
LINEAGE = """第1章
郑微站在树下，当然，这鬼地方真热呀。她想，其实妈妈要是来了，多半也是这副模样吧。
“谢谢啊，叔叔。”她笑眯眯地说。
他们不放心，不过工作也忙，反正她再三保证了。
第2章
一个星期之后的这天晚上，她握着电话发呆。心里空落落的，说实话，她也不知道在等什么。
“同志，电话是拿起还是放下？”朱小北说。
她把电话塞过去，说打吧打吧。想到这里，她甜甜地笑了。
番外一
这一章不该算进去。
"""


@needs_node
def test_style_stats_chapters_ends_against(tmp_path: Path) -> None:
    """style-stats：按第N章切章、跳过番外；--ends 出章首章尾；--against 把本章与师承范围并排并标出界。"""
    ref = tmp_path / "师承.txt"
    ref.write_text(LINEAGE, encoding="utf-8")
    out = subprocess.run(["node", str(STATS), str(ref)], capture_output=True, text=True, encoding="utf-8")
    rows = [json.loads(l) for l in out.stdout.splitlines() if l.strip()]
    summary = rows[-1]
    assert summary["summary"] and summary["chapters"] == 2 and rows[0]["voice"] > 0 and rows[0]["dialoguePct"] > 0
    ends = subprocess.run(["node", str(STATS), str(ref), "--ends"], capture_output=True, text=True, encoding="utf-8")
    e = [json.loads(l) for l in ends.stdout.splitlines() if l.strip()]
    assert len(e) == 2 and e[1]["last"].startswith("她把电话塞过去")
    mine = tmp_path / "第1章.md"
    mine.write_text("# 第1章\n\n她的嗓子先紧了，颧骨发热，手指凉，指尖抖，眼眶一酸，肩膀塌下去，后背发冷，心口发闷。\n", encoding="utf-8")
    ag = subprocess.run(["node", str(STATS), str(mine), "--against", str(ref)], capture_output=True, text=True, encoding="utf-8")
    a = [json.loads(l) for l in ag.stdout.splitlines() if l.strip()]
    assert "body" in a[-1]["outOfRange"] and any(r["metric"] == "body" and r["verdict"] == "高于师承" for r in a[:-1])


@needs_node
def test_prose_tics_body_freeze_and_lineage_source(tmp_path: Path) -> None:
    """check-prose：对照式套话 warn；体感密度超阈值报；定格式收尾 info；书/师承/ 下的文本是照抄来源。"""
    book = make_book(tmp_path)
    (book / "师承").mkdir()
    (book / "师承" / "某书.txt").write_text("第1章\n林昭把碗放下之后走到灶前把火拨旺了一些然后回头看他。\n", encoding="utf-8")
    ch = book / "正文" / "第1章.md"
    ch.write_text("# 第1章\n\n他声音不高，一屋子人却都停了嘴。她的嗓子先紧了，颧骨发热，手指凉，指尖抖，眼眶一酸，肩膀塌下去，后背发冷，心口发闷，耳根烫。\n林昭把碗放下之后走到灶前把火拨旺了一些然后回头看他。\n她的手指搁在碗沿上，搁着。\n", encoding="utf-8")
    code, rows, summary = run(PROSE, str(ch))
    assert code == 1
    assert any("师承" in r["source"] for r in hits(rows, "照抄", "error"))
    assert hits(rows, "对照式套话", "warn") and hits(rows, "定格式收尾", "info")
    assert summary["bodyDensity"] > 4 and summary["tics"] >= 1 and hits(rows, "体感密度")
    ch.write_text("# 第1章\n\n奶娘扯着嗓子喊了一嗓子，他压着嗓子说话。\n", encoding="utf-8")
    code, rows, summary = run(PROSE, str(ch))
    assert summary["bodyDensity"] == 0, summary


@needs_node
def test_prose_contrast_tic_only_small_over_big(tmp_path: Path) -> None:
    """对照式套话只认以小衬大（却字后面跟都、全、让一类）；普通的转折句不报。"""
    book = make_book(tmp_path)
    ch = book / "正文" / "第1章.md"
    ch.write_text("# 第1章\n\n雨不大，风却冷得刺骨。他不说话，她却笑了。东西不贵，他却舍不得买。\n", encoding="utf-8")
    code, rows, summary = run(PROSE, str(ch))
    assert not hits(rows, "对照式套话"), rows
    ch.write_text("# 第1章\n\n个子不高，却让人不敢小看。他没说话，却让所有人坐直了。\n", encoding="utf-8")
    code, rows, summary = run(PROSE, str(ch))
    assert len(hits(rows, "对照式套话", "warn")) == 2, rows


@needs_node
def test_plan_object_touch_limit(tmp_path: Path) -> None:
    """装置表的碰的上限：细纲物件节写了碰的才数；提到只算全书上限。"""
    book = make_book(tmp_path, chapters=3, outline_objects="F001 碰")
    theme = book / "主题.md"
    theme.write_text(theme.read_text(encoding="utf-8").replace(
        "| 编号 | 装置 | 类型 | 认法 | 全书上限 | 用法 |\n|---|---|---|---|---|---|\n| F001 | 那枚铜钱 | 物件 | 铜钱 | 2 | 只在无人处摸它 |",
        "| 编号 | 装置 | 类型 | 认法 | 全书上限 | 碰的上限 | 用法 |\n|---|---|---|---|---|---|---|\n| F001 | 那枚铜钱 | 物件 | 铜钱 | 8 | 1 | 只在无人处摸它 |"), encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert len(hits(rows, "碰超限")) == 2 and not hits(rows, "物件超限"), rows
    for n in (2, 3):
        o = book / "细纲" / f"第{n}章.md"
        o.write_text(o.read_text(encoding="utf-8").replace("F001 碰", "F001 提到"), encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert code == 0 and not hits(rows, "碰超限"), rows


@needs_node
def test_prose_dash_in_dialogue_not_counted(tmp_path: Path) -> None:
    """夹叙：对白里的打断与拖音不数；叙述里拿破折号、省略号做停顿照报。"""
    book = make_book(tmp_path)
    ch = book / "正文" / "第1章.md"
    ch.write_text("# 第1章\n\n“你——”裴恪话没说完。\n“我……我去。”林昭把碗放下。\n", encoding="utf-8")
    code, rows, summary = run(PROSE, str(ch))
    assert summary["dash"] == 0 and summary["ellipsis"] == 0, summary
    ch.write_text("# 第1章\n\n林昭把碗放下——又端起来。灶上的火……慢慢矮下去。\n", encoding="utf-8")
    code, rows, summary = run(PROSE, str(ch))
    assert summary["dash"] == 1 and summary["ellipsis"] == 1 and hits(rows, "叙述破折号（每千字）") and hits(rows, "叙述省略号（每千字）"), rows


@needs_node
def test_prose_narration_only_punctuation(tmp_path: Path) -> None:
    """标点只数叙述：引号、【】里的不数，单独成行的分隔符不数，引出对白的破折号不数；按每千字报。"""
    book = make_book(tmp_path)
    ch = book / "正文" / "第1章.md"
    ch.write_text("# 第1章\n\n裴恪开口道——“你给我站住！站住！”\n【好家伙！这人疯了吧！】\n……\n林昭把碗放下，端起来，又放下，灶上的火慢慢矮下去。\n——\n", encoding="utf-8")
    code, rows, summary = run(PROSE, str(ch))
    assert summary["exclaim"] == 0 and summary["ellipsis"] == 0 and summary["dash"] == 0, summary
    ch.write_text("# 第1章\n\n林昭把碗放下！又端起来！灶上的火！慢慢矮下去！\n", encoding="utf-8")
    code, rows, summary = run(PROSE, str(ch))
    assert summary["exclaim"] == 4 and summary["exclaimPerK"] > 5 and hits(rows, "叙述感叹号（每千字）", "warn"), rows


def setup_ledger(book: Path, extra_rows: str = "") -> None:
    v = book / "卷" / "卷1.md"
    v.write_text(v.read_text(encoding="utf-8")
                 .replace("- 命题的哪一半：她以为锋利就是站得住\n", "- 命题的哪一半：她以为锋利就是站得住\n- 发动机：K001，不交棒\n- 卷末兑现：U-1，K001 他先开口\n")
                 .replace("## 卷末偏移", "## 期待线\n\n| 编号 | 期待 | 尺度 | 期限 | 开 | 兑现 |\n|---|---|---|---|---|---|\n| K001 | 他会不会先开口 | 单元 | 无 | U-1 | U-1 |\n" + extra_rows + "\n## 卷末偏移"),
                 encoding="utf-8")
    u = book / "单元" / "U-1.md"
    u.write_text(u.read_text(encoding="utf-8").replace("- 为什么：选择要落在主角身上。\n", "- 为什么：选择要落在主角身上。\n- 兑现：K001 他先开口\n"), encoding="utf-8")


def add_expect(book: Path, n: int, rows: str, rhythm: str = "紧", hook: str = "悬念", relief: str = "无") -> None:
    o = book / "细纲" / f"第{n}章.md"
    s = o.read_text(encoding="utf-8")
    s = s.replace("## 在场与知情", f"## 期待\n\n- 松紧：{rhythm}\n- 调剂：{relief}\n- 反应层：无\n\n| 编号 | 这一章 | 怎么做 |\n|---|---|---|\n{rows}\n## 在场与知情", 1)
    s = s.replace("## 钩子\n\n停在她放下碗的那一下。", f"## 钩子\n\n- 类型：{hook}\n- 停在：她放下碗的那一下\n- 章题：无")
    o.write_text(s, encoding="utf-8")


EXPECT_CHECKS = ("期待线", "期待", "期待账", "开篇", "松紧", "钩子")


def ledger_rows(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r["check"] in EXPECT_CHECKS or r.get("text") in ("卷末兑现", "兑现", "发动机", "目标读者")]


@needs_node
def test_plan_expect_ledger_clean(tmp_path: Path) -> None:
    """期待账：卷稿期待线、发动机与卷末兑现、单元兑现、细纲期待一节与断章类型；账对得上一条不报，缺了只报 warn 不拦。"""
    book = make_book(tmp_path, chapters=3, outline_objects="无")
    code, rows, summary = run(PLAN, str(book))
    assert code == 0 and hits(rows, "期待线", "warn") and hits(rows, "期待", "warn") and hits(rows, "钩子", "warn"), rows
    setup_ledger(book)
    add_expect(book, 1, "| K001 | 开 | 她要他先开口 |\n| 章内 | 开 | 灶上的火要灭 |\n| 章内 | 兑现 | 她添了柴 |\n")
    add_expect(book, 2, "| K001 | 压 | 他绕着说 |\n", relief="笑")
    add_expect(book, 3, "| K001 | 兑现 | 他先开了口 |\n", rhythm="松", hook="兑现收")
    code, rows, summary = run(PLAN, str(book))
    assert not ledger_rows(rows) and summary["expects"] == 1 and summary["expectsRegistered"] == 1, ledger_rows(rows)


@needs_node
def test_plan_expect_ledger_catches(tmp_path: Path) -> None:
    """对账：第一次出现不是开、兑现以后又压、卷稿没登记的编号、第一章没开、断章类型不对、调剂取值不对、搁置没写理由；
    单元尺度隔章没人动、连着紧没调剂、连着平、开篇没兑现、空章。"""
    one = tmp_path / "一"
    one.mkdir()
    book = make_book(one, chapters=3, outline_objects="无")
    setup_ledger(book)
    add_expect(book, 1, "| K001 | 压 | 还没开就压 |\n", relief="打斗")
    add_expect(book, 2, "| K001 | 兑现 | 他开了口 |\n| K009 | 开 | 没登记的 |\n")
    add_expect(book, 3, "| K001 | 压 | 兑现以后又压 |\n| K009 | 搁置 |  |\n", hook="结尾")
    code, rows, summary = run(PLAN, str(book))
    notes = " ".join(r["note"] for r in hits(rows, "期待账", "warn"))
    assert "第一次出现是压" in notes and "新的期待另起编号" in notes and "卷稿期待线里没有" in notes, rows
    assert any(r["text"] == "第1章" for r in hits(rows, "开篇", "warn")) and any(r["text"] == "结尾" for r in hits(rows, "钩子", "warn"))
    assert any(r["text"] == "打斗" for r in hits(rows, "期待", "warn")) and any(r["text"] == "K009 搁置" for r in hits(rows, "期待", "warn"))
    assert code == 0, "期待账全报 warn"
    two = tmp_path / "二"
    two.mkdir()
    book = make_book(two, chapters=10, outline_objects="无")
    setup_ledger(book)
    add_expect(book, 1, "| K001 | 开 | 她要他先开口 |\n")
    for n in range(2, 11):
        add_expect(book, n, "| K001 | 压 | 他绕着说 |\n" if n == 10 else "")
    code, rows, summary = run(PLAN, str(book))
    assert "隔了 9 章没人动（单元尺度，阈值 8）" in " ".join(r["note"] for r in hits(rows, "期待账", "warn")), rows
    assert any("连着紧 7 章又没有调剂" in r["note"] for r in hits(rows, "松紧", "warn"))
    assert any("连着 4 章没兑现、没推、没调剂" in r["note"] for r in hits(rows, "松紧", "warn"))
    assert any(r["text"] == "空章" for r in hits(rows, "期待", "warn"))
    assert any("没有一回兑现" in r["note"] for r in hits(rows, "开篇", "warn")) and any("登记过的期待兑现" in r["note"] for r in hits(rows, "开篇", "warn"))


@needs_node
def test_plan_expect_scales_relief_deadline(tmp_path: Path) -> None:
    """尺度：卷与全书不按章数查闲置，隔三十章以上再碰只提醒带旧账；常驻不查；搁置以后不查。调剂与推打断连着紧、连着平；带期限的期待悬着，连着松不报。"""
    book = make_book(tmp_path, chapters=36, outline_objects="无")
    setup_ledger(book, "| K002 | 她的底细会不会被他看穿 | 全书 | 无 | U-1 | 待定 |\n| K003 | 她听得见他心里话，他不知道 | 常驻 | 无 | U-1 | 无 |\n| K004 | 三日内交出账本 | 单元 | 三日内 | U-1 | U-1 |\n| K005 | 隔壁那桩旧案 | 单元 | 无 | U-1 | U-1 |\n")
    add_expect(book, 1, "| K001 | 开 | 她要他先开口 |\n| K002 | 开 | 她的底细 |\n| K003 | 开 | 心声 |\n| 章内 | 兑现 | 当场识破 |\n| K005 | 开 | 旧案 |\n")
    add_expect(book, 2, "| K001 | 推 | 他递了碗 |\n| K005 | 搁置 | 她说先顾眼前的 |\n", rhythm="松")
    add_expect(book, 3, "| K001 | 兑现 | 他先开口 |\n| K004 | 开 | 限三日 |\n", rhythm="松")
    for n in range(4, 8):
        add_expect(book, n, "", rhythm="松")  # K004 期限悬着，连着松不报平
    add_expect(book, 8, "| K004 | 兑现 | 账本交了 |\n", rhythm="松")
    for n in range(9, 36):
        add_expect(book, n, "", rhythm="紧", relief="笑")  # 连着紧但有调剂，不报
    add_expect(book, 36, "| K002 | 压 | 他又问起 |\n| K003 | 压 | 心声漏了一句 |\n| K005 | 开 | 醒来 |\n", relief="反应")
    code, rows, summary = run(PLAN, str(book))
    warns = ledger_rows([r for r in rows if r["level"] == "warn"])
    assert not [r for r in warns if r["check"] in ("松紧", "开篇")], warns
    idle = [r for r in hits(rows, "期待账", "warn") if "没人动" in r["note"]]
    assert not [r for r in idle if r["text"] in ("K002", "K003", "K005")], idle
    assert any(r["text"] == "K002" and "旧账" in r["note"] for r in hits(rows, "期待账", "info")), rows
    assert not any(r["text"] == "K003" for r in hits(rows, "期待账", "info"))


@needs_node
def test_plan_hookless_run_and_round_end(tmp_path: Path) -> None:
    """断章：连着四章不留钩报；单元章表的回合栏定回合，回合末章停在场中切或松收上报。"""
    book = make_book(tmp_path, chapters=4, outline_objects="无")
    setup_ledger(book)
    u = book / "单元" / "U-1.md"
    u.write_text(u.read_text(encoding="utf-8").replace(
        "| 章 | 功能：让谁面对什么 | 读者离开时多知道什么 |\n|---|---|---|\n| 1 | 让林昭面对裴恪开口那一下 | 她的刺是怕 |\n| 2 | 让林昭面对沈砚看穿她 | 沈砚站在哪一边 |",
        "| 章 | 回合 | 功能：让谁面对什么 | 读者离开时多知道什么 |\n|---|---|---|---|\n| 1 | 灶房 | 让林昭面对裴恪开口那一下 | 她的刺是怕 |\n| 2 | 灶房 | 让林昭面对沈砚看穿她 | 沈砚站在哪一边 |\n| 3 | 回话 | 让林昭回话 | 她肯欠人 |\n| 4 | 回话 | 让林昭收场 | 他先开口 |"), encoding="utf-8")
    add_expect(book, 1, "| K001 | 开 | 她要他先开口 |\n| 章内 | 兑现 | 识破 |\n", hook="场中切", relief="笑")
    add_expect(book, 2, "| K001 | 压 | 他绕着说 |\n", hook="松收", relief="甜")
    add_expect(book, 3, "| K001 | 推 | 他递碗 |\n", hook="松收", relief="暖")
    add_expect(book, 4, "| K001 | 兑现 | 他开口 |\n", hook="兑现收", rhythm="松")
    code, rows, summary = run(PLAN, str(book))
    notes = [r["note"] for r in hits(rows, "钩子", "warn")]
    assert summary["rounds"] == 2 and any("U-1·灶房 的末章停在松收上" in n for n in notes), rows
    assert not any("U-1·回话" in n for n in notes), notes
    assert not any("连着 4 章章尾不留钩" in n for n in notes)  # 第 1 章是场中切，只连着三章
    o1 = book / "细纲" / "第1章.md"
    o1.write_text(o1.read_text(encoding="utf-8").replace("- 类型：场中切", "- 类型：松收"), encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert any("连着 4 章章尾不留钩" in r["note"] for r in hits(rows, "钩子", "warn")), rows



@needs_node
def test_plan_fun_promise(tmp_path: Path) -> None:
    """乐子：主题卡没有乐子一节报 warn；有了，细纲期待一节不写乐子报，连着三章写无报（阈值 funlessRun 2）。"""
    book = make_book(tmp_path, chapters=3, outline_objects="无")
    setup_ledger(book)
    for n, act in ((1, "开"), (2, "压"), (3, "压")):
        add_expect(book, n, f"| K001 | {act} | 一句 |\n", relief="笑")
    code, rows, summary = run(PLAN, str(book))
    assert any(r.get("text") == "乐子" and r["type"] == "主题" for r in hits(rows, "小节", "warn")), rows
    assert not any(r["check"] == "乐子" for r in rows)
    theme = book / "主题.md"
    theme.write_text(theme.read_text(encoding="utf-8") + "\n## 乐子\n\n- 调子：轻松\n- 她嘴快，把正经话接歪\n", encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert not any(r.get("text") == "乐子" and r["type"] == "主题" for r in rows), rows
    assert sum(1 for r in hits(rows, "期待", "warn") if r.get("text") == "乐子") == 3, rows
    theme.write_text(theme.read_text(encoding="utf-8").replace("- 她嘴快，把正经话接歪", "- 嘴：她快嘴，把正经话接歪"), encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert sum(1 for r in hits(rows, "期待", "warn") if r.get("text") == "乐子") == 3, rows  # 乐子一节全是字段行也算许了
    for n in (1, 2, 3):
        o = book / "细纲" / f"第{n}章.md"
        o.write_text(o.read_text(encoding="utf-8").replace("- 调剂：笑", "- 调剂：笑\n- 乐子：无"), encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert not any(r.get("text") == "乐子" for r in hits(rows, "期待", "warn")), rows
    assert any("连着 3 章没有乐子" in r["note"] for r in hits(rows, "乐子", "warn")), rows
    o = book / "细纲" / "第2章.md"
    o.write_text(o.read_text(encoding="utf-8").replace("- 乐子：无", "- 乐子：第1场，她把正经话接歪"), encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert not any(r["check"] == "乐子" for r in rows), rows


def cast(root: Path, timescale: str) -> None:
    (root / "命盘" / "群像" / "编配.json").write_text(json.dumps(
        {"schema": "bazi-casting/v2", "main": ["林昭", "裴恪"], "sub": [], "background": [], "domainWeights": {}, "timescale": timescale}, ensure_ascii=False), encoding="utf-8")


@needs_node
def test_plan_short_span_volume_and_units_by_situation(tmp_path: Path) -> None:
    """短跨度与回到关口年：卷照编配的段分，大运写无不报；单元按局排，来路写局与日历、对手出招，两难写无，不报 error。
    长跨度没写大运、短跨度没写段报 warn；来路空报 error、认不出一种源报 warn；旧单元记录只有两难一行只提醒补来路；开着的线程认 v2 的压。"""
    book = make_book(tmp_path)
    cast(tmp_path, "短跨度")
    v = book / "卷" / "卷1.md"
    vt = v.read_text(encoding="utf-8").replace("- 大运：D-2-庚辰\n", "- 大运：无\n").replace(
        "| U-1 | 热年出事、对手出招；裴恪先开口 | 林昭 J-325-林昭-裴恪 |", "| U-1 | 局与日历、对手出招；中秋家宴 | 无 |")
    v.write_text(vt, encoding="utf-8")
    u = book / "单元" / "U-1.md"
    ut = u.read_text(encoding="utf-8").replace("- 来路：热年出事、对手出招；裴恪先开口\n- 两难：J-325-林昭-裴恪\n", "- 来路：局与日历；中秋家宴，DF-林昭-328 到点\n")
    u.write_text(ut, encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert code == 0, [r for r in rows if r["level"] == "error"]
    assert not [r for r in rows if r["text"] in ("段", "大运") or "来路" in r["text"] or "两难" in r["text"]], rows
    cast(tmp_path, "回到关口年")
    code, rows, summary = run(PLAN, str(book))
    assert code == 0 and not [r for r in rows if r["text"] in ("段", "大运")], rows
    cast(tmp_path, "长跨度")
    code, rows, summary = run(PLAN, str(book))
    assert code == 0 and any(r["text"] == "大运" and "长跨度" in r["note"] for r in hits(rows, "字段", "warn")), rows
    cast(tmp_path, "短跨度")
    v.write_text(vt.replace("- 段：一\n", ""), encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert code == 0 and any(r["text"] == "段" for r in hits(rows, "字段", "warn")), rows
    v.write_text(vt.replace("| U-1 | 局与日历、对手出招；中秋家宴 |", "| U-1 |  |"), encoding="utf-8")
    u.write_text(ut.replace("- 来路：局与日历；中秋家宴，DF-林昭-328 到点\n", "- 来路：一场家宴\n"), encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert code == 1 and any("来路" in r["text"] for r in hits(rows, "单元表", "error")), rows
    assert any(r["text"].startswith("来路 一场家宴") for r in hits(rows, "字段", "warn")), rows
    v.write_text(vt, encoding="utf-8")
    u.write_text(UNIT.replace("- 来路：热年出事、对手出招；裴恪先开口\n", ""), encoding="utf-8")  # 旧记录：两难一行，没有来路
    (tmp_path / "命盘" / "群像" / "线程.json").write_text(json.dumps({"schema": "bazi-threads/v2", "threads": [
        {"id": "TH-325-裴恪-林昭-感情", "status": "压", "chapters": []}, {"id": "TH-331-甲-乙-感情", "status": "余波", "chapters": []}]}, ensure_ascii=False), encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert code == 0 and any(r["text"] == "来路" for r in hits(rows, "字段", "warn")), rows
    assert summary["threadsChecked"] == 1 and any(r["note"].startswith("压") for r in hits(rows, "线程账", "info")), rows


@needs_node
def test_plan_outline_five_beats_and_opponent(tmp_path: Path) -> None:
    """细纲场表照戏用页：演的场转折要一对正负，对面要什么、怎么去要、读者担心缺了 warn；破只认漏、说破、碎；同一个人碎两回 warn；
    视角切给别人的场，他的线不报；赌注引 DF- 或期待编号都算，没引编号只报 warn。"""
    book = make_book(tmp_path, chapters=2)
    o1 = book / "细纲" / "第1章.md"
    src = o1.read_text(encoding="utf-8")
    row = "| 1 | 林昭 | 演 | 傍晚灶房 | 进：想递碗（正）；出：碗放下（负） | 她先软下来 | 裴恪要她先认 | 绕着说，等她开口 | 林昭 | 被问起来处 | 漏，自己 | 灶烟 | 她把碗放下 |"
    assert row in src
    o1.write_text(src.replace(row, "| 1 | 林昭 | 演 | 傍晚灶房 | 她本想递碗，放下了 |  |  |  | 林昭 | 被问起来处 | 崩了 | 灶烟 | 她把碗放下 |")
                  .replace("引 J-325-林昭-裴恪 与 TH-325-裴恪-林昭-感情 。", "押的是脸面。"), encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert code == 0, [r for r in rows if r["level"] == "error"]
    texts = {r["text"] for r in hits(rows, "场", "warn")}
    assert {"场 1 转折", "场 1 对面要什么", "场 1 怎么去要", "场 1 读者担心"} <= texts, texts
    assert any(t.startswith("场 1 破 崩了") for t in texts), texts
    assert any(r["text"] == "赌注" for r in hits(rows, "小节", "warn")) and not hits(rows, "小节", "error")
    for n in (1, 2):
        o = book / "细纲" / f"第{n}章.md"
        o.write_text(src.replace(row, row.replace("| 林昭 | 演 |", "| 裴恪：知情多 | 演 |").replace("| 林昭 | 被问起来处 | 漏，自己 |", "| 裴恪 | 被问起来处 | 碎，物证 |"))
                     .replace("引 J-325-林昭-裴恪 与", "引 DF-林昭-328 与 K001 与"), encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert code == 0 and not [r for r in hits(rows, "场", "warn") if r["text"] == "裴恪"], rows
    broke = hits(rows, "破", "warn")
    assert len(broke) == 1 and "碎一人全书一回" in broke[0]["note"] and broke[0]["file"].endswith("第2章.md"), broke
    assert not hits(rows, "编号", "error") and not [r for r in hits(rows, "小节") if r["text"] == "赌注"], rows


DEVICES_OLD = "| 编号 | 装置 | 类型 | 认法 | 全书上限 | 用法 |\n|---|---|---|---|---|---|\n| F001 | 那枚铜钱 | 物件 | 铜钱 | 2 | 只在无人处摸它 |"
DEVICES = ("| 编号 | 装置 | 类型 | 谁 | 认法 | 全书上限 | 用法 |\n|---|---|---|---|---|---|---|\n"
           "| F001 | 那枚铜钱 | 物件 |  | 铜钱 | 4 | 只在无人处摸它 |\n"
           "| F002 | 林昭的口头禅 | 重复句 | 林昭 | 这笔账我先记在心上了 | 2 | 被逼急时 |\n"
           "| F003 | 裴恪的口头禅 | 重复句 | 裴恪 | 您看是不是这个理 | 6 | 说完一段道理 |\n"
           "| F004 | 灶上那句旧话 | 回声 |  | 火候到了自然熟 | 2 | 开卷一回、卷末一回 |")


@needs_node
def test_plan_repeat_line_per_person_and_echo(tmp_path: Path) -> None:
    """装置表：口头禅记作重复句，谁一栏写说它的人，每人至多一句（同一个人两句、没写谁报 warn）；回声是一种类型；细纲物件节的重复句写落在第几场。"""
    book = make_book(tmp_path, outline_objects="F001 提到、F002 第1场")
    theme = book / "主题.md"
    theme.write_text(theme.read_text(encoding="utf-8").replace(DEVICES_OLD, DEVICES), encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert code == 0 and not hits(rows, "装置") and not hits(rows, "物件"), [r for r in rows if r["check"] in ("装置", "物件")]
    theme.write_text(theme.read_text(encoding="utf-8").replace("| 裴恪的口头禅 | 重复句 | 裴恪 |", "| 林昭的第二句 | 重复句 | 林昭 |")
                     .replace("| 回声 |", "| 回响 |"), encoding="utf-8")
    o2 = book / "细纲" / "第2章.md"
    o2.write_text(o2.read_text(encoding="utf-8").replace("F002 第1场", "F002"), encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert any("每人至多一句" in r["note"] for r in hits(rows, "装置", "warn")), rows
    assert any(r["text"] == "F004" for r in hits(rows, "装置", "error")), rows
    assert [r["file"] for r in hits(rows, "物件", "warn") if r["text"] == "F002"] == [str(o2)], rows


@needs_node
def test_prose_catchphrase_from_drama_page(tmp_path: Path) -> None:
    """口头禅只从戏用页附问末问来，装置表登记成重复句：正文反复用它不算照抄、不算跨章重复，次数照装置表数；
    同号细纲没排它的章里出现报 warn。戏用页渲染本的其他行照样是照抄来源。"""
    book = make_book(tmp_path, outline_objects="F001 提到、F002 第1场")
    theme = book / "主题.md"
    theme.write_text(theme.read_text(encoding="utf-8").replace(DEVICES_OLD, DEVICES), encoding="utf-8")
    (tmp_path / "人物" / "林昭.戏用页.md").write_text(
        "# 林昭 · 戏用页\n\n## 八、她怎么说话\n\n- 被人逼到墙角时反倒慢下来一字一顿地讲\n\n## 附：她怎么被记住\n\n- 口头禅，被逼急了先撂一句：“这笔账我先记在心上了。”\n", encoding="utf-8")
    (book / "正文" / "第1章.md").write_text("# 第1章\n\n灶烟从门缝里挤出来，林昭把碗放下。\n裴恪站在门口，话说得慢。\n林昭抬眼：“这笔账我先记在心上了。”\n", encoding="utf-8")
    ch2 = "# 第2章\n\n裴恪又来了，她端着碗没动。\n林昭笑了一下：“这笔账我先记在心上了。”\n"
    (book / "正文" / "第2章.md").write_text(ch2, encoding="utf-8")
    code, rows, summary = run(PROSE, str(book / "正文" / "第2章.md"))
    assert not hits(rows, "照抄") and not hits(rows, "跨章重复") and not hits(rows, "装置不在细纲"), rows
    assert summary["objects"]["F002"] == {"chapter": 1, "total": 2, "limit": 2}
    (book / "正文" / "第2章.md").write_text(ch2 + "她被人逼到墙角时反倒慢下来一字一顿地讲。\n", encoding="utf-8")
    code, rows, summary = run(PROSE, str(book / "正文" / "第2章.md"))
    assert code == 1 and any("戏用页" in x["source"] for x in hits(rows, "照抄", "error")), rows
    (book / "正文" / "第2章.md").write_text(ch2, encoding="utf-8")
    o2 = book / "细纲" / "第2章.md"
    o2.write_text(o2.read_text(encoding="utf-8").replace("、F002 第1场", ""), encoding="utf-8")
    code, rows, summary = run(PROSE, str(book / "正文" / "第2章.md"))
    assert code == 0 and hits(rows, "装置不在细纲", "warn"), rows


def test_templates_carry_the_fields_check_plan_reads() -> None:
    """模板与检查器同源：细纲场表的栏、卷的段与骨与单元表的来路两难、单元记录的来路、主题装置表的谁一栏。"""
    head = next(l for l in (TEMPLATES / "细纲.md").read_text(encoding="utf-8").splitlines() if l.startswith("| 场 | 视角"))
    assert {"视角", "述/演", "转折", "读者担心", "对面要什么", "怎么去要", "谁的五拍", "碰线", "破"} <= {c.strip() for c in head.split("|")}, head
    vol = (TEMPLATES / "卷.md").read_text(encoding="utf-8")
    assert "- 段：" in vol and "- 大运：" in vol and "## 骨" in vol and "- 落下风：" in vol and "| 单元 | 来路 | 两难 |" in vol
    unit = (TEMPLATES / "单元.md").read_text(encoding="utf-8")
    assert "- 来路：" in unit and "- 两难：" in unit
    assert "| 编号 | 装置 | 类型 | 谁 |" in (TEMPLATES / "主题.md").read_text(encoding="utf-8")


@needs_node
def test_plan_empty_book_does_not_crash(tmp_path: Path) -> None:
    """开书早期的 书/ 只有设定卡、会议记录（连子目录）与龙套表：检查器不崩，零 error；龙套表文件里另记的表（表头没有称呼）不当龙套行查。"""
    book = tmp_path / "书"
    (book / "会" / "冷读材料").mkdir(parents=True)
    (book / "设定卡.json").write_text("{}", encoding="utf-8")
    (book / "会" / "构思.md").write_text("# 构思\n\n- 种子：无\n", encoding="utf-8")
    (book / "会" / "冷读材料" / "梗概一.md").write_text("# 梗概\n\n她说“走”。\n", encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert code == 0 and summary["files"] == 0 and summary["errors"] == 0, rows
    (book / "龙套.md").write_text("# 龙套\n\n## 只有命盘的人\n\n| 命盘名 | 叙述里的称呼 |\n|---|---|\n| 甲 | 大老爷 |\n\n## 龙套\n\n"
                                "| 称呼 | 功能 | 一句 | 首次出场 |\n|---|---|---|---|\n| 门房 | 看门 | 待定 | 待排 |\n", encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert code == 0 and summary["extras"] == 1 and summary["byType"] == {"龙套": 1}, rows


@needs_node
def test_plan_outline_copies_upstream(tmp_path: Path) -> None:
    """细纲与单元记录、在场各人戏用页十字以上连串重合报 warn（写手会照细纲的字出句）；编号抹掉再比。"""
    book = make_book(tmp_path)
    (tmp_path / "人物" / "林昭.戏用页.md").write_text(
        "# 林昭 · 戏用页\n\n## 八、她怎么说话\n\n- 被人逼到墙角时反倒慢下来一字一顿地讲\n", encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert not any("戏用页" in x["note"] for x in hits(rows, "照抄上游")), rows
    o1 = book / "细纲" / "第1章.md"
    o1.write_text(o1.read_text(encoding="utf-8").replace("## 意图\n", "## 意图\n\n她被人逼到墙角时反倒慢下来一字一顿地讲。\n"), encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert code == 0 and any("戏用页" in x["note"] for x in hits(rows, "照抄上游", "warn")), rows


@needs_node
def test_prose_copy_lineage_common_phrase_and_outline_short_run(tmp_path: Path) -> None:
    """师承里出现三次以上的连串是通用语不报；师承/读法/ 不算来源；与细纲重合不到阈值加四只报 warn。"""
    book = make_book(tmp_path)
    (book / "师承" / "读法").mkdir(parents=True)
    common = "他从怀里掏出一个油纸包来"
    (book / "师承" / "某书.txt").write_text(f"第1章\n{common}。\n第2章\n{common}。\n第3章\n{common}。\n", encoding="utf-8")
    (book / "师承" / "读法" / "某书.md").write_text("掌柜的把那张欠条折了三折塞进袖子里\n", encoding="utf-8")
    o1 = book / "细纲" / "第1章.md"
    o1.write_text(o1.read_text(encoding="utf-8").replace("## 意图\n", "## 意图\n\n门上婆子记哪一房谁跟着。\n"), encoding="utf-8")
    ch = book / "正文" / "第1章.md"
    ch.write_text(f"# 第1章\n\n{common}。\n掌柜的把那张欠条折了三折塞进袖子里。\n门上婆子记哪一房谁跟着，一笔不漏。\n", encoding="utf-8")
    code, rows, summary = run(PROSE, str(ch))
    assert not any("师承" in r["source"] for r in hits(rows, "照抄")), rows
    outline = [r for r in hits(rows, "照抄") if "细纲" in r["source"]]
    assert outline and all(r["level"] == "warn" for r in outline), rows


@needs_node
def test_plan_finished_chapter_must_be_tracked(tmp_path: Path) -> None:
    """进了正文的章要登追踪：在场与知情有这一章、登记里有这一章，缺了报 warn。"""
    book = make_book(tmp_path)
    (book / "正文").mkdir(exist_ok=True)
    (book / "正文" / "第1章.md").write_text("# 第1章\n\n林昭把碗放下。\n", encoding="utf-8")
    (book / "追踪").mkdir(exist_ok=True)
    (book / "追踪" / "在场与知情.json").write_text(json.dumps({"chapters": []}, ensure_ascii=False), encoding="utf-8")
    (book / "追踪" / "登记.json").write_text(json.dumps({"objects": [], "phrases": []}, ensure_ascii=False), encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert len(hits(rows, "登追踪", "warn")) == 2, rows
    (book / "追踪" / "在场与知情.json").write_text(json.dumps({"chapters": [{"chapter": 1}]}, ensure_ascii=False), encoding="utf-8")
    (book / "追踪" / "登记.json").write_text(json.dumps({"objects": [], "phrases": [{"text": "碗放下", "kind": "反应层", "chapter": 1}]}, ensure_ascii=False), encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert not hits(rows, "登追踪"), rows


@needs_node
def test_plan_same_hook_run(tmp_path: Path) -> None:
    """章尾连着三章同一种类型报 warn（轮廓表 sameHookRun 2）；换一种就不报。"""
    book = make_book(tmp_path, chapters=3, outline_objects="无")
    setup_ledger(book)
    add_expect(book, 1, "| K001 | 开 | 她要他先开口 |\n| 章内 | 兑现 | 识破 |\n", relief="笑")
    add_expect(book, 2, "| K001 | 压 | 他绕着说 |\n", relief="甜")
    add_expect(book, 3, "| K001 | 推 | 他递碗 |\n", relief="暖")
    code, rows, summary = run(PLAN, str(book))
    assert any("章尾都是悬念" in r["note"] for r in hits(rows, "钩子", "warn")), rows
    o3 = book / "细纲" / "第3章.md"
    o3.write_text(o3.read_text(encoding="utf-8").replace("- 类型：悬念", "- 类型：情绪"), encoding="utf-8")
    code, rows, summary = run(PLAN, str(book))
    assert not any("章尾都是" in r["note"] for r in hits(rows, "钩子")), rows
