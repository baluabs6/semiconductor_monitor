package com.semimonitor.ai.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.time.Instant;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeParseException;

/** Mirrors the alert JSON produced by the Python engine. Unknown fields are ignored so the Python
 *  side can add fields without breaking this service. Genealogy fields are blank on old alerts. */
@JsonIgnoreProperties(ignoreUnknown = true)
public record AlertDto(
        long id, String timestamp, String source, String severity, String message,
        @JsonProperty("tool_id") String toolId,
        @JsonProperty("lot_id") String lotId,
        @JsonProperty("wafer_id") String waferId,
        String recipe, String step) {

    /** Alert without genealogy context. */
    public AlertDto(long id, String timestamp, String source, String severity, String message) {
        this(id, timestamp, source, severity, message, null, null, null, null, null);
    }

    /** Python currently emits naive local timestamps; also accept offset timestamps (UTC) for later. */
    public Instant toInstant() {
        try {
            return OffsetDateTime.parse(timestamp).toInstant();
        } catch (DateTimeParseException e) {
            return LocalDateTime.parse(timestamp).atZone(ZoneId.systemDefault()).toInstant();
        }
    }
}
