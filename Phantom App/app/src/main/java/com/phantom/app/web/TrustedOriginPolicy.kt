package com.phantom.app.web

import java.net.URI
import java.util.Locale

object TrustedOriginPolicy {

    fun normalizeBaseUrl(url: String?): String? {
        val origin = parseOrigin(url) ?: return null
        return origin.toUrlString()
    }

    fun isTrustedNavigation(candidateUrl: String?, trustedBaseUrl: String?): Boolean {
        val candidateOrigin = parseOrigin(candidateUrl) ?: return false
        val trustedOrigin = parseOrigin(trustedBaseUrl) ?: return false
        return candidateOrigin == trustedOrigin
    }

    fun isTrustedPermissionRequest(
        requestOrigin: String?,
        currentPageUrl: String?,
        trustedBaseUrl: String?,
    ): Boolean {
        val request = parseOrigin(requestOrigin) ?: return false
        val current = parseOrigin(currentPageUrl) ?: return false
        val trusted = parseOrigin(trustedBaseUrl) ?: return false
        return request == trusted && current == trusted
    }

    private fun parseOrigin(url: String?): Origin? {
        val raw = url?.trim().orEmpty()
        if (raw.isEmpty()) return null

        return try {
            val uri = URI(raw)
            val scheme = uri.scheme?.lowercase(Locale.ROOT) ?: return null
            if (scheme != "http" && scheme != "https") return null
            val host = uri.host?.lowercase(Locale.ROOT) ?: return null
            val port = when {
                uri.port > 0 -> uri.port
                scheme == "https" -> 443
                else -> 80
            }
            Origin(scheme = scheme, host = host, port = port)
        } catch (_: Exception) {
            null
        }
    }

    private data class Origin(
        val scheme: String,
        val host: String,
        val port: Int,
    ) {
        fun toUrlString(): String {
            val defaultPort = (scheme == "https" && port == 443) || (scheme == "http" && port == 80)
            return if (defaultPort) {
                "$scheme://$host"
            } else {
                "$scheme://$host:$port"
            }
        }
    }
}