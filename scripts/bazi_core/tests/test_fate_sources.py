"""人物与事件线第 5 步（DESIGN-戏剧层 6、7.5）：默认下场年表与前史（fate）、编配 v2、事件源扩表、时间尺度（短跨度的流月表、回到关口年）、
上一代与单元客。"""

from __future__ import annotations

import pytest

from bazi_core import chart, dilemma, ensemble_run as run, fate, lies, matrix, timeline


def _trio() -> list[dict]:
    a = chart.chart_from_pillars("甲申", "壬申", "乙巳", "戊寅", "male", story_epoch=300, name="沈砚")
    b = chart.chart_from_pillars("庚寅", "壬午", "辛酉", "戊戌", "female", start_age_years=5, story_epoch=306, name="林昭")
    c = chart.chart_from_pillars("丁亥", "壬寅", "己卯", "甲子", "male", story_epoch=303, name="裴恪")
    return [a, b, c]


def _elder() -> dict:
    return chart.chart_from_pillars("庚申", "戊子", "甲午", "丙寅", "male", story_epoch=280, name="林父")


def _guest() -> dict:
    return chart.chart_from_pillars("癸亥", "甲寅", "丙午", "庚寅", "female", story_epoch=310, name="客")


CAST = {"schema": "bazi-casting/v2", "main": ["林昭", "裴恪"], "sub": [["林昭", "沈砚"]], "background": [],
        "domainWeights": {"感情": 2}, "timescale": "长跨度", "families": [["林昭", "林父", "沈砚"]],
        "breakers": [{"who": "裴恪", "by": "别人当面"}],
        "defaultFate": [{"who": "裴恪", "year": 334, "reveal": "传闻", "outcome": "改", "spill": "沈砚"}],
        "calendar": [{"name": "上元灯会", "month": 1, "who": ["林昭", "裴恪"]}, {"name": "秋闱", "month": 8, "year": 331}],
        "objects": [{"name": "玉佩", "holder": "林昭", "passes": [{"year": 331, "to": "裴恪"}], "recognized": {"year": 340, "by": "沈砚"}}]}


def _threads() -> list[dict]:
    return run.load_threads({"schema": "bazi-threads/v2", "threads": [
        {"id": "TH-325-林昭-裴恪-感情", "people": ["林昭", "裴恪"], "domain": "感情", "since": 325, "status": "压",
         "plan": {"year": 343}, "knows": [{"who": "林昭", "since": 325}]}]})


@pytest.fixture(scope="module")
def long_run() -> dict:
    return run.build(_trio(), (324, 346), "林昭", _threads(), casting=CAST, elders=[_elder()])


def test_fate_course_prehistory_and_shelf_life() -> None:
    charts = _trio()
    fd = fate.build(charts, (324, 346), 10)
    assert [p["who"] for p in fd["people"]] == ["沈砚", "林昭", "裴恪"] and fd["elders"] == []
    for c, p in zip(charts, fd["people"]):
        by = matrix._anchor(c)
        tl = timeline.build(c, (324 - by, 356 - by))
        cands = {by + age for age in tl["candidates"]}
        years = [e["year"] for e in p["entries"]]
        assert set(years) <= cands and all(324 <= y <= 356 for y in years)  # 默认下场只取候选年份，窗起到窗后十年
        for e in p["entries"]:
            assert e["id"] == f"DF-{p['who']}-{e['year']}" and e["inWindow"] == (e["year"] <= 346)
            assert e["reveal"][:2] == list(fate._REVEAL_FIRST[e["domain"]]) and sorted(e["reveal"]) == sorted(fate.REVEALS)
            assert p["who"] in e["text"] and "他" not in e["text"]
        # 保质期：窗起那步大运的末年，换运那年原本不准
        step = next(s for s in c["dayun"]["steps"] if s["startAge"] <= 324 - by < s["endAge"])
        assert p["shelfLife"]["coversTo"] == by + step["endAge"] - 1 and p["shelfLife"]["turns"][0] == by + step["endAge"]
        # 前史：窗前的候选年份，六到十二岁的是钉下假话的候选；追上来只在冲年支、伏吟的年份，且对得上领域
        past = {py["year"]: py for py in p["pastYears"]}
        assert all(any(m.startswith(fate.CATCH_MECH) for m in py["mechanisms"]) for py in p["pastYears"])
        for e in p["prehistory"]:
            assert e["year"] < 324 and e["nails"] == (e["age"] in lies.CHILD_AGES)
            for cu in e["catchesUp"]:
                assert cu["year"] in past and e["domain"] in past[cu["year"]]["domains"]
    with pytest.raises(ValueError):
        fate.build([{**charts[0], "calendar": {}}], (324, 346))


