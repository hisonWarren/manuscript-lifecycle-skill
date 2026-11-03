#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
claims_guard.py — 主张边界与防回潮：必须出现的表述在不在，已经决定删掉的写法有没有换个样子回来。

  python claims_guard.py --register claims_register.json --doc en=manuscript_en.md [--doc zh=manuscript_zh.md]
         [--doc resp=response.md] [--reverse-test] [--report out.md]

登记表格式见 assets/templates/claims_register.json。规则三类：
  required  必需表述（主张边界、必须披露的限定）：在指定节里至少出现 min 次；each=true 时每个指定节都要有
  forbidden 禁写表述（已裁决删除的写法、越界措辞、补丁痕迹）：任何一处出现即违反
  if_then   条件表述：出现 if 就必须同时出现 then（例：写"预先指定"就要写"未注册"）
每条规则写 why（为什么）与 decision（对应决策登记号），后来改稿的人才知道它不是随手加的。
--reverse-test：把每条 forbidden 的 sample（或非正则的 pattern）写进副本、把每条 required 从副本删掉，确认检查器真的报错。
一条从来不会报错的规则等于没有，所以检查器本身也要被检查。
退出码：0 所有登记规则在声明范围内完成文本检查；1 有违反或反向测试没报出；2 输入/范围不完整。
本工具只检验登记的文字规则，不评估主张是否真实、规则是否充分或整篇论文是否合格。
空规则、未知类型、未提供的 docs 标签、空范围、无效正则均不能记为通过。
"""
import argparse, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mslib as M


def sec_text(text, sections):
    blocks = M.parse(text)
    if not sections:
        return {"*": "\n".join(b["text"] for b in blocks if b["sec"] != "references" and b["kind"] != "heading")}
    out = {}
    for s in sections:
        keys = {"discussion": ("discussion", "limitations")}.get(s, (s,))
        out[s] = "\n".join(b["text"] for b in blocks if b["sec"] in keys and b["kind"] != "heading")
    return out


def rx(rule, key="pattern"):
    p = rule.get(key, "")
    return re.compile(p if rule.get("regex") else re.escape(p), re.I)


def validate(rules, docs):
    if not isinstance(rules, list) or not rules:
        raise ValueError("rules 必须是非空列表；零规则不能声明通过")
    ids = set()
    allowed = {"id", "type", "pattern", "sections", "each", "min", "docs", "regex", "why", "decision", "if", "then", "sample"}
    sections = {"abstract", "introduction", "methods", "results", "discussion", "limitations", "conclusion", "front", "back"}
    evaluated = 0
    covered_docs = set()
    for rule in rules:
        if not isinstance(rule, dict):
            raise ValueError("每条规则必须是对象")
        unknown = set(rule) - allowed
        if unknown:
            raise ValueError("未知规则字段：%s" % sorted(unknown))
        for key in ("id", "type", "why", "decision"):
            if not isinstance(rule.get(key), str) or not rule[key].strip():
                raise ValueError("规则缺少非空字符串：%s" % key)
        rid = rule["id"]
        if rid in ids:
            raise ValueError("重复规则 ID：%s" % rid)
        ids.add(rid)
        if rule["type"] not in ("required", "forbidden", "if_then"):
            raise ValueError("%s：未知 type" % rid)
        for key in ("regex", "each"):
            if key in rule and not isinstance(rule[key], bool):
                raise ValueError("%s：%s 必须是布尔值" % (rid,key))
        if "min" in rule and (type(rule["min"]) is not int or rule["min"] < 1):
            raise ValueError("%s：min 必须是正整数" % rid)
        for key in ("docs", "sections"):
            if key in rule:
                value = rule[key]
                if not isinstance(value,list) or not value or any(not isinstance(x,str) or not x.strip() for x in value) or len(set(value)) != len(value):
                    raise ValueError("%s：%s 必须是非空且不重复的字符串列表" % (rid,key))
        if set(rule.get("docs",[])) - set(docs):
            raise ValueError("%s：docs 指定了未提供的文档标签" % rid)
        if set(rule.get("sections",[])) - sections:
            raise ValueError("%s：sections 含未知或不支持的节名" % rid)
        keys = ("if", "then") if rule["type"] == "if_then" else ("pattern",)
        for key in keys:
            if not isinstance(rule.get(key),str) or not rule[key].strip():
                raise ValueError("%s：%s 必须是非空字符串" % (rid,key))
            try:
                pattern = rx(rule,key)
            except re.error as error:
                raise ValueError("%s：无效正则 %s" % (rid,error)) from error
            if pattern.search(""):
                raise ValueError("%s：规则不能匹配空字符串" % rid)
        if "sample" in rule and (not isinstance(rule["sample"],str) or not rule["sample"].strip()):
            raise ValueError("%s：sample 必须是非空字符串" % rid)
        for lab in rule.get("docs",list(docs)):
            parts = sec_text(docs[lab],rule.get("sections"))
            if not parts or any(not text.strip() for text in parts.values()):
                raise ValueError("%s［%s］：指定范围没有可检查内容；先核对切节与输入" % (rid,lab))
            evaluated += 1
            covered_docs.add(lab)
    if not evaluated:
        raise ValueError("没有实际评估的规则/文档组合")
    if set(docs) - covered_docs:
        raise ValueError("所提供文档没有适用规则：%s" % sorted(set(docs)-covered_docs))
    return evaluated


REF_HEAD = re.compile(r"^\s*(?:#{1,6}\s*)?(?:\*\*)?\s*(?:references?|bibliography|参考文献)\s*(?:\*\*)?\s*:?\s*$", re.I | re.M)


def inject(text, sample, sec=None):
    """把样例插进正文（参考文献之前），指定节时连同节标题一起插入，保证它落在被检查的范围里。"""
    block = "\n\n" + ("## %s\n\n" % sec.capitalize() if sec else "") + sample + "\n\n"
    m = None
    for m in REF_HEAD.finditer(text):
        pass
    return (text[:m.start()] + block + text[m.start():]) if m else (text + block)


def check(docs, rules):
    bad = []
    for r in rules:
        for lab, text in docs.items():
            if r.get("docs") and lab not in r["docs"]:
                continue
            t = r.get("type")
            if t == "required":
                parts = sec_text(text, r.get("sections"))
                cnt = {s: len(rx(r).findall(v)) for s, v in parts.items()}
                need = int(r.get("min", 1))
                miss = [s for s, c in cnt.items() if c < need] if r.get("each") else ([] if sum(cnt.values()) >= need else ["合计"])
                if miss:
                    bad.append((r["id"], lab, "必需表述不足：%s（%s）" % (r["pattern"], "、".join(miss)), r.get("why", "")))
            elif t == "forbidden":
                for s, v in sec_text(text, r.get("sections")).items():
                    for m in rx(r).finditer(v):
                        bad.append((r["id"], lab, "禁写表述出现：…%s…" % v[max(0, m.start() - 50):m.end() + 50].replace("\n", " "), r.get("why", "")))
            elif t == "if_then":
                parts = sec_text(text,r.get("sections"))
                scopes = parts.values() if r.get("each") else ["\n".join(parts.values())]
                for whole in scopes:
                    if rx(r, "if").search(whole) and not rx(r, "then").search(whole):
                        bad.append((r["id"], lab, "出现「%s」却没有「%s」" % (r["if"], r["then"]), r.get("why", "")))
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--register", required=True); ap.add_argument("--doc", action="append", required=True)
    ap.add_argument("--reverse-test", action="store_true"); ap.add_argument("--report", default="")
    a = ap.parse_args()
    try:
        data = json.load(open(a.register, encoding="utf-8-sig"))
        if not isinstance(data,dict) or "rules" not in data:
            raise ValueError("登记表必须是含 rules 的对象")
        rules = data["rules"]
    except Exception as e:
        print("登记表读取失败：%s" % e, file=sys.stderr); return 2
    docs = {}
    for d in a.doc:
        lab, _, p = d.partition("=")
        if not lab.strip() or not p or lab in docs:
            print("--doc 必须为唯一非空标签=文件路径", file=sys.stderr); return 2
        if not os.path.isfile(p):
            print("找不到 %s" % p, file=sys.stderr); return 2
        try:
            docs[lab] = M.load_text(p)
        except Exception as error:
            print("文档读取失败：%s" % error, file=sys.stderr); return 2
        if not docs[lab].strip():
            print("not_verified：文档为空：%s" % lab, file=sys.stderr); return 2
    try:
        evaluated = validate(rules,docs)
    except (ValueError,TypeError) as error:
        print("登记表/范围无效：%s" % error,file=sys.stderr); return 2
    bad = check(docs, rules)
    L = ["# 主张边界与防回潮检查\n", "规则 %d 条，文件 %s，实际评估 %d 个规则/文档组合。违反 %d 处。\n" % (len(rules), "、".join(docs), evaluated, len(bad))]
    for rid, lab, msg, why in bad:
        L.append("- **%s**［%s］%s%s" % (rid, lab, msg, ("　——" + why) if why else ""))
    rev_fail = []
    if a.reverse_test:
        L.append("\n## 反向测试\n")
        for r in rules:
            for lab, text in docs.items():
                if r.get("docs") and lab not in r["docs"]:
                    continue
                if r.get("type") == "forbidden":
                    sample = r.get("sample") or ("" if r.get("regex") else r.get("pattern"))
                    if not sample:
                        L.append("- %s［%s］**未验证**：正则规则缺少 sample" % (r["id"], lab)); rev_fail.append(r["id"]); continue
                    mod = inject(text, sample, (r.get("sections") or [None])[0])
                elif r.get("type") == "required":
                    mod = rx(r).sub("", text)
                elif r.get("type") == "if_then":
                    sample = r.get("sample") or ("" if r.get("regex") else r["if"])
                    if not sample:
                        L.append("- %s［%s］**未验证**：正则条件规则缺少 sample" % (r["id"], lab)); rev_fail.append(r["id"]); continue
                    mod = inject(rx(r, "then").sub("", text), sample, (r.get("sections") or [None])[0])
                else:
                    continue
                caught = any(x[0] == r["id"] and x[1] == lab for x in check({lab: mod}, [r]))
                L.append("- %s［%s］%s" % (r["id"], lab, "能报出" if caught else "**没报出**"))
                if not caught:
                    rev_fail.append(r["id"])
    L.append("\n边界：仅检查登记的字面/正则规则；退出 0 不证明主张真实、规则完整、作者同意或论文质量。反向测试只检验这些样例触发检查器的能力。")
    out = "\n".join(L) + "\n"
    if a.report:
        with M.wfile(a.report) as f:
            f.write(out)
    print(out if not a.report else "违反 %d 处；反向测试没报出 %d 条" % (len(bad), len(rev_fail)))
    return 1 if (bad or rev_fail) else 0


if __name__ == "__main__":
    sys.exit(main())
