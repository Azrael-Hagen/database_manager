package com.phantom.app.web

import android.Manifest
import android.content.pm.PackageManager
import android.webkit.ConsoleMessage
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat

class PhantomWebChromeClient(
    private val activity: AppCompatActivity,
    private val trustedBaseUrlProvider: () -> String?,
    private val currentPageUrlProvider: () -> String?,
    private val onCameraPermissionRequired: (PermissionRequest) -> Unit,
    private val onProgressChanged: (Int) -> Unit,
) : WebChromeClient() {

    override fun onPermissionRequest(request: PermissionRequest) {
        val requestsVideo = request.resources.contains(PermissionRequest.RESOURCE_VIDEO_CAPTURE)
        if (!requestsVideo) {
            request.deny()
            return
        }

        val isTrusted = TrustedOriginPolicy.isTrustedPermissionRequest(
            requestOrigin = request.origin.toString(),
            currentPageUrl = currentPageUrlProvider(),
            trustedBaseUrl = trustedBaseUrlProvider(),
        )
        if (!isTrusted) {
            request.deny()
            return
        }

        val hasCameraPermission = ContextCompat.checkSelfPermission(
            activity,
            Manifest.permission.CAMERA,
        ) == PackageManager.PERMISSION_GRANTED

        if (hasCameraPermission) {
            request.grant(arrayOf(PermissionRequest.RESOURCE_VIDEO_CAPTURE))
        } else {
            onCameraPermissionRequired(request)
        }
    }

    override fun onConsoleMessage(consoleMessage: ConsoleMessage): Boolean {
        return super.onConsoleMessage(consoleMessage)
    }

    override fun onProgressChanged(view: android.webkit.WebView?, newProgress: Int) {
        onProgressChanged(newProgress)
        super.onProgressChanged(view, newProgress)
    }
}