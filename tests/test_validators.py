"""
Run with:  python tests/test_validators.py     (or: pytest)
Tests the rule engine with hand-written invoices - no AI, no internet.
"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from demo_data import DEMOS, load_demo
from report import build_report, supplier_message, to_csv, to_json
from schema import normalize_invoice_data
from validators import (format_inr, gstin_checksum_char, resolve_state_code, run_all_checks,
                        validate_gstin)

TODAY = date(2026, 9, 20)


def by_id(checks):
    return {c["id"]: c for c in checks}


def test_gstin_checksum_known_values():
    # Publicly documented valid GSTINs
    for gstin in ["27AAPFU0939F1ZV", "07AAGFF2194N1Z1", "27AAACR5055K1Z7"]:
        assert validate_gstin(gstin)[0], gstin
    assert gstin_checksum_char("27AAPFU0939F1Z") == "V"


def test_gstin_failures():
    assert not validate_gstin("27AAPFU0939F1ZX")[0]      # wrong check digit
    assert not validate_gstin("27AAPFU0939F1Z")[0]       # too short
    assert not validate_gstin("99XXXXX0000X1Z1")[0]      # bad pattern


def test_state_resolution():
    assert resolve_state_code("27-Maharashtra") == "27"
    assert resolve_state_code("Maharashtra (27)") == "27"
    assert resolve_state_code("telangana") == "36"
    assert resolve_state_code("Jammu and Kashmir") == "01"
    assert resolve_state_code("Andhra Pradesh") == "37"
    assert resolve_state_code("Narnia") is None


def test_indian_number_format():
    assert format_inr(1234567.5) == "12,34,567.50"
    assert format_inr(999) == "999.00"
    assert format_inr(59000) == "59,000.00"
    assert format_inr(None) == "—"


def test_clean_demo_passes_everything():
    checks = run_all_checks(load_demo("clean"), TODAY)
    assert all(c["status"] == "pass" for c in checks), [(c["id"], c["status"]) for c in checks]
    report = build_report(checks)
    assert report["score"] == 100 and report["risk"] == "low"
    assert supplier_message(load_demo("clean"), checks) == ""


def test_mistakes_demo_flags_expected_problems():
    checks = by_id(run_all_checks(load_demo("mistakes"), TODAY))
    assert checks["buyer_gstin"]["status"] == "fail"
    assert checks["invoice_number"]["status"] == "fail"
    assert checks["hsn"]["status"] == "warn"
    assert checks["tax_type"]["status"] == "fail"
    assert checks["total"]["status"] == "fail"
    assert checks["seller_gstin"]["status"] == "pass"
    report = build_report(list(checks.values()))
    assert report["risk"] == "high" and report["score"] < 70


def test_old_rate_after_gst2_is_warned():
    checks = by_id(run_all_checks(load_demo("old_rate"), TODAY))
    assert checks["rate"]["status"] == "warn"
    assert "12%" in checks["rate"]["message"]


def test_old_rate_before_gst2_is_fine():
    data = load_demo("old_rate")
    data["invoice_date"] = "2025-06-10"
    assert by_id(run_all_checks(data, TODAY))["rate"]["status"] == "pass"


def test_new_rates_after_gst2():
    data = load_demo("clean")
    data.update(cgst=1250.0, sgst=1250.0, total_amount=52500.0)  # 5%
    assert by_id(run_all_checks(data, TODAY))["rate"]["status"] == "pass"
    data.update(cgst=10000.0, sgst=10000.0, total_amount=70000.0)  # 40%
    assert by_id(run_all_checks(data, TODAY))["rate"]["status"] == "pass"


def test_igst_on_same_state_sale_fails():
    data = load_demo("clean")
    data.update(cgst=0.0, sgst=0.0, igst=9000.0)
    assert by_id(run_all_checks(data, TODAY))["tax_type"]["status"] == "fail"


def test_interstate_with_igst_passes():
    data = load_demo("mistakes")
    data.update(cgst=0.0, sgst=0.0, igst=3600.0, total_amount=23600.0)
    checks = by_id(run_all_checks(data, TODAY))
    assert checks["tax_type"]["status"] == "pass"
    assert checks["total"]["status"] == "pass"


def test_unequal_cgst_sgst_fails():
    data = load_demo("clean")
    data.update(cgst=5000.0, sgst=4000.0)
    assert by_id(run_all_checks(data, TODAY))["cgst_sgst"]["status"] == "fail"


def test_estimate_is_not_a_tax_invoice():
    data = load_demo("clean")
    data["document_type"] = "estimate"
    assert by_id(run_all_checks(data, TODAY))["doc_type"]["status"] == "fail"


def test_bill_of_supply_with_tax_fails():
    data = load_demo("clean")
    data["document_type"] = "bill_of_supply"
    assert by_id(run_all_checks(data, TODAY))["doc_type"]["status"] == "fail"


def test_missing_fields_and_future_date():
    data = normalize_invoice_data({"invoice_number": "A1", "invoice_date": "2030-01-01", "total_amount": 100})
    checks = by_id(run_all_checks(data, TODAY))
    assert checks["mandatory"]["status"] == "fail"
    assert checks["invoice_date"]["status"] == "warn"


def test_normalisation_of_messy_ai_output():
    data = normalize_invoice_data({
        "seller_gstin": " 27aakps 4821m1zc ", "invoice_date": "14/08/2026",
        "taxable_value": "₹ 50,000.00", "cgst": "4,500", "sgst": None, "hsn_sac_codes": "7308, 7308.10",
        "document_type": "TAX INVOICE",
    })
    assert data["seller_gstin"] == "27AAKPS4821M1ZC"
    assert data["invoice_date"] == "2026-08-14"
    assert data["taxable_value"] == 50000.0 and data["cgst"] == 4500.0 and data["sgst"] is None
    assert data["hsn_sac_codes"] == ["7308", "730810"]
    assert data["document_type"] == "tax_invoice"


def test_usd_estimate_from_real_upload():
    """The Greenfield Landscape estimate: USD, tax printed only as 7%."""
    data = normalize_invoice_data({
        "seller_name": "Greenfield Landscape", "buyer_name": "Carissa Benson", "invoice_number": "01234",
        "invoice_date": "2025-10-01", "document_type": "Estimate Invoice", "currency": "USD",
        "taxable_value": 350, "total_amount": 374.5,
    })
    checks = by_id(run_all_checks(data, TODAY))
    assert checks["doc_type"]["status"] == "fail"
    assert checks["currency"]["status"] == "fail"
    assert "total" not in checks and "rate" not in checks   # GST amount checks skipped
    assert "an estimate" in checks["doc_type"]["message"]


def test_tax_percentage_only_is_a_warning_not_a_false_failure():
    data = load_demo("clean")
    data.update(cgst=None, sgst=None, igst=None, total_amount=59000.0)
    checks = by_id(run_all_checks(data, TODAY))
    assert checks["total"]["status"] == "warn"
    assert checks["rate"]["status"] == "warn"


def test_exports_work():
    data = load_demo("mistakes")
    checks = run_all_checks(data, TODAY)
    report = build_report(checks)
    assert '"itc_risk": "high"' in to_json(data, checks, report)
    assert b"Seller GSTIN" in to_csv(data, checks, report)
    assert "Nagpur Fasteners" in supplier_message(data, checks) or "Hello" in supplier_message(data, checks)


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
        except AssertionError as error:
            failed += 1
            print(f"FAIL  {name}  {error}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
