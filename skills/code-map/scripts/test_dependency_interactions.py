"""Observable interaction checks for entry and whole-directory snapshots."""
import copy
import re
import shutil
import subprocess
import unittest

from generate_dependency_html import generate, normalize, InputError


def fixture(directory=True):
    files = ['module_a/panels/Page.ets', 'module_a/panels/Menu.ets',
             'module_a/common/Text.ets', 'module_a/hidden/Other.ets',
             'module_b/Button.ets', 'module_a2/Peer.ets']
    resource = 'module_a/src/main/resources/base/element/string.json'
    nodes = {f: {'kind': 'file'} for f in files}
    nodes[files[0]]['analyticsCallCount'] = 2
    nodes[files[3]]['analyticsCallCount'] = 0
    nodes[files[3]]['observability'] = {
        'analytics': [{'line': 7, 'call': 'track(Start)', 'event': 'Start'}],
        'logs': [{'line': 8, 'call': 'logger.info(Start)', 'level': 'INFO'}],
    }
    nodes[resource] = {'kind': 'file', 'category': '资源文件'}
    nodes.update({'@kit.ArkUI': {'kind': 'package'}, '@sdk/ui': {'kind': 'package'},
                  'resource:missing': {'kind': 'resource', 'category': '资源文件'}})
    pairs = [(files[0], files[1]), (files[0], files[2]), (files[1], files[2]),
             (files[1], files[0]), (files[2], files[4]), (files[3], files[5]),
             (files[0], '@kit.ArkUI'), (files[0], '@sdk/ui'),
             (files[0], resource), (files[1], resource), (files[0], 'resource:missing')]
    scope = {'mode': 'entry-subgraph', 'scannedFiles': files[:4] + [resource]}
    if directory:
        scope.update({'mode': 'directory', 'directory': 'module_a', 'members': files[:4] + [resource]})
    graph = {'root': '/repo', 'entry': files[0], 'nodes': nodes, 'scope': scope,
             'edges': [{'source': a, 'target': b} for a, b in pairs]}
    for edge in graph['edges']:
        if edge['target'] == files[2]:
            edge['category'] = '内部源码' if edge['source'] == files[0] else '外部源码'
        if edge['target'] in (resource, 'resource:missing'):
            edge.update({'category': '资源文件', 'resourceKey': 'app.string.Title', 'subtype': '文案', 'type': 'resource-reference'})
            edge['evidence'] = {'file': edge['source'], 'line': 12}
        if edge['target'] == 'resource:missing':
            edge.update({'status': '待解析：动态资源名称', 'subtype': '图标', 'resourceKey': 'app.media.Dynamic'})
        if {edge['source'], edge['target']} == set(files[:2]): edge['cycle'] = True
    return graph


NODE_HARNESS = r'''
const fs=require('fs'),vm=require('vm'),html=fs.readFileSync(0,'utf8');
class Element {
 constructor(){this.children=[];this.style={};this.attrs={};this.textContent=''}
 append(...x){this.children.push(...x)} replaceChildren(...x){this.children=x}
 setAttribute(k,v){this.attrs[k]=String(v)} getAttribute(k){return this.attrs[k]}
 select(){this.selected=true} remove(){this.removed=true}
}
const els={},document={getElementById:id=>els[id]??=new Element(),createElement:()=>new Element(),body:new Element(),execCommand:()=>true};
els.data=new Element();els.data.textContent=html.match(/<script id="data" type="application\/json">([\s\S]*?)<\/script>/)[1];
const context=vm.createContext({document,navigator:{},console});
vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],context);
const graph=JSON.parse(els.data.textContent),all=e=>[e,...e.children.flatMap(all)];
const assert=(v,msg)=>{if(!v)throw Error(msg)};
const tree=()=>all(els.tree),labels=()=>tree().map(e=>e.textContent);
const dir=id=>tree().find(e=>e.attrs['data-directory']===id);
const file=id=>tree().find(e=>e.attrs['data-file']===id);
const li=row=>tree().find(e=>e.children.includes(row));
const toggle=id=>dir(id).children.find(e=>e.className==='toggle').onclick();
const counter=(row,c)=>row.children.find(e=>e.attrs['data-category']===c);
const global=c=>all(els.filterButtons).find(e=>e.attrs['data-category']===c);
const externalRefs=id=>all(li(dir(id))).filter(e=>e.className==='badge'&&e.textContent.includes(' · 外部依赖 ·'));
const resourceType=t=>all(els.resourceButtons).find(e=>e.attrs['data-resource-type']===t);
const raw=els.raw.textContent;
'''

