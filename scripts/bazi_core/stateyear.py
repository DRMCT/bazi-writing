"""年度状态卡（DESIGN-人物层 8，2026-09-24-11）：作者写到某一年时手边的那一页。

上半是人物档案里不随年变的定论（需要与想要、抵抗线、谎言、秘密、亲密关系模式）与这十年的阶段卡，原样抄来；
下半是这一年：几岁、大运在哪一步与顺逆、流年机制、动了哪些领域、哪条抵抗线在动（流年干支五行对此人是用喜还是忌仇）、
和谁的边被引动（群像快照）、群像推演这一年的事件卡里他在哪个位置、悬置的旧账、病候候选（默认不写）、当年岁气（yunqi.year_qi）。
稳定与时变分开写，不混。产物是作者本 markdown 草稿，每条带"｜溯源"编号，模型改成人话；读者本不需要这一页，它不进正文。
不产生新编号：引命盘 features、年表 L- 与 D-、快照 Q-、矩阵 E-、线程 TH-、档案里已有的编号。

命令行（在作者项目根下）：
    python -m bazi_core.stateyear 人物/林昭.json --chart 命盘/林昭.json --year 337 \\
        [--with 命盘/沈砚.json 命盘/裴恪.json] [--threads 命盘/群像/线程.json] [--run 命盘/群像/推演.json] > 人物/状态/林昭/337.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import ensemble as _en
from . import matrix as _mx
from . import timeline as _tl
from . import yongshen as yongshen_mod
from . import yunqi as yunqi_mod
from .shishen import BRANCHES, HIDDEN_STEMS, STEMS, WUXING, element_of

STABLE_TITLES = ("需要与想要", "抵抗线", "谎言", "秘密", "亲密关系模式")


def _src(ids: list[str]) -> str:
    return " ｜溯源 " + "、".join(ids) if ids else ""


def _cn_age(n: int) -> str:
    from character_render import cn_age  # 与档案渲染同一套数字写法
    return cn_age(n)


def build(doc: dict, chart: dict, year: int, others: list[dict] | None = None, threads: list[dict] | None = None,
          run: dict | None = None) -> tuple[str, list[str]]:
    """返回 (markdown, 用到的全部编号)。"""
    name = doc.get("name") or chart.get("name")
    if chart.get("name") and doc.get("name") and chart["name"] != doc["name"]:
        raise ValueError(f"人物档案 {doc['name']} 与命盘 {chart['name']} 不是同一个人")
    born = _mx._anchor(chart)
    if born is None:
        raise ValueError(f"{name} 没有纪年锚（现实历出生年或架空历 --epoch）")
    age = year - born
    if age < 0:
        raise ValueError(f"{year} 年 {name} 还没出生")
    used: list[str] = []

    def use(ids: list[str]) -> list[str]:
        for i in ids:
            if i not in used:
                used.append(i)
        return ids

    ys = chart.get("yongshen") or yongshen_mod.determine(chart["fourPillars"])
    steps = chart["dayun"]["steps"]
    y = _tl.year_facts(chart, age, ys, steps)
    head = f"L-{age}-{y['pillar']}"
    lines = [f"# {name} · {year}年状态卡（作者本）", "",
             f"写这一年章节时手边的一页。上半是画像里不随年变的定论与这十年的阶段卡，下半是这一年的状态；稳定与时变分开写，不混。草稿，模型改成人话；不进正文，读者本不需要。", ""]

    lines += ["## 稳定特质（画像，不随年变）", ""]
    by_title = {s["title"]: s for s in doc.get("sections", [])}
    for t in STABLE_TITLES:
        sec = by_title.get(t)
        for tr in (sec or {}).get("traits", []):
            lines.append(f"- {t}：{tr['text']}{_src(use(tr.get('sources', [])))}")
    lines.append("")

    stage_sec = by_title.get("阶段状态")
    card = next((c for c in (stage_sec or {}).get("stages", []) if c["ages"][0] <= age < c["ages"][1]), None)
    lines += ["## 这十年（阶段卡）", ""]
    if card:
        lines.append(f"{_cn_age(card['ages'][0])}到{_cn_age(card['ages'][1])}岁：{card['label']}{_src(use([card['stage'] + '-基调']))}")
        lines.append("")
        for tr in card.get("traits", []):
            lines.append(f"- {tr.get('aspect', '')}：{tr['text']}{_src(use(tr.get('sources', [])))}")
    else:
        lines.append(f"档案里没有覆盖{_cn_age(age)}岁的阶段卡。")
    lines.append("")

    lines += ["## 这一年", ""]
    st = y.get("dayun")
    seq = next((s for s in steps if st and s["pillar"] == st["pillar"] and s["startAge"] == st["startAge"]), None)
    tone = "顺" if y["score"] > 0 else "逆" if y["score"] < 0 else "平"
    ids = [f"Q-{year}-{name}", head] + ([f"D-{seq['sequence']}-{seq['pillar']}-基调"] if seq else [])
    lines.append(f"- 处境：{_cn_age(age)}岁，流年{y['pillar']}，大运{st['pillar'] if st else '未起运'}"
                 + (f"（{st['startAge']}至{st['endAge']}岁）" if st else "") + f"，这一年顺逆分 {y['score']}（{tone}）。{_src(use(ids))}")
    mech_ids = [f"{head}-{m}" for m in y["mechanisms"]]
    cand = _tl._is_candidate(y)
    lines.append(f"- 机制：{'、'.join(y['mechanisms']) or '无'}；{'候选年份，可出大事件' if cand else '不是候选年份，只有底色在动'}。{_src(use(mech_ids))}")
    if y["domains"]:
        for d in y["domains"]:
            lines.append(f"- 动{d['domain']}（权重 {d['weight']}）：{'；'.join(d['via'])}。{_src(use([f'{head}-域-{d['domain']}']))}")
    else:
        lines.append("- 领域：这一年没有领域在动，只按画像反应。")
    # 抵抗线在动：流年干支五行对此人的用忌
    s_el = WUXING[element_of(STEMS.index(y["pillar"][0]))]
    b_el = WUXING[element_of(HIDDEN_STEMS[BRANCHES.index(y["pillar"][1])][0])]
    roles = ys["roles"]
    rs, rb = roles[s_el], roles[b_el]
    feat_ids = {f["id"] for f in chart.get("features", [])}
    u_ids = list(dict.fromkeys(i for i in (f"U-{rs[0]}-{s_el}", f"U-{rb[0]}-{b_el}") if i in feat_ids))
    press = [r for r in (rs, rb) if r[0] in ("忌", "仇")]
    lift = [r for r in (rs, rb) if r[0] in ("用", "喜")]
    if press and lift:
        moving = f"一推一压：一头是需要的到了，一头是受不了的也到了；写拿着对的东西却站在错的地上，抵抗线两条同时在动"
    elif press:
        moving = f"受不了的临身：抵抗线第一条在动，{name}在对抗自己的忌神，最像自己也最容易闯祸"
    elif lift:
        moving = f"需要的到位：抵抗线第二条在动，看{name}会不会把真正需要的东西用错地方"
    else:
        moving = f"流年干支对{name}是闲神，抵抗线不动，按画像写"
    lines.append(f"- 抵抗线：流年天干{y['pillar'][0]}{s_el}为{rs}、地支{y['pillar'][1]}本气{b_el}为{rb}。{moving}。{_src(use(u_ids + [head]))}")
    if y.get("shensha"):
        lines.append(f"- 流年神煞：{'、'.join(y['shensha'])}。{_src(use([head]))}")
    # 关系：快照的边
    charts = [chart] + [c for c in (others or []) if c.get("name") != name]
    if len(charts) > 1:
        snap = _en.snapshot(charts, year)
        mine = [e for e in snap["edges"] if name in (e["from"], e["to"])]
        if mine:
            for e in mine:
                other = e["to"] if e["from"] == name else e["from"]
                who = f"{name}看{other}为{e['tenGod']}" if e["from"] == name else f"{other}看{name}为{e['tenGod']}"
                lines.append(f"- 关系被引动（{who}）：{'；'.join(r['text'] for r in e['reasons'])}。{_src(use(e['ids'] + [i for i in e['matrixIds'] if '十神' in i]))}")
        else:
            lines.append("- 关系：这一年没有边被引动，各人过各人的。")
    # 群像推演的事件卡
    if run:
        c = next((c for c in run.get("cards", []) if c["year"] == year), None)
        if c and name in c["present"]:
            ev = c["event"]
            if c["source"] == name:
                lines.append(f"- 群像：这一年{name}是事件源，事件是{name}的两难：{ev.get('dilemma') or ev.get('mechanismRaw')}。在场的还有{'、'.join(n for n in c['present'] if n != name) or '没有别人'}。"
                             f"{_src(use(c['intersections'] + [i for i in ev['ids'] if i.startswith('L-')]))}")
            else:
                t = next((t for t in c["tendencies"] if t["who"] == name), None)
                parts = [f"这一年事件源是{c['source']}（{ev.get('dilemma') or ev.get('mechanismRaw')}），{name}在场"]
                if t:
                    parts.append(f"看{c['source']}为{t['seesSourceAs']}，回应偏{t['lean']}：{t['text'].rstrip('。')}")
                    parts += [f"修正：{m['改写'].rstrip('。')}" for m in t["modifiers"]]
                lines.append("- 群像：" + "；".join(parts) + f"。{_src(use(c['intersections'] + (t['ids'] if t else [])))}")
            for th in c.get("threads", []):
                if name in th["people"]:
                    lines.append(f"- 旧账上卡：{th['id']}（{'、'.join(th['why'])}{'；' + '、'.join(th['rewrite']) + '换运，账要改写' if th['rewrite'] else ''}）"
                                 + (f"：{th['note']}" if th.get("note") else "") + f"。{_src(use([th['id']]))}")
        elif c:
            lines.append(f"- 群像：这一年是热年（事件源{c['source']}），但{name}不在场，只按画像过。{_src(use(c['intersections']))}")
        elif year in run.get("hotYears", []):
            pass
        else:
            lines.append("- 群像：这一年不是热年，过场。")
    # 悬置的旧账（线程文件）
    on_card = {i for i in used if i.startswith("TH-")}
    for th in threads or []:
        if name in th["people"] and th["status"] == "悬置" and th["since"] <= year and th["id"] not in on_card:
            other = th["people"][1] if th["people"][0] == name else th["people"][0]
            lines.append(f"- 悬置的账：与{other}在{th['domain']}上，{th['since']}年起" + (f"，{th['note']}" if th.get("note") else "")
                         + (f"；{'、'.join(str(v) for v in th['rewriteYears'])}年有人换运" if th.get("rewriteYears") else "") + f"。{_src(use([th['id']]))}")
    # 病候候选
    ic = _tl.illness_candidate(chart, y)
    if ic:
        lines.append(f"- 病候候选（默认不写，一步大运最多一次）：{ic['yearQi']}；此人{ic['grade']}档，薄弱处{ic['organ']}，取{ic['level']}：{ic['illness']}"
                     + (f"；危及性命之候 {ic['fatal']}" if ic["fatal"] else "") + f"；情志往{ic['zhi']}的方向垮：{ic['mood']}。{_src(use([f'{head}-病候']))}")
    # 当年岁气
    yq = yunqi_mod.year_qi(y["pillar"])
    lines.append(f"- 当年岁气（全书共享的年景，不带编号）：{yq['summary']}。")
    if yq.get("scene"):
        sc = yq["scene"]
        lines.append(f"- 年景（{sc['label']}，上半年偏{sc['upper']}、下半年偏{sc['lower']}）：{sc['text']}" + (f" 疫季：{sc['epidemic']}" if sc["epidemic"] else ""))
    lines += ["", f"草稿。稳定的在上面，这一年的在下面；写正文只用得上下半，上半是提醒{name}是谁。"]
    return "\n".join(lines) + "\n", used


def _main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="年度状态卡：人物档案 + 命盘 + 某一年 → 作者本一页")
    ap.add_argument("character", help="人物档案 JSON")
    ap.add_argument("--chart", required=True, help="命盘档案 JSON")
    ap.add_argument("--year", type=int, required=True, help="故事纪年")
    ap.add_argument("--with", dest="others", nargs="*", default=[], help="其他人的命盘，看这一年谁的边被引动")
    ap.add_argument("--threads", help="线程文件 群像/线程.json")
    ap.add_argument("--run", help="群像推演 群像/推演.json")
    ns = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    doc = json.loads(Path(ns.character).read_text(encoding="utf-8"))
    chart = json.loads(Path(ns.chart).read_text(encoding="utf-8"))
    others = [json.loads(Path(p).read_text(encoding="utf-8")) for p in ns.others]
    threads = None
    run = json.loads(Path(ns.run).read_text(encoding="utf-8")) if ns.run else None
    if ns.threads:
        from . import ensemble_run as _er
        threads = _er.load_threads(json.loads(Path(ns.threads).read_text(encoding="utf-8")))
        if run:  # 推演里的线程带 rewriteYears
            by_id = {t["id"]: t for t in run.get("threads", [])}
            threads = [by_id.get(t["id"], t) for t in threads]
    md, _ = build(doc, chart, ns.year, others, threads, run)
    sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
