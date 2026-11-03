#!/usr/bin/env python3
"""Compare a cited DOI's title, first author and year with Crossref metadata.
This does not check whether the paper supports the cited claim.
Exit 0 identity matched; 1 mismatch/unverified; 2 invalid input.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
sys.path.insert(0,str(Path(__file__).resolve().parent))
import mslib as M

def norm(text):
    return ''.join(c for c in unicodedata.normalize('NFKC',text).casefold() if c.isalnum())

def compare(doi,title,author,year,record):
    titles=record.get('title',[]); authors=record.get('author',[])
    years=set()
    for key in ('published','published-print','published-online','issued'):
        for parts in record.get(key,{}).get('date-parts',[]):
            if parts:years.add(str(parts[0]))
    actual_author=authors[0].get('family','') if authors else ''
    checks={'doi':record.get('DOI','').lower()==doi.lower(),
            'title':any(norm(title)==norm(t) for t in titles),
            'first_author':bool(actual_author) and norm(author)==norm(actual_author),
            'year':str(year) in years}
    return {'status':'identity_matched' if all(checks.values()) else 'identity_mismatch',
            'checks':checks,'expected':{'doi':doi,'title':title,'first_author':author,'year':year},
            'actual':{'doi':record.get('DOI'),'titles':titles,'first_author':actual_author,'years':sorted(years)},
            'claim_support_verified':False,
            'scope':'Identity only. A title variant or year discrepancy needs adjudication; a resolving DOI is insufficient. Read the source separately to assess the claim.'}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('doi');ap.add_argument('--title',required=True);ap.add_argument('--author',required=True,help='First author family name');ap.add_argument('--year',required=True,type=int);ap.add_argument('--report',type=Path)
    a=ap.parse_args();doi=re.sub(r'^https?://(?:dx\.)?doi\.org/','',a.doi.strip(),flags=re.I)
    if not re.fullmatch(r'10\.\d{4,9}/\S+',doi) or not a.title.strip() or not a.author.strip() or not 1500<=a.year<=2500:
        print('Invalid DOI/title/author/year.',file=sys.stderr);return 2
    if a.report and a.report.exists():print('Report exists; use a fresh path.',file=sys.stderr);return 2
    url='https://api.crossref.org/works/'+urllib.parse.quote(doi,safe='')
    try:
        request=urllib.request.Request(url,headers={'User-Agent':'manuscript-lifecycle-reference-identity/1.0'})
        with urllib.request.urlopen(request,timeout=15) as response: raw=response.read()
        record=json.loads(raw.decode('utf-8'))['message']
        result=compare(doi,a.title,a.author,a.year,record)
        result.update(source_url=url,response_sha256=hashlib.sha256(raw).hexdigest(),metadata=record)
    except (OSError,ValueError,KeyError,TypeError) as e:
        result={'status':'unverified','error':str(e),'source_url':url,'claim_support_verified':False}
    result['retrieved_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    if a.report:
        try:
            with a.report.open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,ensure_ascii=False,indent=2)
        except OSError as e:print(str(e),file=sys.stderr);return 2
    print(json.dumps({k:v for k,v in result.items() if k!='metadata'},ensure_ascii=False,indent=2))
    return 0 if result['status']=='identity_matched' else 1

if __name__=='__main__':sys.exit(main())
