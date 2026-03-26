package com.phantom.app.discovery

data class ServerCandidate(
    val baseUrl: String,
    val latencyMs: Long,
    val source: String
)
