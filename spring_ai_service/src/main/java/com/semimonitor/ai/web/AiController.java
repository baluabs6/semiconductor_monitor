package com.semimonitor.ai.web;

import com.semimonitor.ai.model.IncidentAnalysis;
import com.semimonitor.ai.model.ShiftReport;
import com.semimonitor.ai.service.AiInsightService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestClientException;

import java.util.Map;

@RestController
@RequestMapping("/ai")
public class AiController {

    private final AiInsightService ai;

    public AiController(AiInsightService ai) {
        this.ai = ai;
    }

    @GetMapping("/analyze")
    public IncidentAnalysis analyze(@RequestParam(defaultValue = "5") double minutes) {
        return ai.analyze(minutes);
    }

    @GetMapping("/report")
    public ShiftReport report(@RequestParam(defaultValue = "8") double hours,
                              @RequestParam(required = false) String source) {
        return ai.report(hours, source);
    }

    public record ChatRequest(String question) { }

    @PostMapping("/chat")
    public Map<String, String> chat(@RequestBody ChatRequest req) {
        if (req.question() == null || req.question().isBlank()) {
            throw new IllegalArgumentException("question must not be blank");
        }
        return Map.of("answer", ai.ask(req.question()));
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ProblemDetail badRequest(IllegalArgumentException e) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST, e.getMessage());
    }

    @ExceptionHandler(RestClientException.class)
    public ProblemDetail backendDown(RestClientException e) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.BAD_GATEWAY,
                "Could not reach the Python monitor backend: " + e.getMessage());
    }
}
