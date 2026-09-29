"""四张自起草叙事表（日支亲密关系、谎言候选、弧光匹配、意象系统）与两个 M5 尾巴（两难改写、配角日程）。

- 表形态：narrative-table/v1 多分表，每行 anchors 指向的校核卡号都存在（所有校核卡，不只滴天髓）；
- 求值：样例沈砚的亲密关系、意象、谎言各节命中可解释，编号进 features 且不重复；
- 弧光 reading 按表填，档位与分数一致；
- 两难：候选年份都有主机制与主领域，精选格与合成两条路都走到，ids 都在年表里；影响谁按快照边去重；
- 日程：交汇点带 J- 编号，检查器 --schedule 认。
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from bazi_core import arc, chart, dilemma, imagery, intimacy, lies, schedule, timeline

ROOT = Path(__file__).resolve().parents[3]
TABLES = ROOT / "scripts" / "bazi_core" / "tables"
CARDS = ROOT / "references" / "校核"


def _card_ids() -> set[str]:
    ids: set[str] = set()
    for f in CARDS.glob("*.md"):
        ids.update(re.findall(r"(?m)^### (\S+-\S+)", f.read_text(encoding="utf-8")))
    return ids


def _shenyan() -> dict:
    return chart.chart_from_pillars("甲申", "壬申", "乙巳", "戊寅", "male", story_epoch=300, name="沈砚")


def _linzhao() -> dict:
    return chart.chart_from_pillars("戊戌", "甲寅", "辛酉", "甲午", "female", start_age_years=5, story_epoch=306, name="林昭")


@pytest.mark.parametrize("name", ["rizhi_intimacy.json", "lies.json", "arc_match.json", "imagery.json", "stage_overlay.json"])
def test_sectioned_table_shape(name):
    t = json.loads((TABLES / name).read_text(encoding="utf-8"))
    assert t["format"] == "narrative-table/v1" and t["sections"]
    ids = _card_ids()
    for s in t["sections"]:
        keys = {c["key"] for c in s["columns"]}
        assert "anchors" in keys and s["rows"]
        for r in s["rows"]:
            assert set(r) == keys, (name, s["key"], r)
            for a in r["anchors"]:
                assert a in ids, f"{name}: 锚点 {a} 没有对应的卡"


def test_intimacy_table_covers_ten_gods_and_branches():
    t = intimacy.table()
    sec = {s["key"]: s for s in t["sections"]}
    assert {r["tenGod"] for r in sec["tenGod"]["rows"]} == {"正官", "七杀", "正财", "偏财", "正印", "偏印", "食神", "伤官", "比肩", "劫财"}
    assert "".join(r["branch"] for r in sec["branch"]["rows"]) == "子丑寅卯辰巳午未申酉戌亥"
    conds = {r["cond"] for r in sec["modifiers"]["rows"]}
    src = Path(intimacy.__file__).read_text(encoding="utf-8")
    for c in conds:
        assert f'"{c}"' in src, f"条件码 {c} 脚本不会求值"


def test_intimacy_for_shenyan():
    c = _shenyan()
    it = c["intimacy"]
    assert it["tenGod"]["tenGod"] == "伤官" and it["branch"]["branch"] == "巳"
    conds = {m["cond"] for m in it["modifiers"]}
    # 巳火在沈砚为喜；年日、月日申巳六合；日时寅巳刑、害；男命财透一处不算多
    assert {"day_branch_yong", "day_branch_combined", "day_branch_xing", "day_branch_hai"} <= conds
    assert "lover_star_absent" not in conds and "lover_star_multi" not in conds
    assert it["loverStar"] == {"family": "财", "exposed": 1, "main": 0, "anywhere": True}
    ids = {f["id"] for f in chart.features(c)}
    assert {"IN-十神-伤官", "IN-支-巳", "IN-day_branch_yong"} <= ids


def test_intimacy_lover_star_conditions():
    # 女命正官七杀并透：丙午年 壬辰月 辛酉日 丁亥时（辛见丙为正官、丁为七杀）
    c = chart.chart_from_pillars("丙午", "壬辰", "辛酉", "丁亥", "female", story_epoch=310, name="甲")
    assert "female_guan_sha_mixed" in {m["cond"] for m in c["intimacy"]["modifiers"]}
    # 男命四柱无财：甲寅 壬子 乙卯 癸亥（乙木见金为官、土为财：全无金土）
    c = chart.chart_from_pillars("壬子", "癸卯", "乙亥", "丙子", "male", story_epoch=310, name="乙")
    conds = {m["cond"] for m in c["intimacy"]["modifiers"]}
    assert "lover_star_absent" in conds and "jie_heavy_cai_light" in conds


def test_imagery_for_shenyan():
    c = _shenyan()
    im = c["imagery"]
    assert im["material"]["element"] == "木"
    fam = {f["element"]: f for f in im["families"] if f["role"] != "病"}
    assert fam["土"]["kind"] == "救赎意象" and fam["水"]["kind"] == "威胁意象"
    assert any(f["role"] == "病" and f["element"] == "水" for f in im["families"])
    mods = {m["cond"] for m in im["modifiers"]}
    assert {"day_branch_element", "month_branch_element", "shensha_驿马", "shensha_天乙贵人", "shensha_空亡"} <= mods
    ids = [f["id"] for f in im["features"]]
    assert len(ids) == len(set(ids)) and "IM-用-土" in ids and "IM-日支-火" in ids
    # 冬月要火的盘记寒
    c2 = chart.chart_from_pillars("壬辰", "癸丑", "辛丑", "甲午", "male", story_epoch=310, name="丙")
    assert "cold" in {m["cond"] for m in c2["imagery"]["modifiers"]}


def test_lies_patterns_and_pins():
    c = _shenyan()
    li = c["lies"]
    names = [p["pattern"] for p in li["patterns"]]
    assert names == ["中和临界", "身旺印为病"]
    assert all(3 <= len(p["candidates"]) <= 5 for p in li["patterns"])
    pins = {p["mechanism"]: p for p in li["pins"]}
    assert {"冲提纲", "天克地冲", "冲年支"} <= set(pins) and "忌神透干" not in pins
    assert pins["冲提纲"]["years"][0]["age"] == 6 and pins["冲提纲"]["years"][0]["liunianId"] == "L-6-庚寅-冲提纲"
    ids = {f["id"] for f in chart.features(c)}
    assert {"LI-身旺印为病-1", "LI-钉-冲提纲"} <= ids
    # 调候为用的盘
    c2 = chart.chart_from_pillars("壬辰", "癸丑", "辛丑", "甲午", "male", story_epoch=310, name="丙")
    assert "调候为用" in [p["pattern"] for p in c2["lies"]["patterns"]]
    # 每个格局名脚本都认得出：patterns_for 的输出必是表里的行
    for row in lies.table()["sections"][0]["rows"]:
        assert row["pattern"] in lies._PATTERNS


def test_arc_reading():
    c = _shenyan()
    r = arc.for_chart(c, (24, 46), 30)
    rd = r["reading"]
    assert rd["template"] == r["best"] and len(rd["segments"]) == 4
    for t in rd["tones"]:
        assert t["band"] == arc.tone_band(t["score"])
    assert arc.tone_band(0.8) == "强顺" and arc.tone_band(-0.05) == "平" and arc.tone_band(-0.3) == "弱逆"
    assert rd["advice"]["text"] and {t["kind"] for t in rd["turnings"]} <= {"换运", "流年天克地冲日柱", "流年冲日支"}


def test_dilemma_from_timeline():
    c = _shenyan()
    tl = timeline.build(c, (0, 60))
    d = dilemma.build(tl, c, [_linzhao()])
    assert d["schema"] == "bazi-dilemma/v1" and [i["age"] for i in d["items"]] == tl["candidates"]
    tl_ids = {f["id"] for f in tl["features"]}
    templates = set()
    for it in d["items"]:
        assert it["mechanism"] in dilemma.MECH and it["primary"]["domain"] in timeline.DOMAINS and it["dilemma"]
        assert set(it["ids"]) <= tl_ids
        templates.add(it["template"])
        whos = [a["who"] for a in it.get("affects", [])]
        assert len(whos) == len(set(whos))
    assert templates == {"精选格", "按合成规则合成"}
    six = next(i for i in d["items"] if i["age"] == 6)
    # 六岁庚寅天克地冲年柱、冲提纲、冲年支、逢驿马：主机制天克地冲，年柱宫位指向六亲与迁徙，两者一主一副
    assert six["mechanism"] == "天克地冲" and six["affects"]
    assert {six["primary"]["domain"], six["secondary"]["domain"]} == {"六亲", "迁徙与归属"}
    thirty = next(i for i in d["items"] if i["age"] == 30)
    assert thirty["mechanism"] == "冲提纲" and thirty["primary"]["domain"] in ("六亲", "事业与权力")
    assert dilemma.normalize("巳刑申（日支）") == "刑" and dilemma.normalize("天克地冲年柱") == "天克地冲"


@pytest.mark.skipif(shutil.which("node") is None, reason="需要 node")
def test_schedule_and_checker(tmp_path: Path) -> None:
    a, b = _shenyan(), _linzhao()
    s = schedule.build([a, b], (320, 345), main="沈砚")
    assert s["schema"] == "bazi-schedule/v1" and len(s["grid"]) == 26
    rows = {r["year"]: r for r in s["people"][0]["rows"]}
    assert rows[330]["age"] == 30 and rows[330]["candidate"] is True and rows[330]["liunian"] == "甲寅"
    assert s["intersections"] and all(x["id"].startswith("J-") and "沈砚" in x["people"] for x in s["intersections"])
    ids = [f["id"] for f in s["features"]]
    assert len(ids) == len(set(ids))
    with pytest.raises(ValueError):
        schedule.build([a, chart.chart_from_pillars("戊戌", "甲寅", "辛酉", "甲午", "female", name="无锚")], (320, 321))
    # 检查器认 J- 编号
    a["features"] = chart.features(a)
    (tmp_path / "命盘").mkdir()
    (tmp_path / "人物").mkdir()
    (tmp_path / "命盘" / "沈砚.json").write_text(json.dumps(a, ensure_ascii=False), encoding="utf-8")
    sp = tmp_path / "命盘" / "日程.json"
    sp.write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
    titles = ["性格表里", "童年事件", "谎言", "秘密", "需要与想要", "抵抗线", "亲密关系模式", "说话方式",
              "能力与漏洞", "意象系统", "他人眼中的他", "年表与两难"]
    sections = [{"title": t, "traits": []} for t in titles] + [{"title": "阶段状态", "stages": []}]
    sections[-2]["traits"] = [{"text": "那一年两人的事撞在一起。", "sources": [s["intersections"][0]["id"]]}]
    doc = {"schema": "bazi-character/v1", "setting": {"period": "古代", "world": "合成档案，检查器用"}, "name": "沈砚", "chart": "命盘/沈砚.json", "sections": sections}
    p = tmp_path / "人物" / "沈砚.json"
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    cmd = ["node", str(ROOT / "scripts" / "check-character.js"), str(p), "--summary"]
    assert subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8").returncode == 1
    r = subprocess.run(cmd + ["--schedule", str(sp)], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout


def test_lover_star_set_by_author_follows_family_not_gender():
    # DESIGN-人物层 6：亲密关系星由作者在排盘时指定（--lover-star），写进命盘顶层 loverStar；条件跟家族走，年表与阶段卡读同一处
    from bazi_core import stagecard, timeline
    d = chart.chart_from_pillars("丙午", "壬辰", "辛酉", "丁亥", "female", story_epoch=310, name="甲")
    a = chart.chart_from_pillars("丙午", "壬辰", "辛酉", "丁亥", "female", story_epoch=310, name="甲", lover_star="财")
    assert d["loverStar"] == {"family": "官杀", "gods": ["正官", "七杀"], "by": "性别默认"}
    assert a["loverStar"] == {"family": "财", "gods": ["正财", "偏财"], "by": "作者指定"}
    assert "female_guan_sha_mixed" in {m["cond"] for m in d["intimacy"]["modifiers"]}
    assert "female_guan_sha_mixed" not in {m["cond"] for m in a["intimacy"]["modifiers"]}
    assert d["intimacy"]["loverStar"]["family"] == "官杀" and a["intimacy"]["loverStar"]["family"] == "财"
    assert intimacy.lover_gods(d) == ("正官", "七杀") and intimacy.lover_gods(a) == ("正财", "偏财")
    assert intimacy.lover_gods({k: v for k, v in d.items() if k != "loverStar"}) == ("正官", "七杀")  # 旧命盘无此字段：按性别默认
    assert intimacy.lover_gods({"gender": None}) == ()
    with pytest.raises(ValueError):
        chart.chart_from_pillars("丙午", "壬辰", "辛酉", "丁亥", "female", story_epoch=310, lover_star="桃花")
    # 年表：感情领域"流年见亲密关系星"的弱信号跟着家族换
    def lover_years(t):
        return {y["age"] for y in t["years"] for dm in y["domains"] if any("亲密关系星" in v for v in dm["via"])}
    def named(t):
        return {v for y in t["years"] for dm in y["domains"] for v in dm["via"] if "亲密关系星" in v}
    td, ta = timeline.build(d, (0, 30)), timeline.build(a, (0, 30))
    assert lover_years(td) and lover_years(ta) and lover_years(td) != lover_years(ta)
    assert named(td) <= {"流年见亲密关系星正官", "流年见亲密关系星七杀"} and named(ta) <= {"流年见亲密关系星正财", "流年见亲密关系星偏财"}
    # 阶段卡：亲密关系动静里"大运带亲密关系星"按家族
    def stage_lover(c, t):
        out = set()
        for card in stagecard.build(t, c, None, (0, 30))["stages"]:
            for tr in card["aspects"]["亲密关系动静"]["ids"]:
                if tr.endswith(("-正官", "-七杀", "-正财", "-偏财")):
                    out.add(tr.split("-")[-1])
        return out
    assert stage_lover(d, td) <= {"正官", "七杀"} and stage_lover(a, ta) <= {"正财", "偏财"}
    assert stage_lover(d, td) or stage_lover(a, ta)
