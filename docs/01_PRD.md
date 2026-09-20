# 01 – Product Requirements Document (PRD)

**Project:** InvoiceKavach - MSME Invoice Compliance Helper (AI-powered)
**Event:** Hack Devengers 2.0 – Open Innovation (24-hour online hackathon)
**Team:** Solo participant
**Build budget:** ~9–10 hours

---

## 1. Problem

Micro and small businesses in India create GST invoices manually or with basic tools. Common mistakes:

- Missing mandatory fields (invoice number, date, place of supply, etc.)
- Invalid or mistyped GSTIN
- Wrong or missing HSN/SAC code
- Wrong tax split (CGST+SGST used for an inter-state sale, or IGST for intra-state)
- Arithmetic errors in taxable value / tax / total

**Impact:** The buyer's Input Tax Credit (ITC) gets blocked, payments get delayed, and GST notices follow. Small businesses rarely have an accountant to catch these before the invoice is sent.

## 2. Target Users

| User | Need |
|------|------|
| Micro/small business owner | Quickly check if an invoice is correct before sending |
| Small-shop accountant / bookkeeper | Verify invoices received from suppliers before claiming ITC |
| Freelancer / trader | Catch mistakes without GST expertise |

## 3. Solution

A simple web tool where the user uploads an invoice (PDF or photo/scan). The app:

1. Uses **Gemini Vision** to extract the key invoice fields.
2. Runs **rule-based compliance checks** in plain Python (deterministic, not AI).
3. Shows a clear report: extracted data, Green / Yellow / Red flags, and a "Fix these things" list.
4. Lets the user download the extracted data as JSON or CSV.

**Design principle:** AI is used only for *reading* the invoice. All *validation* is done with code, so results are predictable and explainable.

## 4. Features

### 4.1 Must-have (MVP)

| # | Feature | Details |
|---|---------|---------|
| F1 | File upload | PDF, PNG, JPG, JPEG; max ~5 MB |
| F2 | AI extraction | Seller GSTIN, Buyer GSTIN, Invoice No., Date, HSN/SAC, Taxable Value, CGST, SGST, IGST, Total, Place of Supply |
| F3 | Compliance checks | See 4.3 |
| F4 | Results display | Table of extracted fields, colour-coded flags, "Fix these things" list |
| F5 | Export | Download JSON and CSV |

### 4.1b Differentiators (added after review)

| # | Feature | Details |
|---|---------|---------|
| F6 | GSTIN check-digit | Real mod-36 checksum, not just a regex |
| F7 | Date-aware GST rate check | Valid slabs depend on invoice date (GST 2.0 from 22 Sep 2025) |
| F8 | Document type check | Flags estimates / quotations / proforma as not-a-tax-invoice |
| F9 | Score + ITC risk | 0-100 score and Low / Medium / High verdict |
| F10 | Supplier message | Copy-paste / WhatsApp message listing what to correct |
| F11 | Edit & re-check | User corrects AI misreads, checks re-run |
| F12 | Sample invoices | 3 dummy invoices, work without API key |

### 4.2 Nice-to-have (only if time remains)

- Editable extracted fields (user corrects AI mistakes, then re-runs checks)
- Sample-invoice button for one-click demo
- Overall compliance score (e.g., 80/100)
- GSTIN state-code to state-name display

### 4.3 Compliance Checks

| Check | Rule | Severity if failed |
|-------|------|--------------------|
| Mandatory fields | Seller GSTIN, invoice no., date, taxable value, total, place of supply present | Red |
| GSTIN format | 15 chars, regex: `^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$` | Red |
| GSTIN state code | First 2 digits between 01 and 38 (valid state/UT code) | Yellow |
| Buyer GSTIN | Missing is allowed for B2C; flag as info | Yellow |
| HSN/SAC present | Present and 4/6/8 digits (HSN) or 6 digits starting 99 (SAC) | Yellow |
| Tax type logic | Seller state == Place of Supply → CGST + SGST expected. Different → IGST expected | Red |
| CGST = SGST | For intra-state, CGST and SGST should be equal | Red |
| Total check | Taxable + CGST + SGST + IGST ≈ Total (tolerance ₹1) | Red |
| Date sanity | Valid date, not in the future | Yellow |

**Flag meaning**
- 🟢 Green – check passed
- 🟡 Yellow – warning / could not fully verify
- 🔴 Red – definite compliance problem

## 5. Out of Scope

- GSTR-1 / GSTR-3B generation
- GST portal / e-invoice / IRN integration
- Live GSTIN verification against the GST portal
- User login, database, history
- Inventory or accounting features
- Mobile app
- Multi-invoice batch processing

## 6. Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| UI + backend | Streamlit (Python) | Single file/language, fastest to build |
| AI | Google Gemini Flash (Google AI Studio free tier) | Vision + PDF support, free |
| Data handling | pandas | Table display + CSV export |
| Hosting | Streamlit Community Cloud | Free public URL |
| Code | GitHub (public) | Hackathon requirement |

## 7. Success Criteria

- [ ] Live URL works for someone else, without any setup
- [ ] Correctly extracts fields from at least 3 different sample invoices
- [ ] Catches at least 4 deliberately planted errors in a test invoice
- [ ] README explains problem, solution, how it works, limitations
- [ ] I can explain every file of the code if asked

## 8. Risks & Limitations

| Risk | Mitigation |
|------|------------|
| AI misreads blurry images or handwritten text | Show extracted values clearly so the user can spot errors; add editable fields if time permits |
| Gemini free-tier rate limits during demo | Keep a pre-recorded demo video + cached sample result as backup |
| Invoices with multiple line items / multiple HSN codes | MVP handles invoice-level totals; list first/all HSN codes found |
| GSTIN checksum not validated | Only format + state code are checked; state this in README |
| Not legal/tax advice | Add disclaimer in app footer and README |
| API key leak on public repo | Use `st.secrets` / environment variable, never commit the key |
