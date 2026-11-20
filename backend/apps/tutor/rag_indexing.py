"""Offline indexing utilities for the tutor's pgvector document corpus."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

from django.conf import settings
from django.db import transaction
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from apps.tutor.models import TutorDocument, TutorDocumentChunk


SUPPORTED_EXTENSIONS = {".pdf", ".pptx", ".md", ".txt"}
EMBEDDING_MODEL = "text-embedding-3-small"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 120
EMBEDDING_BATCH_SIZE = 64
INDEX_VERSION = f"{EMBEDDING_MODEL}:recursive-{CHUNK_SIZE}-{CHUNK_OVERLAP}:v1"


def build_embeddings():
    from langchain_openai import OpenAIEmbeddings

    api_key = getattr(settings, "OPENAI_API_KEY", None)
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY must be configured to index tutor documents.")
    return OpenAIEmbeddings(api_key=api_key, model=EMBEDDING_MODEL)


def extract_documents(file_bytes: bytes, filename: str) -> list[Document]:
    extension = Path(filename).suffix.casefold()
    if extension == ".pdf":
        import PyPDF2

        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        documents = [
            Document(page_content=(page.extract_text() or ""), metadata={"page": page_number, "file_name": filename})
            for page_number, page in enumerate(reader.pages)
        ]
    elif extension == ".pptx":
        from pptx import Presentation

        presentation = Presentation(io.BytesIO(file_bytes))
        documents = []
        for slide_number, slide in enumerate(presentation.slides):
            blocks = []
            for shape in slide.shapes:
                if getattr(shape, "has_text_frame", False) and shape.text.strip():
                    blocks.append(shape.text.strip())
                if getattr(shape, "has_table", False):
                    blocks.extend(
                        " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                        for row in shape.table.rows
                    )
            text = "\n".join(block for block in blocks if block)
            if text.strip():
                documents.append(Document(
                    page_content=text,
                    metadata={"page": slide_number, "file_name": filename, "slide": slide_number + 1},
                ))
    elif extension in {".md", ".txt"}:
        text = file_bytes.decode("utf-8-sig", errors="replace")
        documents = [Document(page_content=text, metadata={"page": 0, "file_name": filename})]
    else:
        raise ValueError(f"Unsupported file type {extension!r}; supported types: PDF, PPTX, Markdown, and TXT.")

    documents = [document for document in documents if document.page_content.strip()]
    if not documents:
        raise ValueError(f"No readable text found in {filename}.")
    return documents


def _embed_chunks(chunks: list[Document], embeddings) -> list[list[float]]:
    vectors = []
    for offset in range(0, len(chunks), EMBEDDING_BATCH_SIZE):
        batch = chunks[offset:offset + EMBEDDING_BATCH_SIZE]
        vectors.extend(embeddings.embed_documents([chunk.page_content for chunk in batch]))
    return vectors


def index_document_bytes(
    *,
    source_key: str,
    source_name: str,
    filename: str,
    file_bytes: bytes,
    embeddings,
    source_metadata: dict | None = None,
    force: bool = False,
) -> tuple[bool, int]:
    """Idempotently index one supported source; returns (changed, chunk_count)."""
    extension = Path(filename).suffix.casefold()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type {extension!r}; supported types: PDF, PPTX, Markdown, and TXT.")
    digest = hashlib.sha256(file_bytes).hexdigest()
    existing = TutorDocument.objects.filter(source_key=source_key).first()
    if existing and existing.content_sha256 == digest and existing.index_version == INDEX_VERSION and not force:
        if existing.source_name != source_name or existing.metadata != (source_metadata or {}):
            existing.source_name = source_name
            existing.metadata = source_metadata or {}
            existing.save(update_fields=["source_name", "metadata"])
        return False, existing.chunks.count()

    source_documents = extract_documents(file_bytes, filename)
    splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", " ", ""],
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        add_start_index=True,
    )
    chunks = splitter.split_documents(source_documents)
    # Repeated boilerplate or duplicated pages can otherwise create identical
    # rows that crowd retrieval results for this source.
    unique_chunks = []
    seen_content = set()
    for chunk in chunks:
        normalized = " ".join(chunk.page_content.casefold().split())
        if normalized and normalized not in seen_content:
            seen_content.add(normalized)
            unique_chunks.append(chunk)
    chunks = unique_chunks
    if not chunks:
        raise ValueError(f"Splitting produced no chunks for {filename}.")
    vectors = _embed_chunks(chunks, embeddings)
    file_type = extension[1:]

    with transaction.atomic():
        document, _created = TutorDocument.objects.get_or_create(
            source_key=source_key,
            defaults={
                "source_name": source_name,
                "file_type": file_type,
                "content_sha256": digest,
                "index_version": INDEX_VERSION,
                "metadata": source_metadata or {},
            },
        )
        document.source_name = source_name
        document.file_type = file_type
        document.content_sha256 = digest
        document.index_version = INDEX_VERSION
        document.metadata = source_metadata or {}
        document.save()
        document.chunks.all().delete()
        TutorDocumentChunk.objects.bulk_create([
            TutorDocumentChunk(
                document=document,
                chunk_index=index,
                page_number=(int(chunk.metadata["page"]) + 1) if chunk.metadata.get("page") is not None else None,
                content=chunk.page_content,
                embedding=vector,
                metadata={
                    **chunk.metadata,
                    **(source_metadata or {}),
                },
            )
            for index, (chunk, vector) in enumerate(zip(chunks, vectors))
        ])

    return True, len(chunks)


def source_key_for_path(path: Path) -> str:
    canonical = str(path.resolve()).casefold()
    return "file:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
