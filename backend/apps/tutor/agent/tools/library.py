"""Agent tool for browsing the community materials library."""

import logging

from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


def _query_materials(query: str, subject: str, limit: int):
    """Query active materials in a worker thread (sync ORM)."""
    from django.db.models import Q

    from apps.materials.models import Material

    qs = Material.objects.filter(is_active=True).select_related("uploaded_by")
    if query:
        qs = qs.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(subject__icontains=query)
            | Q(original_filename__icontains=query)
        )
    if subject:
        qs = qs.filter(subject__iexact=subject)
    return list(qs.order_by("-created_at")[:limit])


async def list_library_materials(
    query: str = "", subject: str = "", limit: int = 10
) -> dict:
    """List community study materials with direct file links the student can open.

    Each material includes an absolute ``url`` (Cloudinary secure URL) so the
    tutor can present it as a markdown link that opens in a new tab. ``query``
    searches titles, descriptions, subjects, and filenames; ``subject`` filters
    by an exact subject value such as ``mathematics`` or ``computing``.
    """
    from apps.materials.helpers import SUBJECT_CHOICES

    query = (query or "").strip()
    subject = (subject or "").strip()
    try:
        limit = max(1, min(int(limit), 25))
    except (TypeError, ValueError):
        limit = 10

    try:
        rows = await sync_to_async(_query_materials)(query, subject, limit)
    except Exception as exc:
        logger.exception("Tutor library listing failed")
        return {"materials": [], "error": str(exc)}

    labels = {item["value"]: item["label"] for item in SUBJECT_CHOICES}
    materials = [
        {
            "id": row.id,
            "title": row.title,
            "subject": labels.get(row.subject, row.subject),
            "filename": row.original_filename,
            "url": row.file_url,
            "size": row.file_size_display,
            "uploader": row.uploaded_by.username if row.uploaded_by else "Anonymous",
        }
        for row in rows
    ]
    return {
        "materials": materials,
        "count": len(materials),
        "message": "" if materials else "No materials matched the request.",
    }