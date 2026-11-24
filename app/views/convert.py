"""Convert: upload, options, results and downloads."""
import os
import time

import streamlit as st

import ui
from src import history, service, precheck
from src.convert import ACCEPTED

ui.page_title("Convert", "Add files, pick options, download clean Markdown.")
health = service.health()


def log_ok(result, size):
    try:
        history.record_success(result, size)
    except Exception:          # the history must never block a conversion
        pass


def log_error(name, message, size, seconds):
    try:
        history.record_error(name, message, size, seconds)
    except Exception:
        pass


# ------------------------------------------------------------------ 1. files
with st.container(border=True):
    st.subheader("1 · Files")
    uploads = st.file_uploader("Drag files here or browse", accept_multiple_files=True,
                               type=[e.lstrip(".") for e in ACCEPTED], label_visibility="collapsed")
    st.caption(f"Up to {health['max_upload_mb']} MB per file.")

# ------------------------------------------------------------------ 2. options
with st.container(border=True):
    st.subheader("2 · Options")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Output**")
        keep_images = st.checkbox("Keep figures, diagrams and equations as images", value=True,
                                  help="Saved as PNG files linked from the Markdown, with their text as alt text. "
                                       "Word equations also appear as LaTeX text.")
        pic_ocr = st.checkbox("Read text inside pictures (slides saved as images)", value=True,
                              help="Runs OCR on pictures in PowerPoint, Word and PDF files. Useful when slides are screenshots. Text appears as quoted lines under the picture. Slower for large decks.")
        include_summary = st.checkbox("Put the summary at the top of the .md file", value=False)
        page_markers = st.checkbox("Mark page breaks in PDFs", value=False)
    with c2:
        st.markdown("**Save tokens**")
        compact = st.checkbox("Compact mode", value=True,
                              help="Tighter tables, no comments or empty values. Text and numbers are unchanged.")
        max_tokens = st.number_input("Split into parts of about N tokens (0 = one file)", min_value=0,
                                     max_value=200000, value=0, step=1000)
        exact_json = st.checkbox("Keep JSON exact (minified)", value=False)
    with st.expander("Advanced"):
        a1, a2 = st.columns(2)
        keep_headers = a1.checkbox("Keep repeated headers and footers (PDF)", value=False)
        force_ocr = a1.checkbox("Force OCR for PDFs", value=False, help="For PDFs whose text layer is garbled.")
        ocr_lang = a2.text_input("OCR language", value=os.getenv("OCR_LANG", "auto"),
                                 help="auto reads English, and Bengali too when its language pack is installed. Or type codes such as eng, ben, eng+ben.")
        use_llm = a2.checkbox("Use an AI model for the summary", value=False, disabled=not health["llm_configured"])
        if not health["llm_configured"]:
            a2.caption("No AI model configured; the free built-in summary is used.")

bad: set[str] = set()
for up in uploads or []:
    issue = precheck.check_upload(up.name, up.size, health["max_upload_mb"], health["accepted_types"], pic_ocr)
    if issue and issue[0] == "error":
        bad.add(up.file_id if hasattr(up, "file_id") else up.name)
        st.error(issue[1])
    elif issue:
        st.warning(issue[1])
good = [u for u in (uploads or []) if (u.file_id if hasattr(u, "file_id") else u.name) not in bad]
if not uploads:
    st.info("Add one or more files above to begin. The result appears below, with a download button for each file.")
run = st.button(f"Convert {len(good)} file(s)" if good else "Convert", type="primary", disabled=not good,
                use_container_width=True)

# ------------------------------------------------------------------ run
if run and good:
    results, errors = [], []
    bar = st.progress(0.0, text="Starting")
    t_all = time.perf_counter()
    for i, up in enumerate(good):
        bar.progress(i / len(good), text=f"Converting {up.name} ({i + 1} of {len(good)})")
        data = up.getvalue()
        t0 = time.perf_counter()
        spin = (f"Reading {up.name}. Pictures and scans are read with OCR, which can take a while."
                if pic_ocr else f"Reading {up.name}")
        try:
            with st.spinner(spin):
                r = service.process(data, up.name, page_markers=page_markers, strip_repeated=not keep_headers,
                                    force_ocr=force_ocr, use_llm=True if use_llm else False, compact=compact,
                                    json_mode="minified" if exact_json else "readable",
                                    ocr_lang=ocr_lang.strip() or None, max_tokens=int(max_tokens) or None,
                                    assets=keep_images, ocr_pictures=pic_ocr)
            results.append(r)
            log_ok(r, len(data))
        except service.ServiceError as e:
            errors.append((up.name, e.message, precheck.advice(e.status, e.message)))
            log_error(up.name, e.message, len(data), time.perf_counter() - t0)
        except Exception as e:                    # anything unexpected must not stop the other files
            msg = f"unexpected problem: {type(e).__name__}: {e}"
            errors.append((up.name, msg, precheck.advice(500, msg)))
            log_error(up.name, msg, len(data), time.perf_counter() - t0)
    bar.empty()
    st.session_state["results"], st.session_state["errors"] = results, errors
    st.session_state["include_summary"] = include_summary
    st.session_state["ran"] = (len(results), len(errors), time.perf_counter() - t_all)

