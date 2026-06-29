"""
Telegram message splitting utility.
Telegram has a 4096 character limit per message — this module handles splitting long responses.
"""

from typing import List

TELEGRAM_MAX_LENGTH = 4096


def split_message(text: str, max_length: int = TELEGRAM_MAX_LENGTH) -> List[str]:
    """
    Split a long text into multiple chunks suitable for Telegram messages.

    Tries to split at paragraph boundaries first, then sentence boundaries,
    then word boundaries, to avoid cutting mid-word or mid-sentence.

    Args:
        text: The full text to split.
        max_length: Maximum characters per chunk (default: 4096).

    Returns:
        List of text chunks, each within the max_length limit.
    """
    if len(text) <= max_length:
        return [text]

    chunks: List[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break

        # Try to find a good split point
        split_at = max_length

        # 1. Try splitting at double newline (paragraph boundary)
        para_break = remaining.rfind("\n\n", 0, max_length)
        if para_break > max_length // 2:
            split_at = para_break + 2  # Include the double newline

        # 2. Try splitting at single newline
        elif (line_break := remaining.rfind("\n", 0, max_length)) > max_length // 2:
            split_at = line_break + 1

        # 3. Try splitting at sentence boundary (. ! ?)
        elif (sentence_break := remaining.rfind(". ", 0, max_length)) > max_length // 2:
            split_at = sentence_break + 2

        # 4. Try splitting at space (word boundary)
        elif (word_break := remaining.rfind(" ", 0, max_length)) > max_length // 2:
            split_at = word_break + 1

        # 5. Hard split at max_length (last resort)
        else:
            split_at = max_length

        chunk = remaining[:split_at].rstrip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_at:].lstrip()

    return chunks
