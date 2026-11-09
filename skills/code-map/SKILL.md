---
name: code-map
description: Trace call chains with module-qualified calls, DI bindings, callbacks, and branches; show directory trees and source maps with compile dependencies and per-file analytics and logging sites for module extraction analysis, with interactive HTML on request. 适用于运行地图、目录结构图、源码地图，以及模块迁移和跨目录依赖排查。
---

# Code Map

从用户给出的入口、目录或迁移问题出发，输出可核查的运行地图、目录结构图或源码地图。默认只读；用户仅要求分析时不修改代码。

## 选择地图

- 运行地图（追踪调用、按钮行为、DI、回调和业务分支）：遵循下文的运行地图规则。
- 目录层级、文件分布和目录展开/收起：读取 [目录与源码地图](references/directory-and-build-dependencies.md)，输出目录结构图。
- 每个文件的埋点调用、文件或模块之间的编译依赖、折叠后的跨目录引用、模块能否迁走：读取同一参考，输出源码地图并核查依赖边界。

按用户需要选择或组合视图，不默认输出三张图。以下节点命名、箭头、无路径要求及分支格式仅适用于运行地图；目录与源码地图使用参考中的文件路径与树形格式。目录不自动等于构建模块，二者须区分。

## 输出方式

默认输出原始地图：使用 `text` 代码块，在声明的分析范围内完整展开，不添加 `[-]`、`[+]` 等展开状态标记，不为折叠交互裁剪节点。循环、重复引用及范围外终点仍按对应地图规则标注；原始地图不等于无边界递归。

只有用户明确要求“交互式”“可点击展开/收起”或“HTML 页面”等结果时，才读取 [交互式 HTML](references/interactive-html.md)，在同一份原始地图数据上生成可交互的 HTML 文件。源码地图网页优先使用 [生成脚本](scripts/generate_dependency_html.py)，将依赖 JSON 转成独立 HTML，输入格式见 [HTML 生成技巧](references/html-generation.md)。生成网页时，按该参考链接的 [HTML 生成技巧](references/html-generation.md) 实现数据与视图分离、路径渲染和验证。页面必须包含原始地图视图；交付 HTML 链接，不必在回复中重复整张文本地图，除非用户同时要求。用户只要求文本、目录图或源码地图时，不自动生成 HTML。

交互式运行地图须遵循上述参考中的折叠总结与源码链接规则：收起时在尾部显示下游功能总结，展开时隐藏总结；所有可核查节点支持文件和行号跳转，普通调用节点指向当前链路中的调用处。

目录结构图与源码地图遵循两种行语义：目录结构中每个文件夹单独一行；依赖引用中每个目标的完整相对路径单独一行，不拆成目录链。交互式源码地图仅文件夹可折叠，文件不可折叠；具体格式与页面选项见上述参考。

交互式源码地图按引用类别展示：目录单击只切换展开/折叠，折叠时显示可独立显隐的分类计数；文件始终展开，提供相同的分类筛选按钮。顶部通过“依赖类型”提供全局筛选，全局关闭的分类隐藏其引用和节点按钮，资源按钮按图标、文案等小类显示；原始地图和复制不受筛选影响。整目录请求必须声明并扫描全部成员，使用生成器的目录模式，不以入口可达子图冒充整个目录。

源码地图在声明的源码范围内同时梳理依赖与资源使用点。读取 [资源引用与分类](references/resources-and-categories.md)，逐处记录文案、图片、图标等的资源标识、源码位置、定义与未解析项。文本地图保留这些使用点；生成 HTML 时传入 `--include-resources`，在与“依赖类型”并列的“资源类型”中按使用点计数和筛选。仅修改网页交互时复用原 JSON；扩大范围或补扫资源时生成新的完整快照并记录版本。