ENTRY_CHECK = r'''
assert(labels().includes('./Menu.ets'),'sibling path stays one node');
assert(labels().includes('../common/Text.ets'),'cross-directory path stays one node');
assert(labels().some(x=>x.includes('循环引用')),'cycle visible and terminates');
assert(!raw.includes('app.string.Title'),'resources excluded by default');
for(const e of tree())if(e.attrs['aria-expanded']!==undefined)assert(tree().some(r=>r.attrs['data-directory']!==undefined&&r.children.includes(e)),'only directories may fold');
toggle('module_a/panels');assert(!labels().includes('Page.ets'),'fold hides internal files');
const c=counter(dir('module_a/panels'),'源码依赖');assert(c.textContent==='源码依赖(1)','deduplicated count');c.onclick();
const targets=tree().filter(e=>e.textContent==='../common/Text.ets');assert(targets.length===1,'external target deduplicated');targets[0].onclick();
assert(all(els.info).some(e=>e.textContent.includes('Page.ets')&&e.textContent.includes('Menu.ets')),'all sources retained');
toggle('module_a');counter(dir('module_a'),'源码依赖').onclick();
assert(labels().includes('../module_b/Button.ets'),'outside target preserved');
assert(labels().includes('../module_a2/Peer.ets'),'unreachable source included; membership uses path segments');
assert(!labels().includes('./common/Text.ets'),'parent hides internal target');
assert(els.raw.textContent===raw,'raw invariant');
'''

