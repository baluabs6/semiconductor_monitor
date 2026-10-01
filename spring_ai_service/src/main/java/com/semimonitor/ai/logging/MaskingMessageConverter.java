package com.semimonitor.ai.logging;

import ch.qos.logback.classic.pattern.ClassicConverter;
import ch.qos.logback.classic.spi.ILoggingEvent;
import com.semimonitor.ai.security.Redactor;

/** %maskedMsg - the formatted log message with sensitive data masked. */
public class MaskingMessageConverter extends ClassicConverter {
    @Override
    public String convert(ILoggingEvent event) {
        return Redactor.redact(event.getFormattedMessage());
    }
}
