"""规则层叙事表的形态检查：十神性格、五行体质气质、六亲宫位与童年、岁运事件类型，以及滴天髓卡的机器表。

- 每张表能读、列齐、行不空；anchors 指向的滴天髓卡号都存在；
- 岁运事件类型表的机制名与 timeline.py 一致、领域名与 timeline.DOMAINS 一致；
- ditiansui.json 每条带卡号与章，规则条目不为空。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from bazi_core.timeline import DOMAINS

ROOT = Path(__file__).resolve().parents[3]
TABLES = ROOT / "scripts" / "bazi_core" / "tables"
CARDS = ROOT / "references" / "校核"


def _card_ids() -> set[str]:
    ids: set[str] = set()
    for f in CARDS.glob("*.md"):
        ids.update(re.findall(r"(?m)^### (\S+-\S+)", f.read_text(encoding="utf-8")))
    return ids


@pytest.mark.parametrize("name", ["shishen_traits.json", "wuxing_body.json", "liuqin_childhood.json"])
def test_narrative_table_shape(name):
    t = json.loads((TABLES / name).read_text(encoding="utf-8"))
    assert t["format"] == "narrative-table/v1"
    keys = {c["key"] for c in t["columns"]}
    assert "anchors" in keys and t["rows"]
    ids = _card_ids()
    for r in t["rows"] + t.get("modifiers", []):
        assert set(r) - {"anchors"} , r
        for a in r.get("anchors", []):
            assert a in ids, f"{name}: 锚点 {a} 没有对应的卡"


def test_shishen_traits_cover_ten_gods_both_states():
    t = json.loads((TABLES / "shishen_traits.json").read_text(encoding="utf-8"))
    pairs = {(r["tenGod"], r["state"]) for r in t["rows"]}
    for g in ("正官", "七杀", "正财", "偏财", "正印", "偏印", "食神", "伤官", "比肩", "劫财"):
        assert (g, "旺") in pairs and (g, "弱") in pairs


def test_suiyun_events_match_timeline():
    from bazi_core import timeline
    t = json.loads((TABLES / "suiyun_events.json").read_text(encoding="utf-8"))
    src = Path(timeline.__file__).read_text(encoding="utf-8")
    for m in t["mechanisms"]:
        assert m["name"] in src, m["name"]
    assert [d["name"] for d in t["domains"]] == list(DOMAINS)
    ids = _card_ids()
    for row in t["mechanisms"] + t["domains"]:
        for a in row["anchors"]:
            assert a in ids, a
    names = {m["name"] for m in t["mechanisms"]}
    for c in t["cells"]:
        assert c["mechanism"] in names and c["domain"] in DOMAINS and all(s in DOMAINS for s in c["sub"])


def test_ditiansui_table_has_sources():
    t = json.loads((TABLES / "ditiansui.json").read_text(encoding="utf-8"))
    assert t["format"] == "ditiansui/v1" and t["entries"]
    ids = _card_ids()
    for e in t["entries"]:
        assert e["card"] in ids and e["chapter"] and e["rules"], e["card"]
