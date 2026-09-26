"""阶段状态卡（DESIGN 10 第 6 条前半）：年表的阶段事实与编号、stagecard 草稿、人物档案阶段状态段的渲染与检查、排版器、差异度计入。

- 年表 stages 每步带干支十神、用喜忌、档位、冲合、长生、神煞、叠合、领域、候选，编号 D-{步}-{干支}-… 不重复；
- 草稿：窗内每步一张，七面各有 draft 与 ids，ids 都在年表或矩阵里；一推一压给合并句；关系变化不留空；女命用"她"；
- 渲染：作者本带阶段编号，读者本不带；岁数汉字；
- 检查器：阶段状态是必备段落；stage 编号、ages、label、aspect、次序都查；
- 排版器：样例往返一致；差异度把阶段卡的编号与文本计入。
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from bazi_core import chart, matrix, stagecard, timeline

ROOT = Path(__file__).resolve().parents[3]
EX = ROOT / "examples"
PY = sys.executable
sys.path.insert(0, str(ROOT / "scripts"))
import character_format as cf  # noqa: E402
import character_render as cr  # noqa: E402
import check_divergence as cd  # noqa: E402


def _shenyan() -> dict:
    return chart.chart_from_pillars("甲申", "壬申", "乙巳", "戊寅", "male", story_epoch=300, name="沈砚")


def _linzhao() -> dict:
    return chart.chart_from_pillars("庚寅", "壬午", "辛酉", "戊戌", "female", start_age_years=5, story_epoch=306, name="林昭")


def test_timeline_stage_facts_and_ids() -> None:
    t = timeline.build(_linzhao(), (0, 45))
    ids = [f["id"] for f in t["features"]]
    assert len(ids) == len(set(ids))
    st = next(s for s in t["stages"] if s["pillar"] == "己卯")
    assert st["tenGods"] == {"stem": "偏印", "branch": "偏财"} and st["roles"] == {"stem": "用", "branch": "忌"}
    assert st["band"] == "强逆" and st["changsheng"] == "绝" and "冲日支" in st["mechanisms"] and "合绊用神" in st["mechanisms"]
    assert st["overlay"] == {"偏印": "近", "偏财": "近"}  # 命局透正印、藏正财：同家族的另一个
    assert [d["domain"] for d in st["domains"]] == ["感情", "六亲"] and 25 in st["candidates"]
    for suffix in ("干-偏印", "支-偏财", "干-用", "支-忌", "档-强逆", "长生-绝", "冲日支", "煞-桃花", "近-偏印", "域-感情", "基调"):
        assert f"D-3-己卯-{suffix}" in ids
    # 闲神带偏喜偏忌时编号只取首字
    t2 = timeline.build(_shenyan(), (0, 60))
    assert all("（" not in f["id"].split("-")[-1] or "刑" in f["id"] for f in t2["features"] if f["id"].startswith("D-"))
    assert any(f["id"].endswith("-叠-伤官") for f in t2["features"])


def test_stagecard_draft() -> None:
    a, b = _shenyan(), _linzhao()
    t = timeline.build(b, (0, 45))
    m = matrix.build([a, b])
    s = stagecard.build(t, b, m, (24, 46))
    assert s["schema"] == "bazi-stagecard/v1" and [x["stage"] for x in s["stages"]] == ["D-2-庚辰", "D-3-己卯", "D-4-戊寅", "D-5-丁丑"]
    assert [x["partial"] for x in s["stages"]] == [True, False, False, True]
    ok = {f["id"] for f in t["features"]} | {f["id"] for e in m["edges"] for f in e["features"]} | {f["id"] for f in chart.features(b)}  # 底色引命盘的 T- 编号
    for x in s["stages"]:
        assert set(x["aspects"]) == set(stagecard.ASPECTS)
        for asp in x["aspects"].values():
            assert set(asp["ids"]) <= ok
        assert x["aspects"]["关系变化"]["draft"], x["stage"]  # 有边或退回领域，不留空
        assert set(x["allIds"]) <= ok and x["stage"] + "-基调" in x["allIds"]
        for asp in x["aspects"].values():
            assert not asp["draft"] or not re.search(r"(?<!其)他", asp["draft"]), asp["draft"]  # 女命用她
    d3 = next(x for x in s["stages"] if x["stage"] == "D-3-己卯")
    assert "一推一压" not in d3["aspects"]["需要的得失"]["draft"] and d3["aspects"]["需要的得失"]["draft"].startswith("天干己为用神而地支卯为忌神")
    assert "落到年份：25岁合绊用神" in d3["aspects"]["需要的得失"]["draft"] and "L-25-乙卯-合绊用神" in d3["aspects"]["需要的得失"]["ids"]
    assert "用神到位" not in d3["aspects"]["需要的得失"]["draft"]  # 年年都有的机制只留在 hooks
    # 性格与说话方式先给命局透干的画像底色（十神性格表旺行，T- 编号），偏移接在后面
    for asp in ("性格", "说话方式"):
        assert d3["aspects"][asp]["draft"].startswith("画像底色（透干与月令）：月干伤官（") and d3["aspects"][asp]["ids"][:4] == ["T-月干-伤官", "H-月支-本气-七杀", "T-年干-劫财", "T-时干-正印"]
    assert "偏印临运" in d3["aspects"]["说话方式"]["draft"] and "示人的偏移（偏印）" in d3["aspects"]["性格"]["draft"]
    assert {"需要的得失", "亲密关系动静"} <= set(stagecard.ASPECTS) and "需要与想要" not in stagecard.ASPECTS
    assert {e["kind"] for e in d3["edges"]} == {"同步忌运"} and d3["candidates"][0]["age"] == 25
    assert any(i.startswith("L-25-乙卯-域-") for i in d3["candidates"][0]["ids"])
    # 没有阶段事实的旧年表要报错
    old = {**t, "stages": [{k: v for k, v in st.items() if k in ("sequence", "pillar", "ages", "score", "tone")} for st in t["stages"]]}
    with pytest.raises(ValueError):
        stagecard.build(old, b, None, (24, 46))
    # 不给矩阵、不给窗：全部大运
    assert len(stagecard.build(t, b)["stages"]) == len(t["stages"])


def test_stage_table_shape() -> None:
    t = stagecard.table()
    keys = {s["key"] for s in t["sections"]}
    assert keys == {"decade", "overlay", "roles", "palace", "changsheng"}
    assert {r["tenGod"] for r in stagecard.DECADE.values()} == {"正官", "七杀", "正财", "偏财", "正印", "偏印", "食神", "伤官", "比肩", "劫财"}
    assert set(stagecard.OVERLAY) == {"叠", "近", "新", "补"} and set(stagecard.ROLES) == {"用", "喜", "忌", "仇", "闲", "混"}
    assert len(stagecard.CHANGSHENG) == 12
    assert all(r["aspect"] in stagecard.ASPECTS for r in stagecard.PALACE.values())


def test_render_stage_section() -> None:
    doc = json.loads((EX / "林昭" / "人物" / "林昭.json").read_text(encoding="utf-8"))
    author, reader = cr.render(doc, False), cr.render(doc, True)
    assert "### 二十五到三十五岁：" in reader and "｜阶段 D-3-己卯" in author and "D-3-己卯" not in reader
    assert "- 性格：" in reader and "- 需要的得失：" in reader and cr.cn_age(25) == "二十五" and cr.cn_age(10) == "十" and cr.cn_age(43) == "四十三"
    assert "阶段状态" in cr.REQUIRED
    # 体与用分层：表现层与说话方式、能力与漏洞带底色与走向前缀，定论段不带
    assert "- 表现层（底色）：" in reader and "- 表现层（走向）：" in reader and "- 底色：" in reader and "- 走向：" in reader
    assert "- 身份层：" in reader and "底色：身份层" not in reader and cr.LAYERED == ("说话方式", "能力与漏洞")


@pytest.mark.skipif(shutil.which("node") is None, reason="需要 node")
def test_checker_validates_stage_cards(tmp_path: Path) -> None:
    src = EX / "林昭"
    doc = json.loads((src / "人物" / "林昭.json").read_text(encoding="utf-8"))
    sec = next(s for s in doc["sections"] if s["title"] == "阶段状态")
    sec["stages"][1]["traits"][0]["aspect"] = "口头禅"          # 不在七面里
    sec["stages"][2]["stage"] = "D-9-戊寅"                        # 编号找不到
    sec["stages"][0], sec["stages"][3] = sec["stages"][3], sec["stages"][0]  # 次序乱
    sec["stages"][3]["label"] = ""
    (tmp_path / "人物").mkdir()
    p = tmp_path / "人物" / "林昭.json"
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    cmd = ["node", str(ROOT / "scripts" / "check-character.js"), str(p), "--chart", str(src / "命盘" / "林昭.json"),
           "--matrix", str(src / "命盘" / "矩阵.json"), "--timeline", str(src / "命盘" / "林昭.年表.json"), "--schedule", str(src / "命盘" / "日程.json")]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 1
    problems = [json.loads(x)["problem"] for x in r.stdout.strip().splitlines() if not json.loads(x).get("summary")]
    assert any("aspect 应为" in x for x in problems) and any("stage 编号" in x and "找不到" in x for x in problems)
    assert any("递增" in x for x in problems) and any("label 为空" in x for x in problems)
    # 体与用分层：底色不引 D-，走向要引在场的卡，定论段不标 layer，年表与两难要落到年份，表现层要分层
    doc = json.loads((src / "人物" / "林昭.json").read_text(encoding="utf-8"))
    by = {s["title"]: s for s in doc["sections"]}
    by["说话方式"]["traits"][0]["sources"].append("D-3-己卯-干-偏印")                      # 底色引了运
    del by["能力与漏洞"]["traits"][0]["layer"]                                               # 没标层
    next(t for t in by["能力与漏洞"]["traits"] if t.get("layer") == "走向")["sources"] = ["S-身弱"]  # 走向没引卡
    by["谎言"]["traits"][0]["layer"] = "底色"                                                # 定论段标了层
    by["年表与两难"]["traits"][0]["sources"] = ["D-3-己卯-基调"]                            # 按运分段
    next(t for t in by["性格表里"]["traits"] if t["text"].startswith("表现层") and t.get("layer") == "底色")["layer"] = "走向"  # 两条走向、没有底色
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 1
    problems = [json.loads(x)["problem"] for x in r.stdout.strip().splitlines() if not json.loads(x).get("summary")]
    for key in ("不引 D- 编号", "每条要标 layer", "引在场阶段卡的 D- 编号", "定论段，不标 layer", "引 L- 编号", "恰有一条走向，实有 2", "缺表现层的底色条"):
        assert any(key in x for x in problems), (key, problems)
    # 段落缺席也算问题
    doc["sections"] = [s for s in doc["sections"] if s["title"] != "阶段状态"]
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    assert any("阶段状态" in json.loads(x).get("section", "") and "缺席" in json.loads(x)["problem"] for x in r.stdout.strip().splitlines())


def test_format_roundtrip_and_examples_formatted() -> None:
    docs = list((EX / "沈砚" / "人物").glob("*.json")) + list((EX / "林昭" / "人物").glob("*.json")) + list((EX / "对照实验" / "人物").glob("*.json"))
    assert len(docs) == 7  # 六份加同盘换设定卡的 沈砚.现代
    for p in docs:
        raw = p.read_text(encoding="utf-8")
        assert cf.dumps(json.loads(raw)) == raw, p
    r = subprocess.run([PY, str(ROOT / "scripts" / "character_format.py"), *map(str, docs), "--check"], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout


def test_divergence_counts_stage_traits() -> None:
    doc = json.loads((EX / "林昭" / "人物" / "林昭.json").read_text(encoding="utf-8"))
    stripped = {**doc, "sections": [s for s in doc["sections"] if s["title"] != "阶段状态"]}
    assert cd.kinds(doc) > cd.kinds(stripped)
    assert "阶段状态" in cd.section_texts(doc) and cd.section_texts(doc)["阶段状态"]
    assert cd.id_kind("D-3-己卯-近-偏印") == "D-近-偏印" and cd.id_kind("D-4-戊寅-档-弱逆") == "D-档-弱逆"
    assert cd.compare(doc, stripped)["divergence"] > 0
