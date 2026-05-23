"""
MCP Tool: extract_youtube_transcript

Fetches the full transcript and title from a YouTube URL.
This is a deterministic tool (no LLM involved). It is safe to
expose to the AI as it cannot modify any state.

Logic is identical to apps/quiz/youtube_api.py -- kept here so the
FastAPI MCP layer can call it in-process without an HTTP round-trip
back to Django.
"""

import asyncio
import logging
import re
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_VIDEO_ID_RE = re.compile(
    r"(?:v=|youtu\.be/|/shorts/|/embed/)([a-zA-Z0-9_-]{11})"
)


def _extract_video_id(url: str) -> Optional[str]:
    match = _VIDEO_ID_RE.search(url)
    return match.group(1) if match else None


def _fetch_transcript_sync(video_id: str) -> str:
    """Blocking call -- always run via asyncio.to_thread."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        logger.error("youtube-transcript-api not installed. video_id=%s", video_id)
        raise ValueError(
            "youtube-transcript-api is not installed. "
            "Add it to requirements.txt and redeploy."
        )

    logger.info("[mcp:youtube] fetching transcript video_id=%s", video_id)

    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id)
        return " ".join(
            seg.text if hasattr(seg, "text") else seg["text"]
            for seg in fetched
        ).strip()

    except AttributeError:
        # API < 0.6 fallback
        try:
            segments = YouTubeTranscriptApi.get_transcript(video_id)  # type: ignore[attr-defined]
            return " ".join(seg["text"] for seg in segments).strip()
        except Exception as exc:
            raise ValueError(f"Could not retrieve transcript: {exc}")

    except Exception as exc:
        msg = str(exc).lower()
        if "disabled" in msg or "could not retrieve" in msg:
            raise ValueError(
                "Captions are disabled or unavailable for this video. "
                "Try a video with auto-generated or manual captions enabled."
            )
        raise ValueError(f"Could not retrieve transcript: {exc}")


async def _fetch_video_title(video_id: str) -> str:
    try:
        url = (
            f"https://www.youtube.com/oembed"
            f"?url=https://www.youtube.com/watch?v={video_id}&format=json"
        )
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.json().get("title", "")
    except Exception:
        logger.debug("[mcp:youtube] title lookup failed video_id=%s", video_id, exc_info=True)
    return ""


async def extract_youtube_transcript(url: str) -> dict:
    """
    MCP tool handler. Returns:
        {"text": str, "title": str, "video_id": str}
    Raises ValueError with a user-facing message on any expected failure.
    """
    video_id = _extract_video_id(url)
    if not video_id:
        raise ValueError(
            "Could not find a YouTube video ID in the URL. "
            "Accepted formats: youtube.com/watch?v=…, youtu.be/…, youtube.com/shorts/…"
        )

    transcript_result, title_result = await asyncio.gather(
        asyncio.to_thread(_fetch_transcript_sync, video_id),
        _fetch_video_title(video_id),
        return_exceptions=True,
    )

    if isinstance(transcript_result, Exception):
        logger.warning("[mcp:youtube] extraction failed video_id=%s err=%s", video_id, transcript_result)
        raise ValueError(str(transcript_result))

    if isinstance(title_result, Exception):
        title_result = ""

    transcript: str = transcript_result
    title: str = title_result or f"YouTube ({video_id})"

    if len(transcript) < 50:
        raise ValueError("The transcript for this video is too short to be useful.")

    logger.info(
        "[mcp:youtube] done video_id=%s title=%r chars=%d",
        video_id, title, len(transcript),
    )
    return {"text": transcript, "title": title, "video_id": video_id}
