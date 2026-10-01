package com.semimonitor.ai.service;

import com.semimonitor.ai.model.AlertDto;
import com.semimonitor.ai.security.StreamRedactor;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Flux;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class AiInsightServiceTest {

    @Test
    void selectKeepsCriticalsAndBoundsPrompt() {
        List<AlertDto> all = new ArrayList<>();
        for (int i = 1; i <= 1000; i++) {
            all.add(new AlertDto(i, "2026-01-01T00:00:00", "FAB", i % 100 == 0 ? "CRITICAL" : "INFO", "m" + i));
        }
        AiInsightService.Selection sel = AiInsightService.select(all);
        assertEquals(AiInsightService.MAX_ALERTS_IN_PROMPT, sel.alerts().size());
        assertEquals(10, sel.alerts().stream().filter(a -> a.severity().equals("CRITICAL")).count());
        assertTrue(sel.coverage().contains("of 1000"));
        // chronological order restored
        for (int i = 1; i < sel.alerts().size(); i++) {
            assertTrue(sel.alerts().get(i).id() > sel.alerts().get(i - 1).id());
        }
    }

    @Test
    void sourceIsValidated() {
        assertEquals("FAB", AiInsightService.normalizeSource(" fab "));
        assertNull(AiInsightService.normalizeSource(""));
        assertThrows(IllegalArgumentException.class, () -> AiInsightService.normalizeSource("x&y=1"));
    }

    @Test
    void streamMasksSecretsSplitAcrossChunks() {
        Flux<String> chunks = Flux.just("The key is api_", "key=sk-ant-abcdefghij", "klmnopqrstuv now\nnext ", "line ok");
        String out = String.join("", StreamRedactor.redactLines(chunks).collectList().block());
        assertFalse(out.contains("sk-ant"));
        assertTrue(out.contains("api_key=****"));
        assertTrue(out.endsWith("next line ok"));
    }
}
