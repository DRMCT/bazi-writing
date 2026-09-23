"""四柱金樣例——自作者自己的排盤項目 test/bazi_test.dart 移植，另加 tyme4py 交叉校驗。"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from bazi_core import chart, dayun

BJ = ZoneInfo("Asia/Shanghai")
UTC = timezone.utc


def _p(dt: datetime, **kw) -> dict:
    return chart.four_pillars(dt, apply_true_solar=False, **kw)["pillars"]


def test_day_pillar_anchors() -> None:
    assert _p(datetime(2000, 1, 1, 12, tzinfo=UTC))["day"] == "戊午"
    assert _p(datetime(2024, 2, 4, 12, tzinfo=UTC))["day"] == "戊戌"


def test_zi_hour_rolls_day() -> None:
    before = _p(datetime(2024, 6, 1, 22, 30, tzinfo=UTC))
    after = _p(datetime(2024, 6, 1, 23, 30, tzinfo=UTC))
    next_day = _p(datetime(2024, 6, 2, 12, tzinfo=UTC))
    assert before["hour"][1] == "亥"
    assert after["day"] == next_day["day"] and after["hour"][1] == "子"  # 晚子時歸次日，仍是子時
    assert dayun.sexagenary_index(after["day"]) == (dayun.sexagenary_index(before["day"]) + 1) % 60


def test_year_rolls_at_lichun() -> None:
    assert _p(datetime(2024, 2, 3, 12, tzinfo=BJ))["year"] == "癸卯"
    assert _p(datetime(2024, 2, 5, 12, tzinfo=BJ))["year"] == "甲辰"


def test_month_stem_wuhu_dun() -> None:
    p = _p(datetime(2024, 2, 10, 12, tzinfo=BJ))
    assert p["year"] == "甲辰" and p["month"] == "丙寅"


def test_hour_stem_wushu_dun() -> None:
    p = _p(datetime(2024, 6, 1, 12, tzinfo=UTC))
    day_stem = chart.STEMS.index(p["day"][0])
    zi_stem = (day_stem % 5) * 2 % 10
    hour_branch = chart.BRANCHES.index(p["hour"][1])
    assert p["hour"][0] == chart.STEMS[(zi_stem + hour_branch) % 10]


def test_known_chart_1986_05_29() -> None:
    # tyme4py / lunar_python 均排出 丙寅 癸巳 癸酉 癸亥（北京鐘表 22:30）
    c = chart.chart_from_civil(datetime(1986, 5, 29, 22, 30, tzinfo=BJ), "male", longitude_deg=116.4074)
    assert c["fourPillars"] == {"year": "丙寅", "month": "癸巳", "day": "癸酉", "hour": "癸亥"}
    assert c["natal"]["dayMaster"] == "癸水"
    assert c["dayun"]["forward"] is True  # 丙寅陽年男命順行
    assert c["dayun"]["steps"][0]["pillar"] == "甲午"
    assert c["birth"]["birthJie"] == "立夏"
    # 1986 年中國實行夏令時（tzdata 知道：Asia/Shanghai 當日為 UTC+9），鐘表 22:30 的真太陽時約 21:18，仍在亥時
    assert -80 < c["birth"]["trueSolarOffsetMinutes"] < -60


def test_true_solar_can_flip_hour_pillar() -> None:
    # 烏魯木齊（87.6°E）用北京時間，真太陽時比鐘表慢兩小時餘：鐘表 13:30 已入未時，真太陽時 11:2x 仍是午時
    dt = datetime(2024, 6, 1, 13, 30, tzinfo=BJ)
    assert chart.four_pillars(dt, longitude_deg=87.6)["pillars"]["hour"][1] == "午"
    assert chart.four_pillars(dt, apply_true_solar=False)["pillars"]["hour"][1] == "未"


def test_fictional_chart_and_liunian() -> None:
    c = chart.chart_from_pillars("甲子", "丙寅", "庚辰", "丙子", gender="female", start_age_years=6.0, story_epoch=300)
    assert c["calendar"]["mode"] == "fictional"
    assert c["dayun"]["forward"] is False  # 甲子陽年女命逆行
    assert c["dayun"]["steps"][0]["pillar"] == "乙丑"
    assert c["natal"]["structure"]["name"] == "偏财格"  # 庚生寅月，本氣甲透年干，庚見甲為偏財
    ln = chart.liunian(c, 30)
    assert ln["year"] == 330 and ln["pillar"] == "甲午"
    assert ln["dayun"]["sequence"] == 3


def test_fictional_rejects_mismatched_pillar() -> None:
    with pytest.raises(ValueError):
        chart.chart_from_pillars("甲丑", "丙寅", "庚辰", None, gender="male")


# ---------------------------------------------------------------- tyme4py 交叉校驗

tyme = pytest.importorskip("tyme4py", reason="開發期交叉校驗依賴，運行期不需要")


def _tyme_chart(dt: datetime):
    from tyme4py.eightchar import ChildLimit
    from tyme4py.enums import Gender
    from tyme4py.solar import SolarTime
    st = SolarTime.from_ymd_hms(dt.year, dt.month, dt.day, dt.hour, dt.minute, 0)
    ec = st.get_lunar_hour().get_eight_char()
    cl = ChildLimit(st, Gender.MAN)
    df = cl.get_start_decade_fortune()
    steps = [df.next(i).get_sixty_cycle().get_name() for i in range(12)]
    start_years = cl.get_year_count() + cl.get_month_count() / 12 + cl.get_day_count() / 365.25
    return ec.get_name().replace(" ", ""), steps, start_years


def test_cross_check_with_tyme4py_random_1000() -> None:
    rng = random.Random(20260921)
    max_age_diff = 0.0
    mismatches = []
    for _ in range(1000):
        dt = datetime(rng.randint(1920, 2080), rng.randint(1, 12), rng.randint(1, 28),
                      rng.randint(0, 23), rng.randint(0, 59), tzinfo=BJ)
        ours = chart.chart_from_civil(dt, "male", apply_true_solar=False)
        p = ours["fourPillars"]
        ours_name = p["year"] + p["month"] + p["day"] + p["hour"]
        theirs_name, theirs_steps, theirs_start = _tyme_chart(dt)
        if ours_name != theirs_name:
            mismatches.append((dt.isoformat(), ours_name, theirs_name))
            continue
        assert [s["pillar"] for s in ours["dayun"]["steps"]] == theirs_steps, dt
        max_age_diff = max(max_age_diff, abs(ours["dayun"]["startAgeYears"] - theirs_start))
    # 節氣交界分鐘級差異允許極少數不一致；超過千分之三即視為口徑錯誤
    assert len(mismatches) <= 3, mismatches[:5]
    # 起運歲數：tyme4py 按年月日整數計，與「天數÷3」的小數口徑差在一個月以內
    assert max_age_diff < 0.1, max_age_diff
