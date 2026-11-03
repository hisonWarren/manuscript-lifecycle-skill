#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
domain_pack.py — 领域包：把一个领域的对标语料变成只含统计量的基线，供各检查工具直接使用。

  构建：python domain_pack.py build --corpus 语料目录/ [--corpus …] --id psychology_zh --label "心理学（中文期刊实证论文）"
              --field 心理学 [--manifest 清单.csv] [--genre-map 文件=体裁 …] --out assets/domains/psychology_zh [--boot 60]
  检查：python domain_pack.py check assets/domains/psychology_zh
  列出：python domain_pack.py list [assets/domains]

为什么需要它：同一条规则在不同领域、语言、体裁中意义不同。实测 16 篇《心理学报》论文中，"进行"出现 556 次、
11 篇没有单列统计分析小节、15 篇讨论首段没有英文论文常见的概括收束句；把英文经验当成通用规则，会把领域常态报成问题。
领域包让 bench_profile（--baseline）、section_lint（--domain）、phrase_contrast（--baseline）、language_plan（--baseline）
以同领域已发表论文为参照，在用户手头没有对标全文时也能校准。
领域包只含：DOI/题名/期刊/年份/体裁清单，各节数值指标，模式出现率，3 词句式骨架的频数（只保留 ≥2 篇出现的），
各检查规则在已发表论文上的触发率，以及样本量稳定性与体裁差异检验结果。不含全文、句子或段落，可以放进可分享的 skill；
语料本身留在本机。构建会做隐私扫描：任何值超过 60 个字符（清单里的题名除外）即报错。
清单（--manifest）列：file（文件名或相对路径）、id（DOI 优先）、title、journal、year、genre、license；
可用 completeness 标明 fulltext/abstract_only 等状态，只有全文纳入。没有清单时读 md 的 YAML 头
（doi、title_zh、journal、genre、license），再没有就用文件名；--genre-map 可补体裁。
退出码：0 成功；1 check 发现问题；2 输入错误。
"""
import argparse
import collections
import csv
import datetime
import glob
import hashlib
import io
import json
import os
import random
import re
import statistics
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mslib as M  # noqa: E402
import bench_profile as BP  # noqa: E402
import language_plan as LP  # noqa: E402
import phrase_contrast as PC  # noqa: E402

BUILDER = "domain_pack 2"
PACK_FILES = ("profile.json", "bench_baseline.json", "phrase_baseline.json", "texture_baseline.json",
              "rule_rates.json", "corpus_manifest.csv", "build_report.md")
ROOT = os.path.dirname(HERE)
NEVER_DOWNGRADE = {"A1", "W1", "H1", "G1", "G2", "S1", "P1", "N1", "N2"}
# 只有这些固定位置允许超过 60 字符：说明文字、内容指纹、方法小标题
ALLOW_LONG = (r"^/(?:use|label|license_note|note)$", r"/(?:content|body)_sha256$", r"/methods_heads\[\d+\]$", r"/results_heads\[\d+\]$")


def sha_text(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def texture_fingerprint(catalog_text, lex, lang):
    """纹理基线依赖的内容：模式目录全文，加上词表里被目录的 lex 字段引用的键（name、name_re、name_re_cs）。
    词表里目录不引用的键（例如 N1 用的 overclaim_re）只影响别的检查，改它不会让已发出的领域包失效；
    改了被引用的键或目录本身，指纹就变，必须用 build 重建，不能只改指纹。"""
    cat = json.loads(catalog_text)
    names = {e["lex"] for e in cat.get("patterns", []) if e.get("lex") and e.get("lang", "both") in ("both", lang)}
    used = {k: lex[k] for k in sorted(lex) if not k.startswith("_") and (
        k in names or (k.endswith("_re_cs") and k[:-6] in names) or (k.endswith("_re") and k[:-3] in names))}
    return sha_text(catalog_text + "\n" + json.dumps(used, ensure_ascii=False, sort_keys=True))


def lexicon_hash(lang):
    catalog_text = open(LP.CATALOG, encoding="utf-8").read()
    lex = json.load(open(os.path.join(ROOT, "assets", "lexicons", "%s.json" % lang), encoding="utf-8"))
    return texture_fingerprint(catalog_text, lex, lang)


FRONT_MATTER = re.compile(r"^\ufeff?---[ \t]*\n(.*?)\n---[ \t]*(?:\n|$)", re.S)


def yaml_head(raw):
    m = FRONT_MATTER.match(raw)
    out = {}
    if m:
        for line in m.group(1).split("\n"):
            k, sep, v = line.partition(":")
            if sep:
                value = v.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ("\"", "'"):
                    value = value[1:-1]
                out[k.strip()] = value
    return out


def corpus_files(items):
    paths = []
    for it in items:
        if os.path.isdir(it):
            for ext in ("*.md", "*.txt", "*.docx"):
                paths += sorted(glob.glob(os.path.join(it, "**", ext), recursive=True))
        elif os.path.isfile(it):
            paths.append(it)
        else:
            raise ValueError("找不到语料：%s" % it)
    # Repeated/overlapping --corpus arguments must not make manifest basenames ambiguous.
    return list(dict.fromkeys(os.path.abspath(p) for p in paths
                              if not os.path.basename(p).lower().startswith("readme")))


def read_manifest(path):
    if not path:
        return {}
    rows = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if not row.get("file"):
                continue
            key = manifest_key(row["file"])
            if key in rows:
                raise ValueError("清单中 file 重复：%s" % row["file"])
            rows[key] = row
    return rows


def manifest_key(path):
    return os.path.normcase(os.path.normpath(path.replace("\\", "/"))).replace("\\", "/")


def manifest_row(manifest, path, basename_counts):
    """Accept a basename or a relative/absolute path; never silently select a namesake."""
    full = manifest_key(os.path.abspath(path))
    matches = [key for key in manifest if full == key or full.endswith("/" + key)]
    if not matches:
        return {}
    key = max(matches, key=lambda item: len(item.split("/")))
    if "/" not in key and basename_counts[key] > 1:
        raise ValueError("清单 file 只有文件名而语料中有同名文件，请改用相对路径：%s" % key)
    return manifest[key]


def normalized_doi(value):
    """A local manifest id is not a DOI and must not hide the article's own DOI."""
    value = (value or "").strip().strip("\"'")
    match = re.fullmatch(r"(?:https?://(?:dx\.)?doi\.org/|doi\s*:\s*)?(10\.\d{4,9}/\S+)", value, re.I)
    return match.group(1).rstrip(".,;").lower() if match else None


