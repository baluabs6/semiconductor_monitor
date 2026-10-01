package com.semimonitor.ai.security;

/**
 * Makes untrusted text (alert messages, firmware log lines) safe to place inside an LLM prompt.
 * Mirrors backend/core/promptsafety.py; both are tested against shared/promptsafety_cases.json.
 *
 *  - control / format (zero-width, bidi) / surrogate / private-use characters are removed
 *  - newlines and runs of whitespace collapse to one space, so a log line cannot forge extra
 *    alert entries or start a new paragraph of instructions
 *  - '<' and '>' are escaped, so text cannot close the <alerts> block and escape into the instructions
 *  - length is bounded
 *
 * This reduces prompt-injection risk; it cannot remove it. Keep tools read-only.
 */
public final class PromptSafety {

    public static final int MAX_FIELD_CHARS = 500;

    private PromptSafety() { }

    public static String sanitize(String text) {
        return sanitize(text, MAX_FIELD_CHARS);
    }

    public static String sanitize(String text, int maxChars) {
        if (text == null) return "";
        StringBuilder sb = new StringBuilder(text.length());
        boolean pendingSpace = false;
        for (int i = 0; i < text.length(); ) {
            int cp = text.codePointAt(i);
            i += Character.charCount(cp);
            if (Character.isWhitespace(cp) || Character.isSpaceChar(cp) || cp == 0x85) {
                pendingSpace = true;
                continue;
            }
            int type = Character.getType(cp);
            if (type == Character.CONTROL || type == Character.FORMAT
                    || type == Character.SURROGATE || type == Character.PRIVATE_USE) {
                continue;
            }
            if (pendingSpace && sb.length() > 0) sb.append(' ');
            pendingSpace = false;
            if (cp == '<') sb.append("&lt;");
            else if (cp == '>') sb.append("&gt;");
            else sb.appendCodePoint(cp);
        }
        String out = sb.toString();
        return out.length() > maxChars ? out.substring(0, maxChars) + "...[truncated]" : out;
    }
}
