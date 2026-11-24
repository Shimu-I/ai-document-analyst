# 04 - System Architecture

## Full architecture

```mermaid
flowchart LR
    subgraph IN["Inputs"]
        i1["PDF"]
        i2["DOCX XLSX PPTX CSV"]
        i3["Images"]
        i4["JSON YAML XML HTML<br/>notebooks code"]
        i5["Old Office files"]
    end
    subgraph CONV["src/convert"]
        d["convert()<br/>picks a converter<br/>by extension"]
        c1["pdf.py<br/>pdf_special.py"]
        c2["office.py<br/>omml.py"]
        c3["image.py"]
        c4["structured.py"]
        lo["LibreOffice bridge"]
        cp["compact.py<br/>compact + split"]
        as["assets.py<br/>image store"]
    end
    subgraph AN["src/analyze"]
        cl["classify.py<br/>document type"]
        su["summarize.py<br/>summary, outline"]
    end
    subgraph SV["Service layer"]
        sv["service.py<br/>process, output_files,<br/>zip_results"]
        hi["history.py<br/>SQLite"]
    end
    subgraph FR["Front ends"]
        f1["Streamlit app<br/>app/"]
        f2["CLI<br/>src/cli.py"]
        f3["FastAPI<br/>api/main.py"]
    end
    i1 --> d
    i2 --> d
    i3 --> d
    i4 --> d
    i5 --> lo --> d
    d --> c1
    d --> c2
    d --> c3
    d --> c4
    c1 --> as
    c2 --> as
    c1 --> cp
    c2 --> cp
    c3 --> cp
    c4 --> cp
    cp --> sv
    sv --> cl
    sv --> su
    sv --> hi
    sv --> f1
    sv --> f2
    sv --> f3
```

Pre-drawn versions of this diagram are in [`docs/assets`](assets/) (`01_architecture.png`).

## Three layers

| Layer | Folder | Job | Knows about |
|---|---|---|---|
| Conversion | `src/convert/` | Bytes plus a file name become a `ConvertedDocument` | Parsers only |
| Analysis | `src/analyze/` | Decide the document type, write the summary | The Markdown text |
| Delivery | `src/service.py`, `src/cli.py`, `api/`, `app/` | Check requests, call the layers, package results | The two layers above |

Dependencies point one way. The converters do not know about analysis. The front ends do not know about parsers. Replacing Streamlit would change only the `app/` folder.

## Modules

| File | Lines | Responsibility |
|---|---:|---|
| `src/convert/base.py` | 114 | `ConvertedDocument`, `ConversionError`, `estimate_tokens`, table helpers, text cleaning |
| `src/convert/__init__.py` | 130 | `convert()` dispatch, accepted types, LibreOffice bridge |
| `src/convert/pdf.py` | 669 | Rows, columns, headings, lists, tables, header and footer removal, OCR fallback |
| `src/convert/pdf_special.py` | 243 | Figures and display equations of a PDF page, saved as images |
| `src/convert/office.py` | 464 | DOCX, XLSX, PPTX, CSV, text decoding |
| `src/convert/omml.py` | 142 | Word equations to LaTeX |
| `src/convert/image.py` | 228 | Image preparation, Tesseract, layout rebuilding |
| `src/convert/structured.py` | 422 | JSON, YAML, TOML, XML, notebooks, HTML, code, Google shortcut files |
| `src/convert/compact.py` | 140 | Compact mode and splitting by token budget |
| `src/convert/assets.py` | 61 | `AssetStore`: names and keeps image files |
| `src/analyze/classify.py` | 108 | Document type by weighted keyword cues |
| `src/analyze/summarize.py` | 286 | Extractive summary, outline, optional AI summary check |
| `src/llm/client.py`, `cost.py` | 143, 38 | Optional AI clients and cost estimates |
| `src/service.py` | 126 | `process()`, `public()`, `output_files()`, `zip_results()`, `health()` |
| `src/slides.py` | 174 | Slide-by-slide reading: original picture, text and line positions (PDF, PowerPoint, Word, images) |
| `src/desktop_model.py` | 104 | Desktop state: edits, text-to-slide links, geometry |
| `app/desktop.py` | 370 | Desktop window (Tkinter) |
| `src/history.py` | 110 | SQLite record of conversions |
| `src/cli.py` | 121 | Command line |
| `api/main.py` | 82 | FastAPI endpoints |
| `app/streamlit_app.py`, `app/ui.py`, `app/views/*` | 29, 123, 444 | Web app: entry, look, four pages |

## The shared data object

Every converter returns the same object. That is why the rest of the system does not care about the file format.

```mermaid
classDiagram
    class ConvertedDocument {
        +str filename
        +str kind
        +str markdown
        +str title
        +int pages
        +list sheets
        +int tables
        +int figures
        +int formulas
        +int images_omitted
        +int ocr_pages
        +int headers_footers_removed
        +list warnings
        +float seconds
        +float ocr_confidence
        +dict assets
        +int source_chars
        +int compact_saved_chars
        +words()
        +est_tokens()
    }
    class Analysis {
        +str doc_type
        +str confidence
        +list cues
        +str title
        +str one_line
        +str summary
        +list outline
        +list key_points
        +str method
        +list warnings
    }
    class AssetStore {
        +dict files
        +add(kind, data)
        +count(kind)
    }
    ConvertedDocument --> AssetStore : assets
    Analysis ..> ConvertedDocument : reads
```

`kind` is one of `pdf`, `docx`, `xlsx`, `pptx`, `csv`, `image`, `text`, `json`, `yaml`, `toml`, `xml`, `notebook`, `html`, `code`.

## Data flow of one request

```mermaid
sequenceDiagram
    actor User
    participant FE as Front end<br/>(web, CLI or API)
    participant SV as service.process
    participant CV as convert()
    participant AN as analyze()
    participant HI as history (web app only)
    User->>FE: file + options
    FE->>SV: bytes, filename, options
    SV->>SV: empty? too large? type supported?
    SV->>CV: convert(bytes, filename, ...)
    CV-->>SV: ConvertedDocument
    SV->>AN: analyze(document)
    AN-->>SV: type, summary, outline
    SV-->>FE: result dictionary
    FE->>HI: record name, type, size, time
    FE-->>User: preview, .md, .zip
```

Splitting by token budget happens late, in `output_files()`, because it only matters when files are handed over.

## Error mapping

| Situation | Code | Meaning |
|---|---|---|
| Empty file | 400 | Nothing to read |
| File over `MAX_UPLOAD_MB` (50 by default) | 413 | Too large |
| Extension not supported | 415 | Unsupported type |
| Corrupt, encrypted, invalid file; bad option | 422 | Could not convert |

## Deployment view

```mermaid
flowchart LR
    subgraph PC["One computer"]
        b["Browser"] --> st["Streamlit :8501"]
        t["Terminal"] --> cl["CLI"]
        o["Other program"] --> ap["FastAPI :8000"]
        st --> core["service + converters"]
        cl --> core
        ap --> core
        core --> db[("history.db")]
        core --> tess["Tesseract / LibreOffice<br/>(system programs)"]
    end
    core -. "optional" .-> ol["Ollama / LLM server"]
```

Everything runs in one Python process per interface. Nothing is sent out unless the optional AI summary is configured.

---
Previous: [03 Technology Stack](03_technology_stack.md) · Next: [05 Internal Workflow](05_internal_workflow.md)
