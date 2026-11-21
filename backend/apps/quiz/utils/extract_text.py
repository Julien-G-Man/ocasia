"""File text extraction for quiz generation."""

import io
import logging
import os

import docx
import PyPDF2

try:
    import pdfplumber
except Exception:  # optional dependency
    pdfplumber = None

logger = logging.getLogger(__name__)


def extract_file_text(file) -> str:
    """Extract plain text from an uploaded file (PDF, DOCX, PPTX, TXT)."""
    file_ext = os.path.splitext((file.name or "").lower())[1]

    file.seek(0)
    file_content = file.read()

    if file_ext == ".pdf":
        pdf_file = io.BytesIO(file_content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = "".join(page.extract_text() or "" for page in pdf_reader.pages)

        # Fallback for math-heavy PDFs where PyPDF2 misses glyph streams.
        if not text.strip() and pdfplumber is not None:
            pdf_file.seek(0)
            with pdfplumber.open(pdf_file) as pdf:
                text = "\n".join((page.extract_text() or "") for page in pdf.pages)

    elif file_ext == ".docx":
        doc = docx.Document(io.BytesIO(file_content))
        text = "\n".join(para.text for para in doc.paragraphs)

    elif file_ext == ".pptx":
        from pptx import Presentation

        prs = Presentation(io.BytesIO(file_content))
        text = "\n".join(
            shape.text
            for slide in prs.slides
            for shape in slide.shapes
            if hasattr(shape, "text") and shape.text
        )

    elif file_ext == ".txt":
        text = file_content.decode("utf-8", errors="ignore")

    else:
        raise ValueError(f"Unsupported file format: {file_ext}")

    return text.strip()
