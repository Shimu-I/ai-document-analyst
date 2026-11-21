# 01 - Project brief

## Task

Convert any common office document into clean Markdown, say what the document is, and give a short
summary, all locally and for free.

## Who it is for

A person who regularly gives documents (papers, reports, spreadsheets, slide decks) to an AI chatbot
and wants to (a) stop paying tokens for the chatbot to read messy files or re-type them as Markdown,
and (b) keep a plain-text copy of the document.

## Input

PDF (digital or scanned), DOCX, XLSX/XLSM, PPTX, CSV/TSV, images (PNG, JPG, WEBP, TIFF, BMP, GIF; OCR), JSON/JSONL/YAML/TOML/XML,
Jupyter notebooks, HTML, source code, TXT/MD; old DOC/XLS/PPT/ODT/RTF when LibreOffice is installed. Google Drive shortcut files
(`.gsheet` and similar) cannot be read; the tool explains how to export them.

## Output

| Output | Description |
|---|---|
| `.md` file | The document's own content: headings, paragraphs, lists, tables, code, slides, sheets |
| Document type | e.g. Research paper, Business report, Presentation, with the cues that led to it |
| Summary | 3–5 sentences, plus key points and an outline of headings |
| Stats | pages, words, estimated tokens, tables found, time; for text formats, the change against the raw file |
| Warnings | what was not converted (pictures, headers/footers in Word, OCR used, truncated sheets…) |

## Design decisions

- **Offline and free by default.** No API key needed. An AI summary is optional (local Ollama).
- **Faithful over pretty.** The goal is that no text is lost and reading order is right; missing
  content is reported as a warning instead of being silently dropped.
- **Summaries cannot invent.** The default summary only selects sentences that exist in the document;
  an AI summary is rejected if it contains numbers that are not in the document.
- **One service function** (`src/service.py`) feeds the CLI, the API and the web page, so all three
  behave identically.

## Token tools

Compact mode removes padding and empty values; `--max-tokens N` splits the result into parts of about N estimated tokens (chapter 04, section 7).

## Out of scope

Describing images or charts, perfect table recovery from unruled PDFs, editing documents, chatting
with documents, and non-text content such as audio or video.

## History

The first version of this repository was an invoice field extractor. It was replaced by this
document-to-Markdown tool; the invoice work remains in git history (commits before `2c76507`).
