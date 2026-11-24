"""Guide: options, formats, limits and fixes."""
import streamlit as st

import ui

ui.page_title("Guide", "Options, what each format produces, limits, and common fixes.")

tab_opts, tab_formats, tab_limits, tab_fix = st.tabs(["Options", "Formats", "Limits", "Fixes"])

with tab_opts:
    st.markdown("""
| Option | What it does | When to use |
|---|---|---|
| Read text inside pictures | Runs OCR on pictures in PowerPoint, Word and PDF files; the text appears as quoted lines under the picture | Slide decks where slides are screenshots |
| Keep figures, diagrams and equations as images | Saves each as a PNG linked from the Markdown; the words inside become alt text | Documents with charts, diagrams or formulas |
| Compact mode | Removes table padding, comments and empty values | Pasting into a chat where every token counts |
| Split into parts | Cuts the result into parts of about N tokens, before headings | Document longer than the chat limit |
| Keep JSON exact | Same JSON without whitespace instead of readable tables | JSON that a program will read again |
| Mark page breaks | Adds a comment before each PDF page | Finding which page a passage came from |
| Keep repeated headers and footers | Stops the removal of lines repeated on every page | A header that carries real information |
| Force OCR | Reads PDF pages as pictures | Garbled text layer |
| OCR language | `auto` (default) reads English and, when installed, Bengali; or codes such as `eng+ben` | Non-English documents |
""")

with tab_formats:
    st.markdown("""
| Input | Result |
|---|---|
| PDF | Headings, paragraphs, lists, tables, two-column order; repeated headers removed; scans via OCR; figures and display equations as images |
| Word (.docx) | Headings, lists, tables, links, bold and italic; **equations as LaTeX**; pictures as images |
| Excel | One section per visible sheet, tables per block of rows |
| PowerPoint | One section per slide, tables, charts as tables, notes, pictures as images |
| Images | Text read with OCR, with confidence |
| JSON, YAML, TOML, XML, CSV | Tables for lists of similar records, `key: value` lines otherwise |
| HTML, notebooks, code | Main content, cells and outputs, fenced code |
""")
    st.caption("Google Docs, Sheets and Slides shortcut files: download from Google as .docx, .xlsx, .pptx or .pdf.")

with tab_limits:
    st.markdown("""
- PDF equations and diagrams are **pictures** plus their extracted text; they cannot be rebuilt as LaTeX.
- A table in a PDF without ruling lines may come out as plain text.
- Charts inside Word files saved as EMF/WMF cannot be shown and are reported in the notes.
- Handwriting and photographs are not read.
- OCR can misread names, numbers and small print.
- Token numbers are estimates.
- The app has no login: it is meant for this computer or a trusted network.
""")

with tab_fix:
    st.markdown("""
| Symptom | Fix |
|---|---|
| `tesseract is not installed` | `sudo apt install tesseract-ocr` |
| OCR language error | `sudo apt install tesseract-ocr-<code>`, then use the code in Advanced |
| Garbled characters such as `(cid:12)` | Turn on **Force OCR** |
| Columns interleaved | Try **Force OCR**; report the file as a corner case |
| Old .doc or .xls fails | `sudo apt install libreoffice-writer libreoffice-calc libreoffice-impress` |
| File too large | Raise `MAX_UPLOAD_MB` or split the file |
""")
