"""神煞叙事标签表与去术语检查器：表形态、求值形态、几张盘的命中、检查器正反两向。"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from bazi_core import shensha, shensha_tags

ROOT = Path(__file__).resolve().parent.parent.parent.parent
TABLE = ROOT / "scripts" / "bazi_core" / "tables" / "shensha_tags.json"
TERMS = ROOT / "scripts" / "bazi_core" / "tables" / "terms.json"
CHECKER = ROOT / "scripts" / "check-terms.js"


def test_table_shape() -> None:
    t = json.loads(TABLE.read_text(encoding="utf-8"))
    names = {e["name"] for e in json.loads((ROOT / "scripts" / "bazi_core" / "tables" / "shensha.json").read_text(encoding="utf-8"))["entries"]}
    ids: set[str] = set()
    vocab = set(t["conditionVocabulary"])
    for e in t["entries"]:
        assert e["shensha"] in names, e["shensha"]  # 只给白名单里的神煞建标签
        assert e["core"]
        for v in e["variants"]:
            assert v["id"] not in ids and v["id"].startswith(e["shensha"] + "-")
            ids.add(v["id"])
            assert v["tag"] and v["source"]
            assert set(v["when"]) <= vocab, v["id"]
            if v["classic"] is None:
                assert "DESIGN-命盘层 附录 A" in v["source"]
    assert names <= {e["shensha"] for e in t["entries"]}  # 白名单每种都有条目


def test_for_chart_shape_and_provenance() -> None:
    p = {"year": "庚戌", "month": "戊子", "day": "癸酉", "hour": "癸亥"}
    r = shensha_tags.for_chart(p, "male")
    present = {h["name"] for h in shensha.compute(p)}
    assert set(r["cores"]) == present
    for tag in r["tags"]:
        assert tag["shensha"] in present and tag["pillar"] in "年月日时"
        assert tag["id"].startswith(tag["shensha"] + "-") and tag["origin"]
    # 同一编号同一柱不重复
    assert len({(t["id"], t["pillar"]) for t in r["tags"]}) == len(r["tags"])


def test_position_variants_fire() -> None:
    # 庚戌 戊子 癸酉 癸亥：年戌华盖、年戌与时亥旬空 → 华盖-05（空亡同柱）应命中；时亥阴差阳错、时亥孤辰
    p = {"year": "庚戌", "month": "戊子", "day": "癸酉", "hour": "癸亥"}
    ids = {t["id"] for t in shensha_tags.for_chart(p, "male")["tags"]}
    assert "华盖-05" in ids and "空亡-01" in ids
    assert "阴差阳错-03" in ids  # 男命
    assert "阴差阳错-02" not in ids
    # 甲申 壬申 乙巳 戊寅：年月申为天乙贵人 → 天乙贵人-01；两柱 → 天乙贵人-08；寅申冲，时寅驿马逢冲 → 驿马-04
    p = {"year": "甲申", "month": "壬申", "day": "乙巳", "hour": "戊寅"}
    ids = {t["id"] for t in shensha_tags.for_chart(p)["tags"]}
    assert {"天乙贵人-01", "天乙贵人-08", "驿马-04"} <= ids


def test_gender_gate() -> None:
    p = {"year": "庚戌", "month": "戊子", "day": "癸酉", "hour": "癸亥"}
    ids_f = {t["id"] for t in shensha_tags.for_chart(p, "female")["tags"]}
    ids_none = {t["id"] for t in shensha_tags.for_chart(p)["tags"]}
    assert "阴差阳错-02" in ids_f and "阴差阳错-03" not in ids_f
    assert not ({"阴差阳错-02", "阴差阳错-03"} & ids_none)


def test_terms_table_shape() -> None:
    t = json.loads(TERMS.read_text(encoding="utf-8"))
    seen: set[str] = set()
    for g in t["groups"]:
        assert g["level"] in ("error", "warn", "ok")
        for term in g["terms"]:
            assert len(term) >= 2, term  # 单字不进表
            assert term not in seen, term
            seen.add(term)
    # 白名单神煞名与十神名都在 error 组
    err = {term for g in t["groups"] if g["level"] == "error" for term in g["terms"]}
    assert {"正官", "七杀", "食神", "天乙贵人", "空亡", "命中注定", "甲子"} <= err


@pytest.mark.skipif(shutil.which("node") is None, reason="需要 node")
def test_checker_positive_and_negative(tmp_path: Path) -> None:
    clean = tmp_path / "clean.md"
    clean.write_text("他总在关键时刻被人拉一把，却从没学会自救。\n她挑人，不是被挑。\n", encoding="utf-8")
    dirty = tmp_path / "dirty.md"
    dirty.write_text("他日主甲木，生于寅月，正官透出，命中注定要走仕途。\n年柱甲子。\n", encoding="utf-8")
    r = subprocess.run(["node", str(CHECKER), str(clean)], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0
    summary = json.loads(r.stdout.strip().splitlines()[-1])
    assert summary["errors"] == 0
    r = subprocess.run(["node", str(CHECKER), str(dirty)], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 1
    lines = [json.loads(x) for x in r.stdout.strip().splitlines()]
    hits = {h["term"] for h in lines if not h.get("summary")}
    assert {"日主", "正官", "命中注定", "年柱", "甲子"} <= hits
    # 放行与反向自检
    r = subprocess.run(["node", str(CHECKER), str(dirty), "--expect-hits", "--summary"], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0
    r = subprocess.run(["node", str(CHECKER), str(clean), "--expect-hits", "--summary"], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 1


def _terms_rows(path: Path, *extra: str) -> tuple[int, list[dict]]:
    r = subprocess.run(["node", str(CHECKER), str(path), *extra], capture_output=True, text=True, encoding="utf-8")
    return r.returncode, [json.loads(x) for x in r.stdout.strip().splitlines()]


@pytest.mark.skipif(shutil.which("node") is None, reason="需要 node")
def test_checker_common_words_and_whole_word_pass(tmp_path: Path) -> None:
    """古代题材的常用词不报 error：比肩、劫财、驿马、冠带是 warn；大运河、似水流年、沐浴更衣、司天监整词放行，一条不报。命理用法照旧 error。"""
    old = tmp_path / "old.md"
    old.write_text("他沿着大运河往南走了三天，驿马换了两回。\n似水流年，她早不记得那天穿的什么。\n论手艺，镇上没人能与他比肩。\n"
                   "山道上有人劫财，她把钱袋塞进鞋里。\n她沐浴更衣，把冠带理正。\n司天监的人说今年雨水多。\n", encoding="utf-8")
    code, rows = _terms_rows(old, "--period", "古代")
    assert code == 0 and rows[-1]["errors"] == 0, rows
    assert {h["term"] for h in rows if not h.get("summary")} == {"驿马", "比肩", "劫财", "冠带"}, rows
    fate = tmp_path / "fate.md"
    fate.write_text("这一年交了大运，司天在泉都对他不利，流年又冲了日支，冲提纲那年伏吟。\n", encoding="utf-8")
    code, rows = _terms_rows(fate)
    errs = {h["term"] for h in rows if not h.get("summary") and h["level"] == "error"}
    assert code == 1 and {"大运", "司天", "在泉", "日支", "冲提纲", "伏吟"} <= errs, rows
