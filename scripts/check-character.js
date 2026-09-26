#!/usr/bin/env node
// 人物档案契约与溯源检查（DESIGN 第 13 节）。
//
//   node scripts/check-character.js 人物/沈砚.json                  命盘路径取 JSON 里的 chart 字段（相对于人物档案所在目录的上一级，即项目根）
//   node scripts/check-character.js 人物/沈砚.json --chart 命盘/沈砚.json
//   node scripts/check-character.js 人物/沈砚.json --summary
//   node scripts/check-character.js 人物/沈砚.json --matrix 命盘/矩阵.json   另认多人矩阵的 E- 编号（只认从本人出发或指向本人的边）
//   node scripts/check-character.js 人物/沈砚.json --timeline 命盘/沈砚.年表.json   另认年表的 L- 与 D-…-基调 编号
//   node scripts/check-character.js 人物/沈砚.json --schedule 命盘/日程.json   另认配角日程的 J- 交汇编号（只认本人在场的交汇）
//   node scripts/check-character.js 人物/沈砚.json --run 命盘/群像/推演.json   另认群像推演的 Q-、TH- 编号与卡上重列的编号（idPool）
//
// 检查：schema 为 bazi-character/v1；十三个必备段落在场；每条特质 text 非空且 sources 非空；每个溯源编号在命盘 features 里存在；
// 同一段落内特质不重复。阶段状态段用 stages 而不是 traits：每张卡 stage 是命盘里的 D-{步}-{干支} 编号、ages 两个整数、label 非空、
// traits 至少一条且每条 aspect 取七面之一；卡按岁数递增、不重复；卡内特质与其他段落同样查溯源（阶段事实编号在年表里，要加 --timeline）。
// 体与用分层（DESIGN 8.3，2026-09-24）：说话方式、能力与漏洞两段每条标 layer 为底色或走向，至少一条底色，有阶段卡时恰一条走向；
// 性格表里只有表现层标底色，另恰一条走向（text 以"表现层"起头），身份层、内核层、矛盾面不标；其余段落是定论，不标 layer。
// 底色是命局不带运，不引 D- 编号；走向要引在场阶段卡的 D- 编号；年表与两难每条要引 L- 或 J- 编号落到年份（按运分段的写进阶段卡）；空段是待补充，不查层。
// 设定卡（DESIGN 3.6）：顶层 setting 必备，period 取古代、近代、现代、未来、异世界之一，world 一句话非空；其余槽位（authority、elders、union、
// inlaws、path、legacy、money、output）可缺（待补充），在场须是字符串；不认识的键报出来。
// 五运六气主次（DESIGN 7.4 交感，2026-09-24-9）：命盘 yunqi.roles 按角色列 YQ- 编号（主干、体、主、用、改写、背景）；引了 YQ- 的特质
// 至少要引到主干、体（岁运）或主（为纲的那一头）之一，不能只引背景与改写；命盘没有 roles（旧命盘）时不查。
// 事件类编号（roles.事件：YQ-档-、YQ-病-、YQ-志-、YQ-上临-）是疾病与情志候选，写在年表与两难里，不受这条约束。
// 每条问题一行 JSON {"file","section","trait","problem"}，最后一行汇总 {"summary":true,...}，有问题退出码 1。
"use strict";
const fs = require("fs");
const path = require("path");

const REQUIRED = ["性格表里", "童年事件", "谎言", "秘密", "需要与想要", "抵抗线", "亲密关系模式", "说话方式",
  "能力与漏洞", "意象系统", "他人眼中的他", "年表与两难", "阶段状态"];
