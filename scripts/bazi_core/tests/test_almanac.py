"""服務端干支計算對錶：與客戶端 bazi.dart 同校準點。"""

from __future__ import annotations

import re
from datetime import timedelta

from bazi_core.almanac import beijing_day_context, shichen_hours, term_time
from bazi_core.jieqi_corrections import correction_seconds


def test_term_time_matches_authoritative_almanac() -> None:
    # 紫金山曆書：2024 立春 北京時間 2024-02-04 16:26:53 → 就近取分 16:27
    lichun = term_time(2024, 315)
    assert lichun is not None
    beijing = lichun + timedelta(hours=8, seconds=30)  # 就近取分
    assert beijing.strftime("%Y-%m-%d %H:%M") == "2024-02-04 16:27"


def test_term_time_falls_back_outside_table() -> None:
    assert correction_seconds(1899, 315) is None
    assert correction_seconds(2101, 0) is None
    assert term_time(1899, 315) is not None  # 裸 Meeus 兜底


def test_term_time_is_cached_per_year_and_longitude() -> None:
    # 一天的流日語境要問 97 次（立春 1、月柱 24、節氣 72），同參數取緩存。
    assert term_time(2031, 45) is term_time(2031, 45)
    assert term_time.cache_info().hits > 0


def test_day_pillar_calibration_points() -> None:
    # bazi.dart 註釋校準點：2000-01-01 = 戊午、2024-02-04 = 戊戌
    assert beijing_day_context("2000-01-01").day_pillar == "戊午"
    assert beijing_day_context("2024-02-04").day_pillar == "戊戌"


def test_year_rolls_at_lichun() -> None:
    # 2024 立春為 2/4：前一日仍癸卯年，立春次日甲辰年
    assert beijing_day_context("2024-02-03").year_pillar == "癸卯"
    assert beijing_day_context("2024-02-05").year_pillar == "甲辰"


def test_2026_08_14_context() -> None:
    ctx = beijing_day_context("2026-08-14")
    # 2026 丙午年；立秋後申月，五虎遁丙年寅月起庚 → 申月丙申
    assert ctx.year_pillar == "丙午"
    assert ctx.month_pillar == "丙申"
    assert ctx.solar_term == "立秋"
    assert len(ctx.day_pillar) == 2


def test_payload_shape() -> None:
    payload = beijing_day_context("2026-08-14").as_payload()
    assert payload["civilDate"] == "2026-08-14"
    assert set(payload.keys()) == {
        "civilDate",
        "yearPillar",
        "monthPillar",
        "dayPillar",
        "solarTermContext",
    }


def test_shichen_hours_beijing() -> None:
    hours = shichen_hours("2026-08-14", "Asia/Shanghai", 116.4074)
    assert len(hours) == 12
    # 五鼠遁自流日日柱：2026-08-14 日柱天干推得子時時柱
    day_stem_zi = {
        "甲": "甲", "己": "甲", "乙": "丙", "庚": "丙", "丙": "戊",
        "辛": "戊", "丁": "庚", "壬": "庚", "戊": "壬", "癸": "壬",
    }
    day_pillar = beijing_day_context("2026-08-14").day_pillar
    assert hours[0]["pillar"] == day_stem_zi[day_pillar[0]] + "子"
    # 地支序固定子→亥
    assert hours[6]["pillar"][1] == "午"
    for h in hours:
        assert re.match(r"^\d{2}:\d{2}$", h["start"])
        assert re.match(r"^\d{2}:\d{2}$", h["end"])
    # 北京 8 月中：經度修正 −14 分鐘、EoT 約 −5 分鐘 → 子時起於 23:19 上下
    assert hours[0]["start"].startswith("23:")
    # 止即起 +2h（同分鐘）
    assert hours[3]["end"].split(":")[1] == hours[3]["start"].split(":")[1]


def test_shichen_hours_meridian_fallback() -> None:
    # 無座標退回時區中央經線：偏移只剩 EoT，起訖在整點 ±20 分鐘內
    hours = shichen_hours("2026-08-14", "Asia/Shanghai", None)
    minute = int(hours[0]["start"].split(":")[1])
    assert minute <= 20 or minute >= 40
