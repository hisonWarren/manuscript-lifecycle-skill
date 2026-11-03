#!/usr/bin/env python3
"""Run a check with hash-bound receipts (standard library, no shell).

python audit_run.py --receipt run.json --input manuscript.md --input scripts \
  --output report.json -- python scripts/section_lint.py manuscript.md --json report.json

Paths are relative to the invocation cwd. Inputs may be directories; outputs are files.
Receipt records execution, not scientific validity. Exit: command's code; 2 setup error;
124 timeout; 125 inputs changed or declared output missing. Never use untrusted argv.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
from output_safety import output_path, write_fresh

# Windows 中文系统把输出接到管道时默认按 GBK 编码，统计里常见的 − ² ✓ 会让脚本在打印时崩溃；统一按 UTF-8 输出。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def snapshot(paths):
    found = {}
    for name in paths:
        p = Path(name).resolve(strict=True)
        items = sorted(p.rglob('*')) if p.is_dir() else [p]
        for item in items:
            if item.is_file() and '__pycache__' not in item.parts and item.suffix != '.pyc':
                found[str(item)] = digest(item)
    if not found:
        raise ValueError('Input set is empty')
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--receipt', required=True)
    ap.add_argument('--input', action='append', required=True)
    ap.add_argument('--output', action='append', default=[])
    ap.add_argument('--timeout', type=int, default=600)
    ap.add_argument('command', nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.command[1:] if a.command[:1] == ['--'] else a.command
    try:
        if not cmd or not 1 <= a.timeout <= 3600:
            raise ValueError('Command required; timeout must be 1..3600 seconds')
        inputs = snapshot(a.input)
        protected=[*a.input,*inputs]
        dest = output_path(a.receipt,protected)
        log = dest.with_suffix('.log.txt')
        outputs = [Path(p).resolve() for p in a.output]
        destinations=[dest,log,*outputs]
        for index,path in enumerate(destinations):
            output_path(path,[*protected,*destinations[:index],*destinations[index+1:]])
        dest.parent.mkdir(parents=True, exist_ok=True)
        stamp = lambda: datetime.now(timezone.utc).isoformat()
        result = {'schema_version': 1, 'cwd': str(Path.cwd()), 'command': cmd,
                  'started_at': stamp(), 'inputs': inputs, 'outputs': {},
                  'receipt_kind': 'execution_only', 'runner_sha256': digest(__file__)}
        try:
            run = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace',
                                 timeout=a.timeout, shell=False, env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
            code, stdout, stderr = run.returncode, run.stdout, run.stderr
        except subprocess.TimeoutExpired as err:
            code, stdout, stderr = 124, str(err.stdout or ''), str(err.stderr or '')
        result.update(finished_at=stamp(), command_exit=code)
        # Refuse paths created by the command rather than overwrite its files.
        output_path(dest,protected)
        output_path(log,protected)
        write_fresh(log,'STDOUT\n' + stdout + '\nSTDERR\n' + stderr)
        result['log'] = {'path': str(log), 'sha256': digest(log)}
        try:
            result['inputs_unchanged'] = snapshot(a.input) == inputs
        except (OSError, ValueError):
            result['inputs_unchanged'] = False
        for p in outputs:
            if p.is_file() and p.stat().st_size:
                result['outputs'][str(p)] = digest(p)
        result['declared_outputs_complete'] = len(result['outputs']) == len(outputs)
        result['exit_code'] = code if result['inputs_unchanged'] and result['declared_outputs_complete'] else 125
        write_fresh(dest,json.dumps(result, ensure_ascii=False, indent=2))
        print(json.dumps({'receipt': str(dest), 'exit_code': result['exit_code'],
                          'inputs': len(inputs), 'outputs': len(result['outputs'])}, ensure_ascii=False))
        return result['exit_code']
    except (OSError, ValueError, RuntimeError) as err:
        print('INPUT ERROR: ' + str(err))
        return 2


if __name__ == '__main__':
    sys.exit(main())
