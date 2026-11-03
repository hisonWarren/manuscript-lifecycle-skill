#!/usr/bin/env python3
"""Check explicit, version-bound evidence records; never infer scientific support.

python verify_evidence.py evidence.json --report evidence_report.json

schema_version=1; manuscript={path,sha256}; checks is a nonempty list.
All checks: id, kind (numeric/quote/citation), manuscript_anchor (unique exact
passage, whitespace normalized only), source={path,sha256}.
numeric: row_key={column:exact_cell}, value_column, manuscript_value (string),
source_unit,target_unit,scale (string), rounding (half_up/half_even),
context={source_column:exact_cell}. Every context cell must also occur as a
bounded phrase in manuscript_anchor; context must include at least one field.
quote/citation: source_passage (unique exact passage), source_location.
citation additionally: access_level (fulltext/abstract), review={decision,
reviewer, reviewed_at, rationale}. The review is only a recorded assertion:
the script cannot authenticate the reviewer, judge entailment, or grant a
semantic pass. Citation checks always return review_required.

Paths are relative to the manifest. Hashes refer to raw file bytes. Numeric
source is CSV/TSV only. Supported conversion is identity or proportion<->percent;
other transformations require a separately auditable derivation.
Exit 0: all requested mechanical checks matched; 1: failed/not_verified/review;
2: invalid input schema. A 0 is never manuscript-wide coverage or semantic proof.
"""
import argparse
import csv
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mslib as M
from output_safety import declared_paths, output_path, write_fresh


class EvidenceError(Exception):
    def __init__(self, message, status="not_verified"):
        super().__init__(message)
        self.status = status


def required_text(obj, key):
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise EvidenceError("Missing/non-string field: " + key)
    return value


def ws(text):
    return re.sub(r"\s+", " ", text).strip()


def anchored(text, anchor, label):
    anchor = ws(anchor)
    if not anchor or ws(text).count(anchor) != 1:
        raise EvidenceError(label + " must identify exactly one nonempty passage", "failed")
    return anchor


def file_record(record, base):
    if not isinstance(record, dict):
        raise EvidenceError("Missing file record")
    path = Path(required_text(record, "path"))
    path = path if path.is_absolute() else base / path
    if not path.is_file() or path.stat().st_size == 0:
        raise EvidenceError("Missing/empty file: " + str(path))
    expected = required_text(record, "sha256").lower()
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or actual != expected:
        raise EvidenceError("Hash mismatch: " + str(path), "failed")
    return path, {"path": str(path.resolve()), "sha256": actual}


def decimal_value(value, label):
    try:
        result = Decimal(value.replace("−", "-").replace(",", ""))
        if not result.is_finite():
            raise InvalidOperation
        return result
    except (InvalidOperation, ValueError, AttributeError):
        raise EvidenceError("Invalid finite numeric value: " + label, "failed")


def bounded_phrase(phrase, text):
    if M.CJK.search(phrase):
        return phrase in text  # Chinese has no whitespace word boundaries; semantic review remains required.
    if re.fullmatch(r"[+−-]?\d+(?:\.\d+)?(?:[eE][+−-]?\d+)?", phrase):
        # A count followed by 人 is a complete numeric context; 112 must not match 2112 or 112.5.
        return re.search(r"(?<![A-Za-z0-9_.+−-])" + re.escape(phrase) +
                         r"(?![A-Za-z0-9_]|\.\d)", text) is not None
    return re.search(r"(?<![A-Za-z0-9_])" + re.escape(phrase) + r"(?![A-Za-z0-9_])", text, re.I) is not None


def check_numeric(check, source, anchor):
    if source.suffix.lower() not in (".csv", ".tsv"):
        raise EvidenceError("Numeric source must be CSV/TSV")
    key, context = check.get("row_key"), check.get("context")
    if not isinstance(key, dict) or not key or not isinstance(context, dict) or not context:
        raise EvidenceError("Nonempty row_key and context objects are required")
    if not all(isinstance(k, str) and k and isinstance(v, str) and v for mapping in (key, context) for k,v in mapping.items()):
        raise EvidenceError("Row keys and context values must be nonempty strings")
    with source.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t" if source.suffix.lower()==".tsv" else ",")
        columns = reader.fieldnames or []
        rows = list(reader)
    column = required_text(check, "value_column")
    if len(columns) != len(set(columns)) or any(c not in columns for c in [*key, *context, column]):
        raise EvidenceError("Duplicate or missing CSV columns", "failed")
    selected = [r for r in rows if all(r.get(k)==v for k,v in key.items())]
    if len(selected) != 1:
        raise EvidenceError("row_key must select exactly one source row", "failed")
    row = selected[0]
    for k, value in context.items():
        if row.get(k) != value or not bounded_phrase(value, anchor):
            raise EvidenceError("Context mismatch for column " + k, "failed")
    source_number = decimal_value(row.get(column), "source cell")
    literal = required_text(check, "manuscript_value")
    if not re.search(r"(?<![A-Za-z0-9_.+−-])" + re.escape(literal) + r"(?![A-Za-z0-9_]|\.\d|%)", anchor):
        raise EvidenceError("manuscript_value not present as a bounded token in anchor", "failed")
    target_number = decimal_value(literal.rstrip("%"), "manuscript_value")
    source_unit, target_unit = required_text(check, "source_unit"), required_text(check, "target_unit")
    scale = decimal_value(required_text(check, "scale"), "scale")
    if literal.endswith("%") and target_unit != "percent":
        raise EvidenceError("Percent sign contradicts target_unit", "failed")
    conversions = {("proportion", "percent"):Decimal(100), ("percent", "proportion"):Decimal("0.01")}
    allowed_scale = Decimal(1) if source_unit == target_unit else conversions.get((source_unit,target_unit))
    if allowed_scale is None or scale != allowed_scale:
        raise EvidenceError("Unsupported/inconsistent unit conversion", "failed")
    rounding = check.get("rounding")
    if rounding not in ("half_up", "half_even"):
        raise EvidenceError("rounding must be half_up or half_even")
    quant = Decimal(1).scaleb(target_number.as_tuple().exponent)
    rounded = (source_number * scale).quantize(quant, rounding=ROUND_HALF_UP if rounding=="half_up" else ROUND_HALF_EVEN)
    if rounded != target_number:
        raise EvidenceError("Numeric value/sign/precision mismatch", "failed")
    return {"source_value":str(source_number), "reported_value":str(target_number), "scale":str(scale),
            "source_unit":source_unit, "target_unit":target_unit, "row_key":key, "context":context}