def excluded_source(path, meta, row):
    state = (row.get("completeness") or meta.get("completeness") or "").strip().lower().replace("-", "_")
    if state and state not in ("full", "fulltext", "full_text", "complete"):
        return "非全文（completeness=%s）" % state
    stem = os.path.splitext(os.path.basename(path))[0].lower()
    if stem.endswith("_abstract_only") or stem == "00_candidates_index":
        return "摘要占位或候选索引，不是全文"
    return ""


def unexpected_pack_files(path):
    if not os.path.isdir(path):
        return []
    return sorted(name for name in os.listdir(path)
                  if name not in PACK_FILES or not os.path.isfile(os.path.join(path, name)))


# ------------------------------------------------------------------ 稳定性与体裁差异
def metric_keys():
    return [(sec, key) for sec in BP.SECS for key, name, only, _ in BP.METRICS if not (only and sec not in only)]


def stability(ex, ks, boot, seed=7):
    """留一法：每篇已发表论文当作"稿件"，用 k 篇随机子集判定，与用其余全部论文判定比较。
    agreement = 是否标为偏离的一致率；flag_rate = 可测指标比较中被标为偏离的比例。
    分母为 comparisons（指标 × 留出论文 × 抽样重复），没有人工真值，不是误报率。"""
    rng = random.Random(seed)
    keys = metric_keys()
    out = {}
    for k in ks:
        agree = tot = flagged = 0
        for i, d in enumerate(ex):
            others = ex[:i] + ex[i + 1:]
            if k > len(others):
                continue
            full = {}
            for sec, key in keys:
                if sec not in d["sections"] or d["sections"][sec].get(key) is None:
                    continue
                s = M.summarize([e["sections"][sec].get(key) for e in others if sec in e["sections"]])
                if s:
                    full[(sec, key)] = bool(BP.verdict(d["sections"][sec][key], s))
            reps = 1 if k == len(others) else boot
            for _ in range(reps):
                sub = others if k == len(others) else rng.sample(others, k)
                for (sec, key), fv in full.items():
                    s = M.summarize([e["sections"][sec].get(key) for e in sub if sec in e["sections"]])
                    if not s:
                        continue
                    sv = bool(BP.verdict(d["sections"][sec][key], s))
                    agree += sv == fv
                    flagged += sv
                    tot += 1
        if tot:
            out[str(k)] = {"agreement": round(agree / tot, 3), "flag_rate": round(flagged / tot, 3), "comparisons": tot}
    return out


