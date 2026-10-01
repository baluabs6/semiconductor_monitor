package com.semimonitor.ai.security;

import com.semimonitor.ai.model.AlertDto;

import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Masks sensitive data with ****. Mirrors backend/core/redact.py.
 *
 * Applied to: alerts fetched from the Python backend, the user's chat question before it is sent to
 * the LLM, the LLM's chat answer, and error details returned to callers.
 *
 * Pattern-based masking is a safety net, not a guarantee.
 */
public final class Redactor {

    public static final String MASK = "****";
    /** Alerts are short; bounding input bounds regex work (DoS guard). */
    public static final int MAX_INPUT_CHARS = 50_000;

    private static final String OCTET = "(?:25[0-5]|2[0-4]\\d|1?\\d?\\d)";

    private static final Pattern PRIVATE_KEY =
            Pattern.compile("-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", Pattern.DOTALL);
    private static final Pattern JWT =
            Pattern.compile("\\beyJ[A-Za-z0-9_-]{8,}\\.[A-Za-z0-9_-]{8,}\\.[A-Za-z0-9_-]{8,}");
    private static final Pattern URL_CREDS =
            Pattern.compile("(?<=://)[^\\s/@:]+:[^\\s/@]+(?=@)");
    private static final Pattern BEARER =
            Pattern.compile("\\bBearer\\s+[A-Za-z0-9\\-._~+/]+=*", Pattern.CASE_INSENSITIVE);
    private static final Pattern KEY_VALUE = Pattern.compile(
            "\\b(api[_-]?key|apikey|secret(?:[_-]?key)?|token|password|passwd|pwd|"
                    + "authorization|access[_-]?key|private[_-]?key|client[_-]?secret)\\b"
                    + "(\\s*[:=]\\s*)(?:\"[^\"]*\"|'[^']*'|(?:Bearer\\s+)?[^\\s,;\"']+)",
            Pattern.CASE_INSENSITIVE);
    private static final Pattern SK_KEY = Pattern.compile("\\bsk-[A-Za-z0-9_\\-]{16,}");
    private static final Pattern AWS_KEY = Pattern.compile("\\b(?:AKIA|ASIA)[0-9A-Z]{16}\\b");
    private static final Pattern EMAIL =
            Pattern.compile("(?<![A-Za-z0-9._%+\\-])[A-Za-z0-9._%+\\-]+@[A-Za-z0-9\\-]+(?:\\.[A-Za-z0-9\\-]+)+");
    private static final Pattern IPV4 = Pattern.compile("\\b" + OCTET + "(?:\\." + OCTET + "){3}\\b");

    private Redactor() { }

    public static String redact(String text) {
        if (text == null || text.isEmpty()) return text;
        if (text.length() > MAX_INPUT_CHARS) text = text.substring(0, MAX_INPUT_CHARS) + "...[truncated]";
        text = PRIVATE_KEY.matcher(text).replaceAll(MASK);
        text = JWT.matcher(text).replaceAll(MASK);
        text = URL_CREDS.matcher(text).replaceAll(MASK);
        text = BEARER.matcher(text).replaceAll("Bearer " + MASK);
        text = KEY_VALUE.matcher(text).replaceAll(m -> Matcher.quoteReplacement(m.group(1) + m.group(2) + MASK));
        text = SK_KEY.matcher(text).replaceAll(MASK);
        text = AWS_KEY.matcher(text).replaceAll(MASK);
        text = EMAIL.matcher(text).replaceAll(MASK);
        text = IPV4.matcher(text).replaceAll(MASK);
        return text;
    }

    public static AlertDto redact(AlertDto a) {
        return new AlertDto(a.id(), a.timestamp(), a.source(), a.severity(), redact(a.message()));
    }

    public static List<AlertDto> redact(List<AlertDto> alerts) {
        return alerts == null ? null : alerts.stream().map(a -> redact(a)).toList();
    }
}
