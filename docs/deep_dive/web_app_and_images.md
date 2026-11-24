# Web app pages, dashboard, and keeping equations, tables and diagrams

## 1. The web app

Start: `streamlit run app/streamlit_app.py` (Streamlit 1.36 or newer, because the pages use `st.navigation`).

| Page | File | Purpose |
|---|---|---|
| Home | `app/views/home.py` | What the tool does, three steps, what is kept, supported files, buttons into the app |
| Convert | `app/views/convert.py` | Upload, options, results, downloads (.md, .zip with images) |
| Dashboard | `app/views/dashboard.py` | History of every conversion: date, type, size, processing time, charts, CSV export |
| Guide | `app/views/guide.py` | Options, formats, limits, fixes |

Shared pieces: `app/ui.py` (CSS, top bar, preview renderer, size and time formatting), `.streamlit/config.toml` (warm light theme, minimal toolbar).
Look: a top navigation bar instead of a sidebar (the sidebar is hidden by CSS and `st.page_link` builds the bar), body text at Streamlit's default 16 px, modest headings, and a palette of five colours:

| Colour | Hex | Use |
|---|---|---|
| Concrete | `#525871` | headings, primary buttons, charts |
| Warm Steel | `#857C91` | dashed borders, small labels |
| Rosewood | `#CD9FA0` | active page, chips, chart accent |
| Peaches & Cream | `#F2C1A3` | step numbers, gradients |
| Dawn | `#F8CCAA` | hero background |

Body text uses a darker shade of Concrete (`#3E4358`) for contrast. All values are CSS variables at the top of `CSS` in `app/ui.py` and in `.streamlit/config.toml`.

The Streamlit pages were checked here only with a stand-in for Streamlit (every page script runs to the end with real data). They were not rendered in a browser; the first
real run may need small visual tweaks.

## 2. Dashboard and history

Every conversion made through the Convert page is stored by `src/history.py` in a SQLite file:

| Setting | Value |
|---|---|
| Location | `~/.ai_document_analyst/history.db` (falls back to the system temp folder when the home folder is read-only) |
| Override | environment variable `HISTORY_DB=/path/to/file.db` |
| Stored | time, file name and format, document type, size, pages, words, estimated tokens, tables, figures, equations, notes count, processing seconds, success or error text |
| Never stored | the document text or the Markdown |

"Time spent" is the **processing time** of the conversion (the work done by the tool). Time spent reading or editing is not measured.
Delete the file, or use *Clear history* on the dashboard, to reset it.

## 3. What happens to tables, equations and diagrams

| Content | Word (.docx) | PDF | PowerPoint |
|---|---|---|---|
| Table | Markdown table | Markdown table when ruling lines or aligned rules exist; otherwise plain text. A ruled drawing that is not recognised as a table is saved as a figure | Markdown table |
| Equation | **LaTeX text**: `$\frac{a}{b}$` inline, `$$...$$` display | **Image** of the equation (display equations), alt text holds the extracted symbols | not applicable |
| Diagram, chart, picture | Image file for PNG, JPEG, GIF; EMF/WMF reported as not saved | **Image** crop of the region (raster images and clusters of vector drawing objects) | Image file for PNG, JPEG, GIF |

All images are written to an `assets/` folder and linked from the Markdown as `![alt](../assets/name.png)`. The alt text carries the words found inside the figure, so a text-only chat still receives them.
Names start with the document name (`report_p3_fig1.png`, `report_p4_eq2.png`, `deck_s2_img1.png`), so several documents can share one folder.

Switches: web page checkbox *Keep figures, diagrams and equations as images* (on by default); command line `--images`; API form field `images=true`. Off means the earlier behaviour (pictures omitted and counted).

### How the PDF detection works

`src/convert/pdf_special.py`

1. **Figures.** Raster images of at least 40 by 30 points, plus clusters of at least 6 vector objects (lines, curves, rectangles) that are not inside a table. Objects within 12 points of each other form one cluster.
   Short labels next to the drawing (axis titles, tick labels) are included; captions starting with "Figure" or "Table" stay as text.
   A region holding more than 60 words is treated as a background, not a figure, and stays text.
2. **Equations.** Each text row is split into segments where the gap between words is large. A segment is a display equation when at least a quarter of its characters are in a maths font (Computer Modern math, MathTime, STIX, Cambria Math...),
   or it has two or more maths symbols (∑ ∫ ≤ ≥ Greek letters...), and it contains no running prose (fewer than 4 words of 4 or more letters). Neighbouring short segments (numerator, denominator, limits, the equation number) are added to the box.
3. The box is cropped from the rendered page at 170 dpi, scaled to at most 1600 pixels wide, and saved as PNG. At most 80 images are saved per document; further ones are counted in the notes.

Tested on a PDF produced by LaTeX (`pdflatex`) with `E = mc^2`, a sum-fraction-integral inequality and a matplotlib chart, and on generated PDFs in the unit tests.

### Known limits of this feature

- Inline formulas inside a sentence stay as text, so subscripts and special symbols there may be flattened.
- An equation of PDF is an **image**; it is not converted to LaTeX. Converting it needs a maths OCR model, which is outside the free, light scope of the project.
- Equations typed in Word as plain text with symbols are ordinary text; only Office Math objects become LaTeX.
- Detection is heuristic. A formula-like row in prose-free text, or a decorative drawing, can be saved as an image that is not needed; the notes and the *Images* tab show what was saved.
- Text boxes, headers, footers and footnotes of Word files are still not included.
- Images are separate files: a chat that accepts only text receives the alt text and the LaTeX, not the picture.

## 4. API and command line

```bash
python -m src.cli paper.pdf --images -o out/          # out/paper.md and out/assets/*.png
curl -F file=@paper.pdf -F images=true -o paper.zip http://localhost:8000/convert/download
```

`/convert` and `/analyze` return `stats.figures`, `stats.formulas` and `stats.asset_files` (the names); the files themselves come from `/convert/download` as a `.zip`.
