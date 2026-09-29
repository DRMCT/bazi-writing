"""意象系统：查表层（DESIGN-人物层 1：用神五行给救赎意象，忌神五行给威胁意象，日主五行给看世界的材质）。

表在 tables/imagery.json（narrative-table/v1，三张分表）：五行一行（材质、救赎、威胁、背景、感官）、五神位置的部署、修正项。
for_chart 按用神档案给每个五行定位置（用、喜、忌、仇、闲）取对应意象族，日主五行取材质，病神另记一条"长在他身上的意象"；
修正项：cold / dry（月令与调候）、tiaohou_absent（调候之神命局全无）、day_branch_element / month_branch_element（家与出身的材质）、
shensha_{名}（命局有该神煞；红艳并入桃花一条）。
编号前缀 IM：IM-材质-{五行}、IM-{位置}-{五行}、IM-病-{五行}、IM-日支-{五行}、IM-月支-{五行}、IM-{cond}、IM-神煞-{名}。
"""

from __future__ import annotations

import json
from pathlib import Path

from . import shensha as _ss
from .shishen import BRANCHES, HIDDEN_STEMS, STEMS, WUXING, element_of

_TABLE_PATH = Path(__file__).resolve().parent / "tables" / "imagery.json"
_T = json.loads(_TABLE_PATH.read_text(encoding="utf-8"))
_SEC = {s["key"]: s for s in _T["sections"]}
_BY_EL = {r["element"]: r for r in _SEC["elements"]["rows"]}
_ROLES = {r["role"]: r for r in _SEC["roles"]["rows"]}
_MODS = {r["cond"]: r for r in _SEC["modifiers"]["rows"]}
_IMAGE_COL = {"用": "yong", "喜": "yong", "忌": "ji", "仇": "ji", "闲": "xian"}
_LABEL = {"yong": "救赎意象", "ji": "威胁意象", "xian": "背景意象"}


def table() -> dict:
    return _T


def _branch_el(branch: str) -> str:
    return WUXING[element_of(HIDDEN_STEMS[BRANCHES.index(branch)][0])]


def for_chart(pillars: dict, ys: dict, shensha_hits: list[dict] | None = None) -> dict:
    dm_el = WUXING[element_of(STEMS.index(pillars["day"][0]))]
    feats: list[dict] = []
    material = _BY_EL[dm_el]["material"]
    feats.append({"id": f"IM-材质-{dm_el}", "kind": "意象", "text": f"日主{pillars['day'][0]}属{dm_el}，看世界的材质：{material}"})
    families = []
    for el in WUXING:
        role = ys["roles"][el]
        key = role[0]
        col = _IMAGE_COL[key]
        images = _BY_EL[el][col]
        deploy = _ROLES[key]["deploy"]
        fid = f"IM-{key}-{el}"
        families.append({"id": fid, "element": el, "role": role, "kind": _LABEL[col], "images": images,
                         "deploy": deploy, "frequency": _ROLES[key]["frequency"]})
        feats.append({"id": fid, "kind": "意象", "text": f"{el}为{role}神，{_LABEL[col]}：{images}（{deploy}）"})
    bing = ys.get("bing")
    if bing:
        el = bing["element"]
        fid = f"IM-病-{el}"
        families.append({"id": fid, "element": el, "role": "病", "kind": "贴身意象", "images": _BY_EL[el]["ji"],
                         "deploy": _ROLES["病"]["deploy"], "frequency": _ROLES["病"]["frequency"]})
        feats.append({"id": fid, "kind": "意象",
                      "text": f"{el}为病神（{bing['family']}过多），长在他身上的意象：{_BY_EL[el]['ji']}；{_ROLES['病']['deploy']}"})
    mods: list[dict] = []

    def mod(cond: str, fid: str, text: str, **extra) -> None:
        row = _MODS[cond]
        mods.append({"id": fid, "cond": cond, "when": row["when"], "effect": row["effect"], "anchors": row["anchors"], **extra})
        feats.append({"id": fid, "kind": "意象修正", "text": text})

    mb = pillars["month"][1]
    th = ys.get("tiaohou") or {}
    th_el, th_present = th.get("element"), th.get("present")
    # 调候之神落在忌、仇一侧时（用神模块"调候在忌一侧仍用扶抑"），能解寒燥的那一族同时在耗他：饮鸩止渴，不是单纯的救赎
    th_role = ys["roles"].get(th_el, "") if th_el else ""
    poison = f"；但{th_el}在此盘为{th_role}神，能解他{{}}的东西同时在耗他，这一族写成饮鸩止渴：越靠近越舒服，越舒服越坏" if th_role[:1] in ("忌", "仇") else ""
    if mb in "亥子丑" and th_el == "火":
        mod("cold", "IM-cold", f"{mb}月生而调候要火：{_MODS['cold']['effect']}{poison.format('寒')}", poison=bool(poison))
    if mb in "巳午未" and th_el == "水":
        mod("dry", "IM-dry", f"{mb}月生而调候要水：{_MODS['dry']['effect']}{poison.format('燥')}", poison=bool(poison))
    if th_el and th_present is False:
        mod("tiaohou_absent", "IM-tiaohou_absent", f"调候之神{th_el}命局全无：{_MODS['tiaohou_absent']['effect']}", element=th_el)
    db_el = _branch_el(pillars["day"][1])
    mod("day_branch_element", f"IM-日支-{db_el}", f"日支{pillars['day'][1]}属{db_el}，家与亲密空间的材质：{_BY_EL[db_el]['material']}", element=db_el)
    mb_el = _branch_el(mb)
    mod("month_branch_element", f"IM-月支-{mb_el}", f"月支{mb}属{mb_el}，出身环境的材质：{_BY_EL[mb_el]['material']}", element=mb_el)
    hits = shensha_hits if shensha_hits is not None else _ss.compute(pillars)
    for name in sorted({h["name"] for h in hits}):
        cond = "shensha_桃花" if name == "红艳" else f"shensha_{name}"
        if cond in _MODS and not any(m["cond"] == cond for m in mods):
            mod(cond, f"IM-神煞-{cond[len('shensha_'):]}", f"命局有{name}：{_MODS[cond]['effect']}", shensha=name)
    return {"material": {"id": f"IM-材质-{dm_el}", "element": dm_el, "text": material, "senses": _BY_EL[dm_el]["senses"],
                         "anchors": _BY_EL[dm_el]["anchors"]},
            "families": families, "modifiers": mods, "features": feats,
            "status": "叙事映射自起草；材质栏据十干卡的性与象", "source": _TABLE_PATH.name}
