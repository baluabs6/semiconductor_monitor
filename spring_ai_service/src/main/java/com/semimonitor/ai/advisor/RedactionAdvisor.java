package com.semimonitor.ai.advisor;

import com.semimonitor.ai.security.Redactor;
import org.springframework.ai.chat.client.ChatClientRequest;
import org.springframework.ai.chat.client.ChatClientResponse;
import org.springframework.ai.chat.client.advisor.api.AdvisorChain;
import org.springframework.ai.chat.client.advisor.api.BaseAdvisor;
import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.messages.Message;
import org.springframework.ai.chat.messages.UserMessage;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.chat.model.Generation;
import org.springframework.ai.chat.prompt.Prompt;
import org.springframework.core.Ordered;

import java.util.ArrayList;
import java.util.List;

/**
 * Masks sensitive data (****) on every ChatClient call that uses this advisor, so a future endpoint cannot
 * forget to: user messages are redacted before they reach the model (and before chat memory stores them),
 * and the model's reply is redacted on the way out. Runs just inside the audit advisor and before chat
 * memory (whose order is HIGHEST_PRECEDENCE + 1000).
 *
 * Streaming note: for streamed calls this applies only to the final chunk. StreamRedactor in the service
 * masks the whole stream line by line, because a secret can be split across chunks.
 */
public class RedactionAdvisor implements BaseAdvisor {

    public static final String CONTEXT_REDACTED = "monitor.redaction.inputRedacted";

    @Override
    public ChatClientRequest before(ChatClientRequest request, AdvisorChain chain) {
        Prompt prompt = request.prompt();
        List<Message> messages = new ArrayList<>(prompt.getInstructions().size());
        boolean changed = false;
        for (Message m : prompt.getInstructions()) {
            if (m instanceof UserMessage um && um.getText() != null) {
                String masked = Redactor.redact(um.getText());
                if (!masked.equals(um.getText())) {
                    changed = true;
                    m = um.mutate().text(masked).build();
                }
            }
            messages.add(m);
        }
        if (!changed) return request;
        return request.mutate()
                .prompt(new Prompt(messages, prompt.getOptions()))
                .context(CONTEXT_REDACTED, true)
                .build();
    }

    @Override
    public ChatClientResponse after(ChatClientResponse response, AdvisorChain chain) {
        ChatResponse chatResponse = response.chatResponse();
        if (chatResponse == null || chatResponse.getResults() == null) return response;

        List<Generation> masked = new ArrayList<>();
        boolean changed = false;
        for (Generation g : chatResponse.getResults()) {
            AssistantMessage out = g.getOutput();
            String text = out == null ? null : out.getText();
            String clean = Redactor.redact(text);
            if (text != null && !text.equals(clean)) {
                changed = true;
                AssistantMessage fixed = AssistantMessage.builder()
                        .content(clean)
                        .properties(out.getMetadata())
                        .toolCalls(out.getToolCalls())
                        .build();
                masked.add(new Generation(fixed, g.getMetadata()));
            } else {
                masked.add(g);
            }
        }
        if (!changed) return response;
        ChatResponse rebuilt = ChatResponse.builder().from(chatResponse).generations(masked).build();
        return ChatClientResponse.builder().chatResponse(rebuilt).context(response.context()).build();
    }

    @Override
    public int getOrder() {
        return Ordered.HIGHEST_PRECEDENCE + 100;
    }
}
