#!/usr/bin/env python3
"""Fail-closed delivery manifest checker. See references/13_quality_contract.md.
python release_check.py release.json --report release_report.json
Exit 0: evidence contract consistent; 1: incomplete/stale/blocked; 2: malformed input.
Does NOT certify scientific truth, human consent, source authenticity or visual quality.
"""
import argparse
import json
from pathlib import Path
import sys
from audit_run import digest
from output_safety import declared_paths, output_path, write_fresh

# Windows 中文系统把输出接到管道时默认按 GBK 编码，统计里常见的 − ² ✓ 会让脚本在打印时崩溃；统一按 UTF-8 输出。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

BASE = {'source_coverage', 'type_story', 'reporting', 'numbers', 'citations',
        'section_logic', 'language', 'regression'}
REQUIRED = {
    'draft': BASE | {'benchmark'},
    'revision': BASE | {'change_evidence'},
    'submission': BASE | {'benchmark', 'display', 'render', 'package', 'lit_coverage', 'display_semantics', 'expectations'},
    'response': BASE | {'response', 'change_evidence', 'display', 'render', 'package', 'display_semantics', 'expectations'},
    'review': {'source_coverage', 'numbers', 'citations', 'section_logic', 'reporting'},
    'skill_release': {'source_coverage', 'instruction_consistency', 'scripts', 'behavior', 'regression', 'package'},
}
WAIVABLE = {'benchmark', 'display', 'render', 'numbers', 'citations', 'display_semantics', 'expectations'}


