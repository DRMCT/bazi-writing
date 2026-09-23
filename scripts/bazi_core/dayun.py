"""大運排步——作者自己的排盤項目 lib/core/dayun.dart 的 Python 移植。

子平口徑：陽男陰女順行、陰男陽女逆行，自月柱推步；起運按節（不按氣），
順行數到下一節、逆行數到上一節，三日折一年。十二步覆蓋起運後 120 年。

架空歷模式不走節氣：月柱、順逆與起運歲數由調用方直接給定。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .almanac import term_time
from .shishen import BRANCHES, STEMS

# 十二節的黃經（立春起，每 30°）。起運按節，不按氣。
JIE_LONGITUDES: tuple[float, ...] = (
    315, 345, 15, 45, 75, 105, 135, 165, 195, 225, 255, 285,
)

STEPS = 12


def sexagenary_index(pillar: str) -> int:
    """干支 → 六十甲子序（0 = 甲子）。干支陰陽不配時拋 ValueError。"""
    s = STEMS.index(pillar[0])
    b = BRANCHES.index(pillar[1])
    for i in range(60):
        if i % 10 == s and i % 12 == b:
            return i
    raise ValueError(f"非法干支：{pillar}")


def pillar_name(index: int) -> str:
    index %= 60
    return STEMS[index % 10] + BRANCHES[index % 12]


@dataclass(frozen=True)
class DayunStep:
    sequence: int
    pillar: str
    start_age: int
    end_age: int
    # 換運公曆年 = 出生公曆年 + 歲數（約數）；架空模式下為故事紀年偏移
    start_year: int | None
    end_year: int | None

    def as_payload(self) -> dict:
        return {
            "sequence": self.sequence,
            "pillar": self.pillar,
            "startAge": self.start_age,
            "endAge": self.end_age,
            "startYear": self.start_year,
            "endYear": self.end_year,
        }


@dataclass(frozen=True)
class DayunInfo:
    forward: bool
    start_age_years: float
    start_age_label: str
    steps: tuple[DayunStep, ...]

    def as_payload(self) -> dict:
        return {
            "forward": self.forward,
            "startAgeYears": round(self.start_age_years, 4),
            "startAgeLabel": self.start_age_label,
            "steps": [s.as_payload() for s in self.steps],
        }


def is_forward(year_stem_index: int, gender: str) -> bool:
    """陽男陰女順行。gender 取 'male' / 'female'。"""
    if gender not in ("male", "female"):
        raise ValueError(f"gender 必須是 male 或 female，收到 {gender!r}")
    yang_year = year_stem_index % 2 == 0
    return (gender == "male") == yang_year


def format_start_age(years: float) -> str:
    """「6年4月」。與 dayun.dart _formatStartAge 同式：三日折一年，一日折四月。"""
    whole = int(years)
    rem_days = (years - whole) * 3
    months = max(0, min(11, round(rem_days * 4)))
    if months == 0:
        return f"{whole}年"
    return f"{whole}年{months}月"


def _jie_times_around(instant_utc: datetime) -> list[datetime]:
    times: list[datetime] = []
    for year in (instant_utc.year - 1, instant_utc.year, instant_utc.year + 1):
        for lon in JIE_LONGITUDES:
            t = term_time(year, lon)
            if t is not None:
                times.append(t)
    times.sort()
    return times


def start_age_years_from_birth(birth_utc: datetime, forward: bool) -> float:
    """起運歲數（年，帶小數）：距下一節（順）或上一節（逆）的天數除以三。"""
    birth = birth_utc.astimezone(timezone.utc)
    jies = _jie_times_around(birth)
    boundary: datetime | None = None
    if forward:
        for t in jies:
            if t > birth:
                boundary = t
                break
    else:
        for t in reversed(jies):
            if t < birth:
                boundary = t
                break
    if boundary is None:
        return 0.0
    delta = (boundary - birth) if forward else (birth - boundary)
    days = delta.total_seconds() / 86400.0
    return days / 3.0


def steps_from_month(
    month_pillar: str,
    forward: bool,
    start_age_years: float,
    birth_civil_year: int | None,
) -> tuple[DayunStep, ...]:
    month_idx = sexagenary_index(month_pillar)
    base = int(start_age_years)
    steps: list[DayunStep] = []
    for i in range(STEPS):
        idx = (month_idx + 1 + i) % 60 if forward else (month_idx - 1 - i) % 60
        start_age = base + i * 10
        steps.append(
            DayunStep(
                sequence=i + 1,
                pillar=pillar_name(idx),
                start_age=start_age,
                end_age=start_age + 10,
                start_year=None if birth_civil_year is None else birth_civil_year + start_age,
                end_year=None if birth_civil_year is None else birth_civil_year + start_age + 10,
            )
        )
    return tuple(steps)


def compute(
    year_pillar: str,
    month_pillar: str,
    gender: str,
    birth_utc: datetime,
    birth_civil_year: int,
) -> DayunInfo:
    """現實歷：由年柱陰陽與性別定順逆，按節起運。"""
    forward = is_forward(STEMS.index(year_pillar[0]), gender)
    years = start_age_years_from_birth(birth_utc, forward)
    return DayunInfo(
        forward=forward,
        start_age_years=years,
        start_age_label=format_start_age(years),
        steps=steps_from_month(month_pillar, forward, years, birth_civil_year),
    )


def compute_from_pillars(
    year_pillar: str,
    month_pillar: str,
    gender: str | None,
    start_age_years: float,
    forward: bool | None = None,
    birth_civil_year: int | None = None,
) -> DayunInfo:
    """架空歷：不走節氣。順逆可直接指定；未指定時按年柱陰陽與性別。"""
    if forward is None:
        if gender is None:
            raise ValueError("架空模式須給 forward 或 gender 之一")
        forward = is_forward(STEMS.index(year_pillar[0]), gender)
    return DayunInfo(
        forward=forward,
        start_age_years=start_age_years,
        start_age_label=format_start_age(start_age_years),
        steps=steps_from_month(month_pillar, forward, start_age_years, birth_civil_year),
    )


def current_step(info: DayunInfo, birth_utc: datetime, now_utc: datetime) -> DayunStep | None:
    """所處大運步；未起運或已出序列時 None。週歲按回歸年折算，落在 [start, end)。"""
    age_years = (now_utc.astimezone(timezone.utc) - birth_utc.astimezone(timezone.utc)).days / 365.2425
    for step in info.steps:
        if step.start_age <= age_years < step.end_age:
            return step
    return None


def step_at_age(info: DayunInfo, age: float) -> DayunStep | None:
    """按歲數取所處大運步（架空模式與流年展開用）。"""
    for step in info.steps:
        if step.start_age <= age < step.end_age:
            return step
    return None