def eta_sq(groups):
    allv = [v for g in groups for v in g]
    if len(allv) < 4:
        return None
    mu = statistics.mean(allv)
    sst = sum((v - mu) ** 2 for v in allv)
    if sst == 0:
        return None
    ssb = sum(len(g) * (statistics.mean(g) - mu) ** 2 for g in groups if g)
    return ssb / sst


def genre_effect(ex, perms=300, seed=11):
    """各指标中体裁解释的方差（η²），与随机打乱体裁标签的结果比较。只用 ≥3 篇的体裁。"""
    rng = random.Random(seed)
    cnt = collections.Counter(e.get("genre") for e in ex)
    keep = [e for e in ex if e.get("genre") and cnt[e["genre"]] >= 3]
    gs = sorted({e["genre"] for e in keep})
    if len(gs) < 2:
        return None
    res = []
    for sec, key in metric_keys():
        rows = [(e["genre"], e["sections"][sec][key]) for e in keep if sec in e["sections"] and e["sections"][sec].get(key) is not None]
        if len(rows) < 6 or len({g for g, _ in rows}) < 2:
            continue
        obs = eta_sq([[v for g, v in rows if g == gg] for gg in gs])
        if obs is None:
            continue
        labels = [g for g, _ in rows]
        null = []
        for _ in range(perms):
            rng.shuffle(labels)
            e2 = eta_sq([[v for (g0, v), g in zip(rows, labels) if g == gg] for gg in gs])
            if e2 is not None:
                null.append(e2)
        null.sort()
        p95 = null[int(0.95 * (len(null) - 1))] if null else None
        res.append({"metric": "%s|%s" % (sec, key), "eta2": round(obs, 3), "null_mean": round(statistics.mean(null), 3) if null else None,
                    "null_p95": round(p95, 3) if p95 is not None else None, "beyond_chance": bool(p95 is not None and obs > p95)})
    if not res:
        return None
    return {"genres": {g: cnt[g] for g in gs}, "metrics": len(res), "beyond_chance": sum(r["beyond_chance"] for r in res),
            "expected_by_chance": round(0.05 * len(res), 1), "median_eta2": round(statistics.median(r["eta2"] for r in res), 3),
            "median_null": round(statistics.median(r["null_mean"] for r in res if r["null_mean"] is not None), 3),
            "top": sorted([r for r in res if r["beyond_chance"]], key=lambda r: -r["eta2"])[:10]}


# ------------------------------------------------------------------ 构建
def run_lint(path, bench_json):
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "lint.json")
        subprocess.run([sys.executable, os.path.join(HERE, "section_lint.py"), path, "--bench", bench_json, "--json", out],
                       capture_output=True, text=True, encoding="utf-8")
        if not os.path.exists(out):
            return None
        return json.load(open(out, encoding="utf-8"))


def privacy_scan(obj, path="", limit=60, allow=()):
    bad = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and len(k) > limit:
                bad.append(path + "/<key>")
            if k in ("text", "sents", "sentence", "path"):
                bad.append(path + "/" + k)
            bad += privacy_scan(v, path + "/" + str(k), limit, allow)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            bad += privacy_scan(v, "%s[%d]" % (path, i), limit, allow)
    elif isinstance(obj, str) and len(obj) > limit and not any(re.search(a, path) for a in allow):
        bad.append(path)
    return bad


