package com.semimonitor.ai.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/** monitor.security.api-key. Blank disables the API-key check (fine for localhost, not for shared networks). */
@ConfigurationProperties(prefix = "monitor.security")
public record ServiceSecurityProperties(String apiKey) {
}
