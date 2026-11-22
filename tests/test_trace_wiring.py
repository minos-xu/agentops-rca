"""Offline syntax/entrypoint guards; does NOT start the real API or claim runtime integration passed."""
import ast
from pathlib import Path
ROOT=Path(__file__).resolve().parent
if ROOT.name == 'tests':
    ROOT = ROOT.parent
for name in ['trace_callback.py','traced_runtime.py','trace_api.py','trace_report.py']:
    path = ROOT / name
    if not path.is_file() and name == 'trace_api.py':
        path = ROOT / 'tests/fixtures/trace_api.py'
    ast.parse(path.read_text(encoding='utf8'), filename=name)
    print(f'[PASS] {name} syntax')
src=(ROOT/'traced_runtime.py').read_text()
assert 'super()._config(session_id)' in src
assert 'super().ask(session_id, question)' in src
print('[PASS] Original runtime delegates remain in place')
print('ALL LESSON 62 INTEGRATION OFFLINE CHECKS PASSED')
