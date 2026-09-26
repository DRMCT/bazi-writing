"""第二个样例 examples/林昭：反推选盘 → 命盘 → 年表、矩阵、两难、日程 → 人物档案，过全部检查；换盘测试骨架 check_divergence.py。

- 样例命盘与重生成一致（含 IN、IM、LI 三节）；约束文件里的硬约束在选中的盘上成立；
- 人物档案过契约与溯源检查（引了矩阵 E-、年表 L-、日程 J- 编号），读者本零 error；
- 日程交汇点都有当年才有的引动原因或两人同年候选；
- 弧光 reading 给了作者要的模板时按它写，最佳不同则记 closer；意象寒燥修正在调候为仇的盘上带饮鸩止渴一句；
- 差异度：沈砚对林昭远高于同盘对自身（0）。阈值待定，这里只守下限。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from bazi_core import arc, chart, schedule

ROOT = Path(__file__).resolve().parents[3]
EX = ROOT / "examples"
PY = sys.executable
sys.path.insert(0, str(ROOT / "scripts"))
import check_divergence as cd  # noqa: E402


def _linzhao() -> dict:
    c = chart.chart_from_pillars("庚寅", "壬午", "辛酉", "戊戌", "female", start_age_years=5, story_epoch=306, name="林昭")
    c["liunian"] = [chart.liunian(c, n) for n in (6, 10, 25, 31, 37)]
    return c


def test_example_chart_matches_regenerated_and_constraints_hold() -> None:
    saved = json.loads((EX / "林昭" / "命盘" / "林昭.json").read_text(encoding="utf-8"))
    c = _linzhao()
    assert {x["id"] for x in saved["features"]} == {x["id"] for x in chart.features(c)}
    cons = json.loads((EX / "林昭" / "林昭.约束.json").read_text(encoding="utf-8"))
    assert cons["day_master"]["hard"] and c["natal"]["dayMaster"].endswith("金") or "金" in c["natal"]["dayMaster"]
    assert c["strength"]["verdict"] == "身弱" and c["yongshen"]["yong"]["element"] == "土"
    assert c["natal"]["structure"]["name"] == "七杀格" and c["fourPillars"]["day"][1] == "酉"
    res = json.loads((EX / "林昭" / "命盘" / "约束" / "林昭.json").read_text(encoding="utf-8"))
    assert res["results"][0]["pillars"] == c["fourPillars"]


@pytest.mark.skipif(shutil.which("node") is None, reason="需要 node")
def test_example_character_passes_all_checks(tmp_path: Path) -> None:
    d = EX / "林昭"
    r = subprocess.run(["node", str(ROOT / "scripts" / "check-character.js"), str(d / "人物" / "林昭.json"),
                        "--matrix", str(d / "命盘" / "矩阵.json"), "--timeline", str(d / "命盘" / "林昭.年表.json"),
                        "--schedule", str(d / "命盘" / "日程.json"), "--summary"], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout
    s = json.loads(r.stdout.strip().splitlines()[-1])
    assert s["problems"] == 0 and s["traits"] == s["sourced"] >= 30
    # 不带矩阵、年表、日程时必须报找不到，说明这份档案真的引了它们
    r = subprocess.run(["node", str(ROOT / "scripts" / "check-character.js"), str(d / "人物" / "林昭.json"), "--summary"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 1
    out = tmp_path / "读者本.md"
    subprocess.run([PY, str(ROOT / "scripts" / "character_render.py"), str(d / "人物" / "林昭.json"), "--reader", "--out", str(out)], check=True)
    r = subprocess.run(["node", str(ROOT / "scripts" / "check-terms.js"), str(out), "--summary"], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0 and json.loads(r.stdout.strip().splitlines()[-1])["errors"] == 0, r.stdout


def test_schedule_intersections_need_year_specific_reason() -> None:
    a = chart.chart_from_pillars("甲申", "壬申", "乙巳", "戊寅", "male", story_epoch=300, name="沈砚")
    s = schedule.build([a, _linzhao()], (324, 346), main="林昭")
    assert s["intersections"]
    rows = {p["name"]: {r["year"]: r for r in p["rows"]} for p in s["people"]}
    for x in s["intersections"]:
        both = all(rows[n][x["year"]]["candidate"] for n in x["people"])
        specific = any(k in t for t in x["reasons"] for k in ("正是", "同年", "日支"))
        assert both or specific, x
    # 331–342 两人同在忌运，但只靠这条不成交汇：337、339、342 不在
    years = {x["year"] for x in s["intersections"]}
    assert 331 in years and not {337, 339, 342} & years


def test_arc_reading_with_wanted_template() -> None:
    c = _linzhao()
    r = arc.for_chart(c, (18, 40), 24, wanted="正弧")
    rd = r["reading"]
    assert rd["template"] == "正弧" and rd["match"] == next(t["match"] for t in r["templates"] if t["template"] == "正弧")
    if r["best"] != "正弧":
        assert rd["closer"]["template"] == r["best"]
    assert "margin" in rd
    assert "closer" not in arc.for_chart(c, (18, 40), 24, wanted=r["best"])["reading"]


def test_imagery_dry_poison_when_tiaohou_is_foe() -> None:
    c = _linzhao()
    dry = next(m for m in c["imagery"]["modifiers"] if m["cond"] == "dry")
    assert dry["poison"] is True and c["yongshen"]["roles"]["水"] == "仇"
    assert "饮鸩止渴" in next(f["text"] for f in c["imagery"]["features"] if f["id"] == "IM-dry")


def test_divergence_skeleton() -> None:
    a = json.loads((EX / "沈砚" / "人物" / "沈砚.json").read_text(encoding="utf-8"))
    b = json.loads((EX / "林昭" / "人物" / "林昭.json").read_text(encoding="utf-8"))
    same = cd.compare(a, a)
    assert same["divergence"] == 0.0 and same["idDistance"] == 0.0
    diff = cd.compare(a, b)
    assert diff["divergence"] > 0.6 and diff["idDistance"] > 0.5 and diff["textDistance"] > 0.6
    assert cd.id_kind("T-月干-正印") == "T-正印" and cd.id_kind("L-6-庚寅-冲提纲") == "L-冲提纲"
    assert cd.id_kind("NT-驿马-04-时") == "NT-驿马-04" and cd.id_kind("E-沈砚-林昭-十神-七杀") == "E-十神-七杀"
    assert cd.id_kind("J-331-林昭-沈砚") == "J" and cd.id_kind("IN-day_branch_yong") == "IN-day_branch_yong"
    # 命令行：阈值判定
    r = subprocess.run([PY, str(ROOT / "scripts" / "check_divergence.py"), str(EX / "沈砚" / "人物" / "沈砚.json"),
                        str(EX / "沈砚" / "人物" / "沈砚.json"), "--threshold", "0.5", "--summary"], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 1 and json.loads(r.stdout)["pass"] is False
