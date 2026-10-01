package com.semimonitor.ai.security;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.*;

class PromptSafetyTest {

    private static JsonNode read(String name, String field) throws Exception {
        return new ObjectMapper().readTree(Files.readString(Path.of("..", "shared", name))).get(field);
    }

    /** Same vectors as backend/tests/test_promptsafety.py, so the two implementations cannot drift apart. */
    @Test
    void matchesSharedVectors() throws Exception {
        for (JsonNode c : read("promptsafety_cases.json", "cases")) {
            assertEquals(c.get("expected").asText(), PromptSafety.sanitize(c.get("input").asText()), c.get("input").asText());
        }
    }

    @Test
    void hostileLogLinesCannotBreakOutOfThePromptStructure() throws Exception {
        for (JsonNode line : read("injection_corpus.json", "lines")) {
            String out = PromptSafety.sanitize(line.asText());
            assertFalse(out.contains("\n") || out.contains("\r"), out);
            assertFalse(out.contains("<") || out.contains(">"), out);
            assertTrue(out.length() <= PromptSafety.MAX_FIELD_CHARS + "...[truncated]".length());
        }
    }

    @Test
    void formattedPromptHasExactlyOneLinePerAlert() throws Exception {
        var alerts = new java.util.ArrayList<com.semimonitor.ai.model.AlertDto>();
        long id = 0;
        for (JsonNode line : read("injection_corpus.json", "lines")) {
            alerts.add(new com.semimonitor.ai.model.AlertDto(++id, "2026-10-01T10:00:00", "FIRMWARE", "WARNING", line.asText()));
        }
        String formatted = com.semimonitor.ai.service.AiInsightService.format(alerts);
        assertEquals(alerts.size(), formatted.split("\n").length);
        assertFalse(formatted.contains("</alerts>"));
    }
}
