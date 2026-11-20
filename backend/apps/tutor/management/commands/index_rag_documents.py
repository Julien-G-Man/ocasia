from pathlib import Path
from urllib.parse import urlparse

import requests
from django.core.management.base import BaseCommand, CommandError

from apps.tutor.rag_indexing import (
    SUPPORTED_EXTENSIONS,
    build_embeddings,
    index_document_bytes,
    source_key_for_path,
)


class Command(BaseCommand):
    help = "Index PDF/PPTX/Markdown/text sources into Django's pgvector tutor corpus."

    def add_arguments(self, parser):
        parser.add_argument("paths", nargs="*", help="Files or directories to recursively index.")
        parser.add_argument("--materials", action="store_true", help="Also index active public Material records.")
        parser.add_argument("--force", action="store_true", help="Re-index files even when their content hash is unchanged.")

    def handle(self, *args, **options):
        paths = options["paths"]
        if not paths and not options["materials"]:
            raise CommandError("Provide one or more paths, --materials, or both.")

        embeddings = build_embeddings()
        indexed = skipped = failed = 0

        for raw_path in paths:
            path = Path(raw_path).expanduser().resolve()
            if not path.exists():
                self.stderr.write(self.style.ERROR(f"Missing path: {path}"))
                failed += 1
                continue
            files = [path] if path.is_file() else sorted(
                item for item in path.rglob("*")
                if item.is_file() and item.suffix.casefold() in SUPPORTED_EXTENSIONS
            )
            for file_path in files:
                if file_path.suffix.casefold() not in SUPPORTED_EXTENSIONS:
                    self.stderr.write(f"Skipping unsupported file: {file_path.name}")
                    skipped += 1
                    continue
                try:
                    changed, chunk_count = index_document_bytes(
                        source_key=source_key_for_path(file_path),
                        source_name=file_path.name,
                        filename=file_path.name,
                        file_bytes=file_path.read_bytes(),
                        embeddings=embeddings,
                        source_metadata={"source_type": "file"},
                        force=options["force"],
                    )
                    if changed:
                        indexed += 1
                        self.stdout.write(self.style.SUCCESS(f"Indexed {file_path.name}: {chunk_count} chunks"))
                    else:
                        skipped += 1
                        self.stdout.write(f"Unchanged, already indexed: {file_path.name}")
                except Exception as exc:
                    failed += 1
                    self.stderr.write(self.style.ERROR(f"Failed to index {file_path}: {exc}"))

        if options["materials"]:
            from apps.materials.models import Material

            for material in Material.objects.filter(is_active=True).iterator():
                filename = material.original_filename or Path(urlparse(material.file_url).path).name or material.title
                if not Path(filename).suffix:
                    file_type = (material.file_type or "").lower()
                    filename += ".pptx" if "presentation" in file_type or "powerpoint" in file_type else ".pdf"
                if Path(filename).suffix.casefold() not in SUPPORTED_EXTENSIONS:
                    skipped += 1
                    continue
                try:
                    response = requests.get(material.file_url, timeout=60)
                    response.raise_for_status()
                    changed, chunk_count = index_document_bytes(
                        source_key=f"material:{material.pk}",
                        source_name=material.title or filename,
                        filename=filename,
                        file_bytes=response.content,
                        embeddings=embeddings,
                        source_metadata={
                            "source_type": "public_material",
                            "material_id": material.pk,
                            "subject": material.subject,
                            "title": material.title,
                        },
                        force=options["force"],
                    )
                    if changed:
                        indexed += 1
                        self.stdout.write(self.style.SUCCESS(f"Indexed material {material.pk}: {chunk_count} chunks"))
                    else:
                        skipped += 1
                except Exception as exc:
                    failed += 1
                    self.stderr.write(self.style.ERROR(f"Failed to index material {material.pk}: {exc}"))

        self.stdout.write(f"Finished: {indexed} indexed, {skipped} skipped, {failed} failed.")
        if failed:
            raise CommandError(f"{failed} source(s) failed to index.")
