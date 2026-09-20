# 03 – Implementation Plan (Hour-by-Hour)

> **Status update:** Hours 0-5 (full MVP + differentiators) are now implemented in code:
> `app.py`, `extractor.py`, `schema.py`, `validators.py`, `report.py`, `demo_data.py`, `ui.py`, `tests/`.
> Remaining for you: run locally with your Gemini key, test with real invoices (Hour 4-6), deploy (Hour 5-6), README polish, demo video.

**Total budget:** ~9–10 hours, solo, AI-assisted coding.
**Rule:** The MVP (upload → extract → check → results → download) must work by **end of Hour 5**. Everything after that is deploy, polish and documentation. If any hour overruns, cut from "Nice-to-have", never from "Must-have".

---

## Project Structure

```
msme-invoice-helper/
├── app.py              # Streamlit screens
├── extractor.py        # Gemini call + fallback + errors
├── schema.py           # Fields + data cleaning
├── validators.py       # GST rule engine
├── report.py           # Score, risk, supplier message, exports
├── demo_data.py        # 3 dummy sample invoices
├── ui.py               # CSS + HTML components
├── requirements.txt
├── README.md
├── .gitignore
├── .streamlit/
│   ├── config.toml            # Theme
│   └── secrets.toml.example   # Template only
├── tests/test_validators.py
├── sample_invoices/
└── docs/
```

---

## Hour 0 – 1: Setup & Skeleton ✅ (starter code provided)

**Goal:** App runs locally with upload + preview.

- [ ] Create GitHub repo (public), clone locally
- [ ] Python 3.10+ virtual env: `python -m venv venv` and activate
- [ ] `pip install -r requirements.txt`
- [ ] Get Gemini API key from https://aistudio.google.com/app/apikey
- [ ] Copy `.streamlit/secrets.toml.example` → `.streamlit/secrets.toml`, paste key
- [ ] `streamlit run app.py` → verify upload and preview work
- [ ] First commit and push

**Done when:** You can upload a file and see the preview.

---

## Hour 1 – 2: Gemini Extraction

**Goal:** Upload an invoice → get structured JSON.

- [ ] Create `extractor.py` with `extract_invoice_data(file_bytes, mime_type) -> dict`
- [ ] Write the extraction prompt (JSON only, `null` for missing, numbers as numbers, date as YYYY-MM-DD)
- [ ] Use Gemini's JSON response mode if available (`response_mime_type="application/json"`)
- [ ] Handle: missing key, API error, invalid JSON (retry once)
- [ ] Test with 2–3 real/sample invoices; print raw JSON in the app for now
- [ ] Commit: "Add Gemini extraction"

**Done when:** A clear invoice gives correct JSON for most fields.

**AI prompt to use with your coding assistant:**
> "Write `extractor.py` using the `google-genai` Python SDK. Function `extract_invoice_data(file_bytes, mime_type)` sends the file to a Gemini Flash model with a prompt asking for this exact JSON schema: [paste schema from 02_App_Flow.md]. Return a Python dict. Handle errors and invalid JSON. Read API key from `st.secrets['GEMINI_API_KEY']`. Add comments explaining each step."

---

## Hour 2 – 3: Validators (Pure Python)

**Goal:** All compliance checks working and unit-testable without AI.

- [ ] Create `validators.py` with `run_all_checks(data) -> list[dict]`
- [ ] Implement checks in this order (easiest first):
  1. Mandatory fields
  2. GSTIN regex + state code
  3. HSN/SAC format
  4. Total = taxable + taxes (₹1 tolerance)
  5. Intra vs inter-state logic (seller GSTIN state code vs place of supply → state code map)
  6. CGST == SGST
  7. Date sanity
- [ ] Add a `STATE_CODES` dict (01–38) mapping code → state name
- [ ] Test with hand-written dicts (one perfect, one with all errors)
- [ ] Commit: "Add compliance validators"

**Done when:** A dict with planted errors returns the expected red/yellow flags.

**Tip:** Ask your AI assistant to also generate 5–6 small `assert` tests, and run them. This is the best way to *understand* the logic.

---

## Hour 3 – 4: Results UI

**Goal:** Wire everything together in `app.py`.

