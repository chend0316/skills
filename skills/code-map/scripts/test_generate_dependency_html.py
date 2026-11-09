"""Regression checks for the reusable renderer; no browser or repository required."""
import copy
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from generate_dependency_html import generate, InputError, normalize


def fixture():
    files = ['module_a/panels/Page.ets', 'module_a/panels/Menu.ets',
             'module_a/common/Text.ets', 'module_a/hidden/Other.ets', 'module_b/Button.ets',
             'module_a2/Peer.ets']
    nodes = {f: {'kind': 'file'} for f in files}
    nodes[files[0]]['analyticsCallCount'] = 3
    nodes[files[1]]['analyticsCallCount'] = 0
    nodes[files[1]]['observability'] = {'logs': []}
    nodes[files[2]]['analyticsCallCount'] = None
    nodes.update({'@sdk/ui': {'kind': 'package'}, 'app.string.Title': {'kind': 'resource'}})
    pairs = [(files[0], files[1]), (files[0], files[2]), (files[1], files[2]),
             (files[1], files[0]), (files[2], files[4]), (files[3], files[5]),
             (files[0], '@sdk/ui'), (files[0], 'app.string.Title')]
    return {'root': '/repo', 'entry': files[0], 'nodes': nodes,
            'revision': 'fixture', 'scope': {'mode': 'directory', 'scannedFiles': files},
            'edges': [{'source': a, 'target': b, 'type': 'import', 'status': 'resolved',
                       'evidence': {'file': a, 'line': 1, 'snippet': '</script><script>throw 1</script>'}}
                      for a, b in pairs]}


# Shared behavior checks also exercise whole-directory mode and resource filters.
from test_dependency_interactions import InteractionTests, NODE_HARNESS, ENTRY_CHECK
NODE_CHECK = NODE_HARNESS + r'''
assert(file(graph.entry).children.some(e=>e.textContent==='埋点调用 3'),'entry analytics badge');
assert(raw.includes('Page.ets [埋点调用 3]'),'entry count in raw map');
assert(!raw.includes('[埋点调用 0]'),'legacy zero analytics label omitted');
assert(!raw.includes('[日志点 0]'),'empty log list label omitted');
assert(!labels().some(text=>text==='埋点调用 0'||text==='日志点 0'),'interactive zero labels omitted');
assert(raw.includes('[埋点调用待确认]'),'unknown count shown');
''' + ENTRY_CHECK


class GeneratorTests(unittest.TestCase):
    def test_resource_filter_and_nonmutation(self):
        graph = fixture()
        original = copy.deepcopy(graph)
        self.assertNotIn('app.string.Title', normalize(graph)['nodes'])
        self.assertIn('app.string.Title', normalize(graph, True)['nodes'])
        self.assertEqual(graph, original)

    def test_invalid_input(self):
        graph = fixture()
        graph['edges'][0]['target'] = 'missing.ets'
        with self.assertRaises(InputError):
            normalize(graph)
        graph = fixture()
        graph['nodes']['../escape.ets'] = {'kind': 'file'}
        with self.assertRaises(InputError):
            normalize(graph)

    def test_invalid_analytics_call_count(self):
        graph = fixture()
        for count in (-1, True, 1.5, '2', 2**53):
            with self.subTest(count=count), self.assertRaises(InputError):
                graph['nodes'][graph['entry']]['analyticsCallCount'] = count
                normalize(graph)
        graph['nodes'][graph['entry']]['analyticsCallCount'] = 0
        graph['nodes']['@sdk/ui']['analyticsCallCount'] = 1
        with self.assertRaises(InputError):
            normalize(graph)

    def test_safe_embed_and_controls(self):
        html = generate(fixture())
        self.assertNotIn('</script><script>throw', html)
        data = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S)[1])
        self.assertEqual(data['edges'][0]['snippet'], '</script><script>throw 1</script>')
        nav = re.search(r'<nav>(.*?)</nav>', html, re.S)[1]
        self.assertEqual(re.findall(r'<button[^>]*>(.*?)</button>', nav), ['原始地图', '复制原始地图', '源码地图'])

    @unittest.skipUnless(shutil.which('node'), 'Node.js unavailable; syntax/DOM logic checks skipped')
    def test_javascript_and_behavior(self):
        html = generate(fixture())
        script = re.search(r'<script>(.*?)</script>', html, re.S)[1]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'page.js'
            path.write_text(script)
            subprocess.run(['node', '--check', str(path)], check=True, capture_output=True, text=True)
        result = subprocess.run(['node', '-e', NODE_CHECK], input=html, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
