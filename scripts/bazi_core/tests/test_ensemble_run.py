"""群像推演（DESIGN-戏剧层 7.4）：热年由交汇点定、事件源按烈度、在场按边、赌注与画像、回应倾向查表、线程重上卡与改写、
过场与投影、确定性；样例 examples/林昭/命盘/群像/推演.json 与重生成一致；事件链 check_chain。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bazi_core import chart, dilemma, ensemble_run as run, schedule

ROOT = Path(__file__).resolve().parents[3]
EX = ROOT / "examples"


def _trio() -> list[dict]:
    a = chart.chart_from_pillars("甲申", "壬申", "乙巳", "戊寅", "male", story_epoch=300, name="沈砚")
    b = chart.chart_from_pillars("庚寅", "壬午", "辛酉", "戊戌", "female", start_age_years=5, story_epoch=306, name="林昭")
    c = chart.chart_from_pillars("丁亥", "壬寅", "己卯", "甲子", "male", story_epoch=303, name="裴恪")
    return [a, b, c]


def _threads() -> list[dict]:
    return run.load_threads({"schema": run.THREADS_SCHEMA, "threads": [
        {"id": "TH-331-林昭-裴恪-感情", "people": ["林昭", "裴恪"], "domain": "感情", "since": 331, "status": "悬置"},
        {"id": "TH-325-裴恪-林昭-感情", "people": ["裴恪", "林昭"], "domain": "感情", "since": 325, "status": "了结"},
    ]})


@pytest.fixture(scope="module")
def out() -> dict:
    return run.build(_trio(), (324, 346), "林昭", _threads())


def test_hot_years_are_intersection_years_and_gaps_cover_the_rest(out: dict) -> None:
    sched = schedule.build(_trio(), (324, 346))
    assert out["hotYears"] == sorted({it["year"] for it in sched["intersections"]})
    covered = set(out["hotYears"]) | {y for g in out["gaps"] for y in range(g["from"], g["to"] + 1)}
    assert covered == set(range(324, 347))
    assert all(g["years"] == g["to"] - g["from"] + 1 for g in out["gaps"])


def test_source_by_severity_and_present_by_edges(out: dict) -> None:
    cards = {c["year"]: c for c in out["cards"]}
    # 337 年林昭伏吟日柱、岁运相冲，裴恪冲日支：冲日支烈度更高，源是裴恪；沈砚那年只有同步忌运这种底色，不在场
    c = cards[337]
    assert c["source"] == "裴恪" and c["present"] == ["林昭", "裴恪"]
    assert dilemma.PRIORITY.index("冲日支") < dilemma.PRIORITY.index("伏吟")
    # 330 年沈砚冲提纲是源；林昭、裴恪没有领域在动，只按画像反应；裴恪因流年甲木是沈砚日主（在裴恪为忌）被五行临身拉进场
    c = cards[330]
    assert c["source"] == "沈砚" and set(c["present"]) == {"沈砚", "林昭", "裴恪"}
    st = {s["who"]: s for s in c["stakes"]}
    assert st["林昭"]["byPortraitOnly"] and st["裴恪"]["byPortraitOnly"] and not st["沈砚"]["byPortraitOnly"]
    for t in c["tendencies"]:
        assert "他当年没有领域在动" in [m["条件"] for m in t["modifiers"]]
    for c in out["cards"]:
        assert c["source"] in c["present"] and c["event"]["ids"] and c["intersections"]
        assert {s["who"] for s in c["stakes"]} == set(c["present"])
        assert {t["who"] for t in c["tendencies"]} == set(c["present"]) - {c["source"]}


def test_tendency_row_and_lean_follow_matrix(out: dict) -> None:
    for c in out["cards"]:
        for t in c["tendencies"]:
            row = run.ROWS[t["seesSourceAs"]]
            assert t["between"] == row["between"] and t["carries"] == row["carries"]
            if t["sourceIs"] in run.NEAR_ROLES:
                assert t["lean"] == "靠近" and t["text"] == row["near"]
            elif t["sourceIs"] in run.AWAY_ROLES:
                assert t["lean"] == "躲或压" and t["text"] == row["away"]
            else:
                assert t["lean"] == "看"
            assert f"E-{t['who']}-{c['source']}-十神-{t['seesSourceAs']}" in t["ids"]
            assert all(m["条件"] in run.MODS for m in t["modifiers"])
    c = {x["year"]: x for x in out["cards"]}[331]
    t = {x["who"]: x for x in c["tendencies"]}
    assert t["裴恪"]["seesSourceAs"] == "食神" and t["裴恪"]["lean"] == "躲或压" and "日柱相冲" in [m["条件"] for m in t["裴恪"]["modifiers"]]
    assert t["沈砚"]["seesSourceAs"] == "七杀" and t["沈砚"]["lean"] == "靠近"


def test_threads_resurface_after_start_and_closed_ones_do_not(out: dict) -> None:
    years = {c["year"]: [t["id"] for t in c["threads"]] for c in out["cards"]}
    assert "TH-331-林昭-裴恪-感情" not in years[331] and "TH-331-林昭-裴恪-感情" not in years[324]
    assert "TH-331-林昭-裴恪-感情" in years[337] and "TH-331-林昭-裴恪-感情" in years[343]
    assert all("TH-325-裴恪-林昭-感情" not in v for v in years.values())
    c337 = next(t for c in out["cards"] if c["year"] == 337 for t in c["threads"])
    assert "林昭今年是候选年份且动感情" in c337["why"]
    th = {t["id"]: t for t in out["threads"]}
    assert th["TH-331-林昭-裴恪-感情"]["rewriteYears"] == [336, 341, 346]  # 裴恪 336、346 换运，林昭 341 换运；331 以前不算
    assert "TH-331-林昭-裴恪-感情" in out["idPool"] and any(f["id"] == "TH-331-林昭-裴恪-感情" for f in out["features"])
    for c in out["cards"]:
        if c["openThread"]:
            o = c["openThread"]
            assert o["id"] == f"TH-{c['year']}-{c['source']}-{o['people'][1]}-{o['domain']}" and o["status"] == "悬置"


def test_outline_volumes_follow_main_dayun(out: dict) -> None:
    vols = out["outline"]["volumes"]
    assert [v["stage"] for v in vols] == ["D-2-庚辰", "D-3-己卯", "D-4-戊寅"]
    assert vols[0]["years"] == [324, 330] and vols[-1]["years"] == [341, 346]
    assert sum(len(v["hotYears"]) for v in vols) == len(out["hotYears"])
    assert any(t["who"] == "沈砚" and t["year"] == 343 for t in vols[2]["turningPoints"])
    assert [s["year"] for s in out["outline"]["segments"]] == out["hotYears"]


def test_deterministic_and_pool_covers_card_ids(out: dict) -> None:
    again = run.build(_trio(), (324, 346), "林昭", _threads())
    assert json.dumps(again, ensure_ascii=False, sort_keys=True) == json.dumps(out, ensure_ascii=False, sort_keys=True)
    pool = set(out["idPool"])
    for c in out["cards"]:
        assert set(c["ids"]) <= pool


def test_bad_threads_rejected() -> None:
    with pytest.raises(ValueError):
        run.load_threads({"schema": "x", "threads": []})
    with pytest.raises(ValueError):
        run.load_threads({"schema": run.THREADS_SCHEMA, "threads": [{"id": "TH-1-a-b-感情", "people": ["a", "b"], "domain": "感情", "since": 1, "status": "挂着"}]})
    with pytest.raises(ValueError):
        run.build(_trio(), (324, 330), "无此人")


def test_check_chain(out: dict) -> None:
    good = "## 337\n\n- 裴恪先动。 ｜溯源 Q-337-裴恪、E-林昭-裴恪-十神-偏印、TH-331-林昭-裴恪-感情\n"
    assert run.check_chain(good, out) == []
    bad = "## 337\n\n- 谁动。 ｜溯源 Q-337-裴恪、E-林昭-裴恪-十神-正官\n- 空。 ｜溯源 \n"
    ps = run.check_chain(bad, out)
    assert any(p.get("id") == "E-林昭-裴恪-十神-正官" for p in ps) and any(p["problem"] == "溯源为空" for p in ps)
    assert run.check_chain("没有溯源的文本", out)


def test_example_run_matches_regenerated() -> None:
    saved = json.loads((EX / "林昭" / "命盘" / "群像" / "推演.json").read_text(encoding="utf-8"))
    threads = run.load_threads(json.loads((EX / "林昭" / "命盘" / "群像" / "线程.json").read_text(encoding="utf-8")))
    charts = [json.loads((EX / "沈砚" / "命盘" / "沈砚.json").read_text(encoding="utf-8")),
              json.loads((EX / "林昭" / "命盘" / "林昭.json").read_text(encoding="utf-8")),
              json.loads((EX / "林昭" / "命盘" / "裴恪.json").read_text(encoding="utf-8"))]
    fresh = run.build(charts, (324, 346), "林昭", threads)
    assert json.dumps(fresh, ensure_ascii=False, sort_keys=True) == json.dumps(saved, ensure_ascii=False, sort_keys=True)
    md = (EX / "林昭" / "人物" / "推演.md").read_text(encoding="utf-8")
    assert run.check_chain(md, saved) == []
