"""戏剧层（DESIGN-戏剧层 第 4、7、9、11 节）：编配候选、推演读编配（背景的人不当源、领域配权、事件候选、线程四态与次数、高潮候选）、
事件链新写法的检查、戏用页的检查与渲染、三张表的新栏、戏剧层校核卡。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from bazi_core import casting, chart, dilemma, ensemble_run as run

ROOT = Path(__file__).resolve().parents[3]
TABLES = ROOT / "scripts" / "bazi_core" / "tables"
TEN = ("正官", "七杀", "正财", "偏财", "正印", "偏印", "食神", "伤官", "比肩", "劫财")


def _trio() -> list[dict]:
    a = chart.chart_from_pillars("甲申", "壬申", "乙巳", "戊寅", "male", story_epoch=300, name="沈砚")
    b = chart.chart_from_pillars("庚寅", "壬午", "辛酉", "戊戌", "female", start_age_years=5, story_epoch=306, name="林昭")
    c = chart.chart_from_pillars("丁亥", "壬寅", "己卯", "甲子", "male", story_epoch=303, name="裴恪")
    return [a, b, c]


CASTING = {"schema": "bazi-casting/v1", "main": ["林昭", "裴恪"], "sub": [], "background": ["沈砚"],
           "domainWeights": {"感情": 2, "六亲": 0.5}}


def _threads() -> list[dict]:
    return run.load_threads({"schema": "bazi-threads/v2", "threads": [
        {"id": "TH-331-林昭-裴恪-感情", "people": ["林昭", "裴恪"], "domain": "感情", "since": 331, "status": "压",
         "plan": {"year": 343}, "open": "暗", "knows": [{"who": "林昭", "since": 331}]},
        {"id": "TH-325-裴恪-林昭-感情", "people": ["裴恪", "林昭"], "domain": "感情", "since": 325, "status": "余波"},
    ]})


@pytest.fixture(scope="module")
def out() -> dict:
    return run.build(_trio(), (324, 346), "林昭", _threads(), casting=CASTING)


def test_tables_have_drama_columns() -> None:
    rt = json.loads((TABLES / "response_tendency.json").read_text(encoding="utf-8"))
    assert {r["tenGod"] for r in rt["rows"]} == set(TEN)
    assert all(r["nearOpen"] and r["awayOpen"] and r["near"] and r["away"] for r in rt["rows"])
    assert any(m["条件"] == "这条线第三回上卡" for m in rt["modifiers"])
    lies = json.loads((TABLES / "lies.json").read_text(encoding="utf-8"))["sections"][0]
    assert "breaker" in {c["key"] for c in lies["columns"]} and all(r["breaker"] for r in lies["rows"])
    dm = json.loads((TABLES / "drama_means.json").read_text(encoding="utf-8"))
    assert dm["format"] == "narrative-table/v1" and len(dm["rows"]) == 20
    assert {(r["tenGod"], r["state"]) for r in dm["rows"]} == {(g, s) for g in TEN for s in ("旺", "弱")}
    assert all(r["want"] and r["means"] and r["limit"] and r["breaking"] for r in dm["rows"])
    for t in (rt, dm):  # 表里不给台词
        assert not any(ch in json.dumps(t["rows"], ensure_ascii=False) for ch in "“”")


def test_casting_candidates() -> None:
    c = casting.build(_trio(), (324, 346))
    assert c["schema"] == "bazi-casting-candidates/v1" and len(c["pairs"]) == 3
    for p in c["pairs"]:
        assert p["kind"] in ("对子", "只撞不拴", "同盟", "淡")
        assert p["tension"] == round(sum(x["points"] for x in p["tensionWhy"]), 1)
        assert all(i.startswith("E-") for w in p["tensionWhy"] + p["bondWhy"] for i in w["ids"])
        assert p["active"] in p["people"] + [None]
    tensions = [p["tension"] for p in c["pairs"] if p["kind"] == c["pairs"][0]["kind"]]
    assert tensions == sorted(tensions, reverse=True)
    assert casting.build(_trio(), (324, 346)) == c


def test_background_is_never_source_and_weights_move_domains(out: dict) -> None:
    plain = run.build(_trio(), (324, 346), "林昭")
    assert any(c["source"] == "沈砚" for c in plain["cards"])
    assert all(c["source"] != "沈砚" for c in out["cards"])
    assert any(c.get("driver") == "沈砚" for c in out["cards"])
    assert out["casting"]["main"] == ["林昭", "裴恪"]
    for c in out["cards"]:
        for x in c["candidates"]:
            if x["kind"] == "个人":
                assert x["who"] != "沈砚"
            else:
                assert set(x["people"]) != {"沈砚"} and len(x["sides"]) == 2
                assert x["line"] == ("主线" if set(x["people"]) == {"林昭", "裴恪"} else "旁线")
        scores = [x["score"] for x in c["candidates"]]
        assert scores == sorted(scores, reverse=True)
        assert set(i for x in c["candidates"] for i in x["ids"]) <= set(out["idPool"])
    y = {"age": 1, "pillar": "甲子", "mechanisms": ["冲提纲"], "domains": [
        {"domain": "六亲", "via": ["x"], "weight": 2, "strong": True}, {"domain": "感情", "via": ["y"], "weight": 2, "strong": True}]}
    assert dilemma.rewrite_year(y, "L-1-甲子")["primary"]["domain"] == "六亲"
    assert dilemma.rewrite_year(y, "L-1-甲子", {"感情": 2, "六亲": 0.5})["primary"]["domain"] == "感情"
    assert dilemma.rewrite_year(y, "L-1-甲子", None, avoid="六亲")["primary"]["domain"] == "感情"


def test_thread_pressure_escalates_on_third_surfacing(out: dict) -> None:
    seen = [(c["year"], t["pressure"], t["escalate"]) for c in out["cards"] for t in c["threads"] if t["id"] == "TH-331-林昭-裴恪-感情"]
    assert [p for _, p, _ in seen] == list(range(1, len(seen) + 1)) and len(seen) >= 3
    assert [e for _, _, e in seen] == [p >= 3 for _, p, _ in seen]
    year = next(y for y, _, e in seen if e)
    card = next(c for c in out["cards"] if c["year"] == year)
    pair = {"林昭", "裴恪"}
    if card["source"] in pair:
        other = next(t for t in card["tendencies"] if t["who"] in pair)
        assert "这条线第三回上卡" in [m["条件"] for m in other["modifiers"]] and other["textOpen"]
    th = next(t for c in out["cards"] for t in c["threads"])
    assert th["status"] == "压" and th["plan"] == {"year": 343} and th["open"] == "暗"
    assert all(t["id"] != "TH-325-裴恪-林昭-感情" for c in out["cards"] for t in c["threads"])


def test_climax_candidates_per_volume(out: dict) -> None:
    for v in out["outline"]["volumes"]:
        cc = v["climaxCandidates"]
        assert len(cc) <= 3 and all(x["year"] in v["hotYears"] and x["why"] for x in cc)
        assert [x["score"] for x in cc] == sorted((x["score"] for x in cc), reverse=True)


def test_casting_and_threads_validation() -> None:
    names = ["沈砚", "林昭", "裴恪"]
    for bad in ({**CASTING, "schema": "x"}, {**CASTING, "main": ["林昭"]}, {**CASTING, "background": ["林昭"]},
                {**CASTING, "domainWeights": {"爱情": 2}}, {**CASTING, "domainWeights": {"感情": 0}},
                {**CASTING, "sub": [["林昭", "沈砚"], ["裴恪", "沈砚"], ["林昭", "裴恪"]]}, {**CASTING, "main": ["林昭", "无此人"]}):
        with pytest.raises(ValueError):
            run.load_casting(bad, names)
    base = {"id": "TH-1-a-b-感情", "people": ["a", "b"], "domain": "感情", "since": 1, "status": "埋"}
    assert run.load_threads({"schema": "bazi-threads/v2", "threads": [{**base, "plan": {"mute": "留给读者猜"}}]})
    for bad in ({**base, "plan": {"year": "三年后"}}, {**base, "open": "半明"}, {**base, "knows": [{"who": "a"}]}, {**base, "status": "挂着"}):
        with pytest.raises(ValueError):
            run.load_threads({"schema": "bazi-threads/v2", "threads": [bad]})


def _chain(out: dict, *, bone: bool = True, open_step: bool = True, gap: bool = True, src: dict | None = None,
           extra: dict | None = None, gaps: list[str] | None = None) -> str:
    """src：年份 → 源一栏；extra：年份 → 多加的字段行；gaps：过场行，接在最后。"""
    lines = ["# 群像推演", ""]
    for v in out["outline"]["volumes"]:
        lines += [f"## 卷 {v['stage']}", ""]
        if bone:
            lines += ["### 骨", "", "- 为哪一人一事：林昭的婚约", "- 起：一", "- 承：二", "- 转：三", "- 合：四",
                      "- 高潮年：" + str((v["climaxCandidates"] or [{"year": 0}])[0]["year"]), "- 响：无，压到下一卷", "- 清算：无",
                      "- 卷末的问题：她回不回去", ""]
        for i, yr in enumerate(v["hotYears"]):
            mark = "（明）" if open_step else "（暗）"
            lines += [f"### {yr} 年：一件事", "", f"- 牌面：谁在什么位置 ｜溯源 Q-{yr}-林昭", "- 因：上一回她的选择",
                      "- 源：" + (src or {}).get(yr, "热年出事；这一年盘上撞得最狠"), *(extra or {}).get(yr, []),
                      "- 事件：边上的事", "- 步：",
                      f"  1. 她去了。以为：他会留。实际：他走了。{mark} ｜溯源 Q-{yr}-林昭" if gap else f"  1. 她去了。{mark}",
                      "  2. 他回了一句。以为：她会退。实际：她没退。（暗）",
                      "- 选择：她选了去", "- 知情：无", "- 线程：TH-331-林昭-裴恪-感情 压",
                      "- 主线温度：" + "靠离撞退"[i % 4] + "，因为这一年", "- 读者：等着知道他回不回", ""]
    lines += gaps or []
    return "\n".join(lines)


def test_check_chain_drama(out: dict) -> None:
    th = _threads()
    good = run.check_chain_drama(_chain(out), out, th)
    assert good["problems"] == [], good["problems"]
    assert good["stats"]["years"] == len(out["hotYears"]) and good["stats"]["openSteps"] == len(out["hotYears"])
    assert run.check_chain(_chain(out), out) == []
    no_bone = run.check_chain_drama(_chain(out, bone=False), out, th)["problems"]
    assert any("没有骨" in p["problem"] for p in no_bone)
    no_gap = run.check_chain_drama(_chain(out, gap=False), out, th)["problems"]
    assert any("以为" in p["problem"] for p in no_gap)
    covert = run.check_chain_drama(_chain(out, open_step=False), out, th)["problems"]
    assert any("该升级或清算了" in p["problem"] and p.get("id") == "TH-331-林昭-裴恪-感情" for p in covert)
    unplanned = [{**t, "plan": None} if t["status"] == "压" else t for t in th]
    assert any("没写哪一年响" in p["problem"] for p in run.check_chain_drama(_chain(out), out, unplanned)["problems"])
    short = _chain(out).split("### " + str(out["hotYears"][-1]))[0]
    assert any("没有一节" in p["problem"] for p in run.check_chain_drama(short, out, th)["problems"])
    nosrc = _chain(out).replace("- 源：热年出事；这一年盘上撞得最狠\n", "", 1)
    assert any("缺源" in p["problem"] for p in run.check_chain_drama(nosrc, out, th)["problems"])
    flat = _chain(out).replace("主线温度：离", "主线温度：靠").replace("主线温度：撞", "主线温度：靠").replace("主线温度：退", "主线温度：靠")
    assert any("一直帐" in p["problem"] for p in run.check_chain_drama(flat, out, th)["problems"])


def _node(args: list[str]) -> tuple[int, list[dict]]:
    r = subprocess.run(["node", str(ROOT / "scripts" / "check-drama.js"), *args], capture_output=True, text=True, encoding="utf-8")
    return r.returncode, [json.loads(x) for x in r.stdout.splitlines() if x.strip()]


def _page() -> dict:
    ex = ROOT / "examples" / "林昭" / "命盘" / "林昭.json"
    ids = [f["id"] for f in json.loads(ex.read_text(encoding="utf-8"))["features"]]
    t = next(i for i in ids if i.startswith("T-"))
    u = next(i for i in ids if i.startswith("U-"))
    li = next(i for i in ids if i.startswith("LI-"))

    def one(text: str, **kw) -> dict:
        return {"text": text, "origin": "盘", "sources": [t], **kw}

    return {"schema": "bazi-drama-page/v1", "name": "林昭", "chart": str(ex), "pronoun": "她", "asks": [
        {"ask": "他要什么", "lines": [{"text": "那一纸退掉的婚约重新作数", "origin": "定", "ref": "编配 对子 林昭、裴恪"}]},
        {"ask": "谁挡着", "lines": [one("裴恪自己")]},
        {"ask": "他怎么去要", "lines": [one("当面驳，一句顶一句"), one("不肯开口求人")]},
        {"ask": "他信的那句假话", "lines": [{"text": "听话就不会挨打", "origin": "盘", "sources": [li]}]},
        {"ask": "他真正缺的", "lines": [{"text": "一个托得住她的地方", "origin": "盘", "sources": [u]}]},
        {"ask": "碰哪里会疼", "lines": [
            one("有人当面说她不配", line="怕被判", beat="碰线"), one("先拿道理盖住", line="怕被判", beat="盖法"),
            one("第三回被当众说破，她开口求了人", line="怕被判", beat="破")]},
        {"ask": "他瞒着什么", "lines": []},
        {"ask": "他怎么说话", "lines": [one("断语多，句子短")]},
        {"ask": "别人拿他当什么", "lines": [one("一把不肯收的刀")]},
        {"ask": "他从哪儿走到哪儿", "lines": [{"text": "从驳人到肯求人", "origin": "定", "ref": "编配 前提句"}]},
    ]}


def test_check_drama_page(tmp_path: Path) -> None:
    f = tmp_path / "林昭.戏用页.json"
    page = _page()
    f.write_text(json.dumps(page, ensure_ascii=False), encoding="utf-8")
    code, rows = _node([str(f)])
    assert code == 0, rows
    assert rows[-1]["breaks"] == 1 and rows[-1]["decided"] == 2 and rows[-1]["errors"] == 0
    assert any(r.get("level") == "info" and r.get("ask") == "他瞒着什么" for r in rows)
    code, rows = _node([str(f), "--final"])
    assert code == 1 and any(r.get("ask") == "他瞒着什么" and r.get("level") == "error" for r in rows)

    def broken(mut) -> list[dict]:
        p = _page()
        mut(p)
        f.write_text(json.dumps(p, ensure_ascii=False), encoding="utf-8")
        code, rows = _node([str(f)])
        assert code == 1
        return rows

    by = lambda p, ask: next(a for a in p["asks"] if a["ask"] == ask)  # noqa: E731
    assert any("没有一条破" in r["problem"] for r in broken(lambda p: by(p, "碰哪里会疼")["lines"].pop()))
    assert any("不给台词" in r["problem"] for r in broken(lambda p: by(p, "他怎么说话")["lines"][0].update(text="她说“不去”")))
    assert any("编号找不到" in r["problem"] for r in broken(lambda p: by(p, "谁挡着")["lines"][0].update(sources=["T-无此编号"])))
    assert any("ref" in r["problem"] for r in broken(lambda p: by(p, "他要什么")["lines"][0].update(ref="")))
    assert any("缺席" in r["problem"] for r in broken(lambda p: p["asks"].pop(4)))
    assert any("次序" in r["problem"] for r in broken(lambda p: p["asks"].reverse()))
    assert any("origin" in r["problem"] for r in broken(lambda p: by(p, "谁挡着")["lines"][0].update(origin="猜")))


def test_check_drama_belief_by_and_extras(tmp_path: Path) -> None:
    f = tmp_path / "林昭.戏用页.json"
    by = lambda p, ask: next(a for a in p["asks"] if a["ask"] == ask)  # noqa: E731

    def run_page(mut) -> tuple[int, list[dict]]:
        p = _page()
        mut(p)
        f.write_text(json.dumps(p, ensure_ascii=False), encoding="utf-8")
        return _node([str(f)])

    def creed_no_break(p: dict) -> None:  # 信条页：不碎，没有破只报 info
        p["belief"] = "信条"
        by(p, "碰哪里会疼")["lines"].pop()

    code, rows = run_page(creed_no_break)
    assert code == 0 and rows[-1]["belief"] == "信条" and rows[-1]["breaks"] == 0
    assert any(r.get("level") == "info" and "信条页没有破" in r["problem"] for r in rows)
    code, rows = run_page(lambda p: p.update(belief="谎"))
    assert code == 1 and any("belief" in r["problem"] for r in rows)
    code, rows = run_page(lambda p: by(p, "碰哪里会疼")["lines"][-1].update(by="物证"))
    assert code == 0, rows
    code, rows = run_page(lambda p: by(p, "碰哪里会疼")["lines"][-1].update(by="天意"))
    assert code == 1 and any("by 应为" in r["problem"] for r in rows)
    code, rows = run_page(lambda p: by(p, "碰哪里会疼")["lines"][0].update(by="自己"))
    assert code == 1 and any("只有破那一拍" in r["problem"] for r in rows)

    def with_extras(p: dict) -> None:
        p["asks"] += [
            {"ask": "他被叫什么", "lines": [{"text": "他叫她全名，定亲那一场改叫小名", "origin": "定", "ref": "编配 对子 林昭、裴恪"}]},
            {"ask": "他信错了谁", "lines": []},
            {"ask": "他怎么被记住", "lines": [{"text": "口头禅：“不必”", "origin": "定", "ref": "作者定"}]},
        ]

    code, rows = run_page(with_extras)
    assert code == 0 and rows[-1]["extras"] == 2, rows

    def two_quotes(p: dict) -> None:
        with_extras(p)
        p["asks"][-1]["lines"].append({"text": "另一句“算了”", "origin": "定", "ref": "作者定"})

    code, rows = run_page(two_quotes)
    assert code == 1 and any("只许一行带引号" in r["problem"] for r in rows)
    code, rows = run_page(lambda p: p["asks"].insert(0, {"ask": "他被叫什么", "lines": []}))
    assert code == 1 and any("次序" in r["problem"] for r in rows)

    def duels(p: dict) -> None:  # 交手一问：一对一行，不算附问字数，单行过长报 warn
        rows = [{"text": f"对第{i}个人：对方拿规矩盖，她拿账逼；被碰到旧账那根线，先笑后算" + "细" * 30, "origin": "定", "ref": "编配 对子"}
                for i in range(12)]
        rows.append({"text": "长" * 120, "origin": "定", "ref": "编配 对子"})
        p["asks"].append({"ask": "他跟谁怎么交手", "lines": rows})

    code, rows = run_page(duels)
    assert code == 0 and rows[-1]["extraChars"] == 0, rows
    assert sum(1 for r in rows if r.get("level") == "warn" and "一对一行" in r["problem"]) == 1


def test_drama_render(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import drama_render

    page = _page()
    reader = drama_render.render(page, author=False)
    author = drama_render.render(page, author=True)
    assert "## 一、她要什么" in reader and "## 十、她从哪儿走到哪儿" in reader and "他" not in reader.split("## 一、")[0]
    assert "｜盘" not in reader and "｜定" not in reader and "T-" not in reader
    assert "｜定 编配 对子 林昭、裴恪" in author and "｜盘 " in author
    assert reader.index("碰线：") < reader.index("盖法：") < reader.index("破：")
    assert "（待补充）" in reader
    assert "## 附" not in reader  # 附问没答不渲染
    page["belief"] = "信条"
    next(a for a in page["asks"] if a["ask"] == "碰哪里会疼")["lines"][-1]["by"] = "别人当面"
    page["asks"].append({"ask": "他被叫什么", "lines": [{"text": "他叫她全名", "origin": "定", "ref": "编配"}]})
    creed = drama_render.render(page, author=False)
    assert "## 四、她信的那句话" in creed and "破（别人当面）：" in creed and "## 附：她被叫什么" in creed


def test_template_page_and_casting_shapes() -> None:
    tpl = ROOT / "references" / "戏剧层" / "模板"
    page = json.loads((tpl / "戏用页.json").read_text(encoding="utf-8"))
    assert [a["ask"] for a in page["asks"]] == ["他要什么", "谁挡着", "他怎么去要", "他信的那句假话", "他真正缺的", "碰哪里会疼",
                                                "他瞒着什么", "他怎么说话", "别人拿他当什么", "他从哪儿走到哪儿",
                                                "他被叫什么", "他知道哪一层", "他信错了谁", "他对谁演什么", "他跟谁怎么交手", "他独一份的是什么", "他怎么被记住"]
    cast = json.loads((tpl / "编配.json").read_text(encoding="utf-8"))
    assert run.load_casting(cast, ["甲", "乙", "丙", "丁"])["main"] == ["甲", "乙"]
    chain = (tpl / "推演.md").read_text(encoding="utf-8")
    assert all(f"- {k}：" in chain for k in run.BONE_FIELDS + run.YEAR_FIELDS)


def test_drama_cards_pass_quote_check() -> None:
    for name, n in (("李渔_结构.md", 7), ("金圣叹_读法.md", 19)):
        card = ROOT / "references" / "戏剧层" / "校核" / name
        corpus = ROOT / "references" / "校核" / "语料"
        if not any(corpus.glob("*.txt")):
            pytest.skip("语料目录不在（公开库不带语料）")
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_cards.py"), str(card), "--json"], capture_output=True, cwd=ROOT)
        rep = json.loads(r.stdout.decode("utf-8"))
        assert rep["ok"] and rep["cards"] == n and rep["unmatched"] == [], rep["unmatched"]
    asks = (ROOT / "references" / "戏剧层" / "问法.md").read_text(encoding="utf-8")
    ids = set()
    for f in (ROOT / "references" / "戏剧层" / "校核").glob("*.md"):
        ids |= {ln[4:].split()[0] for ln in f.read_text(encoding="utf-8").splitlines() if ln.startswith("### ")}
    import re
    cited = set(re.findall(r"((?:李渔|金圣叹)-[^；）\s]+)", asks))
    assert cited and cited <= ids, cited - ids
