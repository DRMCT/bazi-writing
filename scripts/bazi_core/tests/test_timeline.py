"""年表：流年干支与命盘 liunian 一致、机制与领域可解释、编号不重复、检查器 --timeline 认 L- 编号。"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from bazi_core import chart, timeline

ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _shenyan() -> dict:
    return chart.chart_from_pillars("甲申", "壬申", "乙巳", "戊寅", "male", story_epoch=300, name="沈砚")


def test_years_match_chart_liunian() -> None:
    c = _shenyan()
    t = timeline.build(c, (0, 40))
    # 逐年表延到与窗相交的最后一步大运的末尾（coverage），候选年份只算窗内
    last = max(s["endAge"] for s in c["dayun"]["steps"] if s["startAge"] <= 40 and s["endAge"] > 0) - 1
    assert t["window"] == [0, 40] and t["coverage"] == [0, last] and last > 40
    assert [y["age"] for y in t["years"]] == list(range(0, last + 1))
    assert all(a <= 40 for a in t["candidates"]) and t["stages"][-1]["candidates"] and max(t["stages"][-1]["candidates"]) > 40
    for y in t["years"][::7]:
        ln = chart.liunian(c, y["age"])
        assert ln["pillar"] == y["pillar"] and ln["score"] == y["score"] and y["year"] == 300 + y["age"]
    ids = [f["id"] for f in t["features"]]
    assert len(ids) == len(set(ids))


def test_mechanisms_and_domains() -> None:
    t = timeline.build(_shenyan(), (6, 6))
    y = t["years"][0]
    assert y["pillar"] == "庚寅"
    assert {"冲提纲", "冲年支", "天克地冲年柱"} <= set(y["mechanisms"])
    doms = {d["domain"] for d in y["domains"]}
    assert {"六亲", "迁徙与归属", "事业与权力"} <= doms
    assert set(doms) <= set(timeline.DOMAINS)
    assert 6 in t["candidates"]
    assert "L-6-庚寅-冲提纲" in {f["id"] for f in t["features"]}
    # 弱信号（流年见某十神）单独不成领域：6 岁流年庚寅见官杀，事业与权力靠冲提纲这条强信号成立
    via = {d["domain"]: d["via"] for d in y["domains"]}
    assert "冲提纲申" in via["事业与权力"]


def test_candidates_are_sparse() -> None:
    t = timeline.build(_shenyan(), (0, 60))
    assert 0 < len(t["candidates"]) <= len(t["years"]) // 2
    weak_only = [y for y in t["years"] if y["domains"] and all(len(d["via"]) == 1 and d["via"][0].startswith("流年见") for d in y["domains"])]
    assert not weak_only


def test_stage_tone() -> None:
    t = timeline.build(_shenyan(), (0, 80))
    for s in t["stages"]:
        assert s["tone"] == ("顺" if s["score"] > 0 else "逆" if s["score"] < 0 else "平")
    assert {"顺", "逆"} <= {s["tone"] for s in t["stages"]}


@pytest.mark.skipif(shutil.which("node") is None, reason="需要 node")
def test_checker_accepts_timeline_ids(tmp_path: Path) -> None:
    c = _shenyan()
    c["features"] = chart.features(c)
    (tmp_path / "命盘").mkdir()
    (tmp_path / "人物").mkdir()
    (tmp_path / "命盘" / "沈砚.json").write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")
    tl = tmp_path / "命盘" / "沈砚.年表.json"
    tl.write_text(json.dumps(timeline.build(c, (0, 20)), ensure_ascii=False), encoding="utf-8")
    titles = ["性格表里", "童年事件", "谎言", "秘密", "需要与想要", "抵抗线", "亲密关系模式", "说话方式",
              "能力与漏洞", "意象系统", "他人眼中的他", "年表与两难"]
    sections = [{"title": t, "traits": []} for t in titles] + [{"title": "阶段状态", "stages": []}]
    sections[1]["traits"] = [{"text": "六岁那年家里搬离祖宅，父亲丢了差事。", "sources": ["L-6-庚寅-冲提纲", "L-6-庚寅-域-迁徙与归属"]}]
    doc = {"schema": "bazi-character/v1", "setting": {"period": "古代", "world": "合成档案，检查器用"}, "name": "沈砚", "chart": "命盘/沈砚.json", "sections": sections}
    p = tmp_path / "人物" / "沈砚.json"
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    cmd = ["node", str(ROOT / "scripts" / "check-character.js"), str(p), "--summary"]
    assert subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8").returncode == 1
    r = subprocess.run(cmd + ["--timeline", str(tl)], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout


def test_illness_candidate_only_on_body_mind_years() -> None:
    """身心域被引动的年份挂 L-…-病候（DESIGN 7.4 病秧子问题）：三层写在一条里；其余年份不挂；旧命盘没有 events 不挂。"""
    import json as _json
    from bazi_core import chart, timeline
    c = chart.chart_from_pillars("甲申", "壬申", "乙巳", "戊寅", "male", story_epoch=300, name="沈砚")
    t = timeline.build(c, (0, 60))
    ill = [y for y in t["years"] if y.get("illnessCandidate")]
    assert ill and all(any(d["domain"] == "身心" for d in y["domains"]) for y in ill)
    assert all(not y.get("illnessCandidate") for y in t["years"] if not any(d["domain"] == "身心" for d in y["domains"]))
    ids = {f["id"] for f in t["features"]}
    for y in ill:
        assert f"L-{y['age']}-{y['pillar']}-病候" in ids
        ic = y["illnessCandidate"]
        assert ic["grade"] == "显" and ic["organ"] == "肾" and ic["zhi"] == "郁" and ic["level"] == "重相"
        assert ic["yearQi"].startswith(f"流年{y['pillar']}岁气") and ic["ids"] == ["YQ-档-显", "YQ-病-肾", "YQ-志-郁"]
    txt = next(f["text"] for f in t["features"] if f["id"].endswith("-病候"))
    assert "默认不写" in txt and "薄弱处肾" in txt and "情志往郁的方向垮" in txt
    # 流年司天或在泉克薄弱脏（肾水）时标加重：只有太阴湿土能克
    assert all(q == "太阴湿土" for y in ill for q in y["illnessCandidate"]["pressing"])
    # 旧命盘没有 events：不挂
    c2 = _json.loads(_json.dumps(c)); c2["yunqi"].pop("events")
    assert not any(f["id"].endswith("-病候") for f in timeline.build(c2, (0, 60))["features"])
