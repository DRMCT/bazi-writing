#!/usr/bin/env node
// 计划检查（DESIGN-写作层 第 10 节 check-plan）：查 书/ 里的主题、文风、卷稿、单元记录、细纲。零依赖，JSON 一行一条，最后一行汇总；有 error 退出码 1。
//
//   node scripts/check-plan.js 书/                        整个书目录：主题.md、文风.md、卷/、单元/、细纲/
//   node scripts/check-plan.js 书/细纲/第4章.md            单个文件，类型按所在目录名或标题判
//   --root 项目根       默认书目录的上一级。编号池从 root/命盘 下全部 JSON 收（features、idPool、线程、矩阵边、日程交汇），
//                       人名从 root/人物 与 root/命盘 的文件名收，生年从 root/命盘/{名}.年表.json 收
//   --theme 主题.md     默认 书/主题.md（装置表；细纲的物件编号查它，全书次数也按它的上限）
//   --threads 线程.json 默认 root/命盘/群像/线程.json；开着的线程（埋、压，旧文件的悬置）几章没动（threads[].chapters）超阈值报
//   编配的时间尺度从 root/命盘/群像/编配.json 的 timescale 读：长跨度的卷写大运，短跨度与回到关口年写段
//   --loose             外来大纲（别的套装的卷纲、细纲）：不认模板字段，只查引号、编号、借鉴字样、逐点字数
//   --summary           只打印汇总行
//
// 查（模板见 references/写作层/模板/）：必填字段在场；细纲无引号（error）、卷与单元里的引号 warn、文风的对白节无引号；
//     卷按编配的时间尺度分：长跨度写主角这一步的 D- 编号，短跨度与回到关口年写编配的段，大运可空（两样都空、长跨度没写大运、短跨度没写段报 warn）；
//     卷稿单元表与单元记录写来路（事件链源一栏的十种之一起头，没认出一种报 warn，空报 error）；两难只在事件链给了的单元写，写了要引编号（warn）；
//     卷稿的骨（没有、或落下风空着报 warn）；装置表重复句每人至多一句（谁一栏），类型取物件、重复句、意象、回声；
//     单元的三个走法在『谁做选择』上互不相同，作者选了才查章表、每章一句功能非空；细纲的主视角在在场里、决定小节非空、在场与知情表一人一行末行读者、
//     场表事项一栏（有这一栏而空着 warn；没有这一栏、转折写得很长 info）；章尾同一种类型连用（轮廓表 sameHookRun）warn；
//     场表里的人在在场里，一章没有一场走线报 warn（谁的五拍；别人的线只从外面写报 warn，视角切给他的不报）、演的场转折写成一对正负、对面要什么与怎么去要、读者担心（warn）、
//     破只认漏、说破、碎（warn），同一个人碎两回报 warn；赌注非空（没引 J-、TH-、DF-、PH-、Q-、L- 或期待编号报 warn）；
//     物件编号在装置表里且各细纲合计不超全书上限、写了碰的不超碰的上限、重复句写落在第几场（warn）、在场的人那一年已出生、不是正叙的书细纲要有位置；
//     进了正文的章没登追踪（在场与知情一行、登记里有这一章、细纲期待一节排了的编号在期待账里有这一章，warn）；
//     细纲与单元记录、在场各人戏用页十字以上连串重合（照抄阈值加二，warn，编号抹掉再比，主题白名单放行）；
//     编号（J-、TH-、Q-、L-、D-、E-、DF-、PH-…）都在编号池里；借鉴字样（对标、爽点、公式…）warn；细纲里逐点字数 warn；开着的线程（埋、压，旧文件的悬置）闲置章数超阈值 warn。
//     期待账（全报 warn，跑过一本真书再定哪几条升 error）：卷稿的期待线（编号、尺度、期限）、发动机与卷末兑现，单元选定后的兑现与回合，
//     细纲的期待一节（编号或 章内，开、压、推、兑现、落空、搁置；松紧、调剂）与钩子类型；按章号对账：第一次出现要是开、兑现以后不再出现、
//     回合与单元尺度的期待几章没人动（卷与全书尺度的不按章数查，隔太久再碰提醒带旧账，常驻的不查，搁置以后不查）、第一章没开、
//     开篇几章没兑现、开篇几章没有登记过的期待兑现、连着紧又没有调剂、连着几章平（没兑现没推没调剂也没有期限悬着）、连着几章不留钩、
//     回合末停在场中切或松收上、空章、卷稿期待线里没有的编号。
//     爽感节奏（主题卡有这一节才查，全报 warn）：细纲期待表的赢亏一栏（赢、亏、无）、单元章表的赢亏一栏；按章数主角的赢亏，进了正文、
//     期待账 tally 登了的照账，没登的照细纲：一章赢 0 info，连着两章赢 0、连着四章亏多于赢、开篇十章亏多于赢 warn（阈值轮廓表 rhythm）；
//     进了正文的章没登 tally warn。
// 每条一行：{"file","type","check","level","line","text","note"}；汇总 {"summary":true,...}。
"use strict";
const fs = require("fs");
const path = require("path");
const C = require("./book_common");

const STYLE_SECTIONS = ["师承", "叙述者", "叙述", "句与段", "口吻与用词", "对白", "附魅", "标点", "情绪与节奏", "不写", "阈值"];  // 2026-09-26 叙述层加师承、叙述者两节；附魅一节从频道卡挑几条抄进来
const READING_CARD_FIELDS = ["章", "字数", "覆盖时间", "演", "述", "述演比", "叙述者的判断与幽默", "情绪写法", "旧事怎么进", "环境与感官", "时间过渡", "开头", "结尾", "埋", "收", "对白", "腔调变化", "最值得学的一个讲法"];
const WALK_FIELDS = ["谁做选择", "事件顺序", "输了丢什么", "赢了欠什么", "结束时开着的线程"];
const WALKS = ["走法甲", "走法乙", "走法丙"];
const OBJECT_KINDS = ["物件", "重复句", "意象", "回声"];  // 回声：一句话、一个人、一个动作隔几十上百章再响；重复句含口头禅（戏用页附问末问是唯一出处），每人至多一句
// 单元的来路：事件链源一栏的十种（references/任务书/事件链.md）；旁人求上门也写作班底派活、单元客
const SOURCE_KINDS = ["热年出事", "默认下场到点", "过去追上来", "对手出招", "家人出招", "得知与认出", "主角布局", "局与日历", "旁人求上门", "关系自己往前走"];
const SOURCE_ALIAS = ["班底派活", "单元客", "得知", "认出", "钟", "默认下场"];
const BREAK_LEVELS = ["漏", "说破", "碎"];
const LONG_SPAN = "长跨度";
const PROFILES = C.profileNames();

function parseArgs(argv) {
  const out = { paths: [], root: null, theme: null, threads: null, loose: false, summary: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--root") out.root = argv[++i];
    else if (a === "--theme") out.theme = argv[++i];
    else if (a === "--threads") out.threads = argv[++i];
    else if (a === "--loose") out.loose = true;
    else if (a === "--summary") out.summary = true;
    else out.paths.push(a);
  }
  return out;
}

// 龙套表：直接扫表行，每张表的第一行 | 是表头；只认表头里有『称呼』的表（同一文件里另记的表，如只有命盘的人的称呼表，不算龙套）
function extraRows(text) {
  const rows = [];
  let header = null;
  for (const raw of C.stripComments(text).split(/\r?\n/)) {
    const line = raw.trimEnd();
    if (!/^\|/.test(line)) { if (line.trim()) header = null; continue; }
    const cells = line.split("|").slice(1, -1).map(c => c.trim());
    if (cells.every(c => /^:?-{2,}:?$/.test(c))) continue;
    if (!header) { header = cells; continue; }
    if (!header.includes("称呼")) continue;
    const row = {};
    header.forEach((h, k) => { row[h] = cells[k] === undefined ? "" : cells[k]; });
    rows.push(row);
  }
  return rows;
}

