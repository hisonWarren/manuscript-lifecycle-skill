#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
derivation_check.py — 派生量复算与量纲核对：稿件里由其他估计值算出来的量（乘积、比值、换算、效应量、“约七分之一”），
逐个登记公式、各分量的数值与单位，脚本复算并核对单位、符号与数值（references/22 §8）。

  python derivation_check.py derivations.csv [--report out.md] [--json out.json]

derivations.csv 列：id, label, formula, variables, reported, reported_unit, tolerance, kind, source, note
  formula     Python 算式，只用 + - * / ** 、括号、数字、变量名与 sqrt()、abs()，如 a*b、-b_amp/b_dur*1000、t/sqrt(n)
  variables   “名=数值[单位]”用分号分隔，如 a=-0.705[uV]; b=-0.246[logit/SD]; k=1000[ms/s]。单位写法：uV、ms、s、SD、logit、
              logit/SD、ms/SD、1（无量纲）；乘用 *，除用 /，幂用 ^，如 uV^2。
  reported    稿件里写的值；reported_unit 稿件声称的单位（与算出的单位比对）
  tolerance   可空：默认取报告值末位的半个单位（0.174 → 0.0005）
  kind        identity（应当精确相等，默认）或 approx（报告值来自个体层级计算、只能近似，例如个体乘积的均值不等于均值的乘积）

规则：DV1 MUST 算出的单位与报告单位不同（例如把 μV 的 a 路径与“每标准差”的 b 相乘却报告为 logit）；
      DV3 MUST 符号相反；DV2 MUST 数值超出容差（kind=approx 时为 SHOULD，并提示写明计算层级）；DV0 MUST 算式或单位无法解析。
