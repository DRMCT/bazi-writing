"""用神、弧光的形态与方向测试。用神规则本身按徐评例盘与子代理判定校准，这里只守住口径与下限。"""

from __future__ import annotations

import random

import pytest

from bazi_core import arc, chart, yongshen
from bazi_core.dayun import pillar_name
from bazi_core.shishen import WUXING

SHENYAN = {"year": "甲申", "month": "壬申", "day": "乙巳", "hour": "戊寅"}


def _random_pillars(rng: random.Random) -> dict:
    return {k: pillar_name(rng.randrange(60)) for k in ("year", "month", "day", "hour")}


def test_roles_follow_generation_cycle() -> None:
    rng = random.Random(7)
    for _ in range(200):
        p = _random_pillars(rng)
        y = yongshen.determine(p)
        roles = y["roles"]
        assert sum(r == "用" for r in roles.values()) == 1
        u = WUXING.index(y["yong"]["element"])
        # 克用神者必为忌；病神必为忌
        assert roles[WUXING[(u - 2) % 5]] == "忌"
        if y["bing"]:
            assert roles[y["bing"]["element"]] == "忌"
        assert y["damping"] in (1.0, yongshen.DAMPING_ZHONGHE)
        assert y["preference"][y["yong"]["element"]] == y["damping"]
        assert {round(v / y["damping"], 3) for v in y["preference"].values()} <= {1.0, 0.5, 0.25, 0.0, -0.25, -0.5, -1.0}
        assert y == yongshen.determine(p)  # 确定性


def test_classic_cases() -> None:
    # 子平八-03 丁巳月丁卯日，火炎土燥日元太旺，取年上癸水抑之：身旺比劫为病，官杀有力
    assert yongshen.determine({"year": "癸巳", "month": "丁巳", "day": "丁卯", "hour": "丙午"})["yong"]["family"] == "官杀"
    # 子平八-12 辛丑日丑月金寒水冷，取时上午火调候
    y = yongshen.determine({"year": "壬辰", "month": "癸丑", "day": "辛丑", "hour": "甲午"})
    assert y["yong"]["element"] == "火" and y["method"] == "调候" and y["tiaohou"]["adopted"]
    # 子平三十二-02（与样例沈砚同盘）徐评兼用财印；中和临界盘 preference 减半
    y = yongshen.determine(SHENYAN)
    assert y["yong"]["family"] in ("财", "印") and y["damping"] == 0.5 and y["preference"]["土"] == 0.5
    # 子平八-06 己卯 丁丑 癸丑 乙卯：杀重而印（庚辛）无力，食伤（乙）透干，徐评"取食神制煞为用"
    y = yongshen.determine({"year": "己卯", "month": "丁丑", "day": "癸丑", "hour": "乙卯"})
    assert y["yong"]["family"] == "食伤" and "印无力" in y["reason"]
    saved = yongshen.RULES["yin_weak"]
    yongshen.RULES["yin_weak"] = False
    try:
        assert yongshen.determine({"year": "己卯", "month": "丁丑", "day": "癸丑", "hour": "乙卯"})["yong"]["family"] == "印"
    finally:
        yongshen.RULES["yin_weak"] = saved


def test_xu_gold_lower_bound() -> None:
    import calibrate_yongshen as cy

    cases = [c for c in cy.gold_cases() if c["book"] == "子平"]
    assert len(cases) >= 80
    hit = sum(yongshen.determine(c["pillars"])["yong"]["family"] in c["gold"]["families"] for c in cases)
    assert hit / len(cases) >= 0.47  # 2026-09-23 印无力改食神制杀后 39/82；徐评八格章的用神多指格局用神，见用神_例盘报告


def test_template_match_and_resample() -> None:
    assert arc.match(arc.TEMPLATES["正弧"], "正弧") == 1.0
    assert arc.match([1, 1, 1, 1], [-1, -1, -1, -1]) == 0.0
    steps = [{"startAge": 3, "endAge": 13, "score": 1.0}, {"startAge": 13, "endAge": 23, "score": -1.0}]
    assert arc.resample(steps, (8, 18)) == [1.0, 1.0, -1.0, -1.0]
    assert arc.resample(steps, (0, 12)) == [0.0, 1.0, 1.0, 1.0]  # 起运前记 0
    r = arc.ranking([0.2, -0.3, -0.8, 0.5])
    assert r[0]["template"] == "正弧" and r == sorted(r, key=lambda x: -x["match"])


def test_transit_terms_are_explained() -> None:
    ys = yongshen.determine(SHENYAN)
    r = arc.transit_score(SHENYAN, "乙亥", ys)
    assert any("冲日支" in t["term"] for t in r["terms"])
    assert abs(sum(t["value"] for t in r["terms"]) - r["raw"]) < 1e-9
    assert -1 <= r["score"] <= 1
    r = arc.transit_score(SHENYAN, "戊寅", ys)
    assert "冲提纲" in r["flags"] and any(t["term"].startswith("伏吟时柱") for t in r["terms"])


def test_turning_score() -> None:
    cands = [{"age": 27, "kind": "流年冲日支", "text": ""}, {"age": 33, "kind": "换运", "text": ""}]
    assert arc.turning_score(cands, 27)["score"] == 1.0
    assert arc.turning_score(cands, 29)["score"] == 0.8
    assert arc.turning_score(cands, 30)["score"] == 0.0
    assert arc.turning_score([], 30)["score"] == 0.0


def test_chart_carries_yongshen_and_scores() -> None:
    c = chart.chart_from_pillars("甲申", "壬申", "乙巳", "戊寅", "male", story_epoch=300)
    c["liunian"] = [chart.liunian(c, 30)]
    assert c["yongshen"]["yong"]["element"] == "土"  # 中和偏旺、印多为病，取时干戊土财损印（徐评此造兼用财印）
    assert len(c["dayunScores"]) == len(c["dayun"]["steps"])
    ids = {x["id"] for x in chart.features(c)}
    assert "U-用-土" in ids and "U-忌-木" in ids and "U-病-水" in ids
    assert c["liunian"][0]["score"] is not None
    res = arc.for_chart(c, (24, 46), 30)
    assert set(res["vector"]) == {"起", "承", "转", "合"} and res["best"] in arc.TEMPLATES
    assert res["turning"]["candidates"]


@pytest.mark.parametrize("window", [(24, 24), (30, 20)])
def test_bad_window(window) -> None:
    with pytest.raises(ValueError):
        arc.resample([], window)
