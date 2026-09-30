package com.semimonitor.ai.client;

import com.semimonitor.ai.model.AlertDto;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;

/** Thin HTTP client over the Python backend's existing endpoints. No Python changes required. */
@Component
public class MonitorClient {

    private final RestClient http;

    public MonitorClient(MonitorProperties props, RestClient.Builder builder) {
        this.http = builder.baseUrl(props.baseUrl()).build();
    }

    /** In-memory recent alerts (Python keeps the last 500), optional severity filter. */
    public List<AlertDto> recent(int limit, String severity) {
        return http.get()
                .uri(u -> {
                    u.path("/alerts").queryParam("limit", limit);
                    if (severity != null && !severity.isBlank()) u.queryParam("severity", severity);
                    return u.build();
                })
                .retrieve()
                .body(new ParameterizedTypeReference<List<AlertDto>>() { });
    }

    /** Alerts from the last N minutes (filtered here; Python's buffer is capped at 500). */
    public List<AlertDto> recentWindow(double minutes) {
        Instant cutoff = Instant.now().minus(Duration.ofSeconds((long) (minutes * 60)));
        return recent(500, null).stream().filter(a -> !a.toInstant().isBefore(cutoff)).toList();
    }

    /** Persisted (SQLite) history, newest first, optional source filter. */
    public List<AlertDto> history(int limit, String source) {
        return http.get()
                .uri(u -> {
                    u.path("/alerts/history").queryParam("limit", limit);
                    if (source != null && !source.isBlank()) u.queryParam("source", source);
                    return u.build();
                })
                .retrieve()
                .body(new ParameterizedTypeReference<List<AlertDto>>() { });
    }

    /** Persisted alerts from the last N hours, oldest first. */
    public List<AlertDto> historyWindow(double hours, String source) {
        Instant cutoff = Instant.now().minus(Duration.ofSeconds((long) (hours * 3600)));
        return history(1000, source).stream()
                .filter(a -> !a.toInstant().isBefore(cutoff))
                .sorted((a, b) -> Long.compare(a.id(), b.id()))
                .toList();
    }

    public Map<String, Integer> summary() {
        return http.get().uri("/summary").retrieve().body(new ParameterizedTypeReference<Map<String, Integer>>() { });
    }
}
