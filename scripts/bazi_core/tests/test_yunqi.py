"""五运六气（yunqi 模块，DESIGN-命盘层 3.1、DESIGN-人物层 1）。

- 六十年年关系对手录夹具 fixtures/wuyun_relations_60.json（天符 12、岁会 8、兼 4、同天符 6、同岁会 6、平气 15、客主加临、君臣）；
- 现实历：交气按大寒起每 60°，运气年以大寒为岁首，大寒到立春之间生的人运气年干支与年柱不同；
- 架空历：整月在一步内的月支直接定，跨中气的月默认取中气后一段并标未定，丑月默认不翻年，作者可指定；
- 命盘 yunqi 节与 YQ- 编号进 features，与体质表的行对得上，表的锚点都有卡，机器表每条带卡号。
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from bazi_core import chart, yunqi

ROOT = Path(__file__).resolve().parents[3]
FX = json.loads((Path(__file__).parent / "fixtures" / "wuyun_relations_60.json").read_text(encoding="utf-8"))
STEMS, BRANCHES = "甲乙丙丁戊己庚辛壬癸", "子丑寅卯辰巳午未申酉戌亥"
ALL = [STEMS[i % 10] + BRANCHES[i % 12] for i in range(60)]


def _card_ids() -> set[str]:
    ids: set[str] = set()
    for f in (ROOT / "references" / "校核").glob("*.md"):
        ids.update(re.findall(r"(?m)^### (\S+-\S+)", f.read_text(encoding="utf-8")))
    return ids


def test_year_relations_match_hand_recorded_fixture() -> None:
    pats = {gz: yunqi.year_pattern(gz) for gz in ALL}
    for name, key in (("tian_fu", "tianFu"), ("sui_hui", "suiHui"), ("tian_fu_and_sui_hui", "tianFuSuiHui"),
                      ("tong_tian_fu", "tongTianFu"), ("tong_sui_hui", "tongSuiHui")):
        assert sorted(gz for gz, p in pats.items() if p[key]) == sorted(FX[name]), name
    for rule, years in FX["ping_qi"].items():
        assert sorted(gz for gz, p in pats.items() if p["pingQi"] == rule) == sorted(years), rule
    for gz, rel in FX["yun_vs_sitian"].items():
        assert pats[gz]["yunVsSiTian"] == rel, gz
    for gz, rel in FX["yun_vs_zaiquan"].items():
        assert pats[gz]["yunVsZaiQuan"] == rel, gz
    # 运与在泉同气的年份恰是同天符加同岁会十二年
    assert sorted(gz for gz, p in pats.items() if p["yunVsZaiQuan"] == "同") == sorted(FX["tong_tian_fu"] + FX["tong_sui_hui"])
    for gz, k, rel in FX["yun_vs_step"]:
        p = pats[gz]
        assert yunqi.yun_vs_step(p["yunElement"], yunqi.GUEST_QI[p["group"]][k], p["siTian"], p["zaiQuan"]) == rel, (gz, k)
    # 气交变"上临"五对：恰这十二年带出 YQ-上临，其余不带
    got = {}
    for gz in ALL:
        y = yunqi.for_chart({"year": gz, "month": "壬申"}, None)
        sl = [f["id"] for f in y["features"] if f["id"].startswith("YQ-上临-")]
        if sl:
            got[gz] = sl[0].split("-", 2)[2]
    assert got == FX["shang_lin"]
    for grp, rels in FX["steps"].items():
        assert [yunqi.step_relation(yunqi.HOST_QI[k], yunqi.GUEST_QI[grp][k])["relation"] for k in range(6)] == rels, grp
    for jc, places in FX["jun_chen"].items():
        for grp, k in places:
            assert yunqi.step_relation(yunqi.HOST_QI[k], yunqi.GUEST_QI[grp][k])["junChen"] == jc
    # 二火以外不论君臣；干支阴阳不配报错
    assert yunqi.step_relation("厥阴风木", "太阳寒水")["junChen"] is None
    with pytest.raises(ValueError):
        yunqi.year_pattern("甲丑")


def test_real_calendar_steps_and_yunqi_year_boundary() -> None:
    tz = ZoneInfo("Asia/Shanghai")
    # 1986-05-29 小满后大暑前：三之气；丙寅年水运太过、少阳相火司天、厥阴风木在泉；客气少阳相火与主气同气
    c = chart.chart_from_civil(datetime(1986, 5, 29, 22, 30, tzinfo=tz), "male", 116.4, True)
    y = c["yunqi"]
    assert y["yearPillar"] == "丙寅" and not y["yunqiYearDiffers"]
    assert y["suiYun"] == "水运太过" and y["siTian"] == "少阳相火" and y["zaiQuan"] == "厥阴风木"
    assert y["step"]["label"] == "三之气" and y["step"]["host"] == y["step"]["guest"] == "少阳相火"
    assert y["stepRelation"]["relation"] == "同气" and y["step"]["half"] == "司天" and y["step"]["governing"] == "少阳相火"
    assert y["relations"]["yunVsSiTian"] == "运克天" and y["relations"]["pingQi"] is None
    assert not y["step"]["unresolved"] and y["step"]["by"] == "出生时刻"
    # 1986-01-25 大寒后立春前：年柱乙丑、运气年丙寅初之气
    c = chart.chart_from_civil(datetime(1986, 1, 25, 10, 0, tzinfo=tz), "female", 116.4, True)
    assert c["fourPillars"]["year"] == "乙丑"
    assert c["yunqi"]["yearPillar"] == "丙寅" and c["yunqi"]["yunqiYearDiffers"] and c["yunqi"]["step"]["label"] == "初之气"
    # 1986-01-19 大寒前：仍是乙丑年终之气
    assert yunqi.step_from_instant(datetime(1986, 1, 19, 10, 0, tzinfo=tz)) == {"yunqiYear": 1985, "index": 5, "unresolved": False, "by": "出生时刻"}


def test_fictional_step_from_month_branch_and_override() -> None:
    assert yunqi.step_from_month("寅") == {"index": 0, "unresolved": False, "by": "月支", "nextYear": False}
    for mb, k in (("辰", 1), ("午", 2), ("申", 3), ("戌", 4), ("子", 5)):
        assert yunqi.step_from_month(mb)["index"] == k and not yunqi.step_from_month(mb)["unresolved"]
    r = yunqi.step_from_month("卯")
    assert r["index"] == 1 and r["unresolved"] and "春分" in r["note"]
    r = yunqi.step_from_month("丑")
    assert r["index"] == 5 and r["unresolved"] and not r["nextYear"] and "不翻年" in r["note"]
    assert yunqi.step_from_month("丑", "次年初之气") == {"index": 0, "unresolved": False, "by": "作者指定", "nextYear": True}
    assert yunqi.step_from_month("卯", 3)["index"] == 2 and yunqi.step_from_month("卯", "五之气")["index"] == 4
    for bad in (0, 7, "八之气"):
        with pytest.raises(ValueError):
            yunqi.step_from_month("卯", bad)
    # 丑月指定翻年：运气年干支加一
    c = chart.chart_from_pillars("庚寅", "己丑", "辛酉", "戊戌", "female", 5.0, None, 306, None, None, "次年初之气")
    assert c["yunqi"]["yearPillar"] == "辛卯" and c["yunqi"]["yunqiYearDiffers"] and c["yunqi"]["step"]["by"] == "作者指定"
    assert c["yunqi"]["siTian"] == "阳明燥金"


def test_sample_chart_section_and_features() -> None:
    c = chart.chart_from_pillars("甲申", "壬申", "乙巳", "戊寅", "male", story_epoch=300, name="沈砚")
    y = c["yunqi"]
    assert y["suiYun"] == "土运太过" and y["siTian"] == "少阳相火" and y["zaiQuan"] == "厥阴风木" and y["group"] == "寅申"
    assert y["step"] == {"index": 3, "label": "四之气", "host": "太阴湿土", "guest": "阳明燥金", "by": "月支", "unresolved": False,
                         "half": "在泉", "governing": "厥阴风木"}
    assert y["stepRelation"]["relation"] == "主生客" and y["relations"]["yunVsSiTian"] == "天生运"
    assert y["relations"]["yunVsZaiQuan"] == "泉克运" and y["relations"]["yunVsStep"] == "运生气"
    ids = [f["id"] for f in y["features"]]
    # 主次：年主干 → 运为体 → 纲气为主 → 当步为用 → 修正为改写（运与纲、运与当步、加临）→ 另一头作背景（运与另一头、另一头本身）（DESIGN-命盘层 4 交感）
    assert ids == ["YQ-年-甲申", "YQ-岁运-土运太过", "YQ-在泉-厥阴风木", "YQ-气-四之气-阳明燥金", "YQ-运泉-泉克运", "YQ-运步-运生气", "YQ-加临-主生客",
                   "YQ-运天-天生运", "YQ-司天-少阳相火", "YQ-档-显", "YQ-病-肾", "YQ-志-郁"]
    assert y["roles"] == {"主干": ["YQ-年-甲申"], "体": ["YQ-岁运-土运太过"], "主": ["YQ-在泉-厥阴风木"], "用": ["YQ-气-四之气-阳明燥金"],
                          "改写": ["YQ-运泉-泉克运", "YQ-运步-运生气", "YQ-加临-主生客"], "背景": ["YQ-运天-天生运", "YQ-司天-少阳相火"],
                          "事件": ["YQ-档-显", "YQ-病-肾", "YQ-志-郁"]}
    assert [h["role"] for h in y["hits"]] == ["主干", "体", "主", "用", "改写", "改写", "改写", "背景", "背景", "事件", "事件", "事件"]
    # 画像层文本不带民病（据卡的民病只留在事件层与 row 里）
    portrait = " ".join(f["text"] for f in y["features"] if not f["id"].startswith(("YQ-档-", "YQ-病-", "YQ-志-", "YQ-上临-")))
    for w in ("腹痛", "肌肉萎", "四支不举", "心痛支满", "两胁里急", "身重"):
        assert w not in portrait, w
    # 事件层：档、薄弱脏、情志方向，默认不写
    ev = y["events"]
    assert ev["grade"] == "显" and "泉克运" in ev["gradeWhy"] and ev["tempo"].startswith("太过者暴")
    assert ev["organ"] == "肾" and ev["organElement"] == "水" and ev["zhi"] == "郁" and "意不乐" in ev["zhiFrom"]
    assert "太溪绝者死不治" in ev["illness"]["fatal"] and ev["shangLin"] is None and ev["ids"] == ["YQ-档-显", "YQ-病-肾", "YQ-志-郁"]
    # 主干：甲申归甲寅甲申一对，据卡栏来自六十年纪与少阳之政
    assert y["pair"] == "甲寅甲申"
    trunk = y["hits"][0]["row"]
    assert trunk["shang"] == "少阳相火" and trunk["zhong"] == "太宫土运" and trunk["xia"] == "厥阴风木"
    assert trunk["huaShu"] == "火化二，雨化五，风化八" and trunk["zhengHua"] == "正化日" and "其病体重肘肿痞饮" in trunk["zheng"]
    assert "上少阳相火、中太宫土运、下厥阴风木" in y["features"][0]["text"]
    gov = {h["id"]: h.get("governing") for h in y["hits"]}
    assert gov["YQ-运泉-泉克运"] is True and gov["YQ-运天-天生运"] is False
    # 命中的行与表对得上，且进 features 不重复
    rows = {h["id"]: h.get("row") for h in y["hits"]}
    assert rows["YQ-岁运-土运太过"]["yun"] == "土运太过" and rows["YQ-气-四之气-阳明燥金"]["guest"] == "阳明燥金"
    assert rows["YQ-在泉-厥阴风木"]["position"] == "在泉"
    # 背景那一头只留据卡栏，不给体质句；feature 文本指回为纲的编号
    assert set(rows["YQ-司天-少阳相火"]) == {"qi", "position", "groups", "climate", "anchors"}
    bg = next(f for f in y["features"] if f["id"] == "YQ-司天-少阳相火")
    assert "作背景" in bg["text"] and "YQ-在泉-厥阴风木" in bg["text"] and "体感 " not in bg["text"]
    # 生在岁半之前的盘：司天为主、运与司天作改写；在泉与运与在泉作背景；三之气客气即司天，运与当步不另判
    c2 = chart.chart_from_pillars("庚寅", "壬午", "庚辰", "戊寅", "male", story_epoch=300)
    y2 = c2["yunqi"]
    assert y2["roles"]["主"] == ["YQ-司天-少阳相火"] and y2["roles"]["背景"] == ["YQ-运泉-运克泉", "YQ-在泉-厥阴风木"]
    assert y2["roles"]["体"] == ["YQ-岁运-金运太过", "YQ-平气-金"] and y2["relations"]["yunVsStep"] is None
    assert y2["roles"]["改写"] == ["YQ-运天-天克运", "YQ-加临-同气", "YQ-平气修正", "YQ-叠-燥上加燥"]
    assert y2["events"]["grade"] == "和" and y2["events"]["gradeWhy"].startswith("平气")
    # 上临：戊午年火运太过、少阴君火司天，事件层带出 YQ-上临-少阴君火（据卡栏在 row 里）；太一天符为危档
    c3 = chart.chart_from_pillars("戊午", "甲寅", "乙巳", "戊寅", "male", story_epoch=300)
    sl = next(h for h in c3["yunqi"]["hits"] if h["id"] == "YQ-上临-少阴君火")
    assert sl["role"] == "事件" and "病反谵妄狂越" in sl["row"]["shangLin"]
    assert "YQ-天符" in c3["yunqi"]["roles"]["改写"] and c3["yunqi"]["events"]["grade"] == "危" and "太一天符" in c3["yunqi"]["events"]["gradeWhy"]
    assert c3["yunqi"]["events"]["shangLin"]["shangLinQi"] == "少阴君火、少阳相火"
    all_ids = [f["id"] for f in chart.features(c)]
    assert len(all_ids) == len(set(all_ids)) and set(ids) <= set(all_ids)
    # 与调候寒燥的叠加：庚金子月生调候要丙火（寒盘），丑未年太阳寒水在泉、生在岁半之后 → 寒上加寒
    c = chart.chart_from_pillars("己丑", "丙子", "庚辰", "戊寅", "male", story_epoch=300)
    assert c["yongshen"]["tiaohou"]["element"] == "火" and c["yunqi"]["step"]["governing"] == "太阳寒水"
    assert c["yunqi"]["overlap"] == "cold_same" and "YQ-叠-寒上加寒" in [f["id"] for f in c["yunqi"]["features"]]
    # 同一盘换到卯酉年（阳明燥金司天、少阴君火在泉）：下半年君火为纲 → 外热内寒
    c = chart.chart_from_pillars("癸卯", "甲子", "庚辰", "戊寅", "male", story_epoch=300)
    assert c["yunqi"]["overlap"] == "cold_opposite" and "YQ-叠-外热内寒" in [f["id"] for f in c["yunqi"]["features"]]


def test_grade_distribution_and_story_year_qi() -> None:
    """严重档按经文分：六十年乘上下半年，和过半、危最少（DESIGN-命盘层 4 病秧子问题）；平气→和，太过天符→危，岁会→显。"""
    from collections import Counter
    cnt: Counter = Counter()
    for gz in ALL:
        for mb in ("寅", "申"):
            cnt[yunqi.for_chart({"year": gz, "month": "甲" + mb}, None)["events"]["grade"]] += 1
    assert cnt["和"] > cnt["显"] > cnt["危"] and cnt["和"] >= 60 and cnt["危"] <= 24 and sum(cnt.values()) == 120
    assert yunqi.grade_of(yunqi.year_pattern("乙卯"), "同")[0] == "和"      # 不及天符即平气，同正商
    assert yunqi.grade_of(yunqi.year_pattern("戊子"), "同")[0] == "危"      # 太过天符
    assert yunqi.grade_of(yunqi.year_pattern("丙子"), "运克天")[0] == "显"  # 岁会
    assert yunqi.grade_of(yunqi.year_pattern("甲子"), "天生运")[0] == "和"  # 相得
    # 故事年岁气：丁酉年卯酉之政二之气厉大至、善暴死为疫季；甲子年无疫季之文
    yq = yunqi.year_qi("丁酉")
    assert yq["siTian"] == "阳明燥金" and yq["suiYun"] == "木运不及" and yq["epidemicSteps"] == ["二之气（厉大至、善暴死）"]
    assert len(yq["steps"]) == 6 and yq["steps"][1]["guest"] == "少阳相火" and "疫季" in yq["summary"]
    assert yunqi.year_qi("甲子")["epidemicSteps"] == [] and "无疫季之文" in yunqi.year_qi("甲子")["summary"]


def test_table_anchors_and_machine_table_sources_have_cards() -> None:
    ids = _card_ids()
    t, body = yunqi.tables()
    assert body["format"] == "narrative-table/v1"
    counts = {s["key"]: len(s["rows"]) for s in body["sections"]}
    assert counts == {"sixty": 30, "suiyun": 10, "pingqi": 5, "tianquan": 12, "steps": 36, "relations": 27, "overlap": 4, "events": 10, "grades": 3}
    # 六十年主干：六十干支各归一对，太过十五对全正化、不及十五对全邪气化，癸巳癸亥语料缺化数
    sx = {r["pair"]: r for r in next(s for s in body["sections"] if s["key"] == "sixty")["rows"]}
    assert len({yunqi._PAIR_OF[gz] for gz in ALL}) == 30 and all(gz in yunqi._PAIR_OF for gz in ALL)
    for pair, r in sx.items():
        assert pair[0] == pair[2] and r["zhong"].startswith("太" if STEMS.index(pair[0]) % 2 == 0 else "少")
        assert (r["zhengHua"] == "正化日") == r["zhong"].startswith("太"), pair
        assert bool(r["zaiGong"]) == (r["zhong"].startswith("少") and pair != "癸巳癸亥"), pair
        assert r["huaShu"] or pair == "癸巳癸亥"
    for e in t["sixtyYears"]["rule"]:
        assert e["source"] in ids, e["pairs"]
    # 事件层：上临三栏只有气交变有的五对填了；每运一个受邪之脏与情志方向；十运里七运的方向据卡、三运按五脏五志通则
    ev = next(s for s in body["sections"] if s["key"] == "events")["rows"]
    filled = {r["yun"]: r["shangLinQi"] for r in ev if r["shangLinQi"]}
    assert filled == {"火运太过": "少阴君火、少阳相火", "水运太过": "太阳寒水", "木运不及": "阳明燥金", "土运不及": "厥阴风木", "水运不及": "太阴湿土"}
    assert all(r["shangLin"] for r in ev if r["shangLinQi"]) and all(not r["shangLin"] for r in ev if not r["shangLinQi"])
    assert {r["organ"] for r in ev} == {"肝", "心", "脾", "肺", "肾"} and all(r["zhi"] and r["zhiFrom"] and r["bing"] for r in ev)
    assert sum(1 for r in ev if r["zhiFrom"].startswith("据卡")) == 7 and sum(1 for r in ev if r["zhiFrom"].startswith("通则")) == 3
    assert [r["grade"] for r in next(s for s in body["sections"] if s["key"] == "grades")["rows"]] == ["和", "显", "危"]
    # 六步疫季据卡：六元正纪写明温厉、厉大至、善暴死、温病的六步
    ep = {(r["group"], r["step"]) for r in next(s for s in body["sections"] if s["key"] == "steps")["rows"] if r["epidemic"]}
    assert ep == {("丑未", "二之气"), ("寅申", "初之气"), ("寅申", "三之气"), ("卯酉", "二之气"), ("辰戌", "初之气"), ("巳亥", "终之气")}
    # 修正表的条件码与代码能出的编号一一对上
    conds = {r["cond"] for r in next(s for s in body["sections"] if s["key"] == "relations")["rows"]}
    assert {f"yun_vs_zaiquan:{x}" for x in ("运生泉", "泉生运", "运克泉", "泉克运")} <= conds
    assert {f"yun_vs_step:{x}" for x in ("同", "运生气", "气生运", "运克气", "气克运")} <= conds
    for s in body["sections"]:
        for r in s["rows"]:
            for a in r.get("anchors", []):
                assert a in ids, f"{s['key']}: 锚点 {a} 没有对应的卡"
    for key, val in t.items():
        if isinstance(val, dict) and "source" in val and val["source"] != "自起草":
            assert val["source"] in ids, f"{key}: {val['source']}"
    for key, val in t["relations"].items():
        assert val["source"] in ids, f"relations.{key}: {val['source']}"


# ---- 年景表（2026-09-25，tables/yunqi_year.json）

def test_year_scene_table_and_year_qi_scene() -> None:
    import json as _json
    from pathlib import Path as _P
    t = _json.loads((_P(yunqi.__file__).parent / "tables" / "yunqi_year.json").read_text(encoding="utf-8"))
    rows = t["sections"][0]["rows"]
    assert t["format"] == "narrative-table/v1" and len(rows) == 30
    ban = ("司天", "在泉", "岁运", "太过", "不及", "运气", "天符", "岁会", "正化", "邪气", "命", "厥阴", "少阴", "少阳", "太阴", "阳明", "太阳")
    for r in rows:
        assert r["scene"] and r["labels"]["yun"] in ("风年", "热年", "湿年", "燥年", "寒年"), r["pair"]
        assert bool(r["epidemicScene"]) == bool(r["labels"]["epidemicSteps"]), r["pair"]
        assert not any(w in r["scene"] + r["epidemicScene"] for w in ban), r["pair"]
    assert len({r["scene"] for r in rows}) == 30
    # 六十年每年都能查到年景，一对干支同一句；标签由岁运太过不及按规则给
    from bazi_core.dayun import pillar_name
    seen = {}
    for i in range(60):
        gz = pillar_name(i)
        yq = yunqi.year_qi(gz)
        assert yq.get("scene") and yq["scene"]["text"] and "年景" in yq["summary"], gz
        seen.setdefault(yq["scene"]["text"], set()).add(gz)
    assert all(len(v) == 2 for v in seen.values()) and len(seen) == 30
    assert yunqi.year_qi("戊子")["scene"]["label"] == "热年" and yunqi.year_qi("癸亥")["scene"]["label"] == "寒年"
