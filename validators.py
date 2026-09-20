"""
validators.py
-------------
The RULE ENGINE. No AI here - every check is plain Python, so results are
predictable and can be explained line by line.

Public function:
    run_all_checks(data, today=None) -> list[dict]

Every check returns a dict:
    {
      "id":      "tax_type",
      "name":    "Tax type (CGST+SGST vs IGST)",
      "status":  "pass" | "warn" | "fail",
      "message": "what we found",
      "fix":     "what to do about it"  (empty when passed),
      "weight":  how much this check counts towards the score,
    }
"""

import re
from datetime import date

from schema import parse_date

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------
GSTIN_REGEX = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# GST state / UT codes (first two digits of a GSTIN)
STATE_CODES = {
    "01": "Jammu & Kashmir", "02": "Himachal Pradesh", "03": "Punjab",
    "04": "Chandigarh", "05": "Uttarakhand", "06": "Haryana", "07": "Delhi",
    "08": "Rajasthan", "09": "Uttar Pradesh", "10": "Bihar", "11": "Sikkim",
    "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
    "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam",
    "19": "West Bengal", "20": "Jharkhand", "21": "Odisha",
    "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "25": "Daman & Diu (old code)", "26": "Dadra & Nagar Haveli and Daman & Diu",
    "27": "Maharashtra", "28": "Andhra Pradesh (old code)", "29": "Karnataka",
    "30": "Goa", "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu",
    "34": "Puducherry", "35": "Andaman & Nicobar Islands", "36": "Telangana",
    "37": "Andhra Pradesh", "38": "Ladakh", "97": "Other Territory",
    "99": "Centre Jurisdiction",
}

# Extra spellings people actually write on invoices
_STATE_ALIASES = {
    "orissa": "21", "pondicherry": "34", "uttaranchal": "05", "telengana": "36",
    "chattisgarh": "22", "new delhi": "07", "nct of delhi": "07", "delhi ncr": "07",
    "j and k": "01", "jammu and kashmir": "01", "andaman and nicobar": "35",
    "andaman and nicobar islands": "35", "dadra and nagar haveli": "26",
    "daman and diu": "26", "dnh": "26",
}

# GST 2.0 (56th GST Council) - new rate structure applies from this date
GST2_START = date(2025, 9, 22)
RATES_BEFORE_GST2 = [0, 0.1, 0.25, 1.5, 3, 5, 12, 18, 28]
RATES_AFTER_GST2 = [0, 0.1, 0.25, 1.5, 3, 5, 18, 40]
REMOVED_SLABS = [12, 28]  # no longer standard slabs after GST2_START

GST_START_DATE = date(2017, 7, 1)
AMOUNT_TOLERANCE = 1.0  # rupees - invoices are rounded

STATUS_FACTOR = {"pass": 1.0, "warn": 0.5, "fail": 0.0}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _check(cid, name, status, message, fix="", weight=5):
    return {
        "id": cid, "name": name, "status": status,
        "message": message, "fix": fix, "weight": weight,
    }


def _num(value):
    """None -> 0.0 so we can add tax amounts safely."""
    return float(value) if value is not None else 0.0


def _money(value):
    """Plain rupee text used inside messages, e.g. ₹1,18,000.00"""
    return "₹" + format_inr(value)


def format_inr(value):
    """Indian digit grouping: 1234567.5 -> '12,34,567.50'"""
    if value is None:
        return "—"
    negative = value < 0
    whole, _, frac = f"{abs(value):.2f}".partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{'-' if negative else ''}{whole}.{frac}"


def gstin_checksum_char(first14):
    """
    Compute the 15th character (check digit) of a GSTIN from its first 14.

    Algorithm (public, mod-36):
      - give each character a value: 0-9 -> 0-9, A-Z -> 10-35
      - multiply by 1 (odd positions) or 2 (even positions)
      - split each product into quotient and remainder by 36 and add both
      - check digit = (36 - (sum mod 36)) mod 36, converted back to a character
    """
    total = 0
    for index, char in enumerate(first14):
        value = GSTIN_CHARS.index(char)
        factor = 1 if index % 2 == 0 else 2
        product = value * factor
        total += product // 36 + product % 36
    return GSTIN_CHARS[(36 - total % 36) % 36]


