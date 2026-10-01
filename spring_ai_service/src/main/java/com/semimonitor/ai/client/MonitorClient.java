package com.semimonitor.ai.client;

import com.semimonitor.ai.model.AlertDto;
import com.semimonitor.ai.security.Redactor;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.HttpServerErrorException;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.function.Supplier;

/**
 * Thin HTTP client over the Python backend's existing endpoints. No Python changes required.
 * Has connect/read timeouts and retries transient failures (connection errors, 5xx) with backoff,
 * and masks sensitive data in everything it returns.
 */
@Component
public class MonitorClient {

    private final RestClient http;
    private final int retries;

    public MonitorClient(MonitorProperties props, RestClient.Builder builder) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(props.connectTimeout());
        factory.setReadTimeout(props.readTimeout());
        this.http = builder.requestFactory(factory).baseUrl(props.baseUrl()).build();
        this.retries = props.retries();
    }

    /** In-memory recent alerts (Python keeps the last 500), optional severity filter. */
    public List<AlertDto> recent(int limit, String severity) {
        List<AlertDto> raw = withRetry(() -> http.get()
                .uri(u -> {
                    u.path("/alerts").queryParam("limit", limit);
                    if (severity != null && !severity.isBlank()) u.queryParam("severity", severity);
                    return u.build();
                })
                .retrieve()
                .body(new ParameterizedTypeReference<List<AlertDto>>() { }));
        return Redactor.redact(raw);
    }

    /** Alerts from the last N minutes (filtered here; Python's buffer is capped at 500). */
    public List<AlertDto> recentWindow(double minutes) {
        Instant cutoff = Instant.now().minus(Duration.ofSeconds((long) (minutes * 60)));
        return recent(500, null).stream().filter(a -> !a.toInstant().isBefore(cutoff)).toList();
    }

    /** Persisted (SQLite) history, newest first, optional source filter. */
    public List<AlertDto> history(int limit, String source) {
        List<AlertDto> raw = withRetry(() -> http.get()
                .uri(u -> {
                    u.path("/alerts/history").queryParam("limit", limit);
                    if (source != null && !source.isBlank()) u.queryParam("source", source);
                    return u.build();
                })
                .retrieve()
                .body(new ParameterizedTypeReference<List<AlertDto>>() { }));
        return Redactor.redact(raw);
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
        return withRetry(() -> http.get().uri("/summary").retrieve()
                .body(new ParameterizedTypeReference<Map<String, Integer>>() { }));
    }

    private <T> T withRetry(Supplier<T> call) {
        RestClientException last = null;
        for (int attempt = 0; attempt <= retries; attempt++) {
            try {
                return call.get();
            } catch (ResourceAccessException | HttpServerErrorException e) {   // transient only; 4xx is not retried
                last = e;
                try {
                    Thread.sleep(200L * (attempt + 1));
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    break;
                }
            }
        }
        throw last;
    }
}
