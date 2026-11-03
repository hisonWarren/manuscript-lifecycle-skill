#!/usr/bin/env python3
"""Describe matched table-note/caption distributions, never score writing quality.
python display_profile.py corpus.json --report report.json
Each record: id, role=draft|exemplar, paper_id, path, sha256, text,
kind=table_note|figure_caption|table_title, task, language, panels.
Match on kind/task/language/panels; summarize within each paper first.
Paths relative to JSON. Exits 0 descriptive profile, 1 no matched comparison, 2 invalid evidence.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import statistics
import sys
from audit_run import digest
import mslib as M
from output_safety import declared_paths, output_path, write_fresh


def profile(data, base):
    if data.get('schema_version') != 1 or not isinstance(data.get('records'),list) or not data['records']:
        raise ValueError('Nonempty schema_version 1 records required')
    seen,ex,drafts={},defaultdict(list),[]
    def group(r):return (r['kind'],r['task'],r['language'],r['panels'])
    for r in data['records']:
        for k in ('id','role','paper_id','path','sha256','text','kind','task','language'):
            if not isinstance(r.get(k),str) or not r[k].strip():raise ValueError('Missing '+k)
        if r['id'] in seen:raise ValueError('Duplicate record ID')
        seen[r['id']]=1
        if r['role'] not in {'draft','exemplar'} or r['kind'] not in {'table_note','figure_caption','table_title'}:
            raise ValueError('Unknown role/kind')
        if r['language'] not in {'en','zh'} or not isinstance(r.get('panels'),int) or isinstance(r['panels'],bool) or r['panels']<1:
            raise ValueError('Invalid language/panels')
        p=(base/r['path']).resolve()
        if not p.is_file() or digest(p)!=r['sha256']:raise ValueError('Missing or stale source '+r['id'])
        text=M.load_text(str(p))
        if ' '.join(r['text'].split()) not in ' '.join(text.split()):raise ValueError('Excerpt not in source '+r['id'])
        r=dict(r)
        r['length_units']=M.count_words_ws(r['text'])
        r['sentences']=len(M.sentences(r['text']))
        r['sha256_actual']=digest(p)
        (drafts if r['role']=='draft' else ex[group(r)]).append(r)
    if not drafts or not ex:raise ValueError('Both draft and exemplar evidence required')
    draft_hashes={r['sha256_actual'] for r in drafts}
    comparisons=[]
    for d in drafts:
        # Same source cannot supply the draft and its external benchmark.
        pool=[r for r in ex[group(d)] if r['sha256_actual'] not in draft_hashes and r['paper_id']!=d['paper_id']]
        papers=defaultdict(list)
        unique=set()
        for r in pool:
            key=(r['paper_id'],r['text'])
            if key not in unique:
                papers[r['paper_id']].append(r['length_units']);unique.add(key)
        means=[statistics.mean(v) for v in papers.values()]
        out={'id':d['id'],'stratum':list(group(d)),'draft_length':d['length_units'],
             'unit':'Chinese characters plus Latin tokens' if d['language']=='zh' else 'whitespace words',
             'papers':len(means),'items':len(unique),'source_ids':[r['id'] for r in pool],
             'status':'descriptive_only' if means else 'no_matched_comparison'}
        if means:
            out.update(median=statistics.median(means),minimum=min(means),maximum=max(means),
                       length_flag='review_length_in_context' if d['length_units']>max(means) else 'within_observed_lengths')
        comparisons.append(out)
    return {'comparisons':comparisons,'quality_pass':False,
            'limitations':['Length is not completeness or quality.',
              'Source registration and matching quality require review.',
              'Repeated items averaged within paper; small samples are descriptive.',
              'No universal word limit; retain required definitions and uncertainty.']}


def main():
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('manifest');p.add_argument('--report');a=p.parse_args()
    try:
        src=Path(a.manifest).resolve()
        target=output_path(a.report,[src]) if a.report else None
        data=json.loads(src.read_text(encoding='utf-8-sig'))
        if target:target=output_path(target,[src,*declared_paths(data,src.parent)])
        out=profile(data,src.parent)
        code=0 if all(c['papers'] for c in out['comparisons']) else 1
        body=json.dumps(out,ensure_ascii=False,indent=2)
        if target:write_fresh(target,body)
    except (OSError,ValueError,TypeError,KeyError,AttributeError,RuntimeError) as e:
        print(json.dumps({'status':'input_error','error':str(e)},ensure_ascii=False));return 2
    print(body);return code

if __name__=='__main__':sys.exit(main())
