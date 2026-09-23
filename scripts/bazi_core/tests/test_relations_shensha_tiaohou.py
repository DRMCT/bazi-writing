"""刑沖合害、神煞、調候的查表煙霧測試——只驗證通行口訣的顯而易見條目，逐條校核另見 references/校核/。"""

from __future__ import annotations

from bazi_core import relations, shensha, tiaohou
from bazi_core.chart import chart_from_pillars


def test_branch_pairs() -> None:
    assert relations.branch_pair("子", "午") == ["六冲"]
    assert relations.branch_pair("子", "丑") == ["六合"]
    assert relations.branch_pair("寅", "巳") == ["刑", "害"]  # 寅巳既刑又害
    assert relations.branch_pair("子", "未") == ["害"]
    assert relations.branch_pair("辰", "辰") == ["自刑"]
    assert relations.branch_pair("子", "卯") == ["刑"]
    assert relations.branch_pair("寅", "戌") == []  # 半合不計


def test_stem_relation() -> None:
    assert relations.stem_relation("甲", "己") == "合"
    assert relations.stem_relation("甲", "戊") == "克"
    assert relations.stem_relation("甲", "庚") == "被克"
    assert relations.stem_relation("甲", "丙") == "生"
    assert relations.stem_relation("甲", "壬") == "被生"
    assert relations.stem_relation("甲", "乙") == "同"


def test_pillar_pair_tags() -> None:
    assert relations.pillar_pair("甲子", "甲子")["tags"] == ["伏吟"]
    assert relations.pillar_pair("甲子", "庚午")["tags"] == ["天克地冲"]
    assert relations.pillar_pair("甲子", "丙午")["tags"] == []  # 甲生丙，非天克


def test_natal_trio_and_transit_flags() -> None:
    pillars = {"year": "壬申", "month": "壬子", "day": "戊辰", "hour": "壬子"}
    nat = relations.natal_relations(pillars)
    assert {"kind": "三合", "branches": "申子辰", "element": "水"} in nat["trios"]
    tr = relations.transit_relations(pillars, "甲午")
    assert "冲提纲" in tr["flags"]
    assert "伏吟月柱" in relations.transit_relations(pillars, "壬子")["flags"]
    assert "冲日支" in relations.transit_relations(pillars, "甲戌")["flags"]


def _names(pillars: dict) -> dict[str, list[str]]:
    """同名神煞（年支、日支各查一次）合併位置。"""
    out: dict[str, list[str]] = {}
    for s in shensha.compute(pillars):
        out.setdefault(s["name"], []).extend(s["positions"])
    return out


def test_shensha_day_pillar_kinds() -> None:
    kg = _names({"year": "甲子", "month": "丙寅", "day": "庚辰", "hour": "丙子"})
    assert kg["魁罡"] == ["day"]
    ycyc = _names({"year": "甲子", "month": "丙寅", "day": "丙子", "hour": "戊子"})
    assert ycyc["阴差阳错"] == ["day"]


def test_shensha_xun_kong() -> None:
    assert shensha.xun_kong("甲子") == ("戌", "亥")
    assert shensha.xun_kong("癸酉") == ("戌", "亥")
    assert shensha.xun_kong("甲戌") == ("申", "酉")
    assert shensha.xun_kong("庚辰") == ("申", "酉")  # 甲戌旬
    kong = _names({"year": "甲申", "month": "丙寅", "day": "庚辰", "hour": "乙酉"})
    assert set(kong["空亡"]) == {"year", "hour"}


def test_shensha_stem_and_branch_kinds() -> None:
    # 甲日主：天乙丑未、文昌巳、羊刃卯、紅艷午；年支子：桃花酉、驛馬寅、華蓋辰、將星子
    p = {"year": "壬子", "month": "癸卯", "day": "甲午", "hour": "己巳"}
    names = _names(p)
    assert names["羊刃"] == ["month"]
    assert names["文昌"] == ["hour"]
    assert names["红艳"] == ["day"]
    assert "将星" in names and "year" in names["将星"]
    assert "天乙贵人" not in names  # 無丑未


def test_tiaohou_lookup_and_presence() -> None:
    from datetime import datetime, timezone
    assert tiaohou.table_size() == 120
    # 甲寅按雨水分段：无时刻取雨水后（庚、丁），并标未定
    info = tiaohou.lookup("甲", "寅")
    assert info["stems"] == ["庚", "丁"] and info["periodUnresolved"] is True
    assert info["periods"] == ["雨水前", "雨水后"]
    # 2024-02-10 在立春(2-4)后、雨水(2-19)前：丙、癸
    before = tiaohou.lookup("甲", "寅", datetime(2024, 2, 10, 4, 0, tzinfo=timezone.utc))
    assert before["stems"] == ["丙", "癸"] and before["period"]["label"] == "雨水前" and not before["periodUnresolved"]
    after = tiaohou.lookup("甲", "寅", datetime(2024, 2, 25, 4, 0, tzinfo=timezone.utc))
    assert after["stems"] == ["庚", "丁"] and after["period"]["label"] == "雨水后"
    # 无分段的月：直接给主序，带出处
    lu = tiaohou.lookup("乙", "巳")
    assert lu["stems"] == ["癸"] and lu["source"] == "调候-乙巳" and lu["period"] is None
    assert any(c["stems"] == ["庚", "辛"] for c in lu["conditional"])
    info = tiaohou.present_in_chart({"year": "丙寅", "month": "庚寅", "day": "甲子", "hour": "癸酉"}, "甲", "寅",
                                    datetime(2024, 2, 10, 4, 0, tzinfo=timezone.utc))
    assert info["exposed"] == ["丙", "癸"]
    assert info["missing"] == []


