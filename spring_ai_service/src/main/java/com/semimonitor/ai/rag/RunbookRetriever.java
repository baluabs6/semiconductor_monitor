package com.semimonitor.ai.rag;

import org.springframework.ai.document.Document;
import org.springframework.ai.rag.Query;
import org.springframework.ai.rag.retrieval.search.DocumentRetriever;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Spring AI DocumentRetriever backed by the in-memory BM25 RunbookIndex. To use embeddings instead,
 * replace this bean with a VectorStoreDocumentRetriever; nothing else changes.
 */
public class RunbookRetriever implements DocumentRetriever {

    private final RunbookIndex index;
    private final int topK;
    private final double minScore;
    private final double relativeCutoff;

    public RunbookRetriever(RunbookIndex index, RagProperties props) {
        this.index = index;
        this.topK = props.topK();
        this.minScore = props.minScore();
        this.relativeCutoff = props.relativeCutoff();
    }

    @Override
    public List<Document> retrieve(Query query) {
        List<RunbookIndex.Hit> hits = index.search(query.text(), topK, minScore);
        if (hits.isEmpty()) return List.of();
        double floor = hits.get(0).score() * relativeCutoff;
        return hits.stream()
                .filter(h -> h.score() >= floor)
                .map(h -> {
                    Map<String, Object> meta = new LinkedHashMap<>();
                    meta.put("source", h.chunk().source());
                    meta.put("heading", h.chunk().heading());
                    return Document.builder().text(h.chunk().text()).metadata(meta).score(h.score()).build();
                })
                .toList();
    }
}