# ------------------------------------------------------------------ results
ran = st.session_state.get("ran")
if ran and ran[0]:
    st.success(f"Converted {ran[0]} file(s) in {ui.human_time(ran[2])}." + (f" {ran[1]} failed (below)." if ran[1] else ""))
for name, msg, tip in st.session_state.get("errors", []):
    st.error(f"**{name}**: {msg}\n\n{tip}")

results = st.session_state.get("results", [])
inc = st.session_state.get("include_summary", False)
if results:
    st.subheader("Results")
    if len(results) > 1:
        st.download_button("⬇️ Download everything (.zip)", service.zip_results(results, inc),
                           file_name="markdown_files.zip", mime="application/zip")

for idx, r in enumerate(results):
    an, s = r["analysis"], r["stats"]
    assets = r.get("_assets") or {}
    with st.container(border=True):
        st.markdown(f"### {r['filename']}")
        st.markdown(f"**{an['one_line']}**" + (f" · *{an['title']}*" if an["title"] else ""))
        m = st.columns(5)
        m[0].metric("Words", f"{s['words']:,}")
        delta = None
        if s.get("source_tokens"):
            delta = f"{(s['estimated_tokens'] - s['source_tokens']) / s['source_tokens']:+.0%} vs raw file"
        m[1].metric("≈ Tokens", f"{s['estimated_tokens']:,}", delta=delta, delta_color="inverse",
                    help="Estimate: about 4 characters per token for English. Real counts differ by AI tool.")
        m[2].metric("Tables", s["tables"])
        m[3].metric("Figures · Equations", f"{s.get('figures', 0)} · {s.get('formulas', 0)}")
        m[4].metric("OCR confidence" if s.get("ocr_confidence") is not None else "Time",
                    f"{s['ocr_confidence']:.0f}%" if s.get("ocr_confidence") is not None
                    else ui.human_time(r.get("elapsed") or s["seconds"]))
        if s.get("image_tokens_est"):
            st.caption(f"Sending the image itself would cost roughly {s['image_tokens_est']:,} tokens "
                       "(width × height / 750). The text is only a good substitute when the picture is mostly text.")

        st.markdown("**Summary**")
        st.write(an["summary"])
        for p in an.get("key_points") or []:
            st.write(f"- {p}")
        st.caption(f"Method: {an['method']} · type confidence: {an['confidence']}"
                   + (f" · cues: {', '.join(an['cues'])}" if an["cues"] else ""))
        if r["warnings"]:
            with st.expander(f"Notes ({len(r['warnings'])})"):
                for w in r["warnings"]:
                    st.markdown(f"- {w}")

        files = service.output_files(r, inc)
        md = "\n\n".join(text for _, text in files)
        key = f"{idx}_{r['filename']}_{s['size_bytes']}"
        d1, d2, _ = st.columns([1, 1.4, 2])
        if len(files) == 1:
            d1.download_button("⬇️ Download .md", md, file_name=files[0][0], mime="text/markdown",
                               key=f"dl_{key}", type="primary", use_container_width=True)
            if assets:
                d2.download_button("⬇️ .md + images (.zip)", service.zip_results([r], inc),
                                   file_name=files[0][0].rsplit(".", 1)[0] + ".zip", mime="application/zip",
                                   key=f"dli_{key}", use_container_width=True)
        else:
            st.info(f"Split into {len(files)} parts of about {r['max_tokens']:,} tokens each.")
            d1.download_button(f"⬇️ {len(files)} parts (.zip)", service.zip_results([r], inc),
                               file_name=files[0][0].rsplit("_part", 1)[0] + "_parts.zip", mime="application/zip",
                               key=f"dlz_{key}", type="primary", use_container_width=True)
        tabs = st.tabs(["Preview", "Markdown", "Outline"] + (["Images"] if assets else []))
        with tabs[0]:
            has_pic_text = bool(assets) and "\n> " in md
            show_orig = (st.toggle("Show original pictures beside the text", key=f"orig_{key}",
                                   help="Off: only the text read from pictures. On: each original next to its text.")
                         if has_pic_text else False)
            ui.render_markdown(md, assets, show_original=show_orig)
            if len(md) > 200_000:
                st.caption("The preview shows the first 200,000 characters; the download holds everything.")
        with tabs[1]:
            st.code(md[:200_000], language="markdown")
        with tabs[2]:
            st.code("\n".join(an["outline"]) or "(no headings found)", language=None)
        if assets:
            with tabs[3]:
                cols = st.columns(3)
                for n, (name, blob) in enumerate(sorted(assets.items())):
                    cols[n % 3].image(blob, caption=name)
