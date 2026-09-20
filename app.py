"""
InvoiceKavach - MSME Invoice Compliance Helper
==============================================
Streamlit entry point. Run with:  streamlit run app.py

How the pieces fit together
    app.py         (this file)  screens and buttons
    extractor.py   sends the invoice to Gemini, gets JSON back
    schema.py      cleans that JSON into a predictable dict
    validators.py  the GST rule engine (plain Python, no AI)
    report.py      score, ITC risk, supplier message, JSON/CSV export
    demo_data.py   three sample invoices (work without an API key)
    ui.py          CSS + HTML snippets for the visual design

Screen flow
    Upload -> Analyze -> Report   (or: pick a sample -> Report)
"""

import os
from urllib.parse import quote

import streamlit as st

import ui
from demo_data import DEMOS, load_demo
import extractor
from extractor import DEFAULT_MODELS, ExtractionError, extract_invoice_data
from report import build_report, export_filename, issues_of, supplier_message, to_csv, to_json
from schema import DOC_TYPE_LABELS, FIELD_LABELS, NUMBER_FIELDS, TEXT_FIELDS, looks_empty, normalize_invoice_data
from validators import run_all_checks

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ALLOWED_TYPES = ["pdf", "png", "jpg", "jpeg", "webp"]
MAX_FILE_SIZE_MB = 5
MIME_TYPES = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}

st.set_page_config(page_title="InvoiceKavach - GST invoice checker", page_icon="🛡️", layout="wide")


# ---------------------------------------------------------------------------
# Session state
#   Streamlit re-runs this whole script on every click. Anything we want to
#   remember between clicks (results, the uploaded file) lives in st.session_state.
# ---------------------------------------------------------------------------
RESULT_KEYS = ["data", "checks", "report", "source", "file_bytes", "file_name", "mime", "model_used"]


def init_state():
    for key in RESULT_KEYS:
        st.session_state.setdefault(key, None)
    st.session_state.setdefault("uploader_key", 0)   # changing this key empties the uploader
    st.session_state.setdefault("analysis_id", 0)    # changes on each new analysis (resets edit form)
    st.session_state.setdefault("view", "input")     # which screen: "input" or "report"


def reset_everything():
    for key in RESULT_KEYS:
        st.session_state[key] = None
    st.session_state.uploader_key += 1
    st.session_state.view = "input"


def store_results(data, source, file_info=None):
    """Run the rule engine on `data` and remember everything for the report screen."""
    checks = run_all_checks(data)
    st.session_state.data = data
    st.session_state.checks = checks
    st.session_state.report = build_report(checks)
    st.session_state.analysis_id += 1
    st.session_state.view = "report"
    if source is not None:
        st.session_state.source = source
    if file_info is not None:
        st.session_state.file_bytes, st.session_state.file_name, st.session_state.mime = file_info


# ---------------------------------------------------------------------------
# Configuration helpers (API key, model)
# ---------------------------------------------------------------------------
def get_api_key(typed_key):
    """Order: key typed in the sidebar -> Streamlit secrets -> environment variable."""
    if typed_key and typed_key.strip():
        return typed_key.strip(), "the sidebar"
    try:
        secret = st.secrets["GEMINI_API_KEY"]
        if secret and "paste-your-key" not in secret:
            return secret, "secrets"
    except Exception:  # no secrets file, or key missing
        pass
    env_key = os.getenv("GEMINI_API_KEY")
    if env_key:
        return env_key, "the environment"
    return None, None


def get_models():
    """Optional GEMINI_MODEL override in secrets, otherwise the default fallback list."""
    try:
        override = st.secrets["GEMINI_MODEL"]  # one name, or several separated by commas
        names = [m.strip() for m in str(override).split(",") if m.strip()]
        if names:
            return names
    except Exception:
        pass
    return DEFAULT_MODELS


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def pdf_first_page_png(file_bytes):
    """Render page 1 of a PDF as PNG so we can preview it. Needs PyMuPDF; returns None if unavailable."""
    try:
        import fitz  # PyMuPDF

        document = fitz.open(stream=file_bytes, filetype="pdf")
        return document[0].get_pixmap(dpi=110).tobytes("png")
    except Exception:
        return None


