package com.semimonitor.ai.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

import java.time.Instant;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeParseException;

/** Mirrors the alert JSON produced by the Python engine. Unknown fields are ignored so the
 *  Python side can add structured fields (tool_id, lot_id, ...) without breaking this service. */
@JsonIgnoreProperties(ignoreUnknown = true)
public record AlertDto(long id, String timestamp, String source, String severity, String message) {

    /** Python currently emits naive local timestamps; also accept offset timestamps (UTC) for later. */
    public Instant toInstant() {
        try {
            return OffsetDateTime.parse(timestamp).toInstant();
        } catch (DateTimeParseException e) {
            return LocalDateTime.parse(timestamp).atZone(ZoneId.systemDefault()).toInstant();
        }
    }
}
