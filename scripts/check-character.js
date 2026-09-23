#!/usr/bin/env node
// 人物档案契约与溯源检查（DESIGN 第 13 节）。
//
//   node scripts/check-character.js 人物/沈砚.json                  命盘路径取 JSON 里的 chart 字段（相对于人物档案所在目录的上一级，即项目根）
//   node scripts/check-character.js 人物/沈砚.json --chart 命盘/沈砚.json
//   node scripts/check-character.js 人物/沈砚.json --summary
//
// 检查：schema 为 bazi-character/v1；十二个必备段落在场；每条特质 text 非空且 sources 非空；每个溯源编号在命盘 features 里存在；
// 同一段落内特质不重复。每条问题一行 JSON {"file","section","trait","problem"}，最后一行汇总 {"summary":true,...}，有问题退出码 1。
"use strict";
const fs = require("fs");
const path = require("path");

const REQUIRED = ["性格表里", "童年事件", "谎言", "秘密", "需要与想要", "抵抗线", "亲密关系模式", "说话方式",
  "能力与漏洞", "意象系统", "他人眼中的他", "年表与两难"];

function main() {
  const argv = process.argv.slice(2);
  let chartPath = null, summaryOnly = false;
  const files = [];
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--chart") chartPath = argv[++i];
    else if (argv[i] === "--summary") summaryOnly = true;
    else files.push(argv[i]);
  }
  if (files.length !== 1) {
    console.error("用法：node scripts/check-character.js <人物档案.json> [--chart 命盘.json] [--summary]");
    process.exit(2);
  }
  const file = files[0];
  const doc = JSON.parse(fs.readFileSync(file, "utf8"));
  const problems = [];
  const report = (section, trait, problem) => problems.push({ file, section, trait, problem });

  if (doc.schema !== "bazi-character/v1") report(null, null, `schema 应为 bazi-character/v1，实为 ${doc.schema}`);
  if (!doc.name) report(null, null, "缺 name");
  if (!chartPath) {
    if (!doc.chart) report(null, null, "缺 chart 字段且未给 --chart");
    else chartPath = path.resolve(path.dirname(path.resolve(file)), "..", doc.chart);
  }
  let ids = new Set();
  if (chartPath && fs.existsSync(chartPath)) {
    const chart = JSON.parse(fs.readFileSync(chartPath, "utf8"));
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

  const sections = Array.isArray(doc.sections) ? doc.sections : [];
  const titles = new Set(sections.map(s => s.title));
  for (const r of REQUIRED) if (!titles.has(r)) report(r, null, "必备段落缺席");
  let traits = 0, sourced = 0;
  for (const sec of sections) {
    const seen = new Set();
    for (const [i, t] of (sec.traits || []).entries()) {
      traits++;
      const label = `${sec.title}#${i + 1}`;
      const text = (t.text || "").trim();
      if (!text) { report(sec.title, label, "text 为空"); continue; }
      if (seen.has(text)) report(sec.title, label, "段内重复");
      seen.add(text);
      const src = Array.isArray(t.sources) ? t.sources : [];
      if (!src.length) { report(sec.title, label, "没有溯源编号"); continue; }
      let ok = true;
      for (const id of src) {
        if (!ids.has(id)) { report(sec.title, label, `溯源编号在命盘里找不到：${id}`); ok = false; }
      }
      if (ok) sourced++;
    }
  }
  if (!summaryOnly) for (const p of problems) console.log(JSON.stringify(p));
  console.log(JSON.stringify({ summary: true, file, sections: sections.length, traits, sourced, problems: problems.length, featureIds: ids.size }));
  process.exit(problems.length ? 1 : 0);
}

main();
