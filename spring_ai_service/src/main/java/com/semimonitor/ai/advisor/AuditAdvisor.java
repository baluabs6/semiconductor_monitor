package com.semimonitor.ai.advisor;

import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.client.ChatClientRequest;
import org.springframework.ai.chat.client.ChatClientResponse;
import org.springframework.ai.chat.client.advisor.api.AdvisorChain;
import org.springframework.ai.chat.client.advisor.api.BaseAdvisor;
import org.springframework.ai.chat.memory.ChatMemory;
import org.springframework.ai.chat.metadata.ChatResponseMetadata;
import org.springframework.ai.chat.metadata.Usage;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.document.Document;
import org.springframework.ai.rag.advisor.RetrievalAugmentationAdvisor;
import org.springframework.core.Ordered;

import java.time.Duration;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/**
 * Outermost advisor: writes one audit log line per model call and publishes Micrometer metrics.
 * It logs METADATA ONLY (conversation id, model, token counts, latency, whether input was redacted,
 * which runbooks were retrieved). It never logs prompt or answer text, so the audit trail cannot
 * become a new place for secrets to leak.
 *
 * Metrics (see /actuator/prometheus): monitor_ai_calls_total, monitor_ai_tokens_total{type},
 * monitor_ai_latency_seconds.
 */
public class AuditAdvisor implements BaseAdvisor {

    private static final Logger audit = LoggerFactory.getLogger("monitor.ai.audit");
    private static final String START = "monitor.audit.startNanos";

    private final MeterRegistry meters;

    public AuditAdvisor(MeterRegistry meters) {
        this.meters = meters;
    }

    @Override
    public ChatClientRequest before(ChatClientRequest request, AdvisorChain chain) {
        return request.mutate().context(START, System.nanoTime()).build();
    }

    @Override
    public ChatClientResponse after(ChatClientResponse response, AdvisorChain chain) {
        Object start = response.context().get(START);
        long ms = start instanceof Long s ? Duration.ofNanos(System.nanoTime() - s).toMillis() : -1;

        ChatResponse cr = response.chatResponse();
        ChatResponseMetadata md = cr == null ? null : cr.getMetadata();
        Usage usage = md == null ? null : md.getUsage();
        Integer in = usage == null ? null : usage.getPromptTokens();
        Integer out = usage == null ? null : usage.getCompletionTokens();

        meters.counter("monitor.ai.calls").increment();
        if (in != null) meters.counter("monitor.ai.tokens", "type", "prompt").increment(in);
        if (out != null) meters.counter("monitor.ai.tokens", "type", "completion").increment(out);
        if (ms >= 0) Timer.builder("monitor.ai.latency").register(meters).record(Duration.ofMillis(ms));

        audit.info("ai_call conversation={} model={} promptTokens={} completionTokens={} latencyMs={} inputRedacted={} runbooks={}",
                response.context().getOrDefault(ChatMemory.CONVERSATION_ID, "-"),
                md == null ? "-" : md.getModel(), in, out, ms,
                response.context().containsKey(RedactionAdvisor.CONTEXT_REDACTED),
                runbooks(response));
        return response;
    }

    @SuppressWarnings("unchecked")
    private static Set<String> runbooks(ChatClientResponse response) {
        Object docs = response.context().get(RetrievalAugmentationAdvisor.DOCUMENT_CONTEXT);
        Set<String> names = new LinkedHashSet<>();
        if (docs instanceof List<?> list) {
            for (Object o : (List<Object>) list) {
                if (o instanceof Document d && d.getMetadata().get("source") != null) {
                    names.add(String.valueOf(d.getMetadata().get("source")));
                }
            }
        }
        return names;
    }

    /** Outermost, so latency covers every other advisor and the model call. */
    @Override
    public int getOrder() {
        return Ordered.HIGHEST_PRECEDENCE + 10;
    }
}