const STAGE_ASPECTS = ["性格", "价值观与喜好", "说话方式", "需要的得失", "亲密关系动静", "能力与漏洞", "关系变化"];
const LAYERED = ["说话方式", "能力与漏洞"];  // 底色加走向的段；性格表里只有表现层这一条分底色与走向
const LAYERS = ["底色", "走向"];
const BEAT_SECTION = "情绪过程";  // 可选段，写戏用：每条带 beat，是定论段
const BEATS = ["碰线", "身体先动", "盖法", "余波"];
// 靶子实测（2026-09-25）：卡上带引号的句子会被写手原样搬进正文；这几段只写句式、场合与倾向，不给台词
const NO_QUOTE_SECTIONS = [BEAT_SECTION, "说话方式", "口头禅与标志动作", "语言习惯"];
// 2026-09-25 废：卡上只要有一句可搬的话和一个可搬的动作，写手就每章搬一回；腔调在说话方式，身体习惯并进情绪过程的身体先动
const DEPRECATED_SECTIONS = ["口头禅与标志动作", "语言习惯"];
const SETTING_PERIODS = ["古代", "近代", "现代", "未来", "异世界"];
const SETTING_KEYS = ["period", "world", "authority", "elders", "union", "inlaws", "path", "legacy", "money", "output"];

