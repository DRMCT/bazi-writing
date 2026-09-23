"""十神／取格金樣例——與客戶端 test/shishen_test.dart 一一對應，兩邊同改。"""

from __future__ import annotations

import pytest

from bazi_core.shishen import determine_structure, ten_god, ten_god_lines


def test_ten_god_xin_day_master() -> None:
    xin = 7
    assert ten_god(xin, 7) == "比肩"
    assert ten_god(xin, 6) == "劫财"
    assert ten_god(xin, 9) == "食神"
    assert ten_god(xin, 8) == "伤官"
    assert ten_god(xin, 1) == "偏财"
    assert ten_god(xin, 0) == "正财"
    assert ten_god(xin, 3) == "七杀"
    assert ten_god(xin, 2) == "正官"
    assert ten_god(xin, 5) == "偏印"
    assert ten_god(xin, 4) == "正印"


@pytest.mark.parametrize(
    "pillars, expected",
    [
        # 命主：卯藏乙偏財不透，取本氣
        (("丁丑", "癸卯", "辛酉", "己丑"), "偏财格"),
        (("丁丑", "癸卯", "辛酉", None), "偏财格"),
        # 亥卯未會木局、乙透
        (("己卯", "乙亥", "己丑", "辛未"), "七杀格"),
        (("己卯", "乙亥", "己丑", None), "正财格"),
        # 真詮：丁生亥月，支全卯未，化為印
        (("癸卯", "辛亥", "丁未", "庚子"), "偏印格"),
        # 真詮：己生申月，藏庚透壬，化為財
        (("壬子", "戊申", "己卯", "乙丑"), "正财格"),
        # 本氣中氣皆透，本氣優先
        (("壬子", "庚申", "甲寅", "丙寅"), "七杀格"),
        # 透於時干
        (("丙子", "庚寅", "戊辰", "甲寅"), "七杀格"),
        # 建祿
        (("丙子", "庚寅", "甲辰", "乙丑"), "建禄格"),
        (("丙子", "癸巳", "戊辰", "乙卯"), "建禄格"),
        (("丙子", "甲子", "癸卯", "乙卯"), "建禄格"),
        # 月刃
        (("丙子", "丁酉", "庚辰", "乙丑"), "月刃格"),
        (("丙子", "甲午", "戊辰", "乙卯"), "月刃格"),
        (("丙子", "庚子", "壬辰", "乙巳"), "月刃格"),
        # 月劫
        (("丙子", "庚寅", "乙丑", "丁丑"), "月劫格"),
        (("丙子", "丙申", "辛丑", "己丑"), "月劫格"),
        (("丙子", "癸巳", "丁丑", "庚子"), "月劫格"),
        # 三會方
        (("甲寅", "戊辰", "庚子", "己卯"), "偏财格"),
        (("丙寅", "壬辰", "庚子", "己卯"), "正财格"),
        # 會局與日主同氣不改格
        (("己卯", "乙亥", "甲子", "辛未"), "偏印格"),
        # 祿刃先於會局
        (("丙午", "庚寅", "甲戌", "丙寅"), "建禄格"),
        # 藏干比劫不作候選；雜氣按五行認透干，丑本氣己土，戊透即以土論（正印）
        (("辛未", "乙丑", "辛卯", "戊子"), "正印格"),
        (("辛未", "乙丑", "辛卯", "丙子"), "偏印格"),
    ],
)
def test_structure_golden(pillars, expected) -> None:
    assert determine_structure(*pillars).name == expected


def test_structure_layers() -> None:
    # 月令本格与变格：多数相同；专气与杂气无藏透变格
    s = determine_structure("丁丑", "癸卯", "辛酉", "己丑")
    assert (s.name, s.base, s.variation, s.also) == ("偏财格", "偏财格", None, [])
    # 杂气按五行认透干、兼透兼用：辰为水库，壬亦算印；本气戊透则当旺者先，壬印为兼用
    s = determine_structure("壬寅", "戊辰", "甲子", "丙寅")
    assert (s.name, s.also) == ("偏财格", ["偏印格"])
    # 杂气本气为比劫不立格，余气透干取之（论正官首例：戊生未月杂气正官，丁乙并透，官先于印）
    s = determine_structure("壬戌", "丁未", "戊申", "乙卯")
    assert (s.name, s.base, s.also) == ("正官格", "正官格", ["正印格"])
    # 杂气皆不透而本气为比劫：月劫格
    assert determine_structure("丙寅", "乙丑", "己巳", "甲子").name == "月劫格"
    # 生地本气不透而中气透：本格从当旺之神，变格取透者
    s = determine_structure("甲申", "壬申", "乙巳", "戊寅")
    assert (s.name, s.base, s.variation) == ("正印格", "正官格", "藏透")
    # 生地本气与中气并透：当旺者先，不算变格
    s = determine_structure("甲寅", "戊寅", "壬申", "丙午")
    assert (s.name, s.base, s.variation) == ("食神格", "食神格", None)


def test_structure_basis_wording() -> None:
    s = determine_structure("丁丑", "癸卯", "辛酉", "己丑")
    assert s.basis == "月令卯藏乙木未透干，依本气乙木取偏财格"

    s = determine_structure("己卯", "乙亥", "己丑", "辛未")
    assert (s.name, s.base, s.variation) == ("七杀格", "正财格", "会局")
    assert s.basis == "月令亥本气壬水为正财当旺，未透干仍以当旺之神取正财格；月支亥与卯未三合成木局，乙木透于月干为七杀，随局变格取七杀格"

    s = determine_structure("壬子", "戊申", "己卯", "乙丑")
    assert (s.name, s.base, s.variation) == ("正财格", "伤官格", "藏透")
    assert s.basis == "月令申本气庚金为伤官当旺，未透干仍以当旺之神取伤官格；本气不透而中气壬水透于年干为正财，舍本气而用透者，变格取正财格"

    s = determine_structure("丙子", "癸巳", "戊辰", "乙卯")
    assert s.basis == "月支巳为日主戊土禄位，取建禄格"


def test_ten_god_lines() -> None:
    lines = ten_god_lines("丁丑", "癸卯", "辛酉", "己丑")
    assert lines[0] == "天干十神：年干丁火七杀，月干癸水食神，日干辛金日主，时干己土偏印"
    assert lines[1].startswith("地支藏干（附对日主十神）：年支丑藏己土偏印、癸水食神、辛金比肩；月支卯藏乙木偏财")
    assert "时支丑藏" in lines[1]

    no_hour = ten_god_lines("丁丑", "癸卯", "辛酉", None)
    assert "时干" not in no_hour[0]
    assert "时支" not in no_hour[1]
