package com.semimonitor.ai.config;

import com.semimonitor.ai.security.Redactor;
import org.springframework.context.annotation.Configuration;

/** Applies monitor.redaction.* to the static Redactor at start-up (an invalid pattern stops the app). */
@Configuration
public class RedactionConfig {
    public RedactionConfig(RedactionProperties props) {
        Redactor.configure(props.extraPatterns(), props.allowlist());
    }
}
