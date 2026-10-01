package com.semimonitor.ai.rag;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Stream;

import static org.junit.jupiter.api.Assertions.*;

class RunbookIndexTest {

    private static RunbookIndex sampleIndex() throws Exception {
        List<RunbookIndex.Chunk> chunks = new ArrayList<>();
        try (Stream<Path> files = Files.list(Path.of("src/main/resources/runbooks"))) {
            for (Path p : files.filter(f -> f.toString().endsWith(".md")).toList()) {
                String name = p.getFileName().toString().replaceAll("\\.md$", "");
                chunks.addAll(RunbookIndex.chunkMarkdown(name, Files.readString(p)));
            }
        }
        return new RunbookIndex(chunks);
    }

    @Test
    void firmwareWatchdogAlertFindsFirmwareRunbook() throws Exception {
        var hits = sampleIndex().search("device log: ERROR WDT_RESET: watchdog timeout in main_loop", 3, 0.5);
        assertFalse(hits.isEmpty());
        assertEquals("firmware_watchdog_and_flash", hits.get(0).chunk().source());
    }

    @Test
    void temperatureAlertFindsCoolingRunbook() throws Exception {
        var hits = sampleIndex().search("Temperature out of range: 112.40 chamber coolant", 3, 0.5);
        assertEquals("cooling_failure", hits.get(0).chunk().source());
    }

    @Test
    void unrelatedQueryReturnsNothing() throws Exception {
        assertTrue(sampleIndex().search("what is the best pizza topping", 3, 0.5).isEmpty());
    }

    @Test
    void chunkingKeepsHeadingPathAndBoundsSize() {
        String md = "# Title\n\n## Part A\n" + "word ".repeat(1000) + "\n\n## Part B\nshort text\n";
        var chunks = RunbookIndex.chunkMarkdown("doc", md);
        assertTrue(chunks.stream().allMatch(c -> c.text().length() <= RunbookIndex.MAX_CHUNK_CHARS));
        assertTrue(chunks.stream().anyMatch(c -> c.heading().equals("Title > Part B")));
    }

    @Test
    void emptyIndexAndBlankQueryAreSafe() {
        assertTrue(new RunbookIndex(List.of()).search("x", 3, 0).isEmpty());
        assertTrue(new RunbookIndex(List.of(new RunbookIndex.Chunk("a", "h", "text here"))).search("  ", 3, 0).isEmpty());
    }
}
