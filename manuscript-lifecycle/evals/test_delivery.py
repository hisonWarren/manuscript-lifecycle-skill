"""Adversarial tests for actual file binding and bounded package checks."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
import zlib

SCRIPT=Path(__file__).resolve().parents[1]/'scripts'/'delivery_check.py'
sys.path.insert(0,str(SCRIPT.parent))
spec=importlib.util.spec_from_file_location('delivery_check',SCRIPT)
D=importlib.util.module_from_spec(spec); spec.loader.exec_module(D)


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.base=Path(self.tmp.name)
    def file(self,name,body,role='manuscript_clean',**kwargs):
        p=self.base/name
        if isinstance(body,str):p.write_text(body,encoding='utf-8')
        else:p.write_bytes(body)
        return dict(id=name,path=name,role=role,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),**kwargs)
    def manifest(self,*files,displays=None,**kw):
        return dict(schema_version=1,files=list(files),required_roles=[files[0]['role']],displays=displays or [],**kw)
    def codes(self,m):return {f['code'] for f in D.evaluate(m,self.base)['findings'] if f['severity']=='error'}
    def docx(self,body='',extra=None):
        p=self.base/'paper.docx'
        xml='<w:document xmlns:w="'+D.NS['w']+'"><w:body>'+body+'</w:body></w:document>'
        with zipfile.ZipFile(p,'w') as z:
            z.writestr('word/document.xml',xml)
            for n,v in (extra or {}).items():z.writestr(n,v)
        return dict(id='doc',path=p.name,role='manuscript_clean',sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    def png(self,w=100,h=50,dpi=None):
        def chunk(tag,payload):return struct.pack('>I',len(payload))+tag+payload+struct.pack('>I',zlib.crc32(tag+payload)&0xffffffff)
        data=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))
        if dpi:data+=chunk(b'pHYs',struct.pack('>IIB',round(dpi/.0254),round(dpi/.0254),1))
        return data+chunk(b'IDAT',zlib.compress(b'\0'+b'\0'*(w*3)))+chunk(b'IEND',b'')
    def test_happy_bound_display_does_not_claim_render(self):
        text='Group estimates are reported in Table 1.\nTable 1. Group estimates\nNote. CI, confidence interval. * p < .05.'
        f=self.file('draft.md',text)
        display=dict(id='Table 1',kind='table',file_id=f['id'],title='Table 1. Group estimates',
            note='Note. CI, confidence interval. * p < .05.',used_symbols=['*'],symbol_definitions={'*':'* p < .05'},
            abbreviations={'CI':'confidence interval'},required_explanations=[{'name':'probability','text':'* p < .05'}],
            citations=[{'file_id':f['id'],'text':'Group estimates are reported in Table 1.'}])
        r=D.evaluate(self.manifest(f,displays=[display]),self.base)
        self.assertEqual(r['status'],'PASS');self.assertFalse(r['render_verified'])
    def test_stale_file_hash_blocks(self):
        f=self.file('draft.md','Original');(self.base/'draft.md').write_text('Changed',encoding='utf-8')
        self.assertIn('hash_mismatch',self.codes(self.manifest(f)))
    def test_missing_expected_package_role_blocks(self):
        f=self.file('draft.md','Text');m=self.manifest(f);m['required_roles'].append('cover_letter')
        self.assertIn('missing_role',self.codes(m))
    def test_forged_note_and_caption_are_not_evidence(self):
        f=self.file('draft.md','Figure 1. Estimates\nResults appear in Figure 1.')
        d=dict(id='Figure 1',kind='figure',file_id=f['id'],title='Figure 1. Estimates',caption='Bars are 95% CIs.',
               citations=[dict(file_id=f['id'],text='Results appear in Figure 1.')])
        self.assertIn('excerpt_absent',self.codes(self.manifest(f,displays=[d])))
    def test_missing_symbol_definition_and_abbreviation_block(self):
        f=self.file('draft.md','Table 1. Estimates\nSee estimates in Table 1.\nNote. CI reported.')
        d=dict(id='Table 1',kind='table',file_id=f['id'],title='Table 1. Estimates',note='Note. CI reported.',
               used_symbols=['*'],abbreviations={'CI':'confidence interval'},citations=[dict(file_id=f['id'],text='See estimates in Table 1.')])
        self.assertTrue({'symbol_undefined','abbreviation_undefined'}<=self.codes(self.manifest(f,displays=[d])))
    def test_title_cannot_be_its_own_body_citation(self):
        f=self.file('draft.md','Table 1. Estimates')
        d=dict(id='Table 1',kind='table',file_id=f['id'],title='Table 1. Estimates',citations=[dict(file_id=f['id'],text='Table 1. Estimates')])
        self.assertIn('citation_unbound',self.codes(self.manifest(f,displays=[d])))
    def test_clean_docx_tracks_comments_and_fields(self):
        f=self.docx('<w:p><w:ins><w:r><w:t>New</w:t></w:r></w:ins><w:del><w:r><w:delText>Old</w:delText></w:r></w:del><w:r><w:fldChar w:fldCharType="begin"/></w:r></w:p>',
                    {'word/comments.xml':'<w:comments xmlns:w="'+D.NS['w']+'"><w:comment w:id="0"><w:p><w:r><w:t>Check</w:t></w:r></w:p></w:comment></w:comments>'})
        r=D.evaluate(self.manifest(f),self.base)
        self.assertIn('docx_residue',self.codes(self.manifest(f)))
        self.assertEqual(r['files'][0]['counts'],dict(comments=1,insertions=1,deletions=1,fields=1,other_revisions=0))
    def test_marked_docx_keeps_expected_changes(self):
        f=self.docx('<w:p><w:ins><w:r><w:t>New</w:t></w:r></w:ins></w:p>');f['role']='manuscript_marked'
        self.assertNotIn('docx_residue',self.codes(self.manifest(f)))
    def test_clean_false_cannot_disable_clean_role_protection(self):
        f=self.docx('<w:p><w:ins><w:r><w:t>New</w:t></w:r></w:ins></w:p>');f['clean']=False
        self.assertIn('docx_residue',self.codes(self.manifest(f)))
    def test_registered_dangling_crossref_blocks(self):
        f=self.file('draft.md','The model is shown in Figure 9.')
        m=self.manifest(f,crossrefs=[dict(target_id='Figure 9',file_id=f['id'],text='The model is shown in Figure 9.')])
        self.assertIn('dangling_crossref',self.codes(m))
    def test_split_run_placeholder_is_caught(self):
        f=self.docx('<w:p><w:r><w:t>[VER</w:t></w:r><w:r><w:t>IFY: source]</w:t></w:r></w:p>')
        self.assertIn('placeholder',self.codes(self.manifest(f)))
    def test_table_layout_is_warning_unless_explicit_journal_rule(self):
        f=self.docx('<w:tbl><w:tblPr><w:tblBorders><w:insideV w:val="single"/></w:tblBorders></w:tblPr><w:tr><w:tc><w:p><w:r><w:t>n</w:t></w:r></w:p></w:tc></w:tr></w:tbl>')
        self.assertEqual(self.codes(self.manifest(f)),set())
        strict=self.manifest(f,journal={'repeat_header':'error','vertical_borders':'error'})
        self.assertTrue({'table_repeat_header','table_vertical_borders'}<=self.codes(strict))
    def test_anonymous_file_properties_are_checked(self):
        f=self.docx('<w:p><w:r><w:t>Anonymous manuscript</w:t></w:r></w:p>',{'docProps/core.xml':'<core><creator>Jane Smith</creator></core>'})
        self.assertIn('anonymity_clue',self.codes(self.manifest(f,anonymity={'file_ids':['doc'],'terms':['Jane Smith']})))
    def test_png_no_explicit_requirement_does_not_invent_dpi_failure(self):
        f=self.file('fig.png',self.png(),role='figure')
        self.assertEqual(self.codes(self.manifest(f)),set())
    def test_png_unknown_dpi_fails_explicit_requirement(self):
        f=self.file('fig.png',self.png(),role='figure',requirements={'min_dpi':300})
        self.assertIn('image_dpi',self.codes(self.manifest(f)))
    def test_png_effective_dpi_uses_physical_width(self):
        f=self.file('fig.png',self.png(1200,600),role='figure',requirements={'min_dpi':300,'width_mm':101.6,'min_pixels':[1200,600]})
        self.assertEqual(self.codes(self.manifest(f)),set())
        f['requirements']['width_mm']=203.2
        self.assertIn('image_dpi',self.codes(self.manifest(f)))
    def test_jpeg_jfif_metadata(self):
        def seg(marker,payload):return b'\xff'+bytes([marker])+struct.pack('>H',len(payload)+2)+payload
        data=b'\xff\xd8'+seg(0xE0,b'JFIF\0\x01\x02\x01'+struct.pack('>HH',300,300)+b'\0\0')+seg(0xC0,b'\x08'+struct.pack('>HH',600,1200)+b'\x01')+b'\xff\xd9'
        f=self.file('fig.jpg',data,role='figure',requirements={'min_pixels':[1200,600],'min_dpi':300})
        self.assertEqual(self.codes(self.manifest(f)),set())
    def test_path_escape_fails_closed(self):
        f=self.file('draft.md','Text');f['path']='../draft.md'
        with self.assertRaises(ValueError):D.evaluate(self.manifest(f),self.base)
    def test_cli_refuses_to_overwrite_inspected_file(self):
        f=self.file('draft.md','Text');m=self.base/'delivery.json';m.write_text(json.dumps(self.manifest(f)),encoding='utf-8')
        result=subprocess.run([sys.executable,str(SCRIPT),str(m),'--report',str(self.base/'draft.md')],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,2);self.assertEqual((self.base/'draft.md').read_text(encoding='utf-8'),'Text')
    def test_empty_manifest_is_not_pass(self):
        with self.assertRaises(ValueError):D.evaluate(dict(schema_version=1,files=[],required_roles=[],displays=[]),self.base)
    def test_empty_docx_is_not_a_manuscript(self):
        f=self.docx()
        self.assertIn('text_uninspectable',self.codes(self.manifest(f)))
    def test_unsupported_text_format_is_not_silently_certified(self):
        f=self.file('draft.pdf',b'%PDF unknown')
        self.assertIn('text_uninspectable',self.codes(self.manifest(f)))


if __name__=='__main__':unittest.main()