def state_code_of(gstin):
    """First two digits of a GSTIN, or None."""
    if gstin and len(gstin) >= 2 and gstin[:2].isdigit():
        return gstin[:2]
    return None


def _normalize_words(text):
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _build_name_index():
    index = {}
    for code, name in STATE_CODES.items():
        if code in ("25", "28", "97", "99"):
            continue  # old / special codes are not matched by name
        index[_normalize_words(name)] = code
    index.update(_STATE_ALIASES)
    return index


_NAME_INDEX = _build_name_index()


def resolve_state_code(text):
    """
    Turn a place-of-supply string into a 2-digit state code.
    Handles '27', '27-Maharashtra', 'Maharashtra (27)', 'maharashtra'.
    """
    if not text:
        return None
    raw = str(text).strip()
    match = re.search(r"(?<!\d)(\d{2})(?!\d)", raw)
    if match and match.group(1) in STATE_CODES:
        return match.group(1)
    words = _normalize_words(raw)
    best = None
    for name, code in _NAME_INDEX.items():
        if re.search(rf"\b{re.escape(name)}\b", words):
            if best is None or len(name) > len(best[0]):
                best = (name, code)
    return best[1] if best else None


def state_label(code):
    return f"{STATE_CODES.get(code, 'Unknown')} ({code})" if code else "unknown"


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------
REQUIRED_FIELDS = {
    "seller_name": "seller name",
    "seller_gstin": "seller GSTIN",
    "invoice_number": "invoice number",
    "invoice_date": "invoice date",
    "place_of_supply": "place of supply",
    "taxable_value": "taxable value",
    "total_amount": "total amount",
}


def check_mandatory_fields(data):
    missing = [label for field, label in REQUIRED_FIELDS.items() if data.get(field) in (None, "", [])]
    if missing:
        return _check(
            "mandatory", "Mandatory fields", "fail",
            f"Missing: {', '.join(missing)}.",
            "Add the missing details. If they are on the invoice but we could not read them, "
            "correct them in the 'Extracted data' tab and re-check.",
            weight=15,
        )
    return _check("mandatory", "Mandatory fields", "pass", "All mandatory fields are present.", weight=15)


def check_document_type(data):
    doc_type = data.get("document_type")
    name = "Document type"
    tax_total = _num(data.get("cgst")) + _num(data.get("sgst")) + _num(data.get("igst"))

    if doc_type == "tax_invoice":
        return _check("doc_type", name, "pass", "This is a tax invoice.", weight=10)
    if doc_type == "bill_of_supply":
        if tax_total > 0:
            return _check(
                "doc_type", name, "fail",
                "This is a bill of supply, but GST is charged on it.",
                "A bill of supply must not charge GST. Issue a tax invoice instead if GST applies.",
                weight=10,
            )
        return _check(
            "doc_type", name, "pass",
            "Bill of supply with no GST charged (normal for composition or exempt sellers).",
            weight=10,
        )
    if doc_type in ("proforma", "estimate", "quotation"):
        label = {"proforma": "a proforma invoice", "estimate": "an estimate", "quotation": "a quotation"}[doc_type]
        return _check(
            "doc_type", name, "fail",
            f"This document is {label}, not a tax invoice. ITC cannot be claimed on it.",
            "Ask the seller for a proper tax invoice before making or claiming the payment.",
            weight=10,
        )
    if doc_type in ("credit_note", "debit_note"):
        return _check(
            "doc_type", name, "warn",
            "This is a credit or debit note. Some checks below are written for tax invoices.",
            "Make sure it refers to the original invoice number and date.",
            weight=10,
        )
    return _check(
        "doc_type", name, "warn",
        "We could not confirm that this is a tax invoice.",
        "A GST invoice should be clearly titled 'Tax Invoice'.",
        weight=10,
    )