@st.cache_data(show_spinner=False, ttl=6 * 3600, max_entries=100)
def cached_extract(file_bytes, mime_type, api_key, models):
    """Same invoice + same settings = no second AI call. Saves free-tier quota."""
    data = extract_invoice_data(file_bytes, mime_type, api_key, list(models))
    return data, extractor.LAST_MODEL_USED


def show_invoice_image(file_bytes, mime_type, caption):
    if mime_type == "application/pdf":
        png = pdf_first_page_png(file_bytes)
        if png:
            st.image(png, caption="Page 1 of the PDF")
        else:
            st.info("PDF received. A preview is not available here, but it can still be analyzed.")
    else:
        st.image(file_bytes, caption=caption)


def render_sidebar():
    with st.sidebar:
        st.markdown(ui.brand(), unsafe_allow_html=True)
        st.markdown("### AI engine")
        hosted_key, _ = get_api_key("")  # key from secrets / environment, if the app owner set one
        key_help = "Free key: aistudio.google.com/app/apikey. Used only for this session, never saved."
        if hosted_key:
            st.success("AI engine ready.")
            with st.expander("Use my own API key (optional)"):
                typed = st.text_input("Gemini API key", type="password", placeholder="Paste key", help=key_help)
        else:
            typed = st.text_input("Gemini API key", type="password", placeholder="Paste key", help=key_help)
        key, source = get_api_key(typed)
        if not key:
            st.warning("No API key yet. Uploads need one. The sample invoices work without it.")
        elif not hosted_key:
            st.success(f"API key loaded from {source}.")
        st.divider()
        st.markdown("### Privacy")
        st.markdown(
            ui.tiny(
                "This app does not save your invoice. To read it, the file is sent to Google's Gemini API. "
                "Avoid uploading sensitive real invoices while testing."
            ),
            unsafe_allow_html=True,
        )
        st.markdown("### Good to know")
        st.markdown(
            ui.tiny(
                "InvoiceKavach checks how an invoice is written. It does not check whether the supplier "
                "has filed returns or paid tax, and it is not legal or tax advice."
            ),
            unsafe_allow_html=True,
        )
        st.divider()
        if st.button("Start over", key="sb_reset"):
            reset_everything()
            st.rerun()
    return key


# ---------------------------------------------------------------------------
# Screen 1: upload / ready
# ---------------------------------------------------------------------------
def run_analysis(file_bytes, mime_type, file_name, api_key):
    """Extract -> check -> store. Shows progress; on success re-runs the app to show the report."""
    error_message = error_detail = None
    with st.status("Analyzing your invoice...", expanded=True) as status:
        try:
            st.write("Reading the invoice with Gemini...")
            data, model_used = cached_extract(file_bytes, mime_type, api_key, tuple(get_models()))
            if looks_empty(data):
                error_message = (
                    "We could not find invoice details in this file. "
                    "Try a sharper photo or the original PDF."
                )
            else:
                st.write("Running GST compliance checks...")
                store_results(data, "ai", (file_bytes, file_name, mime_type))
                st.session_state.model_used = model_used
        except ExtractionError as error:
            error_message = str(error)
            error_detail = error.detail

        if error_message:
            status.update(label="Analysis did not finish", state="error", expanded=True)
        else:
            status.update(label="Analysis complete", state="complete", expanded=False)

    if error_message:
        st.error(error_message)
        if error_detail:
            with st.expander("Technical details (send this if you need help)"):
                st.code(error_detail, language=None)
    else:
        st.rerun()


