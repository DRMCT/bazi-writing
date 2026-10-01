"""story 导出器（DESIGN-人物层 9，M7）：样例重生成一致、卡的字段齐、关系表按边映射、导出本过去术语检查、作者补充段保留、短篇只换标记段、没矩阵不崩。"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import export_story as ex

ROOT = Path(__file__).resolve().parents[3]
LIN = ROOT / "examples" / "林昭"
DOCS = [LIN / "人物" / "林昭.json", ROOT / "examples" / "沈砚" / "人物" / "沈砚.json"]
CMD = "python export_story.py 人物/林昭.json 人物/沈砚.json --target {t} --out examples/林昭/导出/{t}"
MAIN_FIELDS = ("姓名：", "性别：", "年龄：", "角色定位：", "身份标签：", "外貌特征：", "性格关键词：", "核心目标：", "核心动机：", "致命弱点：", "口头禅/标志动作：")
SUPPORT_FIELDS = ("姓名：", "性别：", "角色功能：", "与主角关系：", "核心特质：", "标志性特征：", "退场方式：")
BLOCKS = ("## 三层标签", "## 动机链", "## 语言风格档案（七维）", "## 人物弧线（按阶段）", "## 关键节点与两难", "## 亲密关系模式", "## 别人眼里的他", "## 作者补充")


def _ctx():
    mx = json.loads((LIN / "命盘" / "矩阵.json").read_text(encoding="utf-8"))
    sc = json.loads((LIN / "命盘" / "日程.json").read_text(encoding="utf-8"))
    run = json.loads((LIN / "命盘" / "群像" / "推演.json").read_text(encoding="utf-8"))
    return mx, sc, run


def _same_tree(a: Path, b: Path) -> None:
    files = sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file())
    assert files == sorted(p.relative_to(b) for p in b.rglob("*") if p.is_file())
    for rel in files:
        assert (a / rel).read_text(encoding="utf-8") == (b / rel).read_text(encoding="utf-8"), rel


def test_story_long_sample_regenerates(tmp_path: Path) -> None:
    mx, sc, run = _ctx()
    out = tmp_path / "book"
    written = ex.export(DOCS, "story-long", out, mx=mx, schedule=sc, run=run, cmd=CMD.format(t="story-long"))
    assert [p.relative_to(out).as_posix() for p in written] == ["设定/角色/林昭.md", "设定/角色/沈砚.md", "设定/关系.md", "设定/来源/bazi-writing.md"]
    _same_tree(out, LIN / "导出" / "story-long")


def test_story_short_sample_regenerates(tmp_path: Path) -> None:
    mx, sc, run = _ctx()
    out = tmp_path / "short"
    ex.export(DOCS, "story-short", out, mx=mx, schedule=sc, run=run)
    _same_tree(out, LIN / "导出" / "story-short")


def test_cards_have_story_fields_and_blocks() -> None:
    lin = (LIN / "导出" / "story-long" / "设定" / "角色" / "林昭.md").read_text(encoding="utf-8")
    shen = (LIN / "导出" / "story-long" / "设定" / "角色" / "沈砚.md").read_text(encoding="utf-8")
    assert lin.startswith("# 林昭 · 主角卡") and shen.startswith("# 沈砚 · 配角卡")
    for f in MAIN_FIELDS:
        assert f"\n{f}" in lin, f
    for f in SUPPORT_FIELDS:
        assert f"\n{f}" in shen, f
    for b in BLOCKS:
        assert b in lin and b in shen, b
    assert "性别：女" in lin and "年龄：十八岁（324年）" in lin and "性别：男" in shen  # 命盘给性别，推演窗口起点给年龄
    assert "## 意象与视角" in lin and "## 意象与视角" not in shen  # literary 才有
    assert "（当前）" in lin  # 324 年落在十五到二十五岁那张卡
    assert "退场方式：待补充" in shen and "与主角关系：沈砚眼里：" in shen
    # 靶子实测（2026-09-25）：口头禅与标志动作段废；story 模板的这一栏填指路，情绪过程段进卡成写戏用的一块
    assert f"1. 口癖和惯用语：{ex.NO_CATCH}" in shen and f"口头禅/标志动作：{ex.NO_CATCH}" in lin
    assert "\n标志性特征：" in shen and "把笔在指间过一下" not in shen
    assert "## 情绪过程（写戏用）" not in lin and "## 情绪过程（写戏用）" not in shen  # 两份样例都没写这段（新书写在戏用页），可选段缺席不出块
    src = (LIN / "导出" / "story-long" / "设定" / "来源" / "bazi-writing.md").read_text(encoding="utf-8")
    assert "与书名目录并列放在项目根" in src and "对白样本" in src


def test_relations_table_maps_edges() -> None:
    rel = (LIN / "导出" / "story-long" / "设定" / "关系.md").read_text(encoding="utf-8")
    assert rel.startswith("# 角色关系图") and "## 关系总览" in rel and "## 关系演变" in rel and "## 核心冲突关系" in rel
    rows = [l for l in rel.splitlines() if l.startswith("| ") and not l.startswith("| 角色 A")]
    assert [r.split(" | ")[:2] for r in rows] == [["| 林昭", "沈砚"], ["| 林昭", "裴恪"], ["| 沈砚", "裴恪"]]  # 主角的边在前
    assert "权威型（林昭在上" in rows[0] and "复杂" in rows[0] and "待补充（330年首次交汇）" in rows[0]
    assert "冲突型（一近就撞）" in rows[1]  # 林昭裴恪日支相冲
    assert "331–342年两人同陷逆风" in rows[0] and "311–312" not in rows[0]  # 按推演窗口裁掉出生前的段
    assert "331年起感情上的账悬置" in rows[1]
    assert "只排了盘、没有人物档案的角色：裴恪" in rel


@pytest.mark.skipif(shutil.which("node") is None, reason="需要 node")
def test_exports_pass_term_check() -> None:
    r = subprocess.run(["node", str(ROOT / "scripts" / "check-terms.js"), str(LIN / "导出"), "--period", "古代", "--summary"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr
    summary = json.loads(r.stdout.strip().splitlines()[-1])
    assert summary["errors"] == 0 and summary["files"] == 5


def test_author_tail_survives_reexport(tmp_path: Path) -> None:
    mx, sc, run = _ctx()
    out = tmp_path / "book"
    ex.export(DOCS[:1], "story-long", out, mx=mx, schedule=sc, run=run)
    card = out / "设定" / "角色" / "林昭.md"
    text = card.read_text(encoding="utf-8")
    text = text[: text.index("## 作者补充")] + "## 作者补充\n\n退场方式：第 80 章远走。\n"
    card.write_text(text, encoding="utf-8", newline="\n")
    ex.export(DOCS[:1], "story-long", out, mx=mx, schedule=sc, run=run)
    again = card.read_text(encoding="utf-8")
    assert again.endswith("## 作者补充\n\n退场方式：第 80 章远走。\n") and again.count("## 作者补充") == 1
    assert again.startswith("# 林昭 · 主角卡")


def test_short_block_replaces_only_marked_section(tmp_path: Path) -> None:
    out = tmp_path / "short"
    out.mkdir()
    setting = out / "设定.md"
    setting.write_text("# 设定\n\n## 核心框架\n\n作者写的。\n", encoding="utf-8", newline="\n")
    ex.export(DOCS[:1], "story-short", out)
    first = setting.read_text(encoding="utf-8")
    assert first.startswith("# 设定\n\n## 核心框架\n\n作者写的。\n") and ex.START in first and ex.END in first
    setting.write_text(first + "\n## 贯穿道具\n\n后加的。\n", encoding="utf-8", newline="\n")
    ex.export(DOCS[:1], "story-short", out)
    second = setting.read_text(encoding="utf-8")
    assert second.count(ex.START) == 1 and second.endswith("\n## 贯穿道具\n\n后加的。\n") and "作者写的。" in second


def test_no_matrix_no_run(tmp_path: Path) -> None:
    out = tmp_path / "book"
    ex.export(DOCS, "story-long", out)  # 没矩阵、日程、推演：主角取第一份，年龄待补充，关系表空
    lin = (out / "设定" / "角色" / "林昭.md").read_text(encoding="utf-8")
    assert "年龄：待补充" in lin and "（当前）" not in lin
    rel = (out / "设定" / "关系.md").read_text(encoding="utf-8")
    assert "没有矩阵文件" in rel and "| 待补充 | 待补充 |" in rel
    shen = (out / "设定" / "角色" / "沈砚.md").read_text(encoding="utf-8")
    assert "与主角关系：沈砚眼里：" in shen  # 没有边也能从档案的"他人眼中的他"取


def test_cli_dry_run_writes_nothing(tmp_path: Path) -> None:
    out = tmp_path / "book"
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "export_story.py"), str(DOCS[0]), "--target", "story-long", "--out", str(out), "--dry-run"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    assert "会写" in r.stdout and not out.exists()


def test_old_profile_emotion_section_becomes_a_block(tmp_path: Path) -> None:
    """旧档案的情绪过程段（可选段）导出成角色卡写戏用的一块，排在语言风格档案与人物弧线之间。"""
    doc = json.loads(DOCS[1].read_text(encoding="utf-8"))
    doc["sections"].append({"title": "情绪过程", "traits": [{"beat": b, "text": "一拍", "sources": ["DM"]} for b in ("碰线", "身体先动", "盖法", "余波")]})
    src = tmp_path / "人物" / "沈砚.json"
    src.parent.mkdir()
    src.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    mx, sc, run = _ctx()
    ex.export([DOCS[0], src], "story-long", tmp_path / "book", mx=mx, schedule=sc, run=run)
    shen = (tmp_path / "book" / "设定" / "角色" / "沈砚.md").read_text(encoding="utf-8")
    assert "## 情绪过程（写戏用）" in shen and ex.BEAT_HEAD in shen and "- 碰线：" in shen and "- 盖法：" in shen and "- 余波：" in shen
    assert shen.index("## 语言风格档案（七维）") < shen.index("## 情绪过程（写戏用）") < shen.index("## 人物弧线（按阶段）")
