#!/usr/bin/env node
// 文体量尺（DESIGN-写作层 3.2 叙述层）：对师承文本逐章、或对一章稿子，算同一组数。零依赖，JSON 一行一条，最后一行汇总。
//
//   node scripts/style-stats.js 书/师承/{书名}.txt                    逐章一行 JSON，末行汇总（各项的中位数与范围）
//   node scripts/style-stats.js 书/师承/{书名}.txt --md               markdown 表，给汇总代理读
//   node scripts/style-stats.js 书/师承/{书名}.txt --ends             章首章尾表：每章头一段与末一段（全书怎么开章怎么收章，不用读全文）
//   node scripts/style-stats.js 书/稿/U-1-第1章.v1.md --against 书/师承/{书名}.txt
//                                                                    本章各项数与师承逐章数的中位数、范围并排，出了范围的标 出界
//   --split <regex>   章标题行（整行匹配），默认 ^\s*(第[0-9一二三四五六七八九十百零〇两]+章.*|番外.*|尾声.*|后记.*)\s*$；没有匹配就整个文件当一章
//   --skip <regex>    跳过标题匹配的章，默认 ^\s*(番外|后记)
//   --tics <json>     词表，默认 references/写作层/套话.json
//
// 每章的数：chars 字数；paras 段数；sents 句数；sentAvg 平均句长；shortPct/midPct/longPct 短句(<15)中句(15-30)长句(>30)占比；
//   paraAvg 平均段长；dialoguePct 引号内字数占比；dialogueParas 带引号的段占比；negTailPct 叙述句里末短句以否定动词收尾的占比（严口径，book_common.tailNegation）；
//   body 每千字身体部位词；simile 每千字比喻引导词；voice 每千字语气词与评价副词（叙述者腔调的粗尺）；
//   exclaim/ellipsis/dash 叙述里每千字（引号与【】里的、单独成行的分隔符、引出对白的破折号不数，与 check-prose 同口径）；first/last 头一段与末一段（--ends 才打）。
"use strict";
const fs = require("fs");
const path = require("path");
const C = require("./book_common");

const DEFAULT_SPLIT = "^\\s*(第[0-9一二三四五六七八九十百零〇两]+章.*|番外.*|尾声.*|后记.*)\\s*$";
const DEFAULT_SKIP = "^\\s*(番外|后记)";
const TICS = path.join(__dirname, "..", "references", "写作层", "套话.json");

function parseArgs(argv) {
  const out = { files: [], md: false, ends: false, against: null, split: DEFAULT_SPLIT, skip: DEFAULT_SKIP, tics: TICS };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--md") out.md = true;
    else if (a === "--ends") out.ends = true;
    else if (a === "--against") out.against = argv[++i];
    else if (a === "--split") out.split = argv[++i];
    else if (a === "--skip") out.skip = argv[++i];
    else if (a === "--tics") out.tics = argv[++i];
    else out.files.push(a);
  }
  return out;
}

function readText(p) { return fs.readFileSync(p, "utf8").replace(/^﻿/, ""); }

