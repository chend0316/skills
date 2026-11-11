// Pure view of a source-verified snapshot. Rendering never changes graph edges.
const D = JSON.parse(document.getElementById('data').textContent);
const $ = id => document.getElementById(id);
const nodes = D.nodes, edges = D.edges;
const closed = new Set(), shownDirectoryCategories = new Map();
const hiddenFileCategories = new Map(), hiddenCategories = new Set();
const hiddenResourceTypes = new Set();
const hiddenObservability = new Set();
const observabilityTypes = [['analytics', '埋点'], ['logs', '日志']];
const observabilityCounts = new Map(observabilityTypes.map(([type]) => [
  type, Object.values(nodes).reduce((count, node) => count + (node.observability?.[type]?.length || 0), 0)
]));
const outgoing = new Map(), incoming = new Map();
for (const edge of edges) {
  if (!outgoing.has(edge.source)) outgoing.set(edge.source, []);
  if (!incoming.has(edge.target)) incoming.set(edge.target, []);
  outgoing.get(edge.source).push(edge); incoming.get(edge.target).push(edge);
}
const out = id => outgoing.get(id) || [];
const directoryMode = typeof D.scope.directory === 'string';
const ROOT = directoryMode ? (D.scope.directory === '.' ? '' : D.scope.directory) : D.entry.split('/').slice(0, -1).join('/');
const MEMBERS = directoryMode ? D.scope.members : [D.entry];
const memberSet = new Set(MEMBERS);
const categoryOrder = ['系统 API', '源码依赖', '外部包', '构建工具', '构建配置', '待解析引用'];
function inside(file, dir) {
  if (!dir) return true;
  const f = file.split('/'), d = dir.split('/');
  return d.every((part, i) => f[i] === part);
}
function relativeFrom(directory, target) {
  if (nodes[target].kind !== 'file') return target.replace(/^resource:/, '');
  const a = directory ? directory.split('/') : [], b = target.split('/');
  while (a.length && b.length && a[0] === b[0]) { a.shift(); b.shift(); }
  return (a.length ? '../'.repeat(a.length) : './') + b.join('/');
}
const relative = (source, target) => relativeFrom(source.split('/').slice(0, -1).join('/'), target);
function category(edge) {
  const name = edge.category || nodes[edge.target].category;
  return name === '内部源码' || name === '外部源码' ? '源码依赖' : name;
}
const resourceCategories = ['资源文件', '系统资源'];
function resourceType(edge) {
  const target = nodes[edge.target];
  if (edge.resourceKey || edge.type === 'resource-reference' || target.kind === 'resource' ||
      resourceCategories.includes(category(edge)) || resourceCategories.includes(target.category)) {
    return edge.subtype || '未分类资源';
  }
  return '';
}
const resourceAllowed = edge => !hiddenResourceTypes.has(resourceType(edge));
const resourceCounts = new Map();
for (const edge of edges) {
  const type = resourceType(edge);
  if (type) resourceCounts.set(type, (resourceCounts.get(type) || 0) + 1);
}
const categoryName = name => name.replace(/\s+/g, '');
const categoryAllowed = name => !hiddenCategories.has(name);
const globalEdgeAllowed = edge => resourceType(edge) ? resourceAllowed(edge) : categoryAllowed(category(edge));
function compareCategory(a, b) {
  const rank = name => categoryOrder.includes(name) ? categoryOrder.indexOf(name) : 99;
  return rank(a) - rank(b) || a.localeCompare(b, 'zh-CN');
}
const sortedCategories = groups => [...groups].filter(([, targets]) => targets.size).sort((a, b) => compareCategory(a[0], b[0]));
const treeCategory = edge => resourceType(edge) || category(edge);
function groupTargets(es, classify = category) {
  const groups = new Map();
  for (const edge of es) {
    const name = classify(edge);
    if (!groups.has(name)) groups.set(name, new Map());
    const targets = groups.get(name);
    if (!targets.has(edge.target)) targets.set(edge.target, []);
    targets.get(edge.target).push(edge);
  }
  return groups;
}
const allCategoryTargets = groupTargets(edges.filter(edge => !resourceType(edge)));
const allCategories = sortedCategories(allCategoryTargets).map(([name]) => name);
const externalCache = new Map(), fileCategoryCache = new Map();
function externalGroups(dir) {
  if (!externalCache.has(dir)) externalCache.set(dir, groupTargets(edges.filter(e =>
    inside(e.source, dir) && (nodes[e.target].kind !== 'file' || !inside(e.target, dir))), treeCategory));
  return externalCache.get(dir);
}
function fileGroups(id) {
  if (!fileCategoryCache.has(id)) fileCategoryCache.set(id, groupTargets(out(id), treeCategory));
  return fileCategoryCache.get(id);
}
const directoryCategoryVisible = (id, name) => shownDirectoryCategories.get(id)?.has(name) || false;
const fileCategoryVisible = (id, name) => !hiddenFileCategories.get(id)?.has(name);
const visibleFileEdges = id => out(id).filter(e => globalEdgeAllowed(e) && fileCategoryVisible(id, treeCategory(e)));
const statusLabel = edge => edge && !['resolved', '已解析'].includes(edge.status) ? ' [' + edge.status + ']' : '';
const classification = edge => category(edge) + (edge.subtype ? ' · ' + edge.subtype : '');
function referenceLabel(source, edge) {
  return relative(source, edge.target) + (edge.resourceKey ? ' {' + edge.resourceKey + '}' : '') + statusLabel(edge);
}
function rawReferenceLabel(source, edge) {
  const location = resourceType(edge) && edge.evidence ? ' @ ' + edge.evidence : '';
  return referenceLabel(source, edge) + location;
}
function boundary(edge) {
  if (edge.cycle) return '循环引用';
  if (nodes[edge.target].kind === 'package') return '包边界';
  return memberSet.has(edge.target) ? '目录内引用' : '目录外边界';
}
function evidence(id, es = []) {
  $('info').replaceChildren();
  const title = document.createElement('strong'), pre = document.createElement('pre');
  title.textContent = id;
  const refs = es.length ? es : [...(incoming.get(id) || []), ...out(id)];
  pre.textContent = refs.map(e => [classification(e), e.type + ' · ' + e.status,
    '来源 ' + e.source, '目标 ' + e.target, '证据 ' + e.evidence, e.snippet,
    '条件：' + e.condition, ...(e.resourceKey ? ['资源标识 ' + e.resourceKey] : []), ...(e.mapping || [])].join('\n')).join('\n\n') + '\n\n' +
    [...(nodes[id]?.definitions || []), ...(nodes[id]?.mapping || [])].join('\n');
  $('info').append(title, pre);
}
function button(text, label, action, className) {
  const b = document.createElement('button'); b.textContent = text;
  b.setAttribute('aria-label', label); b.className = className || ''; b.onclick = action; return b;
}
function localControl(parent, id, label, key, name, count, isFile, countBasis) {
  const enabled = isFile ? fileCategoryVisible(id, key) : directoryCategoryVisible(id, key);
  const control = button(name + '(' + count + ')', '切换分类：' + label + ' ' + name, () => {
    const map = isFile ? hiddenFileCategories : shownDirectoryCategories;
    if (!map.has(id)) map.set(id, new Set());
    const set = map.get(id); set.has(key) ? set.delete(key) : set.add(key); render();
  }, 'category-control ' + (enabled ? 'is-on' : 'is-off'));
  control.setAttribute('data-category', key);
  control.setAttribute('aria-pressed', enabled);
  control.setAttribute('title', countBasis + '；点击' + (enabled ? '隐藏' : '显示') + name);
  parent.append(control);
}
function categoryControls(parent, id, label, groups, isFile) {
  for (const [name, targets] of sortedCategories(groups)) {
    const count = [...targets.values()].filter(refs => refs.some(globalEdgeAllowed)).length;
    if (count) localControl(parent, id, label, name, categoryName(name), count, isFile, '按目标去重');
  }
}
function makeRow(parent) {
  const li = document.createElement('li'), row = document.createElement('div');
  row.className = 'row'; li.append(row); parent.append(li); return {li, row};
}
function badge(row, text) {
  if (!text) return;
  const span = document.createElement('span'); span.className = 'badge'; span.textContent = text; row.append(span);
}
function observabilityLabels(id, hidden = new Set()) {
  const node = nodes[id];
  return observabilityTypes.flatMap(([type, label]) => {
    if (hidden.has(type)) return [];
    const points = node.observability?.[type];
    const count = points === undefined && type === 'analytics' ? node.analyticsCallCount
      : points === null ? null : points?.length;
    return count === undefined || count === 0 ? [] : [label + (type === 'analytics' ? '调用' : '点') +
      (count === null ? '待确认' : ' ' + count)];
  });
}
function pointLines(id, hidden = new Set()) {
  return observabilityTypes.flatMap(([type, label]) => hidden.has(type) ? [] :
    (nodes[id].observability?.[type] || []).map(point => [
      label, ...(type === 'analytics' ? [point.eventKey || 'key 待解析', point.eventDescription || '中文解释待确认'] : []),
      id + ':' + point.line, point.call, point.event, point.level, point.tag, point.message,
      type === 'analytics' && point.eventEvidence ? '说明来源：' + point.eventEvidence : ''
    ].filter(Boolean).join(' · ')));
}
const observationKey = type => 'observability:' + type;
const observationFiles = Object.keys(nodes).filter(id => nodes[id].observability);
const observationDirectoryCache = new Map();
function directoryObservationFiles(dir) {
  if (!observationDirectoryCache.has(dir)) {
    observationDirectoryCache.set(dir, observationFiles.filter(id => inside(id, dir)));
  }
  return observationDirectoryCache.get(dir);
}
function localObservationPoints(row, id, label, files, isFile) {
  const hidden = new Set(hiddenObservability);
  for (const [type, name] of observabilityTypes) {
    if (hidden.has(type)) continue;
    const key = observationKey(type);
    const count = files.reduce((sum, file) => sum + (nodes[file].observability?.[type]?.length || 0), 0);
    if (count) localControl(row, id, label, key, name, count, isFile, '按源码使用点计数');
    if (!(isFile ? fileCategoryVisible(id, key) : directoryCategoryVisible(id, key))) hidden.add(type);
  }
  return files.flatMap(file => pointLines(file, hidden));
}
function appendObservationPoints(parent, points) {
  for (const text of points) {
    const point = document.createElement('li');
    point.className = 'muted'; point.textContent = text; parent.append(point);
  }
}
function rawFileLabel(id, label) {
  return label + observabilityLabels(id).map(text => ' [' + text + ']').join('');
}
function groupList(parent, name) {
  const li = document.createElement('li'), span = document.createElement('span'), ul = document.createElement('ul');
  span.className = 'category-heading'; span.textContent = name; li.append(span, ul); parent.append(li); return ul;
}
function visibleGroups(es) {
  const result = new Map();
  for (const edge of es) {
    const name = treeCategory(edge);
    if (!result.has(name)) result.set(name, []);
    result.get(name).push(edge);
  }
  return [...result].sort((a, b) => a[0].localeCompare(b[0], 'zh-CN'));
}
function fileView(parent, id, label, trail = [], es = [], expand = true) {
  const {li, row} = makeRow(parent), cycle = trail.includes(id);
  row.append(button(label, '查看引用证据：' + label, () => evidence(id, es), 'label'));
  const hiddenBadges = new Set(hiddenObservability);
  for (const [type] of observabilityTypes) {
    if (nodes[id].observability?.[type]?.length) hiddenBadges.add(type);
  }
  for (const text of observabilityLabels(id, hiddenBadges)) badge(row, text);
  const isSource = nodes[id].kind === 'file' && expand && !cycle;
  if (isSource) { row.setAttribute('data-file', id); categoryControls(row, id, label, fileGroups(id), true); }
  if (es.length) badge(row, classification(es[0]) + ' · ' + (cycle ? '循环引用' : boundary(es[0])));
  if (!isSource) return;
  const visible = visibleFileEdges(id);
  const points = localObservationPoints(row, id, label, [id], true);
  if (!visible.length && !points.length) return;
  const ul = document.createElement('ul'); li.append(ul);
  appendObservationPoints(ul, points);
  for (const [name, refs] of visibleGroups(visible)) {
    const group = groupList(ul, name);
    for (const edge of refs) fileView(group, edge.target, referenceLabel(id, edge), [...trail, id], [edge], !directoryMode);
  }
}
function directoryItems(dir) {
  const folders = new Set(), files = [];
  for (const id of MEMBERS) {
    if (!inside(id, dir)) continue;
    const rest = dir ? id.slice(dir.length + 1) : id, parts = rest.split('/');
    if (parts.length > 1) folders.add((dir ? dir + '/' : '') + parts[0]); else files.push(id);
  }
  return [...[...folders].sort().map(id => ({id, folder: true})), ...files.sort().map(id => ({id, folder: false}))];
}
function externalView(parent, dir) {
  const visible = [...externalGroups(dir)].flatMap(([name, targets]) =>
    directoryCategoryVisible(dir, name)
      ? [...targets.values()].flat().filter(globalEdgeAllowed) : []);
  const selected = sortedCategories(groupTargets(visible, treeCategory));
  if (!selected.length) return;
  const ul = document.createElement('ul'); parent.append(ul);
  for (const [name, targets] of selected) {
    const group = groupList(ul, categoryName(name));
    for (const [target, refs] of targets) {
      const {row} = makeRow(group), statuses = [...new Set(refs.map(statusLabel).filter(Boolean))].join('');
      row.append(button(relativeFrom(dir, target) + statuses, '查看引用证据：' + target, () => evidence(target, refs), 'label'));
      badge(row, name + ' · 外部依赖 · ' + refs.length + ' 条引用');
    }
  }
}
function directoryView(parent, dir, paint) {
  const {li, row} = makeRow(parent), folded = closed.has(dir), label = dir.split('/').pop() + '/';
  row.setAttribute('data-directory', dir);
  const toggle = () => { closed.has(dir) ? closed.delete(dir) : closed.add(dir); render(); };
  const arrow = button(folded ? '▸' : '▾', (folded ? '展开目录：' : '折叠目录：') + label, toggle, 'toggle');
  arrow.setAttribute('aria-expanded', !folded); row.append(arrow);
  const title = button(label, '切换目录状态：' + label, toggle, 'label'); title.setAttribute('aria-expanded', !folded); row.append(title);
  if (folded) {
    categoryControls(row, dir, label, externalGroups(dir), false);
    const points = localObservationPoints(row, dir, label, directoryObservationFiles(dir), false);
    if (points.length) {
      const ul = document.createElement('ul'); li.append(ul);
      appendObservationPoints(ul, points);
    }
    externalView(li, dir);
  } else {
    const ul = document.createElement('ul'); li.append(ul); paint(ul);
  }
}
function directoryContents(parent, dir) {
  for (const item of directoryItems(dir)) {
    if (item.folder) directoryView(parent, item.id, ul => directoryContents(ul, item.id));
    else fileView(parent, item.id, item.id.split('/').pop());
  }
}
function rootDirectories(parent, parts, i = 0) {
  if (!parts.length) { if (directoryMode) directoryContents(parent, ''); else fileView(parent, D.entry, D.entry); return; }
  const dir = parts.slice(0, i + 1).join('/');
  directoryView(parent, dir, ul => {
    if (i < parts.length - 1) rootDirectories(ul, parts, i + 1);
    else if (directoryMode) directoryContents(ul, dir);
    else fileView(ul, D.entry, D.entry.split('/').pop());
  });
}
function rawEntry(id, label, trail = []) {
  const cycle = trail.includes(id), lines = [rawFileLabel(id, label) + (cycle ? ' [循环引用]' : '')];
  if (cycle) return lines;
  out(id).forEach((edge, i, es) => {
    const last = i === es.length - 1;
    const child = rawEntry(edge.target, rawReferenceLabel(id, edge) + ' [' + classification(edge) + ' / ' + boundary(edge) + ']', [...trail, id]);
    lines.push((last ? '└── ' : '├── ') + child[0], ...child.slice(1).map(line => (last ? '    ' : '│   ') + line));
  }); return lines;
}
function rawDirectory(dir) {
  const result = [], items = directoryItems(dir);
  items.forEach((item, i) => {
    const last = i === items.length - 1;
    const name = item.id.split('/').pop();
    result.push((last ? '└── ' : '├── ') + (item.folder ? name + '/' : rawFileLabel(item.id, name)));
    const sub = item.folder ? rawDirectory(item.id) : out(item.id).map((edge, j, es) =>
      (j === es.length - 1 ? '└── ' : '├── ') + rawFileLabel(edge.target, rawReferenceLabel(item.id, edge)) + ' [' + classification(edge) + ' / ' + boundary(edge) + ']');
    result.push(...sub.map(line => (last ? '    ' : '│   ') + line));
  }); return result;
}
const rootParts = ROOT ? ROOT.split('/') : [];
const rawPrefix = rootParts.map((part, i) => (i ? '    '.repeat(i - 1) + '└── ' : '') + part + '/');
const rawBody = directoryMode ? rawDirectory(ROOT) : rawEntry(D.entry, D.entry.split('/').pop());
const RAW = [...rawPrefix, ...rawBody.map(line => '    '.repeat(Math.max(0, rootParts.length - 1)) + (!directoryMode && rootParts.length ? '└── ' : '') + line)].join('\n');
// Entry dependency continuations align with the entry file, not its parent folder.
const rawTree = !directoryMode && rootParts.length ? [...rawPrefix,
  '    '.repeat(rootParts.length - 1) + '└── ' + rawBody[0],
  ...rawBody.slice(1).map(line => '    '.repeat(rootParts.length) + line)].join('\n') : RAW;
