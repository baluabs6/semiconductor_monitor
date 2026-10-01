package com.semimonitor.ai.rag;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * monitor.rag.*  Retrieval over runbooks.
 *
 * @param enabled        turn runbook retrieval on/off
 * @param runbooksDir    directory of *.md runbooks; if blank, the bundled SAMPLE runbooks are used
 * @param topK           max excerpts added to a prompt
 * @param minScore       BM25 score below which an excerpt is ignored
 * @param relativeCutoff drop excerpts scoring below this fraction of the best excerpt
 */
@ConfigurationProperties(prefix = "monitor.rag")
public record RagProperties(Boolean enabled, String runbooksDir, Integer topK, Double minScore, Double relativeCutoff) {

    public RagProperties {
        if (enabled == null) enabled = true;
        if (topK == null || topK < 1) topK = 3;
        if (minScore == null) minScore = 2.0;
        if (relativeCutoff == null) relativeCutoff = 0.5;
    }
}