def validate_gstin(gstin):
    """
    Returns (ok, message). Runs 4 tests in order:
    length -> pattern -> state code -> check digit.
    """
    if len(gstin) != 15:
        return False, f"{gstin} has {len(gstin)} characters. A GSTIN must have exactly 15."
    if not GSTIN_REGEX.match(gstin):
        return False, (
            f"{gstin} does not follow the GSTIN pattern "
            "(2 digits, 5 letters, 4 digits, 1 letter, 1 letter/digit, 'Z', 1 letter/digit)."
        )
    code = gstin[:2]
    if code not in STATE_CODES:
        return False, f"{gstin} starts with {code}, which is not a valid state code."
    expected = gstin_checksum_char(gstin[:14])
    if gstin[14] != expected:
        return False, (
            f"{gstin} fails the GSTIN check-digit test (last character should be {expected}). "
            "This usually means a typo, or the AI misread one character."
        )
    return True, f"{gstin} is valid. State: {state_label(code)}."


def check_seller_gstin(data):
    gstin = data.get("seller_gstin")
    if not gstin:
        return None  # already reported under mandatory fields
    ok, message = validate_gstin(gstin)
    if ok:
        return _check("seller_gstin", "Seller GSTIN", "pass", message, weight=15)
    return _check(
        "seller_gstin", "Seller GSTIN", "fail", message,
        "Compare with the seller's GST registration certificate, then correct the GSTIN. "
        "A wrong GSTIN will not match in the buyer's GSTR-2B.",
        weight=15,
    )


def check_buyer_gstin(data):
    gstin = data.get("buyer_gstin")
    if not gstin:
        return _check(
            "buyer_gstin", "Buyer GSTIN", "warn",
            "No buyer GSTIN found.",
            "Fine for a sale to a consumer (B2C). For a business buyer, add their GSTIN, "
            "otherwise they cannot claim ITC.",
            weight=8,
        )
    ok, message = validate_gstin(gstin)
    if ok:
        return _check("buyer_gstin", "Buyer GSTIN", "pass", message, weight=8)
    return _check(
        "buyer_gstin", "Buyer GSTIN", "fail", message,
        "Confirm the buyer's GSTIN with them and correct it.",
        weight=8,
    )


def check_invoice_number(data):
    number = data.get("invoice_number")
    if not number:
        return None
    name = "Invoice number format"
    if len(number) > 16:
        return _check(
            "invoice_number", name, "fail",
            f"'{number}' has {len(number)} characters. GST rules allow at most 16.",
            "Use a shorter serial number, for example INV/26-27/0142.",
            weight=4,
        )
    if not re.fullmatch(r"[A-Za-z0-9/\-]+", number):
        return _check(
            "invoice_number", name, "warn",
            f"'{number}' contains characters other than letters, digits, '-' and '/'.",
            "GST rules allow only letters, numbers, hyphen and slash in the invoice number.",
            weight=4,
        )
    return _check(
        "invoice_number", name, "pass",
        f"'{number}' is within 16 characters and uses allowed characters.",
        weight=4,
    )


def check_invoice_date(data, today):
    raw = data.get("invoice_date")
    if not raw:
        return None
    name = "Invoice date"
    parsed = parse_date(raw)
    if parsed is None:
        return _check(
            "invoice_date", name, "fail",
            f"'{raw}' is not a date we can understand.",
            "Write the date as DD/MM/YYYY.",
            weight=5,
        )
    if parsed > today:
        return _check(
            "invoice_date", name, "warn",
            f"The invoice date ({parsed:%d %b %Y}) is in the future.",
            "Check the date. An invoice cannot be dated later than the day it is issued.",
            weight=5,
        )
    if parsed < GST_START_DATE:
        return _check(
            "invoice_date", name, "fail",
            f"The invoice date ({parsed:%d %b %Y}) is before GST started (1 Jul 2017).",
            "Check the date on the invoice.",
            weight=5,
        )
    return _check("invoice_date", name, "pass", f"Invoice dated {parsed:%d %b %Y}.", weight=5)


def _no_tax_amounts(data):
    """True when the AI found no CGST / SGST / IGST amount at all (different from a printed 0)."""
    return all(data.get(f) is None for f in ("cgst", "sgst", "igst"))


def check_currency(data):
    currency = data.get("currency")
    if not currency or currency == "INR":
        return None
    return _check(
        "currency", "Currency", "fail",
        f"Amounts are in {currency}. A GST invoice must show amounts in Indian rupees (INR). "
        "GST amount checks were skipped.",
        "Ask for an INR invoice. (Export invoices may show a foreign currency, but the INR value must also be stated.)",
        weight=8,
    )


