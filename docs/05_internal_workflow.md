# 05 - Internal Workflow

This page follows one file through the system, step by step. Each diagram shows one stage. The algorithms behind the boxes are explained in [06 Implementation Details](06_implementation_details.md).

## 1. The whole journey

```mermaid
flowchart TD
    A([File + options]) --> B{"Empty?"}
    B -- yes --> E400["Error 400"]
    B -- no --> C{"Larger than<br/>MAX_UPLOAD_MB?"}
    C -- yes --> E413["Error 413"]
    C -- no --> D{"Extension<br/>supported?"}
    D -- no --> E415["Error 415"]
    D -- yes --> F["convert():<br/>choose converter"]
    F --> G["Converter builds<br/>Markdown + notes"]
    G --> H{"Compact<br/>mode?"}
    H -- yes --> I["Remove padding,<br/>comments, empty values"]
    H -- no --> J
    I --> J["Classify the document"]
    J --> K["Write summary<br/>and outline"]
    K --> L{"Split size<br/>set?"}
    L -- yes --> M["Cut into parts<br/>before headings"]
    L -- no --> N
    M --> N["Result:<br/>.md, images, stats"]
    N --> O([Preview and download])
    G -. "any parser failure" .-> E422["Error 422<br/>with a clear message"]
```

## 2. Choosing the converter

```mermaid
flowchart LR
    X["file name"] --> Y{"extension"}
    Y -- ".pdf" --> P["convert_pdf"]
    Y -- ".docx" --> W["convert_docx"]
    Y -- ".xlsx .xlsm" --> XL["convert_xlsx"]
    Y -- ".pptx" --> PP["convert_pptx"]
    Y -- ".csv .tsv" --> CS["convert_csv"]
    Y -- "image types" --> IM["convert_image"]
    Y -- "json yaml toml xml<br/>html ipynb code" --> ST["structured.py"]
    Y -- ".doc .xls .ppt<br/>.odt .ods .odp .rtf" --> LO["LibreOffice converts<br/>to a modern format"] --> Y2["then DOCX / XLSX / PPTX"]
    Y -- "google shortcut" --> GE["Error with<br/>export instructions"]
```

The decision uses the extension only. A PNG renamed to `.pdf` fails with "could not open PDF".

## 3. PDF workflow

```mermaid
flowchart TD
    P1["Open PDF<br/>(password? error)"] --> P2["For each page:<br/>read words with position,<br/>font and size"]
    P2 --> P3{"Fewer than 20<br/>characters?"}
    P3 -- yes --> P4["Render at 250 dpi<br/>and run OCR"]
    P3 -- no --> P5["Find tables<br/>(ruled and rule-only)"]
    P5 --> P6["Find figures and<br/>display equations<br/>(if images enabled)"]
    P6 --> P7["Group words into rows"]
    P7 --> P8["Detect two columns<br/>(empty gutter)"]
    P8 --> P9["Order: left column,<br/>then right column"]
    P4 --> P10
    P9 --> P10["Classify each row:<br/>heading, list, code,<br/>paragraph"]
    P10 --> P11["Join wrapped lines,<br/>fix hyphenation"]
    P11 --> P12["After all pages:<br/>remove repeated headers,<br/>footers, page numbers"]
    P12 --> P13["Markdown + notes"]
```

## 4. Image (OCR) workflow

```mermaid
flowchart TD
    I1["Open image<br/>(each frame, max 20)"] --> I2["Fix rotation (EXIF)"]
    I2 --> I3["Transparent to white"]
    I3 --> I4{"Mostly dark?"}
    I4 -- yes --> I5["Invert colours"]
    I4 -- no --> I6
    I5 --> I6["Autocontrast,<br/>resize to 1400-5000 px"]
    I6 --> I7["OCR with page mode 3"]
    I7 --> I8{"Confident<br/>enough?"}
    I8 -- no --> I9["Try modes 6 and 4,<br/>keep the best"]
    I8 -- yes --> I10
    I9 --> I10["Rebuild lines,<br/>lists, headings<br/>from word boxes"]
    I10 --> I11["Report mean confidence<br/>and doubtful words"]
```

