# 角色建造-八字法（bazi-writing）

用八字法给小说角色完整的人格和生平，轻松让小说角色像现实中的真人一样拥有一生。这是一个 Claude Code skill，还在更新中。

**目前状态**：给一个角色的生日或八字四柱，脚本排盘，模型据此写出人物档案：性格表里、童年事件、谎言与秘密、需要与想要、亲密关系模式、说话方式、年表与两难等。每条特质都带溯源编号，指向命盘上的具体事实；八字本身不进正文，读者本里不出现干支、十神、神煞这类术语，有检查器兜底。完整样例见 [examples/沈砚](examples/沈砚)。

**最终版本的样子**：一个作者侧的隐藏世界模拟器。除了现在已有的先给出八字再建造角色以外，作者还可以先说想要什么样的角色，skill 反推出合适的命盘；一群人放在一起时，会形成贴近现实的相互作用。各自的起落、彼此的关系（谁压着谁、谁成全谁）都从命盘算出来；到了某一年，让人物互相反应，一件事落到一个人身上，又牵动下一个人，推出事件链（群像推演），整理成大纲和细纲，再交给写作套装去分章、写正文。这些还没做，按 [DESIGN.md](DESIGN.md) 的里程碑推进。

**进阶玩法**（等反推和群像推演做出来）：

1. **提供创作灵感**：把你用八字法建造的人物放进喜欢的小说里，推算出 ta 与小说世界里的人和事如何相互反应。书里原有的人物，可以按性格反推出命盘。
2. **“赛博”游玩小说世界**：用自己的八字创造一个“平行世界的自己”，把 ta 放进小说世界里，达到“赛博游玩”的效果。

这是写作工具，仅作参考，不做命理咨询。

## 和 oh-story 搭配

正文交给写作套装，比如 [oh-story](https://github.com/zenstory-ai/oh-story-claudecode) 的 story-long-write；群像推演做出来之前，大纲和细纲也交给它。现在可以把人物档案的读者本当角色设定手动交给它，自动导出到 oh-story 项目目录的导出器还没做。本 skill 不依赖 oh-story，单独也能用。人物档案"字段在场、值可以待补充"的写法借自 oh-story。

## 安装

需要 Python 3 与 Node.js。脚本在 Python 3.14 上开发和测试；运行期只用标准库，外加 Windows 上 zoneinfo 需要的 tzdata。检查器是纯 Node 脚本，没有 npm 依赖。

```bash
git clone https://github.com/DRMCT/bazi-writing ~/.claude/skills/bazi-writing
cd ~/.claude/skills/bazi-writing
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
```

macOS 与 Linux 把 `.venv/Scripts/` 换成 `.venv/bin/`，下同。

装好后在 Claude Code 里说「用八字捏人」，或输入 `/bazi-writing`。用法见 [SKILL.md](SKILL.md)，设计见 [DESIGN.md](DESIGN.md)。

## 测试

```bash
.venv/Scripts/pip install -r requirements-dev.txt
.venv/Scripts/python -m pytest scripts
node scripts/check-character.js examples/沈砚/人物/沈砚.json
```

## 规则从哪来

排盘与查表全由脚本完成，模型只做解读。有古籍依据的表逐条对照古籍校核，一条规则一张卡，放在 [references/校核](references/校核)；机器表 `scripts/bazi_core/tables/` 的每条都带卡号。

| 表               | 校核依据                 |
| --------------- | -------------------- |
| 调候用神            | 《穷通宝鉴评注》，余春台辑，徐乐吾评注  |
| 神煞、刑冲合害、十二长生、纳音 | 《三命通会》，万民英撰，四库本      |
| 格局成败救应          | 《子平真诠评注》，沈孝瞻原著，徐乐吾评注 |

卡上注明所用版本与页码，可对原书核查。仓库不附古籍全文：校核用的校对本转录自今人整理本，标点校勘和注释属于整理者，不随本仓库发布。校核流水线（OCR、打标、抽卡）的脚本在 `scripts/`，要自备古籍扫描件，依赖见各脚本的文档串。

旺衰打分是自起草的确定性算法，没有古籍逐条依据，校准方法见 DESIGN 6.4。神煞叙事标签与去术语词表也是自起草。

## 第三方代码

- `scripts/bazi_core/vendor/`：节录自 [qianye-wuyu/yueyuan-bazi](https://github.com/qianye-wuyu/yueyuan-bazi)，MIT，许可证见同目录的 `LICENSE.yueyuan-bazi`。
- 测试用 [tyme4py](https://github.com/6tail/tyme4py)（MIT）交叉校验四柱与大运。

## 致谢

 [@BingBingChangChang](https://github.com/BingBingChangChang) 提供灵感，我负责搭建、实现。

## 许可证

代码与自撰内容按 MIT 许可，见 [LICENSE](LICENSE)。卡片与测试夹具里引用的古籍原文和徐乐吾评注不属于本仓库的许可范围。
