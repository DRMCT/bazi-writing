"""刑冲合害表、十二长生表、纳音表：表形态（每条带卡号）、三命通会裁决点、与 tyme4py 交叉。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bazi_core import changsheng, relations
from bazi_core.chart import chart_from_pillars

TABLES = Path(__file__).resolve().parent.parent / "tables"
STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"


def test_relations_table_every_entry_has_card() -> None:
    t = json.loads((TABLES / "relations.json").read_text(encoding="utf-8"))
    for key in ("stemHe", "liuHe", "liuChong", "liuHai", "sanHe", "sanHui"):
        assert all(e["source"].startswith("刑冲合害-") and e["status"] for e in t[key]), key
    assert all(e["source"] == "刑冲合害-三刑" for e in t["sanXing"]["directed"] + t["sanXing"]["self"])
    assert set(relations.table_sources()) == {
        "刑冲合害-天干五合", "刑冲合害-六合", "刑冲合害-六冲", "刑冲合害-六害", "刑冲合害-三刑", "刑冲合害-三合", "刑冲合害-三会"}


def test_pair_tables_cover_all_branches() -> None:
    for table in (relations.LIU_HE, relations.LIU_CHONG, relations.HAI):
        assert set(table) == set(BRANCHES) and all(table[table[b]] == b for b in BRANCHES)
    assert set(relations.STEM_HE) == set(STEMS)


def test_sanxing_direction_follows_sanming_tonghui() -> None:
    # 上130：申刑寅，子刑卯；寅刑巳，戌刑未；巳刑申，丑刑戌；卯刑子，未刑丑；辰午酉亥自刑
    assert relations.xing_direction("寅", "巳") == "寅刑巳"
    assert relations.xing_direction("巳", "寅") == "寅刑巳"
    assert relations.xing_direction("申", "寅") == "申刑寅"
    assert relations.xing_direction("戌", "未") == "戌刑未"
    assert relations.xing_direction("未", "丑") == "未刑丑"
    assert relations.xing_direction("子", "卯") == "子卯互刑"
    assert relations.xing_direction("辰", "辰") == "辰辰自刑"
    assert relations.xing_direction("寅", "亥") is None
    assert relations.XING_KIND["寅巳"] == "无恩" and relations.XING_KIND["丑戌"] == "恃势" and relations.XING_KIND["子卯"] == "无礼"
    assert set(relations.ZI_XING) == set("辰午酉亥")


def test_sanhe_has_earth_when_four_vaults_present() -> None:
    assert relations.SAN_HE == {"申子辰": "水", "寅午戌": "火", "巳酉丑": "金", "亥卯未": "木"}
    assert relations.SI_KU["branches"] == "辰戌丑未" and relations.SI_KU["element"] == "土"
    r = relations.natal_relations({"year": "甲辰", "month": "丙戌", "day": "戊丑", "hour": "己未"})
    assert any(t["kind"] == "四库全" and t["element"] == "土" for t in r["trios"])


def test_natal_pairs_carry_direction_and_elements() -> None:
    r = relations.natal_relations({"year": "甲寅", "month": "己巳", "day": "壬申", "hour": "丁未"})
    by = {p["label"]: p for p in r["pairs"]}
    assert by["年月"]["xing"] == "寅刑巳" and by["年月"]["stemHe"] and by["年月"]["stemHeElement"] == "土"
    assert by["月日"]["xing"] == "巳刑申" and "六合" in by["月日"]["branches"] and by["月日"]["liuHeElement"] == "水"
    assert by["年日"]["xing"] == "申刑寅" and "六冲" in by["年日"]["branches"]
    assert by["日时"]["stemHe"] and by["日时"]["stemHeElement"] == "木"


def test_changsheng_table_shape_and_rule() -> None:
    t = json.loads((TABLES / "changsheng.json").read_text(encoding="utf-8"))
    assert t["stages"] == ["长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养"]
    assert set(t["table"]) == set(STEMS) and all(set(t["table"][s]) == set(BRANCHES) for s in STEMS)
    for s in STEMS:
        assert sorted(t["table"][s].values()) == sorted(t["stages"]), s
    assert set(t["cards"]) == {"长生-十干长生位", "长生-十二宫序"}
    # 阳生阴死、火土同宫
    assert changsheng.birth_branch("甲") == "亥" and changsheng.birth_branch("乙") == "午"
    assert changsheng.birth_branch("戊") == "寅" and changsheng.birth_branch("己") == "酉"
    assert changsheng.stage("甲", "寅") == "临官" and changsheng.stage("甲", "卯") == "帝旺" and changsheng.stage("甲", "未") == "墓"
    assert changsheng.stage("乙", "亥") == "死" and changsheng.stage("癸", "卯") == "长生"


def test_nayin_table_shape() -> None:
    t = json.loads((TABLES / "nayin.json").read_text(encoding="utf-8"))
    assert len(t["entries"]) == 60 and t["card"] == "纳音-六十甲子"
    assert changsheng.nayin("甲子") == {"name": "海中金", "element": "金"}
    assert changsheng.nayin("乙丑")["name"] == "海中金"
    assert changsheng.nayin("戊午") == {"name": "天上火", "element": "火"}
    assert changsheng.nayin("壬戌")["name"] == "大海水"
    names = {e["name"] for e in t["entries"].values()}
    assert len(names) == 30


def test_chart_carries_changsheng() -> None:
    c = chart_from_pillars("丙寅", "癸巳", "癸酉", "癸亥", gender="male")
    cs = c["changsheng"]
    assert cs["nayin"]["year"]["name"] == "炉中火"
    assert cs["dayMasterStage"]["day"] == "病" and cs["dayMasterStage"]["hour"] == "帝旺"
    assert cs["selfStage"]["year"] == "长生"
    assert "changsheng" in cs["source"] and "nayin" in cs["source"]


def test_cross_check_with_tyme4py() -> None:
    tyme = pytest.importorskip("tyme4py.sixtycycle")
    for s in STEMS:
        for b in BRANCHES:
            t = tyme.HeavenStem.from_name(s).get_terrain(tyme.EarthBranch.from_name(b)).get_name()
            assert changsheng.stage(s, b) == t, (s, b)
    for i in range(60):
        sc = tyme.SixtyCycle.from_index(i)
        assert changsheng.nayin(sc.get_name())["element"] == sc.get_sound().get_name()[-1]
    for b in BRANCHES:
        eb = tyme.EarthBranch.from_name(b)
        assert relations.LIU_HE[b] == eb.get_combine().get_name()
        assert relations.LIU_CHONG[b] == eb.get_opposite().get_name()
        assert relations.HAI[b] == eb.get_harm().get_name()
    for s in STEMS:
        assert relations.STEM_HE[s] == tyme.HeavenStem.from_name(s).get_combine().get_name()
