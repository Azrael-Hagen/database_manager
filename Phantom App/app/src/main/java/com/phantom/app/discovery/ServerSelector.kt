package com.phantom.app.discovery

object ServerSelector {
    fun selectBest(candidates: List<ServerCandidate>, previousUrl: String?): ServerCandidate? {
        if (candidates.isEmpty()) {
            return null
        }
        if (!previousUrl.isNullOrBlank()) {
            val previous = candidates.firstOrNull { it.baseUrl == previousUrl }
            if (previous != null) {
                return previous
            }
        }
        return candidates.minByOrNull { it.latencyMs }
    }
}