def test_elders_catch_up_on_heirs_year_branch_clash(long_run: dict) -> None:
    el = long_run["fate"]["elders"]
    assert [e["who"] for e in el] == ["林父"] and el[0]["heirs"] == ["林昭", "沈砚"]
    heirs_clash = {(py["who"], py["year"]) for p in long_run["fate"]["people"] if p["who"] in ("林昭", "沈砚")
                   for py in p["pastYears"] if any(m.startswith("冲年支") for m in py["mechanisms"])}
    for e in el[0]["prehistory"]:
        assert e["elder"] and not e["nails"] and e["year"] < 324 and e["text"].startswith(f"{e['year']}年")
        assert {(c["who"], c["year"]) for c in e["catchesUp"]} == heirs_clash
    assert heirs_clash  # 这组盘在窗里确有冲年支的年份，上一代的旧账有处追上来


def test_casting_v2_validation() -> None:
    names = ["沈砚", "林昭", "裴恪"]
    ok = run.load_casting(CAST, names, ["林父"])
    assert ok["timescale"] == "长跨度" and ok["breakers"][0]["by"] == "别人当面" and ok["schema"] == "bazi-casting/v2"
    assert run.load_casting({**CAST, "breakers": ["裴恪"]}, names, ["林父"])["breakers"] == [{"who": "裴恪"}]
    v1 = run.load_casting({"schema": "bazi-casting/v1", "main": ["林昭", "裴恪"]}, names)
    assert set(v1) == {"schema", "main", "sub", "background", "domainWeights"}  # 旧编配照旧，不多栏
    bads = [
        {**CAST, "timescale": "中跨度"},
        {**CAST, "breakers": [{"who": "裴恪", "by": "天意"}]},
        {**CAST, "breakers": ["裴恪", {"who": "裴恪"}]},
        {**CAST, "families": [["林昭"]]},
        {**CAST, "families": [["林昭", "无此人"]]},
        {**CAST, "defaultFate": [{"who": "裴恪", "year": 334, "reveal": "托梦"}]},
        {**CAST, "defaultFate": [{"who": "林父", "year": 334}]},  # 上一代没有默认下场
        {**CAST, "defaultFate": [{"who": "裴恪", "year": "三三四"}]},
        {**CAST, "calendar": [{"name": "灯会", "month": 13}]},
        {**CAST, "calendar": [{"month": 1}]},
        {**CAST, "objects": [{"name": "玉佩", "holder": "无此人"}]},
        {**CAST, "objects": [{"name": "玉佩", "holder": "林昭", "recognized": {"year": 340, "by": "无此人"}}]},
    ]
    for bad in bads:
        with pytest.raises(ValueError):
            run.load_casting(bad, names, ["林父"])
    with pytest.raises(ValueError):  # 家族里有上一代，却没给上一代的盘
        run.load_casting(CAST, names)
    with pytest.raises(ValueError):  # 透的那一条不在默认下场年表里
        run.build(_trio(), (324, 346), "林昭", casting={**CAST, "defaultFate": [{"who": "裴恪", "year": 335}]}, elders=[_elder()])
    with pytest.raises(ValueError):  # 上一代与单元客不和推演的命盘重名
        run.build(_trio(), (324, 346), "林昭", elders=[{**_elder(), "name": "林昭"}])


