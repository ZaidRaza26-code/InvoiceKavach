"""
report.py
---------
Turns the list of check results into things the user actually wants:
  * a score and an ITC-risk level
  * a ready-to-send message for the supplier
  * JSON / CSV exports

No third-party imports, so this is easy to test.
"""

import csv
import io
import json
import re

from schema import ALL_FIELDS, FIELD_LABELS
from validators import STATUS_FACTOR, format_inr

RISK_TEXT = {
    "low": ("Low risk", "Looks good. Safe to send or claim once you have double-checked the values."),
    "medium": ("Medium risk", "A few things need a second look before you rely on this invoice."),
    "high": ("High risk", "Fix these problems before sending the invoice or claiming ITC on it."),
}


def build_report(checks):
    """Score (0-100), counts and risk level."""
    counts = {"pass": 0, "warn": 0, "fail": 0}
    earned = possible = 0.0
    for check in checks:
        counts[check["status"]] += 1
        earned += check["weight"] * STATUS_FACTOR[check["status"]]
        possible += check["weight"]

    score = round(earned / possible * 100) if possible else 0

    if counts["fail"] > 0:
        risk = "high"
    elif counts["warn"] > 0:
        risk = "medium"
    else:
        risk = "low"

    title, summary = RISK_TEXT[risk]
    return {
        "score": score,
        "counts": counts,
        "risk": risk,
        "risk_title": title,
        "summary": summary,
        "total_checks": len(checks),
    }


def issues_of(checks):
    """Failed checks first, then warnings."""
    fails = [c for c in checks if c["status"] == "fail"]
    warns = [c for c in checks if c["status"] == "warn"]
    return fails + warns


def supplier_message(data, checks):
    """A polite, copy-paste message listing what the supplier must correct."""
    issues = issues_of(checks)
    if not issues:
        return ""

    seller = data.get("seller_name") or "Sir/Madam"
    number = data.get("invoice_number")
    date_text = data.get("invoice_date")
    ref = "your invoice"
    if number:
        ref += f" {number}"
    if date_text:
        ref += f" dated {date_text}"

    lines = [
        f"Hello {seller},",
        "",
        f"While checking {ref}, we found a few points to correct so that the invoice is "
        "GST-compliant and the input tax credit is not affected:",
        "",
    ]
    for i, issue in enumerate(issues, 1):
        lines.append(f"{i}. {issue['name']}: {issue['message']}")
        if issue["fix"]:
            lines.append(f"   Suggested correction: {issue['fix']}")
    lines += [
        "",
        "Please send a corrected invoice (or a credit note and a fresh invoice, if the "
        "original has already been reported in your GST return).",
        "",
        "Thank you.",
    ]
    return "\n".join(lines)


def _safe_name(text):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", text or "invoice").strip("_") or "invoice"


def export_filename(data, extension):
    return f"invoicekavach_{_safe_name(data.get('invoice_number'))}.{extension}"


def to_json(data, checks, report):
    payload = {
        "extracted_data": data,
        "summary": {
            "score": report["score"],
            "itc_risk": report["risk"],
            "passed": report["counts"]["pass"],
            "warnings": report["counts"]["warn"],
            "failed": report["counts"]["fail"],
        },
        "checks": [
            {k: c[k] for k in ("name", "status", "message", "fix")} for c in checks
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def to_csv(data, checks, report):
    """One row: all extracted fields + summary. utf-8-sig so Excel shows ₹ correctly."""
    row = {}
    for field in ALL_FIELDS:
        value = data.get(field)
        if isinstance(value, list):
            value = "; ".join(value)
        row[FIELD_LABELS[field]] = "" if value is None else value
    row["Score"] = report["score"]
    row["ITC risk"] = report["risk"]
    row["Failed checks"] = "; ".join(c["name"] for c in checks if c["status"] == "fail")
    row["Warnings"] = "; ".join(c["name"] for c in checks if c["status"] == "warn")

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(row.keys()))
    writer.writeheader()
    writer.writerow(row)
    return buffer.getvalue().encode("utf-8-sig")


def amount_text(value):
    """₹ text for display, or a dash."""
    return "—" if value is None else "₹" + format_inr(value)