为什么要有它：一次实测中，中介间接效应 0.174 恰等于 μV 单位的 a 乘以“每标准差”单位的 b，结果节照抄进稿件；
数字核对（number_trace）只证明数字在结果文件里出现过，证明不了它在量纲上说得通。退出码 0/1/2；报告与 JSON 必须是新路径。
"""
import argparse, ast, csv, json, math, os, re, sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

TOK = re.compile(r"([A-Za-z%]+)(?:\^(-?\d+))?")


def parse_unit(s):
    s = (s or "").strip().replace("μ", "u").replace("µ", "u").replace("·", "*")
    if s in ("", "1", "-", "none", "dimensionless", "无"):
        return {}
    parts = s.split("/")
    out = {}
    for k, part in enumerate(parts):
        sign = 1 if k == 0 else -1
        for tok in re.split(r"[*\s]+", part.strip()):
            if not tok or tok == "1":
                continue
            m = TOK.fullmatch(tok)
            if not m:
                raise ValueError("看不懂的单位：%s" % tok)
            out[m.group(1)] = out.get(m.group(1), 0) + sign * int(m.group(2) or 1)
    return {k: v for k, v in out.items() if v}


def fmt_unit(u):
    if not u:
        return "1"
    num = "*".join(k + ("^%d" % v if v != 1 else "") for k, v in sorted(u.items()) if v > 0) or "1"
    den = "*".join(k + ("^%d" % -v if v != -1 else "") for k, v in sorted(u.items()) if v < 0)
    return num + ("/" + den if den else "")


class Q:
    def __init__(self, v, u):
        self.v, self.u = v, dict(u)


def mul(a, b, sign=1):
    u = dict(a.u)
    for k, v in b.u.items():
        u[k] = u.get(k, 0) + sign * v
    return {k: v for k, v in u.items() if v}


def ev(node, env):
    if isinstance(node, ast.Expression):
        return ev(node.body, env)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return Q(float(node.value), {})
    if isinstance(node, ast.Name):
        if node.id not in env:
            raise ValueError("算式里的变量 %s 没在 variables 里给出" % node.id)
        return env[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        x = ev(node.operand, env)
        return Q(-x.v if isinstance(node.op, ast.USub) else x.v, x.u)
    if isinstance(node, ast.BinOp):
        a, b = ev(node.left, env), ev(node.right, env)
        if isinstance(node.op, (ast.Add, ast.Sub)):
            if a.u != b.u:
                raise ArithmeticError("加减两边单位不同：%s 与 %s" % (fmt_unit(a.u), fmt_unit(b.u)))
            return Q(a.v + b.v if isinstance(node.op, ast.Add) else a.v - b.v, a.u)
        if isinstance(node.op, ast.Mult):
            return Q(a.v * b.v, mul(a, b))
        if isinstance(node.op, ast.Div):
            return Q(a.v / b.v, mul(a, b, -1))
        if isinstance(node.op, ast.Pow):
            if b.u:
                raise ArithmeticError("幂指数必须无量纲")
            return Q(a.v ** b.v, {k: v * b.v for k, v in a.u.items()})
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("sqrt", "abs") and len(node.args) == 1:
        x = ev(node.args[0], env)
        if node.func.id == "abs":
            return Q(abs(x.v), x.u)
        if any(v % 2 for v in x.u.values()):
            raise ArithmeticError("sqrt 的单位指数不是偶数：%s" % fmt_unit(x.u))
        return Q(math.sqrt(x.v), {k: v // 2 for k, v in x.u.items()})
    raise ValueError("不支持的算式成分：%s" % ast.dump(node)[:80])


def parse_vars(s):
    env = {}
    for part in re.split(r"[;；]", s or ""):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"([A-Za-z_]\w*)\s*=\s*([−\-+]?[\d.]+(?:e[−\-+]?\d+)?)\s*(?:\[(.*?)\])?", part)
        if not m:
            raise ValueError("看不懂的变量：%s" % part)
        env[m.group(1)] = Q(float(m.group(2).replace("−", "-")), parse_unit(m.group(3) or ""))
    return env


def default_tol(rep):
    s = rep.strip().replace("−", "-")
    return 0.5 * 10 ** (-len(s.split(".")[1])) if "." in s else 0.5


def check(rows):
    items, out = [], []
    for r in rows:
        rid = r.get("id") or "?"
        rec = {"id": rid, "label": r.get("label", ""), "formula": r.get("formula", "")}
        try:
            env = parse_vars(r.get("variables", ""))
            q = ev(ast.parse((r.get("formula") or "").replace("−", "-"), mode="eval"), env)
            rep_s = (r.get("reported") or "").strip()
            rep = float(rep_s.replace("−", "-"))
            ru = parse_unit(r.get("reported_unit", ""))
            tol = float(r["tolerance"]) if (r.get("tolerance") or "").strip() else default_tol(rep_s)
            rec.update(computed=q.v, computed_unit=fmt_unit(q.u), reported=rep, reported_unit=fmt_unit(ru), tolerance=tol)
            approx = (r.get("kind") or "identity").strip().lower() == "approx"
            if q.u != ru:
                items.append(("MUST", "DV1", rid, "单位不一致：算式得到 %s，稿件报告为 %s（%s）" % (fmt_unit(q.u), fmt_unit(ru), r.get("label", ""))))
            if q.v * rep < 0:
                items.append(("MUST", "DV3", rid, "符号相反：算出 %.4g，报告 %s（%s）" % (q.v, rep_s, r.get("label", ""))))
            elif abs(q.v - rep) > tol:
                items.append(("SHOULD" if approx else "MUST", "DV2", rid, "数值不符：算出 %.4g，报告 %s，容差 %.3g%s（%s）"
                              % (q.v, rep_s, tol, "；登记为近似，写明报告值在哪个层级计算" if approx else "", r.get("label", ""))))
        except (ValueError, ArithmeticError, SyntaxError, ZeroDivisionError, KeyError) as e:
            items.append(("MUST", "DV0", rid, "算式或单位无法解析：%s" % e))
        out.append(rec)
    return items, out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("table")
    ap.add_argument("--report", default="")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    if not os.path.exists(a.table):
        print("找不到 %s" % a.table, file=sys.stderr)
        return 2
    for p in (a.report, a.json):
        if p and os.path.exists(p):
            print("输出文件已存在：%s" % p, file=sys.stderr)
            return 2
    rows = list(csv.DictReader(open(a.table, encoding="utf-8-sig", newline="")))
    if not rows or "formula" not in rows[0]:
        print("登记表为空或缺 formula 列（模板 assets/templates/derivations.csv）", file=sys.stderr)
        return 2
    items, recs = check(rows)
    L = ["# 派生量复算（derivation_check）", "", "| ID | 量 | 算式 | 算出 | 报告 |", "|---|---|---|---|---|"]
    for r in recs:
        if "computed" in r:
            L.append("| %s | %s | `%s` | %.4g %s | %s %s |" % (r["id"], r["label"], r["formula"], r["computed"], r["computed_unit"], r["reported"], r["reported_unit"]))
    L += ["", "## 问题", ""] + (["- **%s %s**（%s）%s" % x for x in items] or ["没有。"])
    L += ["", "复算只核对登记了的派生量与登记的分量；分量本身对不对、个体层级的计算有没有做对，要回到分析代码。"]
    text = "\n".join(L) + "\n"
    if a.report:
        open(a.report, "w", encoding="utf-8").write(text)
    if a.json:
        json.dump({"schema_version": 1, "items": [dict(zip(("level", "code", "id", "msg"), x)) for x in items], "rows": recs},
                  open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(text if not a.report else "MUST %d、SHOULD %d；报告 %s" % (sum(x[0] == "MUST" for x in items), sum(x[0] == "SHOULD" for x in items), a.report))
    return 1 if any(x[0] == "MUST" for x in items) else 0


if __name__ == "__main__":
    sys.exit(main())
