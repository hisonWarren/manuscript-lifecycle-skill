#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lit_evidence.py — 文献证据阶梯：书目/DOI（L1）、版本状态（L2）、主张支持（L3）、写法对标（L4）分开记账，
并拦下没有依据的“DOI 已核实”“已完成同类文献对标”这类说法。上层成功不会自动点亮下层。

  python lit_evidence.py resolve --ledger citation_ledger.csv --out ledger_resolved.csv [--online]
         [--sources crossref,openalex] [--fixtures 已保存的注册库记录目录] [--save-raw 目录] [--mailto 邮箱]
  python lit_evidence.py check [--ledger citation_ledger.csv] [--text 作者说明.md 稿件.md STATUS.md …]
         [--execution EXECUTE|EXECUTE+NET|REASONING-ONLY] [--benchmark-mode distribution|domain_pack|case|none]
         [--benchmark-report 对标报告] [--benchmark-corpus 语料目录或清单] [--min-distribution 8] [--report out.md] [--json out.json]

resolve：逐个 DOI 查 Crossref 与 OpenAlex 的注册记录（--online），或读取保存好的记录（--fixtures，文件名
crossref_<DOI>.json / openalex_<DOI>.json，“/”换成“_”）。写出新的台账（不覆盖原台账）：doi_status、identity（题名、
第一作者、年份是否对得上）、version_status（Crossref updated-by 与 OpenAlex is_retracted）、tool、checked_on。
请求了在线核对却没查成，记 not_verified，不能写成已核实。命中注册库只证明书目存在，不证明原文支持本句主张。

