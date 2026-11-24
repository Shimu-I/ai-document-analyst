# Testing every feature and reproducing the results

All commands run from the project folder with the virtual environment active (`source .venv/bin/activate`). Setup is in [user manual (deep dive)](user_manual.md#1-install-in-five-minutes).

## 1. Automated tests

```bash
python3 -m unittest discover -s tests -t .          # expect: Ran 131 tests ... OK (skipped=1)
python3 -m pytest -q                                # same tests; expect: 131 passed, 1 skipped
python3 -m unittest tests.test_formats_and_tokens   # only images, data formats, compact, split, tokens
python3 scripts/corner_cases.py                     # 49 awkward inputs; expect: 49 passed
```

- 131 tests. The skipped test is the API test module when FastAPI is not installed.
- Image tests need the `tesseract` program and skip themselves when it is missing.
- Coverage by file: `test_convert_pdf.py` (PDF layout, columns, headers, OCR), `test_convert_office.py` (DOCX/XLSX/PPTX/CSV), `test_formats_and_tokens.py` (images, structured data, HTML, Google shortcuts, compact, splitting, token estimate, service, CLI), `test_analyze.py` (type detection, summaries), `test_llm_clients.py`, `test_service_cli.py`.
- `scripts/corner_cases.py` is described in [corner cases](corner_cases.md).

## 2. Try each feature by hand

Generate sample files (nothing is downloaded; the scripts draw or write them):

```bash
mkdir -p demo/in demo/out
python3 scripts/make_image_samples.py demo/in      # clean/dark/transparent/photo-like/small PNG, JPG, WEBP
python3 scripts/make_data_samples.py demo/in       # JSON, JSONL, YAML, TOML, XML, HTML, notebook, .py, .gsheet
python3 scripts/make_samples.py                    # PDF/DOCX/XLSX/PPTX in data/samples (already included)
```

| Feature | Command | What to check |
|---|---|---|
| Image OCR | `python3 -m src.cli demo/in/clean.png --stdout` | Text and list lines match the picture |
| Dark / transparent image | `... demo/in/dark.png --stdout`, `... transparent.png --stdout` | Text is read, not blank |
| Poor image | `... demo/in/photo.jpg --stdout` | A low-confidence warning with doubtful words |
| JSON to table | `... demo/in/users.json --stdout` | Records become one table; compare with `--json minified` |
| Compact | `... demo/in/users.json --compact --stdout` | No padding or `---` row; same cell values |
| Split | `python3 -m src.cli data/samples/paper_two_column.pdf --max-tokens 1500 -o demo/out` | `paper_two_column_part1.md`, `_part2.md`, ... each with "(part i of n)" |
| YAML/TOML/XML/HTML/notebook/code | Run on the matching file in `demo/in` | Readable output; the notebook drops image data |
| Google file | `... demo/in/sheet.gsheet` | Refused with "File > Download" instructions (exit code 1) |
| Document types | `python3 -m src.cli data/samples/budget.xlsx data/samples/deck.pptx --stdout` | Type label and summary |
| Web page | `streamlit run app/streamlit_app.py` | Upload, Convert, Download .md; sidebar options |
| API | `uvicorn api.main:app`, then `curl -F file=@demo/in/users.json -F compact=true localhost:8000/convert` | JSON with markdown, stats, parts |

## 3. Reproducing the fidelity numbers

```bash
pip install markitdown                              # optional, for the comparison column
python3 scripts/evaluate_fidelity.py                # prints the table, rewrites reports/fidelity.json
```

Ground truth is in `data/samples/expected/*.json`. The samples are small, generated documents that the converter was tuned against, so the scores show that the tool works on
these files, not on documents in general. With markitdown installed, the DOCX comparison is also available: word recall and reading order are 1.0 for both tools there, and heading
detection differs slightly: markitdown finds 5 of 6 and 7 of 8 headings on the two DOCX samples, this tool 6 of 6 and 8 of 8 (exact figures in `reports/fidelity.json`).

## 4. Reproducing the token numbers

The app prints an estimated token count for every result (ASCII characters / 4, other characters / 1.5). To repeat the JSON example:

```bash
python3 scripts/make_data_samples.py demo/in
python3 -m src.cli demo/in/users.json --stdout            # readable: about 822 tokens
python3 -m src.cli demo/in/users.json --compact --stdout  # compact:  about 716 tokens
python3 -m src.cli demo/in/users.json --json minified --stdout
```

The indented source file (40 records) is about 2,600 estimated tokens; minified JSON about 1,400. These are estimates, not a real tokenizer's counts. For exact counts, paste the output into the tokenizer of the model in use.

## 5. Regenerating the figures

```bash
pip install matplotlib                  # only for the two measured charts
python3 scripts/make_figures.py         # docs/assets/tokens_json.png and fidelity.png
```

The diagrams are described in [docs/assets/README.md](../assets/README.md).

## 6. Known issues found while testing

- Two inputs that would produce the same output name **within one run** (for example `report.csv` and `report.txt`) are written as `report.md` and `report_txt.md`; nothing is overwritten. A **later run** into the same output folder does overwrite earlier files, so one folder per run avoids surprises.
- Not run in the build sandbox: the Streamlit page, the FastAPI server and Docker. Their logic is covered through `src/service.py` and the unit tests.
- Windows and macOS were not tested.