def cmd_build(a):
    files = corpus_files(a.corpus)
    if not files:
        raise ValueError("语料为空")
    extra = unexpected_pack_files(a.out)
    if extra:
        raise ValueError("输出目录含领域包以外的文件或子目录，请使用独立目录：%s" % extra)
    man = read_manifest(a.manifest)
    basename_counts = collections.Counter(manifest_key(os.path.basename(p)) for p in files)
    gmap = dict(x.split("=", 1) for x in a.genre_map)
    words, vsha = PC.load_vocab(a.lang)
    pats = [p for p in LP.load_catalog(LP.CATALOG, a.lang) if p["level"] == "compare"]
    ex, seen_doi, seen_txt, skipped, rows, phrase, texture, kept = [], {}, {}, [], [], [], [], []
    for p in files:
        raw = open(p, encoding="utf-8-sig", errors="replace").read() if p.lower().endswith((".md", ".txt")) else ""
        meta = yaml_head(raw)
        mrow = manifest_row(man, p, basename_counts)
        reason = excluded_source(p, meta, mrow)
        if reason:
            skipped.append((os.path.basename(p), reason)); continue
        text = M.load_text(p)
        if M.detect_lang(text) != a.lang:
            skipped.append((os.path.basename(p), "语言不是 %s" % a.lang)); continue
        try:
            r = BP.analyze(p, a.lang, [])
        except ValueError as e:
            skipped.append((os.path.basename(p), str(e)[:80])); continue
        if not any(sec in r["sections"] for sec in BP.BODY):
            skipped.append((os.path.basename(p), "只有摘要或没有可测量正文，不能用作全文基线")); continue
        doi = next((d for d in (normalized_doi(mrow.get("id")), normalized_doi(meta.get("doi")),
                                normalized_doi(r.get("doi"))) if d), None)
        body_sha = M.corpus_body_sha256(text)
        if body_sha in seen_txt or (doi and doi in seen_doi):
            skipped.append((os.path.basename(p), "重复（同 DOI 或去元数据后同文本）")); continue
        seen_txt[body_sha] = 1
        if doi:
            seen_doi[doi] = 1
        pid = doi or mrow.get("id") or meta.get("slug") or os.path.splitext(os.path.basename(p))[0][:40]
        genre = mrow.get("genre") or gmap.get(os.path.basename(p)) or meta.get("genre") or ""
        title = mrow.get("title") or meta.get("title_zh") or meta.get("title") or next(
            (l[2:].strip() for l in raw.split("\n") if l.startswith("# ")), "")
        ym = re.search(r"\.((?:19|20)\d\d)\.", doi or "")
        year = mrow.get("year") or meta.get("year") or (ym.group(1) if ym else "")
        r = {k: v for k, v in r.items() if k not in ("sents", "path")}
        r["file"], r["id"], r["genre"], r["year"] = pid, pid, genre, year
        r["doi"], r["body_sha256"] = doi, body_sha
        ex.append(r)
        kept.append(p)
        rows.append({"id": pid, "title": title[:120], "journal": mrow.get("journal") or meta.get("journal", ""), "year": year, "genre": genre,
                     "license": mrow.get("license") or meta.get("license") or meta.get("license_note", ""), "body_words": sum(r["sections"][k]["words"] for k in BP.BODY if k in r["sections"])})
        st = PC.stats_from_sentences(PC.sections_of(text, a.lang), a.lang, words, keep_examples=False)
        phrase.append({"id": pid, "genre": genre, "sections": {g: {"n": s["n"], "words": s["words"], "op": dict(s["op"]), "fr": dict(s["fr"])} for g, s in st.items()}})
        us = LP.units(text)
        texture.append({"id": pid, "genre": genre, "rates": {pt["id"]: {g: [round(rt, 4), c] for g, (rt, c) in LP.rate_table(pt, us).items()} for pt in pats}})
    if len(ex) < 3:
        raise ValueError("可用论文不足 3 篇（跳过：%s）" % skipped)
    summ = {}
    for sec in BP.SECS:
        for key, name, only, _ in BP.METRICS:
            if only and sec not in only:
                continue
            s = M.summarize([r["sections"][sec].get(key) for r in ex if sec in r["sections"]])
            if s:
                summ["%s|%s" % (sec, key)] = s
    gl = {}
    for key in ("supp_mentions", "distinct_domain_terms"):
        s = M.summarize([r.get(key) for r in ex])
        if s:
            gl[key] = s
    bench = {"pack": a.id, "lang": a.lang, "exemplars": ex, "summary": summ, "global": gl}
    # 句式：只保留 ≥2 篇出现的起句与框架
    loo = []
    full = [{g: {"n": s["n"], "words": s["words"], "op": collections.Counter(s["op"]), "fr": collections.Counter(s["fr"])} for g, s in p["sections"].items()} for p in phrase]
    for i in range(len(full)):
        loo.append(PC.count_flags(full[i], full[:i] + full[i + 1:]))
    phrase_loo = {"median": int(statistics.median(loo)), "max": max(loo), "min": min(loo)} if loo else None
    for kind in ("op", "fr"):            # 按节计篇数，只留同一节中 ≥2 篇出现的骨架
        for g in PC.SECS + ["all"]:
            df = collections.Counter()
            for p in phrase:
                df.update(p["sections"][g][kind].keys())
            for p in phrase:
                s = p["sections"][g]
                s[kind] = {f: c for f, c in s[kind].items() if df[f] >= 2}
    # 规则触发率（用本包的分布校准阈值后再数）
    os.makedirs(a.out, exist_ok=True)
    tmpb = os.path.join(tempfile.mkdtemp(), "bench.json")
    json.dump(bench, open(tmpb, "w", encoding="utf-8"), ensure_ascii=False)
    fired = collections.defaultdict(lambda: collections.Counter())
    linted = 0
    for p in kept:
        try:
            items = run_lint(p, tmpb)
        except Exception:
            items = None
        if items is None:
            continue
        linted += 1
        codes = {}
        for it in items:
            lv = it["level"]
            if it["code"] not in codes or ["INFO", "SHOULD", "MUST"].index(lv) > ["INFO", "SHOULD", "MUST"].index(codes[it["code"]]):
                codes[it["code"]] = lv
        for c, lv in codes.items():
            fired[c][lv] += 1
            fired[c]["any"] += 1
    rules = {c: {"papers": v["any"], "n": linted, "share": round(v["any"] / linted, 3), "levels": {k: v[k] for k in ("MUST", "SHOULD", "INFO") if v[k]}}
             for c, v in sorted(fired.items())} if linted else {}
    ks = [k for k in (3, 5, 8, 10, 12, 15, 20, 25, 30) if k <= len(ex) - 1]
    stab = stability(ex, ks, a.boot)
    genre = genre_effect(ex)
    genres = collections.Counter(r["genre"] or "未标注" for r in ex)
    cover = {sec: sum(1 for r in ex if sec in r["sections"]) for sec in BP.SECS}
    prof = {"schema_version": 1, "id": a.id, "label": a.label, "language": a.lang, "field": a.field, "journals": sorted({r["journal"] for r in rows if r["journal"]}),
            "years": sorted({r["year"] for r in rows if r["year"]}), "n_papers": len(ex), "genres": dict(genres), "section_coverage": cover,
            "built": datetime.date.today().isoformat(), "builder": BUILDER,
            "hashes": {"vocab": vsha, "texture": lexicon_hash(a.lang), "tokenizer": PC.TOKENIZER_VERSION},
            "phrase_vocab_extra": [], "phrase_loo": phrase_loo, "stability": stab, "genre_effect": genre,
            "use": "领域基线是同领域已发表论文的分布，不是与稿件匹配的对标；体裁、期刊或主题差别大时，先用 --genre 或补充匹配对标。",
            "license_note": a.license_note}
    phrase_out = {"pack": a.id, "lang": a.lang, "vocab_sha": vsha, "n_open": PC.N_OPEN, "n_frame": PC.N_FRAME, "papers": phrase}
    texture_out = {"pack": a.id, "lang": a.lang, "texture_sha": lexicon_hash(a.lang), "papers": texture}
    rules_out = {"pack": a.id, "lang": a.lang, "n": linted, "rules": rules,
                 "note": "share = 入选论文中触发该规则（任何级别）的比例；仅可校准的风格规则按 share 降级，科学主张与交付约束不降级。"}
    bad = []
    for name, obj in (("bench", bench), ("phrase", phrase_out), ("texture", texture_out), ("rules", rules_out), ("profile", prof)):
        bad += [name + b for b in privacy_scan(obj, allow=ALLOW_LONG)]
    if bad:
        raise ValueError("隐私扫描未通过（存在长文本字段）：%s" % bad[:5])
    for fn, obj in (("profile.json", prof), ("bench_baseline.json", bench), ("phrase_baseline.json", phrase_out),
                    ("texture_baseline.json", texture_out), ("rule_rates.json", rules_out)):
        with open(os.path.join(a.out, fn), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=None if fn != "profile.json" else 1, separators=(",", ":") if fn != "profile.json" else None)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["id", "title", "journal", "year", "genre", "license", "body_words"])
    w.writeheader()
    w.writerows(rows)
    with open(os.path.join(a.out, "corpus_manifest.csv"), "w", encoding="utf-8-sig", newline="") as f:
        f.write(buf.getvalue())
    rep = report(prof, rules, stab, genre, skipped)
    with open(os.path.join(a.out, "build_report.md"), "w", encoding="utf-8") as f:
        f.write(rep)
    print("领域包 %s：%d 篇（跳过 %d）；体裁 %s；输出 %s" % (a.id, len(ex), len(skipped), dict(genres), a.out))
    return 0


