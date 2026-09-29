#!/usr/bin/env node
// 戏用页检查（DESIGN-戏剧层 5）。戏用页是一个人给排戏的人和写手读的一页：十问，按戏的问题排，不按盘的事实排。
//
//   node scripts/check-drama.js 人物/甲.戏用页.json
//   node scripts/check-drama.js 人物/甲.戏用页.json --matrix 命盘/矩阵.json --timeline 命盘/甲.年表.json --run 命盘/群像/推演.json
//   node scripts/check-drama.js 人物/甲.戏用页.json --final        事件链写完以后用：第七问（他瞒着什么）不许空
//   node scripts/check-drama.js 人物/甲.戏用页.json --summary
//
// 形态 bazi-drama-page/v1：
//   {"schema": "bazi-drama-page/v1", "name": "甲", "chart": "命盘/甲.json", "pronoun": "她",
//    "asks": [{"ask": "他要什么", "lines": [{"text": "……", "origin": "定", "ref": "编配 对子 甲、乙"}]}, …]}
// 十问次序固定，键一律写"他"，渲染时按 pronoun 换。每行两种来历之一：
//   盘：带盘上的编号 sources，编号要在命盘、矩阵、年表、推演里找得到；
//   定：编配或作者定的，没有盘上的编号，ref 写编配表哪一行，或写作者定与日期。
// 第六问（碰哪里会疼）每行另带 line（哪根线，一个短名）与 beat（碰线、身体先动、盖法、破、余波）：
//   每根线要有碰线，后面要么有盖法要么有破；整页至少一条破。破的那一行可带 by（谁来破：自己、别人当面、物证），不带算自己。
// 页级 belief：假话（默认）或信条。信条页的第四问写他拿来过日子的那句话、谁来挑战、怎么走（被认可、不认、慢慢松、碎），
//   不强求碎：整页没有破只报 info。主角默认写信条，谎言与碎给编配谁碎一节挑出来的人。
// 十问之后有六个附问，都可以空，有就按次序排在十问后面：他被叫什么、他知道哪一层、他信错了谁、他对谁演什么、
//   他独一份的是什么、他怎么被记住。口头禅要反复出现，所以只有最后一问允许一行带引号。
// 查：十问齐、次序对；每行 text 非空、没有引号、来历合法；第一至六问、第八至十问至少一行；第七问事件链之前可以空。
// 一页写不下就是没挑：十问 text 合计超过 PAGE_LIMIT 字、附问合计超过 EXTRA_LIMIT 字报 warn，不拦。
// 每条问题一行 JSON，最后一行汇总，有 error 退出码 1。
"use strict";
const fs = require("fs");
const path = require("path");

const ASKS = ["他要什么", "谁挡着", "他怎么去要", "他信的那句假话", "他真正缺的", "碰哪里会疼", "他瞒着什么", "他怎么说话", "别人拿他当什么", "他从哪儿走到哪儿"];
const BEATS = ["碰线", "身体先动", "盖法", "破", "余波"];
const EXTRAS = ["他被叫什么", "他知道哪一层", "他信错了谁", "他对谁演什么", "他独一份的是什么", "他怎么被记住"];
const BELIEFS = ["假话", "信条"];
const BREAK_BY = ["自己", "别人当面", "物证"];
const HURT = "碰哪里会疼", SECRET = "他瞒着什么", REMEMBERED = "他怎么被记住";
const PAGE_LIMIT = 1800, EXTRA_LIMIT = 600;

