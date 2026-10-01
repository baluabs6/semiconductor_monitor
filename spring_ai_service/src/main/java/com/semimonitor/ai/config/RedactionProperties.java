package com.semimonitor.ai.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.List;

/**
 * monitor.redaction.extra-patterns: regexes to mask in addition to the built-ins (badge IDs, internal hostnames).
 * monitor.redaction.allowlist:      literal strings that must never be masked (e.g. a public gateway IP).
 * Note: Spring splits env-var lists on commas, so put regexes containing commas in application.yml instead.
 */
@ConfigurationProperties(prefix = "monitor.redaction")
public record RedactionProperties(List<String> extraPatterns, List<String> allowlist) {
}
