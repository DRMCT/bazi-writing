// 写作层检查器的公共部分（DESIGN-写作层 第 10 节）：书目录推断、markdown 解析、轮廓与阈值、主题的装置表与白名单、
// 编号池、人名与生年、n-gram 连串比对、叙述与对白的分开。零依赖，check-plan.js 与 check-prose.js 共用。
"use strict";
const fs = require("fs");
const path = require("path");

const PROFILE_TABLE = path.join(__dirname, "..", "references", "写作层", "轮廓.json");
const BOOK_DIR = "书";
const QUOTE_RE = /[“”"「」『』]/;
const ID_RE = /\b(?:J|TH|Q|L|D|E|IN|IM|LI|YQ|U|N|NT|G|S|R|C|P|T|H|Y)-[0-9A-Za-z㐀-鿿]+(?:-[0-9A-Za-z㐀-鿿]+)*/g;
const PARA = "¶";
const ID_VALUE_RE = /^(?:J|TH|Q|L|D|E|IN|IM|LI|YQ|U|N|NT|G|S|R|C|P|T|H|Y|DM)(?:-\S+)?$/;

function readText(p) {
  return fs.readFileSync(p, "utf8").replace(/^﻿/, "");
}

// 去掉 HTML 注释但保住行号（注释里的字全换成空格，换行留着）
function stripComments(text) {
  return text.replace(/<!--[\s\S]*?-->/g, m => m.replace(/[^\n]/g, " "));
}

// 只认三种形状：`- 字段：值`（标题下、第一个 ## 之前是文件字段，之后归小节）、`## 小节`、markdown 表（小节内第一行 | 是表头）
function parseMd(text) {
  const lines = stripComments(text).split(/\r?\n/);
  const doc = { title: "", fields: {}, fieldLines: {}, sections: [], lines };
  let cur = null;
  let lastField = null;  // 上一个字段行 {target, key}：紧跟其后的缩进子条（"  - …""  1. …""  ①…"）算这个字段的值
  lines.forEach((raw, i) => {
    const line = raw.trimEnd();
    const n = i + 1;
    const h1 = /^#\s+(.*)$/.exec(line);
    if (h1 && !doc.title && !cur) { doc.title = h1[1].trim(); return; }
    const h2 = /^##\s+(.*)$/.exec(line);
    if (h2) { cur = { heading: h2[1].trim(), line: n, text: [], rows: [], header: null, fields: {}, fieldLines: {} }; doc.sections.push(cur); lastField = null; return; }
    const f = /^-\s+([^：:]{1,24})[：:]\s*(.*)$/.exec(line);
    if (f) {
      const key = f[1].trim(), val = f[2].trim();
      const target = cur || doc;
      if (!(key in target.fields)) { target.fields[key] = val; target.fieldLines[key] = n; lastField = { target, key }; }
      else lastField = null;
    } else if (lastField && /^\s+(-|\d+[.、]|[①-⑳])\s*\S/.test(line)) {
      const t = lastField.target, k = lastField.key;
      t.fields[k] = (t.fields[k] ? t.fields[k] + "\n" : "") + line.trim();
    } else if (line.trim()) lastField = null;
    if (!cur) return;
    if (/^\|/.test(line)) {
      const cells = line.split("|").slice(1, -1).map(c => c.trim());
      if (cells.every(c => /^:?-{2,}:?$/.test(c))) return;
      if (!cur.header) { cur.header = cells; return; }
      const row = { line: n };
      cur.header.forEach((h, k) => { row[h] = cells[k] === undefined ? "" : cells[k]; });
      cur.rows.push(row);
      return;
    }
    cur.text.push({ line: n, text: line });
  });
  return doc;
}

function section(doc, heading) {
  return doc.sections.find(s => s.heading === heading) || null;
}

// 小节正文（不含表与字段行），去掉空行与提示
function bodyText(sec) {
  if (!sec) return "";
  return sec.text.map(t => t.text).filter(t => t.trim() && !/^-\s+[^：:]{1,24}[：:]/.test(t)).join("\n");
}

// 尖括号里的提示、待填、待补充算空
function isBlank(v) {
  if (v === undefined || v === null) return true;
  const s = String(v).trim();
  return !s || /^<[^>]*>$/.test(s) || /^(待填|待补充)$/.test(s);
}

// 句尾否定（2026-09-26 严口径）：叙述句（引号里的不算）末一个短句以否定动词收尾（没、没有、不加一到四个字），复合词与成语（不适应、不错）与反问（信不信）不算。
// 粗尺（末句里有没或不就算）把师承数成 11%，严口径 3% 到 9%；check-prose 与 style-stats 共用这一处。
function tailNegation(sentence, compounds) {
  const core = String(sentence).replace(/[“"][^”"]*[”"]/g, "").replace(/[。！？!?]+$/, "").trim();
  if (!core || /[“”"]/.test(core)) return false;  // 引号没配上对的，是被句号切开的对白，不算叙述句
  const last = core.split(/[，；：]/).pop().replace(/(的|了|呢|呀|吧|啊)$/, "");
  if (!last || last.length > 14) return false;
  if (/([\u4e00-\u9fa5])不\1/.test(last)) return false;
  if (compounds && compounds.length && new RegExp(compounds.join("|")).test(last)) return false;
  return /(没有|没|不)[\u4e00-\u9fa5]{1,4}$/.test(last);
}

function splitList(v) {
  if (isBlank(v)) return [];
  return String(v).split(/[、，,;；\s]+/).map(s => s.trim()).filter(s => s && s !== "无");
}

// 书目录：路径里名为 书 的祖先，或含 主题.md 与 文风.md 的祖先
function findBook(p) {
  let dir = path.resolve(fs.existsSync(p) && fs.statSync(p).isDirectory() ? p : path.dirname(p));
  for (let k = 0; k < 6; k++) {
    if (path.basename(dir) === BOOK_DIR || (fs.existsSync(path.join(dir, "主题.md")) && fs.existsSync(path.join(dir, "文风.md")))) {
      return { book: dir, root: path.dirname(dir) };
    }
    const up = path.dirname(dir);
    if (up === dir) break;
    dir = up;
  }
  return null;
}

function chapterNo(file) {
  const m = /第(\d+)章/.exec(path.basename(file));
  return m ? parseInt(m[1], 10) : null;
}

// 轮廓：默认表 + 主题的写法轮廓行 + 文风阈值表的覆盖。表里没有的轮廓名退回第一张表，asked 记着原来写的名字
function profileNames() {
  return Object.keys(JSON.parse(readText(PROFILE_TABLE)).profiles);
}

function loadProfile({ themeDoc = null, styleDoc = null, name = null } = {}) {
  const table = JSON.parse(readText(PROFILE_TABLE));
  const names = Object.keys(table.profiles);
  const asked = name || (themeDoc && themeDoc.fields["写法轮廓"]) || names[0];
  const pname = table.profiles[asked] ? asked : names[0];
  const base = table.profiles[pname];
  const prof = {
    name: pname,
    asked,
    chapterChars: base.chapterChars,
    chapterRange: Array.isArray(base.chapterRange) ? [...base.chapterRange] : null,
    thresholds: JSON.parse(JSON.stringify(base.thresholds)),
    copy: { ...base.copy },
    repeat: { ...base.repeat },
    objects: { ...base.objects },
    threadIdle: { ...base.threadIdle },
    reviewEvery: base.reviewEvery,
    borrowWords: table.borrowWords,
    expect: base.expect ? { ...base.expect } : null,  // 期待账（DESIGN-写作层 4）
    rhythm: base.rhythm ? { ...base.rhythm } : null,
    scales: table.scales || [],
    hookKinds: table.hookKinds || [],
    hooklessKinds: table.hooklessKinds || [],
    roundEndBad: table.roundEndBad || [],
    expectActs: table.expectActs || [],
    reliefKinds: table.reliefKinds || [],
    overrides: [],
  };
  const sec = styleDoc && section(styleDoc, "阈值");
  if (sec) {
    for (const row of sec.rows) {
      const key = table.fieldKeys[row["项"]];
      const val = parseFloat(row["值"]);  // 体感密度一类可带小数（2026-09-26）
      if (!key || Number.isNaN(val)) continue;
      if (key === "chapterChars") {
        const scale = prof.chapterChars ? val / prof.chapterChars : 1;  // 本书章长改了，范围跟着按比例挪
        prof.chapterChars = val;
        if (prof.chapterRange) prof.chapterRange = prof.chapterRange.map(x => Math.round(x * scale));
      }
      else if (key === "copyNgram") prof.copy.ngram = val;
      else if (key === "repeatNgram") prof.repeat.ngram = val;
      else if (key === "repeatWindow") prof.repeat.window = val;
      else if (prof.thresholds[key]) prof.thresholds[key].max = val;
      prof.overrides.push(row["项"]);
    }
  }
  return prof;
}

// 主题：装置表与白名单
function loadTheme(themeDoc) {
  const out = { objects: [], whitelist: [], profile: themeDoc.fields["写法轮廓"] || null, main: themeDoc.fields["主角"] || null };
  const dev = section(themeDoc, "装置");
  if (dev) {
    for (const row of dev.rows) {
      const id = (row["编号"] || "").trim();
      if (!id || isBlank(id)) continue;
      const touch = (row["碰的上限"] || "").trim();  // 碰与特写的上限，可空；全书上限数认法出现的次数，提到也算
      out.objects.push({
        id, name: row["装置"] || "", kind: row["类型"] || "", line: row.line,
        patterns: splitList(row["认法"]).filter(s => !/^<.*>$/.test(s)),
        limit: /^\d+$/.test((row["全书上限"] || "").trim()) ? parseInt(row["全书上限"], 10) : null,
        usage: row["用法"] || "",
        touchLimit: /^\d+$/.test(touch) ? parseInt(touch, 10) : null,
        touchLimitBad: !isBlank(touch) && !/^\d+$/.test(touch),
      });
    }
  }
  const wl = section(themeDoc, "白名单");
  if (wl) {
    for (const t of wl.text) {
      const m = /^-\s+(.*)$/.exec(t.text);
      if (m && !isBlank(m[1])) out.whitelist.push(m[1].trim());
    }
  }
  return out;
}

// 编号池：项目根 命盘/ 下所有 JSON 里形如 X-… 的字符串值（features、idPool、线程、矩阵边、日程交汇都在里面）
function loadIdPool(root, extra = []) {
  const ids = new Set();
  const walk = v => {
    if (typeof v === "string") { if (ID_VALUE_RE.test(v)) ids.add(v); return; }
    if (Array.isArray(v)) { for (const x of v) walk(x); return; }
    if (v && typeof v === "object") for (const k of Object.keys(v)) walk(v[k]);
  };
  const files = [];
  const dir = path.join(root, "命盘");
  const list = d => {
    if (!fs.existsSync(d)) return;
    for (const name of fs.readdirSync(d)) {
      const full = path.join(d, name);
      const st = fs.statSync(full);
      if (st.isDirectory()) list(full);
      else if (name.endsWith(".json")) files.push(full);
    }
  };
  list(dir);
  for (const f of extra) if (f && fs.existsSync(f)) files.push(f);
  for (const f of files) {
    try { walk(JSON.parse(readText(f))); } catch (e) { /* 坏 JSON 交给别的检查器 */ }
  }
  return { ids, files: files.length };
}

// 人名：人物/ 与 命盘/ 顶层 JSON 的文件名（第一个点之前），去掉矩阵、日程
function loadNames(root) {
  const names = new Set();
  for (const sub of ["人物", "命盘"]) {
    const d = path.join(root, sub);
    if (!fs.existsSync(d)) continue;
    for (const name of fs.readdirSync(d)) {
      if (!name.endsWith(".json")) continue;
      const base = name.split(".")[0];
      if (base && !["矩阵", "日程", "推演", "线程"].includes(base)) names.add(base);
    }
  }
  return names;
}

// 生年：命盘/{名}.年表.json 里任何带 year 与 age 的对象，取 year-age 的最小值
function loadBirthYears(root, names) {
  const out = new Map();
  for (const name of names) {
    const f = path.join(root, "命盘", `${name}.年表.json`);
    if (!fs.existsSync(f)) continue;
    let best = null;
    const walk = v => {
      if (Array.isArray(v)) { for (const x of v) walk(x); return; }
      if (v && typeof v === "object") {
        if (Number.isInteger(v.year) && Number.isInteger(v.age)) { const b = v.year - v.age; if (best === null || b < best) best = b; }
        for (const k of Object.keys(v)) walk(v[k]);
      }
    };
    try { walk(JSON.parse(readText(f))); } catch (e) { /* 忽略 */ }
    if (best !== null) out.set(name, best);
  }
  return out;
}

// 归一：只留字母数字（含汉字），人名折成一个 〇，记每个字在原文的行列
function normalize(text, names = []) {
  const sorted = [...names].filter(Boolean).sort((a, b) => b.length - a.length);
  const chars = [], pos = [];
  const lines = text.split(/\r?\n/);
  for (let li = 0; li < lines.length; li++) {
    const line = lines[li];
    let i = 0;
    while (i < line.length) {
      let matched = null;
      for (const nm of sorted) if (line.startsWith(nm, i)) { matched = nm; break; }
      if (matched) { chars.push("〇"); pos.push({ line: li + 1, col: i + 1 }); i += matched.length; continue; }
      const ch = line[i];
      if (/[\p{L}\p{N}]/u.test(ch)) { chars.push(ch); pos.push({ line: li + 1, col: i + 1 }); }
      i++;
    }
    chars.push(PARA); pos.push({ line: li + 1, col: line.length + 1 });  // 段末记号：连串不跨段
  }
  return { chars, pos, str: chars.join(""), lines };
}

function gramIndex(norm, n, tag, index = new Map()) {
  for (let i = 0; i + n <= norm.chars.length; i++) {
    const g = norm.str.slice(i, i + n);
    if (g.includes(PARA)) continue;
    if (!index.has(g)) index.set(g, { tag, idx: i });
  }
  return index;
}

// 目标里与索引连续重合的最长串；同一来源里必须真是连续的一段（整串在来源归一串里能找到），否则从尾巴缩到能找到为止
function findRuns(target, index, n, sources) {
  const runs = [];
  let i = 0;
  const L = target.chars.length;
  while (i + n <= L) {
    const hit = index.get(target.str.slice(i, i + n));
    if (!hit) { i++; continue; }
    let j = i + n;
    while (j < L) {
      const h2 = index.get(target.str.slice(j - n + 1, j + 1));
      if (!h2 || h2.tag !== hit.tag) break;
      j++;
    }
    const src = sources.get(hit.tag);
    let end = j, text = target.str.slice(i, end), at = src ? src.str.indexOf(text) : -1;
    while (at < 0 && end - i > n) { end--; text = target.str.slice(i, end); at = src ? src.str.indexOf(text) : -1; }
    if (at < 0) { i++; continue; }
    runs.push({ start: i, end, text, tag: hit.tag, srcIdx: at });
    i = end;
  }
  return runs;
}

// 归一串里一段对应的原文片段（按起止的行列切）
function excerpt(norm, start, end) {
  const a = norm.pos[start], b = norm.pos[Math.max(start, end - 1)];
  if (!a || !b) return "";
  if (a.line === b.line) return norm.lines[a.line - 1].slice(a.col - 1, b.col);
  return norm.lines[a.line - 1].slice(a.col - 1) + "…" + norm.lines[b.line - 1].slice(0, b.col);
}

function listFiles(p, exts) {
  const st = fs.statSync(p);
  if (st.isFile()) return [p];
  const out = [];
  for (const name of fs.readdirSync(p).sort()) {
    if (name.startsWith(".") || name.startsWith("_")) continue;
    const full = path.join(p, name);
    const s = fs.statSync(full);
    if (s.isDirectory()) out.push(...listFiles(full, exts));
    else if (exts.includes(path.extname(name))) out.push(full);
  }
  return out;
}

// 叙述（网文口径，六本女频长篇量过）：引号与【】里的是对白、心声、屏上文字，不算叙述；
// 单独成行的分隔符（……、——、***）是换场，不算标点；紧挨着引号的破折号（开口道——“）是引出对白，不算停顿
const SEPARATOR_RE = /^\s*(?:[….。·•]+|[—\-－─]+|[*＊]+|[~～]{2,})\s*$/;
function narrationOf(text) {
  return String(text).split(/\r?\n/).map(line => {
    if (/^#/.test(line) || SEPARATOR_RE.test(line)) return "";
    return line.replace(/(?:—+|--+)\s*(?=[“"「])/g, "").replace(/“[^”\n]*”/g, "").replace(/「[^」\n]*」/g, "").replace(/【[^】\n]*】/g, "").replace(/"[^"\n]*"/g, "");
  }).join("\n");
}

const OBJ_RE = /\bF\d{3,}\b/g;  // 装置编号：F001，与伏笔表同形，不带连字符
const EXPECT_RE = /^K\d{3,}$/;  // 期待编号：K001，卷稿期待线登记，全书连号；细纲里一章之内开了就收的小循环写 章内，不登记

module.exports = {
  tailNegation, narrationOf, SEPARATOR_RE, profileNames,
  PROFILE_TABLE, BOOK_DIR, QUOTE_RE, ID_RE, OBJ_RE, EXPECT_RE, PARA, readText, stripComments, parseMd, section, bodyText, isBlank, splitList,
  findBook, chapterNo, loadProfile, loadTheme, loadIdPool, loadNames, loadBirthYears, normalize, gramIndex, findRuns, excerpt, listFiles,
};
