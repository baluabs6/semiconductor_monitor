package com.semimonitor.ai.config;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/**
 * Optional shared-secret check for /ai/**, /sse and /mcp/** (the AI endpoints and the MCP server).
 * Enabled when monitor.security.api-key (env SERVICE_API_KEY) is non-blank; callers send X-API-Key.
 */
@Component
public class ApiKeyFilter extends OncePerRequestFilter {

    private static final Logger log = LoggerFactory.getLogger(ApiKeyFilter.class);
    private final byte[] expected;

    public ApiKeyFilter(ServiceSecurityProperties props) {
        String key = props.apiKey();
        this.expected = (key == null || key.isBlank()) ? null : key.getBytes(StandardCharsets.UTF_8);
        if (expected == null) {
            log.warn("API-key auth is DISABLED for /ai/**, /sse and /mcp/**. Set SERVICE_API_KEY to enable it.");
        }
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        if (expected == null) return true;
        String path = request.getRequestURI();
        return !(path.startsWith("/ai/") || path.equals("/sse") || path.startsWith("/mcp/"));
    }

    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain)
            throws ServletException, IOException {
        String provided = req.getHeader("X-API-Key");
        if (provided != null && MessageDigest.isEqual(expected, provided.getBytes(StandardCharsets.UTF_8))) {
            chain.doFilter(req, res);
        } else {
            res.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            res.setContentType("application/json");
            res.getWriter().write("{\"error\":\"missing or invalid X-API-Key\"}");
        }
    }
}