def test_sources_expand(long_run: dict) -> None:
    out = long_run
    pool = set(out["idPool"])
    kinds = {k["kind"] for k in out["sourceKinds"]}
    assert len(kinds) == 10 and {"默认下场到点", "过去追上来", "对手出招", "家人出招", "得知与认出", "局与日历"} <= kinds
    rows = [(c["year"], s) for c in out["cards"] for s in c["sources"]] + [(o["year"], s) for o in out["offCard"] for s in o["sources"]]
    seen = {s["kind"] for _, s in rows}
    assert {"默认下场到点", "过去追上来", "对手出招", "家人出招", "得知与认出", "局与日历"} <= seen
    for year, s in rows:
        assert s["kind"] in kinds and all(i in pool for i in s["ids"])
    # 默认下场：编配透过的那一条带 revealed，书一级的保质期到它为止，之后交给还有默认下场年份的人
    df = [s for y, s in rows if s["kind"] == "默认下场到点"]
    rv = [s for s in df if "revealed" in s]
    assert len(rv) == 1 and rv[0]["who"] == "裴恪" and rv[0]["revealed"] == {"reveal": "传闻", "outcome": "改", "spill": "沈砚"}
    book = out["fate"]["book"]
    assert book["coversTo"] == 334 and all(all(334 < y <= 346 for y in h["years"]) for h in book["handover"])
    # 对手出招：同一人同一年只一条，来由可以并几张卡
    moves = [(y, s["who"]) for y, s in rows if s["kind"] == "对手出招"]
    assert len(moves) == len(set(moves))
    cards = {c["year"]: c for c in out["cards"]}
    for y, s in rows:
        if s["kind"] == "对手出招":
            for a in s["after"]:
                assert a["year"] < y and s["who"] in cards[a["year"]]["present"]
    # 家人出招：同族里他是对方的官杀，才压得到对方头上
    edges = {(e["from"], e["to"]): e for e in matrix.build(_trio())["edges"]}
    fam = [s for y, s in rows if s["kind"] == "家人出招"]
    assert fam and all(edges[(s["target"], s["who"])]["tenGod"] in run.PRESS_GODS for s in fam)
    # 得知：线程上卡时，不在知情里的那一头；物件：到认出那一年为止
    learn = [(y, s) for y, s in rows if s["kind"] == "得知与认出"]
    assert all(s["who"] == "裴恪" for y, s in learn if s["how"] == "线程")
    objs = [(y, s) for y, s in learn if s["how"] == "物件"]
    assert (340, "沈砚") in {(y, s["who"]) for y, s in objs if s["planned"]}
    assert all(331 <= y < 340 and s["holder"] == "裴恪" for y, s in objs if not s["planned"])
    # 钟：年年的灯会不单独把过场年拉进 offCard；秋闱只在 331
    bells = [(y, s["name"]) for y, s in rows if s["kind"] == "局与日历"]
    assert [y for y, n in bells if n == "秋闱"] == [331]
    assert all(any(not s.get("every") for s in o["sources"]) for o in out["offCard"])
    # 卡上的谁碎、两难给谁
    for c in out["cards"]:
        assert "breakers" in c
        assert all(b["who"] == "裴恪" and b["who"] in c["present"] for b in c["breakers"])
        if c["source"] == "林昭":
            assert "dilemmaTo" in c and "林昭" not in c["dilemmaTo"]["who"] and c["dilemmaTo"]["note"] == dilemma._T["use"]
        else:
            assert "dilemmaTo" not in c
    assert out["timescale"] == {"kind": "长跨度", "from": "编配", "years": 23, "note": run.TIMESCALE_NOTE["长跨度"]}
    assert "monthGrid" not in out and "returns" not in out and "guests" not in out
    assert run.check_chain("- 裴恪出招。 ｜溯源 " + rv[0]["ids"][0] + "\n", out) == []


def test_short_span_months_and_guests() -> None:
    out = run.build(_trio(), (331, 332), "林昭", _threads(), casting={**CAST, "timescale": None, "families": [["林昭", "沈砚"]], "defaultFate": [], "objects": []},
                    guests=[_guest()])
    assert out["timescale"]["kind"] == "短跨度" and out["timescale"]["from"] == "窗长推定"
    assert all("months" in c for c in out["cards"])  # 短跨度推演最细到流月
    pool = set(out["idPool"])
    grid = out["monthGrid"]
    assert grid and all(331 <= g["year"] <= 332 and 1 <= g["month"] <= 12 and (g["hits"] or g["bells"]) for g in grid)
    assert all(i in pool for g in grid for h in g["hits"] for i in h["ids"])
    assert {g["year"] for g in grid if "上元灯会" in g["bells"]} == {331, 332}
    g = out["guests"][0]
    assert g["who"] == "客" and g["entry"]["year"] < 331 and g["entry"]["id"] in pool
    assert g["nails"] is None or g["nails"]["age"] in lies.CHILD_AGES
    assert all(x["inWindow"] for x in g["course"]) and len(g["asks"]) == 3
    with pytest.raises(ValueError):  # 谁碎里的单元客没给盘
        run.build(_trio(), (331, 332), "林昭", casting={**CAST, "timescale": None, "breakers": ["客"]}, elders=[_elder()])


