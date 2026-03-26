package com.phantom.app.web

object QrInjectionScriptBuilder {

    fun build(decodedValue: String): String {
        val escapedValue = escapeForJavaScript(decodedValue)
        return """
            (function() {
                const phantomCode = $escapedValue;
                window.__phantomNativeLastScan = phantomCode;
                const manualInput = document.getElementById('qrScanCodigoManual');
                if (manualInput) {
                    manualInput.value = phantomCode;
                }
                try {
                    window.dispatchEvent(new CustomEvent('phantom-native-qr-scan', {
                        detail: { code: phantomCode, source: 'native-android' }
                    }));
                } catch (_) {
                    return 'queued';
                }
                return 'dispatched';
            })();
        """.trimIndent()
    }

    private fun escapeForJavaScript(value: String): String {
        val escaped = buildString(value.length + 8) {
            value.forEach { character ->
                when (character) {
                    '\\' -> append("\\\\")
                    '"' -> append("\\\"")
                    '\n' -> append("\\n")
                    '\r' -> append("\\r")
                    '\t' -> append("\\t")
                    '\u2028' -> append("\\u2028")
                    '\u2029' -> append("\\u2029")
                    else -> append(character)
                }
            }
        }
        return "\"$escaped\""
    }
}