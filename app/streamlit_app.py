"""Streamlit UI.   streamlit run app/streamlit_app.py

Upload one or more documents -> see what each is and a short summary -> download clean Markdown.
Pasting the .md into a chatbot instead of the original file keeps the text and structure and
drops the file overhead, which usually means far fewer tokens.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

from src import service  # noqa: E402
from src.convert import ACCEPTED, SUPPORTED  # noqa: E402

st.set_page_config(page_title="Document → Markdown", page_icon="📄", layout="wide")
st.title("📄 Document → Markdown")
st.caption("Upload a PDF, Word, Excel, PowerPoint, image, JSON, HTML, CSV... Get the text as a clean, compact "
           ".md file plus a short summary, then paste it into any AI chat instead of the original file.")

health = service.health()
with st.sidebar:
    st.header("Options")
    include_summary = st.checkbox("Put the summary at the top of the .md file", value=False,
                                  help="Off = the .md contains only the document's own content.")
    page_markers = st.checkbox("Mark page breaks in PDFs", value=False)
    keep_headers = st.checkbox("Keep repeated headers/footers (PDF)", value=False)
    force_ocr = st.checkbox("Force OCR for PDFs", value=False, help="Use for PDFs whose text layer is garbled.")
    st.subheader("Save tokens")
    compact = st.checkbox("Compact mode", value=True,
                          help="Tighter tables, no comments or empty values in JSON/YAML/XML. Text and numbers are unchanged.")
    max_tokens = st.number_input("Split into parts of about N tokens (0 = one file)", min_value=0, max_value=200000,
                                 value=0, step=1000, help="Useful when a chat window or free tier has a size limit.")
    exact_json = st.checkbox("Keep JSON exact (minified)", value=False,
                             help="Off = readable tables and key: value lines (fewest tokens). On = the same JSON, only without whitespace.")
    ocr_lang = st.text_input("OCR language", value=os.getenv("OCR_LANG", "eng"),
                             help="For images and scanned PDFs. Examples: eng, ben, eng+ben. Needs the matching tesseract language pack.")
    st.subheader("Summary")
    use_llm = st.checkbox("Use an AI model for the summary", value=False, disabled=not health["llm_configured"],
                          help="Needs LLM_MODEL (free local Ollama) or a key. Otherwise the free built-in summary is used.")
    if not health["llm_configured"]:
        st.caption("No AI model configured: summaries are produced by a free built-in method. See docs/07_free_setup.md.")
    st.divider()
    st.caption("Supported: " + ", ".join(SUPPORTED) + ". Google files: download as .xlsx/.docx/.pptx/.csv first.")
    st.caption("Everything runs on the computer that hosts this page. Text leaves it only if the AI summary is "
               "pointed at a hosted provider.")

uploads = st.file_uploader("Drop files here", accept_multiple_files=True,
                           type=[e.lstrip(".") for e in ACCEPTED])

if uploads and st.button("Convert", type="primary"):
    results, errors = [], []
    bar = st.progress(0.0)
    for i, up in enumerate(uploads):
        try:
            results.append(service.process(up.getvalue(), up.name, page_markers=page_markers,
                                           strip_repeated=not keep_headers, force_ocr=force_ocr,
                                           use_llm=True if use_llm else False, compact=compact,
                                           json_mode="minified" if exact_json else "readable",
                                           ocr_lang=ocr_lang.strip() or None, max_tokens=int(max_tokens) or None))
        except service.ServiceError as e:
            errors.append((up.name, e.message))
        bar.progress((i + 1) / len(uploads))
    st.session_state["results"], st.session_state["errors"] = results, errors

for name, msg in st.session_state.get("errors", []):
    st.error(f"**{name}**: {msg}")

results = st.session_state.get("results", [])
if len(results) > 1:
    st.download_button("⬇️ Download all as .zip", service.zip_results(results, include_summary),
                       file_name="markdown_files.zip", mime="application/zip")

for r in results:
    an, s = r["analysis"], r["stats"]
    with st.expander(f"{r['filename']}  —  {an['doc_type']}", expanded=len(results) == 1):
        st.markdown(f"**{an['one_line']}**" + (f"  \nTitle: *{an['title']}*" if an["title"] else ""))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Words", f"{s['words']:,}")
        delta = None
        if s.get("source_tokens"):
            delta = f"{(s['estimated_tokens'] - s['source_tokens']) / s['source_tokens']:+.0%} vs the raw file"
        c2.metric("≈ Tokens", f"{s['estimated_tokens']:,}", delta=delta, delta_color="inverse",
                  help="Estimate: about 4 characters per token for English, more tokens per character for other "
                       "scripts. Real counts differ by AI tool. The comparison is only shown for text-based files "
                       "(JSON, HTML, CSV...), where the raw file is what would otherwise be pasted.")
        c3.metric("Tables", s["tables"])
        c4.metric("OCR confidence" if s.get("ocr_confidence") is not None else "Time",
                  f"{s['ocr_confidence']:.0f}%" if s.get("ocr_confidence") is not None else f"{s['seconds']:.2f}s")
        if s.get("image_tokens_est"):
            st.caption(f"Sending the image itself would cost roughly {s['image_tokens_est']:,} tokens "
                       "(width x height / 750, a published rule of thumb for Claude; other tools differ). "
                       "The text above is only useful if the picture is mostly text.")

        st.subheader("Summary")
        st.write(an["summary"])
        for p in an.get("key_points") or []:
            st.write(f"- {p}")
        st.caption(f"Summary method: {an['method']} · type confidence: {an['confidence']}"
                   + (f" · cues: {', '.join(an['cues'])}" if an["cues"] else ""))
        for w in r["warnings"]:
            st.warning(w)

        files = service.output_files(r, include_summary)
        md = "\n\n".join(text for _, text in files)
        if len(files) == 1:
            st.download_button("⬇️ Download .md", md, file_name=files[0][0], mime="text/markdown",
                               key=f"dl_{r['filename']}_{s['size_bytes']}", type="primary")
        else:
            st.info(f"Split into {len(files)} parts of about {r['max_tokens']:,} tokens each.")
            st.download_button(f"⬇️ Download {len(files)} parts (.zip)", service.zip_results([r], include_summary),
                               file_name=files[0][0].rsplit("_part", 1)[0] + "_parts.zip", mime="application/zip",
                               key=f"dlz_{r['filename']}_{s['size_bytes']}", type="primary")
        # Streamlit does not allow an expander inside an expander, so the outline is a tab.
        tab_raw, tab_view, tab_outline = st.tabs(["Markdown (raw)", "Preview", "Outline"])
        with tab_raw:
            st.code(md[:200_000], language="markdown")
        with tab_view:
            st.markdown(md[:200_000])
        with tab_outline:
            st.code("\n".join(an["outline"]) or "(no headings found)", language=None)
        if len(md) > 200_000:
            st.caption("Preview shows the first 200,000 characters; the download contains everything.")
