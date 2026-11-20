"""Business entry evidence is distinct from wrapper forwarding and final delivery."""
import copy
import shutil
import subprocess
import unittest
from generate_dependency_html import generate, normalize, InputError
from test_dependency_interactions import NODE_HARNESS, fixture


class AnalyticsEntryEvidenceTests(unittest.TestCase):
    def entry_fixture(self):
        graph=fixture()
        page='module_a/panels/Page.ets'
        wrapper='module_a/hidden/Other.ets'
        chain=[page+':20 · tracker.trackClick(click)', wrapper+':40 · businessTracker.sendEvent(event)']
        graph['nodes'][page]['observability']={'analytics':[
            {'line':20,'call':'tracker.trackClick(click)','analyticsKind':'report','entryRole':'business-entry',
             'eventKey':'tail_click','eventDescription':'尾窗点击','classificationEvidence':'业务关闭页面时触发',
             'reportingChain':chain}], 'logs':[]}
        graph['nodes'][wrapper]['observability']={'analytics':[
            {'line':40,'call':'businessTracker.sendEvent(event)','analyticsKind':'preparation',
             'preparationRole':'forwarding','eventDescription':'埋点封装内部转发',
             'classificationEvidence':'仅作为封装内部发送，不作为业务入口',
             'reportingChain':chain[1:], 'upstreamEntries':[chain[0]]}], 'logs':[]}
        return graph

    def test_trace_validation(self):
        graph=self.entry_fixture()
        original=copy.deepcopy(graph)
        normalize(graph)
        self.assertEqual(graph,original)
        for field in ('upstreamEntries','reportingChain'):
            for bad in ('Page.ets:20', [None], [2], None):
                broken=copy.deepcopy(graph)
                broken['nodes']['module_a/hidden/Other.ets']['observability']['analytics'][0][field]=bad
                with self.subTest(field=field,bad=bad),self.assertRaises(InputError):normalize(broken)

    @unittest.skipUnless(shutil.which('node'),'Node.js unavailable')
    def test_only_business_call_is_a_reporting_site(self):
        checks=r'''
(async()=>{
const obs=t=>all(els.observabilityButtons).find(e=>e.attrs['data-observability-type']===t);
assert(obs('analytics:report').textContent==='埋点上报(1)','one business entry, not every layer');
assert(obs('analytics:preparation').textContent==='埋点准备(1)','internal send classified preparation');
assert(raw.includes('上游入口：module_a/panels/Page.ets:20 · tracker.trackClick(click)'),'upstream business evidence retained');
assert(raw.includes('上报链路：module_a/hidden/Other.ets:40 · businessTracker.sendEvent(event)'),'downstream forwarding evidence retained');
for(const c of all(els.filterButtons).filter(e=>e.attrs['data-category']).map(e=>e.attrs['data-category']))global(c).onclick();
for(const t of all(els.resourceButtons).filter(e=>e.attrs['data-resource-type']).map(e=>e.attrs['data-resource-type']))resourceType(t).onclick();
obs('analytics:preparation').onclick();obs('logs').onclick();els.hideUnmatched.onclick();
assert(file('module_a/panels/Page.ets'),'business entry stays visible');
assert(!dir('module_a/hidden'),'wrapper subtree is excluded from reporting-only view');
assert(els.raw.textContent===raw,'classification filter leaves raw intact');
let copied='';context.navigator.clipboard={writeText:async value=>{copied=value}};await els.copy.onclick();assert(copied===raw,'copy retains both roles and evidence');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
        result=subprocess.run(['node','-e',NODE_HARNESS+checks],input=generate(self.entry_fixture(),True),text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
