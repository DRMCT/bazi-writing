"""换盘测试的对照实验（examples/对照实验）：同盘重写、同一约束的邻盘、打乱生日的对照盘，差异度必须按这个次序分开，阈值 0.65 落在同盘与异盘之间。

七份档案：沈砚、林昭、林昭重写（同盘）、林昭乙（约束第二名）、林昭丙（约束第三名）、对照（打乱生日）、沈砚.现代（同盘换设定卡）。
四份对照档案各自过契约与溯源检查（引年表 L- 编号），读者本零 error。
同盘换设定卡（DESIGN-人物层 5）：溯源编号一个不动，只按设定卡换措辞，编号路距离为 0，差异度只来自文本路，必须低于同盘重写。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
EX = ROOT / "examples"
PY = sys.executable
sys.path.insert(0, str(ROOT / "scripts"))
import check_divergence as cd  # noqa: E402
import divergence_report as dr  # noqa: E402

DOCS = [EX / "沈砚" / "人物" / "沈砚.json", EX / "林昭" / "人物" / "林昭.json",
        EX / "对照实验" / "人物" / "林昭重写.json", EX / "对照实验" / "人物" / "林昭乙.json",
        EX / "对照实验" / "人物" / "林昭丙.json", EX / "对照实验" / "人物" / "对照.json",
        EX / "沈砚" / "人物" / "沈砚.现代.json"]


def test_same_chart_below_threshold_and_all_different_above() -> None:
    res = dr.run(DOCS)
    assert res["same"]["n"] == 2 and res["diff"]["n"] == 19
    assert res["same"]["max"] < cd.RECOMMENDED_THRESHOLD <= res["diff"]["min"], res
    pairs = {frozenset((r["a"], r["b"])): r for r in res["pairs"]}
    same = pairs[frozenset(("林昭", "林昭重写"))]
    neighbor = pairs[frozenset(("林昭", "林昭乙"))]
    control = pairs[frozenset(("林昭", "对照"))]
    # 次序：同盘 < 邻盘 < 对照盘；编号路是主信号
    assert same["divergence"] < neighbor["divergence"] < control["divergence"]
    assert same["idDistance"] < 0.4 < neighbor["idDistance"] < control["idDistance"]
    # 同盘换设定卡：编号路 0，差异度低于同盘重写；设定层只动措辞不动真相层
    modern = pairs[frozenset(("沈砚", "沈砚.现代"))]
    assert modern["idDistance"] == 0 and modern["divergence"] < same["divergence"]
    assert all(r["divergence"] > cd.RECOMMENDED_THRESHOLD for r in res["pairs"] if "沈砚.现代" in (r["a"], r["b"]) and not r["same"])
    assert res["suggestedThreshold"] is not None and abs(res["suggestedThreshold"] - cd.RECOMMENDED_THRESHOLD) < 0.05


@pytest.mark.skipif(shutil.which("node") is None, reason="需要 node")
@pytest.mark.parametrize("name,timeline", [("林昭乙", "林昭乙"), ("林昭丙", "林昭丙"), ("对照", "对照"), ("林昭重写", "林昭")])
def test_control_profiles_pass_checks(tmp_path: Path, name: str, timeline: str) -> None:
    d = EX / "对照实验"
    r = subprocess.run(["node", str(ROOT / "scripts" / "check-character.js"), str(d / "人物" / f"{name}.json"),
                        "--timeline", str(d / "命盘" / f"{timeline}.年表.json"), "--summary"], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout
    s = json.loads(r.stdout.strip().splitlines()[-1])
    assert s["problems"] == 0 and s["traits"] == s["sourced"] >= 25
    out = tmp_path / "读者本.md"
    subprocess.run([PY, str(ROOT / "scripts" / "character_render.py"), str(d / "人物" / f"{name}.json"), "--reader", "--out", str(out)], check=True)
    r = subprocess.run(["node", str(ROOT / "scripts" / "check-terms.js"), str(out), "--summary"], capture_output=True, text=True, encoding="utf-8")
    assert json.loads(r.stdout.strip().splitlines()[-1])["errors"] == 0, r.stdout


def test_threshold_cli_default_and_report_file() -> None:
    r = subprocess.run([PY, str(ROOT / "scripts" / "check_divergence.py"), str(DOCS[1]), str(DOCS[2]), "--threshold", "--summary"],
                       capture_output=True, text=True, encoding="utf-8")
    out = json.loads(r.stdout)
    assert r.returncode == 1 and out["threshold"] == cd.RECOMMENDED_THRESHOLD and out["pass"] is False
    r = subprocess.run([PY, str(ROOT / "scripts" / "check_divergence.py"), str(DOCS[1]), str(DOCS[3]), "--threshold", "--summary"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0 and json.loads(r.stdout)["pass"] is True
    report = (ROOT / "references" / "校核" / "换盘_对照报告.md").read_text(encoding="utf-8")
    assert "林昭重写" in report and "建议阈值" in report