def render_input_view(api_key):
    state = st.session_state

    # Coming back from the report? Offer a way forward again.
    if state.report is not None:
        note_col, btn_col = st.columns([4, 1])
        with note_col:
            st.markdown(ui.note(f"You already have a report for {state.file_name or 'a sample invoice'}."), unsafe_allow_html=True)
        with btn_col:
            if st.button("View report →", key="to_report"):
                state.view = "report"
                st.rerun()

    st.markdown(ui.hero(), unsafe_allow_html=True)
    steps_slot = st.empty()  # filled in below, once we know if a file was uploaded

    left, right = st.columns([1.25, 1], gap="large")

    file_bytes = mime_type = file_name = None
    with left:
        uploaded = st.file_uploader(
            "Upload an invoice (PDF, PNG, JPG or WEBP, up to 5 MB)",
            type=ALLOWED_TYPES,
            key=f"uploader_{state.uploader_key}",
        )
        if uploaded is not None:
            candidate = uploaded.getvalue()
            extension = uploaded.name.rsplit(".", 1)[-1].lower()
            if len(candidate) > MAX_FILE_SIZE_MB * 1024 * 1024:
                st.error(f"This file is larger than {MAX_FILE_SIZE_MB} MB. Upload a smaller file or compress the image.")
            else:
                file_bytes, file_name = candidate, uploaded.name
                mime_type = MIME_TYPES.get(extension, "application/octet-stream")
                show_invoice_image(file_bytes, mime_type, file_name)

    with right:
        if file_bytes:
            st.markdown(ui.ready_card(file_name, len(file_bytes) / 1024, mime_type), unsafe_allow_html=True)
            if st.button("Analyze invoice", type="primary", key="analyze"):
                run_analysis(file_bytes, mime_type, file_name, api_key)
        else:
            st.markdown(ui.what_we_check_card(), unsafe_allow_html=True)

    steps_slot.markdown(ui.stepper("ready" if file_bytes else "upload"), unsafe_allow_html=True)

    # Samples: full-width row of cards, only while no file is chosen
    if not file_bytes:
        st.markdown(ui.section_heading("Or try a sample invoice", "Dummy data. No API key needed."), unsafe_allow_html=True)
        columns = st.columns(len(DEMOS))
        for column, (key, demo) in zip(columns, DEMOS.items()):
            with column:
                with st.container(border=True):
                    st.markdown(ui.sample_card(demo), unsafe_allow_html=True)
                    if st.button("Open sample →", key=f"demo_{key}"):
                        reset_everything()
                        store_results(load_demo(key), f"demo:{demo['title']}")
                        st.rerun()


# ---------------------------------------------------------------------------
# Screen 2: report
# ---------------------------------------------------------------------------
def render_edit_form(data):
    """Let the user correct anything the AI misread, then re-run the checks."""
    analysis_id = st.session_state.analysis_id
    with st.expander("Something look wrong? Edit the values and re-check"):
        st.caption("AI can misread blurry text. Fix a value here and run the checks again.")
        with st.form(f"edit_form_{analysis_id}"):
            values = {}
            columns = st.columns(3)
            index = 0
            for field in TEXT_FIELDS + NUMBER_FIELDS + ["hsn_sac_codes"]:
                if field == "document_type":
                    continue
                current = data.get(field)
                if field == "hsn_sac_codes":
                    current = ", ".join(current or [])
                elif current is None:
                    current = ""
                with columns[index % 3]:
                    values[field] = st.text_input(FIELD_LABELS[field], value=str(current), key=f"f_{analysis_id}_{field}")
                index += 1

            options = [None] + list(DOC_TYPE_LABELS.keys())
            current_type = data.get("document_type")
            doc_type = st.selectbox(
                FIELD_LABELS["document_type"],
                options,
                index=options.index(current_type) if current_type in options else 0,
                format_func=lambda v: "Not stated" if v is None else DOC_TYPE_LABELS[v],
                key=f"f_{analysis_id}_doc_type",
            )
            submitted = st.form_submit_button("Re-check with my edits", type="primary")

        if submitted:
            raw = dict(values)
            raw["document_type"] = doc_type
            raw["item_descriptions"] = data.get("item_descriptions") or []
            store_results(normalize_invoice_data(raw), None)
            st.rerun()