check：核对台账字段（枚举、主张类型与访问程度是否相称、版本信号是否写了影响），并扫描作者说明、稿件、状态页、
审查与回复里的说法，按 references/23 的 F01–F16 判定。退出码：0 没有 FAIL；1 有 FAIL；2 输入错误。
脚本只用 Python 标准库。查不到 ≠ 伪造；未见撤稿 ≠ 文献可靠；DOI 对得上 ≠ 引得对。
"""
import argparse
import csv
import datetime
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mslib as M  # noqa: E402

CITATION_ACCESS = ("fulltext", "abstract", "metadata", "metadata_web", "unresolved")
DOI_STATUS = ("resolved_crossref", "resolved_openalex", "resolved_other", "not_in_index", "not_verified", "format_only", "unchecked")
VERSION_STATUS = ("checked_clean", "correction", "retracted", "expression_of_concern", "unchecked", "inconclusive")
IDENTITY = ("matched", "mismatch", "unchecked")
RELATION = ("supports", "partially_supports", "does_not_support", "contradicts", "unchecked")
CLAIM_TYPES = ("number", "method", "mechanism", "comparison", "finding", "existence", "background", "bibliographic")
BENCHMARK_MODES = ("distribution", "domain_pack", "case", "none")
EXECUTION = ("EXECUTE", "EXECUTE+NET", "REASONING-ONLY")
RESOLVED = {"resolved_crossref", "resolved_openalex", "resolved_other"}
# 主张类型 → 至少需要的访问程度
NEEDS = {"number": {"fulltext"}, "method": {"fulltext"}, "mechanism": {"fulltext"}, "comparison": {"fulltext"}, "finding": {"fulltext"},
         "existence": {"fulltext", "abstract"}, "background": {"fulltext", "abstract"},
         "bibliographic": {"fulltext", "abstract", "metadata", "metadata_web"}}
COLUMNS = ["id", "claim_location", "claim_text", "claim_type", "citation_id", "doi_or_url", "ref_title", "ref_first_author", "ref_year",
           "doi_status", "identity", "version_status", "version_source", "version_checked_at", "citation_access", "relation",
           "source_locator", "source_passage", "tool", "checked_on", "source_sha256", "reviewer", "notes"]
ALIASES = {"access_level": "citation_access", "correction_retraction_checked_at": "version_checked_at", "reason": "notes"}
DOI_RX = re.compile(r"10\.\d{4,9}/[^\s\"<>|]+", re.I)
CROSSREF_BASE = os.environ.get("LIT_EVIDENCE_CROSSREF_BASE", "https://api.crossref.org")
OPENALEX_BASE = os.environ.get("LIT_EVIDENCE_OPENALEX_BASE", "https://api.openalex.org")
NEG = re.compile(r"未|没有|尚未|不能|无法|不得|禁止|并非|不是|\bnot\b|\bno\b|\bnever\b|unverified|cannot|n't|without", re.I)


def today():
    return datetime.date.today().isoformat()


def norm(s):
    return "".join(c for c in unicodedata.normalize("NFKC", s or "").casefold() if c.isalnum())


def doi_of(s):
    m = DOI_RX.search(s or "")
    return m.group(0).rstrip(".,;)]").lower() if m else ""


def safe(doi):
    return re.sub(r"[^0-9a-z._-]+", "_", doi.lower())


def read_ledger(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        r = {(ALIASES.get(k, k) if k else k): (v or "").strip() for k, v in r.items()}
        for c in COLUMNS:
            r.setdefault(c, "")
        out.append(r)
    return out


def write_ledger(path, rows):
    keys = COLUMNS + sorted({k for r in rows for k in r if k and k not in COLUMNS})
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "x", encoding="utf-8", newline="") as f:   # 只新建，不覆盖原台账
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------- resolve
def fetch(url, mailto):
    ua = "manuscript-lifecycle-lit-evidence/1.0" + (" (mailto:%s)" % mailto if mailto else "")
    headers = {"User-Agent": ua, "Accept": "application/json"}
    key = os.environ.get("OPENALEX_API_KEY")
    if key and url.startswith(OPENALEX_BASE):
        url += ("&" if "?" in url else "?") + "api_key=" + urllib.parse.quote(key)
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def crossref_identity(rec, row):
    t = (rec.get("title") or [""])[0]
    fam = ((rec.get("author") or [{}])[0] or {}).get("family", "")
    yr = ""
    for k in ("issued", "published", "published-print", "published-online"):
        dp = (rec.get(k) or {}).get("date-parts") or []
        if dp and dp[0] and dp[0][0]:
            yr = str(dp[0][0])
            break
    return t, fam, yr


def openalex_identity(rec, row):
    t = rec.get("title") or rec.get("display_name") or ""
    name = (((rec.get("authorships") or [{}])[0] or {}).get("author") or {}).get("display_name", "")
    return t, (name.split()[-1] if name else ""), str(rec.get("publication_year") or "")


def identity_of(row, t, fam, yr):
    want_t, want_a, want_y = row.get("ref_title"), row.get("ref_first_author"), row.get("ref_year")
    if not (want_t or want_a or want_y):
        return "unchecked", "台账没有填 ref_title / ref_first_author / ref_year，未比对书目"
    bad = []
    if want_t and norm(want_t) not in norm(t) and norm(t) not in norm(want_t):
        bad.append("题名“%s”≠注册库“%s”" % (want_t[:60], t[:60]))
    if want_a and norm(want_a) not in norm(fam):
        bad.append("第一作者“%s”≠“%s”" % (want_a, fam))
    if want_y and yr and abs(int(re.sub(r"\D", "", want_y) or 0) - int(re.sub(r"\D", "", yr) or 0)) > 1:
        bad.append("年份 %s≠%s" % (want_y, yr))
    return ("mismatch", "；".join(bad)) if bad else ("matched", "")


VERSION_MAP = [(r"retraction|withdrawal|removal|partial[_ -]?retraction", "retracted"),
               (r"expression[_ -]?of[_ -]?concern|concern", "expression_of_concern"),
               (r"correction|erratum|corrigendum|addendum|clarification", "correction")]


def crossref_version(rec):
    ups = rec.get("updated-by") or []
    found = []
    for u in ups:
        typ = (u.get("type") or u.get("label") or "").lower()
        for rx, st in VERSION_MAP:
            if re.search(rx, typ):
                found.append((st, "%s %s (%s)" % (u.get("type") or u.get("label"), u.get("DOI", ""), u.get("source", ""))))
                break
        else:
            found.append(("inconclusive", "updated-by %s %s" % (typ, u.get("DOI", ""))))
    if not found:
        return "checked_clean", "Crossref updated-by 未见更正、撤稿或关注声明（未命中≠已证明没有问题）"
    order = ["retracted", "expression_of_concern", "correction", "inconclusive"]
    st = min((f[0] for f in found), key=order.index)
    return st, "；".join(f[1] for f in found)


def resolve(a):
    rows = read_ledger(a.ledger)
    if not rows:
        print("台账为空", file=sys.stderr)
        return 2
    if os.path.exists(a.out):
        print("输出文件已存在：%s（换一个文件名，不覆盖原台账）" % a.out, file=sys.stderr)
        return 2
    srcs = [s.strip() for s in a.sources.split(",") if s.strip()]
    cache, raw_out = {}, a.save_raw
    if raw_out:
        os.makedirs(raw_out, exist_ok=True)
    counts = {}
    for r in rows:
        doi = doi_of(r.get("doi_or_url"))
        if not doi:
            if not r["doi_status"]:
                r["doi_status"] = "unchecked"
            continue
        if doi not in cache:
            res = {"crossref": None, "openalex": None, "errors": [], "tool": []}
            for src in srcs:
                fx = os.path.join(a.fixtures, "%s_%s.json" % (src, safe(doi))) if a.fixtures else ""
                try:
                    if fx and os.path.exists(fx):
                        with open(fx, encoding="utf-8") as f:
                            rec = json.load(f)
                        res["tool"].append("%s(saved:%s)" % (src, os.path.basename(fx)))
                    elif a.online:
                        url = (CROSSREF_BASE + "/works/" + urllib.parse.quote(doi)) if src == "crossref" else (OPENALEX_BASE + "/works/doi:" + urllib.parse.quote(doi))
                        rec = fetch(url, a.mailto)
                        res["tool"].append("%s(api %s)" % (src, today()))
                        if raw_out:
                            p = os.path.join(raw_out, "%s_%s.json" % (src, safe(doi)))
                            if not os.path.exists(p):
                                with open(p, "w", encoding="utf-8") as f:
                                    json.dump(rec, f, ensure_ascii=False, indent=1)
                    else:
                        continue
                    res[src] = rec.get("message", rec) if src == "crossref" else rec
                except urllib.error.HTTPError as e:
                    res["errors"].append("%s HTTP %s" % (src, e.code))
                    if e.code == 404:
                        res.setdefault("not_found", []).append(src)
                except (urllib.error.URLError, OSError, ValueError) as e:
                    res["errors"].append("%s %s" % (src, str(e)[:60]))
            cache[doi] = res
        res = cache[doi]
        note = []
        if res["crossref"] is not None:
            r["doi_status"] = "resolved_crossref"
            t, fam, yr = crossref_identity(res["crossref"], r)
            r["identity"], why = identity_of(r, t, fam, yr)
            r["version_status"], r["version_source"] = crossref_version(res["crossref"])
            r["version_checked_at"] = today()
        elif res["openalex"] is not None:
            r["doi_status"] = "resolved_openalex"
            t, fam, yr = openalex_identity(res["openalex"], r)
            r["identity"], why = identity_of(r, t, fam, yr)
            why = why
        else:
            why = ""
            if res.get("not_found") and len(res["not_found"]) == len(srcs):
                r["doi_status"] = "not_in_index"
                note.append("所查注册库都没有这个 DOI：可能在其他注册机构，也可能写错；不等于伪造")
            elif a.online or a.fixtures:
                r["doi_status"] = "not_verified"
                note.append("请求了核对但没完成：%s" % ("；".join(res["errors"]) or "没有保存的记录"))
            else:
                r["doi_status"] = r["doi_status"] if r["doi_status"] in RESOLVED else "format_only"
        if res["openalex"] is not None:
            if res["openalex"].get("is_retracted"):
                r["version_status"], r["version_source"] = "retracted", "OpenAlex is_retracted=true；" + r.get("version_source", "")
            elif res["crossref"] is None and r["version_status"] in ("", "unchecked"):
                r["version_status"], r["version_source"] = "inconclusive", "只有 OpenAlex is_retracted=false；未查 Crossref updated-by、Retraction Watch 或出版商页"
                r["version_checked_at"] = today()
            oa = (res["openalex"].get("open_access") or {})
            if oa.get("oa_url"):
                note.append("开放全文入口：%s（读到全文后才能把 citation_access 记为 fulltext）" % oa["oa_url"])
        if why:
            note.append(why)
        if res["tool"]:
            r["tool"] = "；".join(res["tool"])
            r["checked_on"] = today()
        if note:
            r["notes"] = (r["notes"] + "；" if r["notes"] else "") + "；".join(note)
        counts[r["doi_status"]] = counts.get(r["doi_status"], 0) + 1
    write_ledger(a.out, rows)
    print("已写 %s：%s。命中注册库只说明书目存在；主张是否被原文支持，要读全文后在 relation 与 citation_access 里记。"
          % (a.out, "，".join("%s %d" % kv for kv in sorted(counts.items())) or "没有 DOI"))
    return 0


# ---------------------------------------------------------------- check
CLAIMS = [
    ("F01", r"DOI\s*(?:均|都|全部)?已(?:经)?核(?:实|对)|DOIs?\s+(?:were|have been|are)?\s*(?:all\s+)?(?:verified|validated|confirmed)|已核实(?:全部)?(?:DOI|文献|引文|参考文献)|references?\s+(?:were|have been)\s+(?:all\s+)?verified"),
    ("F03", r"引文(?:均|都)?(?:正确|支持)|文献(?:均|都)?支持(?:该|这一|上述)?(?:结论|主张)|(?:claims?|statements?)\s+(?:are|were)\s+supported\s+by\s+(?:the\s+)?(?:cited|references)|citations?\s+(?:support|confirm)\s+(?:the|this|these)"),
    ("F04", r"已(?:经)?完成(?:了)?(?:同类)?(?:文献)?(?:的)?(?:分布)?对标|(?:同类文献|分布)对标(?:已|均)?完成|benchmark(?:ed|ing)\s+(?:against|with)\s+(?:comparable|published|matched)|benchmarking\s+(?:was|has been)\s+completed|distribution\s+benchmark"),
    ("F05", r"(?:百分位|分位数?|p[1-9]0\b|p95|percentile|高于全部|低于全部|同类(?:文献)?(?:中)?(?:少见|罕见|常见))"),
    ("F06", r"(?:领域包|domain[ _-]?pack)[^。.\n]{0,40}(?:近邻|matched|neighbou?r)[^。.\n]{0,10}(?:全文|full[- ]?texts?|papers)"),
    ("F07", r"未(?:发现|见|检出)撤稿[^。.\n]{0,20}(?:可靠|没有问题|可信|无误)|no\s+retractions?[^.\n]{0,40}(?:reliable|trustworthy|sound|valid|credible)|not\s+(?:been\s+)?retracted[^.\n]{0,30}(?:therefore|thus|so|hence)[^.\n]{0,20}(?:reliable|valid|sound)"),
    ("F08", r"据记忆|凭记忆|根据(?:我的)?(?:训练|记忆)|from\s+(?:my\s+)?memory|based\s+on\s+(?:my\s+)?training|as\s+I\s+recall|I\s+remember\s+(?:that|this)"),
    ("F09", r"机械(?:地)?核(?:实|对)|mechanically\s+verified|programmatically\s+verified|automatically\s+verified"),
    ("F10", r"(?:已|查询了|查了|核对了|通过)\s*(?:Crossref|OpenAlex|Retraction Watch)|(?:queried|checked|looked\s+up|verified\s+(?:with|via|against))\s+(?:Crossref|OpenAlex|Retraction Watch)"),
    ("F11", r"MCP[^。.\n]{0,20}(?:未安装|没有安装|not\s+installed|missing|unavailable)[^。.\n]{0,40}(?:损坏|不能用|无法使用|broken|unusable|cannot\s+(?:be\s+)?used?)|(?:skill|技能)[^。.\n]{0,10}(?:损坏|broken)[^。.\n]{0,30}MCP"),
    ("F16", r"已核(?:实|对)?(?:了)?(?:全部|所有)?(?:文献|引文)|文献(?:均|都)?已核|(?:checked|verified)\s+(?:all\s+)?(?:the\s+)?(?:references|citations|literature)|citations?\s+(?:were|have been)\s+(?:checked|verified)"),
]
BENCH_CTX = re.compile(r"对标|同类文献|已发表论文|领域包|comparable|published papers|benchmark|domain pack|corpus|语料", re.I)


def ledger_issues(rows, execution):
    out = []
    for r in rows:
        rid = r.get("id") or r.get("citation_id") or "?"
        tag = "台账 %s" % rid
        for col, allowed in (("citation_access", CITATION_ACCESS), ("doi_status", DOI_STATUS), ("version_status", VERSION_STATUS),
                             ("identity", IDENTITY), ("relation", RELATION), ("claim_type", CLAIM_TYPES)):
            v = r.get(col, "")
            if v and v not in allowed:
                out.append(("E", tag, "%s=%s 不是允许的取值（%s）" % (col, v, "/".join(allowed))))
        carrying = bool(r.get("claim_text"))
        acc, rel, ctype = r.get("citation_access", ""), r.get("relation", ""), r.get("claim_type", "")
        if carrying and not acc:
            out.append(("F14", tag, "承重引文没有登记 citation_access（fulltext/abstract/metadata/metadata_web/unresolved）"))
        if rel in ("supports", "partially_supports"):
            need = NEEDS.get(ctype or "finding", {"fulltext"})
            if acc not in need:
                out.append(("F14", tag, "relation=%s，但 claim_type=%s 需要 %s，实际访问程度是 %s" % (rel, ctype or "finding(默认)", "/".join(sorted(need)), acc or "空")))
        tool = r.get("tool", "")
        if r.get("doi_status") in RESOLVED:
            if not (tool and r.get("checked_on")):
                out.append(("F01", tag, "doi_status=%s 却没有写工具与日期（tool、checked_on）" % r["doi_status"]))
            if re.search(r"search|搜索", tool, re.I) and not re.search(r"api\.crossref|api\.openalex|crossref|openalex|ref_check|lit_evidence|mcp:openalex|zotero", tool, re.I):
                out.append(("F09", tag, "只用网页搜索（%s）最高只能记 metadata_web，不能记 %s" % (tool, r["doi_status"])))
            if r.get("identity") == "mismatch":
                out.append(("F13", tag, "DOI 能解析，但题名/作者/年份与参考文献条目对不上：%s" % r.get("notes", "")[:120]))
            if execution == "REASONING-ONLY" and not re.search(r"inherited|沿用|上次|saved:", tool, re.I):
                out.append(("F10", tag, "执行条件是 REASONING-ONLY，却登记了 %s（这次运行不可能联网查询；沿用旧记录要在 tool 里写“沿用”及原日期）" % r["doi_status"]))
        if re.search(r"memory|记忆|training|训练", tool, re.I) and (r.get("doi_status") not in ("", "unchecked") or acc not in ("", "unresolved")):
            out.append(("F08", tag, "模型记忆不是来源（tool=%s）：一律记 unresolved/unchecked" % tool))
        vs = r.get("version_status", "")
        if vs in ("correction", "retracted", "expression_of_concern") and not re.search(r"更正|撤稿|关注声明|correction|retract|concern|不影响|影响|affect", r.get("notes", ""), re.I):
            out.append(("F15", tag, "version_status=%s，但 notes 没写它是否影响本句引用的那一点" % vs))
        if vs == "checked_clean" and not (r.get("version_source") and r.get("version_checked_at")):
            out.append(("F07", tag, "version_status=checked_clean 要写查的来源与日期（version_source、version_checked_at）；未命中只代表当时没查到"))
    return out


def corpus_entries(spec):
    if not spec:
        return []
    if os.path.isdir(spec):
        return [os.path.join(dp, f) for dp, dn, fn in os.walk(spec) for f in fn if f.lower().endswith((".md", ".txt", ".pdf", ".docx", ".xml", ".html"))]
    with open(spec, encoding="utf-8-sig") as f:
        return [l.strip() for l in f if l.strip() and not l.startswith("#")]


def check(a):
    for p in [a.ledger] + list(a.text or []):
        if p and not os.path.exists(p):
            print("找不到 %s" % p, file=sys.stderr)
            return 2
    for v, allowed, name in ((a.execution, EXECUTION, "--execution"), (a.benchmark_mode, BENCHMARK_MODES, "--benchmark-mode")):
        if v and v not in allowed:
            print("%s 只能是 %s" % (name, "/".join(allowed)), file=sys.stderr)
            return 2
    rows = read_ledger(a.ledger) if a.ledger else []
    issues = ledger_issues(rows, a.execution) if rows else []
    carrying = [r for r in rows if r.get("claim_text")]
    all_resolved = bool(carrying) and all(r.get("doi_status") in RESOLVED and r.get("tool") and r.get("checked_on") for r in carrying if doi_of(r.get("doi_or_url")))
    support_ok = not any(i[0] == "F14" for i in issues)
    corpus = corpus_entries(a.benchmark_corpus)
    local = [c for c in corpus if not re.match(r"https?://|search:|搜索", c, re.I) and os.path.exists(c if os.path.isabs(c) else os.path.join(os.path.dirname(a.benchmark_corpus) if a.benchmark_corpus and not os.path.isdir(a.benchmark_corpus) else (a.benchmark_corpus or "."), c))]
    if a.benchmark_mode == "distribution":
        if len(corpus) != len(local):
            issues.append(("F12", "对标语料", "%d 条语料不是本地全文（网址或搜索结果）：入库、清洗、按 DOI 去重后才能进分布" % (len(corpus) - len(local))))
        if len(local) < a.min_distribution:
            issues.append(("F05", "对标语料", "benchmark_mode=distribution 要至少 %d 篇可比全文，现有 %d 篇；不足时写 case（结构个案参照）" % (a.min_distribution, len(local))))
        if not (a.benchmark_report and os.path.exists(a.benchmark_report)):
            issues.append(("F04", "对标报告", "benchmark_mode=distribution 但没有给出存在的对标报告（--benchmark-report）"))
    dist_ok = a.benchmark_mode == "distribution" and len(local) >= a.min_distribution and bool(a.benchmark_report and os.path.exists(a.benchmark_report)) and len(corpus) == len(local)
    for path in a.text or []:
        for ln, line in enumerate(M.load_text(path).split("\n"), 1):
            for s in M.sentences(line) if line.strip() else []:
                for fid, rx in CLAIMS:
                    m = re.search(rx, s, re.I)
                    if not m:
                        continue
                    pre = s[max(0, m.start() - 10):m.start()]
                    negated = bool(NEG.search(pre)) or bool(re.search(r"(?:未|没有|尚未|不能|无法|not|no)\s*$", pre, re.I))
                    where = "%s:%d" % (os.path.basename(path), ln)
                    ex = s.strip()[:160]
                    if fid in ("F01", "F16"):
                        if negated:
                            continue
                        if not rows:
                            issues.append(("F16", where, "说已核文献/DOI，但没有引文台账（--ledger）：%s" % ex))
                        elif not all_resolved:
                            issues.append(("F01" if fid == "F01" else "F16", where, "说已核实，但台账里还有未解析或缺工具/日期的承重引文：%s" % ex))
                        elif any(r.get("doi_status") == "not_verified" for r in rows):
                            issues.append(("F02", where, "台账有 not_verified 的条目，文字却说已核实：%s" % ex))
                        elif any(r.get("identity") == "mismatch" for r in rows):
                            issues.append(("F13", where, "台账有书目对不上的条目，文字却说已核实：%s" % ex))
                    elif fid == "F03":
                        if negated:
                            continue
                        if not rows or not support_ok or not any(r.get("relation") in ("supports", "partially_supports") for r in rows):
                            issues.append(("F03", where, "说引文支持结论，但台账没有相称访问程度的支持记录（DOI 能解析≠支持主张）：%s" % ex))
                    elif fid == "F04":
                        if negated:
                            continue
                        if not dist_ok:
                            issues.append(("F04", where, "说已完成同类文献对标，但 benchmark_mode 不是 distribution，或缺可比全文与报告（现为 %s）：%s" % (a.benchmark_mode or "未写", ex)))
                    elif fid == "F05":
                        if BENCH_CTX.search(s) and not negated and not dist_ok and a.benchmark_mode != "domain_pack":
                            issues.append(("F05", where, "用分位、“同类少见”这类分布口吻，但对标不是 distribution（现为 %s）：%s" % (a.benchmark_mode or "未写", ex)))
                    elif fid == "F06":
                        if not negated:
                            issues.append(("F06", where, "领域包是统计基线，不是近邻全文；写“领域包基线参照”：%s" % ex))
                    elif fid == "F07":
                        issues.append(("F07", where, "未见撤稿只代表当时没查到，不能当作文献可靠的证据：%s" % ex))
                    elif fid == "F08":
                        if not negated:
                            issues.append(("F08", where, "据记忆的书目或内容不能支撑承重句：%s" % ex))
                    elif fid == "F09":
                        if not negated and (a.execution == "REASONING-ONLY" or not any(r.get("doi_status") in RESOLVED and not re.search(r"search|搜索", r.get("tool", ""), re.I) for r in rows)):
                            issues.append(("F09", where, "说机械核实，但没有注册库记录（只有搜索或没有台账）：%s" % ex))
                    elif fid == "F10":
                        if not negated and a.execution == "REASONING-ONLY":
                            issues.append(("F10", where, "执行条件是 REASONING-ONLY，却写查过 Crossref/OpenAlex：%s" % ex))
                    elif fid == "F11":
                        issues.append(("F11", where, "MCP 是可选增强，没装不等于技能损坏；改为说明降级到了哪一层：%s" % ex))
    fails = [i for i in issues if i[0] != "E"]
    errs = [i for i in issues if i[0] == "E"]
    L = ["# 文献证据阶梯核对", "",
         "执行条件：%s；引文台账：%s（%d 行，承重 %d 行）；对标：%s，本地全文 %d 篇。FAIL %d、字段错误 %d。" % (
             a.execution or "未写", os.path.basename(a.ledger) if a.ledger else "无", len(rows), len(carrying), a.benchmark_mode or "未写",
             len(local), len(fails), len(errs)), "",
         "四层分开记账：书目存在（L1）、版本状态（L2）、主张支持（L3）、写法对标（L4）。上层成功不点亮下层；定义与允许措辞见 references/23_literature_evidence.md。", ""]
    for code, where, msg in fails + errs:
        L.append("- **%s** %s：%s" % ("字段" if code == "E" else code, where, msg))
    if not fails and not errs:
        L.append("没有发现越界说法或字段错误。这只说明说法与记录对得上，不说明引得对。")
    out = "\n".join(L) + "\n"
    if a.report:
        with M.wfile(a.report) as f:
            f.write(out)
    if a.json:
        with M.wfile(a.json) as f:
            json.dump([{"code": c, "where": w, "msg": m} for c, w, m in fails + errs], f, ensure_ascii=False, indent=1)
    print(out if not a.report else L[2])
    return 1 if (fails or errs) else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("resolve")
    r.add_argument("--ledger", required=True); r.add_argument("--out", required=True)
    r.add_argument("--online", action="store_true"); r.add_argument("--sources", default="crossref,openalex")
    r.add_argument("--fixtures", default=""); r.add_argument("--save-raw", default=""); r.add_argument("--mailto", default="")
    c = sub.add_parser("check")
    c.add_argument("--ledger", default=""); c.add_argument("--text", nargs="*", default=[])
    c.add_argument("--execution", default=""); c.add_argument("--benchmark-mode", default="")
    c.add_argument("--benchmark-report", default=""); c.add_argument("--benchmark-corpus", default="")
    c.add_argument("--min-distribution", type=int, default=8)
    c.add_argument("--report", default=""); c.add_argument("--json", default="")
    a = ap.parse_args()
    if a.cmd == "resolve":
        if not os.path.exists(a.ledger):
            print("找不到台账 %s" % a.ledger, file=sys.stderr)
            return 2
        bad = [s for s in a.sources.split(",") if s.strip() and s.strip() not in ("crossref", "openalex")]
        if bad:
            print("--sources 只认 crossref、openalex", file=sys.stderr)
            return 2
        return resolve(a)
    return check(a)


if __name__ == "__main__":
    sys.exit(main())
