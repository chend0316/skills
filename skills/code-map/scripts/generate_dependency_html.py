#!/usr/bin/env python3
"""Render a dependency JSON snapshot as a self-contained, offline HTML map."""
import argparse
import json
import posixpath
from pathlib import Path


class InputError(ValueError):
    pass


def file_id(value):
    if not isinstance(value, str) or not value or '\\' in value:
        raise InputError(f'文件身份须为 POSIX 相对路径：{value!r}')
    if value.startswith('/') or posixpath.normpath(value) != value or '..' in value.split('/') or value == '.':
        raise InputError(f'文件身份须为规范化仓库相对路径：{value!r}')
    return value


def category_for(identity, node):
    """Fallback for older snapshots; explicit source analysis takes precedence."""
    if node.get('category'):
        return node['category']
    if node['kind'] == 'resource' or '/resources/' in identity:
        return '资源文件'
    if identity.startswith(('@kit.', '@ohos.', '@system.')):
        return '系统 API'
    if identity == '@ohos/hvigor-ohos-plugin':
        return '构建工具'
    if node['kind'] == 'package':
        return '外部包'
    if node['kind'] == 'file':
        if identity.endswith(('oh-package.json5', 'build-profile.json5', 'hvigorfile.ts')):
            return '构建配置'
        return '源码依赖'
    return '待解析引用'


def validate_observability(identity, kind, groups):
    if kind != 'file' or not isinstance(groups, dict) or groups.keys() - {'analytics', 'logs'}:
        raise InputError(f'节点 {identity} 的 observability 须为文件上的 analytics/logs 对象')
    for points in groups.values():
        if points is None:
            continue
        if not isinstance(points, list):
            raise InputError(f'节点 {identity} 的可观测性记录须为数组或 null')
        for point in points:
            if (not isinstance(point, dict) or type(point.get('line')) is not int or point['line'] < 1
                    or not isinstance(point.get('call'), str) or not point['call'].strip()
                    or any(not isinstance(point.get(key, ''), str) for key in
                           ('event', 'eventKey', 'eventDescription', 'eventEvidence', 'level', 'tag', 'message'))):
                raise InputError(f'节点 {identity} 的可观测性记录须包含正整数行号和调用表达式')


