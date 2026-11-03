# -*- coding: utf-8 -*-
"""Observe corpus admission, duplicate counting, manifest identity and package isolation."""
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "domain_pack.py"


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                          capture_output=True, text=True, encoding="utf-8")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def paper(i):
    paragraph = (
        "Participants in cohort %d completed the same assessment at each planned visit. "
        "The study examined how reported symptoms varied across occasions and between participants. "
        "The estimates describe patterns in the observed sample and require comparison with other settings. "
        "Earlier reports provide context for interpreting the size and uncertainty of these associations."
    ) % i
    return "# Public study %d\n\n" % i + "\n\n".join(
        "## %s\n\n%s" % (section, paragraph)
        for section in ("Abstract", "Introduction", "Methods", "Results", "Discussion", "Conclusion"))


def front(i, **extra):
    fields = {"slug": "local%d" % i, "journal": "Metadata Journal", "year": "2024",
              "genre": "metadata_genre", "license_note": "Private corpus; statistics only",
              "doi": "10.9999/test.%d" % i}
    fields.update(extra)
    return "---\n" + "\n".join("%s: %s" % item for item in fields.items()) + "\n---\n\n"


def manifest(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["file", "id", "title", "journal", "year", "genre", "license"])
        writer.writeheader()
        writer.writerows(rows)
    return path


class DomainCorpusIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.temp.name)
        cls.corpus = cls.base / "corpus"
        rows = []
        for i in range(1, 9):
            write(cls.corpus / "group" / ("p%d.md" % i), front(i) + paper(i))
            rows.append({"file": "group/p%d.md" % i, "id": "local%d" % i,
                         "title": "Public study %d" % i, "journal": "Curated Journal",
                         "year": "2025", "genre": "experiment", "license": "Private corpus; statistics only"})
        cls.manifest = manifest(cls.base / "manifest.csv", rows)
        # Same body with different YAML is the duplicate encountered in the supplied corpus.
        write(cls.corpus / "z_metadata_copy.md", front(1, slug="new-copy", doi="", license_note="new note") + paper(1))
        # A local manifest id must not hide the DOI; URI and doi: spellings are one identity.
        write(cls.corpus / "z_doi_copy.md", front(2, doi="'https://doi.org/10.9999/TEST.2'") +
              paper(2).replace("Public study 2", "Public study two"))
        write(cls.corpus / "z_marked_partial.md", front(90, completeness="abstract_only") + paper(90))
        write(cls.corpus / "z_abstract.md", front(91) + "## Abstract\n\n" +
              paper(91).split("## Abstract\n\n", 1)[1].split("## Introduction", 1)[0])
        write(cls.corpus / "00_candidates_index.md", front(92) + paper(92))
        cls.pack = cls.base / "pack"
        result = cls.build(cls.corpus, cls.pack, cls.manifest)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @staticmethod
    def build(corpus, out, source_manifest=None):
        args = ["build", "--corpus", corpus, "--id", "integrity_en", "--label", "Corpus integrity",
                "--lang", "en", "--out", out, "--boot", "1"]
        if source_manifest:
            args += ["--manifest", source_manifest]
        return run(*args)

    def test_duplicates_and_nonfulltext_do_not_inflate_the_pack(self):
        profile = json.loads((self.pack / "profile.json").read_text(encoding="utf-8"))
        self.assertEqual(profile["n_papers"], 8)
        bench = json.loads((self.pack / "bench_baseline.json").read_text(encoding="utf-8"))
        self.assertEqual({item["id"] for item in bench["exemplars"]},
                         {"10.9999/test.%d" % i for i in range(1, 9)})
        self.assertEqual(len({item["body_sha256"] for item in bench["exemplars"]}), 8)
        self.assertEqual(len(bench["exemplars"]), 8)
        # The exclusion record remains reviewable without copying any manuscript text.
        report = (self.pack / "build_report.md").read_text(encoding="utf-8")
        for name in ("z_metadata_copy.md", "z_doi_copy.md", "z_marked_partial.md", "z_abstract.md", "00_candidates_index.md"):
            self.assertIn(name, report)
        self.assertNotIn("Participants in cohort", report)

    def test_relative_manifest_paths_supply_the_actual_metadata(self):
        with (self.pack / "corpus_manifest.csv").open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 8)
        self.assertEqual({row["journal"] for row in rows}, {"Curated Journal"})
        self.assertEqual({row["genre"] for row in rows}, {"experiment"})
        self.assertEqual({row["year"] for row in rows}, {"2025"})
        result = run("check", self.pack)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_changed_metadata_cannot_hide_self_comparison_from_any_consumer(self):
        duplicate = self.corpus / "z_metadata_copy.md"
        with tempfile.TemporaryDirectory(dir=self.base) as tmp:
            tmp = Path(tmp)
            cases = [
                ("bench_profile.py", ["--baseline", self.pack, "--draft", "Copy=" + str(duplicate), "--report", tmp / "bench.md"]),
                ("phrase_contrast.py", ["--baseline", self.pack, "--draft", "Copy=" + str(duplicate), "--report", tmp / "phrase.md"]),
                ("language_plan.py", ["scan", "--baseline", self.pack, "--doc", "Copy=" + str(duplicate), "--plan", tmp / "plan.csv"]),
                ("section_lint.py", [duplicate, "--domain", self.pack, "--json", tmp / "lint.json"]),
            ]
            for script, args in cases:
                with self.subTest(script=script):
                    result = subprocess.run([sys.executable, str(ROOT / "scripts" / script), *map(str, args)],
                                            capture_output=True, text=True, encoding="utf-8")
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertFalse(any(tmp.iterdir()), "self-comparison must not publish a report")

    def test_only_partial_sources_fail_without_creating_a_pack(self):
        with tempfile.TemporaryDirectory(dir=self.base) as tmp:
            corpus, out = Path(tmp) / "corpus", Path(tmp) / "pack"
            for i in range(3):
                write(corpus / ("partial%d.md" % i), front(i, completeness="abstract_only") + paper(i))
            result = self.build(corpus, out)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertFalse(out.exists())
            self.assertIn("abstract_only", result.stdout + result.stderr)

    def test_ambiguous_manifest_basename_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=self.base) as tmp:
            corpus, out = Path(tmp) / "corpus", Path(tmp) / "pack"
            write(corpus / "one" / "same.md", front(1) + paper(1))
            write(corpus / "two" / "same.md", front(2) + paper(2))
            write(corpus / "third.md", front(3) + paper(3))
            source_manifest = manifest(Path(tmp) / "manifest.csv", [{"file": "same.md", "genre": "experiment"}])
            result = self.build(corpus, out, source_manifest)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertFalse(out.exists())
            self.assertIn("same.md", result.stdout + result.stderr)

    def test_check_detects_fulltext_and_build_preserves_it_without_overwriting(self):
        with tempfile.TemporaryDirectory(dir=self.base) as tmp:
            out = Path(tmp) / "pack"
            shutil.copytree(self.pack, out)
            leaked = write(out / "private_fulltext.md", paper(70))
            before = {p.name: p.read_bytes() for p in out.iterdir()}
            checked = run("check", out)
            self.assertEqual(checked.returncode, 1, checked.stdout + checked.stderr)
            self.assertIn(leaked.name, checked.stdout + checked.stderr)
            built = self.build(self.corpus, out, self.manifest)
            self.assertEqual(built.returncode, 2, built.stdout + built.stderr)
            self.assertEqual(before, {p.name: p.read_bytes() for p in out.iterdir()})

    def test_check_detects_corpus_subdirectories(self):
        with tempfile.TemporaryDirectory(dir=self.base) as tmp:
            out = Path(tmp) / "pack"
            shutil.copytree(self.pack, out)
            write(out / "sources" / "fulltext.md", paper(70))
            result = run("check", out)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("sources", result.stdout + result.stderr)

    def test_lint_refuses_a_different_language_pack(self):
        with tempfile.TemporaryDirectory(dir=self.base) as tmp:
            draft = write(Path(tmp) / "zh.md", '## 讨论\n\n本研究发现学习投入与学习成绩相关，但无法确定因果关系。\n')
            report = Path(tmp) / "lint.json"
            result = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'section_lint.py'), str(draft),
                                     '--domain', str(self.pack), '--json', str(report)], capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(report.exists())

    def test_prevalence_cannot_downgrade_design_contradictions(self):
        with tempfile.TemporaryDirectory(dir=self.base) as tmp:
            pack = Path(tmp) / 'pack'
            shutil.copytree(self.pack, pack)
            rates_file = pack / 'rule_rates.json'
            rates = json.loads(rates_file.read_text(encoding='utf-8'))
            rates['rules']['G2'] = {'papers': 8, 'n': 8, 'share': 1.0, 'levels': {'MUST': 8}}
            rates_file.write_text(json.dumps(rates), encoding='utf-8')
            draft = write(Path(tmp) / 'draft.md', '## Discussion\n\nIn this randomized trial, students were randomly assigned to tutoring.\n')
            report = Path(tmp) / 'lint.json'
            result = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'section_lint.py'), str(draft),
                                     '--domain', str(pack), '--design', 'cohort', '--json', str(report)], capture_output=True)
            self.assertEqual(result.returncode, 1)
            items = json.loads(report.read_text(encoding='utf-8'))
            self.assertTrue(any(i['code'] == 'G2' and i['level'] == 'MUST' for i in items))


if __name__ == "__main__":
    unittest.main()
