# Corner cases and troubleshooting

Part 1 lists awkward inputs and exactly what the tool does with each. All 49 are executed by one script, so the table cannot silently drift from the code:

```bash
python scripts/corner_cases.py            # prints a table; exit code 1 if any case deviates
python scripts/corner_cases.py --verbose
```

Last run (November 2026, Linux, Python 3.13, Tesseract and LibreOffice present): **49 passed, 0 failed, 0 skipped**. Cases that need Tesseract or LibreOffice are reported as
`SKIP` when those programs are missing; they are never counted as passes.

## 1. Corner cases and what happens

### Input handling

| Input | Behaviour | HTTP status (API) |
|---|---|---|
| Empty file | Error `empty file` | 400 |
| Extension not supported (`.exe`, or no extension) | Error `unsupported file type ...` followed by the list of supported types | 415 |
| Upper-case extension (`REPORT.PDF`) | Accepted: extensions are compared in lower case | 200 |
| PNG bytes saved as `fake.pdf` | `could not open PDF: ... Is this really a PDF?` (content is not sniffed; the extension decides the converter) | 422 |
| Corrupt PDF | Same `could not open PDF` message | 422 |
| Password-protected PDF | `this PDF is password-protected; remove the password and try again` | 422 |
| DOCX that is not a zip archive | `could not open DOCX: File is not a zip file` | 422 |
| File above the upload limit (default 50 MB, `MAX_UPLOAD_MB`) | `file larger than N MB` | 413 |
| `max_tokens` below 200 | `max_tokens must be at least 200` | 422 |

### Text and encodings

| Input | Behaviour |
|---|---|
| CSV in Windows-1252 (`René,Zürich`) | Decoded correctly (UTF-8 is tried first, then Windows-1252, then Latin-1) |
| UTF-16 CSV with a byte-order mark | Decoded correctly; UTF-16 is only trusted when the mark is present |
| Semicolon-separated CSV | Delimiter detected; columns split correctly |
| CSV with more than 5,000 rows | First 5,000 rows converted; warning `truncated to 5000 rows` |
| Ligatures (`ﬁ`), soft hyphens, non-breaking spaces | Replaced by plain characters (`final`) |
| `|` inside a table cell | Escaped as `\|` so the table stays intact |

### Office files

| Input | Behaviour |
|---|---|
| Excel formula without a stored result (workbook produced by a script, never opened in Excel) | The formula text is shown; warning with the count of such cells |
| Hidden Excel sheet | Skipped; warning names it |
| Empty Excel sheet | `*(empty sheet)*` under its heading |
| Word file with header, footer, footnotes, text boxes | Not included; warning says so (body text is converted) |
| PowerPoint slide with no title | `## Slide N` with the text boxes below |
| Old `.doc/.xls/.ppt/.odt/.ods/.odp/.rtf` | Converted with LibreOffice when installed (warning notes this); otherwise an error asks for a modern format |

### PDF

| Input | Behaviour |
|---|---|
| Scanned PDF (no text layer, fewer than 20 characters on a page) | Each such page is OCR'd; warning `OCR` with page count |
| Running header and page numbers on a 4-page PDF | Removed (8 lines in the test file); body text kept; count reported |
| Same file with `--keep-headers` | Nothing removed |
| Two-column article | Columns read left then right (needs at least 12 rows and a clear gutter) |
| Pictures and charts inside a PDF | Omitted; warning with the count |
| Vertical margin stamp (arXiv identifier) | Moved to the end of the page; warning |

### Data files

| Input | Behaviour |
|---|---|
| Invalid JSON | `this is not valid JSON (line 1): ...` with the parser's position |
| JSON Lines | One table |
| Records with different keys | Not forced into a table (key overlap under 0.5): rendered as lines |
| Records with more than 30 distinct keys | Rendered as lines instead of an unreadable wide table |
| JSON nested 20 levels deep | No crash; levels beyond 12 become compact inline JSON |
| `{}` | `(empty)` |
| Top-level scalar such as `42` | `42` |
| Non-English text in JSON | Kept unchanged; the token estimate uses 1.5 characters per token for non-ASCII text |
| XML containing `<!ENTITY ...>` | Refused (`XML with entity declarations is refused for safety`) |
| Invalid XML | `this is not valid XML: ...` |
| Several YAML documents with the same keys | Treated as a list of records: one table |
| Notebook cell output longer than 40 lines | First 40 lines kept, then `... (N more lines)` |
| HTML that only builds its content with JavaScript | Warning `no readable text` |
| `.gsheet`, `.gdoc`, `.gslides`, `.gdraw`, `.gform` | Error explaining the export route (see the user manual (deep dive) page, section 6) |
| Code that contains triple backticks | Four backticks are used for the fence |

### Images

| Input | Behaviour |
|---|---|
| Image with no text (blank, photo, chart) | Empty text and a warning `no text found` suggesting to send the image itself |
| Corrupt image bytes | `could not read this image` (422) |
| OCR language not installed (`--lang zzz`) | Error naming the package to install, with the list of installed languages |
| Animated GIF with 25 frames | First 20 read; warning `only the first 20 of 25 pages were read` |
| Dark-mode screenshot, transparent PNG | Handled by preparation (inversion; white background) |

### Token tools and command line

| Input | Behaviour |
|---|---|
| One enormous line without spaces and `--max-tokens 500` | Cut by characters; every part stays near the budget (largest about 504 estimated tokens) |
| Split parts and `.zip` | The archive contains each part exactly once |
| Folder scan | Picks up documents, slides, spreadsheets, HTML, notebooks, old Office files and images; skips `.json`, `.py`, `.txt` and similar |
| `report.csv` and `report.txt` converted in one command | `report.md` and `report_txt.md`: no overwrite within one run |
| Exit codes | `0` success, `1` a file failed, `2` nothing to convert |