def evaluate(data, base):
    issues = []
    def fail(s): issues.append(s)
    if data.get('schema_version') != 1 or data.get('stage') not in REQUIRED:
        raise ValueError('Unknown schema_version or stage')
    def file_ok(item, label):
        if not isinstance(item, dict) or not item.get('path') or not item.get('sha256'):
            fail(label + ': missing path/hash'); return None
        p = (base / item['path']).resolve()
        if not p.is_file() or not p.stat().st_size:
            fail(label + ': missing/empty file'); return None
        if digest(p) != item['sha256']:
            fail(label + ': stale hash'); return None
        return p
    artifacts = {}
    for art in data.get('artifacts', []):
        aid = art.get('id')
        if not aid or aid in artifacts:
            fail('Artifact IDs must be nonempty and unique'); continue
        artifacts[aid] = file_ok(art, 'Artifact ' + aid)
    if not artifacts:
        fail('No artifacts')
    targets = data.get('targets', [])
    if not targets or any(t not in artifacts for t in targets):
        fail('Targets must identify delivered content artifacts')
    checks = {}
    for check in data.get('checks', []):
        cid = check.get('id')
        if not cid or cid in checks:
            fail('Check IDs must be nonempty and unique'); continue
        checks[cid] = check
        status = check.get('status')
        if status not in {'pass', 'na'}:
            fail(str(cid) + ': unfinished or failed'); continue
        bindings = check.get('bindings', [])
        if not bindings or any(b not in artifacts for b in bindings) or not set(targets) <= set(bindings):
            fail(str(cid) + ': must bind all delivered targets and relevant sources')
        if status == 'na':
            if cid not in WAIVABLE or not check.get('reason') or not check.get('fallback'):
                fail(str(cid) + ': N/A not permitted or no reason/fallback')
        reviews = check.get('reviews', [])
        for r in reviews:
            p = file_ok(r, cid + ' review')
            if not r.get('reviewer') or r.get('kind') not in {'human', 'model', 'independent_implementation'}:
                fail(cid + ': review identity/type absent')
            if not r.get('locator') or not r.get('quote'):
                fail(cid + ': review needs exact excerpt and locator')
            elif p and r['quote'] not in p.read_text(encoding='utf-8-sig'):
                fail(cid + ': review excerpt absent')
        runs = check.get('runs', [])
        for entry in runs:
            p = file_ok(entry, cid + ' receipt')
            if p is None: continue
            receipt = json.loads(p.read_text(encoding='utf-8-sig'))
            if receipt.get('schema_version') != 1 or receipt.get('receipt_kind') != 'execution_only':
                fail(cid + ': invalid execution receipt'); continue
            if not receipt.get('command') or not receipt.get('started_at') or not receipt.get('finished_at'):
                fail(cid + ': incomplete execution receipt')
            if receipt.get('inputs_unchanged') is not True or receipt.get('declared_outputs_complete') is not True:
                fail(cid + ': run input mutation/output missing')
            rc = receipt.get('exit_code')
            if rc != 0:
                if rc != 1 or not entry.get('adjudication') or not reviews:
                    fail(cid + ': run did not pass (unadjudicated or execution error)')
            for category in ('inputs', 'outputs'):
                mapping = receipt.get(category)
                if not isinstance(mapping, dict) or (category == 'inputs' and not mapping):
                    fail(cid + ': missing recorded ' + category); continue
                for name, sha in mapping.items():
                    file_ok({'path': name, 'sha256': sha}, cid + ' ' + category)
            file_ok(receipt.get('log', {}), cid + ' log')
            input_paths = set(receipt.get('inputs', {}))
            if not all(artifacts.get(t) and str(artifacts[t]) in input_paths for t in targets):
                fail(cid + ': run did not read current delivered target(s)')
        if not reviews and not runs:
            fail(cid + ': no actual evidence')
        # These gates inherently contain semantic or behavioral judgments.
        if cid not in {'scripts'} and not reviews:
            fail(cid + ': semantic judgment not documented')
        if cid in {'scripts', 'regression'} and not runs:
            fail(cid + ': execution receipt required')
    for cid in sorted(REQUIRED[data['stage']] - checks.keys()):
        fail('Missing required check ' + cid)
    if 'findings' not in data or not isinstance(data['findings'], list):
        fail('Explicit findings list required')
    else:
        seen = set()
        for f in data['findings']:
            if not f.get('id') or f['id'] in seen: fail('Finding IDs missing/duplicate')
            seen.add(f.get('id'))
            if f.get('status') not in {'fixed', 'accepted', 'open'}:
                fail('Invalid finding disposition')
            if f.get('severity') not in {'critical', 'major', 'minor'}:
                fail('Invalid finding severity')
            if f.get('severity') in {'critical', 'major'} and f.get('status') != 'fixed':
                fail(str(f.get('id')) + ': unresolved blocking finding')
            if not f.get('rationale') or not f.get('evidence'):
                fail(str(f.get('id')) + ': no finding evidence/rationale')
    return {'status': 'contract_pass' if not issues else 'blocked', 'stage': data['stage'],
            'issues': issues, 'boundary': 'Evidence consistency only; not scientific or human approval.'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('manifest'); ap.add_argument('--report')
    a = ap.parse_args()
    try:
        p = Path(a.manifest).resolve()
        target = output_path(a.report,[p]) if a.report else None
        data = json.loads(p.read_text(encoding='utf-8-sig'))
        protected = [p,*declared_paths(data,p.parent)]
        if target:target=output_path(target,protected)
        # Receipts contain additional files consumed by evaluate; protect those
        # paths and logs even when they are absent from the top-level artifacts.
        if target and isinstance(data,dict):
            for check in data.get('checks',[]):
                if not isinstance(check,dict):continue
                for entry in check.get('runs',[]):
                    if not isinstance(entry,dict) or not isinstance(entry.get('path'),str):continue
                    receipt_path=(p.parent/entry['path']).resolve()
                    if receipt_path.is_file():
                        receipt=json.loads(receipt_path.read_text(encoding='utf-8-sig'))
                        protected.extend(declared_paths(receipt,p.parent))
            target=output_path(target,protected)
        result = evaluate(data, p.parent)
        code = 0 if result['status'] == 'contract_pass' else 1
        output = json.dumps(result, ensure_ascii=False, indent=2)
        if target:write_fresh(target,output)
    except (OSError, ValueError, KeyError, TypeError, AttributeError,RuntimeError) as err:
        print(json.dumps({'status':'input_error','issues':[str(err)]},ensure_ascii=False));return 2
    print(output)
    return code


if __name__ == '__main__':
    sys.exit(main())
