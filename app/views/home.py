"""Home: landing page with features, how it works, a short manual and the way into the app."""
import streamlit as st

import landing
import ui
from src.convert import SUPPORTED

st.markdown(landing.LANDING_CSS, unsafe_allow_html=True)
st.markdown(landing.hero(), unsafe_allow_html=True)
st.markdown(landing.about(), unsafe_allow_html=True)
st.markdown(landing.features(), unsafe_allow_html=True)
st.markdown(landing.steps(), unsafe_allow_html=True)
st.markdown(landing.numbers(), unsafe_allow_html=True)

# ------------------------------------------------------------------ manual
st.markdown('<div class="sec"><div class="kicker">Manual</div><h2>Using the app</h2></div>',
            unsafe_allow_html=True)
t1, t2, t3, t4 = st.tabs(["Get started", "Read the result", "Use in AI chats", "Common questions"])
with t1:
    st.markdown("""
1. Open **Convert** from the top bar.
2. Drag files into the box, or choose **Browse files**. Several files can be converted at once.
3. Check the options. The defaults suit most documents: images kept, compact mode on, no splitting.
4. Press **Convert**. Each file gets its own card.
5. Press **Download .md**, or **.md + images (.zip)** when figures or equations were saved.
""")
    st.caption("Files up to 50 MB are accepted by default. Google Docs, Sheets and Slides shortcut files cannot "
               "be read; download them from Google as .docx, .xlsx, .pptx or .pdf first.")
with t2:
    st.markdown("""
- **Type and summary** describe the file. *Low* confidence means few clues were found; the Markdown is still valid.
- **Notes** list everything that did not convert faithfully: omitted pictures, removed headers, formulas without stored results, low OCR confidence.
- **Tokens** are an estimate (about 4 characters each for English). The AI tool in use may count differently.
- **OCR confidence** above 90% is usually reliable. Names, amounts and dates are worth checking against the original.
- **Preview** shows the rendered result, **Markdown** the raw text to copy, **Images** the saved figures.
""")
with t3:
    st.markdown("""
1. Convert the file with **compact mode** on.
2. For a long document, set a split size (3,000 to 8,000 tokens is common) and paste one part at a time.
3. Paste the Markdown instead of attaching the original file.
4. Attach an image file only when the picture itself matters. Its alt text and any LaTeX are already in the Markdown.
5. Keep the .md files: plain text is easy to search and version.
""")
with t4:
    with st.expander("Is anything uploaded?"):
        st.write("No. Conversion runs on the computer hosting this page. Only the optional AI summary can contact a "
                 "model, and only when one is configured.")
    with st.expander("Why is a PDF equation an image?"):
        st.write("A PDF stores where symbols are drawn, not the formula. The tool saves the region as a picture and "
                 "keeps the symbols as text. Word files store real equations, so those become LaTeX.")
    with st.expander("A table came out as plain text."):
        st.write("Tables in PDFs need ruling lines or aligned rules to be detected. Without them the rows stay as text.")
    with st.expander("Where is the history stored?"):
        st.write("In a small file in the home folder (`~/.ai_document_analyst/history.db`). The Dashboard can clear it.")
    st.caption("More in the Guide: options, formats, limits and fixes.")

# ------------------------------------------------------------------ formats and footer
st.markdown(landing.end_cta(), unsafe_allow_html=True)
st.markdown('<div class="sec"><div class="kicker">Supported files</div></div>', unsafe_allow_html=True)
SHOWN = ["pdf", "docx", "xlsx", "pptx", "csv", "png", "jpg", "webp", "tiff", "json", "yaml", "xml", "html",
         "ipynb", "md", "txt", "py", "doc", "xls", "ppt", "odt", "rtf"]          # the most common of all supported types
ui.chips([e for e in SHOWN if "." + e in SUPPORTED] + [f"+ {len(SUPPORTED) - len(SHOWN)} more (code, config, old Office)"])
st.markdown('<div class="anchor" id="technical"></div><div class="sec"><div class="kicker">Technical information</div>'
            '<h2>Methods, measurements and limits</h2></div>', unsafe_allow_html=True)
st.caption("For readers who want to know how the results are produced. Not needed to use the app.")
with st.expander("Methodology"):
    st.markdown("""
- **PDF:** words and their positions are read, then rows, headings (by font size), columns, tables and repeated page headers are rebuilt from the geometry. Pages with almost no text are read with OCR.
- **Images and pictures:** the picture is flattened, rotated upright, enlarged if small and read with Tesseract in several modes; lines, bullets and nesting are rebuilt from word positions.
- **Word / PowerPoint / Excel:** read from the file structure. Word equations are translated to LaTeX.
- **Data files:** lists of similar records become one table; other structures become `key: value` lines.
- **Summary and type:** weighted keyword cues choose the type; the summary only selects sentences that already exist.
""")
with st.expander("Data and preprocessing"):
    st.markdown("""
No model is trained, so there is no training data. Evaluation uses small **generated** sample files shipped with the project
(`data/samples/`). Preprocessing for OCR: transparency flattened to white, dark backgrounds inverted, contrast stretched, small images enlarged.
""")
with st.expander("Evaluation results"):
    st.markdown("""
| Measure | This tool | Comparison tool |
|---|---|---|
| Reading order, 3 sample PDFs | 100% | 52% to 93% |
| Headings recovered, 3 sample PDFs | 22 of 22 | 0 of 22 |
| Scanned page, word recall | 99.1% | no OCR |
| 40-record JSON, estimated tokens | 2,600 indented · 1,416 minified · 716 readable + compact | n/a |

Samples are small and generated, and the rules were tuned on them; real documents will score lower. Savings against a
chatbot's own file reader were not measured. Details: the Testing and Evaluation document in `docs/`.
""")
with st.expander("Known limitations"):
    st.markdown("""
- PDF equations are saved as images with their text, not converted to LaTeX. Word equations are converted.
- Tables without ruling lines in PDFs may come out as plain text.
- OCR can misread names, numbers and small print. Charts and photos are not described.
- Word headers, footers, footnotes and text boxes are not included (a note says so).
- Token counts are estimates. There is no login: do not expose the app publicly as it is.
""")

import os
from src.project_status import repo_status
repo = os.getenv("GITHUB_REPO", "").strip()
gh = f"https://github.com/{repo}" if repo and "<" not in repo and repo.count("/") == 1 else ""
_ps = repo_status() if repo else {"label": "", "detail": ""}
st.markdown('<div class="foot"><b>Document Analyst</b> · open source (MIT) · runs locally · token numbers are estimates<br>'
            + ("" if not gh else f'<a class="navlink" target="_blank" href="{gh}">GitHub repository</a> ')
            + ('<a class="navlink" target="_blank" href="' + (gh + "/tree/main/docs" if gh else "#") + '">Documentation</a> ' if gh else
               'Documentation: the <code>docs/</code> folder of the project · set <code>GITHUB_REPO</code> to show repository links')
            + (f'<br>Project activity: {_ps["label"].replace("Open source · ", "")} ({_ps["detail"]})' if repo and _ps["label"] else '')
            + '</div>', unsafe_allow_html=True)
