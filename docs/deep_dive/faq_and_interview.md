# FAQ and interview questions

Part 1 answers practical questions about the tool. Part 2 collects questions likely to come up when the project is presented (interview, viva, portfolio review), with answers grounded in what the code and the measurements actually show.

## Part 1 - FAQ

**What is this project?**
A local tool that converts PDF, Word, Excel, PowerPoint, CSV, images, JSON-like data, HTML and code into clean Markdown, says what kind of document it is, and writes a short summary. The Markdown is meant to be pasted into an AI chat instead of the original file. See [concepts and architecture](concepts_and_architecture.md).

**Why not just ask a chatbot to convert the file?**
Three reasons. (1) The chatbot spends output tokens re-typing the whole document. (2) A local converter is deterministic: the same file gives the same result. (3) The file never leaves the computer during conversion. The cost of the alternative was not measured against any specific chatbot, so no percentage is claimed for that comparison.

**Does anything leave the computer?**
Conversion: no. Only the optional AI summary sends text to a model, and only when a hosted provider is configured. With local Ollama nothing leaves the machine. A hosted deployment (the free deployment page) uploads files to that host.

**Does it cost anything?**
No. Every dependency is open source. The optional AI summary can use free local models.

**How accurate is the conversion?**
Measured on three synthetic PDFs, reading order was 100% for this tool against 52% to 93% for the comparison tool (markitdown); see [evaluation details](evaluation_details.md). Those samples were built during development and the rules were tuned on them, so real-world accuracy will be lower. The honest statement: good on clean digital documents, variable on messy ones, and every known loss is reported as a warning.

**How accurate is OCR?**
It depends on image quality. The tool reports the mean Tesseract confidence and names doubtful words. Names, amounts and dates should always be checked against the picture.

**How are tokens counted?**
By an estimate: ASCII characters divided by 4 plus other characters divided by 1.5. Real tokenizers differ by model. The estimate is good for deciding whether a split is needed, not for billing.

**Which token savings are real?**
Measured on one generated 40-record JSON file: indented JSON 2,600 estimated tokens, minified 1,416, readable 822, readable plus compact 716. Against minified JSON (the fairer baseline) that is about 42% and 49% fewer. The result depends heavily on the data; records with long text values save much less.

**Why is a Google Sheet not readable?**
`.gsheet` files saved by Google Drive for desktop are shortcuts containing only a link. The content lives on Google's servers. Export to `.xlsx` or `.csv` first ([user manual (deep dive), section 6](user_manual.md#6-google-sheets-docs-and-slides)).

**Can pictures and charts be described?**
No. The tool extracts text. A chart or photo should be sent to the chat as an image. The tool prints the estimated cost of sending the image so the two options can be compared.

**Can it run on Windows?**
The code is plain Python and should work, but it was only run on Linux. Tesseract must be installed separately and added to `PATH`.

**Why does the command line not convert my `.json` files when a folder is given?**
JSON, YAML, XML, TOML, plain text and source code are already text, so a folder scan skips them. Naming such a file explicitly converts it.

**Where are the tests, and how are they run?**
`pytest -q` runs the unit tests (131 pass, 1 skipped when FastAPI is missing). `python scripts/corner_cases.py` runs 49 awkward inputs. `python scripts/evaluate_fidelity.py` compares against markitdown. See [testing and reproduction](testing_and_reproduction.md).

## Part 2 - Interview and presentation questions

### The pitch

**Describe the project in 30 seconds.**
Chat tools charge by the token, and documents carry a lot of tokens that mean nothing: repeated page headers, JSON punctuation, padded tables, screenshots where only the text matters. This tool converts the file locally into compact Markdown, identifies the document type, summarises it, and can split the result into token-sized parts. It is free, runs offline, and reports everything it could not convert.

**Who is the user, and what problem is solved?**
Anyone who regularly pastes documents into AI chats on a free or limited plan: students, analysts, developers. The problem is wasted context and wasted quota, plus the privacy cost of uploading files to a tool just to get text.

**Why is this a reasonable project for a portfolio?**
It combines parsing of messy real formats, a small algorithmic core (layout inference from coordinates), honest evaluation against an existing tool, a shared service layer behind three interfaces, tests, and documentation of limits.

### Design decisions

**Why one `ConvertedDocument` type?**
Every converter returns the same dataclass, so analysis, the service layer and all three front ends stay format-agnostic. Adding a format touches one module and the dispatch table.

**Why a shared `service.py`?**
The command line, the API and the web page must not drift apart. Validation, error codes, splitting and zipping live in one place and are tested once.

**Why rule-based classification instead of a model?**
It is explainable (the matched cues are returned), free, instant and testable. The cost: only nine types, and unusual documents fall back to General. A trained classifier would need labelled data that was not available.

**Why is the default summary extractive?**
It can only select sentences that exist, so it cannot invent facts. The optional AI summary is checked: if any number of three or more characters is missing from the document, the reply is discarded and the extractive summary is kept.

**Why not use an existing converter such as markitdown?**
It was used as a baseline for evaluation. Writing the converters directly made layout handling (columns, headers, tables) controllable and was the learning goal. Fidelity numbers show where each tool wins.

**Why estimate tokens rather than use a tokenizer library?**
Tokenizers are model-specific, and the common ones need downloads or accounts. An estimate with a clear label avoids false precision.

**Why does the PDF converter use geometry?**
A PDF stores glyph positions, not paragraphs. Rows are formed from vertical overlap, headings from font size relative to the body, columns from an empty vertical strip, tables from ruling lines or aligned rules.

**Why Tesseract?**
It is free, local and supports many languages. Its weakness (layout and low-quality images) is handled by image preparation, trying more than one page segmentation mode, and rebuilding lines from word coordinates.

### Evaluation and honesty

**How was the tool evaluated?**
Fidelity script on three synthetic PDFs and one DOCX against markitdown (word recall, reading order, heading and table detection), a corner-case script with 49 cases, and 131 unit tests. Token savings were measured on one generated JSON file.

**What are the weaknesses of that evaluation?**
Samples are synthetic and the rules were tuned on them. There is no real-world corpus, no measurement of savings against real chatbot readers, and no user study. These are stated in the documentation rather than hidden.

**What failed during development, and what was learned?**
Two examples. (1) Two-column PDFs interleaved lines until the gutter detection was added. (2) The OCR layout step merged separate lines because the wrap rule treated short lines as wrapped; a guard for label-like lines (`LABEL_RE`) and a right-edge threshold of 0.88 fixed it. Both were found by testing on generated inputs, which is why a corner-case script exists.

**What would be checked first on a real document that converts badly?**
Whether the PDF has a text layer (run with `--ocr`), whether the columns were detected, and the warnings list.

### Extensions

**What would be improved next?**
Real UI screenshots and a hosted demo; a corpus of real, permission-cleared documents for evaluation; table detection for borderless PDFs; DOCX headers, footers and footnotes; a real tokenizer option; right-to-left language tests; a login layer for the API.

**How could the savings claim be proven?**
Take a set of real documents, convert them, and compare token counts using the target model's own tokenizer against the raw text extraction and against the image input, reporting the spread rather than a single number.

**What are the security risks?**
Untrusted files are parsed: XML entity declarations are refused, upload size is capped, nothing is executed. The API and page have no authentication, so a public deployment needs a password or proxy in front (the free deployment page).

**What would be done differently from scratch?**
Collect real sample documents first and build the evaluation set before tuning rules, to avoid fitting the rules to the samples.
