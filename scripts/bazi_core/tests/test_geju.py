"""格局成败表：表形态（八格、每条带卡号与定稿状态）、几条书里明说的成败条件、chart 带出格局节。"""

from __future__ import annotations

import json
from pathlib import Path

from bazi_core import geju
from bazi_core.chart import chart_from_pillars

TABLE = Path(__file__).resolve().parent.parent / "tables" / "geju.json"


def test_table_shape() -> None:
    t = json.loads(TABLE.read_text(encoding="utf-8"))
    names = [e["name"] for e in t["entries"]]
    assert sorted(names) == sorted(["正官", "财", "印绶", "食神", "偏官", "伤官", "阳刃", "建禄月劫"])
    for e in t["entries"]:
        assert e["source"] == f"格局-{e['name']}" and e["status"] in ("已核", "已裁", "已审"), e["name"]
        assert e["cheng"] and e["bai"] and e["yun"], e["name"]
        for i in e["cheng"] + e["bai"]:
            assert i["atoms"], i
    covered = {s for e in t["entries"] for s in e["structures"]}
    assert covered == {"正官格", "正财格", "偏财格", "正印格", "偏印格", "食神格", "七杀格", "伤官格", "月刃格", "建禄格", "月劫格"}


def test_rulings_from_sanming() -> None:
    # 第九章：官逢财印、无刑冲破害，官格成也；官逢伤为败，透印救
    zg = geju.entry("正官格")
    assert any("官逢财" in i["core"] and "逢印" in i["core"] for i in zg["cheng"])
    assert any(i["core"] == "官逢伤" for i in zg["bai"])
    assert any("官逢伤" in j["cause"]["core"] and "印" in j["fix"]["core"] for j in zg["jiu"])
    # 偏官：裁决以"刃当煞"为主条，"印化煞"降为本书异文
    qs = geju.entry("七杀格")
    assert any("刃当煞" in i["core"] for i in qs["cheng"])
    assert any("印化煞" in i["core"] and i["notes"] for i in qs["cheng"])
    # 财：败条从徐评加"且无印"
    assert any("财旺" in i["core"] and "无印" in i["core"] for i in geju.entry("正财格")["bai"])
    # 取运按局分列，喜忌不忌三档
    assert any(y["scope"] != "通" and (y["favor"] or y["avoid"]) for y in zg["yun"])


def test_chart_carries_geju() -> None:
    c = chart_from_pillars("甲申", "壬申", "乙巳", "戊寅", gender="male")   # 薛相公命
    assert c["geju"]["structure"] == c["natal"]["structure"]["name"]
    assert c["geju"]["status"] == "校核定稿" and c["geju"]["source"].startswith("格局-")
    assert c["geju"]["cheng"] and c["geju"]["yun"]


# ---- 逐盘判定（2026-09-23）

def test_judge_xue_xianggong() -> None:
    # 薛相公命：变格正印，财印不相碍；本格正官因申巳合、寅申冲而"官逢刑冲"，判定按 monthBase 一并带出
    from bazi_core.shishen import determine_structure
    p = {"year": "甲申", "month": "壬申", "day": "乙巳", "hour": "戊寅"}
    j = geju.judge(p, determine_structure(*p.values()))
    assert j["structure"] == "正印格" and j["verdict"] == "成格"
    assert j["monthBase"]["structure"] == "正官格"
    assert any(b["text"] == "官逢刑冲" and b["holds"] for b in j["monthBase"]["bai"])
    k, n = j["coverage"].split("/")
    assert int(n) > 0 and int(k) / int(n) >= 0.8


def test_judge_atoms() -> None:
    f = geju.chart_facts({"year": "甲申", "month": "壬申", "day": "乙巳", "hour": "戊寅"})
    assert geju.eval_atom("透财", f) is True and geju.eval_atom("透煞", f) is False
    assert geju.eval_atom("财印不相碍", f) is True  # 戊在时、壬在月，隔日主
    assert geju.eval_atom("逢官", f) is True and geju.eval_atom("无官", f) is False  # 申本气庚为官
    assert geju.eval_atom("印化劫", f) is None  # 化类原子不判
    assert geju.eval_atom("身强", f) in (True, False)
    # 逢只认透干与本气：癸日亥中甲木（中气）不算"官逢伤"
    f2 = geju.chart_facts({"year": "庚戌", "month": "戊子", "day": "癸酉", "hour": "癸亥"})
    assert geju.eval_atom("官逢伤", f2) is False and geju.eval_atom("官煞混", f2) is False


def test_chart_carries_judge() -> None:
    from bazi_core import chart
    c = chart.chart_from_pillars("甲申", "壬申", "乙巳", "戊寅", "male", story_epoch=300)
    assert c["geju"]["judge"]["verdict"] in ("成格", "败格", "败而有救", "不成格", "待判")
    assert c["geju"]["monthBase"]["structure"] == "正官格"
