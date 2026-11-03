#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
key_units.py — 从调研表里登记的近邻全文抽出关键段，生成语步编码模板（references/20 §1b–1c）。

  python key_units.py --neighbors 02_bench/neighbors.csv [--pair "标签=全文.md" …] [--draft 稿件.md]
         [--units intro_closing,disc_first,abs_last,conclusion,intro_paras] --out 目录

为什么要有它：语步对照最容易出错的一步是“拿哪几篇来比”。第八轮的错误就是图方便，用了两篇手边的综合刊论文当近邻，
让“引言预告结果”看起来是多数做法。这个脚本只从 neighbors.csv 里登记过的近邻取材，并把每篇是否类型匹配（type_match 列以
yes 开头为是）、属于哪一类期刊（tier 列：flagship → general，field → discipline，其余照写）写进编码单元，编码者只需填语步代码。
关键段：
  intro_closing  引言最后一段（逐句）        disc_first  讨论第一段（逐句）       disc_last  讨论最后一段（逐句）
  abs_last       摘要最后两句（逐句）        conclusion  结论节（逐句；没有结论节时取讨论里以 In conclusion 起的段）
  intro_paras    引言全文（段落级，一段一条）
全文文件：neighbors.csv 有 file 列就用它；否则用 --pair "标签=路径"（标签与 neighbors.csv 的 label 列一致）。读不到全文的近邻跳过并列出。
有 journal 或 venue 列时写进单元，move_check 会提示近邻是否集中在同一刊物或出版社。
输出：目录下 src/ 存各段原文摘录，coding_template.json 是编码模板（代码一栏是 “?”，move_check 会把没填的当作错误）。
退出码：0 写出模板；1 类型匹配的近邻少于 3 篇（模板照写，但比例不作数）；2 输入错误。
"""
import argparse, csv, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mslib as M  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

UNITS = ("intro_closing", "disc_first", "disc_last", "abs_last", "conclusion", "intro_paras")
FAMILY = {"flagship": "general", "field": "discipline"}


def paras(blocks, secs):
    return [b["text"] for b in blocks if b["sec"] in secs and b["kind"] == "para"]


def extract(text, unit):
    blocks = M.parse(text)
    intro = paras(blocks, ("introduction",))
    disc = paras(blocks, ("discussion", "discussion_all"))
    if unit == "intro_closing":
        return intro[-1] if intro else ""
    if unit == "intro_paras":
        return "\n\n".join(intro)
    if unit == "disc_first":
        return disc[0] if disc else ""
    if unit == "disc_last":
        return disc[-1] if len(disc) > 1 else ""
    if unit == "abs_last":
        ss = [s for p in paras(blocks, ("abstract",)) for s in M.sentences(p)]
        return " ".join(ss[-2:])
    if unit == "conclusion":
        con = paras(blocks, ("conclusion",))
        if con:
            return " ".join(con)
        return next((p for p in disc if re.match(r"\s*(?:In conclusion|To conclude|In summary|总之|综上)", p, re.I)), "")
    return ""


def cue(sentence, n=6):
    words = re.findall(r"\S+", sentence.strip())
    return " ".join(words[:n])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--neighbors", required=True)
    ap.add_argument("--pair", nargs="*", default=[])
    ap.add_argument("--draft", default="")
    ap.add_argument("--units", default="intro_closing,disc_first,abs_last,conclusion")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    units = [u.strip() for u in a.units.split(",") if u.strip()]
    bad = [u for u in units if u not in UNITS]
    if bad or not os.path.exists(a.neighbors):
        print("未知的关键段：%s；可用 %s" % ("、".join(bad), "、".join(UNITS)) if bad else "找不到 %s" % a.neighbors, file=sys.stderr)
        return 2
    with open(a.neighbors, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    pairs = dict(p.split("=", 1) for p in a.pair if "=" in p)
    base = os.path.dirname(os.path.abspath(a.neighbors))
    os.makedirs(os.path.join(a.out, "src"), exist_ok=True)
    out_units, skipped, n_tm = [], [], 0
    for r in rows:
        label = (r.get("label") or "").strip()
        path = (r.get("file") or "").strip() or pairs.get(label, "")
        if path and not os.path.isabs(path) and not os.path.exists(path):
            path = os.path.join(base, path)
        if not path or not os.path.exists(path):
            skipped.append(label)
            continue
        tm = (r.get("type_match") or "").strip().lower().startswith(("yes", "y", "是"))
        fam = FAMILY.get((r.get("tier") or "").strip().lower(), (r.get("tier") or "other").strip().lower() or "other")
        n_tm += tm
        venue = (r.get("journal") or r.get("venue") or "").strip()
        text = M.load_text(path)
        slug = re.sub(r"[^\w]+", "_", label)[:40]
        for u in units:
            seg = extract(text, u)
            if not seg.strip():
                continue
            src = os.path.join("src", "%s_%s.md" % (slug, u))
            with open(os.path.join(a.out, src), "w", encoding="utf-8") as f:
                f.write(seg.strip() + "\n")
            if u == "intro_paras":
                codes = [["?", cue(p)] for p in seg.split("\n\n") if p.strip()]
                out_units.append({"paper": label, "section": u, "role": "exemplar", "granularity": "paragraph", "source": src,
                                  "type_match": tm, "family": fam, "venue": venue, "codes": codes})
            else:
                out_units.append({"paper": label, "section": u, "role": "exemplar", "source": src, "type_match": tm, "family": fam, "venue": venue,
                                  "codes": [["?", cue(s)] for s in M.sentences(seg)]})
    if a.draft:
        text = M.load_text(a.draft)
        for u in units:
            seg = extract(text, u)
            if not seg.strip():
                continue
            src = os.path.join("src", "draft_%s.md" % u)
            with open(os.path.join(a.out, src), "w", encoding="utf-8") as f:
                f.write(seg.strip() + "\n")
            if u == "intro_paras":
                out_units.append({"paper": "稿件", "section": u, "role": "draft", "granularity": "paragraph", "source": src,
                                  "codes": [["?", cue(p)] for p in seg.split("\n\n") if p.strip()]})
            else:
                out_units.append({"paper": "稿件", "section": u, "role": "draft", "source": src, "codes": [["?", cue(s)] for s in M.sentences(seg)]})
    tpl = {"_note": "把每条的 “?” 换成语步代码（AIM、DES、HYP、FND、INT、IMP、FUT、VAL…，见 move_check.py 的 MOVES）；段落级单元一段承担几项职能就用 + 连写，"
                    "线索用 || 分隔补齐。type_match 与 family 取自 neighbors.csv，不要为了凑比例改动。", "units": out_units}
    with open(os.path.join(a.out, "coding_template.json"), "w", encoding="utf-8") as f:
        json.dump(tpl, f, ensure_ascii=False, indent=1)
    print("写出 %d 个单元（近邻 %d 篇有全文，其中类型匹配 %d 篇）%s" % (len(out_units), len(rows) - len(skipped), n_tm,
          "；没有全文、跳过：%s" % "、".join(skipped) if skipped else ""))
    if n_tm < 3:
        print("类型匹配的近邻少于 3 篇：比例不作数。先补全文，或按段落职能与目标刊判断。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