const rawPoints = Object.keys(nodes).sort().flatMap(id => pointLines(id));
const RAW_TEXT = rawPoints.length ? [rawTree, '', '可观测性使用点', ...rawPoints].join('\n') : rawTree;
$('raw').textContent = RAW_TEXT;
function renderFilters() {
  $('filterButtons').replaceChildren();
  for (const name of allCategories) {
    const on = categoryAllowed(name);
    const b = button(categoryName(name) + '(' + allCategoryTargets.get(name).size + ')', '筛选依赖类型：' + categoryName(name), () => {
      hiddenCategories.has(name) ? hiddenCategories.delete(name) : hiddenCategories.add(name); render();
    }, 'global-filter ' + (on ? 'is-on' : 'is-off'));
    b.setAttribute('data-category', name); b.setAttribute('aria-pressed', on); $('filterButtons').append(b);
  }
}
function renderResourceFilters() {
  const controls = $('resourceButtons');
  controls.replaceChildren();
  for (const [type, count] of [...resourceCounts].sort(([a], [b]) => a.localeCompare(b, 'zh-CN'))) {
    const on = !hiddenResourceTypes.has(type);
    const control = button(type + '(' + count + ')', '筛选资源类型：' + type, () => {
      if (hiddenResourceTypes.has(type)) hiddenResourceTypes.delete(type);
      else hiddenResourceTypes.add(type);
      render();
    }, 'global-filter ' + (on ? 'is-on' : 'is-off'));
    control.setAttribute('data-resource-type', type);
    control.setAttribute('aria-pressed', on);
    controls.append(control);
  }
  if (!resourceCounts.size) {
    const message = document.createElement('span');
    message.className = 'muted';
    message.textContent = D.includeResources ? '快照中没有资源使用点' : '此快照未纳入资源';
    controls.append(message);
  }
}
function renderObservabilityFilters() {
  const controls = $('observabilityButtons');
  controls.replaceChildren();
  for (const [type, label] of observabilityTypes) {
    const on = !hiddenObservability.has(type);
    const control = button(label + '(' + observabilityCounts.get(type) + ')', '筛选可观测性：' + label, () => {
      if (hiddenObservability.has(type)) hiddenObservability.delete(type);
      else hiddenObservability.add(type);
      render();
    }, 'global-filter ' + (on ? 'is-on' : 'is-off'));
    control.setAttribute('data-observability-type', type);
    control.setAttribute('aria-pressed', on);
    controls.append(control);
  }
}
function render() {
  renderFilters(); renderResourceFilters(); renderObservabilityFilters(); $('tree').replaceChildren();
  const ul = document.createElement('ul'); $('tree').append(ul); rootDirectories(ul, rootParts);
}
$('rawBtn').onclick = () => {
  $('raw').style.display = 'block'; $('tree').style.display = 'none';
  $('rawBtn').setAttribute('aria-pressed', true); $('dep').setAttribute('aria-pressed', false);
  $('viewTitle').textContent = '原始地图'; $('hint').textContent = '完整原始地图，不受折叠、文件筛选或全局筛选影响。';
};
$('dep').onclick = () => {
  $('raw').style.display = 'none'; $('tree').style.display = 'block';
  $('rawBtn').setAttribute('aria-pressed', false); $('dep').setAttribute('aria-pressed', true);
  $('viewTitle').textContent = '源码地图'; $('hint').textContent = hint; render();
};
$('copy').onclick = async () => {
  try { await navigator.clipboard.writeText(RAW_TEXT); $('notice').textContent = '已复制'; }
  catch {
    const area = document.createElement('textarea'); area.value = RAW_TEXT; document.body.append(area); area.select();
    const ok = document.execCommand('copy'); area.remove(); $('notice').textContent = ok ? '已复制' : '请在原始地图中手动选择复制';
  }
};
const hint = '目录名称或箭头单击切换展开/折叠。展开时不显示右侧分类；折叠时显示非零分类计数，单独点击可高亮显示或置灰隐藏外部引用和目录内可观测性使用点。文件始终展开，分类按钮筛选自身直接引用和可观测性使用点。全局隐藏优先，恢复后保留各节点选择。每条引用路径相对于直接引用文件，折叠汇总路径相对于目录；引用计数按分类和目标去重，可观测性按使用点计数。' +
  (directoryMode ? '整目录模式逐一列出全部声明成员，目录内重复引用的完整依赖见目标自身条目。' : '当前为入口子图；目录汇总覆盖输入快照中的全部边，未声明扫描的文件不视为已分析。');
