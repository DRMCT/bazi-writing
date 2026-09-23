"""《穷通宝鉴评注》例盘烟雾测试。

夹具 fixtures/qiongtong_lipan.json 由 scripts/extract_lipan.py 从校对本抽出：九百多张例盘的四柱、
所属月份、断语，四百多张带农历纪年。用来烟雾 present_in_chart（每张盘都能查到调候并判透藏），
并拿带纪年的盘反过来校排盘：农历纪年经 tyme4py 转公历，再由 chart.four_pillars 排出四柱，
应与书上的四柱一致。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from bazi_core import chart, tiaohou

FIXTURE = Path(__file__).parent / "fixtures" / "qiongtong_lipan.json"
BJ = timezone(timedelta(hours=8))   # 书上纪年按中国本地时，取东八区近似
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
STEMS = "甲乙丙丁戊己庚辛壬癸"

# 农历纪年排出的四柱与书不合的例盘：纪年行错配到邻盘或书自身有误，抽取报告里另记
KNOWN_DATE_MISMATCH = {"戊-006", "戊-026", "戊-089", "己-004", "壬-008"}


@pytest.fixture(scope="module")
def cases() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]


def _clean(cases: list[dict]) -> list[dict]:
    return [c for c in cases if not c["flags"]]


def solar_datetime(lunar: dict) -> datetime:
    """农历年月日时支 → 该时辰中点的东八区时刻。"""
    from tyme4py.lunar import LunarHour
    hour_idx = BRANCHES.index(lunar["hourBranch"])
    lh = LunarHour.from_ymd_hms(lunar["year"], -lunar["month"] if lunar["leap"] else lunar["month"],
                                lunar["day"], (hour_idx * 2) % 24, 0, 0)
    st = lh.get_solar_time()
    base = datetime(st.get_year(), st.get_month(), st.get_day(), 12, tzinfo=BJ)
    return base + timedelta(hours=hour_idx * 2 - 12)   # 子时中点取当日 0 点，亥时 22 点


def test_fixture_shape(cases: list[dict]) -> None:
    assert len(cases) >= 900
    per = {dm: sum(1 for c in cases if c["dayMaster"] == dm) for dm in STEMS}
    assert all(v >= 70 for v in per.values()), per
    assert sum(1 for c in cases if c["lunar"]) >= 400
    for c in cases:
        assert set(c["pillars"]) == {"year", "month", "day", "hour"}
        assert all(p[0] in STEMS and p[1] in BRANCHES for p in c["pillars"].values())


def test_day_master_and_section_match_volume(cases: list[dict]) -> None:
    clean = _clean(cases)
    assert len(clean) >= len(cases) - 12
    for c in clean:
        assert c["pillars"]["day"][0] == c["dayMaster"]
        if c["section"]:
            assert c["pillars"]["month"][1] in c["section"]


def test_present_in_chart_runs_on_every_example(cases: list[dict]) -> None:
    for c in _clean(cases):
        p = c["pillars"]
        info = tiaohou.present_in_chart(p, p["day"][0], p["month"][1])
        assert info["source"] == f"调候-{p['day'][0]}{p['month'][1]}"
        assert info["stems"], c["id"]
        assert set(info["exposed"]) | set(info["hidden"]) | set(info["missing"]) == {s for s in info["stems"] if s in STEMS}
        assert not (set(info["exposed"]) & set(info["hidden"]))


def test_lunar_dates_reproduce_book_pillars(cases: list[dict]) -> None:
    dated = [c for c in _clean(cases) if c["lunar"]]
    bad = []
    for c in dated:
        p = chart.four_pillars(solar_datetime(c["lunar"]), apply_true_solar=False)["pillars"]
        if p != c["pillars"]:
            bad.append(c["id"])
    assert set(bad) <= KNOWN_DATE_MISMATCH, bad
    assert len(bad) / len(dated) < 0.02


def _by_name(cases: list[dict], name: str) -> dict:
    return next(c for c in cases if c["name"] == name)


def test_chen_jitang_before_yushui(cases: list[dict]) -> None:
    # 陈济棠：庚寅 戊寅 甲子 丙寅，光绪十六年正月二十三日寅时，书注「生于雨水前七日，丙透癸藏」
    c = _by_name(cases, "陈济棠")
    assert c["pillars"] == {"year": "庚寅", "month": "戊寅", "day": "甲子", "hour": "丙寅"}
    info = tiaohou.present_in_chart(c["pillars"], "甲", "寅", solar_datetime(c["lunar"]))
    assert info["period"]["label"] == "雨水前" and not info["periodUnresolved"]
    assert info["stems"] == ["丙", "癸"]
    assert info["exposed"] == ["丙"] and info["hidden"] == ["癸"] and info["missing"] == []


def test_yang_huazhao_after_yushui(cases: list[dict]) -> None:
    # 杨化昭：庚寅 戊寅 甲戌 丙寅，「生于雨水后五日……四柱无癸」
    c = _by_name(cases, "杨化昭")
    info = tiaohou.present_in_chart(c["pillars"], "甲", "寅", solar_datetime(c["lunar"]))
    assert info["period"]["label"] == "雨水后" and info["stems"] == ["庚", "丁"]
    # 书说四柱无癸：癸既不透也不藏
    hidden = {chart.STEMS[h] for p in c["pillars"].values() for h in chart.HIDDEN_STEMS[chart.BRANCHES.index(p[1])]}
    assert "癸" not in hidden and all(p[0] != "癸" for p in c["pillars"].values())


def test_yu_youren_after_qingming(cases: list[dict]) -> None:
    # 于右任：己卯 戊辰 甲子 壬申，「生于清明后六日，乙木司令，义同二月」→ 三月甲木清明后谷雨前段
    c = _by_name(cases, "于右任")
    info = tiaohou.present_in_chart(c["pillars"], "甲", "辰", solar_datetime(c["lunar"]))
    assert info["period"]["label"] == "清明后谷雨前" and not info["periodUnresolved"]
    assert info["stems"] == ["庚", "丁"]
