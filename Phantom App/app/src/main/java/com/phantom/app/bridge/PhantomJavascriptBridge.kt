package com.phantom.app.bridge

import android.webkit.JavascriptInterface

class PhantomJavascriptBridge(
    private val onStartNativeQrScan: () -> Unit,
) {

    @JavascriptInterface
    fun startNativeQrScan() {
        onStartNativeQrScan()
    }

    @JavascriptInterface
    fun isNativeScannerAvailable(): Boolean = true
}