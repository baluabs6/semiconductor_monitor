package com.semimonitor.ai.logging;

import ch.qos.logback.classic.pattern.ThrowableProxyConverter;
import ch.qos.logback.classic.spi.ILoggingEvent;
import com.semimonitor.ai.security.Redactor;

/** %maskedEx - stack traces (exception messages often echo URLs, tokens or headers) with sensitive data masked. */
public class MaskingThrowableConverter extends ThrowableProxyConverter {
    @Override
    public String convert(ILoggingEvent event) {
        return Redactor.redact(super.convert(event));
    }
}
