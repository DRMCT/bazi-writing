"""年度状态卡（DESIGN 10 第 6 条）：稳定段照抄档案、阶段卡按岁数取、这一年的机制领域抵抗线关系群像旧账岁气都在、
每条溯源都在池里（命盘、年表、快照、矩阵、线程、推演）；样例 examples/林昭/人物/状态/林昭/337.md 与重生成一致。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bazi_core import chart, ensemble, ensemble_run, matrix, stateyear, timeline

ROOT = Path(__file__).resolve().parents[3]
EX = ROOT / "examples" / "林昭"


def _load():
    doc = json.loads((EX / "人物" / "林昭.json").read_text(encoding="utf-8"))
    me = json.loads((EX / "命盘" / "林昭.json").read_text(encoding="utf-8"))
    others = [json.loads((ROOT / "examples" / "沈砚" / "命盘" / "沈砚.json").read_text(encoding="utf-8")),
              json.loads((EX / "命盘" / "裴恪.json").read_text(encoding="utf-8"))]
    run = json.loads((EX / "命盘" / "群像" / "推演.json").read_text(encoding="utf-8"))
    threads = ensemble_run.load_threads(json.loads((EX / "命盘" / "群像" / "线程.json").read_text(encoding="utf-8")))
    by_id = {t["id"]: t for t in run["threads"]}
    threads = [by_id.get(t["id"], t) for t in threads]
    return doc, me, others, threads, run


def test_sample_card_matches_and_all_ids_resolve() -> None:
    doc, me, others, threads, run = _load()
    md, used = stateyear.build(doc, me, 337, others, threads, run)
    assert md == (EX / "人物" / "状态" / "林昭" / "337.md").read_text(encoding="utf-8")
    pool = {f["id"] for f in me["features"]} | set(run["idPool"])
    pool |= {f["id"] for f in timeline.build(me, (0, 45))["features"]}
    pool |= {f["id"] for f in ensemble.snapshot([me] + others, 337)["features"]}
    pool |= {f["id"] for e in matrix.build([me] + others)["edges"] for f in e["features"]}
    for s in doc["sections"]:
        for t in s.get("traits", []):
            pool |= set(t.get("sources", []))
        for c in s.get("stages", []):
            pool.add(c["stage"] + "-基调")
            for t in c["traits"]:
                pool |= set(t.get("sources", []))
    assert used and set(used) <= pool
    assert ensemble_run.check_chain(md, {"idPool": sorted(pool)}) == []
    for key in ("## 稳定特质", "## 这十年（阶段卡）", "二十五到三十五岁：门后的孩子回来了", "## 这一年", "- 处境：三十一岁，流年辛酉",
                "候选年份", "- 动感情", "- 抵抗线：", "关系被引动（林昭看裴恪为偏印）", "- 群像：这一年事件源是裴恪", "TH-331-林昭-裴恪-感情", "当年岁气"):
        assert key in md, key
    assert sum(1 for l in md.splitlines() if "TH-331-林昭-裴恪-感情" in l) == 1  # 旧账上了卡就不在"悬置的账"里再列一遍
    assert "他在场" not in md and "他是谁" not in md


def test_quiet_year_without_others() -> None:
    doc, me, _, _, _ = _load()
    md, used = stateyear.build(doc, me, 333)
    assert "不是候选年份" in md and "关系被引动" not in md and "群像" not in md and "Q-333-林昭" in used


def test_source_year_and_absent_year_lines() -> None:
    doc, me, others, threads, run = _load()
    md, _ = stateyear.build(doc, me, 331, others, threads, run)
    assert "这一年林昭是事件源" in md and "TH-331" not in md.split("## 这一年")[1].split("悬置的账")[0]  # 331 是它开出来的年份，不算重上
    md2, _ = stateyear.build(doc, me, 330, others, threads, run)
    assert "事件源是沈砚" in md2 and "林昭在场" in md2 and "没有领域在动" in md2


def test_errors() -> None:
    doc, me, *_ = _load()
    with pytest.raises(ValueError):
        stateyear.build(doc, me, 300)  # 还没出生
    other = chart.chart_from_pillars("甲申", "壬申", "乙巳", "戊寅", "male", story_epoch=300, name="沈砚")
    with pytest.raises(ValueError):
        stateyear.build(doc, other, 337)  # 档案与命盘不是同一个人
    with pytest.raises(ValueError):
        stateyear.build(doc, chart.chart_from_pillars("庚寅", "壬午", "辛酉", "戊戌", "female", name="林昭"), 337)  # 没有纪年锚
