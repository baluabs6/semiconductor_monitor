package com.semimonitor.ai.web;

import com.semimonitor.ai.model.ContainmentProposal;
import com.semimonitor.ai.model.IncidentAnalysis;
import com.semimonitor.ai.model.ShiftReport;
import com.semimonitor.ai.security.Redactor;
import com.semimonitor.ai.service.AiInsightService;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ProblemDetail;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestClientException;
import reactor.core.publisher.Flux;

import java.util.Map;
import java.util.regex.Pattern;

@RestController
@RequestMapping("/ai")
public class AiController {

    private static final Pattern CONVERSATION_ID = Pattern.compile("[A-Za-z0-9_-]{1,64}");
    private static final int MAX_QUESTION_CHARS = 4000;

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

    /** conversationId is optional; requests that share one id share chat memory. */
    /** Excursion-containment PROPOSAL (which lots to consider holding). Requires human approval; nothing is executed. */
    @GetMapping("/containment")
    public ContainmentProposal containment(@RequestParam(defaultValue = "8") double hours) {
        return ai.containment(hours);
    }

    public record ChatRequest(String question, String conversationId) { }

    @PostMapping("/chat")
    public Map<String, String> chat(@RequestBody ChatRequest req) {
        String id = conversationId(req);
        return Map.of("conversationId", id, "answer", ai.ask(question(req), id));
    }

    /** Server-Sent Events; each event is one complete, masked line of the answer. */
    @PostMapping(value = "/chat/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<String> chatStream(@RequestBody ChatRequest req) {
        return ai.askStream(question(req), conversationId(req));
    }

    private static String question(ChatRequest req) {
        String q = req.question();
        if (q == null || q.isBlank()) throw new IllegalArgumentException("question must not be blank");
        if (q.length() > MAX_QUESTION_CHARS) {
            throw new IllegalArgumentException("question must be at most " + MAX_QUESTION_CHARS + " characters");
        }
        return q;
    }

    private static String conversationId(ChatRequest req) {
        String id = req.conversationId();
        if (id == null || id.isBlank()) return "default";
        if (!CONVERSATION_ID.matcher(id).matches()) {
            throw new IllegalArgumentException("conversationId must match [A-Za-z0-9_-]{1,64}");
        }
        return id;
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ProblemDetail badRequest(IllegalArgumentException e) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST, e.getMessage());
    }

    @ExceptionHandler(RestClientException.class)
    public ProblemDetail backendDown(RestClientException e) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.BAD_GATEWAY,
                "Could not reach the Python monitor backend: " + Redactor.redact(e.getMessage()));
    }
}
