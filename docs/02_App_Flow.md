# 02 – App Flow

## 1. User Journey (High Level)

```
┌──────────┐    ┌───────────┐    ┌────────────┐    ┌────────────┐    ┌──────────┐
│  Upload  │ -> │  Extract  │ -> │   Check    │ -> │  Results   │ -> │ Download │
│ PDF/Image│    │ (Gemini)  │    │ (Python)   │    │ Table+Flags│    │ JSON/CSV │
└──────────┘    └───────────┘    └────────────┘    └────────────┘    └──────────┘
```

## 2. Step-by-Step

### Step 1 – Landing / Upload
- User sees title, one-line description, and a file uploader.
- Accepted: `pdf`, `png`, `jpg`, `jpeg`. Max ~5 MB.
- After upload: image preview (or file name + size for PDF).
- "Analyze Invoice" button becomes active.

### Step 2 – Extraction (AI)
- User clicks **Analyze Invoice**.
- App shows a spinner: "Reading your invoice…".
- File bytes + a strict prompt are sent to Gemini.
- Gemini returns **JSON only** (see schema below).
- App parses JSON. If parsing fails → show friendly error + retry option.

### Step 3 – Compliance Checks (Python, no AI)
- Extracted JSON goes to `validators.py`.
- Each check returns: `{name, status, message, fix}` where status ∈ `pass | warn | fail`.

### Step 4 – Results Display
1. **Summary banner:** e.g., "3 passed · 2 warnings · 1 failed" (overall colour = worst status).
2. **Extracted data table:** field | value (missing shown as "—").
3. **Checks list:** 🟢 / 🟡 / 🔴 icon + message.
4. **"Fix these things":** only warn/fail items, each with a plain-language suggestion.

### Step 5 – Download
- **Download JSON** – extracted data + check results.
- **Download CSV** – extracted fields as one row.
- "Check another invoice" – clears state.

## 3. Screen Layout (Single Page)

```
┌────────────────────────────────────────────────┐
│  🧾 MSME Invoice Compliance Helper              │
│  Upload an invoice. Get a GST compliance report.│
├────────────────────────────────────────────────┤
│  [ Upload area: drag & drop PDF / image ]       │
│  [ Preview ]                                    │
│  [ Analyze Invoice ]                            │
├────────────────────────────────────────────────┤
│  (after analysis)                               │
│  Summary banner                                 │
│  ┌──────────────┬─────────────────────────┐    │
│  │ Extracted    │ Compliance checks        │    │
│  │ data table   │ 🟢 🟡 🔴 list            │    │
│  └──────────────┴─────────────────────────┘    │
│  Fix these things (list)                        │
│  [ Download JSON ] [ Download CSV ]             │
├────────────────────────────────────────────────┤
│  Disclaimer + GitHub link                       │
└────────────────────────────────────────────────┘
```

## 4. Data Flow

```
uploaded_file (bytes, mime_type)
      │
      ▼
extractor.extract_invoice_data(bytes, mime)   ──► Gemini API
      │
      ▼
invoice_data : dict   (schema below)
      │
      ▼
validators.run_all_checks(invoice_data)
      │
      ▼
checks : list[dict]
      │
      ▼
app.py renders table + flags + fixes + download buttons
```

## 5. Extraction JSON Schema

```json
{
  "seller_gstin": "27ABCDE1234F1Z5",
  "buyer_gstin": "27PQRSX5678L1Z2",
  "invoice_number": "INV-001",
  "invoice_date": "2026-09-01",
  "hsn_sac_codes": ["8471"],
  "taxable_value": 10000.00,
  "cgst": 900.00,
  "sgst": 900.00,
  "igst": 0.00,
  "total_amount": 11800.00,
  "place_of_supply": "Maharashtra"
}
```

Rules for the prompt:
- Return **only** JSON, no markdown or explanation.
- Use `null` for fields not found (never guess).
- Numbers as plain numbers (no ₹ or commas).
- Dates in `YYYY-MM-DD`.

## 6. Check Result Schema

```json
{
  "name": "Tax type logic",
  "status": "fail",
  "message": "Seller is in Maharashtra (27) but Place of Supply is Karnataka. IGST expected, found CGST+SGST.",
  "fix": "Replace CGST and SGST with IGST on this invoice."
}
```

## 7. Error & Edge States

| Situation | App behaviour |
|-----------|---------------|
| No file uploaded | Analyze button disabled |
| File too large / wrong type | Error message, no API call |
| Missing API key | Clear error: "GEMINI_API_KEY not configured" |
| Gemini API error / rate limit | "AI service busy, try again in a minute" |
| Gemini returns invalid JSON | Retry once, then show error |
| Most fields = null (not an invoice / unreadable) | Warning: "Couldn't read this as an invoice. Try a clearer image." |
| Invoice has no buyer GSTIN | Yellow flag (B2C possible), not red |

## 8. Session State (Streamlit)

| Key | Purpose |
|-----|---------|
| `invoice_data` | Extracted dict (persists across reruns) |
| `checks` | List of check results |
| `file_name` | To detect when user uploads a different file |

Streamlit reruns the whole script on every interaction, so results are stored in `st.session_state` to avoid calling Gemini again when the user clicks a download button.
