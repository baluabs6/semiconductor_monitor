package com.semimonitor.ai.client;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Duration;

/** Location and client settings for the Python monitor backend (the C/C++ engine lives behind it). */
@ConfigurationProperties(prefix = "monitor")
public record MonitorProperties(String baseUrl, Duration connectTimeout, Duration readTimeout, Integer retries) {

    public MonitorProperties {
        if (baseUrl == null || baseUrl.isBlank()) baseUrl = "http://localhost:8001";
        if (connectTimeout == null) connectTimeout = Duration.ofSeconds(2);
        if (readTimeout == null) readTimeout = Duration.ofSeconds(5);
        if (retries == null || retries < 0) retries = 2;
    }
}
