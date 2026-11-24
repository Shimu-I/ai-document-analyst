"""FastAPI service.   uvicorn api.main:app --reload   ->   http://localhost:8000/docs

GET  /health            status, supported file types
POST /analyze           file -> what it is, summary, outline, stats   (no Markdown body)
POST /convert           file -> everything above + the Markdown text (JSON)
POST /convert/download  file -> the .md file itself (Content-Disposition: attachment); a .zip when max_tokens
                        splits it into several parts

Options (form fields, all optional): compact, json_mode (readable|minified), ocr_lang (e.g. eng+ben),
max_tokens (split into parts of about this many tokens), picture_ocr (read text inside pictures), images (save figures and equations; the download
becomes a .zip with an assets/ folder), page_markers, keep_headers, force_ocr, use_llm.

No authentication or rate limiting: do not expose publicly as is.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI, File, Form, HTTPException, UploadFile  # noqa: E402
from fastapi.responses import Response  # noqa: E402

from src import service  # noqa: E402

app = FastAPI(title="AI Document Analyst", version="2.0.0",
              description="Convert documents, images, spreadsheets and data files to compact Markdown, with a summary.")


async def _run(file: UploadFile, page_markers: bool, keep_headers: bool, force_ocr: bool, use_llm: bool | None,
               compact: bool = False, json_mode: str = "readable", ocr_lang: str | None = None,
               max_tokens: int | None = None, images: bool = False, picture_ocr: bool = False):
    data = await file.read()
    try:
        return service.process(data, file.filename or "", page_markers=page_markers,
                               strip_repeated=not keep_headers, force_ocr=force_ocr, use_llm=use_llm,
                               compact=compact, json_mode=json_mode, ocr_lang=ocr_lang, max_tokens=max_tokens, assets=images, ocr_pictures=picture_ocr)
    except service.ServiceError as e:
        raise HTTPException(status_code=e.status, detail=e.message) from e


@app.get("/health")
def health():
    return service.health()


@app.post("/analyze")
async def analyze(file: UploadFile = File(...), page_markers: bool = Form(False), keep_headers: bool = Form(False),
                  force_ocr: bool = Form(False), use_llm: bool | None = Form(None), compact: bool = Form(False),
                  json_mode: str = Form("readable"), ocr_lang: str | None = Form(None),
                  max_tokens: int | None = Form(None), images: bool = Form(False),
                  picture_ocr: bool = Form(False)):
    r = await _run(file, page_markers, keep_headers, force_ocr, use_llm, compact, json_mode, ocr_lang, max_tokens, images, picture_ocr)
    r.pop("markdown")
    return service.public(r)


@app.post("/convert")
async def convert(file: UploadFile = File(...), page_markers: bool = Form(False), keep_headers: bool = Form(False),
                  force_ocr: bool = Form(False), use_llm: bool | None = Form(None), compact: bool = Form(False),
                  json_mode: str = Form("readable"), ocr_lang: str | None = Form(None),
                  max_tokens: int | None = Form(None), images: bool = Form(False),
                  picture_ocr: bool = Form(False)):
    r = await _run(file, page_markers, keep_headers, force_ocr, use_llm, compact, json_mode, ocr_lang, max_tokens, images, picture_ocr)
    r["parts"] = [{"filename": n, "markdown": t} for n, t in service.output_files(r)]
    return service.public(r)


@app.post("/convert/download")
async def convert_download(file: UploadFile = File(...), include_summary: bool = Form(False),
                           page_markers: bool = Form(False), keep_headers: bool = Form(False),
                           force_ocr: bool = Form(False), use_llm: bool | None = Form(None),
                           compact: bool = Form(False), json_mode: str = Form("readable"),
                           ocr_lang: str | None = Form(None), max_tokens: int | None = Form(None),
                           images: bool = Form(False), picture_ocr: bool = Form(False)):
    r = await _run(file, page_markers, keep_headers, force_ocr, use_llm, compact, json_mode, ocr_lang, max_tokens, images, picture_ocr)
    files = service.output_files(r, include_summary)
    if len(files) > 1 or r["_assets"]:
        zname = r["markdown_filename"].rsplit(".", 1)[0] + ("_parts.zip" if len(files) > 1 else ".zip")
        return Response(service.zip_results([r], include_summary), media_type="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="{zname}"'})
    return Response(files[0][1], media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{files[0][0]}"'})
