"""Checks that can be done before a file is converted, and plain-language advice for errors."""
from __future__ import annotations

SLOW_MB = 15


def check_upload(name: str, size: int, max_mb: int, accepted: list[str] | set[str], picture_ocr: bool = False) -> tuple[str, str] | None:
    """None when the file is fine, else (level, message) with level "error" or "warning"."""
    ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if size == 0:
        return "error", f"{name} is empty (0 bytes). Check that the file was saved or copied completely."
    if size > max_mb * 1024 * 1024:
        return "error", (f"{name} is {size / 1048576:.0f} MB, above the {max_mb} MB limit. Split the file, or raise the limit "
                         "with the MAX_UPLOAD_MB environment variable before starting the app.")
    if ext not in set(accepted):
        return "error", f"{name} has an unsupported type ({ext or 'no extension'}). See the Guide for the supported formats."
    if size > SLOW_MB * 1048576 or (picture_ocr and ext in (".pptx", ".docx", ".pdf") and size > 8 * 1048576):
        return "warning", f"{name} is large ({size / 1048576:.0f} MB){' and pictures are read with OCR' if picture_ocr else ''}: it may take a minute or more."
    return None


def advice(status: int, message: str) -> str:
    """One sentence on what to do next, for a service error status."""
    m = message.lower()
    if "password" in m:
        return "Remove the password in the program that created the file, save a copy and upload that."
    if "tesseract" in m or "ocr language" in m:
        return "OCR needs the Tesseract program (and the language pack for the chosen language). See Troubleshooting in the documentation."
    if status == 413:
        return "Use a smaller file, or raise MAX_UPLOAD_MB."
    if status == 415:
        return "Convert the file to a supported format first (for Google files: download as .docx, .xlsx, .pptx or .pdf)."
    if status == 400:
        return "Check that the file is not empty."
    return "Open the file in its own program, save a new copy, and try again. If it still fails, the Troubleshooting document lists common causes."
