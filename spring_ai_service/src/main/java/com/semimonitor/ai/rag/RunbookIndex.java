package com.semimonitor.ai.rag;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * Small in-memory BM25 keyword index over runbook sections. Deliberately free of Spring and of any
 * embedding model: Anthropic offers no embeddings API, and a keyword index over a few hundred
 * short runbook sections works well for exact terms such as "WDT_RESET" or "Leakage_Current".
 * It is used through the DocumentRetriever interface, so replacing it with a VectorStore-backed
 * retriever later is a one-bean change.
 */
public final class RunbookIndex {

    public record Chunk(String source, String heading, String text) { }

    public record Hit(Chunk chunk, double score) { }

    static final int MAX_CHUNK_CHARS = 1200;
    private static final double K1 = 1.5;
    private static final double B = 0.75;
    private static final Set<String> STOP = Set.of(
            "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "is", "are", "was", "were", "be",
            "by", "with", "at", "as", "it", "this", "that", "from", "if", "then", "than", "not", "no", "can",
            "may", "what", "which", "who", "how", "why", "when", "do", "does", "we", "you", "our", "your");

    private final List<Chunk> chunks;
    private final List<Map<String, Integer>> termFreqs = new ArrayList<>();
    private final int[] lengths;
    private final Map<String, Integer> docFreq = new HashMap<>();
    private final double avgLength;

    public RunbookIndex(List<Chunk> chunks) {
        this.chunks = List.copyOf(chunks);
        this.lengths = new int[this.chunks.size()];
        long total = 0;
        for (int i = 0; i < this.chunks.size(); i++) {
            Chunk c = this.chunks.get(i);
            List<String> tokens = tokenize(c.heading() + "\n" + c.text());
            Map<String, Integer> tf = new HashMap<>();
            for (String t : tokens) tf.merge(t, 1, Integer::sum);
            termFreqs.add(tf);
            lengths[i] = tokens.size();
            total += tokens.size();
            for (String t : tf.keySet()) docFreq.merge(t, 1, Integer::sum);
        }
        this.avgLength = this.chunks.isEmpty() ? 0 : (double) total / this.chunks.size();
    }

    public int size() {
        return chunks.size();
    }

    /** Top-K chunks scoring at least minScore, best first. Query term repetition is ignored so long queries don't dominate. */
    public List<Hit> search(String query, int topK, double minScore) {
        if (chunks.isEmpty() || query == null || query.isBlank() || topK <= 0) return List.of();
        Set<String> terms = new HashSet<>(tokenize(query));
        int n = chunks.size();
        List<Hit> hits = new ArrayList<>();
        for (int i = 0; i < n; i++) {
            double score = 0;
            Map<String, Integer> tf = termFreqs.get(i);
            for (String t : terms) {
                Integer f = tf.get(t);
                if (f == null) continue;
                int df = docFreq.get(t);
                double idf = Math.log(1 + (n - df + 0.5) / (df + 0.5));
                score += idf * (f * (K1 + 1)) / (f + K1 * (1 - B + B * lengths[i] / avgLength));
            }
            if (score >= minScore) hits.add(new Hit(chunks.get(i), score));
        }
        hits.sort(Comparator.comparingDouble(Hit::score).reversed());
        return hits.size() > topK ? List.copyOf(hits.subList(0, topK)) : List.copyOf(hits);
    }

    // ---- tokenizing -------------------------------------------------------------------------

    static List<String> tokenize(String text) {
        List<String> out = new ArrayList<>();
        for (String raw : text.toLowerCase(Locale.ROOT).split("[^a-z0-9]+")) {
            if (raw.length() < 2 || STOP.contains(raw)) continue;
            out.add(stem(raw));
        }
        return out;
    }

    /** Deliberately tiny stemmer; it only has to be consistent between documents and queries. */
    static String stem(String t) {
        if (t.length() > 5 && t.endsWith("ing")) return t.substring(0, t.length() - 3);
        if (t.length() > 4 && t.endsWith("ies")) return t.substring(0, t.length() - 3) + "y";
        if (t.length() > 4 && t.endsWith("ed")) return t.substring(0, t.length() - 2);
        if (t.length() > 3 && t.endsWith("s") && !t.endsWith("ss")) return t.substring(0, t.length() - 1);
        return t;
    }

    // ---- markdown chunking ------------------------------------------------------------------

    /** Splits markdown into sections by heading (levels 1-3); long sections are split by paragraph. */
    public static List<Chunk> chunkMarkdown(String source, String markdown) {
        markdown = markdown.replaceAll("(?s)<!--.*?-->", "");   // HTML comments (e.g. SAMPLE notes) are not content
        List<Chunk> out = new ArrayList<>();
        String[] titles = new String[3];
        StringBuilder body = new StringBuilder();
        String heading = source;
        for (String line : markdown.split("\\R", -1)) {
            int level = headingLevel(line);
            if (level > 0) {
                flush(out, source, heading, body);
                titles[level - 1] = line.substring(level).trim();
                for (int i = level; i < 3; i++) titles[i] = null;
                StringBuilder path = new StringBuilder();
                for (String t : titles) {
                    if (t != null && !t.isEmpty()) path.append(path.length() == 0 ? "" : " > ").append(t);
                }
                heading = path.length() == 0 ? source : path.toString();
            } else {
                body.append(line).append('\n');
            }
        }
        flush(out, source, heading, body);
        return out;
    }

    private static int headingLevel(String line) {
        int i = 0;
        while (i < line.length() && i < 4 && line.charAt(i) == '#') i++;
        return (i >= 1 && i <= 3 && line.length() > i && line.charAt(i) == ' ') ? i : 0;
    }

    private static void flush(List<Chunk> out, String source, String heading, StringBuilder body) {
        String text = body.toString().strip();
        body.setLength(0);
        if (text.isEmpty()) return;
        StringBuilder cur = new StringBuilder();
        for (String para : text.split("\\n\\s*\\n")) {
            String p = para.strip();
            while (p.length() > MAX_CHUNK_CHARS) {                       // hard-split a giant paragraph
                emit(out, source, heading, cur);
                out.add(new Chunk(source, heading, p.substring(0, MAX_CHUNK_CHARS)));
                p = p.substring(MAX_CHUNK_CHARS);
            }
            if (cur.length() + p.length() + 2 > MAX_CHUNK_CHARS) emit(out, source, heading, cur);
            if (cur.length() > 0) cur.append("\n\n");
            cur.append(p);
        }
        emit(out, source, heading, cur);
    }

    private static void emit(List<Chunk> out, String source, String heading, StringBuilder cur) {
        if (cur.toString().isBlank()) return;
        out.add(new Chunk(source, heading, cur.toString().strip()));
        cur.setLength(0);
    }
}