function main() {
  const argv = process.argv.slice(2);
  let chartPath = null, matrixPath = null, timelinePath = null, runPath = null, summaryOnly = false, final = false;
  const files = [];
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--chart") chartPath = argv[++i];
    else if (argv[i] === "--matrix") matrixPath = argv[++i];
    else if (argv[i] === "--timeline") timelinePath = argv[++i];
    else if (argv[i] === "--run") runPath = argv[++i];
    else if (argv[i] === "--final") final = true;
    else if (argv[i] === "--summary") summaryOnly = true;
    else files.push(argv[i]);
  }
  if (files.length !== 1) {
    console.error("用法：node scripts/check-drama.js <戏用页.json> [--chart 命盘.json] [--matrix 矩阵.json] [--timeline 年表.json] [--run 推演.json] [--final] [--summary]");
    process.exit(2);
  }
  const file = files[0];
  const doc = JSON.parse(fs.readFileSync(file, "utf8"));
  const problems = [];
  const report = (level, ask, line, problem) => problems.push({ file, level, ask, line, problem });

  if (doc.schema !== "bazi-drama-page/v1") report("error", null, null, `schema 应为 bazi-drama-page/v1，实为 ${doc.schema}`);
  if (!doc.name) report("error", null, null, "缺 name");
  const belief = doc.belief === undefined ? "假话" : doc.belief;
  if (!BELIEFS.includes(belief)) report("error", null, null, `belief 应为 ${BELIEFS.join("、")} 之一，实为 ${doc.belief}`);
  if (!chartPath) {
    if (!doc.chart) report("error", null, null, "缺 chart 字段且未给 --chart");
    else chartPath = path.resolve(path.dirname(path.resolve(file)), "..", doc.chart);
  }
  const ids = new Set();
  const load = (p, what, take) => {
    if (!p) return;
    if (!fs.existsSync(p)) { report("error", null, null, `${what}文件不存在：${p}`); return; }
    take(JSON.parse(fs.readFileSync(p, "utf8")));
  };
  load(chartPath, "命盘", c => { for (const f of c.features || []) ids.add(f.id); });
  load(matrixPath, "矩阵", m => { for (const e of m.edges || []) if (e.from === doc.name || e.to === doc.name) for (const f of e.features || []) ids.add(f.id); });
  load(timelinePath, "年表", t => { for (const f of t.features || []) ids.add(f.id); });
  load(runPath, "推演", r => { for (const id of r.idPool || []) ids.add(id); });

  const asks = Array.isArray(doc.asks) ? doc.asks : [];
  const titles = asks.map(a => a.ask);
  for (const a of ASKS) if (!titles.includes(a)) report("error", a, null, "这一问缺席");
  const ALL = ASKS.concat(EXTRAS);
  for (const t of titles) if (!ALL.includes(t)) report("error", t, null, `不认识的问：${t}；十问是 ${ASKS.join("、")}，附问是 ${EXTRAS.join("、")}`);
  const order = titles.filter(t => ALL.includes(t));
  if (order.join("|") !== ALL.filter(a => order.includes(a)).join("|")) report("error", null, null, "十问与附问的次序不对：十问在前，附问在后，各按固定次序");

  let lines = 0, chars = 0, extraChars = 0, chart = 0, decided = 0, breaks = 0, extras = 0, quoted = 0;
  for (const a of asks) {
    const ls = Array.isArray(a.lines) ? a.lines : [];
    const extra = EXTRAS.includes(a.ask);
    if (extra && ls.length) extras++;
    if (!ls.length) {
      if (extra) continue;
      if (a.ask === SECRET && !final) report("info", a.ask, null, "还空着：事件链写完以后补，补完带 --final 再查");
      else if (ASKS.includes(a.ask)) report("error", a.ask, null, "这一问没有答");
    }
    const byLine = new Map();
    const seen = new Set();
    for (const [i, l] of ls.entries()) {
      const label = `${a.ask}#${i + 1}`;
      lines++;
      const text = (l.text || "").trim();
      if (!text) { report("error", a.ask, label, "text 为空"); continue; }
      if (extra) extraChars += text.length; else chars += text.length;
      if (seen.has(text)) report("error", a.ask, label, "这一问里重复");
      seen.add(text);
      if (/[“”"「」]/.test(text)) {
        if (a.ask === REMEMBERED && !quoted) quoted++;
        else report("error", a.ask, label, a.ask === REMEMBERED ? "这一问只许一行带引号：那一句格言或口头禅" : "戏用页不给台词：写句式、场合与倾向，引号里的话会被写手照抄进正文");
      }
      if (l.origin === "盘") {
        chart++;
        const src = Array.isArray(l.sources) ? l.sources : [];
        if (!src.length) report("error", a.ask, label, "来历是盘，要带盘上的编号 sources");
        for (const id of src) if (!ids.has(id)) report("error", a.ask, label, `编号找不到：${id}`);
      } else if (l.origin === "定") {
        decided++;
        if (!(l.ref || "").trim()) report("error", a.ask, label, "来历是定，ref 要写编配表哪一行，或写作者定与日期");
      } else report("error", a.ask, label, `origin 应为 盘 或 定，实为 ${l.origin}`);
      if (a.ask === HURT) {
        if (!(l.line || "").trim()) report("error", a.ask, label, "要写 line：这是哪根线，一个短名");
        if (!BEATS.includes(l.beat)) report("error", a.ask, label, `beat 应为 ${BEATS.join("、")} 之一，实为 ${l.beat}`);
        else {
          const k = (l.line || "").trim();
          if (!byLine.has(k)) byLine.set(k, new Set());
          byLine.get(k).add(l.beat);
          if (l.beat === "破") breaks++;
        }
        if (l.by !== undefined) {
          if (l.beat !== "破") report("error", a.ask, label, "只有破那一拍带 by（谁来破）");
          else if (!BREAK_BY.includes(l.by)) report("error", a.ask, label, `by 应为 ${BREAK_BY.join("、")} 之一，实为 ${l.by}`);
        }
      } else if (l.beat !== undefined || l.line !== undefined || l.by !== undefined) report("error", a.ask, label, `只有${HURT}这一问的行带 line、beat 与 by`);
    }
    if (a.ask === HURT && ls.length) {
      if (byLine.size > 3) report("warn", a.ask, null, `写了 ${byLine.size} 根线，至多三根：挑这本书里会被碰到的`);
      for (const [k, beats] of byLine) {
        if (!beats.has("碰线")) report("error", a.ask, k, "这根线没有碰线那一拍");
        if (!beats.has("盖法") && !beats.has("破")) report("error", a.ask, k, "这根线碰了以后怎样：要么有盖法，要么有破");
      }
      if (!breaks) {
        if (belief === "信条") report("info", a.ask, null, "信条页没有破：他不碎，那句话怎么走写在第四问与第十问");
        else report("error", a.ask, null, "整页没有一条破：他什么时候盖不住、破了做什么");
      }
    }
  }
  if (chars > PAGE_LIMIT) report("warn", null, null, `十问 ${chars} 字，超过 ${PAGE_LIMIT}：一页写不下就是没挑`);
  if (extraChars > EXTRA_LIMIT) report("warn", null, null, `附问 ${extraChars} 字，超过 ${EXTRA_LIMIT}：附问是几样看得见的东西，一问一两行`);

  const errors = problems.filter(p => p.level === "error").length;
  const warns = problems.filter(p => p.level === "warn").length;
  if (!summaryOnly) for (const p of problems) console.log(JSON.stringify(p));
  console.log(JSON.stringify({ summary: true, file, belief, asks: asks.length, extras, lines, chars, extraChars, chart, decided, breaks, errors, warns, featureIds: ids.size }));
  process.exit(errors ? 1 : 0);
}

main();
