# 独立 HTML 的生成实现

用于把已核查的地图数据生成交互网页。推荐用 Python 处理源码路径、分析数据和 HTML 模板，用原生 JavaScript 渲染；无需前端框架、构建服务或 CDN。此实现方式可替换，但地图语义遵循 [交互式 HTML](interactive-html.md)。

## 直接使用生成脚本

以下命令从本技能目录执行。

源码地图网页优先复用技能内的 [generate_dependency_html.py](../scripts/generate_dependency_html.py)，不要每次重新实现渲染器。脚本只读输入 JSON，不扫描仓库、不编译、不刷新分析快照；输出内嵌所有依赖数据、样式和脚本的单文件 HTML。仅需 Python 3 标准库。

```bash
python3 scripts/generate_dependency_html.py dependencies.json -o dependencies.html
```

输入示例（合法 JSON）：

```json
{
  "root": "/absolute/repository",
  "entry": "module_a/pages/Page.ets",
  "revision": "分析时的提交或快照标识",
  "scope": {
    "mode": "entry-subgraph",
    "description": "仅入口相关子图；包内部依赖未扫描",
    "scannedFiles": ["module_a/pages/Page.ets", "module_b/Button.ets"]
  },
  "nodes": {
    "module_a/pages/Page.ets": {"kind": "file"},
    "module_b/Button.ets": {"kind": "file"},
    "@sdk/ui": {"kind": "package"}
  },
  "edges": [
    {
      "source": "module_a/pages/Page.ets",
      "target": "module_b/Button.ets",
      "type": "import",
      "status": "resolved",
      "condition": "static",
      "evidence": {
        "file": "module_a/pages/Page.ets",
        "line": 1,
        "snippet": "import { Button } from '../../module_b/Button'"
      }
    },
    {
      "source": "module_a/pages/Page.ets",
      "target": "@sdk/ui",
      "type": "import",
      "status": "待解析：缺少包实现"
    }
  ]
}
```

必填字段为 `root`、`entry`、`nodes`、`edges`。生成器同时支持入口子图和整目录模式；不负责扫描或验证源码。`title`、`revision`、`scope` 可选，但生成前应尽量补齐版本和扫描范围；未提供完整性说明时网页明确标记证据缺口。`entry` 必须是文件节点。文件节点可包含 `observability`，其 `analytics`（埋点）和 `logs`（日志）各为使用点数组。已核实无调用用空数组，证据不足用 `null`，缺少字段表示快照未提供。每个使用点包含正整数 `line` 和字符串 `call`，可选字符串 `event`、`level`、`tag`、`message`。例如 `{"logs":[{"line":42,"call":"Logger.info(TAG, template)","level":"INFO","tag":"Recording","message":"开始录音"}]}`。顶部数量按已记录使用点统计。旧快照的 `analyticsCallCount` 仍可用于文件行展示；有 `analytics` 明细时优先用明细。