function main() {
  const argv = process.argv.slice(2);
  let chartPath = null, matrixPath = null, timelinePath = null, schedulePath = null, runPath = null, summaryOnly = false;
  const files = [];
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--chart") chartPath = argv[++i];
    else if (argv[i] === "--matrix") matrixPath = argv[++i];
    else if (argv[i] === "--timeline") timelinePath = argv[++i];
    else if (argv[i] === "--schedule") schedulePath = argv[++i];
    else if (argv[i] === "--run") runPath = argv[++i];
    else if (argv[i] === "--summary") summaryOnly = true;
    else files.push(argv[i]);
  }
  if (files.length !== 1) {
    console.error("用法：node scripts/check-character.js <人物档案.json> [--chart 命盘.json] [--matrix 矩阵.json] [--timeline 年表.json] [--schedule 日程.json] [--summary]");
    process.exit(2);
  }
  const file = files[0];
  const doc = JSON.parse(fs.readFileSync(file, "utf8"));
  const problems = [];
  const report = (section, trait, problem) => problems.push({ file, section, trait, problem });

  if (doc.schema !== "bazi-character/v1") report(null, null, `schema 应为 bazi-character/v1，实为 ${doc.schema}`);
  if (!doc.name) report(null, null, "缺 name");
  if (doc.setting === undefined) report("设定卡", null, "缺设定卡 setting（period 与 world 必填，其余槽位可待补充）");
  else if (!doc.setting || typeof doc.setting !== "object" || Array.isArray(doc.setting)) report("设定卡", null, "setting 应为对象");
  else {
    const st = doc.setting;
    if (!SETTING_PERIODS.includes(st.period)) report("设定卡", "period", `period 应为 ${SETTING_PERIODS.join("、")} 之一，实为 ${st.period}`);
    if (typeof st.world !== "string" || !st.world.trim()) report("设定卡", "world", "world 要一句话说清时代与世界");
    for (const k of Object.keys(st)) {
      if (!SETTING_KEYS.includes(k)) report("设定卡", k, `不认识的槽位 ${k}，可用：${SETTING_KEYS.join("、")}`);
      else if (k !== "period" && k !== "world" && typeof st[k] !== "string") report("设定卡", k, "槽位的值应为字符串");
    }
  }
  if (!chartPath) {
    if (!doc.chart) report(null, null, "缺 chart 字段且未给 --chart");
    else chartPath = path.resolve(path.dirname(path.resolve(file)), "..", doc.chart);
  }
  let ids = new Set();
  let yqCore = null;  // 五运六气可作体质依据的编号（主干、体、主）；null 表示命盘没有 roles，不查
  let yqEvent = new Set();
  if (chartPath && fs.existsSync(chartPath)) {
    const chart = JSON.parse(fs.readFileSync(chartPath, "utf8"));
    if (chart.yunqi && chart.yunqi.roles && typeof chart.yunqi.roles === "object") {
      const r = chart.yunqi.roles;
      yqCore = new Set([...(r["主干"] || []), ...(r["体"] || []), ...(r["主"] || [])]);
      yqEvent = new Set(r["事件"] || []);  // 疾病与情志候选（YQ-档-、YQ-病-、YQ-志-、YQ-上临-）：事件层，不受体质句的主干规则约束
    }
    if (!Array.isArray(chart.features)) report(null, null, `命盘 ${chartPath} 没有 features 索引，用 chart 命令行重新生成`);
    else {
      ids = new Set(chart.features.map(f => f.id));
      if (ids.size !== chart.features.length) {
        const dup = [...new Set(chart.features.map(f => f.id).filter((id, i, all) => all.indexOf(id) !== i))];
        report(null, null, `命盘 features 编号重复：${dup.join("、")}，用 chart 命令行重新生成`);
      }
    }
    if (doc.name && chart.name && chart.name !== doc.name) report(null, null, `人物档案 name ${doc.name} 与命盘 name ${chart.name} 不一致`);
  } else {
    report(null, null, `命盘文件不存在：${chartPath}`);
  }

  if (matrixPath) {
    if (!fs.existsSync(matrixPath)) report(null, null, `矩阵文件不存在：${matrixPath}`);
    else {
      const m = JSON.parse(fs.readFileSync(matrixPath, "utf8"));
      if (m.schema !== "bazi-matrix/v1") report(null, null, `矩阵 schema 应为 bazi-matrix/v1，实为 ${m.schema}`);
      for (const e of m.edges || []) {
        if (e.from !== doc.name && e.to !== doc.name) continue;
        for (const f of e.features || []) ids.add(f.id);
      }
    }
  }

  if (timelinePath) {
    if (!fs.existsSync(timelinePath)) report(null, null, `年表文件不存在：${timelinePath}`);
    else {
      const t = JSON.parse(fs.readFileSync(timelinePath, "utf8"));
      if (t.schema !== "bazi-timeline/v1") report(null, null, `年表 schema 应为 bazi-timeline/v1，实为 ${t.schema}`);
      if (doc.name && t.name && t.name !== doc.name) report(null, null, `年表 name ${t.name} 与人物档案 name ${doc.name} 不一致`);
      for (const f of t.features || []) ids.add(f.id);
    }
  }

  if (schedulePath) {
    if (!fs.existsSync(schedulePath)) report(null, null, `日程文件不存在：${schedulePath}`);
    else {
      const s = JSON.parse(fs.readFileSync(schedulePath, "utf8"));
      if (s.schema !== "bazi-schedule/v1") report(null, null, `日程 schema 应为 bazi-schedule/v1，实为 ${s.schema}`);
      for (const x of s.intersections || []) {
        if (doc.name && !(x.people || []).includes(doc.name)) continue;
        ids.add(x.id);
      }
    }
  }

  if (runPath) {
    if (!fs.existsSync(runPath)) report(null, null, `推演文件不存在：${runPath}`);
    else {
      const r = JSON.parse(fs.readFileSync(runPath, "utf8"));
      if (r.schema !== "bazi-ensemble-run/v1") report(null, null, `推演 schema 应为 bazi-ensemble-run/v1，实为 ${r.schema}`);
      if (doc.name && Array.isArray(r.people) && !r.people.includes(doc.name)) report(null, null, `推演的人物里没有 ${doc.name}`);
      for (const id of r.idPool || []) ids.add(id);  // Q-、TH- 与推演卡上重列的 E-、L-、J-、D-
    }
  }

  const sections = Array.isArray(doc.sections) ? doc.sections : [];
  const titles = new Set(sections.map(s => s.title));
  for (const r of REQUIRED) if (!titles.has(r)) report(r, null, "必备段落缺席");
  // 在场的阶段卡：走向要引它们的 D- 编号
  const cardStages = new Set(sections.filter(s => Array.isArray(s.stages)).flatMap(s => s.stages.map(st => st.stage)).filter(Boolean));
  const stageOf = id => id.split("-").slice(0, 3).join("-");
  let traits = 0, sourced = 0, stages = 0, trends = 0;
  const where = `命盘${matrixPath ? "、矩阵" : ""}${timelinePath ? "、年表" : ""}${schedulePath ? "、日程" : ""}${runPath ? "、推演" : ""}`;
  const checkTrait = (section, label, t, seen) => {
    traits++;
    const text = (t.text || "").trim();
    if (!text) { report(section, label, "text 为空"); return; }
    if (seen.has(text)) report(section, label, "段内重复");
    seen.add(text);
    const src = Array.isArray(t.sources) ? t.sources : [];
    if (!src.length) { report(section, label, "没有溯源编号"); return; }
    let ok = true;
    for (const id of src) {
      if (!ids.has(id)) { report(section, label, `溯源编号在${where}里找不到：${id}`); ok = false; }
    }
    if (ok) sourced++;
    const yq = src.filter(s => s.startsWith("YQ-") && !yqEvent.has(s));
    if (yq.length && yqCore && !yq.some(s => yqCore.has(s))) {
      report(section, label, `引了五运六气却没引到主干、岁运或为纲的那一头（${[...yqCore].join("、")}），只引了背景或修正：${yq.join("、")}`);
    }
  };
  for (const sec of sections) {
    const seen = new Set();
    if (DEPRECATED_SECTIONS.includes(sec.title)) report(sec.title, null, `${sec.title}段已废（2026-09-25）：删掉；身体习惯并进情绪过程的身体先动，全书的重复句装置归主题命题段`);
    if (Array.isArray(sec.stages)) {
      let lastAge = -1;
      const seenStages = new Set();
      for (const [j, st] of sec.stages.entries()) {
        stages++;
        const card = `${sec.title}@${st.stage || j + 1}`;
        if (!st.stage || !/^D-\d+-[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]$/.test(st.stage)) report(sec.title, card, `stage 应为 D-{步}-{干支} 编号，实为 ${st.stage}`);
        else if (!ids.has(st.stage)) report(sec.title, card, `stage 编号在${where}里找不到：${st.stage}`);
        if (seenStages.has(st.stage)) report(sec.title, card, "同一步大运出现两张卡");
        seenStages.add(st.stage);
        const ages = Array.isArray(st.ages) ? st.ages : [];
        if (ages.length !== 2 || !ages.every(Number.isInteger) || ages[0] >= ages[1]) report(sec.title, card, "ages 应为两个递增整数");
        else { if (ages[0] < lastAge) report(sec.title, card, "阶段卡未按岁数递增排列"); lastAge = ages[0]; }
        if (!(st.label || "").trim()) report(sec.title, card, "label 为空");
        const ts = Array.isArray(st.traits) ? st.traits : [];
        if (!ts.length) report(sec.title, card, "阶段卡没有特质");
        for (const [i, t] of ts.entries()) {
          if (!STAGE_ASPECTS.includes(t.aspect)) report(sec.title, `${card}#${i + 1}`, `aspect 应为 ${STAGE_ASPECTS.join("、")} 之一，实为 ${t.aspect}`);
          if (t.layer !== undefined) report(sec.title, `${card}#${i + 1}`, "阶段卡的特质不标 layer，卡本身就是阶段");
          checkTrait(sec.title, `${card}#${i + 1}`, t, seen);
        }
      }
      continue;
    }
    const layered = LAYERED.includes(sec.title), surface = sec.title === "性格表里", beatSec = sec.title === BEAT_SECTION;
    let base = 0, trend = 0;
    const beatsSeen = new Set();
    for (const [i, t] of (sec.traits || []).entries()) {
      const label = `${sec.title}#${i + 1}`;
      checkTrait(sec.title, label, t, seen);
      const src = Array.isArray(t.sources) ? t.sources : [];
      const layer = t.layer;
      if (beatSec) {
        if (!BEATS.includes(t.beat)) report(sec.title, label, `beat 应为 ${BEATS.join("、")} 之一，实为 ${t.beat}`);
        else beatsSeen.add(t.beat);
        if (t.beat === "碰线" && !src.some(s => /^(U-|LI-|E-|IN-)/.test(s))) report(sec.title, label, "碰线要落到他在对抗的那根线：引 U-（用忌）、LI-（谎言）、E-（矩阵边）或 IN-（亲密关系）");
        if (t.beat === "身体先动" && !src.some(s => /^(YQ-|IM-|DM$|Y-)/.test(s))) report(sec.title, label, "身体先动要引体感与材质：YQ-、IM-、Y- 或 DM");
      } else if (t.beat !== undefined) report(sec.title, label, `只有${BEAT_SECTION}段的特质带 beat`);
      if (NO_QUOTE_SECTIONS.includes(sec.title) && /[“”"]/.test(t.text || "")) report(sec.title, label, `${sec.title}不给台词：写句式、场合与倾向，引号里的话会被写手照抄进正文`);
      if (layer !== undefined && !LAYERS.includes(layer)) report(sec.title, label, `layer 应为 ${LAYERS.join(" 或 ")}，实为 ${layer}`);
      if (sec.title === "年表与两难" && !src.some(s => s.startsWith("L-") || s.startsWith("J-"))) report(sec.title, label, "年表与两难每条要落到具体年份、引 L- 编号（或日程的 J- 交汇）；按运分段的写进阶段卡");
      if (!layered && !surface) {
        if (layer !== undefined) report(sec.title, label, `${sec.title} 是定论段，不标 layer`);
        continue;
      }
      const isSurface = surface && (t.text || "").trim().startsWith("表现层");
      if (layered && layer === undefined) report(sec.title, label, "底色加走向的段每条要标 layer（底色或走向）");
      if (surface) {
        if (isSurface && layer !== "底色" && layer !== "走向") report(sec.title, label, "表现层要标 layer：命局的一条是底色，随大运变的一条是走向");
        if (!isSurface && layer !== undefined) report(sec.title, label, "性格表里只有表现层分底色与走向（text 以\"表现层\"起头）；身份层、内核层、矛盾面是定论，不标 layer");
      }
      if (layer === "底色") {
        base++;
        const d = src.filter(s => s.startsWith("D-"));
        if (d.length) report(sec.title, label, `底色是命局不带运，不引 D- 编号：${d.join("、")}`);
      } else if (layer === "走向") {
        trend++;
        if (!cardStages.size) report(sec.title, label, "没有阶段卡就没有走向可写，先写阶段状态段");
        else if (!src.some(s => s.startsWith("D-") && cardStages.has(stageOf(s)))) report(sec.title, label, "走向要引在场阶段卡的 D- 编号（把几张卡的偏移串成一条线）");
      }
    }
    if (beatSec && (sec.traits || []).length) {
      for (const b of ["碰线", "盖法"]) if (!beatsSeen.has(b)) report(sec.title, null, `情绪过程至少要有碰线与盖法各一条，缺${b}`);
    }
    if ((layered || surface) && (sec.traits || []).length) {  // 空段是待补充，不查层
      if (!base) report(sec.title, null, surface ? "缺表现层的底色条" : "缺底色条");
      if (cardStages.size && trend !== 1) report(sec.title, null, `有阶段卡时要恰有一条走向，实有 ${trend}`);
      trends += trend;
    }
  }
  if (!summaryOnly) for (const p of problems) console.log(JSON.stringify(p));
  console.log(JSON.stringify({ summary: true, file, sections: sections.length, traits, sourced, stages, trends, problems: problems.length, featureIds: ids.size,
    period: doc.setting && doc.setting.period || null }));
  process.exit(problems.length ? 1 : 0);
}

main();