def check_hsn(data):
    codes = data.get("hsn_sac_codes") or []
    name = "HSN / SAC code"
    if not codes:
        return _check(
            "hsn", name, "warn",
            "No HSN or SAC code found.",
            "Add a 4-digit HSN (6-digit if annual turnover is above ₹5 crore) for goods, "
            "or a 6-digit SAC for services.",
            weight=8,
        )
    bad = [c for c in codes if len(c) not in (4, 6, 8)]
    if bad:
        return _check(
            "hsn", name, "warn",
            f"Unusual HSN/SAC length: {', '.join(bad)}. Valid codes have 4, 6 or 8 digits.",
            "Use the full HSN (goods) or SAC (services, starts with 99) code for each item.",
            weight=8,
        )
    return _check("hsn", name, "pass", f"HSN/SAC present: {', '.join(codes)}.", weight=8)


def check_tax_type(data):
    """Intra-state -> CGST+SGST. Inter-state -> IGST."""
    name = "Tax type (CGST+SGST or IGST)"
    if data.get("document_type") == "bill_of_supply":
        return None

    cgst, sgst, igst = _num(data.get("cgst")), _num(data.get("sgst")), _num(data.get("igst"))
    if cgst + sgst + igst == 0:
        return None  # nothing to compare - the rate check reports zero tax

    seller_code = state_code_of(data.get("seller_gstin"))
    pos_code = resolve_state_code(data.get("place_of_supply"))
    if not seller_code or not pos_code:
        return _check(
            "tax_type", name, "warn",
            "Could not compare the seller's state with the place of supply, "
            "so the tax split could not be verified.",
            "Make sure the seller GSTIN and the place of supply are both clearly readable. "
            "(Exports and SEZ supplies follow different rules.)",
            weight=15,
        )

    same_state = seller_code == pos_code
    seller_state, pos_state = state_label(seller_code), state_label(pos_code)

    if same_state:
        if cgst > 0 and sgst > 0 and igst == 0:
            return _check(
                "tax_type", name, "pass",
                f"Seller and place of supply are both in {seller_state}, and CGST + SGST are charged.",
                weight=15,
            )
        if igst > 0:
            return _check(
                "tax_type", name, "fail",
                f"Seller and place of supply are both in {seller_state} (same state), "
                "so CGST + SGST should be charged. This invoice charges IGST.",
                "Replace IGST with equal CGST and SGST (half the rate each).",
                weight=15,
            )
        return _check(
            "tax_type", name, "fail",
            "Same-state sale needs both CGST and SGST, but only one of them is charged.",
            "Charge CGST and SGST at equal amounts.",
            weight=15,
        )

    # inter-state
    if igst > 0 and cgst == 0 and sgst == 0:
        return _check(
            "tax_type", name, "pass",
            f"Seller is in {seller_state}, place of supply is {pos_state} (different states), "
            "and IGST is charged.",
            weight=15,
        )
    if cgst > 0 or sgst > 0:
        return _check(
            "tax_type", name, "fail",
            f"Seller is in {seller_state} but place of supply is {pos_state}. "
            "This is an inter-state sale, so IGST is required. This invoice charges CGST/SGST.",
            "Replace CGST + SGST with a single IGST amount at the full rate.",
            weight=15,
        )
    return None


def check_cgst_equals_sgst(data):
    cgst, sgst = _num(data.get("cgst")), _num(data.get("sgst"))
    if cgst <= 0 or sgst <= 0:
        return None
    name = "CGST equals SGST"
    if abs(cgst - sgst) <= AMOUNT_TOLERANCE:
        return _check("cgst_sgst", name, "pass", f"CGST and SGST match ({_money(cgst)} each).", weight=5)
    return _check(
        "cgst_sgst", name, "fail",
        f"CGST is {_money(cgst)} but SGST is {_money(sgst)}. They should be equal.",
        "Recalculate: CGST and SGST are each half of the total GST rate.",
        weight=5,
    )