埋点记录另用字符串 `eventKey` 保存解析后的实际 key，`eventDescription` 保存中文解释，`eventEvidence` 保存定义/说明来源（文件和行号或文档位置）；`event` 保留原事件/指标表达式，不能用它冒充已解析 key。新扫描应补齐这些字段，解析口径见[可观测性使用点](directory-and-build-dependencies.md#可观测性使用点)。例如：

```json
{"line":125,"call":"mmPerfTracker.start(MmPerfMetric.SWITCH_FISHBONE_TO_WEBVIEW_LOAD)","event":"MmPerfMetric.SWITCH_FISHBONE_TO_WEBVIEW_LOAD","eventKey":"switch_fishbone_to_webview_load","eventDescription":"切到鱼骨图到 WebView 加载成功的耗时（仅首次加载）","eventEvidence":"framework/statistics/MmPerformanceTracker.ets:14"}
```

渲染顺序为 `埋点 · eventKey · eventDescription · 文件:行号 · call · event`，有 `eventEvidence` 时在末尾显示说明来源。旧快照缺少新字段仍能打开，但显示“key 待解析”“中文解释待确认”；生成器只展示输入，不自行翻译、读取源码或推测 key。补扫解释须从原快照对应版本核查，保存带来源的新快照，不能静默混入新版本源码。

- `file` 节点身份必须是规范化的仓库相对 POSIX 路径，不能包含 `..`；相对展示路径由脚本计算，不作为身份输入。
- `package`、`external` 节点用于包边界及未解析目标；所有边的端点必须存在，未解析目标也要建节点并保留 `status`，不能省略边。依赖源必须为文件节点。
- `category` 指定引用类别，优先采用边上的值，其次节点上的值；旧快照会按文件/包/SDK 名称提供保守回退，不替代源码核查。`subtype`、`resourceKey`、`mapping`（字符串数组）、`cycle` 可保存资源类型、原符号、定义/变体位置和环证据。
- `type`、`status`、`condition`、`evidence` 可省略；除 `resolved` / `已解析` 以外的状态会出现在地图中。证据可用上例对象，也兼容 `"file:line"` 字符串配合边级 `snippet`。
- `scope.scannedFiles` 记录明确扫描的文件，目录折叠汇总仍使用输入中的所有原始边，包括不在入口可达路径上的边。
- 默认过滤 `kind: resource`、`category: 资源文件/系统资源`、实际 `resources/` 文件，以及 `app.string.*`、`app.color.*`、`app.media.*` 等资源节点及关联边；目录成员、扫描计数和类别计数同步过滤。生成源码地图时传入 `--include-resources` 保留资源使用点。
- 旧快照的 `branch`、`scanned`、字符串证据仍兼容；不自动把未扫描的节点声称为已扫描文件。

整目录输入在上述结构中补充：

```json
{
  "scope": {
    "mode": "directory",
    "directory": "module_a",
    "members": ["module_a/pages/Page.ets", "module_a/common/Text.ets"],
    "scannedFiles": ["module_a/pages/Page.ets", "module_a/common/Text.ets"],
    "description": "完整扫描 module_a 源码；目录外源码及包停在边界"
  }
}
```

`scope.directory` 为仓库相对规范化目录，仓库根可用 `.`；`members` 是目录内真实文件列表，不是依赖边。所有成员须存在于 `nodes` 且属于该目录；未从入口可达的成员也会显示。`entry` 仍提供一个真实文件身份，目录模式不把其他成员挂成入口依赖。整个目录要完整扫描成员；排除测试、资源或生成物时在范围中说明。未提供目录字段的旧快照按入口模式兼容。

资源定义与分类证据格式见 [资源引用与分类](resources-and-categories.md)。生成包含资源使用点的源码地图：

```bash
python3 scripts/generate_dependency_html.py dependencies.json -o dependencies.html --include-resources
```

页面结构与样式位于 [assets/dependency-map.html](../assets/dependency-map.html)，通用交互在 [assets/dependency-map.js](../assets/dependency-map.js)。生成器内联两者成为独立 HTML，不依赖外部脚本、网络或具体仓库路径。修改脚本或模板后运行：

```bash
python3 scripts/test_generate_dependency_html.py
```

检查覆盖输入校验、资源过滤、内嵌转义、JS 语法、入口/整目录两种模式、未从入口可达的成员、路径、循环、分类计数、文件/目录独立筛选、全局优先级、状态恢复、去重、视图切换与复制回退。JS 检查需要 Node.js；没有 Node.js 时对应测试会明确跳过。它不代替真实浏览器验证或剪贴板权限验证。

## 数据先行，展示后置

分开保存分析快照、原始文本和折叠状态。可在 HTML 旁保存 JSON，方便后续仅修改展示，不必重新扫描正在变化的工作区。

```javascript
const graph = {
  root: '/absolute/repository',
  entry: 'module_a/Page1.ets',
  revision: '分析时的提交或快照标识',
  scope: { mode: 'entry-subgraph', scannedFiles: ['module_a/Page1.ets'] },
  nodes: {
    'module_a/Page1.ets': { kind: 'file', module: 'module_a' },
    'module_b/Button.ets': { kind: 'file', module: 'module_b' }
  },
  edges: [{
    source: 'module_a/Page1.ets', target: 'module_b/Button.ets',
    type: 'import', status: 'resolved', condition: 'static',
    evidence: { file: 'module_a/Page1.ets', line: 1, snippet: 'import …' }
  }]
};
const closedDirectories = new Set(); // 展示状态，不修改 graph
```

文件身份使用相对仓库根的规范化路径，包身份使用独立命名空间或节点类型。另建目录树存储包含关系；有向依赖边只放在 `edges`，不以目录树父子关系代替。展示实例用“父展示 ID + 边 ID”等稳定键，支持同一文件在不同依赖分支出现。

源码提取可用正则定位 import/export 候选，但须核查多行导入、转导出、包清单 main 字段与路径别名；需要处理更复杂语法时使用对应语言解析器。正则命中本身不能证明完整编译依赖。资源使用点与依赖边来自同一源码快照。

交互式运行地图按展示实例保存 `summary` 和源码定位（如 `source.file`、`source.line`、`source.kind`、`source.snippet`）。`source.kind` 区分调用处、入口定义、回调、绑定和条件；同一方法的不同调用节点不能共享单一声明位置。折叠状态独立保存，渲染时仅在节点有子项且已收起时显示 `summary`。源码名称使用链接元素，折叠使用独立按钮，二者事件互不触发。此数据约定不要求改变源码地图的输入格式。

## 安全地内嵌数据

推荐将 JSON 放入 `application/json` 脚本块，渲染代码独立存放。源码或 JSON 中的 `</script>` 即使位于 JSON 字符串内也可能提前关闭 HTML 标签，因此先转义 `<`：

```python
import json
payload = json.dumps(graph, ensure_ascii=False).replace('<', r'\u003c')
html = template.replace('GRAPH_DATA_PLACEHOLDER', payload)
```

```html
<script id="graph-data" type="application/json">GRAPH_DATA_PLACEHOLDER</script>
<script>
const graph = JSON.parse(document.getElementById('graph-data').textContent);
</script>
```

显示文件名、证据和源码片段时使用 `textContent`、`createElement` 和 `append`；不拼入 `innerHTML`。Python 内嵌 JavaScript 模板使用原始三引号字符串，或将 JS 单独读入，避免 JavaScript 的 `\n` 被 Python 提前转换为实际换行而破坏语法。最终仍需提取生成后的脚本运行 `node --check`。

## 两种行语义分别渲染

- 入口定位或目录包含：分割规范化目录路径，每个文件夹一行，只有目录提供折叠按钮。
- 文件依赖：计算 `relative(dirname(source), target)`，将完整结果作为一个文件标签。不能再对这条标签做 `/` 分割；这同样适用于 `./src/main/ets/Wave.ets` 和 `../../../record/Wave.ets`。
- 文件节点不创建折叠状态或 `aria-expanded`，右侧提供自身直接引用的分类按钮。分类筛选可隐藏该类引用，文件条目本身保留；全局筛选优先。目录折叠时整体隐藏其内部文件。整目录模式的重复目标作为证据终点，完整依赖在其自身成员条目展开。
- DFS 展开依赖时仅用当前祖先链检测循环；不要用一个全局 visited 集合丢弃其他分支对同一文件的引用。
- 原始地图也从同一份原始数据生成；先生成不受折叠影响的完整文本。切换原始视图或复制时读取该文本，不从当前 DOM 反推地图。

目录折叠从原始边按类别与目标身份汇总，不能从已渲染节点汇总，也不能从当前筛选后的边汇总。实际交互由共享生成器实现，无需在每次分析时重新拼接模板。路径成员关系按段比较，防止 `module_a2` 被误归入 `module_a`：

```javascript
function inside(file, directory) {
  const f = file.split('/'), d = directory.split('/');
  return d.every((part, i) => f[i] === part);
}
function externalEdges(graph, directory) {
  const targets = new Map();
  for (const edge of graph.edges) {
    if (!inside(edge.source, directory) || inside(edge.target, directory)) continue;
    if (!targets.has(edge.target)) targets.set(edge.target, []);
    targets.get(edge.target).push(edge); // 去重目标，保留每条来源证据
  }
  return targets;
}
```

实际实现中先依据节点 kind 判断文件或包，包节点作为目录外部目标处理，不将包名当成本地路径。此汇总只覆盖声明的分析范围；局部分析必须在页面标明。

## 页面交互与交付

源码地图页面保留“原始地图”“复制原始地图”“源码地图”，在顶部通过“依赖类型”提供全局筛选。采用单一当前视图状态驱动按钮选中状态、标题和内容，避免切换后状态不一致。文件名点击只显示证据；目录名称或箭头单击只切换展开/折叠，不使用三态循环或下拉框。展开目录不显示右侧文案；折叠目录与展开文件提供非零分类计数按钮，例如 `系统API(1) 图标(2)`，高亮/置灰控制独立显隐。全局关闭时隐藏对应的引用和节点按钮，并保留节点选择；原始图与复制保持完整。目录按钮支持键盘及 `aria-expanded`，分类按钮使用 `aria-pressed`。

复制优先使用 `navigator.clipboard.writeText(rawText)`；本地文件环境不可用时可尝试临时 textarea 复制，并如实显示结果，失败时允许用户手动选择文本。CSS 使用等宽路径字体、清晰的树形缩进和窄屏布局；无需为实现交互引入在线依赖。

仅修改网页样式或交互时，复用已保存的 JSON 快照，不重新读源码。需要刷新分析时生成新的完整快照，记录范围与版本；不能因源码已变化而手工补入旧依赖并伪装成当前证据。

## 验证技巧

1. 检查 JSON 所有边的端点存在，规范化身份一致；核对资源使用位置、定义或候选，以及资源类型按使用点计数。
2. 从最终 HTML 提取可执行 JS，运行 `node --check`；这能发现模板转义引起的语法错误。
3. 在纯逻辑或轻量 DOM 测试中验证：初始完整展开、依赖完整路径单行、只有目录有折叠控件、折叠后的分类按钮可独立显示外部目标、上级目录隐藏内部引用、文件分类可独立筛选、全局覆盖局部且恢复偏好、多来源去重保留证据、原始地图及复制不被过滤。
4. 浏览器可用时进一步验证实际布局、键盘折叠、三个选项切换与复制。逻辑测试或模拟 DOM 不能代替浏览器验证；若本地文件被浏览器策略拒绝，不绕过限制，明确说明验证范围。