def test_return_years() -> None:
    cast = {**CAST, "timescale": "回到关口年", "families": [["林昭", "沈砚"]]}
    out = run.build(_trio(), (324, 346), "林昭", _threads(), casting=cast)
    rs = out["returns"]
    assert rs and all(r["age"] >= min(lies.CHILD_AGES) and r["year"] < 324 and r["ids"][0] in out["idPool"] for r in rs)
    for n in ("沈砚", "林昭", "裴恪"):
        assert 1 <= sum(r["who"] == n for r in rs) <= 3
    assert "monthGrid" not in out


def test_example_has_fate_and_sources_without_casting() -> None:
    out = run.build(_trio(), (324, 346), "林昭", run.load_threads({"schema": "bazi-threads/v1", "threads": []}))
    assert out["timescale"]["from"] == "窗长推定" and out["timescale"]["kind"] == "长跨度"
    assert [p["who"] for p in out["fate"]["people"]] == ["沈砚", "林昭", "裴恪"] and "book" not in out["fate"]
    assert all("sources" in c and "breakers" not in c and "dilemmaTo" not in c for c in out["cards"])
    assert not any(s["kind"] in ("家人出招", "局与日历", "得知与认出") for c in out["cards"] for s in c["sources"])


def test_check_chain_sources_and_default_fate(long_run: dict) -> None:
    from bazi_core.tests.test_drama_layer import _chain

    out = long_run
    th = _threads()
    src = {325: "对手出招、得知与认出；上一回她驳了他，这回他出招", 331: "对手出招、旁人求上门；他找上门来", 334: "默认下场到点；原本他这一年要出事"}
    extra = {325: ["- 默认下场：DF-裴恪-334 透，旁人的判断"], 334: ["- 默认下场：DF-裴恪-334改，余波落在沈砚身上"]}
    good = run.check_chain_drama(_chain(out, src=src, extra=extra, gaps=["过场 327：DF-沈砚-327 应验，一句带过"]), out, th)
    assert good["problems"] == [], good["problems"]
    st = good["stats"]
    assert st["sources"]["对手出招"] == 2 and st["sources"]["旁人求上门、班底派活"] == 1 and st["sources"]["默认下场到点"] == 1
    assert st["defaultFate"] == {"透": 1, "应验": 1, "改": 1}
    warn = [w["problem"] for w in good["warnings"]]
    assert any("325年的卡上没有对手出招" in w for w in warn)  # 325 的卡上没有对手出招
    assert any("没透就兑现" in w for w in warn)  # 过场 327 那一条没透
    assert any("连着三个热年只有热年出事" in w for w in warn)
    assert not any("编配定的是" in w for w in warn)
    # 编配透的那一条：没写透、没写兑现都是问题；写反了报 warn
    bare = run.check_chain_drama(_chain(out, src=src), out, th)["problems"]
    assert any("没写哪一年透" in p["problem"] for p in bare) and any("没写应验还是改" in p["problem"] for p in bare)
    flipped = run.check_chain_drama(_chain(out, src=src, extra={**extra, 334: ["- 默认下场：DF-裴恪-334 应验"]}), out, th)
    assert flipped["problems"] == [] and any("编配定的是改" in w["problem"] for w in flipped["warnings"])
    # 认不得的源、没写为什么、编号不在默认下场里、编号后面没跟状态
    bad = run.check_chain_drama(_chain(out, src={324: "天意；老天安排", 325: "对手出招"},
                                       extra={**extra, 330: ["- 默认下场：DF-裴恪-333 透；DF-林昭-331"]}), out, th)["problems"]
    msgs = [p["problem"] for p in bad]
    assert any("天意 不是十种源之一" in m for m in msgs) and any("325年源要在分号后写为什么" in m for m in msgs)
    assert any(p.get("id") == "DF-裴恪-333" and "不在推演的默认下场里" in p["problem"] for p in bad)
    assert any(p.get("id") == "DF-林昭-331" and "跟 透、应验、改" in p["problem"] for p in bad)
    assert run.parse_kinds("旁人求上门、班底派活、局与日历；因为") == (["旁人求上门、班底派活", "局与日历"], [], "因为")
