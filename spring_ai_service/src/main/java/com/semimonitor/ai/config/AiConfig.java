package com.semimonitor.ai.config;

import com.semimonitor.ai.advisor.AuditAdvisor;
import com.semimonitor.ai.advisor.RedactionAdvisor;
import com.semimonitor.ai.rag.RagProperties;
import com.semimonitor.ai.rag.RunbookIndex;
import com.semimonitor.ai.rag.RunbookLoader;
import com.semimonitor.ai.rag.RunbookRetriever;
import com.semimonitor.ai.security.Redactor;
import com.semimonitor.ai.tools.MonitorTools;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.ai.chat.memory.ChatMemory;
import org.springframework.ai.chat.memory.MessageWindowChatMemory;
import org.springframework.ai.chat.prompt.PromptTemplate;
import org.springframework.ai.document.Document;
import org.springframework.ai.rag.advisor.RetrievalAugmentationAdvisor;
import org.springframework.ai.rag.generation.augmentation.ContextualQueryAugmenter;
import org.springframework.ai.tool.ToolCallbackProvider;
import org.springframework.ai.tool.method.MethodToolCallbackProvider;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.stream.Collectors;

@Configuration
public class AiConfig {

    /** Sliding window of the last 20 messages per conversation. In-memory: lost on restart. */
    @Bean
    ChatMemory chatMemory() {
        return MessageWindowChatMemory.builder().maxMessages(20).build();
    }

    /** Publishes the read-only monitor tools over MCP (Claude Desktop / Claude Code can connect). */
    @Bean
    ToolCallbackProvider monitorToolCallbacks(MonitorTools tools) {
        return MethodToolCallbackProvider.builder().toolObjects(tools).build();
    }

    // ---- advisors ---------------------------------------------------------------------------

    @Bean
    RedactionAdvisor redactionAdvisor() {
        return new RedactionAdvisor();
    }

    @Bean
    AuditAdvisor auditAdvisor(MeterRegistry meters) {
        return new AuditAdvisor(meters);
    }

    // ---- RAG over runbooks ------------------------------------------------------------------

    @Bean
    @ConditionalOnProperty(prefix = "monitor.rag", name = "enabled", havingValue = "true", matchIfMissing = true)
    RunbookRetriever runbookRetriever(RagProperties props) {
        RunbookIndex index = new RunbookIndex(RunbookLoader.load(props.runbooksDir()));
        return new RunbookRetriever(index, props);
    }

    /**
     * Adds matching runbook excerpts to the user message. allowEmptyContext(true) is essential: by
     * default Spring AI replaces the question with "the query is outside your knowledge base" when
     * nothing is retrieved, which would break general questions and tool-calling.
     */
    @Bean
    @ConditionalOnProperty(prefix = "monitor.rag", name = "enabled", havingValue = "true", matchIfMissing = true)
    RetrievalAugmentationAdvisor runbookAdvisor(RunbookRetriever retriever) {
        PromptTemplate template = new PromptTemplate("""
                Relevant excerpts from the fab's internal runbooks (trusted documentation) are below.
                ---------------------
                {context}
                ---------------------
                Use an excerpt only if it applies to the request, and cite it by its runbook name in
                square brackets, for example [cooling_failure]. If none apply, ignore them and do not
                mention them.

                {query}
                """);
        ContextualQueryAugmenter augmenter = ContextualQueryAugmenter.builder()
                .promptTemplate(template)
                .allowEmptyContext(true)
                .documentFormatter(docs -> docs.stream()
                        .map(AiConfig::formatExcerpt)
                        .collect(Collectors.joining("\n\n")))
                .build();
        return RetrievalAugmentationAdvisor.builder()
                .documentRetriever(retriever)
                .queryAugmenter(augmenter)
                .build();
    }

    private static String formatExcerpt(Document d) {
        // Runbooks are trusted, but they are sent to an external API, so mask anything secret-shaped as well.
        return "[" + d.getMetadata().get("source") + "] " + d.getMetadata().get("heading") + "\n" + Redactor.redact(d.getText());
    }
}
