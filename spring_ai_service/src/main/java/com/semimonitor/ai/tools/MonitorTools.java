package com.semimonitor.ai.tools;

import com.semimonitor.ai.client.MonitorClient;
import com.semimonitor.ai.model.AlertDto;
import com.semimonitor.ai.model.ContainmentReport;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;

/**
 * Tools Claude can call on its own during /ai/chat. Read-only by design: the model can look at
 * alerts but cannot change anything. Results are untrusted data (alert text originates from
 * device logs), which the system prompt tells the model to treat as data, not instructions.
 */
@Component
public class MonitorTools {

    private final MonitorClient monitor;

    public MonitorTools(MonitorClient monitor) {
        this.monitor = monitor;
    }

    @Tool(description = "Get the most recent live alerts from the semiconductor monitor, newest last. "
            + "Sources are FAB (sensors), ATE (die test), FIRMWARE (device logs), HEALTH (controller).")
    public List<AlertDto> getRecentAlerts(
            @ToolParam(description = "Max alerts to return, 1-100") int limit,
            @ToolParam(description = "Optional severity filter: INFO, WARNING or CRITICAL", required = false) String severity) {
        return monitor.recent(clamp(limit, 1, 100), severity);
    }

    @Tool(description = "Get persisted alert history from the database, newest first, optionally for one source.")
    public List<AlertDto> getAlertHistory(
            @ToolParam(description = "Max alerts to return, 1-200") int limit,
            @ToolParam(description = "Optional source filter: FAB, ATE, FIRMWARE or HEALTH", required = false) String source) {
        return monitor.history(clamp(limit, 1, 200), source);
    }

    @Tool(description = "Get running alert counts by severity since the monitor started.")
    public Map<String, Integer> getSeverityCounts() {
        return monitor.summary();
    }

    @Tool(description = "Get the deterministic excursion-containment report: which lots were on the tool during "
            + "critical FAB/FIRMWARE/HEALTH alerts, with risk (HIGH/MEDIUM) per lot. Read-only; it does not hold anything.")
    public ContainmentReport getContainmentReport(
            @ToolParam(description = "Look-back window in hours, 1-72") int hours) {
        return monitor.containment(clamp(hours, 1, 72));
    }

    private static int clamp(int v, int lo, int hi) {
        return Math.max(lo, Math.min(hi, v));
    }
}
