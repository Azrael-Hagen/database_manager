package com.phantom.app.web

import android.webkit.WebSettings

object PhantomWebLoadPolicy {

    fun buildMobilePanelUrl(baseUrl: String?): String? {
        val normalized = TrustedOriginPolicy.normalizeBaseUrl(baseUrl) ?: return null
        return "$normalized/m"
    }

    fun resolveCacheMode(networkAvailable: Boolean, forceCache: Boolean): Int {
        return if (forceCache || !networkAvailable) {
            WebSettings.LOAD_CACHE_ELSE_NETWORK
        } else {
            WebSettings.LOAD_DEFAULT
        }
    }

    fun decodeEvaluatedHtml(raw: String?): String? {
        val payload = raw?.trim().orEmpty()
        if (payload.isEmpty() || payload == "null" || payload == "undefined") {
            return null
        }

        val normalized = payload
            .removeSurrounding("\"")
            .replace("\\u003C", "<")
            .replace("\\u003E", ">")
            .replace("\\u0026", "&")
            .replace("\\u003D", "=")
            .replace("\\/", "/")
            .replace("\\n", "\n")
            .replace("\\t", "\t")
            .replace("\\\"", "\"")
            .replace("\\\\", "\\")

        return normalized.takeIf { it.isNotBlank() }
    }
}