function typeOf(file, loose) {
  if (loose) return "外来";
  const base = path.basename(file), dir = path.basename(path.dirname(file));
  if (base === "主题.md") return "主题";
  if (base === "文风.md") return "文风";
  if (base === "龙套.md") return "龙套";
  if (base === "口味.md") return null;  // 作者口味卡：作者本，暂不查
  if (dir === "卷") return "卷";
  if (dir === "单元") return "单元";
  if (dir === "细纲") return "细纲";
  const segs = path.dirname(path.resolve(file)).split(/[\\/]/);
  const inBook = segs.lastIndexOf("书") >= 0 ? segs.slice(segs.lastIndexOf("书") + 1) : [dir];
  if (inBook.some(d => d === "会" || d === "正文" || d === "稿" || d === "追踪")) return null;  // 会议记录、正文、留底稿、追踪，连它们的子目录都不查
  const head = C.readText(file).split(/\r?\n/).find(l => /^#\s/.test(l)) || "";
  if (/^#\s+卷/.test(head)) return "卷";
  if (/^#\s+U-\d+/.test(head)) return "单元";
  if (/^#\s+第\d+章/.test(head)) return "细纲";
  if (/^#\s+读法卡/.test(head)) return "读法卡";
  if (/(^|[\\/])师承([\\/]|$)/.test(path.dirname(file))) return null;  // 书/师承/ 下只认读法卡；文本、片段、量尺表、汇总不查
  if (/^#\s+主题/.test(head)) return "主题";
  if (/^#\s+文风/.test(head)) return "文风";
  if (/^#\s+龙套/.test(head)) return "龙套";
  return "外来";
}

function collect(paths, loose) {
  const files = [];
  for (const p of paths) {
    if (!fs.existsSync(p)) { files.push({ file: p, type: "缺失" }); continue; }
    for (const f of C.listFiles(p, [".md"])) {
      const t = typeOf(f, loose);
      if (t) files.push({ file: f, type: t });
    }
  }
  return files;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.paths.length) {
    console.error("用法：node scripts/check-plan.js <书/ 或 文件>... [--root 项目根] [--theme 主题.md] [--threads 线程.json] [--loose] [--summary]");
    process.exit(2);
  }
  const files = collect(args.paths, args.loose);
  const first = files.find(f => f.type !== "缺失");
  const found = first ? C.findBook(first.file) : null;
  const book = found ? found.book : null;
  const root = args.root ? path.resolve(args.root) : (found ? found.root : null);
  const themePath = args.theme || (book && fs.existsSync(path.join(book, "主题.md")) ? path.join(book, "主题.md") : null);
  const threadsPath = args.threads || (root && fs.existsSync(path.join(root, "命盘", "群像", "线程.json")) ? path.join(root, "命盘", "群像", "线程.json") : null);
  const themeDoc = themePath ? C.parseMd(C.readText(themePath)) : null;
  const theme = themeDoc ? C.loadTheme(themeDoc) : { objects: [], whitelist: [], profile: null };
  // 乐子（2026-09-30）：主题卡许给读者的调子与笑从哪来；许了的书，细纲每章写这一章乐在哪
  const hasFun = doc => { const sec = C.section(doc, "乐子"); return !!sec && (!!C.bodyText(sec).replace(/<[^>]*>/g, "").trim() || Object.values(sec.fields || {}).some(v => !C.isBlank(v))); };
  const themeFun = themeDoc ? hasFun(themeDoc) : false;
  // 爽感节奏（2026-10-04）：读者站在主角这边追的书，主题卡写了这一节，细纲期待表逐行记这一下对她是赢是亏，按章数赢亏；来源写无、别的不写算没许
  const hasSway = doc => {
    const sec = C.section(doc, "爽感节奏");
    if (!sec) return false;
    const vals = [C.bodyText(sec).replace(/<[^>]*>/g, "").replace(/^\s*-\s*/gm, ""), ...Object.entries(sec.fields || {}).filter(([k, v]) => k !== "来源" && !C.isBlank(v)).map(([, v]) => v)];
    return vals.map(v => v.trim()).some(v => v && v !== "无");
  };
  const themeSway = themeDoc ? hasSway(themeDoc) : false;
  const stylePath = book && fs.existsSync(path.join(book, "文风.md")) ? path.join(book, "文风.md") : null;
  const profile = C.loadProfile({ themeDoc, styleDoc: stylePath ? C.parseMd(C.readText(stylePath)) : null });
  const pool = root ? C.loadIdPool(root) : { ids: new Set(), files: 0 };
  const names = root ? C.loadNames(root) : new Set();
  // 龙套（2026-09-25）：书/龙套.md 里的称呼算在场，但没有盘、没有五拍
  const extras = new Set();
  const extrasPath = book && fs.existsSync(path.join(book, "龙套.md")) ? path.join(book, "龙套.md") : null;
  if (extrasPath) for (const r of extraRows(C.readText(extrasPath))) if (!C.isBlank(r["称呼"])) extras.add(r["称呼"].trim());
  const births = root ? C.loadBirthYears(root, names) : new Map();
  // 编配的时间尺度（命盘/群像/编配.json 的 timescale）：长跨度一卷约一步大运，短跨度与回到关口年卷按编配的段分
  let timescale = null;
  const castingPath = root ? path.join(root, "命盘", "群像", "编配.json") : null;
  if (castingPath && fs.existsSync(castingPath)) { try { timescale = JSON.parse(C.readText(castingPath)).timescale || null; } catch (e) { timescale = null; } }
  const shatters = new Map();  // 人 → 细纲里写了碎的 [{file, line, chapter}]：碎一人全书一回
  const objectIds = new Map(theme.objects.map(o => [o.id, o]));
  const objectUse = new Map();  // 装置 → [{file, line}]
  const touchUse = new Map();  // 装置 → 细纲里写了碰的 [{file, line}]
  const wn = !!profile.expect;  // 轮廓表带期待账的写法（网文）才对账
  const expLevel = (profile.expect && profile.expect.level) || "warn";  // 期待账全报 warn，跑过一本真书再定哪几条升 error
  const expectEvents = new Map();  // 期待编号 → [{chapter, act, file, line}]
  const expectMeta = [];  // 写了期待一节的细纲：{chapter, file, line, rhythm, acts, relief, hook, fun}
  const registered = new Map();  // 卷稿期待线登记的编号 → {file, line, scale, deadline}
  const tallyByCh = new Map();  // 期待账 tally：章号 → {wins, losses}，进了正文照定稿登的主角赢亏
  const roundOf = new Map();  // 章号 → 回合（单元号加回合名）：单元章表的回合栏
  const chapterUse = new Map();  // 章号 → [{file, line}]：各单元记录排的章全书不许重号
  let chapterDupOff = false;  // 不是正叙的书，主题卡叙述结构的插入表没填完时，章号只是单元内序号，不查全书重号（2026-09-26）
  const nonLinear = !!(themeDoc && (() => { const nar = C.section(themeDoc, "叙述结构"); const s = nar ? (nar.fields["结构"] || "").trim() : ""; return s && !s.includes("正叙"); })());  // 讲述顺序脱开故事顺序：细纲要有位置
  const unitFiles = new Set(files.filter(f => f.type === "单元").map(f => path.basename(f.file, ".md")));
  const problems = [];
  let errors = 0, warns = 0, maxChapter = 0;
  const byType = {};
  const emit = (file, type, check, level, extra) => {
    if (level === "error") errors++; else if (level === "warn") warns++;
    problems.push({ file, type, check, level, ...extra });
  };

  // 每个文件都查的：引号、编号、借鉴字样、逐点字数
  function common(file, type, doc, text) {
    const lines = C.stripComments(text).split(/\r?\n/);
    const quoteLevel = type === "细纲" ? "error" : (type === "卷" || type === "单元" || type === "外来") ? "warn" : null;
    lines.forEach((line, i) => {
      const n = i + 1;
      if (quoteLevel && C.QUOTE_RE.test(line)) emit(file, type, "引号", quoteLevel, { line: n, text: line.trim().slice(0, 80), note: type === "细纲" ? "细纲不给台词，也不给强调引号；写意图与句式" : "计划里的引号会一路传到细纲与正文" });
      for (const w of profile.borrowWords) if (line.includes(w)) emit(file, type, "借鉴字样", "warn", { line: n, text: w, note: "写作层不从市场与对标出发（DESIGN-写作层 第 1 节）" });
      if ((type === "细纲" || type === "外来") && /\d+\s*字|字数/.test(line)) emit(file, type, "逐点字数", "warn", { line: n, text: line.trim().slice(0, 80), note: "字数只报不卡，细纲不给逐点字数" });
      for (const m of line.matchAll(C.ID_RE)) {
        const tok = m[0];
        if (/^U-\d+$/.test(tok)) continue;  // 单元编号是书里的，另查
        if (!pool.ids.size) continue;
        if (pool.ids.has(tok)) continue;
        let k = tok.length - 1, hit = null;
        for (; k >= 3; k--) if (pool.ids.has(tok.slice(0, k))) { hit = tok.slice(0, k); break; }
        if (hit) emit(file, type, "编号", "warn", { line: n, text: tok, note: `认作 ${hit}；编号后面紧贴着字，加个空格或标点` });
        else emit(file, type, "编号", "error", { line: n, text: tok, note: "编号池（命盘/ 下全部 JSON）里找不到" });
      }
    });
    if (!pool.ids.size && type !== "文风") emit(file, type, "编号", "info", { text: "没有找到 命盘/，编号没有核" });
  }

  function need(file, type, doc, key, level = "error") {
    if (C.isBlank(doc.fields[key])) { emit(file, type, "字段", level, { line: doc.fieldLines[key] || null, text: key, note: "缺或没填" }); return false; }
    return true;
  }

  // 来路：事件链源一栏的十种之一起头（局、钟上的日子、默认下场到点、单元客找上门都能做单元），空报 error，一种都没认出报 warn
  function checkOrigin(file, type, check, line, label, value) {
    if (C.isBlank(value)) { emit(file, type, check, "error", { line, text: label, note: `单元的来路没填：${SOURCE_KINDS.join("、")} 之一起头，几种用顿号分开，照事件链这一年的源` }); return; }
    const head = String(value).split(/[；;]/)[0];
    if (!SOURCE_KINDS.concat(SOURCE_ALIAS).some(k => head.includes(k))) emit(file, type, check, "warn", { line, text: `${label} ${String(value).trim().slice(0, 30)}`, note: `来路以十种源之一起头：${SOURCE_KINDS.join("、")}` });
  }

  // 两难可空：只在事件链的选择一栏把两难给了这一单元时写；写了要引编号（J-，没有交汇点引 Q- 或该年的 L-）
  function checkDilemma(file, type, check, line, value) {
    if (C.isBlank(value) || String(value).trim() === "无") return;
    if (!/\b(?:J|Q|L)-/.test(value)) emit(file, type, check, "warn", { line, text: `两难 ${String(value).trim().slice(0, 30)}`, note: "两难引事件链那一年的编号：有交汇点引 J-，没有引推演卡的 Q- 或该年的 L-；这一单元没有两难写无" });
  }

  function checkTheme(file, doc) {
    const t = "主题";
    if (!PROFILES.includes(doc.fields["写法轮廓"])) emit(file, t, "字段", "error", { line: doc.fieldLines["写法轮廓"] || null, text: "写法轮廓", note: `取轮廓表里的 ${PROFILES.join("、")}` });
    need(file, t, doc, "主角", "warn");
    need(file, t, doc, "目标读者", "warn");
    need(file, t, doc, "读者为什么爱上", "warn");  // 2026-10-03：主角与感情线上的人凭什么叫读者一上来就爱上（编配人表与档案看得见的样子照它）
    if (!C.bodyText(C.section(doc, "命题")).replace(/<[^>]*>/g, "").trim()) emit(file, t, "小节", "error", { text: "命题", note: "全书要回答的问题，一句问句" });
    if (!hasFun(doc)) emit(file, t, "小节", "warn", { text: "乐子", note: "这本书许给读者的调子，笑与乐从哪几处来（从设定、主角的性子、人物关系里长，不靠写的时候插笑话）；单元会与细纲拿它量这一段乐在哪" });
    if (!C.section(doc, "爽感节奏")) emit(file, t, "小节", "warn", { text: "爽感节奏", note: "读者站在主角这边追的书：她的赢与亏怎么交替、亏多久打回，照频道卡写几条；虐、悲剧向的书来源写无" });
    const nar = C.section(doc, "叙述结构");
    const NARRATIVES = ["正叙", "倒叙", "双线", "框架", "多视角"];
    if (!nar) emit(file, t, "小节", "warn", { text: "叙述结构", note: "讲述顺序那一层：正叙、倒叙、双线、框架、多视角选一种，写明现在时是哪条线；不写按正叙" });
    else if (C.isBlank(nar.fields["结构"]) || !NARRATIVES.some(k => (nar.fields["结构"] || "").includes(k))) emit(file, t, "字段", "warn", { line: nar.fieldLines["结构"] || nar.line, text: "结构", note: `取 ${NARRATIVES.join("、")} 之一` });
    else if (!(nar.fields["结构"] || "").includes("正叙")) {
      // 讲述顺序脱开故事顺序：插入表（现在时段 → 插在它后面的回忆单元）填完，各单元的章号才是全书格子号
      const rows = nar.rows.filter(r => !C.isBlank(r["现在时段"]));
      const ready = rows.length > 0 && rows.every(r => !C.isBlank(r["插在它后面的回忆单元"]) && !/待排/.test(r["插在它后面的回忆单元"]));
      if (!ready) { chapterDupOff = true; emit(file, t, "插入表", "warn", { line: nar.line, text: rows.length ? "待排" : "插入表", note: "插入表没填完：各单元章号按单元内序号，不查全书重号；填完统一改格子号" }); }
    }
    const dev = C.section(doc, "装置");
    if (!dev) emit(file, t, "小节", "warn", { text: "装置", note: "没有装置表就没有伏笔物件次数可查" });
    const repeatWho = new Map();  // 说它的人 → 重复句编号
    for (const o of theme.objects) {
      if (!/^F\d{3,}$/.test(o.id)) emit(file, t, "装置", "error", { line: o.line, text: o.id, note: "编号形如 F001" });
      if (!OBJECT_KINDS.includes(o.kind)) emit(file, t, "装置", "error", { line: o.line, text: o.id, note: `类型取 ${OBJECT_KINDS.join("、")} 之一` });
      if (!o.patterns.length) emit(file, t, "装置", "error", { line: o.line, text: o.id, note: "认法为空：检查器靠它在正文里数次数" });
      if (o.limit === null) emit(file, t, "装置", "error", { line: o.line, text: o.id, note: "全书上限要是整数" });
      if (o.touchLimitBad) emit(file, t, "装置", "error", { line: o.line, text: o.id, note: "碰的上限要是整数，或空着" });
      else if (o.touchLimit !== null && o.limit !== null && o.touchLimit > o.limit) emit(file, t, "装置", "warn", { line: o.line, text: o.id, note: "碰的上限比全书上限还大：碰也算在全书次数里" });
      if (o.kind === "重复句") {
        if (!o.who) emit(file, t, "装置", "warn", { line: o.line, text: o.id, note: "重复句在谁一栏写说它的人：口头禅每人至多一句，从他戏用页附问末问那一行来" });
        else if (repeatWho.has(o.who)) emit(file, t, "装置", "warn", { line: o.line, text: o.id, note: `${o.who} 已有重复句 ${repeatWho.get(o.who)}：每人至多一句` });
        else repeatWho.set(o.who, o.id);
      }
    }
  }

  function checkStyle(file, doc) {
    const t = "文风";
    for (const s of STYLE_SECTIONS) if (!C.section(doc, s)) emit(file, t, "小节", s === "附魅" ? "warn" : "error", { text: s, note: s === "附魅" ? "开书时从频道卡挑几条抄进来，没有写 无；旧卡没有，只报 warn" : "十一节都要在场，标题不改（2026-09-26 加师承、叙述者）" });
    const lineage = C.section(doc, "师承");
    if (lineage && C.isBlank(lineage.fields["书"])) emit(file, t, "字段", "warn", { line: lineage.line, text: "师承 书", note: "作者点的书，没有写 无" });
    const narr = C.section(doc, "叙述者");
    if (narr) for (const k of ["是谁、离多远", "述与演", "情绪怎么写", "开头与结尾"]) if (C.isBlank(narr.fields[k])) emit(file, t, "字段", "warn", { line: narr.fieldLines[k] || narr.line, text: `叙述者 ${k}`, note: "从师承提炼，作者改定；没定写 待定" });
    const d = C.section(doc, "对白");
    if (d) for (const l of d.text) if (C.QUOTE_RE.test(l.text)) emit(file, t, "引号", "error", { line: l.line, text: l.text.trim().slice(0, 80), note: "对白节只写句式与倾向，不给台词" });
    const th = C.section(doc, "阈值");
    if (th) for (const r of th.rows) if (!/^\d+(\.\d+)?$/.test((r["值"] || "").trim())) emit(file, t, "阈值", "error", { line: r.line, text: r["项"], note: "值要是数（体感密度可带小数）" });
  }

  function checkVolume(file, doc) {
    const t = "卷";
    for (const k of ["卷", "起止年", "主角", "命题的哪一半"]) need(file, t, doc, k);
    // 卷按时间尺度分：长跨度一卷约主角的一步大运（D- 编号），短跨度与回到关口年照编配的段；大运可空
    const run = (doc.fields["大运"] || "").trim(), part = (doc.fields["段"] || "").trim();
    const hasRun = !C.isBlank(run) && run !== "无", hasPart = !C.isBlank(part) && part !== "无";
    if (hasRun && !/^D-\d+-/.test(run)) emit(file, t, "字段", "warn", { line: doc.fieldLines["大运"], text: "大运", note: "写主角这一步运的 D- 编号；短跨度的书空着或写无" });
    if (!hasRun && !hasPart) emit(file, t, "字段", "warn", { line: doc.fieldLines["段"] || doc.fieldLines["大运"] || null, text: "段", note: "卷按编配的段分（长跨度的书另写主角这一步大运的 D- 编号）" });
    else if (timescale === LONG_SPAN && !hasRun) emit(file, t, "字段", "warn", { line: doc.fieldLines["大运"] || null, text: "大运", note: "编配的时间尺度是长跨度：一卷约主角的一步大运，写 D- 编号" });
    else if (timescale && timescale !== LONG_SPAN && !hasPart) emit(file, t, "字段", "warn", { line: doc.fieldLines["段"] || null, text: "段", note: `编配的时间尺度是${timescale}：卷照编配的段分，不照大运` });
    const units = C.section(doc, "单元");
    if (!units || !units.rows.length) emit(file, t, "小节", "error", { text: "单元", note: "卷稿至少排一个单元" });
    else for (const r of units.rows) {
      if (!/^U-\d+$/.test((r["单元"] || "").trim())) emit(file, t, "单元表", "error", { line: r.line, text: r["单元"], note: "单元编号形如 U-1" });
      const origin = r["来路"] !== undefined ? r["来路"] : r["谁的哪个两难"];  // 旧卷稿的『谁的哪个两难』一栏读作来路
      checkOrigin(file, t, "单元表", r.line, `${r["单元"]} 来路`, origin);
      checkDilemma(file, t, "单元表", r.line, r["两难"]);
      for (const k of ["赌注", "起止年", "在场"]) if (C.isBlank(r[k])) emit(file, t, "单元表", "error", { line: r.line, text: `${r["单元"]} ${k}`, note: "没填" });
    }
    // 骨：从事件链这一卷的骨来；每段主角落一回下风
    const bone = C.section(doc, "骨");
    if (!bone) emit(file, t, "小节", "warn", { text: "骨", note: "这一卷为哪一人一事、起承转合各落哪个单元、高潮、响、清算、落下风、破、卷末的问题，照事件链这一卷的骨" });
    else if (C.isBlank(bone.fields["落下风"])) emit(file, t, "骨", "warn", { line: bone.fieldLines["落下风"] || bone.line, text: "落下风", note: "这一卷的每一段主角在哪个单元落一回下风，出手的是谁、用他什么手段" });
    const drift = C.section(doc, "卷末偏移");
    if (!drift || !drift.text.some(l => /^-\s+\S/.test(l.text) && !C.isBlank(l.text.replace(/^-\s+/, "")))) emit(file, t, "小节", "warn", { text: "卷末偏移", note: "每个在场的人这一卷走完偏到哪，写回阶段卡的材料" });
    C.stripComments(C.readText(file)).split(/\r?\n/).forEach((l, i) => { if (/章数/.test(l)) emit(file, t, "卷不排章", "warn", { line: i + 1, text: l.trim().slice(0, 80), note: "卷稿只到单元；章在单元会上排" }); });
    // 期待线（编号 K001 全书连号）、发动机与卷末兑现
    const ledger = C.section(doc, "期待线");
    const lrows = ledger ? ledger.rows.filter(r => !C.isBlank(r["编号"])) : [];
    for (const r of lrows) {
      const id = (r["编号"] || "").trim();
      if (!C.EXPECT_RE.test(id)) { emit(file, t, "期待线", expLevel, { line: r.line, text: id, note: "编号形如 K001，全书连号；一章之内开了就收的小循环不登记，细纲里写 章内" }); continue; }
      const scale = (r["尺度"] || "").trim();
      const dl = (r["期限"] || "").trim();
      if (registered.has(id)) emit(file, t, "期待线", expLevel, { line: r.line, text: id, note: `与 ${path.basename(registered.get(id).file)} 重号` });
      else registered.set(id, { file, line: r.line, scale, deadline: C.isBlank(dl) || dl === "无" ? "" : dl });
      if (C.isBlank(r["期待"])) emit(file, t, "期待线", expLevel, { line: r.line, text: `${id} 期待`, note: "读者在等的那一件事，一句" });
      if (!profile.scales.includes(scale)) emit(file, t, "期待线", expLevel, { line: r.line, text: `${id} 尺度`, note: `取 ${profile.scales.join("、")} 之一：等多久（常驻是全书不兑现的知情差或处境，不查闲置）` });
    }
    if (wn && !lrows.length) emit(file, t, "期待线", expLevel, { text: "期待线", note: "这一卷开哪几个期待、多大尺度、在哪个单元兑现" });
    if (wn) { need(file, t, doc, "卷末兑现", expLevel); need(file, t, doc, "发动机", expLevel); }
  }

  function checkUnit(file, doc) {
    const t = "单元";
    for (const k of ["单元", "卷", "年", "在场"]) need(file, t, doc, k);
    if (!C.isBlank(doc.fields["单元"]) && !/^U-\d+$/.test(doc.fields["单元"])) emit(file, t, "字段", "error", { line: doc.fieldLines["单元"], text: "单元", note: "形如 U-1" });
    // 来路必填；两难只在事件链把两难给了这一单元时写。旧记录只有两难一行的，读作来路，只提醒补来路
    if (C.isBlank(doc.fields["来路"]) && !C.isBlank(doc.fields["两难"]) && doc.fields["两难"].trim() !== "无") emit(file, t, "字段", "warn", { line: doc.fieldLines["两难"], text: "来路", note: "写这一单元的来路（事件链源一栏的十种之一），两难只在事件链给了的单元写" });
    else checkOrigin(file, t, "字段", doc.fieldLines["来路"] || null, "来路", doc.fields["来路"]);
    checkDilemma(file, t, "字段", doc.fieldLines["两难"] || null, doc.fields["两难"]);
    const year = parseInt(doc.fields["年"], 10);
    const jm = /J-(\d+)-/.exec(doc.fields["两难"] || "");
    if (jm && !Number.isNaN(year) && parseInt(jm[1], 10) !== year) emit(file, t, "字段", "warn", { line: doc.fieldLines["两难"], text: doc.fields["两难"], note: `两难是 ${jm[1]} 年的，单元的年是 ${year}` });
    const present = new Set(C.splitList(doc.fields["在场"]));
    const choosers = [];
    for (const w of WALKS) {
      const s = C.section(doc, w);
      if (!s) { emit(file, t, "走法", "error", { text: w, note: "三个走法都要在场" }); continue; }
      for (const k of WALK_FIELDS) if (C.isBlank(s.fields[k])) emit(file, t, "走法", "error", { line: s.line, text: `${w} ${k}`, note: "没填" });
      // 谁做选择：名字在最前，句号或冒号后面可以接他在哪一步做了什么决定（任务书这么要求），只拿名字比
      const who = (s.fields["谁做选择"] || "").trim().split(/[。：:；;（(\n]/)[0].trim();
      if (!C.isBlank(who)) {
        choosers.push(who);
        if (present.size && !C.splitList(who).every(n => present.has(n))) emit(file, t, "走法", "warn", { line: s.fieldLines["谁做选择"], text: who, note: "做选择的人不在在场里" });
      }
    }
    if (choosers.length === 3 && new Set(choosers).size < 3) emit(file, t, "走法", "error", { text: choosers.join(" / "), note: "三个走法必须在谁做选择上不同，不许只是顺序不同" });
    const pick = C.section(doc, "作者选");
    const chosen = pick && !C.isBlank(pick.fields["选"]) && pick.fields["选"] !== "待定";
    if (!pick || C.isBlank(pick.fields["选"])) emit(file, t, "作者选", "error", { text: "选", note: "作者选一个、合两个，或重来；还没开会写 待定" });
    else if (!chosen) emit(file, t, "作者选", "warn", { line: pick.fieldLines["选"], text: "待定", note: "单元会还没选，选定后再排章" });
    else if (C.isBlank(pick.fields["为什么"])) emit(file, t, "作者选", "warn", { line: pick.line, text: "为什么", note: "记一句为什么，回纲会要看" });
    if (wn && chosen && C.isBlank(pick.fields["兑现"])) emit(file, t, "作者选", expLevel, { line: pick.line, text: "兑现", note: "这个单元结束时读者拿到什么，引期待编号；落空写换来了什么" });
    const ch = C.section(doc, "章");
    const rows = ch ? ch.rows.filter(r => !C.isBlank(r["章"])) : [];
    if (chosen) {
      if (!rows.length) emit(file, t, "章", "error", { text: "章", note: "选定后要有章数估计与每章一句功能" });
      for (const r of rows) {
        if (!/^\d+(-\d+)?$/.test(r["章"].trim())) emit(file, t, "章", "error", { line: r.line, text: r["章"], note: "章号是数字" });
        else {
          const key = r["章"].trim();
          if (!chapterUse.has(key)) chapterUse.set(key, []);
          chapterUse.get(key).push({ file, line: r.line });
          if (!C.isBlank(r["回合"]) && r["回合"].trim() !== "无") roundOf.set(parseInt(key, 10), `${(doc.fields["单元"] || "").trim()}·${r["回合"].trim()}`);
        }
        for (const k of ["功能：让谁面对什么", "读者离开时多知道什么"]) if (C.isBlank(r[k])) emit(file, t, "章", "error", { line: r.line, text: `第${r["章"]}章 ${k}`, note: "每章一句功能；答不出来的章不排" });
        if (C.isBlank(r["读者追什么"])) emit(file, t, "章", "warn", { line: r.line, text: `第${r["章"]}章 读者追什么`, note: "这一章读者追的是哪个问题；答不出来的章该并进别的章（2026-09-26）" });
        if (themeSway && ch.header.includes("赢亏") && C.isBlank(r["赢亏"])) emit(file, t, "章", "warn", { line: r.line, text: `第${r["章"]}章 赢亏`, note: "主角这一章赢在哪、亏在哪、亏打回在第几章" });
      }
      if (themeSway && rows.length && !ch.header.includes("赢亏")) emit(file, t, "章", "warn", { line: ch.line, text: "赢亏", note: "主题卡有爽感节奏一节：章表加赢亏一栏，每章写主角赢在哪、亏在哪、亏打回在第几章" });
    } else if (rows.length) emit(file, t, "章", "warn", { line: rows[0].line, text: `${rows.length} 行`, note: "作者还没选走法就排了章" });
  }

  function checkReadingCard(file, doc) {
    const t = "读法卡";
    for (const k of READING_CARD_FIELDS) need(file, t, doc, k);
    need(file, t, doc, "追什么", "warn");  // 2026-09-26 加：这一章让读者从哪儿起追哪个问题、结尾答了没；旧卡没有，只报 warn
  need(file, t, doc, "期待", "warn");  // 2026-09-29 加这三项：期待账、断章与反应层的读法；旧卡没有，只报 warn
  need(file, t, doc, "断章", "warn");
  need(file, t, doc, "兑现怎么写", "warn");
  need(file, t, doc, "场内手法", "warn");  // 2026-09-30 加：一拍怎么写（停几层、旁人心声、登场样子、夸张、接头等）；旧卡没有，只报 warn
    const long = [];
    for (const [k, v] of Object.entries(doc.fields)) {
      const sv = String(v);
      for (const m of sv.matchAll(/“([^“”\n]{16,})”/g)) long.push({ k, q: m[1] });
      sv.split('"').forEach((seg, i) => { if (i % 2 === 1 && seg.length >= 16 && !/\n/.test(seg)) long.push({ k, q: seg }); });  // 直引号按先后配对，第二个关第一个
    }
    for (const x of long) emit(file, t, "引文", "warn", { line: doc.fieldLines[x.k], text: x.q.slice(0, 30), note: "读法卡引原文只为定位，一处不超过十五个字；记讲法不记句子" });
  }

  function checkOutline(file, doc) {
    const t = "细纲";
    for (const k of ["章", "单元", "主视角", "年", "地点", "在场"]) need(file, t, doc, k);
    need(file, t, doc, "时候", "warn");
    if (nonLinear && C.isBlank(doc.fields["位置"])) emit(file, t, "字段", "warn", { line: doc.fieldLines["位置"] || null, text: "位置", note: "不是正叙的书：回忆或现在时、接在第几章之后；没定写 待排" });
    const chapter = parseInt(doc.fields["章"], 10);
    if (!Number.isNaN(chapter)) maxChapter = Math.max(maxChapter, chapter);
    const unit = (doc.fields["单元"] || "").trim();
    if (!C.isBlank(unit)) {
      if (!/^U-\d+$/.test(unit)) emit(file, t, "字段", "error", { line: doc.fieldLines["单元"], text: unit, note: "形如 U-1" });
      else if (book && !unitFiles.has(unit) && !fs.existsSync(path.join(book, "单元", `${unit}.md`))) emit(file, t, "字段", "warn", { line: doc.fieldLines["单元"], text: unit, note: "没有这个单元的记录：先开单元会" });
    }
    const year = parseInt(doc.fields["年"], 10);
    const present = C.splitList(doc.fields["在场"]);
    for (const p of present) {
      if (extras.has(p)) continue;
      if (names.size && !names.has(p)) emit(file, t, "在场", "warn", { line: doc.fieldLines["在场"], text: p, note: "人物/ 与 命盘/ 里没有这个人；龙套登进 书/龙套.md" });
      else if (!Number.isNaN(year) && births.has(p) && births.get(p) > year) emit(file, t, "在场", "error", { line: doc.fieldLines["在场"], text: p, note: `${year} 年还没出生（生于 ${births.get(p)}）` });
    }
    // 照抄上游原句（2026-10-01 样例书实测）：细纲的句子写手会搬进正文，从单元记录、戏用页原样来的也一路传下去；
    // check-prose 只比细纲与正文，这一道在细纲这一层拦。编号先抹掉（编号里的人名与字连起来会凑够阈值）。
    if (book && root) {
      const unitPath = /^U-\d+$/.test(unit) ? path.join(book, "单元", `${unit}.md`) : null;
      const ups = [];
      if (unitPath) ups.push(["单元", unitPath]);
      for (const p of present) if (!extras.has(p)) ups.push(["戏用页", path.join(root, "人物", `${p}.戏用页.md`)]);
      const blankIds = s => s.replace(C.ID_RE, m => " ".repeat(m.length)).replace(/[KF]\d{3,}/g, m => " ".repeat(m.length));
      const srcs = new Map(), idx = new Map();
      const upN = profile.copy.ngram + 2;  // 比正文照抄宽两字：细纲与上游共用一套人名、物名与事项短语，八字连串多是这些
      for (const [kind, p] of ups) {
        if (!fs.existsSync(p)) continue;
        const tag = `${kind}:${path.relative(root, p)}`;
        const norm = C.normalize(blankIds(C.stripComments(C.readText(p))), names);
        srcs.set(tag, norm);
        C.gramIndex(norm, upN, tag, idx);
      }
      if (idx.size) {
        // 放行：主题白名单；模板里的字段名与提示（单元表头、细纲字段几处字样相同）
        const tplDir = path.join(__dirname, "..", "references", "写作层", "模板");
        const tpl = ["单元.md", "细纲.md"].map(f => path.join(tplDir, f)).filter(f => fs.existsSync(f)).map(f => C.normalize(C.readText(f), names).str).join("");
        const allowed = theme.whitelist.map(w => C.normalize(w, names).str.replace(new RegExp(C.PARA, "g"), "")).filter(Boolean);
        const target = C.normalize(blankIds(C.stripComments(C.readText(file))), names);
        for (const run of C.findRuns(target, idx, upN, srcs)) {
          if (allowed.some(w => w.includes(run.text)) || tpl.includes(run.text)) continue;
          emit(file, t, "照抄上游", "warn", { line: target.pos[run.start] ? target.pos[run.start].line : null, text: C.excerpt(target, run.start, run.end),
            note: `与 ${run.tag.split(":").slice(1).join(":")} 连串重合 ${run.end - run.start} 字（阈值 ${upN}）：写成你自己的短语，写手会照细纲的字出句` });
        }
      }
    }
    const pov = (doc.fields["主视角"] || "").trim();
    if (pov && extras.has(pov)) emit(file, t, "字段", "error", { line: doc.fieldLines["主视角"], text: pov, note: "龙套不做主视角" });
    else if (pov && present.length && !present.includes(pov)) emit(file, t, "字段", "error", { line: doc.fieldLines["主视角"], text: pov, note: "主视角不在在场里" });
    for (const s of ["意图", "赌注", "决定", "弧", "在场与知情", "场", "禁放", "物件", "承接"]) if (!C.section(doc, s)) emit(file, t, "小节", "error", { text: s, note: s === "弧" ? "缺小节：章的骨头，要什么、起、承、转、合（2026-09-26）" : "缺小节" });
    const arc = C.section(doc, "弧");
    if (arc) for (const k of ["要什么", "起", "承", "转", "合"]) if (C.isBlank(arc.fields[k])) emit(file, t, "弧", "warn", { line: arc.fieldLines[k] || arc.line, text: k, note: "没填：读者这一章追的问题从哪起、怎么加压、在哪翻、留下什么" });
    const decision = C.bodyText(C.section(doc, "决定")).replace(/<[^>]*>/g, "").trim();
    if (C.section(doc, "决定") && !decision) emit(file, t, "小节", "error", { text: "决定", note: "主视角这一章落下的那个可以不这样做的决定；真没有写 无，再写这一章靠什么站住" });
    const know = C.section(doc, "在场与知情");
    if (know) {
      if (!know.rows.length) emit(file, t, "在场与知情", "error", { line: know.line, text: "在场与知情", note: "一人一行：这一章做什么、知道什么；末行是读者" });
      const listed = new Set();
      for (const r of know.rows) {
        const who = (r["人"] || "").trim();
        if (!who || who === "读者") continue;
        listed.add(who);
        if (present.length && !present.includes(who) && !extras.has(who)) emit(file, t, "在场与知情", "warn", { line: r.line, text: who, note: "不在本章在场里" });
      }
      for (const p of present) if (!listed.has(p)) emit(file, t, "在场与知情", "warn", { line: know.line, text: p, note: "在场却没写他这一章做什么、知道什么" });
      if (know.rows.length && !know.rows.some(r => (r["人"] || "").trim() === "读者")) emit(file, t, "在场与知情", "warn", { line: know.line, text: "读者", note: "末行写读者到章末知道什么、还不知道什么" });
    }
    if (wn && !C.section(doc, "钩子")) emit(file, t, "小节", "warn", { text: "钩子", note: "每章写停在哪里、停在哪一种上" });
    const hook = C.section(doc, "钩子");
    let hookKind = null;
    if (wn && hook) {
      const kind = (hook.fields["类型"] || "").trim();
      if (!profile.hookKinds.includes(kind)) emit(file, t, "钩子", expLevel, { line: hook.fieldLines["类型"] || hook.line, text: kind || "类型", note: `断章的类型取 ${profile.hookKinds.join("、")} 之一` });
      else hookKind = kind;
    }
    // 期待账：这一章对哪几个期待做什么；章内 是一章之内开了就收的小循环，不登记
    const exp = C.section(doc, "期待");
    if (!exp) { if (wn) emit(file, t, "期待", expLevel, { text: "期待", note: "这一章对哪几个期待做什么（开、压、推、兑现、落空、搁置），松紧与调剂" }); }
    else {
      const erows = exp.rows.filter(r => !C.isBlank(r["编号"]));
      const acts = [];
      for (const r of erows) {
        const id = (r["编号"] || "").trim(), act = (r["这一章"] || "").trim();
        const inner = id === "章内";
        if (!inner && !C.EXPECT_RE.test(id)) { emit(file, t, "期待", expLevel, { line: r.line, text: id, note: "编号形如 K001，引卷稿期待线；一章之内开了就收的写 章内" }); continue; }
        if (!profile.expectActs.includes(act)) { emit(file, t, "期待", expLevel, { line: r.line, text: `${id} ${act}`, note: `这一章取 ${profile.expectActs.join("、")} 之一` }); continue; }
        if (act === "搁置" && C.isBlank(r["怎么做"])) emit(file, t, "期待", expLevel, { line: r.line, text: `${id} 搁置`, note: "搁置写理由：人物为什么先不动它，读者要知道它只是睡着" });
        acts.push({ id, act });
        if (inner) continue;
        if (!expectEvents.has(id)) expectEvents.set(id, []);
        expectEvents.get(id).push({ chapter, act, file, line: r.line });
      }
      // 赢亏：这一下对主角是赢、亏还是无；主题卡有爽感节奏一节才查
      const swayCol = !!(exp.header && exp.header.includes("赢亏"));
      let wins = 0, losses = 0;
      for (const r of erows) {
        const v = (r["赢亏"] || "").trim();
        if (v === "赢") wins++;
        else if (v === "亏") losses++;
        else if (themeSway && swayCol && !C.isBlank(v) && v !== "无") emit(file, t, "期待", expLevel, { line: r.line, text: `${(r["编号"] || "").trim()} ${v}`, note: "赢亏取 赢、亏、无" });
      }
      if (themeSway && !swayCol) emit(file, t, "期待", expLevel, { line: exp.line, text: "赢亏", note: "主题卡有爽感节奏一节：期待表加赢亏一栏，每行写这一下对主角是赢、亏还是无；章内的小赢小亏也写一行" });
      const reliefRaw = (exp.fields["调剂"] || "").trim();
      const relief = C.splitList(reliefRaw);
      const badRelief = relief.filter(k => !profile.reliefKinds.includes(k));
      if (C.isBlank(reliefRaw)) emit(file, t, "期待", expLevel, { line: exp.line, text: "调剂", note: `这一章有什么让人往下读、又不是期待的：${profile.reliefKinds.join("、")}，顿号分开；没有写无` });
      else if (badRelief.length) emit(file, t, "期待", expLevel, { line: exp.fieldLines["调剂"], text: badRelief.join("、"), note: `调剂取 ${profile.reliefKinds.join("、")}，或无` });
      if (!erows.length && !relief.length) emit(file, t, "期待", expLevel, { line: exp.line, text: "空章", note: "这一章什么期待都没动，也没有调剂" });
      const funRaw = (exp.fields["乐子"] || "").trim();
      if (themeFun && C.isBlank(funRaw)) emit(file, t, "期待", expLevel, { line: exp.line, text: "乐子", note: "主题卡许了乐子：这一章乐在哪一场、从乐子一节哪一条来；真没有写无" });
      const rh = (exp.fields["松紧"] || "").trim();
      if (!["紧", "松"].includes(rh)) emit(file, t, "期待", expLevel, { line: exp.fieldLines["松紧"] || exp.line, text: "松紧", note: "取 紧 或 松：这一章在绷还是在松" });
      expectMeta.push({ chapter, file, line: exp.line, rhythm: ["紧", "松"].includes(rh) ? rh : null, acts, relief: relief.length > 0, hook: hookKind, fun: !themeFun || (!C.isBlank(funRaw) && funRaw !== "无"), sway: swayCol ? { wins, losses } : null });
    }
    const intent = C.bodyText(C.section(doc, "意图")).replace(/<[^>]*>/g, "").trim();
    if (C.section(doc, "意图") && !intent) emit(file, t, "小节", "error", { text: "意图", note: "读者离开时多知道什么、多担心什么" });
    // 赌注：短跨度的单元从局与日历来，常没有 J-；引两难、线程、默认下场、前史、事件卡、年表或期待编号都算
    const stake = C.bodyText(C.section(doc, "赌注")).replace(/<[^>]*>/g, "").trim();
    if (C.section(doc, "赌注") && !stake) emit(file, t, "小节", "error", { text: "赌注", note: "主视角这一章押着什么、两头各丢什么" });
    else if (C.section(doc, "赌注") && !/\b(?:J|TH|DF|PH|Q|L)-|\bK\d{3,}\b/.test(stake)) emit(file, t, "小节", "warn", { text: "赌注", note: "引编号：两难 J-、线程 TH-、默认下场 DF-、前史 PH-、事件卡 Q-、年表 L-，或期待编号" });
    const scenes = C.section(doc, "场");
    if (scenes && !scenes.rows.length) emit(file, t, "场", "error", { line: scenes.line, text: "场", note: "至少一场" });
    let beats = 0, played = 0;
    if (scenes) for (const r of scenes.rows) {
      const mode = (r["述/演"] || "").trim();
      if (mode && !/^(述|演)$/.test(mode)) emit(file, t, "场", "warn", { line: r.line, text: `场 ${r["场"]} 述/演`, note: "写 述 或 演" });
      if (mode === "演") played++;
      const turn = (r["转折"] || "").trim();
      if (C.isBlank(turn)) emit(file, t, "场", "warn", { line: r.line, text: `场 ${r["场"]} 转折`, note: "没填：这一场主视角里面什么变了，写手先写它" });
      else if (mode === "演" && !(/正/.test(turn) && /负/.test(turn))) emit(file, t, "场", "warn", { line: r.line, text: `场 ${r["场"]} 转折`, note: "演的场转折写成一对正负：进场是正、出场是负，或反过来" });
      if (r["事项"] !== undefined && C.isBlank(r["事项"])) emit(file, t, "场", "warn", { line: r.line, text: `场 ${r["场"]} 事项`, note: "没填：这一场发生什么，短语逐项，不成句" });
      else if (r["事项"] === undefined && turn.length > 120) emit(file, t, "场", "info", { line: r.line, text: `场 ${r["场"]} 转折`, note: "转折只写一对正负；这一场发生什么写进事项一栏（模板场表新加的一栏）" });
      if (mode === "演") {
        for (const k of ["对面要什么", "怎么去要"]) if (C.isBlank(r[k])) emit(file, t, "场", "warn", { line: r.line, text: `场 ${r["场"]} ${k}`, note: "演的场对面那个人这一场要什么、怎么去要（取他戏用页第一、三问与交手一行）；一个人的独角戏写无" });
        if (C.isBlank(r["读者担心"])) emit(file, t, "场", "warn", { line: r.line, text: `场 ${r["场"]} 读者担心`, note: "这一场读者替谁担心什么" });
      }
      const raw = (r["谁的五拍"] !== undefined ? r["谁的五拍"] : r["谁的四拍"] || "").trim();  // 旧细纲的『谁的四拍』一栏照认
      if (mode === "述" && C.splitList(raw).length) emit(file, t, "场", "warn", { line: r.line, text: `场 ${r["场"]}`, note: "述的场不走线，五拍在演的场里" });
      const who = C.splitList(raw);
      if (!who.length && raw !== "无") emit(file, t, "场", "error", { line: r.line, text: `场 ${r["场"]}`, note: "谁的五拍在走（戏用页第六问的哪一个人）；过场写 无" });
      if (who.length) beats++;
      const view = (r["视角"] || "").trim();
      for (const w of who) {
        if (extras.has(w)) emit(file, t, "场", "error", { line: r.line, text: w, note: "龙套没有五拍：一场戏走的是有戏用页的人的线" });
        else if (present.length && !present.includes(w)) emit(file, t, "场", "error", { line: r.line, text: w, note: "不在本章在场里" });
        else if (pov && w !== pov && !view.startsWith(w)) emit(file, t, "场", "warn", { line: r.line, text: w, note: "不是主视角：他的线只从外面写（身体先动、盖法、破），碰线底下的情绪不进；视角切给他的场不报" });
      }
      if (who.length && C.isBlank(r["碰线"])) emit(file, t, "场", "warn", { line: r.line, text: `场 ${r["场"]} 碰线`, note: "没填：他戏用页第六问的哪根线、被什么碰到" });
      const brk = (r["破"] || "").trim();
      if (!C.isBlank(brk) && brk !== "无") {
        const level = BREAK_LEVELS.slice().sort((a, b) => b.length - a.length).find(k => brk.startsWith(k));
        if (!level) emit(file, t, "场", "warn", { line: r.line, text: `场 ${r["场"]} 破 ${brk.slice(0, 20)}`, note: `破以 ${BREAK_LEVELS.join("、")} 之一起头，后面写谁来破（自己、别人当面、物证）；不破写无` });
        else if (level === "碎") for (const w of who) {
          if (!shatters.has(w)) shatters.set(w, []);
          shatters.get(w).push({ file, line: r.line, chapter });
        }
      }
      if (C.isBlank(r["时候与地点"])) emit(file, t, "场", "warn", { line: r.line, text: `场 ${r["场"]} 时候与地点`, note: "没填" });
    }
    if (scenes && scenes.rows.length && !beats) emit(file, t, "场", "warn", { line: scenes.line, text: "五拍", note: "这一章没有一场走线：调剂或松的一章可以，连着几章都不走线就是断了" });
    if (scenes && scenes.rows.length && scenes.rows.some(r => (r["述/演"] || "").trim()) && !played) emit(file, t, "场", "warn", { line: scenes.line, text: "演", note: "一章至少一场演出来" });
    const forbid = C.section(doc, "禁放");
    if (forbid) for (const k of ["禁", "放"]) if (C.isBlank(forbid.fields[k])) emit(file, t, "禁放", "warn", { line: forbid.line, text: k, note: "没填" });
    const objSec = C.section(doc, "物件");
    if (objSec) {
      const body = C.bodyText(objSec).replace(/<[^>]*>/g, "");
      const marks = [...body.matchAll(/\b(F\d{3,})\b\s*[（(]?\s*(碰|提到|觉出)?/g)];  // F001 碰、F002 提到
      if (!marks.length && !/无/.test(body)) emit(file, t, "物件", "warn", { line: objSec.line, text: "物件", note: "本章用到的装置编号，每个写碰还是提到；没有写无" });
      for (const mk of marks) {
        const id = mk[1];
        if (!objectIds.has(id)) { emit(file, t, "物件", "error", { line: objSec.line, text: id, note: themePath ? "主题的装置表里没有这个编号" : "没有主题.md，装置表无从查" }); continue; }
        if (objectIds.get(id).kind === "重复句" && !/^[^、，；\n]*第\s*\d+\s*场/.test(body.slice(mk.index + id.length))) emit(file, t, "物件", "warn", { line: objSec.line, text: id, note: "重复句写这一章让它落在第几场（F001 第2场）：写手照细纲写，不自行每章搬" });
        if (!objectUse.has(id)) objectUse.set(id, []);
        objectUse.get(id).push({ file, line: objSec.line, chapter });
        if (mk[2] === "碰") { if (!touchUse.has(id)) touchUse.set(id, []); touchUse.get(id).push({ file, line: objSec.line, chapter }); }
      }
    }
  }

  for (const f of files) {
    byType[f.type] = (byType[f.type] || 0) + 1;
    if (f.type === "缺失") { emit(f.file, f.type, "文件", "error", { text: "不存在" }); continue; }
    const text = C.readText(f.file);
    const doc = C.parseMd(text);
    common(f.file, f.type, doc, text);
    if (f.type === "主题") checkTheme(f.file, doc);
    else if (f.type === "文风") checkStyle(f.file, doc);
    else if (f.type === "卷") checkVolume(f.file, doc);
    else if (f.type === "单元") checkUnit(f.file, doc);
    else if (f.type === "细纲") checkOutline(f.file, doc);
    else if (f.type === "读法卡") checkReadingCard(f.file, doc);
    else if (f.type === "龙套") {
      for (const r of extraRows(text)) {
        for (const k of ["称呼", "功能"]) if (C.isBlank(r[k])) emit(f.file, "龙套", "龙套表", "error", { text: `${r["称呼"] || "?"} ${k}`, note: "没填" });
      }
    }
  }

  // 登追踪：进了正文的章要登进追踪表（在场与知情一行、登记里有这一章），下一章的细纲与写手照它接、照它避开用过的写法
  if (book && fs.existsSync(path.join(book, "正文"))) {
    const done = fs.readdirSync(path.join(book, "正文")).map(f => (f.match(/^第(\d+)章\.md$/) || [])[1]).filter(Boolean).map(Number).sort((a, b) => a - b);
    const readJson = f => { try { return JSON.parse(C.readText(f)); } catch (e) { return null; } };
    const knowPath = path.join(book, "追踪", "在场与知情.json"), regPath = path.join(book, "追踪", "登记.json");
    const know = fs.existsSync(knowPath) ? readJson(knowPath) : null;
    const reg = fs.existsSync(regPath) ? readJson(regPath) : null;
    const knownCh = new Set(((know && know.chapters) || []).map(c => Number(c.chapter)));
    const regCh = new Set([...((reg && reg.phrases) || []).filter(x => x && x.text).map(x => Number(x.chapter)),
      ...((reg && reg.objects) || []).flatMap(o => (o.uses || []).map(u => Number(u.chapter)))]);
    for (const k of done) {
      if (!knownCh.has(k)) emit(knowPath, "追踪", "登追踪", "warn", { text: `第${k}章`, note: "进了正文还没登在场与知情（含事实）：照定稿登，下一章细纲与写手照它接" });
      if (!regCh.has(k)) emit(regPath, "追踪", "登追踪", "warn", { text: `第${k}章`, note: "进了正文还没登登记（装置次数、用过的比喻、包袱、身体反应与盖法、章尾落法）：不登，下一章会照样再用" });
    }
    // 期待账：进了正文的章，细纲期待一节排了的编号要在期待账里有这一章的一笔（2026-10-03：样例书五章没登，三张表只查了两张）
    if (wn) {
      const expPath = path.join(book, "追踪", "期待.json");
      const led = fs.existsSync(expPath) ? readJson(expPath) : null;
      const touched = new Set(((led && led.expects) || []).flatMap(e => (e.touches || []).map(x => `${e.id}@${Number(x.chapter)}`)));
      for (const k of done) {
        const miss = [...expectEvents].filter(([id, evs]) => evs.some(ev => Number(ev.chapter) === k) && !touched.has(`${id}@${k}`)).map(([id]) => id);
        if (miss.length) emit(expPath, "追踪", "登追踪", "warn", { text: `第${k}章`, note: `进了正文还没登期待账：细纲期待一节排了 ${miss.join("、")}，照定稿登这一章开、压、推还是兑现；不登，往后几章对账与隔章没人动的提醒都失准` });
      }
      const filled = a => (Array.isArray(a) ? a : []).filter(x => !C.isBlank(x)).length;
      for (const x of (led && led.tally) || []) if (x && Number.isInteger(Number(x.chapter))) tallyByCh.set(Number(x.chapter), { wins: filled(x.wins), losses: filled(x.losses) });
      if (themeSway) for (const k of done) if (!tallyByCh.has(k)) emit(expPath, "追踪", "登追踪", "warn", { text: `第${k}章`, note: "进了正文还没登主角的赢亏（tally）：照定稿登这一章她赢在哪、亏在哪，只读前文的读者读成亏的登亏" });
    }
  }

  // 装置在各细纲里排的次数合计不超上限
  for (const [id, uses] of objectUse) {
    const o = objectIds.get(id);
    if (o && o.limit !== null && uses.length > o.limit) {
      const over = uses.slice(o.limit);
      for (const u of over) emit(u.file, "细纲", "物件超限", profile.objects.level, { line: u.line, text: id, note: `${o.name} 全书上限 ${o.limit}，各细纲已排 ${uses.length} 次（${uses.map(x => x.chapter ? `第${x.chapter}章` : path.basename(x.file)).join("、")}）` });
    }
  }

  // 碎：一人全书一回
  for (const [w, uses] of shatters) if (uses.length > 1) for (const u of uses.slice(1)) emit(u.file, "细纲", "破", "warn", { line: u.line, text: w, note: `${w} 已在${uses[0].chapter ? `第${uses[0].chapter}章` : path.basename(uses[0].file)}碎过：碎一人全书一回，这里是漏还是说破` });

  // 写了碰的不超碰的上限（提到只算全书上限）
  for (const [id, uses] of touchUse) {
    const o = objectIds.get(id);
    if (o && o.touchLimit !== null && uses.length > o.touchLimit) for (const u of uses.slice(o.touchLimit)) emit(u.file, "细纲", "碰超限", profile.objects.level, { line: u.line, text: id, note: `${o.name} 碰的上限 ${o.touchLimit}，各细纲已排碰 ${uses.length} 次（${uses.map(x => x.chapter ? `第${x.chapter}章` : path.basename(x.file)).join("、")}）` });
  }

  // 期待账：按章号对账。章号只是单元内序号时（插入表没填完）不对
  if (!chapterDupOff && expectMeta.length) {
    const E = profile.expect || {};
    const idle = Number.isInteger(E.idle) ? E.idle : null;
    const idleScales = E.idleScales || [];
    const byCh = new Map(expectMeta.filter(m => !Number.isNaN(m.chapter)).map(m => [m.chapter, m]));
    const chs = [...byCh.keys()].sort((a, b) => a - b);
    const lastCh = chs.length ? chs[chs.length - 1] : 0;
    const openSpans = [];  // 带期限的期待开着的章段：[开, 收；没收到全书末]
    for (const [id, evs] of expectEvents) {
      const list = evs.filter(e => !Number.isNaN(e.chapter)).sort((a, b) => a.chapter - b.chapter);
      if (!list.length) continue;
      const reg = registered.get(id);
      if (registered.size && !reg) for (const e of list) emit(e.file, "细纲", "期待账", expLevel, { line: e.line, text: id, note: "卷稿期待线里没有这个编号" });
      const scale = reg ? reg.scale : "";
      const checkIdle = idle !== null && (!reg || idleScales.includes(scale));  // 没登记的按单元算；卷、全书、常驻不按章数查
      if (list[0].act !== "开") emit(list[0].file, "细纲", "期待账", expLevel, { line: list[0].line, text: id, note: `第一次出现是${list[0].act}：先开，再压、推或兑现` });
      let closed = null;
      for (let k = 0; k < list.length; k++) {
        const e = list[k], next = list[k + 1];
        if (closed) { emit(e.file, "细纲", "期待账", expLevel, { line: e.line, text: id, note: `第${closed.chapter}章已经${closed.act}，这里又${e.act}：新的期待另起编号` }); continue; }
        if (e.act === "兑现" || e.act === "落空") { closed = e; continue; }
        if (!checkIdle && scale !== "常驻" && next && Number.isInteger(E.reopenGap) && next.chapter - e.chapter > E.reopenGap)
          emit(next.file, "细纲", "期待账", "info", { line: next.line, text: id, note: `隔了 ${next.chapter - e.chapter} 章再碰：重启的这一章带一句旧账，读者可能忘了` });
        if (e.act === "搁置" || !checkIdle) continue;  // 睡着的不查闲置
        const until = next ? next.chapter : lastCh;
        if (until - e.chapter > idle) emit(e.file, "细纲", "期待账", expLevel, { line: e.line, text: id, note: next ? `第${e.chapter}章到第${next.chapter}章隔了 ${next.chapter - e.chapter} 章没人动（${scale || "单元"}尺度，阈值 ${idle}）` : `开着，第${e.chapter}章以后 ${lastCh - e.chapter} 章没人动（${scale || "单元"}尺度，阈值 ${idle}）` });
      }
      if (reg && reg.deadline && list[0].act === "开") openSpans.push([list[0].chapter, closed ? closed.chapter : Infinity]);
    }
    const acted = (m, set) => m.acts.some(a => set.includes(a.act));
    if (wn && byCh.has(1) && !byCh.get(1).acts.some(a => a.act === "开" && a.id !== "章内")) emit(byCh.get(1).file, "细纲", "开篇", expLevel, { line: byCh.get(1).line, text: "第1章", note: "第一章一个登记过的期待都没开：立住谁要什么、谁挡着" });
    const by = E.openingPayoffBy, real = E.openingRealPayoffBy;
    const early = n => chs.filter(c => c <= n).map(c => byCh.get(c));
    if (wn && Number.isInteger(by) && lastCh >= by && !early(by).some(m => acted(m, ["兑现"]))) {
      const at = byCh.get(by) || byCh.get(chs[0]);
      emit(at.file, "细纲", "开篇", expLevel, { line: at.line, text: `前${by}章`, note: `开篇${by}章里没有一回兑现（章内的也算）：读者手里先拿到一样东西` });
    }
    if (wn && Number.isInteger(real) && lastCh >= real && !early(real).some(m => m.acts.some(a => a.act === "兑现" && a.id !== "章内"))) {
      const at = byCh.get(real) || byCh.get(chs[chs.length - 1]);
      emit(at.file, "细纲", "开篇", expLevel, { line: at.line, text: `前${real}章`, note: `开篇${real}章（约一万字）里没有一回登记过的期待兑现：局面要翻过来一回` });
    }
    const rhy = profile.rhythm || {};
    const rlevel = rhy.level || "warn";
    let tense = 0, flat = 0, hookless = 0, funless = 0, sameHook = 0, lastHook = null;
    for (const c of chs) {
      const m = byCh.get(c);
      tense = m.rhythm === "紧" && !m.relief ? tense + 1 : 0;
      if (Number.isInteger(rhy.tenseRun) && tense === rhy.tenseRun + 1) emit(m.file, "细纲", "松紧", rlevel, { line: m.line, text: `第${c}章`, note: `连着紧 ${tense} 章又没有调剂（阈值 ${rhy.tenseRun}）：绷太久读者会累` });
      const hanging = openSpans.some(([a, b]) => a <= c && c < b);
      flat = !acted(m, ["兑现", "推", "落空"]) && !m.relief && !hanging ? flat + 1 : 0;
      if (Number.isInteger(rhy.flatRun) && flat === rhy.flatRun + 1) emit(m.file, "细纲", "松紧", rlevel, { line: m.line, text: `第${c}章`, note: `连着 ${flat} 章没兑现、没推、没调剂，也没有带期限的期待悬着（阈值 ${rhy.flatRun}）：读者会走` });
      funless = m.fun ? 0 : funless + 1;
      if (Number.isInteger(rhy.funlessRun) && funless === rhy.funlessRun + 1) emit(m.file, "细纲", "乐子", rlevel, { line: m.line, text: `第${c}章`, note: `连着 ${funless} 章没有乐子（阈值 ${rhy.funlessRun}）：主题卡许给读者的调子断了` });
      // 章尾同一种连着用：读者读出套路（落法也要换，不只换类型）
      sameHook = m.hook && m.hook === lastHook ? sameHook + 1 : (m.hook ? 1 : 0);
      lastHook = m.hook || null;
      if (Number.isInteger(rhy.sameHookRun) && sameHook === rhy.sameHookRun + 1) emit(m.file, "细纲", "钩子", rlevel, { line: m.line, text: `第${c}章`, note: `连着 ${sameHook} 章章尾都是${m.hook}（阈值 ${rhy.sameHookRun}）：换一种，停的东西也换（一句话、一个动作、一句露底、旁人的反应）` });
      hookless = m.hook && profile.hooklessKinds.includes(m.hook) ? hookless + 1 : 0;
      if (Number.isInteger(rhy.hooklessRun) && hookless === rhy.hooklessRun + 1) emit(m.file, "细纲", "钩子", rlevel, { line: m.line, text: `第${c}章`, note: `连着 ${hookless} 章章尾不留钩（${profile.hooklessKinds.join("、")}，阈值 ${rhy.hooklessRun}）` });
    }
    // 爽感节奏：按章数主角的赢亏；进了正文、期待账 tally 登了的照账，没登的照细纲期待表；两样都没有的章断开连数
    if (themeSway) {
      let winless = 0, lossy = 0, owin = 0, oloss = 0, oseen = 0;
      const openN = rhy.openingWinBy;
      for (const c of chs) {
        const m = byCh.get(c), led = tallyByCh.get(c), sw = led || m.sway;
        if (!sw) { winless = 0; lossy = 0; continue; }
        const src = led ? "（照期待账 tally）" : "";
        if (!sw.wins) emit(m.file, "细纲", "赢亏", "info", { line: m.line, text: `第${c}章`, note: `这一章她没有一处赢${src}：在布局的章，读者也得看得见她手里的算盘，网下一章收` });
        winless = sw.wins ? 0 : winless + 1;
        if (Number.isInteger(rhy.winlessRun) && winless === rhy.winlessRun + 1) emit(m.file, "细纲", "赢亏", rlevel, { line: m.line, text: `第${c}章`, note: `连着 ${winless} 章她没有一处赢${src}（阈值 ${rhy.winlessRun}）：读者攒着憋屈会走` });
        lossy = sw.losses > sw.wins ? lossy + 1 : 0;
        if (Number.isInteger(rhy.lossRun) && lossy === rhy.lossRun + 1) emit(m.file, "细纲", "赢亏", rlevel, { line: m.line, text: `第${c}章`, note: `连着 ${lossy} 章亏多于赢${src}（阈值 ${rhy.lossRun}）：这一章要翻过来` });
        if (Number.isInteger(openN) && c <= openN) { owin += sw.wins; oloss += sw.losses; oseen = c; }
      }
      if (Number.isInteger(openN) && lastCh >= openN && oloss > owin) {
        const at = byCh.get(oseen) || byCh.get(chs[0]);
        emit(at.file, "细纲", "赢亏", rlevel, { line: at.line, text: `前${openN}章`, note: `开篇${openN}章她赢 ${owin} 处、亏 ${oloss} 处：开篇赢不少于亏，读者才站到她这边` });
      }
    }
    // 回合末：回合是断章的单位，回合里可以松收、场中切，回合末要兑现或设钩
    const roundLast = new Map();
    for (const [c, r] of roundOf) if (!roundLast.has(r) || c > roundLast.get(r)) roundLast.set(r, c);
    for (const [r, c] of roundLast) {
      const m = byCh.get(c);
      if (m && m.hook && profile.roundEndBad.includes(m.hook)) emit(m.file, "细纲", "钩子", expLevel, { line: m.line, text: `第${c}章`, note: `回合 ${r} 的末章停在${m.hook}上：回合末要兑现或设钩` });
    }
  }

  // 章号全书查重（讲述顺序脱开故事顺序后，各单元的章合起来是全书的格子，不许重）
  if (!chapterDupOff) for (const [key, uses] of chapterUse) if (uses.length > 1) for (const u of uses.slice(1)) emit(u.file, "单元", "章", "error", { line: u.line, text: `第${key}章`, note: `与 ${path.basename(uses[0].file)} 第 ${uses[0].line} 行重号；一章只能属于一个单元` });

  // 开着的线程几章没动
  let threadsChecked = 0;
  if (threadsPath && fs.existsSync(threadsPath) && maxChapter) {
    try {
      const th = JSON.parse(C.readText(threadsPath));
      for (const tr of th.threads || []) {
        if (!["悬置", "埋", "压"].includes(tr.status)) continue;  // v2 四态里埋与压开着；旧文件的悬置读作压
        threadsChecked++;
        const chs = Array.isArray(tr.chapters) ? tr.chapters.filter(Number.isInteger) : [];
        if (!chs.length) { emit(threadsPath, "线程", "线程账", "info", { text: tr.id, note: `${tr.status}，还没有章动过它（chapters 为空）` }); continue; }
        const idle = maxChapter - Math.max(...chs);
        if (idle > profile.threadIdle.chapters) emit(threadsPath, "线程", "线程账", profile.threadIdle.level, { text: tr.id, note: `${tr.status}，${idle} 章没动（阈值 ${profile.threadIdle.chapters}），最近第${Math.max(...chs)}章` });
      }
    } catch (e) { emit(threadsPath, "线程", "线程账", "warn", { text: "线程文件读不了", note: String(e.message) }); }
  }

  if (!args.summary) for (const p of problems) console.log(JSON.stringify(p));
  console.log(JSON.stringify({ summary: true, files: files.length, byType, profile: profile.name, idPool: pool.ids.size, names: names.size, extras: extras.size, objects: theme.objects.length,
    maxChapter, threadsChecked, expects: expectEvents.size, expectsRegistered: registered.size, rounds: new Set(roundOf.values()).size, errors, warns, loose: args.loose }));
  process.exit(errors ? 1 : 0);
}

main();
