#!/usr/bin/env python3
"""Bounded file/package checks; standard library only.

python delivery_check.py delivery.json --report delivery_report.json
0 mechanical checks have no errors; 1 findings; 2 malformed input.
XML/metadata checks NEVER establish visual, semantic or scientific correctness.
See references/14_display_and_delivery.md for scope and manifest fields.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import xml.etree.ElementTree as ET
import zipfile
from mslib import PLACEHOLDER, detect_lang, iter_paragraphs, paragraph_text
from output_safety import declared_paths, output_path, write_fresh

NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
W = '{' + NS['w'] + '}'
MAX_FILE = 100 * 1024 * 1024
MAX_XML = 30 * 1024 * 1024
CLEAN = {'manuscript_clean', 'anonymous_manuscript', 'supplement', 'cover_letter', 'response'}
# Placeholder labels that do not name a person (revision authors, document properties).
GENERIC_PERSON = re.compile(r'^(?:authors?|reviewers?|editors?|anonymous|unknown|users?|admin(?:istrator)?|guest|owner|'
                            r'windows user|microsoft office (?:user|用户)|python-docx|作者|审稿人|编辑|匿名|未知|用户)\s*\d*$', re.I)


def norm(value):
    return re.sub(r'\s+', ' ', value).strip()


def docx_info(path):
    text, original, identity, metadata, tables, people = [], [], [], [], [], set()
    counts = {'comments': 0, 'insertions': 0, 'deletions': 0, 'fields': 0, 'other_revisions': 0}
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > 3000 or sum(i.file_size for i in members) > MAX_FILE:
            raise ValueError('DOCX archive exceeds bounded inspection size')
        if 'word/document.xml' not in archive.namelist():
            raise ValueError('DOCX has no word/document.xml')
        for item in members:
            name = item.filename
            rels = name.endswith('.rels')
            if not rels and (not name.endswith('.xml') or not name.startswith(('word/', 'docProps/'))):
                continue
            if item.file_size > MAX_XML:
                raise ValueError('DOCX XML part exceeds bounded inspection size')
            raw = archive.read(name)
            if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
                raise ValueError('XML declarations with entities are unsupported')
            root = ET.fromstring(raw)
            if rels:
                # External targets (hyperlinks, attached template paths) can carry user names.
                identity.extend(r.get('Target', '') for r in root if r.get('TargetMode') == 'External')
                continue
            if name.startswith('docProps/'):
                metadata.extend(t for t in root.itertext() if t.strip())
                if name == 'docProps/core.xml':
                    people.update(n.text.strip() for n in root
                                  if n.tag.rsplit('}', 1)[-1] in {'creator', 'lastModifiedBy'} and (n.text or '').strip())
                continue
            # One entry per paragraph keeps phrases split across Word runs together. Unresolved-item
            # checks read the accepted text; deleted text, revision/comment authors (also people.xml),
            # field codes and document variables still travel with the file, so anonymity reads them too.
            for para in iter_paragraphs(root):
                text.append(paragraph_text(para, 'accept'))
                original.append(paragraph_text(para, 'reject'))
            for node in root.iter():
                for key, value in node.attrib.items():
                    local = key.rsplit('}', 1)[-1]
                    if local in {'author', 'initials', 'userId'} and value.strip():
                        identity.append(value)
                        if local == 'author':
                            people.add(value.strip())
                if node.tag in {W+'instrText', W+'delInstrText'} and node.text:
                    identity.append(node.text)
                elif node.tag == W+'docVar':
                    identity.append(node.get(W+'val', ''))
            for field, tag in [('comments','comment'), ('insertions','ins'), ('insertions','moveTo'), ('deletions','del'), ('deletions','moveFrom')]:
                counts[field] += len(root.findall('.//w:' + tag, NS))
            counts['other_revisions'] += sum(n.tag.startswith(W) and (n.tag[len(W):].endswith('PrChange') or n.tag[len(W):] in {'cellIns','cellDel','cellMerge','numberingChange'}) for n in root.iter())
            counts['fields'] += len(root.findall('.//w:fldSimple', NS)) + sum(
                n.get(W+'fldCharType') == 'begin' for n in root.findall('.//w:fldChar', NS))
            if name == 'word/document.xml':
                for table in root.findall('.//w:tbl', NS):
                    rows = table.findall('w:tr', NS)
                    header = rows[0].find('w:trPr/w:tblHeader', NS) if rows else None
                    repeated = header is not None and header.get(W+'val', '1') not in {'0', 'false', 'off'}
                    # Explicit borders only: styles/inherited defaults require rendering.
                    vertical = any(n.tag in {W+'left',W+'right',W+'insideV',W+'start',W+'end'} and
                                   n.get(W+'val', 'single') not in {'nil','none','0'}
                                   for borders in table.iter() if borders.tag in {W+'tblBorders',W+'tcBorders'}
                                   for n in borders)
                    tables.append({'rows':len(rows), 'repeat_header':repeated, 'explicit_vertical_borders':vertical})
    return {'text':'\n'.join(text), 'metadata':'\n'.join(metadata), 'identity':'\n'.join(original + identity),
            'people':sorted(people), 'counts':counts, 'tables':tables}


def image_info(path):
    data = path.read_bytes()
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        result = {'format':'PNG', 'width':None, 'height':None, 'dpi':None}
        pos = 8
        while pos + 12 <= len(data):
            size = struct.unpack('>I', data[pos:pos+4])[0]
            tag, chunk = data[pos+4:pos+8], data[pos+8:pos+8+size]
            if pos + size + 12 > len(data): raise ValueError('Truncated PNG chunk')
            if tag == b'IHDR' and len(chunk) == 13:
                result['width'],result['height'] = struct.unpack('>II',chunk[:8])
            if tag == b'pHYs' and len(chunk) == 9 and chunk[8] == 1:
                result['dpi'] = [v * .0254 for v in struct.unpack('>II',chunk[:8])]
            pos += size + 12
            if tag == b'IEND': break
        if not result['width'] or not result['height']: raise ValueError('PNG dimensions unavailable')
        return result
    if data[:2] == b'\xff\xd8':
        result = {'format':'JPEG', 'width':None, 'height':None, 'dpi':None}
        pos = 2
        while pos < len(data):
            if data[pos] != 255: raise ValueError('Malformed JPEG marker')
            while pos < len(data) and data[pos] == 255: pos += 1
            if pos >= len(data): break
            marker = data[pos]; pos += 1
            if marker in {0xD9,0xDA}: break
            if marker == 0x01 or 0xD0 <= marker <= 0xD7: continue
            if pos + 2 > len(data): raise ValueError('Truncated JPEG length')
            size = struct.unpack('>H',data[pos:pos+2])[0]
            if size < 2 or pos + size > len(data): raise ValueError('Truncated JPEG segment')
            chunk = data[pos+2:pos+size]; pos += size
            if marker == 0xE0 and chunk.startswith(b'JFIF\0') and len(chunk) >= 12:
                unit = chunk[7]; x,y = struct.unpack('>HH',chunk[8:12])
                if unit in (1,2): result['dpi'] = [x*(2.54 if unit==2 else 1),y*(2.54 if unit==2 else 1)]
            if marker in {0xC0,0xC1,0xC2,0xC3,0xC5,0xC6,0xC7,0xC9,0xCA,0xCB,0xCD,0xCE,0xCF} and len(chunk)>=5:
                result['height'],result['width'] = struct.unpack('>HH',chunk[1:5])
        if not result['width'] or not result['height']: raise ValueError('JPEG dimensions unavailable')
        return result
    raise ValueError('Only PNG and JPEG metadata inspection supported')


def evaluate(data, base):
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        raise ValueError('schema_version must equal 1')
    for name in ['files','required_roles','displays']:
        if not isinstance(data.get(name), list): raise ValueError(name+' must be an explicit list')
    if not data['files'] or not data['required_roles']: raise ValueError('files and required_roles must not be empty')
    journal = data.get('journal',{})
    for setting in ['repeat_header','vertical_borders']:
        if journal.get(setting,'warn') not in {'warn','error','ignore'}: raise ValueError('Invalid journal '+setting)
    findings, files, displays, summaries = [], {}, {}, []
    def add(severity,code,message,target=''):
        findings.append({'severity':severity,'code':code,'target':target,'message':message})
    def demand(condition,code,message,target=''):
        if not condition: add('error',code,message,target)
        return condition
    for entry in data['files']:
        if not isinstance(entry,dict) or not all(isinstance(entry.get(k),str) and entry[k] for k in ['id','path','role','sha256']):
            raise ValueError('Every file needs nonempty id/path/role/sha256')
        fid = entry['id']
        if fid in files: raise ValueError('Duplicate file ID: '+fid)
        path = (base / entry['path']).resolve()
        if not path.is_relative_to(base.resolve()): raise ValueError('Package path escapes manifest directory: '+entry['path'])
        record = {'entry':entry,'path':path,'text':None,'metadata':'','identity':'','people':[],'ok':False}
        files[fid] = record
        if not demand(path.is_file(),'missing_file','Declared file does not exist',fid): continue
        size = path.stat().st_size
        if not demand(0 < size <= MAX_FILE,'file_size','File is empty or exceeds 100 MB inspection bound',fid): continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if not demand(re.fullmatch('[0-9a-f]{64}',entry['sha256']) and actual == entry['sha256'],
                      'hash_mismatch','Manifest hash is invalid or stale',fid): continue
        record['ok'] = True
        summary = {'id':fid,'role':entry['role'],'path':str(path),'sha256':actual}
        try:
            if path.suffix.lower() == '.docx':
                info = docx_info(path)
                record.update(text=info.pop('text'),metadata=info.pop('metadata'),identity=info.pop('identity'),people=info.pop('people'))
                summary.update(info)
                clean = entry['role'] in CLEAN or entry.get('clean') is True
                for key in ['comments','insertions','deletions','other_revisions']:
                    if clean and info['counts'][key]: add('error','docx_residue',key+' present in clean file',fid)
                if entry['role'] == 'manuscript_marked' and not (info['counts']['insertions'] or info['counts']['deletions'] or info['counts']['other_revisions']):
                    add('warn','no_tracked_changes','No tracked changes found; manual highlighting may be valid but needs review',fid)
                if info['counts']['fields']: add('warn','fields_present','Fields need refresh and rendered cross-reference verification',fid)
                for index,table in enumerate(info['tables'],1):
                    for key,condition in [('repeat_header',not table['repeat_header']),('vertical_borders',table['explicit_vertical_borders'])]:
                        severity = journal.get(key,'warn')
                        if condition and severity!='ignore': add(severity,'table_'+key,'Explicit table structure requires journal-specific review',fid+':table '+str(index))
            elif path.suffix.lower() in {'.txt','.md','.csv','.json'}:
                record['text'] = path.read_text(encoding='utf-8-sig')
            req = entry.get('requirements',{})
            if req:
                if not isinstance(req,dict) or not set(req) <= {'min_pixels','min_dpi','width_mm','height_mm'}:
                    raise ValueError('Unsupported image requirement keys')
                info = image_info(path); summary['image'] = info
                minimum = req.get('min_pixels')
                if minimum is not None:
                    if not isinstance(minimum,list) or len(minimum)!=2 or any(not isinstance(n,(int,float)) or isinstance(n,bool) or n<=0 for n in minimum):
                        raise ValueError('min_pixels must be two positive numbers')
                    demand(info['width']>=minimum[0] and info['height']>=minimum[1],'image_pixels','Image pixel dimensions below explicit requirement',fid)
                dpi = req.get('min_dpi')
                for dim in ['width_mm','height_mm']:
                    if dim in req and (not isinstance(req[dim],(int,float)) or isinstance(req[dim],bool) or req[dim]<=0): raise ValueError(dim+' must be positive')
                if dpi is not None:
                    if not isinstance(dpi,(int,float)) or isinstance(dpi,bool) or dpi<=0: raise ValueError('min_dpi must be positive')
                    effective = [info[axis]/(req[dim]/25.4) for axis,dim in [('width','width_mm'),('height','height_mm')] if dim in req]
                    values = effective if effective else info['dpi']
                    demand(bool(values) and min(values)+0.5>=dpi,'image_dpi','DPI unavailable or below requirement at stated size',fid)
        except (ValueError, OSError, UnicodeError, zipfile.BadZipFile, ET.ParseError,struct.error) as err:
            add('error','inspection_failed',str(err),fid); record['ok']=False
        summaries.append(summary)
        if entry['role'] in CLEAN | {'manuscript_marked','title_page','abstract','reporting_checklist'}:
            demand(record['text'] is not None and bool(record['text'].strip()),
                   'text_uninspectable','Required textual role has no inspectable text; unsupported formats need a separate check',fid)
        if record['text']:
            for match in PLACEHOLDER.finditer(record['text']): add('error','placeholder','Unresolved placeholder: '+match.group()[:100],fid)
            # Remarks typed into the text as tracked insertions survive "accept all"; in an English file Chinese is a strong sign.
            zh=list(re.finditer(r'[\u4e00-\u9fff]{2,}',record['text'])) if detect_lang(record['text'])=='en' else []
            if zh:
                add('warn','foreign_script','Chinese text in an English file (%d places), check for annotator remarks or translation residue: %s'%(
                    len(zh),' | '.join(record['text'][max(0,m.start()-15):m.end()+15].replace('\n',' ') for m in zh[:3])[:240]),fid)
            if re.search(r'Error!\s*(?:Reference source not found|Bookmark not defined)|错误[！!].*(?:引用|书签)',record['text'],re.I):
                add('error','broken_field','Unresolved cross-reference field text',fid)
    for role in data['required_roles']:
        if not isinstance(role,str) or not role: raise ValueError('required_roles must contain strings')
        demand(any(f['ok'] and f['entry']['role']==role for f in files.values()),'missing_role','Required package role absent: '+role)
    for item in data['displays']:
        if not isinstance(item,dict) or not item.get('id') or item.get('kind') not in {'table','figure'} or not item.get('file_id'):
            raise ValueError('Each display needs id/kind/file_id')
        did = item['id']
        if did in displays: raise ValueError('Duplicate display ID: '+did)
        displays[did] = item
        source = files.get(item['file_id'],{})
        source_text = source.get('text')
        if not demand(source.get('ok') and source_text is not None,'display_source','Display must bind an inspected text/DOCX file',did): continue
        text = norm(source_text)
        for key in ['title','caption','note']:
            phrase = item.get(key,'')
            if not isinstance(phrase,str): raise ValueError('Display '+key+' must be text')
            if phrase: demand(norm(phrase) in text,'excerpt_absent',key+' absent from bound file',did)
        demand(bool(item.get('title')),'missing_title','Display title missing',did)
        if item['kind']=='figure': demand(bool(item.get('caption')),'missing_caption','Figure caption missing',did)
        explanation = norm(' '.join(item.get(k,'') for k in ['title','caption','note']))
        used = item.get('used_symbols',[]); definitions=item.get('symbol_definitions',{}); abbr=item.get('abbreviations',{})
        if not isinstance(used,list) or not isinstance(definitions,dict) or not isinstance(abbr,dict): raise ValueError('Invalid symbol/abbreviation collections')
        for symbol in used:
            phrase = definitions.get(symbol,'')
            demand(bool(phrase) and symbol in phrase and norm(phrase) in explanation,'symbol_undefined','Used symbol lacks a bound definition: '+str(symbol),did)
        for token,meaning in abbr.items():
            demand(bool(token and meaning) and token in explanation and norm(meaning).casefold() in explanation.casefold(),
                   'abbreviation_undefined','Abbreviation or its declared expansion absent: '+token,did)
        required=item.get('required_explanations',[])
        if not isinstance(required,list): raise ValueError('required_explanations must be a list')
        for row in required:
            if not isinstance(row,dict) or not row.get('name'): raise ValueError('Explanation needs a name')
            phrase=row.get('text','')
            demand(isinstance(phrase,str) and bool(phrase) and norm(phrase) in explanation,'explanation_missing','Missing bound explanation: '+row['name'],did)
        citations=item.get('citations',[])
        if not isinstance(citations,list): raise ValueError('citations must be a list')
        demand(bool(citations),'display_uncited','No contextual citation registered',did)
        for cite in citations:
            if not isinstance(cite,dict): raise ValueError('Citation must be an object')
            bound=files.get(cite.get('file_id'),{}); phrase=cite.get('text','')
            demand(bound.get('ok') and isinstance(phrase,str) and len(norm(phrase))>len(did) and did in phrase and
                   norm(phrase) in norm(bound.get('text') or '') and norm(phrase) not in {norm(item.get(k,'')) for k in ['title','caption','note']},
                   'citation_unbound','Citation needs actual context distinct from title/caption/note',did)
    crossrefs=data.get('crossrefs',[])
    if not isinstance(crossrefs,list): raise ValueError('crossrefs must be a list')
    for ref in crossrefs:
        if not isinstance(ref,dict) or not isinstance(ref.get('target_id'),str): raise ValueError('Crossref needs target_id')
        did=ref['target_id']; source=files.get(ref.get('file_id'),{}); phrase=ref.get('text','')
        demand(did in displays,'dangling_crossref','Crossref target is not a registered display: '+did)
        demand(source.get('ok') and isinstance(phrase,str) and did in phrase and len(norm(phrase))>len(did) and
               norm(phrase) in norm(source.get('text') or ''),'crossref_unbound','Crossref context absent from bound file',did)
    anon=data.get('anonymity',{})
    if anon:
        if not isinstance(anon,dict) or not isinstance(anon.get('file_ids'),list) or not isinstance(anon.get('terms'),list):
            raise ValueError('anonymity needs file_ids and terms lists')
        for fid in anon['file_ids']:
            record=files.get(fid)
            if not demand(record and record['ok'] and record['text'] is not None,'anonymity_unchecked','Anonymous target not inspectable',str(fid)): continue
            hay='\n'.join([record['text'],record['metadata'],record['identity'],record['path'].name]).casefold()
            for term in anon['terms']:
                if not isinstance(term,str) or not term.strip(): raise ValueError('Anonymity terms must be nonempty strings')
                if term.casefold() in hay: add('error','anonymity_clue','Known author/institution clue present: '+term,str(fid))
            if re.search(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|\b\d{4}-\d{4}-\d{4}-[\dX]{4}\b',hay):
                add('warn','anonymity_identifier','Email/ORCID-like identifier needs review',str(fid))
            named=[p for p in record['people'] if not GENERIC_PERSON.match(p)]
            if named:
                add('warn','anonymity_people','Names stored in revisions, comments or document properties: '+
                    ', '.join(named)[:300]+'; confirm none identifies an author',str(fid))
    return {'schema_version':1,'status':'FAIL' if any(f['severity']=='error' for f in findings) else 'PASS',
            'scope':'declared_file_and_metadata_checks_only','render_verified':False,'findings':findings,'files':summaries,
            'limitations':['No visual rendering, OCR, statistical truth or literature support is checked.',
                           'Display inventories, symbols, abbreviations and required explanations may be incompletely declared.',
                           'Exact text presence does not prove an explanation is correct or a citation supports it.',
                           'DOCX inherited styles, actual page breaks and full anonymity need human/rendered review.',
                           'PNG/JPEG metadata are not decoded pixel validation; EXIF-only JPEG DPI is unsupported.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest'); parser.add_argument('--report',required=True)
    args=parser.parse_args()
    try:
        source=Path(args.manifest).resolve(); target=output_path(args.report,[source])
        data=json.loads(source.read_text(encoding='utf-8-sig'))
        target=output_path(target,[source,*declared_paths(data,source.parent)])
        report=evaluate(data,source.parent)
        write_fresh(target,json.dumps(report,ensure_ascii=False,indent=2))
        print(json.dumps({'status':report['status'],'findings':len(report['findings']),'render_verified':False},ensure_ascii=False))
        return int(report['status']=='FAIL')
    except (OSError,ValueError,TypeError,KeyError,AttributeError,RuntimeError) as err:
        print('INPUT ERROR: '+str(err)); return 2


if __name__=='__main__': sys.exit(main())
