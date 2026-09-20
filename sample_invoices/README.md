# Sample invoices (dummy data)

Upload these to try InvoiceKavach. All names, GSTINs and amounts are fictional.

| File | What it shows | Expected result |
|---|---|---|
| `sample_1_clean.png` / `.pdf` | Correct same-state invoice, 18% GST | 100/100, Low risk |
| `sample_2_wrong_tax_and_gstin.png` | Inter-state sale with CGST+SGST, bad buyer GSTIN, wrong total, long invoice number, 2-digit HSN | 59/100, High risk |
| `sample_3_old_12pct_rate.png` | 12% GST charged after the 22 Sep 2025 rate change | 96/100, Medium risk |
