#!/usr/bin/env python3
"""Independently recompute declared row-level rates and identify missing event denominators.

The human supplies a JSON mapping of source columns to the scientific definitions.
This script never guesses whether the selected denominator reflects the estimand.
No network, third-party modules, or user-data upload. Exit 1 means a declared
reported number does not match the specified arithmetic; exit 2 input error.

python scripts/metric_audit.py --csv observations.csv --spec audit.json --out audit_result.json
"""
import argparse
import csv
import decimal
import hashlib
import json
import math
from pathlib import Path
import sys

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def as_number(raw, name, row):
    try:
        n = float(raw)
    except (ValueError, TypeError):
        raise ValueError(f'Row {row}, column {name}: nonnumeric or missing value {raw!r}')
    if not math.isfinite(n):
        raise ValueError(f'Row {row}, column {name}: value must be finite')
    return n


def default_tolerance(value):
    """Half a unit of the last reported decimal (0.070 -> 0.0005 after JSON drops the zero -> 0.005)."""
    try:
        exp = decimal.Decimal(repr(float(value))).normalize().as_tuple().exponent
    except (decimal.InvalidOperation, ValueError):
        return 1e-8
    return 0.5 * 10 ** exp + 1e-12 if exp < 0 else 0.5 + 1e-12


def audit(csv_path, spec_path):
    config = json.loads(spec_path.read_text(encoding='utf-8-sig'))
    if not isinstance(config, dict) or config.get('schema_version') != 1:
        raise ValueError('Expected schema_version 1 object')
    metrics = config.get('metrics')
    group_by = config.get('group_by')
    if not isinstance(group_by, str) or not group_by:
        raise ValueError('Missing group_by column')
    if not isinstance(metrics, list) or not metrics:
        raise ValueError('Missing metrics')
    with csv_path.open(encoding='utf-8-sig', newline='') as file:
        reader = csv.DictReader(file)
        fields = reader.fieldnames
        if not fields or len(fields) != len(set(fields)):
            raise ValueError('Missing or duplicate CSV header')
        if group_by not in fields:
            raise ValueError('No grouping column: ' + group_by)
        rows = list(reader)
    if not rows:
        raise ValueError('Empty CSV dataset')
    allowed = {'rate', 'mean', 'event_fraction', 'capped_mean'}
    seen = set()
    for m in metrics:
        if not isinstance(m, dict) or not isinstance(m.get('id'), str) or not m['id'] or m['id'] in seen:
            raise ValueError('Metric IDs must be distinct and nonempty')
        seen.add(m['id'])
        if m.get('kind') not in allowed:
            raise ValueError('Unknown metric kind for '+m['id'])
        kind=m['kind']
        cols = (['numerator','denominator'] if kind=='rate' else ['column'] if kind in ('mean','event_fraction') else ['column','event_column'])
        for k in cols:
            if m.get(k) not in fields:
                raise ValueError(f'{m["id"]}: missing source column {k} = {m.get(k)!r}')
        if kind=='rate' and m.get('aggregation') not in ('pooled','mean_row_ratios'):
            raise ValueError(m['id']+': select pooled or mean_row_ratios')
        if kind in ('event_fraction','capped_mean'):
            k = 'positive_values' if kind=='event_fraction' else 'event_values'
            if not isinstance(m.get(k), list) or not m[k] or any(not isinstance(v,str) for v in m[k]):
                raise ValueError(m['id']+': declare string list '+k)
        if kind=='capped_mean' and (isinstance(m.get('cap'), bool) or not isinstance(m.get('cap'), (int,float))):
            raise ValueError(m['id']+': capped_mean requires cap')
    grouped = {}
    for idx, row in enumerate(rows,2):
        if None in row or not row[group_by] or any(v is None for v in row.values()):
            raise ValueError(f'Incomplete row {idx}')
        grouped.setdefault(row[group_by],[]).append((idx,row))
    for m in metrics:
        reported=m.get('reported_by_group',{})
        if reported and (not isinstance(reported,dict) or set(reported)-set(grouped)):
            raise ValueError(m['id']+': reported_by_group contains a group absent from CSV')
    output={'schema_version':1,'status':'arithmetic_recomputed_not_semantic_validation',
            'csv_sha256':sha(csv_path),'spec_sha256':sha(spec_path),'group_by':group_by,
            'source_rows':len(rows),'groups':{}}
    mismatches=[]
    for label, records in sorted(grouped.items()):
        info={'n_rows':len(records),'metrics':{}}
        for m in metrics:
            kind=m['kind']; ident=m['id']
            if kind == 'rate':
                nums=[];dens=[]
                for idx,row in records:
                    n=as_number(row[m['numerator']],m['numerator'],idx)
                    d=as_number(row[m['denominator']],m['denominator'],idx)
                    if d<=0 or n<0 or n>d:
                        raise ValueError(f'{ident}, row {idx}: count-rate requires 0 <= numerator <= denominator and denominator > 0')
                    nums.append(n);dens.append(d)
                pooled=sum(nums)/sum(dens)
                avg=sum(n/d for n,d in zip(nums,dens))/len(nums)
                agg=m['aggregation']
                info['metrics'][ident]={'kind':kind, 'aggregation':agg,
                    'numerator_column':m['numerator'],'denominator_column':m['denominator'],
                    'numerator_total':sum(nums),'denominator_total':sum(dens),
                    'value':pooled if agg=='pooled' else avg,
                    'pooled_rate':pooled,'mean_row_rate':avg,
                    'aggregation_differs':not math.isclose(pooled,avg,rel_tol=1e-12,abs_tol=1e-12)}
            elif kind=='mean':
                values=[as_number(row[m['column']],m['column'],idx) for idx,row in records]
                info['metrics'][ident]={'kind':kind,'column':m['column'],'value':sum(values)/len(values)}
            elif kind=='event_fraction':
                pos=sum(row[m['column']] in m['positive_values'] for idx,row in records)
                info['metrics'][ident]={'kind':kind,'column':m['column'], 'positive_values':m['positive_values'],
                    'positive_n':pos,'denominator_n':len(records),'value':pos/len(records)}
            elif kind=='capped_mean':
                cap=float(m['cap'])
                if not math.isfinite(cap): raise ValueError(ident+': cap must be finite')
                values=[]; events=0
                for idx,row in records:
                    attained=row[m['event_column']] in m['event_values']
                    if attained:
                        val=as_number(row[m['column']],m['column'],idx)
                        if val>cap: raise ValueError(f'{ident}, row {idx}: observed event time exceeds cap')
                        events+=1
                    else:
                        val=cap
                    values.append(val)
                info['metrics'][ident]={'kind':kind,'column':m['column'],
                    'event_column':m['event_column'],'cap':cap,
                    'event_n':events,'unfinished_or_capped_n':len(records)-events,
                    'value':sum(values)/len(values),'calculation':'event time for completed rows; cap assigned to unfinished rows',
                    'warning':'Arithmetic mean contains unfinished/capped observations; do not call this mean completion time.' if events<len(records) else None}
            reported=m.get('reported_by_group',{})
            if reported:
                if not isinstance(reported,dict) or any(isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) for v in reported.values()):
                    raise ValueError(ident+': invalid reported_by_group')
                if label in reported:
                    tolerance=m.get('tolerance',default_tolerance(reported[label]))
                    if isinstance(tolerance,bool) or not isinstance(tolerance,(float,int)) or not math.isfinite(tolerance) or tolerance<0:
                        raise ValueError(ident+': invalid tolerance')
                    calculated=info['metrics'][ident]['value']
                    info['metrics'][ident]['reported_value']=reported[label]
                    info['metrics'][ident]['matches_reported']=abs(calculated-reported[label])<=tolerance
                    if not info['metrics'][ident]['matches_reported']:
                        mismatches.append({'metric':ident,'group':label,'reported':reported[label],'recomputed':calculated})
        output['groups'][label]=info
    output['reported_mismatches']=mismatches
    output['limits']=['Definition and correct column choices are supplied by the executor; inspect code and data dictionary.',
                      'A matched arithmetic value does not establish valid sampling, causal inference, confidence intervals, or independent validation.',
                      'Changing denominator or aggregation defines a DIFFERENT estimand; do not silently overwrite submitted outputs.']
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv',type=Path,required=True)
    parser.add_argument('--spec',type=Path,required=True)
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    try:
        if args.out and args.out.exists(): raise ValueError('Report exists; select a new path')
        result=audit(args.csv,args.spec)
        t=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
        if args.out: args.out.write_text(t,encoding='utf-8')
        else: print(t,end='')
        return 1 if result['reported_mismatches'] else 0
    except (OSError,ValueError,TypeError,KeyError,json.JSONDecodeError) as err:
        print('Input error: '+str(err),file=sys.stderr)
        return 2
    return 0

if __name__=='__main__': sys.exit(main())
