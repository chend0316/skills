"""Offline checks: never contact a device or change an application."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import collect_memory as c

MEM = '''Pss Shared Shared Private Private Swap SwapPss Heap Heap Heap
Total Clean Dirty Clean Dirty Total Total Size Alloc Free
ark ts heap 100 0 0 100 0 1 2 0 0 0
native heap 200 0 0 200 0 2 3 300 200 100
Total 300 0 0 300 0 3 5 300 200 100
'''


class MemoryTests(unittest.TestCase):
    def test_columns_and_missing_fields(self):
        parsed = c.parse_memory(MEM)
        self.assertEqual((parsed['pss_kb'], parsed['swappss_kb']), (300, 5))
        self.assertEqual(parsed['arkts_pss_kb'], 100)
        no_ark = '\n'.join(line for line in MEM.splitlines() if not line.startswith('ark ts heap'))
        self.assertIsNone(c.parse_memory(no_ark)['arkts_pss_kb'])
        for bad in [MEM.replace('SwapPss', 'Unknown'), 'No such process', MEM.replace('Total 300', 'Total -1')]:
            with self.assertRaises(ValueError):
                c.parse_memory(bad)

    def test_ambiguous_process_is_not_silently_selected(self):
        listing = c.processes('PID ARGS\n10 app.example\n11 app.example:render\n12 app.example\n')
        with self.assertRaises(ValueError):
            c.choose_main(listing, 'app.example')
        self.assertEqual(c.choose_main(listing, 'app.example', 10), 10)
        with self.assertRaises(ValueError):
            c.choose_main(listing, 'app.example', 11)

    def run_fixture(self, root, listing_calls):
        args = argparse.Namespace(out=str(root / 'result'), device='fixture', bundle='app.example',
                                  main_pid=None, interval=.01, duration=.03, include_related=True,
                                  hdc='not-executed', command_timeout=1)
        calls = iter(listing_calls)
        previous = listing_calls[-1]
        def fake_hdc(args, *command):
            if command[1] == 'ps':
                return next(calls, previous), ''
            self.assertEqual(command[:3], ('shell', 'hidumper', '--mem'))
            return MEM, ''
        with patch.object(c, 'run_hdc', side_effect=fake_hdc), contextlib.redirect_stdout(io.StringIO()):
            code = c.collect(args)
        out = Path(args.out)
        samples = [json.loads(line) for line in (out / 'samples.jsonl').read_text().splitlines()]
        return code, out, samples

    def test_collect_preserves_raw_and_excludes_same_name_fork(self):
        with tempfile.TemporaryDirectory() as tmp:
            initial = '10 app.example\n11 app.example:render\n'
            later = initial + '12 app.example\n'
            code, out, samples = self.run_fixture(Path(tmp), [initial, later])
            self.assertEqual(code, 0)
            self.assertTrue(samples)
            self.assertEqual(samples[0]['same_name_auxiliary_pids_excluded'], [12])
            self.assertEqual([p['pid'] for p in samples[0]['processes']], [10, 11])
            for proc in samples[0]['processes']:
                self.assertEqual((out / proc['raw_path']).read_text(), MEM)

    def test_restart_ends_batch_instead_of_adopting_new_pid(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, samples = self.run_fixture(Path(tmp), ['10 app.example\n', '20 app.example\n'])
            self.assertEqual(code, 2)
            self.assertEqual(len(samples), 1)
            self.assertFalse(samples[0]['processes'])
            self.assertEqual(json.loads((out / 'manifest.json').read_text())['main_pid'], 10)
            self.assertIn('main_process_missing', (out / 'events.jsonl').read_text())


if __name__ == '__main__':
    unittest.main()
