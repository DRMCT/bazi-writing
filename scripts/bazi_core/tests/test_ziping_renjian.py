"""《子平真诠评注》附录《人鉴·命理存验》67 例夹具（2026-09-25）。

夹具 fixtures/ziping_renjian.json 由 scripts/extract_ziping_renjian.py 从校对本抽出：67 例四柱、大运（带起运岁）、胎元立命、林庚白判词。
守住：例数 67 且编号齐；不带 flags 的例四柱合法、大运干支连续且首步接月柱、起运岁按十年递增；带 flags 的只限登记过的原书误字那几例；
每例都能取格并逐盘判定；判词非空且不含今人解说的痕迹（阿拉伯数字年份）。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from bazi_core import geju
from bazi_core.dayun import pillar_name, sexagenary_index
from bazi_core.shishen import determine_structure

FIXTURE = Path(__file__).parent / "fixtures" / "ziping_renjian.json"
LEGAL = {pillar_name(i) for i in range(60)}
# 原书排印之误（各批校对报告登记）：壬年、丙甲、己印、乙丙、癸才、起运岁漏印或空
KNOWN_FLAGGED = {"人鉴-11", "人鉴-12", "人鉴-14", "人鉴-20", "人鉴-32", "人鉴-38", "人鉴-55"}


@pytest.fixture(scope="module")
def cases() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]


def test_sixty_seven_cases_numbered(cases: list[dict]) -> None:
    assert len(cases) == 67 and sorted(c["seq"] for c in cases) == list(range(1, 68))
    assert all(c["name"] and c["page"] and c["dayun"] and c["taiyuan"] for c in cases)


def test_flags_only_known(cases: list[dict]) -> None:
    assert {c["id"] for c in cases if c["flags"]} == KNOWN_FLAGGED


def test_clean_cases_are_consistent(cases: list[dict]) -> None:
    for c in cases:
        if c["flags"]:
            continue
        assert len(c["pillars"]) == 4 and all(p in LEGAL for p in c["pillars"]), c["id"]
        idx = [sexagenary_index(d["pillar"]) for d in c["dayun"]]
        steps = {(b - a) % 60 for a, b in zip(idx, idx[1:])}
        assert steps in ({1}, {59}), c["id"]
        assert (idx[0] - sexagenary_index(c["pillars"][1])) % 60 in (1, 59), c["id"]
        ages = [d["age"] for d in c["dayun"]]
        assert all(b - a == 10 for a, b in zip(ages, ages[1:])) and 1 <= ages[0] <= 10, c["id"]


def test_every_case_structures_and_judges(cases: list[dict]) -> None:
    verdicts = set()
    for c in cases:
        if c["flags"]:
            continue
        p = dict(zip(("year", "month", "day", "hour"), c["pillars"]))
        s = determine_structure(*c["pillars"])
        j = geju.judge(p, s)
        assert j["verdict"] in ("成格", "败格", "败而有救", "不成格", "待判", "无卡"), c["id"]
        verdicts.add(j["verdict"])
    assert {"成格", "败格"} <= verdicts


def test_comments_are_lin_gengbai_not_modern(cases: list[dict]) -> None:
    for c in cases:
        assert len(c["comment"]) >= 40, c["id"]
        assert not re.search(r"\d{4}年|意译|解说", c["comment"]), c["id"]
