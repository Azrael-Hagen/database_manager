package com.phantom.app.web

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class TrustedOriginPolicyTest {

    @Test
    fun normalizeBaseUrl_removesPathAndUsesDefaultPort() {
        val normalized = TrustedOriginPolicy.normalizeBaseUrl("http://192.168.1.20:80/dashboard")

        assertEquals("http://192.168.1.20", normalized)
    }

    @Test
    fun isTrustedNavigation_requiresExactOrigin() {
        assertTrue(TrustedOriginPolicy.isTrustedNavigation("http://192.168.1.20:8000/qr", "http://192.168.1.20:8000"))
        assertFalse(TrustedOriginPolicy.isTrustedNavigation("http://192.168.1.20:9000/qr", "http://192.168.1.20:8000"))
        assertFalse(TrustedOriginPolicy.isTrustedNavigation("https://192.168.1.20/qr", "http://192.168.1.20"))
    }

    @Test
    fun isTrustedPermissionRequest_requires_request_and_page_match_trusted_origin() {
        assertTrue(
            TrustedOriginPolicy.isTrustedPermissionRequest(
                requestOrigin = "http://192.168.1.20:8000",
                currentPageUrl = "http://192.168.1.20:8000/qr",
                trustedBaseUrl = "http://192.168.1.20:8000",
            )
        )

        assertFalse(
            TrustedOriginPolicy.isTrustedPermissionRequest(
                requestOrigin = "http://evil.local:8000",
                currentPageUrl = "http://192.168.1.20:8000/qr",
                trustedBaseUrl = "http://192.168.1.20:8000",
            )
        )
    }
}