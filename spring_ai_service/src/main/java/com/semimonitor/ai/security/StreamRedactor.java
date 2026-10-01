package com.semimonitor.ai.security;

import reactor.core.publisher.Flux;

import java.util.ArrayList;
import java.util.List;

/**
 * Masks secrets in a streamed LLM answer. Tokens arrive in arbitrary pieces, so a secret can be split
 * across chunks; redacting per chunk would miss it. This buffers until a newline and redacts whole
 * lines, so output is delivered line by line (slightly coarser than token streaming, but safe).
 */
public final class StreamRedactor {

    private StreamRedactor() { }

    public static Flux<String> redactLines(Flux<String> chunks) {
        return Flux.defer(() -> {
            StringBuilder buf = new StringBuilder();
            return chunks
                    .concatMapIterable(chunk -> {
                        buf.append(chunk);
                        List<String> lines = new ArrayList<>();
                        int nl;
                        while ((nl = buf.indexOf("\n")) >= 0) {
                            lines.add(Redactor.redact(buf.substring(0, nl + 1)));
                            buf.delete(0, nl + 1);
                        }
                        // Bound memory if the model emits a huge line with no newline.
                        if (buf.length() > Redactor.MAX_INPUT_CHARS) {
                            lines.add(Redactor.redact(buf.toString()));
                            buf.setLength(0);
                        }
                        return lines;
                    })
                    .concatWith(Flux.defer(() -> buf.length() == 0
                            ? Flux.<String>empty()
                            : Flux.just(Redactor.redact(buf.toString()))));
        });
    }
}
