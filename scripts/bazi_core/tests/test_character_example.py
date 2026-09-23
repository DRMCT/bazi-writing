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
    assert {"P", "DM", "T", "H", "G", "S", "Y", "R", "N", "NT", "C", "D", "L"} <= prefixes
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
    r = subprocess.run(["node", str(ROOT / "scripts" / "check-character.js"), str(doc), "--summary"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout
    s = json.loads(r.stdout.strip().splitlines()[-1])
    assert s["problems"] == 0 and s["traits"] == s["sourced"] >= 20
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
    r = subprocess.run(["node", str(ROOT / "scripts" / "check-character.js"), str(p), "--chart", str(EXAMPLE / "命盘" / "沈砚.json")],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 1
    problems = [json.loads(x)["problem"] for x in r.stdout.strip().splitlines() if not json.loads(x).get("summary")]
    assert any("找不到" in x for x in problems) and any("缺席" in x for x in problems)


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
