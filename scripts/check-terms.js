#!/usr/bin/env node
// 去术语检查（DESIGN 第 13 节）：对文件或目录扫词表 bazi_core/tables/terms.json，输出 JSON 行，有 error 级命中则退出码 1。
//
//   node scripts/check-terms.js 人物/ 设定/角色/            扫目录（.md .txt .json）
//   node scripts/check-terms.js 人物/张三.md --allow 桃花 --allow 丙寅   放行个别词（历史题材的纪年、意象里的桃花）
//   node scripts/check-terms.js 人物/ --allowlist .bazi-allow.txt      每行一个放行词
//   node scripts/check-terms.js 命盘/ --expect-hits                    反向用：对作者本故意跑一遍，零命中反而失败（检查器自检）
//   node scripts/check-terms.js 人物/ --summary                         只打印汇总行
//
// 每条命中一行：{"file","line","col","term","group","level","context"}；最后一行汇总 {"summary":true,"files","errors","warns"}。
// 只做子串匹配，不做分词：术语都是两字以上的固定搭配，误伤靠 warn 级与 --allow 兜住。
"use strict";
const fs = require("fs");
const path = require("path");

const TABLE = path.join(__dirname, "bazi_core", "tables", "terms.json");
const EXTS = new Set([".md", ".txt", ".json"]);

function parseArgs(argv) {
  const out = { paths: [], allow: new Set(), expectHits: false, summary: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--allow") out.allow.add(argv[++i]);
    else if (a === "--allowlist") {
      for (const line of fs.readFileSync(argv[++i], "utf8").split(/\r?\n/)) {
        const t = line.trim();
        if (t && !t.startsWith("#")) out.allow.add(t);
      }
    } else if (a === "--expect-hits") out.expectHits = true;
    else if (a === "--summary") out.summary = true;
    else out.paths.push(a);
  }
  return out;
}

function listFiles(p) {
  const st = fs.statSync(p);
  if (st.isFile()) return [p];
  const out = [];
  for (const name of fs.readdirSync(p)) {
    if (name.startsWith(".")) continue;
    const full = path.join(p, name);
    const s = fs.statSync(full);
    if (s.isDirectory()) out.push(...listFiles(full));
    else if (EXTS.has(path.extname(name))) out.push(full);
  }
  return out;
}

function loadTerms(allow) {
  const t = JSON.parse(fs.readFileSync(TABLE, "utf8"));
  const terms = [];
  for (const g of t.groups) {
    for (const term of g.terms) {
      if (allow.has(term)) continue;
      terms.push({ term, group: g.name, level: g.level });
    }
  }
  // 长词先匹配，短词若被长词覆盖则不重复报（天乙贵人 命中后不再报 贵人）
  terms.sort((a, b) => b.term.length - a.term.length);
  return terms;
}

function scanFile(file, terms) {
  const hits = [];
  const lines = fs.readFileSync(file, "utf8").split(/\r?\n/);
  lines.forEach((line, idx) => {
    const covered = [];
    for (const { term, group, level } of terms) {
      let from = 0;
      for (;;) {
        const col = line.indexOf(term, from);
        if (col < 0) break;
        const end = col + term.length;
        const overlapped = covered.some(([s, e]) => col < e && end > s);
        if (!overlapped) {
          covered.push([col, end]);
          hits.push({ file, line: idx + 1, col: col + 1, term, group, level,
                      context: line.slice(Math.max(0, col - 12), end + 12) });
        }
        from = end;
      }
    }
  });
  return hits;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.paths.length) {
    console.error("用法：node scripts/check-terms.js <文件或目录>... [--allow 词] [--allowlist 文件] [--expect-hits] [--summary]");
    process.exit(2);
  }
  const terms = loadTerms(args.allow);
  let files = 0, errors = 0, warns = 0;
  for (const p of args.paths) {
    for (const file of listFiles(p)) {
      files++;
      for (const h of scanFile(file, terms)) {
        if (h.level === "error") errors++; else warns++;
        if (!args.summary) console.log(JSON.stringify(h));
      }
    }
  }
  console.log(JSON.stringify({ summary: true, files, errors, warns, expectHits: args.expectHits }));
  if (args.expectHits) process.exit(errors > 0 ? 0 : 1);
  process.exit(errors > 0 ? 1 : 0);
}

main();
