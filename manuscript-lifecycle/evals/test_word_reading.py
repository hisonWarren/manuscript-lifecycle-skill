"""Word 读取：接受/拒绝两种读法、内容控件、文本框、段落标记与表格行的修订、符号字体；交付检查的占位符与匿名线索。"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import mslib as M  # noqa: E402
import delivery_check as D  # noqa: E402

WNS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NSDECL = ('xmlns:w="%s" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
          'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" xmlns:v="urn:schemas-microsoft-com:vml" '
          'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"' % WNS)
STYLES = ('<w:styles xmlns:w="%s"><w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/></w:style>'
          '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/></w:style></w:styles>' % WNS)
REV = 'w:id="%d" w:author="Reviser" w:date="2024-05-01T00:00:00Z"'


def r(t):
    return '<w:r><w:t xml:space="preserve">%s</w:t></w:r>' % t


def ins(xml, i=1):
    return '<w:ins %s>%s</w:ins>' % (REV % i, xml)


def dele(t, i=2):
    return '<w:del %s><w:r><w:delText xml:space="preserve">%s</w:delText></w:r></w:del>' % (REV % i, t)


def p(body, style=None, mark=None, change=None):
    ppr = ''
    if style or mark or change is not None:
        ppr = '<w:pPr>%s%s%s</w:pPr>' % ('<w:pStyle w:val="%s"/>' % style if style else '',
                                          '<w:rPr><w:%s %s/></w:rPr>' % (mark, REV % 9) if mark else '',
                                          '<w:pPrChange %s><w:pPr>%s</w:pPr></w:pPrChange>' % (REV % 8, change) if change is not None else '')
    return '<w:p>%s%s</w:p>' % (ppr, body)


class WordReading(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.base = Path(self.tmp.name)

    def docx(self, body, extra=None, name='paper.docx'):
        path = self.base/name
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('word/document.xml', '<w:document %s><w:body>%s</w:body></w:document>' % (NSDECL, body))
            z.writestr('word/styles.xml', STYLES)
            for k, v in (extra or {}).items():
                z.writestr(k, v)
        return path

    def views(self, body):
        path = self.docx(body)
        return M.docx_to_md(str(path), 'accept'), M.docx_to_md(str(path), 'reject')

    def lines(self, md):
        return [l for l in md.split('\n') if l.strip()]

    def test_body_level_content_controls_are_read(self):
        body = ('<w:sdt><w:sdtPr><w:alias w:val="Title"/></w:sdtPr><w:sdtContent>%s</w:sdtContent></w:sdt>' % p(r('Feedback and help seeking'))
                + p(r('Introduction text.'))
                + '<w:sdt><w:sdtPr><w:docPartObj><w:docPartGallery w:val="Bibliographies"/></w:docPartObj></w:sdtPr><w:sdtContent>'
                + p(r('References'), 'Heading1') + p(r('Lee, A. (2020). Help seeking. J. Ed., 1, 1-9.')) + '</w:sdtContent></w:sdt>')
        for md in self.views(body):
            self.assertEqual(self.lines(md), ['Feedback and help seeking', 'Introduction text.', '# References',
                                              'Lee, A. (2020). Help seeking. J. Ed., 1, 1-9.'])

    def test_textbox_is_read_once_as_its_own_paragraph(self):
        box = '<w:txbxContent>%s</w:txbxContent>' % p(r('Figure 1. Help requests by week.'))
        body = p(r('Anchor paragraph.') + '<w:r><mc:AlternateContent><mc:Choice Requires="wps"><w:drawing><wps:txbx>%s</wps:txbx>'
                 '</w:drawing></mc:Choice><mc:Fallback><w:pict><v:textbox>%s</v:textbox></w:pict></mc:Fallback>'
                 '</mc:AlternateContent></w:r>' % (box, box))
        for md in self.views(body):
            self.assertEqual(self.lines(md), ['Anchor paragraph.', 'Figure 1. Help requests by week.'])

    def test_paragraph_mark_revisions_merge_and_split(self):
        body = (p(r('The effect was '), mark='del') + p(r('small.'))
                + p(r('First half.'), mark='ins') + p(r(' Second half.')))
        accept, reject = self.views(body)
        self.assertEqual(self.lines(accept), ['The effect was small.', 'First half.', 'Second half.'])
        self.assertEqual(self.lines(reject), ['The effect was', 'small.', 'First half. Second half.'])

    def test_deleted_heading_paragraph_leaves_no_heading_level(self):
        body = p(dele('Old heading'), 'Heading1', mark='del') + p(r('Body text.'))
        accept, reject = self.views(body)
        self.assertEqual(self.lines(accept), ['Body text.'])
        self.assertEqual(self.lines(reject), ['# Old heading', 'Body text.'])

    def test_reject_view_uses_previous_paragraph_style(self):
        body = p(r('Methods'), 'Heading2', change='<w:pStyle w:val="Heading1"/>') + p(r('Results'), 'Heading1', change='')
        accept, reject = self.views(body)
        self.assertEqual(self.lines(accept), ['## Methods', '# Results'])
        self.assertEqual(self.lines(reject), ['# Methods', 'Results'])

    def test_table_row_revisions_and_nested_tables(self):
        def cell(xml): return '<w:tc>%s</w:tc>' % xml
        nested = '<w:tbl><w:tr>%s</w:tr></w:tbl>' % cell(p(r('Inner')))
        body = ('<w:tbl>'
                '<w:tr>%s%s</w:tr>' % (cell(p(r('Variable'))), cell(p(r('B'))))
                + '<w:tr><w:trPr><w:del %s/></w:trPr>%s%s</w:tr>' % (REV % 3, cell(p(dele('Age'))), cell(p(dele('0.10'))))
                + '<w:tr><w:trPr><w:ins %s/></w:trPr>%s%s</w:tr>' % (REV % 4, cell(p(ins(r('Sex')))), cell(p(ins(r('0.20')))))
                + '<w:tr>%s%s</w:tr>' % (cell(p(r('Outer')) + nested + p('')), cell(p(r('0.30'))))
                + '</w:tbl>')
        accept, reject = self.views(body)
        self.assertEqual(self.lines(accept), ['| Variable | B |', '| Sex | 0.20 |', '| Outer Inner | 0.30 |'])
        self.assertEqual(self.lines(reject), ['| Variable | B |', '| Age | 0.10 |', '| Outer Inner | 0.30 |'])

    def test_symbol_fonts_hyphens_tabs_fields_and_equations(self):
        sym = lambda font, code: '<w:r><w:sym w:font="%s" w:char="%s"/></w:r>' % (font, code)
        symbol_run = '<w:r><w:rPr><w:rFonts w:ascii="Symbol" w:hAnsi="Symbol"/></w:rPr><w:t>c</w:t></w:r>'
        body = p('<w:pPr><w:tabs><w:tab w:val="left" w:pos="720"/></w:tabs></w:pPr>' + r('p ') + sym('Symbol', 'F0A3') + r(' .05, ')
                 + sym('Symbol', 'F0B1') + r(' SD, ') + symbol_run + r('2 = 4.1, d ') + sym('Cambria Math', '2265') + r(' 0.2, self')
                 + '<w:r><w:noBreakHyphen/></w:r>' + r('report ') + sym('Wingdings', 'F0FC') + sym('Wingdings', 'F021'))
        body += p('<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> REF _Ref1 \\h </w:instrText></w:r>'
                  '<w:r><w:fldChar w:fldCharType="separate"/></w:r>' + r('Table 2') + '<w:r><w:fldChar w:fldCharType="end"/></w:r>')
        body += p(r('Error: ') + '<m:oMath><m:r><m:t>RMSE</m:t></m:r></m:oMath>')
        accept, _ = self.views(body)
        self.assertEqual(self.lines(accept), ['p \u2264 .05, \u00b1 SD, \u03c72 = 4.1, d \u2265 0.2, self-report \u2713\ufffd',
                                              'Table 2', 'Error: RMSE'])

    def test_moves_and_insert_then_delete(self):
        body = p('<w:moveFrom %s>%s</w:moveFrom>' % (REV % 5, r('moved ')) + r('kept ') + '<w:moveTo %s>%s</w:moveTo>' % (REV % 6, r('moved'))
                 + '<w:ins %s><w:del %s><w:r><w:delText>gone</w:delText></w:r></w:del></w:ins>' % (REV % 7, REV % 10))
        accept, reject = self.views(body)
        self.assertEqual(self.lines(accept), ['kept moved'])
        self.assertEqual(self.lines(reject), ['moved kept'])


class Annotations(unittest.TestCase):
    W14 = 'http://schemas.microsoft.com/office/word/2010/wordml'
    W15 = 'http://schemas.microsoft.com/office/word/2012/wordml'

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.base = Path(self.tmp.name)

    def docx(self, body, extra=None):
        path = self.base/'annotated.docx'
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('word/document.xml', '<w:document %s><w:body>%s</w:body></w:document>' % (NSDECL, body))
            for k, v in (extra or {}).items():
                z.writestr(k, v)
        return path

    def comment(self, cid, para_id, text):
        return '<w:comment w:id="%s" w:author="Adviser" w:date="2024-05-02T00:00:00Z"><w:p w14:paraId="%s">%s</w:p></w:comment>' % (cid, para_id, r(text))

    def test_comments_have_exact_anchor_replies_and_resolution(self):
        body = ('<w:p>' + r('Results were ') + '<w:commentRangeStart w:id="0"/>' + r('clearly ') + dele('very ') + '</w:p>'
                '<w:p>' + r('robust') + '<w:commentRangeEnd w:id="0"/><w:r><w:commentReference w:id="0"/></w:r>' + r(' overall.') + '</w:p>'
                + p(r('Another sentence.') + '<w:r><w:commentReference w:id="2"/></w:r>'))
        comments = ('<w:comments xmlns:w="%s" xmlns:w14="%s">%s%s%s</w:comments>' % (WNS, self.W14,
                    self.comment(0, 'AAAA0001', 'Too strong?'), self.comment(1, 'AAAA0002', 'Agreed, softened.'), self.comment(2, 'AAAA0003', 'Cite this.')))
        ext = ('<w15:commentsEx xmlns:w15="%s"><w15:commentEx w15:paraId="AAAA0001" w15:done="1"/>'
               '<w15:commentEx w15:paraId="AAAA0002" w15:paraIdParent="AAAA0001" w15:done="0"/><w15:commentEx w15:paraId="AAAA0003"/></w15:commentsEx>' % self.W15)
        res = M.docx_annotations(str(self.docx(body, {'word/comments.xml': comments, 'word/commentsExtended.xml': ext})))
        got = {c['id']: (c['anchor'], c['text'], c['reply_to'], c['done'], c['paragraph']) for c in res['comments']}
        self.assertEqual(got['0'][:4], ('clearly / robust', 'Too strong?', '', True))
        self.assertEqual(got['1'][2:4], ('0', False))
        self.assertEqual((got['2'][0], got['2'][4]), ('', 'Another sentence.'))

    def test_revisions_merge_fragments_and_flag_remarks_typed_into_the_text(self):
        body = (p(r('The scale ') + ins(r('was ')) + ins(r('validated')) + r(' in outpatients.') + ins(r('（这一段是否需要再概括？）')) + dele('clearly '))
                + p(r('Conclusion text'), mark='del')
                + p('<w:r><w:rPr><w:b/><w:rPrChange %s><w:rPr/></w:rPrChange></w:rPr><w:t>Key result.</w:t></w:r>' % (REV % 11))
                + p(r('We thank ') + ins(r('the participants.'))))
        res = M.docx_annotations(str(self.docx(body)))
        self.assertEqual(res['language'], 'en')
        self.assertEqual([(e['type'], e['text'], e['remark']) for e in res['revisions']],
                         [('插入', 'was validated', False), ('插入', '（这一段是否需要再概括？）', True), ('删除', 'clearly ', False),
                          ('段落合并', '', False), ('格式', 'Key result.', False), ('插入', 'the participants.', False)])

    def test_cli_prints_report_and_will_not_overwrite_json(self):
        path = self.docx(p(r('Text ') + ins(r('（请作者核对）'))))
        out = self.base/'notes.json'
        cmd = [sys.executable, str(ROOT/'scripts'/'mslib.py'), 'annotations', str(path), '--json', str(out)]
        first = subprocess.run(cmd, capture_output=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn('⚑', first.stdout.decode('utf-8'))
        self.assertTrue(json.loads(out.read_text(encoding='utf-8'))['revisions'][0]['remark'])
        self.assertEqual(subprocess.run(cmd, capture_output=True).returncode, 2)


class DeliveryWord(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.base = Path(self.tmp.name)

    def entry(self, body, role, extra=None, name='paper.docx'):
        path = self.base/name
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('word/document.xml', '<w:document %s><w:body>%s</w:body></w:document>' % (NSDECL, body))
            for k, v in (extra or {}).items():
                z.writestr(k, v)
        return dict(id='doc', path=name, role=role, sha256=hashlib.sha256(path.read_bytes()).hexdigest())

    def report(self, entry, **kw):
        return D.evaluate(dict(schema_version=1, files=[entry], required_roles=[entry['role']], displays=[], **kw), self.base)

    def codes(self, report, severity='error'):
        return [f['code'] for f in report['findings'] if f['severity'] == severity]

    def test_deleted_placeholder_is_resolved_but_inserted_one_is_not(self):
        done = self.entry(p(r('Funding: ') + dele('[Authors to add: grant number]') + ins(r('Grant 123.'))), 'manuscript_marked')
        self.assertNotIn('placeholder', self.codes(self.report(done)))
        todo = self.entry(p(r('Funding: ') + ins(r('[TBD]'))), 'manuscript_marked', name='todo.docx')
        self.assertIn('placeholder', self.codes(self.report(todo)))

    def test_anonymity_reads_people_revision_authors_fields_links_and_variables(self):
        people = ('<w15:people xmlns:w15="http://schemas.microsoft.com/office/word/2012/wordml"><w15:person w15:author="Zhang San">'
                  '<w15:presenceInfo w15:providerId="AD" w15:userId="S::zs@uni.example.edu::1"/></w15:person></w15:people>')
        rels = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/attachedTemplate" '
                'Target="file:///C:/Users/zhangsan/Templates/Normal.dotm" TargetMode="External"/></Relationships>')
        settings = '<w:settings xmlns:w="%s"><w:docVars><w:docVar w:name="lab" w:val="Smith Lab"/></w:docVars></w:settings>' % WNS
        field = ('<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText>HYPERLINK "https://lab.example.org/kim"</w:instrText></w:r>'
                 '<w:r><w:fldChar w:fldCharType="separate"/></w:r>' + r('lab page') + '<w:r><w:fldChar w:fldCharType="end"/></w:r>')
        body = p(r('Anonymous text. ') + field) + p(dele('Li Si') + r('Method.'))
        e = self.entry(body, 'anonymous_manuscript', {'word/people.xml': people, 'word/_rels/settings.xml.rels': rels, 'word/settings.xml': settings})
        rep = self.report(e, anonymity=dict(file_ids=['doc'], terms=['zhangsan', 'Smith Lab', 'lab.example.org/kim', 'Li Si']))
        clues = sorted(f['message'] for f in rep['findings'] if f['code'] == 'anonymity_clue')
        self.assertEqual(len(clues), 4, clues)
        self.assertIn('anonymity_identifier', self.codes(rep, 'warn'))
        people_warn = [f['message'] for f in rep['findings'] if f['code'] == 'anonymity_people']
        self.assertTrue(people_warn and 'Zhang San' in people_warn[0] and 'Reviser' in people_warn[0], people_warn)

    def test_generic_author_labels_are_not_listed(self):
        e = self.entry(p(r('Text.')), 'anonymous_manuscript',
                       {'word/comments.xml': '<w:comments xmlns:w="%s"><w:comment w:id="0" w:author="Author 1"><w:p/></w:comment></w:comments>' % WNS,
                        'docProps/core.xml': '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
                                             'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:creator>python-docx</dc:creator></cp:coreProperties>'})
        rep = self.report(e, anonymity=dict(file_ids=['doc'], terms=[]))
        self.assertNotIn('anonymity_people', [f['code'] for f in rep['findings']])

    def test_chinese_left_in_an_english_file_is_flagged(self):
        en = self.base/'paper.md'; en.write_text('The effect was small in outpatients.（这一段需要再看看）\n', encoding='utf-8')
        entry = dict(id='doc', path='paper.md', role='manuscript_clean', sha256=hashlib.sha256(en.read_bytes()).hexdigest())
        self.assertIn('foreign_script', self.codes(self.report(entry), 'warn'))
        zh = self.base/'zh.md'; zh.write_text('本研究发现，反馈可见性与再次求助相关（effect size 较小）。\n', encoding='utf-8')
        entry = dict(id='doc', path='zh.md', role='manuscript_clean', sha256=hashlib.sha256(zh.read_bytes()).hexdigest())
        self.assertNotIn('foreign_script', self.codes(self.report(entry), 'warn'))


if __name__ == '__main__':
    unittest.main()