def report(prof, rules, stab, genre, skipped):
    L = ["# 领域包构建报告：%s\n" % prof["id"],
         "%s；语言 %s；%d 篇（%s）；期刊：%s；年份：%s；构建 %s。\n" % (prof["label"], prof["language"], prof["n_papers"],
                                                         "、".join("%s %d" % kv for kv in prof["genres"].items()), "、".join(prof["journals"]) or "未注明",
                                                         "–".join([min(prof["years"]), max(prof["years"])]) if prof["years"] else "未注明", prof["built"]),
         "各节可测量的篇数：" + "、".join("%s %d" % (k, v) for k, v in prof["section_coverage"].items()) + "。\n",
         "## 样本量与判定稳定性\n",
         "留一法：每篇已发表论文轮流当作“稿件”，用 k 篇随机子集判定各指标是否偏离，与用其余全部论文的判定比较。"
         "k<10 时按范围判定，10–19 篇按 p10–p90，≥20 篇按 p05–p95（与 bench_profile 相同）。\n",
         "| 参照篇数 k | 与全部参照的判定一致率 | 可测指标比较中被标偏离的比例 |", "|---|---|---|"]
    for k, v in stab.items():
        L.append("| %s | %.0f%% | %.0f%% |" % (k, 100 * v["agreement"], 100 * v["flag_rate"]))
    L.append("\n“被标偏离的比例”的分母是可测指标比较次数（指标 × 留出论文 × 抽样重复），不是论文篇数。"
             "这些判定没有人工真值，不能称为误报率；单项偏离只是核查线索，不等于写作问题。\n")
    if genre:
        L += ["## 体裁是否改变常态\n",
              "只比较 ≥3 篇的体裁（%s）。%d 个指标中，%d 个的体裁差异超过随机打乱标签的 95%% 分位（随机情况下预期约 %s 个）；"
              "η² 中位数 %.2f，随机打乱时 %.2f。\n" % ("、".join("%s %d" % kv for kv in genre["genres"].items()), genre["metrics"], genre["beyond_chance"],
                                                    genre["expected_by_chance"], genre["median_eta2"], genre["median_null"]),
              "差异最大的指标：" + "；".join("%s（η²=%.2f）" % (t["metric"], t["eta2"]) for t in genre["top"][:8]) + "\n"]
    if prof.get("phrase_loo"):
        lo = prof["phrase_loo"]
        L.append("## 句式对照的校准参照\n\n每篇已发表论文对其余论文做 phrase_contrast（留一法，默认标准）：被标出中位 %d 项，范围 %d–%d 项。"
                 "稿件的标记数应与此对照阅读。\n" % (lo["median"], lo["min"], lo["max"]))
    L += ["## 检查规则在已发表论文上的触发率\n", "| 规则 | 触发篇数 | 比例 | 级别分布 |", "|---|---|---|---|"]
    for c, v in sorted(rules.items(), key=lambda kv: -kv[1]["share"]):
        L.append("| %s | %d/%d | %.0f%% | %s |" % (c, v["papers"], v["n"], 100 * v["share"], "、".join("%s %d" % kv for kv in v["levels"].items())))
    L.append("\n触发率 ≥50%% 的风格规则可降为 INFO 并注明；交付残留、字数限制、设计/因果、趋势话术、建议、新颖性和作者声明规则（%s）不按发表频率降级。常见不等于正确。\n" % "、".join(sorted(NEVER_DOWNGRADE)))
    if skipped:
        L.append("跳过的文件：" + "；".join("%s（%s）" % s for s in skipped) + "\n")
    L.append("隐私：本目录只含统计量、短句式骨架与文献清单；语料全文不在其中。\n")
    return "\n".join(L)


