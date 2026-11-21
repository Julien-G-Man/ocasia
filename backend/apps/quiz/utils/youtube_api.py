"""
YouTube Transcript Utility for Quiz Generation

Extracts transcripts from YouTube videos using youtube-transcript-api.
Video title is fetched via the YouTube oEmbed endpoint (no API key needed).
"""

import re
import asyncio
import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

# Matches: youtube.com/watch?v=ID, youtu.be/ID, youtube.com/shorts/ID, youtube.com/embed/ID
_VIDEO_ID_RE = re.compile(
    r'(?:v=|youtu\.be/|/shorts/|/embed/)([a-zA-Z0-9_-]{11})'
)


def extract_video_id(url: str) -> Optional[str]:
    """Return the 11-char video ID from any standard YouTube URL, or None."""
    match = _VIDEO_ID_RE.search(url)
    return match.group(1) if match else None


def _fetch_transcript_sync(video_id: str) -> str:
    """
    Blocking call — run via asyncio.to_thread.
    Returns the full transcript as a single string.
    Raises ValueError with a user-facing message on failure.

    Compatible with both youtube-transcript-api < 0.6 and >= 0.6.
    In 0.6+, get_transcript() was removed; use YouTubeTranscriptApi().fetch().
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        logger.error("YouTube transcript dependency missing for video_id=%s", video_id)
        raise ValueError(
            "youtube-transcript-api is not installed. "
            "Add it to requirements.txt and redeploy."
        )

    logger.info("Fetching YouTube transcript video_id=%s", video_id)

    try:
        # --- API >= 0.6: instance-based fetch() ---
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id)
        # FetchedTranscript is iterable; each item has a .text attribute.
        return " ".join(
            seg.text if hasattr(seg, "text") else seg["text"]
            for seg in fetched
        ).strip()

    except AttributeError:
        # --- API < 0.6 fallback: classmethod get_transcript() ---
        try:
            segments = YouTubeTranscriptApi.get_transcript(video_id)  # type: ignore[attr-defined]
            return " ".join(seg["text"] for seg in segments).strip()
        except Exception as exc:
            logger.warning("YouTube transcript fetch failed video_id=%s reason=%s", video_id, exc)
            raise ValueError(f"Could not retrieve transcript: {exc}")

    except Exception as exc:
        msg = str(exc).lower()
        if "disabled" in msg or "could not retrieve" in msg:
            logger.warning("YouTube captions unavailable video_id=%s reason=%s", video_id, exc)
            raise ValueError(
                "Captions are disabled or unavailable for this video. "
                "Try a video with auto-generated or manual captions enabled."
            )
        logger.warning("YouTube transcript fetch failed video_id=%s reason=%s", video_id, exc)
        raise ValueError(f"Could not retrieve transcript: {exc}")


async def _fetch_video_title(video_id: str) -> str:
    """
    Fetch the video title via YouTube's oEmbed endpoint.
    Returns an empty string on any failure (title is optional metadata).
    """
    try:
        oembed_url = (
            f"https://www.youtube.com/oembed"
            f"?url=https://www.youtube.com/watch?v={video_id}&format=json"
        )
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(oembed_url)
            if resp.status_code == 200:
                return resp.json().get("title", "")
    except Exception:
        logger.debug("YouTube title lookup failed video_id=%s", video_id, exc_info=True)
    return ""


async def fetch_youtube_quiz_content(url: str) -> dict:
    """
    Main entry point for the quiz flow.

    Parses the video ID, fetches the transcript (in a thread) and the title
    (async) concurrently, then returns a dict ready for the quiz pipeline.

    Returns:
        {
            "text":     str,   # full transcript — goes to study_text
            "title":    str,   # video title — used as source_filename
            "video_id": str,
        }

    Raises:
        ValueError with a user-facing message on any expected failure.
    """
    video_id = extract_video_id(url)
    if not video_id:
        logger.info("YouTube URL missing video_id url=%s", url)
        raise ValueError(
            "Could not find a YouTube video ID in the URL. "
            "Accepted formats: youtube.com/watch?v=…, youtu.be/…, youtube.com/shorts/…"
        )

    # Run blocking transcript fetch and async title fetch concurrently.
    transcript_result, title_result = await asyncio.gather(
        asyncio.to_thread(_fetch_transcript_sync, video_id),
        _fetch_video_title(video_id),
        return_exceptions=True,
    )

    if isinstance(transcript_result, Exception):
        logger.warning("YouTube transcript extraction failed video_id=%s", video_id)
        raise ValueError(str(transcript_result))

    if isinstance(title_result, Exception):
        title_result = ""

    transcript: str = transcript_result
    title: str = title_result or f"YouTube ({video_id})"

    if len(transcript) < 50:
        logger.warning("YouTube transcript too short video_id=%s chars=%d", video_id, len(transcript))
        raise ValueError(
            "The transcript for this video is too short to generate a useful quiz."
        )

    logger.info("YouTube transcript fetched video_id=%s title=%r chars=%d", video_id, title, len(transcript))

    return {
        "text": transcript,
        "title": title,
        "video_id": video_id,
    }