## 5. Data file workflow (JSON, YAML, TOML, XML)

```mermaid
flowchart TD
    D1["Parse the file<br/>(error if invalid)"] --> D2{"List of 2+ records<br/>with similar keys<br/>and 30 columns or fewer?"}
    D2 -- yes --> D3["One Markdown table:<br/>keys written once"]
    D2 -- no --> D4["key: value lines,<br/>indented by depth"]
    D3 --> D5["Compact mode:<br/>drop empty values"]
    D4 --> D5
    D5 --> D6["Markdown"]
```

## 6. Word and PowerPoint extras

```mermaid
flowchart LR
    W1["Paragraph"] --> W2{"Contains<br/>equation?"}
    W2 -- yes --> W3["Office Math tree<br/>to LaTeX"]
    W2 -- no --> W4["Runs: bold, italic, links"]
    W1 --> W5{"Contains<br/>picture?"}
    W5 -- yes --> W6["Save PNG/JPG/GIF<br/>in assets/ and link it"]
```

## 7. Figures and equations in a PDF page

```mermaid
flowchart TD
    F1["Page objects"] --> F2["Raster images<br/>40x30 pt or larger"]
    F1 --> F3["Clusters of 6+ lines,<br/>curves, rectangles<br/>(outside tables)"]
    F2 --> F4["Merge overlapping boxes,<br/>add nearby axis labels"]
    F3 --> F4
    F4 --> F5{"More than 60<br/>words inside?"}
    F5 -- yes --> F6["Not a figure:<br/>keep as text"]
    F5 -- no --> F7["Crop page at 170 dpi<br/>save PNG, words become alt text"]
    F1 --> E1["Rows split into segments<br/>at large gaps"]
    E1 --> E2{"Maths font or<br/>2+ maths symbols,<br/>and little prose?"}
    E2 -- yes --> E3["Add neighbouring short<br/>segments (fraction parts,<br/>limits, equation number)"]
    E3 --> E4["Crop and save PNG"]
    E2 -- no --> E5["Stay normal text"]
```

## 8. Token tools

```mermaid
flowchart LR
    T1["Markdown"] --> T2["Compact:<br/>trim table padding,<br/>HTML comments,<br/>blank lines"]
    T2 --> T3["Estimate tokens"]
    T3 --> T4{"Over the<br/>limit N?"}
    T4 -- no --> T5["One file"]
    T4 -- yes --> T6["Split into blocks,<br/>pack until N,<br/>break before headings"]
    T6 --> T7["Label '(part i of n)',<br/>repeat table header"]
```

## 9. Analysis workflow

```mermaid
flowchart TD
    A1["Markdown + kind"] --> A2{"Format decides?<br/>(json, yaml, code,<br/>notebook, html)"}
    A2 -- yes --> A3["Fixed label"]
    A2 -- no --> A4["Score each document type<br/>with weighted cues"]
    A4 --> A5{"Best score<br/>at least 4?"}
    A5 -- no --> A6["General document,<br/>low confidence"]
    A5 -- yes --> A7["Type + confidence<br/>+ matched cues"]
    A3 --> S1
    A6 --> S1
    A7 --> S1["Summary"]
    S1 --> S2{"AI model<br/>configured and<br/>chosen?"}
    S2 -- no --> S3["Extractive summary:<br/>pick the best sentences"]
    S2 -- yes --> S4["AI writes JSON summary"]
    S4 --> S5{"Every number in it<br/>found in the document?"}
    S5 -- yes --> S6["Use AI summary"]
    S5 -- no --> S3
```

## 10. Web app and history

```mermaid
sequenceDiagram
    participant U as User
    participant H as Home page
    participant C as Convert page
    participant S as service
    participant DB as history.db
    participant D as Dashboard page
    U->>H: reads features and manual
    U->>C: adds files, sets options
    C->>S: process(each file)
    S-->>C: results
    C->>DB: save name, type, size, time, counts
    C-->>U: cards, preview, downloads
    U->>D: opens dashboard
    D->>DB: read all rows
    D-->>U: totals, charts, table, CSV
```

---
Previous: [04 System Architecture](04_system_architecture.md) · Next: [06 Implementation Details](06_implementation_details.md)