# ------------------------------------------------------------------ 检查与列出
def cmd_check(a):
    d = a.pack
    need = PACK_FILES
    probs, notes = [], []
    extra = unexpected_pack_files(d)
    if extra:
        probs.append("目录含领域包以外的文件或子目录：%s" % extra)
    for fn in need:
        if not os.path.isfile(os.path.join(d, fn)):
            probs.append("缺少 %s" % fn)
    if probs:
        print("\n".join(probs)); return 1
    prof = json.load(open(os.path.join(d, "profile.json"), encoding="utf-8"))
    lang = prof["language"]
    _, vsha = PC.load_vocab(lang, prof.get("phrase_vocab_extra", []))
    if prof["hashes"].get("vocab") != vsha:
        probs.append("句式词表或切词方式已变（%s ≠ %s）：重建领域包" % (prof["hashes"].get("vocab"), vsha))
    if prof["hashes"].get("texture") != lexicon_hash(lang):
        probs.append("模式目录或%s词表已变：重建领域包后 language_plan --baseline 才可用" % lang)
    n = prof["n_papers"]
    if n < 8:
        probs.append("只有 %d 篇：不足以描述分布（建议 ≥15，至少 8）" % n)
    elif n < 15:
        notes.append("%d 篇：样本较小；分位数按每项指标实际可测 n 计算，仅作描述性参照" % n)
    for sec, c in prof["section_coverage"].items():
        if c < min(8, n):
            notes.append("%s 只有 %d 篇可测量" % (sec, c))
    for fn in ("bench_baseline.json", "phrase_baseline.json", "texture_baseline.json", "rule_rates.json"):
        obj = json.load(open(os.path.join(d, fn), encoding="utf-8"))
        bad = privacy_scan(obj, allow=ALLOW_LONG)
        if bad:
            probs.append("%s 含长文本字段：%s" % (fn, bad[:3]))
    print("领域包 %s（%s，%d 篇）：问题 %d、提示 %d" % (prof["id"], lang, n, len(probs), len(notes)))
    for x in probs:
        print("- 问题：" + x)
    for x in notes:
        print("- 提示：" + x)
    return 1 if probs else 0


