package com.semimonitor.ai.model;

import java.util.List;

/**
 * What /ai/containment returns. It is a PROPOSAL: nothing is held or released automatically, and
 * humanApprovalRequired is always true. The lot list comes from deterministic data; Claude only writes
 * the summary and the rationale for each lot, and the service rejects any lot Claude invents.
 */
public record ContainmentProposal(
        boolean humanApprovalRequired,
        String summary,
        List<LotRecommendation> recommendations,
        List<String> caveats,
        ContainmentReport evidence) {

    public enum Priority { HOLD_NOW, HOLD_PENDING_REVIEW, MONITOR }

    public record LotRecommendation(String lotId, Priority priority, String rationale) { }

    /** The part Claude fills in (structured output). */
    public record ModelDraft(String summary, List<LotRecommendation> recommendations, List<String> caveats) { }
}
