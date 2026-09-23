"""《子平真诠评注》徐评命例：夹具形态、八格章取格一致率的下限、几张书里明说格局的盘。

夹具 fixtures/ziping_lipan.json 由 scripts/extract_ziping_lipan.py 从校对本抽出。八格章的命例是徐评为讲该格取运而举，
多数按章名取格即中，但也有讲变格、讲相神的盘，所以只设一致率下限，不逐张断言；不符的清单在 references/校核/格局_例盘报告.md。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bazi_core.shishen import determine_structure

FIXTURE = Path(__file__).parent / "fixtures" / "ziping_lipan.json"
STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"


@pytest.fixture(scope="module")
def cases() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]


def test_fixture_shape(cases: list[dict]) -> None:
    assert len(cases) >= 150
    for c in cases:
        assert len(c["pillars"]) == 4 and c["page"].startswith("p") and c["chapter"]
        if not c["flags"]:
            for p in c["pillars"]:
                assert STEMS.index(p[0]) % 2 == BRANCHES.index(p[1]) % 2, (c["id"], p)


def test_month_base_agreement_floor(cases: list[dict]) -> None:
    """徐评归章按月令本格（当旺之神；杂气透干取之），base 与章名一致率 2026-09-23 为 79/83，
    余下四张是食神伤官互称、建禄用食、杂气兼透官煞与食神谁重，见报告。"""
    graded = [c for c in cases if "expectedStructures" in c]
    assert len(graded) >= 80
    hit = sum(1 for c in graded if determine_structure(*c["pillars"]).base in c["expectedStructures"])
    assert hit / len(graded) >= 0.9, f"{hit}/{len(graded)}"


def test_variant_matches_xu_reading(cases: list[dict]) -> None:
    """变格与徐评判词相合的几张：会局变格与生地藏透变格，name 是徐评实际论的格，base 是所在章。"""
    by_id = {c["id"]: c for c in cases}
    # 金状元命（论正官）：亥卯未三合，徐评"化官为印"
    s = determine_structure(*by_id["三十二-03"]["pillars"])
    assert (s.name, s.base, s.variation) == ("偏印格", "正官格", "会局")
    # 宣参国命（论正官）：亥卯未三合，徐评"官化为伤"
    s = determine_structure(*by_id["三十二-04"]["pillars"])
    assert (s.name, s.base, s.variation) == ("伤官格", "正官格", "会局")
    # 论财篇：丙生申月透壬，徐评"弃财而用煞"
    s = determine_structure(*by_id["三十四-13"]["pillars"])
    assert (s.name, s.base, s.variation) == ("七杀格", "偏财格", "藏透")


def test_named_examples() -> None:
    # 薛相公命（论正官）：月令申正官当旺为本格，壬印透为藏透变格，徐评"月令正官，透壬本可舍官而用印"
    s = determine_structure("甲申", "壬申", "乙巳", "戊寅")
    assert (s.base, s.name) == ("正官格", "正印格")
    # 论正官取运首例：戊生未月杂气正官，乙木透时干，丁印兼透
    s = determine_structure("壬戌", "丁未", "戊申", "乙卯")
    assert (s.name, s.also) == ("正官格", ["正印格"])
