# skills

用于代码分析与可视化、鸿蒙真机内存诊断及工作说明的 Agent Skills，支持通过 `npx skills` 安装到 Codex、Claude Code 等 Agent。

## 技能

| 名称 | 功能 |
| --- | --- |
| [code-map](skills/code-map/SKILL.md) | 默认生成独立交互式 HTML 源码地图，梳理源码依赖、资源使用点，以及埋点和日志；也支持明确指定的运行地图、目录结构图和纯文本输出。 |
| [explain-work](skills/explain-work/SKILL.md) | 仅在用户明确指定时启用；解释工作、代码改动与技术决策，先说明具体改动、依据和验证结果，再按需展开实现细节。 |
| [harmony-memory-diagnostics](skills/harmony-memory-diagnostics/SKILL.md) | 自动编译运行用户指定的鸿蒙真机场景，逐个定位并修复内存泄漏，真机复测有效后每个问题单独提交 commit。 |

`code-map` 支持按依赖类型、资源类型及可观测性筛选；埋点上报、埋点准备和日志独立展示，也可开启“隐藏无匹配节点”。原始地图和复制内容保持完整。

## 安装

安装工具当前要求 Node.js 22.20 或更高版本，详见 [skills CLI 文档](https://github.com/vercel-labs/skills)。安装后的运行要求按技能区分：

| 技能 | 运行要求 |
| --- | --- |
| code-map | 使用内置 HTML 生成脚本需要 Python 3；本地交互测试需要 Node.js。生成的独立 HTML 可离线打开。 |
| explain-work | 纯说明型技能，无附带脚本或额外运行依赖。 |
| harmony-memory-diagnostics | Python 3、可用的 `hdc`、HarmonyOS 真机，以及目标项目所需的 SDK、构建和签名环境。内存采样脚本仅使用 Python 标准库。 |

```bash
# 查看仓库中的技能
npx skills add chend0316/skills --list

# 安装 code-map 到当前项目，供 Codex 和 Claude Code 使用
npx skills add chend0316/skills --skill code-map -a codex -a claude-code

# 安装到用户目录，跨项目使用
npx skills add chend0316/skills --skill code-map -a codex -a claude-code -g

# 安装工作说明或鸿蒙内存诊断技能
npx skills add chend0316/skills --skill explain-work -a codex -a claude-code
npx skills add chend0316/skills --skill harmony-memory-diagnostics -a codex -a claude-code
```

安装后可以直接描述任务，例如：

- 使用 code-map，梳理这个按钮从点击到结果展示的运行地图。
- 使用 code-map，梳理录音尾窗业务场景的代码地图。（默认交付交互式 HTML 源码地图）
- 使用 code-map，分析这个目录的源码依赖、文案、图片和图标使用点，以及埋点和日志。
- 使用 explain-work，解释这次改动解决了什么问题、为什么这样改，以及实际验证了哪些结果。
- 使用 harmony-memory-diagnostics，在指定鸿蒙真机上反复打开并退出目标页面 5 次，定位并修复内存泄漏，每个问题真机复测有效后单独提交。

源码地图由 Agent 核查源码并整理快照。内置 Python 脚本读取快照 JSON 并生成 HTML。

鸿蒙诊断需要明确应用和操作场景。完整调用默认包含构建、保留数据的覆盖安装、场景测试、修复和验证后的本地提交；可以明确要求只诊断、不提交，或每修复一个问题后停下。每个已验证修复交付独立报告、指标表和目标对象趋势图，最后对累计修复版本执行完整场景验收。采样脚本负责进程内存取证，不能单凭 PSS 上涨判断泄漏；具体流程见技能入口及其参考文档。

## 更新

```bash
npx skills check

# 更新指定技能
npx skills update code-map

# 更新所有已安装技能
npx skills update
```

技能提交并推送到 GitHub 默认分支后，即可通过 `npx skills` 分发安装，无需打 tag。只有用户明确要求时才创建 GitHub Release 页面。`skills update` 按安装源更新技能。

## 本地开发

每个技能放在 `skills/<name>/`，入口文件为 `SKILL.md`，相关脚本、参考文档和模板随该技能保存。

```text
skills/
├── code-map/                    # 源码地图、HTML 模板、生成器与测试
├── explain-work/                # 工作说明规则
└── harmony-memory-diagnostics/  # 真机诊断流程、采样脚本与测试
```

新增、重命名或调整技能能力时，同步更新上面的技能表、运行要求和使用示例。各技能内的文件引用使用相对路径。

在仓库根目录运行：

```bash
# 源码地图生成与交互检查
python3 -m unittest discover -s skills/code-map/scripts -v

# 鸿蒙采样解析与批次管理检查（离线，不连接设备）
python3 -m unittest discover -s skills/harmony-memory-diagnostics/scripts -v
```

源码地图测试覆盖快照校验、HTML 生成、埋点分类，以及文件、目录和全局筛选的交互逻辑。Node.js 不可用时，相关交互测试会跳过；修改 HTML 或 JavaScript 时需要安装 Node.js 并确认交互测试实际执行。

鸿蒙采样测试覆盖内存列解析、主进程选择、原始数据保存、同名辅助进程排除和主进程重启后的批次停止。离线测试通过不代表已完成真机诊断或修复验证。`explain-work` 无自动化测试，修改后核对说明与示例一致。
