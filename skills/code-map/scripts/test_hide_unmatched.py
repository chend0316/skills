"""Pruning uses global content matches and preserves ancestors, state and raw exports."""
import shutil
import subprocess
import unittest
from generate_dependency_html import generate
from test_dependency_interactions import NODE_HARNESS, fixture


class HideUnmatchedTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js unavailable')
    def test_recursive_pruning_and_global_filter_changes(self):
        graph = fixture()
        zero = 'module_a/empty/deep/Zero.ets'
        graph['nodes'][zero] = {'kind': 'file', 'observability': {'analytics': [], 'logs': []}}
        graph['scope']['members'].append(zero)
        graph['scope']['scannedFiles'].append(zero)
        graph['nodes']['module_a/panels/Menu.ets']['observability'] = {'analytics': [
            {'line': 3, 'call': 'startTimer()', 'analyticsKind': 'preparation', 'eventDescription': '记录开始时间'}], 'logs': []}
        checks = r'''
(async()=>{
const obs=t=>all(els.observabilityButtons).find(e=>e.attrs['data-observability-type']===t);
const report='module_a/hidden/Other.ets', prep='module_a/panels/Menu.ets';
assert(file('module_a/empty/deep/Zero.ets'),'default tree remains complete');
assert(els.hideUnmatched.attrs['aria-pressed']==='false','default switch off');
// Retain only the reporting global filter.
for(const key of all(els.filterButtons).filter(e=>e.attrs['data-category']).map(e=>e.attrs['data-category']))global(key).onclick();
for(const type of all(els.resourceButtons).filter(e=>e.attrs['data-resource-type']).map(e=>e.attrs['data-resource-type']))resourceType(type).onclick();
obs('logs').onclick();obs('analytics:preparation').onclick();obs('analytics:unknown').onclick();
els.hideUnmatched.onclick();
assert(els.hideUnmatched.attrs['aria-pressed']==='true','switch enabled');
assert(file(report)&&dir('module_a')&&dir('module_a/hidden'),'matching file and ancestors remain');
assert(!file(prep)&&!dir('module_a/panels'),'zero-match siblings recursively removed');
assert(!dir('module_a/empty')&&!dir('module_a/empty/deep'),'consecutive empty directories removed');
assert(!labels().includes('../common/Text.ets'),'disabled references stay hidden');
counter(file(report),'observability:analytics:report').onclick();
assert(file(report),'local display toggle cannot remove matching file');
toggle('module_a/hidden');assert(dir('module_a/hidden'),'folding does not remove matching directory');
obs('analytics:report').onclick();assert(!dir('module_a'),'all-zero root hidden');
assert(labels().includes('没有匹配当前全局筛选的节点。'),'explicit empty state');
obs('analytics:preparation').onclick();assert(file(prep)&&dir('module_a/panels'),'global change restores newly matching branch');
assert(!dir('module_a/hidden'),'nonmatching old branch remains hidden');
obs('analytics:report').onclick();assert(dir('module_a/hidden'),'multiple selected categories use union');
assert(!file(report),'restored branch retains folded state');
toggle('module_a/hidden');assert(file(report),'matching file restored after reopen');
assert(counter(file(report),'observability:analytics:report').attrs['aria-pressed']==='false','local preference preserved');
obs('analytics:report').onclick();obs('analytics:preparation').onclick();global('源码依赖').onclick();
assert(file('module_a/panels/Page.ets'),'dependency sources match selected outgoing references');
assert(labels().includes('../common/Text.ets'),'matching target retained as evidence regardless of its own sites');
assert(!dir('module_a/empty'),'empty directories still excluded');
els.hideUnmatched.onclick();assert(file('module_a/empty/deep/Zero.ets'),'switch off restores full tree');
assert(els.raw.textContent===raw,'raw invariant');
let copied='';context.navigator.clipboard={writeText:async t=>{copied=t}};await els.copy.onclick();assert(copied===raw,'copy invariant');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
        result = subprocess.run(['node', '-e', NODE_HARNESS + checks], input=generate(graph, True),
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
