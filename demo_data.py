"""
demo_data.py
------------
Three ready-made "extracted invoices" so the app can be demonstrated without
an API key, without an internet connection, and without an invoice in hand.

All names, GSTINs and amounts are DUMMY data. The GSTINs have valid check
digits (so they pass the checksum test) but do not belong to real businesses.
"""

from schema import normalize_invoice_data

_CLEAN = {
    "seller_name": "Sharma Steel Works",
    "seller_gstin": "27AKSPS4821M1ZC",
    "buyer_name": "Gupta Traders",
    "buyer_gstin": "27AAGFG7712K1Z6",
    "invoice_number": "SSW/26-27/0142",
    "invoice_date": "2026-08-14",
    "document_type": "tax_invoice",
    "place_of_supply": "27-Maharashtra",
    "hsn_sac_codes": ["7308"],
    "item_descriptions": ["MS angle 40x40x5 mm, 2 tonnes"],
    "taxable_value": 50000,
    "cgst": 4500,
    "sgst": 4500,
    "igst": 0,
    "total_amount": 59000,
}

_MISTAKES = {
    "seller_name": "Nagpur Fasteners Pvt Ltd",
    "seller_gstin": "27AADCV5510R1ZU",
    "buyer_name": "Deccan Engineering",
    "buyer_gstin": "36AABCP3390D1ZX",  # wrong last character on purpose
    "invoice_number": "NFP/INV/2026-27/000123",  # 22 characters, limit is 16
    "invoice_date": "2026-09-02",
    "document_type": "tax_invoice",
    "place_of_supply": "Telangana",  # inter-state sale...
    "hsn_sac_codes": ["73"],  # 2-digit code
    "item_descriptions": ["Hex bolts M12, 5000 pcs"],
    "taxable_value": 20000,
    "cgst": 1800,  # ...but CGST + SGST charged instead of IGST
    "sgst": 1800,
    "igst": 0,
    "total_amount": 24000,  # should be 23,600
}

_OLD_RATE = {
    "seller_name": "Kavita Garments",
    "seller_gstin": "27AAHFM9034B1ZF",
    "buyer_name": "Rohan Retail",
    "buyer_gstin": "27AAGFG7712K1Z6",
    "invoice_number": "KG-0457",
    "invoice_date": "2026-08-20",
    "document_type": "tax_invoice",
    "place_of_supply": "Maharashtra",
    "hsn_sac_codes": ["6109"],
    "item_descriptions": ["Cotton T-shirts, 200 pcs"],
    "taxable_value": 10000,
    "cgst": 600,  # 12% slab, removed on 22 Sep 2025
    "sgst": 600,
    "igst": 0,
    "total_amount": 11200,
}

DEMOS = {
    "clean": {
        "title": "Clean invoice",
        "risk": "low",
        "blurb": "Everything is correct. Shows what a passing report looks like.",
        "data": _CLEAN,
    },
    "mistakes": {
        "title": "Invoice with mistakes",
        "risk": "high",
        "blurb": "Wrong tax type, bad GSTIN, wrong total. Shows the fix list.",
        "data": _MISTAKES,
    },
    "old_rate": {
        "title": "Old GST rate",
        "risk": "medium",
        "blurb": "12% charged after the 22 Sep 2025 rate change.",
        "data": _OLD_RATE,
    },
}


def load_demo(key):
    """Return a clean, normalised copy of a demo invoice."""
    return normalize_invoice_data(DEMOS[key]["data"])
