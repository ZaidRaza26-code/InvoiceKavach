"""
schema.py
---------
The single source of truth for "what does an extracted invoice look like?".

Both the AI extractor and the rule engine use this file, so a field is
defined in exactly one place. This module has NO third-party imports, which
makes it easy to test.

Main pieces
  * FIELD_LABELS          - human-friendly names for every field
  * normalize_invoice_data - turns messy AI output into a clean, predictable dict
  * parse_date             - understands ISO and common Indian date formats
"""

import re
from datetime import date, datetime

# ---------------------------------------------------------------------------
# Field definitions
# ---------------------------------------------------------------------------
TEXT_FIELDS = [
    "seller_name",
    "seller_gstin",
    "buyer_name",
    "buyer_gstin",
    "invoice_number",
    "invoice_date",
    "place_of_supply",
    "document_type",
    "currency",
]
LIST_FIELDS = ["hsn_sac_codes", "item_descriptions"]
NUMBER_FIELDS = [
    "taxable_value",
    "cgst",
    "sgst",
    "igst",
    "cess",
    "round_off",
    "total_amount",
]
ALL_FIELDS = TEXT_FIELDS + LIST_FIELDS + NUMBER_FIELDS

FIELD_LABELS = {
    "seller_name": "Seller name",
    "seller_gstin": "Seller GSTIN",
    "buyer_name": "Buyer name",
    "buyer_gstin": "Buyer GSTIN",
    "invoice_number": "Invoice number",
    "invoice_date": "Invoice date",
    "place_of_supply": "Place of supply",
    "document_type": "Document type",
    "currency": "Currency",
    "hsn_sac_codes": "HSN / SAC codes",
    "item_descriptions": "Items",
    "taxable_value": "Taxable value",
    "cgst": "CGST",
    "sgst": "SGST / UTGST",
    "igst": "IGST",
    "cess": "Cess",
    "round_off": "Round off",
    "total_amount": "Total amount",
}

# Document types we recognise -> label shown in the UI
DOC_TYPE_LABELS = {
    "tax_invoice": "Tax invoice",
    "bill_of_supply": "Bill of supply",
    "proforma": "Proforma invoice",
    "estimate": "Estimate",
    "quotation": "Quotation",
    "credit_note": "Credit note",
    "debit_note": "Debit note",
    "other": "Other / unclear",
}

_EMPTY_WORDS = {"", "null", "none", "n/a", "na", "nil", "-", "--", "—", "not found", "not available"}


# ---------------------------------------------------------------------------
# Small converters
# ---------------------------------------------------------------------------
def _clean_text(value):
    """Return a stripped string, or None if the value is empty-ish."""
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in _EMPTY_WORDS:
        return None
    return text


def _clean_gstin(value):
    """GSTINs are upper-case with no spaces or dashes."""
    text = _clean_text(value)
    if text is None:
        return None
    text = re.sub(r"[\s\-]", "", text).upper()
    return text or None


def _to_number(value):
    """Convert '₹ 1,18,000.50', '(500)', 1200 ... to a float, or None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if text.lower() in _EMPTY_WORDS:
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = re.sub(r"(?i)rs\.?|inr|₹", "", text)
    text = re.sub(r"[,\s()]", "", text)
    try:
        number = float(text)
    except ValueError:
        return None
    return -number if negative else number


def _to_code_list(value):
    """HSN/SAC codes -> list of digit-only strings (no duplicates)."""
    if value is None:
        return []
    if isinstance(value, str):
        value = re.split(r"[,;/\s]+", value)
    codes = []
    for item in value:
        digits = re.sub(r"\D", "", str(item))
        if digits and digits not in codes:
            codes.append(digits)
    return codes[:10]


def _to_text_list(value, limit=5):
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    items = []
    for item in value:
        text = _clean_text(item)
        if text and text not in items:
            items.append(text)
    return items[:limit]


def _clean_currency(value):
    """'₹', 'Rs.', 'inr' -> 'INR'; '$', 'usd' -> 'USD'; other codes upper-cased."""
    text = _clean_text(value)
    if text is None:
        return None
    t = text.strip().upper().replace(".", "")
    if t in ("₹", "RS", "INR", "RUPEE", "RUPEES"):
        return "INR"
    if t in ("$", "US$", "USD"):
        return "USD"
    return t[:3]


def _clean_doc_type(value):
    """Map free text like 'Tax Invoice' / 'Bill of Supply' to our fixed list."""
    text = _clean_text(value)
    if text is None:
        return None
    t = text.lower().replace("_", " ")
    if "bill of supply" in t:
        return "bill_of_supply"
    if "proforma" in t or "pro forma" in t or "pro-forma" in t:
        return "proforma"
    if "estimate" in t:
        return "estimate"
    if "quotation" in t or "quote" in t:
        return "quotation"
    if "credit" in t:
        return "credit_note"
    if "debit" in t:
        return "debit_note"
    if "invoice" in t:
        return "tax_invoice"
    return "other"


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------
_DATE_FORMATS = [
    "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y",
    "%d %b %Y", "%d-%b-%Y", "%d %B %Y", "%d-%b-%y", "%b %d, %Y", "%B %d, %Y",
]


def parse_date(value):
    """Return a datetime.date, or None if it can't be understood."""
    if isinstance(value, date):
        return value
    text = _clean_text(value)
    if text is None:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def empty_invoice():
    """A blank invoice dict with every field present."""
    data = {f: None for f in TEXT_FIELDS + NUMBER_FIELDS}
    data.update({f: [] for f in LIST_FIELDS})
    return data


def normalize_invoice_data(raw):
    """
    Take whatever the AI (or the edit form) gave us and return a clean dict
    with exactly the fields we expect and the right types.
    """
    raw = raw if isinstance(raw, dict) else {}
    data = empty_invoice()

    for field in TEXT_FIELDS:
        if field in ("seller_gstin", "buyer_gstin"):
            data[field] = _clean_gstin(raw.get(field))
        elif field == "document_type":
            data[field] = _clean_doc_type(raw.get(field))
        elif field == "currency":
            data[field] = _clean_currency(raw.get(field))
        else:
            data[field] = _clean_text(raw.get(field))

    # Dates: store as ISO text when we can understand them, otherwise keep raw
    parsed = parse_date(data["invoice_date"])
    if parsed:
        data["invoice_date"] = parsed.isoformat()

    for field in NUMBER_FIELDS:
        data[field] = _to_number(raw.get(field))

    data["hsn_sac_codes"] = _to_code_list(raw.get("hsn_sac_codes"))
    data["item_descriptions"] = _to_text_list(raw.get("item_descriptions"))
    return data


def looks_empty(data):
    """True when the AI found almost nothing (probably not an invoice)."""
    key_fields = ["seller_gstin", "invoice_number", "invoice_date", "taxable_value", "total_amount"]
    found = sum(1 for f in key_fields if data.get(f) not in (None, "", []))
    return found <= 1
