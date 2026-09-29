#!/usr/bin/env node
// 正文检查（DESIGN-写作层 第 8 节 check-prose）：一章一跑，也可一次给几章。零依赖，JSON 一行一条，最后一行汇总；有 error 退出码 1。
//
//   node scripts/check-prose.js 书/正文/第4章.md                  按 书/ 推断：细纲/第4章.md、文风.md、主题.md、../人物/*.读者本.md、前几章
//   node scripts/check-prose.js 书/正文/第1章.md 书/正文/第2章.md   几章一起，前面的章自动当后面的章的前文
//   node scripts/check-prose.js 正文.md --plan 细纲.md --style 文风.md --theme 主题.md --cards 人物/ --source 设定/角色/ --prev 上一章.md
//                                                                 目录不是 书/ 形状时（别的套装的项目）逐项指定
//   --profile 名字                写法轮廓，默认读主题的『写法轮廓』行，再默认轮廓表第一张（webnovel）
//   --names 甲,乙                 另加人名（连串比对时人名折成一个字，人名之外要够长才报）
//   --banned 词表.txt             去味词表，一行一个词，命中报 warn
//   --window N                    跨章重复回看几章，默认按轮廓表
//   --summary                     只打印汇总行
//
// 查：引号照抄（正文与细纲、读者本、文风卡、额外来源做八字以上连串比对，主题白名单放行，error）；
//     跨章重复（与前几章比六字以上连串，人名不计入长度，warn）；句尾否定（句尾落在没、不上的句子数与比例，超文风阈值报）；
//     双否定（没…也没、不…也不）；感叹号、省略号、破折号只数叙述、按每千字算（引号与【】里的对白、心声、屏上文字不数，单独成行的分隔符与引出对白的破折号不数）；
//     伏笔物件次数（按主题装置表的认法数，本章与前文合计超上限报）；字数出了轮廓表的章长范围报 info，句长、段长只报；套话模式（对照式、像是、仿佛）与体感密度（每千字身体部位词）按 references/写作层/套话.json 与文风阈值报，定格式收尾 info；
//     书/师承/ 下的文本也是照抄来源。术语归 check-terms，另跑。
// 每条一行：{"file","check","level","line","col","text","source","sourceLine","note"}；汇总 {"summary":true,...}。
"use strict";
const fs = require("fs");
const path = require("path");
const C = require("./book_common");

const NEG_SKIP = /不过|不由|不禁|不妨|不如|不料|不知不觉|不动声色|不声不响|不紧不慢|不三不四|不闻不问/g;
const PUNCT_ONLY = /^[。！？!?，、；：,;:…—\-（）()《》\s]*$/;

function parseArgs(argv) {
  const out = { files: [], book: null, plan: [], style: null, theme: null, cards: [], source: [], prev: [], profile: null, names: [], banned: null, window: null, summary: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--book") out.book = argv[++i];
    else if (a === "--plan") out.plan.push(argv[++i]);
    else if (a === "--style") out.style = argv[++i];
    else if (a === "--theme") out.theme = argv[++i];
    else if (a === "--cards") out.cards.push(argv[++i]);
    else if (a === "--source") out.source.push(argv[++i]);
    else if (a === "--prev") out.prev.push(argv[++i]);
    else if (a === "--profile") out.profile = argv[++i];
    else if (a === "--names") out.names.push(...argv[++i].split(/[,，、]/));
    else if (a === "--banned") out.banned = argv[++i];
    else if (a === "--window") out.window = parseInt(argv[++i], 10);
    else if (a === "--summary") out.summary = true;
    else out.files.push(a);
  }
  return out;
}

function mdFiles(p) {
  if (!p || !fs.existsSync(p)) return [];
  return C.listFiles(p, [".md", ".txt"]);
}

function readerCards(root) {
  const d = path.join(root, "人物");
  if (!fs.existsSync(d)) return [];
  const all = fs.readdirSync(d).filter(n => n.endsWith(".读者本.md")).map(n => path.join(d, n));
  return all.length ? all : fs.readdirSync(d).filter(n => n.endsWith(".md")).map(n => path.join(d, n));
}

