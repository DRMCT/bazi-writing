"""反推搜索：硬约束、确定性、去重、现实历枚举与四柱一致、关系约束读他人命盘。枚举用年柱收窄，测试不跑全量。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from bazi_core import chart, search


def _cons(**kw) -> dict:
    base = {"calendar": {"mode": "fictional", "year_pillars": ["甲子"]}, "gender": "female", "story_age_window": [24, 46]}
    base.update(kw)
    return base


def test_hard_constraints_and_determinism() -> None:
    cons = _cons(day_master={"stem": ["丙"], "hard": True}, strength={"value": "身弱", "weight": 2},
                 arc={"template": "正弧", "turning_age": 30, "weight": 3},
                 events=[{"age_range": [28, 32], "type": "冲日支", "weight": 2}])
    a = search.search(cons, top=5)
    b = search.search(cons, top=5)
    assert a["results"] == b["results"]
    assert a["searched"] == 12 * 60 * 12 and 1 <= len(a["results"]) <= 5
    for r in a["results"]:
        assert r["pillars"]["year"] == "甲子" and r["pillars"]["day"][0] == "丙"
        assert r["score"] <= r["max"] == 8.0
        assert {h["constraint"] for h in r["hits"]} == {"day_master", "strength", "arc", "events"}
        assert abs(sum(h["points"] for h in r["hits"]) - r["score"]) < 1e-6
    scores = [r["score"] for r in a["results"]]
    assert scores == sorted(scores, reverse=True)


def test_results_are_deduplicated() -> None:
    res = search.search(_cons(day_branch={"any_of": ["午"], "weight": 1}), top=5)["results"]
    for i, x in enumerate(res):
        for y in res[i + 1:]:
            same = sum(x["pillars"][k] == y["pillars"][k] for k in ("year", "month", "day", "hour"))
            assert same < 3 or not search._dup({"pillars": x["pillars"], "_tg": search._tg_counts(x["pillars"])},
                                               {"pillars": y["pillars"], "_tg": search._tg_counts(y["pillars"])})


def test_real_calendar_pillars_match_chart() -> None:
    cons = {"calendar": {"mode": "real", "birth_year_range": [1990, 1990]}, "gender": "male",
            "day_branch": {"any_of": ["酉"], "hard": True}, "structure": {"any_of": ["七杀格"], "weight": 1}}
    out = search.search(cons, top=3)
    assert out["searched"] == 365 * 12
    for r in out["results"]:
        assert r["pillars"]["day"][1] == "酉" and r["birth"]["date"].startswith("1990")
        local = datetime.fromisoformat(r["birth"]["local"])
        assert chart.four_pillars(local, None, apply_true_solar=False)["pillars"] == r["pillars"]


def test_relation_constraint_reads_other_chart(tmp_path: Path) -> None:
    other = chart.chart_from_pillars("甲申", "壬申", "乙巳", "戊寅", "male", story_epoch=300, name="沈砚")
    (tmp_path / "沈砚.json").write_text(json.dumps(other, ensure_ascii=False), encoding="utf-8")
    cons = _cons(relations=[{"to": "沈砚", "ten_god_seen_by_them": "七杀", "hard": True}])
    res = search.search(cons, top=3, charts_dir=tmp_path)["results"]
    assert res and all(r["pillars"]["day"][0] == "辛" for r in res)  # 乙木见辛金为七杀


def test_bad_constraints() -> None:
    with pytest.raises(ValueError):
        search.search({"calendar": {"mode": "fictional", "year_pillars": ["甲子"]}})
    with pytest.raises(ValueError):
        search.search({"gender": "male", "calendar": {"year_pillars": ["甲子"]}, "arc": {"template": "正弧"}})
    with pytest.raises(ValueError):
        search.search(_cons(events=[{"age_range": [1, 2], "type": "发财"}]))


def test_random_fill_is_seeded_and_fills_missing_fields() -> None:
    cons = {"calendar": {"mode": "fictional", "year_pillars": ["甲子"]}, "day_master": {"stem": ["丙"], "hard": True}}
    with pytest.raises(ValueError):
        search.search(cons, top=3)  # 没给性别又没给种子
    a = search.search(cons, top=3, seed=7)
    b = search.search(cons, top=3, seed=7)
    c = search.search(cons, top=3, seed=8)
    assert a["results"] == b["results"] and a["results"] != c["results"]
    assert a["random"]["seed"] == 7 and a["random"]["pool"] > 0 and set(a["random"]["filled"]) == {"gender", "start_age"}
    assert a["constraints"]["gender"] in ("male", "female") and 0 <= a["constraints"]["calendar"]["start_age"] <= 9
    assert a["constraints"]["random"]["seed"] == 7
    for r in a["results"]:
        assert r["pillars"]["day"][0] == "丙" and r["pillars"]["year"] == "甲子"
        assert f"--start-age {a['constraints']['calendar']['start_age']}" in r["chartArgs"]
    # 种子写进约束后再跑，结果相同（保存的约束可复现）
    again = search.search(a["constraints"], top=3)
    assert again["results"] == a["results"]


def test_constraint_aliases_are_normalized() -> None:
    """身强 认作 身旺；relations 的 day_branch 字符串包成列表（样例书实测 2026-09-25：字符串会被当成单字集合）。"""
    cons = {"strength": {"value": "身强"}, "relations": [{"to": "甲", "day_branch": "六冲"}]}
    search.normalize_constraints(cons)
    assert cons["strength"]["value"] == "身旺"
    assert cons["relations"][0]["day_branch"] == ["六冲"]
    cons2 = {"strength": {"value": "身弱"}, "relations": [{"to": "甲", "day_branch": ["刑", "害"]}]}
    search.normalize_constraints(cons2)
    assert cons2["strength"]["value"] == "身弱" and cons2["relations"][0]["day_branch"] == ["刑", "害"]

