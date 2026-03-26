package com.phantom.app.web

import org.junit.Assert.assertTrue
import org.junit.Test

class QrInjectionScriptBuilderTest {

    @Test
    fun build_includes_native_event_and_cache_assignment() {
        val script = QrInjectionScriptBuilder.build("https://host/qr?id=10")

        assertTrue(script.contains("phantom-native-qr-scan"))
        assertTrue(script.contains("__phantomNativeLastScan"))
        assertTrue(script.contains("qrScanCodigoManual"))
    }

    @Test
    fun build_escapes_special_characters() {
        val script = QrInjectionScriptBuilder.build("linea\"42\nnext")

        assertTrue(script.contains("\\\"42"))
        assertTrue(script.contains("\\nnext"))
    }
}