def verify(data, base):
    if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("checks"), list) or not data["checks"]:
        raise ValueError("schema_version=1 and a nonempty checks list are required")
    if any(not isinstance(c,dict) for c in data["checks"]):
        raise ValueError("Every check must be an object")
    ids=[c.get("id") for c in data["checks"]]
    if any(not isinstance(x,str) or not x.strip() for x in ids) or len(set(ids)) != len(ids):
        raise ValueError("Check IDs must be nonempty and unique")
    manuscript, manuscript_receipt = file_record(data.get("manuscript"), base)
    manuscript_text = M.load_text(str(manuscript))
    results=[]
    for check in data["checks"]:
        result={"id":check["id"],"kind":check.get("kind"),"status":"not_verified"}
        try:
            anchor = anchored(manuscript_text, required_text(check,"manuscript_anchor"), "manuscript_anchor")
            source, source_receipt = file_record(check.get("source"),base)
            if source.resolve() == manuscript.resolve():
                raise EvidenceError("Manuscript cannot be its own evidence source", "failed")
            result["source"] = source_receipt
            kind = required_text(check,"kind")
            if kind == "numeric":
                result["details"] = check_numeric(check, source, anchor)
                result["status"] = "verified_mechanical"
            elif kind in ("quote","citation"):
                passage = anchored(M.load_text(str(source)), required_text(check,"source_passage"), "source_passage")
                result["source_location"] = required_text(check,"source_location")
                if kind == "quote":
                    if passage not in anchor:
                        raise EvidenceError("Quoted source passage not present in manuscript anchor", "failed")
                    result["status"] = "verified_mechanical"
                else:
                    if check.get("access_level") not in ("fulltext","abstract"):
                        raise EvidenceError("Citation access_level must be fulltext or abstract")
                    review = check.get("review")
                    if not isinstance(review,dict):
                        raise EvidenceError("Citation lacks a review record")
                    for key in ("reviewer","reviewed_at","rationale","decision"):
                        required_text(review,key)
                    if review["decision"] not in ("supports","partial","does_not_support","uncertain"):
                        raise EvidenceError("Unknown citation review decision")
                    result["status"] = "review_required"
                    result["recorded_review"] = review
                    result["reason"] = "Passage located; semantic decision is a supplied record, not machine verified. Reviewer identity and source authenticity not authenticated."
            else:
                raise EvidenceError("Unknown check kind: " + kind)
        except (EvidenceError, OSError, ValueError, InvalidOperation) as e:
            result["status"] = getattr(e,"status","not_verified")
            result["reason"] = str(e)
        results.append(result)
    return {"schema_version":1,"manuscript":manuscript_receipt,"checks":results,
            "status":"verified_mechanical" if all(r["status"]=="verified_mechanical" for r in results) else "not_verified",
            "boundary":"Only listed anchors, recorded source bytes, CSV fields and arithmetic are checked. Coverage, scientific meaning, source authenticity, citation entailment and reviewer identity remain outside machine verification."}


def main():
    ap=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("manifest"); ap.add_argument("--report",default="")
    args=ap.parse_args()
    try:
        path=Path(args.manifest).resolve()
        out=output_path(args.report,[path]) if args.report else None
        data=json.loads(path.read_text(encoding="utf-8-sig"))
        if out:out=output_path(out,[path,*declared_paths(data,path.parent)])
        report=verify(data,path.parent)
    except EvidenceError as e:
        report={"schema_version":1,"status":e.status,"reason":str(e),"checks":[]}
    except (OSError,ValueError,TypeError,RuntimeError) as e:
        print(json.dumps({"status":"input_error","reason":str(e)},ensure_ascii=False)); return 2
    text=json.dumps(report,ensure_ascii=False,indent=2)
    if args.report:
        try:
            write_fresh(out,text+"\n")
        except (OSError,ValueError,RuntimeError) as e:
            print(json.dumps({"status":"input_error","reason":str(e)},ensure_ascii=False)); return 2
    print(text)
    return 0 if report["status"]=="verified_mechanical" else 1


if __name__=="__main__":
    sys.exit(main())