## 2. Limits that no flag removes

| Limitation | Why | What to do |
|---|---|---|
| Pictures, charts, diagrams, handwriting are not described | The tool reads text, not meaning of images | Send the image itself to a vision model |
| OCR can misread names, numbers, small print | OCR is probabilistic; the confidence figure is an average | Check amounts, dates and names against the source |
| PDF tables without ruling lines and without horizontal rules are read as rows of text | Detection needs lines or rules | Check table-heavy PDFs; consider the spreadsheet source |
| Equations and special symbols in PDFs come out as text fragments | PDFs store glyph positions, not formulas | Use the LaTeX or Word source |
| Word headers, footers, footnotes, text boxes are not included | Not read by the converter (warned) | Copy them manually if needed |
| Formulas in Excel appear as values | Markdown has no formulas | Keep the `.xlsx` for calculations |
| JSON is not reproduced byte for byte | Readable rendering trades exactness for tokens | `--json minified` for exact JSON |
| Only nine document types are recognised | Rule-based classifier | Extend the cue dictionary (the build from scratch page, phase 8) |
| Right-to-left text in PDFs, password-protected Office files, very large files (hundreds of MB) | Not tested | Test with a real sample first; expect clear errors, not silent success |
| Token numbers are estimates | A real tokenizer is model-specific | Use the target model's own counter for exact numbers |
| The web page and the API have no login | Kept simple | Do not expose them publicly (the free deployment page) |

## 3. Troubleshooting

### Installation

| Symptom | Cause | Fix |
|---|---|---|
| `python: command not found` | Ubuntu provides `python3` only | Use `python3` outside the virtual environment; inside an activated venv `python` works |
| `error: externally-managed-environment` | `pip install` outside a venv | `python3 -m venv .venv && source .venv/bin/activate`, then `pip install -r requirements.txt` |
| `source: .venv/bin/activate: No such file` | Venv not created, or wrong folder | Run `python3 -m venv .venv` in the project folder |
| `The virtual environment was not created successfully ... ensurepip` | `python3-venv` missing | `sudo apt install python3-venv` |
| `ModuleNotFoundError: No module named 'src'` | Command run from the wrong folder | `cd` into the project root; run `python -m src.cli ...`, not `python src/cli.py` |
| `ModuleNotFoundError: pdfplumber` (or another package) | Venv not active, or packages not installed | Activate the venv; `pip install -r requirements.txt` |
| `TesseractNotFoundError` / `tesseract is not installed` | OCR program missing | `sudo apt install tesseract-ocr` (macOS: `brew install tesseract`; Windows: install a Tesseract build and add it to `PATH`, untested here) |
| `OCR language 'ben' is not installed` | Language pack missing | `sudo apt install tesseract-ocr-ben`; list installed: `tesseract --list-langs` |
| `streamlit: command not found` | Venv not active | Activate the venv, or `python -m streamlit run app/streamlit_app.py` |
| `Address already in use` | Port 8501 or 8000 taken | `streamlit run app/streamlit_app.py --server.port 8502`; `uvicorn api.main:app --port 8001` |
| Windows: venv activation fails | Different command | `.venv\Scripts\activate` (PowerShell may need `Set-ExecutionPolicy -Scope Process RemoteSigned`); untested here |

### Output quality

| Symptom | Likely cause | Fix |
|---|---|---|
| Text in a PDF is gibberish (`(cid:12)`, odd symbols) | Broken font mapping | Run with `--ocr` to read the page image instead |
| Two-column text interleaves | Gutter not detected (very few rows, or narrow gutter) | Try `--ocr`; open an issue with a sample |
| Headings missing in a PDF | Headings use the same size and weight as body text | Nothing to detect; add manually |
| Whole document in one paragraph (image) | Low-resolution or unusual layout | Use a larger or sharper screenshot; try `--lang` |
| OCR text has strange words | Wrong language | Set `--lang` to the document's language |
| A header the reader wanted is gone | It repeated on at least half the pages | `--keep-headers` |
| Numbers differ from the chat tool's counter | Estimate vs real tokenizer | Expected; use the model's counter for exact figures |
| Output is longer than the original text file | Pretty-printed data converted to a table of long rows, or `--json minified` of compact input | Compare with `--compact`; for text formats the web page shows the difference |
| `.md` overwritten | Same output name in a later run | Use a different `-o` folder per run |

### Runtime errors

| Error shown | Meaning |
|---|---|
| `could not convert this file: <ErrorType>: ...` | A parser failed on a malformed file; the type and message come from the library. The file may be corrupt: open it in its normal application and save again |
| HTTP 413 | File over `MAX_UPLOAD_MB` (raise the variable, or split the file) |
| HTTP 415 | Extension not supported (rename only if the content really is that format) |
| `LLMUnavailable: no LLM configured` | `--llm` used without `LLM_MODEL` or `ANTHROPIC_API_KEY`; the built-in summary needs none |
| Summary warning `kept the extractive summary` | The AI model wrote a number that is not in the document; the checked fallback was used |

## 4. Reporting a problem usefully

Include: the command or options used, the exact message, `python3 --version`, `tesseract --version`, and a small *non-confidential* file that reproduces it. Then add the case to
`scripts/corner_cases.py` and a unit test, so the fix stays fixed.