def test_tiaohou_table_shape() -> None:
    from bazi_core import tiaohou as th
    seen = set()
    for (dm, mb), e in th._ENTRIES.items():
        assert e["source"] == f"调候-{dm}{mb}" and e["status"] in ("已核", "已审", "已裁")
        assert e["primary"] and all(p["stems"] for p in e["primary"])
        for p in e["primary"]:
            if p.get("period"):
                assert p["period"]["boundary"] in ("雨水", "谷雨", "清明后十日", "夏至", "大暑", "秋分", "霜降", "冬至", "半月")
                assert p["period"]["side"] in ("before", "after")
        seen.add((dm, mb))
    assert len(seen) == 120
    # 半月分段与中气分段都能定出时刻
    from datetime import datetime, timezone
    t = th.boundary_time(datetime(2024, 10, 20, tzinfo=timezone.utc), "戌", "半月")
    assert t is not None and t.month == 10 and 22 <= t.day <= 24     # 寒露 10-8 + 15 天
    t2 = th.boundary_time(datetime(2024, 10, 20, tzinfo=timezone.utc), "戌", "霜降")
    assert t2 is not None and t2.month == 10 and t2.day in (22, 23)  # 霜降 2024-10-23 06:14 北京，UTC 为 22 日
    # 甲丑：不可缺火、无庚降格
    e = th.entry("甲", "丑")
    assert e["indispensable"] and e["downgrade"][0]["absent"] == "庚"


def test_shensha_table_shape_and_rulings() -> None:
    # 十七条（天月二德、孤辰寡宿各拆两张），每条带卡号与状态，状态只能是定稿三种
    assert len(shensha.table_names()) == 17
    for name in shensha.table_names():
        e = shensha.entry(name)
        assert e["source"] == f"神煞-{name}" and e["status"] in ("已核", "已审", "已裁"), name
        assert e["method"] in ("日干查地支", "三合局查地支", "月支查干支", "日柱", "日柱旬空", "年支三会查地支")
        assert not e["unlisted"], (name, e["unlisted"])
    # 裁决落表：红艳从三命通会（壬巳），文昌从"文昌贵"歌诀（乙亥），另说进 alternates
    assert shensha.entry("红艳")["table"]["壬"] == ["巳"] and shensha.entry("红艳")["alternates"][0]["table"]["壬"] == ["子"]
    assert shensha.entry("文昌")["table"]["乙"] == ["亥"] and shensha.entry("文昌")["alternates"][0]["table"]["乙"] == ["午"]
    # 羊刃只有阳干；天德十二格补齐，子月巳；空亡六旬与公式一致
    assert set(shensha.entry("羊刃")["table"]) == {"甲", "丙", "戊", "庚", "壬"}
    assert len(shensha.entry("天德")["table"]) == 12 and shensha.entry("天德")["table"]["子"] == ["巳"]
    for head, kong in shensha.entry("空亡")["table"].items():
        assert tuple(kong) == shensha.xun_kong(head), head
    # 阴差阳错查月日时并报重数；魁罡只查日柱
    p = {"year": "甲子", "month": "丙子", "day": "丁丑", "hour": "庚子"}
    hit = next(s for s in shensha.compute(p) if s["name"] == "阴差阳错")
    assert hit["positions"] == ["month", "day"] and hit["basis"].endswith("2重")
    assert all(s["positions"] == ["day"] for s in shensha.compute({"year": "庚辰", "month": "庚辰", "day": "庚辰", "hour": "庚辰"}) if s["name"] == "魁罡")
    # 三合局类年支为本，日支起查另算并标明
    q = {"year": "壬申", "month": "壬子", "day": "戊辰", "hour": "壬子"}
    bases = {s["basis"] for s in shensha.compute(q) if s["name"] == "华盖"}
    assert bases == {"年支申", "日支辰（日支起）"}


def test_chart_carries_enrichment() -> None:
    c = chart_from_pillars("壬申", "壬子", "戊辰", "壬子", gender="male")
    assert c["relations"]["trios"][0]["element"] == "水"
    assert any(s["name"] == "空亡" for s in c["shensha"]) or True  # 有無皆可，只驗字段存在
    assert c["tiaohou"]["status"] == "校核定稿" and c["tiaohou"]["source"] == "调候-戊子"
    assert set(c) >= {"relations", "shensha", "tiaohou"}