def check_tax_rate(data):
    """
    Implied rate = total tax / taxable value. It must match a valid GST slab.
    The list of valid slabs depends on the invoice date (GST 2.0 from 22 Sep 2025).
    """
    name = "GST rate"
    taxable = data.get("taxable_value")
    if taxable is None or taxable <= 0:
        return None
    tax_total = _num(data.get("cgst")) + _num(data.get("sgst")) + _num(data.get("igst"))
    invoice_date = parse_date(data.get("invoice_date"))
    after_reform = invoice_date is None or invoice_date >= GST2_START
    allowed = RATES_AFTER_GST2 if after_reform else RATES_BEFORE_GST2
    tolerance = max(AMOUNT_TOLERANCE, taxable * 0.0005)
    implied = tax_total / taxable * 100

    if data.get("document_type") == "bill_of_supply":
        return None

    if _no_tax_amounts(data):
        return _check(
            "rate", name, "warn",
            "No tax amounts (CGST / SGST / IGST) were found, so the GST rate could not be checked.",
            "Print the tax amounts on the invoice (not only a percentage), or enter them in "
            "'Extracted data' and re-check.",
            weight=8,
        )
    if tax_total == 0:
        return _check(
            "rate", name, "warn",
            "No GST is charged on this invoice.",
            "Zero GST is valid only for nil-rated, exempt or export supplies. "
            "Otherwise add the correct tax.",
            weight=8,
        )

    for rate in allowed:
        if abs(tax_total - taxable * rate / 100) <= tolerance:
            return _check(
                "rate", name, "pass",
                f"Total GST is {implied:.1f}% of the taxable value, which is a valid slab.",
                weight=8,
            )

    if after_reform:
        for rate in REMOVED_SLABS:
            if abs(tax_total - taxable * rate / 100) <= tolerance:
                return _check(
                    "rate", name, "warn",
                    f"GST works out to {rate}%. The 12% and 28% slabs were removed "
                    "from 22 Sep 2025 (now mainly 5%, 18% and 40%).",
                    "Check the item's current rate. It has most likely moved to 5% or 18%.",
                    weight=8,
                )

    return _check(
        "rate", name, "warn",
        f"GST works out to {implied:.2f}% of the taxable value, which is not a standard slab.",
        "Recheck the tax amount. If the invoice has items at different rates, "
        "this can be ignored.",
        weight=8,
    )


def check_total(data):
    taxable, total = data.get("taxable_value"), data.get("total_amount")
    if taxable is None or total is None:
        return None
    name = "Total amount"
    expected = (
        taxable + _num(data.get("cgst")) + _num(data.get("sgst")) + _num(data.get("igst"))
        + _num(data.get("cess")) + _num(data.get("round_off"))
    )
    diff = abs(expected - total)
    if _no_tax_amounts(data) and total - taxable > AMOUNT_TOLERANCE:
        return _check(
            "total", name, "warn",
            f"The total ({_money(total)}) is higher than the taxable value ({_money(taxable)}), but no tax "
            "amounts were found. The tax may be printed only as a percentage.",
            "Print CGST/SGST/IGST amounts on the invoice, or enter them in 'Extracted data' and re-check.",
            weight=12,
        )
    if diff <= AMOUNT_TOLERANCE:
        return _check(
            "total", name, "pass",
            f"Taxable value + taxes = {_money(expected)}, which matches the total.",
            weight=12,
        )
    return _check(
        "total", name, "fail",
        f"Taxable value + taxes add up to {_money(expected)}, but the invoice total is {_money(total)} "
        f"(difference {_money(diff)}).",
        "Recalculate the total. If there are extra charges such as TCS or freight that are not in "
        "the taxable value, add them to the Extracted data and re-check.",
        weight=12,
    )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def run_all_checks(data, today=None):
    """Run every check and return only the ones that apply."""
    today = today or date.today()
    foreign = data.get("currency") not in (None, "", "INR")
    results = [
        check_mandatory_fields(data),
        check_document_type(data),
        check_currency(data),
        check_seller_gstin(data),
        check_buyer_gstin(data),
        check_invoice_number(data),
        check_invoice_date(data, today),
        check_hsn(data),
    ]
    if not foreign:  # GST amount rules only make sense for rupee invoices
        results += [
            check_tax_type(data),
            check_cgst_equals_sgst(data),
            check_tax_rate(data),
            check_total(data),
        ]
    return [r for r in results if r is not None]