def cmd_list(a):
    base = a.dir or os.path.join(ROOT, "assets", "domains")
    found = 0
    for p in sorted(glob.glob(os.path.join(base, "*", "profile.json"))):
        prof = json.load(open(p, encoding="utf-8"))
        found += 1
        print("%-22s %-3s %3d 篇  %s  体裁：%s  构建：%s" % (prof["id"], prof["language"], prof["n_papers"], prof["label"],
                                                       "、".join("%s %d" % kv for kv in prof["genres"].items()), prof["built"]))
    if not found:
        print("没有领域包：%s" % base)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--corpus", nargs="+", required=True)
    b.add_argument("--id", required=True)
    b.add_argument("--label", required=True)
    b.add_argument("--field", default="")
    b.add_argument("--lang", default="zh", choices=["zh", "en"])
    b.add_argument("--manifest", default="")
    b.add_argument("--genre-map", nargs="*", default=[])
    b.add_argument("--license-note", default="语料全文留在本机；本目录只含统计量与文献清单。")
    b.add_argument("--boot", type=int, default=60)
    b.add_argument("--out", required=True)
    c = sub.add_parser("check")
    c.add_argument("pack")
    li = sub.add_parser("list")
    li.add_argument("dir", nargs="?", default="")
    a = ap.parse_args()
    try:
        return {"build": cmd_build, "check": cmd_check, "list": cmd_list}[a.cmd](a)
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as e:
        print("输入错误：%s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
