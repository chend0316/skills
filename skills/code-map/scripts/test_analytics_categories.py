"""Reporting and preparation remain distinct across filters, folding and raw export."""
import copy
import shutil
import subprocess
import unittest
from generate_dependency_html import generate, normalize, InputError
from test_dependency_interactions import NODE_HARNESS, fixture


def categorized_fixture():
    graph = fixture()
    graph['nodes']['module_a/hidden/Other.ets']['observability']['analytics'] = [
        {'line': 7, 'call': 'tracker.start(metric)', 'analyticsKind': 'preparation',
         'eventDescription': '记录指标开始时间', 'eventKey': 'must_not_display', 'event': 'metric'},
        {'line': 8, 'call': 'tracker.end(metric)', 'analyticsKind': 'report',
         'eventKey': 'duration', 'eventDescription': '计算并上报耗时'},
        {'line': 9, 'call': 'sendEvent(name)', 'analyticsKind': 'report',
         'eventKey': '动态 key', 'eventDescription': '透传运行时事件名'},
        {'line': 10, 'call': 'unverified()'},
    ]
    return graph


class AnalyticsCategoryTests(unittest.TestCase):
    def test_schema_and_snapshot_nonmutation(self):
        graph = categorized_fixture()
        original = copy.deepcopy(graph)
        normalize(graph)
        self.assertEqual(graph, original)
        for bad in ('send', '', None, 1, []):
            invalid = copy.deepcopy(graph)
            invalid['nodes']['module_a/hidden/Other.ets']['observability']['analytics'][0]['analyticsKind'] = bad
            with self.subTest(bad=bad), self.assertRaises(InputError):
                normalize(invalid)
        graph['nodes']['module_a/hidden/Other.ets']['observability']['logs'][0]['analyticsKind'] = 'preparation'
        with self.assertRaises(InputError):
            normalize(graph)

    @unittest.skipUnless(shutil.which('node'), 'Node.js unavailable')
    def test_independent_categories(self):
        checks = r'''
(async()=>{
const obs=t=>all(els.observabilityButtons).find(e=>e.attrs['data-observability-type']===t);
const source='module_a/hidden/Other.ets',folder='module_a/hidden';
const prep='埋点准备 · 记录指标开始时间 · '+source+':7 · tracker.start(metric)';
assert(!obs('analytics'),'no aggregate or parent analytics filter');
assert(obs('analytics:report').textContent==='埋点上报(2)','dynamic key still reporting');
assert(obs('analytics:preparation').textContent==='埋点准备(1)','preparation count');
assert(obs('analytics:unknown').textContent==='埋点待分类(3)','old point and legacy aggregate stay unclassified');
assert(labels().includes(prep),'preparation description has no key/metric tail');
assert(!raw.includes('must_not_display'),'preparation cannot masquerade as a report');
assert(raw.includes('埋点待分类 · '+source+':10'),'legacy points not defaulted to reporting');
assert(raw.includes('Other.ets [埋点上报 2] [埋点准备 1] [埋点待分类 1]'),'raw file counts separated');
counter(file(source),'observability:analytics:preparation').onclick();
assert(!labels().includes(prep),'local preparation toggle');
obs('analytics:report').onclick();
assert(!counter(file(source),'observability:analytics:report'),'global hides report controls');
assert(labels().some(t=>t.includes('unverified()')),'unknown unaffected');
assert(obs('analytics:preparation').attrs['aria-pressed']==='true','report toggle leaves preparation filter unchanged');
assert(obs('logs').attrs['aria-pressed']==='true','report toggle leaves logs unchanged');
assert(counter(file(source),'observability:analytics:preparation').attrs['aria-pressed']==='false','report toggle preserves local preparation preference');
obs('analytics:report').onclick();
toggle(folder);counter(dir(folder),'observability:analytics:preparation').onclick();
assert(labels().includes(prep),'collapsed directory preparation uses same label');
assert(counter(dir(folder),'observability:analytics:report').attrs['aria-pressed']==='false','folded reports initially hidden');
counter(dir(folder),'observability:analytics:report').onclick();
obs('analytics:preparation').onclick();assert(!labels().includes(prep),'subfilter applies to folded points');
obs('analytics:preparation').onclick();assert(labels().includes(prep),'restore folded preference');
toggle(folder);assert(!labels().includes(prep),'file preference remains hidden after unfold');
assert(els.raw.textContent===raw,'all filters preserve raw text');
let copied='';context.navigator.clipboard={writeText:async value=>{copied=value}};
await els.copy.onclick();assert(copied===raw&&copied.includes(prep),'copy retains complete classified data');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
        result = subprocess.run(['node', '-e', NODE_HARNESS + checks],
                                input=generate(categorized_fixture(), True), text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
