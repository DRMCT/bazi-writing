#!/usr/bin/env python3
"""人物档案 → story 套装（oh-story 的 story-long-write / story-short-write）的设定文件。DESIGN-人物层 9 导出器，M7。

    python scripts/export_story.py 人物/林昭.json 人物/沈砚.json --target story-long --out ../书名 --main 林昭
    python scripts/export_story.py 人物/林昭.json 人物/沈砚.json --target story-short --out ../短篇标题
    python scripts/export_story.py 人物/林昭.json --target story-long --out ../书名 --year 337 --dry-run

story-long 写三样（长篇项目根 `--out` 下）：
    设定/角色/{角色}.md      主角卡或配角卡（character-basics.md 的字段），后接三层标签、动机链、语言风格档案（七维）、
                             人物弧线（阶段卡）、关键节点与两难、亲密关系模式、别人眼里的他；literary 轮廓另有意象与视角
    设定/关系.md             artifact-protocols.md 的关系总览表、关系演变、核心冲突关系；关系类型按矩阵边映射成
                             冲突型 / 联盟型 / 亲密型 / 权威型（DESIGN-命盘层 6：映射是导出器的事）
    设定/来源/bazi-writing.md  指向 命盘/ 与 人物/ 的说明。放子目录是因为 story 的提交钩子把 设定/ 直属的散文件当角色卡查"姓名"字段
story-short 只写一样：`--out` 下的 设定.md 里 `<!-- bazi-writing:start -->` 到 `<!-- bazi-writing:end -->` 之间的一段
（人设加关系表），文件已有就只换这一段，没有就建一个；短篇的设定.md 是单文件，其余段落是作者的。

输入：人物档案 JSON（bazi-character/v1）若干；命盘（doc.chart，相对档案所在项目根解析）给性别与生年；
矩阵 命盘/矩阵.json、日程 命盘/日程.json、推演 命盘/群像/推演.json 默认按第一份档案的项目根找，找不到就不写对应内容。
`--main` 默认取推演的 main，没有就第一份档案；`--year` 故事起始年，算年龄与标出当前阶段卡，默认取推演窗口的起点。
只用档案里读者本那一层的文字（text），不碰 sources 与 note，所以导出本天然过去术语检查；字段在场、值可以"待补充"，
沿用 story 的口径。每张卡末尾的 `## 作者补充` 段重导出时原样保留，退场方式、章节号一类作者定的东西写在那里。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bazi_core import matrix as matrix_mod  # noqa: E402
from character_render import cn_age  # noqa: E402

TABLES = Path(__file__).resolve().parent / "bazi_core" / "tables"
PENDING = "待补充"
START = "<!-- bazi-writing:start -->"
END = "<!-- bazi-writing:end -->"
AUTHOR_TAIL = "## 作者补充"
TARGETS = ("story-long", "story-short")
DOMAIN_PLAIN = {"六亲": "家人与血缘"}
GENDER = {"male": "男", "female": "女"}
# 矩阵边 A 看 B 的十神 → story 的关系类型与一句谁在上的说明。官杀是 B 压 A，财是 A 拿 B，印是 B 托 A，食伤是 A 护 B。
EDGE_TYPE = {
    "正官": ("权威型", "{B}在上，{A}守分寸"), "七杀": ("权威型", "{B}压着{A}"),
    "正财": ("权威型", "{A}在上，{B}是{A}守着的"), "偏财": ("权威型", "{A}在上，{B}是{A}顺手用的"),
    "正印": ("联盟型", "{B}托着{A}"), "偏印": ("联盟型", "{B}懂{A}，不暖"),
    "食神": ("联盟型", "{A}护着{B}"), "伤官": ("联盟型", "{A}替{B}出头，也拿{B}立威"),
    "比肩": ("联盟型", "同路人"), "劫财": ("冲突型", "抢同一样东西"),
}
ROLE_SIGN = {"用": 1, "喜": 1, "忌": -1, "仇": -1}
ROLE_PLAIN = {"用": "{A}缺的正是{B}这样的人", "喜": "{B}对{A}是助力", "忌": "{B}耗{A}", "仇": "{B}是{A}的对头", "闲": ""}
CLASH = ("六冲", "三刑", "自刑", "六害", "天克地冲")
BOND = ("六合", "三合", "半合", "天干合")


# ---------- 读档案 ----------

def _section(doc: dict, title: str) -> dict:
    for s in doc.get("sections", []):
        if s.get("title") == title:
            return s
    return {}


def _texts(doc: dict, title: str, layer: str | None = None) -> list[str]:
    out = []
    for t in _section(doc, title).get("traits", []):
        if layer and t.get("layer") != layer:
            continue
        if t.get("text"):
            out.append(t["text"])
    return out


def _after(text: str, prefix: str) -> str:
    return text[len(prefix):].lstrip("：:") if text.startswith(prefix) else text


def _join(items: list[str], sep: str = "；") -> str:
    items = [x for x in items if x]
    if not items:
        return PENDING
    return sep.join([x.rstrip("。；;") for x in items[:-1]] + [items[-1]])


def portrait(doc: dict) -> dict:
    """性格表里的六个固定条目，按前缀认；认不出的归"其他"。"""
    out: dict = {"身份": "", "外貌": "", "表现底色": "", "表现走向": "", "内核": "", "矛盾面": "", "其他": []}
    for t in _section(doc, "性格表里").get("traits", []):
        text = t.get("text", "")
        if text.startswith("身份层"):
            out["身份"] = _after(text, "身份层")
        elif text.startswith("体质与外貌"):
            out["外貌"] = _after(text, "体质与外貌")
        elif text.startswith("表现层"):
            out["表现走向" if t.get("layer") == "走向" else "表现底色"] = _after(text, "表现层")
        elif text.startswith("内核层"):
            out["内核"] = _after(text, "内核层")
        elif text.startswith("矛盾面"):
            out["矛盾面"] = _after(text, "矛盾面")
        elif text:
            out["其他"].append(text)
    return out


def needs(doc: dict) -> tuple[str, str]:
    need = want = ""
    for text in _texts(doc, "需要与想要"):
        if text.startswith("真正需要的"):
            need = _after(text, "真正需要的")
        elif text.startswith("以为想要的"):
            want = _after(text, "以为想要的")
    return need, want


def speech(doc: dict) -> dict:
    base = _texts(doc, "说话方式", "底色")
    avoid = [_after(x, "回避的话题") for x in base if x.startswith("回避的话题")]
    return {"节奏": [x for x in base if not x.startswith("回避的话题")], "回避": avoid, "走向": _texts(doc, "说话方式", "走向")}


# 口头禅与标志动作段 2026-09-25 废：卡上只要有一句可搬的话和一个可搬的动作，写手就每章搬一回。
# story 模板的这一栏照填，填的是指路：腔调在语言风格档案，身体反应在情绪过程。
NO_CATCH = "无固定口头禅；腔调见语言风格档案，身体反应见情绪过程（写戏用）"
BEAT_HEAD = "写他的戏按这四拍走，先碰线、身体先动、再盖、再余波；一场戏走一遍就够。下面写的是倾向，台词与动作由你现写。"


def beats(doc: dict) -> list[str]:
    return [f"{t['beat']}：{t['text']}" if t.get("beat") else t.get("text", "") for t in _section(doc, "情绪过程").get("traits", []) or []]


def role_line(doc: dict) -> str:
    return _join(_texts(doc, "功能位")) if _texts(doc, "功能位") else (doc.get("summary") or PENDING)


def stages(doc: dict) -> list[dict]:
    return _section(doc, "阶段状态").get("stages", []) or []


def _mentions(doc: dict, other: str) -> list[str]:
    return [x for x in _texts(doc, "他人眼中的他") if other in x]


def load_chart(doc_path: Path, doc: dict) -> dict | None:
    rel = doc.get("chart")
    if not rel:
        return None
    cand = doc_path.parent.parent / rel
    if not cand.exists():
        return None
    return json.loads(cand.read_text(encoding="utf-8"))


def person_facts(doc_path: Path, doc: dict, year: int | None) -> dict:
    chart = load_chart(doc_path, doc)
    gender = GENDER.get((chart or {}).get("gender"), PENDING)
    born = matrix_mod._anchor(chart) if chart else None
    age = year - born if (year is not None and born is not None) else None
    age_text = f"{cn_age(age)}岁（{year}年）" if age is not None and age >= 0 else PENDING
    return {"gender": gender, "born": born, "age": age, "age_text": age_text}


# ---------- 角色卡 ----------

def _bullets(items: list[str]) -> list[str]:
    return [f"- {x}" for x in items] or [f"- {PENDING}"]


def _arc_block(doc: dict, age: int | None) -> list[str]:
    lines = ["## 人物弧线（按阶段）", ""]
    cards = stages(doc)
    if not cards:
        return lines + [PENDING, ""]
    for c in cards:
        a, b = c.get("ages", [None, None])
        span = f"{cn_age(a)}到{cn_age(b)}岁" if a is not None and b is not None else "岁数待补充"
        now = "（当前）" if age is not None and a is not None and b is not None and a <= age < b else ""
        lines += [f"### {span}：{c.get('label') or PENDING}{now}", ""]
        lines += [f"- {t['aspect']}：{t['text']}" if t.get("aspect") else f"- {t.get('text') or PENDING}" for t in c.get("traits", [])] or [f"- {PENDING}"]
        lines.append("")
    return lines


def _common_blocks(doc: dict, p: dict, facts: dict, main: str | None) -> list[str]:
    need, want = needs(doc)
    sp = speech(doc)
    lines: list[str] = []
    theme = _texts(doc, "主题命题")
    if theme:
        lines += ["## 主题命题", ""] + _bullets(theme) + [""]
    lines += ["## 三层标签", "",
              f"- 身份标签：{p['身份'] or PENDING}",
              f"- 表现标签：{p['表现底色'] or PENDING}",
              f"- 内核标签：{p['内核'] or PENDING}",
              f"- 反差：{p['矛盾面'] or PENDING}", ""]
    lines += ["## 动机链", "",
              f"- 起因：{_join(_texts(doc, '童年事件'))}",
              f"- 意图：{want or PENDING}" + (f"（底下真正要的是：{need.rstrip('。')}）" if need else ""),
              f"- 约束：{_join(_texts(doc, '谎言'))}",
              f"- 风险：{_join(_texts(doc, '秘密'))}", ""]
    stage_speech = [f"{cn_age(c['ages'][0])}到{cn_age(c['ages'][1])}岁：{t['text']}"
                    for c in stages(doc) if c.get("ages") for t in c.get("traits", []) if t.get("aspect") == "说话方式"]
    lines += ["## 语言风格档案（七维）", "",
              f"1. 口癖和惯用语：{NO_CATCH}",
              f"2. 说话节奏：{_join(sp['节奏'][:1])}",
              f"3. 信息偏好：{_join(([f'回避的话题：{x}' for x in sp['回避']]) + _texts(doc, '视角声音'))}",
              f"4. 立场固定：{_join(_texts(doc, '潜文本提示') or theme)}",
              f"5. 身份影响措辞：{p['身份'] or PENDING}",
              f"6. 性格影响语气：{p['表现底色'] or PENDING}",
              f"7. 进度影响态度：{_join(sp['走向'] or stage_speech)}", ""]
    if beats(doc):
        lines += ["## 情绪过程（写戏用）", "", BEAT_HEAD, ""] + _bullets(beats(doc)) + [""]
    lines += _arc_block(doc, facts["age"])
    lines += ["## 关键节点与两难", ""] + _bullets(_texts(doc, "年表与两难")) + [""]
    lines += ["## 亲密关系模式", ""] + _bullets(_texts(doc, "亲密关系模式")) + [""]
    lines += ["## 别人眼里的他", ""] + _bullets(_texts(doc, "他人眼中的他")) + [""]
    if doc.get("profile") == "literary":
        lines += ["## 意象与视角", ""] + _bullets(_texts(doc, "意象系统") + _texts(doc, "视角声音") + _texts(doc, "潜文本提示")) + [""]
    return lines


def _header_note() -> list[str]:
    return ["> bazi-writing 导出本。重导出会覆盖『作者补充』之前的全部内容；要改人先改 人物/{角色}.json 再导出。"
            "作者本在作者项目根的 `人物/`，排出它们的原始数据在旁边的作者本目录里，都不进正文。", ""]


def main_card(name: str, doc: dict, facts: dict) -> str:
    p = portrait(doc)
    need, want = needs(doc)
    keywords = "／".join(x for x in (f"表现：{p['表现底色']}" if p["表现底色"] else "", f"内核：{p['内核']}" if p["内核"] else "",
                                    f"矛盾面：{p['矛盾面']}" if p["矛盾面"] else "") if x) or PENDING
    lines = [f"# {name} · 主角卡", ""] + _header_note() + [
        f"姓名：{name}",
        f"性别：{facts['gender']}",
        f"年龄：{facts['age_text']}",
        f"角色定位：{role_line(doc)}",
        f"身份标签：{p['身份'] or PENDING}",
        f"外貌特征：{p['外貌'] or PENDING}",
        f"性格关键词：{keywords}",
        f"核心目标：{want or PENDING}",
        f"核心动机：{need or PENDING}",
        f"致命弱点：{_join(_texts(doc, '抵抗线'))}",
        f"口头禅/标志动作：{NO_CATCH}", ""]
    lines += _common_blocks(doc, p, facts, None)
    return "\n".join(lines)


def support_card(name: str, doc: dict, facts: dict, main: str | None, main_doc: dict | None, edge_lines: list[str]) -> str:
    p = portrait(doc)
    rel = _mentions(doc, main) if main else []
    if main_doc is not None and main:
        rel += _mentions(main_doc, name)
    rel = rel or edge_lines
    traits = "／".join(x for x in (p["内核"], p["表现底色"]) if x) or PENDING
    lines = [f"# {name} · 配角卡", ""] + _header_note() + [
        f"姓名：{name}",
        f"性别：{facts['gender']}",
        f"年龄：{facts['age_text']}",
        f"角色功能：{role_line(doc)}",
        f"与主角关系：{_join(rel)}",
        f"核心特质：{traits}",
        f"标志性特征：{p['外貌'] or PENDING}",
        f"退场方式：{PENDING}", ""]
    lines += _common_blocks(doc, p, facts, main)
    return "\n".join(lines)


# ---------- 关系 ----------

def _tendency_rows() -> dict:
    t = json.loads((TABLES / "response_tendency.json").read_text(encoding="utf-8"))
    return {r["tenGod"]: r for r in t["rows"]}


def _edge_text(e: dict, rows: dict) -> str:
    """A 看 B 这条边的一句人话：回应倾向表的 carries 换上名字，再按用忌接靠近或躲压那一栏。"""
    a, b = e["from"], e["to"]
    row = rows.get(e["tenGod"], {})
    text = (row.get("carries") or "").replace("源", b)
    role = (e.get("yongji") or {}).get("role")
    if role in ("用", "喜") and row.get("near"):
        text += f"{a}偏靠近：{row['near'].replace('源', b)}"
    elif role in ("忌", "仇") and row.get("away"):
        text += f"{a}偏躲或压：{row['away'].replace('源', b)}"
    return text


def _pair_type(ab: dict, ba: dict) -> str:
    a, b = ab["from"], ab["to"]
    kind, why = EDGE_TYPE.get(ab["tenGod"], ("联盟型", ""))
    parts = [f"{kind}（{why.format(A=a, B=b)}）" if why else kind]
    branches = set((ab.get("dayPillar") or {}).get("branches", [])) | set((ab.get("dayPillar") or {}).get("tags", []))
    both_bad = ROLE_SIGN.get((ab.get("yongji") or {}).get("role"), 0) < 0 and ROLE_SIGN.get((ba.get("yongji") or {}).get("role"), 0) < 0
    if (branches & set(CLASH) or both_bad) and kind != "冲突型":
        parts.append("冲突型（一近就撞）" if branches & set(CLASH) else "冲突型（互相耗）")
    if branches & set(BOND) and kind != "亲密型":
        parts.append("亲密型（一近就粘）")
    return "／".join(parts)


def _pair_mood(ab: dict, ba: dict) -> str:
    s1 = ROLE_SIGN.get((ab.get("yongji") or {}).get("role"), 0)
    s2 = ROLE_SIGN.get((ba.get("yongji") or {}).get("role"), 0)
    if s1 > 0 and s2 > 0:
        return "正面"
    if s1 < 0 and s2 < 0:
        return "负面"
    if s1 * s2 < 0:
        return "复杂"
    tilt = s1 + s2
    return "中性偏正" if tilt > 0 else "中性偏负" if tilt < 0 else "中性"


def _segments(e: dict, window: list[int] | None = None) -> list[str]:
    """同步逆风与一顺一逆的年份段；有故事窗口就只留与窗口相交的段。"""
    a, b = e["from"], e["to"]
    def keep(s: dict) -> bool:
        return not window or (s["to"] >= window[0] and s["from"] <= window[1])
    out = [f"{s['from']}–{s['to']}年两人同陷逆风" for s in e.get("syncJi", []) if keep(s)]
    out += [f"{s['from']}–{s['to']}年{a}顺{b}逆" for s in e.get("aUpBDown", []) if keep(s)]
    return out


def _domains_plain(items: list[str]) -> str:
    return "、".join(DOMAIN_PLAIN.get(x, x) for x in items)


def relations(docs: dict[str, dict], main: str | None, mx: dict | None, schedule: dict | None, run: dict | None) -> str:
    lines = ["# 角色关系图", "", "> bazi-writing 导出本：关系类型按人物之间的边映射，章节号与当前状态等作者填；重导出会整份覆盖，作者的话写在末尾『作者补充』段。", ""]
    lines += ["## 关系总览", "", "| 角色 A | 角色 B | 关系类型 | 情感倾向 | 当前状态 | 起始章节 | 变化节点 |",
              "|--------|--------|---------|---------|---------|---------|---------|"]
    if not mx:
        lines += ["| " + " | ".join([PENDING] * 7) + " |", "", "没有矩阵文件，关系表空着；跑 bazi_core.matrix 后重导出。", ""]
        return "\n".join(lines)
    rows = _tendency_rows()
    edges = {(e["from"], e["to"]): e for e in mx.get("edges", [])}
    names = [n["name"] for n in mx.get("nodes", [])]
    pairs = [(a, b) for i, a in enumerate(names) for b in names[i + 1:] if (a, b) in edges and (b, a) in edges]
    pairs = [(b, a) if b == main else (a, b) for a, b in pairs]
    pairs.sort(key=lambda p: (0 if main in p else 1, names.index(p[0]), names.index(p[1])))
    inter = [x for x in (schedule or {}).get("intersections", [])]
    segs = (run or {}).get("outline", {}).get("segments", [])
    threads = (run or {}).get("threads", [])
    window = (run or {}).get("window")
    evolve: list[str] = []
    conflict: list[tuple[int, str]] = []
    for a, b in pairs:
        ab, ba = edges[(a, b)], edges[(b, a)]
        first = sorted((x for x in inter if set(x.get("people", [])) == {a, b}), key=lambda x: x["year"])
        first_year = min((x["year"] for x in first), default=None)
        state = _mentions(docs[a], b) if a in docs else []
        state += _mentions(docs[b], a) if b in docs else []
        turning = _segments(ab, window)
        my_threads = [t for t in threads if set(t.get("people", [])) == {a, b}]
        turning += [f"{t['since']}年起{DOMAIN_PLAIN.get(t.get('domain'), t.get('domain'))}上的账{t.get('status', '')}" for t in my_threads]
        row = [a, b, _pair_type(ab, ba), _pair_mood(ab, ba), _join(state) if state else _join([_edge_text(ab, rows)]),
               f"{PENDING}（{first_year}年首次交汇）" if first_year else PENDING, _join(turning) if turning else PENDING]
        lines.append("| " + " | ".join(x.replace("|", "／") for x in row) + " |")
        # 关系演变
        hot = [s for s in segs if {a, b} <= set(s.get("present", [])) and s.get("source") in (a, b)]
        start = f"{first_year}年两人第一次交汇" if first_year else PENDING
        if first:
            d = first[0].get("domains", {})
            moved = [f"{n}动的是{_domains_plain(d[n])}" for n in (a, b) if d.get(n)]
            if moved:
                start += "（" + "，".join(moved) + "）"
        evolve += [f"{a}<->{b}：", f"- 起点：{start}。{_edge_text(ab, rows)}{_edge_text(ba, rows)}"]
        turns = [f"{s['year']}年·{s.get('dilemma', '')}（事件源{s.get('source', '')}）" for s in hot]
        turns += [f"{t['since']}年起{DOMAIN_PLAIN.get(t.get('domain'), t.get('domain'))}上的账，{t.get('status', '')}：{t.get('note') or '待补充'}" for t in my_threads]
        evolve += [f"- 转折：{_join(turns)}", f"- 当前：{PENDING}", ""]
        score = (2 if "冲突型" in row[2] or "权威型" in row[2] else 0) + sum(1 for e in (ab, ba) if ROLE_SIGN.get((e.get("yongji") or {}).get("role"), 0) < 0)
        between_a = rows.get(ab["tenGod"], {}).get("between", "")
        between_b = rows.get(ba["tenGod"], {}).get("between", "")
        conflict.append((score, f"{a} vs {b}——{row[2]}；{a}对{b}在{between_a}之间，{b}对{a}在{between_b}之间。"))
    lines += ["", "## 关系演变", ""] + evolve
    lines += ["## 核心冲突关系", ""]
    top = sorted(conflict, key=lambda x: -x[0])[:3]
    lines += [f"{i + 1}. {text}" for i, (_, text) in enumerate(top)] or [PENDING]
    missing = [n for n in names if n not in docs]
    if missing:
        lines += ["", f"只排了盘、没有人物档案的角色：{'、'.join(missing)}；表里他们的状态按边写，卡没有导出。"]
    return "\n".join(lines) + "\n"


# ---------- 短篇 ----------

def short_block(docs: dict[str, dict], facts: dict[str, dict], main: str | None, mx: dict | None) -> str:
    lines = [START, "## 人设（bazi-writing 导出）", "",
             "> 导出本，重导出只替换这一段。作者本在作者项目根的 `人物/`，排出它们的原始数据在旁边的作者本目录里，都不进正文。", ""]
    order = [main] + [n for n in docs if n != main] if main in docs else list(docs)
    rows = _tendency_rows()
    edges = {(e["from"], e["to"]): e for e in (mx or {}).get("edges", [])}
    for name in order:
        doc, f, p = docs[name], facts[name], portrait(docs[name])
        need, want = needs(doc)
        sp = speech(doc)
        tag = "主角" if name == main else "配角"
        lines += [f"### {name}（{tag}）", "",
                  f"- 性别：{f['gender']}；年龄：{f['age_text']}",
                  f"- 身份：{p['身份'] or PENDING}",
                  f"- 表现／内核：{p['表现底色'] or PENDING}／{p['内核'] or PENDING}",
                  f"- 要什么：{_join([want, f'底下真正要的：{need}' if need else ''])}",
                  f"- 弱点：{_join(_texts(doc, '抵抗线'))}",
                  f"- 说话：{_join(sp['节奏'][:1])}"]
        if name != main and main:
            rel = _mentions(doc, main) + (_mentions(docs[main], name) if main in docs else [])
            if not rel and (name, main) in edges:
                rel = [_edge_text(edges[(name, main)], rows)]
            lines.append(f"- 与主角：{_join(rel)}")
        lines += ["- 关键节点：" + _join(_texts(doc, "年表与两难")), ""]
    lines += ["### 关系", "", "| 角色 A | 角色 B | 关系类型 | 情感倾向 | 一句话 |", "|--------|--------|---------|---------|-------|"]
    names = [n["name"] for n in (mx or {}).get("nodes", [])]
    pairs = [(a, b) for i, a in enumerate(names) for b in names[i + 1:] if (a, b) in edges and (b, a) in edges]
    pairs = [(b, a) if b == main else (a, b) for a, b in pairs]
    for a, b in pairs:
        ab, ba = edges[(a, b)], edges[(b, a)]
        lines.append(f"| {a} | {b} | {_pair_type(ab, ba)} | {_pair_mood(ab, ba)} | {_edge_text(ab, rows)} |")
    if not pairs:
        lines.append("| " + " | ".join([PENDING] * 5) + " |")
    lines += ["", END]
    return "\n".join(lines)


def splice_short(existing: str | None, block: str) -> str:
    if existing and START in existing and END in existing:
        pre, rest = existing.split(START, 1)
        _, post = rest.split(END, 1)
        return pre + block + post
    if existing:
        return existing.rstrip("\n") + "\n\n" + block + "\n"
    return "# 设定\n\n" + block + "\n"


# ---------- 写文件 ----------

def keep_author_tail(new: str, old: str | None) -> str:
    tail = f"\n{AUTHOR_TAIL}\n\n（导出不动这一段，退场方式、章节号、临时改动写这里。）\n"
    if old and AUTHOR_TAIL in old:
        tail = "\n" + old[old.index(AUTHOR_TAIL):]
        if not tail.endswith("\n"):
            tail += "\n"
    return new.rstrip("\n") + "\n" + tail


def source_note(target: str, cmd: str) -> str:
    return "\n".join([
        "# 人物来源：bazi-writing", "",
        "本书 `设定/角色/` 的角色卡与 `设定/关系.md` 由 bazi-writing 从人物档案导出。",
        "作者本在作者项目根的 `人物/`，排出它们的原始数据在旁边的作者本目录里（见 bazi-writing 的 SKILL.md 目录一节），都不进正文，也不复制到这里。",
        "这两个目录与书名目录并列放在项目根，不放进书名目录：story 的追踪、一致性检查与提交钩子只读书名目录，放外面它们就碰不到。",
        "要改人物，先改 `人物/{角色}.json`（每条特质带溯源编号，检查器会核），再重导出；每张卡末尾『作者补充』段导出时保留。",
        "卡上不给口头禅与标志动作，腔调在语言风格档案、身体反应在情绪过程，都是倾向；对白样本请写在『作者补充』段并标明是样本，写手会照抄引号里的话。", "",
        "导出命令：", "", "```bash", cmd, "```", ""])


def _write(path: Path, text: str, dry: bool, keep_tail: bool = False) -> None:
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if keep_tail:
        text = keep_author_tail(text, old)
    if dry:
        print("会写", path)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    print("→", path)


def _load_optional(explicit: str | None, default: Path) -> dict | None:
    p = Path(explicit) if explicit else default
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def export(doc_paths: list[Path], target: str, out: Path, main: str | None = None, year: int | None = None,
           mx: dict | None = None, schedule: dict | None = None, run: dict | None = None, dry: bool = False,
           cmd: str = "") -> list[Path]:
    docs: dict[str, dict] = {}
    facts: dict[str, dict] = {}
    for p in doc_paths:
        doc = json.loads(p.read_text(encoding="utf-8"))
        if doc.get("schema") != "bazi-character/v1":
            raise ValueError(f"{p} 不是 bazi-character/v1")
        docs[doc["name"]] = doc
    if main is None:
        main = (run or {}).get("main") if (run or {}).get("main") in docs else next(iter(docs))
    if year is None and (run or {}).get("window"):
        year = run["window"][0]
    for p in doc_paths:
        doc = json.loads(p.read_text(encoding="utf-8"))
        facts[doc["name"]] = person_facts(p, doc, year)
    written: list[Path] = []
    if target == "story-short":
        path = out / "设定.md"
        old = path.read_text(encoding="utf-8") if path.exists() else None
        _write(path, splice_short(old, short_block(docs, facts, main, mx)), dry)
        return [path]
    rows = _tendency_rows()
    edges = {(e["from"], e["to"]): e for e in (mx or {}).get("edges", [])}
    for name, doc in docs.items():
        if name == main:
            text = main_card(name, doc, facts[name])
        else:
            edge_lines = [_edge_text(edges[(name, main)], rows)] if (name, main) in edges else []
            text = support_card(name, doc, facts[name], main, docs.get(main), edge_lines)
        path = out / "设定" / "角色" / f"{name}.md"
        _write(path, text, dry, keep_tail=True)
        written.append(path)
    path = out / "设定" / "关系.md"
    _write(path, relations(docs, main, mx, schedule, run), dry, keep_tail=True)
    written.append(path)
    path = out / "设定" / "来源" / "bazi-writing.md"
    _write(path, source_note(target, cmd), dry)
    written.append(path)
    return written


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("docs", nargs="+", help="人物档案 JSON，第一份所在项目根用来找矩阵、日程、推演")
    ap.add_argument("--target", choices=TARGETS, required=True)
    ap.add_argument("--out", required=True, help="story 项目根（长篇）或短篇目录")
    ap.add_argument("--main", default=None, help="主角名，默认推演的 main 或第一份档案")
    ap.add_argument("--year", type=int, default=None, help="故事起始年（算年龄、标当前阶段卡），默认推演窗口起点")
    ap.add_argument("--matrix", default=None)
    ap.add_argument("--schedule", default=None)
    ap.add_argument("--run", default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    docs = [Path(x) for x in a.docs]
    root = docs[0].resolve().parent.parent
    mx = _load_optional(a.matrix, root / "命盘" / "矩阵.json")
    schedule = _load_optional(a.schedule, root / "命盘" / "日程.json")
    run = _load_optional(a.run, root / "命盘" / "群像" / "推演.json")
    cmd = "python export_story.py " + " ".join(f"人物/{p.name}" for p in docs) + f" --target {a.target} --out {a.out}"
    export(docs, a.target, Path(a.out), a.main, a.year, mx, schedule, run, a.dry_run, cmd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
