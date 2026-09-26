"""多人矩阵：十神互看、日柱关系对称、同步忌运对称、无纪年锚不算同步、检查器 --matrix 认 E- 编号。"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from bazi_core import chart, matrix

ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _two(epoch_b: int | None = 306):
    a = chart.chart_from_pillars("甲申", "壬申", "乙巳", "戊寅", "male", story_epoch=300, name="沈砚")
    b = chart.chart_from_pillars("戊戌", "甲寅", "辛酉", "甲午", "female", start_age_years=5, story_epoch=epoch_b, name="林昭")
    return a, b


def test_edges_both_ways() -> None:
    m = matrix.build(list(_two()))
    e = {(x["from"], x["to"]): x for x in m["edges"]}
    assert e[("沈砚", "林昭")]["tenGod"] == "七杀" and e[("林昭", "沈砚")]["tenGod"] == "偏财"
    assert e[("沈砚", "林昭")]["dayPillar"]["stem"] == "被克" and e[("林昭", "沈砚")]["dayPillar"]["stem"] == "克"
    ab = [(s["from"], s["to"]) for s in e[("沈砚", "林昭")]["syncJi"]]
    ba = [(s["from"], s["to"]) for s in e[("林昭", "沈砚")]["syncJi"]]
    assert ab == ba
    ids = [f["id"] for f in m["features"]]
    assert len(ids) == len(set(ids)) and all(i.startswith("E-") for i in ids)
    assert "E-沈砚-林昭-十神-七杀" in ids


def test_no_anchor_no_sync() -> None:
    m = matrix.build(list(_two(epoch_b=None)))
    assert all(not x["syncJi"] and not x["aUpBDown"] for x in m["edges"])


def test_duplicate_names_rejected() -> None:
    a, _ = _two()
    with pytest.raises(ValueError):
        matrix.build([a, a])


@pytest.mark.skipif(shutil.which("node") is None, reason="需要 node")
def test_checker_accepts_matrix_ids(tmp_path: Path) -> None:
    a, b = _two()
    (tmp_path / "命盘").mkdir()
    (tmp_path / "人物").mkdir()
    a["features"] = chart.features(a)
    (tmp_path / "命盘" / "沈砚.json").write_text(json.dumps(a, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "命盘" / "矩阵.json").write_text(json.dumps(matrix.build([a, b]), ensure_ascii=False), encoding="utf-8")
    titles = ["性格表里", "童年事件", "谎言", "秘密", "需要与想要", "抵抗线", "亲密关系模式", "说话方式",
              "能力与漏洞", "意象系统", "他人眼中的他", "年表与两难"]
    sections = [{"title": t, "traits": []} for t in titles] + [{"title": "阶段状态", "stages": []}]
    sections[10]["traits"] = [{"text": "在林昭眼里他是一笔能动用的钱，也是一个她拿捏得住的人。", "sources": ["E-林昭-沈砚-十神-偏财"]}]
    doc = {"schema": "bazi-character/v1", "setting": {"period": "古代", "world": "合成档案，检查器用"}, "name": "沈砚", "chart": "命盘/沈砚.json", "sections": sections}
    p = tmp_path / "人物" / "沈砚.json"
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    cmd = ["node", str(ROOT / "scripts" / "check-character.js"), str(p), "--summary"]
    assert subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8").returncode == 1
    r = subprocess.run(cmd + ["--matrix", str(tmp_path / "命盘" / "矩阵.json")], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout


def test_edge_draft_uses_response_table_and_ids_exist() -> None:
    a = chart.chart_from_pillars("甲申", "壬申", "乙巳", "戊寅", "male", story_epoch=300, name="沈砚")
    b = chart.chart_from_pillars("庚寅", "壬午", "辛酉", "戊戌", "female", start_age_years=5, story_epoch=306, name="林昭")
    m = matrix.build([a, b])
    for e in m["edges"]:
        ids = {f["id"] for f in e["features"]}
        assert e["draft"] and set(e["draftIds"]) <= ids
        assert f"{e['from']}看{e['to']}为{e['tenGod']}" in e["draft"]
        assert e["draftIds"][0] == f"E-{e['from']}-{e['to']}-十神-{e['tenGod']}"
        if e["yongji"]["role"] in ("用", "喜"):
            assert "回应偏靠近" in e["draft"]
        elif e["yongji"]["role"] in ("忌", "仇"):
            assert "回应偏躲或压" in e["draft"]
        for s in e["syncJi"]:
            assert f"{s['from']}–{s['to']}年两人同在忌运" in e["draft"]