// 切章：标题行整行匹配；标题行本身不算正文
function splitChapters(text, splitRe, skipRe) {
  const lines = text.split(/\r?\n/);
  const re = new RegExp(splitRe), skip = skipRe ? new RegExp(skipRe) : null;
  const chapters = [];
  let cur = null;
  for (const raw of lines) {
    const line = raw.replace(/^#+\s*/, "");
    if (re.test(line)) { cur = { title: line.trim(), lines: [] }; chapters.push(cur); continue; }
    if (!cur) { cur = { title: "", lines: [] }; chapters.push(cur); }
    cur.lines.push(raw);
  }
  const kept = chapters.filter(c => c.lines.some(l => l.trim()) && !(skip && c.title && skip.test(c.title)));
  return kept.length ? kept : [{ title: "", lines }];
}

function countWords(text, words) {
  let n = 0;
  for (const w of words) { let from = 0; for (;;) { const k = text.indexOf(w, from); if (k < 0) break; n++; from = k + w.length; } }
  return n;
}

function measure(ch, tics) {
  const paras = ch.lines.map(l => l.trim()).filter(l => l && !/^#/.test(l) && !/^<!--/.test(l));
  const body = paras.join("\n");
  const chars = (body.match(/[\p{L}\p{N}]/gu) || []).length;
  const per = n => chars ? +(n * 1000 / chars).toFixed(1) : 0;
  const sents = body.split(/(?<=[。！？!?])["”』」]?\s*/).map(s => s.replace(/[“”"『』「」\s]/g, "")).filter(s => s);
  const lens = sents.map(s => (s.match(/[\p{L}\p{N}]/gu) || []).length).filter(n => n > 0);
  const total = lens.length || 1;
  const pct = f => Math.round(lens.filter(f).length * 100 / total);
  const quoted = (body.match(/[“"][^”"\n]*[”"]/g) || []).join("");
  const dialogueChars = (quoted.match(/[\p{L}\p{N}]/gu) || []).length;
  const rawSents = body.split(/(?<=[。！？!?])/).map(s => s.trim()).filter(s => /[\p{L}]/u.test(s));
  const negTail = rawSents.filter(s => C.tailNegation(s, tics.negationCompounds)).length;  // 严口径，与 check-prose 同一处
  return {
    title: ch.title, chars, paras: paras.length, sents: lens.length,
    sentAvg: lens.length ? Math.round(lens.reduce((a, b) => a + b, 0) / lens.length) : 0,
    shortPct: pct(n => n < 15), midPct: pct(n => n >= 15 && n <= 30), longPct: pct(n => n > 30),
    paraAvg: paras.length ? Math.round(chars / paras.length) : 0,
    dialoguePct: chars ? Math.round(dialogueChars * 100 / chars) : 0,
    dialogueParas: paras.length ? Math.round(paras.filter(p => /[“"]/.test(p)).length * 100 / paras.length) : 0,
    negTailPct: lens.length ? Math.round(negTail * 100 / lens.length) : 0,
    body: per(countWords((tics.bodyNot || []).reduce((s, w) => s.split(w).join(" "), body), tics.body || [])),
    simile: per(countWords(body, tics.simile || [])),
    voice: per(countWords(body, tics.voice || [])),
    exclaim: per((C.narrationOf(body).match(/[！!]/g) || []).length),  // 标点与 check-prose 同口径：只数叙述，分隔行与引出对白的破折号不数
    ellipsis: per((C.narrationOf(body).match(/(?:…+|\.{3,})/g) || []).length),
    dash: per((C.narrationOf(body).match(/(?:—+|--+)/g) || []).length),
    first: paras[0] || "", last: paras[paras.length - 1] || "",
  };
}

const METRICS = ["chars", "paras", "sents", "sentAvg", "shortPct", "midPct", "longPct", "paraAvg", "dialoguePct", "dialogueParas", "negTailPct", "body", "simile", "voice", "exclaim", "ellipsis", "dash"];
const LABELS = { chars: "字数", paras: "段数", sents: "句数", sentAvg: "平均句长", shortPct: "短句%", midPct: "中句%", longPct: "长句%", paraAvg: "平均段长", dialoguePct: "对白字数%", dialogueParas: "带对白的段%", negTailPct: "句尾否定%", body: "体感/千字", simile: "比喻词/千字", voice: "语气词/千字", exclaim: "叙述感叹号/千字", ellipsis: "叙述省略号/千字", dash: "叙述破折号/千字" };

function median(xs) { const s = [...xs].sort((a, b) => a - b); const m = s.length >> 1; return s.length % 2 ? s[m] : +((s[m - 1] + s[m]) / 2).toFixed(1); }
function summarize(rows) {
  const out = { summary: true, chapters: rows.length };
  for (const k of METRICS) { const xs = rows.map(r => r[k]); out[k] = { median: median(xs), min: Math.min(...xs), max: Math.max(...xs) }; }
  return out;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.files.length) { console.error("用法：node scripts/style-stats.js <文本> [--md] [--ends] [--against 师承文本] [--split 正则] [--skip 正则]"); process.exit(2); }
  const tics = fs.existsSync(args.tics) ? JSON.parse(readText(args.tics)) : {};
  const strip = r => { const { first, last, ...rest } = r; return rest; };
  if (args.against) {
    const ref = splitChapters(readText(args.against), args.split, args.skip).map(c => measure(c, tics));
    const sum = summarize(ref);
    for (const f of args.files) {
      const mine = measure({ title: path.basename(f), lines: readText(f).split(/\r?\n/) }, tics);
      const rows = METRICS.filter(k => !["chars", "paras", "sents"].includes(k)).map(k => {
        const s = sum[k], v = mine[k];
        const out = v < s.min ? "低于师承" : v > s.max ? "高于师承" : "";
        return { metric: k, label: LABELS[k], mine: v, median: s.median, min: s.min, max: s.max, verdict: out };
      });
      if (args.md) {
        console.log(`| 项 | 本章 | 师承中位数 | 师承范围 | 出界 |\n|---|---|---|---|---|`);
        for (const r of rows) console.log(`| ${r.label} | ${r.mine} | ${r.median} | ${r.min}–${r.max} | ${r.verdict} |`);
        console.log(`\n字数 ${mine.chars}，师承每章中位数 ${sum.chars.median}（${sum.chars.min}–${sum.chars.max}）；师承 ${ref.length} 章。`);
      } else {
        for (const r of rows) console.log(JSON.stringify({ file: f, ...r }));
        console.log(JSON.stringify({ summary: true, file: f, chars: mine.chars, refChapters: ref.length, outOfRange: rows.filter(r => r.verdict).map(r => r.metric) }));
      }
    }
    return;
  }
  for (const f of args.files) {
    const rows = splitChapters(readText(f), args.split, args.skip).map((c, i) => ({ n: i + 1, ...measure(c, tics) }));
    if (args.ends) {
      if (args.md) { console.log(`| 章 | 头一段 | 末一段 |\n|---|---|---|`); for (const r of rows) console.log(`| ${r.n} ${r.title} | ${r.first.replace(/\|/g, "｜")} | ${r.last.replace(/\|/g, "｜")} |`); }
      else for (const r of rows) console.log(JSON.stringify({ n: r.n, title: r.title, first: r.first, last: r.last }));
      continue;
    }
    if (args.md) {
      console.log(`| 章 | ${METRICS.map(k => LABELS[k]).join(" | ")} |\n|---|${METRICS.map(() => "---").join("|")}|`);
      for (const r of rows) console.log(`| ${r.n} | ${METRICS.map(k => r[k]).join(" | ")} |`);
      const s = summarize(rows);
      console.log(`| 中位数 | ${METRICS.map(k => s[k].median).join(" | ")} |`);
      console.log(`| 范围 | ${METRICS.map(k => `${s[k].min}–${s[k].max}`).join(" | ")} |`);
    } else {
      for (const r of rows) console.log(JSON.stringify(strip(r)));
      console.log(JSON.stringify({ file: f, ...summarize(rows) }));
    }
  }
}

main();
