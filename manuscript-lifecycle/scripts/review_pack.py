#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
review_pack.py — 生成完整审查包：正文、全部表格、图注、补充材料与图片清单放进同一份文件，每个来源带 SHA-256。

  python review_pack.py --manuscript 稿件.md|docx [--supplement 补充.md|docx …] [--tables 表.csv|md …] [--legends 图注.md …]
         [--figures 图.png|pdf|svg …] [--expectations expectations.json] --out review_package.md [--manifest manifest.json]

为什么：审稿人只拿到 Markdown 正文时看不到表（实际发生过：表格、图注与补充材料里的内部代码没有任何审稿人看到）。
审稿人把审查包的 sha256 填作 manuscript_sha256；review_merge.py validate --manuscript review_package.md 能核对落在表格与图注里的锚点。
图片只列文件与指纹：图内文字要看原图或渲染页（reviewer_display）。--expectations 只给需要核对用户要求的角色，不给盲审角色（references/26）。
退出码：0 已写出；2 输入错误。
"""
import argparse
import csv
import datetime
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mslib as M  # noqa: E402
from output_safety import output_path, write_fresh  # noqa: E402


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def csv_md(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.reader(f, delimiter="\t" if path.lower().endswith(".tsv") else ",") if any(c.strip() for c in r)]
    if not rows:
        return "（空表）"
    n = max(len(r) for r in rows)

    def cell(c):
        return c.replace("|", "/").replace("\n", " ")
    out = ["| " + " | ".join(cell(c) for c in rows[0] + [""] * (n - len(rows[0]))) + " |", "|" + "---|" * n]
    out += ["| " + " | ".join(cell(c) for c in r + [""] * (n - len(r))) + " |" for r in rows[1:]]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manuscript", required=True)
    ap.add_argument("--supplement", nargs="*", default=[])
    ap.add_argument("--tables", nargs="*", default=[])
    ap.add_argument("--legends", nargs="*", default=[])
    ap.add_argument("--figures", nargs="*", default=[])
    ap.add_argument("--expectations", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--manifest", default="")
    a = ap.parse_args()
    parts = [("正文", a.manuscript)] + [("补充材料", p) for p in a.supplement] + [("表", p) for p in a.tables] + \
            [("图注", p) for p in a.legends] + [("图片", p) for p in a.figures]
    srcs = [p for _, p in parts] + ([a.expectations] if a.expectations else [])
    miss = [p for p in srcs if not os.path.isfile(p)]
    if miss:
        print("找不到输入：%s" % "、".join(miss), file=sys.stderr)
        return 2
    try:
        out = output_path(a.out, srcs)
        man = output_path(a.manifest, srcs + [a.out]) if a.manifest else None
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    if not M.load_text(a.manuscript).strip():
        print("not_verified：稿件为空", file=sys.stderr)
        return 2
    L = ["# 审查包", "", "生成于 %s。审稿只依据本包：包外的文件不算审过；表格、图注与补充材料和正文同等审查。" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "",
         "| 部分 | 文件 | SHA-256 |", "|---|---|---|"]
    rec = []
    for kind, p in parts:
        d = sha(p)
        rec.append({"part": kind, "path": os.path.basename(p), "sha256": d})
        L.append("| %s | %s | %s |" % (kind, os.path.basename(p), d[:16]))
    L.append("")
    for kind, p in parts:
        if kind == "图片":
            continue
        L += ["", "# 〔%s〕%s" % (kind, os.path.basename(p)), ""]
        L.append(csv_md(p) if (kind == "表" and p.lower().endswith((".csv", ".tsv"))) else M.load_text(p).strip())
    figs = [r for r in rec if r["part"] == "图片"]
    if figs:
        L += ["", "# 〔图片清单〕", "", "图内文字（坐标轴、图例、面板标签）不在本包里：须看原图或渲染页，并核对与表、正文用语一致。", ""]
        L += ["- %s（%s）" % (r["path"], r["sha256"][:16]) for r in figs]
    if a.expectations:
        try:
            with open(a.expectations, encoding="utf-8-sig") as f:
                exp = json.load(f)
        except (OSError, ValueError) as e:
            print("读不了用户要求登记表：%s" % e, file=sys.stderr)
            return 2
        L += ["", "# 〔用户明确要求〕", "", "以下是用户已经明确提出、必须逐条核对的要求（不是审稿人的偏好）：", ""]
        L += ["- %s：%s" % (e.get("id", "?"), e.get("text", "")) for e in exp.get("items", [])]
    text = "\n".join(L) + "\n"
    write_fresh(out, text)
    # 指纹取写入后的文件字节：Windows 上文本模式写入会把换行转成 CRLF，按内存字符串算的指纹会与文件对不上
    with open(out, "rb") as fb:
        digest = hashlib.sha256(fb.read()).hexdigest()
    if man:
        write_fresh(man, json.dumps({"package": os.path.basename(a.out), "package_sha256": digest, "sources": rec}, ensure_ascii=False, indent=1))
    print("已写出审查包 %s（%d 个来源；sha256 %s）。审稿人把它作为稿件，manuscript_sha256 填这个值。" % (out, len(rec), digest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
