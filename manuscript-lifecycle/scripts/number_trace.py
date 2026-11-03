#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
number_trace.py — 数字同值候选筛查；不是上下文溯源验证。

  python number_trace.py 稿件.md --sources 结果目录/ 表1.csv 补充材料.md ... [--allow allow.txt] [--min-int 10]
         [--sections abstract,introduction,methods,results,discussion,limitations,conclusion] [--captions] [--report out.md]

匹配规则：
  · 按稿件写出的小数位，判断源数值是否在半个末位单位之内；四舍五入与银行家舍入都接受。
  · .738 与 0.738 等价；忽略千分位逗号；真负号与连字符等价。
  · 不自动忽略符号或猜测百分比单位；转换与派生量改用 verify_evidence.py。
不计：年份、表图节号、引文、软件版本号、量表名里的数字（PHQ-9）、小于 --min-int 的整数。
源文件要选准：只给承载正文数字的结果表。默认跳过文件名含 replicate、_private、raw 的文件（自助重复抽样、原始数据），
可用 --exclude 追加。报告会给出"碰巧匹配率"：源数值越密，任意一个三位小数碰巧能在源里找到的概率越高；
超过 50% 时，"可追溯"已经说明不了什么，必须缩小源文件范围后重跑。
找不到的数字列出上下文，供排查。--allow 不会把全局同值数字豁免为通过；不来自结果文件的数字，在 check_all 的 --allow 登记表里写明理由。
默认扫描识别到的正文、表格、题注；识别器仍可能漏掉年份、小节或复杂表格，不能声称覆盖所有数字。
退出码：0 本次范围内未发现同值异常（不是溯源通过）；1 不匹配或需结构化核对；2 输入错误或零覆盖。
"""
import argparse, json, re, bisect, csv, glob, os, re, sys
from decimal import Decimal, InvalidOperation
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mslib as M

NUM_ANY = re.compile(r"[−-]?(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)(?:[eE][+−-]?\d+)?")


def parse_num(tok):
    t = tok.replace("−", "-").replace(",", "").rstrip("%")
    neg = t.startswith("-"); t = t.lstrip("-")
    if t.startswith("."):
        t = "0" + t
    try:
        v = float(t)
    except ValueError:
        return None, 0
    mant = re.split(r"[eE]", t)[0]
    return (-v if neg else v), (len(mant.split(".")[1]) if "." in mant else 0)


PCT_IN_TEXT = re.compile(r"(?<![\w.])[−-]?\d+(?:\.\d+)?\s?%")
CI_LABEL = re.compile(r"^\s*(?:CI|C\.I\.|CrI|confidence|credible|置信|可信)", re.I)


def source_percents(paths):
    """来源里逐字出现的百分数（62.0%、9.8%）。原样出现的百分数视为有出处；派生或换算出来的仍要核。"""
    out = set()
    for p in paths:
        try:
            t = M.load_text(p) if not p.lower().endswith((".csv", ".tsv")) else open(p, encoding="utf-8-sig", errors="replace").read()
        except Exception:
            continue
        out.update(m.group(0).replace(" ", "").replace("−", "-") for m in PCT_IN_TEXT.finditer(t))
    return out


def source_values(paths):
    vals = []
    for p in paths:
        ext = os.path.splitext(p)[1].lower()
        try:
            if ext in (".csv", ".tsv"):
                with open(p, encoding="utf-8-sig", errors="replace", newline="") as f:
                    for row in csv.reader(f, delimiter="\t" if ext == ".tsv" else ","):
                        for cell in row:
                            vals += [parse_num(m.group(0))[0] for m in NUM_ANY.finditer(cell)]
            else:
                vals += [parse_num(m.group(0))[0] for m in NUM_ANY.finditer(M.load_text(p))]
        except Exception as e:
            raise ValueError("读取失败 %s：%s" % (p, e)) from e
    return sorted(v for v in vals if v is not None)


def near(sorted_vals, x, tol):
    i = bisect.bisect_left(sorted_vals, x - tol)
    return i < len(sorted_vals) and sorted_vals[i] <= x + tol


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("manuscript"); ap.add_argument("--sources", nargs="+", required=True)
    ap.add_argument("--allow", default=""); ap.add_argument("--min-int", type=int, default=0)
    ap.add_argument("--sections", default="abstract,introduction,methods,results,discussion,limitations,conclusion")
    ap.add_argument("--captions", action="store_true", help="保留此选项；现在默认就扫描表格、题注与表注")
    ap.add_argument("--exclude", nargs="*", default=["*replicate*", "*_private*", "*raw*"])
    ap.add_argument("--report", default="")
    ap.add_argument("--json", default="", help="把未匹配清单另存为 JSON")
    a = ap.parse_args()
    if not os.path.exists(a.manuscript):
        print("找不到稿件", file=sys.stderr); return 2
    paths = []
    for s in a.sources:
        if os.path.isdir(s):
            for ext in ("*.csv", "*.tsv", "*.md", "*.txt", "*.json", "*.docx"):
                paths += glob.glob(os.path.join(s, "**", ext), recursive=True)
        elif os.path.exists(s):
            paths.append(s)
        else:
            print("源文件不存在：%s" % s, file=sys.stderr); return 2
    import fnmatch
    skipped = [p for p in paths if any(fnmatch.fnmatch(os.path.basename(p).lower(), x.lower()) for x in a.exclude)]
    paths = [p for p in paths if os.path.abspath(p) != os.path.abspath(a.manuscript) and p not in skipped]
    try:
        vals = source_values(paths)
    except ValueError as e:
        print(str(e), file=sys.stderr); return 2
    if not vals:
        print("源文件里没有读到数字", file=sys.stderr); return 2
    cover = {}
    for d in (2, 3):
        grid = [round(-1 + k * 10 ** (-d), d) for k in range(2 * 10 ** d + 1)]
        tol = 0.5 * 10 ** (-d) + 1e-9
        cover[d] = sum(1 for g in grid if near(vals, g, tol)) / len(grid)
    allow = set()
    if a.allow:
        for line in open(a.allow, encoding="utf-8-sig"):
            if line.strip() and not line.startswith("#"):
                allow.add(line.split()[0].replace("−", "-"))
    secs = set(a.sections.split(","))
    kinds = ("para", "caption", "table")
    blocks = [b for b in M.parse(M.load_text(a.manuscript)) if
              (b["sec"] in secs or (b["sec"] == "back" and b["kind"] in ("table", "caption"))) and b["kind"] in kinds]
    total = ok = okabs = 0; bad = []
    pcts = source_percents(paths)
    for b in blocks:
        for tok, pos in M.number_tokens(b["text"]):
            x, d = parse_num(tok)
            if x is None:
                continue
            if d == 0 and not tok.endswith("%") and abs(x) < a.min_int:
                continue
            total += 1
            # Membership is a screening heuristic. Sign/unit/scale are not guessed.
            raw = tok.replace("−", "-").replace(",", "").rstrip("%")
            try:
                tol = float(Decimal(5).scaleb(Decimal(raw).as_tuple().exponent - 1))
            except InvalidOperation:
                tol = 0.0
            if tok.endswith("%") and CI_LABEL.match(b["text"][pos + len(tok):pos + len(tok) + 14]):
                total -= 1
                continue   # 95% CI 里的 95% 是区间水平，不是结果数字
            if tok.endswith("%") and tok.replace("−", "-") not in allow and tok.replace("−", "-") in pcts:
                ok += 1
                continue   # 来源里逐字出现的百分数
            if tok.replace("−", "-") in allow or tok.endswith("%"):
                bad.append((b["sec"], tok, "需用 verify_evidence.py 做带上下文的派生量/百分比核对；不能全局豁免同值数字。 " + b["text"][max(0,pos-40):pos+50]))
            elif near(vals, x, tol):
                ok += 1
            elif re.search(r"[<≤]\s*$", b["text"][max(0, pos - 3):pos]) and x > 0 and any(0 <= v < x for v in vals):
                ok += 1  # 阈值写法（p < .001）：只核对来源里有更小的值，不核对是哪一个
            else:
                bad.append((b["sec"], tok, b["text"][max(0, pos - 70):pos + 50].replace("\n", " ")))
    if total == 0:
        print("not_verified：没有纳入任何数字；检查节标题、表格解析和输入范围。不能记为通过。", file=sys.stderr); return 2
    L = ["# 数字候选匹配筛查：%s\n" % os.path.basename(a.manuscript),
         "源文件 %d 个、源数值 %d 个。纳入核对的数字 %d 个：同值候选 %d 个（按绝对值自动通过 %d 个），未匹配或待结构化核对 %d 个。\n" % (
             len(paths), len(vals), total, ok, okabs, len(bad)),
         "碰巧匹配率（[−1, 1] 区间）：两位小数 %.0f%%，三位小数 %.0f%%%s。跳过的文件：%d 个。\n" % (
             100 * cover[2], 100 * cover[3], "——**源数值过密，溯源失去判别力，请只给承载正文数字的结果表后重跑**" if cover[3] > 0.5 else "", len(skipped)),
         "同值候选仅为启发式筛查，不验证行、结局、组别、单位、方向、来源版本或主张。退出 0 也不构成溯源通过；关键数字须用 verify_evidence.py 的行键/列名/单位记录核对，并人工审查语义。\n"]
    if bad:
        L.append("| 节 | 数字 | 上下文 |\n|---|---|---|")
        for sec, tok, ctx in bad:
            L.append("| %s | %s | …%s… |" % (sec, tok, ctx.replace("|", "/")))
    out = "\n".join(L) + "\n"
    if a.json:
        with M.wfile(a.json) as f:
            json.dump({"checked": total, "matched": ok, "unmatched": [{"section": x[0], "number": x[1], "context": x[2][-160:]} for x in bad]}, f, ensure_ascii=False, indent=1)
    if a.report:
        with M.wfile(a.report) as f:
            f.write(out)
    print(out[:3000] if not a.report else (L[1].strip() + " " + L[2].strip()))
    return 1 if bad or cover[3] > 0.5 else 0


if __name__ == "__main__":
    sys.exit(main())
