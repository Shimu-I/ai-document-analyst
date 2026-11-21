# 06 - User manual

How to use the tool day to day: install, convert files, pick options, understand the result, save tokens.
Installation details are in [07](07_free_setup.md); free hosting is in [09](09_deployment_free.md).

## 1. Install in five minutes

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip tesseract-ocr    # macOS: brew install python tesseract
cd ai-document-analyst
python3 -m venv .venv
source .venv/bin/activate              # repeat in every new terminal
pip install -r requirements.txt
```

Optional: LibreOffice (`sudo apt install libreoffice-writer libreoffice-calc libreoffice-impress`) for old `.doc`, `.xls`, `.ppt`, `.odt`, `.rtf` files.

## 2. Three ways to use it

| Way | Start | Best for |
|---|---|---|
| Web page | `streamlit run app/streamlit_app.py` (opens http://localhost:8501) | One-off conversions, previewing, downloading |
| Command line | `python -m src.cli <file or folder>` | Batches, scripts, automation |
| HTTP API | `uvicorn api.main:app` (docs at http://localhost:8000/docs) | Calling the tool from other programs |

All three use the same code (`src/service.py`) and give the same results.

### 2.1 Web page

1. Open the page, choose one or more files (drag and drop works).
2. Set the options in the left sidebar (section 4). **Compact mode is switched on by default in the web page** (it is off by default in the command line and the API).
3. Click **Convert**.
4. For each file: read *What this is* and the summary, check the warnings, then **Download .md**.
5. For several files or split parts, a **.zip** download appears.

The tabs show the raw Markdown (copy it from there), a rendered preview, and the outline. The metrics show word count, estimated tokens, and,
for text-based formats, the change against the raw file.

### 2.2 Command line

```bash
python -m src.cli report.pdf                       # writes report.md next to the PDF
python -m src.cli report.pdf -o markdown/          # writes into a folder
python -m src.cli scan.png --stdout                # prints the text, writes nothing
python -m src.cli docs/ -o markdown/               # every document and image in the folder, recursively
python -m src.cli data.json --compact              # smallest readable form
python -m src.cli data.json --json minified        # exact JSON, whitespace removed
python -m src.cli book.pdf --max-tokens 3000       # book_part1.md, book_part2.md, ...
python -m src.cli note.png --lang eng+ben          # English + Bangla OCR (language pack needed)
python -m src.cli report.pdf --summary             # add a short summary block at the top of the .md
```

| Flag | Meaning |
|---|---|
| `-o`, `--out DIR` | Output folder (default: next to each input) |
| `--stdout` | Print Markdown instead of writing files |
| `--summary` | Put the type, summary and key points at the top of the `.md` |
| `--compact` | Remove table padding, comments, blank lines, empty data values |
| `--max-tokens N` | Split into parts of about N tokens (N of at least 200) |
| `--json readable\|minified` | Data-file style: readable tables and lines (default), or exact one-line JSON |
| `--lang CODE` | OCR language, e.g. `eng`, `ben`, `eng+ben` (also the `OCR_LANG` environment variable) |
| `--ocr` | Force OCR for every PDF page, even when a text layer exists |
| `--page-markers` | Insert `<!-- page N -->` before each PDF page (removed again by `--compact`) |
| `--keep-headers` | Keep repeated headers and footers in PDFs |
| `--llm` | Use the configured AI model for the summary (section 7) |

**Exit codes:** `0` all files converted; `1` at least one failed (the others are still written); `2` nothing to convert.

**Folders.** A folder scan converts documents, spreadsheets, slides, HTML, notebooks, old Office files and images. Plain text, Markdown, source code and
data files (JSON, YAML, XML, TOML) are skipped, since they are already text; name them explicitly to convert them. Within one run, two inputs that would
produce the same name never overwrite each other (`report.md` and `report_docx.md`). A *later* run into the same folder overwrites earlier outputs.

### 2.3 HTTP API

```bash
curl -F file=@report.pdf http://localhost:8000/analyze                         # type, summary, stats (no Markdown)
curl -F file=@report.pdf http://localhost:8000/convert                         # everything, as JSON
curl -F file=@data.json -F compact=true -o data.md http://localhost:8000/convert/download
curl -F file=@book.pdf -F max_tokens=3000 -o book_parts.zip http://localhost:8000/convert/download
curl http://localhost:8000/health
```

Form fields: `compact`, `json_mode` (`readable` or `minified`), `ocr_lang`, `max_tokens`, `page_markers`, `keep_headers`, `force_ocr`, `use_llm`,
and, for `/convert/download`, `include_summary`. Errors are JSON `{"detail": "..."}` with status 400 (empty), 413 (too large), 415 (unsupported), 422 (could not convert).
The API has **no authentication and no rate limit**; use it only on a trusted network.

## 3. What each format produces

| Input | Output |
|---|---|
| **PDF** | Headings from font size; paragraphs re-joined; lists; tables (ruled and rule-only); code blocks; two-column text in reading order; repeated headers, footers and page numbers removed. Scanned pages go through OCR |
| **DOCX** | Headings, bold/italic, links, nested bullet and numbered lists, tables (merged cells blanked once) |
| **XLSX / XLSM** | One `## Sheet` heading per visible sheet; one table per block of rows; dates as ISO text; formulas shown as results (or as formula text when the file was never recalculated) |
| **PPTX** | `## Slide N: title`, bullets with nesting, tables, charts as tables, speaker notes as quotes |
| **CSV / TSV** | A table; delimiter and encoding detected |
| **Image** | Text with lines, lists and headings; mean OCR confidence; doubtful words named |
| **JSON / JSONL / YAML / TOML / XML** | Tables for lists of similar records, `key: value` lines otherwise |
| **Notebook** | Markdown and code cells, text outputs (first 40 lines of each), no embedded images |
| **HTML** | Main content only; navigation, footers, scripts and link addresses removed |
| **Code** | A fenced block with the language |
| **.gsheet / .gdoc / .gslides** | An error that explains how to export (section 6) |

