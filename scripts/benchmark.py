r"""Reproducible local measurements; no network calls or timing assertions.

Run in a fresh process: .venv\Scripts\python.exe scripts/benchmark.py
"""

import argparse
import ctypes
import json
from pathlib import Path
import platform
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def memory_mib():
    """Process working set on Windows; peak RSS only on Unix (not Python heap)."""
    if sys.platform == 'win32':
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in (
                    'PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
                    'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
                    'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]

        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        psapi = ctypes.WinDLL('psapi', use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return {'working_set': round(counters.WorkingSetSize / 2**20, 2),
                'peak_working_set': round(counters.PeakWorkingSetSize / 2**20, 2)}
    try:
        import resource
        divisor = 2**20 if sys.platform == 'darwin' else 1024
        return {'peak_rss': round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / divisor, 2)}
    except ImportError:
        return {'unavailable': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error('--repeats must be positive')
    baseline = memory_mib()
    started = time.perf_counter()
    from app import app
    from algorithms import suggest_words
    startup = time.perf_counter() - started
    trie = app.extensions['dictionary'].trie
    report = {'python': platform.python_version(), 'platform': platform.system(),
              'processor': platform.processor(), 'word_count': trie.size,
              'cold_module_import_seconds': round(startup, 4),
              'baseline_memory_mib': baseline, 'loaded_memory_mib': memory_mib(),
              'repeats_per_query': args.repeats, 'queries': []}
    for query in ['aple', 'dictionry', 'accomodation', 'photosyntheis',
                  'zzzzzzzzzz', 'qzxvbnmlkjhgfdsa', 'abcdefghijklmno', 'x' * 50,
                  'pneumonoultramicroscopicsilicovolcanoconiosis']:
        durations = []
        for _ in range(args.repeats):
            started = time.perf_counter()
            results = suggest_words(query, trie)
            durations.append((time.perf_counter() - started) * 1000)
        report['queries'].append({'query': query, 'milliseconds': [round(t, 3) for t in durations],
                                  'median_ms': round(statistics.median(durations), 3),
                                  'results': results})
    report['final_memory_mib'] = memory_mib()
    output = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(output + '\n', encoding='utf-8')
    print(output)


if __name__ == '__main__':
    main()
