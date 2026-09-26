"""群像快照：流月五虎遁、每人状态与年表一致、边的引动原因、未出生与无纪年锚的处理。"""

from __future__ import annotations

import pytest

from bazi_core import chart, ensemble, timeline


def _pair(epoch_b: int | None = 306):
    a = chart.chart_from_pillars("甲申", "壬申", "乙巳", "戊寅", "male", story_epoch=300, name="沈砚")
    b = chart.chart_from_pillars("戊戌", "甲寅", "辛酉", "甲午", "female", start_age_years=5, story_epoch=epoch_b, name="林昭")
    return [a, b]


def test_month_pillars_wuhudun() -> None:
    assert ensemble.month_pillars("甲子")[0] == "丙寅" and ensemble.month_pillars("甲子")[11] == "丁丑"
    assert ensemble.month_pillars("戊午")[0] == "甲寅"
    assert len(set(ensemble.month_pillars("癸卯"))) == 12


def test_people_state_matches_timeline() -> None:
    charts = _pair()
    snap = ensemble.snapshot(charts, 327, months=True)
    p = {x["name"]: x for x in snap["people"]}
    assert p["沈砚"]["age"] == 27 and p["林昭"]["age"] == 21
    t = timeline.build(charts[0], (27, 27))["years"][0]
    assert p["沈砚"]["liunian"] == t["pillar"] and p["沈砚"]["mechanisms"] == t["mechanisms"]
    assert "冲日支" in p["沈砚"]["keyMechanisms"] and len(p["沈砚"]["months"]) == 12
    ids = [f["id"] for f in snap["features"]]
    assert len(ids) == len(set(ids)) and "Q-327-沈砚" in ids


def test_edge_reasons() -> None:
    snap = ensemble.snapshot(_pair(), 333)
    kinds = {(e["from"], e["to"]): {r["kind"] for r in e["reasons"]} for e in snap["edges"]}
    assert "五行临身" in kinds[("林昭", "沈砚")]  # 乙巳年，乙木是沈砚日主，在林昭为忌
    for e in snap["edges"]:
        assert e["ids"] and all(i.startswith("Q-333-") for i in e["ids"]) and e["matrixIds"]


def test_unborn_and_no_anchor() -> None:
    snap = ensemble.snapshot(_pair(), 303)
    p = {x["name"]: x for x in snap["people"]}
    assert p["林昭"]["born"] is False and not snap["edges"]
    with pytest.raises(ValueError):
        ensemble.snapshot(_pair(epoch_b=None), 330)
