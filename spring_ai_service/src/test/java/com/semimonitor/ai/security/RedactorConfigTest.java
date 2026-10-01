package com.semimonitor.ai.security;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class RedactorConfigTest {

    @AfterEach
    void reset() {
        Redactor.configure(List.of(), List.of());
    }

    @Test
    void extraPatternsAndAllowlist() {
        Redactor.configure(List.of("\\bBADGE-\\d{6}\\b"), List.of("10.0.0.1"));
        assertEquals("op **** on 10.0.0.1 and **** api_key=****",
                Redactor.redact("op BADGE-123456 on 10.0.0.1 and 10.0.0.2 api_key=zz"));
    }

    @Test
    void invalidPatternFailsLoudly() {
        IllegalArgumentException e = assertThrows(IllegalArgumentException.class,
                () -> Redactor.configure(List.of("(unclosed"), List.of()));
        assertTrue(e.getMessage().contains("invalid redaction pattern"));
    }
}
