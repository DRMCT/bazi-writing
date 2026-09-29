"""五运六气：生年运气盘面、出生所值之气与体质表查表（DESIGN-命盘层 3.1 五运六气行、DESIGN-人物层 1 体质与外貌暗示、气质底色）。

盘面按运气年干支推：岁运（年干化五行，阳年太过阴年不及）、司天在泉（年支组）、客气六步、主气六步；
年关系：天符、岁会、天符兼岁会、同天符、同岁会、平气（后世推演）、岁运与司天、岁运与在泉的生克结构（为纲那一头作改写、另一头作背景）、
岁运与出生所值之步客气的生克结构（本仓推演，客气即司天在泉时不另判）、气交变"上临某气则病反"的五对；
出生所值之气：现实历按出生时刻对交气边界（大寒起每 60° 一步，almanac.term_time）定运气年与步，运气年以大寒为岁首、
年柱以立春换年，大寒到立春之间生的人两者不同，记 yunqiYearDiffers；架空历按月支取（tables/yunqi.json fictionalStep：
跨中气的月默认取中气后一段并标 stepUnresolved，丑月默认不翻年），作者可用 yunqi_step 指定（初之气…终之气、次年初之气、1–6）。
岁半之法：初二三之气以司天为纲，四五终之气以在泉为纲。客主加临只给五行结构与二火的君臣顺逆。
主次（DESIGN-命盘层 4 交感，2026-09-24-9）：年主干（六元正纪六十年纪一对干支一条，上中下合看，编号 YQ-年-{干支}）总起，
运为体、纲气为主、当步之气为用、修正为改写、另一头作背景，features 按此排，
hits 每条带 role，顶层 roles 按角色列编号；背景那一头只给气化与民病，不给体质句，免得同一股气写两遍。

查表常量与年关系判法从作者自己的排盘项目搬入，逐条对《素问》运气七篇的卡（references/校核/运气_盘面.md）；
体质表 tables/yunqi_body.json（narrative-table/v1，六张分表：岁运、平气、司天在泉、六步、年关系与加临修正、与调候寒燥的叠加）
的据卡栏指向 运气_岁运、运气_司天在泉、运气_六步 的卡，体质、外貌、气质三栏自起草。
两层（DESIGN-命盘层 4 病秧子问题，2026-09-24-10）：画像层只给体格与体感和一句薄弱处，据卡从五常政其化其德其候与气化取，文本不带民病、不给气质；
事件层 events 给疾病与情志候选（受邪之脏、民病、甚则、死不治、情志方向与轻相重相、上临病反）与严重档（和、显、危），role 事件，默认不写，
year_qi(流年干支) 给故事年岁气与疫季，timeline 在身心域被引动的年份挂 L-…-病候。
编号前缀 YQ：YQ-年-{干支}、YQ-岁运-{木运太过}、YQ-平气-{五行}、YQ-司天-{六气}、YQ-在泉-{六气}、YQ-气-{步}-{客气}、YQ-加临-{客生主}、
YQ-君臣-{君位臣}、YQ-天符、YQ-岁会、YQ-天符兼岁会、YQ-同天符、YQ-同岁会、YQ-运天-{运克天}、YQ-运泉-{泉克运}、YQ-运步-{气克运}、
YQ-叠-{寒上加寒}；事件层 YQ-档-{和}、YQ-病-{脾}、YQ-志-{怒}、YQ-上临-{司天}。
运气七篇论的是岁气与民病，没有"某年生人禀某气"之文，生年推底子是后世运气家的引申，表里的叙事栏都标自起草。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .almanac import term_time
from .shishen import BRANCHES, STEMS, WUXING

_TABLES = Path(__file__).resolve().parent / "tables"
_T = json.loads((_TABLES / "yunqi.json").read_text(encoding="utf-8"))
_B = json.loads((_TABLES / "yunqi_body.json").read_text(encoding="utf-8"))
_SEC = {s["key"]: s for s in _B["sections"]}

GROUPS = ["子午", "丑未", "寅申", "卯酉", "辰戌", "巳亥"]
STEP_LABELS: list[str] = _T["steps"]["labels"]
STEP_LON: list[float] = [float(x) for x in _T["steps"]["startLongitudes"]]
HOST_QI: list[str] = _T["hostQi"]["rule"]
GUEST_QI: dict[str, list[str]] = _T["guestQi"]["rule"]
QI_ELEMENT: dict[str, str] = _T["qiElement"]["rule"]
STEM_YUN: dict[str, str] = _T["stemYun"]["rule"]
_SITIAN = {r["groups"]: (r["sitian"], r["zaiquan"]) for r in _T["sitianZaiquan"]["rule"]}
_SUI_HUI: dict[str, str] = _T["suiHuiBranches"]["rule"]
_BRANCH_EL: dict[str, str] = _T["branchElement"]["rule"]
_FICTIONAL: dict[str, dict] = _T["fictionalStep"]["rule"]
NEXT_YEAR_STEP = "次年初之气"

_ROWS_SIXTY = {r["pair"]: r for r in _SEC["sixty"]["rows"]}
_ROWS_EVENTS = {r["yun"]: r for r in _SEC["events"]["rows"]}
_ROWS_GRADES = {r["grade"]: r for r in _SEC["grades"]["rows"]}
_ORGAN_EL = {"肝": "木", "心": "火", "脾": "土", "肺": "金", "肾": "水"}
_PAIR_OF = {gz: e["pairs"][0] + e["pairs"][1] for e in _T["sixtyYears"]["rule"] for gz in e["pairs"]}
_ROWS_SUIYUN = {r["yun"]: r for r in _SEC["suiyun"]["rows"]}
_ROWS_PINGQI = {r["element"]: r for r in _SEC["pingqi"]["rows"]}
_ROWS_TIANQUAN = {(r["qi"], r["position"]): r for r in _SEC["tianquan"]["rows"]}
_ROWS_STEP = {(r["group"], r["step"]): r for r in _SEC["steps"]["rows"]}
_ROWS_REL = {r["cond"]: r for r in _SEC["relations"]["rows"]}
_ROWS_OVERLAP = {r["cond"]: r for r in _SEC["overlap"]["rows"]}
# 年景表（2026-09-25，DESIGN-命盘层 4 副产品）：故事年一对干支一行，全书共享的年景；表还没起草时 year_qi 不带 scene
_YEAR_TABLE = _TABLES / "yunqi_year.json"
_ROWS_SCENE: dict[str, dict] = {}
if _YEAR_TABLE.exists():
    _Y = json.loads(_YEAR_TABLE.read_text(encoding="utf-8"))
    _ROWS_SCENE = {r["pair"]: r for s in _Y["sections"] for r in s["rows"]}
_OVERLAP_NAME = {"cold_same": "寒上加寒", "cold_opposite": "外热内寒", "dry_same": "燥上加燥", "dry_opposite": "外湿内燥"}
_FIRE = ("少阴君火", "少阳相火")
ROLES = ("主干", "体", "主", "用", "改写", "背景", "事件")
READING = ("画像层：年主干总起（上司天、中岁运、下在泉一句体格体感加一句薄弱处，六元正纪六十年纪）、运为体（岁运通主一年）、纲气为主（岁半之法定的那一头）、"
           "当步之气为用、修正为改写、另一头作背景；只给体格与体感和一句薄弱处，不给病、不给气质，体质段要引到主干、体或主，不能只引背景与改写。"
           "事件层：疾病与情志候选与严重档，默认不写，年表在身心域被引动的年份挂病候时由作者挑")


def tables() -> tuple[dict, dict]:
    return _T, _B


# ---------------------------------------------------------------- 干支与五行

def _sexagenary(pillar: str) -> int:
    s, b = STEMS.index(pillar[0]), BRANCHES.index(pillar[1])
    if s % 2 != b % 2:
        raise ValueError(f"干支不成对：{pillar}")
    return next(i for i in range(60) if i % 10 == s and i % 12 == b)


def _pillar_name(index: int) -> str:
    return STEMS[index % 10] + BRANCHES[index % 12]


def group_of(branch: str) -> str:
    return GROUPS[BRANCHES.index(branch) % 6]


def _generates(a: str, b: str) -> bool:
    return (WUXING.index(a) + 1) % 5 == WUXING.index(b)


def _overcomes(a: str, b: str) -> bool:
    return (WUXING.index(a) + 2) % 5 == WUXING.index(b)


# ---------------------------------------------------------------- 年关系

def year_pattern(year_pillar: str) -> dict:
    """一个运气年的盘面与年关系（方宜 wuyun_relations.year_pattern 的口径，夹具 wuyun_relations_60.json）。"""
    stem, branch = year_pillar[0], year_pillar[1]
    _sexagenary(year_pillar)
    yun = STEM_YUN[stem]
    tai_guo = STEMS.index(stem) % 2 == 0
    grp = group_of(branch)
    si_tian, zai_quan = _SITIAN[grp]
    heaven, earth = QI_ELEMENT[si_tian], QI_ELEMENT[zai_quan]
    yun_vs = _rel5(yun, heaven, "天")
    yun_vs_earth = _rel5(yun, earth, "泉")
    ping: str | None = None
    if tai_guo and _overcomes(heaven, yun):
        ping = "太过被抑"
    elif not tai_guo and heaven == yun:
        ping = "不及得司天之助"
    elif not tai_guo and _BRANCH_EL[branch] == yun:
        ping = "不及得年支之助"
    tian_fu = yun == heaven
    sui_hui = branch in _SUI_HUI[yun]
    return {
        "yearPillar": year_pillar,
        "group": grp,
        "yunElement": yun,
        "taiGuo": tai_guo,
        "suiYun": f"{yun}运{'太过' if tai_guo else '不及'}",
        "siTian": si_tian,
        "zaiQuan": zai_quan,
        "tianFu": tian_fu,
        "suiHui": sui_hui,
        "tianFuSuiHui": tian_fu and sui_hui,
        "tongTianFu": tai_guo and yun == earth,
        "tongSuiHui": (not tai_guo) and yun == earth,
        "yunVsSiTian": yun_vs,
        "yunVsZaiQuan": yun_vs_earth,
        "pingQi": ping,
    }


def _rel5(yun: str, other: str, tag: str) -> str:
    """岁运五行与另一路气五行的五种结构：同、运生X、X生运、运克X、X克运（X 为天、泉、气）。"""
    if yun == other:
        return "同"
    if _generates(yun, other):
        return f"运生{tag}"
    if _generates(other, yun):
        return f"{tag}生运"
    if _overcomes(yun, other):
        return f"运克{tag}"
    return f"{tag}克运"


def grade_of(pat: dict, rel_gov: str) -> tuple[str, str]:
    """严重档（DESIGN-命盘层 4 病秧子问题，卡 运气-盘面-运与司天、天符、岁会、太一天符、同天符同岁会、平气）：
    平气→和；太过之年天符（含太一天符）、同天符→危（执法其病速而危，贵人其病暴而死）；岁会、同岁会、运与为纲之气不相得→显（行令其病徐而持，不相得则病）；
    其余（相得、不加不临而相得）→和（气相得则和）。"""
    if pat["pingQi"]:
        return "和", f"平气（{pat['pingQi']}），偏性抹平"
    if pat["tianFuSuiHui"]:
        return "危", "太一天符（天符兼岁会），中贵人者其病暴而死"
    if pat["tianFu"]:
        return "危", "天符，中执法者其病速而危"
    if pat["tongTianFu"]:
        return "危", "同天符（太过而加），与天符同例"
    if pat["suiHui"]:
        return "显", "岁会，中行令者其病徐而持"
    if pat["tongSuiHui"]:
        return "显", "同岁会（不及而加），与岁会同例，病缠而不凶"
    if "克" in rel_gov:
        return "显", f"岁运与为纲之气不相得（{rel_gov}），不相得则病"
    return "和", f"岁运与为纲之气相得（{rel_gov}），气相得则和"


def year_qi(year_pillar: str) -> dict:
    """故事年的岁气（DESIGN-命盘层 4 事件层）：按流年干支查同一张表，给司天在泉、岁运、六步的气化与民病、疫季。年表在身心域被引动的年份用它写病候。"""
    pat = year_pattern(year_pillar)
    steps = []
    for k, label in enumerate(STEP_LABELS):
        r = _ROWS_STEP.get((pat["group"], label)) or {}
        steps.append({"label": label, "host": HOST_QI[k], "guest": GUEST_QI[pat["group"]][k], "climate": r.get("climate", ""),
                      "illness": r.get("illness", ""), "epidemic": r.get("epidemic", "")})
    ep = [f"{x['label']}（{x['epidemic']}）" for x in steps if x["epidemic"]]
    up, down = _ROWS_TIANQUAN.get((pat["siTian"], "司天")) or {}, _ROWS_TIANQUAN.get((pat["zaiQuan"], "在泉")) or {}
    out = {"yearPillar": year_pillar, "suiYun": pat["suiYun"], "siTian": pat["siTian"], "zaiQuan": pat["zaiQuan"], "group": pat["group"],
           "siTianIllness": up.get("illness", ""), "zaiQuanIllness": down.get("illness", ""), "steps": steps, "epidemicSteps": ep,
           "summary": f"流年{year_pillar}岁气：上{pat['siTian']}、中{pat['suiYun']}、下{pat['zaiQuan']}" + (f"；疫季 {'、'.join(ep)}" if ep else "；无疫季之文")}
    row = _ROWS_SCENE.get(_PAIR_OF.get(year_pillar, ""))
    if row and row.get("scene"):
        lab = row["labels"]
        out["scene"] = {"label": lab["yun"], "upper": lab["upper"], "lower": lab["lower"], "labelWhy": lab["yunWhy"],
                        "text": row["scene"], "epidemic": row.get("epidemicScene", ""), "anchors": row["anchors"]}
        out["summary"] += f"；年景{lab['yun']}"
    return out


def yun_vs_step(yun: str, guest: str, si_tian: str, zai_quan: str) -> str | None:
    """岁运与出生所值之步客气的五种结构（本仓推演，卡 运气-盘面-运与当步）；客气即司天或在泉时不另判，返回 None。"""
    if guest in (si_tian, zai_quan):
        return None
    return _rel5(yun, QI_ELEMENT[guest], "气")


def step_relation(host: str, guest: str) -> dict:
    """一步的客主加临：五行结构与二火的君臣顺逆。"""
    h, g = QI_ELEMENT[host], QI_ELEMENT[guest]
    if h == g:
        rel = "同气"
    elif _generates(g, h):
        rel = "客生主"
    elif _generates(h, g):
        rel = "主生客"
    elif _overcomes(g, h):
        rel = "客克主"
    else:
        rel = "主克客"
    jun: str | None = None
    if guest == "少阴君火" and host == "少阳相火":
        jun = "君位臣"
    elif guest == "少阳相火" and host == "少阴君火":
        jun = "臣位君"
    return {"host": host, "guest": guest, "relation": rel, "junChen": jun}


# ---------------------------------------------------------------- 出生所值之气

def step_from_instant(instant_utc: datetime) -> dict:
    """现实历：出生时刻 → 运气年（公历年，大寒起）与步序。"""
    if instant_utc.tzinfo is None:
        instant_utc = instant_utc.replace(tzinfo=timezone.utc)
    instant_utc = instant_utc.astimezone(timezone.utc)
    marks: list[tuple[datetime, int, int]] = []
    for y in (instant_utc.year - 1, instant_utc.year, instant_utc.year + 1):
        for k, lon in enumerate(STEP_LON):
            t = term_time(y, lon)
            if t is not None:
                marks.append((t, k, y))
    marks.sort(key=lambda m: m[0])
    cur = None
    for m in marks:
        if m[0] <= instant_utc:
            cur = m
    if cur is None:  # pragma: no cover
        raise RuntimeError("交气边界查找失败")
    return {"yunqiYear": cur[2], "index": cur[1], "unresolved": False, "by": "出生时刻"}


def _year_index_of(civil_year: int) -> int:
    return ((civil_year - 1984) % 60 + 60) % 60


def step_from_month(month_branch: str, override: str | int | None = None) -> dict:
    """架空历：月支 → 步序（默认与未定标记），或作者指定。返回 nextYear=True 表示翻到次年运气年。"""
    if override is not None:
        if override == NEXT_YEAR_STEP:
            return {"index": 0, "unresolved": False, "by": "作者指定", "nextYear": True}
        if isinstance(override, int) or (isinstance(override, str) and override.isdigit()):
            n = int(override)
            if not 1 <= n <= 6:
                raise ValueError(f"yunqi_step 须在 1 到 6 之间或为步名：{override}")
            return {"index": n - 1, "unresolved": False, "by": "作者指定", "nextYear": False}
        if override in STEP_LABELS:
            return {"index": STEP_LABELS.index(override), "unresolved": False, "by": "作者指定", "nextYear": False}
        raise ValueError(f"yunqi_step 认不得：{override}")
    r = _FICTIONAL[month_branch]
    out = {"index": r["step"], "unresolved": r["unresolved"], "by": "月支", "nextYear": False}
    if r["unresolved"]:
        after = r["after"]
        out["note"] = (f"月支{month_branch}跨{r['boundary']}，{r['boundary']}前为{STEP_LABELS[r['before']]}、后为"
                       f"{after if isinstance(after, str) else STEP_LABELS[after]}，默认取"
                       f"{STEP_LABELS[r['step']]}{'（不翻年）' if month_branch == '丑' else ''}，可用 --yunqi-step 指定")
    return out


# ---------------------------------------------------------------- 查表进命盘

def _cell(row: dict | None, key: str) -> str:
    return (row or {}).get(key) or ""


def _strip_bing(zheng: str) -> str:
    """画像层文本里去掉六政逐运句的"其病……"与"其变……"（发作相归事件层，据卡原句仍在 row 里）。"""
    import re
    return re.sub(r"，其(?:病|变)[^，；]*", "", zheng)


def for_chart(pillars: dict, instant_utc: datetime | None, ys: dict | None = None,
              yunqi_step: str | int | None = None) -> dict:
    """命盘 yunqi 节：盘面、出生所值之气、年关系、体质表命中的行与 YQ- 编号。ys 是用神档案（取调候之神看寒燥叠加）。

    画像层 features 与 hits 按主次排（DESIGN-命盘层 4 交感）：年主干（六十年纪上中下一句体格体感加薄弱处）→ 运为体（岁运、平气）→ 纲气为主（岁半之法定的那一头）
    → 当步之气为用 → 修正为改写（运与司天在泉、运与当步、客主加临、君臣、年关系、平气、与调候叠加）→ 另一头作背景；只给体格体感，文本里不带民病。
    事件层（DESIGN-命盘层 4 病秧子问题）另列在后：严重档、疾病候选、情志候选、上临病反，role 事件，默认不写，年表在身心域被引动的年份挂病候时由作者挑。
    每条 hit 带 role，顶层 roles 按角色列编号，检查器据此要求体质段引到主干、体或主，不能只引背景与改写；事件类编号不受此约束。"""
    year_pillar = pillars["year"]
    if instant_utc is not None:
        st = step_from_instant(instant_utc)
        yq_pillar = _pillar_name(_year_index_of(st["yunqiYear"]))
        st_note = None
    else:
        st = step_from_month(pillars["month"][1], yunqi_step)
        yq_pillar = _pillar_name(_sexagenary(year_pillar) + 1) if st.get("nextYear") else year_pillar
        st_note = st.get("note")
    pat = year_pattern(yq_pillar)
    k = st["index"]
    label = STEP_LABELS[k]
    host, guest = HOST_QI[k], GUEST_QI[pat["group"]][k]
    rel = step_relation(host, guest)
    half = "司天" if k < 3 else "在泉"
    governing = pat["siTian"] if half == "司天" else pat["zaiQuan"]
    other_pos = "在泉" if half == "司天" else "司天"
    other_qi = pat["zaiQuan"] if half == "司天" else pat["siTian"]
    differs = yq_pillar != year_pillar

    feats: list[dict] = []
    hits: list[dict] = []
    roles: dict[str, list[str]] = {r: [] for r in ROLES}

    def add(fid: str, kind: str, role: str, text: str, row: dict | None = None, **extra) -> None:
        feats.append({"id": fid, "kind": kind, "text": text})
        hits.append({"id": fid, "kind": kind, "role": role, **extra, **({"row": row} if row is not None else {})})
        roles[role].append(fid)

    yr_note = f"运气年{yq_pillar}" + ("（大寒后立春前生，与年柱不同）" if differs else "")
    # 主干：六十年纪一对干支一条，上中下合看
    pair = _PAIR_OF[yq_pillar]
    r = _ROWS_SIXTY.get(pair)
    hua = "；".join(x for x in (_cell(r, "huaShu"), _cell(r, "zhengHua") + (f"，灾{_cell(r, 'zaiGong')}" if _cell(r, "zaiGong") else "")) if x)
    add(f"YQ-年-{yq_pillar}", "运气", "主干",
        f"{yr_note}本年气象（六元正纪{pair}条）：上{_cell(r, 'shang')}、中{_cell(r, 'zhong')}、下{_cell(r, 'xia')}（{_strip_bing(_cell(r, 'zheng'))}；{hua}"
        + (f"；{_cell(r, 'mark')}" if _cell(r, "mark") else "") + f"）：体格体感 {_cell(r, 'body')}；薄弱处 {_cell(r, 'weak')}",
        r, pair=pair)
    # 体：岁运（与平气）
    r = _ROWS_SUIYUN.get(pat["suiYun"])
    add(f"YQ-岁运-{pat['suiYun']}", "运气", "体",
        f"岁运{pat['suiYun']}，通主一年、为体（{_cell(r, 'ji')}之纪；{_cell(r, 'climate')}；{_cell(r, 'de')}）：体格外貌 {_cell(r, 'build')}；体感 {_cell(r, 'feel')}",
        r)
    if pat["pingQi"]:
        r = _ROWS_PINGQI.get(pat["yunElement"])
        add(f"YQ-平气-{pat['yunElement']}", "运气", "体",
            f"岁运得平（{pat['pingQi']}，后世推演）：{_cell(r, 'ji')}之纪，{_cell(r, 'climate')}；体感 {_cell(r, 'feel')}，太过不及的偏性按此打折、体格写匀称",
            r)
    # 主：岁半之法为纲的那一头
    r = _ROWS_TIANQUAN.get((governing, half))
    add(f"YQ-{half}-{governing}", "运气", "主",
        f"{pat['group']}年{governing}{half}，出生在岁半{'之前' if half == '司天' else '之后'}，此气为纲、为主（{_cell(r, 'climate')}）：体感 {_cell(r, 'feel')}",
        r, governing=True)
    # 用：出生所值之气
    r = _ROWS_STEP.get((pat["group"], label))
    how = {"出生时刻": "按出生时刻", "月支": f"架空历按月支{pillars['month'][1]}取", "作者指定": "作者指定"}[st["by"]]
    add(f"YQ-气-{label}-{guest}", "运气", "用",
        f"出生所值{label}，为用（{how}{'，未定' if st['unresolved'] else ''}）：主气{host}、客气{guest}（{_cell(r, 'climate')}）：体感 {_cell(r, 'feel')}"
        + (f"。{st_note}" if st_note else ""),
        r, unresolved=st["unresolved"])
    # 改写：运与为纲那一头（岁半之法）；另一头的结构放到背景里
    rel_gov_key, rel_gov = ("yunVsSiTian", pat["yunVsSiTian"]) if half == "司天" else ("yunVsZaiQuan", pat["yunVsZaiQuan"])
    rel_other_key, rel_other = ("yunVsZaiQuan", pat["yunVsZaiQuan"]) if half == "司天" else ("yunVsSiTian", pat["yunVsSiTian"])
    tag_gov, tag_other = ("运天", "运泉") if half == "司天" else ("运泉", "运天")
    cond_gov, cond_other = ("yun_vs_sitian", "yun_vs_zaiquan") if half == "司天" else ("yun_vs_zaiquan", "yun_vs_sitian")
    if rel_gov != "同":  # 同即天符或同天符、同岁会，年关系里已有
        r = _ROWS_REL.get(f"{cond_gov}:{rel_gov}")
        add(f"YQ-{tag_gov}-{rel_gov}", "运气修正", "改写",
            f"岁运{pat['yunElement']}与为纲的{half}{governing}：{rel_gov}：{_cell(r, 'effect')}", r, governing=True)
    # 改写：运与出生所值之步的客气（本仓推演；客气即司天、在泉时归上面）
    rel_step = yun_vs_step(pat["yunElement"], guest, pat["siTian"], pat["zaiQuan"])
    if rel_step:
        r = _ROWS_REL.get(f"yun_vs_step:{rel_step}")
        add(f"YQ-运步-{rel_step}", "运气修正", "改写",
            f"岁运{pat['yunElement']}与出生所值{label}的客气{guest}：{rel_step}（推演）：{_cell(r, 'effect')}", r)
    # 改写：客主加临与君臣
    r = _ROWS_REL.get(f"step:{rel['relation']}")
    add(f"YQ-加临-{rel['relation']}", "运气修正", "改写", f"本步客主加临{rel['relation']}（客{guest}、主{host}）：{_cell(r, 'effect')}", r)
    if rel["junChen"]:
        r = _ROWS_REL.get(f"jun_chen:{rel['junChen']}")
        add(f"YQ-君臣-{rel['junChen']}", "运气修正", "改写", f"二火互临，{rel['junChen']}：{_cell(r, 'effect')}", r)
    # 改写：年关系
    for flag, cond, fid, name in (("tianFu", "tian_fu", "YQ-天符", "天符"), ("suiHui", "sui_hui", "YQ-岁会", "岁会"),
                                   ("tianFuSuiHui", "tian_fu_sui_hui", "YQ-天符兼岁会", "天符、岁会同年"),
                                   ("tongTianFu", "tong_tian_fu", "YQ-同天符", "同天符"), ("tongSuiHui", "tong_sui_hui", "YQ-同岁会", "同岁会")):
        if pat[flag]:
            r = _ROWS_REL.get(cond)
            add(fid, "运气修正", "改写", f"{yq_pillar}年{_cell(r, 'when') or name}：{_cell(r, 'effect')}", r)
    if pat["pingQi"]:
        r = _ROWS_REL.get("ping_qi")
        add("YQ-平气修正", "运气修正", "改写", f"平气（{pat['pingQi']}）：{_cell(r, 'effect')}", r)
    # 改写：与调候寒燥的叠加
    th = (ys or {}).get("tiaohou") or {}
    th_el = th.get("element")
    mb = pillars["month"][1]
    cond = None
    if mb in "亥子丑" and th_el == "火":
        cond = "cold_same" if governing == "太阳寒水" else ("cold_opposite" if governing in _FIRE else None)
    elif mb in "巳午未" and th_el == "水":
        cond = "dry_same" if governing in _FIRE or governing == "阳明燥金" else ("dry_opposite" if governing in ("太阳寒水", "太阴湿土") else None)
    if cond:
        r = _ROWS_OVERLAP.get(cond)
        add(f"YQ-叠-{_OVERLAP_NAME[cond]}", "运气修正", "改写", f"{_cell(r, 'when')}：{_OVERLAP_NAME[cond]}，{_cell(r, 'effect')}", r)
    # 背景：运与另一头的结构，再是另一头本身（只给气化，不给体感句；据卡栏保留在 row 里）
    if rel_other != "同":
        r = _ROWS_REL.get(f"{cond_other}:{rel_other}")
        add(f"YQ-{tag_other}-{rel_other}", "运气修正", "背景",
            f"岁运{pat['yunElement']}与另一头的{other_pos}{other_qi}：{rel_other}，作背景：{_cell(r, 'effect')}", r, governing=False)
    r = _ROWS_TIANQUAN.get((other_qi, other_pos))
    bg_row = {key: r[key] for key in ("qi", "position", "groups", "climate", "anchors") if r and key in r}
    add(f"YQ-{other_pos}-{other_qi}", "运气", "背景",
        f"{pat['group']}年{other_qi}{other_pos}，{'下' if half == '司天' else '上'}半年的天气，作背景（{_cell(r, 'climate')}）：写人时一笔带过，体感按为纲的 YQ-{half}-{governing}",
        bg_row, governing=False)

    # 事件层（DESIGN-命盘层 4 病秧子问题）：严重档、疾病候选、情志候选、上临病反；默认不写，年表在身心域被引动的年份挂病候时由作者挑
    grade, grade_why = grade_of(pat, rel_gov)
    tempo = "太过者暴，病甚" if pat["taiGuo"] else "不及者徐，病持"
    g = _ROWS_GRADES.get(grade)
    add(f"YQ-档-{grade}", "运气事件", "事件",
        f"疾病与情志的严重档：{grade}（{grade_why}；{tempo}）：{_cell(g, 'write')}", g)
    e = _ROWS_EVENTS.get(pat["suiYun"]) or {}
    add(f"YQ-病-{e.get('organ', '')}", "运气事件", "事件",
        f"疾病候选（默认不写，年表身心域被引动的年份挑）：受邪之脏{e.get('organ', '')}，民病 {e.get('bing', '')}；轻相 {e.get('mild', '')}；重相 {e.get('severe', '')}"
        + (f"；死不治之候：{e.get('fatal')}" if e.get('fatal') else "；经文无死不治之候"),
        {key: e.get(key, "") for key in ("yun", "organ", "bing", "shen", "fatal", "bian", "mild", "severe", "anchors")})
    add(f"YQ-志-{e.get('zhi', '')}", "运气事件", "事件",
        f"情志候选（默认不写，与薄弱处同脏）：方向{e.get('zhi', '')}（{e.get('zhiFrom', '')}；其动其变 {e.get('bian', '')}）：轻相 {e.get('moodMild', '')}；重相 {e.get('moodSevere', '')}",
        {key: e.get(key, "") for key in ("yun", "organ", "zhi", "zhiFrom", "moodWords", "bian", "moodMild", "moodSevere", "anchors")})
    shang_lin = None
    if e and pat["siTian"] in [x for x in (e.get("shangLinQi") or "").split("、") if x]:
        shang_lin = {key: e.get(key, "") for key in ("yun", "shangLinQi", "shangLin", "shangLinEffect", "anchors")}
        add(f"YQ-上临-{pat['siTian']}", "运气事件", "事件",
            f"上临病反（气交变，岁运{pat['suiYun']}上临{pat['siTian']}：{e.get('shangLin', '')}）：{e.get('shangLinEffect', '')}", shang_lin)
    events = {"grade": grade, "gradeWhy": grade_why, "tempo": tempo, "organ": e.get("organ", ""), "organElement": _ORGAN_EL.get(e.get("organ", ""), ""),
              "zhi": e.get("zhi", ""), "zhiFrom": e.get("zhiFrom", ""),
              "illness": {key: e.get(key, "") for key in ("bing", "shen", "fatal", "mild", "severe")},
              "mood": {"words": e.get("moodWords", ""), "bian": e.get("bian", ""), "mild": e.get("moodMild", ""), "severe": e.get("moodSevere", "")},
              "shangLin": shang_lin, "ids": list(roles["事件"]),
              "note": "候选，默认不写进人物档案；年表在身心域被引动的年份挂 L-…-病候，作者挑，一步大运最多一次"}

    return {
        "algorithm": "yunqi/v1",
        "status": "盘面与年关系搬自方宜、对《素问》运气七篇卡；体格体感与疾病情志候选自起草；架空历按月支定步自起草；"
                  "画像层 features 按年主干、运为体、纲气为主、当步为用、修正为改写、另一头作背景排，不带民病（DESIGN-命盘层 4 交感）；事件层 events 默认不写（病秧子问题）",
        "reading": READING,
        "yearPillar": yq_pillar,
        "pair": pair,
        "yunqiYearDiffers": differs,
        "suiYun": pat["suiYun"],
        "yunElement": pat["yunElement"],
        "taiGuo": pat["taiGuo"],
        "siTian": pat["siTian"],
        "zaiQuan": pat["zaiQuan"],
        "group": pat["group"],
        "step": {"index": k, "label": label, "host": host, "guest": guest, "by": st["by"], "unresolved": st["unresolved"],
                 **({"note": st_note} if st_note else {}), "half": half, "governing": governing},
        "stepRelation": rel,
        "relations": {**{key: pat[key] for key in ("tianFu", "suiHui", "tianFuSuiHui", "tongTianFu", "tongSuiHui", "yunVsSiTian", "yunVsZaiQuan", "pingQi")},
                      "yunVsStep": rel_step},
        "overlap": cond,
        "events": events,
        "roles": roles,
        "hits": hits,
        "features": feats,
    }