function blankTitles(lines) {
  return lines.map(l => (/^#/.test(l) ? "" : l));
}

function sentencesOf(lines) {
  const out = [];
  lines.forEach((line, li) => {
    if (/^#/.test(line) || !line.trim()) return;
    for (const p of line.split(/(?<=[。！？!?])/)) {
      const core = p.replace(/[“”"「」『』\s]/g, "");
      if (PUNCT_ONLY.test(core)) continue;
      out.push({ line: li + 1, text: p.trim(), core });
    }
  });
  return out;
}

function lastClause(core) {
  return core.replace(/[。！？!?]+$/, "").split(/[，、；：,;:]/).pop() || "";
}

function countAll(text, re) {
  const m = text.match(re);
  return m ? m.length : 0;
}

function objectHits(text, patterns) {
  const hits = [];
  const lines = text.split(/\r?\n/);
  lines.forEach((line, li) => {
    for (const p of patterns) {
      let from = 0;
      for (;;) {
        const k = line.indexOf(p, from);
        if (k < 0) break;
        hits.push({ line: li + 1, col: k + 1, pattern: p, context: line.slice(Math.max(0, k - 12), k + p.length + 12) });
        from = k + p.length;
      }
    }
  });
  return hits;
}

function resolve(file, args, order) {
  const ctx = { file };
  const found = args.book ? { book: path.resolve(args.book), root: path.dirname(path.resolve(args.book)) } : C.findBook(file);
  ctx.book = found ? found.book : null;
  ctx.root = found ? found.root : null;
  const no = C.chapterNo(file);
  ctx.chapter = no;
  const inBook = p => (ctx.book ? path.join(ctx.book, p) : null);
  const exists = p => p && fs.existsSync(p) ? p : null;
  // 细纲：指定了几份时按章号配对（第001章 与 第1章 同号），配不上就全用；
  // 书里先找同名（章号待排时文件叫 U-1-第1章.md，正文、稿与细纲同名，稿的 .vK 去掉），再找 第N章.md
  const paired = args.plan.filter(p => no !== null && C.chapterNo(p) === no);
  const unitPrefix = (/^(U-\d+-)/.exec(path.basename(file)) || [])[1] || "";
  ctx.plans = args.plan.length ? (paired.length ? paired : args.plan)
    : (exists(inBook(path.join("细纲", path.basename(file).replace(/\.v\d+(?=\.md$)/, "")))) ? [inBook(path.join("细纲", path.basename(file).replace(/\.v\d+(?=\.md$)/, "")))]
      : (no !== null && exists(inBook(path.join("细纲", `第${no}章.md`))) ? [inBook(path.join("细纲", `第${no}章.md`))] : []));
  ctx.style = args.style || exists(inBook("文风.md"));
  ctx.theme = args.theme || exists(inBook("主题.md"));
  ctx.cards = args.cards.length ? args.cards.flatMap(mdFiles) : (ctx.root ? readerCards(ctx.root) : []);
  ctx.sources = args.source.flatMap(mdFiles);
  // 前文：指定的；或书里章号更小的正文；或命令行里排在前面的章
  let allPrev = [];
  if (args.prev.length) allPrev = args.prev;
  else if (ctx.book && no !== null && fs.existsSync(inBook("正文"))) {
    allPrev = fs.readdirSync(inBook("正文")).map(n => path.join(inBook("正文"), n))
      .filter(p => p.endsWith(".md") && C.chapterNo(p) !== null && C.chapterNo(p) < no && path.basename(p).startsWith(unitPrefix)).sort((a, b) => C.chapterNo(a) - C.chapterNo(b));
  } else allPrev = order.slice(0, order.indexOf(file));
  ctx.allPrev = allPrev;
  ctx.names = new Set([...(ctx.root ? C.loadNames(ctx.root) : []), ...args.names.filter(Boolean)]);
  const extrasFile = exists(inBook("龙套.md"));  // 龙套称呼也折成一个字，连串比对不吃它们的长度
  if (extrasFile) for (const line of C.stripComments(C.readText(extrasFile)).split(/\r?\n/)) {
    const m = /^\|\s*([^|<>]{1,12}?)\s*\|/.exec(line);
    if (m && !/^称呼$|^-+$/.test(m[1].trim())) ctx.names.add(m[1].trim());
  }
  ctx.themeDoc = ctx.theme ? C.parseMd(C.readText(ctx.theme)) : null;
  ctx.styleDoc = ctx.style ? C.parseMd(C.readText(ctx.style)) : null;
  ctx.profile = C.loadProfile({ themeDoc: ctx.themeDoc, styleDoc: ctx.styleDoc, name: args.profile });
  ctx.themeInfo = ctx.themeDoc ? C.loadTheme(ctx.themeDoc) : { objects: [], whitelist: [] };
  const win = args.window || ctx.profile.repeat.window;
  ctx.prev = allPrev.slice(-win);
  return ctx;
}

function checkOne(ctx, args, emit) {
  const file = ctx.file;
  const raw = C.readText(file);
  const lines = raw.split(/\r?\n/);
  const body = blankTitles(lines).join("\n");  // 标题行抹空但留着，行号不变
  const names = [...ctx.names];
  const prof = ctx.profile;
  let errors = 0, warns = 0;
  const say = (check, level, extra) => {
    if (level === "error") errors++; else if (level === "warn") warns++;
    emit({ file, check, level, ...extra });
  };
  const rel = p => { const r = path.relative(process.cwd(), p); return r && !r.startsWith("..") ? r : p; };  // 在工作目录下才写相对路径
  const target = C.normalize(body, names);
  const ticsPath = path.join(__dirname, "..", "references", "写作层", "套话.json");
  const T = fs.existsSync(ticsPath) ? JSON.parse(C.readText(ticsPath)) : {};
  const lineOf = i => target.pos[i] ? target.pos[i].line : null;
  const colOf = i => target.pos[i] ? target.pos[i].col : null;

  // 1. 引号照抄
  const copySources = new Map();
  const copyIndex = new Map();
  const addSource = (p, kind) => {
    if (!p || !fs.existsSync(p)) return;
    const tag = `${kind}:${rel(p)}`;
    const norm = C.normalize(C.stripComments(C.readText(p)), names);
    copySources.set(tag, norm);
    C.gramIndex(norm, prof.copy.ngram, tag, copyIndex);
  };
  for (const p of ctx.plans) addSource(p, "细纲");
  for (const p of ctx.cards) addSource(p, "档案");
  if (ctx.style) addSource(ctx.style, "文风");
  for (const p of ctx.sources) addSource(p, "来源");
  // 师承（2026-09-26 叙述层）：书/师承/ 下的文本、片段、读法卡全是照抄来源；学讲法不借句子
  if (ctx.book && fs.existsSync(path.join(ctx.book, "师承"))) for (const p of C.listFiles(path.join(ctx.book, "师承"), [".txt", ".md"])) addSource(p, "师承");
  const whitelist = ctx.themeInfo.whitelist.map(w => C.normalize(w, names).str);
  let copies = 0;
  if (copyIndex.size) {
    for (const run of C.findRuns(target, copyIndex, prof.copy.ngram, copySources)) {
      if (whitelist.some(w => w.includes(run.text))) continue;
      copies++;
      const src = copySources.get(run.tag);
      say("照抄", prof.copy.level, { line: lineOf(run.start), col: colOf(run.start), text: C.excerpt(target, run.start, run.end),
        source: run.tag.split(":").slice(1).join(":"), sourceLine: src.pos[run.srcIdx] ? src.pos[run.srcIdx].line : null,
        note: `与来源连串重合 ${run.end - run.start} 字（阈值 ${prof.copy.ngram}）` });
    }
  }

  // 2. 跨章重复
  let repeats = 0;
  for (const p of ctx.prev) {
    if (!fs.existsSync(p)) continue;
    const tag = `前文:${rel(p)}`;
    const norm = C.normalize(blankTitles(C.readText(p).split(/\r?\n/)).join("\n"), names);
    const idx = C.gramIndex(norm, prof.repeat.ngram, tag);
    const srcs = new Map([[tag, norm]]);
    for (const run of C.findRuns(target, idx, prof.repeat.ngram, srcs)) {
      if (run.text.replace(/〇/g, "").length < prof.repeat.ngram) continue;  // 人名不算长度
      if (whitelist.some(w => w.includes(run.text))) continue;  // 律文一类的原话可以再出现
      repeats++;
      say("跨章重复", prof.repeat.level, { line: lineOf(run.start), col: colOf(run.start), text: C.excerpt(target, run.start, run.end),
        source: rel(p), sourceLine: norm.pos[run.srcIdx] ? norm.pos[run.srcIdx].line : null,
        note: `与前文连串重合 ${run.end - run.start} 字（阈值 ${prof.repeat.ngram}）；同一比喻、同一句反应层的写法全书一次` });
    }
  }

  // 3. 句尾否定与双否定
  const sents = sentencesOf(lines);
  const negHits = [], dblHits = [];
  for (const s of sents) {
    if (C.tailNegation(s.core, T.negationCompounds)) negHits.push(s);  // 严口径：叙述句末短句以否定动词收尾
    if (/(没|不)[^。！？；]{0,12}也(没|不)/.test(s.core)) dblHits.push(s);
  }
  const negT = prof.thresholds.negationTail, dblT = prof.thresholds.doubleNegation;
  if (!args.summary) for (const s of negHits) emit({ file, check: "句尾否定", level: "info", line: s.line, text: s.text });
  if (negHits.length > negT.max) say("句尾否定", negT.level, { text: `${negHits.length} 处（阈值 ${negT.max}），占全章句子 ${sents.length ? Math.round(negHits.length / sents.length * 100) : 0}%`,
    note: "叙述句末短句落在没、不上写的是人没做什么；师承一章七到十七处（每千字一到两个）" });
  for (const s of dblHits) say("双否定", dblT.max === 0 ? dblT.level : "info", { line: s.line, text: s.text });
  if (dblT.max > 0 && dblHits.length > dblT.max) say("双否定", dblT.level, { text: `${dblHits.length} 处（阈值 ${dblT.max}）` });

  // 4. 标点：只数叙述，按每千字（网文口径：感叹号、省略号几乎都在对白与心声里；分隔行与引出对白的破折号不是停顿）
  const chars = countAll(body, /[\p{L}\p{N}]/gu);
  const narration = C.narrationOf(body);
  const counts = { exclaim: countAll(narration, /[！!]/g), ellipsis: countAll(narration, /(?:…+|\.{3,})/g), dash: countAll(narration, /(?:—+|--+)/g) };
  const perK = {};
  for (const k of Object.keys(counts)) {
    perK[k] = chars ? +(counts[k] * 1000 / chars).toFixed(1) : 0;
    const t = prof.thresholds[`${k}PerK`];
    if (t && perK[k] > t.max) say(t.label, t.level, { text: `叙述里 ${counts[k]} 处，每千字 ${perK[k]}（阈值 ${t.max}）` });
  }

  // 5. 字数、句长、段长（只报）
  const paras = lines.filter(l => l.trim() && !/^#/.test(l));
  const sentenceAvg = sents.length ? Math.round(chars / sents.length) : 0;
  const paragraphAvg = paras.length ? Math.round(chars / paras.length) : 0;
  const range = prof.chapterRange || (prof.chapterChars ? [prof.chapterChars * 0.7, prof.chapterChars * 1.3] : null);
  if (range && (chars < range[0] || chars > range[1])) emit({ file, check: "字数", level: "info", text: `${chars} 字，本书章长 ${prof.chapterChars} 上下（${range[0]} 到 ${range[1]}）` });
  for (const [k, v] of [["sentenceAvg", sentenceAvg], ["paragraphAvg", paragraphAvg]]) {
    const t = prof.thresholds[k];
    if (t && v > t.max) emit({ file, check: t.label, level: t.level, text: `${v} 字（阈值 ${t.max}）` });
  }

  // 6. 伏笔物件次数
  const objects = {};
  for (const o of ctx.themeInfo.objects) {
    if (!o.patterns.length) continue;
    const here = objectHits(body, o.patterns);
    let before = 0;
    for (const p of ctx.allPrev) if (fs.existsSync(p)) before += objectHits(C.readText(p), o.patterns).length;
    const total = before + here.length;
    objects[o.id] = { chapter: here.length, total, limit: o.limit };
    for (const h of here) emit({ file, check: "装置", level: "info", line: h.line + 0, col: h.col, text: h.context, note: `${o.id} ${o.name}：本章第 ${here.indexOf(h) + 1} 次，全书第 ${before + here.indexOf(h) + 1} 次${o.limit !== null ? `，上限 ${o.limit}` : ""}` });
    if (o.limit !== null && total > o.limit) say("装置超限", prof.objects.level, { text: `${o.id} ${o.name} 到本章共 ${total} 次，上限 ${o.limit}`, note: o.usage });
  }

  // 6b. 套话、体感密度、定格式收尾（词表 references/写作层/套话.json；2026-09-26 叙述层：样例书第一稿每千字身体词 6.4，师承 0.2 到 1.3）
  let tics = 0, bodyDensity = 0;
  if (T.tics || T.body || T.freeze) {
    const bodyLines = body.split(/\r?\n/);
    for (const t of T.tics || []) {
      const re = new RegExp(t.pattern, "g");
      bodyLines.forEach((l, i) => { let m; while ((m = re.exec(l))) { tics++; say(t.label, t.level, { line: i + 1, col: m.index + 1, text: l.slice(Math.max(0, m.index - 8), m.index + m[0].length + 8), note: t.note || "" }); if (!m[0]) re.lastIndex++; } });
    }
    const bodyHits = objectHits(body, T.body || []);
    bodyDensity = chars ? +(bodyHits.length * 1000 / chars).toFixed(1) : 0;
    const bt = prof.thresholds.bodyDensity;
    if (bt && bodyDensity > bt.max) say(bt.label, bt.level, { text: `每千字 ${bodyDensity} 个身体部位词（阈值 ${bt.max}）`, note: "情绪全走身体是清单式写法；身体反应留给一章最要紧的一下，其余按文风卡叙述者一节直说" });
    if (T.freeze && paras.length) {
      const last = paras[paras.length - 1].trim();
      if (last.length <= (T.freeze.maxChars || 45) && new RegExp(T.freeze.pattern).test(last)) emit({ file, check: "定格式收尾", level: "info", line: lines.lastIndexOf(paras[paras.length - 1]) + 1, text: last, note: T.freeze.note || "" });
    }
  }

  // 7. 去味词表（可选）
  let banned = 0;
  if (args.banned && fs.existsSync(args.banned)) {
    const words = C.readText(args.banned).split(/\r?\n/).map(s => s.trim()).filter(s => s && !s.startsWith("#"));
    for (const h of objectHits(body, words)) { banned++; say("去味词", "warn", { line: h.line, col: h.col, text: h.context, note: h.pattern }); }
  }

  emit({ summary: true, file, profile: prof.name, overrides: prof.overrides, chars, paragraphs: paras.length, sentences: sents.length,
    negationTail: negHits.length, negationRatio: sents.length ? +(negHits.length / sents.length).toFixed(3) : 0, doubleNegation: dblHits.length,
    exclaim: counts.exclaim, ellipsis: counts.ellipsis, dash: counts.dash, exclaimPerK: perK.exclaim, ellipsisPerK: perK.ellipsis, dashPerK: perK.dash, sentenceAvg, paragraphAvg,
    copies, repeats, banned, tics, bodyDensity, objects, sources: copyIndex.size ? copySources.size : 0, prev: ctx.prev.length, errors, warns });
  return errors;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.files.length) {
    console.error("用法：node scripts/check-prose.js <正文.md>... [--book 书/] [--plan 细纲.md] [--style 文风.md] [--theme 主题.md] [--cards 人物/] [--source 路径] [--prev 前一章.md] [--profile 轮廓名] [--names 甲,乙] [--banned 词表] [--window N] [--summary]");
    process.exit(2);
  }
  let errors = 0;
  const order = args.files.map(f => path.resolve(f));
  for (const f of args.files) {
    const ctx = resolve(path.resolve(f), args, order);
    ctx.file = f;
    // 命令行里排在前面的章当前文时，路径按给的写
    if (!args.prev.length && !(ctx.book && ctx.chapter !== null && fs.existsSync(path.join(ctx.book, "正文")))) {
      ctx.allPrev = args.files.slice(0, args.files.indexOf(f));
      ctx.prev = ctx.allPrev.slice(-(args.window || ctx.profile.repeat.window));
    }
    errors += checkOne(ctx, args, o => { if (o.summary || !args.summary) console.log(JSON.stringify(o)); });
  }
  process.exit(errors ? 1 : 0);
}

main();
