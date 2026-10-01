package com.semimonitor.ai.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

/** Deterministic excursion-containment report from the Python backend (GET /containment). No AI involved. */
@JsonIgnoreProperties(ignoreUnknown = true)
public record ContainmentReport(
        @JsonProperty("window_hours") double windowHours,
        Excursion excursion,
        List<LotExposure> lots,
        String note) {

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Excursion(String start, String end, @JsonProperty("critical_alerts") int criticalAlerts) { }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record LotExposure(
            @JsonProperty("lot_id") String lotId,
            @JsonProperty("tool_id") String toolId,
            String recipe,
            String risk,   // HIGH or MEDIUM
            @JsonProperty("exposed_during_excursion") boolean exposedDuringExcursion,
            @JsonProperty("critical_alerts") int criticalAlerts,
            @JsonProperty("warning_alerts") int warningAlerts,
            @JsonProperty("ate_failures") int ateFailures,
            List<String> sources) { }
}
