"""Analytics labels retain resolved keys, explanations, and unknown-state markers."""
import copy
import json
import shutil
import subprocess
import unittest

from generate_dependency_html import InputError, generate, normalize
from test_dependency_interactions import NODE_HARNESS, fixture


class AnalyticsDescriptionTests(unittest.TestCase):
    def test_metadata_validation_and_nonmutation(self):
        graph = fixture()
        point = graph['nodes']['module_a/hidden/Other.ets']['observability']['analytics'][0]
        point.update(eventKey='start', eventDescription='开始录音', eventEvidence='Events.ets:12')
        original = copy.deepcopy(graph)
        self.assertEqual(normalize(graph)['nodes']['module_a/hidden/Other.ets']['observability']['analytics'][0], point)
        self.assertEqual(graph, original)
        for key in ('eventKey', 'eventDescription', 'eventEvidence'):
            for value in (None, 12, {}):
                invalid = copy.deepcopy(graph)
                invalid['nodes']['module_a/hidden/Other.ets']['observability']['analytics'][0][key] = value
                with self.subTest(key=key, value=value), self.assertRaises(InputError):
                    normalize(invalid)

    @unittest.skipUnless(shutil.which('node'), 'Node.js unavailable')
    def test_labels_across_views_filters_and_copy(self):
        for enriched in (True, False):
            graph = fixture()
            point = graph['nodes']['module_a/hidden/Other.ets']['observability']['analytics'][0]
            if enriched:
                point.update(eventKey='start', eventDescription='开始录音', eventEvidence='Events.ets:12')
            expected = ('埋点 · start · 开始录音' if enriched
                        else '埋点 · key 待解析 · 中文解释待确认')
            checks = r'''
const expected = EXPECTED;
assert(raw.includes(expected + ' · module_a/hidden/Other.ets:7 · track(Start) · Start'), 'raw label order');
assert(labels().some(t=>t.startsWith(expected)), 'expanded file label');
assert(expected.includes('key 待解析') || raw.includes('说明来源：Events.ets:12'), 'definition evidence retained');
assert(labels().some(t=>t==='日志 · module_a/hidden/Other.ets:8 · logger.info(Start) · INFO'), 'log unchanged');
toggle('module_a/hidden');
counter(dir('module_a/hidden'),'observability:analytics').onclick();
assert(labels().some(t=>t.startsWith(expected)), 'collapsed directory label');
const analytics=()=>all(els.observabilityButtons).find(e=>e.attrs['data-observability-type']==='analytics');
analytics().onclick();assert(!labels().some(t=>t.startsWith(expected)), 'global analytics filter');
analytics().onclick();assert(labels().some(t=>t.startsWith(expected)), 'restore selection');
assert(els.raw.textContent===raw, 'raw unaffected');
els.rawBtn.onclick();assert(els.raw.style.display==='block', 'raw view');
(async()=>{
 let copied='';context.navigator.clipboard={writeText:async t=>{copied=t}};
 await els.copy.onclick();assert(copied===raw&&copied.includes(expected), 'copy contains label');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
            checks = checks.replace('EXPECTED', json.dumps(expected, ensure_ascii=False))
            with self.subTest(enriched=enriched):
                result = subprocess.run(['node', '-e', NODE_HARNESS + checks],
                                        input=generate(graph, True), text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
