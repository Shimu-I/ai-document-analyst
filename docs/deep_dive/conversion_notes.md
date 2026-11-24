# Conversion notes and known limits

Warnings listed here are shown to the user in the app, CLI and API (`warnings`).

## PDF (`src/convert/pdf.py`)

How it works: words are read with their font size and name; larger or all-bold short lines become
headings; bullets and numbers become lists; monospace lines become code blocks; wrapped lines are
re-joined and end-of-line hyphenation repaired; ruled tables become Markdown tables; two-column pages
are detected from an empty vertical gutter and read left column then right; repeated headers, footers
and bare page numbers are removed (and counted); pages without a text layer go through Tesseract OCR.

| Limit | Behaviour |
|---|---|
| Images / charts / figures | Omitted. Warning: "N image(s) omitted: only text is converted" |
| Tables without ruling lines | Come out as plain text, not a Markdown table |
| Maths | Plain text; symbols may be garbled |
| Scanned pages | OCR; warning "expect character errors". Quality depends on the scan |
| Fonts with no Unicode table | Unreadable characters are counted and reported |
| Vertical margin text (e.g. arXiv stamp) | Moved to the end of its page and reported |
| Diagonal watermarks | Skipped and reported |
| Headings | Detected from font size/boldness; a document that styles headings unusually may get none |
| Password-protected PDFs | Clear error: "remove the password and try again" |

## Word (`.docx`)

Headings, lists, tables, bold/italic and code styles are kept in document order. Not included:
headers, footers, footnotes, text boxes (warning shown). Pictures omitted.

## Excel (`.xlsx`, `.xlsm`)

One `##` section and one table per sheet. Formula cells show the value stored in the file; if the
workbook was never recalculated those cells are empty and a warning says how many. Hidden sheets are
skipped. Limits: 5,000 rows and 60 columns per sheet (truncation is reported). Charts omitted.

## PowerPoint (`.pptx`)

One `## Slide N: title` section per slide with bullets (nesting kept), tables and speaker notes.
Pictures and charts omitted (counted).

## Images, CSV/TSV, text

Images are OCR'd (prepared first: orientation, transparency, dark mode, size; confidence reported). CSV/TSV become a table with
delimiter and encoding detection (rows above 5,000 are cut with a warning). TXT/MD are passed through after cleaning.

## Data, web and code files

JSON, JSONL, YAML, TOML and XML: lists of similar records become one table, everything else becomes `key: value` lines
(XML with entity declarations is refused). Notebooks keep Markdown cells, code and text outputs (first 40 lines each).
HTML keeps the main content only. Source code becomes a fenced block. Google shortcut files (`.gsheet`, `.gdoc`, `.gslides`)
give an error with export instructions. Full behaviour per case: [corner cases](corner_cases.md).

## Old formats

`.doc .xls .ppt .odt .ods .odp .rtf` are converted through LibreOffice first if `soffice` is on the
PATH; otherwise the error says to save as the modern format.

## Summary and type detection (`src/analyze/`)

- Type: weighted keyword cues per type; the cues that matched are returned. Spreadsheets and
  presentations are labelled from the file kind. Low score → "General document".
- Summary: extractive by default (picks sentences, preferring an Abstract / Summary / Overview section).
  Spreadsheets and slide decks get a structural summary (sheet names and columns, slide titles).
- Optional AI summary: any number the model writes must occur in the document; otherwise it is
  discarded and the extractive summary is used. Long documents are sent as beginning + end, with the
  middle marked as omitted.

## Not tested

Password-protected Office files, very large files (> 50 MB by default), right-to-left and CJK
scripts in PDFs, heavily skewed scans, Windows and macOS have no dedicated tests.
