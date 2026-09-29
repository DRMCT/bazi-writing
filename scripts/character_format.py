#!/usr/bin/env python3
"""人物档案 JSON 的固定排版：外层缩进两格，设定卡每个槽位一行，每条特质一行，阶段状态段每张卡的头一行并排、特质逐行。

    python scripts/character_format.py 人物/沈砚.json [更多文件]     原地重排
    python scripts/character_format.py 人物/沈砚.json --check         只检查，不一致退出码 1

样例与作者项目里的档案都按这个排，diff 才只落在真改的那几行；模型改档案时用 dumps() 写回，不要直接 json.dump。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def _j(v) -> str:
    return json.dumps(v, ensure_ascii=False)


# 设定卡（DESIGN-人物层 5）的槽位次序：时代与世界在前，八个社会位置槽位按十神与宫位的来源排，作者自加的键排最后
SETTING_KEYS = ("period", "world", "authority", "elders", "union", "inlaws", "path", "legacy", "money", "output")


def _setting(v: dict) -> list[str]:
    keys = [k for k in SETTING_KEYS if k in v] + [k for k in v if k not in SETTING_KEYS]
    if not keys:
        return ['  "setting": {},']
    lines = ['  "setting": {']
    lines += [f"    {_j(k)}: {_j(v[k])}" + ("," if i < len(keys) - 1 else "") for i, k in enumerate(keys)]
    lines.append("  },")
    return lines


def _trait(t: dict) -> str:
    keys = [k for k in ("aspect", "layer", "text", "sources", "note") if k in t] + [k for k in t if k not in ("aspect", "layer", "text", "sources", "note")]
    return "{" + ", ".join(f"{_j(k)}: {_j(t[k])}" for k in keys) + "}"


def _stage(st: dict, ind: str) -> list[str]:
    head_keys = [k for k in st if k != "traits"]
    lines = [f"{ind}{{", f"{ind}  " + ", ".join(f"{_j(k)}: {_j(st[k])}" for k in head_keys) + ","]
    traits = st.get("traits", [])
    if traits:
        lines.append(f'{ind}  "traits": [')
        lines += [f"{ind}    {_trait(t)}" + ("," if i < len(traits) - 1 else "") for i, t in enumerate(traits)]
        lines.append(f"{ind}  ]")
    else:
        lines.append(f'{ind}  "traits": []')
    lines.append(f"{ind}}}")
    return lines


def dumps(doc: dict) -> str:
    lines = ["{"]
    keys = list(doc)
    for k in keys:
        if k == "sections":
            continue
        if k == "setting" and isinstance(doc[k], dict):
            lines += _setting(doc[k])
            continue
        lines.append(f"  {_j(k)}: {_j(doc[k])},")
    lines.append('  "sections": [')
    secs = doc.get("sections", [])
    for si, sec in enumerate(secs):
        lines.append("    {")
        lines.append(f'      "title": {_j(sec["title"])},')
        extra = [k for k in sec if k not in ("title", "traits", "stages")]
        for k in extra:
            lines.append(f"      {_j(k)}: {_j(sec[k])},")
        if "stages" in sec:
            stages = sec["stages"]
            if stages:
                lines.append('      "stages": [')
                for i, st in enumerate(stages):
                    block = _stage(st, "        ")
                    if i < len(stages) - 1:
                        block[-1] += ","
                    lines += block
                lines.append("      ]")
            else:
                lines.append('      "stages": []')
        else:
            traits = sec.get("traits", [])
            if traits:
                lines.append('      "traits": [')
                lines += [f"        {_trait(t)}" + ("," if i < len(traits) - 1 else "") for i, t in enumerate(traits)]
                lines.append("      ]")
            else:
                lines.append('      "traits": []')
        lines.append("    }" + ("," if si < len(secs) - 1 else ""))
    lines.append("  ]")
    lines.append("}")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    check = "--check" in argv
    paths = [Path(a) for a in argv if a != "--check"]
    bad = 0
    for p in paths:
        raw = p.read_text(encoding="utf-8")
        doc = json.loads(raw)
        out = dumps(doc)
        assert json.loads(out) == doc, p
        if out != raw:
            if check:
                print("排版不一致", p)
                bad += 1
            else:
                p.write_text(out, encoding="utf-8", newline="\n")
                print("→", p)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
