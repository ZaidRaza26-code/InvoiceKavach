"""
ui.py
-----
All the visual design lives here: one CSS block plus small functions that
return HTML strings. app.py just calls them with st.markdown(..., unsafe_allow_html=True).

Security note: anything that came from the invoice (names, numbers, messages)
is passed through html.escape() before it is placed in HTML.

Visual idea: an invoice checker should feel like an official desk that stamps
documents. So the verdict is a rubber stamp (the one memorable element),
everything else is quiet paper, ink-blue and ledger lines.
"""

from datetime import date
from html import escape

from schema import DOC_TYPE_LABELS, FIELD_LABELS, parse_date
from validators import STATE_CODES, resolve_state_code, state_code_of, format_inr

CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,800&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

:root{
  --ink:#132238; --ink2:#3B4A61; --muted:#6B7A90;
  --paper:#F3F5F9; --card:#FFFFFF; --line:#D8DFEA;
  --brand:#1D3E8F; --brand-soft:#E8EEFB;
  --pass:#167A4A; --pass-bg:#E5F4EC;
  --warn:#9A5B00; --warn-bg:#FCF0D9;
  --fail:#B3261E; --fail-bg:#FCE7E5;
  --display:'Bricolage Grotesque','IBM Plex Sans',system-ui,-apple-system,'Segoe UI',sans-serif;
  --body:'IBM Plex Sans',system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
}
.stApp{background:var(--paper);}
.stApp, .stMarkdown, .stMarkdown p, .stMarkdown li, label, input, textarea,
.stButton button, .stDownloadButton button, [data-baseweb="tab"]{font-family:var(--body);}
.block-container{padding-top:1.4rem;max-width:1180px;}
header[data-testid="stHeader"]{background:transparent;}
section[data-testid="stSidebar"]{background:#FFFFFF;border-right:1px solid var(--line);}

/* ---------- brand + hero ---------- */
.kv-brand{display:flex;align-items:center;gap:.7rem;margin-bottom:1.6rem;}
.kv-brand svg{flex:none;}
.kv-name{font-family:var(--display);font-weight:800;font-size:1.35rem;color:var(--ink);letter-spacing:-.01em;display:block;line-height:1.1;}
.kv-sub{font-size:.82rem;color:var(--muted);display:block;}
.kv-h1{font-family:var(--display);font-weight:800;font-size:clamp(1.8rem,3.6vw,2.6rem);line-height:1.08;
  letter-spacing:-.02em;color:var(--ink);margin:0 0 .7rem;max-width:18em;}
.kv-lead{font-size:1.05rem;line-height:1.55;color:var(--ink2);max-width:38em;margin:0 0 1.4rem;}

/* ---------- stepper ---------- */
.kv-steps{display:flex;gap:.5rem;align-items:center;margin:0 0 1.6rem;flex-wrap:wrap;}
.kv-step{display:flex;align-items:center;gap:.5rem;font-size:.9rem;color:var(--muted);font-weight:500;}
.kv-dot{width:1.7rem;height:1.7rem;border-radius:50%;border:1.5px solid var(--line);background:#fff;
  display:inline-flex;align-items:center;justify-content:center;font-size:.8rem;font-weight:600;color:var(--muted);}
.kv-step.done{color:var(--ink2);} .kv-step.done .kv-dot{background:var(--brand);border-color:var(--brand);color:#fff;}
.kv-step.now{color:var(--ink);font-weight:600;} .kv-step.now .kv-dot{border-color:var(--brand);color:var(--brand);box-shadow:0 0 0 4px var(--brand-soft);}
.kv-bar{width:2.2rem;height:2px;background:var(--line);border-radius:2px;}
.kv-bar.done{background:var(--brand);}

/* ---------- generic card ---------- */
.kv-card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:1.15rem 1.3rem;}
.kv-card h3{font-family:var(--display);font-size:1.1rem;font-weight:600;color:var(--ink);margin:0 0 .7rem;}
.kv-list{list-style:none;margin:0;padding:0;}
.kv-list li{display:flex;gap:.65rem;padding:.55rem 0;border-top:1px solid var(--line);font-size:.93rem;color:var(--ink2);line-height:1.4;}
.kv-list li:first-child{border-top:0;padding-top:0;}
.kv-list b{color:var(--ink);font-weight:600;}
.kv-tick{flex:none;width:1.15rem;height:1.15rem;border-radius:50%;background:var(--brand-soft);color:var(--brand);
  font-size:.7rem;display:inline-flex;align-items:center;justify-content:center;margin-top:.1rem;font-weight:700;}
.kv-filecard{display:flex;flex-direction:column;gap:.2rem;margin-bottom:1rem;}
.kv-filename{font-weight:600;color:var(--ink);word-break:break-all;}
.kv-filemeta{font-size:.85rem;color:var(--muted);}
.kv-note{background:var(--brand-soft);border:1px solid #C9D6F3;color:var(--ink2);border-radius:12px;padding:.7rem 1rem;font-size:.92rem;margin:0 0 1rem;}
.kv-samples-title{font-weight:600;color:var(--ink);margin:1.2rem 0 .1rem;}
.kv-samples-sub{font-size:.88rem;color:var(--muted);margin:0 0 .6rem;}
.kv-tiny{font-size:.8rem;color:var(--muted);line-height:1.45;}

/* ---------- verdict (the stamp) ---------- */
.kv-verdict{display:flex;gap:1.6rem;align-items:center;background:var(--card);border:1px solid var(--line);
  border-radius:16px;padding:1.3rem 1.6rem;margin:0 0 1.2rem;flex-wrap:wrap;}
.kv-verdict.low{--c:var(--pass);--bg:var(--pass-bg);}
.kv-verdict.medium{--c:var(--warn);--bg:var(--warn-bg);}
.kv-verdict.high{--c:var(--fail);--bg:var(--fail-bg);}
.kv-stamp{flex:none;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;
  min-width:9.5rem;padding:.75rem 1.1rem;border:3px solid var(--c);border-radius:12px;color:var(--c);background:var(--bg);
  box-shadow:inset 0 0 0 3px var(--bg), inset 0 0 0 5px var(--c);transform:rotate(-4deg);
  animation:kv-thud .45s cubic-bezier(.2,.9,.3,1.2) both;}
.kv-stamp-big{font-family:var(--display);font-weight:800;font-size:1.7rem;line-height:1;letter-spacing:-.01em;}
.kv-stamp-small{font-size:.78rem;font-weight:600;margin-top:.3rem;opacity:.9;}
@keyframes kv-thud{from{transform:rotate(-12deg) scale(1.5);opacity:0;}to{transform:rotate(-4deg) scale(1);opacity:1;}}
@media (prefers-reduced-motion:reduce){.kv-stamp{animation:none;}}
.kv-vtext{flex:1;min-width:14rem;}
.kv-vtext h2{font-family:var(--display);font-size:1.35rem;font-weight:600;color:var(--ink);margin:0 0 .3rem;}
.kv-vtext p{margin:0 0 .8rem;color:var(--ink2);font-size:.95rem;line-height:1.5;}
.kv-counts{display:flex;gap:.5rem;flex-wrap:wrap;}
.kv-count{font-size:.85rem;font-weight:600;border-radius:999px;padding:.25rem .7rem;}
.kv-count.fail{background:var(--fail-bg);color:var(--fail);}
.kv-count.warn{background:var(--warn-bg);color:var(--warn);}
.kv-count.pass{background:var(--pass-bg);color:var(--pass);}
.kv-scorebox{flex:none;text-align:right;}
.kv-score{font-family:var(--display);font-weight:800;font-size:3.4rem;line-height:1;color:var(--ink);font-variant-numeric:tabular-nums;}
.kv-score span{font-size:1.1rem;color:var(--muted);font-weight:600;margin-left:.15rem;}
.kv-scorelabel{font-size:.82rem;color:var(--muted);margin-top:.2rem;}
@media (max-width:720px){.kv-scorebox{text-align:left;}.kv-verdict{padding:1.1rem;}}

/* ---------- check cards ---------- */
.kv-sectiontitle{font-family:var(--display);font-weight:600;font-size:1.15rem;color:var(--ink);margin:1.2rem 0 .6rem;}
.kv-chk{background:var(--card);border:1px solid var(--line);border-left:5px solid var(--c);border-radius:12px;padding:.85rem 1.1rem;margin:0 0 .65rem;}
.kv-chk.fail{--c:var(--fail);} .kv-chk.warn{--c:var(--warn);} .kv-chk.pass{--c:var(--pass);}
.kv-chk-head{display:flex;align-items:center;gap:.6rem;flex-wrap:wrap;margin-bottom:.25rem;}
.kv-pill{font-size:.76rem;font-weight:600;border-radius:999px;padding:.12rem .6rem;color:var(--c);background:color-mix(in srgb,var(--c) 12%,white);}
.kv-chk-name{font-weight:600;color:var(--ink);}
.kv-chk-msg{margin:0;color:var(--ink2);font-size:.93rem;line-height:1.5;}
.kv-chk-fix{margin:.5rem 0 0;padding:.5rem .75rem;background:var(--paper);border-radius:8px;font-size:.9rem;color:var(--ink);line-height:1.5;}
.kv-chk-fix b{color:var(--c);}
.kv-chk.pass{padding:.6rem 1.1rem;}

/* ---------- data ledger ---------- */
.kv-ledger{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;}
.kv-ledger th{background:var(--brand-soft);color:var(--brand);text-align:left;font-family:var(--display);font-weight:600;font-size:.92rem;padding:.55rem 1rem;}
.kv-ledger td{padding:.5rem 1rem;border-top:1px solid var(--line);font-size:.93rem;color:var(--ink);vertical-align:top;}
.kv-ledger td.k{color:var(--muted);width:38%;}
.kv-ledger td.num{text-align:right;font-variant-numeric:tabular-nums;}
.kv-ledger td.miss{color:#98A4B6;}
.kv-ledger tr.total td{font-weight:700;background:#FAFBFD;}
.kv-hint{color:var(--muted);font-size:.85rem;}
.kv-wrap{overflow-x:auto;margin-bottom:1rem;}

/* ---------- Streamlit widgets ---------- */
[data-testid="stFileUploaderDropzone"]{border:1.5px dashed #9FB0D0;background:#fff;border-radius:14px;}
.stTabs [data-baseweb="tab-list"]{gap:.4rem;border-bottom:1px solid var(--line);}
.stTabs [data-baseweb="tab"]{font-weight:600;padding:.5rem .9rem;}
.stButton > button, .stDownloadButton > button, .stLinkButton > a{border-radius:10px;font-weight:600;}
/* ---------- hero panel ---------- */
.kv-hero{display:flex;gap:2rem;align-items:center;justify-content:space-between;
  background:linear-gradient(135deg,#0E2255 0%,#1D3E8F 62%,#2F5BC4 100%);border-radius:22px;
  padding:2.3rem 2.5rem;margin:0 0 1.5rem;overflow:hidden;box-shadow:0 10px 30px rgba(20,40,100,.18);}
.kv-hero h1{font-family:var(--display);font-weight:800;font-size:clamp(1.7rem,3vw,2.45rem);line-height:1.1;
  letter-spacing:-.02em;color:#fff !important;margin:0 0 .8rem;padding:0;max-width:16em;}
.kv-hero p{color:#D3DEF6;font-size:1.02rem;line-height:1.55;max-width:33em;margin:0 0 1.1rem;}
.kv-chips{display:flex;gap:.5rem;flex-wrap:wrap;}
.kv-chip{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.24);color:#fff;border-radius:999px;padding:.28rem .85rem;font-size:.82rem;font-weight:500;}
.kv-hero-art{flex:none;}
@media (max-width:860px){.kv-hero-art{display:none;}.kv-hero{padding:1.5rem;}}

/* ---------- sample cards ---------- */
.kv-h2{font-family:var(--display);font-weight:600;font-size:1.2rem;color:var(--ink);margin:1.6rem 0 .1rem;}
.kv-h2-sub{font-size:.9rem;color:var(--muted);margin:0 0 .8rem;}
.kv-mini{display:inline-block;font-size:.72rem;font-weight:600;border-radius:999px;padding:.12rem .6rem;}
.kv-mini.low{background:var(--pass-bg);color:var(--pass);}
.kv-mini.medium{background:var(--warn-bg);color:var(--warn);}
.kv-mini.high{background:var(--fail-bg);color:var(--fail);}
.kv-sample-t{font-family:var(--display);font-weight:600;font-size:1.05rem;color:var(--ink);margin:.5rem 0 .2rem;}
.kv-sample-d{font-size:.88rem;color:var(--ink2);line-height:1.45;margin:0 0 .5rem;min-height:2.6em;}
[data-testid="stVerticalBlockBorderWrapper"]{background:#fff;border-radius:14px;border-color:var(--line);}

/* ---------- verdict extras: ring + segments ---------- */
.kv-ring{flex:none;width:112px;height:112px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  background:conic-gradient(var(--c) calc(var(--p) * 1%), #E6EBF3 0);}
.kv-ring-in{width:86px;height:86px;border-radius:50%;background:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;}
.kv-ring-in b{font-family:var(--display);font-size:1.9rem;line-height:1;color:var(--ink);font-variant-numeric:tabular-nums;}
.kv-ring-in span{font-size:.72rem;color:var(--muted);margin-top:.15rem;}
.kv-seg{display:flex;gap:3px;height:10px;margin:.2rem 0 .6rem;max-width:26rem;}
.kv-seg i{flex:1;border-radius:4px;background:#E6EBF3;}
.kv-seg i.s-fail{background:var(--fail);} .kv-seg i.s-warn{background:#E8A020;} .kv-seg i.s-pass{background:var(--pass);}
.kv-legend{display:flex;gap:1rem;flex-wrap:wrap;font-size:.85rem;color:var(--ink2);}
.kv-legend b{color:var(--ink);}

/* ---------- invoice snapshot ---------- */
.kv-snap{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:1px;background:var(--line);
  border:1px solid var(--line);border-radius:14px;overflow:hidden;margin:0 0 1.3rem;}
.kv-snap > div{background:#fff;padding:.85rem 1.05rem;display:flex;flex-direction:column;gap:.15rem;}
.kv-snap-l{font-size:.75rem;color:var(--muted);font-weight:500;}
.kv-snap-v{font-weight:600;color:var(--ink);font-size:1rem;word-break:break-word;}
.kv-snap-sub{font-size:.8rem;color:var(--muted);word-break:break-all;}
.kv-footer{margin-top:2.2rem;padding-top:1rem;border-top:1px solid var(--line);font-size:.82rem;color:var(--muted);line-height:1.5;}

/* ---------- fixes to Streamlit defaults ---------- */
p.kv-tiny, .stMarkdown p.kv-tiny{font-size:.82rem !important;line-height:1.5;color:var(--muted);margin:0 0 .6rem;}
[data-testid="stSidebar"] h3{font-size:1.02rem;font-family:var(--display);margin:.6rem 0 .3rem;}
[data-testid="stFileUploaderDropzone"]{min-height:130px;padding:1.4rem;background:linear-gradient(180deg,#fff,#F6F8FD);border:2px dashed #9FB0D0;border-radius:16px;}
[data-testid="stFileUploaderDropzone"]:hover{border-color:var(--brand);background:#F1F5FF;}
.stButton > button{padding:.5rem 1.1rem;border-color:var(--line);}
.stTabs [data-baseweb="tab-highlight"]{background:var(--brand);height:3px;}
</style>"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _h(html_text):
    """Collapse a multi-line HTML string onto one line.
    (Markdown treats blank lines and 4-space indents as special, so we avoid both.)"""
    return " ".join(line.strip() for line in html_text.splitlines() if line.strip())


def _e(value):
    return escape(str(value))


def _date_text(value):
    parsed = parse_date(value)
    return parsed.strftime("%d %b %Y") if parsed else value


# ---------------------------------------------------------------------------
# Header, hero, stepper
# ---------------------------------------------------------------------------
_SHIELD = (
    '<svg width="38" height="42" viewBox="0 0 38 42" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
    '<path d="M19 2 34 8v12c0 10-6.5 17.5-15 20C10.5 37.5 4 30 4 20V8L19 2Z" fill="#1D3E8F"/>'
    '<path d="M12 20.5l5 5 9.5-10.5" stroke="#fff" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>'
    "</svg>"
)


def brand():
    return _h(
        f"""<div class="kv-brand">{_SHIELD}<div>
        <span class="kv-name">InvoiceKavach</span>
        <span class="kv-sub">MSME invoice compliance helper</span></div></div>"""
    )


_HERO_ART = (
    '<svg width="250" height="240" viewBox="0 0 250 240" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
    '<g transform="rotate(4 125 120)"><rect x="24" y="14" width="196" height="212" rx="14" fill="#fff"/>'
    '<rect x="42" y="34" width="70" height="10" rx="5" fill="#1D3E8F"/><rect x="42" y="54" width="110" height="6" rx="3" fill="#D8DFEA"/>'
    '<rect x="42" y="82" width="160" height="8" rx="4" fill="#E8EEFB"/><rect x="42" y="100" width="160" height="8" rx="4" fill="#E8EEFB"/>'
    '<rect x="38" y="118" width="168" height="22" rx="6" fill="#FCE7E5"/><rect x="46" y="126" width="94" height="7" rx="3.5" fill="#B3261E" opacity=".55"/>'
    '<rect x="42" y="154" width="160" height="8" rx="4" fill="#E8EEFB"/><rect x="122" y="186" width="80" height="14" rx="4" fill="#1D3E8F"/></g>'
    '<g transform="rotate(-10 190 56)"><rect x="140" y="30" width="98" height="40" rx="8" fill="#FCE7E5" stroke="#B3261E" stroke-width="3"/>'
    '<text x="189" y="56" text-anchor="middle" font-family="Arial,sans-serif" font-weight="800" font-size="15" fill="#B3261E">1 to fix</text></g></svg>'
)


def hero():
    return _h(
        f"""<div class="kv-hero"><div>
        <h1>Catch GST invoice mistakes before they cost you input tax credit.</h1>
        <p>Upload an invoice photo or PDF. AI reads it, GST rules check it, and you get a clear list of what to fix.</p>
        <div class="kv-chips"><span class="kv-chip">Free to use</span><span class="kv-chip">No login</span>
        <span class="kv-chip">Aware of the Sep 2025 GST rate change</span></div></div>
        <div class="kv-hero-art">{_HERO_ART}</div></div>"""
    )


def stepper(stage):
    """stage: 'upload' | 'ready' | 'report'"""
    labels = ["Upload invoice", "Analyze", "Read the report"]
    active = {"upload": 0, "ready": 1, "report": 2}[stage]
    parts = []
    for i, label in enumerate(labels):
        state = "done" if i < active else ("now" if i == active else "")
        mark = "✓" if state == "done" else str(i + 1)
        parts.append(f'<div class="kv-step {state}"><span class="kv-dot">{mark}</span>{label}</div>')
        if i < len(labels) - 1:
            parts.append(f'<div class="kv-bar {"done" if i < active else ""}"></div>')
    return _h(f'<div class="kv-steps">{"".join(parts)}</div>')


# ---------------------------------------------------------------------------
# Landing / ready cards
# ---------------------------------------------------------------------------
_WHAT_WE_CHECK = [
    ("Tax invoice or not", "Estimates, quotations and proforma invoices are flagged."),
    ("Mandatory fields", "Seller, invoice number, date, place of supply and amounts."),
    ("GSTIN validity", "Pattern, state code and the check digit, so typos are caught."),
    ("CGST + SGST or IGST", "Compared against the seller's state and the place of supply."),
    ("GST rate", "Matched to the slabs in force on the invoice date, including the 22 Sep 2025 change."),
    ("Totals and format", "Amounts add up. HSN/SAC and invoice number follow the rules."),
]


def what_we_check_card():
    items = "".join(
        f'<li><span class="kv-tick">✓</span><span><b>{_e(t)}</b><br>{_e(d)}</span></li>' for t, d in _WHAT_WE_CHECK
    )
    return _h(f'<div class="kv-card"><h3>What we check</h3><ul class="kv-list">{items}</ul></div>')


def ready_card(filename, size_kb, mime_type):
    kind = "PDF document" if mime_type == "application/pdf" else "Image"
    return _h(
        f"""<div class="kv-card"><div class="kv-filecard">
        <span class="kv-filename">{_e(filename)}</span>
        <span class="kv-filemeta">{_e(kind)} · {size_kb:.0f} KB</span></div>
        <p class="kv-tiny">Press Analyze to read the invoice and run all checks.
        Make sure the photo is sharp and the whole invoice is visible.</p></div>"""
    )


def section_heading(title, sub=""):
    sub_html = f'<p class="kv-h2-sub">{_e(sub)}</p>' if sub else ""
    return f'<div class="kv-h2">{_e(title)}</div>{sub_html}'


def sample_card(demo):
    label = {"low": "Low risk", "medium": "Medium risk", "high": "High risk"}[demo["risk"]]
    return _h(
        f"""<span class="kv-mini {demo['risk']}">{label}</span>
        <div class="kv-sample-t">{_e(demo['title'])}</div><p class="kv-sample-d">{_e(demo['blurb'])}</p>"""
    )


def note(text):
    return f'<div class="kv-note">{_e(text)}</div>'


def tiny(text):
    return f'<p class="kv-tiny">{_e(text)}</p>'


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def _plural(n, one, many):
    return f"{n} {one if n == 1 else many}"


def verdict_panel(report):
    c = report["counts"]
    if c["fail"] == 0 and c["warn"] == 0:
        headline = "Nothing to fix"
    else:
        headline = f"{_plural(c['fail'], 'thing', 'things')} to fix, {c['warn']} to review"
    segments = "".join(f'<i class="s-{k}"></i>' for k in ("fail", "warn", "pass") for _ in range(c[k]))
    return _h(
        f"""<div class="kv-verdict {report['risk']}">
        <div class="kv-stamp"><span class="kv-stamp-big">{_e(report['risk_title'])}</span>
        <span class="kv-stamp-small">for your ITC claim</span></div>
        <div class="kv-vtext"><h2>{_e(headline)}</h2><p>{_e(report['summary'])}</p>
        <div class="kv-seg">{segments}</div>
        <div class="kv-legend"><span><b>{c['fail']}</b> failed</span>
        <span><b>{c['warn']}</b> {'warning' if c['warn'] == 1 else 'warnings'}</span><span><b>{c['pass']}</b> passed</span></div></div>
        <div class="kv-scorebox"><div class="kv-ring" style="--p:{report['score']}"><div class="kv-ring-in">
        <b>{report['score']}</b><span>out of 100</span></div></div></div></div>"""
    )


def snapshot(data):
    def cell(label, main, sub=""):
        sub_html = f'<span class="kv-snap-sub">{_e(sub)}</span>' if sub else ""
        return f'<div><span class="kv-snap-l">{_e(label)}</span><span class="kv-snap-v">{_e(main)}</span>{sub_html}</div>'

    total = data.get("total_amount")
    taxable = data.get("taxable_value")
    sym = _sym(data)
    return _h(
        '<div class="kv-snap">'
        + cell("Seller", data.get("seller_name") or "Not found", data.get("seller_gstin") or "")
        + cell("Buyer", data.get("buyer_name") or "Not found", data.get("buyer_gstin") or "No GSTIN")
        + cell("Invoice", data.get("invoice_number") or "Not found", _date_text(data.get("invoice_date")) or "")
        + cell("Total", sym + format_inr(total) if total is not None else "Not found",
               "Taxable " + sym + format_inr(taxable) if taxable is not None else "")
        + "</div>"
    )


def footer():
    return _h(
        """<div class="kv-footer"><b>InvoiceKavach</b> · Built for Hack Devengers 2.0 ·
        Guidance only, not legal or tax advice. Verify important invoices with a qualified professional.</div>"""
    )


_STATUS_LABEL = {"pass": "Passed", "warn": "Needs a look", "fail": "Fix needed"}


def check_card(check):
    fix = ""
    if check["fix"] and check["status"] != "pass":
        fix = f'<p class="kv-chk-fix"><b>How to fix:</b> {_e(check["fix"])}</p>'
    return _h(
        f"""<div class="kv-chk {check['status']}">
        <div class="kv-chk-head"><span class="kv-pill">{_STATUS_LABEL[check['status']]}</span>
        <span class="kv-chk-name">{_e(check['name'])}</span></div>
        <p class="kv-chk-msg">{_e(check['message'])}</p>{fix}</div>"""
    )


def section_title(text):
    return f'<div class="kv-sectiontitle">{_e(text)}</div>'


# ---------------------------------------------------------------------------
# Extracted data ledger
# ---------------------------------------------------------------------------
def _row(label, value, num=False, total=False):
    missing = value in (None, "", [])
    shown = "Not found" if missing else str(value)
    cls = "miss" if missing else ("num" if num else "")
    row_cls = ' class="total"' if total else ""
    return f'<tr{row_cls}><td class="k">{_e(label)}</td><td class="{cls}">{_e(shown)}</td></tr>'


def _gstin_value(gstin):
    if not gstin:
        return None
    code = state_code_of(gstin)
    state = STATE_CODES.get(code)
    return f"{gstin}  ·  {state}" if state else gstin


def _sym(data):
    cur = data.get("currency")
    return "₹" if cur in (None, "", "INR") else f"{cur} "


def _money(value, sym="₹"):
    return None if value is None else sym + format_inr(value)


def data_ledger(data):
    def section(title, rows):
        return f'<tr><th colspan="2">{_e(title)}</th></tr>' + "".join(rows)

    pos = data.get("place_of_supply")
    pos_code = resolve_state_code(pos)
    pos_text = f"{pos}  ·  state code {pos_code}" if pos and pos_code else pos

    parties = section("Parties", [
        _row(FIELD_LABELS["seller_name"], data.get("seller_name")),
        _row(FIELD_LABELS["seller_gstin"], _gstin_value(data.get("seller_gstin"))),
        _row(FIELD_LABELS["buyer_name"], data.get("buyer_name")),
        _row(FIELD_LABELS["buyer_gstin"], _gstin_value(data.get("buyer_gstin"))),
    ])
    details = section("Invoice details", [
        _row(FIELD_LABELS["invoice_number"], data.get("invoice_number")),
        _row(FIELD_LABELS["invoice_date"], _date_text(data.get("invoice_date"))),
        _row(FIELD_LABELS["document_type"], DOC_TYPE_LABELS.get(data.get("document_type"))),
        _row(FIELD_LABELS["currency"], data.get("currency") or "INR (assumed)"),
        _row(FIELD_LABELS["place_of_supply"], pos_text),
        _row(FIELD_LABELS["hsn_sac_codes"], ", ".join(data.get("hsn_sac_codes") or [])),
        _row(FIELD_LABELS["item_descriptions"], "; ".join(data.get("item_descriptions") or [])),
    ])
    sym = _sym(data)
    amount_rows = [
        _row(FIELD_LABELS["taxable_value"], _money(data.get("taxable_value"), sym), num=True),
        _row(FIELD_LABELS["cgst"], _money(data.get("cgst"), sym), num=True),
        _row(FIELD_LABELS["sgst"], _money(data.get("sgst"), sym), num=True),
        _row(FIELD_LABELS["igst"], _money(data.get("igst"), sym), num=True),
    ]
    if data.get("cess") is not None:
        amount_rows.append(_row(FIELD_LABELS["cess"], _money(data.get("cess"), sym), num=True))
    if data.get("round_off") is not None:
        amount_rows.append(_row(FIELD_LABELS["round_off"], _money(data.get("round_off"), sym), num=True))
    amount_rows.append(_row(FIELD_LABELS["total_amount"], _money(data.get("total_amount"), sym), num=True, total=True))
    amounts = section("Amounts", amount_rows)

    return f'<div class="kv-wrap"><table class="kv-ledger">{parties}{details}{amounts}</table></div>'


def report_html(data, checks, report):
    """A standalone HTML report the user can save or print to PDF."""
    issues = sorted((c for c in checks if c["status"] != "pass"), key=lambda c: c["status"] != "fail")
    passed = [c for c in checks if c["status"] == "pass"]
    body = brand() + verdict_panel(report) + snapshot(data)
    if issues:
        body += section_title(f"Fix these things ({len(issues)})") + "".join(check_card(c) for c in issues)
    if passed:
        body += section_title(f"Passed checks ({len(passed)})") + "".join(check_card(c) for c in passed)
    body += section_title("Extracted data") + data_ledger(data)
    body += f'<p class="kv-tiny">Generated on {date.today():%d %b %Y} by InvoiceKavach. Guidance only, not legal or tax advice.</p>'
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'><title>InvoiceKavach report</title>"
        + CSS
        + "<style>body{margin:0;background:#F3F5F9;font-family:var(--body);}.wrap{max-width:900px;margin:0 auto;padding:28px 20px;}"
        "@media print{body{background:#fff;}}</style></head><body><div class='wrap'>" + body + "</div></body></html>"
    )
