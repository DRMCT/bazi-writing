---
name: bazi-writing
description: 用八字给小说角色生成自洽的性格、童年、需要、关系与人生时间线，产出格式中立的人物档案，八字本身永不进入正文。触发：/bazi-writing、「用八字捏人」「排人物盘」「反推一个角色」。
---

# bazi-writing：作者侧的隐藏世界模拟器

设计稿见 DESIGN.md。本文只讲怎么用。**目前可用的是正推一条线**（给生日或四柱 → 命盘档案 → 人物档案 → 检查）；反推搜索、多人矩阵、年表展开、导出器还没做，遇到这些需求先告诉作者哪些能做哪些不能。

## 铁律

1. 命盘是建议，作者是天。作者的手动覆盖永远优先于命盘推导。
2. 所有排盘与查表由脚本完成，模型只做解读，不做心算。不许自己推四柱、算大运、认神煞。
3. 产物分作者本与读者本两套。读者本与任何导出本里不得出现干支、十神、神煞和"命中注定"式措辞，用检查器兜底。
4. 人物档案每条特质带溯源编号，编号必须在命盘档案的 features 索引里；没有依据的特质不写。

## 目录

在作者的项目根下：

```
命盘/                 作者本，永不进正文
  {角色}.json         命盘档案（脚本产出，含 features 索引）
  {角色}.推导.md      作者本解读，推导过程（可选）
人物/                 人物真相层，格式中立
  {角色}.json         人物档案主产物（bazi-character/v1）
  {角色}.md           作者本渲染（带溯源编号）
  {角色}.读者本.md    读者本渲染（剥掉编号）
```

样例：本 skill 目录下的 `examples/沈砚/`。

## 流程（正推）

### 1. 排盘

命令都在作者的项目根下执行，产物写进项目的 `命盘/` 与 `人物/`。脚本在本 skill 目录的 `scripts/` 里，命令中的 `$SKILL` 换成本 skill 的目录（加载时给出的 base directory）。Python 用本 skill 的 `.venv`：Windows 是 `.venv/Scripts/python`，macOS 与 Linux 是 `.venv/bin/python`；脚本零第三方依赖，运行期只要 tzdata 可用。

```bash
PYTHONPATH="$SKILL/scripts" "$SKILL/.venv/Scripts/python" -m bazi_core.chart --birth 1986-05-29T22:30 --lon 116.4 --gender male --name 张三 --age 30 > 命盘/张三.json
```

```bash
PYTHONPATH="$SKILL/scripts" "$SKILL/.venv/Scripts/python" -m bazi_core.chart --pillars 甲申 壬申 乙巳 戊寅 --gender male --epoch 300 --name 沈砚 --age 30 > 命盘/沈砚.json
```

- 现实历给 `--birth`（ISO 钟表时刻）加 `--tz`（默认 Asia/Shanghai）加 `--lon`（出生地经度）；架空历给 `--pillars` 四柱加 `--epoch`（出生所在故事纪年）加 `--start-age`（起运岁数，默认 3）。
- `--age N [N ...]` 附带这几岁的流年（如 `--age 8 29 34`），童年钉事件的那年和年表要用的年份一次给齐。
- **真太阳时按题材选开关**（DESIGN 4.2）：民国以前的角色，作者给的时辰本身是当地太阳时，加 `--no-true-solar`；1949 年以后按北京时间修正，给 `--lon`；民国看设定，城市可修正，乡下不修正。误用的后果是时柱跑到隔壁时辰。
- 排盘前问清三件事：性别（大运顺逆用）、时辰是否可靠（不可靠就只给三柱，去掉时柱）、题材年代（定真太阳时开关）。

### 2. 读命盘档案

档案里每节都带 `status` 与 `source`，解读时按状态区别对待：

