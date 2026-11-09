# skills

用于代码分析与可视化的 Agent Skills，支持通过 `npx skills` 安装到 Codex、Claude Code 等 Agent。

## 技能

| 名称 | 功能 |
| --- | --- |
| [code-map](skills/code-map/SKILL.md) | 生成运行地图、目录结构图和源码地图，梳理源码依赖、资源使用点，以及埋点和日志。按需生成独立交互 HTML。 |

## 安装

安装工具当前要求 Node.js 22.20 或更高版本。使用 Python 生成源码地图 HTML 时需要 Python 3；运行技能自带的交互逻辑测试还需要 Node.js。

```bash
# 查看仓库中的技能
npx skills add chend0316/skills --list

# 安装 code-map 到当前项目，供 Codex 和 Claude Code 使用
npx skills add chend0316/skills --skill code-map -a codex -a claude-code

# 安装到用户目录，跨项目使用
npx skills add chend0316/skills --skill code-map -a codex -a claude-code -g
```

安装后可以直接描述任务，例如：

- 使用 code-map，梳理这个按钮从点击到结果展示的运行地图。
- 使用 code-map，分析这个目录的源码依赖、文案、图片和图标使用点，以及埋点和日志，生成交互式 HTML。

源码地图由 Agent 核查源码并整理快照。内置 Python 脚本读取快照 JSON 并生成 HTML。

## 更新

```bash
npx skills check
npx skills update code-map
```

新版本通过本仓库提交发布。用户更新后获取安装源中的最新技能内容。

## 本地开发

每个技能放在 `skills/<name>/`，入口文件为 `SKILL.md`，相关脚本、参考文档和模板随该技能保存。

```bash
python3 -m unittest discover -s skills/code-map/scripts -v
```

测试覆盖快照校验、HTML 生成，以及文件、目录和全局筛选的交互逻辑。Node.js 不可用时，相关交互测试会跳过。

安装工具的用法见 [skills CLI 文档](https://github.com/vercel-labs/skills)。
