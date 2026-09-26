#!/usr/bin/env python3
"""人物档案 JSON → markdown。JSON 是主产物（人物/{角色}.json），md 是投影。

    python scripts/character_render.py 人物/沈砚.json                 → 作者本 人物/沈砚.md（每条特质带溯源编号）
    python scripts/character_render.py 人物/沈砚.json --reader        → 读者本 人物/沈砚.读者本.md（剥掉编号与作者本段落）
    python scripts/character_render.py 人物/沈砚.json --out 路径

JSON 形态（bazi-character/v1）：
    {"schema": "bazi-character/v1", "name": "沈砚", "chart": "命盘/沈砚.json", "profile": "webnovel|literary",
     "setting": {"period": "古代|近代|现代|未来|异世界", "world": "一句话", "authority": "…", "elders": "…", "union": "…",
                 "inlaws": "…", "path": "…", "legacy": "…", "money": "…", "output": "…"},
     "summary": "一句话人物真相",
     "sections": [{"title": "性格表里", "traits": [{"text": "……", "sources": ["T-月干-正印", "S-中和"], "note": "可选"}]}, ...]}
必备段落十三个（DESIGN 3.2；第十三段"阶段状态"用 stages 而不是 traits，见下），可选段落按 profile（DESIGN 3.4）；
字段在场、值可以待补充（traits 或 stages 为空列表）。
设定卡 setting（DESIGN 3.6）：period 必填，其余槽位是传统词对应的社会位置，作者本渲染成一块，读者本不渲染。
体与用分层（DESIGN 8.3）：说话方式、能力与漏洞两段每条带 "layer": "底色"|"走向"，性格表里只有表现层那条分底色与走向；
渲染时前缀"底色："或"走向："，表现层写成"表现层（底色）："。其余段落是定论，不带 layer。
情绪过程（可选段，写戏用，2026-09-25）：每条带 "beat": "碰线"|"身体先动"|"盖法"|"余波"，是命局定的定论段，不带 layer；
渲染时前缀"碰线："等；导出到 story 时成为角色卡的"情绪过程（写戏用）"块。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

REQUIRED = ["性格表里", "童年事件", "谎言", "秘密", "需要与想要", "抵抗线", "亲密关系模式", "说话方式",
            "能力与漏洞", "意象系统", "他人眼中的他", "年表与两难", "阶段状态"]
AUTHOR_ONLY = {"年表与两难": False}  # 目前没有只给作者看的段落；溯源编号本身是作者本才有的东西
# 阶段状态段（DESIGN 10 第 6 条前半）的形态：{"title": "阶段状态", "stages": [{"stage": "D-3-己卯", "ages": [25, 35], "label": "……",
#   "traits": [{"aspect": "性格", "text": "……", "sources": [...], "note": "可选"}]}]}；aspect 取 STAGE_ASPECTS 之一，每步大运一张卡。
STAGE_ASPECTS = ("性格", "价值观与喜好", "说话方式", "需要的得失", "亲密关系动静", "能力与漏洞", "关系变化")
LAYERED = ("说话方式", "能力与漏洞")  # 底色加走向的段；性格表里只有表现层那条分层
BEATS = ("碰线", "身体先动", "盖法", "余波")  # 情绪过程段每条的 beat：哪根线被碰、身体先怎么动、用什么盖住真情绪、余波拖到哪
BEAT_SECTION = "情绪过程"
SETTING_PERIODS = ("古代", "近代", "现代", "未来", "异世界")
SETTING_SLOTS = (("period", "时代"), ("world", "世界"), ("authority", "权力与规矩落在哪"), ("elders", "上一辈是谁"),
                 ("union", "结合的形式"), ("inlaws", "伴侣那边的人"), ("path", "体面的路"), ("legacy", "家底与留下的东西"),
                 ("money", "钱怎么来"), ("output", "拿得出手的东西"))
_DIGITS = "零一二三四五六七八九"


def cn_age(n: int) -> str:
    """周岁 → 汉字数字（0–199），与档案正文里"二十五岁"的写法一致。"""
    if n < 10:
        return _DIGITS[n]
    if n < 20:
        return "十" + (_DIGITS[n % 10] if n % 10 else "")
    if n < 100:
        return _DIGITS[n // 10] + "十" + (_DIGITS[n % 10] if n % 10 else "")
    return "一百" + (cn_age(n % 100) if n % 100 else "")


def _trait_line(t: dict, reader: bool, prefix: str = "") -> str:
    text = t.get("text") or "（待补充）"
    layer = t.get("layer")
    if layer:
        text = f"表现层（{layer}）：{text[len('表现层：'):]}" if text.startswith("表现层：") else f"{layer}：{text}"
    if reader:
        return f"- {prefix}{text}"
    src = "、".join(t.get("sources", []))
    note = f"（{t['note']}）" if t.get("note") else ""
    return f"- {prefix}{text}{note} ｜溯源 {src}" if src else f"- {prefix}{text}{note}"


def render(doc: dict, reader: bool) -> str:
    lines = [f"# {doc['name']}", ""]
    if not reader:
        lines += [f"人物档案（作者本）· 写法轮廓 {doc.get('profile', 'webnovel')} · 命盘 `{doc.get('chart', '')}`", ""]
        setting = doc.get("setting") or {}
        if setting:
            labels = dict(SETTING_SLOTS)
            lines += ["设定卡：" + " · ".join(f"{labels.get(k, k)} {setting[k]}" for k in ("period", "world") if setting.get(k))]
            lines += [f"- {labels.get(k, k)}：{setting[k]}" for k in [x for x, _ in SETTING_SLOTS[2:]] + [x for x in setting if x not in labels]
                      if setting.get(k)]
            lines.append("")
    if doc.get("summary"):
        lines += [doc["summary"], ""]
    for sec in doc["sections"]:
        lines += [f"## {sec['title']}", ""]
        if "stages" in sec:
            if not sec["stages"]:
                lines += ["（待补充）", ""]
                continue
            for st in sec["stages"]:
                a, b = st.get("ages", [None, None])
                span = f"{cn_age(a)}到{cn_age(b)}岁" if a is not None and b is not None else "（岁数待补充）"
                label = st.get("label") or "（待补充）"
                head = f"### {span}：{label}" if reader else f"### {span}：{label} ｜阶段 {st.get('stage', '')}"
                lines += [head, ""]
                for t in st.get("traits", []) or [{"text": ""}]:
                    prefix = f"{t['aspect']}：" if t.get("aspect") else ""
                    lines.append(_trait_line(t, reader, prefix))
                lines.append("")
            continue
        traits = sec.get("traits", [])
        if not traits:
            lines += ["（待补充）", ""]
            continue
        for t in traits:
            lines.append(_trait_line(t, reader, f"{t['beat']}：" if t.get("beat") else ""))
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("doc")
    ap.add_argument("--reader", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    src = Path(a.doc)
    doc = json.loads(src.read_text(encoding="utf-8"))
    out = Path(a.out) if a.out else src.with_name(src.stem + (".读者本.md" if a.reader else ".md"))
    out.write_text(render(doc, a.reader), encoding="utf-8", newline="\n")
    print("→", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
