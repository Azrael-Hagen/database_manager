package com.phantom.app.web

import android.webkit.WebSettings
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PhantomWebLoadPolicyTest {

    @Test
    fun buildMobilePanelUrl_appendsMobileRouteToTrustedOrigin() {
        val resolved = PhantomWebLoadPolicy.buildMobilePanelUrl("http://192.168.1.20:8000/dashboard")

        assertEquals("http://192.168.1.20:8000/m", resolved)
    }

    @Test
    fun buildMobilePanelUrl_returnsNullForInvalidOrigin() {
        assertNull(PhantomWebLoadPolicy.buildMobilePanelUrl("ftp://192.168.1.20/app"))
    }

    @Test
    fun resolveCacheMode_prefersCacheWhenOfflineOrForced() {
        assertEquals(
            WebSettings.LOAD_CACHE_ELSE_NETWORK,
            PhantomWebLoadPolicy.resolveCacheMode(networkAvailable = false, forceCache = false)
        )
        assertEquals(
            WebSettings.LOAD_CACHE_ELSE_NETWORK,
            PhantomWebLoadPolicy.resolveCacheMode(networkAvailable = true, forceCache = true)
        )
        assertEquals(
            WebSettings.LOAD_DEFAULT,
            PhantomWebLoadPolicy.resolveCacheMode(networkAvailable = true, forceCache = false)
        )
    }

    @Test
    fun decodeEvaluatedHtml_unwrapsJavascriptStringPayload() {
        val decoded = PhantomWebLoadPolicy.decodeEvaluatedHtml("\"<html><body>ok</body></html>\"")

        assertEquals("<html><body>ok</body></html>", decoded)
    }

    @Test
    fun decodeEvaluatedHtml_returnsNullForEmptyPayload() {
        assertNull(PhantomWebLoadPolicy.decodeEvaluatedHtml("null"))
    }
}