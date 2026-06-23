from __future__ import annotations

import base64
from pathlib import PurePath

import fitz

MAX_RESUME_BYTES = 8 * 1024 * 1024


def extract_resume_text(filename: str, content_base64: str) -> dict:
    clean_filename = PurePath(filename or "resume").name
    extension = clean_filename.lower().rsplit(".", 1)[-1] if "." in clean_filename else ""
    raw_bytes = decode_resume_bytes(content_base64)

    if extension == "pdf":
        text = extract_pdf_text(raw_bytes)
        if text:
            return parsed_response(clean_filename, text, "PDF text extracted.")

        return {
            "filename": clean_filename,
            "status": "no_text",
            "text": "",
            "text_character_count": 0,
            "detail": "PDF was uploaded, but no selectable text was found. Scanned PDFs need OCR, which is not enabled yet.",
        }

    if extension in {"txt", "md"}:
        text = decode_text_file(raw_bytes)
        return parsed_response(clean_filename, text, "Text resume extracted.")

    return {
        "filename": clean_filename,
        "status": "unsupported",
        "text": "",
        "text_character_count": 0,
        "detail": "This file type is attached but not parsed yet. Upload PDF, TXT, or MD, or paste resume text.",
    }


def decode_resume_bytes(content_base64: str) -> bytes:
    try:
        raw_bytes = base64.b64decode(content_base64, validate=True)
    except ValueError as error:
        raise ValueError("Resume upload is not valid base64.") from error

    if len(raw_bytes) > MAX_RESUME_BYTES:
        raise ValueError("Resume upload is too large. Keep files under 8MB.")

    return raw_bytes


def extract_pdf_text(raw_bytes: bytes) -> str:
    page_text = []

    with fitz.open(stream=raw_bytes, filetype="pdf") as document:
        for page in document:
            text = page.get_text("text") or ""
            if text.strip():
                page_text.append(text)

    return clean_text("\n".join(page_text))


def decode_text_file(raw_bytes: bytes) -> str:
    for encoding in ["utf-8", "utf-16", "latin-1"]:
        try:
            return clean_text(raw_bytes.decode(encoding))
        except UnicodeDecodeError:
            continue
    return ""


def parsed_response(filename: str, text: str, detail: str) -> dict:
    return {
        "filename": filename,
        "status": "parsed" if text else "empty",
        "text": text,
        "text_character_count": len(text),
        "detail": detail if text else "File was uploaded, but no readable text was extracted.",
    }


def clean_text(value: str) -> str:
    return "\n".join(line.strip() for line in value.replace("\r", "\n").split("\n") if line.strip())
