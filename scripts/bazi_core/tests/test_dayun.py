"""大運金樣例——自作者自己的排盤項目 test/dayun_test.dart 移植。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from bazi_core import dayun
from bazi_core.chart import four_pillars

BIRTH_UTC = datetime(2024, 6, 1, 4, tzinfo=timezone.utc)
# dart 測試給的真太陽時是 2024-06-01 12:00；此處直接以 UTC 12:00 當鐘表時、不做真太陽校正
PILLARS = four_pillars(datetime(2024, 6, 1, 12, tzinfo=timezone.utc), apply_true_solar=False)["pillars"]


def _compute(gender: str) -> dayun.DayunInfo:
    return dayun.compute(PILLARS["year"], PILLARS["month"], gender, BIRTH_UTC, 2024)


def test_yang_year_male_forward_female_backward() -> None:
    assert dayun.STEMS.index(PILLARS["year"][0]) % 2 == 0, "甲辰應為陽年"
    assert _compute("male").forward is True
    assert _compute("female").forward is False


def test_steps_from_month_pillar() -> None:
    month_idx = dayun.sexagenary_index(PILLARS["month"])
    male, female = _compute("male"), _compute("female")
    assert dayun.sexagenary_index(male.steps[0].pillar) == (month_idx + 1) % 60
    assert dayun.sexagenary_index(female.steps[0].pillar) == (month_idx - 1) % 60
    assert len(male.steps) == 12
    for i, step in enumerate(male.steps):
        assert dayun.sexagenary_index(step.pillar) == (month_idx + 1 + i) % 60
        assert step.end_age - step.start_age == 10
        assert step.start_year == 2024 + step.start_age
        assert step.end_year == 2024 + step.end_age


def test_start_age_range_and_complement() -> None:
    male, female = _compute("male"), _compute("female")
    assert 0 <= male.start_age_years < 10
    assert 0 <= female.start_age_years < 10
    # 順數到下節 + 逆數到上節 = 一個節月 ≈ 30.4 天 ≈ 10.1 年運齡
    assert abs(male.start_age_years + female.start_age_years - 10.15) < 0.5


def test_long_lived_still_inside_sequence() -> None:
    male = _compute("male")
    for age in (90, 110):
        step = dayun.current_step(male, BIRTH_UTC, datetime(2024 + age, 6, 1, tzinfo=timezone.utc))
        assert step is not None, f"{age} 歲應仍在大運序列內"
        assert step.sequence >= 9
    assert dayun.current_step(male, BIRTH_UTC, BIRTH_UTC) is None


def test_current_step_half_open_interval() -> None:
    male = _compute("male")
    first, last = male.steps[0], male.steps[-1]

    def at(age: int, days: int = 0) -> datetime:
        return datetime(2024 + age, 6, 1, 4, tzinfo=timezone.utc) + timedelta(days=days)

    assert dayun.current_step(male, BIRTH_UTC, at(first.start_age, -1)) is None
    assert dayun.current_step(male, BIRTH_UTC, at(first.start_age, 1)).sequence == 1
    assert dayun.current_step(male, BIRTH_UTC, at(first.start_age + 5)).sequence == 1
    assert dayun.current_step(male, BIRTH_UTC, at(first.end_age, -1)).sequence == 1
    assert dayun.current_step(male, BIRTH_UTC, at(first.end_age, 1)).sequence == 2
    assert dayun.current_step(male, BIRTH_UTC, at(last.end_age - 1)).sequence == 12
    assert dayun.current_step(male, BIRTH_UTC, at(last.end_age, 1)) is None


def test_format_start_age() -> None:
    assert dayun.format_start_age(6.0) == "6年"
    assert dayun.format_start_age(6.0 + 1 / 3) == "6年4月"  # 一日折四月


def test_fictional_mode_does_not_need_calendar() -> None:
    info = dayun.compute_from_pillars("甲子", "丙寅", None, 4.5, forward=False, birth_civil_year=100)
    assert info.forward is False
    assert info.start_age_label == "4年6月"
    assert info.steps[0].pillar == "乙丑"
    assert info.steps[0].start_age == 4
    assert info.steps[0].start_year == 104
    with pytest.raises(ValueError):
        dayun.compute_from_pillars("甲子", "丙寅", None, 3.0)


def test_invalid_pillar_rejected() -> None:
    with pytest.raises(ValueError):
        dayun.sexagenary_index("甲丑")  # 陽干配陰支