$('hint').textContent = hint; $('title').textContent = D.title; document.title = D.title + ' · 源码地图';
$('scope').textContent = '快照：' + (D.revision || D.branch || '未提供版本') + '；范围：' + (D.scope.mode || 'entry-subgraph') + '；明确扫描 ' + D.scanned.length + ' 个文件。';
$('coverage').textContent = D.scope.description || '未声明扫描完整性，不能据此推断整个目录无外部依赖。';
$('resources').textContent = D.includeResources ? '已纳入本快照声明的资源引用；定义、变体及待解析项见证据。' : '本次未纳入文案、图标、颜色等资源引用。';
$('root').textContent = '图根目录：' + D.root;
for (const text of [Object.values(nodes).filter(n => n.kind === 'file').length + ' 个文件节点', edges.length + ' 条依赖', '静态快照 · 未构建']) {
  const span = document.createElement('span'); span.className = 'tag'; span.textContent = text; $('stats').append(span);
}
render();
// Keep sticky evidence clear of a wrapping global-filter toolbar.
if (typeof ResizeObserver !== 'undefined') {
  const nav = document.querySelector('nav');
  new ResizeObserver(() => document.documentElement.style.setProperty('--controls-height', (nav.getBoundingClientRect().height + 16) + 'px')).observe(nav);
}
