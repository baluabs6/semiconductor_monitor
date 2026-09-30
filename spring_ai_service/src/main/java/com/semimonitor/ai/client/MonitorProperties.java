package com.semimonitor.ai.client;

import org.springframework.boot.context.properties.ConfigurationProperties;

/** Location of the Python monitor backend (the C/C++ engine lives behind it). */
@ConfigurationProperties(prefix = "monitor")
public record MonitorProperties(String baseUrl) {
}
