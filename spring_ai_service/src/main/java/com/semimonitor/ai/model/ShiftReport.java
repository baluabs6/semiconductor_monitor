package com.semimonitor.ai.model;

import java.util.List;

/** Structured shift-handoff report. */
public record ShiftReport(
        String overallStatus,
        List<SubsystemSummary> subsystems,
        List<String> followUps) {

    public record SubsystemSummary(String subsystem, List<String> incidents) { }
}
