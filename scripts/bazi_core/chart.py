"""命盤檔案入口：出生時刻或四柱 → 排盤 JSON。

兩種歷法：
- 現實歷 chart_from_civil：公曆鐘表時刻 + 時區 + 經度 → 真太陽時 → 四柱，
  按節起運。口徑與作者自己的排盤項目（bazi.dart / dayun.dart）一致：
  * 日柱、時柱看真太陽時，子初（23:00）換日，晚子時歸次日；
  * 年柱以立春為界，月柱以十二節為界（含修正表），五虎遁定月干；
  * 真太陽時 = 鐘表時 + 經度×4 分 + 時差（EoT）− 時區偏移。
- 架空歷 chart_from_pillars：直接給四柱，不走節氣；起運歲數與順逆由調用方定。

此處只做確定性計算與查表（四柱、十神、藏干、格局、大運）。旺衰、用忌、
調候、神煞、刑沖合害在各自模塊，chart 匯總時按可用性逐步掛上。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from . import dayun as dayun_mod
from . import changsheng as changsheng_mod
from . import geju as geju_mod
from . import shensha_tags as shensha_tags_mod
from . import relations as relations_mod
from . import shensha as shensha_mod
from . import strength as strength_mod
from . import tiaohou as tiaohou_mod
from .almanac import (
    _day_ganzhi_index,
    _month_order_from_yin,
    _year_ganzhi_index,
    equation_of_time_minutes,
    term_time,
)
from .shishen import (
    BRANCHES,
    HIDDEN_STEMS,
    STEMS,
    determine_structure,
    stem_label,
    ten_god,
)

SCHEMA = "bazi-chart/v1"

_PILLAR_KEYS = ("year", "month", "day", "hour")
_PILLAR_CN = {"year": "年", "month": "月", "day": "日", "hour": "时"}
_JIE_NAMES = ("立春", "惊蛰", "清明", "立夏", "芒种", "小暑",
              "立秋", "白露", "寒露", "立冬", "大雪", "小寒")


def _pillar(stem: int, branch: int) -> str:
    return STEMS[stem % 10] + BRANCHES[branch % 12]


# ---------------------------------------------------------------- 四柱

def true_solar_offset_minutes(local_dt: datetime, longitude_deg: float | None) -> float:
    """真太陽時 − 鐘表時（分）。經度缺席時退回時區中央經線，只剩 EoT 一項。"""
    tz_minutes = local_dt.utcoffset().total_seconds() / 60  # type: ignore[union-attr]
    if longitude_deg is None:
        longitude_deg = tz_minutes / 4.0
    local_noon = local_dt.replace(hour=12, minute=0, second=0, microsecond=0)
    eot = equation_of_time_minutes(local_noon.astimezone(timezone.utc))
    return longitude_deg * 4.0 + eot - tz_minutes


def four_pillars(
    local_dt: datetime,
    longitude_deg: float | None = None,
    apply_true_solar: bool = True,
) -> dict:
    """tz-aware 鐘表時刻 → 四柱與相關事實。"""
    if local_dt.tzinfo is None:
        raise ValueError("local_dt 必須帶時區")
    instant_utc = local_dt.astimezone(timezone.utc)
    offset = true_solar_offset_minutes(local_dt, longitude_deg) if apply_true_solar else 0.0
    true_solar = local_dt.replace(tzinfo=None) + timedelta(minutes=offset)

    # 日柱 / 時柱：真太陽時 23:00 起算次日
    gan_day = true_solar.date()
    if true_solar.hour >= 23:
        gan_day = gan_day + timedelta(days=1)
    day_idx = _day_ganzhi_index(gan_day.year, gan_day.month, gan_day.day)
    day_stem, day_branch = day_idx % 10, day_idx % 12
    hour_branch = ((true_solar.hour + 1) // 2) % 12
    zi_stem = (day_stem % 5) * 2 % 10
    hour_stem = (zi_stem + hour_branch) % 10

    # 年柱：立春換年
    lichun = term_time(instant_utc.year, 315)
    year = instant_utc.year
    if lichun is not None and instant_utc < lichun:
        year -= 1
    year_idx = _year_ganzhi_index(year)
    year_stem = year_idx % 10

    # 月柱：十二節定支，五虎遁定干
    order = _month_order_from_yin(instant_utc)
    month_branch = (2 + order) % 12
    yin_stem = ((year_stem % 5) * 2 + 2) % 10
    month_stem = (yin_stem + order) % 10

    # 出生所在節與節後第幾日（節當日為第 1 日）
    jie_time = _latest_jie(instant_utc, order)
    jie_day = None if jie_time is None else int((instant_utc - jie_time).total_seconds() // 86400) + 1

    return {
        "pillars": {
            "year": _pillar(year_stem, year_idx % 12),
            "month": _pillar(month_stem, month_branch),
            "day": _pillar(day_stem, day_branch),
            "hour": _pillar(hour_stem, hour_branch),
        },
        "trueSolarTime": true_solar.strftime("%Y-%m-%d %H:%M:%S"),
        "trueSolarOffsetMinutes": round(offset, 1),
        "instantUtc": instant_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "birthJie": _JIE_NAMES[order],
        "birthJieDay": jie_day,
    }


def _latest_jie(instant_utc: datetime, order: int) -> datetime | None:
    lon = (315.0 + 30.0 * order) % 360.0
    best: datetime | None = None
    for y in (instant_utc.year - 1, instant_utc.year):
        t = term_time(y, lon)
        if t is not None and t <= instant_utc and (best is None or t > best):
            best = t
    return best


# ---------------------------------------------------------------- 十神、藏干、格局

def natal_facts(pillars: dict) -> dict:
    """天干十神、地支藏干（附十神）、格局。日干記「日主」。"""
    ds = STEMS.index(pillars["day"][0])
    stems = {}
    hidden = {}
    for key in _PILLAR_KEYS:
        p = pillars.get(key)
        if not p:
            continue
        s = STEMS.index(p[0])
        b = BRANCHES.index(p[1])
        stems[key] = {
            "stem": stem_label(s),
            "tenGod": "日主" if key == "day" else ten_god(ds, s),
        }
        hidden[key] = [
            {"stem": stem_label(h), "tenGod": ten_god(ds, h), "layer": layer}
            for layer, h in zip(("本气", "中气", "余气"), HIDDEN_STEMS[b])
        ]
    structure = determine_structure(
        pillars["year"], pillars["month"], pillars["day"], pillars.get("hour")
    )
    return {
        "dayMaster": stem_label(ds),
        "stems": stems,
        "hiddenStems": hidden,
        "structure": {"name": structure.name, "base": structure.base, "variation": structure.variation,
                      "also": structure.also or [], "basis": structure.basis},
    }


def _geju(pillars: dict) -> dict:
    """格局条件表加逐盘判定：conditions 是卡上的原文条件，judge 是对本盘的求值（True/False/None）。"""
    s = determine_structure(pillars["year"], pillars["month"], pillars["day"], pillars.get("hour"))
    out = geju_mod.for_chart(s)
    out["judge"] = geju_mod.judge(pillars, s)
    return out


def enrich(pillars: dict, instant_utc: datetime | None = None, gender: str | None = None) -> dict:
    """刑沖合害、神煞、調候：均為查表，狀態隨各模塊標注。調候按出生時刻定節氣段，架空歷無時刻則取中氣後一段。"""
    return {
        "relations": relations_mod.natal_relations(pillars),
        "shensha": shensha_mod.compute(pillars),
        "shenshaTags": shensha_tags_mod.for_chart(pillars, gender),
        "tiaohou": tiaohou_mod.present_in_chart(pillars, pillars["day"][0], pillars["month"][1], instant_utc),
        "strength": strength_mod.assess(pillars),
        "changsheng": changsheng_mod.for_chart(pillars),
        "geju": _geju(pillars),
    }


def features(chart: dict) -> list[dict]:
    """命盘特征索引：把档案里可被人物档案引用的事实摊平成 {id, kind, text}，id 稳定可读，供溯源编号与检查器用。
    编号前缀：P 柱、DM 日主、T 透干、H 藏干、G 格局、S 旺衰、Y 调候、R 关系、N 神煞、NT 神煞标签、C 长生纳音、D 大运、L 流年。"""
    cn = {"year": "年", "month": "月", "day": "日", "hour": "时"}
    out: list[dict] = []

    def add(fid: str, kind: str, text: str) -> None:
        out.append({"id": fid, "kind": kind, "text": text})

    fp = chart["fourPillars"]
    for k in ("year", "month", "day", "hour"):
        if fp.get(k):
            add(f"P-{cn[k]}", "柱", f"{cn[k]}柱{fp[k]}")
    natal = chart["natal"]
    add("DM", "日主", f"日主{natal['dayMaster']}")
    for k, v in natal["stems"].items():
        if k != "day":
            add(f"T-{cn[k]}干-{v['tenGod']}", "透干", f"{cn[k]}干{v['stem']}为{v['tenGod']}")
    for k, items in natal["hiddenStems"].items():
        for h in items:
            add(f"H-{cn[k]}支-{h['layer']}-{h['tenGod']}", "藏干", f"{cn[k]}支{h['layer']}{h['stem']}为{h['tenGod']}")
    st = natal["structure"]
    add(f"G-{st['name']}", "格局", f"取格{st['name']}" + (f"（月令本格{st['base']}，{st['variation']}变格）" if st.get("base") and st["base"] != st["name"] else "") + "：" + st["basis"])
    for a in st.get("also") or []:
        add(f"G-兼-{a}", "格局", f"杂气兼用{a}")
    j = chart.get("geju", {}).get("judge") or {}
    if j.get("verdict"):
        add(f"G-判-{j['verdict']}", "格局判定", f"{j['structure']}{j['verdict']}")
        for kind, key in (("成", "cheng"), ("败", "bai")):
            for c in j.get(key, []):
                if c["holds"]:
                    add(f"G-{kind}-{c['text']}", "格局条件", f"{kind}格条件成立：{c['text']}")
        for x in j.get("jiu", []):
            if x["applies"]:
                add(f"G-救-{x['text']}", "格局救应", f"救应成立：{x['text']}")
        for y in j.get("yun", []):
            if y["holds"]:
                add(f"G-运-{y['scope']}", "取运局", f"取运局「{y['scope']}」：喜{'、'.join(y['favor']) or '无'}；忌{'、'.join(y['avoid']) or '无'}")
    sg = chart["strength"]
    add(f"S-{sg['verdict']}", "旺衰", f"旺衰{sg['verdict']}（比值 {sg['ratio']}，得令{'是' if sg['flags']['得令'] else '否'}、得地{'是' if sg['flags']['得地'] else '否'}、得势{'是' if sg['flags']['得势'] else '否'}）" + (f"，{sg['note']}" if sg.get("note") else ""))
    if sg.get("favorable"):
        add("S-喜", "旺衰", f"喜{'、'.join(sg['favorable'])}，忌{'、'.join(sg['unfavorable'])}")
    for i, c in enumerate(sg.get("combos", []), 1):
        add(f"S-合局-{i}", "合局", c["detail"])
    th = chart["tiaohou"]
    add("Y-主", "调候", f"调候用神{'、'.join(th['stems'])}" + (f"，{th['period']}" if th.get("period") else ""))
    for i, c in enumerate(th.get("conditional", []), 1):
        add(f"Y-条件-{i}", "调候", f"条件用神{'、'.join(c['stems'])}：{c['when']}")
    def _th_text(c) -> str:
        if not isinstance(c, dict):
            return str(c)
        return c.get("text") or c.get("note") or c.get("when") or "、".join(c.get("stems", []))

    for i, c in enumerate(th.get("indispensable", []), 1):
        add(f"Y-不可缺-{i}", "调候", f"不可缺：{_th_text(c)}")
    for i, c in enumerate(th.get("downgrade", []), 1):
        add(f"Y-降格-{i}", "调候", f"降格：{_th_text(c)}")
    for i, c in enumerate(th.get("avoid", []), 1):
        add(f"Y-忌-{i}", "调候", f"忌：{_th_text(c)}")
    for i, c in enumerate(th.get("avoidExceptions", []), 1):
        add(f"Y-忌例外-{i}", "调候", f"忌（例外句）：{_th_text(c)}")
    rel = chart["relations"]
    for pr in rel["pairs"]:
        parts = list(pr["branches"])
        if pr.get("stemHe"):
            parts.append(f"天干合化{pr.get('stemHeElement') or ''}")
        if pr.get("tianKeDiChong"):
            parts.append("天克地冲")
        for part in parts:
            add(f"R-{pr['label']}-{part}", "关系", f"{pr['label']}{part}" + (f"（{pr['xing']}）" if "刑" in part and pr.get("xing") else ""))
    for t in rel.get("trios", []):
        add(f"R-{t['kind']}-{t['branches']}", "关系", f"{t['branches']}{t['kind']}{t['element']}局")
    # 同一神煞可由年支、日支两种起法落在同一柱，合成一条，起法并列写进 text
    bases: dict[tuple[str, str], list[str]] = {}
    for h in chart["shensha"]:
        for p in h["positions"]:
            bases.setdefault((h["name"], p), []).append(h["basis"])
    for (name, p), bs in bases.items():
        add(f"N-{name}-{cn[p]}", "神煞", f"{cn[p]}柱{name}（{'；'.join(bs)}）")
    for t in chart.get("shenshaTags", {}).get("tags", []):
        add(f"NT-{t['id']}-{t['pillar']}", "神煞标签", f"{t['pillar']}柱{t['shensha']}：{t['tag']}" + (f"｜古籍：{t['classic']}" if t.get("classic") else ""))
    cs = chart.get("changsheng", {})
    for k, v in cs.get("dayMasterStage", {}).items():
        add(f"C-{cn[k]}-{v}", "长生", f"日主在{cn[k]}支{v}")
    for k, v in cs.get("nayin", {}).items():
        add(f"C-纳音-{cn[k]}-{v['name']}", "纳音", f"{cn[k]}柱纳音{v['name']}")
    for d in chart["dayun"]["steps"]:
        add(f"D-{d['sequence']}-{d['pillar']}", "大运", f"第{d['sequence']}步大运{d['pillar']}，{d['startAge']}至{d['endAge']}岁" + (f"（{d['startYear']}–{d['endYear']}）" if d.get("startYear") else ""))
    for ln in chart.get("liunian") or []:
        add(f"L-{ln['age']}-{ln['pillar']}", "流年", f"{ln['age']}岁流年{ln['pillar']}")
    dup = sorted({x["id"] for x in out if sum(y["id"] == x["id"] for y in out) > 1})
    if dup:
        raise ValueError(f"features 编号重复：{'、'.join(dup)}")
    return out


# ---------------------------------------------------------------- 入口

def chart_from_civil(
    local_dt: datetime,
    gender: str,
    longitude_deg: float | None = None,
    apply_true_solar: bool = True,
    name: str | None = None,
) -> dict:
    fp = four_pillars(local_dt, longitude_deg, apply_true_solar)
    pillars = fp["pillars"]
    instant_utc = local_dt.astimezone(timezone.utc)
    dy = dayun_mod.compute(pillars["year"], pillars["month"], gender, instant_utc, local_dt.year)
    return {
        "schema": SCHEMA,
        "calendar": {"mode": "real", "birthLocal": local_dt.isoformat(), "longitude": longitude_deg,
                     "trueSolarApplied": apply_true_solar},
        "name": name,
        "gender": gender,
        "fourPillars": pillars,
        "birth": {k: fp[k] for k in ("trueSolarTime", "trueSolarOffsetMinutes", "instantUtc", "birthJie", "birthJieDay")},
        "natal": natal_facts(pillars),
        "dayun": dy.as_payload(),
        **enrich(pillars, instant_utc, gender),
    }


def chart_from_pillars(
    year: str,
    month: str,
    day: str,
    hour: str | None,
    gender: str | None = None,
    start_age_years: float = 3.0,
    forward: bool | None = None,
    story_epoch: int | None = None,
    name: str | None = None,
) -> dict:
    """架空歷。story_epoch 為出生所在的故事紀年（整數），用於換運年份。"""
    for p in (year, month, day) + ((hour,) if hour else ()):
        dayun_mod.sexagenary_index(p)  # 干支陰陽不配即拋錯
    pillars = {"year": year, "month": month, "day": day, "hour": hour}
    dy = dayun_mod.compute_from_pillars(year, month, gender, start_age_years, forward, story_epoch)
    return {
        "schema": SCHEMA,
        "calendar": {"mode": "fictional", "storyEpochBirthYear": story_epoch},
        "name": name,
        "gender": gender,
        "fourPillars": pillars,
        "birth": None,
        "natal": natal_facts(pillars),
        "dayun": dy.as_payload(),
        **enrich(pillars, None, gender),
    }


def liunian(chart: dict, age: int) -> dict:
    """某週歲的流年干支與所處大運（現實歷按立春年份，架空歷按紀年偏移）。"""
    cal = chart["calendar"]
    if cal["mode"] == "real":
        birth_year = datetime.fromisoformat(cal["birthLocal"]).year
        # 出生年立春前生者年柱已減一，流年以年柱為 0 歲起算
        base = dayun_mod.sexagenary_index(chart["fourPillars"]["year"])
        civil_year = birth_year + age
    else:
        base = dayun_mod.sexagenary_index(chart["fourPillars"]["year"])
        civil_year = None if cal["storyEpochBirthYear"] is None else cal["storyEpochBirthYear"] + age
    step = None
    for s in chart["dayun"]["steps"]:
        if s["startAge"] <= age < s["endAge"]:
            step = s
            break
    return {"age": age, "year": civil_year, "pillar": dayun_mod.pillar_name(base + age), "dayun": step}


def _main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="排盤 → 命盤檔案 JSON")
    ap.add_argument("--birth", help="ISO 鐘表時刻，如 1986-05-29T22:30")
    ap.add_argument("--tz", default="Asia/Shanghai")
    ap.add_argument("--lon", type=float, default=None, help="出生地經度（東經為正）")
    ap.add_argument("--no-true-solar", action="store_true")
    ap.add_argument("--pillars", nargs="+", help="架空：年 月 日 [時] 四柱干支")
    ap.add_argument("--start-age", type=float, default=3.0, help="架空：起運歲數")
    ap.add_argument("--forward", choices=["yes", "no"], default=None, help="架空：強制順逆")
    ap.add_argument("--epoch", type=int, default=None, help="架空：出生所在故事紀年")
    ap.add_argument("--gender", choices=["male", "female"], default=None)
    ap.add_argument("--name", default=None)
    ap.add_argument("--age", type=int, nargs="+", default=None, help="附帶某歲流年，可給多個")
    a = ap.parse_args(argv)

    if a.birth:
        if not a.gender:
            ap.error("現實歷須給 --gender")
        local_dt = datetime.fromisoformat(a.birth).replace(tzinfo=ZoneInfo(a.tz))
        chart = chart_from_civil(local_dt, a.gender, a.lon, not a.no_true_solar, a.name)
    elif a.pillars:
        if len(a.pillars) not in (3, 4):
            ap.error("--pillars 需要 3 或 4 個干支")
        hour = a.pillars[3] if len(a.pillars) == 4 else None
        fwd = None if a.forward is None else a.forward == "yes"
        chart = chart_from_pillars(a.pillars[0], a.pillars[1], a.pillars[2], hour,
                                   a.gender, a.start_age, fwd, a.epoch, a.name)
    else:
        ap.error("須給 --birth 或 --pillars")
        return 2
    if a.age:
        chart["liunian"] = [liunian(chart, n) for n in sorted(set(a.age))]
    chart["features"] = features(chart)
    sys.stdout.buffer.write((json.dumps(chart, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
