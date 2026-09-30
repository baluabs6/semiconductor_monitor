package com.semimonitor.ai.model;

import java.util.List;

/** Structured root-cause hypothesis returned by Claude (Spring AI maps the JSON to this record). */
public record IncidentAnalysis(
        boolean related,
        Confidence confidence,
        String hypothesis,
        String nextStep,
        List<String> affectedSubsystems) {

    public enum Confidence { LOW, MEDIUM, HIGH }
}
