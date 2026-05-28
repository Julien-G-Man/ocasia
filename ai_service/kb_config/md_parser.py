"""
Hybrid KB loader: JSON index (chunk IDs + keywords) + .md files (content).

kb_index.json  -- chunk_id -> {heading, source_file, keywords}
*.md files     -- sections delimited by ## headings, matched by heading text
"""
import json
import re
from pathlib import Path


def load_kb_dir(kb_dir: Path) -> dict[str, dict]:
    index_path = kb_dir / "kb_index.json"
    if not index_path.exists():
        return {}

    index: dict[str, dict] = json.loads(index_path.read_text(encoding="utf-8"))

    # Parse all .md files into {filename: {heading: text}}
    md_content: dict[str, dict[str, str]] = {}
    for md_file in kb_dir.glob("*.md"):
        md_content[md_file.name] = _parse_md(md_file)

    chunks: dict[str, dict] = {}
    for chunk_id, meta in index.items():
        if not isinstance(meta, dict):
            continue
        source_file = meta.get("source_file", "")
        heading = meta.get("heading", "")
        text = md_content.get(source_file, {}).get(heading, "")
        if not text:
            continue
        chunks[chunk_id] = {
            "heading": heading,
            "source_file": source_file,
            "keywords": meta.get("keywords", []),
            "text": text,
        }
    return chunks


def _parse_md(md_file: Path) -> dict[str, str]:
    raw = md_file.read_text(encoding="utf-8")
    sections = re.split(r"(?m)^## ", raw)
    result: dict[str, str] = {}
    for section in sections:
        if not section.strip():
            continue
        nl = section.find("\n")
        if nl == -1:
            continue
        heading = section[:nl].strip()
        text = section[nl + 1:].strip()
        if heading and text:
            result[heading] = text
    return result