DIRECTORY_CHECK = r'''
(async()=>{
const page='module_a/panels/Page.ets';
assert(file(page).children.some(e=>e.textContent==='埋点调用 2'),'directory file analytics badge');
assert(raw.includes('Other.ets [埋点调用 1] [日志点 1]'),'detailed counts override legacy counts');
assert(raw.includes('Other.ets:8 · logger.info(Start)'),'raw includes log location and call');
const observation = type => all(els.observabilityButtons).find(e=>e.attrs['data-observability-type']===type);
assert(observation('logs').textContent==='日志(1)'&&observation('analytics').textContent==='埋点(1)','built-in observability counts');
const other = 'module_a/hidden/Other.ets';
const logKey = 'observability:logs';
assert(counter(file(other),logKey).textContent==='日志(1)','file log control');
counter(file(other),logKey).onclick();
observation('logs').onclick();
assert(!counter(file(other),logKey),'global filter hides file log control');
observation('logs').onclick();
assert(counter(file(other),logKey).attrs['aria-pressed']==='false','global restore preserves file selection');
counter(file(other),logKey).onclick();
toggle('module_a/hidden');
assert(counter(dir('module_a/hidden'),logKey).attrs['aria-pressed']==='false','folded log control starts off');
counter(dir('module_a/hidden'),logKey).onclick();
assert(labels().some(text=>text.includes('logger.info(Start)')),'folded directory shows its source log sites');
observation('logs').onclick();
assert(!counter(dir('module_a/hidden'),logKey),'global filter hides folded log control');
observation('logs').onclick();
assert(counter(dir('module_a/hidden'),logKey).attrs['aria-pressed']==='true','global restore preserves folded selection');
toggle('module_a/hidden');
observation('logs').onclick();
assert(!labels().some(text=>text.includes('logger.info(Start)')),'log filter hides log sites');
assert(labels().some(text=>text.includes('track(Start)')),'log filter leaves analytics sites visible');
assert(els.raw.textContent===raw,'observability filters preserve raw');
observation('logs').onclick();
assert(labels().includes('Other.ets')&&raw.includes('Other.ets'),'entry-unreachable directory member retained');
assert(raw.includes('app.string.Title')&&raw.includes('待解析'),'resolved and unresolved resources retained');
assert(raw.includes('@ module_a/panels/Page.ets:12'),'raw resource use retains source location');
assert(global('源码依赖').textContent==='源码依赖(5)','source types merged by distinct target');
assert(!global('内部源码')&&!global('外部源码')&&!global('资源文件')&&!global('系统资源'),'legacy and resource types absent from dependency filters');
assert(resourceType('文案').textContent==='文案(2)','resource count uses sites sharing one target');
assert(resourceType('图标').textContent==='图标(1)','unresolved icon counted');
resourceType('文案').onclick();
assert(!labels().some(x=>x.includes('app.string.Title')),'resource type hides text use sites');
assert(labels().some(x=>x.includes('app.media.Dynamic')),'icon type unaffected');
resourceType('文案').onclick();
assert(labels().includes('resources/'),'real resource directory included');
assert(counter(file(page),'系统 API').textContent==='系统API(1)','file category counts');
assert(!file(page).children.some(e=>e.attrs['aria-expanded']!==undefined),'file cannot fold');
counter(file(page),'文案').onclick();assert(counter(file(page),'文案').attrs['aria-pressed']==='false','file category hidden');
assert(counter(file('module_a/panels/Menu.ets'),'文案').attrs['aria-pressed']==='true','other file unchanged');
resourceType('文案').onclick();
assert(!counter(file(page),'文案'),'globally hidden resource control omitted');
assert(counter(file(page),'图标'),'other resource subtype control remains');
resourceType('文案').onclick();
global('系统 API').onclick();
assert(!counter(file(page),'系统 API'),'globally hidden dependency control omitted');
global('系统 API').onclick();
assert(counter(file(page),'文案').attrs['aria-pressed']==='false','restore preserves file choice');counter(file(page),'文案').onclick();
toggle('module_a/panels');assert(!file(page),'folder folded');
assert(counter(dir('module_a/panels'),'文案').textContent==='文案(1)','text targets deduplicated');
assert(!counter(dir('module_a/panels'),'构建工具'),'zero categories omitted');
assert(!counter(dir('module_a/panels'),'资源文件'),'broad resource control omitted');
counter(dir('module_a/panels'),'文案').onclick();
counter(dir('module_a/panels'),'图标').onclick();
assert(externalRefs('module_a/panels').length===2,'only resources shown');
resourceType('文案').onclick();
assert(!counter(dir('module_a/panels'),'文案'),'globally hidden folded control omitted');
assert(externalRefs('module_a/panels').length===1,'resource filter applies to folded references');
resourceType('文案').onclick();
counter(dir('module_a/panels'),'系统 API').onclick();assert(externalRefs('module_a/panels').length===3,'independent category shown');
resourceType('文案').onclick();resourceType('图标').onclick();
assert(externalRefs('module_a/panels').length===1,'resource filters folded references');
resourceType('文案').onclick();resourceType('图标').onclick();
assert(externalRefs('module_a/panels').length===3,'restore directory choice');
toggle('module_a');counter(dir('module_a'),'图标').onclick();
assert(externalRefs('module_a').length===1,'parent hides own resource file but preserves unresolved candidate');
toggle('module_a');assert(externalRefs('module_a/panels').length===3,'nested state preserved');
toggle('module_a/panels');assert(file(page),'reopen restores files');assert(els.raw.textContent===raw,'raw remains complete');
els.rawBtn.onclick();assert(els.raw.style.display==='block'&&els.dep.attrs['aria-pressed']==='false','raw view');
els.dep.onclick();assert(els.tree.style.display==='block'&&els.rawBtn.attrs['aria-pressed']==='false','graph view');
let copied='';context.navigator.clipboard={writeText:async value=>{copied=value}};
await els.copy.onclick();assert(copied===raw,'complete copy');delete context.navigator.clipboard;
await els.copy.onclick();assert(els.notice.textContent==='已复制','clipboard fallback');
})().catch(e=>{console.error(e);process.exitCode=1});
'''


class InteractionTests(unittest.TestCase):
    def test_directory_validation_and_resource_filter(self):
        graph = fixture(); original = copy.deepcopy(graph)
        normalized = normalize(graph)
        self.assertFalse(any('/resources/' in p for p in normalized['scope']['members']))
        self.assertFalse(any(e.get('resourceKey') for e in normalized['edges']))
        self.assertEqual(graph, original)
        for members in (['module_a2/Peer.ets'], None, ['missing.ets']):
            invalid = fixture(); invalid['scope']['members'] = members
            with self.assertRaises(InputError): normalize(invalid)

    @unittest.skipUnless(shutil.which('node'), 'Node.js unavailable')
    def test_directory_and_entry_interactions(self):
        for directory, checks in ((False, ENTRY_CHECK), (True, DIRECTORY_CHECK)):
            with self.subTest(directory=directory):
                result = subprocess.run(['node', '-e', NODE_HARNESS + checks], input=generate(fixture(directory), directory),
                                        text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