def normalize(data, include_resources=False):
    if not isinstance(data, dict):
        raise InputError('JSON 顶层必须是对象')
    for key in ('root', 'entry', 'nodes', 'edges'):
        if key not in data:
            raise InputError(f'缺少字段：{key}')
    if not isinstance(data['root'], str):
        raise InputError('root 必须是字符串')
    if not isinstance(data['nodes'], dict) or not isinstance(data['edges'], list):
        raise InputError('nodes 必须是对象，edges 必须是数组')
    if not isinstance(data.get('scope', {}), dict):
        raise InputError('scope 必须是对象')
    if not isinstance(data.get('title', ''), str):
        raise InputError('title 必须是字符串')
    nodes, dropped = {}, set()
    for identity, original in data['nodes'].items():
        if not isinstance(original, dict):
            raise InputError(f'节点必须是对象：{identity}')
        kind = original.get('kind', 'file')
        if kind not in ('file', 'package', 'external', 'resource'):
            raise InputError(f'不支持的节点 kind：{identity}: {kind}')
        if kind == 'file':
            file_id(identity)
        if 'analyticsCallCount' in original:
            count = original['analyticsCallCount']
            if kind != 'file' or (count is not None and (type(count) is not int or not 0 <= count < 2**53)):
                raise InputError(f'节点 {identity} 的 analyticsCallCount 仅适用于文件，须为非负安全整数或 null')
        if 'observability' in original:
            validate_observability(identity, kind, original['observability'])
        is_resource = (kind == 'resource' or original.get('category') in ('资源文件', '系统资源')
                       or '/resources/' in identity
                       or identity.startswith(('resource:', 'app.string.', 'app.color.', 'app.media.')))
        if is_resource and not include_resources:
            dropped.add(identity)
            continue
        nodes[identity] = {**original, 'id': identity, 'kind': kind}
        nodes[identity]['category'] = category_for(identity, nodes[identity])
        for key in ('definitions', 'mapping'):
            if key in original and (not isinstance(original[key], list) or any(not isinstance(v, str) for v in original[key])):
                raise InputError(f'节点 {identity} 的 {key} 须为字符串数组')
    entry = file_id(data['entry'])
    if entry not in nodes or nodes[entry]['kind'] != 'file':
        raise InputError('entry 必须指向 nodes 中的文件节点')
    edges = []
    for index, original in enumerate(data['edges']):
        if not isinstance(original, dict):
            raise InputError(f'edges[{index}] 必须是对象')
        source, target = original.get('source'), original.get('target')
        if source not in data['nodes'] or target not in data['nodes']:
            raise InputError(f'edges[{index}] 引用了未定义节点：{source!r} → {target!r}')
        if source in dropped or target in dropped:
            continue
        if not include_resources and (original.get('resourceKey') or original.get('category') in ('资源文件', '系统资源')):
            continue
        if nodes[source]['kind'] != 'file':
            raise InputError(f'edges[{index}] 的 source 必须是文件')
        edge = {'type': 'import', 'status': '已解析', 'condition': '静态声明', **original}
        edge.setdefault('category', nodes[target]['category'])
        evidence = edge.get('evidence', '')
        if isinstance(evidence, dict):
            edge['snippet'] = edge.get('snippet', evidence.get('snippet', ''))
            edge['evidence'] = f"{evidence.get('file', source)}:{evidence.get('line', '?')}"
        elif isinstance(evidence, str):
            edge['evidence'] = evidence
        else:
            raise InputError(f'edges[{index}].evidence 须为字符串或对象')
        for key in ('type', 'status', 'condition', 'snippet', 'category'):
            edge.setdefault(key, '')
            if not isinstance(edge[key], str):
                raise InputError(f'edges[{index}].{key} 必须是字符串')
        for key in ('resourceKey', 'subtype'):
            if key in edge and not isinstance(edge[key], str):
                raise InputError(f'edges[{index}].{key} 必须是字符串')
        if 'mapping' in edge and (not isinstance(edge['mapping'], list) or any(not isinstance(v, str) for v in edge['mapping'])):
            raise InputError(f'edges[{index}].mapping 须为字符串数组')
        if 'cycle' in edge and not isinstance(edge['cycle'], bool):
            raise InputError(f'edges[{index}].cycle 须为布尔值')
        edge['id'] = f'edge:{index}'
        edges.append(edge)
    scanned = data.get('scope', {}).get('scannedFiles', data.get('scanned', []))
    if not isinstance(scanned, list) or any(not isinstance(x, str) for x in scanned):
        raise InputError('scope.scannedFiles 必须是文件身份数组')
    for identity in scanned:
        if identity not in data['nodes'] or data['nodes'][identity].get('kind', 'file') != 'file':
            raise InputError(f'扫描范围包含未定义文件：{identity}')
    scanned = [identity for identity in scanned if identity in nodes]
    scope = dict(data.get('scope', {'mode': 'entry-subgraph'}))
    if 'directory' in scope:
        if scope['directory'] != '.':
            file_id(scope['directory'])
        if 'members' not in scope or not isinstance(scope['members'], list):
            raise InputError('整目录模式须提供 scope.members 文件身份数组')
        members = []
        for identity in scope['members']:
            file_id(identity)
            if identity not in data['nodes'] or data['nodes'][identity].get('kind', 'file') != 'file':
                raise InputError(f'目录成员须指向已定义文件：{identity}')
            directory = scope['directory']
            if directory != '.' and identity.split('/')[:len(directory.split('/'))] != directory.split('/'):
                raise InputError(f'成员不在分析目录内：{identity}')
            if identity in nodes and identity not in members:
                members.append(identity)
        scope['members'] = sorted(members)
    for node in nodes.values():
        if not isinstance(node['category'], str):
            raise InputError('节点 category 须为字符串')
    return {**data, 'entry': entry, 'nodes': nodes, 'edges': edges, 'scanned': scanned,
            'scope': scope,
            'title': data.get('title', posixpath.basename(entry)), 'includeResources': include_resources}


def generate(data, include_resources=False):
    graph = normalize(data, include_resources)
    assets = Path(__file__).resolve().parent.parent / 'assets'
    template = (assets / 'dependency-map.html').read_text()
    script = (assets / 'dependency-map.js').read_text()
    # A replacement callback avoids interpreting escapes in user data.
    payload = json.dumps(graph, ensure_ascii=False).replace('<', r'\u003c')
    return template.replace('RENDERER_SCRIPT_PLACEHOLDER', script).replace('GRAPH_DATA_PLACEHOLDER', payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='依赖 JSON；格式见 references/html-generation.md')
    parser.add_argument('-o', '--output', required=True, type=Path)
    parser.add_argument('--include-resources', action='store_true', help='保留源码地图的资源使用点')
    args = parser.parse_args()
    try:
        html = generate(json.loads(args.input.read_text()), args.include_resources)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(html)
    except (OSError, ValueError, TypeError) as error:
        parser.exit(2, f'生成失败：{error}\n')
    print(args.output.resolve())


if __name__ == '__main__':
    main()
