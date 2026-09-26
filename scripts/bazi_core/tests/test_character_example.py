"""薄 M4 切片的端到端：命盘 features 索引稳定、样例人物档案过契约与溯源检查、读者本过去术语检查、作者本目录反向自检命中。"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from bazi_core import chart

ROOT = Path(__file__).resolve().parent.parent.parent.parent
EXAMPLE = ROOT / "examples" / "沈砚"
PY = sys.executable


def test_features_index_shape() -> None:
    c = chart.chart_from_pillars("甲申", "壬申", "乙巳", "戊寅", "male", story_epoch=300, name="沈砚")
    c["liunian"] = [chart.liunian(c, 30)]
    f = chart.features(c)
    ids = [x["id"] for x in f]
    assert len(ids) == len(set(ids)) and len(ids) > 80
    prefixes = {i.split("-")[0] for i in ids}
    assert {"P", "DM", "T", "H", "G", "S", "Y", "R", "N", "NT", "C", "D", "L", "IN", "IM", "LI"} <= prefixes
    assert "G-正印格" in ids and "S-中和" in ids and "L-30-甲寅" in ids and "NT-驿马-04-时" in ids
    assert all(x["text"] and x["kind"] for x in f)


def test_example_chart_matches_regenerated() -> None:
    saved = json.loads((EXAMPLE / "命盘" / "沈砚.json").read_text(encoding="utf-8"))
    c = chart.chart_from_pillars("甲申", "壬申", "乙巳", "戊寅", "male", story_epoch=300, name="沈砚")
    c["liunian"] = [chart.liunian(c, 30)]
    assert {x["id"] for x in saved["features"]} == {x["id"] for x in chart.features(c)}


@pytest.mark.skipif(shutil.which("node") is None, reason="需要 node")
def test_example_character_passes_checks(tmp_path: Path) -> None:
    doc = EXAMPLE / "人物" / "沈砚.json"
    r = subprocess.run(["node", str(ROOT / "scripts" / "check-character.js"), str(doc), "--timeline", str(EXAMPLE / "命盘" / "沈砚.年表.json"), "--summary"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout
    s = json.loads(r.stdout.strip().splitlines()[-1])
    assert s["problems"] == 0 and s["traits"] == s["sourced"] >= 20 and s["stages"] == 3
    # 不带年表时阶段卡的编号必须报找不到
    r = subprocess.run(["node", str(ROOT / "scripts" / "check-character.js"), str(doc), "--summary"], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 1
    # 读者本渲染后零 error
    out = tmp_path / "读者本.md"
    r = subprocess.run([PY, str(ROOT / "scripts" / "character_render.py"), str(doc), "--reader", "--out", str(out)],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    r = subprocess.run(["node", str(ROOT / "scripts" / "check-terms.js"), str(out), "--summary"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout
    assert json.loads(r.stdout.strip().splitlines()[-1])["errors"] == 0
    # 作者本目录反向自检必须命中
    r = subprocess.run(["node", str(ROOT / "scripts" / "check-terms.js"), str(EXAMPLE / "命盘"), "--expect-hits", "--summary"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0


@pytest.mark.skipif(shutil.which("node") is None, reason="需要 node")
def test_character_checker_catches_bad_source(tmp_path: Path) -> None:
    doc = json.loads((EXAMPLE / "人物" / "沈砚.json").read_text(encoding="utf-8"))
    doc["sections"][0]["traits"][0]["sources"] = ["NT-不存在-99-年"]
    del doc["sections"][-1]  # 可选段落删掉不算问题
    doc["sections"] = [s for s in doc["sections"] if s["title"] != "秘密"]  # 必备段落缺席算问题
    p = tmp_path / "人物" / "沈砚.json"
    p.parent.mkdir()
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run(["node", str(ROOT / "scripts" / "check-character.js"), str(p), "--chart", str(EXAMPLE / "命盘" / "沈砚.json"),
                        "--timeline", str(EXAMPLE / "命盘" / "沈砚.年表.json")], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 1
    problems = [json.loads(x)["problem"] for x in r.stdout.strip().splitlines() if not json.loads(x).get("summary")]
    assert any("找不到" in x for x in problems) and any("缺席" in x for x in problems)


@pytest.mark.skipif(shutil.which("node") is None, reason="需要 node")
def test_character_checker_guards_emotion_beats(tmp_path: Path) -> None:
    """情绪过程段（2026-09-25）：beat 只认四拍、碰线要落到线上、身体先动要引体感与材质、不许带引号台词、至少碰线与盖法各一。"""
    doc = json.loads((EXAMPLE / "人物" / "沈砚.json").read_text(encoding="utf-8"))
    sec = next(s for s in doc["sections"] if s["title"] == "情绪过程")
    assert {t["beat"] for t in sec["traits"]} == {"碰线", "身体先动", "盖法", "余波"}
    sec["traits"] = [
        {"beat": "起承转合", "text": "拍名不对", "sources": ["DM"]},
        {"beat": "碰线", "text": "没落到线上", "sources": ["T-月干-正印"]},
        {"beat": "身体先动", "text": "没引体感", "sources": ["T-月干-正印"]},
        {"beat": "余波", "text": "他会说“这事得问问”", "sources": ["DM"]},
    ]
    doc["sections"][0]["traits"][0]["beat"] = "碰线"  # 别的段带 beat 也报
    speech = next(s for s in doc["sections"] if s["title"] == "说话方式")
    speech["traits"][0]["text"] += "，压人的那句是“你觉得呢”"  # 说话方式段一样不给引号台词（作者定扩，2026-09-25）
    doc["sections"].append({"title": "口头禅与标志动作", "traits": [{"text": "口头禅：这事得问问。", "sources": ["DM"]}]})  # 已废的段要报
    p = tmp_path / "人物" / "沈砚.json"
    p.parent.mkdir()
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    run = lambda: subprocess.run(["node", str(ROOT / "scripts" / "check-character.js"), str(p), "--chart", str(EXAMPLE / "命盘" / "沈砚.json"),
                                  "--timeline", str(EXAMPLE / "命盘" / "沈砚.年表.json")], capture_output=True, text=True, encoding="utf-8")
    r = run()
    assert r.returncode == 1
    problems = [json.loads(x)["problem"] for x in r.stdout.strip().splitlines() if not json.loads(x).get("summary")]
    assert any("beat 应为" in x for x in problems) and any("碰线要落到" in x for x in problems) and any("身体先动要引" in x for x in problems)
    assert any("缺盖法" in x for x in problems) and any("只有情绪过程段" in x for x in problems)
    quoted = [x for x in problems if "不给台词" in x]
    assert any(x.startswith("情绪过程") for x in quoted) and any(x.startswith("说话方式") for x in quoted)
    assert any("已废" in x for x in problems)
    # 渲染带拍名前缀；读者本一样带
    import character_render as cr
    good = json.loads((EXAMPLE / "人物" / "沈砚.json").read_text(encoding="utf-8"))
    text = cr.render(good, reader=True)
    assert "- 碰线：" in text and "- 身体先动：" in text and "- 盖法：" in text and "- 余波：" in text


@pytest.mark.skipif(shutil.which("node") is None, reason="需要 node")
def test_character_checker_requires_yunqi_core_source(tmp_path: Path) -> None:
    """五运六气主次（DESIGN 7.4 交感）：引了 YQ- 的特质要引到体（岁运）或主（为纲那一头），只引背景与修正要报。"""
    c = chart.chart_from_pillars("甲申", "壬申", "乙巳", "戊寅", "male", story_epoch=300, name="沈砚")
    c["liunian"] = [chart.liunian(c, 30)]
    c["features"] = chart.features(c)
    (tmp_path / "命盘").mkdir()
    (tmp_path / "命盘" / "沈砚.json").write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")
    doc = json.loads((EXAMPLE / "人物" / "沈砚.json").read_text(encoding="utf-8"))
    doc["sections"] = [s for s in doc["sections"] if s["title"] != "阶段状态"] + [{"title": "阶段状态", "stages": []}]
    for s in doc["sections"]:
        for t in s.get("traits", []):
            t["sources"] = [x for x in t["sources"] if not x.startswith("D-")]
            if t.get("layer") == "走向":
                t["layer"] = "底色"
    traits = doc["sections"][0]["traits"]
    body = next(t for t in traits if any(x.startswith("YQ-") for x in t["sources"]))
    body["sources"] = ["DM", "YQ-司天-少阳相火", "YQ-加临-主生客"]  # 只引背景与修正
    (tmp_path / "人物").mkdir()
    p = tmp_path / "人物" / "沈砚.json"
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    run = lambda: subprocess.run(["node", str(ROOT / "scripts" / "check-character.js"), str(p), "--chart", str(tmp_path / "命盘" / "沈砚.json")],
                                 capture_output=True, text=True, encoding="utf-8")
    r = run()
    problems = [json.loads(x)["problem"] for x in r.stdout.strip().splitlines() if not json.loads(x).get("summary")]
    assert r.returncode == 1 and any("只引了背景或修正" in x and "YQ-在泉-厥阴风木" in x for x in problems), r.stdout
    # 引到为纲那一头就过
    body["sources"] = ["DM", "YQ-在泉-厥阴风木", "YQ-加临-主生客"]
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    r = run()
    problems = [json.loads(x)["problem"] for x in r.stdout.strip().splitlines() if not json.loads(x).get("summary")]
    assert not any("只引了背景或修正" in x for x in problems), r.stdout


def test_shensha_from_two_bases_merge_into_one_feature() -> None:
    # 丁丑 癸卯 辛酉 己丑：华盖年支起、日支起都落年时两柱，将星两种起法都落日柱；编号不得重复
    from datetime import datetime
    from zoneinfo import ZoneInfo
    c = chart.chart_from_civil(datetime(1997, 3, 20, 2, 0, tzinfo=ZoneInfo("Asia/Shanghai")), "male", None, False, None)
    assert [c["fourPillars"][k] for k in ("year", "month", "day", "hour")] == ["丁丑", "癸卯", "辛酉", "己丑"]
    f = {x["id"]: x["text"] for x in chart.features(c)}
    assert len(f) == len(chart.features(c))
    assert f["N-华盖-年"] == "年柱华盖（年支丑；日支酉（日支起））"
    assert "年支丑" in f["N-将星-日"] and "日支起" in f["N-将星-日"]


def test_cli_accepts_several_ages() -> None:
    r = subprocess.run([PY, "-m", "bazi_core.chart", "--pillars", "甲申", "壬申", "乙巳", "戊寅", "--gender", "male",
                        "--epoch", "300", "--age", "30", "8", "30"],
                       capture_output=True, cwd=ROOT / "scripts")
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    c = json.loads(r.stdout.decode("utf-8"))
    assert [x["age"] for x in c["liunian"]] == [8, 30]
    ids = {x["id"] for x in c["features"]}
    assert {"L-8-" + c["liunian"][0]["pillar"], "L-30-甲寅"} <= ids


@pytest.mark.skipif(shutil.which("node") is None, reason="需要 node")
def test_setting_card_contract_render_and_period_aware_terms(tmp_path: Path) -> None:
    """设定卡（DESIGN 3.6）：检查器查 period、world 与不认识的槽位；渲染只进作者本；去术语检查的时代措辞组按设定卡的 period 开关；
    现代样例 沈砚.现代 与 沈砚 同盘同编号，过契约检查，读者本零 error 零 warn。"""
    sys.path.insert(0, str(ROOT / "scripts"))
    import character_render as cr
    doc = json.loads((EXAMPLE / "人物" / "沈砚.json").read_text(encoding="utf-8"))
    assert doc["setting"]["period"] == "古代" and doc["setting"]["world"]
    checker = [str(ROOT / "scripts" / "check-character.js")]
    chart_args = ["--chart", str(EXAMPLE / "命盘" / "沈砚.json"), "--timeline", str(EXAMPLE / "命盘" / "沈砚.年表.json")]

    def problems(d: dict) -> list[str]:
        p = tmp_path / "x.json"
        p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run(["node", *checker, str(p), *chart_args], capture_output=True, text=True, encoding="utf-8")
        return [json.loads(x)["problem"] for x in r.stdout.strip().splitlines() if not json.loads(x).get("summary")]

    ps = problems({**doc, "setting": {**doc["setting"], "period": "宋朝", "world": "", "dynasty": "宋"}})
    assert any("period 应为" in x for x in ps) and any("world" in x for x in ps) and any("不认识的槽位 dynasty" in x for x in ps)
    assert any("缺设定卡" in x for x in problems({k: v for k, v in doc.items() if k != "setting"}))
    assert problems(doc) == []
    author, reader = cr.render(doc, False), cr.render(doc, True)
    assert "设定卡：时代 古代" in author and "- 伴侣那边的人：妻家（岳家）" in author
    assert "设定卡" not in reader and "妻家（岳家）" not in reader

    reader_md = EXAMPLE / "人物" / "沈砚.读者本.md"

    def warns(*extra: str, path: Path = reader_md) -> int:
        r = subprocess.run(["node", str(ROOT / "scripts" / "check-terms.js"), str(path), "--summary", *extra],
                           capture_output=True, text=True, encoding="utf-8")
        s = json.loads(r.stdout.strip().splitlines()[-1])
        assert s["errors"] == 0, r.stdout
        return s["warns"]

    by_card, forced_modern, forced_ancient = warns(), warns("--period", "现代"), warns("--period", "古代")
    assert by_card == forced_ancient < forced_modern  # 古代读者本里的长辈、妻家一类词，设定卡说古代就不报，硬说现代就报
    orphan = tmp_path / "沈砚.读者本.md"  # 找不到同名档案 JSON：不知道时代，照报
    orphan.write_text(reader_md.read_text(encoding="utf-8"), encoding="utf-8")
    assert warns(path=orphan) == forced_modern
    # 现代样例：同一张盘、同一批编号，只换设定卡与措辞
    modern_doc = json.loads((EXAMPLE / "人物" / "沈砚.现代.json").read_text(encoding="utf-8"))
    assert modern_doc["setting"]["period"] == "现代" and modern_doc["chart"] == doc["chart"]
    src = lambda d: [t["sources"] for s in d["sections"] for t in (s.get("traits") or [x for st in s.get("stages", []) for x in st["traits"]])]
    assert src(modern_doc) == src(doc)
    assert problems(modern_doc) == []
    assert warns(path=EXAMPLE / "人物" / "沈砚.现代.读者本.md") == 0
