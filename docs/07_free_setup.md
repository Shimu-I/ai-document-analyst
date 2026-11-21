# 07 - Running the project for free

Nothing in this project needs a paid service.

| Option | Cost | Needs internet | Text leaves the computer? |
|---|---|---|---|
| Conversion (all file types) and the built-in summary | $0 | no | no |
| AI summary with a local model (Ollama) | $0 (own CPU/GPU) | only to download the model | no |
| AI summary with a hosted provider's free tier | $0 within the provider's limits | yes | **yes** |

The AI summary is only needed for a rewritten summary and key points. The converter and the built-in extractive summary work without it.
Free hosting of the web page itself is covered in [chapter 09](09_deployment_free.md).

## 1. Local model with Ollama

1. Install Ollama from <https://ollama.com> and start it (it listens on `localhost:11434`).
2. `ollama pull <model>`: any instruction-tuned model. Smaller models run on a normal laptop but are less accurate and slow on a CPU. `ollama list` shows the exact name.
3. Set the model name and run:

```bash
export LLM_MODEL=<name from ollama list>
streamlit run app/streamlit_app.py        # tick "Use an AI model for the summary"
python -m src.cli paper.pdf --summary --llm
```

`LLM_BASE_URL` defaults to `http://localhost:11434/v1`. `LLM_TIMEOUT` (default 300 seconds) controls how long to wait on slow CPUs.

## 2. Hosted free tier (any OpenAI-compatible service)

```bash
export LLM_BASE_URL=<the provider's OpenAI-compatible base URL>
export LLM_MODEL=<a model that provider offers>
export LLM_API_KEY=<the provider's key>
```

Free-tier limits and model names change; the provider's documentation is the source of truth (not verified here). The document text is sent to that provider, so this is unsuitable for confidential files.

## 3. Safety net

An AI summary is accepted only if every number of three or more characters in it appears in the document. Otherwise the built-in extractive summary is kept and a warning says so.

## 4. Status

The AI-summary code path is tested with stub servers. It has **not** been run against a real model in the environment where the project was built.

## 5. OCR languages (images and scanned PDFs)

English is installed with `tesseract-ocr`. Other languages need a language pack, then a name on the command:

```bash
sudo apt install tesseract-ocr-ben          # Bangla; list installed: tesseract --list-langs
python -m src.cli screenshot.png --lang eng+ben
```

If a pack is missing, the tool stops with a message naming the package to install. Package names follow the pattern `tesseract-ocr-<code>`.

## 6. Other operating systems (untested)

| System | Python and Tesseract | Notes |
|---|---|---|
| macOS | `brew install python tesseract` | Language packs: `brew install tesseract-lang` |
| Windows | Python from python.org; a Tesseract build installed separately and added to `PATH` | Virtual environment activation: `.venv\Scripts\activate` |

Only Linux was used to build and test the project. Corrections from other systems are welcome as issues.

## 7. Optional: LibreOffice for old Office files

`sudo apt install libreoffice-writer libreoffice-calc libreoffice-impress` enables `.doc`, `.xls`, `.ppt`, `.odt`, `.ods`, `.odp` and `.rtf`. Without it, the tool answers with a clear error asking for a modern format.
