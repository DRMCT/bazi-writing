"""服務端流日干支計算 —— 訂閱報告生成用。

單次獲取時流日語境由客戶端算好上送；訂閱報告由服務端定時生成，須在
服務端復刻同一口徑：**北京真太陽時正午取年/月/日柱**（對齊客戶端
lib/features/explore/day_pillars.dart 與 lib/core/bazi.dart）。

公式與客戶端 lib/core/astronomy.dart 完全同源（方宜 almanac_compute.py
亦同一套）：低階太陽黃經近似 + 時差（equation of time）。節氣時刻另加
修正表（jieqi_corrections.py，生成見客戶端 tool/gen_jieqi_corrections.py）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

from .jieqi_corrections import correction_seconds

STEMS = list("甲乙丙丁戊己庚辛壬癸")
BRANCHES = list("子丑寅卯辰巳午未申酉戌亥")

# 北京口徑：Asia/Shanghai 固定 UTC+8，經度 116.4074°E
_BEIJING_TZ_MINUTES = 8 * 60
_BEIJING_LONGITUDE = 116.4074

TERMS_BY_LONGITUDE: list[tuple[str, float]] = [
    ("春分", 0), ("清明", 15), ("谷雨", 30), ("立夏", 45), ("小满", 60),
    ("芒种", 75), ("夏至", 90), ("小暑", 105), ("大暑", 120), ("立秋", 135),
    ("处暑", 150), ("白露", 165), ("秋分", 180), ("寒露", 195), ("霜降", 210),
    ("立冬", 225), ("小雪", 240), ("大雪", 255), ("冬至", 270), ("小寒", 285),
    ("大寒", 300), ("立春", 315), ("雨水", 330), ("惊蛰", 345),
]


# ---------------------------------------------------------------- 天文基礎

def _julian_day(utc: datetime) -> float:
    t = utc.astimezone(timezone.utc)
    year, month = t.year, t.month
    day = (
        t.day
        + (t.hour + (t.minute + (t.second + t.microsecond / 1e6) / 60) / 60) / 24
    )
    if month <= 2:
        year -= 1
        month += 12
    a = year // 100
    b = 2 - a + a // 4
    return int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + b - 1524.5


def _days_since_j2000(utc: datetime) -> float:
    return _julian_day(utc) - 2451545.0


def _norm360(deg: float) -> float:
    r = deg % 360.0
    return r + 360.0 if r < 0 else r


def _norm180(deg: float) -> float:
    r = _norm360(deg)
    return r - 360.0 if r > 180.0 else r


def solar_longitude(utc: datetime) -> float:
    d = _days_since_j2000(utc)
    mean_long = _norm360(280.460 + 0.9856474 * d)
    mean_anom = math.radians(_norm360(357.528 + 0.9856003 * d))
    return _norm360(
        mean_long + 1.915 * math.sin(mean_anom) + 0.020 * math.sin(2 * mean_anom)
    )


def equation_of_time_minutes(utc: datetime) -> float:
    """時差（真太陽時 − 平太陽時），分鐘。與客戶端 astronomy.dart 同式。"""
    d = _days_since_j2000(utc)
    mean_long = _norm360(280.460 + 0.9856474 * d)
    mean_anom = math.radians(_norm360(357.528 + 0.9856003 * d))
    lam = math.radians(
        mean_long + 1.915 * math.sin(mean_anom) + 0.020 * math.sin(2 * mean_anom)
    )
    obliquity = math.radians(23.439 - 0.0000004 * d)
    ra = math.degrees(
        math.atan2(math.cos(obliquity) * math.sin(lam), math.cos(lam))
    )
    return 4.0 * _norm180(mean_long - _norm360(ra))


def _delta(utc: datetime, target: float) -> float:
    diff = (solar_longitude(utc) - target) % 360.0
    return diff - 360.0 if diff > 180.0 else diff


def _bisect(lo: datetime, hi: datetime, target: float) -> datetime:
    for _ in range(42):
        mid = lo + timedelta(seconds=(hi - lo).total_seconds() / 2)
        if _delta(mid, target) < 0:
            lo = mid
        else:
            hi = mid
    return lo + timedelta(seconds=(hi - lo).total_seconds() / 2)


@lru_cache(maxsize=512)
def term_time(year: int, target_longitude: float) -> datetime | None:
    """Meeus 低精度解 + 修正表（1900–2100，DE440s 口徑）；範圍外退回裸 Meeus。

    純函數但不便宜（逐日掃描 + 42 輪二分）。一天的流日語境要問它 97 次
    （立春 1、月柱 24、節氣 72），訂閱逐台生成時同一組參數反覆問到，故按
    (year, longitude) 緩存；datetime 不可變，共用結果無妨。512 項約合
    21 年 × 24 節氣，遠超實際訪問窗口（前後各一年）。同方宜 almanac_compute。
    """
    cursor = datetime(year, 1, 1, tzinfo=timezone.utc)
    prev = _delta(cursor, target_longitude)
    for _ in range(366):
        nxt = cursor + timedelta(days=1)
        cur = _delta(nxt, target_longitude)
        if prev < 0 <= cur:
            meeus = _bisect(cursor, nxt, target_longitude)
            corr = correction_seconds(year, target_longitude)
            return meeus if corr is None else meeus + timedelta(seconds=corr)
        cursor, prev = nxt, cur
    return None


def current_term(instant: datetime) -> str:
    """instant 所處節氣名（最近一個已交的節氣）。"""
    now = instant.astimezone(timezone.utc)
    latest: tuple[str, datetime] | None = None
    for year in (now.year - 1, now.year, now.year + 1):
        for name, lon in TERMS_BY_LONGITUDE:
            t = term_time(year, lon)
            if t is not None and t <= now:
                if latest is None or t > latest[1]:
                    latest = (name, t)
    return latest[0] if latest else ""


# ---------------------------------------------------------------- 干支

def _day_ganzhi_index(y: int, m: int, d: int) -> int:
    """60 甲子序（0 = 甲子）。與客戶端同校準：2000-01-01 = 戊午（54）。"""
    jdn = math.floor(_julian_day(datetime(y, m, d, 12, tzinfo=timezone.utc)))
    return ((jdn - 11) % 60 + 60) % 60


def _year_ganzhi_index(year: int) -> int:
    return ((year - 1984) % 60 + 60) % 60


def _pillar_name(stem: int, branch: int) -> str:
    return STEMS[stem] + BRANCHES[branch]


@dataclass(frozen=True)
class DayContext:
    civil_date: str
    year_pillar: str
    month_pillar: str
    day_pillar: str
    solar_term: str

    def as_payload(self) -> dict:
        return {
            "civilDate": self.civil_date,
            "yearPillar": self.year_pillar,
            "monthPillar": self.month_pillar,
            "dayPillar": self.day_pillar,
            "solarTermContext": self.solar_term,
        }


def _month_order_from_yin(instant_utc: datetime) -> int:
    """instant 距最近已交之節的月序（0 = 立春起寅月）。

    以 term_time（含修正表）定界；理論上必有結果，兜底退回裸黃經分桶。
    """
    latest: datetime | None = None
    latest_order = None
    for y in (instant_utc.year - 1, instant_utc.year):
        for k in range(12):
            t = term_time(y, (315.0 + 30.0 * k) % 360.0)
            if t is not None and t <= instant_utc and (latest is None or t > latest):
                latest, latest_order = t, k
    if latest_order is not None:
        return latest_order
    shift = ((solar_longitude(instant_utc) - 315.0) % 360.0 + 360.0) % 360.0
    return int(shift // 30.0)


def beijing_day_context(civil_date: str) -> DayContext:
    """目標公曆日（YYYY-MM-DD）的流年/流月/流日干支 + 節氣，北京真太陽時正午口徑。"""
    target = date.fromisoformat(civil_date)

    # 真太陽時正午對應的民用鐘：12:00 − offset；offset = 經度修正 + 時差 − 時區
    approx_noon_utc = datetime(
        target.year, target.month, target.day, 12, tzinfo=timezone.utc
    ) - timedelta(minutes=_BEIJING_TZ_MINUTES)
    offset_minutes = (
        _BEIJING_LONGITUDE * 4.0
        + equation_of_time_minutes(approx_noon_utc)
        - _BEIJING_TZ_MINUTES
    )
    instant_utc = approx_noon_utc - timedelta(minutes=offset_minutes)

    # 日柱：真太陽時正午恆在 23:00 前，無子時換日
    day_idx = _day_ganzhi_index(target.year, target.month, target.day)
    day_pillar = _pillar_name(day_idx % 10, day_idx % 12)

    # 年柱：立春（315°）換年
    lichun = term_time(target.year, 315)
    year = target.year
    if lichun is not None and instant_utc < lichun:
        year -= 1
    year_idx = _year_ganzhi_index(year)
    year_stem = year_idx % 10
    year_pillar = _pillar_name(year_stem, year_idx % 12)

    # 月柱：十二節（立春 315° 起每 30°）定支，五虎遁定干。
    # 以 term_time（含修正表）節時刻定界，與客戶端 bazi.dart 同口徑。
    order_from_yin = _month_order_from_yin(instant_utc)
    branch = (2 + order_from_yin) % 12
    yin_stem = ((year_stem % 5) * 2 + 2) % 10
    month_pillar = _pillar_name((yin_stem + order_from_yin) % 10, branch)

    return DayContext(
        civil_date=civil_date,
        year_pillar=year_pillar,
        month_pillar=month_pillar,
        day_pillar=day_pillar,
        solar_term=current_term(instant_utc),
    )


def shichen_hours(
    civil_date: str,
    tz_name: str,
    longitude_deg: float | None,
) -> list[dict]:
    """目標日十二時辰干支＋當地鐘表起訖，真太陽時校準（訂閱重放用）。

    口徑與客戶端 DailySolarTime / FourPillars.compute 對齊（方宜
    flow_qi_compute.py 同式）：
    - 鐘表偏移 = 經度×4 + 時差(EoT) − 時區偏移，按目標日正午取值，全日視為常數；
    - 時柱五鼠遁自流日日柱（北京黃曆口徑，與 beijing_day_context 一致）；
    - [longitude_deg] 缺席時退回時區中央經線（此時偏移只剩 EoT 的日內小量）。
    """
    target = date.fromisoformat(civil_date)
    tz = ZoneInfo(tz_name)
    local_noon = datetime(target.year, target.month, target.day, 12, tzinfo=tz)
    tz_minutes = local_noon.utcoffset().total_seconds() / 60
    if longitude_deg is None:
        longitude_deg = tz_minutes / 4.0  # 時區中央經線：15°/小時
    eot = equation_of_time_minutes(local_noon.astimezone(timezone.utc))
    offset_minutes = longitude_deg * 4.0 + eot - tz_minutes

    day_idx = _day_ganzhi_index(target.year, target.month, target.day)
    zi_stem = (day_idx % 10 % 5) * 2 % 10

    result: list[dict] = []
    for branch in range(12):
        # 子時起於真太陽時 23:00，逐支 +2h；換回鐘表時間即減偏移
        true_solar_start = datetime(
            target.year, target.month, target.day, (2 * branch + 23) % 24
        ) - timedelta(minutes=offset_minutes)
        end_hour = (true_solar_start.hour + 2) % 24
        result.append(
            {
                "pillar": _pillar_name((zi_stem + branch) % 10, branch),
                "start": f"{true_solar_start.hour:02d}:{true_solar_start.minute:02d}",
                "end": f"{end_hour:02d}:{true_solar_start.minute:02d}",
            }
        )
    return result
