"""旺衰打分的烟雾测试：只验证方向明显的盘、分类带与合局项的形态，权重本身另行校准。"""

from __future__ import annotations

from bazi_core import strength


def test_obviously_strong_wood() -> None:
    # 甲生寅月得令，年寅時亥通根，天干乙木助：明顯身旺
    r = strength.assess({"year": "甲寅", "month": "丙寅", "day": "甲辰", "hour": "乙亥"})
    assert r["verdict"] == "身旺"
    assert r["flags"] == {"得令": True, "得地": True, "得势": True}
    assert r["favorable"] == ["火", "土", "金"] and r["unfavorable"] == ["水", "木"]


def test_obviously_weak_wood() -> None:
    # 甲生申月失令，年申時午無根，庚金兩透：明顯身弱
    r = strength.assess({"year": "庚申", "month": "甲申", "day": "甲午", "hour": "庚午"})
    assert r["verdict"] == "身弱"
    assert r["flags"]["得令"] is False and r["flags"]["得地"] is False
    assert r["favorable"] == ["水", "木"]


def test_ratio_and_contributions_are_explainable() -> None:
    r = strength.assess({"year": "壬申", "month": "壬子", "day": "戊辰", "hour": "壬子"})
    assert abs(r["support"] + r["drain"] - sum(c["weight"] for c in r["contributions"])) < 1e-9
    assert 0 <= r["ratio"] <= 1
    assert all(c["side"] in ("support", "drain") for c in r["contributions"])


def test_bands() -> None:
    assert strength.WEAK_AT < strength.STRONG_AT
    assert strength.FOLLOW_WEAK_AT < strength.WEAK_AT
    assert strength.FOLLOW_STRONG_AT > strength.STRONG_AT


# ---- v2 合局项

def test_sanhe_full_overrides_main_qi() -> None:
    # 申子辰三合水局：参与之支本气一律改按水论，戊土日主的辰根被夺
    p = {"year": "壬申", "month": "壬子", "day": "戊辰", "hour": "壬子"}
    b_eff, _, combos = strength.combo_effects(p)
    trio = next(c for c in combos if c["kind"] == "三合")
    assert trio["branches"] == "申子辰" and trio["element"] == "水" and trio["override"] is True
    assert b_eff["day"]["override"] == "水"
    r = strength.assess(p)
    assert any("从水局" in c["where"] for c in r["contributions"])
    assert r["verdict"] == "身弱"


def test_sanhui_stronger_than_sanhe() -> None:
    assert strength.SANHUI_FACTOR > strength.SANHE_FACTOR > strength.BANHE_FACTOR


def test_banhe_boosts_but_keeps_main_qi() -> None:
    # 申子半合（含中神子）：只加权，不改本气
    p = {"year": "壬申", "month": "壬子", "day": "丙午", "hour": "戊戌"}
    b_eff, _, combos = strength.combo_effects(p)
    half = [c for c in combos if c["kind"] == "半合"]
    assert half and all(c["override"] is False for c in half)
    assert b_eff["year"]["override"] is None and b_eff["year"]["factor"] > 1.0
    assert not any("从" in c["where"] for c in strength.assess(p)["contributions"])


def test_banhe_needs_center_branch() -> None:
    # 申辰无中神子，只算拱合，不计
    _, _, combos = strength.combo_effects({"year": "壬申", "month": "丙寅", "day": "戊辰", "hour": "丁巳"})
    assert not any(c["kind"] in ("半合", "三合") for c in combos)


def test_liuhe_hua_when_in_season_else_damp() -> None:
    # 寅亥合木，生于卯月木当令：合化成立，两支改按木论
    b_eff, _, combos = strength.combo_effects({"year": "丁亥", "month": "癸卯", "day": "庚寅", "hour": "丙子"})
    six = next(c for c in combos if c["kind"] == "六合")
    assert six["override"] is True and six["element"] == "木" and b_eff["year"]["override"] == "木"
    # 同样寅亥，生于酉月：不当令，合绊减力
    b_eff, _, combos = strength.combo_effects({"year": "丁亥", "month": "己酉", "day": "庚寅", "hour": "丙子"})
    six = next(c for c in combos if c["kind"] == "六合")
    assert six["override"] is False and b_eff["year"]["factor"] < 1.0 and b_eff["day"]["factor"] < 1.0
    # 午未所化两存，一律合绊
    _, _, combos = strength.combo_effects({"year": "甲午", "month": "辛未", "day": "庚子", "hour": "丙子"})
    six = next(c for c in combos if c["kind"] == "六合")
    assert six["override"] is False and "两存" in six["detail"]


