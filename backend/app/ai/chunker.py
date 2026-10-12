import re
from typing import Optional

CHUNK_SIZE_TOKENS = 800
CHUNK_OVERLAP_TOKENS = 100
SEPARATORS = ["\n\n", "\n", ". ", ", ", " "]


def _token_count(text: str) -> int:
    return len(text) // 4


def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    if not text.strip():
        return []
    chunks = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(start + chunk_size * 4, text_len)  # chars ~= tokens * 4
        if end < text_len:
            # Try to break at a separator
            for sep in SEPARATORS:
                last_sep = text.rfind(sep, start, end)
                if last_sep > start + (chunk_size * 2):  # don't break too early
                    end = last_sep + len(sep)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= text_len:
            break
        start = max(end - overlap * 4, start + 1)
        if start >= text_len:
            break
    return chunks


def chunk_document(text: str, source_type: str = "generic") -> list[dict]:
    if source_type in ("earnings_call", "earnings_call_transcript"):
        return _chunk_earnings_call(text)
    raw_chunks = _split_text(text, CHUNK_SIZE_TOKENS, CHUNK_OVERLAP_TOKENS)
    return [{"text": c, "is_management": None, "speaker": None} for c in raw_chunks]


def _chunk_earnings_call(transcript: str) -> list[dict]:
    speaker_pattern = re.compile(r"^([A-Z][a-zA-Z\s]+):\s*$", re.MULTILINE)
    turns = speaker_pattern.split(transcript)
    chunks: list[dict] = []

    if len(turns) < 2:
        return chunk_document(transcript, "generic")

    for i in range(1, len(turns), 2):
        speaker = turns[i].strip()
        content = turns[i + 1] if i + 1 < len(turns) else ""
        role = (
            "management"
            if any(
                t in speaker.lower()
                for t in ["ceo", "cfo", "president", "officer", "coo", "director", "chairman"]
            )
            else "analyst"
        )
        for sub_chunk in _split_text(content, CHUNK_SIZE_TOKENS, CHUNK_OVERLAP_TOKENS):
            chunks.append({
                "text": f"[{speaker} ({role})]: {sub_chunk}",
                "speaker": speaker,
                "is_management": role == "management",
            })

    return chunks
