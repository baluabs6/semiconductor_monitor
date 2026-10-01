"""
promptsafety.py - makes untrusted text (alert messages, firmware log lines) safe to place inside an LLM prompt.

Alert text can originate from device logs, so it is attacker-influenced. Before it goes into a prompt:
  * invisible / control characters are removed (zero-width and bidi tricks, NUL, ...)
  * newlines and runs of whitespace collapse to one space, so a log line cannot forge extra
    "- [timestamp] SOURCE/SEVERITY: ..." entries or start a new paragraph of instructions
  * '<' and '>' are escaped, so the text cannot close our <alerts> block and escape into the instructions
  * length is bounded

This reduces prompt-injection risk; it cannot remove it (the model still reads the words). Keep tool
permissions read-only, and keep telling the model the text is data. Mirrored by PromptSafety.java.
"""

import unicodedata

MAX_FIELD_CHARS = 500


def sanitize_untrusted(text, max_chars: int = MAX_FIELD_CHARS) -> str:
    if text is None:
        return ""
    s = str(text)
    # drop control (Cc), format (Cf: zero-width, bidi), surrogate (Cs) and private-use (Co) characters,
    # but keep whitespace so it can be collapsed below
    cleaned = []
    for ch in s:
        if ch.isspace():
            cleaned.append(" ")
        elif unicodedata.category(ch) in ("Cc", "Cf", "Cs", "Co"):
            continue
        else:
            cleaned.append(ch)
    s = " ".join("".join(cleaned).split())
    s = s.replace("<", "&lt;").replace(">", "&gt;")
    if len(s) > max_chars:
        s = s[:max_chars] + "...[truncated]"
    return s