def test_stem_he_hua_and_jealousy() -> None:
    # 年甲月己生于辰月：甲己化土成立（非辰戌丑未月不化），两干改按土论
    _, s_eff, combos = strength.combo_effects({"year": "甲子", "month": "己巳", "day": "庚午", "hour": "丙子"})
    assert not any(c["kind"] == "天干合" and c["override"] for c in combos)  # 巳月不化
    _, s_eff, combos = strength.combo_effects({"year": "甲子", "month": "戊辰", "day": "庚午", "hour": "丙子"})
    assert not any(c["kind"] == "天干合" for c in combos)  # 甲戊不合
    _, s_eff, combos = strength.combo_effects({"year": "甲辰", "month": "己巳", "day": "庚午", "hour": "丙子"})
    he = next(c for c in combos if c["kind"] == "天干合")
    assert he["override"] is False and "不化" in he["detail"]
    _, s_eff, combos = strength.combo_effects({"year": "甲戌", "month": "己丑", "day": "庚午", "hour": "丙子"})
    he = next(c for c in combos if c["kind"] == "天干合")
    assert he["override"] is True and s_eff["year"]["override"] == "土" and s_eff["month"]["override"] == "土"
    # 柱有戊则妒合不化
    _, s_eff, combos = strength.combo_effects({"year": "甲戌", "month": "己丑", "day": "庚午", "hour": "戊子"})
    he = next(c for c in combos if c["kind"] == "天干合")
    assert he["override"] is False and "妒合" in he["detail"] and s_eff["year"]["factor"] < 1.0
    # 年时不相邻不合
    _, _, combos = strength.combo_effects({"year": "甲戌", "month": "丙寅", "day": "庚午", "hour": "己丑"})
    assert not any(c["kind"] == "天干合" for c in combos)


def test_stem_he_with_day_master_only_binds_the_other() -> None:
    # 日主庚合月干乙：乙被合住减力，日主不改
    _, s_eff, combos = strength.combo_effects({"year": "壬子", "month": "乙酉", "day": "庚午", "hour": "丙子"})
    he = next(c for c in combos if c["kind"] == "天干合")
    assert he["pillars"] == ["月"] and s_eff["month"]["factor"] < 1.0 and s_eff["day"]["factor"] == 1.0


def test_combo_changes_the_verdict() -> None:
    with_ju = strength.assess({"year": "壬申", "month": "壬子", "day": "甲辰", "hour": "壬子"})
    without = strength.assess({"year": "壬申", "month": "壬子", "day": "甲戌", "hour": "壬子"})
    assert with_ju["ratio"] != without["ratio"]
    assert any(c["kind"] == "三合" for c in with_ju["combos"])
    assert not any(c["kind"] == "三合" for c in without["combos"])


def test_factor_is_clamped_and_sum_explainable() -> None:
    for p in ({"year": "甲寅", "month": "丁卯", "day": "庚辰", "hour": "丙子"},
              {"year": "壬申", "month": "壬子", "day": "戊辰", "hour": "壬子"},
              {"year": "甲戌", "month": "己丑", "day": "庚午", "hour": "丙子"}):
        b_eff, s_eff, _ = strength.combo_effects(p)
        for eff in (b_eff, s_eff):
            assert all(strength.FACTOR_FLOOR <= e["factor"] <= strength.FACTOR_CEIL for e in eff.values())
        r = strength.assess(p)
        assert abs(r["support"] + r["drain"] - sum(c["weight"] for c in r["contributions"])) < 0.02