源码地图的“可观测性”与“依赖类型”“资源类型”并列，内置“埋点”和“日志”。识别项目上报及日志 API 和封装，按源码调用位置记录明细和每文件数量。口径见 [可观测性使用点](references/directory-and-build-dependencies.md#可观测性使用点)。

## 运行地图输出格式

地图使用 `text` 代码块。每个代码节点格式为 `【构建模块】类型.方法`；包括入口、接口、实现和回调。模块名须依据源码路径及构建配置确认，不要用包名或目录分类代替。无法确认时标 `【模块待确认】`，并在地图外简短说明缺少的证据。

地图不写文件名、路径或行号。匿名回调写作 `类型.外层方法.{lambda}`；同一方法有多个时按源码出现顺序编号，如 `{lambda#2}`。

```text
【ui_core】Controller.click
  → 【service_api】IService.run
  ⇢ 【service_impl】ServiceImpl.run  [DI]
  → 【data_core】Repository.save
```

只使用以下边：

- `→` 表示源码中可见的直接调用，节点写调用表达式的静态类型。接口调用后若需要说明其运行时实现，再用 `⇢` 标出绑定；绑定是对前一调用接收者的解释，不是额外调用。
- `⇢` 表示依赖反转边：接口/抽象类型到其具体实现，或触发方法到外部传入、注册的回调体。实现绑定写 `[DI]`、`[factory]` 等；回调边直接指向回调体，不插入 listener 接口节点。回调说明应包含注册点，如 `[callback，注册于 Page.init]`。
- 异步、线程切换、事件总线、消息或 RPC 等机制写在对应边的行尾，如 `[callback，主线程 post]`、`[RPC]`。所有边说明均放在目标节点之后，行首方括号只用于分支条件。
- 若节点会导致用户可感知的 UI 变化，或表示链路中需要用户进行的屏幕交互，在该行末尾用 `@UI(具体行为)` 标注。界面变化示例：`@UI(打开录音页面)`、`@UI(显示错误提示)`；用户操作示例：`@UI(用户点击暂停按钮)`、`@UI(用户输入标题)`、`@UI(用户选择分享对象)`、`@UI(用户确认弹窗)`。只标注实际发生或链路明确要求的界面变化与用户操作，不把纯数据处理或不可感知的内部状态变化标成 UI。
- 行尾信息顺序固定为：目标节点、`[技术解释]`、`@UI(具体变化)`、零个或多个独立注释标记。没有技术解释时，UI 标注直接跟在节点之后。例：`→ 【recording_ui】RecordingPage.open  [callback，注册于 Controller.click] @UI(打开录音页面)`。
- 缺乏实现或回调的绑定证据时，不猜目标；标为 `⇢ ?`，并在地图外说明尚缺的证据。若存在多个实际目标，分别展开。

## 分支与顺序

条件分支挂在包含判断的方法节点下，按源码判断顺序列出互斥路径。标签用业务语言描述，并能对应源码中的判断、开关或提前返回。列出与用户问题相关的所有路径，包括默认分支和静默返回；无关路径可合并说明。

```text
【minutes_assembly】MinutesRecordingEntry.openInternal
    ├─ [已有新录音]
    │   → 【unified_recording_api】IUnifiedRecordingApi.openRecordingPage
    ├─ [新建，统一录音 FG 关闭]
    │   → 旧录音链路
    └─ [新建，统一录音 FG 开启]
        → 【minutes_assembly】MinutesRecordingEntry.startNewRecording
        → 【unified_recording_api】IUnifiedRecordingApi.startRecording
```

每个分支条件必须独占一行；条件行只写树形符号和 `[条件]`，不附调用节点。所有后继节点另起行，并使用 `→` 或 `⇢` 引出；禁止把节点写在条件行上。这样同层分支的模块名和类型名保持纵向对齐。分支层级使用 `├─` / `└─`；非末分支的续行用 `│` 对齐。嵌套判断按相同规则缩进。范围外终点可用简短中文描述，不加模块括号。分支条件不是顺序关系：同一方法中无条件依次执行的调用应画为线性子链路，并可用 `[依次]` 标明顺序。

## 追踪与核查

1. 明确入口、问题范围和终点；用符号引用与邻近源码定位实际调用，不凭命名或注释推断。
2. 核实每个直接调用、模块归属、接口实现绑定、回调注册与触发位置；识别多实现/多订阅者、条件、提前返回及异步边界。
3. 按实际控制流展开相关分支。不要把互斥路径画成一条线，也不要把注册回调与触发回调混作一次调用。
4. 输出一张完整地图。地图外仅补充理解地图所必需的范围说明或证据缺口；不要附加重复的简版地图。检查模块有依据、分支完整、边说明在行尾，且地图节点没有路径或行号。

```text
【ui_core】Controller.click
  → 【service_api】IService.run
  ⇢ 【service_impl】ServiceImpl.run  [DI]
      ├─ [未登录]
      │   → 【account_api】IAccountService.login
      ├─ [已登录，上传 FG 开启]
      │   → 【net_core】Uploader.upload
      │   ⇢ 【service_impl】ServiceImpl.run.{lambda}  [callback，注册于 ServiceImpl.run，主线程 post]
      │   → 【ui_core】Controller.showResult
      └─ [已登录，上传 FG 关闭]
          → 【data_core】Repository.save
```