def render_report_view():
    state = st.session_state
    data, checks, report = state.data, state.checks, state.report

    back_col, new_col, note_col = st.columns([1.2, 1.5, 5])
    with back_col:
        if st.button("← Back", key="back"):
            state.view = "input"
            st.rerun()
    with new_col:
        if st.button("New invoice", key="restart"):
            reset_everything()
            st.rerun()
    with note_col:
        if state.source and state.source.startswith("demo:"):
            title = state.source.split(":", 1)[1]
            st.markdown(ui.note(f"Sample invoice: {title}. Dummy data, no AI used."), unsafe_allow_html=True)
        else:
            read_by = f" · read by {state.model_used}" if state.model_used else ""
            st.markdown(ui.note(f"Report for {state.file_name or 'your invoice'}{read_by}"), unsafe_allow_html=True)

    st.markdown(ui.stepper("report"), unsafe_allow_html=True)
    st.markdown(ui.verdict_panel(report), unsafe_allow_html=True)
    st.markdown(ui.snapshot(data), unsafe_allow_html=True)

    tab_report, tab_data, tab_message, tab_download = st.tabs(
        ["Report", "Extracted data", "Message to supplier", "Download"]
    )

    # ---- Report ---------------------------------------------------------
    with tab_report:
        issues = issues_of(checks)
        passed = [c for c in checks if c["status"] == "pass"]
        if issues:
            st.markdown(ui.section_title(f"Fix these things ({len(issues)})"), unsafe_allow_html=True)
            st.markdown("".join(ui.check_card(c) for c in issues), unsafe_allow_html=True)
        else:
            st.success("Nothing to fix. Every check passed.")
        if passed:
            with st.expander(f"Passed checks ({len(passed)})", expanded=not issues):
                st.markdown("".join(ui.check_card(c) for c in passed), unsafe_allow_html=True)

    # ---- Extracted data -------------------------------------------------
    with tab_data:
        table_col, image_col = st.columns([1.15, 1], gap="large")
        with table_col:
            st.markdown(ui.data_ledger(data), unsafe_allow_html=True)
        with image_col:
            if state.file_bytes:
                st.caption("Original invoice. Compare it with the values on the left.")
                show_invoice_image(state.file_bytes, state.mime, state.file_name)
            else:
                st.markdown(ui.tiny("Sample data has no original image."), unsafe_allow_html=True)
        render_edit_form(data)

    # ---- Message to supplier -------------------------------------------
    with tab_message:
        message = supplier_message(data, checks)
        if not message:
            st.success("All checks passed, so there is nothing to send to the supplier.")
        else:
            st.markdown(
                ui.tiny("Edit the message if you like, then copy it or send it on WhatsApp."),
                unsafe_allow_html=True,
            )
            text = st.text_area(
                "Message", value=message, height=340,
                key=f"msg_{state.analysis_id}", label_visibility="collapsed",
            )
            st.link_button("Open in WhatsApp", "https://wa.me/?text=" + quote(text))

    # ---- Download -------------------------------------------------------
    with tab_download:
        st.markdown(ui.tiny("Download the extracted data and the check results."), unsafe_allow_html=True)
        col_json, col_csv, col_html = st.columns(3)
        with col_json:
            st.download_button(
                "Download JSON", data=to_json(data, checks, report),
                file_name=export_filename(data, "json"), mime="application/json",
            )
        with col_csv:
            st.download_button(
                "Download CSV", data=to_csv(data, checks, report),
                file_name=export_filename(data, "csv"), mime="text/csv",
            )
        with col_html:
            st.download_button(
                "Download report (HTML)", data=ui.report_html(data, checks, report),
                file_name=export_filename(data, "html"), mime="text/html",
                help="Open it in a browser and use Print > Save as PDF.",
            )
        with st.expander("Preview JSON"):
            st.json({"extracted_data": data, "summary": {k: report[k] for k in ("score", "risk", "counts")}})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    init_state()
    st.markdown(ui.CSS, unsafe_allow_html=True)
    api_key = render_sidebar()
    st.markdown(ui.brand(), unsafe_allow_html=True)

    if st.session_state.view == "report" and st.session_state.report is not None:
        render_report_view()
    else:
        render_input_view(api_key)

    st.markdown(ui.footer(), unsafe_allow_html=True)


main()