- [ ] "Analyze Invoice" button → extractor → validators → store in `st.session_state`
- [ ] Summary banner (count of pass / warn / fail)
- [ ] Extracted data table (`st.dataframe` or `st.table`)
- [ ] Checks list with 🟢 🟡 🔴 icons
- [ ] "Fix these things" section (only warn/fail)
- [ ] Spinner + friendly error messages
- [ ] Commit: "Wire results UI"

**Done when:** End-to-end flow works on one invoice.

---

## Hour 4 – 5: Download + MVP Complete 🎯

**Goal:** Feature-complete MVP.

- [ ] `st.download_button` for JSON (data + checks) and CSV (data row)
- [ ] "Check another invoice" reset
- [ ] Test with 3+ invoices (clean, photo at angle, one with wrong tax)
- [ ] Fix the worst bugs only
- [ ] Commit: "MVP complete"

**✅ CHECKPOINT:** If MVP isn't working by now, drop all nice-to-haves and focus on stability.

---

## Hour 5 – 6: Deploy

**Goal:** Live URL.

- [ ] `requirements.txt` correct and pinned loosely (e.g., `streamlit>=1.35`)
- [ ] Confirm `.streamlit/secrets.toml` is in `.gitignore` and NOT on GitHub
- [ ] Push to GitHub
- [ ] https://share.streamlit.io → New app → select repo → `app.py`
- [ ] Add `GEMINI_API_KEY` under Advanced settings → Secrets
- [ ] Test the live URL from your phone / another browser
- [ ] Commit: "Deployed"

**Done when:** Someone else can open the URL and analyze an invoice.

---

## Hour 6 – 7: Testing & Sample Data

- [ ] Put 3–4 invoices in `sample_invoices/` (use **fake/dummy** data only, no real GSTINs of real businesses)
  - `good_invoice.pdf`
  - `wrong_tax_type.pdf`
  - `missing_fields.jpg`
  - `blurry_photo.jpg`
- [ ] Run each through the live app, note results
- [ ] Fix any extraction prompt problems
- [ ] (Nice-to-have) Add "Try a sample invoice" button

---

## Hour 7 – 8: README & Docs

README sections:
1. Title + one-line pitch + live demo link + screenshot/GIF
2. Problem
3. Solution
4. How it works (short flow diagram from 02_App_Flow.md)
5. Features
6. Tech stack
7. Run locally (5 commands)
8. Compliance checks implemented (table)
9. **Limitations** (be honest: no GSTIN checksum, no portal verification, AI can misread, not tax advice)
10. Future scope (GSTR-1 export, GSTIN live verification, batch upload, e-invoice IRN check)

---

## Hour 8 – 9: Polish + Demo Prep

- [ ] Clean UI (title, icons, footer disclaimer, sidebar "How it works")
- [ ] Code cleanup: remove dead code, add docstrings/comments
- [ ] Record a 1–2 minute demo video (backup in case of API rate limit)
- [ ] Prepare 2-minute pitch: Problem → Demo → How it works → Limitations → Future

---

## Hour 9 – 10: Buffer & Submission

- [ ] Final test of live URL
- [ ] Verify GitHub repo is public and has no secrets (`git log -p | grep -i "AIza"` should return nothing)
- [ ] Submit on the hackathon platform (repo link + live URL + video)
- [ ] Rest 😄

---

## "Can I explain this?" Checklist (for judges' questions)

- [ ] Why Streamlit? (single language, fast, free hosting)
- [ ] Why AI only for extraction, not validation? (deterministic, explainable, no hallucinated compliance advice)
- [ ] How does GSTIN validation work? (regex + state code)
- [ ] How do you decide CGST/SGST vs IGST? (seller state vs place of supply)
- [ ] What happens if AI extracts wrong? (shown to user; limitation noted; editable fields as future scope)
- [ ] Where is the API key stored? (Streamlit secrets, never in repo)
- [ ] What would you build next?

---

## If You Fall Behind – Cut List (in this order)

1. Sample-invoice button
2. Compliance score
3. Editable fields
4. CSV download (keep JSON only)
5. HSN/SAC format check (keep presence check)

**Never cut:** upload, extraction, GSTIN check, tax-type check, total check, live URL, README.
