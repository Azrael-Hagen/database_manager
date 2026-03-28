package com.phantom.app.web

import android.graphics.Bitmap
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient

class PhantomWebViewClient(
    private val trustedBaseUrlProvider: () -> String?,
    private val onPageReady: (String) -> Unit,
    private val onNavigationBlocked: (String) -> Unit,
    private val onStatusUpdate: (String) -> Unit,
    private val onPageError: (String) -> Unit,
) : WebViewClient() {

    override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
        val targetUrl = request?.url?.toString().orEmpty()
        if (targetUrl.isBlank() || request?.isForMainFrame != true) {
            return false
        }
        return if (TrustedOriginPolicy.isTrustedNavigation(targetUrl, trustedBaseUrlProvider())) {
            false
        } else {
            onNavigationBlocked(targetUrl)
            true
        }
    }

    override fun onPageStarted(view: WebView?, url: String?, favicon: Bitmap?) {
        super.onPageStarted(view, url, favicon)
        onStatusUpdate("Conectando con el panel...")
    }

    override fun onPageFinished(view: WebView?, url: String?) {
        super.onPageFinished(view, url)
        val loadedUrl = url.orEmpty()
        if (TrustedOriginPolicy.isTrustedNavigation(loadedUrl, trustedBaseUrlProvider())) {
            onPageReady(loadedUrl)
        }
    }

    override fun onReceivedError(
        view: WebView?,
        request: WebResourceRequest?,
        error: WebResourceError?,
    ) {
        super.onReceivedError(view, request, error)
        if (request?.isForMainFrame == true) {
            onPageError("No se pudo cargar el servidor: ${error?.description ?: "error desconocido"}")
        }
    }

    override fun onReceivedHttpError(
        view: WebView?,
        request: WebResourceRequest?,
        errorResponse: WebResourceResponse?,
    ) {
        super.onReceivedHttpError(view, request, errorResponse)
        if (request?.isForMainFrame == true) {
            onPageError("Respuesta HTTP inválida del servidor: ${errorResponse?.statusCode ?: 0}")
        }
    }
}