#!/usr/bin/env python3
"""Read-only, fixed-main-PID HarmonyOS memory sampling; Python stdlib only."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
import time


EXPECTED_HEADER = ['Pss', 'Shared', 'Shared', 'Private', 'Private',
                   'Swap', 'SwapPss', 'Heap', 'Heap', 'Heap']
ROW = re.compile(r'^\s*(.*?)\s+(-?\d+(?:\s+-?\d+){9})\s*$')


def parse_memory(raw):
    """Fail closed if the column layout is unfamiliar; preserve missing fields."""
    headers = [line.split() for line in raw.splitlines() if 'Pss' in line and 'SwapPss' in line]
    if EXPECTED_HEADER not in headers:
        raise ValueError('Unsupported HiDumper header; inspect raw output before adapting parser')
    rows = {}
    for line in raw.splitlines():
        match = ROW.match(line)
        if match:
            rows.setdefault(match[1].strip(), [int(v) for v in match[2].split()])
    if 'Total' not in rows or any(v < 0 for values in rows.values() for v in values):
        raise ValueError('Missing Total row or invalid negative memory value')
    return {
        'rows': rows, 'pss_kb': rows['Total'][0], 'swappss_kb': rows['Total'][6],
        'arkts_pss_kb': rows.get('ark ts heap', [None])[0],
        'native_pss_kb': rows.get('native heap', [None])[0],
    }


def processes(raw):
    result = {}
    for line in raw.splitlines():
        fields = line.strip().split(None, 1)
        if len(fields) == 2 and fields[0].isdigit():
            result[int(fields[0])] = fields[1].strip()
    return result


def choose_main(listing, bundle, requested=None):
    matches = [pid for pid, name in listing.items() if name == bundle]
    if requested is not None:
        if requested not in matches:
            raise ValueError('Requested main PID is not running with the exact bundle ARGS')
        return requested
    if len(matches) != 1:
        raise ValueError('Expected one main process; inspect ps and specify --main-pid if ambiguous')
    return matches[0]


def run_hdc(args, *command):
    completed = subprocess.run([args.hdc, '-t', args.device, *map(str, command)],
                               capture_output=True, text=True, timeout=args.command_timeout)
    if completed.returncode:
        raise RuntimeError('HDC command failed: ' + completed.stderr.strip())
    return completed.stdout, completed.stderr


def stamp():
    return {'time': time.time(), 'iso_utc': datetime.now(timezone.utc).isoformat(),
            'monotonic': time.monotonic()}


def collect(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    (out / 'raw').mkdir()
    manifest = {**vars(args), 'started': stamp(), 'status': 'initializing',
                'units': 'kB as reported by HiDumper', 'scope': 'fixed main PID; related processes separate'}
    manifest_path = out / 'manifest.json'

    def save_manifest():
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')

    def event(name, **fields):
        with (out / 'events.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({**stamp(), 'event': name, **fields}, ensure_ascii=False) + '\n')

    save_manifest()
    status = 0
    try:
        raw, stderr = run_hdc(args, 'shell', 'ps', '-A', '-o', 'PID,ARGS')
        (out / 'raw' / 'initial-ps.txt').write_text(raw, encoding='utf-8')
        (out / 'raw' / 'initial-ps.stderr.txt').write_text(stderr, encoding='utf-8')
        pid = choose_main(processes(raw), args.bundle, args.main_pid)
        manifest.update(main_pid=pid, status='running')
        save_manifest()
        event('sampling_started', main_pid=pid)
        began = time.monotonic()
        deadline = began
        tick = 0
        with (out / 'samples.jsonl').open('w', encoding='utf-8', buffering=1) as stream:
            while time.monotonic() - began < args.duration and not (out / 'STOP').exists():
                tick += 1
                sample = {**stamp(), 'tick': tick, 'processes': []}
                stop = False
                try:
                    listing_raw, listing_err = run_hdc(args, 'shell', 'ps', '-A', '-o', 'PID,ARGS')
                    (out / 'raw' / f'{tick:06d}-ps.txt').write_text(listing_raw, encoding='utf-8')
                    if listing_err:
                        (out / 'raw' / f'{tick:06d}-ps.stderr.txt').write_text(listing_err, encoding='utf-8')
                    listing = processes(listing_raw)
                    if listing.get(pid) != args.bundle:
                        event('main_process_missing', expected_pid=pid,
                              candidates=[p for p, name in listing.items() if name == args.bundle])
                        raise ValueError('Main process ended or restarted; continuous batch stopped')
                    sample['same_name_auxiliary_pids_excluded'] = [
                        p for p, name in listing.items() if name == args.bundle and p != pid]
                    targets = [(pid, args.bundle)]
                    if args.include_related:
                        targets.extend((p, name) for p, name in listing.items()
                                       if name.startswith(args.bundle + ':'))
                    for target, name in targets:
                        proc = {**stamp(), 'pid': target, 'name': name,
                                'role': 'main' if target == pid else 'related'}
                        try:
                            text, stderr = run_hdc(args, 'shell', 'hidumper', '--mem', target)
                            path = out / 'raw' / f'{tick:06d}-{target}.txt'
                            path.write_text(text, encoding='utf-8')
                            proc['raw_path'] = str(path.relative_to(out))
                            if stderr:
                                (path.with_suffix('.stderr.txt')).write_text(stderr, encoding='utf-8')
                            proc.update(parse_memory(text))
                        except Exception as exc:
                            proc['error'] = str(exc)
                        proc['duration_seconds'] = time.monotonic() - proc['monotonic']
                        sample['processes'].append(proc)
                except ValueError as exc:
                    sample['error'] = str(exc)
                    status = 2
                    stop = True
                except Exception as exc:
                    sample['error'] = str(exc)
                    # A disconnected or unresponsive device cannot safely support the batch.
                    status = 2
                    stop = True
                sample['duration_seconds'] = time.monotonic() - sample['monotonic']
                sample['overrun'] = sample['duration_seconds'] > args.interval
                stream.write(json.dumps(sample, ensure_ascii=False) + '\n')
                main = next((p for p in sample['processes'] if p['role'] == 'main'), {})
                if main.get('error'):
                    event('main_sample_failed', tick=tick, error=main['error'])
                    status, stop = 2, True
                if stop:
                    break
                deadline += args.interval
                delay = min(deadline, began + args.duration) - time.monotonic()
                # Poll a local stop marker without busy-waiting for long intervals.
                until = time.monotonic() + max(0, delay)
                while time.monotonic() < until and not (out / 'STOP').exists():
                    time.sleep(min(0.2, max(0, until - time.monotonic())))
                if deadline < time.monotonic():
                    deadline = time.monotonic()
        manifest['status'] = 'stopped_on_error' if status else ('stopped_by_marker' if (out / 'STOP').exists() else 'duration_completed')
    except KeyboardInterrupt:
        manifest['status'], status = 'interrupted', 130
    except Exception as exc:
        event('sampling_failed', error=str(exc))
        manifest.update(status='failed', error=str(exc))
        status = 2
    finally:
        manifest['ended'] = stamp()
        save_manifest()
    print(json.dumps({'out': str(out), 'status': manifest['status']}, ensure_ascii=False))
    return status


def positive(value):
    number = float(value)
    if not 0 < number < float('inf'):
        raise argparse.ArgumentTypeError('Expected a finite positive number')
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', required=True)
    parser.add_argument('--bundle', required=True)
    parser.add_argument('--out', required=True, help='New, non-existing output directory')
    parser.add_argument('--duration', required=True, type=positive, help='Bounded duration in seconds')
    parser.add_argument('--interval', type=positive, default=2.0)
    parser.add_argument('--main-pid', type=int)
    parser.add_argument('--include-related', action='store_true')
    parser.add_argument('--hdc', default='hdc', help='HDC executable path')
    parser.add_argument('--command-timeout', type=positive, default=15.0)
    args = parser.parse_args()
    try:
        return collect(args)
    except FileExistsError:
        parser.error('Output directory already exists; choose a new directory')


if __name__ == '__main__':
    sys.exit(main())