## 4. Options and when to use them

| Situation | Option |
|---|---|
| Pasting into a chat and every token counts | `--compact` (already on in the web page) |
| Document longer than the chat's limit | `--max-tokens N` (3,000 to 8,000 is a common range; use the model's limit minus room for questions and answers) |
| JSON that another program will parse again | `--json minified` (exact) |
| Text in a scanned PDF looks garbled | `--ocr` to force a fresh OCR of every page, and set `--lang` |
| Non-English images | `--lang ben`, `--lang eng+ben`, and so on |
| Need to know which page a passage came from | `--page-markers` (not with `--compact`) |
| Running header was removed that should have stayed | `--keep-headers` |

## 5. Read the result before trusting it

1. **Type and confidence.** `low` confidence means few cues matched; the Markdown is still valid.
2. **Warnings.** Each is something that did *not* convert faithfully: pictures omitted, headers removed, formulas without results, low OCR confidence, truncated sheets.
3. **OCR confidence.** Above 90% is usually reliable. Below 85% a warning lists doubtful words. Always verify names, amounts and dates against the picture.
4. **Token numbers** are estimates. They guide decisions (is the split long enough?) but do not replace the model's own counter.
5. **Spot-check one table and one list** against the original after the first conversion of a new document type.

## 6. Google Sheets, Docs and Slides

`.gsheet`, `.gdoc`, `.gslides`, `.gdraw` and `.gform` files saved by Google Drive for desktop are shortcuts containing only a link. Nothing can be read from them.
Export first, then upload the exported file:

| Google file | Export route (in the browser) | Upload |
|---|---|---|
| Sheets | File > Download > Microsoft Excel (.xlsx) or Comma-separated values (.csv, current sheet only) | `.xlsx` / `.csv` |
| Docs | File > Download > Microsoft Word (.docx) or PDF | `.docx` / `.pdf` |
| Slides | File > Download > Microsoft PowerPoint (.pptx) or PDF | `.pptx` / `.pdf` |

## 7. Optional AI summary (free options)

The default summary needs no AI. To let a model write it:

```bash
# Local and free: install Ollama, then
ollama pull llama3.2
export LLM_BASE_URL=http://localhost:11434/v1
export LLM_MODEL=llama3.2
python -m src.cli report.pdf --llm
```

The model is chosen from the environment: when `LLM_MODEL` is set, an OpenAI-compatible endpoint is used (`LLM_BASE_URL`, `LLM_API_KEY`; Ollama needs no key); otherwise,
when `ANTHROPIC_API_KEY` is set, Anthropic's API is used; `LLM_PROVIDER=anthropic|openai` forces a choice. With none of these set, the *Use an AI model* box in the web page stays disabled.
A model reply that contains a number absent from the document is discarded, and the extractive summary stays (a warning says so). Only the *summary*
step ever leaves the computer, and only with a hosted provider configured.

## 8. A workflow for saving tokens in chat

1. Convert the file: `python -m src.cli paper.pdf --compact --max-tokens 6000 -o md/`.
2. Open `md/paper_part1.md`; check the first lines and the warnings.
3. Paste part 1 with the question. Paste further parts only when the question needs them (parts say `(part i of n)`).
4. For images that are mostly text, paste the OCR text instead of attaching the picture (the tool prints the cost of both).
5. For spreadsheets, convert and paste only the relevant sheet section instead of the whole file.
6. Keep the `.md` files: they are plain text, searchable and versionable.

## 9. Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `OCR_LANG` | `eng` | Default OCR language(s) |
| `MAX_UPLOAD_MB` | `50` | Upload limit (web page and API) |
| `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` | unset | OpenAI-compatible model (Ollama, others) for the optional summary |
| `LLM_PROVIDER` | auto | Force `anthropic` or `openai` |
| `PRICE_INPUT_PER_MTOK`, `PRICE_OUTPUT_PER_MTOK` | built-in table | Price per million tokens used for the cost estimate of an AI summary (a local model costs $0) |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | unset | Anthropic API for the optional summary |
| `LLM_SUMMARY_CHARS` | `12000` | How much of the document is sent to the model |
| `LLM_TIMEOUT` | `300` | Seconds to wait for the model |

## 10. Limits at a glance

| Limit | Value |
|---|---|
| Upload size | 50 MB (`MAX_UPLOAD_MB`) |
| Spreadsheet rows / columns per sheet | 5,000 / 60 (warning when cut) |
| Image frames (GIF/TIFF) read | 20 |
| Notebook output lines per cell | 40 |
| Minimum `--max-tokens` | 200 |
| Nested data depth rendered line by line | 12 levels |

More edge cases: [chapter 10](10_corner_cases_and_troubleshooting.md).
