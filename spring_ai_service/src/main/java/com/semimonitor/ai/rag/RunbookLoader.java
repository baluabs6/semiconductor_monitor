package com.semimonitor.ai.rag;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.io.Resource;
import org.springframework.core.io.support.PathMatchingResourcePatternResolver;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Stream;

/** Loads runbooks from RUNBOOKS_DIR if configured, otherwise from the bundled SAMPLE runbooks on the classpath. */
public final class RunbookLoader {

    private static final Logger log = LoggerFactory.getLogger(RunbookLoader.class);
    private static final long MAX_FILE_BYTES = 2_000_000;

    private RunbookLoader() { }

    public static List<RunbookIndex.Chunk> load(String runbooksDir) {
        List<RunbookIndex.Chunk> chunks = new ArrayList<>();
        try {
            if (runbooksDir != null && !runbooksDir.isBlank()) {
                try (Stream<Path> files = Files.list(Path.of(runbooksDir))) {
                    for (Path p : files.filter(f -> f.toString().endsWith(".md")).sorted().toList()) {
                        if (Files.size(p) > MAX_FILE_BYTES) {
                            log.warn("Skipping runbook {} (larger than {} bytes)", p.getFileName(), MAX_FILE_BYTES);
                            continue;
                        }
                        chunks.addAll(RunbookIndex.chunkMarkdown(baseName(p.getFileName().toString()),
                                Files.readString(p, StandardCharsets.UTF_8)));
                    }
                }
                log.info("Loaded {} runbook chunks from {}", chunks.size(), runbooksDir);
            } else {
                Resource[] resources = new PathMatchingResourcePatternResolver().getResources("classpath*:runbooks/*.md");
                for (Resource r : resources) {
                    String text = new String(r.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
                    chunks.addAll(RunbookIndex.chunkMarkdown(baseName(r.getFilename()), text));
                }
                log.info("Loaded {} chunks from the bundled SAMPLE runbooks. Set RUNBOOKS_DIR to use your own.", chunks.size());
            }
        } catch (IOException e) {
            log.error("Could not load runbooks ({}); continuing without retrieval context", e.toString());
        }
        return chunks;
    }

    private static String baseName(String filename) {
        return filename == null ? "runbook" : filename.replaceAll("\\.md$", "");
    }
}