| 节 | 内容 | 状态 |
|---|---|---|
| natal.structure | 取格：name 变格、base 月令本格、variation 变化路径、also 杂气兼用 | 按徐评例盘裁定 |
| geju | 格局成败救应取运条件（卡上原文）加 judge 逐盘判定（True/False/None） | 卡定稿；判定器覆盖率 85%，None 的条件自己按原句读 |
| strength | 旺衰比值、结论、得令得地得势、合局项、每项贡献 | v2 校准定稿；中和是临界盘，解读时自己补判并说理 |
| tiaohou | 调候用神（按节气段）、条件用神、不可缺、降格、忌 | 定稿 |
| relations | 刑冲合害（带方向与所化）、三合三会 | 定稿 |
| shensha / shenshaTags | 神煞落柱，加叙事标签（自起草译法，附古籍判词） | 神煞定稿；标签是自起草，可反用可弱化 |
| changsheng | 十二长生、纳音 | 定稿 |
| dayun / liunian | 大运表、指定岁流年 | 定稿 |
| features | 以上全部摊平成 {id, kind, text}，溯源编号从这里取 | |

规则表在本 skill 目录的 `references/`：`神煞_叙事标签.md`、`去术语词表.md`、`校核/` 下是每张表的古籍校核卡（要看某条规则的出处就翻卡）。十神性格表、六亲宫位表、岁运事件表、意象系统表还没写，这些部分凭 DESIGN 第 8 节的字段来源表自己推，并在特质的 note 里注明"自起草"。

### 3. 写人物档案

写 `人物/{角色}.json`，形态 `bazi-character/v1`（见 `$SKILL/scripts/character_render.py` 文档串）：

- 必备段落十二个：性格表里、童年事件、谎言、秘密、需要与想要、抵抗线、亲密关系模式、说话方式、能力与漏洞、意象系统、他人眼中的他、年表与两难。字段在场、值可以待补充（traits 空列表）。
- 按写法轮廓加可选段落（DESIGN 3.4）：webnovel 加口头禅与标志动作、功能位、主题命题；literary 加主题命题（前置）、视角声音、潜文本提示，意象系统重点写。
- 每条特质 `{"text", "sources": [编号], "note"}`。sources 至少一个，全部来自命盘的 features 索引。一个特质最好落到具体事实（哪一柱、哪步大运、哪个标签），不要只挂 DM。
- 字段的八字来源按 DESIGN 8.1 的表；抵抗线是防宿命感的关键：用神是他真正需要的，喜神是他以为想要的，戏在落差里。
- 读者本口径：写人不写命，所有句子都要能脱离八字成立。干支、十神、神煞、命中注定一类词只允许出现在 sources 里。

渲染：

```bash
"$SKILL/.venv/Scripts/python" "$SKILL/scripts/character_render.py" 人物/沈砚.json
```

```bash
"$SKILL/.venv/Scripts/python" "$SKILL/scripts/character_render.py" 人物/沈砚.json --reader
```

### 4. 检查

契约与溯源（必备段落齐、每条有编号、编号在命盘里找得到）：

```bash
node "$SKILL/scripts/check-character.js" 人物/沈砚.json
```

去术语（读者本与导出本零 error；warn 是常用词兼术语，人看上下文）：

```bash
node "$SKILL/scripts/check-terms.js" 人物/沈砚.读者本.md
```

反向自检（对作者本目录跑，零命中反而失败，证明检查器活着）：

```bash
node "$SKILL/scripts/check-terms.js" 命盘/ --expect-hits --summary
```

历史题材的纪年干支、意象里的桃花、对白里的算命先生，用 `--allow 词` 逐词放行，放行记录在项目里。

## 还没做的（遇到就明说）

- 反推搜索（约束 JSON → 找盘）、随机补位。
- 多人矩阵与关系注释、年表自动展开与两难生成、年度状态卡。
- 群像推演：人物在同一时间点互相反应，推出大纲与细纲。
- story 导出器与其他导出器。
- 换盘测试（同一约束换盘，两份人物档案差异度须过阈值）。
- 规则层其余表：十神性格、六亲宫位与童年推法、岁运事件类型、日支亲密关系、五行体质气质、谎言候选、弧光匹配、意象系统。
