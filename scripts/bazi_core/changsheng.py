"""十二长生与纳音：查表层。

表来自 tables/changsheng.json 与 tables/nayin.json，由 scripts/build_changsheng.py 从校核卡
references/校核/十二长生纳音.md 的「采用规则」生成；每张表带 source 指向卡号与卡状态。
十二宫取阳生阴死、戊己随丙丁寄生（四库本《三命通会》卷二），另说记在卡上不入表。
"""

from __future__ import annotations

import json
from pathlib import Path

_TABLES = Path(__file__).resolve().parent / "tables"
_CS = json.loads((_TABLES / "changsheng.json").read_text(encoding="utf-8"))
_NY = json.loads((_TABLES / "nayin.json").read_text(encoding="utf-8"))

STAGES: tuple[str, ...] = tuple(_CS["stages"])
_PILLAR_KEYS = ("year", "month", "day", "hour")
_FINAL = ("已核", "已裁", "已审")


def stage(stem: str, branch: str) -> str:
    """天干在地支的十二宫名，如 stage('甲', '寅') → '临官'。"""
    return _CS["table"][stem][branch]


def birth_branch(stem: str) -> str:
    """天干长生所在支。"""
    return _CS["birthBranch"][stem]


def nayin(pillar: str) -> dict:
    """柱的纳音：{'name': '海中金', 'element': '金'}。"""
    return dict(_NY["entries"][pillar])


def sources() -> dict:
    return {"changsheng": dict(_CS["cards"]), "nayin": {_NY["card"]: _NY["status"]}}


def status() -> str:
    ok = all(v in _FINAL for v in _CS["cards"].values()) and _NY["status"] in _FINAL
    return "校核定稿" if ok else "待校对本"


def for_chart(pillars: dict) -> dict:
    """命盘四柱：各柱纳音、日主对各支的十二宫（星运）、各柱天干自坐十二宫。"""
    keys = [k for k in _PILLAR_KEYS if pillars.get(k)]
    day_stem = pillars["day"][0]
    return {
        "nayin": {k: nayin(pillars[k]) for k in keys},
        "dayMasterStage": {k: stage(day_stem, pillars[k][1]) for k in keys},
        "selfStage": {k: stage(pillars[k][0], pillars[k][1]) for k in keys},
        "status": status(),
        "source": sources(),
    }
