"""可移植性：文本读写写明编码、命令行输出一律 UTF-8、脚本用 LF 换行。

中文 Windows 把输出接到管道或文件时默认按 GBK 编码，统计里常见的 − ² ✓ • 无法编码，脚本会在打印时崩溃；
不写 encoding 的 open()/read_text() 也会按 GBK 读 UTF-8 文件。整套测试还应在下面两种方式下各跑一遍：
  python -X warn_default_encoding -W error::EncodingWarning evals/run_evals.py
  （Linux/macOS）LC_ALL=zh_CN.GBK python evals/run_evals.py   # 需要系统里有 GBK 区域
"""
import ast
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT/'scripts'
SAMPLE = 'β = −0.21，R² ✓ •'
TEXT_SUFFIXES = {'.py', '.md', '.json', '.yaml', '.yml', '.txt', '.csv'}


def _kw(call, name):
    return next((k.value for k in call.keywords if k.arg == name), None)


def _mode(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def default_encoding_calls(path):
    """返回依赖平台默认编码的文本读写调用（行号, 说明）。"""
    found = []
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
        if not isinstance(node, ast.Call):
            continue
        f, enc = node.func, _kw(node, 'encoding') is not None
        name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ''
        owner = f.value.id if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) else ''
        if name == 'open' and (isinstance(f, ast.Name) or owner in {'io', 'codecs'}):
            mode = _mode(node.args[1]) if len(node.args) > 1 else _mode(_kw(node, 'mode')) if _kw(node, 'mode') else 'r'
            if (mode is None or 'b' not in mode) and not enc and len(node.args) < 4:
                found.append((node.lineno, 'open()'))
        elif name == 'open' and isinstance(f, ast.Attribute):
            mode = _mode(node.args[0]) if node.args else _mode(_kw(node, 'mode')) if _kw(node, 'mode') else None
            if mode is not None and not mode.strip('rwax+t') and 'b' not in mode and not enc:
                found.append((node.lineno, '.open()'))
        elif name in {'read_text', 'write_text'} and isinstance(f, ast.Attribute):
            if not enc and len(node.args) <= (0 if name == 'read_text' else 1):
                found.append((node.lineno, name))
        elif owner == 'subprocess' and name in {'run', 'check_output', 'Popen', 'call', 'check_call'}:
            text = any(k.arg in {'text', 'universal_newlines'} and not (isinstance(k.value, ast.Constant) and k.value.value is False)
                       for k in node.keywords)
            if text and not enc:
                found.append((node.lineno, 'subprocess text mode'))
        elif name in {'NamedTemporaryFile', 'TemporaryFile', 'SpooledTemporaryFile'}:
            mode = _mode(node.args[0]) if node.args else _mode(_kw(node, 'mode')) if _kw(node, 'mode') else 'w+b'
            if mode and 'b' not in mode and not enc:
                found.append((node.lineno, name))
        elif name == 'TextIOWrapper' and not enc or (owner == 'os' and name == 'popen'):
            found.append((node.lineno, name))
    return found


def cli_scripts():
    return sorted(p for p in SCRIPTS.glob('*.py') if "__name__" in p.read_text(encoding='utf-8'))


def gbk_pipe_env():
    return dict(os.environ, PYTHONIOENCODING='gbk', PYTHONUTF8='0')


class Portability(unittest.TestCase):
    def test_text_io_declares_encoding(self):
        bad = ['%s:%d %s' % (p.relative_to(ROOT), ln, what)
               for p in sorted(ROOT.rglob('*.py')) if '__pycache__' not in p.parts
               for ln, what in default_encoding_calls(p)]
        self.assertEqual(bad, [])

    def test_checker_catches_default_encoding(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)/'x.py'
            p.write_text("open('a').read()\nPath('a').read_text()\nsubprocess.run(['x'], text=True)\n"
                         "open('b', 'rb')\nopen('c', encoding='utf-8')\n", encoding='utf-8')
            self.assertEqual(sorted(ln for ln, _ in default_encoding_calls(p)), [1, 2, 3])

    def test_every_cli_writes_utf8_through_a_gbk_pipe(self):
        scripts = cli_scripts()
        self.assertGreaterEqual(len(scripts), 20)
        for script in scripts:
            # 代码本身只用 ASCII（%a 转义）：POSIX 的 GBK 区域里命令行参数无法携带 −，真实 Windows 用 UTF-16 传参没有这个限制。
            code = ('import importlib,sys; importlib.import_module(%a); print(%a); print(%a, file=sys.stderr)'
                    % (script.stem, SAMPLE, SAMPLE))
            p = subprocess.run([sys.executable, '-c', code], cwd=SCRIPTS, env=gbk_pipe_env(), capture_output=True)
            self.assertEqual(p.returncode, 0, (script.name, p.stderr[-300:]))
            self.assertIn(SAMPLE, p.stdout.decode('utf-8'), script.name)
            self.assertIn(SAMPLE, p.stderr.decode('utf-8'), script.name)

    def test_init_project_and_release_check_end_to_end_through_gbk_pipe(self):
        try:
            '研究−A'.encode(sys.getfilesystemencoding())
        except UnicodeEncodeError:
            self.skipTest('POSIX GBK 区域的文件名与参数无法含 −；各脚本的 UTF-8 输出已由上一项测试覆盖')
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)/'研究−A'
            p = subprocess.run([sys.executable, str(SCRIPTS/'init_project.py'), '--dir', str(project), '--mode', 'D'],
                               env=gbk_pipe_env(), capture_output=True)
            self.assertEqual(p.returncode, 0, p.stderr[-300:])
            self.assertIn('研究−A', p.stdout.decode('utf-8'))
            p = subprocess.run([sys.executable, str(SCRIPTS/'release_check.py'), str(Path(td)/'清单−1.json'),
                                '--report', str(Path(td)/'r.json')], env=gbk_pipe_env(), capture_output=True)
            self.assertEqual(p.returncode, 2, p.stderr[-300:])
            self.assertIn('清单−1.json', p.stdout.decode('utf-8'))

    def test_line_endings(self):
        # 脚本若用 CRLF，Linux/macOS 上 ./script.py 会找不到 "python3\r"；CSV 按 RFC 4180 允许 CRLF（csv 模块写出的领域包清单即如此）。
        bad = [str(p.relative_to(ROOT)) for p in sorted(ROOT.rglob('*'))
               if p.is_file() and '__pycache__' not in p.parts and p.suffix in TEXT_SUFFIXES - {'.csv'}
               and b'\r\n' in p.read_bytes()]
        self.assertEqual(bad, [])


if __name__ == '__main__':
    unittest.main()
