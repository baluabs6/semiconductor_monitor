package com.semimonitor.ai.security;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTimeout;

import java.time.Duration;

class RedactorTest {

    /** Same vectors as backend/tests/test_redact.py, so the two implementations cannot drift apart. */
    @Test
    void matchesSharedVectors() throws Exception {
        Path file = Path.of("..", "shared", "redaction_cases.json");
        JsonNode cases = new ObjectMapper().readTree(Files.readString(file)).get("cases");
        for (JsonNode c : cases) {
            assertEquals(c.get("expected").asText(), Redactor.redact(c.get("input").asText()), c.get("input").asText());
        }
    }

    @Test
    void handlesHugeInputQuickly() {
        String nasty = "a".repeat(200_000) + "@" + "1.".repeat(100_000);
        assertTimeout(Duration.ofSeconds(2), () -> Redactor.redact(nasty));
    }
}
